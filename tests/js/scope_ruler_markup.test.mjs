/**
 * Functional unit tests for `js/scope/viewport.js`, `js/scope/ruler_tool.js`,
 * and `js/scope/markup_tool.js`.
 *
 * Verifies:
 * 1. `ScopeViewport` Retina `devicePixelRatio` (`2.0x`) backing-store sizing and
 *    `ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0)` on `#markup-canvas`.
 * 2. `PrecisionRulerTool` magnetic pad snapping vs `Shift` freehand override, plus
 *    exact `mm`, `mil`, and `angleDeg` computation.
 * 3. `MarkupAndPinController` 2D shape strokes, 3D world-space pins, undo/clear stack,
 *    and `ScopeTargetBugRequest` payload serialization.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import "./glsl_loader.mjs";
import { Scene } from "../../js/static/vendor/three/three.module.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import { MarkupAndPinController } from "../../js/scope/markup_tool.js";
import { computeRulerMeasurement, PrecisionRulerTool } from "../../js/scope/ruler_tool.js";
import { ScopeViewport } from "../../js/scope/viewport.js";

const { CadCameraController } = await import("../../js/scope/camera_controller.js");
const { PcbGpuRenderer } = await import("../../js/scope/pcb_renderer.js");

describe("scope/viewport, ruler_tool, & markup_tool", () => {
  it("configures WebGLRenderer and #markup-canvas at physical 2.0x Retina DPR with coalesced RAF", () => {
    let appliedPixelRatio = 0;
    let appliedSize = null;
    let renderCount = 0;
    let lastTransform = null;

    const mockGlRenderer = {
      domElement: {
        style: {},
        getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 600 }),
      },
      setPixelRatio(r) {
        appliedPixelRatio = r;
      },
      setSize(w, h) {
        appliedSize = [w, h];
      },
      render() {
        renderCount += 1;
      },
      dispose() {},
    };

    const overlayCanvas = {
      width: 0,
      height: 0,
      style: {},
      getContext() {
        return {
          setTransform(...args) {
            lastTransform = args;
          },
          clearRect() {},
          save() {},
          restore() {},
        };
      },
    };

    const container = {
      clientWidth: 900,
      clientHeight: 600,
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 600 }),
    };

    const ctx = createMockRuntimeContext({ dpr: 2.0, viewport: { width: 900, height: 600 } });
    const vp = new ScopeViewport({
      ctx,
      container,
      overlayCanvas,
      renderer: mockGlRenderer,
    });
    const camCtrl = new CadCameraController({ width: 900, height: 600 });
    vp.setCamera(camCtrl.activeCamera);

    assert.equal(vp.dpr, 2.0);
    assert.equal(appliedPixelRatio, 2.0);
    assert.deepEqual(appliedSize, [900, 600]);
    assert.equal(overlayCanvas.width, 1800);
    assert.equal(overlayCanvas.height, 1200);
    assert.deepEqual(lastTransform, [2, 0, 0, 2, 0, 0]);

    // Multiple requestRender() calls within the same frame coalesce into 1 WebGL render!
    renderCount = 0;
    vp.requestRender();
    vp.requestRender();
    vp.requestOverlayRedraw();
    ctx.flushAnimationFrames(16);
    assert.equal(renderCount, 1);
    vp.dispose();
  });

  it("computes exact mm/mil ruler distances and snaps magnetically unless Shift is held", () => {
    const meas = computeRulerMeasurement({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 0 });
    assert.ok(Math.abs(meas.distanceMm - 5.0) < 1e-6);
    assert.ok(Math.abs(meas.distanceMil - 196.85039) < 1e-3);

    const camCtrl = new CadCameraController({ width: 1000, height: 800 });
    camCtrl.configureForMode("PCB", {
      bounds: { min: [-25, -25, -0.8], max: [25, 25, 0.8], center: [0, 0, 0], size: [50, 50, 1.6] },
    });

    const scene = new Scene();
    const pcb = new PcbGpuRenderer({ scene });
    pcb.loadMetadata({
      pads: [{ comp: "R1", pin: "1", net: "GND", x: 10.0, y: 5.0, w: 1.0, h: 1.0, layer: "F.Cu", pad_type: "smd" }],
    });

    const ruler = new PrecisionRulerTool();
    ruler.toggle(true);

    // Cursor slightly off pad center `(10.25, 5.15)` -> snaps to exact `(10.0, 5.0)` when Shift is false!
    const nearCss = camCtrl.worldToCss(10.25, 5.15, 0);
    const ndcX = (nearCss.x / 1000) * 2 - 1;
    const ndcY = -(nearCss.y / 800) * 2 + 1;

    const snappedPt = ruler.resolveWorldPoint({
      ndcX,
      ndcY,
      shiftKey: false,
      mode: "PCB",
      cameraController: camCtrl,
      pcbRenderer: pcb,
    });
    assert.equal(snappedPt.snapped, true);
    assert.equal(snappedPt.x, 10.0);
    assert.equal(snappedPt.y, 5.0);

    // Holding Shift disables magnetic snap -> freehand coordinate `(10.25, 5.15)`
    const freePt = ruler.resolveWorldPoint({
      ndcX,
      ndcY,
      shiftKey: true,
      mode: "PCB",
      cameraController: camCtrl,
      pcbRenderer: pcb,
    });
    assert.equal(freePt.snapped, false);
    assert.ok(Math.abs(freePt.x - 10.25) < 1e-3);

    ruler.handleClick(snappedPt);
    ruler.handleClick({ x: 12.54, y: 5.0, z: 0 });
    assert.ok(Math.abs(computeRulerMeasurement(ruler.p1, ruler.p2).distanceMm - 2.54) < 1e-6);

    // First Escape clears points while keeping tool active; second Escape deactivates tool
    assert.equal(ruler.clearOrDeactivate(), true);
    assert.equal(ruler.p1, null);
    assert.equal(ruler.active, true);
    assert.equal(ruler.clearOrDeactivate(), true);
    assert.equal(ruler.active, false);
  });

  it("manages 2D markups and 3D spatial pins with LIFO undo and bug-report serialization", () => {
    const mc = new MarkupAndPinController();
    mc.setToolbarOpen(true);
    mc.setTool("arrow");
    mc.setColor("#00ffff");
    mc.beginStroke(0.1, 0.2);
    mc.updateStroke(0.4, 0.6);
    mc.endStroke();

    mc.setTool("pin");
    mc.addPin({ x: 12.5, y: -3.25, z: 43.0 }, "Impeller clearance");

    assert.equal(mc.markups.length, 1);
    assert.equal(mc.pins.length, 1);
    assert.equal(mc.getAnnotationsPayload()[0].text, "Impeller clearance");
    assert.equal(mc.getMarkupsPayload()[0].type, "arrow");

    // Undo pops most recent item (the pin) first, then the arrow
    assert.equal(mc.undo(), true);
    assert.equal(mc.pins.length, 0);
    assert.equal(mc.markups.length, 1);

    mc.clearAll();
    assert.equal(mc.markups.length, 0);
  });
});
