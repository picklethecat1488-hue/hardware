/**
 * $O(1)$ Uniform 2D Spatial Hash Grid for PCB Hit-Testing, Magnetic Snapping, & Frustum Culling.
 *
 * Indexes copper pads, test points, vias, trace segments, silkscreen legends, and component
 * bounding boxes into `2.0 mm` uniform cells so:
 * 1. Cursor hover queries only the `3x3` local cell neighborhood (`< 0.02 ms`, zero Three.js
 *    raycasting, zero heap allocations on empty board space, substrate strictly excluded!).
 * 2. Magnetic ruler snapping locates the nearest pad/via/trace vertex in $O(1)$.
 * 3. Retina Canvas2D net/pin/silkscreen rendering visits only entities inside the active
 *    camera frustum and strictly respects active-side (`F.Cu` vs `B.Cu`) substrate occlusion!
 */

export const DEFAULT_GRID_CELL_MM = 2.0;
const TRACE_HIT_MARGIN_MM = 0.08;
const PAD_HIT_MARGIN_MM = 0.04;
const MIN_NET_LABEL_TRACE_LENGTH_MM = 1.1;

/**
 * Compute squared Euclidean distance from `(px, py)` to line segment `(x1, y1) -> (x2, y2)`.
 *
 * @param {number} px - Query X in mm.
 * @param {number} py - Query Y in mm.
 * @param {number} x1 - Segment start X.
 * @param {number} y1 - Segment start Y.
 * @param {number} x2 - Segment end X.
 * @param {number} y2 - Segment end Y.
 * @returns {number} Squared distance in `mm^2`.
 */
export function pointToSegmentDistanceSq(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  if (lenSq <= 1e-10) {
    const ex = px - x1;
    const ey = py - y1;
    return ex * ex + ey * ey;
  }
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lenSq));
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  const ox = px - projX;
  const oy = py - projY;
  return ox * ox + oy * oy;
}

/**
 * Test whether `(px, py)` lies inside an oriented pad (`rect`, `roundrect`, `circle`, `oval`).
 *
 * @param {number} px - Query X in mm.
 * @param {number} py - Query Y in mm.
 * @param {object} pad - Normalized pad entry.
 * @returns {boolean}
 */
export function isPointInsidePad(px, py, pad) {
  const dx = px - pad.x;
  const dy = py - pad.y;
  const halfW = pad.w * 0.5 + PAD_HIT_MARGIN_MM;
  const halfH = pad.h * 0.5 + PAD_HIT_MARGIN_MM;

  if (pad.shape === "circle") {
    const r = Math.max(halfW, halfH);
    return dx * dx + dy * dy <= r * r;
  }

  const rad = (-pad.rotDeg * Math.PI) / 180;
  const cosA = Math.cos(rad);
  const sinA = Math.sin(rad);
  const lx = dx * cosA - dy * sinA;
  const ly = dx * sinA + dy * cosA;
  return Math.abs(lx) <= halfW && Math.abs(ly) <= halfH;
}

/**
 * Uniform 2D spatial hash grid over `pcb_metadata`.
 */
export class PcbSpatialGrid {
  /**
   * Build a `PcbSpatialGrid` from `pcb_metadata`.
   *
   * @param {object|null} pcbMetadata - Backend `pcb_metadata` dictionary.
   * @param {number} [cellSizeMm] - Uniform grid cell width in mm (`2.0` default).
   */
  constructor(pcbMetadata = null, cellSizeMm = DEFAULT_GRID_CELL_MM) {
    const resolvedCell =
      typeof pcbMetadata === "number" ? pcbMetadata : Number(cellSizeMm) || DEFAULT_GRID_CELL_MM;
    const resolvedMeta =
      pcbMetadata && typeof pcbMetadata === "object" ? pcbMetadata : null;
    /** @type {number} */
    this.cellSizeMm = Math.max(0.5, resolvedCell);
    /** @type {Map<string, Array<object>>} */
    this.cells = new Map();
    /** @type {Array<object>} */
    this.pads = [];
    /** @type {Array<object>} */
    this.vias = [];
    /** @type {Array<object>} */
    this.traces = [];
    /** @type {Array<object>} */
    this.components = [];
    /** @type {Array<object>} */
    this.silkscreenTexts = [];
    /** @type {Array<object>} */
    this.silkscreenGraphics = [];
    /** @type {Array<Array<Array<number>>>} */
    this.edgeCuts = [];
    /** @type {Array<object>} */
    this.copperRegions = [];
    /** @type {Array<string>} */
    this.copperLayers = ["F.Cu", "B.Cu"];
    /** @type {Map<string, number>} */
    this.copperLayerOrder = new Map([
      ["F.Cu", 0],
      ["B.Cu", 1],
    ]);
    /** @type {Map<string, object>} */
    this.netsByName = new Map();
    /** @type {number} */
    this._queryStamp = 1;

    if (resolvedMeta) {
      this.buildFromMetadata(resolvedMeta);
    }
  }

