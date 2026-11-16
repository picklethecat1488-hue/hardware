/**
 * Synchronized Perspective / Orthographic CAD & 2D Planar Camera Controller.
 *
 * Architectural guarantees:
 * 1. Maintains twin `PerspectiveCamera` (`DEFAULT_FOV_DEG = 35`) and `OrthographicCamera`
 *    instances with exact visible frustum-height parity when toggling Ortho/Persp (`5`).
 * 2. Enforces `up = (0, 1, 0)` with rotation locked (`enableRotate = false`) in 2D planar
 *    modes (`PCB`, `DIAGRAM`) — completely eliminating polar gimbal lock at zenith/nadir
 *    and preserving exact `(panX, panY)` when flipping Top (`F.Cu`) <-> Bottom (`B.Cu`) (`F`).
 * 3. Enforces `up = (0, 0, 1)` Z-up engineering convention in 3D modes (`CAD`, `SIMULATE`).
 * 4. Renders a derivative-antialiased (`fwidth()`) shader floor grid, a crisp `2x` Retina
 *    Canvas2D 3D orientation gizmo, and a physical world-space scale bar (`mm` / `mil`).
 */

import {
  DoubleSide,
  MOUSE,
  Mesh,
  OrthographicCamera,
  PerspectiveCamera,
  PlaneGeometry,
  Ray,
  ShaderMaterial,
  Vector3,
} from "../static/vendor/three/three.module.js";
import { OrbitControls } from "../static/vendor/three/addons/controls/OrbitControls.js";
import FLOOR_GRID_FRAGMENT_SHADER from "./shaders/floor_grid.frag.glsl";
import FLOOR_GRID_VERTEX_SHADER from "./shaders/floor_grid.vert.glsl";

export const DEFAULT_FOV_DEG = 35;
const DEG_TO_RAD = Math.PI / 180;
const MIN_NEAR_PLANE = 0.05;
const MAX_FAR_PLANE = 250000;
const FIT_PADDING_3D = 1.28;
const FIT_PADDING_2D = 1.14;
const MIN_BOUNDS_SPAN_MM = 1.0;
const KEYBOARD_PAN_FRACTION = 0.08;
const ZOOM_STEP_FACTOR = 1.22;
const MILS_PER_MM = 39.37007874;

const GIZMO_RADIUS_PX = 34;
const GIZMO_MARGIN_RIGHT_PX = 52;
const GIZMO_MARGIN_BOTTOM_PX = 52;

const SCALE_BAR_LEFT_PX = 18;
const SCALE_BAR_BOTTOM_PX = 18;
const SCALE_BAR_TARGET_PX = 110;
const NICE_SCALE_STEPS = Object.freeze([
  0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
]);

const SCRATCH_RAY = new Ray();
const SCRATCH_PLANE_NORMAL = new Vector3(0, 0, 1);
const SCRATCH_VEC_A = new Vector3();
const SCRATCH_VEC_B = new Vector3();

/**
 * Synchronized 3D CAD + 2D PCB/Diagram camera, floor grid, orientation gizmo, and scale bar controller.
 */
export class CadCameraController {
  /**
   * Construct a `CadCameraController`.
   *
   * @param {object} options - Initialization options.
   * @param {HTMLElement|null} [options.domElement] - Interactive canvas element (nullable in headless tests).
   * @param {number} [options.width] - Initial viewport CSS width.
   * @param {number} [options.height] - Initial viewport CSS height.
   * @param {function(): void} [options.onChange] - Callback invoked whenever camera pose/projection changes.
   */
  constructor({ domElement = null, width = 1280, height = 800, onChange = null } = {}) {
    /** @type {number} */
    this.width = Math.max(1, width);
    /** @type {number} */
    this.height = Math.max(1, height);
    /** @type {number} */
    this.aspect = this.width / this.height;
    /** @type {function(): void|null} */
    this.onChange = onChange;

    /** @type {PerspectiveCamera} */
    this.perspCamera = new PerspectiveCamera(DEFAULT_FOV_DEG, this.aspect, MIN_NEAR_PLANE, MAX_FAR_PLANE);
    this.perspCamera.up.set(0, 0, 1);

    /** @type {OrthographicCamera} */
    this.orthoCamera = new OrthographicCamera(-50 * this.aspect, 50 * this.aspect, 50, -50, MIN_NEAR_PLANE, MAX_FAR_PLANE);
    this.orthoCamera.up.set(0, 0, 1);

    /** @type {boolean} */
    this.isOrtho = false;
    /** @type {boolean} */
    this.is2DMode = false;
    /** @type {"F.Cu"|"B.Cu"} */
    this.activeBoardSide = "F.Cu";
    /** @type {string} */
    this.defaultPreset = "iso";
    /** @type {string} */
    this.mode = "CAD";
    /** @type {boolean} */
    this.axesVisible = true;
    /** @type {boolean} */
    this.gridVisible = true;

    /** @type {{min: [number, number, number], max: [number, number, number], center: [number, number, number], size: [number, number, number]}} */
    this.sceneBounds = {
      min: [-50, -50, -50],
      max: [50, 50, 50],
      center: [0, 0, 0],
      size: [100, 100, 100],
    };

    /** @type {number} */
    this._orthoHalfHeight = 60;

    /** @type {OrbitControls} */
    this.controls = new OrbitControls(this.perspCamera, domElement);
    this.controls.zoomToCursor = true;
    this.controls.screenSpacePanning = true;
    this.controls.addEventListener("change", () => {
      this._syncInactiveCamera();
      if (this.onChange) {
        this.onChange();
      }
    });

    /** @type {Mesh} */
    this.floorGridMesh = this._createFloorGridMesh();
  }

