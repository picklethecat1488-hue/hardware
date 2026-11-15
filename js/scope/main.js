/**
 * First-Class Scope CAD / PCB / Simulation / Diagram Workstation Application Entrypoint.
 *
 * Strictly zero-globals ES module (`getRuntimeContext()` only at top-level auto-boot;
 * `createScopeApp(ctx)` accepts explicit `RuntimeContext` for deterministic `node --test` suites).
 */

import { setupPanelResizer } from "../core/resizer.js";
import { getRuntimeContext } from "../core/runtime_context.js";
import { showToast } from "../core/toast.js";
import { applyUiScale, initUiScaleControl } from "../core/ui_scale.js";
import { CadSceneManager } from "./cad_scene.js";
import { CadCameraController } from "./camera_controller.js";
import { decodeOcpPayload } from "./decoder.js";
import { ScopeInspectorController } from "./inspector.js";
import { MarkupAndPinController } from "./markup_tool.js";
import { PcbGpuRenderer } from "./pcb_renderer.js";
import { PrecisionRulerTool } from "./ruler_tool.js";
import { SimulationVoxelRenderer } from "./sim_renderer.js";
import { ScopeViewport } from "./viewport.js";

const CLICK_SLOP_PX = 5.0;
const DEFAULT_SIDEBAR_WIDTH_PX = 320;
const UI_SCALE_STEPS = Object.freeze(["75%", "80%", "90%", "100%", "110%", "125%", "150%"]);

/**
 * Orchestrates the Scope Workstation viewport, camera, CAD/PCB/Sim renderers, tools, and REST APIs.
 */
export class ScopeWorkstationApp {
  /**
   * Construct a `ScopeWorkstationApp`.
   *
   * @param {object} ctx - Explicit `RuntimeContext`.
   * @param {object} [options] - Optional injected dependencies for headless unit testing.
   * @param {object} [options.renderer] - Optional mock WebGL renderer.
   * @param {boolean} [options.autoLoad] - Whether `boot()` automatically fetches projects/geometry (`true` default).
   */
  constructor(ctx, options = {}) {
    /** @type {object} */
    this.ctx = ctx;
    /** @type {boolean} */
    this.autoLoad = options.autoLoad !== false;

    const bootCfg = this.ctx.getBootConfig() || {};
    /** @type {string} */
    this.currentProject = String(bootCfg.initProject || "");
    /** @type {string} */
    this.currentTarget = String(bootCfg.initTarget || "");
    /** @type {string} */
    this.currentSub = String(bootCfg.initSubassembly || "");
    /** @type {string} */
    this.currentMode = String(bootCfg.initMode || "CAD").toUpperCase();
    /** @type {number} */
    this.maxSteps = Number(bootCfg.initMaxSteps) || 1000;

    const container = this._el("cad-view");
    const overlayCanvas = /** @type {HTMLCanvasElement|null} */ (this._el("markup-canvas"));

    /** @type {ScopeViewport} */
    this.viewport = new ScopeViewport({
      ctx: this.ctx,
      container,
      overlayCanvas,
      renderer: options.renderer || null,
    });

    /** @type {CadCameraController} */
    this.cameraController = new CadCameraController({
      domElement: this.viewport.renderer?.domElement || container,
      width: this.viewport.cssWidth,
      height: this.viewport.cssHeight,
      onChange: () => {
        this.viewport.setCamera(this.cameraController.activeCamera);
        this.viewport.requestRender();
      },
    });
    this.viewport.scene.add(this.cameraController.floorGridMesh);
    this.viewport.setCamera(this.cameraController.activeCamera);

    /** @type {CadSceneManager} */
    this.cadScene = new CadSceneManager({
      scene: this.viewport.scene,
      dpr: this.viewport.dpr,
    });

    /** @type {PcbGpuRenderer} */
    this.pcbRenderer = new PcbGpuRenderer({
      scene: this.viewport.scene,
    });

    /** @type {SimulationVoxelRenderer} */
    this.simRenderer = new SimulationVoxelRenderer({
      ctx: this.ctx,
      scene: this.viewport.scene,
      cadScene: this.cadScene,
      onFrameChange: (summary) => {
        if (this.inspector) {
          this.inspector.updateSimulationFrameHud(summary);
        }
        this._syncSimPlayButtonState();
        this._syncSimStyleButtons();
        this.viewport.requestRender();
      },
    });

    /** @type {PrecisionRulerTool} */
    this.rulerTool = new PrecisionRulerTool({
      onUpdate: () => {
        this._syncRulerButtonState();
        this.viewport.requestOverlayRedraw();
      },
    });

    /** @type {MarkupAndPinController} */
    this.markupController = new MarkupAndPinController({
      onChange: () => {
        if (this.inspector) {
          this.inspector.renderPinsList();
        }
        this.viewport.requestOverlayRedraw();
      },
    });

    /** @type {ScopeInspectorController} */
    this.inspector = new ScopeInspectorController({
      ctx: this.ctx,
      viewport: this.viewport,
      cameraController: this.cameraController,
      cadScene: this.cadScene,
      pcbRenderer: this.pcbRenderer,
      simRenderer: this.simRenderer,
      markupController: this.markupController,
      onSelectTarget: (sel) => this.loadTarget(sel),
    });

    // Register Retina 2D overlay layers in painter order
    this.viewport.addOverlayLayer((ctx2d, metrics) => {
      if (this.currentMode === "PCB") {
        this.pcbRenderer.drawRetinaOverlay(ctx2d, metrics, this.cameraController);
      }
      this.cameraController.drawHudOverlays(ctx2d, metrics);
      this.rulerTool.drawRetinaOverlay(ctx2d, metrics, this.cameraController);
      this.markupController.drawRetinaOverlay(ctx2d, metrics, this.cameraController);
    });

    this.viewport.onResize(({ width, height, dpr }) => {
      this.cameraController.resize(width, height);
      this.cadScene.setDevicePixelRatio(dpr);
    });

    this._pointerDownScreen = null;
    this._markupDrawingPointerId = null;

    this._bindWorkstationControls();
  }

