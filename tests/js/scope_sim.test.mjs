/**
 * Functional unit tests for `js/scope/sim_renderer.js` (`SimulationVoxelRenderer`).
 *
 * Verifies:
 * 1. Undecimated binary `positions_b64` decoding (`> 10,000` fluid elements in 1 `InstancedMesh`
 *    draw call — zero `MAX_TELEMETRY_PARTICLES = 4000` decimation!).
 * 2. Exact world-space `3.50 mm` `BoxGeometry` in Voxel mode vs `1.89 mm` `IcosahedronGeometry`
 *    in Sphere mode via `setRenderStyle("voxels" | "spheres")`.
 * 3. Live per-step `/world/impeller` kinematic `Transform3D` quaternion & translation application
 *    onto `CadSceneManager`.
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { describe, it } from "node:test";
import "./glsl_loader.mjs";
import { DoubleSide, FrontSide, Scene } from "../../js/static/vendor/three/three.module.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import { CadSceneManager } from "../../js/scope/cad_scene.js";
import { decodeOcpPayload } from "../../js/scope/decoder.js";

const { SimulationVoxelRenderer } = await import("../../js/scope/sim_renderer.js");

/**
 * Encode a `Float32Array` as base64 string.
 *
 * @param {Float32Array} floats - Source float32 coordinates.
 * @returns {string}
 */
function toBase64Float32(floats) {
  return Buffer.from(floats.buffer, floats.byteOffset, floats.byteLength).toString("base64");
}

