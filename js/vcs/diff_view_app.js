/**
 * Shared VCS Diff Viewer & Smartlog Workstation Entrypoint (`diff_view_app.js`).
 *
 * Orchestrates Smartlog DAG navigation, Working Tree operations, Diff rendering,
 * Commit/Branch/PR modals, and embedded Code Review / Issue Tracker modals.
 * Parameterized via `#app-boot-config` (`issueKind`, `trackerRoute`, `issueLabel`)
 * so `hardware` and `firmware` run 100% byte-identical module code.
 */

import {
  applyIframeContextClass,
  bindDelegatedEvent,
  clearChildren,
  createEl,
  queryAll,
  resolveElement,
} from "../core/dom.js";
import { bindModalBackdropClose } from "../core/modal.js";
import { setupPanelResizer } from "../core/resizer.js";
import { getRuntimeContext } from "../core/runtime_context.js";
import { copyToClipboard, showToast } from "../core/toast.js";
import { applyUiScale } from "../core/ui_scale.js";
import { renderDiff } from "../diff/diff_engine.js";
import {
  checkoutBranch,
  closeBranchModal,
  closeCommitModal,
  closePrSubmitModal,
  combineSelectedCommits,
  createPullRequests,
  discardSelectedFromModal,
  finishPrSubmitModal,
  openBranchModal,
  openCommitModal,
  openGotoModal,
  performInitialSync,
  rebaseRepository,
  renderBranchLists,
  splitActiveCommit,
  submitCommitModal,
  syncRepository,
  toggleModalSelectAll,
  unlinkPullRequests,
} from "./commit_modals.js";
import {
  bindSmartlogEvents,
  computeShiftRangeSelection,
  renderSmartlogNodes,
  selectAllCommits,
  selectNoneCommits,
  toggleMergedCommits,
  updateMergedVisibility,
  updateSelectedCount,
} from "./smartlog_dag.js";
import {
  bindFilesContainerEvents,
  discardSelectedWorkingFiles,
  quickCommitStaged,
  renderCommitFiles,
  renderWorkingTreeFiles,
} from "./working_tree.js";

const WORD_WRAP_STORAGE_KEY = "quake_diff_word_wrap";
const SMARTLOG_WIDTH_STORAGE_KEY = "diffview_smartlog_width";
const FILES_WIDTH_STORAGE_KEY = "diffview_files_width";
const AUTO_SYNC_INTERVAL_MS = 10000;

/**
 * Parse URL query parameters without referencing the `URLSearchParams` browser global.
 *
 * @param {string} searchStr - `location.search` string (e.g. `"?commit=abc&goto=def"`).
 * @returns {Record<string, string>} Decoded key-value map.
 */
export function parseQueryParams(searchStr) {
  const result = {};
  const trimmed = String(searchStr || "").replace(/^\?/, "");
  if (!trimmed) {
    return result;
  }
  for (const pair of trimmed.split("&")) {
    if (!pair) continue;
    const eqIdx = pair.indexOf("=");
    if (eqIdx === -1) {
      result[decodeURIComponent(pair)] = "";
    } else {
      const key = decodeURIComponent(pair.slice(0, eqIdx));
      const val = decodeURIComponent(pair.slice(eqIdx + 1).replace(/\+/g, " "));
      result[key] = val;
    }
  }
  return result;
}

/**
 * Initialize the VCS Diff Viewer & Smartlog Workstation against `ctx`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @returns {object} Controller handle for testing and lifecycle inspection.
 */
