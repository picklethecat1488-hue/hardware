/**
 * Scope Workstation Sidebar Panels, Rich Inspector, Sparkline Metrics, & Modal Controllers.
 *
 * Manages all DOM panels in the Scope Workstation with zero global access:
 * 1. Mode-scoped sidebar tabs (`PCB Layers`, `Tree`, `View`, `Metrics`, `Inspect`, `Pins`)
 *    and mode-scoped keyboard/mouse shortcut HUD rows (`BUG-EMERALD-TICK-950`).
 * 2. Hierarchical CAD Scene Tree (`#cad-tree-list`) with subtree visibility toggles.
 * 3. PCB Layer stackup controls (`Solo`, `All On`, `Flip 2D`) + fuzzy-searchable Nets list.
 * 4. Rich Engineering Inspector (`#inspect-content`) for B-rep faces (`Plane`, `Cylinder`,
 *    `Sphere`, `Cone`, `Torus` area/diameter/normal/centroid) and PCB entities (`pad`,
 *    `test_point`, `via`, `trace`, `component`, plus `Open in KiCad`).
 * 5. Simulation Rerun Metrics panel (`#metrics-list`) with crisp Retina Canvas2D sparklines
 *    and live step cursor + `[Voxels | Spheres]` fluid primitive toggle.
 * 6. Project & Target Chooser modal (`#modal-project-chooser`) and Target Bug modal (`#modal-bug`).
 */

import { fuzzyFilterAndRank } from "../core/fuzzy_search.js";
import { escapeHtml } from "../core/sanitize.js";
import { copyToClipboard, showToast } from "../core/toast.js";

const SPARKLINE_CSS_HEIGHT_PX = 42;
const SPARKLINE_MIN_CSS_WIDTH_PX = 240;
const MILS_PER_MM = 39.37007874;
const AUTO_COLLAPSE_CHILD_THRESHOLD = 16;

const DEFAULT_PCB_LAYERS = Object.freeze([
  { id: "edge_cuts", label: "Edge.Cuts (Outline)", color: "#e6d84c", type: "Edge.Cuts", default_visible: true },
  { id: "traces_fcu", label: "Top Copper (F.Cu)", color: "#c83434", type: "F.Cu", default_visible: true },
  { id: "traces_bcu", label: "Bottom Copper (B.Cu)", color: "#4d7fc4", type: "B.Cu", default_visible: true },
  { id: "pads", label: "Copper Pads", color: "#ce4785", type: "Pads", default_visible: true },
  { id: "vias", label: "Plated Vias", color: "#ececec", type: "Vias", default_visible: true },
  { id: "silkscreen_f", label: "Top Silkscreen (F.SilkS)", color: "#f2eda1", type: "F.SilkS", default_visible: true },
  { id: "silkscreen_b", label: "Bottom Silkscreen (B.SilkS)", color: "#e8b2a7", type: "B.SilkS", default_visible: true },
  { id: "substrate", label: "Board Substrate", color: "#041830", type: "Substrate", default_visible: true },
]);

/**
 * Format a numeric value cleanly with `digits` decimal places.
 *
 * @param {number} val - Numeric input.
 * @param {number} [digits] - Decimal places.
 * @returns {string}
 */
function fmtNum(val, digits = 3) {
  const num = Number(val);
  return Number.isFinite(num) ? num.toFixed(digits) : "0.000";
}

/**
 * Controller for Scope Workstation sidebar tabs, inspector, sparkline metrics, and modals.
 */
export class ScopeInspectorController {
  /**
   * Create a `ScopeInspectorController`.
   *
   * @param {object} options - Initialization parameters.
   * @param {object} options.ctx - Explicit `RuntimeContext`.
   * @param {import("./viewport.js").ScopeViewport} options.viewport - Scope viewport.
   * @param {import("./camera_controller.js").CadCameraController} options.cameraController - Camera controller.
   * @param {import("./cad_scene.js").CadSceneManager} options.cadScene - CAD scene manager.
   * @param {import("./pcb_renderer.js").PcbGpuRenderer} options.pcbRenderer - PCB GPU renderer.
   * @param {import("./sim_renderer.js").SimulationVoxelRenderer} options.simRenderer - Simulation voxel renderer.
   * @param {import("./markup_tool.js").MarkupAndPinController} options.markupController - Markup & pin controller.
   * @param {function(object): Promise<void>} options.onSelectTarget - Callback `{project, target, subassembly, mode, maxSteps}`.
   */
  constructor({
    ctx,
    viewport,
    cameraController,
    cadScene,
    pcbRenderer,
    simRenderer,
    markupController,
    onSelectTarget,
  }) {
    /** @type {object} */
    this.ctx = ctx;
    /** @type {import("./viewport.js").ScopeViewport} */
    this.viewport = viewport;
    /** @type {import("./camera_controller.js").CadCameraController} */
    this.cameraController = cameraController;
    /** @type {import("./cad_scene.js").CadSceneManager} */
    this.cadScene = cadScene;
    /** @type {import("./pcb_renderer.js").PcbGpuRenderer} */
    this.pcbRenderer = pcbRenderer;
    /** @type {import("./sim_renderer.js").SimulationVoxelRenderer} */
    this.simRenderer = simRenderer;
    /** @type {import("./markup_tool.js").MarkupAndPinController} */
    this.markupController = markupController;
    /** @type {function(object): Promise<void>} */
    this.onSelectTarget = onSelectTarget;

    /** @type {Array<object>} */
    this.projects = [];
    /** @type {string} */
    this.currentProject = "";
    /** @type {string} */
    this.currentTarget = "";
    /** @type {string} */
    this.currentSub = "";
    /** @type {string} */
    this.currentMode = "CAD";
    /** @type {number} */
    this.maxSteps = 1000;

    /** @type {Array<{name: string, count: number}>} */
    this._allNets = [];
    /** @type {string|null} */
    this._soloLayerType = null;
    /** @type {Array<object>} */
    this._cadTreeRooms = [];
    /** @type {Set<string>} */
    this._collapsedTreeNodeIds = new Set();
    /** @type {Map<string, boolean>} */
    this._treeVisibilityById = new Map();
    /** @type {string} */
    this._cadTreeQuery = "";
    /** @type {Array<{key: string, values: Array<number>, min: number, max: number, last: number}>} */
    this._metricSeries = [];
    /** @type {Map<string, HTMLCanvasElement>} */
    this._metricCanvases = new Map();
    /** @type {string} */
    this._lastBugSnapshotDataUrl = "";

    this._bindDomListeners();
  }

  /**
   * Look up a DOM element by ID via `RuntimeContext`.
   *
   * @param {string} id - Element ID.
   * @returns {HTMLElement|null}
   */
  _el(id) {
    const doc = this.ctx.getDocument();
    return doc ? doc.getElementById(id) : null;
  }

