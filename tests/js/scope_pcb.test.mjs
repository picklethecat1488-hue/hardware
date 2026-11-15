/**
 * Functional unit tests for `js/scope/pcb_spatial_index.js` and `js/scope/pcb_renderer.js`.
 *
 * Verifies:
 * 1. $O(1)$ `PcbSpatialGrid` priority hit-testing (`pad` > `via` > `trace` > `component`,
 *    and bare FR-4 substrate returning `null`).
 * 2. Strict `activeSide` (`F.Cu` vs `B.Cu`) occlusion: front-side SMD pads, `F.Cu` traces,
 *    and `F.SilkS` labels NEVER appear or hit-test when viewing `B.Cu` (while plated
 *    through-hole pads and vias ARE accessible from both sides!).
 * 3. `PcbGpuRenderer` <= 6 GPU `InstancedMesh` batches and instant `setHighlightedNet`
 *    attribute updates.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import "./glsl_loader.mjs";
import { Scene } from "../../js/static/vendor/three/three.module.js";
import { PcbSpatialGrid } from "../../js/scope/pcb_spatial_index.js";

const { PcbGpuRenderer } = await import("../../js/scope/pcb_renderer.js");

const SAMPLE_PCB_METADATA = {
  render_version: 2,
  board_thickness_mm: 1.6,
  z_top_mm: 0.8,
  z_bottom_mm: -0.8,
  nets: ["GND", "VCC_3V3", "SWDIO"],
  components: [
    { ref_des: "U1", footprint: "QFN-32", layer: "F.Cu", x: 10, y: 10, value: "STM32" },
    { ref_des: "C4", footprint: "0402", layer: "B.Cu", x: -12, y: 6, value: "100nF" },
  ],
  pads: [
    { comp: "U1", pin: "VDD", number: "1", net: "VCC_3V3", x: 10, y: 12, w: 0.8, h: 0.4, layer: "F.Cu", shape: "roundrect", pad_type: "smd", drill: 0 },
    { comp: "C4", pin: "1", number: "1", net: "VCC_3V3", x: -12, y: 6, w: 0.6, h: 0.6, layer: "B.Cu", shape: "roundrect", pad_type: "smd", drill: 0 },
    { comp: "J1", pin: "GND", number: "2", net: "GND", x: 0, y: -15, w: 1.6, h: 1.6, layer: "F.Cu", shape: "circle", pad_type: "thru_hole", drill: 0.9 },
  ],
  test_points: [
    { comp: "TP1", id: "TP_SWDIO", net: "SWDIO", x: 22, y: -4, w: 1.2, h: 1.2, layer: "B.Cu", shape: "circle" },
  ],
  traces: [
    { net: "VCC_3V3", layer: "F.Cu", width: 0.35, start: [10, 12], end: [18, 12] },
    { net: "SWDIO", layer: "B.Cu", width: 0.25, start: [15, -4], end: [22, -4] },
  ],
  vias: [
    { net: "VCC_3V3", x: 18, y: 12, drill: 0.3, pad_dia: 0.6 },
  ],
  silkscreen_texts: [
    { text: "U1", layer: "F.SilkS", x: 10, y: 14, font_size: 1.0, rotation: 0 },
    { text: "C4", layer: "B.SilkS", x: -12, y: 8, font_size: 1.0, rotation: 0 },
  ],
  silkscreen_graphics: [
    { shape: "rect", layer: "F.SilkS", x: 10, y: 10, w: 5, h: 5, thickness: 0.15, fill: false },
  ],
};

describe("scope/pcb_spatial_index & pcb_renderer", () => {
  it("resolves pads, vias, traces, and through-hole pads strictly for the active board side and ignores bare substrate", () => {
    const grid = new PcbSpatialGrid(2.0);
    grid.buildFromMetadata(SAMPLE_PCB_METADATA);

    // 1. Bare FR-4 substrate far from copper -> null (never steals selection!)
    assert.equal(grid.queryPoint(-35, -20, { activeSide: "F.Cu" }), null);

    // 2. Top SMD pad U1.VDD hits on F.Cu, but MUST NOT hit when viewing B.Cu!
    const topHit = grid.queryPoint(10.1, 12.05, { activeSide: "F.Cu" });
    assert.equal(topHit?.kind, "pad");
    assert.equal(topHit?.comp, "U1");
    assert.equal(topHit?.net, "VCC_3V3");
    assert.equal(grid.queryPoint(10.1, 12.05, { activeSide: "B.Cu" }), null);

    // 3. Bottom test point TP1 hits on B.Cu, NOT on F.Cu
    const botTp = grid.queryPoint(22.0, -4.0, { activeSide: "B.Cu" });
    assert.equal(botTp?.kind, "test_point");
    assert.equal(botTp?.net, "SWDIO");
    assert.equal(grid.queryPoint(22.0, -4.0, { activeSide: "F.Cu" }), null);

    // 4. Plated Through-Hole pad J1.GND and Via hit on BOTH F.Cu and B.Cu!
    assert.equal(grid.queryPoint(0, -15, { activeSide: "F.Cu" })?.comp, "J1");
    assert.equal(grid.queryPoint(0, -15, { activeSide: "B.Cu" })?.comp, "J1");
    assert.equal(grid.queryPoint(18, 12, { activeSide: "F.Cu" })?.kind, "via");
    assert.equal(grid.queryPoint(18, 12, { activeSide: "B.Cu" })?.kind, "via");
  });

  it("prevents front-side net labels and silkscreen from bleeding into B.Cu frustum overlays", () => {
    const grid = new PcbSpatialGrid(2.0);
    grid.buildFromMetadata(SAMPLE_PCB_METADATA);
    const fullBoard = { minX: -50, minY: -50, maxX: 50, maxY: 50 };

    const frontOverlays = grid.queryFrustumOverlays(fullBoard, { activeSide: "F.Cu" });
    assert.ok(frontOverlays.pads.some((p) => p.comp === "U1"));
    assert.ok(!frontOverlays.pads.some((p) => p.comp === "C4"));
    assert.ok(frontOverlays.traces.every((t) => t.layer === "F.Cu"));
    assert.ok(frontOverlays.silkTexts.every((s) => s.layer === "F.SilkS"));

    const backOverlays = grid.queryFrustumOverlays(fullBoard, { activeSide: "B.Cu" });
    assert.ok(backOverlays.pads.some((p) => p.comp === "C4"));
    assert.ok(backOverlays.pads.some((p) => p.comp === "J1"), "Thru-hole pad visible on back");
    assert.ok(!backOverlays.pads.some((p) => p.comp === "U1"), "Front SMD pad must NOT bleed onto B.Cu");
    assert.ok(backOverlays.traces.every((t) => t.layer === "B.Cu"), "Front trace labels must NOT bleed onto B.Cu");
    assert.ok(backOverlays.silkTexts.every((s) => s.layer === "B.SilkS"));
    assert.equal(backOverlays.silkGraphics.length, 0);
  });

  it("builds <= 6 GPU SDF InstancedMesh batches and updates per-instance net highlight flags", () => {
    const scene = new Scene();
    const renderer = new PcbGpuRenderer({ scene });
    renderer.loadMetadata(SAMPLE_PCB_METADATA);

    const batchCount = renderer.getGpuBatchCount();
    assert.ok(batchCount > 0 && batchCount <= 6, `Expected <= 6 GPU batches, got ${batchCount}`);

    renderer.setHighlightedNet("VCC_3V3");
    assert.equal(renderer.highlightedNet, "VCC_3V3");

    // Verify F.Cu trace highlight attribute (`styleAttr.array[1] === 1.0`) and external .glsl shader sources
    const fcuTraceBatch = renderer._traceBatches.find((b) => b.layerName === "F.Cu");
    assert.ok(fcuTraceBatch.mesh.material.vertexShader.includes("attribute vec4 aTraceGeom;"));
    assert.ok(fcuTraceBatch.mesh.material.fragmentShader.includes("void main()"));
    assert.equal(fcuTraceBatch.styleAttr.array[1], 1.0);

    // Verify B.Cu trace (`SWDIO`) is NOT highlighted (`0.0`)
    const bcuTraceBatch = renderer._traceBatches.find((b) => b.layerName === "B.Cu");
    assert.equal(bcuTraceBatch.styleAttr.array[1], 0.0);

    // Toggle F.Cu layer off -> GPU trace mesh hides immediately
    renderer.setLayerVisibility("F.Cu", false);
    assert.equal(fcuTraceBatch.mesh.visible, false);
    renderer.enableAllLayers();
    assert.equal(fcuTraceBatch.mesh.visible, true);
  });
});
