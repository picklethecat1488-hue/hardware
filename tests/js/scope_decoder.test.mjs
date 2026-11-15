/**
 * Functional unit tests for `js/scope/decoder.js` (`decodeOcpPayload`, `lookupBrepFace`,
 * `lookupBrepEdge`, `measureBrepFace`, and unaligned base64 buffer decoding).
 */

import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { describe, it } from "node:test";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import { Scene } from "../../js/static/vendor/three/three.module.js";
import { CadSceneManager } from "../../js/scope/cad_scene.js";
import {
  decodeOcpPayload,
  decodeTypedBuffer,
  lookupBrepEdge,
  lookupBrepFace,
  measureBrepFace,
} from "../../js/scope/decoder.js";

/**
 * Encode a TypedArray into `{ buffer, dtype, codec: "b64" }`.
 *
 * @param {ArrayBufferView} typedArr - Source typed array.
 * @param {string} dtype - Data type label.
 * @returns {{buffer: string, dtype: string, codec: string}}
 */
function encodeB64Field(typedArr, dtype) {
  const bytes = new Uint8Array(typedArr.buffer, typedArr.byteOffset, typedArr.byteLength);
  return {
    buffer: Buffer.from(bytes).toString("base64"),
    dtype,
    codec: "b64",
  };
}

