/**
 * Batched 3D CAD Scene Graph, Clipping/Explode Controller, & Fast AABB B-Rep Raycaster.
 *
 * Replaces `three-cad-viewer`'s 23,180-object unbatched scene graph and synchronous
 * multi-pass `IdPicker` (`gl.readPixels`) stalls with:
 * 1. Shared indexed `BufferGeometry` + physical-pixel `LineSegments2` per unique `instance`.
 * 2. Named rigid-body `Group` nodes (`linkGroups`) for $O(1)$ kinematic `Transform3D` updates
 *    in `SIMULATE` mode and radial centroid `setExplode(0..1)` in `CAD` mode.
 * 3. Fast world-AABB pre-filtered CPU raycasting + `lookupBrepFace` + `measureBrepFace`
 *    with a dedicated single-mesh B-rep face highlight overlay (`polygonOffset`).
 */

import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  FrontSide,
  Group,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Plane,
  Quaternion,
  Raycaster,
  Uint32BufferAttribute,
  Vector2,
  Vector3,
} from "../static/vendor/three/three.module.js";
import { LineMaterial } from "../static/vendor/three/addons/lines/LineMaterial.js";
import { LineSegments2 } from "../static/vendor/three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "../static/vendor/three/addons/lines/LineSegmentsGeometry.js";
import { lookupBrepFace, measureBrepFace } from "./decoder.js";

export const DEFAULT_CAD_ROUGHNESS = 0.78;
export const DEFAULT_CAD_METALNESS = 0.04;
const DEFAULT_PCB_SUBSTRATE_ROUGHNESS = 0.82;
const DEFAULT_PCB_SUBSTRATE_METALNESS = 0.03;
const DEFAULT_EDGE_COLOR_CAD = 0x182230;
const DEFAULT_EDGE_COLOR_DIAGRAM = 0x0f172a;
const HIGHLIGHT_FACE_COLOR_HEX = 0xffb800;
const BASE_EDGE_CSS_PX = 1.25;
const DIAGRAM_EDGE_CSS_PX = 1.5;
const EXPLODE_RADIAL_MULTIPLIER = 1.35;
const MIN_INSTANCED_BATCH_COUNT = 6;
const INDICES_PER_TRIANGLE = 3;

const SCRATCH_RAYCASTER = new Raycaster();
const SCRATCH_NDC = new Vector2();
const SCRATCH_MAT4 = new Matrix4();
const SCRATCH_POS = new Vector3();
const SCRATCH_QUAT = new Quaternion();
const SCRATCH_SCALE = new Vector3(1, 1, 1);

/**
 * Manages decoded OCP B-rep meshes, crisp Retina `LineSegments2` feature edges,
 * clipping planes, exploded assembly offsets, kinematic link transforms, and B-rep face picking.
 */
export class CadSceneManager {
  /**
   * Create a `CadSceneManager`.
   *
   * @param {object} options - Scene manager options.
   * @param {import("../static/vendor/three/three.module.js").Scene} options.scene - Target Three.js scene.
   * @param {number} [options.dpr] - Initial physical device pixel ratio.
   */
  constructor({ scene, dpr = 2.0 }) {
    /** @type {import("../static/vendor/three/three.module.js").Scene} */
    this.scene = scene;
    /** @type {number} */
    this.dpr = dpr;

    /** @type {Group} */
    this.rootGroup = new Group();
    this.rootGroup.name = "scope_cad_root";
    this.scene.add(this.rootGroup);

    /** @type {Array<Plane>} */
    this.clipPlanes = [
      new Plane(new Vector3(-1, 0, 0), Infinity),
      new Plane(new Vector3(0, -1, 0), Infinity),
      new Plane(new Vector3(0, 0, -1), Infinity),
    ];
    /** @type {[boolean, boolean, boolean]} */
    this.clipEnabled = [false, false, false];

    /** @type {Map<string, object>} */
    this.leafRecords = new Map();
    /** @type {Map<string, Array<object>>} */
    this.linkRecordsByName = new Map();
    /** @type {Array<LineMaterial>} */
    this._lineMaterials = [];
    /** @type {Array<BufferGeometry|LineSegmentsGeometry>} */
    this._disposableGeometries = [];
    /** @type {Array<MeshStandardMaterial|MeshBasicMaterial|LineMaterial>} */
    this._disposableMaterials = [];

    /** @type {boolean} */
    this.wireframe = false;
    /** @type {number} */
    this.explodeFactor = 0;
    /** @type {string} */
    this.mode = "CAD";
    /** @type {object|null} */
    this.decodedPayload = null;

    /** @type {Mesh|null} */
    this.faceHighlightMesh = null;
    /** @type {object|null} */
    this.selectedFaceInfo = null;
  }