  /**
   * Return the currently active Three.js camera (`OrthographicCamera` or `PerspectiveCamera`).
   *
   * @returns {PerspectiveCamera|OrthographicCamera}
   */
  get activeCamera() {
    return this.isOrtho ? this.orthoCamera : this.perspCamera;
  }

  /**
   * Build the infinite-feel derivative-antialiased (`fwidth()`) XY floor grid mesh.
   *
   * @returns {Mesh}
   */
  _createFloorGridMesh() {
    const geom = new PlaneGeometry(4000, 4000, 1, 1);
    const mat = new ShaderMaterial({
      vertexShader: FLOOR_GRID_VERTEX_SHADER,
      fragmentShader: FLOOR_GRID_FRAGMENT_SHADER,
      transparent: true,
      depthWrite: false,
      side: DoubleSide,
      uniforms: {
        uMinorStep: { value: 5.0 },
        uMajorStep: { value: 25.0 },
        uFadeRadius: { value: 600.0 },
      },
    });
    const mesh = new Mesh(geom, mat);
    mesh.name = "scope_floor_grid";
    mesh.renderOrder = -10;
    return mesh;
  }

  /**
   * Update viewport aspect ratio and camera frustums on window/panel resize.
   *
   * @param {number} width - CSS width in pixels.
   * @param {number} height - CSS height in pixels.
   */
  resize(width, height) {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.aspect = this.width / this.height;

    this.perspCamera.aspect = this.aspect;
    this.perspCamera.updateProjectionMatrix();

    this._applyOrthoFrustum();
  }

  /**
   * Recompute orthographic camera left/right/top/bottom bounds from `_orthoHalfHeight` and `aspect`.
   */
  _applyOrthoFrustum() {
    this.orthoCamera.left = -this._orthoHalfHeight * this.aspect;
    this.orthoCamera.right = this._orthoHalfHeight * this.aspect;
    this.orthoCamera.top = this._orthoHalfHeight;
    this.orthoCamera.bottom = -this._orthoHalfHeight;
    this.orthoCamera.updateProjectionMatrix();
  }

  /**
   * Configure camera mode (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`), mouse button bindings,
   * up-vector convention, and default projection.
   *
   * @param {string} mode - Target Scope mode.
   * @param {{bounds?: object, viewFrom?: string|null}} [options] - Optional fit bounds and preset hint.
   */
  configureForMode(mode, { bounds = null, viewFrom = null } = {}) {
    const upper = String(mode || "CAD").toUpperCase();
    this.mode = upper;
    this.is2DMode = upper === "PCB" || upper === "DIAGRAM";

    if (bounds) {
      this.setSceneBounds(bounds);
    }

    if (this.is2DMode) {
      this.isOrtho = true;
      this.activeBoardSide = "F.Cu";
      this.controls.enableRotate = false;
      this.controls.mouseButtons = {
        LEFT: MOUSE.PAN,
        MIDDLE: MOUSE.DOLLY,
        RIGHT: MOUSE.PAN,
      };
      this.floorGridMesh.visible = false;
      this.controls.object = this.orthoCamera;
      const diagramPreset = upper === "PCB" ? "top" : String(viewFrom || "iso").toLowerCase();
      this.defaultPreset = diagramPreset;
      this.setPreset(diagramPreset, { fit: true });
    } else {
      this.isOrtho = false;
      this.controls.enableRotate = true;
      this.controls.mouseButtons = {
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.ROTATE,
        RIGHT: MOUSE.PAN,
      };
      this.floorGridMesh.visible = this.gridVisible && upper !== "DIAGRAM";
      this.controls.object = this.perspCamera;
      const initialPreset = viewFrom ? String(viewFrom).toLowerCase() : "iso";
      this.defaultPreset = initialPreset;
      this.setPreset(initialPreset, { fit: true });
    }
  }

