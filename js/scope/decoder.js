/**
 * Zero-Globals OCP Instanced Geometry & B-Rep Topology Decoder.
 *
 * Decodes `ocp_viewer_core` v3 instanced tessellation buffers into typed arrays,
 * flattens hierarchical `ShapeTreeNode` assemblies with composed world transforms,
 * builds prefix-sum triangle/segment offset tables for $O(\log F)$ B-rep face/edge
 * lookup, and computes exact analytical surface metrics (planar area/normal,
 * cylindrical radius/diameter/axis).
 */

const BYTES_PER_NUMBER_32 = 4;
const COORDS_PER_VERTEX = 3;
const INDICES_PER_TRIANGLE = 3;
const COORDS_PER_SEGMENT = 6;
const QUAT_COMPONENTS = 4;
const DEFAULT_PART_COLOR = "#8a99ad";
const EPSILON = 1e-9;

/**
 * Canonical OpenCascade `GeomAbs_SurfaceType` enum names emitted by `ocp_viewer_core`.
 * @type {ReadonlyArray<string>}
 */
export const FACE_TYPE_NAMES = Object.freeze([
  "Plane",
  "Cylinder",
  "Cone",
  "Sphere",
  "Torus",
  "BezierSurface",
  "BSplineSurface",
  "SurfaceOfRevolution",
  "SurfaceOfExtrusion",
  "OffsetSurface",
  "OtherSurface",
]);

/**
 * Canonical OpenCascade `GeomAbs_CurveType` enum names emitted by `ocp_viewer_core`.
 * @type {ReadonlyArray<string>}
 */
export const EDGE_TYPE_NAMES = Object.freeze([
  "Line",
  "Circle",
  "Ellipse",
  "Hyperbola",
  "Parabola",
  "BezierCurve",
  "BSplineCurve",
  "OffsetCurve",
  "OtherCurve",
]);

/**
 * Decode an `ocp_viewer_core` buffer descriptor (`{ buffer, dtype, codec }` or plain array)
 * into the requested TypedArray using `ctx.decodeBase64Bytes`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object|Array<number>|ArrayBufferView|null|undefined} raw - Encoded buffer field.
 * @param {"float32"|"uint32"|"int32"} targetType - Desired typed array element kind.
 * @returns {Float32Array|Uint32Array|Int32Array}
 */
export function decodeTypedBuffer(ctx, raw, targetType) {
  const Ctor =
    targetType === "float32"
      ? Float32Array
      : targetType === "uint32"
        ? Uint32Array
        : Int32Array;

  if (!raw) {
    return new Ctor(0);
  }
  if (raw instanceof Ctor) {
    return raw;
  }
  if (ArrayBuffer.isView(raw)) {
    return new Ctor(raw);
  }
  if (Array.isArray(raw)) {
    return Ctor.from(raw);
  }
  if (typeof raw === "object" && typeof raw.buffer === "string") {
    const bytes = ctx.decodeBase64Bytes(raw.buffer);
    if (bytes.byteLength === 0) {
      return new Ctor(0);
    }
    const elemCount = Math.floor(bytes.byteLength / BYTES_PER_NUMBER_32);
    if (bytes.byteOffset % BYTES_PER_NUMBER_32 === 0) {
      return new Ctor(bytes.buffer, bytes.byteOffset, elemCount);
    }
    const alignedCopy = bytes.slice(0, elemCount * BYTES_PER_NUMBER_32);
    return new Ctor(alignedCopy.buffer, 0, elemCount);
  }
  return new Ctor(0);
}

/**
 * Build a prefix-sum cumulative offset table of length `counts.length + 1`.
 *
 * @param {Int32Array|Uint32Array} counts - Per-entity primitive counts.
 * @returns {Uint32Array} Cumulative start offsets (`offsets[i]` .. `offsets[i + 1]`).
 */