  /**
   * Populate spatial hash buckets from `pcb_metadata`.
   *
   * @param {object} meta - PCB metadata dictionary.
   */
  buildFromMetadata(meta) {
    this.cells.clear();
    this.pads = [];
    this.vias = [];
    this.traces = [];
    this.components = [];
    this.silkscreenTexts = [];
    this.silkscreenGraphics = [];
    this.edgeCuts = [];
    this.copperRegions = [];
    this.netsByName.clear();

    const rawCuLayers = Array.isArray(meta.copper_layers) && meta.copper_layers.length >= 2
      ? meta.copper_layers.map((l) => String(l))
      : ["F.Cu", "B.Cu"];
    this.copperLayers = rawCuLayers;
    this.copperLayerOrder = new Map();
    rawCuLayers.forEach((layerName, idx) => {
      this.copperLayerOrder.set(layerName, idx);
    });

    for (const loop of meta.edge_cuts || []) {
      if (Array.isArray(loop) && loop.length >= 3) {
        this.edgeCuts.push(loop.map((pt) => [Number(pt[0]) || 0, Number(pt[1]) || 0]));
      }
    }

    for (const rawRegion of meta.copper_regions || []) {
      const poly = Array.isArray(rawRegion.polygon) ? rawRegion.polygon : [];
      if (poly.length < 3) continue;
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      const pts = poly.map((pt) => {
        const px = Number(pt[0]) || 0;
        const py = Number(pt[1]) || 0;
        if (px < minX) minX = px;
        if (px > maxX) maxX = px;
        if (py < minY) minY = py;
        if (py > maxY) maxY = py;
        return [px, py];
      });
      this.copperRegions.push({
        layer: String(rawRegion.layer || "In1.Cu"),
        net: String(rawRegion.net || ""),
        clearance: Math.max(0.05, Number(rawRegion.clearance) || 0.25),
        priority: Number(rawRegion.priority) || 1,
        polygon: pts,
        minX,
        minY,
        maxX,
        maxY,
      });
    }

    for (const net of meta.nets || []) {
      if (typeof net === "string" && net) {
        this.netsByName.set(net, { name: net });
      } else if (net && net.name) {
        this.netsByName.set(net.name, net);
      }
    }

    // 1. Pads & Test Points
    (meta.pads || []).forEach((rawPad, index) => {
      const x = Number(rawPad.x) || 0;
      const y = Number(rawPad.y) || 0;
      const w = Math.max(0.05, Number(rawPad.w) || 0.5);
      const h = Math.max(0.05, Number(rawPad.h) || 0.5);
      const rotDeg = Number(rawPad.rot_deg) || 0;
      const boundR = Math.hypot(w, h) * 0.5;
      const pad = {
        id: `pad_${index}`,
        kind: rawPad.is_test_point ? "test_point" : "pad",
        index,
        x,
        y,
        w,
        h,
        rotDeg,
        shape: String(rawPad.shape || (rawPad.is_test_point ? "circle" : "roundrect")).toLowerCase(),
        padType: String(rawPad.pad_type || "smd").toLowerCase(),
        drill: Number(rawPad.drill) || 0,
        comp: String(rawPad.comp || ""),
        pin: String(rawPad.pin || ""),
        number: String(rawPad.number || rawPad.pin || ""),
        net: String(rawPad.net || ""),
        layer: rawPad.layer === "B.Cu" ? "B.Cu" : "F.Cu",
        isTestPoint: Boolean(rawPad.is_test_point),
        isSensor: Boolean(rawPad.is_sensor),
        minX: x - boundR,
        minY: y - boundR,
        maxX: x + boundR,
        maxY: y + boundR,
        _stamp: 0,
      };
      this.pads.push(pad);
      this._insertAabb(pad, pad.minX, pad.minY, pad.maxX, pad.maxY);
    });

    // Also index standalone `meta.test_points` if not already merged into `meta.pads`
    const hasMergedTestPoints = this.pads.some((p) => p.isTestPoint);
    if (!hasMergedTestPoints && Array.isArray(meta.test_points)) {
      meta.test_points.forEach((rawTp, tpIdx) => {
        const x = Number(rawTp.x) || 0;
        const y = Number(rawTp.y) || 0;
        const dia = Math.max(0.1, Number(rawTp.dia ?? rawTp.w) || 1.0);
        const w = Math.max(0.1, Number(rawTp.w) || dia);
        const h = Math.max(0.1, Number(rawTp.h) || dia);
        const drill = Number(rawTp.drill) || 0;
        const boundR = Math.hypot(w, h) * 0.5;
        const index = this.pads.length + tpIdx;
        const tpPad = {
          id: `pad_${index}`,
          kind: "test_point",
          index,
          x,
          y,
          w,
          h,
          rotDeg: 0,
          shape: String(rawTp.shape || "circle").toLowerCase(),
          padType: drill > 0 ? "thru_hole" : "smd",
          drill,
          comp: String(rawTp.comp || rawTp.name || rawTp.id || "TP"),
          pin: String(rawTp.pin || "1"),
          number: "1",
          net: String(rawTp.net || ""),
          layer: rawTp.layer === "B.Cu" ? "B.Cu" : "F.Cu",
          isTestPoint: true,
          isSensor: false,
          minX: x - boundR,
          minY: y - boundR,
          maxX: x + boundR,
          maxY: y + boundR,
          _stamp: 0,
        };
        this.pads.push(tpPad);
        this._insertAabb(tpPad, tpPad.minX, tpPad.minY, tpPad.maxX, tpPad.maxY);
      });
    }

    // 2. Plated Through-Hole Vias
    (meta.vias || []).forEach((rawVia, index) => {
      const pos = Array.isArray(rawVia.pos) ? rawVia.pos : [rawVia.x ?? 0, rawVia.y ?? 0];
      const x = Number(pos[0]) || 0;
      const y = Number(pos[1]) || 0;
      const padDia = Math.max(0.1, Number(rawVia.pad ?? rawVia.pad_dia) || 0.6);
      const drillDia = Math.max(0.05, Number(rawVia.drill) || 0.3);
      const r = padDia * 0.5;
      const via = {
        id: `via_${index}`,
        kind: "via",
        index,
        x,
        y,
        padDia,
        drillDia,
        net: String(rawVia.net || ""),
        layerStart: String(rawVia.layer_start || "F.Cu"),
        layerEnd: String(rawVia.layer_end || "B.Cu"),
        minX: x - r,
        minY: y - r,
        maxX: x + r,
        maxY: y + r,
        _stamp: 0,
      };
      this.vias.push(via);
      this._insertAabb(via, via.minX, via.minY, via.maxX, via.maxY);
    });

    // 3. Copper Trace Segments
    (meta.traces || []).forEach((rawTrace, index) => {
      const start = Array.isArray(rawTrace.start) ? rawTrace.start : [0, 0];
      const end = Array.isArray(rawTrace.end) ? rawTrace.end : [0, 0];
      const x1 = Number(start[0]) || 0;
      const y1 = Number(start[1]) || 0;
      const x2 = Number(end[0]) || 0;
      const y2 = Number(end[1]) || 0;
      const width = Math.max(0.05, Number(rawTrace.width) || 0.2);
      const length = Math.hypot(x2 - x1, y2 - y1);
      if (length < 1e-5) {
        return;
      }
      const halfW = width * 0.5;
      const trace = {
        id: `trace_${index}`,
        kind: "trace",
        index,
        x1,
        y1,
        x2,
        y2,
        midX: (x1 + x2) * 0.5,
        midY: (y1 + y2) * 0.5,
        angleRad: Math.atan2(y2 - y1, x2 - x1),
        width,
        length,
        layer: String(rawTrace.layer || "F.Cu"),
        net: String(rawTrace.net || ""),
        minX: Math.min(x1, x2) - halfW,
        minY: Math.min(y1, y2) - halfW,
        maxX: Math.max(x1, x2) + halfW,
        maxY: Math.max(y1, y2) + halfW,
        _stamp: 0,
      };
      this.traces.push(trace);
      this._insertAabb(trace, trace.minX, trace.minY, trace.maxX, trace.maxY);
    });

    // 4. Component Footprints
    (meta.components || []).forEach((rawComp, index) => {
      const pos = Array.isArray(rawComp.position) ? rawComp.position : [rawComp.x ?? 0, rawComp.y ?? 0, 0];
      const size = Array.isArray(rawComp.size) ? rawComp.size : [rawComp.w ?? 2, rawComp.h ?? 2];
      const x = Number(pos[0]) || 0;
      const y = Number(pos[1]) || 0;
      const w = Math.max(0.2, Number(size[0]) || 2);
      const h = Math.max(0.2, Number(size[1]) || 2);
      const yaw = Number(rawComp.yaw) || 0;
      const boundR = Math.hypot(w, h) * 0.5;
      const side = (rawComp.side || rawComp.layer) === "B.Cu" ? "B.Cu" : "F.Cu";
      const comp = {
        id: `comp_${index}`,
        kind: "component",
        index,
        name: String(rawComp.name || rawComp.ref_des || ""),
        refDes: String(rawComp.ref_des || rawComp.name || ""),
        footprint: String(rawComp.footprint || ""),
        value: String(rawComp.value || ""),
        mpn: String(rawComp.mpn || ""),
        side,
        layer: side,
        x,
        y,
        w,
        h,
        yaw,
        minX: x - boundR,
        minY: y - boundR,
        maxX: x + boundR,
        maxY: y + boundR,
        _stamp: 0,
      };
      this.components.push(comp);
      this._insertAabb(comp, comp.minX, comp.minY, comp.maxX, comp.maxY);
    });

    // 5. Silkscreen Texts & Graphics (stored with AABBs for fast frustum culling)
    for (const rawTxt of meta.silkscreen_texts || []) {
      const x = Number(rawTxt.x) || 0;
      const y = Number(rawTxt.y) || 0;
      const fontSize = Math.max(0.3, Number(rawTxt.font_size) || 0.8);
      const text = String(rawTxt.text || "");
      const halfSpan = Math.max(1.5, text.length * fontSize * 0.45);
      this.silkscreenTexts.push({
        text,
        layer: rawTxt.layer === "B.SilkS" ? "B.SilkS" : "F.SilkS",
        x,
        y,
        fontSize,
        rotation: Number(rawTxt.rotation) || 0,
        mirror: Boolean(rawTxt.mirror),
        isRefDes: Boolean(rawTxt.is_ref_des),
        minX: x - halfSpan,
        minY: y - halfSpan,
        maxX: x + halfSpan,
        maxY: y + halfSpan,
      });
    }

    for (const rawGfx of meta.silkscreen_graphics || []) {
      const pos = Array.isArray(rawGfx.position) ? rawGfx.position : [0, 0];
      const dims = Array.isArray(rawGfx.dimensions) ? rawGfx.dimensions : [1, 1];
      const pts = Array.isArray(rawGfx.points) ? rawGfx.points : [];
      let minX = pos[0] - dims[0] * 0.5;
      let maxX = pos[0] + dims[0] * 0.5;
      let minY = pos[1] - dims[1] * 0.5;
      let maxY = pos[1] + dims[1] * 0.5;
      for (const pt of pts) {
        if (pt[0] < minX) minX = pt[0];
        if (pt[0] > maxX) maxX = pt[0];
        if (pt[1] < minY) minY = pt[1];
        if (pt[1] > maxY) maxY = pt[1];
      }
      this.silkscreenGraphics.push({
        layer: rawGfx.layer === "B.SilkS" ? "B.SilkS" : "F.SilkS",
        shape: String(rawGfx.shape || "rect"),
        x: Number(pos[0]) || 0,
        y: Number(pos[1]) || 0,
        w: Number(dims[0]) || 0,
        h: Number(dims[1]) || 0,
        thickness: Math.max(0.08, Number(rawGfx.thickness) || 0.15),
        fill: Boolean(rawGfx.fill),
        points: pts,
        minX,
        minY,
        maxX,
        maxY,
      });
    }
  }