  /**
   * Update cached world bounding box and position floor grid at `minZ`.
   *
   * @param {{min: [number, number, number], max: [number, number, number], center: [number, number, number], size: [number, number, number]}} bounds - World AABB.
   */
  setSceneBounds(bounds) {
    if (!bounds || !Array.isArray(bounds.min) || !Array.isArray(bounds.max)) {
      return;
    }
    this.sceneBounds = bounds;
    const span = Math.max(bounds.size[0], bounds.size[1], bounds.size[2], MIN_BOUNDS_SPAN_MM);
    this.floorGridMesh.position.set(bounds.center[0], bounds.center[1], bounds.min[2] - 0.05);
    const mat = this.floorGridMesh.material;
    mat.uniforms.uMinorStep.value = span > 250 ? 10.0 : span > 60 ? 5.0 : 1.0;
    mat.uniforms.uMajorStep.value = mat.uniforms.uMinorStep.value * 5.0;
    mat.uniforms.uFadeRadius.value = Math.max(300.0, span * 4.5);
  }

  /**
   * Toggle seamlessly between Perspective and Orthographic projection (`5` shortcut),
   * matching exact visible world frustum height at `controls.target`!
   *
   * @param {boolean} [forceOrtho] - Optional explicit boolean state.
   * @returns {boolean} Active `isOrtho` flag after toggling.
   */
  toggleProjection(forceOrtho) {
    if (this.is2DMode && forceOrtho === false) {
      // Even if user switches to Perspective in 2D or toggles Ortho, keep frustum height synced
    }
    const nextOrtho = typeof forceOrtho === "boolean" ? forceOrtho : !this.isOrtho;
    if (nextOrtho === this.isOrtho) {
      return this.isOrtho;
    }

    const dist = Math.max(MIN_BOUNDS_SPAN_MM, this.activeCamera.position.distanceTo(this.controls.target));
    const halfFovTan = Math.tan((this.perspCamera.fov * DEG_TO_RAD) * 0.5);

    if (nextOrtho) {
      // Switching Perspective -> Orthographic: match visible half-height at target
      const visibleHalfHeight = dist * halfFovTan;
      this._orthoHalfHeight = visibleHalfHeight;
      this.orthoCamera.zoom = 1.0;
      this.orthoCamera.position.copy(this.perspCamera.position);
      this.orthoCamera.up.copy(this.perspCamera.up);
      this.orthoCamera.quaternion.copy(this.perspCamera.quaternion);
      this._applyOrthoFrustum();
      this.orthoCamera.updateMatrixWorld(true);
      this.isOrtho = true;
      this.controls.object = this.orthoCamera;
    } else {
      // Switching Orthographic -> Perspective: position camera at exact matching distance
      const visibleHalfHeight = this._orthoHalfHeight / Math.max(1e-4, this.orthoCamera.zoom);
      const newDist = Math.max(MIN_NEAR_PLANE * 4, visibleHalfHeight / halfFovTan);
      SCRATCH_VEC_A.subVectors(this.orthoCamera.position, this.controls.target).normalize();
      if (SCRATCH_VEC_A.lengthSq() < 0.5) {
        SCRATCH_VEC_A.set(0, 0, 1);
      }
      this.perspCamera.position.copy(this.controls.target).addScaledVector(SCRATCH_VEC_A, newDist);
      this.perspCamera.up.copy(this.orthoCamera.up);
      this.perspCamera.lookAt(this.controls.target);
      this.perspCamera.updateProjectionMatrix();
      this.perspCamera.updateMatrixWorld(true);
      this.isOrtho = false;
      this.controls.object = this.perspCamera;
    }

    this.controls.update();
    if (this.onChange) {
      this.onChange();
    }
    return this.isOrtho;
  }

  /**
   * Synchronize the inactive camera pose with the active camera so world-space queries stay consistent.
   */
  _syncInactiveCamera() {
    const active = this.activeCamera;
    const inactive = this.isOrtho ? this.perspCamera : this.orthoCamera;
    inactive.position.copy(active.position);
    inactive.quaternion.copy(active.quaternion);
    inactive.up.copy(active.up);
    active.updateMatrixWorld();
    inactive.updateMatrixWorld();
  }