export function initDiffViewApp(ctx) {
  applyIframeContextClass(ctx);
  const config = ctx.getBootConfig();
  const issueKind = config.issueKind === "worm" ? "worm" : "bug";
  const trackerRoute = config.trackerRoute || (issueKind === "worm" ? "/worms" : "/bugs");
  const issueLabel = config.issueLabel || (issueKind === "worm" ? "WORM" : "BUG");
  const openIssueApi = issueKind === "worm" ? "/api/open_worm" : "/api/open_bug";

  const state = {
    repoName: config.repoName || "hardware",
    repoRoot: config.repoRoot || "",
    repoWebUrl: config.repoWebUrl || "",
    githubRepo: config.githubRepo || "",
    activeCommit: config.activeCommit || "working",
    activeFile: null,
    diffMode: "side_by_side",
    files: [],
    workingFiles: [],
    conflicts: [],
    currentDiff: null,
    selectedCommits: Array.isArray(config.selectedCommits) ? config.selectedCommits.slice() : [],
    feedbackCollapsed: false,
    isAmendMode: false,
    panes: {
      smartlog: true,
      files: true,
    },
    currentBranch: config.currentBranch || "",
    lastWorkingFingerprint: null,
    lastCommitFingerprint: null,
  };

  const prTimerRef = { intervalId: null };
  let autoSyncTimer = null;
  let isAutoSyncing = false;

  const updateWrapButtonState = (isWrapped) => {
    const btn = resolveElement(ctx, "btnToggleWrap");
    if (btn) {
      btn.textContent = isWrapped ? "Wrap: On" : "Wrap: Off";
      btn.className = isWrapped
        ? "quake-btn quake-btn-gold quake-btn-sm"
        : "quake-btn quake-btn-default quake-btn-sm";
    }
  };

  const initWordWrap = () => {
    const isWrapped = ctx.getStorage().getItem(WORD_WRAP_STORAGE_KEY) === "true";
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.classList.toggle("diff-word-wrap", isWrapped);
    }
    updateWrapButtonState(isWrapped);
  };

  const toggleWordWrap = () => {
    const doc = ctx.getDocument();
    if (!doc || !doc.body) {
      return;
    }
    const isWrapped = doc.body.classList.toggle("diff-word-wrap");
    ctx.getStorage().setItem(WORD_WRAP_STORAGE_KEY, isWrapped ? "true" : "false");
    updateWrapButtonState(isWrapped);
  };

  const togglePane = (pane) => {
    if (pane === "smartlog" || pane === "commits") {
      state.panes.smartlog = !state.panes.smartlog;
      const el = resolveElement(ctx, "paneSmartlog");
      const resizer = resolveElement(ctx, "resizerSmartlog");
      if (el) {
        el.classList.toggle("collapsed", !state.panes.smartlog);
        if (state.panes.smartlog) {
          const savedW = ctx.getStorage().getItem(SMARTLOG_WIDTH_STORAGE_KEY);
          if (savedW) el.style.width = `${savedW}px`;
        }
      }
      if (resizer) resizer.classList.toggle("hidden", !state.panes.smartlog);
      const btn = resolveElement(ctx, "btnToggleSmartlog");
      if (btn) btn.classList.toggle("quake-btn-active", state.panes.smartlog);
    } else if (pane === "files") {
      state.panes.files = !state.panes.files;
      const el = resolveElement(ctx, "paneFiles");
      const resizer = resolveElement(ctx, "resizerFiles");
      if (el) {
        el.classList.toggle("collapsed", !state.panes.files);
        if (state.panes.files) {
          const savedW = ctx.getStorage().getItem(FILES_WIDTH_STORAGE_KEY);
          if (savedW) el.style.width = `${savedW}px`;
        }
      }
      if (resizer) resizer.classList.toggle("hidden", !state.panes.files);
      const btn = resolveElement(ctx, "btnToggleFiles");
      if (btn) btn.classList.toggle("quake-btn-active", state.panes.files);
    }
  };

  const buildFullFilePath = (filePath) => {
    if (!filePath) return "";
    if (filePath.startsWith("/")) return filePath;
    if (!state.repoRoot) return filePath;
    return `${state.repoRoot.replace(/\/+$/, "")}/${filePath.replace(/^\/+/, "")}`;
  };

  const updateActiveFileActions = (filePath) => {
    if (!filePath) return;
    const fullPath = buildFullFilePath(filePath);
    const vscodeUrl = `vscode://file${fullPath.startsWith("/") ? "" : "/"}${fullPath}`;
    const btnVsCode = resolveElement(ctx, "btnOpenVsCode");
    if (btnVsCode) {
      btnVsCode.href = vscodeUrl;
    }
  };

  const openInVsCode = async (line = 1) => {
    const filePath = state.activeFile;
    if (!filePath) return;
    if (!state.repoRoot && !filePath.startsWith("/")) {
      showToast(ctx, "Error: Repository root is not configured", "error");
      return;
    }
    const fullPath = buildFullFilePath(filePath);
    const vscodeUrl = `vscode://file${fullPath.startsWith("/") ? "" : "/"}${fullPath}${line > 1 ? `:${line}` : ""}`;
    const resp = await ctx.fetchRaw("/api/open-vscode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: fullPath, line }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data && data.status === "ok") {
        showToast(ctx, `Opened in VS Code: ${filePath}`);
        return;
      }
    }
    ctx.navigate(vscodeUrl);
  };

  const selectFile = async (filePath) => {
    state.activeFile = filePath;
    for (const el of queryAll(ctx, ".file-item")) {
      const rowPath = (el.dataset && el.dataset.path) || "";
      el.classList.toggle("active", rowPath === filePath);
    }

    const titleText = resolveElement(ctx, "diffFileTitleText");
    if (titleText) {
      titleText.textContent = filePath;
    }
    const fileActions = resolveElement(ctx, "diffFileActions");
    if (fileActions) {
      fileActions.style.display = "inline-flex";
    }
    updateActiveFileActions(filePath);

    const diffBody = resolveElement(ctx, "diffBodyContainer");
    if (diffBody) {
      clearChildren(diffBody);
      diffBody.appendChild(
        createEl(ctx, "div", {
          text: "Loading diff...",
          style: { textAlign: "center", padding: "30px", color: "var(--quake-text-muted)" },
        }),
      );
    }

    const url = `/api/diff?commit=${encodeURIComponent(state.activeCommit)}&file=${encodeURIComponent(filePath)}`;
    const resp = await ctx.fetchRaw(url);
    if (!resp.ok) {
      if (diffBody) {
        clearChildren(diffBody);
        diffBody.appendChild(
          createEl(ctx, "div", {
            text: `Failed to load diff (HTTP ${resp.status})`,
            style: { color: "var(--quake-red)", padding: "20px" },
          }),
        );
      }
      return;
    }
    const diffData = await resp.json();
    state.currentDiff = diffData;

    const statsBadge = resolveElement(ctx, "diffStatsBadge");
    if (statsBadge) statsBadge.style.display = "inline-flex";
    const addEl = resolveElement(ctx, "diffStatsAdd");
    if (addEl) addEl.textContent = `+${diffData.additions || 0}`;
    const delEl = resolveElement(ctx, "diffStatsDel");
    if (delEl) delEl.textContent = `-${diffData.deletions || 0}`;

    renderDiff(ctx, diffBody, diffData, { mode: state.diffMode });
  };

  const loadFilesForActiveCommit = async () => {
    const container = resolveElement(ctx, "filesContainer");
    if (container) {
      clearChildren(container);
      container.appendChild(
        createEl(ctx, "div", {
          text: "Loading files...",
          style: { textAlign: "center", padding: "20px", color: "var(--quake-text-muted)" },
        }),
      );
    }

    const commitArea = resolveElement(ctx, "workingTreeCommitArea");
    if (commitArea) {
      commitArea.style.display = state.activeCommit === "working" ? "flex" : "none";
    }

    if (state.activeCommit === "working") {
      const workResp = await ctx.fetchRaw("/api/working");
      state.workingFiles = workResp.ok ? await workResp.json() : [];
      const confResp = await ctx.fetchRaw("/api/conflicts");
      state.conflicts = confResp.ok ? await confResp.json() : [];
      renderWorkingTreeFiles(ctx, container, state, selectFile);
    } else {
      const filesResp = await ctx.fetchRaw(
        `/api/files?commit=${encodeURIComponent(state.activeCommit)}&include_feedback=true`,
      );
      state.files = filesResp.ok ? await filesResp.json() : [];
      renderCommitFiles(ctx, container, state, selectFile);
    }
  };

  const selectCommit = async (commitHash, event = null, clickedNode = null) => {
    if (event && event.shiftKey && state.activeCommit && state.activeCommit !== commitHash) {
      const allNodes = queryAll(ctx, ".smartlog-node").filter((n) =>
        Boolean(n.dataset && n.dataset.hash),
      );
      const allHashes = allNodes.map((n) => n.dataset.hash);
      const rangeHashes = computeShiftRangeSelection(allHashes, state.activeCommit, commitHash);
      if (rangeHashes.length > 0) {
        for (const node of allNodes) {
          const inRange = rangeHashes.includes(node.dataset.hash);
          const cb = node.querySelector(".commit-checkbox");
          if (cb) cb.checked = inRange;
          node.classList.toggle("selected", inRange);
        }
        state.selectedCommits = rangeHashes;
        updateSelectedCount(ctx, state);
      }
    }

    state.activeCommit = commitHash;
    state.activeFile = null;
    state.currentDiff = null;

    const allNodes = queryAll(ctx, ".smartlog-node");
    for (const el of allNodes) {
      el.classList.remove("active");
    }

    let activeEl = clickedNode;
    if (!activeEl) {
      if (commitHash === "working") {
        activeEl = resolveElement(ctx, "node-working");
      } else {
        activeEl =
          allNodes.find((n) => n.dataset && n.dataset.hash === commitHash) ||
          allNodes.find(
            (n) => n.dataset && n.dataset.hash && n.dataset.hash.startsWith(commitHash),
          ) ||
          resolveElement(ctx, `node-${commitHash}`);
      }
    }

    if (activeEl) {
      activeEl.classList.add("active");
      if (activeEl.dataset && activeEl.dataset.hash && activeEl.dataset.hash !== "working") {
        state.activeCommit = activeEl.dataset.hash;
      }
    }

    const commitArea = resolveElement(ctx, "workingTreeCommitArea");
    if (commitArea) {
      commitArea.style.display = state.activeCommit === "working" ? "flex" : "none";
    }

    const shaSpan = activeEl ? activeEl.querySelector(".node-sha") : null;
    const shortSha = shaSpan
      ? shaSpan.textContent.trim()
      : state.activeCommit.length > 8
        ? state.activeCommit.slice(0, 8)
        : state.activeCommit;
    const filesTitle = resolveElement(ctx, "filesHeaderTitle");
    if (filesTitle) {
      filesTitle.textContent =
        state.activeCommit === "working" ? "Working Tree Files" : `Files (${shortSha})`;
    }

    await loadFilesForActiveCommit();
  };

  const setDiffMode = (mode) => {
    state.diffMode = mode;
    const btnSbs = resolveElement(ctx, "btnModeSbs");
    const btnUni = resolveElement(ctx, "btnModeUnified");
    if (btnSbs) {
      btnSbs.className =
        mode === "side_by_side"
          ? "quake-btn quake-btn-gold quake-btn-sm"
          : "quake-btn quake-btn-default quake-btn-sm";
    }
    if (btnUni) {
      btnUni.className =
        mode === "unified"
          ? "quake-btn quake-btn-gold quake-btn-sm"
          : "quake-btn quake-btn-default quake-btn-sm";
    }
    if (state.currentDiff) {
      renderDiff(ctx, "diffBodyContainer", state.currentDiff, { mode: state.diffMode });
    }
  };

  const openWorkstationModal = (url, targetName = "_blank") => {
    const modal = resolveElement(ctx, "workstationModal");
    const iframe = resolveElement(ctx, "workstationIframe");
    if (!modal || !iframe) {
      ctx.openExternalUrl(url, targetName);
      return;
    }
    iframe.src = url;
    if (typeof iframe.setAttribute === "function") {
      iframe.setAttribute("src", url);
    }
    modal.style.display = "flex";
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.style.overflow = "hidden";
    }
  };

  const syncWorkingAndCommitsSilently = async () => {
    const doc = ctx.getDocument();
    if (isAutoSyncing || (doc && doc.hidden && doc.visibilityState === "hidden")) {
      return;
    }
    isAutoSyncing = true;
    const resp = await ctx.fetchRaw("/api/session?type=diff");
    if (resp.ok) {
      const session = await resp.json();
      const workingFiles = Array.isArray(session.working_files) ? session.working_files : [];
      const workingFp = JSON.stringify(
        workingFiles.map((f) => [
          f.path,
          f.is_staged,
          f.is_untracked,
          f.is_conflicted,
          f.status,
          f.additions,
          f.deletions,
        ]),
      );
      if (state.lastWorkingFingerprint === null) {
        state.lastWorkingFingerprint = workingFp;
      } else if (workingFp !== state.lastWorkingFingerprint) {
        state.lastWorkingFingerprint = workingFp;
        state.workingFiles = workingFiles;
        state.conflicts = Array.isArray(session.conflicts) ? session.conflicts : [];
        if (state.activeCommit === "working") {
          renderWorkingTreeFiles(ctx, "filesContainer", state, selectFile);
          if (state.activeFile) {
            await selectFile(state.activeFile);
          }
        }
      }

      const nodes = Array.isArray(session.smartlog_nodes) ? session.smartlog_nodes : [];
      const commitFp = JSON.stringify(
        nodes.map((n) => [
          n.commit_hash,
          n.short_hash,
          n.subject,
          n.is_head,
          n.branches,
          n.tags,
          n.pr_number,
          n.pr_status,
          n.cr_open_count,
          n.cr_resolved_count,
        ]),
      );
      if (state.lastCommitFingerprint === null) {
        state.lastCommitFingerprint = commitFp;
      } else if (commitFp !== state.lastCommitFingerprint) {
        state.lastCommitFingerprint = commitFp;
        renderSmartlogNodes(ctx, "smartlogList", nodes, state, config);
        await loadFilesForActiveCommit();
        if (state.activeFile) {
          await selectFile(state.activeFile);
        }
      }

      if (session.current_branch && session.current_branch !== state.currentBranch) {
        state.currentBranch = session.current_branch;
        const brBtn = resolveElement(ctx, "btnBranchDropdown");
        if (brBtn) {
          const label = brBtn.querySelector("span");
          if (label) label.textContent = `🌿 ${session.current_branch}`;
        }
      }
    }
    isAutoSyncing = false;
  };

  const closeWorkstationModal = () => {
    const modal = resolveElement(ctx, "workstationModal");
    const iframe = resolveElement(ctx, "workstationIframe");
    if (!modal) return;
    modal.style.display = "none";
    if (iframe) iframe.src = "about:blank";
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.style.overflow = "";
    }
    syncWorkingAndCommitsSilently();
  };

  const jumpToCR = async (commitHash) => {
    if (!commitHash) return;
    const targetName = `${state.repoName}_code_review`;
    const resp = await ctx.fetchRaw("/api/open_code_review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commits: [commitHash] }),
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res && res.url) {
        openWorkstationModal(res.url, targetName);
        return;
      }
    }
    openWorkstationModal(`/review?revisions=${encodeURIComponent(commitHash)}`, targetName);
  };

  const openSelectedInCodeReview = async () => {
    let commits =
      state.selectedCommits.length > 0
        ? state.selectedCommits.slice()
        : state.activeCommit
          ? [state.activeCommit]
          : [];
    if (
      commits.length === 1 &&
      commits[0] === "working" &&
      (!state.workingFiles || state.workingFiles.length === 0)
    ) {
      commits = [];
    }
    const targetName = `${state.repoName}_code_review`;
    const resp = await ctx.fetchRaw("/api/open_code_review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commits }),
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res && res.url) {
        openWorkstationModal(res.url, targetName);
        return;
      }
    }
    const revStr = commits.join(",");
    openWorkstationModal(
      revStr ? `/review?revisions=${encodeURIComponent(revStr)}` : "/review",
      targetName,
    );
  };

  const openIssueById = async (issueId) => {
    const targetName = `${state.repoName}_${issueKind}_tracker`;
    const body = issueKind === "worm" ? { worm_id: issueId } : { bug_id: issueId };
    const resp = await ctx.fetchRaw(openIssueApi, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res && res.url) {
        openWorkstationModal(res.url, targetName);
        return;
      }
    }
    openWorkstationModal(`${trackerRoute}#${issueLabel}-${issueId}`, targetName);
  };

  const openIssueTracker = async () => {
    const targetName = `${state.repoName}_${issueKind}_tracker`;
    const resp = await ctx.fetchRaw(openIssueApi, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res && res.url) {
        openWorkstationModal(res.url, targetName);
        return;
      }
    }
    openWorkstationModal(trackerRoute, targetName);
  };

  const createIssueForCommit = async (commitHash) => {
    const targetName = `${state.repoName}_${issueKind}_tracker`;
    const resp = await ctx.fetchRaw(openIssueApi, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commit: commitHash }),
    });
    if (resp.ok) {
      const res = await resp.json();
      if (res && res.url) {
        openWorkstationModal(res.url, targetName);
        return;
      }
    }
    openWorkstationModal(`${trackerRoute}#new?commit=${encodeURIComponent(commitHash)}`, targetName);
  };

  // Setup UI Scale & Panel Resizers
  const uiScaleScales = ["75%", "80%", "90%", "100%", "110%", "125%", "150%"];
  const applyScaleLabel = (rawLabel) => {
    const label = uiScaleScales.includes(rawLabel) ? rawLabel : "100%";
    const pct = Number.parseInt(label, 10) || 100;
    applyUiScale(ctx, pct, { storageKey: "ui_scale", persistValue: label });
    const selEl = resolveElement(ctx, "uiScaleSelect");
    if (selEl && selEl.value !== label) {
      selEl.value = label;
    }
  };
  applyScaleLabel(ctx.getStorage().getItem("ui_scale") || "100%");
  const uiScaleSel = resolveElement(ctx, "uiScaleSelect");
  if (uiScaleSel) {
    uiScaleSel.addEventListener("change", () => applyScaleLabel(uiScaleSel.value));
  }
  initWordWrap();
  setupPanelResizer(ctx, "resizerSmartlog", "paneSmartlog", SMARTLOG_WIDTH_STORAGE_KEY, {
    minSize: 180,
    maxSize: 800,
    axis: "x",
  });
  setupPanelResizer(ctx, "resizerFiles", "paneFiles", FILES_WIDTH_STORAGE_KEY, {
    minSize: 160,
    maxSize: 700,
    axis: "x",
  });

  // Bind Smartlog & Files delegated events
  bindSmartlogEvents(ctx, "smartlogList", state, config, {
    onSelectCommit: selectCommit,
    onJumpToCR: jumpToCR,
    onOpenIssue: openIssueById,
    onCreateIssueForCommit: createIssueForCommit,
  });
  bindFilesContainerEvents(ctx, "filesContainer", state, {
    onSelectFile: selectFile,
    onRefreshFiles: loadFilesForActiveCommit,
  });

  // Bind modal backdrop clicks
  bindModalBackdropClose(ctx, "commitModalOverlay", () => closeCommitModal(ctx));
  bindModalBackdropClose(ctx, "modalBranchPicker", () => closeBranchModal(ctx));
  bindModalBackdropClose(ctx, "workstationModal", closeWorkstationModal);

  // Bind Branch Picker search & filter inputs
  const branchSearch = resolveElement(ctx, "branchSearchInput");
  if (branchSearch) {
    branchSearch.addEventListener("input", () =>
      renderBranchLists(ctx, config, (name) => checkoutBranch(ctx, state, name)),
    );
  }
  const chkHideOthers = resolveElement(ctx, "chkHideOtherUsers");
  if (chkHideOthers) {
    chkHideOthers.addEventListener("change", () =>
      renderBranchLists(ctx, config, (name) => checkoutBranch(ctx, state, name)),
    );
  }
  const branchSelect = resolveElement(ctx, "branchSelect");
  if (branchSelect) {
    branchSelect.addEventListener("change", () =>
      checkoutBranch(ctx, state, branchSelect.value),
    );
  }
  const modalSelectAll = resolveElement(ctx, "modalSelectAll");
  if (modalSelectAll) {
    modalSelectAll.addEventListener("change", () =>
      toggleModalSelectAll(ctx, Boolean(modalSelectAll.checked)),
    );
  }

  const isDescendantOf = (ancestor, node) => {
    let cur = node;
    while (cur) {
      if (cur === ancestor) return true;
      cur = cur.parentNode;
    }
    return false;
  };

  // Bind global delegated `[data-action]` buttons across HUD, toolbars, and modals
  const doc = ctx.getDocument();
  if (doc && doc.body) {
    bindDelegatedEvent(doc.body, "click", "[data-action]", (event, actionEl) => {
      // Skip smartlogList and filesContainer actions already handled by their dedicated delegates
      const sl = resolveElement(ctx, "smartlogList");
      const fc = resolveElement(ctx, "filesContainer");
      if ((sl && isDescendantOf(sl, actionEl)) || (fc && isDescendantOf(fc, actionEl))) {
        return;
      }

      const action = actionEl.dataset.action;
      switch (action) {
        case "sync-repo":
          syncRepository(ctx);
          break;
        case "rebase-repo":
          rebaseRepository(ctx);
          break;
        case "open-commit-modal":
          openCommitModal(
            ctx,
            state,
            actionEl.dataset.amend === "true",
            loadFilesForActiveCommit,
          );
          break;
        case "close-commit-modal":
          closeCommitModal(ctx);
          break;
        case "submit-commit-modal":
          submitCommitModal(ctx, state);
          break;
        case "discard-modal-selected":
          discardSelectedFromModal(ctx, state, loadFilesForActiveCommit);
          break;
        case "toggle-pane":
          togglePane(actionEl.dataset.pane || "");
          break;
        case "open-branch-modal":
          openBranchModal(ctx, config, (name) => checkoutBranch(ctx, state, name));
          break;
        case "close-branch-modal":
          closeBranchModal(ctx);
          break;
        case "copy-current-branch":
          copyToClipboard(ctx, state.currentBranch, state.currentBranch);
          break;
        case "goto-commit":
          openGotoModal(ctx, selectCommit);
          break;
        case "open-code-review":
          openSelectedInCodeReview();
          break;
        case "open-issue-tracker":
          openIssueTracker();
          break;
        case "create-pr":
          createPullRequests(ctx, state, prTimerRef);
          break;
        case "unlink-pr":
          unlinkPullRequests(ctx, state);
          break;
        case "close-pr-modal":
          closePrSubmitModal(ctx, prTimerRef);
          break;
        case "finish-pr-modal":
          finishPrSubmitModal(ctx, prTimerRef);
          break;
        case "toggle-merged":
          toggleMergedCommits(ctx);
          break;
        case "select-all-commits":
          selectAllCommits(ctx, state);
          break;
        case "select-none-commits":
          selectNoneCommits(ctx, state);
          break;
        case "split-commit":
          splitActiveCommit(ctx, state);
          break;
        case "combine-commits":
          combineSelectedCommits(ctx, state);
          break;
        case "discard-working-selected":
          discardSelectedWorkingFiles(ctx, loadFilesForActiveCommit);
          break;
        case "quick-commit-staged":
          quickCommitStaged(ctx);
          break;
        case "copy-active-file":
          if (state.activeFile) {
            copyToClipboard(ctx, state.activeFile, state.activeFile);
          }
          break;
        case "open-vscode":
          if (typeof event.preventDefault === "function") {
            event.preventDefault();
          }
          openInVsCode(1);
          break;
        case "set-diff-mode":
          setDiffMode(actionEl.dataset.mode || "side_by_side");
          break;
        case "toggle-word-wrap":
          toggleWordWrap();
          break;
        case "copy-diff-snippet":
          if (state.currentDiff) {
            const snippet = state.currentDiff.raw_diff || state.currentDiff.full_content || "";
            copyToClipboard(ctx, snippet, "Diff snippet");
          }
          break;
        default:
          break;
      }
    });
  }

  // Listen for child workstation iframe close/open messages & keyboard shortcuts
  ctx.addViewportListener("message", (event) => {
    const payload = event && event.data;
    if (!payload) {
      return;
    }
    if (payload.action === "close_workstation" || payload.type === "close_modal") {
      closeWorkstationModal();
    } else if (payload.action === "open_workstation" && typeof payload.url === "string") {
      openWorkstationModal(payload.url);
    }
  });

  ctx.getDocument()?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      const wsModal = resolveElement(ctx, "workstationModal");
      if (wsModal && wsModal.style.display === "flex") {
        closeWorkstationModal();
        return;
      }
    }
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    const activeEl = doc ? doc.activeElement : null;
    const tag = activeEl && activeEl.tagName ? activeEl.tagName.toUpperCase() : "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return;
    }
    if (event.key === "[") {
      togglePane("smartlog");
    } else if (event.key === "]") {
      togglePane("files");
    } else if (typeof event.key === "string" && event.key.toLowerCase() === "w") {
      toggleWordWrap();
    }
  });

  // Boot state synchronization
  updateMergedVisibility(ctx);
  if (config.initialSyncDone === false) {
    performInitialSync(ctx, false, false, issueLabel);
  }
  updateSelectedCount(ctx, state);

  const commitArea = resolveElement(ctx, "workingTreeCommitArea");
  if (commitArea) {
    commitArea.style.display = state.activeCommit === "working" ? "flex" : "none";
  }

  loadFilesForActiveCommit();

  autoSyncTimer = ctx.setInterval(syncWorkingAndCommitsSilently, AUTO_SYNC_INTERVAL_MS);
  ctx.getDocument()?.addEventListener("visibilitychange", () => {
    if (doc && doc.visibilityState === "visible") {
      syncWorkingAndCommitsSilently();
    }
  });
  ctx.addViewportListener("focus", () => {
    syncWorkingAndCommitsSilently();
  });

  const params = parseQueryParams(ctx.getLocation().search);
  const urlCommit = params.commit || params.goto;
  if (urlCommit && urlCommit !== state.activeCommit) {
    selectCommit(urlCommit);
  }

  return {
    state,
    selectCommit,
    selectFile,
    setDiffMode,
    togglePane,
    toggleWordWrap,
    dispose() {
      if (autoSyncTimer !== null) {
        ctx.clearInterval(autoSyncTimer);
      }
      if (prTimerRef.intervalId !== null) {
        ctx.clearInterval(prTimerRef.intervalId);
      }
    },
  };
}

const defaultCtx = getRuntimeContext();
if (defaultCtx.getDocument()) {
  if (defaultCtx.getDocument().readyState === "loading") {
    defaultCtx.getDocument()?.addEventListener("DOMContentLoaded", () => initDiffViewApp(defaultCtx));
  } else {
    initDiffViewApp(defaultCtx);
  }
}
