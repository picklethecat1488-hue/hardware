/**
 * Functional unit tests for `js/scope/camera_controller.js` (`CadCameraController`).
 *
 * Verifies:
 * 1. 2D planar (`PCB` / `DIAGRAM`) locked `+Y` up vector (`(0, 1, 0)`), disabled rotation,
 *    and exact `(panX, panY)` preservation across `Top` (`F.Cu`) <-> `Bottom` (`B.Cu`) `Flip`.
 * 2. Exact $O(1)$ affine `screenNdcToPlaneZ` round-trip accuracy with `worldToCss` on both
 *    `F.Cu` and X-mirrored `B.Cu` views.
 * 3. Synchronized Perspective (`fov=35`) <-> Orthographic (`5`) frustum-height parity.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import "./glsl_loader.mjs";

const { CadCameraController, DEFAULT_FOV_DEG } = await import("../../js/scope/camera_controller.js");

const SAMPLE_PCB_BOUNDS = {
  min: [-40, -25, -0.8],
  max: [40, 25, 0.8],
  center: [0, 0, 0],
  size: [80, 50, 1.6],
};

describe("scope/camera_controller", () => {
  it("locks rotation in PCB 2D mode, uses +Y up without gimbal lock, and preserves pan/zoom on Flip", () => {
    const camCtrl = new CadCameraController({ width: 1200, height: 800 });
    camCtrl.configureForMode("PCB", { bounds: SAMPLE_PCB_BOUNDS });

    assert.equal(camCtrl.is2DMode, true);
    assert.equal(camCtrl.isOrtho, true);
    assert.equal(camCtrl.controls.enableRotate, false);
    assert.equal(camCtrl.activeBoardSide, "F.Cu");
    assert.deepEqual(
      [camCtrl.activeCamera.up.x, camCtrl.activeCamera.up.y, camCtrl.activeCamera.up.z],
      [0, 1, 0],
    );

    // Pan off-center and zoom in
    camCtrl.panBySteps(2, -1);
    camCtrl.zoomByStep(1);
    const pannedX = camCtrl.controls.target.x;
    const pannedY = camCtrl.controls.target.y;
    const zoomedVal = camCtrl.orthoCamera.zoom;
    assert.notEqual(pannedX, 0);
    assert.notEqual(pannedY, 0);

    // Flip to B.Cu (`F`): pan target `(x, y)` and zoom MUST be preserved identically!
    camCtrl.setPreset("flip", { fit: false });
    assert.equal(camCtrl.activeBoardSide, "B.Cu");
    assert.ok(camCtrl.activeCamera.position.z < 0, "B.Cu camera must view from -Z");
    assert.ok(Math.abs(camCtrl.controls.target.x - pannedX) < 1e-6);
    assert.ok(Math.abs(camCtrl.controls.target.y - pannedY) < 1e-6);
    assert.ok(Math.abs(camCtrl.orthoCamera.zoom - zoomedVal) < 1e-6);
    assert.deepEqual(
      [camCtrl.activeCamera.up.x, camCtrl.activeCamera.up.y, camCtrl.activeCamera.up.z],
      [0, 1, 0],
    );
  });

  it("maps screenNdcToPlaneZ <-> worldToCss with sub-micrometer accuracy on both F.Cu and B.Cu", () => {
    const camCtrl = new CadCameraController({ width: 1000, height: 600 });
    camCtrl.configureForMode("PCB", { bounds: SAMPLE_PCB_BOUNDS });

    for (const side of ["top", "bottom"]) {
      camCtrl.setPreset(side, { fit: false });
      const testBoardPt = { x: 17.35, y: -9.8 };
      const css = camCtrl.worldToCss(testBoardPt.x, testBoardPt.y, 0);
      const ndcX = (css.x / 1000) * 2 - 1;
      const ndcY = -(css.y / 600) * 2 + 1;

      const roundTrip = camCtrl.screenNdcToPlaneZ(ndcX, ndcY, 0);
      assert.ok(Math.abs(roundTrip.x - testBoardPt.x) < 1e-4, `X mismatch on ${side}`);
      assert.ok(Math.abs(roundTrip.y - testBoardPt.y) < 1e-4, `Y mismatch on ${side}`);
    }
  });

  it("preserves exact visible world millimeter-per-pixel scale when toggling Perspective <-> Orthographic", () => {
    const camCtrl = new CadCameraController({ width: 1280, height: 720 });
    camCtrl.configureForMode("CAD", {
      bounds: {
        min: [-60, -60, 0],
        max: [60, 60, 90],
        center: [0, 0, 45],
        size: [120, 120, 90],
      },
    });

    assert.equal(camCtrl.isOrtho, false);
    assert.equal(camCtrl.perspCamera.fov, DEFAULT_FOV_DEG);
    const mmPerPxPersp = camCtrl.getMillimetersPerCssPixel();

    // Toggle to Orthographic (`5`)
    camCtrl.toggleProjection(true);
    assert.equal(camCtrl.isOrtho, true);
    const mmPerPxOrtho = camCtrl.getMillimetersPerCssPixel();
    assert.ok(Math.abs(mmPerPxOrtho - mmPerPxPersp) < 1e-5);

    // Zoom in while in Orthographic, then toggle back to Perspective (`5`)
    camCtrl.zoomByStep(1);
    const mmPerPxZoomedOrtho = camCtrl.getMillimetersPerCssPixel();
    camCtrl.toggleProjection(false);
    assert.equal(camCtrl.isOrtho, false);
    const mmPerPxZoomedPersp = camCtrl.getMillimetersPerCssPixel();
    assert.ok(Math.abs(mmPerPxZoomedPersp - mmPerPxZoomedOrtho) < 1e-5);
  });

  it("zooms responsively on two-finger trackpad scroll and ctrlKey pinch gestures (BUG-LUSTROUS-TICK-848)", () => {
    const camCtrl = new CadCameraController({ width: 1200, height: 800 });
    camCtrl.configureForMode("SIMULATE", {
      bounds: {
        min: [-100, -100, 0],
        max: [100, 100, 115],
        center: [0, 0, 57.5],
        size: [200, 200, 115],
      },
    });

    const distBeforeScroll = camCtrl.perspCamera.position.distanceTo(camCtrl.controls.target);
    camCtrl.controls._handleMouseWheel({
      deltaY: -20,
      deltaMode: 0,
      ctrlKey: false,
      clientX: 600,
      clientY: 400,
      preventDefault() {},
    });
    const distAfterScroll = camCtrl.perspCamera.position.distanceTo(camCtrl.controls.target);
    const scrollReductionFraction = (distBeforeScroll - distAfterScroll) / distBeforeScroll;
    assert.ok(
      scrollReductionFraction >= 0.05,
      `Expected >= 5% zoom on -20px trackpad scroll tick, got ${(scrollReductionFraction * 100).toFixed(2)}%`,
    );

    const distBeforePinch = camCtrl.perspCamera.position.distanceTo(camCtrl.controls.target);
    camCtrl.controls._handleMouseWheel({
      deltaY: -5,
      deltaMode: 0,
      ctrlKey: true,
      clientX: 600,
      clientY: 400,
      preventDefault() {},
    });
    const distAfterPinch = camCtrl.perspCamera.position.distanceTo(camCtrl.controls.target);
    const pinchReductionFraction = (distBeforePinch - distAfterPinch) / distBeforePinch;
    assert.ok(
      pinchReductionFraction >= 0.05,
      `Expected >= 5% zoom on -5px trackpad ctrlKey pinch tick, got ${(pinchReductionFraction * 100).toFixed(2)}%`,
    );
  });
});