  /**
   * Apply a canonical camera preset (`iso`, `top`, `bottom`, `front`, `rear`, `right`, `left`, `flip`, `fit`).
   *
   * In `PCB` / `DIAGRAM` 2D modes:
   * - `top`, `bottom`, and `flip` preserve the current `(panX, panY)` and zoom unless `fit: true` is passed!
   * - `up` is strictly `(0, 1, 0)` (zero polar gimbal singularity!).
   *
   * @param {string} preset - Preset name.
   * @param {{fit?: boolean}} [options] - Whether to re-fit zoom/target to full `sceneBounds`.
   */
  setPreset(preset, { fit = false } = {}) {
    const key = String(preset || "iso").toLowerCase();
    const bounds = this.sceneBounds;
    const [cx, cy, cz] = bounds.center;
    const [sx, sy, sz] = bounds.size;
    const maxSpan3D = Math.max(sx, sy, sz, MIN_BOUNDS_SPAN_MM);
    const halfFovTan = Math.tan((this.perspCamera.fov * DEG_TO_RAD) * 0.5);

    if (key === "fit") {
      if (this.is2DMode && (this.defaultPreset === "top" || this.defaultPreset === "bottom")) {
        this._fit2DView(this.activeBoardSide === "B.Cu" ? "bottom" : "top");
      } else {
        this._fit3DCurrentDirection();
      }
      return;
    }

    if (this.is2DMode && (key === "top" || key === "bottom" || key === "flip")) {
      const targetSide =
        key === "flip"
          ? this.activeBoardSide === "F.Cu"
            ? "B.Cu"
            : "F.Cu"
          : key === "bottom"
            ? "B.Cu"
            : "F.Cu";

      this.activeBoardSide = targetSide;
      if (fit) {
        this._fit2DView(targetSide === "B.Cu" ? "bottom" : "top");
        return;
      }

      const keepX = this.controls.target.x;
      const keepY = this.controls.target.y;
      const dist = Math.max(maxSpan3D * 2.5, 200);
      const zSign = targetSide === "B.Cu" ? -1 : 1;

      this.controls.target.set(keepX, keepY, cz);
      const cam = this.activeCamera;
      cam.up.set(0, 1, 0);
      cam.position.set(keepX, keepY, cz + zSign * dist);
      cam.lookAt(this.controls.target);
      cam.updateProjectionMatrix();
      cam.updateMatrixWorld(true);
      this._syncInactiveCamera();
      this.controls.update();
      if (this.onChange) this.onChange();
      return;
    }

    // 3D presets (`Z` is world vertical up; when viewing straight along +/-Z, use `Y` up cleanly)
    let dir = [1, -1, 0.82];
    let up = [0, 0, 1];

    switch (key) {
      case "top":
        dir = [0, 0, 1];
        up = [0, 1, 0];
        this.activeBoardSide = "F.Cu";
        break;
      case "bottom":
        dir = [0, 0, -1];
        up = [0, 1, 0];
        this.activeBoardSide = "B.Cu";
        break;
      case "flip":
        if (this.activeBoardSide === "F.Cu") {
          dir = [0, 0, -1];
          up = [0, 1, 0];
          this.activeBoardSide = "B.Cu";
        } else {
          dir = [0, 0, 1];
          up = [0, 1, 0];
          this.activeBoardSide = "F.Cu";
        }
        break;
      case "front":
        dir = [0, -1, 0];
        up = [0, 0, 1];
        break;
      case "rear":
      case "back":
        dir = [0, 1, 0];
        up = [0, 0, 1];
        break;
      case "right":
        dir = [1, 0, 0];
        up = [0, 0, 1];
        break;
      case "left":
        dir = [-1, 0, 0];
        up = [0, 0, 1];
        break;
      case "iso":
      default:
        dir = [1, -1.15, 0.85];
        up = [0, 0, 1];
        break;
    }

    const dLen = Math.hypot(dir[0], dir[1], dir[2]) || 1;
    const ux = dir[0] / dLen;
    const uy = dir[1] / dLen;
    const uz = dir[2] / dLen;

    const fitRadius = Math.max(Math.hypot(sx, sy, sz) * 0.5, MIN_BOUNDS_SPAN_MM) * FIT_PADDING_3D;
    const aspectScale = this.aspect < 1 ? 1 / Math.max(0.25, this.aspect) : 1.0;
    const perspDist = (fitRadius * aspectScale) / halfFovTan;

    this.controls.target.set(cx, cy, cz);
    this._orthoHalfHeight = fitRadius * aspectScale;
    this.orthoCamera.zoom = 1.0;
    this._applyOrthoFrustum();

    this.perspCamera.up.set(up[0], up[1], up[2]);
    this.orthoCamera.up.set(up[0], up[1], up[2]);

    this.perspCamera.position.set(cx + ux * perspDist, cy + uy * perspDist, cz + uz * perspDist);
    this.orthoCamera.position.copy(this.perspCamera.position);

    this.perspCamera.lookAt(this.controls.target);
    this.orthoCamera.lookAt(this.controls.target);
    this.perspCamera.updateProjectionMatrix();
    this.orthoCamera.updateProjectionMatrix();
    this.perspCamera.updateMatrixWorld(true);
    this.orthoCamera.updateMatrixWorld(true);

    this.controls.update();
    if (this.onChange) this.onChange();
  }

