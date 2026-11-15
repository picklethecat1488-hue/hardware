/**
 * Undecimated 3D Voxel / Sphere Fluid Simulation Renderer & Kinematic Playback Engine.
 *
 * Architectural fixes over the legacy `PointsMaterial` simulation renderer:
 * 1. Decodes 100% of all ~30,000+ water voxels per frame (`positions_b64` little-endian `float32`)
 *    with zero `MAX_TELEMETRY_PARTICLES = 4000` spatial-hash decimation!
 * 2. Renders the entire fluid volume in **1 `THREE.InstancedMesh` draw call** using compact
 *    3-float `aInstancePos` + `aInstanceColor` attributes (`360 KB/frame`, 4x smaller than `Matrix4`).
 * 3. Uses exact world-space `BoxGeometry(voxel_dx_mm, voxel_dx_mm, voxel_dx_mm)` (`3.50 mm` cubes)
 *    in Voxel Mode and `IcosahedronGeometry(radius_mm, 1)` (`1.89 mm` spheres) in Sphere Mode —
 *    100% perspective-correct and orthographic-correct at every zoom and FOV!
 * 4. Applies per-step `/world/<link>` `Transform3D` poses (`impeller`, `drive_hub`) synchronously.
 */

import {
  BoxGeometry,
  DynamicDrawUsage,
  FrontSide,
  Group,
  IcosahedronGeometry,
  InstancedBufferAttribute,
  InstancedMesh,
  Matrix4,
  ShaderMaterial,
  Vector3,
} from "../static/vendor/three/three.module.js";
import FLUID_FRAGMENT_SHADER from "./shaders/fluid_particle.frag.glsl";
import FLUID_VERTEX_SHADER from "./shaders/fluid_particle.vert.glsl";

const BYTES_PER_FLOAT32 = 4;
const FLOATS_PER_VEC3 = 3;
const DEFAULT_VOXEL_DX_MM = 3.5;
const DEFAULT_SPHERE_RADIUS_MM = 1.89;
const BASE_PLAYBACK_FPS = 30;
const MIN_CAPACITY = 64;
const FLUID_POLYGON_OFFSET_FACTOR = 2.0;
const FLUID_POLYGON_OFFSET_UNITS = 2.0;

const IDENTITY_MAT4 = new Matrix4();

/**
 * Decode a single simulation frame's `positions_b64` (or fallback `positions` list) into `Float32Array`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} frame - Telemetry frame object.
 * @returns {Float32Array} Flat `[x0, y0, z0, ...]` positions in mm.
 */
export function decodeFramePositionsMm(ctx, frame) {
  if (!frame) {
    return new Float32Array(0);
  }
  if (typeof frame.positions_b64 === "string" && frame.positions_b64.length > 0) {
    const bytes = ctx.decodeBase64Bytes(frame.positions_b64);
    const floatCount = Math.floor(bytes.byteLength / BYTES_PER_FLOAT32);
    if (bytes.byteOffset % BYTES_PER_FLOAT32 === 0) {
      return new Float32Array(bytes.buffer, bytes.byteOffset, floatCount);
    }
    const copy = bytes.slice(0, floatCount * BYTES_PER_FLOAT32);
    return new Float32Array(copy.buffer, 0, floatCount);
  }
  if (Array.isArray(frame.positions)) {
    const out = new Float32Array(frame.positions.length * FLOATS_PER_VEC3);
    for (let idx = 0; idx < frame.positions.length; idx += 1) {
      const pt = frame.positions[idx];
      out[idx * 3] = Number(pt[0]) || 0;
      out[idx * 3 + 1] = Number(pt[1]) || 0;
      out[idx * 3 + 2] = Number(pt[2]) || 0;
    }
    return out;
  }
  return new Float32Array(0);
}

/**
 * Decode optional per-element `colors_b64` (`Uint8` RGB) or fallback `colors` into normalized `Float32Array`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} frame - Telemetry frame object.
 * @param {number} elementCount - Number of fluid elements in this frame.
 * @param {[number, number, number]} defaultRgb - Default normalized RGB color `[r, g, b]`.
 * @returns {Float32Array}
 */