  /**
   * Clear and dispose all active scene geometries, materials, and highlight overlays.
   */
  clear() {
    while (this.rootGroup.children.length > 0) {
      this.rootGroup.remove(this.rootGroup.children[0]);
    }
    this.clearFaceHighlight();

    for (const geom of this._disposableGeometries) {
      if (geom && typeof geom.dispose === "function") {
        geom.dispose();
      }
    }
    for (const mat of this._disposableMaterials) {
      if (mat && typeof mat.dispose === "function") {
        mat.dispose();
      }
    }

    this._disposableGeometries = [];
    this._disposableMaterials = [];
    this._lineMaterials = [];
    this.leafRecords.clear();
    this.linkRecordsByName.clear();
    this.decodedPayload = null;
    this.explodeFactor = 0;
  }

  /**
   * Populate the Three.js scene from a decoded `decodeOcpPayload` structure.
   *
   * @param {object} decoded - Output of `decodeOcpPayload(ctx, payload)`.
   * @param {{mode?: string}} [options] - Active Scope mode (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`).
   */
  loadDecodedPayload(decoded, { mode = "CAD" } = {}) {
    this.clear();
    this.decodedPayload = decoded;
    this.mode = String(mode || "CAD").toUpperCase();

    const activeClipPlanes = this._getActiveClipPlanes();
    const edgeCssWidth = this.mode === "DIAGRAM" ? DIAGRAM_EDGE_CSS_PX : BASE_EDGE_CSS_PX;
    const edgeHex = this.mode === "DIAGRAM" ? DEFAULT_EDGE_COLOR_DIAGRAM : DEFAULT_EDGE_COLOR_CAD;
    const physLineWidth = Math.max(1, Math.round(edgeCssWidth * this.dpr));

    // 1. Build shared BufferGeometry & LineSegmentsGeometry per unique instance
    const sharedMeshGeoms = new Map();
    const sharedEdgeGeoms = new Map();

    const getMeshGeometry = (instance) => {
      if (instance.index >= 0 && sharedMeshGeoms.has(instance.index)) {
        return sharedMeshGeoms.get(instance.index);
      }
      if (!instance.vertices || instance.vertices.length === 0) {
        return null;
      }
      const geom = new BufferGeometry();
      geom.setAttribute("position", new BufferAttribute(instance.vertices, 3));
      if (instance.normals && instance.normals.length === instance.vertices.length) {
        geom.setAttribute("normal", new BufferAttribute(instance.normals, 3));
      }
      if (instance.triangles && instance.triangles.length > 0) {
        geom.setIndex(new Uint32BufferAttribute(instance.triangles, 1));
      }
      if (!geom.attributes.normal) {
        geom.computeVertexNormals();
      }
      geom.computeBoundingBox();
      geom.computeBoundingSphere();
      this._disposableGeometries.push(geom);
      if (instance.index >= 0) {
        sharedMeshGeoms.set(instance.index, geom);
      }
      return geom;
    };

    const getEdgeGeometry = (instance) => {
      if (instance.index >= 0 && sharedEdgeGeoms.has(instance.index)) {
        return sharedEdgeGeoms.get(instance.index);
      }
      if (!instance.edges || instance.edges.length < 6) {
        return null;
      }
      const lineGeom = new LineSegmentsGeometry();
      lineGeom.setPositions(instance.edges);
      lineGeom.computeBoundingBox();
      lineGeom.computeBoundingSphere();
      this._disposableGeometries.push(lineGeom);
      if (instance.index >= 0) {
        sharedEdgeGeoms.set(instance.index, lineGeom);
      }
      return lineGeom;
    };

    const sharedEdgeMat = new LineMaterial({
      color: edgeHex,
      linewidth: physLineWidth,
      worldUnits: false,
      clippingPlanes: activeClipPlanes,
    });
    this._lineMaterials.push(sharedEdgeMat);
    this._disposableMaterials.push(sharedEdgeMat);

    // Count static identical `{ref, color, alpha, renderback}` leaves in DIAGRAM mode for InstancedMesh batching
    const batchBuckets = new Map();
    if (this.mode === "DIAGRAM") {
      for (const leaf of decoded.leaves) {
        if (leaf.ref >= 0 && leaf.edgesVisible === false) {
          const bKey = `${leaf.ref}|${leaf.color}|${leaf.alpha}|${leaf.renderback}`;
          let arr = batchBuckets.get(bKey);
          if (!arr) {
            arr = [];
            batchBuckets.set(bKey, arr);
          }
          arr.push(leaf);
        }
      }
    }

    const batchedLeafIds = new Set();
    for (const [, bucket] of batchBuckets.entries()) {
      if (bucket.length < MIN_INSTANCED_BATCH_COUNT) {
        continue;
      }
      const sample = bucket[0];
      const meshGeom = getMeshGeometry(sample.instance);
      if (!meshGeom) {
        continue;
      }
      const mat = this._createSurfaceMaterial(sample.color, sample.alpha, sample.renderback, activeClipPlanes);
      const instMesh = new InstancedMesh(meshGeom, mat, bucket.length);
      instMesh.name = `batched_${sample.name}`;
      bucket.forEach((leaf, idx) => {
        batchedLeafIds.add(leaf.id);
        SCRATCH_POS.set(leaf.location.translation[0], leaf.location.translation[1], leaf.location.translation[2]);
        SCRATCH_QUAT.set(
          leaf.location.quaternion[0],
          leaf.location.quaternion[1],
          leaf.location.quaternion[2],
          leaf.location.quaternion[3],
        );
        SCRATCH_MAT4.compose(SCRATCH_POS, SCRATCH_QUAT, SCRATCH_SCALE);
        instMesh.setMatrixAt(idx, SCRATCH_MAT4);
      });
      instMesh.instanceMatrix.needsUpdate = true;
      this.rootGroup.add(instMesh);
    }

    const assemblyCenter = decoded.worldBounds ? decoded.worldBounds.center : [0, 0, 0];

    for (const leaf of decoded.leaves) {
      if (batchedLeafIds.has(leaf.id)) {
        continue;
      }
      const group = new Group();
      group.name = leaf.name;
      group.visible = leaf.visible;
      group.position.set(
        leaf.location.translation[0],
        leaf.location.translation[1],
        leaf.location.translation[2],
      );
      group.quaternion.set(
        leaf.location.quaternion[0],
        leaf.location.quaternion[1],
        leaf.location.quaternion[2],
        leaf.location.quaternion[3],
      );

      let mesh = null;
      const meshGeom = getMeshGeometry(leaf.instance);
      if (meshGeom) {
        const mat = this._createSurfaceMaterial(leaf.color, leaf.alpha, leaf.renderback, activeClipPlanes);
        mesh = new Mesh(meshGeom, mat);
        mesh.name = `${leaf.name}_mesh`;
        if (leaf.alpha < 0.999) {
          mesh.renderOrder = 2;
        }
        group.add(mesh);
      }

      let edgeLines = null;
      const edgeGeom = getEdgeGeometry(leaf.instance);
      if (edgeGeom) {
        // Diagram black text glyph interiors don't need thick dark outlines on top of tiny strokes
        const isLabelGlyph = leaf.name.toLowerCase().includes("label");
        if (!isLabelGlyph) {
          edgeLines = new LineSegments2(edgeGeom, sharedEdgeMat);
          edgeLines.name = `${leaf.name}_edges`;
          edgeLines.visible = leaf.edgesVisible;
          edgeLines.renderOrder = 1;
          group.add(edgeLines);
        }
      }

      this.rootGroup.add(group);

      const leafCenter = leaf.worldBounds ? leaf.worldBounds.center : leaf.location.translation;
      const explodeVec = [
        leafCenter[0] - assemblyCenter[0],
        leafCenter[1] - assemblyCenter[1],
        leafCenter[2] - assemblyCenter[2],
      ];

      const worldBox = leaf.worldBounds
        ? new Box3(
            new Vector3(leaf.worldBounds.min[0], leaf.worldBounds.min[1], leaf.worldBounds.min[2]),
            new Vector3(leaf.worldBounds.max[0], leaf.worldBounds.max[1], leaf.worldBounds.max[2]),
          )
        : null;

      const record = {
        id: leaf.id,
        name: leaf.name,
        linkKey: leaf.linkKey,
        leaf,
        group,
        mesh,
        edgeLines,
        restTranslation: [...leaf.location.translation],
        restQuaternion: [...leaf.location.quaternion],
        explodeVector: explodeVec,
        worldBox,
      };

      this.leafRecords.set(leaf.id, record);
      const linkList = this.linkRecordsByName.get(leaf.linkKey) || [];
      linkList.push(record);
      this.linkRecordsByName.set(leaf.linkKey, linkList);
    }
  }