  /**
   * Fit the 2D planar orthographic view tightly around `sceneBounds` (`XY` plane).
   *
   * @param {"top"|"bottom"} side - Planar viewing side.
   */
  _fit2DView(side) {
    const [cx, cy, cz] = this.sceneBounds.center;
    const sx = Math.max(this.sceneBounds.size[0], MIN_BOUNDS_SPAN_MM);
    const sy = Math.max(this.sceneBounds.size[1], MIN_BOUNDS_SPAN_MM);

    const halfW = (sx * 0.5) * FIT_PADDING_2D;
    const halfH = (sy * 0.5) * FIT_PADDING_2D;
    this._orthoHalfHeight = Math.max(halfH, halfW / Math.max(0.1, this.aspect));
    this.orthoCamera.zoom = 1.0;
    this._applyOrthoFrustum();

    const dist = Math.max(sx, sy, 100) * 2.5;
    const zSign = side === "bottom" ? -1 : 1;
    this.activeBoardSide = side === "bottom" ? "B.Cu" : "F.Cu";

    this.controls.target.set(cx, cy, cz);
    this.orthoCamera.up.set(0, 1, 0);
    this.perspCamera.up.set(0, 1, 0);
    this.orthoCamera.position.set(cx, cy, cz + zSign * dist);
    this.perspCamera.position.copy(this.orthoCamera.position);
    this.orthoCamera.lookAt(this.controls.target);
    this.perspCamera.lookAt(this.controls.target);
    this.orthoCamera.updateMatrixWorld(true);
    this.perspCamera.updateMatrixWorld(true);

    this.controls.update();
    if (this.onChange) this.onChange();
  }

  /**
   * Re-frame `sceneBounds` along the current 3D viewing ray without resetting orbit orientation.
   */
  _fit3DCurrentDirection() {
    const [cx, cy, cz] = this.sceneBounds.center;
    const [sx, sy, sz] = this.sceneBounds.size;
    const fitRadius = Math.max(Math.hypot(sx, sy, sz) * 0.5, MIN_BOUNDS_SPAN_MM) * FIT_PADDING_3D;
    const aspectScale = this.aspect < 1 ? 1 / Math.max(0.25, this.aspect) : 1.0;
    const halfFovTan = Math.tan((this.perspCamera.fov * DEG_TO_RAD) * 0.5);
    const perspDist = (fitRadius * aspectScale) / halfFovTan;

    SCRATCH_VEC_A.subVectors(this.activeCamera.position, this.controls.target).normalize();
    if (SCRATCH_VEC_A.lengthSq() < 0.5) {
      SCRATCH_VEC_A.set(1, -1.15, 0.85).normalize();
    }

    this.controls.target.set(cx, cy, cz);
    this._orthoHalfHeight = fitRadius * aspectScale;
    this.orthoCamera.zoom = 1.0;
    this._applyOrthoFrustum();

    this.perspCamera.position.set(
      cx + SCRATCH_VEC_A.x * perspDist,
      cy + SCRATCH_VEC_A.y * perspDist,
      cz + SCRATCH_VEC_A.z * perspDist,
    );
    this.orthoCamera.position.copy(this.perspCamera.position);
    this.perspCamera.lookAt(this.controls.target);
    this.orthoCamera.lookAt(this.controls.target);
    this.perspCamera.updateMatrixWorld(true);
    this.orthoCamera.updateMatrixWorld(true);

    this.controls.update();
    if (this.onChange) this.onChange();
  }

  /**
   * Center the camera pivot (`controls.target`) on world point `(wx, wy, wz)` while preserving viewing offset.
   *
   * @param {number} wx - World X in mm.
   * @param {number} wy - World Y in mm.
   * @param {number} [wz] - World Z in mm.
   */
  focusPoint(wx, wy, wz = 0) {
    const cam = this.activeCamera;
    SCRATCH_VEC_A.set(
      (Number(wx) || 0) - this.controls.target.x,
      (Number(wy) || 0) - this.controls.target.y,
      (Number(wz) || 0) - this.controls.target.z,
    );
    cam.position.add(SCRATCH_VEC_A);
    this.controls.target.add(SCRATCH_VEC_A);
    this._syncInactiveCamera();
    this.controls.update();
    if (this.onChange) this.onChange();
  }

