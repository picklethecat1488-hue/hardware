/**
 * Native Retina WebGL2 + 2D Overlay Viewport & Coalesced Demand Render Scheduler.
 *
 * Eliminates all three root causes of viewport blur and frame-budget waste:
 * 1. Configures `WebGLRenderer` at native `devicePixelRatio` (`2.0x` Retina, up to `MAX_DEVICE_PIXEL_RATIO = 3.0`)
 *    instead of `three-cad-viewer`'s `1.5x` non-integer resample clamp.
 * 2. Configures `#markup-canvas` backing store to `Math.round(cssW * dpr) x Math.round(cssH * dpr)`
 *    with `ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0)` so all Canvas2D text, silkscreen, net labels,
 *    gizmo axes, scale bars, and rulers render crisply at physical Retina pixels.
 * 3. Uses `preserveDrawingBuffer: false` and a coalesced single-RAF demand loop (`requestRender()`,
 *    `requestOverlayRedraw()`), rendering synchronously only when capturing a composited PNG snapshot.
 */

import {
  ACESFilmicToneMapping,
  AmbientLight,
  Color,
  DirectionalLight,
  HemisphereLight,
  SRGBColorSpace,
  Scene,
  WebGLRenderer,
} from "../static/vendor/three/three.module.js";

export const MAX_DEVICE_PIXEL_RATIO = 3.0;
export const AMBIENT_LIGHT_INTENSITY = 1.65;
export const HEMI_LIGHT_INTENSITY = 1.25;
export const KEY_LIGHT_INTENSITY = 2.45;
export const FILL_LIGHT_INTENSITY = 1.45;
export const RIM_LIGHT_INTENSITY = 1.15;
const TONE_MAPPING_EXPOSURE = 1.15;
const MIN_CANVAS_CSS_PX = 1;
const DEFAULT_CAD_BG_HEX = 0x10141b;
const DEFAULT_PCB_BG_HEX = 0x050d17;
const DEFAULT_DIAGRAM_BG_HEX = 0xf4f6f9;

/**
 * Manages the Three.js `WebGLRenderer`, `Scene` lighting rig, Retina 2D overlay `<canvas>`,
 * single-RAF demand render coalescing, and composited PNG snapshot capture.
 */
export class ScopeViewport {
  /**
   * Create a `ScopeViewport`.
   *
   * @param {object} options - Viewport construction options.
   * @param {object} options.ctx - Explicit `RuntimeContext`.
   * @param {HTMLElement} options.container - `#cad-view` mount container.
   * @param {HTMLCanvasElement|null} [options.overlayCanvas] - `#markup-canvas` 2D overlay canvas.
   * @param {object|null} [options.renderer] - Optional injected renderer for headless unit testing.
   */
  constructor({ ctx, container, overlayCanvas = null, renderer = null }) {
    /** @type {object} */
    this.ctx = ctx;
    /** @type {HTMLElement} */
    this.container = container;
    /** @type {HTMLCanvasElement|null} */
    this.overlayCanvas = overlayCanvas;
    /** @type {CanvasRenderingContext2D|null} */
    this.overlayCtx = overlayCanvas && typeof overlayCanvas.getContext === "function"
      ? overlayCanvas.getContext("2d")
      : null;

    /** @type {Scene} */
    this.scene = new Scene();
    this.scene.background = new Color(DEFAULT_CAD_BG_HEX);

    /** @type {number} */
    this.dpr = this._computeClampedDpr();
    /** @type {number} */
    this.cssWidth = MIN_CANVAS_CSS_PX;
    /** @type {number} */
    this.cssHeight = MIN_CANVAS_CSS_PX;

    /** @type {WebGLRenderer|object} */
    this.renderer = renderer || this._createWebGLRenderer();
    if (!renderer && this.container && typeof this.container.appendChild === "function") {
      this.container.innerHTML = "";
      this.renderer.domElement.style.display = "block";
      this.renderer.domElement.style.width = "100%";
      this.renderer.domElement.style.height = "100%";
      this.container.appendChild(this.renderer.domElement);
    }

    this._setupLightingRig();

    /** @type {import("../static/vendor/three/three.module.js").Camera|null} */
    this.activeCamera = null;
    /** @type {Array<function(CanvasRenderingContext2D, {width: number, height: number, dpr: number}): void>} */
    this._overlayLayers = [];
    /** @type {Array<function({width: number, height: number, dpr: number}): void>} */
    this._resizeListeners = [];

    this._webglDirty = false;
    this._overlayDirty = false;
    this._rafHandle = null;
    this._disposed = false;

    this._boundFrameTick = this._onAnimationFrame.bind(this);
    this._boundWindowResize = () => this.resize();
    this.ctx.addViewportListener("resize", this._boundWindowResize);

    this.resize();
  }

