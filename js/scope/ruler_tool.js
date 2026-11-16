/**
 * World-Space Precision Ruler Tool (`M`) with Magnetic PCB/CAD Feature Snapping.
 *
 * Measures exact 3D Euclidean distance (`mm` + `mil`), component deltas (`dX`, `dY`, `dZ`),
 * and planar angle (`deg`), rendering crisp `2x` Retina graduated ticks, magnetic snap rings,
 * and a high-contrast engineering readout badge on `#markup-canvas`.
 */

const MILS_PER_MM = 39.37007874;
const RAD_TO_DEG = 180 / Math.PI;
const MAGNETIC_SNAP_CSS_PX = 14;
const TICK_SPACING_PX = 24;

/**
 * Compute engineering distance & angle metrics between two 3D points in millimeters.
 *
 * @param {{x: number, y: number, z?: number}} p1 - Start point in mm.
 * @param {{x: number, y: number, z?: number}} p2 - End point in mm.
 * @returns {{
 *   dxMm: number,
 *   dyMm: number,
 *   dzMm: number,
 *   planarMm: number,
 *   distanceMm: number,
 *   distanceMil: number,
 *   angleDeg: number
 * }}
 */
export function computeRulerMeasurement(p1, p2) {
  const z1 = Number(p1.z) || 0;
  const z2 = Number(p2.z) || 0;
  const dxMm = p2.x - p1.x;
  const dyMm = p2.y - p1.y;
  const dzMm = z2 - z1;
  const planarMm = Math.hypot(dxMm, dyMm);
  const distanceMm = Math.hypot(dxMm, dyMm, dzMm);
  const distanceMil = distanceMm * MILS_PER_MM;
  const angleDeg = Math.atan2(dyMm, dxMm) * RAD_TO_DEG;

  return {
    dxMm,
    dyMm,
    dzMm,
    planarMm,
    distanceMm,
    distanceMil,
    angleDeg,
  };
}

/**
 * Interactive world-space ruler controller (`M` toggle, `Shift` freehand override, `Esc` clear).
 */
export class PrecisionRulerTool {
  /**
   * Construct a `PrecisionRulerTool`.
   *
   * @param {object} [options] - Optional state change callback.
   * @param {function(): void} [options.onUpdate] - Invoked whenever ruler state changes.
   */
  constructor({ onUpdate = null } = {}) {
    /** @type {boolean} */
    this.active = false;
    /** @type {{x: number, y: number, z: number, label?: string}|null} */
    this.p1 = null;
    /** @type {{x: number, y: number, z: number, label?: string}|null} */
    this.p2 = null;
    /** @type {{x: number, y: number, z: number, label?: string, snapped?: boolean}|null} */
    this.hoverPoint = null;
    /** @type {function(): void|null} */
    this.onUpdate = onUpdate;
  }

  /**
   * Toggle ruler active mode (`M`).
   *
   * @param {boolean} [forceActive] - Optional explicit boolean.
   * @returns {boolean} Active state.
   */
  toggle(forceActive) {
    const next = typeof forceActive === "boolean" ? forceActive : !this.active;
    this.active = next;
    if (!next) {
      this.hoverPoint = null;
    }
    this._notify();
    return this.active;
  }

  /**
   * Clear active measurement points (`Escape`). Returns `true` if points or active state were cleared.
   *
   * @returns {boolean}
   */
  clearOrDeactivate() {
    if (this.p1 || this.p2) {
      this.p1 = null;
      this.p2 = null;
      this._notify();
      return true;
    }
    if (this.active) {
      this.active = false;
      this.hoverPoint = null;
      this._notify();
      return true;
    }
    return false;
  }