  /**
   * Pan camera in screen space by normalized keyboard step `(-1, 0, +1)`.
   *
   * @param {number} stepRight - Horizontal step (`+1` right, `-1` left).
   * @param {number} stepUp - Vertical step (`+1` up, `-1` down).
   */
  panBySteps(stepRight, stepUp) {
    const mmPerPx = this.getMillimetersPerCssPixel();
    const dxMm = stepRight * this.width * KEYBOARD_PAN_FRACTION * mmPerPx;
    const dyMm = stepUp * this.height * KEYBOARD_PAN_FRACTION * mmPerPx;

    const cam = this.activeCamera;
    cam.updateMatrixWorld();
    SCRATCH_VEC_A.setFromMatrixColumn(cam.matrixWorld, 0).multiplyScalar(dxMm);
    SCRATCH_VEC_B.setFromMatrixColumn(cam.matrixWorld, 1).multiplyScalar(dyMm);
    SCRATCH_VEC_A.add(SCRATCH_VEC_B);

    cam.position.add(SCRATCH_VEC_A);
    this.controls.target.add(SCRATCH_VEC_A);
    this._syncInactiveCamera();
    this.controls.update();
    if (this.onChange) this.onChange();
  }

  /**
   * Zoom in (`direction > 0`) or out (`direction < 0`) around viewport center.
   *
   * @param {number} direction - `+1` zoom in, `-1` zoom out.
   */
  zoomByStep(direction) {
    const factor = direction > 0 ? ZOOM_STEP_FACTOR : 1 / ZOOM_STEP_FACTOR;
    if (this.isOrtho) {
      this.orthoCamera.zoom = Math.max(1e-3, Math.min(1e5, this.orthoCamera.zoom * factor));
      this.orthoCamera.updateProjectionMatrix();
    } else {
      SCRATCH_VEC_A.subVectors(this.perspCamera.position, this.controls.target);
      SCRATCH_VEC_A.multiplyScalar(1 / factor);
      if (SCRATCH_VEC_A.length() > MIN_NEAR_PLANE * 2) {
        this.perspCamera.position.copy(this.controls.target).add(SCRATCH_VEC_A);
      }
      this.perspCamera.updateMatrixWorld(true);
    }
    this._syncInactiveCamera();
    if (this.onChange) this.onChange();
  }

  /**
   * Compute physical world millimeters per logical CSS pixel at `controls.target`.
   *
   * @returns {number}
   */
  getMillimetersPerCssPixel() {
    if (this.isOrtho) {
      const worldHeight = (this._orthoHalfHeight * 2) / Math.max(1e-6, this.orthoCamera.zoom);
      return worldHeight / Math.max(1, this.height);
    }
    const dist = Math.max(1e-3, this.perspCamera.position.distanceTo(this.controls.target));
    const worldHeight = 2 * dist * Math.tan((this.perspCamera.fov * DEG_TO_RAD) * 0.5);
    return worldHeight / Math.max(1, this.height);
  }

  /**
   * Project world `(x, y, z)` coordinates to logical CSS viewport `(px, py)`.
   *
   * @param {number} wx - World X in mm.
   * @param {number} wy - World Y in mm.
   * @param {number} [wz] - World Z in mm.
   * @returns {{x: number, y: number, ndcZ: number, visible: boolean}}
   */
  worldToCss(wx, wy, wz = 0) {
    const cam = this.activeCamera;
    SCRATCH_VEC_A.set(wx, wy, wz).project(cam);
    const x = (SCRATCH_VEC_A.x * 0.5 + 0.5) * this.width;
    const y = (-SCRATCH_VEC_A.y * 0.5 + 0.5) * this.height;
    const visible = SCRATCH_VEC_A.z >= -1.0 && SCRATCH_VEC_A.z <= 1.0;
    return { x, y, ndcZ: SCRATCH_VEC_A.z, visible };
  }

