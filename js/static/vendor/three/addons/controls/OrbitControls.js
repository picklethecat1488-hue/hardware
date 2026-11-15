/**
 * Zero-globals CAD/PCB/2D Orbit, Pan, and Cursor-Centric Zoom Controls.
 *
 * Adapted for Three.js r184 (MIT License) with strict zero-globals compliance:
 * binds exclusively to the explicitly supplied `domElement` using Pointer Capture
 * (`setPointerCapture` / `releasePointerCapture`), supports seamless switching
 * between `PerspectiveCamera` and `OrthographicCamera`, supports locked 2D planar
 * pan/zoom (`enableRotate = false`), and zooms directly toward the cursor point!
 */

import { EventDispatcher, MOUSE, Quaternion, Spherical, Vector2, Vector3 } from "../../three.module.js";

const CHANGE_EVENT = { type: "change" };
const START_EVENT = { type: "start" };
const END_EVENT = { type: "end" };

const STATE_NONE = -1;
const STATE_ROTATE = 0;
const STATE_DOLLY = 1;
const STATE_PAN = 2;
const STATE_TOUCH_ROTATE = 3;
const STATE_TOUCH_PAN = 4;
const STATE_TOUCH_DOLLY_PAN = 5;

const EPSILON = 1e-6;
const TWO_PI = 2 * Math.PI;
const DEFAULT_POLAR_MIN_RAD = 1e-4;
const DEFAULT_POLAR_MAX_RAD = Math.PI - 1e-4;
const DEFAULT_ZOOM_SPEED = 1.0;
const DEFAULT_ROTATE_SPEED = 1.0;
const DEFAULT_PAN_SPEED = 1.0;
const WHEEL_DOLLY_BASE = 0.86;
const WHEEL_DELTA_NORMALIZER = 45;
const TRACKPAD_PINCH_MULTIPLIER = 3.5;
const MAX_WHEEL_DOLLY_STEPS = 6;
const WHEEL_LINE_HEIGHT_PX = 16;
const WHEEL_MODE_LINE = 1;
const MIN_ORTHO_ZOOM = 1e-4;
const MAX_ORTHO_ZOOM = 1e6;
const MIN_PERSP_DISTANCE = 0.1;
const MAX_PERSP_DISTANCE = 1e7;

const SCRATCH_OFFSET = new Vector3();
const SCRATCH_PAN_OFFSET = new Vector3();
const SCRATCH_COL_V = new Vector3();
const SCRATCH_QUAT = new Quaternion();
const SCRATCH_QUAT_INV = new Quaternion();
const SCRATCH_SPHERICAL = new Spherical();
const SCRATCH_WORLD_BEFORE = new Vector3();
const SCRATCH_WORLD_AFTER = new Vector3();
const CANONICAL_Y_UP = new Vector3(0, 1, 0);

/**
 * Interactive 3D/2D camera controller for Three.js scenes with cursor-centric zoom.
 */