  /**
   * Look up a DOM element by ID.
   *
   * @param {string} id - Element ID.
   * @returns {HTMLElement|null}
   */
  _el(id) {
    const doc = this.ctx.getDocument();
    return doc ? doc.getElementById(id) : null;
  }

  /**
   * Initialize UI scale, panel resizer, toolbar buttons, viewport pointer events, and keyboard shortcuts.
   */
  _bindWorkstationControls() {
    const doc = this.ctx.getDocument();
    if (!doc) return;

    initUiScaleControl(this.ctx, "uiScaleSelect", {
      storageKey: "scope_ui_scale",
      defaultValue: "100%",
      onScaleChange: () => this.viewport.resize(),
    });

    setupPanelResizer(this.ctx, "sidebar-resizer", "sidebar", "scope_sidebar_width", {
      minSize: 180,
      maxSize: 780,
      onResize: () => this.viewport.resize(),
    });

    const resizerEl = this._el("sidebar-resizer");
    const sidebarEl = this._el("sidebar");
    if (resizerEl && sidebarEl) {
      resizerEl.addEventListener("dblclick", () => {
        sidebarEl.style.width = `${DEFAULT_SIDEBAR_WIDTH_PX}px`;
        this.ctx.getStorage().setItem("scope_sidebar_width", String(DEFAULT_SIDEBAR_WIDTH_PX));
        this.viewport.resize();
      });
    }

    // Top HUD Mode pills
    for (const pill of doc.querySelectorAll("#top-hud .mode-pill")) {
      pill.addEventListener("click", () => {
        if (pill.disabled || pill.classList.contains("disabled")) return;
        const targetMode = pill.getAttribute("data-mode") || "CAD";
        if (targetMode !== this.currentMode && this.currentProject && this.currentTarget) {
          this.loadTarget({
            project: this.currentProject,
            target: this.currentTarget,
            subassembly: this.currentSub,
            mode: targetMode,
            maxSteps: this.maxSteps,
          });
        }
      });
    }

    // Sync button
    const btnSync = this._el("btn-sync");
    if (btnSync) {
      btnSync.addEventListener("click", () => this.syncWorkspace());
    }

    // Shortcuts HUD toggle
    const btnShortcuts = this._el("btn-shortcuts");
    const btnCloseShortcuts = this._el("btn-close-shortcuts-hud");
    if (btnShortcuts) {
      btnShortcuts.addEventListener("click", () => this.toggleShortcutsHud());
    }
    if (btnCloseShortcuts) {
      btnCloseShortcuts.addEventListener("click", () => this.toggleShortcutsHud(false));
    }

    // Floating camera preset buttons & Sidebar View buttons
    const presetBindings = [
      ["cam-iso", "iso"],
      ["btn-view-iso", "iso"],
      ["cam-top", "top"],
      ["btn-view-top", "top"],
      ["cam-bottom", "bottom"],
      ["btn-view-bottom", "bottom"],
      ["cam-flip", "flip"],
      ["cam-front", "front"],
      ["btn-view-front", "front"],
      ["cam-right", "right"],
      ["btn-view-right", "right"],
      ["btn-view-left", "left"],
      ["cam-focus", "fit"],
    ];
    for (const [btnId, preset] of presetBindings) {
      const btn = this._el(btnId);
      if (btn) {
        btn.addEventListener("click", () => {
          this.cameraController.setPreset(preset, { fit: preset === "fit" });
          this.viewport.setCamera(this.cameraController.activeCamera);
        });
      }
    }

    for (const orthoId of ["cam-ortho", "btn-view-ortho"]) {
      const btn = this._el(orthoId);
      if (btn) {
        btn.addEventListener("click", () => {
          const isOrtho = this.cameraController.toggleProjection();
          this.viewport.setCamera(this.cameraController.activeCamera);
          const camOrthoBtn = this._el("cam-ortho");
          if (camOrthoBtn) camOrthoBtn.classList.toggle("active", isOrtho);
        });
      }
    }

    for (const wireId of ["cam-wire", "btn-view-wire"]) {
      const btn = this._el(wireId);
      if (btn) {
        btn.addEventListener("click", () => {
          const wf = this.cadScene.setWireframe();
          const camWireBtn = this._el("cam-wire");
          if (camWireBtn) camWireBtn.classList.toggle("active", wf);
          this.viewport.requestRender();
        });
      }
    }

    const btnAxes = this._el("btn-view-axes");
    if (btnAxes) {
      btnAxes.addEventListener("click", () => {
        this.cameraController.setAxesVisible(!this.cameraController.axesVisible);
      });
    }

    const btnGrid = this._el("btn-view-grid");
    if (btnGrid) {
      btnGrid.addEventListener("click", () => {
        this.cameraController.setGridVisible(!this.cameraController.gridVisible);
      });
    }

    const explodeSlider = /** @type {HTMLInputElement|null} */ (this._el("view-explode-slider"));
    const explodeVal = this._el("view-explode-val");
    if (explodeSlider) {
      explodeSlider.addEventListener("input", () => {
        const pct = Number(explodeSlider.value) || 0;
        if (explodeVal) explodeVal.textContent = `${Math.round(pct)}%`;
        this.cadScene.setExplode(pct / 100);
        this.viewport.requestRender();
      });
    }

    const camRuler = this._el("cam-ruler");
    if (camRuler) {
      camRuler.addEventListener("click", () => {
        this.rulerTool.toggle();
      });
    }

    // Markup Toolbar controls
    this._bindMarkupControls();

    // Simulation Bar controls
    this._bindSimulationControls();

    // Viewport Pointer Interactions (`#cad-view` canvas)
    this._bindViewportPointerEvents();

    // Global Keyboard Shortcuts
    doc.addEventListener("keydown", (ev) => this._onKeyDown(ev));
  }