export function buildPrefixOffsets(counts) {
  const offsets = new Uint32Array(counts.length + 1);
  let running = 0;
  for (let idx = 0; idx < counts.length; idx += 1) {
    offsets[idx] = running;
    running += Math.max(0, counts[idx]);
  }
  offsets[counts.length] = running;
  return offsets;
}

/**
 * Compute axis-aligned bounding box `{ min, max, center, size }` from flat `XYZ` float32 coordinates.
 *
 * @param {Float32Array} vertices - Flat `[x0, y0, z0, ...]` buffer.
 * @returns {{min: [number, number, number], max: [number, number, number], center: [number, number, number], size: [number, number, number]}|null}
 */
export function computeBufferBounds(vertices) {
  if (!vertices || vertices.length < COORDS_PER_VERTEX) {
    return null;
  }
  let minX = Infinity;
  let minY = Infinity;
  let minZ = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let maxZ = -Infinity;

  for (let idx = 0; idx <= vertices.length - COORDS_PER_VERTEX; idx += COORDS_PER_VERTEX) {
    const vx = vertices[idx];
    const vy = vertices[idx + 1];
    const vz = vertices[idx + 2];
    if (vx < minX) minX = vx;
    if (vy < minY) minY = vy;
    if (vz < minZ) minZ = vz;
    if (vx > maxX) maxX = vx;
    if (vy > maxY) maxY = vy;
    if (vz > maxZ) maxZ = vz;
  }

  return {
    min: [minX, minY, minZ],
    max: [maxX, maxY, maxZ],
    center: [(minX + maxX) * 0.5, (minY + maxY) * 0.5, (minZ + maxZ) * 0.5],
    size: [maxX - minX, maxY - minY, maxZ - minZ],
  };
}

/**
 * Multiply two unit quaternions `a * b` given as `[x, y, z, w]`.
 *
 * @param {[number, number, number, number]} qa - Left quaternion.
 * @param {[number, number, number, number]} qb - Right quaternion.
 * @returns {[number, number, number, number]}
 */