  /**
   * Create a CAD surface material (`MeshBasicMaterial` for flat 2D diagrams, `MeshStandardMaterial` for 3D).
   *
   * @param {string} hexColor - CSS hex color.
   * @param {number} alpha - Opacity `[0..1]`.
   * @param {boolean} renderback - Whether backfaces should be shaded.
   * @param {Array<Plane>} clippingPlanes - Active Three.js clip planes.
   * @returns {MeshStandardMaterial|MeshBasicMaterial}
   */
  _createSurfaceMaterial(hexColor, alpha, renderback, clippingPlanes) {
    const isTransparent = alpha < 0.995;
    const side = renderback || isTransparent || this.mode === "DIAGRAM" ? DoubleSide : FrontSide;

    let mat;
    if (this.mode === "DIAGRAM") {
      mat = new MeshBasicMaterial({
        color: new Color(hexColor || "#1e293b"),
        opacity: alpha,
        transparent: isTransparent,
        side,
        polygonOffset: true,
        polygonOffsetFactor: 1.0,
        polygonOffsetUnits: 1.0,
        wireframe: this.wireframe,
      });
    } else {
      mat = new MeshStandardMaterial({
        color: new Color(hexColor || "#8a99ad"),
        roughness: this.mode === "PCB" ? DEFAULT_PCB_SUBSTRATE_ROUGHNESS : DEFAULT_CAD_ROUGHNESS,
        metalness: this.mode === "PCB" ? DEFAULT_PCB_SUBSTRATE_METALNESS : DEFAULT_CAD_METALNESS,
        opacity: alpha,
        transparent: isTransparent,
        depthWrite: !isTransparent || alpha >= 0.85,
        side,
        polygonOffset: true,
        polygonOffsetFactor: 1.0,
        polygonOffsetUnits: 1.0,
        wireframe: this.wireframe,
        clippingPlanes,
      });
    }
    this._disposableMaterials.push(mat);
    return mat;
  }