  /**
   * Bind `#btn-toggle-markup`, `#markup-toolbar`, and `#markup-canvas` drawing listeners.
   */
  _bindMarkupControls() {
    const doc = this.ctx.getDocument();
    if (!doc) return;

    const btnToggleMarkup = this._el("btn-toggle-markup");
    const toolbar = this._el("markup-toolbar");
    const overlayCanvas = this._el("markup-canvas");

    const syncMarkupUi = () => {
      const open = this.markupController.toolbarOpen;
      if (toolbar) toolbar.classList.toggle("visible", open);
      if (overlayCanvas) overlayCanvas.classList.toggle("active", open);
      if (btnToggleMarkup) btnToggleMarkup.classList.toggle("active", open);
    };

    if (btnToggleMarkup) {
      btnToggleMarkup.addEventListener("click", () => {
        this.markupController.setToolbarOpen();
        syncMarkupUi();
      });
    }

    for (const toolBtn of doc.querySelectorAll("#markup-toolbar .tool-btn[data-tool]")) {
      toolBtn.addEventListener("click", () => {
        const tool = toolBtn.getAttribute("data-tool") || "pen";
        this.markupController.setTool(/** @type {any} */ (tool));
        for (const b of doc.querySelectorAll("#markup-toolbar .tool-btn[data-tool]")) {
          b.classList.toggle("active", b === toolBtn);
        }
      });
    }

    for (const swatch of doc.querySelectorAll("#markup-toolbar .color-swatch[data-color]")) {
      swatch.addEventListener("click", () => {
        const color = swatch.getAttribute("data-color") || "#ff3333";
        this.markupController.setColor(color);
        for (const s of doc.querySelectorAll("#markup-toolbar .color-swatch[data-color]")) {
          s.classList.toggle("active", s === swatch);
        }
      });
    }

    const noteInput = /** @type {HTMLInputElement|null} */ (this._el("markup-text-input"));
    if (noteInput) {
      noteInput.addEventListener("input", () => {
        this.markupController.pendingNoteText = noteInput.value;
      });
    }

    const btnUndo = this._el("btn-undo-markup");
    if (btnUndo) {
      btnUndo.addEventListener("click", () => this.markupController.undo());
    }
    const btnClear = this._el("btn-clear-markup");
    if (btnClear) {
      btnClear.addEventListener("click", () => this.markupController.clearAll());
    }

    if (overlayCanvas) {
      overlayCanvas.addEventListener("pointerdown", (ev) => {
        if (!this.markupController.toolbarOpen || ev.button !== 0) return;
        const coords = this.viewport.getPointerCoords(ev);
        if (this.markupController.activeTool === "pin") {
          const worldPt = this.rulerTool.resolveWorldPoint({
            ndcX: coords.ndcX,
            ndcY: coords.ndcY,
            shiftKey: ev.shiftKey,
            mode: this.currentMode,
            cameraController: this.cameraController,
            pcbRenderer: this.pcbRenderer,
            cadScene: this.cadScene,
          });
          if (worldPt) {
            const pin = this.markupController.addPin(worldPt, noteInput ? noteInput.value : "");
            showToast(this.ctx, `Placed Pin #${pin.id}`, "info");
          }
          return;
        }

        const nx = Math.max(0, Math.min(1, coords.x / Math.max(1, coords.width)));
        const ny = Math.max(0, Math.min(1, coords.y / Math.max(1, coords.height)));
        this.markupController.beginStroke(nx, ny, noteInput ? noteInput.value : "");
        if (this.markupController.activeTool !== "text") {
          this._markupDrawingPointerId = ev.pointerId;
          if (overlayCanvas.setPointerCapture) {
            overlayCanvas.setPointerCapture(ev.pointerId);
          }
        }
      });

      overlayCanvas.addEventListener("pointermove", (ev) => {
        if (this._markupDrawingPointerId === null || ev.pointerId !== this._markupDrawingPointerId) {
          return;
        }
        const coords = this.viewport.getPointerCoords(ev);
        const nx = Math.max(0, Math.min(1, coords.x / Math.max(1, coords.width)));
        const ny = Math.max(0, Math.min(1, coords.y / Math.max(1, coords.height)));
        this.markupController.updateStroke(nx, ny);
      });

      const finishStroke = (ev) => {
        if (this._markupDrawingPointerId === null || ev.pointerId !== this._markupDrawingPointerId) {
          return;
        }
        if (overlayCanvas.hasPointerCapture && overlayCanvas.hasPointerCapture(ev.pointerId)) {
          overlayCanvas.releasePointerCapture(ev.pointerId);
        }
        this._markupDrawingPointerId = null;
        this.markupController.endStroke();
      };
      overlayCanvas.addEventListener("pointerup", finishStroke);
      overlayCanvas.addEventListener("pointercancel", finishStroke);
    }
  }