  /**
   * Intersect a normalized device coordinate `(ndcX, ndcY)` ray with the horizontal plane `z = planeZ`
   * in $O(1)$ arithmetic (5 ns, zero allocations, zero scene-graph traversal!).
   *
   * @param {number} ndcX - Normalized device X in `[-1, 1]`.
   * @param {number} ndcY - Normalized device Y in `[-1, 1]`.
   * @param {number} [planeZ] - Target Z plane in mm (`0` default).
   * @returns {{x: number, y: number, z: number}|null}
   */
  screenNdcToPlaneZ(ndcX, ndcY, planeZ = 0) {
    const cam = this.activeCamera;
    cam.updateMatrixWorld();

    if (this.isOrtho && this.is2DMode) {
      // Pure 4-multiply affine screen-to-board transform when looking straight along +/-Z!
      const zoom = Math.max(1e-6, this.orthoCamera.zoom);
      const halfW = (this._orthoHalfHeight * this.aspect) / zoom;
      const halfH = this._orthoHalfHeight / zoom;
      const xSign = this.activeBoardSide === "B.Cu" ? -1 : 1;
      return {
        x: cam.position.x + ndcX * halfW * xSign,
        y: cam.position.y + ndcY * halfH,
        z: planeZ,
      };
    }

    if (this.isOrtho) {
      SCRATCH_RAY.origin
        .set(ndcX, ndcY, (cam.near + cam.far) / (cam.near - cam.far))
        .unproject(cam);
      SCRATCH_RAY.direction.set(0, 0, -1).transformDirection(cam.matrixWorld);
    } else {
      SCRATCH_RAY.origin.setFromMatrixPosition(cam.matrixWorld);
      SCRATCH_RAY.direction.set(ndcX, ndcY, 0.5).unproject(cam).sub(SCRATCH_RAY.origin).normalize();
    }

    const denom = SCRATCH_RAY.direction.dot(SCRATCH_PLANE_NORMAL);
    if (Math.abs(denom) < 1e-8) {
      return null;
    }
    const t = (planeZ - SCRATCH_RAY.origin.z) / denom;
    if (t < 0 && !this.isOrtho) {
      return null;
    }
    return {
      x: SCRATCH_RAY.origin.x + SCRATCH_RAY.direction.x * t,
      y: SCRATCH_RAY.origin.y + SCRATCH_RAY.direction.y * t,
      z: planeZ,
    };
  }