  /**
   * Compute physical pixel ratio clamped to `[1, MAX_DEVICE_PIXEL_RATIO]`.
   *
   * @returns {number}
   */
  _computeClampedDpr() {
    const raw = Number(this.ctx.getDevicePixelRatio());
    if (!Number.isFinite(raw) || raw <= 0) {
      return 1.0;
    }
    return Math.min(raw, MAX_DEVICE_PIXEL_RATIO);
  }

  /**
   * Instantiate the WebGL2 renderer with `preserveDrawingBuffer: false` and crisp sRGB tone mapping.
   *
   * @returns {WebGLRenderer}
   */
  _createWebGLRenderer() {
    const glRenderer = new WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: false,
      stencil: false,
    });
    glRenderer.outputColorSpace = SRGBColorSpace;
    glRenderer.toneMapping = ACESFilmicToneMapping;
    glRenderer.toneMappingExposure = TONE_MAPPING_EXPOSURE;
    glRenderer.localClippingEnabled = true;
    glRenderer.setPixelRatio(this.dpr);
    return glRenderer;
  }

  /**
   * Configure balanced 3-point CAD studio lighting + hemisphere fill calibrated for Three.js r184
   * physically-correct `1/PI` diffuse BRDF units so machined B-rep fillets, dark FR4 soldermasks,
   * IC packages, and water voxels read brightly and evenly from every camera azimuth.
   */
  _setupLightingRig() {
    this.ambientLight = new AmbientLight(0xffffff, AMBIENT_LIGHT_INTENSITY);
    this.hemiLight = new HemisphereLight(0xf8fafc, 0x64748b, HEMI_LIGHT_INTENSITY);
    this.hemiLight.position.set(0, 0, 250);

    this.keyLight = new DirectionalLight(0xffffff, KEY_LIGHT_INTENSITY);
    this.keyLight.position.set(180, -160, 260);

    this.fillLight = new DirectionalLight(0xe2e8f0, FILL_LIGHT_INTENSITY);
    this.fillLight.position.set(-200, 180, 160);

    this.rimLight = new DirectionalLight(0xdbeafe, RIM_LIGHT_INTENSITY);
    this.rimLight.position.set(40, 220, -220);

    this.scene.add(this.ambientLight, this.hemiLight, this.keyLight, this.fillLight, this.rimLight);
  }

  /**
   * Apply canonical mode background color (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`).
   *
   * @param {string} mode - Active visualization mode.
   */
  setModeTheme(mode) {
    const upper = String(mode || "CAD").toUpperCase();
    if (upper === "PCB") {
      this.scene.background = new Color(DEFAULT_PCB_BG_HEX);
    } else if (upper === "DIAGRAM") {
      this.scene.background = new Color(DEFAULT_DIAGRAM_BG_HEX);
    } else {
      this.scene.background = new Color(DEFAULT_CAD_BG_HEX);
    }
    this.requestRender();
  }

  /**
   * Set the active Three.js camera rendered on demand ticks.
   *
   * @param {import("../static/vendor/three/three.module.js").Camera} camera - Active camera.
   */
  setCamera(camera) {
    this.activeCamera = camera;
    this.requestRender();
  }

  /**
   * Register a Retina 2D overlay drawing callback invoked in registration order.
   *
   * @param {function(CanvasRenderingContext2D, {width: number, height: number, dpr: number}): void} drawFn - Layer painter.
   * @returns {function(): void} Unsubscribe callback.
   */
  addOverlayLayer(drawFn) {
    this._overlayLayers.push(drawFn);
    return () => {
      const idx = this._overlayLayers.indexOf(drawFn);
      if (idx >= 0) {
        this._overlayLayers.splice(idx, 1);
      }
    };
  }

  /**
   * Register a viewport resize callback receiving `{ width, height, dpr }`.
   *
   * @param {function({width: number, height: number, dpr: number}): void} listener - Resize callback.
   * @returns {function(): void} Unsubscribe callback.
   */
  onResize(listener) {
    this._resizeListeners.push(listener);
    return () => {
      const idx = this._resizeListeners.indexOf(listener);
      if (idx >= 0) {
        this._resizeListeners.splice(idx, 1);
      }
    };
  }

  /**
   * Recompute CSS and physical Retina backing-store dimensions for both WebGL and `#markup-canvas`.
   *
   * @param {number} [explicitWidth] - Optional explicit CSS width override.
   * @param {number} [explicitHeight] - Optional explicit CSS height override.
   */
  resize(explicitWidth, explicitHeight) {
    this.dpr = this._computeClampedDpr();

    let rectW = Number(explicitWidth) || 0;
    let rectH = Number(explicitHeight) || 0;

    if ((!rectW || !rectH) && this.container) {
      if (typeof this.container.getBoundingClientRect === "function") {
        const rect = this.container.getBoundingClientRect();
        rectW = rect.width;
        rectH = rect.height;
      }
      if (!rectW) rectW = Number(this.container.clientWidth) || 0;
      if (!rectH) rectH = Number(this.container.clientHeight) || 0;
    }

    if (!rectW || !rectH) {
      const vp = this.ctx.getViewportSize();
      rectW = rectW || vp.width;
      rectH = rectH || vp.height;
    }

    this.cssWidth = Math.max(MIN_CANVAS_CSS_PX, Math.round(rectW));
    this.cssHeight = Math.max(MIN_CANVAS_CSS_PX, Math.round(rectH));

    if (this.renderer && typeof this.renderer.setPixelRatio === "function") {
      this.renderer.setPixelRatio(this.dpr);
    }
    if (this.renderer && typeof this.renderer.setSize === "function") {
      this.renderer.setSize(this.cssWidth, this.cssHeight, false);
    }

    if (this.overlayCanvas) {
      const physW = Math.max(1, Math.round(this.cssWidth * this.dpr));
      const physH = Math.max(1, Math.round(this.cssHeight * this.dpr));
      if (this.overlayCanvas.width !== physW || this.overlayCanvas.height !== physH) {
        this.overlayCanvas.width = physW;
        this.overlayCanvas.height = physH;
      }
      if (this.overlayCanvas.style) {
        this.overlayCanvas.style.width = `${this.cssWidth}px`;
        this.overlayCanvas.style.height = `${this.cssHeight}px`;
      }
      if (this.overlayCtx) {
        this.overlayCtx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      }
    }

    const metrics = { width: this.cssWidth, height: this.cssHeight, dpr: this.dpr };
    for (const listener of this._resizeListeners) {
      listener(metrics);
    }

    this.requestRender();
  }

  /**
   * Convert a pointer event's `clientX`/`clientY` into logical CSS coordinates and NDC `[-1, 1]`.
   *
   * @param {{clientX: number, clientY: number}} event - Pointer/mouse/wheel event.
   * @returns {{x: number, y: number, width: number, height: number, ndcX: number, ndcY: number}}
   */
  getPointerCoords(event) {
    const domEl = this.renderer?.domElement || this.container;
    let left = 0;
    let top = 0;
    let width = this.cssWidth;
    let height = this.cssHeight;
    if (domEl && typeof domEl.getBoundingClientRect === "function") {
      const rect = domEl.getBoundingClientRect();
      left = rect.left;
      top = rect.top;
      if (rect.width > 0) width = rect.width;
      if (rect.height > 0) height = rect.height;
    }
    const x = event.clientX - left;
    const y = event.clientY - top;
    return {
      x,
      y,
      width,
      height,
      ndcX: (x / width) * 2 - 1,
      ndcY: -(y / height) * 2 + 1,
    };
  }

  /**
   * Coalesce both WebGL and 2D Retina overlay rendering into a single upcoming display frame.
   */
  requestRender() {
    this._webglDirty = true;
    this._overlayDirty = true;
    this._scheduleFrame();
  }

  /**
   * Coalesce a 2D Retina overlay-only redraw without re-rendering the 3D WebGL scene.
   */
  requestOverlayRedraw() {
    this._overlayDirty = true;
    this._scheduleFrame();
  }

  /**
   * Schedule at most one `requestAnimationFrame` callback per display refresh interval.
   */
  _scheduleFrame() {
    if (this._disposed || this._rafHandle !== null) {
      return;
    }
    this._rafHandle = this.ctx.requestAnimationFrame(this._boundFrameTick);
  }

  /**
   * Execute pending WebGL and/or Retina 2D overlay passes in a single synchronized frame.
   */
  _onAnimationFrame() {
    this._rafHandle = null;
    if (this._disposed) {
      return;
    }
    this.renderNow({ forceWebgl: this._webglDirty, forceOverlay: this._overlayDirty });
  }

  /**
   * Synchronously execute WebGL and/or Retina 2D overlay passes immediately.
   *
   * @param {{forceWebgl?: boolean, forceOverlay?: boolean}} [options] - Pass flags.
   */
  renderNow({ forceWebgl = true, forceOverlay = true } = {}) {
    if (forceWebgl && this.activeCamera && this.renderer && typeof this.renderer.render === "function") {
      this._webglDirty = false;
      this.renderer.render(this.scene, this.activeCamera);
    }

    if (forceOverlay && this.overlayCtx) {
      this._overlayDirty = false;
      this.overlayCtx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      this.overlayCtx.clearRect(0, 0, this.cssWidth, this.cssHeight);
      this.overlayCtx.imageSmoothingEnabled = true;

      const metrics = { width: this.cssWidth, height: this.cssHeight, dpr: this.dpr };
      for (const drawLayer of this._overlayLayers) {
        this.overlayCtx.save();
        drawLayer(this.overlayCtx, metrics);
        this.overlayCtx.restore();
      }
    }
  }

  /**
   * Capture a crisp Retina PNG data URL compositing the live WebGL frame and 2D markup/HUD overlay
   * without requiring `preserveDrawingBuffer: true` during normal interactive rendering!
   *
   * @returns {string} `data:image/png;base64,...` URL.
   */
  captureCompositedPng() {
    this.renderNow({ forceWebgl: true, forceOverlay: true });

    const physW = Math.max(1, Math.round(this.cssWidth * this.dpr));
    const physH = Math.max(1, Math.round(this.cssHeight * this.dpr));
    const composite = this.ctx.createCanvas(physW, physH);
    const compCtx = typeof composite.getContext === "function" ? composite.getContext("2d") : null;
    if (!compCtx) {
      return "";
    }

    if (this.renderer?.domElement) {
      compCtx.drawImage(this.renderer.domElement, 0, 0, physW, physH);
    }
    if (this.overlayCanvas) {
      compCtx.drawImage(this.overlayCanvas, 0, 0, physW, physH);
    }
    return typeof composite.toDataURL === "function" ? composite.toDataURL("image/png") : "";
  }

  /**
   * Dispose WebGL context and detach viewport listeners.
   */
  dispose() {
    this._disposed = true;
    if (this._rafHandle !== null) {
      this.ctx.cancelAnimationFrame(this._rafHandle);
      this._rafHandle = null;
    }
    this.ctx.removeViewportListener("resize", this._boundWindowResize);
    if (this.renderer && typeof this.renderer.dispose === "function") {
      this.renderer.dispose();
    }
  }
}