export class OrbitControls extends EventDispatcher {
  /**
   * Construct an `OrbitControls` instance bound to `object` and `domElement`.
   *
   * @param {import("../../three.module.js").Camera} object - Controlled Perspective or Orthographic camera.
   * @param {HTMLElement|null} domElement - Viewport element receiving pointer/wheel events (nullable in headless tests).
   */
  constructor(object, domElement = null) {
    super();

    /** @type {import("../../three.module.js").Camera} */
    this.object = object;
    /** @type {HTMLElement|null} */
    this.domElement = domElement;

    /** @type {boolean} */
    this.enabled = true;
    /** @type {Vector3} */
    this.target = new Vector3();

    /** @type {number} */
    this.minDistance = MIN_PERSP_DISTANCE;
    /** @type {number} */
    this.maxDistance = MAX_PERSP_DISTANCE;
    /** @type {number} */
    this.minZoom = MIN_ORTHO_ZOOM;
    /** @type {number} */
    this.maxZoom = MAX_ORTHO_ZOOM;

    /** @type {number} */
    this.minPolarAngle = DEFAULT_POLAR_MIN_RAD;
    /** @type {number} */
    this.maxPolarAngle = DEFAULT_POLAR_MAX_RAD;

    /** @type {boolean} */
    this.enableRotate = true;
    /** @type {number} */
    this.rotateSpeed = DEFAULT_ROTATE_SPEED;

    /** @type {boolean} */
    this.enableZoom = true;
    /** @type {number} */
    this.zoomSpeed = DEFAULT_ZOOM_SPEED;
    /** @type {boolean} */
    this.zoomToCursor = true;

    /** @type {boolean} */
    this.enablePan = true;
    /** @type {number} */
    this.panSpeed = DEFAULT_PAN_SPEED;
    /** @type {boolean} */
    this.screenSpacePanning = true;

    this.mouseButtons = {
      LEFT: MOUSE.ROTATE,
      MIDDLE: MOUSE.PAN,
      RIGHT: MOUSE.PAN,
    };

    this._state = STATE_NONE;
    this._sphericalDelta = new Spherical();
    this._panOffset = new Vector3();
    this._scale = 1.0;

    this._rotateStart = new Vector2();
    this._rotateEnd = new Vector2();
    this._rotateDelta = new Vector2();

    this._panStart = new Vector2();
    this._panEnd = new Vector2();
    this._panDelta = new Vector2();

    this._dollyStart = new Vector2();
    this._dollyEnd = new Vector2();
    this._dollyDelta = new Vector2();

    this._pointers = [];
    this._pointerPositions = new Map();

    this._lastPosition = new Vector3();
    this._lastQuaternion = new Quaternion();
    this._lastZoom = 1;

    this._onPointerDown = this._handlePointerDown.bind(this);
    this._onPointerMove = this._handlePointerMove.bind(this);
    this._onPointerUp = this._handlePointerUp.bind(this);
    this._onContextMenu = this._handleContextMenu.bind(this);
    this._onMouseWheel = this._handleMouseWheel.bind(this);

    if (this.domElement !== null) {
      this.connect(this.domElement);
    }
    this.update();
  }

  /**
   * Attach pointer, contextmenu, and wheel listeners to `element`.
   *
   * @param {HTMLElement} element - Target viewport element.
   */
  connect(element) {
    if (this.domElement !== null && this.domElement !== element) {
      this.disconnect();
    }
    this.domElement = element;
    if (this.domElement.style) {
      this.domElement.style.touchAction = "none";
    }
    this.domElement.addEventListener("pointerdown", this._onPointerDown);
    this.domElement.addEventListener("pointermove", this._onPointerMove);
    this.domElement.addEventListener("pointerup", this._onPointerUp);
    this.domElement.addEventListener("pointercancel", this._onPointerUp);
    this.domElement.addEventListener("contextmenu", this._onContextMenu);
    this.domElement.addEventListener("wheel", this._onMouseWheel, { passive: false });
  }

  /**
   * Detach all event listeners from `domElement`.
   */
  disconnect() {
    if (this.domElement === null) {
      return;
    }
    this.domElement.removeEventListener("pointerdown", this._onPointerDown);
    this.domElement.removeEventListener("pointermove", this._onPointerMove);
    this.domElement.removeEventListener("pointerup", this._onPointerUp);
    this.domElement.removeEventListener("pointercancel", this._onPointerUp);
    this.domElement.removeEventListener("contextmenu", this._onContextMenu);
    this.domElement.removeEventListener("wheel", this._onMouseWheel);
  }

  /**
   * Dispose event listeners.
   */
  dispose() {
    this.disconnect();
  }

  /**
   * Swap the controlled camera (e.g. toggling Perspective <-> Orthographic) without losing target.
   *
   * @param {import("../../three.module.js").Camera} camera - Replacement camera.
   */
  setCamera(camera) {
    this.object = camera;
    this._lastZoom = -1;
    this.update();
  }

  /**
   * Rotate horizontally by `angleRad` radians around the camera's `up` axis.
   *
   * @param {number} angleRad - Azimuth delta in radians.
   */
  rotateLeft(angleRad) {
    this._sphericalDelta.theta -= angleRad;
  }

  /**
   * Rotate vertically by `angleRad` radians.
   *
   * @param {number} angleRad - Polar delta in radians.
   */
  rotateUp(angleRad) {
    this._sphericalDelta.phi -= angleRad;
  }

