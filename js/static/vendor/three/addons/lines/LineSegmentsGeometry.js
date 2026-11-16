/**
 * Instanced line-segment geometry for screen-space and world-unit wide lines.
 *
 * Adapted from Three.js r184 addons (MIT License) with strict zero-globals
 * compliance, named constants, and clean `toJSON()` serialization.
 */

import {
  Box3,
  Float32BufferAttribute,
  InstancedBufferGeometry,
  InstancedInterleavedBuffer,
  InterleavedBufferAttribute,
  Sphere,
  Vector3,
  WireframeGeometry,
} from "../../three.module.js";

const BASE_QUAD_POSITIONS = [
  -1, 2, 0, 1, 2, 0, -1, 1, 0, 1, 1, 0, -1, 0, 0, 1, 0, 0, -1, -1, 0, 1, -1, 0,
];
const BASE_QUAD_UVS = [-1, 2, 1, 2, -1, 1, 1, 1, -1, -1, 1, -1, -1, -2, 1, -2];
const BASE_QUAD_INDICES = [0, 2, 1, 2, 3, 1, 2, 4, 3, 4, 5, 3, 4, 6, 5, 6, 7, 5];
const INTERLEAVED_SEGMENT_STRIDE = 6;
const VERTEX_COMPONENT_COUNT = 3;
const END_VERTEX_OFFSET = 3;
const UV_COMPONENT_COUNT = 2;

const SCRATCH_BOX = new Box3();
const SCRATCH_VECTOR = new Vector3();

/**
 * Represents a batch of `[startXYZ, endXYZ]` line segments rendered via GPU instancing.
 */
export class LineSegmentsGeometry extends InstancedBufferGeometry {
  /**
   * Initialize the base quad template for instanced wide line segments.
   */
  constructor() {
    super();

    /**
     * Runtime type-guard flag matching Three.js geometry conventions.
     * @type {boolean}
     */
    this.isLineSegmentsGeometry = true;
    this.type = "LineSegmentsGeometry";

    this.setIndex(BASE_QUAD_INDICES);
    this.setAttribute(
      "position",
      new Float32BufferAttribute(BASE_QUAD_POSITIONS, VERTEX_COMPONENT_COUNT),
    );
    this.setAttribute("uv", new Float32BufferAttribute(BASE_QUAD_UVS, UV_COMPONENT_COUNT));
  }

