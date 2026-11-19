/**
 * Shared Code Review Workstation Root Entrypoint (`code_review_app.js`).
 *
 * Orchestrates Commit Stream selection, Changed Files proximity search, Multi-mode
 * Diff rendering (`side_by_side`, `unified`, `full_file`, `is_binary`, `is_oversized`),
 * Inline Review Comment Threads, Quake/Xerxes CLI Console (`Ctrl+R` fuzzy history &
 * `@file` autocomplete), Code Search modal, Verdict controls, and 3s silent auto-sync.
 * Parameterized via `#app-boot-config` so `hardware` and `firmware` run 100%
 * byte-identical ES module code.
 */

import {
  applyIframeContextClass,
  bindDelegatedEvent,
  clearChildren,
  createEl,
  resolveElement,
} from "../core/dom.js";
import { bindModalBackdropClose } from "../core/modal.js";
import { setupPanelResizer } from "../core/resizer.js";
import { getRuntimeContext } from "../core/runtime_context.js";
import { copyToClipboard, showToast } from "../core/toast.js";
import { applyUiScale } from "../core/ui_scale.js";
import { detectLanguage, renderDiff } from "../diff/diff_engine.js";
import { logCli, setupCliDrawer, updateTargetUI } from "./cli_drawer.js";
import {
  createInlineCommentCard,
  deleteReviewComment,
  editReviewComment,
  isCommentVisible,
  postReviewComment,
  updateReviewCommentStatus,
} from "./comment_threads.js";
import {
  commentMatchesCommit,
  getFileChanges,
  isLfsFile,
  renderCommitsList,
  renderFilesList,
  setFileReviewStatus,
} from "./file_tree.js";
import {
  exportReviewMarkdown,
  setReviewVerdict,
  syncReviewFeedback,
  updateSessionMetricsUI,
} from "./verdict_controller.js";

const UI_SCALES = Object.freeze(["75%", "80%", "90%", "100%", "110%", "125%", "150%"]);
const UI_SCALE_STORAGE_KEY = "ui_scale";
const WORD_WRAP_STORAGE_KEY = "quake_diff_word_wrap";
const COMMITS_WIDTH_STORAGE_KEY = "codereview_commits_width";
const FILES_WIDTH_STORAGE_KEY = "codereview_files_width";
const CLI_HEIGHT_STORAGE_KEY = "codereview_cli_height";
const SBS_SPLIT_STORAGE_KEY = "cr_sbs_split_ratio";
const AUTO_SYNC_INTERVAL_MS = 3000;
const SCROLL_DEBOUNCE_MS = 50;

/**
 * Parse URL query parameters without referencing the `URLSearchParams` browser global.
 *
 * @param {string} searchStr - `location.search` string (e.g. `"?revisions=abc&bug_id=12"`).
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
      const k = decodeURIComponent(pair.slice(0, eqIdx));
      const v = decodeURIComponent(pair.slice(eqIdx + 1));
      result[k] = v;
    }
  }
  return result;
}

/**
 * Boot and bind the Code Review Workstation UI against `ctx`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} [ctx] - Explicit runtime context.
 * @returns {object} Controller handle (`state`, `goto`, `selectCommit`, `setDiffMode`, `dispose`).
 */