  /**
   * Pan the camera and target in screen space by `(deltaX, deltaY)` CSS pixels.
   *
   * @param {number} deltaX - Horizontal drag in CSS pixels.
   * @param {number} deltaY - Vertical drag in CSS pixels.
   * @param {number} [viewportWidth] - Explicit viewport width override.
   * @param {number} [viewportHeight] - Explicit viewport height override.
   */
  pan(deltaX, deltaY, viewportWidth, viewportHeight) {
    const rect = this._getElementBounds(viewportWidth, viewportHeight);
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const camera = this.object;

    if (camera.isPerspectiveCamera) {
      SCRATCH_OFFSET.copy(camera.position).sub(this.target);
      const targetDistance =
        SCRATCH_OFFSET.length() * Math.tan(((camera.fov * 0.5) * Math.PI) / 180.0);
      this._panLeft((2 * deltaX * targetDistance) / height, camera.matrix);
      this._panUp((2 * deltaY * targetDistance) / height, camera.matrix);
    } else if (camera.isOrthographicCamera) {
      const worldWidth = (camera.right - camera.left) / camera.zoom;
      const worldHeight = (camera.top - camera.bottom) / camera.zoom;
      this._panLeft((deltaX * worldWidth) / width, camera.matrix);
      this._panUp((deltaY * worldHeight) / height, camera.matrix);
    }
  }

  /**
   * Apply a multiplicative dolly/zoom factor (`scale < 1` zooms in; `scale > 1` zooms out).
   *
   * @param {number} dollyScale - Multiplicative scale factor.
   * @param {number} [ndcX] - Optional cursor NDC X in `[-1, 1]` for cursor-centric zoom.
   * @param {number} [ndcY] - Optional cursor NDC Y in `[-1, 1]` for cursor-centric zoom.
   */
  dollyByScale(dollyScale, ndcX = 0, ndcY = 0) {
    if (!Number.isFinite(dollyScale) || dollyScale <= 0) {
      return;
    }

    const camera = this.object;
    const anchorCursor =
      this.zoomToCursor && (Math.abs(ndcX) > EPSILON || Math.abs(ndcY) > EPSILON);

    if (camera.isOrthographicCamera) {
      if (anchorCursor) {
        this._unprojectOnTargetPlane(ndcX, ndcY, SCRATCH_WORLD_BEFORE);
      }
      camera.zoom = Math.max(
        this.minZoom,
        Math.min(this.maxZoom, camera.zoom / dollyScale),
      );
      camera.updateProjectionMatrix();
      if (anchorCursor) {
        this._unprojectOnTargetPlane(ndcX, ndcY, SCRATCH_WORLD_AFTER);
        SCRATCH_PAN_OFFSET.subVectors(SCRATCH_WORLD_BEFORE, SCRATCH_WORLD_AFTER);
        camera.position.add(SCRATCH_PAN_OFFSET);
        this.target.add(SCRATCH_PAN_OFFSET);
        camera.updateMatrixWorld();
      }
    } else if (camera.isPerspectiveCamera) {
      if (anchorCursor) {
        this._unprojectOnTargetPlane(ndcX, ndcY, SCRATCH_WORLD_BEFORE);
      }
      this._scale *= dollyScale;
      this.update();
      if (anchorCursor) {
        this._unprojectOnTargetPlane(ndcX, ndcY, SCRATCH_WORLD_AFTER);
        SCRATCH_PAN_OFFSET.subVectors(SCRATCH_WORLD_BEFORE, SCRATCH_WORLD_AFTER);
        camera.position.add(SCRATCH_PAN_OFFSET);
        this.target.add(SCRATCH_PAN_OFFSET);
        camera.updateMatrixWorld();
        this.dispatchEvent(CHANGE_EVENT);
      }
      return;
    }

    this.update();
  }

