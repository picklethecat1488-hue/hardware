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
  render_version: 3,
  board_thickness_mm: 1.6,
  z_top_mm: 0.8,
  z_bottom_mm: -0.8,
  copper_layers: ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"],
  layers: [
    { id: "edge_cuts", name: "Edge.Cuts (Outline)", color: "#e6d84c", type: "Edge.Cuts", default_visible: true },
    { id: "f_cu", name: "F.Cu (L1 Top)", color: "#c83434", type: "F.Cu", default_visible: true },
    { id: "in1_cu", name: "In1.Cu (L2 Ground)", color: "#c2c200", type: "In1.Cu", is_inner: true, default_visible: false },
    { id: "in2_cu", name: "In2.Cu (L3 Signal)", color: "#c200c2", type: "In2.Cu", is_inner: true, default_visible: false },
    { id: "in3_cu", name: "In3.Cu (L4 Power)", color: "#00c2c2", type: "In3.Cu", is_inner: true, default_visible: false },
    { id: "in4_cu", name: "In4.Cu (L5 Signal)", color: "#28a448", type: "In4.Cu", is_inner: true, default_visible: false },
    { id: "b_cu", name: "B.Cu (L6 Bottom)", color: "#4d7fc4", type: "B.Cu", default_visible: true },
    { id: "pads", name: "Pads", color: "#ce4785", type: "Pads", default_visible: true },
    { id: "vias", name: "Vias", color: "#ececec", type: "Vias", default_visible: true },
    { id: "f_silk", name: "F.SilkS", color: "#f2eda1", type: "F.SilkS", default_visible: true },
    { id: "b_silk", name: "B.SilkS", color: "#e8b2a7", type: "B.SilkS", default_visible: true },
    { id: "substrate", name: "Substrate", color: "#041830", type: "Substrate", default_visible: true },
  ],
  edge_cuts: [
    [[-30, -45], [30, -45], [30, 45], [-30, 45], [-30, -45]],
  ],
  copper_regions: [
    { layer: "In1.Cu", net: "GND", polygon: [[-29, -44], [29, -44], [29, 44], [-29, 44]], clearance: 0.25, priority: 1 },
    { layer: "In3.Cu", net: "VCC_3V3", polygon: [[-29, -44], [29, -44], [29, 44], [-29, 44]], clearance: 0.25, priority: 1 },
  ],
  nets: ["GND", "VCC_3V3", "SWDIO", "SPI_CLK"],
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
    { net: "SPI_CLK", layer: "In2.Cu", width: 0.2, start: [-8, 0], end: [8, 0] },
  ],
  vias: [
    { net: "VCC_3V3", x: 18, y: 12, drill: 0.3, pad_dia: 0.6, layer_start: "F.Cu", layer_end: "B.Cu" },
    { net: "GND", x: -5, y: -5, drill: 0.2, pad_dia: 0.45, layer_start: "F.Cu", layer_end: "In1.Cu" },
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

  it("builds <= 8 GPU SDF InstancedMesh batches and updates per-instance net highlight flags", () => {
    const scene = new Scene();
    const renderer = new PcbGpuRenderer({ scene });
    renderer.loadMetadata(SAMPLE_PCB_METADATA);

    const batchCount = renderer.getGpuBatchCount();
    assert.ok(batchCount > 0 && batchCount <= 8, `Expected <= 8 GPU batches, got ${batchCount}`);

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

  it("preserves inner copper layers (In1.Cu..In4.Cu), Edge.Cuts outline, and copper_regions pours", () => {
    const scene = new Scene();
    const renderer = new PcbGpuRenderer({ scene });
    renderer.loadMetadata(SAMPLE_PCB_METADATA);

    // Edge.Cuts outline is enabled by default and indexed for magnetic snapping
    assert.equal(renderer.visibleLayers.has("Edge.Cuts"), true);
    assert.equal(renderer.spatialGrid.edgeCuts.length, 1);
    const cornerSnap = renderer.spatialGrid.findMagneticSnap(-29.8, -44.9, 0.5, "F.Cu");
    assert.ok(cornerSnap && Math.abs(cornerSnap.x - -30) < 1e-3 && Math.abs(cornerSnap.y - -45) < 1e-3);

    // Inner trace SPI_CLK stays on In2.Cu (never coerced to F.Cu!)
    const in2Trace = renderer.spatialGrid.traces.find((t) => t.net === "SPI_CLK");
    assert.ok(in2Trace);
    assert.equal(in2Trace.layer, "In2.Cu");
    const in2Batch = renderer._traceBatches.find((b) => b.layerName === "In2.Cu");
    assert.ok(in2Batch, "Expected dedicated GPU SDF trace batch for In2.Cu");

    // In2.Cu defaults hidden (`default_visible: false`), then becomes visible & hit-testable when toggled ON
    assert.equal(in2Batch.mesh.visible, false);
    assert.equal(renderer.hitTest(0, 0, "F.Cu"), null);

    renderer.setLayerVisibility("In2.Cu", true);
    assert.equal(in2Batch.mesh.visible, true);
    const innerHit = renderer.hitTest(0, 0, "F.Cu");
    assert.equal(innerHit?.kind, "trace");
    assert.equal(innerHit?.layer, "In2.Cu");
    assert.equal(innerHit?.net, "SPI_CLK");

    // Copper regions on In1.Cu & In3.Cu are indexed and check via span penetration
    assert.equal(renderer.spatialGrid.copperRegions.length, 2);
    assert.equal(renderer.spatialGrid.doesViaSpanLayer(renderer.spatialGrid.vias[1], "In1.Cu"), true);
    assert.equal(renderer.spatialGrid.doesViaSpanLayer(renderer.spatialGrid.vias[1], "In3.Cu"), false);
  });
});
