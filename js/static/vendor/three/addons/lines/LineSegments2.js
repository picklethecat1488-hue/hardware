/**
 * Instanced wide-line mesh synchronized to the WebGL physical drawing-buffer resolution.
 *
 * Adapted from Three.js r184 addons (MIT License). Updates `LineMaterial.resolution`
 * from `renderer.getDrawingBufferSize()` rather than logical CSS viewport dimensions
 * so integer `linewidth` values snap cleanly to physical Retina pixels.
 */

import {
  Box3,
  InstancedInterleavedBuffer,
  InterleavedBufferAttribute,
  Line3,
  MathUtils,
  Matrix4,
  Mesh,
  Sphere,
  Vector2,
  Vector3,
  Vector4,
} from "../../three.module.js";
import { LineMaterial } from "./LineMaterial.js";
import { LineSegmentsGeometry } from "./LineSegmentsGeometry.js";

const DEFAULT_LINE_COLOR_HEX = 0xffffff;
const DISTANCE_PAIR_STRIDE = 2;
const HALF_SCALE = 0.5;

const SCRATCH_DRAWING_BUFFER_SIZE = new Vector2();
const SCRATCH_START = new Vector3();
const SCRATCH_END = new Vector3();
const SCRATCH_START4 = new Vector4();
const SCRATCH_END4 = new Vector4();
const SCRATCH_SS_ORIGIN = new Vector4();
const SCRATCH_SS_ORIGIN3 = new Vector3();
const SCRATCH_MV_MATRIX = new Matrix4();
const SCRATCH_LINE = new Line3();
const SCRATCH_CLOSEST_POINT = new Vector3();
const SCRATCH_BOX = new Box3();
const SCRATCH_SPHERE = new Sphere();
const SCRATCH_CLIP_TO_WORLD = new Vector4();

/**
 * Compute world-space bounding margin corresponding to a physical-pixel line width.
 *
 * @param {import("../../three.module.js").Camera} camera - Active scene camera.
 * @param {number} distance - Camera-space distance to geometry bounds.
 * @param {number} lineWidth - Effective line width in physical pixels.
 * @param {Vector2} resolution - Physical drawing-buffer size.
 * @returns {number} Required world-space expansion radius.
 */
function getWorldSpaceHalfWidth(camera, distance, lineWidth, resolution) {
  SCRATCH_CLIP_TO_WORLD.set(0, 0, -distance, 1.0).applyMatrix4(camera.projectionMatrix);
  SCRATCH_CLIP_TO_WORLD.multiplyScalar(1.0 / SCRATCH_CLIP_TO_WORLD.w);
  SCRATCH_CLIP_TO_WORLD.x = lineWidth / Math.max(1, resolution.width);
  SCRATCH_CLIP_TO_WORLD.y = lineWidth / Math.max(1, resolution.height);
  SCRATCH_CLIP_TO_WORLD.applyMatrix4(camera.projectionMatrixInverse);
  SCRATCH_CLIP_TO_WORLD.multiplyScalar(1.0 / SCRATCH_CLIP_TO_WORLD.w);
  return Math.abs(Math.max(SCRATCH_CLIP_TO_WORLD.x, SCRATCH_CLIP_TO_WORLD.y));
}

/**
 * Raycast against segments whose width is defined in world-space units.
 *
 * @param {LineSegments2} lineSegments - Target line segments object.
 * @param {import("../../three.module.js").Ray} ray - World-space ray.
 * @param {number} lineWidth - Effective world-space width.
 * @param {Array<object>} intersects - Output intersection hits.
 */
function raycastWorldUnits(lineSegments, ray, lineWidth, intersects) {
  const matrixWorld = lineSegments.matrixWorld;
  const geometry = lineSegments.geometry;
  const instanceStart = geometry.attributes.instanceStart;
  const instanceEnd = geometry.attributes.instanceEnd;
  const segmentCount = Math.min(geometry.instanceCount, instanceStart.count);

  for (let idx = 0; idx < segmentCount; idx += 1) {
    SCRATCH_LINE.start.fromBufferAttribute(instanceStart, idx);
    SCRATCH_LINE.end.fromBufferAttribute(instanceEnd, idx);
    SCRATCH_LINE.applyMatrix4(matrixWorld);

    const pointOnLine = new Vector3();
    const point = new Vector3();
    ray.distanceSqToSegment(SCRATCH_LINE.start, SCRATCH_LINE.end, point, pointOnLine);
    if (point.distanceTo(pointOnLine) < lineWidth * HALF_SCALE) {
      intersects.push({
        point,
        pointOnLine,
        distance: ray.origin.distanceTo(point),
        object: lineSegments,
        face: null,
        faceIndex: idx,
        uv: null,
        uv1: null,
      });
    }
  }
}

/**
 * Raycast against segments whose width is defined in physical drawing-buffer pixels.
 *
 * @param {LineSegments2} lineSegments - Target line segments object.
 * @param {import("../../three.module.js").Camera} camera - Active camera.
 * @param {import("../../three.module.js").Ray} ray - World-space ray.
 * @param {number} lineWidth - Effective physical-pixel width.
 * @param {Array<object>} intersects - Output intersection hits.
 */