  /**
   * Integrate pending spherical/pan/scale deltas into `camera.position` and `target`.
   *
   * @returns {boolean} True when camera pose or zoom changed.
   */
  update() {
    const camera = this.object;
    SCRATCH_QUAT.setFromUnitVectors(camera.up, CANONICAL_Y_UP);
    SCRATCH_QUAT_INV.copy(SCRATCH_QUAT).invert();

    SCRATCH_OFFSET.copy(camera.position).sub(this.target);

    if (this.enableRotate) {
      SCRATCH_OFFSET.applyQuaternion(SCRATCH_QUAT);
      SCRATCH_SPHERICAL.setFromVector3(SCRATCH_OFFSET);
      SCRATCH_SPHERICAL.theta += this._sphericalDelta.theta;
      SCRATCH_SPHERICAL.phi += this._sphericalDelta.phi;
      SCRATCH_SPHERICAL.phi = Math.max(
        this.minPolarAngle,
        Math.min(this.maxPolarAngle, SCRATCH_SPHERICAL.phi),
      );
      SCRATCH_SPHERICAL.makeSafe();
      SCRATCH_SPHERICAL.radius = Math.max(
        this.minDistance,
        Math.min(this.maxDistance, SCRATCH_SPHERICAL.radius * this._scale),
      );
      SCRATCH_OFFSET.setFromSpherical(SCRATCH_SPHERICAL);
      SCRATCH_OFFSET.applyQuaternion(SCRATCH_QUAT_INV);
    } else {
      const nextLen = Math.max(
        this.minDistance,
        Math.min(this.maxDistance, SCRATCH_OFFSET.length() * this._scale),
      );
      if (SCRATCH_OFFSET.lengthSq() > EPSILON) {
        SCRATCH_OFFSET.setLength(nextLen);
      }
    }

    this.target.add(this._panOffset);
    camera.position.copy(this.target).add(SCRATCH_OFFSET);
    camera.lookAt(this.target);
    camera.updateMatrixWorld();

    this._sphericalDelta.set(0, 0, 0);
    this._panOffset.set(0, 0, 0);
    this._scale = 1.0;

    const currentZoom = camera.zoom || 1;
    if (
      this._lastPosition.distanceToSquared(camera.position) > EPSILON ||
      8 * (1 - this._lastQuaternion.dot(camera.quaternion)) > EPSILON ||
      Math.abs(this._lastZoom - currentZoom) > EPSILON
    ) {
      this._lastPosition.copy(camera.position);
      this._lastQuaternion.copy(camera.quaternion);
      this._lastZoom = currentZoom;
      this.dispatchEvent(CHANGE_EVENT);
      return true;
    }
    return false;
  }

  _panLeft(distance, objectMatrix) {
    SCRATCH_COL_V.setFromMatrixColumn(objectMatrix, 0);
    SCRATCH_COL_V.multiplyScalar(-distance);
    this._panOffset.add(SCRATCH_COL_V);
  }

  _panUp(distance, objectMatrix) {
    if (this.screenSpacePanning) {
      SCRATCH_COL_V.setFromMatrixColumn(objectMatrix, 1);
    } else {
      SCRATCH_COL_V.setFromMatrixColumn(objectMatrix, 0);
      SCRATCH_COL_V.crossVectors(this.object.up, SCRATCH_COL_V);
    }
    SCRATCH_COL_V.multiplyScalar(distance);
    this._panOffset.add(SCRATCH_COL_V);
  }

  _unprojectOnTargetPlane(ndcX, ndcY, outWorld) {
    const camera = this.object;
    camera.updateMatrixWorld();
    const planeNormal = SCRATCH_OFFSET.copy(camera.position).sub(this.target);
    const dist = planeNormal.length();
    if (dist <= EPSILON) {
      outWorld.copy(this.target);
      return outWorld;
    }
    planeNormal.divideScalar(dist);

    if (camera.isOrthographicCamera) {
      outWorld.set(ndcX, ndcY, 0).unproject(camera);
      const signedDist = SCRATCH_COL_V.subVectors(outWorld, this.target).dot(planeNormal);
      outWorld.addScaledVector(planeNormal, -signedDist);
      return outWorld;
    }

    const rayPoint = SCRATCH_COL_V.set(ndcX, ndcY, 0.5).unproject(camera);
    const rayDir = rayPoint.sub(camera.position).normalize();
    const denom = rayDir.dot(planeNormal);
    if (Math.abs(denom) <= EPSILON) {
      outWorld.copy(this.target);
      return outWorld;
    }
    const t = SCRATCH_PAN_OFFSET.subVectors(this.target, camera.position).dot(planeNormal) / denom;
    outWorld.copy(camera.position).addScaledVector(rayDir, t);
    return outWorld;
  }