  /**
   * Bind `#sim-bar` playback, scrubber, timescale, and `[Voxels | Spheres]` toggle controls.
   */
  _bindSimulationControls() {
    const btnPlay = this._el("btn-sim-play");
    if (btnPlay) {
      btnPlay.addEventListener("click", () => {
        this.simRenderer.togglePlay();
        this._syncSimPlayButtonState();
      });
    }

    const btnPrev = this._el("btn-sim-prev");
    if (btnPrev) {
      btnPrev.addEventListener("click", () => {
        this.simRenderer.pause();
        this.simRenderer.stepBy(-10);
        this._syncSimPlayButtonState();
      });
    }

    const btnNext = this._el("btn-sim-next");
    if (btnNext) {
      btnNext.addEventListener("click", () => {
        this.simRenderer.pause();
        this.simRenderer.stepBy(10);
        this._syncSimPlayButtonState();
      });
    }

    const stepSlider = /** @type {HTMLInputElement|null} */ (this._el("sim-step-slider"));
    if (stepSlider) {
      stepSlider.addEventListener("input", () => {
        this.simRenderer.pause();
        this.simRenderer.setFrameIndex(Number(stepSlider.value) || 0);
        this._syncSimPlayButtonState();
      });
    }

    const timeScaleSel = /** @type {HTMLSelectElement|null} */ (this._el("sim-timescale"));
    if (timeScaleSel) {
      timeScaleSel.addEventListener("change", () => {
        this.simRenderer.setTimeScale(Number(timeScaleSel.value) || 1.0);
      });
    }

    const btnVoxels = this._el("btn-sim-style-voxels");
    const btnSpheres = this._el("btn-sim-style-spheres");
    if (btnVoxels) {
      btnVoxels.addEventListener("click", () => {
        this.simRenderer.setRenderStyle("voxels");
        this._syncSimStyleButtons();
        this.viewport.requestRender();
      });
    }
    if (btnSpheres) {
      btnSpheres.addEventListener("click", () => {
        this.simRenderer.setRenderStyle("spheres");
        this._syncSimStyleButtons();
        this.viewport.requestRender();
      });
    }
  }

  /**
   * Synchronize `#btn-sim-play` label with `simRenderer.isPlaying`.
   */
  _syncSimPlayButtonState() {
    const btnPlay = this._el("btn-sim-play");
    if (btnPlay) {
      btnPlay.textContent = this.simRenderer.isPlaying ? "⏸ Pause" : "▶ Play";
    }
  }

  /**
   * Synchronize `#btn-sim-style-voxels` / `#btn-sim-style-spheres` active pill classes.
   */
  _syncSimStyleButtons() {
    const btnVoxels = this._el("btn-sim-style-voxels");
    const btnSpheres = this._el("btn-sim-style-spheres");
    const isVoxels = this.simRenderer.renderStyle === "voxels";
    if (btnVoxels) btnVoxels.classList.toggle("active", isVoxels);
    if (btnSpheres) btnSpheres.classList.toggle("active", !isVoxels);
  }