describe("scope/decoder", () => {
  it("decodes base64 float32/uint32/int32 buffers cleanly even when byteOffset is unaligned", () => {
    // Force an unaligned Uint8Array view (`byteOffset = 1`) inside `decodeBase64Bytes`
    const baseCtx = createMockRuntimeContext();
    const unalignedCtx = {
      ...baseCtx,
      decodeBase64Bytes(b64) {
        const raw = Buffer.from(b64, "base64");
        const padded = new Uint8Array(raw.byteLength + 3);
        padded.set(raw, 1);
        return padded.subarray(1, 1 + raw.byteLength);
      },
    };

    const src = new Float32Array([10.5, -22.25, 0.125, 42.0]);
    const field = encodeB64Field(src, "float32");
    const out = decodeTypedBuffer(unalignedCtx, field, "float32");

    assert.equal(out.length, 4);
    assert.ok(Math.abs(out[0] - 10.5) < 1e-5);
    assert.ok(Math.abs(out[1] + 22.25) < 1e-5);
    assert.ok(Math.abs(out[3] - 42.0) < 1e-5);
  });

  it("decodes hierarchical OCP assembly, composes world transforms, and resolves B-rep Plane & Cylinder faces", () => {
    const ctx = createMockRuntimeContext();

    // Face 0: Planar 10x20 mm rectangle on Z=0 (2 triangles, area = 200 mm^2, normal = +Z)
    // Face 1: Cylindrical ring segment of radius R = 6.0 mm (diameter = 12.0 mm) around Z axis
    const R = 6.0;
    const a0 = 0;
    const a1 = Math.PI / 6;
    const vertices = new Float32Array([
      // Face 0 vertices (0..3)
      0, 0, 0,
      10, 0, 0,
      10, 20, 0,
      0, 20, 0,
      // Face 1 cylinder vertices (4..7)
      R * Math.cos(a0), R * Math.sin(a0), 0,
      R * Math.cos(a1), R * Math.sin(a1), 0,
      R * Math.cos(a1), R * Math.sin(a1), 15,
      R * Math.cos(a0), R * Math.sin(a0), 15,
    ]);

    const normals = new Float32Array([
      0, 0, 1,
      0, 0, 1,
      0, 0, 1,
      0, 0, 1,
      Math.cos(a0), Math.sin(a0), 0,
      Math.cos(a1), Math.sin(a1), 0,
      Math.cos(a1), Math.sin(a1), 0,
      Math.cos(a0), Math.sin(a0), 0,
    ]);

    const triangles = new Uint32Array([
      0, 1, 2,
      0, 2, 3,
      4, 5, 6,
      4, 6, 7,
    ]);

    const edges = new Float32Array([
      0, 0, 0, 10, 0, 0,
      10, 0, 0, 10, 20, 0,
    ]);

    const payload = {
      instances: [
        {
          vertices: encodeB64Field(vertices, "float32"),
          normals: encodeB64Field(normals, "float32"),
          triangles: encodeB64Field(triangles, "uint32"),
          edges: encodeB64Field(edges, "float32"),
          face_types: encodeB64Field(new Int32Array([0, 1]), "int32"), // 0 = Plane, 1 = Cylinder
          triangles_per_face: encodeB64Field(new Uint32Array([2, 2]), "uint32"),
          edge_types: encodeB64Field(new Int32Array([0]), "int32"), // 0 = Line
          segments_per_edge: encodeB64Field(new Uint32Array([2]), "uint32"),
        },
      ],
      shapes: {
        loc: [[5, -3, 12], [0, 0, 0, 1]],
        parts: [
          {
            id: "/root/housing",
            name: "housing",
            color: "#38bdf8",
            alpha: 1.0,
            loc: [[10, 3, 8], [0, 0, 0, 1]],
            shape: { ref: 0 },
            state: [1, 1],
          },
        ],
      },
    };

    const decoded = decodeOcpPayload(ctx, payload);
    assert.equal(decoded.leaves.length, 1);
    assert.equal(decoded.totalTriangles, 4);
    assert.equal(decoded.totalSegments, 2);

    const leaf = decoded.leaves[0];
    // Composed translation: [5 + 10, -3 + 3, 12 + 8] = [15, 0, 20]
    assert.deepEqual(leaf.location.translation, [15, 0, 20]);
    assert.equal(leaf.linkKey, "housing");

    const f0 = lookupBrepFace(leaf.instance, 1);
    assert.equal(f0.faceIndex, 0);
    assert.equal(f0.surfaceType, "Plane");
    const m0 = measureBrepFace(leaf.instance, 0, leaf.location);
    assert.ok(Math.abs(m0.areaMm2 - 200.0) < 1e-3);
    assert.ok(Math.abs(m0.normal[2] - 1.0) < 1e-4);
    assert.ok(Math.abs(m0.centroid[0] - 20.0) < 1e-3); // 15 + 5

    const f1 = lookupBrepFace(leaf.instance, 3);
    assert.equal(f1.faceIndex, 1);
    assert.equal(f1.surfaceType, "Cylinder");
    const m1 = measureBrepFace(leaf.instance, 1, leaf.location);
    assert.ok(Math.abs(m1.radiusMm - 6.0) < 1e-3);
    assert.ok(Math.abs(m1.diameterMm - 12.0) < 1e-3);

    const e0 = lookupBrepEdge(leaf.instance, 1);
    assert.equal(e0.edgeIndex, 0);
    assert.equal(e0.curveType, "Line");
  });

  it("renders 3D PCB copper traces without dark B-rep edge washout and overlays crisp silkscreen on top (BUG-SPOTTED-SPIDER-413)", () => {
    const ctx = createMockRuntimeContext();
    const vertices = new Float32Array([0, 0, 0, 2, 0, 0, 2, 0.2, 0, 0, 0.2, 0]);
    const triangles = new Uint32Array([0, 1, 2, 0, 2, 3]);
    const edges = new Float32Array([0, 0, 0, 2, 0, 0, 2, 0, 0, 2, 0.2, 0]);

    const payload = {
      instances: [
        {
          vertices: encodeB64Field(vertices, "float32"),
          triangles: encodeB64Field(triangles, "uint32"),
          edges: encodeB64Field(edges, "float32"),
        },
      ],
      shapes: {
        parts: [
          {
            id: "/Group/carrier_board_traces_top",
            name: "carrier_board_traces_top",
            color: "#d47e3c",
            parts: [
              { id: "/Group/carrier_board_traces_top/Solid_0", name: "Solid_0", shape: { ref: 0 }, state: [1, 1] },
            ],
          },
          {
            id: "/Group/carrier_board_silkscreen_top",
            name: "carrier_board_silkscreen_top",
            color: "#f5f5f5",
            parts: [
              { id: "/Group/carrier_board_silkscreen_top/Solid_0", name: "Solid_0", shape: { ref: 0 }, state: [1, 1] },
            ],
          },
        ],
      },
    };

    const decoded = decodeOcpPayload(ctx, payload);
    const scene = new Scene();
    const cadScene = new CadSceneManager({ scene, dpr: 2.0 });
    cadScene.loadDecodedPayload(decoded, { mode: "CAD" });

    const traceRec = cadScene.leafRecords.get("/Group/carrier_board_traces_top/Solid_0");
    const silkRec = cadScene.leafRecords.get("/Group/carrier_board_silkscreen_top/Solid_0");

    assert.ok(traceRec && silkRec);
    assert.equal(traceRec.edgeLines, null, "Copper trace segments & endcaps must not have dark B-rep edge outlines");
    assert.equal(silkRec.edgeLines, null, "Silkscreen glyphs must not have dark B-rep edge outlines swallowing strokes");
    assert.ok(traceRec.mesh.material.metalness >= 0.35, "3D copper traces should render with metallic copper luster");
    assert.ok(silkRec.mesh.material.polygonOffsetFactor < traceRec.mesh.material.polygonOffsetFactor, "Silkscreen must bias in front of copper traces");
  });

  it("renders 1D diagram wires with their explicit per-wire colors instead of black silhouette edges (BUG-PINCERED-TARANTULA-172)", () => {
    const ctx = createMockRuntimeContext();
    const wireEdges = new Float32Array([0, 0, 0, 15, 0, 0, 15, 0, 0, 15, 10, 0]);
    const boxVerts = new Float32Array([0, 0, 0, 10, 0, 0, 10, 10, 0]);
    const boxTris = new Uint32Array([0, 1, 2]);

    const payload = {
      instances: [
        {
          vertices: encodeB64Field(new Float32Array(0), "float32"),
          triangles: encodeB64Field(new Uint32Array(0), "uint32"),
          edges: encodeB64Field(wireEdges, "float32"),
        },
        {
          vertices: encodeB64Field(boxVerts, "float32"),
          triangles: encodeB64Field(boxTris, "uint32"),
          edges: encodeB64Field(wireEdges, "float32"),
        },
      ],
      shapes: {
        parts: [
          {
            id: "/Group/wire_vcc_logic",
            name: "wire_vcc_logic",
            color: "#ff0000",
            shape: { ref: 0 },
            state: [1, 1],
          },
          {
            id: "/Group/wire_scl",
            name: "wire_scl",
            color: "#0000ff",
            shape: { ref: 0 },
            state: [1, 1],
          },
          {
            id: "/Group/fp_pico",
            name: "fp_pico",
            color: "#808080",
            shape: { ref: 1 },
            state: [1, 1],
          },
        ],
      },
    };

    const decoded = decodeOcpPayload(ctx, payload);
    const scene = new Scene();
    const cadScene = new CadSceneManager({ scene, dpr: 2.0 });
    cadScene.loadDecodedPayload(decoded, { mode: "DIAGRAM" });

    const vccRec = cadScene.leafRecords.get("/Group/wire_vcc_logic");
    const sclRec = cadScene.leafRecords.get("/Group/wire_scl");
    const picoRec = cadScene.leafRecords.get("/Group/fp_pico");

    assert.equal(vccRec.mesh, null);
    assert.ok(vccRec.edgeLines, "1D wire leaf must emit LineSegments2");
    assert.equal(`#${vccRec.edgeLines.material.color.getHexString()}`, "#ff0000");
    assert.equal(`#${sclRec.edgeLines.material.color.getHexString()}`, "#0000ff");
    assert.equal(`#${picoRec.edgeLines.material.color.getHexString()}`, "#0f172a");
  });
});