  /**
   * Update physical pixel ratio so `LineSegments2` edges snap to crisp Retina pixel widths.
   *
   * @param {number} dpr - Physical device pixel ratio.
   */
  setDevicePixelRatio(dpr) {
    this.dpr = Math.max(1, dpr);
    const edgeCssWidth = this.mode === "DIAGRAM" ? DIAGRAM_EDGE_CSS_PX : BASE_EDGE_CSS_PX;
    const physWidth = Math.max(1, Math.round(edgeCssWidth * this.dpr));
    for (const lineMat of this._lineMaterials) {
      lineMat.linewidth = physWidth;
    }
  }

  /**
   * Toggle global wireframe rendering (`Z` shortcut).
   *
   * @param {boolean} [forceState] - Optional explicit wireframe boolean.
   * @returns {boolean} Active wireframe flag.
   */
  setWireframe(forceState) {
    this.wireframe = typeof forceState === "boolean" ? forceState : !this.wireframe;
    for (const mat of this._disposableMaterials) {
      if ("wireframe" in mat && !(mat instanceof LineMaterial)) {
        mat.wireframe = this.wireframe;
      }
    }
    return this.wireframe;
  }

  /**
   * Set assembly radial explode factor in `[0..1]`.
   *
   * @param {number} normalizedFactor - Explode factor `0.0` (assembled) to `1.0` (fully exploded).
   */
  setExplode(normalizedFactor) {
    const clamped = Math.max(0, Math.min(1, Number(normalizedFactor) || 0));
    this.explodeFactor = clamped;
    const scale = clamped * EXPLODE_RADIAL_MULTIPLIER;

    for (const record of this.leafRecords.values()) {
      const [rx, ry, rz] = record.restTranslation;
      const [ex, ey, ez] = record.explodeVector;
      record.group.position.set(rx + ex * scale, ry + ey * scale, rz + ez * scale);
      record.group.updateMatrixWorld(true);
      if (record.leaf.worldBounds) {
        const b = record.leaf.worldBounds;
        record.worldBox.min.set(b.min[0] + ex * scale, b.min[1] + ey * scale, b.min[2] + ez * scale);
        record.worldBox.max.set(b.max[0] + ex * scale, b.max[1] + ey * scale, b.max[2] + ez * scale);
      }
    }
  }