  /**
   * Apply a 4x4 homogeneous transform matrix to both segment endpoints.
   *
   * @param {import("../../three.module.js").Matrix4} matrix - Transformation matrix.
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  applyMatrix4(matrix) {
    const start = this.attributes.instanceStart;
    const end = this.attributes.instanceEnd;

    if (start !== undefined && end !== undefined) {
      start.applyMatrix4(matrix);
      end.applyMatrix4(matrix);
      start.needsUpdate = true;
    }

    if (this.boundingBox !== null) {
      this.computeBoundingBox();
    }
    if (this.boundingSphere !== null) {
      this.computeBoundingSphere();
    }

    return this;
  }

  /**
   * Populate segment endpoint coordinates from a flat `[x0, y0, z0, x1, y1, z1, ...]` buffer.
   *
   * @param {Float32Array|Array<number>} array - Flat endpoint coordinates (multiple of 6).
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  setPositions(array) {
    let lineSegments;
    if (array instanceof Float32Array) {
      lineSegments = array;
    } else if (Array.isArray(array)) {
      lineSegments = new Float32Array(array);
    } else {
      throw new TypeError("LineSegmentsGeometry.setPositions expects Float32Array or Array");
    }

    const instanceBuffer = new InstancedInterleavedBuffer(
      lineSegments,
      INTERLEAVED_SEGMENT_STRIDE,
      1,
    );
    this.setAttribute(
      "instanceStart",
      new InterleavedBufferAttribute(instanceBuffer, VERTEX_COMPONENT_COUNT, 0),
    );
    this.setAttribute(
      "instanceEnd",
      new InterleavedBufferAttribute(instanceBuffer, VERTEX_COMPONENT_COUNT, END_VERTEX_OFFSET),
    );
    this.instanceCount = this.attributes.instanceStart.count;

    this.computeBoundingBox();
    this.computeBoundingSphere();
    return this;
  }

  /**
   * Populate per-segment endpoint RGB colors `[r0, g0, b0, r1, g1, b1, ...]`.
   *
   * @param {Float32Array|Array<number>} array - Flat RGB endpoint colors (multiple of 6).
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  setColors(array) {
    let colors;
    if (array instanceof Float32Array) {
      colors = array;
    } else if (Array.isArray(array)) {
      colors = new Float32Array(array);
    } else {
      throw new TypeError("LineSegmentsGeometry.setColors expects Float32Array or Array");
    }

    const instanceColorBuffer = new InstancedInterleavedBuffer(
      colors,
      INTERLEAVED_SEGMENT_STRIDE,
      1,
    );
    this.setAttribute(
      "instanceColorStart",
      new InterleavedBufferAttribute(instanceColorBuffer, VERTEX_COMPONENT_COUNT, 0),
    );
    this.setAttribute(
      "instanceColorEnd",
      new InterleavedBufferAttribute(
        instanceColorBuffer,
        VERTEX_COMPONENT_COUNT,
        END_VERTEX_OFFSET,
      ),
    );
    return this;
  }

  /**
   * Populate segments from a `WireframeGeometry`.
   *
   * @param {WireframeGeometry} geometry - Source wireframe geometry.
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  fromWireframeGeometry(geometry) {
    this.setPositions(geometry.attributes.position.array);
    return this;
  }

  /**
   * Populate segments from an `EdgesGeometry`.
   *
   * @param {import("../../three.module.js").EdgesGeometry} geometry - Source edges geometry.
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  fromEdgesGeometry(geometry) {
    this.setPositions(geometry.attributes.position.array);
    return this;
  }

  /**
   * Populate wireframe segments from a triangle `Mesh`.
   *
   * @param {import("../../three.module.js").Mesh} mesh - Source mesh.
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  fromMesh(mesh) {
    this.fromWireframeGeometry(new WireframeGeometry(mesh.geometry));
    return this;
  }

  /**
   * Populate segments from a non-indexed `LineSegments` object.
   *
   * @param {import("../../three.module.js").LineSegments} lineSegments - Source line segments.
   * @returns {LineSegmentsGeometry} This geometry instance.
   */
  fromLineSegments(lineSegments) {
    this.setPositions(lineSegments.geometry.attributes.position.array);
    return this;
  }

  /**
   * Compute the axis-aligned bounding box enclosing all segment endpoints.
   */
  computeBoundingBox() {
    if (this.boundingBox === null) {
      this.boundingBox = new Box3();
    }

    const start = this.attributes.instanceStart;
    const end = this.attributes.instanceEnd;
    if (start !== undefined && end !== undefined) {
      this.boundingBox.setFromBufferAttribute(start);
      SCRATCH_BOX.setFromBufferAttribute(end);
      this.boundingBox.union(SCRATCH_BOX);
    }
  }

  /**
   * Compute the bounding sphere enclosing all segment endpoints.
   */
  computeBoundingSphere() {
    if (this.boundingSphere === null) {
      this.boundingSphere = new Sphere();
    }
    if (this.boundingBox === null) {
      this.computeBoundingBox();
    }

    const start = this.attributes.instanceStart;
    const end = this.attributes.instanceEnd;
    if (start !== undefined && end !== undefined) {
      const center = this.boundingSphere.center;
      this.boundingBox.getCenter(center);

      let maxRadiusSq = 0;
      for (let idx = 0; idx < start.count; idx += 1) {
        SCRATCH_VECTOR.fromBufferAttribute(start, idx);
        maxRadiusSq = Math.max(maxRadiusSq, center.distanceToSquared(SCRATCH_VECTOR));
        SCRATCH_VECTOR.fromBufferAttribute(end, idx);
        maxRadiusSq = Math.max(maxRadiusSq, center.distanceToSquared(SCRATCH_VECTOR));
      }

      this.boundingSphere.radius = Math.sqrt(maxRadiusSq);
      if (Number.isNaN(this.boundingSphere.radius)) {
        throw new RangeError(
          "LineSegmentsGeometry.computeBoundingSphere encountered NaN endpoint coordinates",
        );
      }
    }
  }

  /**
   * Serialize geometry metadata using `InstancedBufferGeometry.prototype.toJSON`.
   *
   * @returns {object} Serialized geometry payload.
   */
  toJSON() {
    return InstancedBufferGeometry.prototype.toJSON.call(this);
  }
}