function raycastScreenSpace(lineSegments, camera, ray, lineWidth, intersects) {
  const projectionMatrix = camera.projectionMatrix;
  const resolution = lineSegments.material.resolution;
  const matrixWorld = lineSegments.matrixWorld;
  const geometry = lineSegments.geometry;
  const instanceStart = geometry.attributes.instanceStart;
  const instanceEnd = geometry.attributes.instanceEnd;
  const segmentCount = Math.min(geometry.instanceCount, instanceStart.count);
  const near = -camera.near;

  ray.at(1, SCRATCH_SS_ORIGIN);
  SCRATCH_SS_ORIGIN.w = 1;
  SCRATCH_SS_ORIGIN.applyMatrix4(camera.matrixWorldInverse);
  SCRATCH_SS_ORIGIN.applyMatrix4(projectionMatrix);
  SCRATCH_SS_ORIGIN.multiplyScalar(1 / SCRATCH_SS_ORIGIN.w);

  SCRATCH_SS_ORIGIN.x *= resolution.x * HALF_SCALE;
  SCRATCH_SS_ORIGIN.y *= resolution.y * HALF_SCALE;
  SCRATCH_SS_ORIGIN.z = 0;
  SCRATCH_SS_ORIGIN3.copy(SCRATCH_SS_ORIGIN);

  SCRATCH_MV_MATRIX.multiplyMatrices(camera.matrixWorldInverse, matrixWorld);

  for (let idx = 0; idx < segmentCount; idx += 1) {
    SCRATCH_START4.fromBufferAttribute(instanceStart, idx);
    SCRATCH_END4.fromBufferAttribute(instanceEnd, idx);
    SCRATCH_START4.w = 1;
    SCRATCH_END4.w = 1;

    SCRATCH_START4.applyMatrix4(SCRATCH_MV_MATRIX);
    SCRATCH_END4.applyMatrix4(SCRATCH_MV_MATRIX);

    if (SCRATCH_START4.z > near && SCRATCH_END4.z > near) {
      continue;
    }

    if (SCRATCH_START4.z > near) {
      const deltaDist = SCRATCH_START4.z - SCRATCH_END4.z;
      SCRATCH_START4.lerp(SCRATCH_END4, (SCRATCH_START4.z - near) / deltaDist);
    } else if (SCRATCH_END4.z > near) {
      const deltaDist = SCRATCH_END4.z - SCRATCH_START4.z;
      SCRATCH_END4.lerp(SCRATCH_START4, (SCRATCH_END4.z - near) / deltaDist);
    }

    SCRATCH_START4.applyMatrix4(projectionMatrix);
    SCRATCH_END4.applyMatrix4(projectionMatrix);
    SCRATCH_START4.multiplyScalar(1 / SCRATCH_START4.w);
    SCRATCH_END4.multiplyScalar(1 / SCRATCH_END4.w);

    SCRATCH_START4.x *= resolution.x * HALF_SCALE;
    SCRATCH_START4.y *= resolution.y * HALF_SCALE;
    SCRATCH_END4.x *= resolution.x * HALF_SCALE;
    SCRATCH_END4.y *= resolution.y * HALF_SCALE;

    SCRATCH_LINE.start.set(SCRATCH_START4.x, SCRATCH_START4.y, 0);
    SCRATCH_LINE.end.set(SCRATCH_END4.x, SCRATCH_END4.y, 0);

    const param = SCRATCH_LINE.closestPointToPointParameter(SCRATCH_SS_ORIGIN3, true);
    SCRATCH_LINE.at(param, SCRATCH_CLOSEST_POINT);

    const zPos = MathUtils.lerp(SCRATCH_START4.z, SCRATCH_END4.z, param);
    const isInClipSpace = zPos >= -1 && zPos <= 1;
    const isInside = SCRATCH_SS_ORIGIN3.distanceTo(SCRATCH_CLOSEST_POINT) < lineWidth * HALF_SCALE;

    if (isInClipSpace && isInside) {
      SCRATCH_LINE.start.fromBufferAttribute(instanceStart, idx).applyMatrix4(matrixWorld);
      SCRATCH_LINE.end.fromBufferAttribute(instanceEnd, idx).applyMatrix4(matrixWorld);

      const pointOnLine = new Vector3();
      const point = new Vector3();
      ray.distanceSqToSegment(SCRATCH_LINE.start, SCRATCH_LINE.end, point, pointOnLine);

      intersects.push({
        point,
        pointOnLine,
        distance: ray.origin.distanceTo(point),
        object: lineSegments,
        face: null,
        faceIndex: idx,
        uv: null,
        uv1: null,
      });
    }
  }
}

/**
 * Instanced wide-line mesh pairing `LineSegmentsGeometry` with `LineMaterial`.
 */