  /**
   * Synchronize `#cam-ruler` active highlight with `rulerTool.active`.
   */
  _syncRulerButtonState() {
    const camRuler = this._el("cam-ruler");
    if (camRuler) {
      camRuler.classList.toggle("active", this.rulerTool.active);
    }
  }

  /**
   * Bind hover, click-selection, and double-click pivot listeners to the WebGL viewport element.
   */
  _bindViewportPointerEvents() {
    const targetEl = this.viewport.renderer?.domElement || this.viewport.container;
    if (!targetEl || typeof targetEl.addEventListener !== "function") return;

    targetEl.addEventListener("pointerdown", (ev) => {
      if (ev.button === 0) {
        this._pointerDownScreen = { x: ev.clientX, y: ev.clientY };
      }
    });

    targetEl.addEventListener("pointermove", (ev) => {
      if (this.markupController.toolbarOpen) return;
      // Skip hover hit-testing while actively dragging OrbitControls
      if (ev.buttons !== 0) return;

      const coords = this.viewport.getPointerCoords(ev);
      if (this.rulerTool.active) {
        const pt = this.rulerTool.resolveWorldPoint({
          ndcX: coords.ndcX,
          ndcY: coords.ndcY,
          shiftKey: ev.shiftKey,
          mode: this.currentMode,
          cameraController: this.cameraController,
          pcbRenderer: this.pcbRenderer,
          cadScene: this.cadScene,
        });
        this.rulerTool.handleHover(pt);
        return;
      }

      if (this.currentMode === "PCB") {
        const boardPt = this.cameraController.screenNdcToPlaneZ(coords.ndcX, coords.ndcY, 0);
        const hit = boardPt
          ? this.pcbRenderer.hitTest(boardPt.x, boardPt.y, this.cameraController.activeBoardSide)
          : null;
        if (hit !== this.pcbRenderer.hoveredEntity) {
          this.pcbRenderer.hoveredEntity = hit;
          this.viewport.requestOverlayRedraw();
        }
      }
    });

    targetEl.addEventListener("pointerup", (ev) => {
      if (ev.button !== 0 || !this._pointerDownScreen || this.markupController.toolbarOpen) {
        return;
      }
      const moved = Math.hypot(
        ev.clientX - this._pointerDownScreen.x,
        ev.clientY - this._pointerDownScreen.y,
      );
      this._pointerDownScreen = null;
      if (moved > CLICK_SLOP_PX) {
        return;
      }

      const coords = this.viewport.getPointerCoords(ev);

      // 1. Ruler click takes priority when ruler is active
      if (this.rulerTool.active) {
        const pt = this.rulerTool.resolveWorldPoint({
          ndcX: coords.ndcX,
          ndcY: coords.ndcY,
          shiftKey: ev.shiftKey,
          mode: this.currentMode,
          cameraController: this.cameraController,
          pcbRenderer: this.pcbRenderer,
          cadScene: this.cadScene,
        });
        this.rulerTool.handleClick(pt);
        return;
      }

      // 2. PCB 2D entity inspection & instant GPU net highlighting
      if (this.currentMode === "PCB") {
        const boardPt = this.cameraController.screenNdcToPlaneZ(coords.ndcX, coords.ndcY, 0);
        const hit = boardPt
          ? this.pcbRenderer.hitTest(boardPt.x, boardPt.y, this.cameraController.activeBoardSide)
          : null;
        this.pcbRenderer.selectedEntity = hit;
        this.pcbRenderer.setHighlightedNet(hit && hit.net ? hit.net : "");
        this.inspector.renderPcbInspection(hit);
        this.inspector.renderNetsList(
          /** @type {HTMLInputElement|null} */ (this._el("net-search"))?.value || "",
        );
        if (hit) {
          this.inspector.activateTab("tab-inspect");
        }
        this.viewport.requestRender();
        return;
      }

      // 3. 3D CAD / SIMULATE / DIAGRAM B-rep face inspection
      const brepHit = this.cadScene.pickBrepFace(
        this.cameraController.activeCamera,
        coords.ndcX,
        coords.ndcY,
      );
      this.cadScene.highlightBrepFace(brepHit);
      this.inspector.renderBrepInspection(brepHit);
      if (brepHit) {
        this.inspector.activateTab("tab-inspect");
      }
      this.viewport.requestRender();
    });

    targetEl.addEventListener("dblclick", (ev) => {
      if (this.markupController.toolbarOpen || this.currentMode === "PCB" || this.currentMode === "DIAGRAM") {
        return;
      }
      const coords = this.viewport.getPointerCoords(ev);
      const hit = this.cadScene.pickBrepFace(
        this.cameraController.activeCamera,
        coords.ndcX,
        coords.ndcY,
      );
      if (hit && Array.isArray(hit.point)) {
        this.cameraController.focusPoint(hit.point[0], hit.point[1], hit.point[2]);
      }
    });
  }