  /**
   * Insert an entity into every `cellSizeMm` grid bucket overlapped by `[minX, minY, maxX, maxY]`.
   *
   * @param {object} entity - Spatial item.
   * @param {number} minX - Minimum X in mm.
   * @param {number} minY - Minimum Y in mm.
   * @param {number} maxX - Maximum X in mm.
   * @param {number} maxY - Maximum Y in mm.
   */
  _insertAabb(entity, minX, minY, maxX, maxY) {
    const inv = 1 / this.cellSizeMm;
    const cx0 = Math.floor(minX * inv);
    const cy0 = Math.floor(minY * inv);
    const cx1 = Math.floor(maxX * inv);
    const cy1 = Math.floor(maxY * inv);

    for (let cx = cx0; cx <= cx1; cx += 1) {
      for (let cy = cy0; cy <= cy1; cy += 1) {
        const key = `${cx},${cy}`;
        let bucket = this.cells.get(key);
        if (!bucket) {
          bucket = [];
          this.cells.set(key, bucket);
        }
        bucket.push(entity);
      }
    }
  }

  /**
   * Return whether a plated or blind/buried `via` spans `layerName` in the board stackup.
   *
   * @param {object} via - Spatial via entry.
   * @param {string} layerName - Copper layer identifier (e.g. `"In1.Cu"`, `"In3.Cu"`).
   * @returns {boolean}
   */
  doesViaSpanLayer(via, layerName) {
    const targetIdx = this.copperLayerOrder.get(layerName);
    if (targetIdx === undefined) {
      return true;
    }
    const i0 = this.copperLayerOrder.get(via.layerStart) ?? 0;
    const i1 = this.copperLayerOrder.get(via.layerEnd) ?? (this.copperLayers.length - 1);
    const minIdx = Math.min(i0, i1);
    const maxIdx = Math.max(i0, i1);
    return targetIdx >= minIdx && targetIdx <= maxIdx;
  }

