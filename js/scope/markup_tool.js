/**
 * Retina 2D Markup Drawing (`Pen`, `Line`, `Arrow`, `Rect`, `Circle`, `Text`) & 3D Spatial `Pin` Controller.
 *
 * Stores normalized viewport markups (`[0..1]` screen ratios so drawings remain anchored across
 * window resizes) and 3D world-space `ScopeAnnotationModel` pins (`(x, y, z)` in mm), rendering
 * everything crisply at physical Retina resolution via `#markup-canvas`.
 */

const DEFAULT_MARKUP_COLOR = "#ff3333";
const DEFAULT_STROKE_WIDTH_PX = 2;
const ARROW_HEAD_LEN_PX = 11;
const ARROW_HEAD_ANGLE_RAD = Math.PI / 6;

/**
 * Controller for viewport markups, spatial 3D annotation pins, and undo/clear history.
 */
export class MarkupAndPinController {
  /**
   * Construct a `MarkupAndPinController`.
   *
   * @param {object} [options] - Optional callbacks.
   * @param {function(): void} [options.onChange] - Invoked whenever markups or pins mutate.
   */
  constructor({ onChange = null } = {}) {
    /** @type {boolean} */
    this.toolbarOpen = false;
    /** @type {"pen"|"line"|"arrow"|"rect"|"circle"|"text"|"pin"} */
    this.activeTool = "pen";
    /** @type {string} */
    this.activeColor = DEFAULT_MARKUP_COLOR;
    /** @type {number} */
    this.strokeWidth = DEFAULT_STROKE_WIDTH_PX;
    /** @type {string} */
    this.pendingNoteText = "";

    /** @type {Array<object>} */
    this.markups = [];
    /** @type {Array<{id: number, x: number, y: number, z: number, text: string, created_at: string}>} */
    this.pins = [];
    /** @type {Array<"markup"|"pin">} */
    this._historyOrder = [];
    /** @type {number} */
    this._nextPinId = 1;

    /** @type {object|null} */
    this._activeDraft = null;
    /** @type {function(): void|null} */
    this.onChange = onChange;
  }

  /**
   * Toggle whether interactive markup drawing intercepts viewport pointer gestures.
   *
   * @param {boolean} [forceOpen] - Optional explicit boolean.
   * @returns {boolean}
   */
  setToolbarOpen(forceOpen) {
    this.toolbarOpen = typeof forceOpen === "boolean" ? forceOpen : !this.toolbarOpen;
    if (!this.toolbarOpen) {
      this._activeDraft = null;
    }
    this._notify();
    return this.toolbarOpen;
  }

  /**
   * Set active drawing tool (`pen`, `line`, `arrow`, `rect`, `circle`, `text`, `pin`).
   *
   * @param {"pen"|"line"|"arrow"|"rect"|"circle"|"text"|"pin"} toolName - Tool identifier.
   */
  setTool(toolName) {
    this.activeTool = toolName;
    this._activeDraft = null;
    this._notify();
  }

  /**
   * Set active stroke/fill hex color.
   *
   * @param {string} hexColor - Hex color string.
   */
  setColor(hexColor) {
    if (hexColor) {
      this.activeColor = String(hexColor);
      this._notify();
    }
  }

  /**
   * Add a 3D world-space annotation pin (`ScopeAnnotationModel`).
   *
   * @param {{x: number, y: number, z: number}} worldPoint - World coordinates in mm.
   * @param {string} [noteText] - Pin label text.
   * @returns {{id: number, x: number, y: number, z: number, text: string, created_at: string}}
   */
  addPin(worldPoint, noteText = "") {
    const id = this._nextPinId;
    this._nextPinId += 1;
    const cleanText = String(noteText || this.pendingNoteText || `Pin #${id}`).trim() || `Pin #${id}`;
    const pin = {
      id,
      x: Number(worldPoint.x) || 0,
      y: Number(worldPoint.y) || 0,
      z: Number(worldPoint.z) || 0,
      text: cleanText,
      created_at: new Date().toISOString(),
    };
    this.pins.push(pin);
    this._historyOrder.push("pin");
    this._notify();
    return pin;
  }

  /**
   * Remove a specific 3D spatial pin by `pinId`.
   *
   * @param {number} pinId - Pin ID.
   */
  removePin(pinId) {
    const idx = this.pins.findIndex((p) => p.id === pinId);
    if (idx >= 0) {
      this.pins.splice(idx, 1);
      this._notify();
    }
  }