  _getElementBounds(overrideW, overrideH) {
    if (Number.isFinite(overrideW) && Number.isFinite(overrideH)) {
      return { left: 0, top: 0, width: overrideW, height: overrideH };
    }
    if (this.domElement && typeof this.domElement.getBoundingClientRect === "function") {
      return this.domElement.getBoundingClientRect();
    }
    const fallbackW = (this.domElement && this.domElement.clientWidth) || 1;
    const fallbackH = (this.domElement && this.domElement.clientHeight) || 1;
    return { left: 0, top: 0, width: fallbackW, height: fallbackH };
  }

  _handleContextMenu(event) {
    if (!this.enabled) {
      return;
    }
    event.preventDefault();
  }

  _handlePointerDown(event) {
    if (!this.enabled) {
      return;
    }
    if (this._pointers.length === 0 && this.domElement && this.domElement.setPointerCapture) {
      this.domElement.setPointerCapture(event.pointerId);
    }
    if (!this._pointers.includes(event.pointerId)) {
      this._pointers.push(event.pointerId);
    }
    this._pointerPositions.set(event.pointerId, new Vector2(event.clientX, event.clientY));

    if (event.pointerType === "touch") {
      this._startTouchGesture();
    } else {
      this._startMouseGesture(event);
    }

    if (this._state !== STATE_NONE) {
      this.dispatchEvent(START_EVENT);
    }
  }

  _startMouseGesture(event) {
    let mouseAction = -1;
    switch (event.button) {
      case 0:
        mouseAction = this.mouseButtons.LEFT;
        break;
      case 1:
        mouseAction = this.mouseButtons.MIDDLE;
        break;
      case 2:
        mouseAction = this.mouseButtons.RIGHT;
        break;
      default:
        mouseAction = -1;
    }

    if (mouseAction === MOUSE.DOLLY) {
      if (!this.enableZoom) {
        return;
      }
      this._dollyStart.set(event.clientX, event.clientY);
      this._state = STATE_DOLLY;
    } else if (mouseAction === MOUSE.ROTATE) {
      if (event.shiftKey || event.ctrlKey || event.metaKey || !this.enableRotate) {
        if (!this.enablePan) {
          return;
        }
        this._panStart.set(event.clientX, event.clientY);
        this._state = STATE_PAN;
      } else {
        this._rotateStart.set(event.clientX, event.clientY);
        this._state = STATE_ROTATE;
      }
    } else if (mouseAction === MOUSE.PAN) {
      if (!this.enablePan) {
        return;
      }
      this._panStart.set(event.clientX, event.clientY);
      this._state = STATE_PAN;
    }
  }

  _startTouchGesture() {
    if (this._pointers.length === 1) {
      const pos = this._pointerPositions.get(this._pointers[0]);
      if (this.enableRotate) {
        this._rotateStart.copy(pos);
        this._state = STATE_TOUCH_ROTATE;
      } else if (this.enablePan) {
        this._panStart.copy(pos);
        this._state = STATE_TOUCH_PAN;
      }
    } else if (this._pointers.length >= 2) {
      const p0 = this._pointerPositions.get(this._pointers[0]);
      const p1 = this._pointerPositions.get(this._pointers[1]);
      const dist = p0.distanceTo(p1);
      this._dollyStart.set(0, dist);
      this._panStart.set(0.5 * (p0.x + p1.x), 0.5 * (p0.y + p1.y));
      this._state = STATE_TOUCH_DOLLY_PAN;
    }
  }