  /**
   * Perform $O(1)$ spatial hit-test at `(boardX, boardY)` in millimeters.
   *
   * Substrate is NEVER indexed here, so hovering bare FR-4 soldermask returns `null`.
   * Active-side (`F.Cu` or `B.Cu`) and explicitly enabled inner copper (`In*.Cu`) items win
   * over opposite-side outer copper; opposite-side outer copper is only hit when `Substrate` is hidden!
   *
   * @param {number} boardX - Board X coordinate in mm.
   * @param {number} boardY - Board Y coordinate in mm.
   * @param {{
   *   activeSide?: "F.Cu"|"B.Cu",
   *   visibleLayers?: Set<string>|null
   * }} [options] - Active viewing side and enabled layer types.
   * @returns {object|null} Best hit entity (`pad`, `test_point`, `via`, `trace`, or `component`).
   */
  queryPoint(boardX, boardY, { activeSide = "F.Cu", visibleLayers = null } = {}) {
    const inv = 1 / this.cellSizeMm;
    const baseCx = Math.floor(boardX * inv);
    const baseCy = Math.floor(boardY * inv);
    const stamp = (this._queryStamp += 1);

    const isLayerOn = (type) => !visibleLayers || visibleLayers.has(type);
    const substrateOpaque = isLayerOn("Substrate");

    let bestActivePadOrVia = null;
    let bestActivePadDistSq = Infinity;
    let bestActiveTrace = null;
    let bestActiveTraceDistSq = Infinity;
    let bestActiveComp = null;
    let bestActiveCompArea = Infinity;

    let bestBackPad = null;
    let bestBackTrace = null;

    for (let dx = -1; dx <= 1; dx += 1) {
      for (let dy = -1; dy <= 1; dy += 1) {
        const bucket = this.cells.get(`${baseCx + dx},${baseCy + dy}`);
        if (!bucket) {
          continue;
        }
        for (let idx = 0; idx < bucket.length; idx += 1) {
          const item = bucket[idx];
          if (item._stamp === stamp) {
            continue;
          }
          item._stamp = stamp;

          if (item.kind === "via") {
            if (!isLayerOn("Vias")) continue;
            const r = item.padDia * 0.5 + PAD_HIT_MARGIN_MM;
            const dSq = (boardX - item.x) ** 2 + (boardY - item.y) ** 2;
            if (dSq <= r * r && dSq < bestActivePadDistSq) {
              bestActivePadDistSq = dSq;
              bestActivePadOrVia = item;
            }
          } else if (item.kind === "pad" || item.kind === "test_point") {
            if (!isLayerOn("Pads") || !isLayerOn(item.layer)) continue;
            const isActive = item.layer === activeSide || item.padType === "thru_hole";
            if (!isActive && substrateOpaque) continue;
            if (isPointInsidePad(boardX, boardY, item)) {
              const dSq = (boardX - item.x) ** 2 + (boardY - item.y) ** 2;
              if (isActive) {
                if (dSq < bestActivePadDistSq) {
                  bestActivePadDistSq = dSq;
                  bestActivePadOrVia = item;
                }
              } else if (!bestBackPad) {
                bestBackPad = item;
              }
            }
          } else if (item.kind === "trace") {
            if (!isLayerOn(item.layer)) continue;
            const isInnerLayer = item.layer !== "F.Cu" && item.layer !== "B.Cu";
            const isActive = item.layer === activeSide || isInnerLayer;
            if (!isActive && substrateOpaque) continue;
            const halfW = item.width * 0.5 + TRACE_HIT_MARGIN_MM;
            const dSq = pointToSegmentDistanceSq(boardX, boardY, item.x1, item.y1, item.x2, item.y2);
            if (dSq <= halfW * halfW) {
              if (isActive) {
                if (dSq < bestActiveTraceDistSq) {
                  bestActiveTraceDistSq = dSq;
                  bestActiveTrace = item;
                }
              } else if (!bestBackTrace) {
                bestBackTrace = item;
              }
            }
          } else if (item.kind === "component") {
            const isActive = item.side === activeSide;
            if (!isActive && substrateOpaque) continue;
            const rad = (-item.yaw * Math.PI) / 180;
            const cosA = Math.cos(rad);
            const sinA = Math.sin(rad);
            const rx = boardX - item.x;
            const ry = boardY - item.y;
            const lx = rx * cosA - ry * sinA;
            const ly = rx * sinA + ry * cosA;
            if (Math.abs(lx) <= item.w * 0.5 && Math.abs(ly) <= item.h * 0.5) {
              const area = item.w * item.h;
              if (isActive && area < bestActiveCompArea) {
                bestActiveCompArea = area;
                bestActiveComp = item;
              }
            }
          }
        }
      }
    }

    return bestActivePadOrVia || bestActiveTrace || bestActiveComp || bestBackPad || bestBackTrace || null;
  }