describe("scope/sim_renderer", () => {
  it("renders all undecimated voxels in 1 InstancedMesh at exact 3.5mm BoxGeometry size and updates impeller pose", () => {
    const ctx = createMockRuntimeContext();
    const scene = new Scene();
    const cadScene = new CadSceneManager({ scene, dpr: 2.0 });

    // Create a minimal CAD scene with an `impeller` rigid body link at Z = 43.0 mm
    const decoded = decodeOcpPayload(ctx, {
      instances: [
        {
          vertices: [0, 0, 0, 5, 0, 0, 0, 5, 0],
          normals: [0, 0, 1, 0, 0, 1, 0, 0, 1],
          triangles: [0, 1, 2],
        },
      ],
      shapes: {
        parts: [
          {
            id: "/world/impeller",
            name: "impeller",
            loc: [[0, 0, 43.0], [0, 0, 0, 1]],
            shape: { ref: 0 },
          },
        ],
      },
    });
    cadScene.loadDecodedPayload(decoded, { mode: "SIMULATE" });

    // Construct 12,000 undecimated water voxels (> 4,000 legacy cap!)
    const voxelCount = 12000;
    const coords0 = new Float32Array(voxelCount * 3);
    for (let i = 0; i < voxelCount; i += 1) {
      coords0[i * 3] = (i % 30) * 3.5;
      coords0[i * 3 + 1] = (Math.floor(i / 30) % 20) * 3.5;
      coords0[i * 3 + 2] = 14.0 + Math.floor(i / 600) * 3.5;
    }
    const coords1 = new Float32Array(coords0);
    coords1[2] = 77.5;

    const zRot90Quat = [0, 0, Math.SQRT1_2, Math.SQRT1_2];
    const telemetry = {
      status: "ok",
      is_voxel_grid: true,
      voxel_dx_mm: 3.5,
      radius_mm: 1.89,
      default_color: [0.2, 0.7, 0.98, 1.0],
      frames: [
        {
          step: 0,
          count: voxelCount,
          positions_b64: toBase64Float32(coords0),
          transforms: { impeller: { translation: [0, 0, 43.0], quaternion: [0, 0, 0, 1] } },
          metrics: { spout_flow_ml_s: 12.4 },
        },
        {
          step: 10,
          count: voxelCount,
          positions_b64: toBase64Float32(coords1),
          transforms: { impeller: { translation: [0, 0, 43.0], quaternion: zRot90Quat } },
          metrics: { spout_flow_ml_s: 28.9 },
        },
      ],
    };

    const sim = new SimulationVoxelRenderer({ ctx, scene, cadScene });
    sim.loadTelemetry(telemetry);

    // 1. Single InstancedMesh draw call containing all 12,000 voxels + imported .glsl shaders!
    assert.equal(sim.rootGroup.children.length, 1);
    assert.equal(sim._instancedMesh.count, 12000);
    assert.ok(sim._material.vertexShader.includes("attribute vec3 aInstancePos;"));
    assert.ok(sim._material.fragmentShader.includes("void main()"));
    assert.equal(sim.renderStyle, "voxels");
    assert.equal(sim._geometry.parameters.width, 3.5);
    assert.equal(sim._geometry.parameters.height, 3.5);
    assert.equal(sim._geometry.parameters.depth, 3.5);

    // 2. Advance to frame 1 -> impeller rotates to `zRot90Quat` and voxel 0 Z updates to 77.5 mm!
    const summary = sim.setFrameIndex(1);
    assert.equal(summary.step, 10);
    assert.ok(Math.abs(sim._posAttr.array[2] - 77.5) < 1e-4);

    const impellerRecord = cadScene.linkRecordsByName.get("impeller")[0];
    assert.ok(Math.abs(impellerRecord.group.quaternion.z - Math.SQRT1_2) < 1e-5);
    assert.ok(Math.abs(impellerRecord.group.quaternion.w - Math.SQRT1_2) < 1e-5);

    // 3. Toggle to Spheres -> geometry switches to IcosahedronGeometry(1.89) while preserving frame 1!
    sim.setRenderStyle("spheres");
    assert.equal(sim.renderStyle, "spheres");
    assert.equal(sim._geometry.parameters.radius, 1.89);
    assert.equal(sim._instancedMesh.count, 12000);
  });

  it("prevents translucent container inner-wall voxel clipping via FrontSide culling and fluid polygonOffset (BUG-LUSTROUS-TICK-848)", () => {
    const ctx = createMockRuntimeContext();
    const scene = new Scene();
    const cadScene = new CadSceneManager({ scene, dpr: 2.0 });

    const decoded = decodeOcpPayload(ctx, {
      instances: [
        {
          vertices: [0, 0, 0, 10, 0, 0, 0, 10, 0],
          normals: [0, 0, 1, 0, 0, 1, 0, 0, 1],
          triangles: [0, 1, 2],
        },
      ],
      shapes: {
        parts: [
          {
            id: "/world/bowl",
            name: "bowl",
            color: "#1d4ed8",
            alpha: 0.45,
            renderback: false,
            loc: [[0, 0, 0], [0, 0, 0, 1]],
            shape: { ref: 0 },
          },
          {
            id: "/world/baffle_sheet",
            name: "baffle_sheet",
            color: "#38bdf8",
            alpha: 0.5,
            renderback: true,
            loc: [[0, 0, 10], [0, 0, 0, 1]],
            shape: { ref: 0 },
          },
        ],
      },
    });
    cadScene.loadDecodedPayload(decoded, { mode: "SIMULATE" });

    const bowlRec = cadScene.leafRecords.get("/world/bowl");
    const sheetRec = cadScene.leafRecords.get("/world/baffle_sheet");
    assert.equal(
      bowlRec.mesh.material.side,
      FrontSide,
      "Closed translucent 3D solids (renderback=false) must cull internal back-facing cavity walls to prevent voxel corner clipping stripes",
    );
    assert.equal(
      sheetRec.mesh.material.side,
      DoubleSide,
      "Open surfaces with renderback=true must remain DoubleSide",
    );

    const sim = new SimulationVoxelRenderer({ ctx, scene, cadScene });
    sim.loadTelemetry({
      status: "ok",
      is_voxel_grid: true,
      voxel_dx_mm: 3.5,
      frames: [{ step: 0, count: 1, positions: [[94.5, 0, 50.0]] }],
    });
    assert.equal(sim._material.polygonOffset, true);
    assert.ok(sim._material.polygonOffsetFactor > 0);
  });
});