  /**
   * Toggle `#cad-shortcuts-hud` visibility (`?` or `H`).
   *
   * @param {boolean} [forceVisible] - Optional explicit visibility.
   */
  toggleShortcutsHud(forceVisible) {
    const hud = this._el("cad-shortcuts-hud");
    const btn = this._el("btn-shortcuts");
    if (!hud) return;
    const next = typeof forceVisible === "boolean" ? forceVisible : !hud.classList.contains("visible");
    hud.classList.toggle("visible", next);
    if (btn) btn.classList.toggle("active", next);
  }

  /**
   * Step UI scale up (`+1`) or down (`-1`) or reset (`0`) via `Cmd/Ctrl +/-/0`.
   *
   * @param {-1|0|1} direction - Scale step direction.
   */
  _stepUiScale(direction) {
    const sel = /** @type {HTMLSelectElement|null} */ (this._el("uiScaleSelect"));
    if (direction === 0) {
      if (sel) sel.value = "100%";
      applyUiScale(this.ctx, "100%", {
        storageKey: "scope_ui_scale",
        persistValue: "100%",
        onScaleChange: () => this.viewport.resize(),
      });
      return;
    }
    const curVal = (sel && sel.value) || "100%";
    const idx = Math.max(0, UI_SCALE_STEPS.indexOf(curVal));
    const nextIdx = Math.max(0, Math.min(UI_SCALE_STEPS.length - 1, idx + direction));
    const nextVal = UI_SCALE_STEPS[nextIdx];
    if (sel) sel.value = nextVal;
    applyUiScale(this.ctx, nextVal, {
      storageKey: "scope_ui_scale",
      persistValue: nextVal,
      onScaleChange: () => this.viewport.resize(),
    });
  }

  /**
   * Handle global Scope keyboard shortcuts.
   *
   * @param {KeyboardEvent} ev - Keyboard event.
   */
  _onKeyDown(ev) {
    const tag = ev.target && ev.target.tagName ? String(ev.target.tagName).toUpperCase() : "";
    const isInput = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || ev.target?.isContentEditable;

    // UI Scale & Undo with Cmd/Ctrl
    if (ev.metaKey || ev.ctrlKey) {
      if (ev.key === "=" || ev.key === "+") {
        ev.preventDefault();
        this._stepUiScale(1);
        return;
      }
      if (ev.key === "-") {
        ev.preventDefault();
        this._stepUiScale(-1);
        return;
      }
      if (ev.key === "0") {
        ev.preventDefault();
        this._stepUiScale(0);
        return;
      }
      if (!isInput && ev.key.toLowerCase() === "z") {
        ev.preventDefault();
        this.markupController.undo();
        return;
      }
    }

    if (ev.key === "Escape") {
      const bugModal = this._el("modal-bug");
      if (bugModal && bugModal.classList.contains("visible")) {
        this.inspector.closeTargetBugModal();
        return;
      }
      const chooserModal = this._el("modal-project-chooser");
      if (chooserModal && chooserModal.classList.contains("visible")) {
        this.inspector.closeProjectChooser();
        return;
      }
      const shortcutsHud = this._el("cad-shortcuts-hud");
      if (shortcutsHud && shortcutsHud.classList.contains("visible")) {
        this.toggleShortcutsHud(false);
        return;
      }
      if (this.rulerTool.clearOrDeactivate()) {
        return;
      }
      if (this.currentMode === "PCB" && (this.pcbRenderer.highlightedNet || this.pcbRenderer.selectedEntity)) {
        this.pcbRenderer.selectedEntity = null;
        this.pcbRenderer.setHighlightedNet("");
        this.inspector.renderNetsList(
          /** @type {HTMLInputElement|null} */ (this._el("net-search"))?.value || "",
        );
        this.viewport.requestRender();
        return;
      }
      this.cadScene.clearFaceHighlight();
      this.viewport.requestRender();
      return;
    }

    if (isInput) {
      return;
    }

    const key = ev.key;
    const lower = key.toLowerCase();

    switch (lower) {
      case "?":
      case "h":
        ev.preventDefault();
        this.toggleShortcutsHud();
        break;
      case "m":
        ev.preventDefault();
        this.rulerTool.toggle();
        break;
      case "b":
        ev.preventDefault();
        this.inspector.openTargetBugModal();
        break;
      case "f":
        ev.preventDefault();
        if (this.currentMode === "PCB") {
          this.cameraController.setPreset("flip", { fit: false });
        } else {
          this.cameraController.setPreset("fit", { fit: true });
        }
        break;
      case ".":
      case "home":
        ev.preventDefault();
        this.cameraController.setPreset("fit", { fit: true });
        break;
      case "0":
        if (!this.cameraController.is2DMode) {
          ev.preventDefault();
          this.cameraController.setPreset("iso", { fit: true });
        }
        break;
      case "1":
        ev.preventDefault();
        if (this.currentMode === "PCB") {
          this.cameraController.setPreset("bottom", { fit: false });
        } else if (!this.cameraController.is2DMode) {
          this.cameraController.setPreset(ev.ctrlKey ? "rear" : "front", { fit: true });
        }
        break;
      case "3":
        if (!this.cameraController.is2DMode) {
          ev.preventDefault();
          this.cameraController.setPreset(ev.ctrlKey ? "left" : "right", { fit: true });
        }
        break;
      case "7":
        ev.preventDefault();
        if (this.currentMode === "PCB") {
          this.cameraController.setPreset("top", { fit: false });
        } else if (!this.cameraController.is2DMode) {
          this.cameraController.setPreset(ev.ctrlKey ? "bottom" : "top", { fit: true });
        }
        break;
      case "5":
        if (!this.cameraController.is2DMode) {
          ev.preventDefault();
          this.cameraController.toggleProjection();
          this.viewport.setCamera(this.cameraController.activeCamera);
        }
        break;
      case "z":
        if (!this.cameraController.is2DMode) {
          ev.preventDefault();
          const wf = this.cadScene.setWireframe();
          const camWire = this._el("cam-wire");
          if (camWire) camWire.classList.toggle("active", wf);
          this.viewport.requestRender();
        }
        break;
      case "w":
      case "arrowup":
        ev.preventDefault();
        this.cameraController.panBySteps(0, 1);
        break;
      case "s":
      case "arrowdown":
        ev.preventDefault();
        this.cameraController.panBySteps(0, -1);
        break;
      case "a":
      case "arrowleft":
        ev.preventDefault();
        this.cameraController.panBySteps(-1, 0);
        break;
      case "d":
      case "arrowright":
        ev.preventDefault();
        this.cameraController.panBySteps(1, 0);
        break;
      case "+":
      case "=":
        ev.preventDefault();
        this.cameraController.zoomByStep(1);
        break;
      case "-":
      case "_":
        ev.preventDefault();
        this.cameraController.zoomByStep(-1);
        break;
      case " ":
        if (this.currentMode === "SIMULATE") {
          ev.preventDefault();
          this.simRenderer.togglePlay();
          this._syncSimPlayButtonState();
        }
        break;
      case "x":
      case "delete":
      case "backspace":
        if (this.markupController.toolbarOpen) {
          ev.preventDefault();
          this.markupController.clearAll();
        }
        break;
      default:
        break;
    }
  }