export function decodeFrameColorsRgb(ctx, frame, elementCount, defaultRgb) {
  const out = new Float32Array(elementCount * FLOATS_PER_VEC3);
  if (elementCount === 0) {
    return out;
  }

  if (typeof frame?.colors_b64 === "string" && frame.colors_b64.length > 0) {
    const bytes = ctx.decodeBase64Bytes(frame.colors_b64);
    const limit = Math.min(elementCount * 3, bytes.byteLength);
    const inv255 = 1 / 255;
    for (let idx = 0; idx < limit; idx += 1) {
      out[idx] = bytes[idx] * inv255;
    }
    return out;
  }

  if (Array.isArray(frame?.colors) && frame.colors.length > 0) {
    const count = Math.min(elementCount, frame.colors.length);
    for (let idx = 0; idx < count; idx += 1) {
      const c = frame.colors[idx];
      out[idx * 3] = Number(c[0]) || defaultRgb[0];
      out[idx * 3 + 1] = Number(c[1]) || defaultRgb[1];
      out[idx * 3 + 2] = Number(c[2]) || defaultRgb[2];
    }
    return out;
  }

  for (let idx = 0; idx < elementCount; idx += 1) {
    out[idx * 3] = defaultRgb[0];
    out[idx * 3 + 1] = defaultRgb[1];
    out[idx * 3 + 2] = defaultRgb[2];
  }
  return out;
}

/**
 * Single-draw-call GPU Instanced Voxel & Sphere Fluid Renderer with timeline playback controller.
 */
export class SimulationVoxelRenderer {
  /**
   * Construct a `SimulationVoxelRenderer`.
   *
   * @param {object} options - Renderer options.
   * @param {object} options.ctx - Explicit `RuntimeContext`.
   * @param {import("../static/vendor/three/three.module.js").Scene} options.scene - Target Three.js scene.
   * @param {import("./cad_scene.js").CadSceneManager|null} [options.cadScene] - Optional CAD scene for kinematic transforms.
   * @param {function(object): void} [options.onFrameChange] - Callback invoked when active frame changes.
   */
  constructor({ ctx, scene, cadScene = null, onFrameChange = null }) {
    /** @type {object} */
    this.ctx = ctx;
    /** @type {import("../static/vendor/three/three.module.js").Scene} */
    this.scene = scene;
    /** @type {import("./cad_scene.js").CadSceneManager|null} */
    this.cadScene = cadScene;
    /** @type {function(object): void|null} */
    this.onFrameChange = onFrameChange;

    /** @type {Group} */
    this.rootGroup = new Group();
    this.rootGroup.name = "scope_sim_fluid_root";
    this.scene.add(this.rootGroup);

    /** @type {"voxels"|"spheres"} */
    this.renderStyle = "voxels";
    /** @type {number} */
    this.voxelDxMm = DEFAULT_VOXEL_DX_MM;
    /** @type {number} */
    this.sphereRadiusMm = DEFAULT_SPHERE_RADIUS_MM;
    /** @type {boolean} */
    this.isVoxelGrid = true;
    /** @type {[number, number, number]} */
    this.defaultRgb = [0.22, 0.68, 0.98];

    /** @type {object|null} */
    this.telemetry = null;
    /** @type {Array<object>} */
    this.frames = [];
    /** @type {Array<Float32Array|null>} */
    this._decodedPositionsCache = [];
    /** @type {Array<Float32Array|null>} */
    this._decodedColorsCache = [];

    /** @type {number} */
    this.currentFrameIndex = 0;
    /** @type {boolean} */
    this.isPlaying = false;
    /** @type {number} */
    this.timeScale = 1.0;

    this._maxCapacity = 0;
    this._instancedMesh = null;
    this._posAttr = null;
    this._colAttr = null;
    this._material = null;
    this._geometry = null;

    this._playRafHandle = null;
    this._lastTickMs = 0;
    this._accumFrameFloat = 0;
    this._boundPlayTick = this._onPlaybackTick.bind(this);
  }

  /**
   * Stop playback and dispose GPU buffers.
   */
  clear() {
    this.pause();
    this._disposeMesh();
    this.telemetry = null;
    this.frames = [];
    this._decodedPositionsCache = [];
    this._decodedColorsCache = [];
    this.currentFrameIndex = 0;
    this._maxCapacity = 0;
  }

  /**
   * Dispose current `InstancedMesh`, geometry, and shader material.
   */
  _disposeMesh() {
    if (this._instancedMesh) {
      this.rootGroup.remove(this._instancedMesh);
      this._instancedMesh = null;
    }
    if (this._geometry) {
      this._geometry.dispose();
      this._geometry = null;
    }
    if (this._material) {
      this._material.dispose();
      this._material = null;
    }
    this._posAttr = null;
    this._colAttr = null;
  }