export class LineSegments2 extends Mesh {
  /**
   * Construct a `LineSegments2` object.
   *
   * @param {LineSegmentsGeometry} [geometry] - Segment endpoint geometry.
   * @param {LineMaterial} [material] - Wide-line shader material.
   */
  constructor(
    geometry = new LineSegmentsGeometry(),
    material = new LineMaterial({ color: DEFAULT_LINE_COLOR_HEX }),
  ) {
    super(geometry, material);

    /**
     * Runtime type-guard flag.
     * @type {boolean}
     */
    this.isLineSegments2 = true;
    this.type = "LineSegments2";
  }

  /**
   * Compute cumulative segment start/end distances required for dashed lines.
   *
   * @returns {LineSegments2} This object.
   */
  computeLineDistances() {
    const geometry = this.geometry;
    const instanceStart = geometry.attributes.instanceStart;
    const instanceEnd = geometry.attributes.instanceEnd;
    const lineDistances = new Float32Array(DISTANCE_PAIR_STRIDE * instanceStart.count);

    for (let idx = 0, outIdx = 0; idx < instanceStart.count; idx += 1, outIdx += DISTANCE_PAIR_STRIDE) {
      SCRATCH_START.fromBufferAttribute(instanceStart, idx);
      SCRATCH_END.fromBufferAttribute(instanceEnd, idx);
      lineDistances[outIdx] = outIdx === 0 ? 0 : lineDistances[outIdx - 1];
      lineDistances[outIdx + 1] = lineDistances[outIdx] + SCRATCH_START.distanceTo(SCRATCH_END);
    }

    const instanceDistanceBuffer = new InstancedInterleavedBuffer(
      lineDistances,
      DISTANCE_PAIR_STRIDE,
      1,
    );
    geometry.setAttribute(
      "instanceDistanceStart",
      new InterleavedBufferAttribute(instanceDistanceBuffer, 1, 0),
    );
    geometry.setAttribute(
      "instanceDistanceEnd",
      new InterleavedBufferAttribute(instanceDistanceBuffer, 1, 1),
    );
    return this;
  }

  /**
   * Test intersection between a `Raycaster` and instanced line segments.
   *
   * @param {import("../../three.module.js").Raycaster} raycaster - Scene raycaster.
   * @param {Array<object>} intersects - Output hit array.
   */
  raycast(raycaster, intersects) {
    const worldUnits = this.material.worldUnits;
    const camera = raycaster.camera;
    if (camera === null && !worldUnits) {
      throw new Error(
        "LineSegments2.raycast requires raycaster.camera when material.worldUnits is false",
      );
    }

    const threshold = raycaster.params.Line2 !== undefined ? raycaster.params.Line2.threshold || 0 : 0;
    const ray = raycaster.ray;
    const geometry = this.geometry;
    const material = this.material;
    const lineWidth = material.linewidth + threshold;

    if (!geometry.attributes.instanceStart) {
      return;
    }

    if (geometry.boundingSphere === null) {
      geometry.computeBoundingSphere();
    }
    SCRATCH_SPHERE.copy(geometry.boundingSphere).applyMatrix4(this.matrixWorld);

    const sphereMargin = worldUnits
      ? lineWidth * HALF_SCALE
      : getWorldSpaceHalfWidth(
          camera,
          Math.max(camera.near, SCRATCH_SPHERE.distanceToPoint(ray.origin)),
          lineWidth,
          material.resolution,
        );
    SCRATCH_SPHERE.radius += sphereMargin;
    if (!ray.intersectsSphere(SCRATCH_SPHERE)) {
      return;
    }

    if (geometry.boundingBox === null) {
      geometry.computeBoundingBox();
    }
    SCRATCH_BOX.copy(geometry.boundingBox).applyMatrix4(this.matrixWorld);

    const boxMargin = worldUnits
      ? lineWidth * HALF_SCALE
      : getWorldSpaceHalfWidth(
          camera,
          Math.max(camera.near, SCRATCH_BOX.distanceToPoint(ray.origin)),
          lineWidth,
          material.resolution,
        );
    SCRATCH_BOX.expandByScalar(boxMargin);
    if (!ray.intersectsBox(SCRATCH_BOX)) {
      return;
    }

    if (worldUnits) {
      raycastWorldUnits(this, ray, lineWidth, intersects);
    } else {
      raycastScreenSpace(this, camera, ray, lineWidth, intersects);
    }
  }

  /**
   * Synchronize `LineMaterial.resolution` with the renderer's physical drawing-buffer pixel size.
   *
   * @param {import("../../three.module.js").WebGLRenderer} renderer - Active WebGL renderer.
   */
  onBeforeRender(renderer) {
    const uniforms = this.material && this.material.uniforms;
    if (uniforms && uniforms.resolution) {
      renderer.getDrawingBufferSize(SCRATCH_DRAWING_BUFFER_SIZE);
      uniforms.resolution.value.set(
        SCRATCH_DRAWING_BUFFER_SIZE.x,
        SCRATCH_DRAWING_BUFFER_SIZE.y,
      );
    }
  }
}