  /**
   * Bind delegated sidebar, chooser modal, and bug report modal event listeners.
   */
  _bindDomListeners() {
    const doc = this.ctx.getDocument();
    if (!doc) {
      return;
    }

    // Sidebar tab buttons
    const tabButtons = doc.querySelectorAll(".sidebar-tab");
    for (const btn of tabButtons) {
      btn.addEventListener("click", () => {
        const paneId = btn.getAttribute("data-pane");
        if (paneId) {
          this.activateTab(paneId);
        }
      });
    }

    // CAD Tree search & expand/collapse room controls
    const cadTreeSearch = this._el("cad-tree-search");
    const btnCadTreeClear = this._el("btn-cad-tree-clear-search");
    if (cadTreeSearch) {
      cadTreeSearch.addEventListener("input", () => {
        this._cadTreeQuery = cadTreeSearch.value || "";
        if (btnCadTreeClear) {
          btnCadTreeClear.style.display = this._cadTreeQuery.trim() ? "inline-flex" : "none";
        }
        this._refreshCadTreeDom();
      });
    }
    if (btnCadTreeClear && cadTreeSearch) {
      btnCadTreeClear.addEventListener("click", () => {
        cadTreeSearch.value = "";
        this._cadTreeQuery = "";
        btnCadTreeClear.style.display = "none";
        this._refreshCadTreeDom();
      });
    }
    const btnCadExpandAll = this._el("btn-cad-tree-expand-all");
    if (btnCadExpandAll) {
      btnCadExpandAll.addEventListener("click", () => this.expandAllCadTree());
    }
    const btnCadCollapseAll = this._el("btn-cad-tree-collapse-all");
    if (btnCadCollapseAll) {
      btnCadCollapseAll.addEventListener("click", () => this.collapseAllCadTree());
    }

    // PCB layer buttons & net search
    const btnAllLayers = this._el("btn-all-layers");
    if (btnAllLayers) {
      btnAllLayers.addEventListener("click", () => {
        this._soloLayerType = null;
        this.pcbRenderer.enableAllLayers();
        this._syncSubstrateCadVisibility(true);
        this.renderPcbLayersList();
        this.viewport.requestRender();
      });
    }

    const btnFlipPcb = this._el("btn-flip-pcb");
    if (btnFlipPcb) {
      btnFlipPcb.addEventListener("click", () => {
        this.cameraController.setPreset("flip", { fit: false });
        this.viewport.requestRender();
      });
    }

    const netSearch = this._el("net-search");
    if (netSearch) {
      netSearch.addEventListener("input", () => {
        this.renderNetsList(netSearch.value);
      });
    }

    const btnClearNet = this._el("btn-clear-net-highlight");
    if (btnClearNet) {
      btnClearNet.addEventListener("click", () => {
        this.pcbRenderer.setHighlightedNet("");
        if (netSearch) {
          netSearch.value = "";
        }
        this.renderNetsList("");
        this.viewport.requestRender();
      });
    }

    // Open in KiCad button
    const btnOpenKicad = this._el("btn-open-kicad");
    if (btnOpenKicad) {
      btnOpenKicad.addEventListener("click", () => this.openInKicad());
    }

    // Simulation Metrics search & .rrd export / Rerun launch
    const metricsSearch = this._el("metrics-search");
    const btnMetricsClear = this._el("btn-metrics-clear-filter");
    if (metricsSearch) {
      metricsSearch.addEventListener("input", () => {
        if (btnMetricsClear) {
          btnMetricsClear.style.display = metricsSearch.value.trim() ? "inline-flex" : "none";
        }
        this.renderMetricsList(metricsSearch.value);
      });
    }
    if (btnMetricsClear && metricsSearch) {
      btnMetricsClear.addEventListener("click", () => {
        metricsSearch.value = "";
        btnMetricsClear.style.display = "none";
        this.renderMetricsList("");
      });
    }

    const btnSaveRrd = this._el("btn-save-rrd");
    if (btnSaveRrd) {
      btnSaveRrd.addEventListener("click", () => {
        if (!this.currentProject || !this.currentTarget) return;
        const url = `/api/scope/download_rrd?project=${encodeURIComponent(this.currentProject)}&target=${encodeURIComponent(this.currentTarget)}`;
        const link = this.ctx.createElement("a");
        link.href = url;
        link.download = `${this.currentProject}_${this.currentTarget}.rrd`;
        doc.body.appendChild(link);
        link.click();
        link.remove();
      });
    }

    const btnOpenRerun = this._el("btn-open-rerun");
    if (btnOpenRerun) {
      btnOpenRerun.addEventListener("click", () => this.openInRerunViewer());
    }

    // Project & Target Chooser Modal
    const btnOpenChooser = this._el("btn-open-chooser");
    if (btnOpenChooser) {
      btnOpenChooser.addEventListener("click", () => this.openProjectChooser());
    }
    for (const closeId of ["btn-close-chooser", "btn-chooser-cancel"]) {
      const el = this._el(closeId);
      if (el) {
        el.addEventListener("click", () => this.closeProjectChooser());
      }
    }
    const chooserProject = this._el("chooser-project");
    if (chooserProject) {
      chooserProject.addEventListener("change", () => this._populateChooserTargets());
    }
    const chooserTarget = this._el("chooser-target");
    if (chooserTarget) {
      chooserTarget.addEventListener("change", () => this._populateChooserSubsAndModes());
    }
    const chooserPills = doc.querySelectorAll("#chooser-mode-pills .mode-pill");
    for (const pill of chooserPills) {
      pill.addEventListener("click", () => {
        if (pill.disabled || pill.classList.contains("disabled")) return;
        for (const p of chooserPills) p.classList.remove("active");
        pill.classList.add("active");
        const simStepsBox = this._el("chooser-sim-steps-container");
        if (simStepsBox) {
          simStepsBox.style.display = pill.getAttribute("data-mode") === "SIMULATE" ? "flex" : "none";
        }
      });
    }
    const btnChooserSubmit = this._el("btn-chooser-submit");
    if (btnChooserSubmit) {
      btnChooserSubmit.addEventListener("click", () => this._submitChooserSelection());
    }

    // Target Bug Modal
    const btnTargetBug = this._el("btn-target-bug");
    if (btnTargetBug) {
      btnTargetBug.addEventListener("click", () => this.openTargetBugModal());
    }
    for (const closeId of ["btn-close-bug", "btn-cancel-bug"]) {
      const el = this._el(closeId);
      if (el) {
        el.addEventListener("click", () => this.closeTargetBugModal());
      }
    }
    const btnSubmitBug = this._el("btn-submit-bug");
    if (btnSubmitBug) {
      btnSubmitBug.addEventListener("click", () => this.submitTargetBug());
    }
  }

  /**
   * Activate a sidebar pane by ID (`tab-layers`, `tab-tree`, `tab-display`, `tab-metrics`, `tab-inspect`, `tab-pins`).
   *
   * @param {string} paneId - Target pane DOM ID.
   */
  activateTab(paneId) {
    const doc = this.ctx.getDocument();
    if (!doc) return;
    for (const btn of doc.querySelectorAll(".sidebar-tab")) {
      btn.classList.toggle("active", btn.getAttribute("data-pane") === paneId);
    }
    for (const pane of doc.querySelectorAll(".tab-pane")) {
      pane.classList.toggle("active", pane.id === paneId);
    }
  }

  /**
   * Synchronize `body.mode-*`, mode pills, sidebar tab visibility, and Shortcuts HUD text for `mode`.
   *
   * @param {string} mode - Active Scope mode (`CAD`, `PCB`, `SIMULATE`, `DIAGRAM`).
   * @param {{project?: string, target?: string, subassembly?: string}} [targetInfo] - Active target metadata.
   */
  applyModeUiState(mode, targetInfo = {}) {
    const upper = String(mode || "CAD").toUpperCase();
    this.currentMode = upper;
    if (targetInfo.project !== undefined) this.currentProject = targetInfo.project;
    if (targetInfo.target !== undefined) this.currentTarget = targetInfo.target;
    if (targetInfo.subassembly !== undefined) this.currentSub = targetInfo.subassembly;

    const doc = this.ctx.getDocument();
    if (!doc || !doc.body) return;

    doc.body.classList.remove("mode-cad", "mode-pcb", "mode-simulate", "mode-diagram");
    doc.body.classList.add(`mode-${upper.toLowerCase()}`);

    // Top HUD Target label
    const activeTargetLabel = this._el("hud-active-target");
    if (activeTargetLabel) {
      if (this.currentProject && this.currentTarget) {
        const subSuffix = this.currentSub ? ` [${this.currentSub}]` : "";
        activeTargetLabel.textContent = `${this.currentProject}/${this.currentTarget}${subSuffix}`;
      } else {
        activeTargetLabel.textContent = "(Select Target)";
      }
    }

    // Top HUD Mode pills (enable/disable supported modes for active target)
    const supportedModes = this._getSupportedModesForActiveTarget();
    const topPills = doc.querySelectorAll("#top-hud .mode-pill");
    for (const pill of topPills) {
      const m = pill.getAttribute("data-mode");
      const allowed = supportedModes.length === 0 || supportedModes.includes(m);
      pill.disabled = !allowed;
      pill.classList.toggle("disabled", !allowed);
      pill.classList.toggle("active", m === upper);
    }

    // Sidebar tab visibility
    const tabLayers = this._el("tab-btn-layers");
    const tabTree = this._el("tab-btn-tree");
    const tabMetrics = this._el("tab-btn-metrics");
    if (tabLayers) tabLayers.style.display = upper === "PCB" ? "block" : "none";
    if (tabTree) tabTree.style.display = upper === "PCB" ? "none" : "block";
    if (tabMetrics) tabMetrics.style.display = upper === "SIMULATE" ? "block" : "none";

    const btnOpenKicad = this._el("btn-open-kicad");
    if (btnOpenKicad) {
      btnOpenKicad.style.display = upper === "PCB" ? "inline-flex" : "none";
    }

    const simBar = this._el("sim-bar");
    if (simBar) {
      simBar.classList.toggle("visible", upper === "SIMULATE");
    }

    const innerLayerBtns = this._el("pcb-inner-layer-btns");
    if (innerLayerBtns && upper !== "PCB") {
      innerLayerBtns.style.display = "none";
    }

    if (upper === "PCB") {
      this.activateTab("tab-layers");
    } else if (upper === "SIMULATE") {
      this.activateTab("tab-metrics");
    } else {
      this.activateTab("tab-tree");
    }

    // Update Shortcuts HUD dynamic cells (`BUG-EMERALD-TICK-950`)
    this._syncShortcutsHudForMode(upper);
  }