  /**
   * Set visibility for one or more `leafIds` from the CAD assembly tree.
   *
   * @param {Array<string>} leafIds - Target leaf node IDs.
   * @param {boolean} visible - Desired visibility.
   */
  setLeavesVisibility(leafIds, visible) {
    const flag = Boolean(visible);
    for (const id of leafIds) {
      const rec = this.leafRecords.get(id);
      if (rec) {
        rec.group.visible = flag;
      }
    }
  }

  /**
   * Apply per-frame simulation kinematic `Transform3D` poses (`/world/<linkName>`) to CAD link groups!
   *
   * @param {Record<string, {translation?: [number, number, number], quaternion?: [number, number, number, number]}>} transforms - Link pose map.
   */
  applyKinematicTransforms(transforms) {
    if (!transforms || typeof transforms !== "object") {
      return;
    }
    for (const [linkName, pose] of Object.entries(transforms)) {
      const records = this.linkRecordsByName.get(linkName);
      if (!records || records.length === 0) {
        continue;
      }
      for (const rec of records) {
        if (Array.isArray(pose.translation) && pose.translation.length >= 3) {
          rec.group.position.set(pose.translation[0], pose.translation[1], pose.translation[2]);
        }
        if (Array.isArray(pose.quaternion) && pose.quaternion.length >= 4) {
          rec.group.quaternion.set(
            pose.quaternion[0],
            pose.quaternion[1],
            pose.quaternion[2],
            pose.quaternion[3],
          );
        }
        rec.group.updateMatrixWorld(true);
      }
    }
  }

  /**
   * Reset all CAD link groups to their rest assembly poses.
   */
  resetKinematicTransforms() {
    for (const rec of this.leafRecords.values()) {
      rec.group.position.set(rec.restTranslation[0], rec.restTranslation[1], rec.restTranslation[2]);
      rec.group.quaternion.set(
        rec.restQuaternion[0],
        rec.restQuaternion[1],
        rec.restQuaternion[2],
        rec.restQuaternion[3],
      );
      rec.group.updateMatrixWorld(true);
    }
  }

  /**
   * Configure an axis-aligned section clipping plane (`0=X`, `1=Y`, `2=Z`).
   *
   * @param {0|1|2} axisIndex - Axis index (`0: X`, `1: Y`, `2: Z`).
   * @param {boolean} enabled - Whether clipping is active on this axis.
   * @param {number} [constantMm] - Signed plane offset in mm.
   */
  setClipPlane(axisIndex, enabled, constantMm = 0) {
    if (axisIndex < 0 || axisIndex > 2) {
      return;
    }
    this.clipEnabled[axisIndex] = Boolean(enabled);
    this.clipPlanes[axisIndex].constant = Number.isFinite(constantMm) ? constantMm : 0;
    const active = this._getActiveClipPlanes();
    for (const mat of this._disposableMaterials) {
      mat.clippingPlanes = active;
      mat.needsUpdate = true;
    }
  }

  /**
   * Return array of currently enabled `THREE.Plane` section planes.
   *
   * @returns {Array<Plane>}
   */
  _getActiveClipPlanes() {
    const active = [];
    for (let idx = 0; idx < 3; idx += 1) {
      if (this.clipEnabled[idx]) {
        active.push(this.clipPlanes[idx]);
      }
    }
    return active;
  }