  /**
   * Load simulation telemetry payload from `/api/scope/simulation_telemetry`, allocate a single
   * pre-sized `InstancedMesh` across the peak frame count, and render frame `0`.
   *
   * @param {object} telemetryPayload - Backend simulation telemetry response.
   */
  loadTelemetry(telemetryPayload) {
    this.clear();
    if (!telemetryPayload || telemetryPayload.status !== "ok" || !Array.isArray(telemetryPayload.frames)) {
      return;
    }

    this.telemetry = telemetryPayload;
    this.frames = telemetryPayload.frames;
    this._decodedPositionsCache = Array.from({ length: this.frames.length }, () => null);
    this._decodedColorsCache = Array.from({ length: this.frames.length }, () => null);

    this.isVoxelGrid = telemetryPayload.is_voxel_grid !== false;
    this.voxelDxMm = Math.max(0.1, Number(telemetryPayload.voxel_dx_mm) || DEFAULT_VOXEL_DX_MM);
    this.sphereRadiusMm = Math.max(0.05, Number(telemetryPayload.radius_mm) || DEFAULT_SPHERE_RADIUS_MM);
    this.renderStyle = this.isVoxelGrid ? "voxels" : "spheres";

    if (Array.isArray(telemetryPayload.default_color) && telemetryPayload.default_color.length >= 3) {
      this.defaultRgb = [
        Number(telemetryPayload.default_color[0]) || 0.22,
        Number(telemetryPayload.default_color[1]) || 0.68,
        Number(telemetryPayload.default_color[2]) || 0.98,
      ];
    }

    let maxElements = 0;
    for (const f of this.frames) {
      const c = typeof f.count === "number"
        ? f.count
        : Array.isArray(f.positions)
          ? f.positions.length
          : 0;
      if (c > maxElements) {
        maxElements = c;
      }
    }
    this._maxCapacity = Math.max(MIN_CAPACITY, maxElements);
    this._rebuildInstancedMesh();
    this.setFrameIndex(0);
  }

  /**
   * Build or rebuild the single `THREE.InstancedMesh` for the active `renderStyle` (`"voxels"` or `"spheres"`).
   */
  _rebuildInstancedMesh() {
    this._disposeMesh();
    if (this._maxCapacity <= 0) {
      return;
    }

    if (this.renderStyle === "voxels") {
      // Exact world-space `voxel_dx_mm` cube (e.g. 3.50 x 3.50 x 3.50 mm) — zero gaps, zero FOV/zoom distortion!
      const s = this.voxelDxMm;
      this._geometry = new BoxGeometry(s, s, s);
    } else {
      this._geometry = new IcosahedronGeometry(this.sphereRadiusMm, 1);
    }

    const posBuffer = new Float32Array(this._maxCapacity * FLOATS_PER_VEC3);
    const colBuffer = new Float32Array(this._maxCapacity * FLOATS_PER_VEC3);

    this._posAttr = new InstancedBufferAttribute(posBuffer, 3);
    this._posAttr.setUsage(DynamicDrawUsage);
    this._colAttr = new InstancedBufferAttribute(colBuffer, 3);
    this._colAttr.setUsage(DynamicDrawUsage);

    this._geometry.setAttribute("aInstancePos", this._posAttr);
    this._geometry.setAttribute("aInstanceColor", this._colAttr);

    const lightA = new Vector3(0.55, -0.48, 0.68).normalize();
    const lightB = new Vector3(-0.62, 0.52, 0.35).normalize();

    this._material = new ShaderMaterial({
      vertexShader: FLUID_VERTEX_SHADER,
      fragmentShader: FLUID_FRAGMENT_SHADER,
      transparent: false,
      depthWrite: true,
      depthTest: true,
      polygonOffset: true,
      polygonOffsetFactor: FLUID_POLYGON_OFFSET_FACTOR,
      polygonOffsetUnits: FLUID_POLYGON_OFFSET_UNITS,
      side: FrontSide,
      uniforms: {
        uOpacity: { value: 1.0 },
        uLightDirA: { value: lightA },
        uLightDirB: { value: lightB },
      },
    });

    this._instancedMesh = new InstancedMesh(this._geometry, this._material, this._maxCapacity);
    this._instancedMesh.name = `scope_fluid_${this.renderStyle}`;
    this._instancedMesh.frustumCulled = false;
    this._instancedMesh.count = 0;

    for (let idx = 0; idx < this._maxCapacity; idx += 1) {
      this._instancedMesh.setMatrixAt(idx, IDENTITY_MAT4);
    }
    this._instancedMesh.instanceMatrix.needsUpdate = true;

    this.rootGroup.add(this._instancedMesh);
  }

  /**
   * Switch between `"voxels"` (`BoxGeometry(voxel_dx_mm)`) and `"spheres"` (`IcosahedronGeometry(radius_mm)`).
   *
   * @param {"voxels"|"spheres"} style - Desired fluid element primitive.
   */
  setRenderStyle(style) {
    const next = style === "spheres" ? "spheres" : "voxels";
    if (next === this.renderStyle && this._instancedMesh) {
      return;
    }
    this.renderStyle = next;
    if (this._maxCapacity > 0) {
      this._rebuildInstancedMesh();
      this.setFrameIndex(this.currentFrameIndex);
    }
  }