  /**
   * Show or hide `#modal-sync-progress` during geometry compilation or workspace sync.
   *
   * @param {boolean} visible - Modal visibility.
   * @param {string} [stageText] - Primary stage title.
   * @param {string} [detailText] - Subtitle detail.
   * @param {number} [percent] - Progress bar percentage `0..100`.
   */
  _setSyncProgress(visible, stageText = "", detailText = "", percent = 0) {
    const modal = this._el("modal-sync-progress");
    if (!modal) return;
    modal.classList.toggle("visible", visible);
    if (!visible) return;

    const st = this._el("sync-stage-text");
    const dt = this._el("sync-stage-detail");
    const bar = this._el("sync-progress-bar");
    const pct = this._el("sync-percent-text");
    if (st && stageText) st.textContent = stageText;
    if (dt) dt.textContent = detailText;
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (pct) pct.textContent = `${Math.round(percent)}%`;
  }

  /**
   * Boot the Scope Workstation: discover projects and load initial target (or open chooser).
   */
  async boot() {
    this.inspector.applyModeUiState(this.currentMode, {
      project: this.currentProject,
      target: this.currentTarget,
      subassembly: this.currentSub,
    });
    this.viewport.setModeTheme(this.currentMode);

    if (!this.autoLoad) {
      return;
    }

    const projectsResp = await this.ctx.fetchJson("/api/scope/projects");
    if (projectsResp && Array.isArray(projectsResp.projects)) {
      this.inspector.projects = projectsResp.projects;
    }

    if (this.currentProject && this.currentTarget) {
      await this.loadTarget({
        project: this.currentProject,
        target: this.currentTarget,
        subassembly: this.currentSub,
        mode: this.currentMode,
        maxSteps: this.maxSteps,
      });
    } else {
      this.inspector.openProjectChooser();
    }
  }

  /**
   * Synchronize manifests & clear server caches via `GET /api/scope/sync`, then reload active target.
   */
  async syncWorkspace() {
    this._setSyncProgress(true, "Synchronizing manifests & clearing caches...", "GET /api/scope/sync", 35);
    const resp = await this.ctx.fetchJson("/api/scope/sync");
    const projResp = await this.ctx.fetchJson("/api/scope/projects");
    if (projResp && Array.isArray(projResp.projects)) {
      this.inspector.projects = projResp.projects;
    }
    this._setSyncProgress(false);
    if (resp && resp.status === "ok") {
      showToast(this.ctx, "Manifests synchronized", "success");
      if (this.currentProject && this.currentTarget) {
        await this.loadTarget({
          project: this.currentProject,
          target: this.currentTarget,
          subassembly: this.currentSub,
          mode: this.currentMode,
          maxSteps: this.maxSteps,
        });
      }
    }
  }