export function multiplyQuaternions(qa, qb) {
  const [ax, ay, az, aw] = qa;
  const [bx, by, bz, bw] = qb;
  return [
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

/**
 * Rotate a 3D vector `[vx, vy, vz]` by unit quaternion `[qx, qy, qz, qw]`.
 *
 * @param {[number, number, number]} vec - Input vector.
 * @param {[number, number, number, number]} quat - Unit quaternion.
 * @returns {[number, number, number]}
 */
export function rotateVectorByQuaternion(vec, quat) {
  const [vx, vy, vz] = vec;
  const [qx, qy, qz, qw] = quat;
  const tx = 2 * (qy * vz - qz * vy);
  const ty = 2 * (qz * vx - qx * vz);
  const tz = 2 * (qx * vy - qy * vx);
  return [
    vx + qw * tx + (qy * tz - qz * ty),
    vy + qw * ty + (qz * tx - qx * tz),
    vz + qw * tz + (qx * ty - qy * tx),
  ];
}

/**
 * Normalize an `ocp_viewer_core` `loc` tuple `[[tx, ty, tz], [qx, qy, qz, qw]]`.
 *
 * @param {Array<any>|null|undefined} rawLoc - Raw location tuple.
 * @returns {{translation: [number, number, number], quaternion: [number, number, number, number]}}
 */
export function normalizeLocation(rawLoc) {
  const rawTrans = Array.isArray(rawLoc) && Array.isArray(rawLoc[0]) ? rawLoc[0] : [0, 0, 0];
  const rawQuat = Array.isArray(rawLoc) && Array.isArray(rawLoc[1]) ? rawLoc[1] : [0, 0, 0, 1];
  const translation = [
    Number(rawTrans[0]) || 0,
    Number(rawTrans[1]) || 0,
    Number(rawTrans[2]) || 0,
  ];
  const qx = Number(rawQuat[0]) || 0;
  const qy = Number(rawQuat[1]) || 0;
  const qz = Number(rawQuat[2]) || 0;
  const qw = rawQuat.length >= QUAT_COMPONENTS && Number.isFinite(Number(rawQuat[3])) ? Number(rawQuat[3]) : 1;
  const norm = Math.hypot(qx, qy, qz, qw) || 1;
  return {
    translation,
    quaternion: [qx / norm, qy / norm, qz / norm, qw / norm],
  };
}

/**
 * Compose parent and child rigid locations `parent * child`.
 *
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} parent - Parent world location.
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} child - Child local location.
 * @returns {{translation: [number, number, number], quaternion: [number, number, number, number]}}
 */
export function composeLocations(parent, child) {
  const rotatedChildPos = rotateVectorByQuaternion(child.translation, parent.quaternion);
  return {
    translation: [
      parent.translation[0] + rotatedChildPos[0],
      parent.translation[1] + rotatedChildPos[1],
      parent.translation[2] + rotatedChildPos[2],
    ],
    quaternion: multiplyQuaternions(parent.quaternion, child.quaternion),
  };
}

/**
 * Transform a local bounding box into world space and merge into aggregate bounds.
 *
 * @param {{min: number[], max: number[]}} localBounds - Local AABB.
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} worldLoc - World rigid transform.
 * @returns {{min: [number, number, number], max: [number, number, number], center: [number, number, number], size: [number, number, number]}}
 */
export function transformBounds(localBounds, worldLoc) {
  const [minX, minY, minZ] = localBounds.min;
  const [maxX, maxY, maxZ] = localBounds.max;
  const corners = [
    [minX, minY, minZ],
    [maxX, minY, minZ],
    [minX, maxY, minZ],
    [maxX, maxY, minZ],
    [minX, minY, maxZ],
    [maxX, minY, maxZ],
    [minX, maxY, maxZ],
    [maxX, maxY, maxZ],
  ];

  let wMinX = Infinity;
  let wMinY = Infinity;
  let wMinZ = Infinity;
  let wMaxX = -Infinity;
  let wMaxY = -Infinity;
  let wMaxZ = -Infinity;

  for (const corner of corners) {
    const rot = rotateVectorByQuaternion(corner, worldLoc.quaternion);
    const wx = rot[0] + worldLoc.translation[0];
    const wy = rot[1] + worldLoc.translation[1];
    const wz = rot[2] + worldLoc.translation[2];
    if (wx < wMinX) wMinX = wx;
    if (wy < wMinY) wMinY = wy;
    if (wz < wMinZ) wMinZ = wz;
    if (wx > wMaxX) wMaxX = wx;
    if (wy > wMaxY) wMaxY = wy;
    if (wz > wMaxZ) wMaxZ = wz;
  }

  return {
    min: [wMinX, wMinY, wMinZ],
    max: [wMaxX, wMaxY, wMaxZ],
    center: [(wMinX + wMaxX) * 0.5, (wMinY + wMaxY) * 0.5, (wMinZ + wMaxZ) * 0.5],
    size: [wMaxX - wMinX, wMaxY - wMinY, wMaxZ - wMinZ],
  };
}

/**
 * Decode a complete `ScopeGeometryPipeline` payload (`instances` + `shapes` tree)
 * into ready-to-upload typed buffers, flattened leaf descriptors, tree hierarchy,
 * and aggregate world bounding box.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} payload - JSON geometry response from `/api/scope/load`.
 * @returns {{
 *   instances: Array<object>,
 *   leaves: Array<object>,
 *   treeNodes: Array<object>,
 *   worldBounds: {min: [number, number, number], max: [number, number, number], center: [number, number, number], size: [number, number, number]},
 *   totalTriangles: number,
 *   totalSegments: number
 * }}
 */
export function decodeOcpPayload(ctx, payload) {
  const rawInstances = Array.isArray(payload?.instances) ? payload.instances : [];
  const instances = rawInstances.map((inst, index) => {
    const vertices = decodeTypedBuffer(ctx, inst.vertices, "float32");
    const normals = decodeTypedBuffer(ctx, inst.normals, "float32");
    const triangles = decodeTypedBuffer(ctx, inst.triangles, "uint32");
    const edges = decodeTypedBuffer(ctx, inst.edges, "float32");
    const objVertices = decodeTypedBuffer(ctx, inst.obj_vertices, "float32");
    const faceTypes = decodeTypedBuffer(ctx, inst.face_types, "int32");
    const edgeTypes = decodeTypedBuffer(ctx, inst.edge_types, "int32");
    const trianglesPerFace = decodeTypedBuffer(ctx, inst.triangles_per_face, "uint32");
    const segmentsPerEdge = decodeTypedBuffer(ctx, inst.segments_per_edge, "uint32");

    const faceTriangleOffsets = buildPrefixOffsets(trianglesPerFace);
    const edgeSegmentOffsets = buildPrefixOffsets(segmentsPerEdge);
    const localBounds = computeBufferBounds(vertices) || computeBufferBounds(edges) || computeBufferBounds(objVertices);

    return {
      index,
      vertices,
      normals,
      triangles,
      edges,
      objVertices,
      faceTypes,
      edgeTypes,
      trianglesPerFace,
      segmentsPerEdge,
      faceTriangleOffsets,
      edgeSegmentOffsets,
      triangleCount: Math.floor(triangles.length / INDICES_PER_TRIANGLE),
      segmentCount: Math.floor(edges.length / COORDS_PER_SEGMENT),
      localBounds,
    };
  });

  const leaves = [];
  let totalTriangles = 0;
  let totalSegments = 0;

  let wMinX = Infinity;
  let wMinY = Infinity;
  let wMinZ = Infinity;
  let wMaxX = -Infinity;
  let wMaxY = -Infinity;
  let wMaxZ = -Infinity;

  const mergeBounds = (b) => {
    if (!b) return;
    if (b.min[0] < wMinX) wMinX = b.min[0];
    if (b.min[1] < wMinY) wMinY = b.min[1];
    if (b.min[2] < wMinZ) wMinZ = b.min[2];
    if (b.max[0] > wMaxX) wMaxX = b.max[0];
    if (b.max[1] > wMaxY) wMaxY = b.max[1];
    if (b.max[2] > wMaxZ) wMaxZ = b.max[2];
  };

  const identityLoc = normalizeLocation(null);
  const rootShapes = payload?.shapes || {};

  const walkNode = (node, parentLoc, parentColor, parentAlpha, depth) => {
    const localLoc = normalizeLocation(node.loc);
    const worldLoc = composeLocations(parentLoc, localLoc);
    const color = typeof node.color === "string" ? node.color : parentColor;
    const alpha = typeof node.alpha === "number" ? node.alpha : parentAlpha;
    const stateArr = Array.isArray(node.state) ? node.state : [1, 1];
    const shapeVisible = stateArr[0] !== 0;
    const edgesVisible = stateArr[1] !== 0;
    const nodeId = String(node.id || node.name || `node_${leaves.length}`);
    const nodeName = String(node.name || nodeId.split("/").pop() || nodeId);

    const treeEntry = {
      id: nodeId,
      name: nodeName,
      depth,
      color,
      alpha,
      visible: shapeVisible,
      edgesVisible,
      leafIds: [],
      children: [],
    };

    if (Array.isArray(node.parts) && node.parts.length > 0) {
      for (const child of node.parts) {
        const childEntry = walkNode(child, worldLoc, color, alpha, depth + 1);
        treeEntry.children.push(childEntry);
        for (const leafId of childEntry.leafIds) {
          treeEntry.leafIds.push(leafId);
        }
      }
      return treeEntry;
    }

    let instance = null;
    if (node.shape && typeof node.shape.ref === "number") {
      instance = instances[node.shape.ref] || null;
    } else if (node.shape && (node.shape.vertices || node.shape.edges)) {
      const inlineVertices = decodeTypedBuffer(ctx, node.shape.vertices, "float32");
      const inlineNormals = decodeTypedBuffer(ctx, node.shape.normals, "float32");
      const inlineTriangles = decodeTypedBuffer(ctx, node.shape.triangles, "uint32");
      const inlineEdges = decodeTypedBuffer(ctx, node.shape.edges, "float32");
      const inlineFaceTypes = decodeTypedBuffer(ctx, node.shape.face_types, "int32");
      const inlineEdgeTypes = decodeTypedBuffer(ctx, node.shape.edge_types, "int32");
      const inlineTriPerFace = decodeTypedBuffer(ctx, node.shape.triangles_per_face, "uint32");
      const inlineSegPerEdge = decodeTypedBuffer(ctx, node.shape.segments_per_edge, "uint32");
      instance = {
        index: -1,
        vertices: inlineVertices,
        normals: inlineNormals,
        triangles: inlineTriangles,
        edges: inlineEdges,
        objVertices: decodeTypedBuffer(ctx, node.shape.obj_vertices, "float32"),
        faceTypes: inlineFaceTypes,
        edgeTypes: inlineEdgeTypes,
        trianglesPerFace: inlineTriPerFace,
        segmentsPerEdge: inlineSegPerEdge,
        faceTriangleOffsets: buildPrefixOffsets(inlineTriPerFace),
        edgeSegmentOffsets: buildPrefixOffsets(inlineSegPerEdge),
        triangleCount: Math.floor(inlineTriangles.length / INDICES_PER_TRIANGLE),
        segmentCount: Math.floor(inlineEdges.length / COORDS_PER_SEGMENT),
        localBounds: computeBufferBounds(inlineVertices) || computeBufferBounds(inlineEdges),
      };
    }

    if (instance) {
      const leafWorldBounds = instance.localBounds ? transformBounds(instance.localBounds, worldLoc) : null;
      mergeBounds(leafWorldBounds);
      totalTriangles += instance.triangleCount;
      totalSegments += instance.segmentCount;

      const leaf = {
        id: nodeId,
        name: nodeName,
        linkKey: nodeName.split("/").pop(),
        ref: instance.index,
        instance,
        color,
        alpha,
        visible: shapeVisible,
        edgesVisible,
        renderback: Boolean(node.renderback),
        location: worldLoc,
        worldBounds: leafWorldBounds,
      };
      leaves.push(leaf);
      treeEntry.leafIds.push(nodeId);
    }

    return treeEntry;
  };

  const rootParts = Array.isArray(rootShapes.parts) ? rootShapes.parts : [];
  const rootLoc = normalizeLocation(rootShapes.loc);
  const treeNodes = rootParts.map((part) => walkNode(part, rootLoc || identityLoc, DEFAULT_PART_COLOR, 1.0, 0));

  let worldBounds = null;
  if (Number.isFinite(wMinX) && Number.isFinite(wMaxX)) {
    worldBounds = {
      min: [wMinX, wMinY, wMinZ],
      max: [wMaxX, wMaxY, wMaxZ],
      center: [(wMinX + wMaxX) * 0.5, (wMinY + wMaxY) * 0.5, (wMinZ + wMaxZ) * 0.5],
      size: [wMaxX - wMinX, wMaxY - wMinY, wMaxZ - wMinZ],
    };
  } else if (rootShapes.bb && typeof rootShapes.bb === "object") {
    const bb = rootShapes.bb;
    const minX = Number(bb.xmin) || -50;
    const maxX = Number(bb.xmax) || 50;
    const minY = Number(bb.ymin) || -50;
    const maxY = Number(bb.ymax) || 50;
    const minZ = Number(bb.zmin) || -50;
    const maxZ = Number(bb.zmax) || 50;
    worldBounds = {
      min: [minX, minY, minZ],
      max: [maxX, maxY, maxZ],
      center: [(minX + maxX) * 0.5, (minY + maxY) * 0.5, (minZ + maxZ) * 0.5],
      size: [maxX - minX, maxY - minY, maxZ - minZ],
    };
  } else {
    worldBounds = {
      min: [-50, -50, -50],
      max: [50, 50, 50],
      center: [0, 0, 0],
      size: [100, 100, 100],
    };
  }

  return {
    instances,
    leaves,
    treeNodes,
    worldBounds,
    totalTriangles,
    totalSegments,
  };
}

/**
 * Binary-search `offsets` (`Uint32Array` of length `N + 1`) to locate the entity index
 * owning primitive `primitiveIndex`.
 *
 * @param {Uint32Array} offsets - Monotonic cumulative offset array.
 * @param {number} primitiveIndex - Zero-based triangle or segment index.
 * @returns {number} Owning face/edge index, or `-1` if out of range.
 */
export function binarySearchOffsetBucket(offsets, primitiveIndex) {
  if (!offsets || offsets.length < 2 || primitiveIndex < 0) {
    return -1;
  }
  const count = offsets.length - 1;
  if (primitiveIndex >= offsets[count]) {
    return -1;
  }
  let low = 0;
  let high = count - 1;
  while (low <= high) {
    const mid = (low + high) >>> 1;
    const start = offsets[mid];
    const end = offsets[mid + 1];
    if (primitiveIndex < start) {
      high = mid - 1;
    } else if (primitiveIndex >= end) {
      low = mid + 1;
    } else {
      return mid;
    }
  }
  return -1;
}

/**
 * Resolve topological B-rep face metadata from a raycasted `triangleIndex` in $O(\log F)$.
 *
 * @param {object} instance - Decoded instance descriptor from `decodeOcpPayload`.
 * @param {number} triangleIndex - Hit triangle index (`0 .. triangleCount - 1`).
 * @returns {{faceIndex: number, surfaceType: string, surfaceTypeCode: number, startTriangle: number, endTriangle: number}|null}
 */
export function lookupBrepFace(instance, triangleIndex) {
  if (!instance || !instance.faceTriangleOffsets) {
    return null;
  }
  const faceIndex = binarySearchOffsetBucket(instance.faceTriangleOffsets, triangleIndex);
  if (faceIndex < 0) {
    return null;
  }
  const code = instance.faceTypes && faceIndex < instance.faceTypes.length ? instance.faceTypes[faceIndex] : -1;
  const surfaceType = FACE_TYPE_NAMES[code] || "OtherSurface";
  return {
    faceIndex,
    surfaceType,
    surfaceTypeCode: code,
    startTriangle: instance.faceTriangleOffsets[faceIndex],
    endTriangle: instance.faceTriangleOffsets[faceIndex + 1],
  };
}

/**
 * Resolve topological B-rep edge metadata from a segment index in $O(\log E)$.
 *
 * @param {object} instance - Decoded instance descriptor.
 * @param {number} segmentIndex - Hit segment index (`0 .. segmentCount - 1`).
 * @returns {{edgeIndex: number, curveType: string, curveTypeCode: number, startSegment: number, endSegment: number}|null}
 */
export function lookupBrepEdge(instance, segmentIndex) {
  if (!instance || !instance.edgeSegmentOffsets) {
    return null;
  }
  const edgeIndex = binarySearchOffsetBucket(instance.edgeSegmentOffsets, segmentIndex);
  if (edgeIndex < 0) {
    return null;
  }
  const code = instance.edgeTypes && edgeIndex < instance.edgeTypes.length ? instance.edgeTypes[edgeIndex] : -1;
  const curveType = EDGE_TYPE_NAMES[code] || "OtherCurve";
  return {
    edgeIndex,
    curveType,
    curveTypeCode: code,
    startSegment: instance.edgeSegmentOffsets[edgeIndex],
    endSegment: instance.edgeSegmentOffsets[edgeIndex + 1],
  };
}

/**
 * Compute geometric surface properties for a B-rep face (`areaMm2`, `centroid`, `normal`,
 * and fitted `radiusMm` / `diameterMm` for cylindrical or spherical surfaces).
 *
 * @param {object} instance - Decoded instance descriptor.
 * @param {number} faceIndex - Zero-based B-rep face index.
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} [worldLocation] - Optional world transform.
 * @returns {{
 *   faceIndex: number,
 *   surfaceType: string,
 *   triangleCount: number,
 *   areaMm2: number,
 *   centroid: [number, number, number],
 *   normal: [number, number, number],
 *   radiusMm: number|null,
 *   diameterMm: number|null
 * }|null}
 */
export function measureBrepFace(instance, faceIndex, worldLocation = null) {
  if (!instance || !instance.faceTriangleOffsets) {
    return null;
  }
  const faceCount = instance.faceTriangleOffsets.length - 1;
  if (faceIndex < 0 || faceIndex >= faceCount) {
    return null;
  }
  const startTri = instance.faceTriangleOffsets[faceIndex];
  const endTri = instance.faceTriangleOffsets[faceIndex + 1];
  if (endTri <= startTri) {
    return null;
  }

  const code = instance.faceTypes && faceIndex < instance.faceTypes.length ? instance.faceTypes[faceIndex] : -1;
  const surfaceType = FACE_TYPE_NAMES[code] || "OtherSurface";
  const loc = worldLocation || normalizeLocation(null);

  const verts = instance.vertices;
  const tris = instance.triangles;

  let areaSum = 0;
  let cxSum = 0;
  let cySum = 0;
  let czSum = 0;
  let nxSum = 0;
  let nySum = 0;
  let nzSum = 0;

  const transformVertex = (vIdx) => {
    const base = vIdx * COORDS_PER_VERTEX;
    const local = [verts[base], verts[base + 1], verts[base + 2]];
    const rot = rotateVectorByQuaternion(local, loc.quaternion);
    return [
      rot[0] + loc.translation[0],
      rot[1] + loc.translation[1],
      rot[2] + loc.translation[2],
    ];
  };

  const sampledVertices = [];

  for (let tIdx = startTri; tIdx < endTri; tIdx += 1) {
    const iBase = tIdx * INDICES_PER_TRIANGLE;
    const i0 = tris[iBase];
    const i1 = tris[iBase + 1];
    const i2 = tris[iBase + 2];

    const p0 = transformVertex(i0);
    const p1 = transformVertex(i1);
    const p2 = transformVertex(i2);
    if (sampledVertices.length < 96) {
      sampledVertices.push(p0, p1, p2);
    }

    const ux = p1[0] - p0[0];
    const uy = p1[1] - p0[1];
    const uz = p1[2] - p0[2];
    const vx = p2[0] - p0[0];
    const vy = p2[1] - p0[1];
    const vz = p2[2] - p0[2];

    const crossX = uy * vz - uz * vy;
    const crossY = uz * vx - ux * vz;
    const crossZ = ux * vy - uy * vx;
    const doubleArea = Math.hypot(crossX, crossY, crossZ);
    const triArea = doubleArea * 0.5;

    areaSum += triArea;
    cxSum += ((p0[0] + p1[0] + p2[0]) / 3) * triArea;
    cySum += ((p0[1] + p1[1] + p2[1]) / 3) * triArea;
    czSum += ((p0[2] + p1[2] + p2[2]) / 3) * triArea;
    nxSum += crossX * 0.5;
    nySum += crossY * 0.5;
    nzSum += crossZ * 0.5;
  }

  const safeArea = Math.max(areaSum, EPSILON);
  const centroid = [cxSum / safeArea, cySum / safeArea, czSum / safeArea];
  const nLen = Math.hypot(nxSum, nySum, nzSum) || 1;
  const normal = [nxSum / nLen, nySum / nLen, nzSum / nLen];

  let radiusMm = null;
  let diameterMm = null;

  if (surfaceType === "Cylinder" && sampledVertices.length >= 6) {
    radiusMm = estimateCylinderRadius(instance, startTri, endTri, loc);
    if (radiusMm !== null) {
      diameterMm = radiusMm * 2;
    }
  } else if (surfaceType === "Sphere" && sampledVertices.length >= 4) {
    radiusMm = estimateSphereRadius(instance, startTri, endTri, loc);
    if (radiusMm !== null) {
      diameterMm = radiusMm * 2;
    }
  }

  return {
    faceIndex,
    surfaceType,
    triangleCount: endTri - startTri,
    areaMm2: areaSum,
    centroid,
    normal,
    radiusMm,
    diameterMm,
  };
}

/**
 * Estimate analytical cylinder radius from vertex positions and vertex normals:
 * for a right circular cylinder, `p_i + R * n_i` (or `p_i - R * n_i`) lies on the cylinder axis,
 * and consecutive cross-sectional chords satisfy `|Δp_⊥| = R * |Δn_⊥|`.
 *
 * @param {object} instance - Decoded instance.
 * @param {number} startTri - First triangle index of the cylindrical face.
 * @param {number} endTri - Exclusive end triangle index.
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} loc - World location.
 * @returns {number|null}
 */
function estimateCylinderRadius(instance, startTri, endTri, loc) {
  const verts = instance.vertices;
  const norms = instance.normals;
  const tris = instance.triangles;
  if (!norms || norms.length !== verts.length) {
    return null;
  }

  const ratios = [];
  const maxSamples = Math.min(endTri, startTri + 64);

  for (let tIdx = startTri; tIdx < maxSamples; tIdx += 1) {
    const base = tIdx * INDICES_PER_TRIANGLE;
    const indices = [tris[base], tris[base + 1], tris[base + 2]];
    for (let edge = 0; edge < 3; edge += 1) {
      const ia = indices[edge] * COORDS_PER_VERTEX;
      const ib = indices[(edge + 1) % 3] * COORDS_PER_VERTEX;

      const na = rotateVectorByQuaternion([norms[ia], norms[ia + 1], norms[ia + 2]], loc.quaternion);
      const nb = rotateVectorByQuaternion([norms[ib], norms[ib + 1], norms[ib + 2]], loc.quaternion);
      const dnX = nb[0] - na[0];
      const dnY = nb[1] - na[1];
      const dnZ = nb[2] - na[2];
      const dnNorm = Math.hypot(dnX, dnY, dnZ);
      if (dnNorm < 0.05) {
        continue;
      }

      const pa = rotateVectorByQuaternion([verts[ia], verts[ia + 1], verts[ia + 2]], loc.quaternion);
      const pb = rotateVectorByQuaternion([verts[ib], verts[ib + 1], verts[ib + 2]], loc.quaternion);
      const dpX = pb[0] - pa[0];
      const dpY = pb[1] - pa[1];
      const dpZ = pb[2] - pa[2];

      // Project chord onto normal-difference direction to eliminate axial displacement component!
      const proj = Math.abs(dpX * dnX + dpY * dnY + dpZ * dnZ) / (dnNorm * dnNorm);
      if (Number.isFinite(proj) && proj > 1e-3) {
        ratios.push(proj);
      }
    }
  }

  if (ratios.length === 0) {
    return null;
  }
  ratios.sort((a, b) => a - b);
  return ratios[ratios.length >>> 1];
}

/**
 * Estimate sphere radius from `|dp · dn| / |dn|^2` across face triangle edges.
 *
 * @param {object} instance - Decoded instance.
 * @param {number} startTri - Start triangle index.
 * @param {number} endTri - End triangle index.
 * @param {{translation: [number, number, number], quaternion: [number, number, number, number]}} loc - World location.
 * @returns {number|null}
 */
function estimateSphereRadius(instance, startTri, endTri, loc) {
  return estimateCylinderRadius(instance, startTri, endTri, loc);
}