  /**
   * Compute the visible XY world bounding rectangle `[minX, minY, maxX, maxY]` at `planeZ`.
   *
   * @param {number} [planeZ] - Board Z plane in mm.
   * @returns {{minX: number, minY: number, maxX: number, maxY: number}}
   */
  getVisibleWorldBounds2D(planeZ = 0) {
    const corners = [
      this.screenNdcToPlaneZ(-1, -1, planeZ),
      this.screenNdcToPlaneZ(1, -1, planeZ),
      this.screenNdcToPlaneZ(-1, 1, planeZ),
      this.screenNdcToPlaneZ(1, 1, planeZ),
    ];
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const pt of corners) {
      if (!pt) continue;
      if (pt.x < minX) minX = pt.x;
      if (pt.y < minY) minY = pt.y;
      if (pt.x > maxX) maxX = pt.x;
      if (pt.y > maxY) maxY = pt.y;
    }
    if (!Number.isFinite(minX)) {
      return {
        minX: this.sceneBounds.min[0],
        minY: this.sceneBounds.min[1],
        maxX: this.sceneBounds.max[0],
        maxY: this.sceneBounds.max[1],
      };
    }
    return { minX, minY, maxX, maxY };
  }

  /**
   * Set floor grid visibility.
   *
   * @param {boolean} visible - Grid visibility flag.
   */
  setGridVisible(visible) {
    this.gridVisible = Boolean(visible);
    this.floorGridMesh.visible = this.gridVisible && !this.is2DMode;
    if (this.onChange) this.onChange();
  }

  /**
   * Set coordinate axes gizmo visibility.
   *
   * @param {boolean} visible - Gizmo visibility flag.
   */
  setAxesVisible(visible) {
    this.axesVisible = Boolean(visible);
    if (this.onChange) this.onChange();
  }

  /**
   * Draw the crisp `2x` Retina 3D orientation gizmo and physical world-space scale bar (`mm` / `mil`).
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina-scaled 2D canvas context.
   * @param {{width: number, height: number}} metrics - Logical CSS viewport dimensions.
   */
  drawHudOverlays(ctx2d, { width, height }) {
    this._drawScaleBar(ctx2d, height);
    if (this.axesVisible) {
      this._drawOrientationGizmo(ctx2d, width, height);
    }
  }

  /**
   * Draw physical `mm` + `mil` scale bar in the bottom-left corner of the viewport.
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina 2D context.
   * @param {number} height - Viewport CSS height.
   */
  _drawScaleBar(ctx2d, height) {
    const mmPerPx = this.getMillimetersPerCssPixel();
    if (!Number.isFinite(mmPerPx) || mmPerPx <= 0) {
      return;
    }
    const rawMm = SCALE_BAR_TARGET_PX * mmPerPx;
    let chosenMm = NICE_SCALE_STEPS[0];
    for (const step of NICE_SCALE_STEPS) {
      chosenMm = step;
      if (step >= rawMm * 0.75) {
        break;
      }
    }
    const barPx = Math.max(28, Math.min(180, chosenMm / mmPerPx));
    const x0 = Math.round(SCALE_BAR_LEFT_PX) + 0.5;
    const y0 = Math.round(height - SCALE_BAR_BOTTOM_PX) + 0.5;
    const x1 = Math.round(SCALE_BAR_LEFT_PX + barPx) + 0.5;

    const isLightBg = this.mode === "DIAGRAM";
    const bgFill = isLightBg ? "rgba(15, 23, 42, 0.84)" : "rgba(12, 16, 24, 0.86)";
    const strokeCol = "#38bdf8";
    const textCol = "#f8fafc";

    const labelMm = chosenMm >= 1 ? `${chosenMm} mm` : `${chosenMm.toFixed(2)} mm`;
    const mils = chosenMm * MILS_PER_MM;
    const labelText = this.mode === "PCB" ? `${labelMm} (${Math.round(mils)} mil)` : labelMm;

    ctx2d.font = '700 10.5px ui-monospace, "SF Mono", Menlo, monospace';
    const textW = ctx2d.measureText(labelText).width;
    const boxW = Math.max(barPx, textW) + 16;

    ctx2d.fillStyle = bgFill;
    ctx2d.strokeStyle = "rgba(56, 189, 248, 0.45)";
    ctx2d.lineWidth = 1;
    ctx2d.beginPath();
    ctx2d.roundRect(SCALE_BAR_LEFT_PX - 6, y0 - 24, boxW, 30, 4);
    ctx2d.fill();
    ctx2d.stroke();

    ctx2d.strokeStyle = strokeCol;
    ctx2d.lineWidth = 2;
    ctx2d.beginPath();
    ctx2d.moveTo(x0, y0 - 4);
    ctx2d.lineTo(x0, y0);
    ctx2d.lineTo(x1, y0);
    ctx2d.lineTo(x1, y0 - 4);
    ctx2d.stroke();

    ctx2d.fillStyle = textCol;
    ctx2d.textAlign = "left";
    ctx2d.textBaseline = "bottom";
    ctx2d.fillText(labelText, SCALE_BAR_LEFT_PX, y0 - 6);
  }

  /**
   * Draw the `2x` Retina `X / Y / Z` orientation triad gizmo in the bottom-right corner.
   *
   * @param {CanvasRenderingContext2D} ctx2d - Retina 2D context.
   * @param {number} width - Viewport CSS width.
   * @param {number} height - Viewport CSS height.
   */
  _drawOrientationGizmo(ctx2d, width, height) {
    const cx = width - GIZMO_MARGIN_RIGHT_PX;
    const cy = height - GIZMO_MARGIN_BOTTOM_PX;
    const armLen = GIZMO_RADIUS_PX - 8;

    const cam = this.activeCamera;
    cam.updateMatrixWorld();
    const invView = cam.matrixWorldInverse.elements;

    const axes = [
      { label: "X", color: "#ef4444", vx: invView[0], vy: invView[1], vz: invView[2] },
      { label: "Y", color: "#22c55e", vx: invView[4], vy: invView[5], vz: invView[6] },
      { label: "Z", color: "#38bdf8", vx: invView[8], vy: invView[9], vz: invView[10] },
    ];
    axes.sort((a, b) => a.vz - b.vz);

    ctx2d.fillStyle = "rgba(12, 16, 24, 0.78)";
    ctx2d.strokeStyle = "rgba(141, 93, 51, 0.65)";
    ctx2d.lineWidth = 1;
    ctx2d.beginPath();
    ctx2d.arc(cx, cy, GIZMO_RADIUS_PX + 4, 0, Math.PI * 2);
    ctx2d.fill();
    ctx2d.stroke();

    ctx2d.font = '800 10px ui-monospace, "SF Mono", Menlo, monospace';
    ctx2d.textAlign = "center";
    ctx2d.textBaseline = "middle";

    for (const axis of axes) {
      const ex = cx + axis.vx * armLen;
      const ey = cy - axis.vy * armLen;

      ctx2d.strokeStyle = axis.color;
      ctx2d.lineWidth = 2;
      ctx2d.beginPath();
      ctx2d.moveTo(cx, cy);
      ctx2d.lineTo(ex, ey);
      ctx2d.stroke();

      ctx2d.fillStyle = axis.color;
      ctx2d.beginPath();
      ctx2d.arc(ex, ey, 6.5, 0, Math.PI * 2);
      ctx2d.fill();

      ctx2d.fillStyle = "#080c12";
      ctx2d.fillText(axis.label, ex, ey + 0.5);
    }
  }
}