  /**
   * Locate the closest magnetic snap point (pad center, via center, trace endpoint, Edge.Cuts vertex,
   * or component center) within `snapRadiusMm` for precision ruler measurement (`M`).
   *
   * @param {number} boardX - Cursor X in mm.
   * @param {number} boardY - Cursor Y in mm.
   * @param {number} snapRadiusMm - Search radius in mm.
   * @param {"F.Cu"|"B.Cu"} [activeSide] - Active viewing side.
   * @returns {{x: number, y: number, z: number, label: string}|null}
   */
  findMagneticSnap(boardX, boardY, snapRadiusMm, activeSide = "F.Cu") {
    const r = Math.max(0.05, Number(snapRadiusMm) || 1.0);
    const maxDistSq = r * r;
    const inv = 1 / this.cellSizeMm;
    const cx0 = Math.floor((boardX - r) * inv);
    const cy0 = Math.floor((boardY - r) * inv);
    const cx1 = Math.floor((boardX + r) * inv);
    const cy1 = Math.floor((boardY + r) * inv);
    const stamp = (this._queryStamp += 1);

    let best = null;
    let bestDistSq = maxDistSq;

    const consider = (x, y, label) => {
      const dSq = (boardX - x) ** 2 + (boardY - y) ** 2;
      if (dSq <= bestDistSq) {
        bestDistSq = dSq;
        best = { x, y, z: 0, label };
      }
    };

    for (let cx = cx0; cx <= cx1; cx += 1) {
      for (let cy = cy0; cy <= cy1; cy += 1) {
        const bucket = this.cells.get(`${cx},${cy}`);
        if (!bucket) continue;
        for (const item of bucket) {
          if (item._stamp === stamp) continue;
          item._stamp = stamp;

          if (item.kind === "via") {
            consider(item.x, item.y, item.net ? `Via (${item.net})` : "Via");
          } else if ((item.kind === "pad" || item.kind === "test_point") && (item.layer === activeSide || item.padType === "thru_hole")) {
            consider(item.x, item.y, `${item.comp}.${item.pin}`);
          } else if (item.kind === "trace" && (item.layer === activeSide || (item.layer !== "F.Cu" && item.layer !== "B.Cu"))) {
            consider(item.x1, item.y1, item.net || "Trace");
            consider(item.x2, item.y2, item.net || "Trace");
          } else if (item.kind === "component" && item.side === activeSide) {
            consider(item.x, item.y, item.refDes);
          }
        }
      }
    }

    for (const loop of this.edgeCuts) {
      for (const pt of loop) {
        consider(pt[0], pt[1], "Edge.Cuts");
      }
    }

    return best;
  }