export function initCodeReviewApp(ctx = getRuntimeContext()) {
  const config = ctx.getBootConfig() || {};
  const repoName = config.repoName || "repo";
  const issueKind = config.issueKind === "worm" ? "worm" : "bug";
  const trackerRoute = config.trackerRoute || (issueKind === "worm" ? "/worms" : "/bugs");
  const issueLabel = config.issueLabel || (issueKind === "worm" ? "WORM" : "BUG");
  const openIssueApi = config.openIssueApi || (issueKind === "worm" ? "/api/open_worm" : "/api/open_bug");
  const singleCommitBoot = Boolean(config.singleCommit);

  const state = {
    repoName,
    session: null,
    commits: [],
    files: [],
    commitFiles: {},
    openedFilesByCommit: {},
    allReviewedNotified: {},
    selectedCommit: "working",
    selectedFile: null,
    diffMode: "side_by_side",
    currentDiff: null,
    activeLanguage: "plaintext",
    selectedRange: { start: null, end: null },
    currentSeverity: "MUST_FIX",
    cmdHistory: [],
    cmdHistoryIdx: -1,
    panes: {
      commits: !singleCommitBoot,
      files: true,
      cli: true,
    },
    lastCommitsFingerprint: undefined,
    lastSessionFingerprint: undefined,
  };

  let activeSearchHitIndex = -1;
  let autoSyncTimer = null;
  let isAutoSyncing = false;

  applyIframeContextClass(ctx);
  const doc = ctx.getDocument();
  const storage = ctx.getStorage();

  // --- UI Scale ---
  const applyScaleLabel = (rawLabel) => {
    const label = UI_SCALES.includes(rawLabel) ? rawLabel : "100%";
    const pct = Number.parseInt(label, 10) || 100;
    applyUiScale(ctx, pct, { storageKey: UI_SCALE_STORAGE_KEY, persistValue: label });
    const sel = resolveElement(ctx, "uiScaleSelect");
    if (sel && sel.value !== label) {
      sel.value = label;
    }
  };

  const adjustScale = (delta) => {
    const cur = storage.getItem(UI_SCALE_STORAGE_KEY) || "100%";
    let idx = UI_SCALES.indexOf(cur);
    if (idx === -1) idx = UI_SCALES.indexOf("100%");
    const nextIdx = Math.max(0, Math.min(UI_SCALES.length - 1, idx + delta));
    applyScaleLabel(UI_SCALES[nextIdx]);
  };

  applyScaleLabel(storage.getItem(UI_SCALE_STORAGE_KEY) || "100%");
  const uiScaleSelect = resolveElement(ctx, "uiScaleSelect");
  if (uiScaleSelect) {
    uiScaleSelect.addEventListener("change", () => applyScaleLabel(uiScaleSelect.value));
  }

  // --- Word Wrap ---
  const updateWrapButtonState = (wrapped) => {
    const btn = resolveElement(ctx, "btnToggleWrap");
    if (btn) {
      btn.textContent = wrapped ? "Wrap: On" : "Wrap: Off";
      btn.classList.toggle("quake-btn-gold", wrapped);
      btn.classList.toggle("quake-btn-active", wrapped);
    }
  };

  const initWordWrap = () => {
    const wrapped = storage.getItem(WORD_WRAP_STORAGE_KEY) === "true";
    if (doc && doc.body) {
      doc.body.classList.toggle("diff-word-wrap", wrapped);
    }
    updateWrapButtonState(wrapped);
  };

  const toggleWordWrap = () => {
    if (!doc || !doc.body) return;
    const wrapped = doc.body.classList.toggle("diff-word-wrap");
    storage.setItem(WORD_WRAP_STORAGE_KEY, wrapped ? "true" : "false");
    updateWrapButtonState(wrapped);
  };

  // --- Issue Tracker Back-Navigation & Workstation Closing ---
  const resolveDefectQueryId = () => {
    const params = parseQueryParams(ctx.getLocation().search);
    return params.worm_id || params.bug_id || "";
  };

  const isOpenedFromTracker = () => {
    const params = parseQueryParams(ctx.getLocation().search);
    return (
      params.from === "bugs" ||
      params.from === "worms" ||
      Boolean(params.bug_id) ||
      Boolean(params.worm_id)
    );
  };

  const formatDefectId = (rawId) => {
    if (!rawId) return "";
    const upper = String(rawId).toUpperCase();
    if (upper.startsWith(`${issueLabel}-`)) {
      return upper;
    }
    return `${issueLabel}-${upper.replace(/^(BUG|WORM)-/, "")}`;
  };

  const returnToIssueTracker = () => {
    const rawId = resolveDefectQueryId();
    const cleanId = formatDefectId(rawId);
    const hash = cleanId ? `#${cleanId}` : "";
    const targetUrl = `${trackerRoute}${hash}`;
    const targetName = `${repoName}_${issueKind}_tracker`;
    if (ctx.isEmbeddedInFrame()) {
      ctx.postParentMessage({ action: "open_workstation", url: targetUrl, targetName });
      ctx.navigate(targetUrl);
    } else {
      ctx.navigate(targetUrl);
    }
  };

  const initTrackerBackButtons = () => {
    if (!isOpenedFromTracker()) {
      return;
    }
    const rawId = resolveDefectQueryId();
    const cleanId = formatDefectId(rawId);
    const defaultName = issueKind === "worm" ? "Worms" : "Bug Report";
    const label = cleanId ? `◀ Back to ${cleanId}` : `◀ Back to ${defaultName}`;
    for (const btnId of ["btnBackToBugsHeader", "btnBackToBugsToolbar"]) {
      const btn = resolveElement(ctx, btnId);
      if (btn) {
        btn.style.display = "inline-flex";
        btn.textContent = label;
        btn.setAttribute("title", `Return to ${cleanId || defaultName}`);
      }
    }
  };

  const openIssueTracker = async () => {
    let targetUrl = trackerRoute;
    try {
      const res = await ctx.postJson(openIssueApi, {});
      if (res && res.url) {
        targetUrl = res.url;
      }
    } catch (err) {
      logCli(ctx, `Opening ${trackerRoute} directly (${err.message})`, "dim");
    }
    if (ctx.isEmbeddedInFrame()) {
      ctx.postParentMessage({
        action: "open_workstation",
        url: targetUrl,
        targetName: `${repoName}_${issueKind}_tracker`,
      });
    }
    ctx.navigate(targetUrl);
  };

  const closeWorkstation = () => {
    if (isOpenedFromTracker()) {
      returnToIssueTracker();
      return;
    }
    if (ctx.isEmbeddedInFrame()) {
      ctx.postParentMessage({ action: "close_workstation", type: "close_modal" });
      return;
    }
    ctx.navigate("/");
  };

  // --- Pane & CLI Drawer Controls ---
  const ensureCliOpen = () => {
    state.panes.cli = true;
    const drawer = resolveElement(ctx, "cliDrawer");
    if (drawer) {
      drawer.classList.remove("minimized");
    }
  };

  const toggleCliDrawer = () => {
    state.panes.cli = !state.panes.cli;
    const drawer = resolveElement(ctx, "cliDrawer");
    if (drawer) {
      drawer.classList.toggle("minimized", !state.panes.cli);
    }
  };

  const togglePane = (pane) => {
    if (pane === "commits") {
      state.panes.commits = !state.panes.commits;
      const el = resolveElement(ctx, "paneCommits");
      const resizer = resolveElement(ctx, "resizerCommits");
      if (el) {
        el.classList.toggle("collapsed", !state.panes.commits);
        if (state.panes.commits) {
          const savedW = storage.getItem(COMMITS_WIDTH_STORAGE_KEY);
          if (savedW) el.style.width = `${savedW}px`;
        }
      }
      if (resizer) resizer.classList.toggle("hidden", !state.panes.commits);
      const btn = resolveElement(ctx, "btnToggleCommits");
      if (btn) btn.classList.toggle("quake-btn-active", state.panes.commits);
    } else if (pane === "files") {
      state.panes.files = !state.panes.files;
      const el = resolveElement(ctx, "paneFiles");
      const resizer = resolveElement(ctx, "resizerFiles");
      if (el) {
        el.classList.toggle("collapsed", !state.panes.files);
        if (state.panes.files) {
          const savedW = storage.getItem(FILES_WIDTH_STORAGE_KEY);
          if (savedW) el.style.width = `${savedW}px`;
        }
      }
      if (resizer) resizer.classList.toggle("hidden", !state.panes.files);
      const btn = resolveElement(ctx, "btnToggleFiles");
      if (btn) btn.classList.toggle("quake-btn-active", state.panes.files);
    }
  };

  const toggleFocusMode = () => {
    const isFocused = !state.panes.commits && !state.panes.files;
    state.panes.commits = isFocused;
    state.panes.files = isFocused;

    const commitsPane = resolveElement(ctx, "paneCommits");
    const filesPane = resolveElement(ctx, "paneFiles");
    const resizerCommits = resolveElement(ctx, "resizerCommits");
    const resizerFiles = resolveElement(ctx, "resizerFiles");

    if (commitsPane) {
      commitsPane.classList.toggle("collapsed", !state.panes.commits);
      if (state.panes.commits) {
        const savedW = storage.getItem(COMMITS_WIDTH_STORAGE_KEY);
        if (savedW) commitsPane.style.width = `${savedW}px`;
      }
    }
    if (filesPane) {
      filesPane.classList.toggle("collapsed", !state.panes.files);
      if (state.panes.files) {
        const savedW = storage.getItem(FILES_WIDTH_STORAGE_KEY);
        if (savedW) filesPane.style.width = `${savedW}px`;
      }
    }
    if (resizerCommits) resizerCommits.classList.toggle("hidden", !state.panes.commits);
    if (resizerFiles) resizerFiles.classList.toggle("hidden", !state.panes.files);

    const btnFocus = resolveElement(ctx, "btnFocus");
    if (btnFocus) btnFocus.classList.toggle("quake-btn-active", !isFocused);
    const btnCommits = resolveElement(ctx, "btnToggleCommits");
    if (btnCommits) btnCommits.classList.toggle("quake-btn-active", state.panes.commits);
    const btnFiles = resolveElement(ctx, "btnToggleFiles");
    if (btnFiles) btnFiles.classList.toggle("quake-btn-active", state.panes.files);
  };

  // --- Active File Actions (Copy & VS Code) ---
  const resolveAbsoluteFilePath = (filePath) => {
    const repoRoot =
      (state.session && state.session.repo_root) || config.repoRoot || "";
    if (!repoRoot || filePath.startsWith("/")) {
      return filePath;
    }
    return `${repoRoot.replace(/\/+$/, "")}/${filePath.replace(/^\/+/, "")}`;
  };

  const updateActiveFileActions = (filePath) => {
    if (!filePath) return;
    const fullPath = resolveAbsoluteFilePath(filePath);
    const vscodeUrl = `vscode://file${fullPath.startsWith("/") ? "" : "/"}${fullPath}`;
    const btnVsCode = resolveElement(ctx, "btnOpenVsCode");
    if (btnVsCode) {
      btnVsCode.setAttribute("href", vscodeUrl);
    }
  };

  const openInVsCode = async (line = 1) => {
    const filePath = state.selectedFile;
    if (!filePath) return;
    const repoRoot =
      (state.session && state.session.repo_root) || config.repoRoot || "";
    if (!repoRoot && !filePath.startsWith("/")) {
      showToast(ctx, "Error: Repository root is not configured", "error");
      return;
    }
    const fullPath = resolveAbsoluteFilePath(filePath);
    const vscodeUrl = `vscode://file${fullPath.startsWith("/") ? "" : "/"}${fullPath}${
      line > 1 ? `:${line}` : ""
    }`;

    try {
      const data = await ctx.postJson("/api/open-vscode", { file: fullPath, line });
      if (data && data.status === "ok") {
        showToast(ctx, `Opened in VS Code: ${filePath}`, "success");
        return;
      }
    } catch (err) {
      logCli(ctx, `VS Code backend fallback to URL scheme (${err.message})`, "dim");
    }
    ctx.navigate(vscodeUrl);
  };

  // --- Session, Commits, Files, & Diff Loading ---
  const loadSession = async () => {
    try {
      const params = parseQueryParams(ctx.getLocation().search);
      const revs = params.revisions || params.commit || "";
      const sessionUrl = revs
        ? `/api/session?revisions=${encodeURIComponent(revs)}`
        : "/api/session";
      state.session = await ctx.fetchJson(sessionUrl);
      updateSessionMetricsUI(ctx, state, config);
    } catch (err) {
      logCli(ctx, `Error loading review session: ${err.message}`, "red");
    }
  };

  const editCommentViaCli = (commentId) => {
    const comments = (state.session && state.session.comments) || [];
    const found = comments.find((c) => c.id === commentId);
    if (!found) return;
    ensureCliOpen();
    const input = resolveElement(ctx, "cliInput");
    if (input) {
      input.value = `edit ${commentId} ${found.body}`;
      input.focus();
      if (typeof input.setSelectionRange === "function") {
        input.setSelectionRange(input.value.length, input.value.length);
      }
    }
    logCli(ctx, `> Editing comment [${commentId}]. Update text and press Enter to save.`, "gold");
  };

  const handleDeleteComment = async (commentId) => {
    try {
      const data = await deleteReviewComment(ctx, commentId);
      if (data && data.status === "ok") {
        logCli(ctx, `Deleted comment ${commentId}`, "dim");
        await loadSession();
        renderCurrentDiff();
        refreshFilesUI();
      }
    } catch (err) {
      logCli(ctx, `Error deleting comment: ${err.message}`, "red");
    }
  };

  const handleCommentStatusChange = async (commentId, targetStatus, notes = "") => {
    try {
      const data = await updateReviewCommentStatus(ctx, commentId, targetStatus, notes);
      if (data && data.status === "ok") {
        logCli(ctx, `> Comment [${commentId}] status -> [${targetStatus}]`, "green");
        await loadSession();
        renderCurrentDiff();
        refreshFilesUI();
        showToast(ctx, `Comment ${commentId} -> ${targetStatus}`, "success");
      } else {
        logCli(
          ctx,
          `Error updating comment status: ${(data && data.error) || "Unknown error"}`,
          "red",
        );
      }
    } catch (err) {
      logCli(ctx, `Network error updating comment status: ${err.message}`, "red");
    }
  };

  const renderCurrentDiff = () => {
    if (!state.currentDiff) {
      return;
    }
    const diffPayload = {
      ...state.currentDiff,
      file_path: state.selectedFile || state.currentDiff.file_path || "",
      commit: state.selectedCommit || "working",
    };
    const showClosedCb = resolveElement(ctx, "showClosedCommentsCb");
    const showClosed = showClosedCb ? Boolean(showClosedCb.checked) : false;
    const fileComments = ((state.session && state.session.comments) || []).filter(
      (c) =>
        c.file_path === state.selectedFile &&
        commentMatchesCommit(c, state.selectedCommit) &&
        isCommentVisible(c, showClosed),
    );
    const activeRange =
      state.selectedRange && state.selectedRange.start
        ? {
            start: state.selectedRange.start,
            end: state.selectedRange.end || state.selectedRange.start,
          }
        : null;

    renderDiff(ctx, "diffContent", diffPayload, {
      mode: state.diffMode,
      storageKey: SBS_SPLIT_STORAGE_KEY,
      selectedRange: activeRange,
      comments: fileComments,
      renderCommentCard: (comment) =>
        createInlineCommentCard(ctx, comment, {
          language: state.activeLanguage,
          authorBlacklist: config.authorBlacklist || [],
          onStatusChange: (cid, nextStatus) => handleCommentStatusChange(cid, nextStatus),
          onEdit: editCommentViaCli,
          onDelete: handleDeleteComment,
          onGotoRef: (fileRef, lineRef) => goto(fileRef, lineRef),
        }),
      onLineClick: ({ line, shiftKey }) => {
        if (shiftKey && state.selectedRange.start) {
          state.selectedRange.end = line;
        } else {
          state.selectedRange.start = line;
          state.selectedRange.end = line;
        }
        ensureCliOpen();
        updateTargetUI(ctx, state, true);
        renderCurrentDiff();
        const cliInput = resolveElement(ctx, "cliInput");
        if (cliInput) {
          cliInput.focus();
          const s = Math.min(state.selectedRange.start, state.selectedRange.end);
          const e = Math.max(state.selectedRange.start, state.selectedRange.end);
          cliInput.placeholder =
            s === e
              ? `Type comment for L${s} and press Enter...`
              : `Type comment for L${s}-L${e} and press Enter...`;
        }
      },
    });
  };

  const refreshCommitsUI = () => {
    renderCommitsList(ctx, state, config, {
      onSelectCommit: (sha) => selectCommit(sha),
      onCopySha: (sha) => copyToClipboard(ctx, sha, `Copied: ${sha}`),
    });
  };

  const refreshFilesUI = () => {
    renderFilesList(ctx, state, {
      onSelectFile: (filePath) => goto(filePath),
    });
  };

  const loadDiff = async () => {
    if (!state.selectedFile) return;
    const pathEl = resolveElement(ctx, "activeFilePath");
    if (pathEl) pathEl.textContent = state.selectedFile;
    const actionsEl = resolveElement(ctx, "activeFileActions");
    if (actionsEl) actionsEl.style.display = "inline-flex";
    updateActiveFileActions(state.selectedFile);
    updateSessionMetricsUI(ctx, state, config);

    try {
      const url = `/api/diff?commit=${encodeURIComponent(state.selectedCommit)}&file=${encodeURIComponent(state.selectedFile)}`;
      state.currentDiff = await ctx.fetchJson(url);
      state.activeLanguage = detectLanguage(state.selectedFile);

      const langBadge = resolveElement(ctx, "activeFileLang");
      if (langBadge) {
        langBadge.textContent = state.activeLanguage.toUpperCase();
        langBadge.style.display = "inline-block";
      }

      const activeFileObj = (state.files || []).find((f) => f.path === state.selectedFile);
      const lfsBadge = resolveElement(ctx, "activeFileLfs");
      if (lfsBadge) {
        lfsBadge.style.display = isLfsFile(activeFileObj || state.selectedFile, state.currentDiff)
          ? "inline-flex"
          : "none";
      }

      renderCurrentDiff();
    } catch (err) {
      logCli(ctx, `Error loading diff: ${err.message}`, "red");
    }
  };

  const scrollLineIntoView = (lineNo) => {
    ctx.setTimeout(() => {
      if (!doc) return;
      const row = doc.querySelector(`[data-line="${lineNo}"]`);
      if (row && typeof row.scrollIntoView === "function") {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, SCROLL_DEBOUNCE_MS);
  };

  const applyChange = (change, isNewFile = false) => {
    state.selectedRange = { start: change.startLine, end: change.endLine };
    ensureCliOpen();
    updateTargetUI(ctx, state, false);
    renderCurrentDiff();
    scrollLineIntoView(change.startLine);

    const filePrefix = isNewFile ? `[${state.selectedFile}] ` : "";
    const lineStr =
      change.startLine === change.endLine
        ? `L${change.startLine}`
        : `L${change.startLine}-L${change.endLine}`;
    logCli(
      ctx,
      `${filePrefix}Jumped to change (${String(change.type || "hunk").toUpperCase()}) at ${lineStr}`,
      "cyan",
    );

    const cliInput = resolveElement(ctx, "cliInput");
    if (cliInput) {
      cliInput.focus();
      cliInput.placeholder = `Type comment for ${lineStr} and press Enter...`;
    }
  };

  const jumpToLine = (lineNo) => {
    state.selectedRange = { start: lineNo, end: lineNo };
    ensureCliOpen();
    updateTargetUI(ctx, state, false);
    renderCurrentDiff();
    scrollLineIntoView(lineNo);

    const cliInput = resolveElement(ctx, "cliInput");
    if (cliInput) {
      cliInput.focus();
      cliInput.placeholder = `Type comment for L${lineNo} and press Enter...`;
    }
  };

  const goto = async (target, targetLine = null) => {
    if (!target) return;
    let fileTarget = String(target).trim();
    let lineTarget = targetLine;

    if (fileTarget.startsWith("@")) {
      fileTarget = fileTarget.slice(1).trim();
    }
    if (fileTarget.startsWith("[") && fileTarget.endsWith("]")) {
      fileTarget = fileTarget.slice(1, -1).trim();
    }

    if (/^\d+$/.test(fileTarget) && state.selectedFile) {
      lineTarget = Number.parseInt(fileTarget, 10);
      fileTarget = state.selectedFile;
    } else if (fileTarget.includes(":")) {
      const colonIdx = fileTarget.indexOf(":");
      const rawLine = fileTarget.slice(colonIdx + 1).trim().replace(/^L/i, "");
      fileTarget = fileTarget.slice(0, colonIdx).trim();
      lineTarget = Number.parseInt(rawLine, 10);
    }

    let matchedFile = state.files.find((f) => f.path === fileTarget);
    if (!matchedFile) {
      const lowerTarget = fileTarget.toLowerCase();
      matchedFile = state.files.find(
        (f) =>
          f.path.toLowerCase().endsWith(lowerTarget) ||
          f.path.toLowerCase().includes(lowerTarget),
      );
    }

    const activePath = matchedFile ? matchedFile.path : fileTarget;
    state.selectedFile = activePath;

    if (state.selectedCommit && activePath) {
      if (!state.openedFilesByCommit[state.selectedCommit]) {
        state.openedFilesByCommit[state.selectedCommit] = new Set();
      }
      state.openedFilesByCommit[state.selectedCommit].add(activePath);
      refreshCommitsUI();

      const openedSet = state.openedFilesByCommit[state.selectedCommit];
      const allReviewed =
        state.files.length > 0 && state.files.every((f) => openedSet.has(f.path));
      if (allReviewed && !state.allReviewedNotified[state.selectedCommit]) {
        state.allReviewedNotified[state.selectedCommit] = true;
        logCli(
          ctx,
          `✨ All ${state.files.length} changed file(s) in commit ${state.selectedCommit.slice(0, 8)} have been reviewed! You can now move to the next commit.`,
          "gold",
        );
        ctx
          .fetchRaw(`/api/commit_reviewed?commit=${encodeURIComponent(state.selectedCommit)}`, {
            method: "POST",
          })
          .catch((err) => {
            logCli(ctx, `Note: commit_reviewed notification skipped (${err.message})`, "dim");
          });
      }
    }

    state.selectedRange = { start: null, end: null };
    updateTargetUI(ctx, state, false);
    refreshFilesUI();
    await loadDiff();

    if (lineTarget !== null && Number.isFinite(lineTarget) && lineTarget > 0) {
      jumpToLine(lineTarget);
      logCli(ctx, `> goto @${activePath}:${lineTarget}`, "cyan");
    } else {
      const changes = getFileChanges(state.currentDiff);
      if (changes.length > 0) {
        applyChange(changes[0], true);
      }
      logCli(ctx, `> goto @${activePath}`, "cyan");
    }
  };

  const selectCommit = async (commitHash) => {
    state.selectedCommit = commitHash;
    refreshCommitsUI();
    logCli(ctx, `Selected revision: ${commitHash}`, "cyan");

    try {
      state.files = await ctx.fetchJson(`/api/files?commit=${encodeURIComponent(commitHash)}`);
      state.commitFiles[commitHash] = state.files.map((f) => f.path);
      refreshFilesUI();
      refreshCommitsUI();

      if (state.files.length > 0) {
        await goto(state.files[0].path);
      } else {
        const diffEl = resolveElement(ctx, "diffContent");
        if (!diffEl) return;
        clearChildren(diffEl);
        const currentCommit = (state.commits || []).find((c) => c.commit_hash === commitHash);
        if (
          currentCommit &&
          Array.isArray(currentCommit.ignored_files) &&
          currentCommit.ignored_files.length > 0
        ) {
          diffEl.appendChild(
            createEl(ctx, "div", {
              style: {
                padding: "50px 20px",
                textAlign: "center",
                color: "var(--quake-text-dim)",
              },
              children: [
                createEl(ctx, "div", {
                  style: { fontSize: "2.2em", marginBottom: "15px" },
                  text: "📋",
                }),
                createEl(ctx, "div", {
                  style: {
                    color: "var(--quake-gold)",
                    fontSize: "1.15em",
                    fontWeight: "bold",
                    marginBottom: "8px",
                  },
                  text: "Issue Tracker & Documentation Update Only",
                }),
                createEl(ctx, "div", {
                  style: {
                    fontSize: "0.9em",
                    maxWidth: "550px",
                    margin: "0 auto",
                    lineHeight: "1.6",
                  },
                  text: `All changes in revision ${currentCommit.short_hash} are to tracking files (${currentCommit.ignored_files.join(", ")}), which are hidden from code review.`,
                }),
              ],
            }),
          );
        } else {
          diffEl.appendChild(
            createEl(ctx, "div", {
              style: {
                padding: "40px",
                textAlign: "center",
                color: "var(--quake-text-dim)",
              },
              text: `No files modified in revision ${commitHash}.`,
            }),
          );
        }
      }
    } catch (err) {
      logCli(ctx, `Error loading files: ${err.message}`, "red");
    }
  };

  const loadCommits = async () => {
    try {
      const params = parseQueryParams(ctx.getLocation().search);
      const revs = params.revisions || params.commit || "";
      const commitsUrl = revs
        ? `/api/commits?revisions=${encodeURIComponent(revs)}`
        : "/api/commits";
      state.commits = await ctx.fetchJson(commitsUrl);
      refreshCommitsUI();

      if (state.commits.length > 0) {
        let targetCommit = state.commits[0].commit_hash;
        if (revs) {
          const firstReq = revs.split(",")[0].trim();
          const matched = state.commits.find(
            (c) =>
              c.commit_hash.startsWith(firstReq) ||
              firstReq.startsWith(c.commit_hash) ||
              c.short_hash === firstReq,
          );
          if (matched) {
            targetCommit = matched.commit_hash;
          }
        }
        await selectCommit(targetCommit);
      }

      if (state.commits.length <= 1) {
        state.panes.commits = false;
        const paneEl = resolveElement(ctx, "paneCommits");
        if (paneEl) paneEl.classList.add("collapsed");
        const resizerEl = resolveElement(ctx, "resizerCommits");
        if (resizerEl) resizerEl.classList.add("hidden");
        const btnToggle = resolveElement(ctx, "btnToggleCommits");
        if (btnToggle) btnToggle.classList.remove("quake-btn-active");
      }
    } catch (err) {
      logCli(ctx, `Error loading commits: ${err.message}`, "red");
    }
  };

  // --- Navigation & Comment Actions ---
  const navigateFile = async (direction) => {
    if (!state.files.length) return;
    let idx = state.files.findIndex((f) => f.path === state.selectedFile);
    idx += direction;
    if (idx < 0) idx = state.files.length - 1;
    if (idx >= state.files.length) idx = 0;
    await goto(state.files[idx].path);
  };

  const navigateCommit = async (direction) => {
    if (!state.commits || state.commits.length === 0) return;
    let idx = state.commits.findIndex((c) => c.commit_hash === state.selectedCommit);
    if (idx === -1) idx = 0;
    idx += direction;
    if (idx < 0) {
      logCli(ctx, "Already at the first revision in the stack.", "amber");
      return;
    }
    if (idx >= state.commits.length) {
      logCli(ctx, "Already at the latest revision in the stack.", "amber");
      return;
    }
    await selectCommit(state.commits[idx].commit_hash);
  };

  const navigateChange = async (direction) => {
    if (!state.files || state.files.length === 0) return;
    if (!state.selectedFile) {
      await goto(state.files[0].path);
    }

    let changes = getFileChanges(state.currentDiff);
    const curLine = state.selectedRange ? state.selectedRange.start : null;

    if (direction === 1) {
      const nextChange =
        curLine === null || curLine === undefined
          ? changes[0]
          : changes.find((c) => c.startLine > curLine);
      if (nextChange) {
        applyChange(nextChange);
        return;
      }

      let nextIdx = state.files.findIndex((f) => f.path === state.selectedFile) + 1;
      while (nextIdx < state.files.length) {
        await goto(state.files[nextIdx].path);
        changes = getFileChanges(state.currentDiff);
        if (changes.length > 0) {
          applyChange(changes[0], true);
          return;
        }
        nextIdx += 1;
      }
      logCli(ctx, "Reached the last change across all files.", "amber");
      showToast(ctx, "Reached last change");
    } else {
      let prevChange = null;
      if (curLine === null || curLine === undefined) {
        prevChange = changes[changes.length - 1];
      } else {
        for (let idx = changes.length - 1; idx >= 0; idx -= 1) {
          if (
            changes[idx].endLine < curLine ||
            (changes[idx].startLine < curLine && changes[idx].endLine <= curLine)
          ) {
            prevChange = changes[idx];
            break;
          }
        }
      }
      if (prevChange) {
        applyChange(prevChange);
        return;
      }

      let prevIdx = state.files.findIndex((f) => f.path === state.selectedFile) - 1;
      while (prevIdx >= 0) {
        await goto(state.files[prevIdx].path);
        changes = getFileChanges(state.currentDiff);
        if (changes.length > 0) {
          applyChange(changes[changes.length - 1], true);
          return;
        }
        prevIdx -= 1;
      }
      logCli(ctx, "Reached the first change across all files.", "amber");
      showToast(ctx, "Reached first change");
    }
  };

  const setDiffMode = (mode) => {
    state.diffMode = mode;
    const btnSbs = resolveElement(ctx, "btnModeSbs");
    const btnUni = resolveElement(ctx, "btnModeUnified");
    const btnFull = resolveElement(ctx, "btnModeFull");
    if (btnSbs) btnSbs.classList.toggle("quake-btn-active", mode === "side_by_side");
    if (btnUni) btnUni.classList.toggle("quake-btn-active", mode === "unified");
    if (btnFull) btnFull.classList.toggle("quake-btn-active", mode === "full_file");
    renderCurrentDiff();
  };

  const handlePostComment = async (body, severity) => {
    if (!state.selectedFile) {
      logCli(ctx, "Error: Select a file before adding a comment", "red");
      return;
    }
    const rawStart = state.selectedRange.start || 1;
    const rawEnd = state.selectedRange.end || rawStart;
    const startLine = Math.min(rawStart, rawEnd);
    const endLine = Math.max(rawStart, rawEnd);

    let codeSnippet = "";
    if (state.currentDiff && state.currentDiff.full_content) {
      const lines = String(state.currentDiff.full_content).split("\n");
      const sIdx = Math.max(0, startLine - 1);
      const eIdx = Math.min(lines.length, endLine);
      codeSnippet = lines.slice(sIdx, eIdx).join("\n");
    }

    try {
      const data = await postReviewComment(ctx, {
        file_path: state.selectedFile,
        start_line: startLine,
        end_line: endLine,
        severity,
        body,
        author: "Reviewer",
        commit: state.selectedCommit || "working",
        code_snippet: codeSnippet,
      });
      if (data && data.status === "ok") {
        const rangeSuffix = startLine !== endLine ? `-L${endLine}` : "";
        logCli(
          ctx,
          `[${severity}] Added comment to ${state.selectedFile}:L${startLine}${rangeSuffix}`,
          "green",
        );
        await loadSession();
        renderCurrentDiff();
        refreshFilesUI();
        showToast(ctx, `Comment saved [${severity}]`, "success");
      } else {
        logCli(ctx, `Error saving comment: ${(data && data.message) || "Unknown error"}`, "red");
      }
    } catch (err) {
      logCli(ctx, `Error submitting comment: ${err.message}`, "red");
    }
  };

  const handleEditComment = async (commentId, newBody) => {
    try {
      const data = await editReviewComment(ctx, commentId, newBody);
      if (data && data.status === "ok") {
        logCli(ctx, `> Comment [${commentId}] updated successfully.`, "green");
        await loadSession();
        renderCurrentDiff();
        refreshFilesUI();
        showToast(ctx, "Comment updated", "success");
      } else {
        logCli(ctx, `Error updating comment: ${(data && data.error) || "Unknown error"}`, "red");
      }
    } catch (err) {
      logCli(ctx, `Network error updating comment: ${err.message}`, "red");
    }
  };

  const handleSetFileStatus = async (filePath, status) => {
    try {
      const data = await setFileReviewStatus(ctx, filePath, status);
      if (data && data.status === "ok") {
        logCli(ctx, `File status updated: ${filePath} -> [${status}]`, "green");
        await loadSession();
        refreshFilesUI();
      }
    } catch (err) {
      logCli(ctx, `Error updating file status: ${err.message}`, "red");
    }
  };

  const handleVerdict = async (verdict) => {
    await setReviewVerdict(ctx, verdict, {
      logCli: (msg, color) => logCli(ctx, msg, color),
      onSessionUpdated: (nextSession) => {
        state.session = nextSession;
        updateSessionMetricsUI(ctx, state, config);
      },
      onConclude: closeWorkstation,
    });
  };

  // --- Fuzzy Code Search Modal ---
  const closeCodeSearchModal = () => {
    const modal = resolveElement(ctx, "codeSearchResultsModal");
    if (modal) modal.style.display = "none";
  };

  const executeCodeSearch = async () => {
    const inputEl = resolveElement(ctx, "codeSearchInput");
    const query = String((inputEl && inputEl.value) || "").trim();
    if (!query) return;

    const activeFile = state.selectedFile || "";
    logCli(
      ctx,
      `Fuzzy searching code references for: "${query}"${activeFile ? ` (nearest to ${activeFile})` : ""}...`,
      "cyan",
    );

    const modal = resolveElement(ctx, "codeSearchResultsModal");
    const listEl = resolveElement(ctx, "codeSearchResultsList");
    const titleEl = resolveElement(ctx, "codeSearchTitle");
    if (!modal || !listEl) return;

    if (titleEl) {
      titleEl.textContent = activeFile
        ? `Fuzzy Search: "${query}" — Nearest to ${activeFile}`
        : `Fuzzy Search Results for "${query}"`;
    }
    clearChildren(listEl);
    listEl.appendChild(
      createEl(ctx, "div", {
        style: { padding: "15px", color: "var(--quake-text-dim)" },
        text: "Searching...",
      }),
    );
    modal.style.display = "flex";
    activeSearchHitIndex = -1;

    try {
      const commit = state.selectedCommit || "working";
      const data = await ctx.fetchJson(
        `/api/search?q=${encodeURIComponent(query)}&commit=${encodeURIComponent(commit)}&file=${encodeURIComponent(activeFile)}`,
      );
      const results = (data && data.results) || [];
      clearChildren(listEl);

      if (results.length === 0) {
        listEl.appendChild(
          createEl(ctx, "div", {
            style: { padding: "20px", textAlign: "center", color: "var(--quake-text-dim)" },
            text: "No fuzzy occurrences found.",
          }),
        );
        return;
      }

      results.forEach((hit, idx) => {
        const headerChildren = [
          createEl(ctx, "div", {
            className: "search-result-loc",
            text: `${hit.file_path}:${hit.line_number}`,
          }),
        ];
        if (activeFile) {
          const dist = typeof hit.proximity_distance === "number" ? hit.proximity_distance : 99;
          let badgeClass = "search-proximity-other";
          let badgeText = `${dist - 1} HOPS`;
          if (dist === 0 || hit.file_path === activeFile) {
            badgeClass = "search-proximity-active";
            badgeText = "ACTIVE FILE";
          } else if (dist === 1) {
            badgeClass = "search-proximity-near";
            badgeText = "SAME DIR";
          } else if (dist <= 3) {
            badgeClass = "search-proximity-near";
            badgeText = "NEARBY";
          }
          headerChildren.push(
            createEl(ctx, "span", {
              className: `search-proximity-badge ${badgeClass}`,
              text: badgeText,
            }),
          );
        }

        const row = createEl(ctx, "div", {
          className: `search-result-row${idx === 0 ? " active-hit" : ""}`,
          children: [
            createEl(ctx, "div", { className: "search-result-header", children: headerChildren }),
            createEl(ctx, "div", {
              className: "search-result-content",
              text: String(hit.line_content || ""),
            }),
          ],
        });
        row.addEventListener("click", () => {
          goto(`${hit.file_path}:${hit.line_number}`);
          closeCodeSearchModal();
        });
        listEl.appendChild(row);
      });
      activeSearchHitIndex = 0;
    } catch (err) {
      clearChildren(listEl);
      listEl.appendChild(
        createEl(ctx, "div", {
          style: { padding: "15px", color: "var(--quake-red)" },
          text: `Error searching code: ${err.message}`,
        }),
      );
    }
  };

  // --- Silent Background Auto-Sync ---
  const syncReviewSilently = async () => {
    if (isAutoSyncing || (doc && doc.hidden && doc.visibilityState === "hidden")) {
      return;
    }
    isAutoSyncing = true;
    try {
      const params = parseQueryParams(ctx.getLocation().search);
      const revs = params.revisions || params.commit || "";
      const commitsUrl = revs
        ? `/api/commits?type=review&revisions=${encodeURIComponent(revs)}`
        : "/api/commits?type=review";
      const cResp = await ctx.fetchRaw(commitsUrl);
      if (cResp.ok) {
        const commits = await cResp.json();
        const fp = JSON.stringify(
          commits.map((c) => [
            c.commit_hash,
            c.short_hash,
            c.subject,
            c.is_head,
            c.cr_open_count,
            c.cr_resolved_count,
            c.cr_total_count,
            c.cr_reviewed,
          ]),
        );
        if (state.lastCommitsFingerprint === undefined) {
          state.lastCommitsFingerprint = fp;
        } else if (fp !== state.lastCommitsFingerprint) {
          state.lastCommitsFingerprint = fp;
          state.commits = commits;
          refreshCommitsUI();
          if (state.selectedCommit) {
            await selectCommit(state.selectedCommit);
          }
        }
      }

      const sessionUrl = revs
        ? `/api/session?revisions=${encodeURIComponent(revs)}`
        : "/api/session";
      const sResp = await ctx.fetchRaw(sessionUrl);
      if (sResp.ok) {
        const session = await sResp.json();
        const sFp = JSON.stringify([
          session.updated_at,
          session.verdict,
          Object.entries(session.files || {}).map(([p, f]) => [p, f.status, f.notes]),
          (session.comments || []).map((c) => [
            c.id,
            c.status,
            c.resolved,
            c.resolution_notes,
            c.body,
            c.severity,
            c.commit_hash,
            c.file_path,
            c.start_line,
            c.end_line,
          ]),
        ]);
        if (state.lastSessionFingerprint === undefined) {
          state.lastSessionFingerprint = sFp;
        } else if (sFp !== state.lastSessionFingerprint) {
          state.lastSessionFingerprint = sFp;
          state.session = session;
          updateSessionMetricsUI(ctx, state, config);
          refreshFilesUI();
          refreshCommitsUI();
          if (state.selectedFile && state.currentDiff) {
            renderCurrentDiff();
          }
        }
      }
    } catch (err) {
      logCli(ctx, `Auto-sync skipped (${err.message})`, "dim");
    } finally {
      isAutoSyncing = false;
    }
  };

  // --- Setup Resizers, CLI Drawer, & Event Delegation ---
  initWordWrap();
  initTrackerBackButtons();

  const paneCommits = resolveElement(ctx, "paneCommits");
  const resizerCommits = resolveElement(ctx, "resizerCommits");
  if (paneCommits && paneCommits.classList.contains("collapsed") && resizerCommits) {
    resizerCommits.classList.add("hidden");
  }
  const paneFiles = resolveElement(ctx, "paneFiles");
  const resizerFiles = resolveElement(ctx, "resizerFiles");
  if (paneFiles && paneFiles.classList.contains("collapsed") && resizerFiles) {
    resizerFiles.classList.add("hidden");
  }

  setupPanelResizer(ctx, "resizerCommits", "paneCommits", COMMITS_WIDTH_STORAGE_KEY, {
    minSize: 180,
    maxSize: 800,
    axis: "x",
  });
  setupPanelResizer(ctx, "resizerFiles", "paneFiles", FILES_WIDTH_STORAGE_KEY, {
    minSize: 160,
    maxSize: 700,
    axis: "x",
  });
  setupPanelResizer(ctx, "cliResizer", "cliDrawer", CLI_HEIGHT_STORAGE_KEY, {
    minSize: 60,
    maxSize: 650,
    axis: "y",
    invert: true,
    onResize: () => {
      ensureCliOpen();
    },
  });

  const cliControls = setupCliDrawer(ctx, state, {
    goto,
    postComment: handlePostComment,
    editComment: handleEditComment,
    updateCommentStatus: handleCommentStatusChange,
    setFileStatus: handleSetFileStatus,
    navigateChange,
    navigateCommit,
    navigateFile,
    onRangeChanged: () => renderCurrentDiff(),
    exportMarkdown: () => exportReviewMarkdown(ctx, (msg, col) => logCli(ctx, msg, col)),
    setVerdict: handleVerdict,
  });

  bindModalBackdropClose(ctx, "codeSearchResultsModal", closeCodeSearchModal);

  const commitSearchInput = resolveElement(ctx, "commitSearchInput");
  if (commitSearchInput) {
    commitSearchInput.addEventListener("input", refreshCommitsUI);
  }
  const fileSearchInput = resolveElement(ctx, "fileSearchInput");
  if (fileSearchInput) {
    fileSearchInput.addEventListener("input", refreshFilesUI);
  }
  const hideAttachmentsCb = resolveElement(ctx, "hideAttachmentsCb");
  if (hideAttachmentsCb) {
    hideAttachmentsCb.addEventListener("change", refreshFilesUI);
  }
  const showClosedCommentsCb = resolveElement(ctx, "showClosedCommentsCb");
  if (showClosedCommentsCb) {
    showClosedCommentsCb.addEventListener("change", () => {
      updateSessionMetricsUI(ctx, state, config);
      refreshFilesUI();
      renderCurrentDiff();
    });
  }

  const codeSearchInput = resolveElement(ctx, "codeSearchInput");
  const codeSearchClearBtn = resolveElement(ctx, "codeSearchClearBtn");
  if (codeSearchInput) {
    codeSearchInput.addEventListener("input", () => {
      if (codeSearchClearBtn) {
        codeSearchClearBtn.style.display = codeSearchInput.value ? "inline-block" : "none";
      }
    });
    codeSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        executeCodeSearch();
      } else if (event.key === "Escape") {
        codeSearchInput.value = "";
        if (codeSearchClearBtn) codeSearchClearBtn.style.display = "none";
        closeCodeSearchModal();
      }
    });
  }

  const isDescendantOf = (ancestor, node) => {
    let cur = node;
    while (cur) {
      if (cur === ancestor) return true;
      cur = cur.parentNode;
    }
    return false;
  };

  if (doc && doc.body) {
    bindDelegatedEvent(doc.body, "click", "[data-action]", (event, actionEl) => {
      const commitsList = resolveElement(ctx, "commitsList");
      const diffContent = resolveElement(ctx, "diffContent");
      if (
        (commitsList && isDescendantOf(commitsList, actionEl)) ||
        (diffContent && isDescendantOf(diffContent, actionEl))
      ) {
        return;
      }

      const action = actionEl.dataset.action;
      switch (action) {
        case "return-to-tracker":
          returnToIssueTracker();
          break;
        case "open-issue-tracker":
          openIssueTracker();
          break;
        case "sync-feedback":
          syncReviewFeedback(ctx, {
            logCli: (msg, col) => logCli(ctx, msg, col),
            onSynced: async () => {
              await loadSession();
              refreshFilesUI();
              if (state.selectedFile) {
                renderCurrentDiff();
              }
            },
          });
          break;
        case "set-verdict":
          handleVerdict(actionEl.dataset.verdict || "IN_REVIEW");
          break;
        case "close-workstation":
          if (typeof event.preventDefault === "function") {
            event.preventDefault();
          }
          closeWorkstation();
          break;
        case "toggle-pane":
          togglePane(actionEl.dataset.pane || "");
          break;
        case "toggle-focus":
          toggleFocusMode();
          break;
        case "copy-active-file":
          if (state.selectedFile) {
            copyToClipboard(ctx, state.selectedFile, `Copied: ${state.selectedFile}`);
          }
          break;
        case "open-vscode":
          if (typeof event.preventDefault === "function") {
            event.preventDefault();
          }
          openInVsCode(1);
          break;
        case "navigate-change":
          navigateChange(Number.parseInt(actionEl.dataset.direction || "1", 10));
          break;
        case "set-diff-mode":
          setDiffMode(actionEl.dataset.mode || "side_by_side");
          break;
        case "toggle-word-wrap":
          toggleWordWrap();
          break;
        case "execute-code-search":
          executeCodeSearch();
          break;
        case "clear-code-search":
          if (codeSearchInput) {
            codeSearchInput.value = "";
            codeSearchInput.focus();
          }
          if (codeSearchClearBtn) {
            codeSearchClearBtn.style.display = "none";
          }
          break;
        case "close-code-search":
          closeCodeSearchModal();
          break;
        case "reload-diff":
          loadDiff();
          break;
        case "set-cli-severity": {
          const sev = actionEl.dataset.severity || "MUST_FIX";
          state.currentSeverity = sev;
          logCli(ctx, `Severity preset set to: [${sev}]`, "gold");
          const cliInput = resolveElement(ctx, "cliInput");
          if (cliInput) cliInput.focus();
          break;
        }
        case "toggle-cli-drawer":
          toggleCliDrawer();
          break;
        case "cli-send":
          cliControls.executeCliInput();
          break;
        case "close-fuzzy-history":
          cliControls.closeFuzzyHistory();
          break;
        default:
          break;
      }
    });
  }

  // --- Global Keyboard Shortcuts ---
  ctx.addViewportListener("keydown", async (event) => {
    const searchModal = resolveElement(ctx, "codeSearchResultsModal");
    if (searchModal && searchModal.style.display !== "none" && searchModal.style.display !== "") {
      const listEl = resolveElement(ctx, "codeSearchResultsList");
      const rows = listEl ? listEl.querySelectorAll(".search-result-row") : [];
      if (event.key === "Escape") {
        event.preventDefault();
        closeCodeSearchModal();
        return;
      }
      if (event.key === "ArrowDown" && rows.length > 0) {
        event.preventDefault();
        activeSearchHitIndex = (activeSearchHitIndex + 1) % rows.length;
        rows.forEach((r, idx) => r.classList.toggle("active-hit", idx === activeSearchHitIndex));
        return;
      }
      if (event.key === "ArrowUp" && rows.length > 0) {
        event.preventDefault();
        activeSearchHitIndex = (activeSearchHitIndex - 1 + rows.length) % rows.length;
        rows.forEach((r, idx) => r.classList.toggle("active-hit", idx === activeSearchHitIndex));
        return;
      }
      if (
        event.key === "Enter" &&
        rows.length > 0 &&
        (!doc || !doc.activeElement || doc.activeElement.id !== "codeSearchInput")
      ) {
        if (activeSearchHitIndex >= 0 && rows[activeSearchHitIndex]) {
          event.preventDefault();
          rows[activeSearchHitIndex].click();
          return;
        }
      }
    }

    if (event.metaKey || event.ctrlKey) {
      if (event.key === "=" || event.key === "+" || event.code === "Equal" || event.code === "NumpadAdd") {
        event.preventDefault();
        adjustScale(1);
        return;
      }
      if (event.key === "-" || event.key === "_" || event.code === "Minus" || event.code === "NumpadSubtract") {
        event.preventDefault();
        adjustScale(-1);
        return;
      }
      if (event.key === "0" || event.code === "Digit0" || event.code === "Numpad0") {
        event.preventDefault();
        applyScaleLabel("100%");
        return;
      }
      if (event.key === "r" || event.key === "R") {
        event.preventDefault();
        cliControls.openFuzzyHistory();
        return;
      }
    }

    const targetTag = event.target && event.target.tagName ? event.target.tagName.toUpperCase() : "";
    if (targetTag === "INPUT" || targetTag === "TEXTAREA" || targetTag === "SELECT") {
      return;
    }

    const keyLower = typeof event.key === "string" ? event.key.toLowerCase() : "";
    if (event.key === "[") {
      togglePane("commits");
    } else if (event.key === "]") {
      togglePane("files");
    } else if (event.key === "\\") {
      toggleFocusMode();
    } else if (event.key === "/" && codeSearchInput) {
      event.preventDefault();
      codeSearchInput.focus();
    } else if (keyLower === "s") {
      setDiffMode("side_by_side");
    } else if (keyLower === "u") {
      setDiffMode("unified");
    } else if (keyLower === "f") {
      setDiffMode("full_file");
    } else if (keyLower === "w") {
      toggleWordWrap();
    } else if (keyLower === "j" || (event.altKey && event.key === "ArrowDown")) {
      event.preventDefault();
      await navigateChange(1);
    } else if (keyLower === "k" || (event.altKey && event.key === "ArrowUp")) {
      event.preventDefault();
      await navigateChange(-1);
    } else if (event.key === "Escape") {
      if (state.selectedRange && state.selectedRange.start) {
        state.selectedRange = { start: null, end: null };
        updateTargetUI(ctx, state, false);
        renderCurrentDiff();
      } else {
        closeWorkstation();
      }
    }
  });

  // Boot initial data fetch & background auto-sync
  const ready = (async () => {
    await loadSession();
    await loadCommits();
  })();

  autoSyncTimer = ctx.setInterval(syncReviewSilently, AUTO_SYNC_INTERVAL_MS);
  if (doc) {
    doc.addEventListener("visibilitychange", () => {
      if (doc.visibilityState === "visible") {
        syncReviewSilently();
      }
    });
  }
  ctx.addViewportListener("focus", syncReviewSilently);

  return {
    state,
    ready,
    goto,
    selectCommit,
    setDiffMode,
    togglePane,
    toggleWordWrap,
    dispose() {
      if (autoSyncTimer !== null) {
        ctx.clearInterval(autoSyncTimer);
      }
    },
  };
}

const defaultCtx = getRuntimeContext();
if (defaultCtx.getDocument()) {
  if (defaultCtx.getDocument().readyState === "loading") {
    defaultCtx.getDocument().addEventListener("DOMContentLoaded", () => initCodeReviewApp(defaultCtx));
  } else {
    initCodeReviewApp(defaultCtx);
  }
}