  /**
   * Raycast visible CAD parts using fast world-AABB pre-filtering, resolving the exact
   * topological B-rep face (`Plane`, `Cylinder`, `Cone`, `Sphere`, `Torus`) and surface metrics!
   *
   * @param {import("../static/vendor/three/three.module.js").Camera} camera - Active camera.
   * @param {number} ndcX - Normalized device X in `[-1, 1]`.
   * @param {number} ndcY - Normalized device Y in `[-1, 1]`.
   * @returns {object|null} Hit descriptor `{ leafId, partName, point, distance, face, measurement }` or `null`.
   */
  pickBrepFace(camera, ndcX, ndcY) {
    SCRATCH_NDC.set(ndcX, ndcY);
    SCRATCH_RAYCASTER.setFromCamera(SCRATCH_NDC, camera);

    const candidateRecords = [];
    for (const rec of this.leafRecords.values()) {
      if (!rec.group.visible || !rec.mesh) {
        continue;
      }
      if (rec.worldBox && !SCRATCH_RAYCASTER.ray.intersectsBox(rec.worldBox)) {
        continue;
      }
      candidateRecords.push(rec);
    }

    if (candidateRecords.length === 0) {
      return null;
    }

    let closestHit = null;
    let closestRecord = null;

    for (const rec of candidateRecords) {
      const hits = SCRATCH_RAYCASTER.intersectObject(rec.mesh, false);
      if (hits.length > 0 && (!closestHit || hits[0].distance < closestHit.distance)) {
        closestHit = hits[0];
        closestRecord = rec;
      }
    }

    if (!closestHit || !closestRecord) {
      return null;
    }

    const triIndex = typeof closestHit.faceIndex === "number" ? closestHit.faceIndex : -1;
    const face = lookupBrepFace(closestRecord.leaf.instance, triIndex);
    const currentLoc = {
      translation: [
        closestRecord.group.position.x,
        closestRecord.group.position.y,
        closestRecord.group.position.z,
      ],
      quaternion: [
        closestRecord.group.quaternion.x,
        closestRecord.group.quaternion.y,
        closestRecord.group.quaternion.z,
        closestRecord.group.quaternion.w,
      ],
    };
    const measurement = face
      ? measureBrepFace(closestRecord.leaf.instance, face.faceIndex, currentLoc)
      : null;

    return {
      leafId: closestRecord.id,
      partName: closestRecord.name,
      color: closestRecord.leaf.color,
      point: [closestHit.point.x, closestHit.point.y, closestHit.point.z],
      distance: closestHit.distance,
      triangleIndex: triIndex,
      face,
      measurement,
      record: closestRecord,
    };
  }

  /**
   * Highlight a picked B-rep face by extracting its exact `[startTriangle .. endTriangle)` sub-mesh.
   *
   * @param {object|null} hit - Output of `pickBrepFace()`, or `null` to clear.
   */
  highlightBrepFace(hit) {
    this.clearFaceHighlight();
    if (!hit || !hit.face || !hit.record) {
      return;
    }

    const { instance } = hit.record.leaf;
    const { startTriangle, endTriangle } = hit.face;
    const triCount = endTriangle - startTriangle;
    if (triCount <= 0 || !instance.triangles || !instance.vertices) {
      return;
    }

    const subIndices = instance.triangles.slice(
      startTriangle * INDICES_PER_TRIANGLE,
      endTriangle * INDICES_PER_TRIANGLE,
    );
    const hlGeom = new BufferGeometry();
    hlGeom.setAttribute("position", new BufferAttribute(instance.vertices, 3));
    hlGeom.setIndex(new Uint32BufferAttribute(subIndices, 1));

    const hlMat = new MeshBasicMaterial({
      color: HIGHLIGHT_FACE_COLOR_HEX,
      transparent: true,
      opacity: 0.42,
      side: DoubleSide,
      depthTest: true,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2.0,
      polygonOffsetUnits: -2.0,
    });

    this.faceHighlightMesh = new Mesh(hlGeom, hlMat);
    this.faceHighlightMesh.name = "scope_brep_face_highlight";
    this.faceHighlightMesh.renderOrder = 8;
    hit.record.group.add(this.faceHighlightMesh);
    this.selectedFaceInfo = hit;
  }

  /**
   * Remove and dispose any active B-rep face highlight overlay mesh.
   */
  clearFaceHighlight() {
    if (this.faceHighlightMesh) {
      if (this.faceHighlightMesh.parent) {
        this.faceHighlightMesh.parent.remove(this.faceHighlightMesh);
      }
      this.faceHighlightMesh.geometry.dispose();
      this.faceHighlightMesh.material.dispose();
      this.faceHighlightMesh = null;
    }
    this.selectedFaceInfo = null;
  }
}