  /**
   * Begin a 2D markup gesture at normalized coordinates `(nx, ny)` in `[0..1]`.
   *
   * @param {number} nx - Normalized X (`cssX / width`).
   * @param {number} ny - Normalized Y (`cssY / height`).
   * @param {string} [noteText] - Optional text for `text` tool.
   */
  beginStroke(nx, ny, noteText = "") {
    if (!this.toolbarOpen || this.activeTool === "pin") {
      return;
    }
    if (this.activeTool === "text") {
      const text = String(noteText || this.pendingNoteText || "Annotation").trim() || "Annotation";
      this.markups.push({
        type: "text",
        color: this.activeColor,
        stroke_width: this.strokeWidth,
        data: { x: nx, y: ny, text },
      });
      this._historyOrder.push("markup");
      this._notify();
      return;
    }

    if (this.activeTool === "pen") {
      this._activeDraft = {
        type: "pen",
        color: this.activeColor,
        stroke_width: this.strokeWidth,
        data: { points: [[nx, ny]] },
      };
    } else {
      this._activeDraft = {
        type: this.activeTool,
        color: this.activeColor,
        stroke_width: this.strokeWidth,
        data: { x1: nx, y1: ny, x2: nx, y2: ny },
      };
    }
    this._notify();
  }

  /**
   * Update active 2D markup gesture to normalized coordinates `(nx, ny)`.
   *
   * @param {number} nx - Normalized X.
   * @param {number} ny - Normalized Y.
   */
  updateStroke(nx, ny) {
    if (!this._activeDraft) {
      return;
    }
    if (this._activeDraft.type === "pen") {
      this._activeDraft.data.points.push([nx, ny]);
    } else {
      this._activeDraft.data.x2 = nx;
      this._activeDraft.data.y2 = ny;
    }
    this._notify();
  }

  /**
   * Commit active 2D markup gesture to history.
   */
  endStroke() {
    if (!this._activeDraft) {
      return;
    }
    const draft = this._activeDraft;
    this._activeDraft = null;
    if (draft.type === "pen" && draft.data.points.length < 2) {
      this._notify();
      return;
    }
    this.markups.push(draft);
    this._historyOrder.push("markup");
    this._notify();
  }

  /**
   * Undo the most recently created markup or pin (`Cmd/Ctrl + Z`).
   *
   * @returns {boolean} True if an item was undone.
   */
  undo() {
    while (this._historyOrder.length > 0) {
      const kind = this._historyOrder.pop();
      if (kind === "pin" && this.pins.length > 0) {
        this.pins.pop();
        this._notify();
        return true;
      }
      if (kind === "markup" && this.markups.length > 0) {
        this.markups.pop();
        this._notify();
        return true;
      }
    }
    if (this.markups.length > 0) {
      this.markups.pop();
      this._notify();
      return true;
    }
    if (this.pins.length > 0) {
      this.pins.pop();
      this._notify();
      return true;
    }
    return false;
  }

  /**
   * Clear all 2D markups and 3D spatial pins (`X` / `Delete`).
   */
  clearAll() {
    if (this.markups.length === 0 && this.pins.length === 0 && !this._activeDraft) {
      return;
    }
    this.markups = [];
    this.pins = [];
    this._historyOrder = [];
    this._activeDraft = null;
    this._notify();
  }

  /**
   * Export serialized `ScopeAnnotationModel` array for `POST /api/scope/target_bug`.
   *
   * @returns {Array<{id: number, x: number, y: number, z: number, text: string, created_at: string}>}
   */
  getAnnotationsPayload() {
    return this.pins.map((p) => ({
      id: p.id,
      x: Number(p.x.toFixed(4)),
      y: Number(p.y.toFixed(4)),
      z: Number(p.z.toFixed(4)),
      text: p.text,
      created_at: p.created_at,
    }));
  }

  /**
   * Export serialized `ScopeMarkupModel` array for `POST /api/scope/target_bug`.
   *
   * @returns {Array<{type: string, color: string, stroke_width: number, data: object}>}
   */
  getMarkupsPayload() {
    return this.markups.map((m) => ({
      type: m.type,
      color: m.color,
      stroke_width: m.stroke_width,
      data: JSON.parse(JSON.stringify(m.data)),
    }));
  }