  /**
   * Update Shortcuts HUD header and dynamic shortcut cells for `upperMode`.
   *
   * @param {string} upperMode - Uppercase mode string.
   */
  _syncShortcutsHudForMode(upperMode) {
    const titleEl = this._el("shortcuts-hud-title");
    const colHeader = this._el("shortcuts-col-header");
    const cellPan = this._el("hud-cell-pan");
    const cellZoom = this._el("hud-cell-zoom");
    const labelTop = this._el("hud-label-top");
    const cellTop = this._el("hud-cell-top");
    const cellFocus = this._el("hud-cell-focus");

    const is2D = upperMode === "PCB" || upperMode === "DIAGRAM";

    if (titleEl) {
      if (upperMode === "PCB") titleEl.textContent = "◈ PCB 2D CONTROLS & SHORTCUTS ◈";
      else if (upperMode === "DIAGRAM") titleEl.textContent = "◈ DIAGRAM 2D CONTROLS & SHORTCUTS ◈";
      else if (upperMode === "SIMULATE") titleEl.textContent = "◈ SIMULATION CONTROLS & SHORTCUTS ◈";
      else titleEl.textContent = "◈ KEYBOARD & MOUSE CONTROLS ◈";
    }
    if (colHeader) {
      if (upperMode === "PCB") colHeader.textContent = "Shortcut (2D PCB)";
      else if (upperMode === "DIAGRAM") colHeader.textContent = "Shortcut (2D Diagram)";
      else colHeader.textContent = "Shortcut (3D Viewport)";
    }
    if (cellPan) {
      cellPan.innerHTML = is2D
        ? '<span class="kbd-badge">LMB Drag</span> or <span class="kbd-badge">RMB Drag</span>'
        : '<span class="kbd-badge">RMB Drag</span> or <span class="kbd-badge">Shift + MMB</span>';
    }
    if (cellZoom) {
      cellZoom.innerHTML = is2D
        ? '<span class="kbd-badge">Scroll Wheel</span>, <span class="kbd-badge">MMB Drag</span>, or <span class="kbd-badge">+</span> / <span class="kbd-badge">-</span>'
        : '<span class="kbd-badge">Scroll Wheel</span> or <span class="kbd-badge">+</span> / <span class="kbd-badge">-</span>';
    }
    if (labelTop) {
      labelTop.textContent = upperMode === "PCB" ? "Top (F.Cu) / Bottom (B.Cu)" : "Top / Bottom View";
    }
    if (cellTop) {
      cellTop.innerHTML = upperMode === "PCB"
        ? '<span class="kbd-badge">7</span> (Top) / <span class="kbd-badge">1</span> (Bottom)'
        : '<span class="kbd-badge">7</span> / <span class="kbd-badge">Ctrl + 7</span>';
    }
    if (cellFocus) {
      cellFocus.innerHTML = upperMode === "PCB"
        ? '<span class="kbd-badge">.</span> or <span class="kbd-badge">Home</span>'
        : '<span class="kbd-badge">F</span>, <span class="kbd-badge">.</span>, or <span class="kbd-badge">Home</span>';
    }
  }

  /**
   * Look up supported modes for `(currentProject, currentTarget)`.
   *
   * @returns {Array<string>}
   */
  _getSupportedModesForActiveTarget() {
    const proj = this.projects.find((p) => p.name === this.currentProject);
    if (!proj || !Array.isArray(proj.targets)) return [];
    const tgt = proj.targets.find((t) => t.name === this.currentTarget);
    return tgt && Array.isArray(tgt.modes) ? tgt.modes.map((m) => String(m).toUpperCase()) : [];
  }

  /**
   * Organize decoded `treeNodes` into collapsible CAD Room root nodes (`room/part` or active target room).
   *
   * @param {Array<object>} treeNodes - Decoded `treeEntry` array.
   * @returns {Array<object>}
   */
  _buildCadTreeRooms(treeNodes) {
    if (!Array.isArray(treeNodes) || treeNodes.length === 0) {
      return [];
    }

    // Group slash-delimited multi-room entries (`room_a/part_1`) into explicit CAD room nodes
    const hasSlashRooms = treeNodes.some((n) => typeof n.name === "string" && n.name.includes("/"));
    if (hasSlashRooms) {
      const roomMap = new Map();
      for (const node of treeNodes) {
        const rawName = String(node.name || "Part");
        const slashIdx = rawName.indexOf("/");
        const roomName = slashIdx > 0 ? rawName.slice(0, slashIdx) : (this.currentTarget || "Room");
        const subName = slashIdx > 0 ? rawName.slice(slashIdx + 1) : rawName;
        let roomEntry = roomMap.get(roomName);
        if (!roomEntry) {
          roomEntry = {
            id: `room:${roomName}`,
            name: roomName,
            isRoom: true,
            visible: true,
            color: null,
            leafIds: [],
            children: [],
          };
          roomMap.set(roomName, roomEntry);
        }
        const childClone = { ...node, name: subName };
        roomEntry.children.push(childClone);
        if (Array.isArray(node.leafIds)) {
          roomEntry.leafIds.push(...node.leafIds);
        }
        if (node.visible === false) {
          roomEntry.visible = roomEntry.children.some((c) => c.visible !== false);
        }
      }
      return Array.from(roomMap.values());
    }

    // Single room with a single root group that already has children -> mark as collapsible room directly
    if (treeNodes.length === 1 && Array.isArray(treeNodes[0].children) && treeNodes[0].children.length > 0) {
      return [{ ...treeNodes[0], isRoom: true }];
    }

    // Wrap multi-part target assembly into a collapsible CAD Room root node
    const defaultRoomLabel = this.currentSub || this.currentTarget || this.currentProject || "CAD Room";
    const allLeafIds = [];
    for (const node of treeNodes) {
      if (Array.isArray(node.leafIds)) {
        allLeafIds.push(...node.leafIds);
      }
    }
    return [
      {
        id: `room:${defaultRoomLabel}`,
        name: defaultRoomLabel,
        isRoom: true,
        visible: treeNodes.some((n) => n.visible !== false),
        color: null,
        leafIds: allLeafIds,
        children: treeNodes,
      },
    ];
  }

  /**
   * Collapse all CAD Room root nodes (and nested compound groups) in `#cad-tree-list`.
   */
  collapseAllCadTree() {
    const markCollapsed = (nodes) => {
      for (const node of nodes) {
        if (Array.isArray(node.children) && node.children.length > 0) {
          this._collapsedTreeNodeIds.add(String(node.id || node.name));
          markCollapsed(node.children);
        }
      }
    };
    markCollapsed(this._cadTreeRooms);
    this._refreshCadTreeDom();
  }

  /**
   * Expand all CAD Room root nodes and nested groups in `#cad-tree-list`.
   */
  expandAllCadTree() {
    this._collapsedTreeNodeIds.clear();
    this._refreshCadTreeDom();
  }

  /**
   * Render the hierarchical CAD object tree (`#cad-tree-list`) with collapsible CAD rooms
   * and shared fuzzy search (`fuzzyFilterAndRank`).
   *
   * @param {Array<object>} treeNodes - Array of `treeEntry` nodes from `decodeOcpPayload`.
   */
  renderCadTree(treeNodes) {
    this._cadTreeRooms = this._buildCadTreeRooms(treeNodes);
    this._collapsedTreeNodeIds.clear();
    this._treeVisibilityById.clear();
    this._cadTreeQuery = "";

    const searchInput = /** @type {HTMLInputElement|null} */ (this._el("cad-tree-search"));
    const clearBtn = this._el("btn-cad-tree-clear-search");
    if (searchInput) {
      searchInput.value = "";
    }
    if (clearBtn) {
      clearBtn.style.display = "none";
    }

    // Seed visibility map & auto-collapse dense sub-compounds (>16 primitives) while keeping CAD Rooms open
    const initTreeState = (nodes, depth) => {
      for (const node of nodes) {
        const key = String(node.id || node.name);
        this._treeVisibilityById.set(key, node.visible !== false);
        if (Array.isArray(node.children) && node.children.length > 0) {
          if (depth >= 1 && node.children.length > AUTO_COLLAPSE_CHILD_THRESHOLD) {
            this._collapsedTreeNodeIds.add(key);
          }
          initTreeState(node.children, depth + 1);
        }
      }
    };
    initTreeState(this._cadTreeRooms, 0);

    this._refreshCadTreeDom();
  }