  /**
   * Resolve world-space cursor point with optional magnetic snapping (`!shiftKey`).
   *
   * @param {object} params - Cursor query parameters.
   * @param {number} params.ndcX - Normalized device X.
   * @param {number} params.ndcY - Normalized device Y.
   * @param {boolean} params.shiftKey - Whether `Shift` freehand override is held.
   * @param {string} params.mode - Active Scope mode (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`).
   * @param {import("./camera_controller.js").CadCameraController} params.cameraController - Camera controller.
   * @param {import("./pcb_renderer.js").PcbGpuRenderer|null} [params.pcbRenderer] - PCB renderer for magnetic snap.
   * @param {import("./cad_scene.js").CadSceneManager|null} [params.cadScene] - CAD scene for 3D surface raycast.
   * @returns {{x: number, y: number, z: number, label: string, snapped: boolean}|null}
   */
  resolveWorldPoint({ ndcX, ndcY, shiftKey = false, mode = "CAD", cameraController, pcbRenderer = null, cadScene = null }) {
    const upper = String(mode || "CAD").toUpperCase();

    if (upper === "PCB") {
      const planePt = cameraController.screenNdcToPlaneZ(ndcX, ndcY, 0);
      if (!planePt) return null;
      if (!shiftKey && pcbRenderer) {
        const snapRadiusMm = MAGNETIC_SNAP_CSS_PX * cameraController.getMillimetersPerCssPixel();
        const snap = pcbRenderer.spatialGrid.findMagneticSnap(
          planePt.x,
          planePt.y,
          snapRadiusMm,
          cameraController.activeBoardSide,
        );
        if (snap) {
          return { x: snap.x, y: snap.y, z: 0, label: snap.label, snapped: true };
        }
      }
      return { x: planePt.x, y: planePt.y, z: 0, label: "", snapped: false };
    }

    if (cadScene && upper !== "DIAGRAM") {
      const hit = cadScene.pickBrepFace(cameraController.activeCamera, ndcX, ndcY);
      if (hit && Array.isArray(hit.point)) {
        if (!shiftKey && hit.measurement && hit.face && (hit.face.surfaceType === "Cylinder" || hit.face.surfaceType === "Sphere")) {
          const [cx, cy, cz] = hit.measurement.centroid;
          return {
            x: cx,
            y: cy,
            z: cz,
            label: `${hit.face.surfaceType} Center`,
            snapped: true,
          };
        }
        return {
          x: hit.point[0],
          y: hit.point[1],
          z: hit.point[2],
          label: hit.partName || "",
          snapped: false,
        };
      }
    }

    const fallbackZ = cameraController.sceneBounds ? cameraController.sceneBounds.center[2] : 0;
    const planePt = cameraController.screenNdcToPlaneZ(ndcX, ndcY, upper === "DIAGRAM" ? 0 : fallbackZ);
    if (!planePt) return null;
    return { x: planePt.x, y: planePt.y, z: planePt.z, label: "", snapped: false };
  }

  /**
   * Handle pointer hover while ruler is active.
   *
   * @param {{x: number, y: number, z: number, label?: string, snapped?: boolean}|null} worldPoint - Resolved world point.
   */
  handleHover(worldPoint) {
    if (!this.active) return;
    this.hoverPoint = worldPoint;
    this._notify();
  }

  /**
   * Handle click placement of `p1` or `p2`.
   *
   * @param {{x: number, y: number, z: number, label?: string, snapped?: boolean}|null} worldPoint - Clicked world point.
   * @returns {boolean} True if click was consumed by the ruler.
   */
  handleClick(worldPoint) {
    if (!this.active || !worldPoint) {
      return false;
    }
    if (!this.p1 || (this.p1 && this.p2)) {
      this.p1 = { ...worldPoint };
      this.p2 = null;
    } else {
      this.p2 = { ...worldPoint };
    }
    this._notify();
    return true;
  }

  /**
   * Trigger registered update listener.
   */
  _notify() {
    if (this.onUpdate) {
      this.onUpdate();
    }
  }