  _handlePointerMove(event) {
    if (!this.enabled || this._state === STATE_NONE) {
      return;
    }
    const tracked = this._pointerPositions.get(event.pointerId);
    if (tracked) {
      tracked.set(event.clientX, event.clientY);
    }

    const rect = this._getElementBounds();
    const height = Math.max(1, rect.height);

    if (this._state === STATE_ROTATE || this._state === STATE_TOUCH_ROTATE) {
      this._rotateEnd.set(event.clientX, event.clientY);
      this._rotateDelta
        .subVectors(this._rotateEnd, this._rotateStart)
        .multiplyScalar(this.rotateSpeed);
      this.rotateLeft((TWO_PI * this._rotateDelta.x) / height);
      this.rotateUp((TWO_PI * this._rotateDelta.y) / height);
      this._rotateStart.copy(this._rotateEnd);
      this.update();
    } else if (this._state === STATE_PAN || this._state === STATE_TOUCH_PAN) {
      this._panEnd.set(event.clientX, event.clientY);
      this._panDelta.subVectors(this._panEnd, this._panStart).multiplyScalar(this.panSpeed);
      this.pan(this._panDelta.x, this._panDelta.y, rect.width, rect.height);
      this._panStart.copy(this._panEnd);
      this.update();
    } else if (this._state === STATE_DOLLY) {
      this._dollyEnd.set(event.clientX, event.clientY);
      this._dollyDelta.subVectors(this._dollyEnd, this._dollyStart);
      if (this._dollyDelta.y > 0) {
        this.dollyByScale(1 / Math.pow(WHEEL_DOLLY_BASE, this.zoomSpeed));
      } else if (this._dollyDelta.y < 0) {
        this.dollyByScale(Math.pow(WHEEL_DOLLY_BASE, this.zoomSpeed));
      }
      this._dollyStart.copy(this._dollyEnd);
    } else if (this._state === STATE_TOUCH_DOLLY_PAN && this._pointers.length >= 2) {
      const p0 = this._pointerPositions.get(this._pointers[0]);
      const p1 = this._pointerPositions.get(this._pointers[1]);
      if (this.enablePan) {
        this._panEnd.set(0.5 * (p0.x + p1.x), 0.5 * (p0.y + p1.y));
        this._panDelta.subVectors(this._panEnd, this._panStart).multiplyScalar(this.panSpeed);
        this.pan(this._panDelta.x, this._panDelta.y, rect.width, rect.height);
        this._panStart.copy(this._panEnd);
      }
      if (this.enableZoom) {
        const dist = Math.max(1, p0.distanceTo(p1));
        this._dollyEnd.set(0, dist);
        const ratio = Math.pow(this._dollyStart.y / this._dollyEnd.y, this.zoomSpeed);
        this.dollyByScale(ratio);
        this._dollyStart.copy(this._dollyEnd);
      } else {
        this.update();
      }
    }
  }

  _handlePointerUp(event) {
    const idx = this._pointers.indexOf(event.pointerId);
    if (idx !== -1) {
      this._pointers.splice(idx, 1);
    }
    this._pointerPositions.delete(event.pointerId);

    if (
      this._pointers.length === 0 &&
      this.domElement &&
      this.domElement.hasPointerCapture &&
      this.domElement.hasPointerCapture(event.pointerId)
    ) {
      this.domElement.releasePointerCapture(event.pointerId);
    }

    if (this._pointers.length === 0 && this._state !== STATE_NONE) {
      this._state = STATE_NONE;
      this.dispatchEvent(END_EVENT);
    }
  }

  _handleMouseWheel(event) {
    if (!this.enabled || !this.enableZoom) {
      return;
    }
    event.preventDefault();

    const rect = this._getElementBounds();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const ndcX = ((event.clientX - rect.left) / width) * 2 - 1;
    const ndcY = -(((event.clientY - rect.top) / height) * 2 - 1);

    let rawDeltaY = event.deltaY;
    if (event.deltaMode === WHEEL_MODE_LINE) {
      rawDeltaY *= WHEEL_LINE_HEIGHT_PX;
    }
    if (event.ctrlKey) {
      rawDeltaY *= TRACKPAD_PINCH_MULTIPLIER;
    }
    const clampedSteps = Math.max(
      -MAX_WHEEL_DOLLY_STEPS,
      Math.min(MAX_WHEEL_DOLLY_STEPS, rawDeltaY / WHEEL_DELTA_NORMALIZER),
    );
    const dollyScale = Math.pow(1 / WHEEL_DOLLY_BASE, clampedSteps * this.zoomSpeed);

    this.dispatchEvent(START_EVENT);
    this.dollyByScale(dollyScale, ndcX, ndcY);
    this.dispatchEvent(END_EVENT);
  }
}