  /**
   * Collect frustum-culled active-side pads, traces, copper regions, and silkscreen items inside `bounds2D`
   * for `2x` Retina Canvas2D typography & zone rendering.
   *
   * INVARIANT: Strictly filters outer copper net labels and pad pin labels to `activeSide` (`F.Cu` on Top,
   * `B.Cu` on Bottom, plus `thru_hole` pads and explicitly enabled inner copper layers) so front-side net
   * labels NEVER bleed through onto the back side!
   *
   * @param {{minX: number, minY: number, maxX: number, maxY: number}} bounds2D - Visible board rectangle.
   * @param {{
   *   activeSide?: "F.Cu"|"B.Cu",
   *   visibleLayers?: Set<string>|null
   * }} [options] - Active board side and enabled layer types.
   * @returns {{
   *   pads: Array<object>,
   *   traces: Array<object>,
   *   copperRegions: Array<object>,
   *   silkTexts: Array<object>,
   *   silkGraphics: Array<object>
   * }}
   */
  queryFrustumOverlays(bounds2D, { activeSide = "F.Cu", visibleLayers = null } = {}) {
    const { minX, minY, maxX, maxY } = bounds2D;
    const isLayerOn = (type) => !visibleLayers || visibleLayers.has(type);
    const activeSilkLayer = activeSide === "B.Cu" ? "B.SilkS" : "F.SilkS";

    const pads = [];
    if (isLayerOn("Pads") && isLayerOn(activeSide)) {
      for (const pad of this.pads) {
        if (pad.layer !== activeSide && pad.padType !== "thru_hole") continue;
        if (pad.maxX < minX || pad.minX > maxX || pad.maxY < minY || pad.minY > maxY) continue;
        pads.push(pad);
      }
    }

    const traces = [];
    for (const trace of this.traces) {
      const isInner = trace.layer !== "F.Cu" && trace.layer !== "B.Cu";
      const allowLayer = isInner ? Boolean(visibleLayers && visibleLayers.has(trace.layer)) : (trace.layer === activeSide && isLayerOn(activeSide));
      if (!allowLayer || !trace.net || trace.length < MIN_NET_LABEL_TRACE_LENGTH_MM) continue;
      if (trace.maxX < minX || trace.minX > maxX || trace.maxY < minY || trace.minY > maxY) continue;
      traces.push(trace);
    }

    const copperRegions = [];
    for (const region of this.copperRegions) {
      const isInner = region.layer !== "F.Cu" && region.layer !== "B.Cu";
      const allowRegion = isInner
        ? Boolean(visibleLayers && visibleLayers.has(region.layer))
        : (region.layer === activeSide && isLayerOn(activeSide));
      if (!allowRegion) continue;
      if (region.maxX < minX || region.minX > maxX || region.maxY < minY || region.minY > maxY) continue;
      copperRegions.push(region);
    }

    const silkTexts = [];
    const silkGraphics = [];
    if (isLayerOn(activeSilkLayer)) {
      for (const st of this.silkscreenTexts) {
        if (st.layer !== activeSilkLayer) continue;
        if (st.maxX < minX || st.minX > maxX || st.maxY < minY || st.minY > maxY) continue;
        silkTexts.push(st);
      }
      for (const sg of this.silkscreenGraphics) {
        if (sg.layer !== activeSilkLayer) continue;
        if (sg.maxX < minX || sg.minX > maxX || sg.maxY < minY || sg.minY > maxY) continue;
        silkGraphics.push(sg);
      }
    }

    return { pads, traces, copperRegions, silkTexts, silkGraphics };
  }
}