  /**
   * Render crisp `2x` Retina ruler line, graduated ticks, magnetic snap target, and dimension readout pill.
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina-scaled 2D context.
   * @param {{width: number, height: number}} viewportMetrics - Viewport CSS dimensions.
   * @param {import("./camera_controller.js").CadCameraController} cameraController - Active camera controller.
   */
  drawRetinaOverlay(ctx2d, viewportMetrics, cameraController) {
    const startPt = this.p1;
    const endPt = this.p2 || (this.active ? this.hoverPoint : null);

    // Draw live magnetic snap reticle under cursor when active
    if (this.active && this.hoverPoint) {
      const hp = cameraController.worldToCss(this.hoverPoint.x, this.hoverPoint.y, this.hoverPoint.z);
      ctx2d.strokeStyle = this.hoverPoint.snapped ? "#ffb800" : "#38bdf8";
      ctx2d.lineWidth = 1.6;
      ctx2d.beginPath();
      ctx2d.arc(hp.x, hp.y, this.hoverPoint.snapped ? 6.5 : 4.5, 0, Math.PI * 2);
      ctx2d.stroke();

      ctx2d.beginPath();
      ctx2d.moveTo(hp.x - 9, hp.y);
      ctx2d.lineTo(hp.x + 9, hp.y);
      ctx2d.moveTo(hp.x, hp.y - 9);
      ctx2d.lineTo(hp.x, hp.y + 9);
      ctx2d.stroke();
    }

    if (!startPt) {
      return;
    }

    const s1 = cameraController.worldToCss(startPt.x, startPt.y, startPt.z);
    ctx2d.fillStyle = "#ffb800";
    ctx2d.beginPath();
    ctx2d.arc(s1.x, s1.y, 4.5, 0, Math.PI * 2);
    ctx2d.fill();

    if (!endPt) {
      return;
    }

    const s2 = cameraController.worldToCss(endPt.x, endPt.y, endPt.z);
    const meas = computeRulerMeasurement(startPt, endPt);

    const dxPx = s2.x - s1.x;
    const dyPx = s2.y - s1.y;
    const screenLen = Math.hypot(dxPx, dyPx);

    // Orthogonal Manhattan ΔX / ΔY dashed projection guide in 2D modes
    if (cameraController.is2DMode && screenLen > 18) {
      const corner = cameraController.worldToCss(endPt.x, startPt.y, startPt.z);
      ctx2d.save();
      ctx2d.setLineDash([4, 4]);
      ctx2d.strokeStyle = "rgba(56, 189, 248, 0.55)";
      ctx2d.lineWidth = 1.1;
      ctx2d.beginPath();
      ctx2d.moveTo(s1.x, s1.y);
      ctx2d.lineTo(corner.x, corner.y);
      ctx2d.lineTo(s2.x, s2.y);
      ctx2d.stroke();
      ctx2d.restore();
    }

    // Primary measurement line + end caps + graduated ticks
    ctx2d.strokeStyle = "#ffb800";
    ctx2d.lineWidth = 2.0;
    ctx2d.beginPath();
    ctx2d.moveTo(s1.x, s1.y);
    ctx2d.lineTo(s2.x, s2.y);
    ctx2d.stroke();

    if (screenLen > 8) {
      const nx = -dyPx / screenLen;
      const ny = dxPx / screenLen;

      // End-cap Witness Bars
      ctx2d.beginPath();
      ctx2d.moveTo(s1.x - nx * 8, s1.y - ny * 8);
      ctx2d.lineTo(s1.x + nx * 8, s1.y + ny * 8);
      ctx2d.moveTo(s2.x - nx * 8, s2.y - ny * 8);
      ctx2d.lineTo(s2.x + nx * 8, s2.y + ny * 8);
      ctx2d.stroke();

      // Graduated ruler ticks along span
      const tickCount = Math.floor(screenLen / TICK_SPACING_PX);
      ctx2d.lineWidth = 1.2;
      ctx2d.beginPath();
      for (let idx = 1; idx < tickCount; idx += 1) {
        const t = (idx * TICK_SPACING_PX) / screenLen;
        const tx = s1.x + dxPx * t;
        const ty = s1.y + dyPx * t;
        const tickHalf = idx % 5 === 0 ? 5.5 : 3.0;
        ctx2d.moveTo(tx - nx * tickHalf, ty - ny * tickHalf);
        ctx2d.lineTo(tx + nx * tickHalf, ty + ny * tickHalf);
      }
      ctx2d.stroke();
    }

    ctx2d.fillStyle = "#ffb800";
    ctx2d.beginPath();
    ctx2d.arc(s2.x, s2.y, 4.5, 0, Math.PI * 2);
    ctx2d.fill();

    // High-contrast measurement pill readout
    const primaryLine = `${meas.distanceMm.toFixed(3)} mm (${meas.distanceMil.toFixed(1)} mil)`;
    const deltaLine = Math.abs(meas.dzMm) > 1e-3
      ? `ΔX ${meas.dxMm.toFixed(2)}  ΔY ${meas.dyMm.toFixed(2)}  ΔZ ${meas.dzMm.toFixed(2)} mm`
      : `ΔX ${meas.dxMm.toFixed(2)}  ΔY ${meas.dyMm.toFixed(2)} mm  ·  ∠${meas.angleDeg.toFixed(1)}°`;

    ctx2d.font = '800 11px ui-monospace, "SF Mono", Menlo, monospace';
    const w1 = ctx2d.measureText(primaryLine).width;
    ctx2d.font = '600 9.5px ui-monospace, "SF Mono", Menlo, monospace';
    const w2 = ctx2d.measureText(deltaLine).width;

    const pillW = Math.max(w1, w2) + 18;
    const pillH = 36;
    const midX = (s1.x + s2.x) * 0.5;
    const midY = (s1.y + s2.y) * 0.5;
    const bx = Math.max(8, Math.min(viewportMetrics.width - pillW - 8, midX - pillW * 0.5));
    const by = Math.max(8, Math.min(viewportMetrics.height - pillH - 8, midY - pillH - 12));

    ctx2d.fillStyle = "rgba(12, 16, 24, 0.94)";
    ctx2d.strokeStyle = "#ffb800";
    ctx2d.lineWidth = 1.4;
    ctx2d.beginPath();
    ctx2d.roundRect(bx, by, pillW, pillH, 5);
    ctx2d.fill();
    ctx2d.stroke();

    ctx2d.textAlign = "left";
    ctx2d.textBaseline = "top";
    ctx2d.font = '800 11px ui-monospace, "SF Mono", Menlo, monospace';
    ctx2d.fillStyle = "#ffb800";
    ctx2d.fillText(primaryLine, bx + 9, by + 5);

    ctx2d.font = '600 9.5px ui-monospace, "SF Mono", Menlo, monospace';
    ctx2d.fillStyle = "#bae6fd";
    ctx2d.fillText(deltaLine, bx + 9, by + 20);
  }
}