  /**
   * Load geometry (and PCB metadata or Simulation telemetry) for the specified target & mode.
   *
   * @param {object} selection - Target selection.
   * @param {string} selection.project - Project identifier.
   * @param {string} selection.target - Target identifier.
   * @param {string} [selection.subassembly] - Optional subassembly filter.
   * @param {string} [selection.mode] - Visualization mode (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`).
   * @param {number} [selection.maxSteps] - Max simulation steps.
   */
  async loadTarget({ project, target, subassembly = "", mode = "CAD", maxSteps = 1000 }) {
    const upperMode = String(mode || "CAD").toUpperCase();
    this.currentProject = project;
    this.currentTarget = target;
    this.currentSub = subassembly || "";
    this.currentMode = upperMode;
    this.maxSteps = maxSteps || 1000;

    // Tear down active renderers cleanly before switching modes
    this.simRenderer.clear();
    this.pcbRenderer.clear();
    this.cadScene.clear();
    this.rulerTool.toggle(false);

    const explodeSlider = /** @type {HTMLInputElement|null} */ (this._el("view-explode-slider"));
    const explodeVal = this._el("view-explode-val");
    if (explodeSlider) explodeSlider.value = "0";
    if (explodeVal) explodeVal.textContent = "0%";

    this.inspector.applyModeUiState(upperMode, {
      project: this.currentProject,
      target: this.currentTarget,
      subassembly: this.currentSub,
    });
    this.viewport.setModeTheme(upperMode);

    const queryParts = [
      `project=${encodeURIComponent(project)}`,
      `target=${encodeURIComponent(target)}`,
      `mode=${encodeURIComponent(upperMode)}`,
    ];
    if (this.currentSub) {
      queryParts.push(`subassembly=${encodeURIComponent(this.currentSub)}`);
    }

    this._setSyncProgress(
      true,
      `Loading ${project}/${target} [${upperMode}]...`,
      "Streaming tessellated geometry & metadata",
      45,
    );

    const payload = await this.ctx.fetchJson(`/api/scope/load?${queryParts.join("&")}`);
    if (!payload || payload.error) {
      this._setSyncProgress(false);
      showToast(this.ctx, (payload && payload.error) || `Failed to load ${project}/${target}`, "error");
      return;
    }

    this._setSyncProgress(true, `Building GPU scene for ${project}/${target}...`, "Uploading vertex & instance buffers", 78);

    const decoded = decodeOcpPayload(this.ctx, payload);
    this.cadScene.loadDecodedPayload(decoded, { mode: upperMode });
    this.inspector.renderCadTree(decoded.treeNodes);

    let fitBounds = decoded.worldBounds;
    if (upperMode === "PCB" && payload.pcb_metadata) {
      this.pcbRenderer.loadMetadata(payload.pcb_metadata);
      this.inspector.populatePcbSidebar(payload.pcb_metadata);
      this.inspector.renderPcbInspection(null);
    } else {
      this.inspector.renderBrepInspection(null);
    }

    this.cameraController.configureForMode(upperMode, {
      bounds: fitBounds,
      viewFrom: payload.view_from || null,
    });
    this.viewport.setCamera(this.cameraController.activeCamera);

    if (upperMode === "SIMULATE") {
      this._setSyncProgress(
        true,
        `Streaming Rerun fluid telemetry for ${project}/${target}...`,
        "Decoding undecimated 3D voxel frames",
        90,
      );
      const simPayload = await this.ctx.fetchJson(
        `/api/scope/simulation_telemetry?project=${encodeURIComponent(project)}&target=${encodeURIComponent(target)}`,
      );
      if (simPayload && simPayload.status === "ok") {
        this.simRenderer.loadTelemetry(simPayload);
        this.inspector.populateSimulationMetrics(simPayload);
        this._syncSimStyleButtons();
      } else {
        this.inspector.populateSimulationMetrics(null);
      }
    }

    this._setSyncProgress(false);
    this.viewport.resize();
    this.viewport.requestRender();
  }

  /**
   * Dispose WebGL, animation frames, and sub-renderers cleanly.
   */
  destroy() {
    this.simRenderer.clear();
    this.pcbRenderer.clear();
    this.cadScene.clear();
    this.viewport.dispose();
  }
}

/**
 * Factory helper creating and optionally booting a `ScopeWorkstationApp` for an explicit `RuntimeContext`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} [options] - Optional overrides (`renderer`, `autoLoad`).
 * @returns {ScopeWorkstationApp}
 */
export function createScopeApp(ctx, options = {}) {
  const app = new ScopeWorkstationApp(ctx, options);
  if (options.autoBoot !== false) {
    void app.boot();
  }
  return app;
}

// Auto-boot when loaded in a browser document containing `#cad-view`
const runtimeCtx = getRuntimeContext();
const runtimeDoc = runtimeCtx.getDocument();
if (runtimeDoc && runtimeDoc.getElementById("cad-view")) {
  createScopeApp(runtimeCtx);
}