  /**
   * Render all 2D markups, active stroke draft, and projected 3D spatial pins at Retina DPR.
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina-scaled 2D context.
   * @param {{width: number, height: number}} viewportMetrics - Logical CSS viewport size.
   * @param {import("./camera_controller.js").CadCameraController} cameraController - Active camera controller.
   */
  drawRetinaOverlay(ctx2d, viewportMetrics, cameraController) {
    const { width, height } = viewportMetrics;

    // 1. Committed + Draft 2D Markups
    for (const item of this.markups) {
      this._drawMarkupItem(ctx2d, item, width, height);
    }
    if (this._activeDraft) {
      this._drawMarkupItem(ctx2d, this._activeDraft, width, height);
    }

    // 2. Projected 3D Spatial Annotation Pins
    for (const pin of this.pins) {
      const sp = cameraController.worldToCss(pin.x, pin.y, pin.z);
      if (!sp.visible) continue;

      ctx2d.strokeStyle = "#080c14";
      ctx2d.lineWidth = 2.0;
      ctx2d.fillStyle = "#ef4444";
      ctx2d.beginPath();
      ctx2d.arc(sp.x, sp.y, 5.5, 0, Math.PI * 2);
      ctx2d.fill();
      ctx2d.stroke();

      const label = `#${pin.id}: ${pin.text}`;
      ctx2d.font = '700 10.5px ui-monospace, "SF Mono", Menlo, monospace';
      const tw = ctx2d.measureText(label).width;
      const bx = Math.min(width - tw - 18, Math.max(6, sp.x + 10));
      const by = Math.max(6, sp.y - 12);

      ctx2d.fillStyle = "rgba(15, 18, 26, 0.92)";
      ctx2d.strokeStyle = "#ef4444";
      ctx2d.lineWidth = 1.2;
      ctx2d.beginPath();
      ctx2d.roundRect(bx, by, tw + 12, 20, 4);
      ctx2d.fill();
      ctx2d.stroke();

      ctx2d.fillStyle = "#f8fafc";
      ctx2d.textAlign = "left";
      ctx2d.textBaseline = "middle";
      ctx2d.fillText(label, bx + 6, by + 10.5);
    }
  }

  /**
   * Draw a single 2D markup shape onto `ctx2d`.
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina 2D context.
   * @param {object} item - Markup entry.
   * @param {number} width - CSS width.
   * @param {number} height - CSS height.
   */
  _drawMarkupItem(ctx2d, item, width, height) {
    ctx2d.strokeStyle = item.color || DEFAULT_MARKUP_COLOR;
    ctx2d.fillStyle = item.color || DEFAULT_MARKUP_COLOR;
    ctx2d.lineWidth = Number(item.stroke_width) || DEFAULT_STROKE_WIDTH_PX;
    ctx2d.lineCap = "round";
    ctx2d.lineJoin = "round";

    const d = item.data || {};
    if (item.type === "pen" && Array.isArray(d.points) && d.points.length >= 2) {
      ctx2d.beginPath();
      d.points.forEach((pt, idx) => {
        const px = pt[0] * width;
        const py = pt[1] * height;
        if (idx === 0) ctx2d.moveTo(px, py);
        else ctx2d.lineTo(px, py);
      });
      ctx2d.stroke();
      return;
    }

    if (item.type === "text") {
      const tx = (d.x || 0) * width;
      const ty = (d.y || 0) * height;
      const label = String(d.text || "");
      ctx2d.font = '700 12px ui-monospace, "SF Mono", Menlo, monospace';
      ctx2d.strokeStyle = "rgba(8, 12, 20, 0.9)";
      ctx2d.lineWidth = 3;
      ctx2d.textAlign = "left";
      ctx2d.textBaseline = "middle";
      ctx2d.strokeText(label, tx, ty);
      ctx2d.fillText(label, tx, ty);
      return;
    }

    const x1 = (d.x1 || 0) * width;
    const y1 = (d.y1 || 0) * height;
    const x2 = (d.x2 || 0) * width;
    const y2 = (d.y2 || 0) * height;

    if (item.type === "line") {
      ctx2d.beginPath();
      ctx2d.moveTo(x1, y1);
      ctx2d.lineTo(x2, y2);
      ctx2d.stroke();
    } else if (item.type === "arrow") {
      const angle = Math.atan2(y2 - y1, x2 - x1);
      ctx2d.beginPath();
      ctx2d.moveTo(x1, y1);
      ctx2d.lineTo(x2, y2);
      ctx2d.lineTo(
        x2 - ARROW_HEAD_LEN_PX * Math.cos(angle - ARROW_HEAD_ANGLE_RAD),
        y2 - ARROW_HEAD_LEN_PX * Math.sin(angle - ARROW_HEAD_ANGLE_RAD),
      );
      ctx2d.moveTo(x2, y2);
      ctx2d.lineTo(
        x2 - ARROW_HEAD_LEN_PX * Math.cos(angle + ARROW_HEAD_ANGLE_RAD),
        y2 - ARROW_HEAD_LEN_PX * Math.sin(angle + ARROW_HEAD_ANGLE_RAD),
      );
      ctx2d.stroke();
    } else if (item.type === "rect") {
      ctx2d.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
    } else if (item.type === "circle") {
      const r = Math.hypot(x2 - x1, y2 - y1);
      ctx2d.beginPath();
      ctx2d.arc(x1, y1, r, 0, Math.PI * 2);
      ctx2d.stroke();
    }
  }

  /**
   * Notify registered listener on state mutation.
   */
  _notify() {
    if (this.onChange) {
      this.onChange();
    }
  }
}