  /**
   * Propagate checkbox visibility recursively across a CAD tree node and its descendants.
   *
   * @param {object} node - Target CAD tree node.
   * @param {boolean} visible - Desired visibility flag.
   */
  _setSubtreeCheckedState(node, visible) {
    const key = String(node.id || node.name);
    this._treeVisibilityById.set(key, visible);
    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        this._setSubtreeCheckedState(child, visible);
      }
    }
  }

  /**
   * Re-render `#cad-tree-list` according to `_collapsedTreeNodeIds` and `_cadTreeQuery`.
   */
  _refreshCadTreeDom() {
    const listEl = this._el("cad-tree-list");
    if (!listEl) return;
    listEl.innerHTML = "";
    if (!Array.isArray(this._cadTreeRooms) || this._cadTreeRooms.length === 0) return;

    const query = (this._cadTreeQuery || "").trim();

    const buildTreeRow = (node, depth, breadcrumb = "") => {
      const nodeKey = String(node.id || node.name);
      const children = Array.isArray(node.children) ? node.children : [];
      const hasChildren = children.length > 0;
      const isCollapsed = hasChildren && this._collapsedTreeNodeIds.has(nodeKey);
      const leafIds = Array.isArray(node.leafIds) ? node.leafIds : [];

      const row = this.ctx.createElement("div");
      row.className = `cad-tree-row${node.isRoom ? " cad-tree-room" : ""}`;
      row.style.cssText =
        `display:flex;align-items:center;gap:6px;padding:4px 6px 4px ${6 + depth * 12}px;` +
        "border-bottom:1px solid rgba(255,255,255,0.05);font-size:11px;" +
        (node.isRoom ? "background:rgba(255,184,0,0.06);font-weight:700;" : "");

      if (hasChildren && !query) {
        const toggleBtn = this.ctx.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "cad-tree-chevron";
        toggleBtn.textContent = isCollapsed ? "▸" : "▾";
        toggleBtn.title = isCollapsed ? `Expand ${node.name}` : `Collapse ${node.name}`;
        toggleBtn.style.cssText =
          "background:transparent;border:none;color:var(--quake-gold);cursor:pointer;" +
          "padding:0 2px;font-size:11px;line-height:1;width:14px;flex-shrink:0;";
        toggleBtn.addEventListener("click", (ev) => {
          if (ev && typeof ev.stopPropagation === "function") ev.stopPropagation();
          if (this._collapsedTreeNodeIds.has(nodeKey)) {
            this._collapsedTreeNodeIds.delete(nodeKey);
          } else {
            this._collapsedTreeNodeIds.add(nodeKey);
          }
          this._refreshCadTreeDom();
        });
        row.appendChild(toggleBtn);
      } else if (!query) {
        const spacer = this.ctx.createElement("span");
        spacer.style.cssText = "display:inline-block;width:14px;flex-shrink:0;";
        row.appendChild(spacer);
      }

      const cb = this.ctx.createElement("input");
      cb.type = "checkbox";
      cb.checked = this._treeVisibilityById.has(nodeKey)
        ? Boolean(this._treeVisibilityById.get(nodeKey))
        : node.visible !== false;
      cb.style.accentColor = "#ffb800";
      cb.addEventListener("change", () => {
        this._setSubtreeCheckedState(node, cb.checked);
        this.cadScene.setLeavesVisibility(leafIds, cb.checked);
        this._refreshCadTreeDom();
        this.viewport.requestRender();
      });
      row.appendChild(cb);

      if (node.color) {
        const swatch = this.ctx.createElement("span");
        swatch.style.cssText =
          `width:10px;height:10px;border-radius:2px;background:${node.color};` +
          "border:1px solid rgba(255,255,255,0.3);flex-shrink:0;";
        row.appendChild(swatch);
      }

      const label = this.ctx.createElement("span");
      label.textContent = node.name || "Assembly";
      label.style.cssText =
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;flex:1;";
      label.title = breadcrumb ? `${breadcrumb} / ${node.name}` : (node.id || node.name);
      label.addEventListener("click", () => {
        if (hasChildren && !query) {
          if (this._collapsedTreeNodeIds.has(nodeKey)) {
            this._collapsedTreeNodeIds.delete(nodeKey);
          } else {
            this._collapsedTreeNodeIds.add(nodeKey);
          }
          this._refreshCadTreeDom();
          return;
        }
        if (leafIds.length >= 1) {
          const rec = this.cadScene.leafRecords.get(leafIds[0]);
          if (rec && rec.leaf.worldBounds) {
            this.renderCadPartSummary(rec);
            this.activateTab("tab-inspect");
          }
        }
      });
      row.appendChild(label);

      if (breadcrumb) {
        const pathBadge = this.ctx.createElement("span");
        pathBadge.textContent = breadcrumb;
        pathBadge.style.cssText =
          "font-size:9px;color:var(--quake-text-muted);max-width:92px;overflow:hidden;" +
          "text-overflow:ellipsis;white-space:nowrap;flex-shrink:0;";
        row.appendChild(pathBadge);
      } else if (hasChildren) {
        const countBadge = this.ctx.createElement("span");
        countBadge.textContent = `${children.length}`;
        countBadge.style.cssText =
          "font-size:9px;padding:0 5px;border-radius:8px;background:rgba(255,255,255,0.08);" +
          "color:var(--quake-text-muted);flex-shrink:0;";
        row.appendChild(countBadge);
      }

      return row;
    };

    if (query) {
      const flatCandidates = [];
      const collectCandidates = (nodes, ancestors) => {
        for (const node of nodes) {
          const name = String(node.name || "");
          const breadcrumb = ancestors.join(" / ");
          const searchKey = breadcrumb ? `${name} ${breadcrumb}` : name;
          flatCandidates.push({ node, breadcrumb, searchKey });
          if (Array.isArray(node.children) && node.children.length > 0) {
            collectCandidates(node.children, [...ancestors, name]);
          }
        }
      };
      collectCandidates(this._cadTreeRooms, []);

      const ranked = fuzzyFilterAndRank(query, flatCandidates, (entry) => entry.searchKey);
      if (ranked.length === 0) {
        const empty = this.ctx.createElement("div");
        empty.style.cssText = "font-size:10px;color:var(--quake-text-muted);padding:6px 4px;";
        empty.textContent = "No matching CAD rooms or parts.";
        listEl.appendChild(empty);
        return;
      }

      for (const { item } of ranked) {
        listEl.appendChild(buildTreeRow(item.node, 0, item.breadcrumb));
      }
      return;
    }

    const appendRecursive = (node, depth) => {
      const nodeKey = String(node.id || node.name);
      listEl.appendChild(buildTreeRow(node, depth));
      if (Array.isArray(node.children) && node.children.length > 0 && !this._collapsedTreeNodeIds.has(nodeKey)) {
        for (const child of node.children) {
          appendRecursive(child, depth + 1);
        }
      }
    };

    for (const roomNode of this._cadTreeRooms) {
      appendRecursive(roomNode, 0);
    }
  }

  /**
   * Populate PCB Layers stackup & electrical Nets list from `pcbMetadata`.
   *
   * @param {object|null} pcbMetadata - Backend `pcb_metadata`.
   */
  populatePcbSidebar(pcbMetadata) {
    this._soloLayerType = null;
    this.renderPcbLayersList(pcbMetadata);

    // Aggregate pin/trace counts per electrical net
    const netCounts = new Map();
    if (pcbMetadata) {
      if (Array.isArray(pcbMetadata.nets)) {
        for (const n of pcbMetadata.nets) {
          const netName = typeof n === "string" ? n : n?.name;
          if (netName) netCounts.set(String(netName), 0);
        }
      }
      if (Array.isArray(pcbMetadata.pads)) {
        for (const p of pcbMetadata.pads) {
          if (p.net) netCounts.set(p.net, (netCounts.get(p.net) || 0) + 1);
        }
      }
      if (Array.isArray(pcbMetadata.test_points)) {
        for (const tp of pcbMetadata.test_points) {
          if (tp.net) netCounts.set(tp.net, (netCounts.get(tp.net) || 0) + 1);
        }
      }
    }

    this._allNets = Array.from(netCounts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name));

    const netSearch = this._el("net-search");
    if (netSearch) netSearch.value = "";
    this.renderNetsList("");
  }

  /**
   * Synchronize substrate B-rep solid visibility in `CadSceneManager` when `Substrate` layer toggles.
   *
   * @param {boolean} visible - Substrate visibility.
   */
  _syncSubstrateCadVisibility(visible) {
    if (this.currentMode !== "PCB") return;
    const allIds = Array.from(this.cadScene.leafRecords.keys());
    this.cadScene.setLeavesVisibility(allIds, visible);
  }

  /**
   * Solo a specific PCB layer (`In1.Cu`..`In4.Cu`, `F.Cu`, `B.Cu`, etc.) or toggle back to default surface layers.
   *
   * @param {string|null} layerType - Layer type to solo (`null` restores default surface stackup).
   * @param {object|null} [pcbMetadata] - Optional PCB metadata override.
   */
  toggleSoloPcbLayer(layerType, pcbMetadata = null) {
    const meta = pcbMetadata || this.pcbRenderer.metadata;
    const layers = meta && Array.isArray(meta.layers) && meta.layers.length > 0
      ? meta.layers
      : DEFAULT_PCB_LAYERS;

    if (!layerType || this._soloLayerType === layerType) {
      this._soloLayerType = null;
      this.pcbRenderer.resetDefaultLayers();
      this._syncSubstrateCadVisibility(true);
    } else {
      this._soloLayerType = layerType;
      const isCopperLayer = layerType.endsWith(".Cu");
      for (const l of layers) {
        const lt = l.type || l.id;
        const keepRef =
          lt === layerType
          || lt === "Substrate"
          || (lt === "Edge.Cuts" && layerType !== "Substrate")
          || (lt === "Vias" && isCopperLayer);
        this.pcbRenderer.setLayerVisibility(lt, keepRef);
        if (lt === "Substrate") {
          this._syncSubstrateCadVisibility(keepRef);
        }
      }
    }
    this.renderPcbLayersList(meta);
    this.viewport.requestRender();
  }

  /**
   * Render `#layers-list` checkboxes, `Solo` buttons, and `#pcb-inner-layer-btns` toolbar pills.
   *
   * @param {object|null} [pcbMetadata] - Optional metadata override.
   */
  renderPcbLayersList(pcbMetadata = null) {
    const listEl = this._el("layers-list");
    const meta = pcbMetadata || this.pcbRenderer.metadata;
    const layers = meta && Array.isArray(meta.layers) && meta.layers.length > 0
      ? meta.layers
      : DEFAULT_PCB_LAYERS;

    this._renderInnerLayerToolbarBtns(layers, meta);
    if (!listEl) return;
    listEl.innerHTML = "";

    for (const layer of layers) {
      const layerType = layer.type || layer.id;
      const isVisible = this.pcbRenderer.visibleLayers.has(layerType);

      const item = this.ctx.createElement("div");
      item.className = "layer-item";

      const info = this.ctx.createElement("label");
      info.className = "layer-info";
      info.style.cursor = "pointer";

      const cb = this.ctx.createElement("input");
      cb.type = "checkbox";
      cb.checked = isVisible;
      cb.style.accentColor = "#ffb800";
      cb.addEventListener("change", () => {
        this._soloLayerType = null;
        this.pcbRenderer.setLayerVisibility(layerType, cb.checked);
        if (layerType === "Substrate") {
          this._syncSubstrateCadVisibility(cb.checked);
        }
        this._renderInnerLayerToolbarBtns(layers, meta);
        this.viewport.requestRender();
      });

      const dot = this.ctx.createElement("span");
      dot.className = "layer-color-dot";
      dot.style.background = layer.color || "#888";

      const text = this.ctx.createElement("span");
      text.textContent = layer.label || layer.name || layerType;

      info.appendChild(cb);
      info.appendChild(dot);
      info.appendChild(text);

      const soloBtn = this.ctx.createElement("button");
      soloBtn.className = `layer-btn-solo${this._soloLayerType === layerType ? " active" : ""}`;
      soloBtn.textContent = "SOLO";
      soloBtn.addEventListener("click", () => {
        this.toggleSoloPcbLayer(layerType, meta);
      });

      item.appendChild(info);
      item.appendChild(soloBtn);
      listEl.appendChild(item);
    }
  }

  /**
   * Populate quick-select inner copper layer buttons (`In1`, `In2`, `In3`, `In4`) inside `#cam-toolbar`.
   *
   * @param {Array<object>} layers - PCB stackup layer descriptors.
   * @param {object|null} meta - PCB metadata.
   */
  _renderInnerLayerToolbarBtns(layers, meta) {
    const wrap = this._el("pcb-inner-layer-btns");
    if (!wrap) return;
    wrap.innerHTML = "";

    const innerLayers = layers.filter((l) => Boolean(l.is_inner) || /^In\d+\.Cu$/i.test(String(l.type || "")));
    if (this.currentMode !== "PCB" || innerLayers.length === 0) {
      wrap.style.display = "none";
      return;
    }

    wrap.style.display = "inline-flex";
    for (const layer of innerLayers) {
      const layerType = String(layer.type || layer.id);
      const shortLabel = layerType.replace(/\.Cu$/i, "");
      const btn = this.ctx.createElement("button");
      const isActive = this._soloLayerType === layerType || this.pcbRenderer.visibleLayers.has(layerType);
      btn.className = `cam-btn${isActive ? " active" : ""}`;
      btn.textContent = shortLabel;
      btn.title = `Inspect ${layer.label || layer.name || layerType} (click again to return to surface view)`;
      if (layer.color) {
        btn.style.borderBottom = `2px solid ${layer.color}`;
      }
      btn.addEventListener("click", () => {
        this.toggleSoloPcbLayer(layerType, meta);
      });
      wrap.appendChild(btn);
    }
  }

  /**
   * Render fuzzy-filtered `#nets-list` items.
   *
   * @param {string} query - Fuzzy search query.
   */
  renderNetsList(query = "") {
    const listEl = this._el("nets-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    const ranked = query.trim()
      ? fuzzyFilterAndRank(query, this._allNets, (item) => item.name)
      : this._allNets.map((item) => ({ item }));

    if (ranked.length === 0) {
      const empty = this.ctx.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--quake-text-muted);padding:6px 2px;";
      empty.textContent = "No matching nets.";
      listEl.appendChild(empty);
      return;
    }

    for (const { item } of ranked) {
      const row = this.ctx.createElement("div");
      const isSelected = this.pcbRenderer.highlightedNet === item.name;
      row.className = `net-item${isSelected ? " active" : ""}`;

      const nameSpan = this.ctx.createElement("span");
      nameSpan.textContent = item.name;

      const countSpan = this.ctx.createElement("span");
      countSpan.className = "net-pin-count";
      countSpan.textContent = `${item.count} pads`;

      row.appendChild(nameSpan);
      row.appendChild(countSpan);
      row.addEventListener("click", () => {
        const nextNet = this.pcbRenderer.highlightedNet === item.name ? "" : item.name;
        this.pcbRenderer.setHighlightedNet(nextNet);
        this.renderNetsList(query);
        this.viewport.requestRender();
      });
      listEl.appendChild(row);
    }
  }

  /**
   * Render B-rep CAD face inspection details into `#inspect-content`.
   *
   * @param {object|null} hit - Output of `cadScene.pickBrepFace()`.
   */
  renderBrepInspection(hit) {
    const el = this._el("inspect-content");
    if (!el) return;
    if (!hit) {
      el.innerHTML = "Click on any CAD surface or edge to inspect topological B-rep geometry.";
      return;
    }

    const [px, py, pz] = hit.point || [0, 0, 0];
    const coordStr = `(${fmtNum(px, 2)}, ${fmtNum(py, 2)}, ${fmtNum(pz, 2)}) mm`;
    const m = hit.measurement;
    const surfType = (hit.face && hit.face.surfaceType) || "Surface";

    const rows = [
      ["Part", escapeHtml(hit.partName || hit.leafId)],
      ["Surface Type", `<span style="color:var(--quake-gold);font-weight:700;">${escapeHtml(surfType)}</span>`],
      ["Hit Point", `<span id="inspect-copy-pt" style="color:var(--quake-cyan);cursor:pointer;text-decoration:underline;" title="Click to copy">${escapeHtml(coordStr)}</span>`],
    ];

    if (m) {
      rows.push(["Surface Area", `${fmtNum(m.areaMm2, 2)} mm²`]);
      if (typeof m.diameterMm === "number") {
        rows.push([
          "Diameter / Radius",
          `<span style="color:#4ade80;font-weight:700;">Ø ${fmtNum(m.diameterMm, 3)} mm</span> (R ${fmtNum(m.radiusMm, 3)} mm)`,
        ]);
      }
      if (Array.isArray(m.normal)) {
        rows.push([
          "Unit Normal",
          `(${fmtNum(m.normal[0], 3)}, ${fmtNum(m.normal[1], 3)}, ${fmtNum(m.normal[2], 3)})`,
        ]);
      }
      if (Array.isArray(m.centroid)) {
        rows.push([
          "Face Centroid",
          `(${fmtNum(m.centroid[0], 2)}, ${fmtNum(m.centroid[1], 2)}, ${fmtNum(m.centroid[2], 2)}) mm`,
        ]);
      }
    }

    el.innerHTML = this._formatKeyValueTable(rows);
    const copyEl = this._el("inspect-copy-pt");
    if (copyEl) {
      copyEl.addEventListener("click", () => {
        copyToClipboard(this.ctx, `${px.toFixed(3)}, ${py.toFixed(3)}, ${pz.toFixed(3)}`, "Copied 3D coordinates!");
      });
    }
  }

  /**
   * Render CAD tree leaf bounding-box summary when clicked from `#cad-tree-list`.
   *
   * @param {object} rec - Leaf record from `CadSceneManager`.
   */
  renderCadPartSummary(rec) {
    const el = this._el("inspect-content");
    if (!el || !rec) return;
    const b = rec.leaf.worldBounds;
    const rows = [
      ["Object", `<span style="color:var(--quake-gold);font-weight:700;">${escapeHtml(rec.name)}</span>`],
      ["Link Key", escapeHtml(rec.linkKey || rec.name)],
    ];
    if (b) {
      rows.push(["Size (X×Y×Z)", `${fmtNum(b.size[0], 2)} × ${fmtNum(b.size[1], 2)} × ${fmtNum(b.size[2], 2)} mm`]);
      rows.push(["Center", `(${fmtNum(b.center[0], 2)}, ${fmtNum(b.center[1], 2)}, ${fmtNum(b.center[2], 2)}) mm`]);
    }
    el.innerHTML = this._formatKeyValueTable(rows);
  }

  /**
   * Render PCB entity (`pad`, `test_point`, `via`, `trace`, `component`) details into `#inspect-content`.
   *
   * @param {object|null} entity - Hit entity from `PcbSpatialGrid`.
   */
  renderPcbInspection(entity) {
    const el = this._el("inspect-content");
    if (!el) return;
    if (!entity) {
      el.innerHTML = "Hover or click a copper pad, trace, via, or component to inspect electrical & physical details.";
      return;
    }

    const rows = [];
    if (entity.kind === "pad" || entity.kind === "test_point") {
      rows.push(["Entity", entity.kind === "test_point" ? "Test Point Pad" : "Component Pad"]);
      rows.push(["Component / Pin", `<span style="color:var(--quake-gold);font-weight:700;">${escapeHtml(entity.comp)}.${escapeHtml(entity.pin)}</span>${entity.number ? ` (#${escapeHtml(entity.number)})` : ""}`]);
      rows.push(["Net", entity.net ? `<span style="color:#4ade80;font-weight:700;">${escapeHtml(entity.net)}</span>` : "(unconnected)"]);
      rows.push(["Layer / Type", `${escapeHtml(entity.layer)} (${escapeHtml(entity.padType || "smd")})`]);
      rows.push(["Pad Size", `${fmtNum(entity.w, 3)} × ${fmtNum(entity.h, 3)} mm (${fmtNum(entity.w * MILS_PER_MM, 1)} × ${fmtNum(entity.h * MILS_PER_MM, 1)} mil)`]);
      if (entity.drill > 0) {
        rows.push(["Drill Bore", `Ø ${fmtNum(entity.drill, 3)} mm`]);
      }
      rows.push(["Position", `(${fmtNum(entity.x, 3)}, ${fmtNum(entity.y, 3)}) mm`]);
    } else if (entity.kind === "via") {
      rows.push(["Entity", "Plated Through-Hole Via"]);
      rows.push(["Net", entity.net ? `<span style="color:#4ade80;font-weight:700;">${escapeHtml(entity.net)}</span>` : "(unassigned)"]);
      rows.push(["Outer / Drill Ø", `Ø ${fmtNum(entity.padDia, 3)} mm / Ø ${fmtNum(entity.drillDia, 3)} mm`]);
      rows.push(["Position", `(${fmtNum(entity.x, 3)}, ${fmtNum(entity.y, 3)}) mm`]);
    } else if (entity.kind === "trace") {
      rows.push(["Entity", "Copper Trace Segment"]);
      rows.push(["Net", entity.net ? `<span style="color:#4ade80;font-weight:700;">${escapeHtml(entity.net)}</span>` : "(unassigned)"]);
      rows.push(["Layer", escapeHtml(entity.layer)]);
      rows.push(["Trace Width", `${fmtNum(entity.width, 3)} mm (${fmtNum(entity.width * MILS_PER_MM, 1)} mil)`]);
      rows.push(["Segment Length", `${fmtNum(entity.length, 3)} mm`]);
    } else if (entity.kind === "component") {
      rows.push(["Reference", `<span style="color:var(--quake-gold);font-weight:700;">${escapeHtml(entity.refDes)}</span>`]);
      rows.push(["Footprint", escapeHtml(entity.footprint || "—")]);
      if (entity.value) rows.push(["Value", escapeHtml(entity.value)]);
      if (entity.mpn) rows.push(["MPN", escapeHtml(entity.mpn)]);
      if (entity.description) rows.push(["Description", escapeHtml(entity.description)]);
      rows.push(["Side / Centroid", `${escapeHtml(entity.layer)} · (${fmtNum(entity.x, 2)}, ${fmtNum(entity.y, 2)}) mm`]);
    }

    el.innerHTML = this._formatKeyValueTable(rows);
  }

  /**
   * Format `[label, valueHtml]` pairs into a clean Quake HUD key-value table.
   *
   * @param {Array<[string, string]>} rows - Key-value pairs.
   * @returns {string} HTML markup.
   */
  _formatKeyValueTable(rows) {
    const trs = rows
      .map(
        ([k, v]) =>
          `<tr>` +
          `<td style="padding:4px 8px 4px 0;color:var(--quake-text-muted);white-space:nowrap;vertical-align:top;">${escapeHtml(k)}:</td>` +
          `<td style="padding:4px 0;color:#f8fafc;word-break:break-word;">${v}</td>` +
          `</tr>`,
      )
      .join("");
    return `<table style="width:100%;border-collapse:collapse;font-size:11px;"><tbody>${trs}</tbody></table>`;
  }

  /**
   * Build simulation scalar time-series sparklines from `telemetry.frames`.
   *
   * @param {object|null} telemetry - Backend simulation telemetry response.
   */
  populateSimulationMetrics(telemetry) {
    this._metricSeries = [];
    this._metricCanvases.clear();
    if (!telemetry || !Array.isArray(telemetry.frames) || telemetry.frames.length === 0) {
      this.renderMetricsList("");
      return;
    }

    const keysSet = new Set();
    for (const f of telemetry.frames) {
      if (f.metrics && typeof f.metrics === "object") {
        for (const k of Object.keys(f.metrics)) keysSet.add(k);
      }
    }

    for (const key of Array.from(keysSet).sort()) {
      const values = telemetry.frames.map((f) => {
        const raw = f.metrics ? Number(f.metrics[key]) : NaN;
        return Number.isFinite(raw) ? raw : 0;
      });
      let min = Infinity;
      let max = -Infinity;
      for (const v of values) {
        if (v < min) min = v;
        if (v > max) max = v;
      }
      this._metricSeries.push({
        key,
        values,
        min: Number.isFinite(min) ? min : 0,
        max: Number.isFinite(max) ? max : 1,
        last: values[values.length - 1] || 0,
      });
    }

    this.renderMetricsList("");
  }

  /**
   * Render fuzzy-filtered simulation metric sparkline cards into `#metrics-list`.
   *
   * @param {string} query - Metric filter query.
   */
  renderMetricsList(query = "") {
    const listEl = this._el("metrics-list");
    const countEl = this._el("metrics-count");
    if (!listEl) return;
    listEl.innerHTML = "";
    this._metricCanvases.clear();

    const ranked = query.trim()
      ? fuzzyFilterAndRank(query, this._metricSeries, (m) => m.key)
      : this._metricSeries.map((item) => ({ item }));

    if (countEl) {
      countEl.textContent = `${ranked.length} / ${this._metricSeries.length} metrics`;
    }

    const dpr = Math.min(3, Math.max(1, Number(this.ctx.getDevicePixelRatio()) || 2));

    for (const { item } of ranked) {
      const card = this.ctx.createElement("div");
      card.style.cssText =
        "background:#0d1017;border:1px solid var(--quake-border);border-radius:4px;padding:6px 8px;";

      const header = this.ctx.createElement("div");
      header.style.cssText =
        "display:flex;justify-content:space-between;align-items:center;font-size:10px;margin-bottom:4px;gap:6px;";

      const title = this.ctx.createElement("span");
      title.style.cssText = "color:var(--quake-gold);font-weight:700;overflow:hidden;text-overflow:ellipsis;";
      title.textContent = item.key;

      const valBadge = this.ctx.createElement("span");
      valBadge.dataset.metricValueFor = item.key;
      valBadge.style.cssText = "color:var(--quake-cyan);font-variant-numeric:tabular-nums;";
      const curVal = item.values[this.simRenderer.currentFrameIndex] ?? item.last;
      valBadge.textContent = fmtNum(curVal, 3);

      header.appendChild(title);
      header.appendChild(valBadge);
      card.appendChild(header);

      const canvas = this.ctx.createElement("canvas");
      const cssW = SPARKLINE_MIN_CSS_WIDTH_PX;
      const cssH = SPARKLINE_CSS_HEIGHT_PX;
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      canvas.style.cssText = `width:100%;height:${cssH}px;display:block;cursor:pointer;`;
      canvas.addEventListener("click", (ev) => {
        const rect = canvas.getBoundingClientRect();
        const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / Math.max(1, rect.width)));
        const idx = Math.round(frac * Math.max(0, item.values.length - 1));
        this.simRenderer.setFrameIndex(idx);
      });

      card.appendChild(canvas);
      listEl.appendChild(card);
      this._metricCanvases.set(item.key, canvas);
      this._drawSparkline(canvas, item, this.simRenderer.currentFrameIndex, dpr);
    }
  }

  /**
   * Update live metric readouts and sparkline step cursors when simulation frame changes.
   *
   * @param {object} frameSummary - Summary emitted by `SimulationVoxelRenderer.onFrameChange`.
   */
  updateSimulationFrameHud(frameSummary) {
    if (!frameSummary) return;

    const stepValEl = this._el("sim-step-val");
    if (stepValEl) {
      stepValEl.textContent =
        `Step: ${frameSummary.step} (${frameSummary.elementCount.toLocaleString()} ${frameSummary.renderStyle === "voxels" ? "voxels" : "spheres"})`;
    }
    const stepSlider = this._el("sim-step-slider");
    if (stepSlider) {
      stepSlider.max = String(Math.max(0, frameSummary.totalFrames - 1));
      stepSlider.value = String(frameSummary.frameIndex);
    }

    const flowEl = this._el("sim-flow-metrics");
    if (flowEl && frameSummary.metrics) {
      const entries = Object.entries(frameSummary.metrics).slice(0, 4);
      flowEl.textContent = entries
        .map(([k, v]) => `${k.split("/").pop()}: ${fmtNum(Number(v), 2)}`)
        .join("  │  ");
    }

    const doc = this.ctx.getDocument();
    const dpr = Math.min(3, Math.max(1, Number(this.ctx.getDevicePixelRatio()) || 2));
    for (const series of this._metricSeries) {
      const canvas = this._metricCanvases.get(series.key);
      if (canvas) {
        this._drawSparkline(canvas, series, frameSummary.frameIndex, dpr);
      }
      if (doc) {
        const safeKey = series.key.replace(/["\\]/g, "\\$&");
        const badge = doc.querySelector(`[data-metric-value-for="${safeKey}"]`);
        if (badge) {
          badge.textContent = fmtNum(series.values[frameSummary.frameIndex] ?? 0, 3);
        }
      }
    }
  }

  /**
   * Draw a crisp Retina sparkline + live vertical step cursor onto `canvas`.
   *
   * @param {HTMLCanvasElement} canvas - Sparkline canvas.
   * @param {{values: Array<number>, min: number, max: number}} series - Metric series.
   * @param {number} activeIdx - Current frame index.
   * @param {number} dpr - Physical device pixel ratio.
   */
  _drawSparkline(canvas, series, activeIdx, dpr) {
    const c2d = canvas.getContext && canvas.getContext("2d");
    if (!c2d) return;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    c2d.clearRect(0, 0, w, h);

    const vals = series.values;
    if (vals.length === 0) return;
    const span = Math.max(1e-6, series.max - series.min);

    c2d.strokeStyle = "#38bdf8";
    c2d.lineWidth = 1.4;
    c2d.beginPath();
    for (let i = 0; i < vals.length; i += 1) {
      const x = vals.length === 1 ? w * 0.5 : (i / (vals.length - 1)) * (w - 6) + 3;
      const y = h - 4 - ((vals[i] - series.min) / span) * (h - 8);
      if (i === 0) c2d.moveTo(x, y);
      else c2d.lineTo(x, y);
    }
    c2d.stroke();

    const clampedIdx = Math.max(0, Math.min(vals.length - 1, activeIdx));
    const cx = vals.length === 1 ? w * 0.5 : (clampedIdx / (vals.length - 1)) * (w - 6) + 3;
    c2d.strokeStyle = "#ffb800";
    c2d.lineWidth = 1.2;
    c2d.beginPath();
    c2d.moveTo(cx, 1);
    c2d.lineTo(cx, h - 1);
    c2d.stroke();
  }

  /**
   * Render `#pins-list` spatial 3D annotation pins with camera focus & delete buttons.
   */
  renderPinsList() {
    const listEl = this._el("pins-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    if (this.markupController.pins.length === 0) {
      const empty = this.ctx.createElement("div");
      empty.style.cssText = "font-size:11px;color:var(--quake-text-muted);";
      empty.textContent = "No 3D pins placed. Open ✏️ Markup → 📍 Pin and click on model.";
      listEl.appendChild(empty);
      return;
    }

    for (const pin of this.markupController.pins) {
      const card = this.ctx.createElement("div");
      card.style.cssText =
        "display:flex;justify-content:space-between;align-items:center;gap:6px;padding:6px 8px;" +
        "background:#0d1017;border:1px solid var(--quake-border);border-radius:4px;font-size:11px;";

      const info = this.ctx.createElement("div");
      info.style.cssText = "cursor:pointer;flex:1;overflow:hidden;";
      info.innerHTML =
        `<div style="color:var(--quake-gold);font-weight:700;">#${pin.id}: ${escapeHtml(pin.text)}</div>` +
        `<div style="font-size:10px;color:var(--quake-text-muted);">(${fmtNum(pin.x, 1)}, ${fmtNum(pin.y, 1)}, ${fmtNum(pin.z, 1)}) mm</div>`;
      info.addEventListener("click", () => {
        this.cameraController.focusPoint(pin.x, pin.y, pin.z);
        this.viewport.requestRender();
      });

      const delBtn = this.ctx.createElement("button");
      delBtn.className = "hud-btn";
      delBtn.style.cssText = "padding:2px 6px;font-size:10px;";
      delBtn.textContent = "✕";
      delBtn.addEventListener("click", () => {
        this.markupController.removePin(pin.id);
        this.renderPinsList();
      });

      card.appendChild(info);
      card.appendChild(delBtn);
      listEl.appendChild(card);
    }
  }

  /**
   * Open the Project & Target Chooser modal (`#modal-project-chooser`).
   */
  openProjectChooser() {
    const modal = this._el("modal-project-chooser");
    if (!modal) return;
    this._populateChooserProjects();
    modal.classList.add("visible");
  }

  /**
   * Close the Project & Target Chooser modal.
   */
  closeProjectChooser() {
    const modal = this._el("modal-project-chooser");
    if (modal) modal.classList.remove("visible");
  }

  /**
   * Populate `#chooser-project` options from `this.projects`.
   */
  _populateChooserProjects() {
    const projSel = this._el("chooser-project");
    if (!projSel) return;
    projSel.innerHTML = "";
    for (const p of this.projects) {
      const opt = this.ctx.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name;
      if (p.name === this.currentProject) opt.selected = true;
      projSel.appendChild(opt);
    }
    this._populateChooserTargets();
  }

  /**
   * Populate `#chooser-target` for the selected project.
   */
  _populateChooserTargets() {
    const projSel = this._el("chooser-project");
    const tgtSel = this._el("chooser-target");
    if (!projSel || !tgtSel) return;

    const proj = this.projects.find((p) => p.name === projSel.value) || this.projects[0];
    tgtSel.innerHTML = "";
    if (!proj || !Array.isArray(proj.targets)) return;

    for (const t of proj.targets) {
      const opt = this.ctx.createElement("option");
      opt.value = t.name;
      opt.textContent = t.name;
      if (proj.name === this.currentProject && t.name === this.currentTarget) {
        opt.selected = true;
      }
      tgtSel.appendChild(opt);
    }
    this._populateChooserSubsAndModes();
  }

  /**
   * Populate `#chooser-sub` and `#chooser-mode-pills` for the selected target.
   */
  _populateChooserSubsAndModes() {
    const projSel = this._el("chooser-project");
    const tgtSel = this._el("chooser-target");
    const subSel = this._el("chooser-sub");
    const doc = this.ctx.getDocument();
    if (!projSel || !tgtSel || !subSel || !doc) return;

    const proj = this.projects.find((p) => p.name === projSel.value);
    const tgt = proj && Array.isArray(proj.targets) ? proj.targets.find((t) => t.name === tgtSel.value) : null;

    subSel.innerHTML = '<option value="">(None / Entire Target)</option>';
    if (tgt && Array.isArray(tgt.subassemblies)) {
      for (const s of tgt.subassemblies) {
        const opt = this.ctx.createElement("option");
        opt.value = s;
        opt.textContent = s;
        if (s === this.currentSub) opt.selected = true;
        subSel.appendChild(opt);
      }
    }

    const allowed = tgt && Array.isArray(tgt.modes) ? tgt.modes.map((m) => String(m).toUpperCase()) : ["CAD"];
    const pills = doc.querySelectorAll("#chooser-mode-pills .mode-pill");
    let activePicked = false;
    for (const pill of pills) {
      const m = pill.getAttribute("data-mode");
      const ok = allowed.includes(m);
      pill.disabled = !ok;
      pill.classList.toggle("disabled", !ok);
      if (ok && m === this.currentMode && !activePicked) {
        pill.classList.add("active");
        activePicked = true;
      } else {
        pill.classList.remove("active");
      }
    }
    if (!activePicked) {
      for (const pill of pills) {
        if (!pill.disabled) {
          pill.classList.add("active");
          break;
        }
      }
    }

    const activePill = doc.querySelector("#chooser-mode-pills .mode-pill.active");
    const simStepsBox = this._el("chooser-sim-steps-container");
    if (simStepsBox) {
      simStepsBox.style.display =
        activePill && activePill.getAttribute("data-mode") === "SIMULATE" ? "flex" : "none";
    }
  }

  /**
   * Dispatch target load from chooser selection.
   */
  async _submitChooserSelection() {
    const projSel = this._el("chooser-project");
    const tgtSel = this._el("chooser-target");
    const subSel = this._el("chooser-sub");
    const stepsSel = this._el("chooser-max-steps");
    const doc = this.ctx.getDocument();
    if (!projSel || !tgtSel || !doc) return;

    const activePill = doc.querySelector("#chooser-mode-pills .mode-pill.active");
    const mode = (activePill && activePill.getAttribute("data-mode")) || "CAD";
    const maxSteps = stepsSel ? Number(stepsSel.value) || 1000 : 1000;

    this.closeProjectChooser();
    if (this.onSelectTarget) {
      await this.onSelectTarget({
        project: projSel.value,
        target: tgtSel.value,
        subassembly: subSel ? subSel.value : "",
        mode,
        maxSteps,
      });
    }
  }

  /**
   * Capture a Retina composited PNG snapshot (`WebGL + #markup-canvas`) and open `#modal-bug`.
   */
  openTargetBugModal() {
    const modal = this._el("modal-bug");
    if (!modal) return;

    this._lastBugSnapshotDataUrl = this.viewport.captureCompositedPng();
    const previewImg = this._el("bug-snapshot-preview");
    if (previewImg) {
      previewImg.src = this._lastBugSnapshotDataUrl;
    }

    const titleEl = this._el("bug-title");
    if (titleEl) {
      const scopeTag = this.currentProject ? `[${this.currentProject}/${this.currentTarget}]` : "[scope]";
      titleEl.value = `${scopeTag} Defect Summary`;
    }
    const compEl = this._el("bug-comp");
    if (compEl) {
      compEl.value = this.currentProject
        ? `${this.currentProject}/${this.currentTarget}${this.currentSub ? `/${this.currentSub}` : ""}`
        : "scope";
    }
    const catEl = this._el("bug-cat");
    if (catEl) {
      catEl.value =
        this.currentMode === "PCB"
          ? "PCB"
          : this.currentMode === "SIMULATE"
            ? "SIMULATION"
            : "CAD";
    }
    const stepsEl = this._el("bug-steps");
    if (stepsEl) {
      const targetArg = this.currentProject && this.currentTarget
        ? `${this.currentProject}/${this.currentTarget}`
        : "";
      const modeFlag = this.currentMode !== "CAD" ? ` --mode ${this.currentMode.toLowerCase()}` : "";
      stepsEl.value = `python tools/scope.py ${targetArg}${modeFlag}`.trim();
    }

    modal.classList.add("visible");
  }

  /**
   * Close `#modal-bug`.
   */
  closeTargetBugModal() {
    const modal = this._el("modal-bug");
    if (modal) modal.classList.remove("visible");
  }

  /**
   * Submit `ScopeTargetBugRequest` to `POST /api/scope/target_bug`.
   */
  async submitTargetBug() {
    const titleEl = this._el("bug-title");
    const sevEl = this._el("bug-severity");
    const catEl = this._el("bug-cat");
    const descEl = this._el("bug-desc");
    const stepsEl = this._el("bug-steps");

    const payload = {
      project: this.currentProject || "workspace",
      target: this.currentTarget || "default",
      subassembly: this.currentSub || null,
      mode: this.currentMode || "CAD",
      title: (titleEl && titleEl.value.trim()) || "Scope Defect Report",
      severity: (sevEl && sevEl.value) || "MEDIUM",
      category: (catEl && catEl.value) || "CAD",
      description: (descEl && descEl.value.trim()) || "Reported via Scope Workstation.",
      reproduction_steps: (stepsEl && stepsEl.value) || "python tools/scope.py",
      image_base64: this._lastBugSnapshotDataUrl || "data:image/png;base64,",
      annotations: this.markupController.getAnnotationsPayload(),
      markups: this.markupController.getMarkupsPayload(),
    };

    const resp = await this.ctx.fetchJson("/api/scope/target_bug", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (resp && resp.bug_id) {
      this.closeTargetBugModal();
      showToast(this.ctx, `Filed Bug ${resp.bug_id}!`, "success");
    } else {
      showToast(this.ctx, (resp && resp.error) || "Failed to submit bug report", "error");
    }
  }

  /**
   * Launch local KiCad EDA via `POST /api/scope/open_kicad`.
   */
  async openInKicad() {
    if (!this.currentProject || !this.currentTarget) return;
    const resp = await this.ctx.fetchJson("/api/scope/open_kicad", {
      method: "POST",
      body: JSON.stringify({
        project: this.currentProject,
        target: this.currentTarget,
        subassembly: this.currentSub || null,
      }),
    });
    if (resp && resp.status === "ok") {
      showToast(this.ctx, resp.message || "Opened in KiCad", "success");
    } else {
      showToast(this.ctx, (resp && resp.error) || "Could not launch KiCad", "warning");
    }
  }

  /**
   * Launch native Rerun Viewer via `POST /api/scope/open_rerun`.
   */
  async openInRerunViewer() {
    if (!this.currentProject || !this.currentTarget) return;
    const resp = await this.ctx.fetchJson("/api/scope/open_rerun", {
      method: "POST",
      body: JSON.stringify({
        project: this.currentProject,
        target: this.currentTarget,
      }),
    });
    if (resp && resp.status === "ok") {
      showToast(this.ctx, resp.message || "Launched Rerun Viewer", "success");
    } else {
      showToast(this.ctx, (resp && resp.error) || "Could not launch Rerun Viewer", "warning");
    }
  }
}