  /**
   * Upload frame `frameIndex`'s fluid positions, colors, and kinematic `Transform3D` link poses!
   *
   * @param {number} frameIndex - Target frame index (`0 .. frames.length - 1`).
   * @returns {object|null} Active frame metadata.
   */
  setFrameIndex(frameIndex) {
    if (this.frames.length === 0 || !this._instancedMesh) {
      return null;
    }
    const idx = Math.max(0, Math.min(this.frames.length - 1, Math.floor(Number(frameIndex) || 0)));
    this.currentFrameIndex = idx;
    const frame = this.frames[idx];

    let positions = this._decodedPositionsCache[idx];
    if (!positions) {
      positions = decodeFramePositionsMm(this.ctx, frame);
      this._decodedPositionsCache[idx] = positions;
    }
    const elementCount = Math.min(this._maxCapacity, Math.floor(positions.length / FLOATS_PER_VEC3));

    let colors = this._decodedColorsCache[idx];
    if (!colors) {
      colors = decodeFrameColorsRgb(this.ctx, frame, elementCount, this.defaultRgb);
      this._decodedColorsCache[idx] = colors;
    }

    if (elementCount > 0) {
      this._posAttr.array.set(positions.subarray(0, elementCount * FLOATS_PER_VEC3), 0);
      this._colAttr.array.set(colors.subarray(0, elementCount * FLOATS_PER_VEC3), 0);
      this._posAttr.needsUpdate = true;
      this._colAttr.needsUpdate = true;
    }
    this._instancedMesh.count = elementCount;

    if (this.cadScene && frame.transforms) {
      this.cadScene.applyKinematicTransforms(frame.transforms);
    }

    const summary = {
      frameIndex: idx,
      totalFrames: this.frames.length,
      step: frame.step ?? idx,
      elementCount,
      metrics: frame.metrics || {},
      transforms: frame.transforms || {},
      renderStyle: this.renderStyle,
      voxelDxMm: this.voxelDxMm,
      sphereRadiusMm: this.sphereRadiusMm,
    };
    if (this.onFrameChange) {
      this.onFrameChange(summary);
    }
    return summary;
  }

  /**
   * Step relative to `currentFrameIndex` by `deltaFrames` (wrapping cleanly).
   *
   * @param {number} deltaFrames - Signed frame offset (`-10`, `+10`, etc.).
   */
  stepBy(deltaFrames) {
    if (this.frames.length === 0) {
      return;
    }
    const next = (this.currentFrameIndex + deltaFrames + this.frames.length) % this.frames.length;
    this.setFrameIndex(next);
  }

  /**
   * Start timeline playback via `ctx.requestAnimationFrame`.
   */
  play() {
    if (this.isPlaying || this.frames.length <= 1) {
      return;
    }
    this.isPlaying = true;
    this._lastTickMs = this.ctx.nowMs();
    this._accumFrameFloat = 0;
    this._playRafHandle = this.ctx.requestAnimationFrame(this._boundPlayTick);
  }

  /**
   * Pause timeline playback.
   */
  pause() {
    this.isPlaying = false;
    if (this._playRafHandle !== null) {
      this.ctx.cancelAnimationFrame(this._playRafHandle);
      this._playRafHandle = null;
    }
  }

  /**
   * Toggle play/pause (`Space` shortcut).
   *
   * @returns {boolean} New `isPlaying` state.
   */
  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
    return this.isPlaying;
  }

  /**
   * Set playback speed multiplier (`0.25`, `0.5`, `1.0`, `2.0`, `5.0`).
   *
   * @param {number} scale - Speed multiplier.
   */
  setTimeScale(scale) {
    const parsed = Number(scale);
    if (Number.isFinite(parsed) && parsed > 0) {
      this.timeScale = parsed;
    }
  }

  /**
   * Advance simulation frame index proportionally to elapsed wall time and `timeScale`.
   */
  _onPlaybackTick() {
    this._playRafHandle = null;
    if (!this.isPlaying || this.frames.length <= 1) {
      return;
    }
    const now = this.ctx.nowMs();
    const dtSec = Math.min(0.25, Math.max(0, (now - this._lastTickMs) * 0.001));
    this._lastTickMs = now;

    this._accumFrameFloat += dtSec * BASE_PLAYBACK_FPS * this.timeScale;
    if (this._accumFrameFloat >= 1.0) {
      const advance = Math.floor(this._accumFrameFloat);
      this._accumFrameFloat -= advance;
      const nextIdx = (this.currentFrameIndex + advance) % this.frames.length;
      this.setFrameIndex(nextIdx);
    }

    this._playRafHandle = this.ctx.requestAnimationFrame(this._boundPlayTick);
  }
}
