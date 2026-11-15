/**
 * Working Tree & Commit File List Operations (`working_tree.js`).
 *
 * Renders working-tree groups (Conflicts, LFS, Staged, Unstaged, Untracked,
 * Agent Feedback) and commit file lists, and handles stage/unstage/discard/quick-commit.
 */

import { clearChildren, createEl, queryAll, resolveElement } from "../core/dom.js";
import { showConfirmModal } from "../core/modal.js";
import { showToast } from "../core/toast.js";
import { createConflictGroupElement, resolveConflictFile } from "./conflict_resolver.js";

/**
 * Create a single working-tree `.file-item` row element.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} file - Working file record.
 * @param {object} options - Row rendering options.
 * @returns {HTMLElement} `.file-item` element.
 */
function createWorkingFileRow(ctx, file, options) {
  const filePath = String(file.path || "");
  const cb = createEl(ctx, "input", {
    className: "working-file-cb",
    attrs: { type: "checkbox", value: filePath },
  });
  cb.checked = Boolean(options.checked);

  const children = [cb];
  if (options.isLfs) {
    children.push(createEl(ctx, "span", { className: "file-status-badge status-lfs", text: "LFS" }));
  }
  children.push(
    createEl(ctx, "span", {
      className: `file-status-badge ${options.badgeClass || ""}`.trim(),
      text: String(options.statusLabel || file.status || "M"),
      style: options.badgeStyle || undefined,
    }),
  );
  children.push(
    createEl(ctx, "span", {
      className: "file-path",
      text: filePath,
      attrs: { title: filePath },
    }),
  );

  const actionButtons = [];
  if (options.isStaged) {
    actionButtons.push(
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-default quake-btn-icon",
        text: "➖",
        attrs: { type: "button", title: `Unstage ${filePath}` },
        dataset: { action: "unstage-file", path: filePath },
      }),
    );
  } else {
    actionButtons.push(
      createEl(ctx, "button", {
        className: `quake-btn ${options.isFeedback ? "quake-btn-default" : "quake-btn-gold"} quake-btn-icon`,
        text: "➕",
        attrs: { type: "button", title: `Stage ${filePath}` },
        dataset: { action: "stage-file", path: filePath },
      }),
    );
  }
  actionButtons.push(
    createEl(ctx, "button", {
      className: "quake-btn quake-btn-red quake-btn-icon",
      text: "🗑",
      attrs: { type: "button", title: `Discard ${filePath}` },
      dataset: { action: "discard-file", path: filePath },
    }),
  );

  children.push(createEl(ctx, "div", { className: "file-actions", children: actionButtons }));

  const rowClasses = ["file-item"];
  if (options.isLfs) rowClasses.push("lfs-file-item");
  if (options.isFeedback) rowClasses.push("agent-feedback");
  if (options.isActive) rowClasses.push("active");

  return createEl(ctx, "div", {
    className: rowClasses.join(" "),
    dataset: { path: filePath },
    children,
  });
}

/**
 * Render working tree file groups into `container`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} containerOrId - `#filesContainer` element or ID.
 * @param {object} state - Mutable VCS state.
 * @param {Function} [onAutoSelectFile] - Optional `(filePath) => void` when no file is selected yet.
 */
export function renderWorkingTreeFiles(ctx, containerOrId, state, onAutoSelectFile) {
  const container = resolveElement(ctx, containerOrId);
  if (!container) {
    return;
  }
  clearChildren(container);

  const workingFiles = Array.isArray(state.workingFiles) ? state.workingFiles : [];
  const conflicts = Array.isArray(state.conflicts) ? state.conflicts : [];
  const lfs = workingFiles.filter((f) => f.is_lfs && !f.is_feedback);
  const staged = workingFiles.filter((f) => f.is_staged && !f.is_feedback && !f.is_lfs);
  const unstaged = workingFiles.filter(
    (f) => !f.is_staged && !f.is_untracked && !f.is_conflicted && !f.is_feedback && !f.is_lfs,
  );
  const untracked = workingFiles.filter((f) => f.is_untracked && !f.is_feedback && !f.is_lfs);
  const feedback = workingFiles.filter((f) => f.is_feedback);

  const countBadge = resolveElement(ctx, "filesCountBadge");
  if (countBadge) {
    countBadge.textContent = `${workingFiles.length} changes`;
  }

  const conflictSection = createConflictGroupElement(ctx, conflicts, state.activeFile);
  if (conflictSection) {
    container.appendChild(conflictSection);
  }

  const appendGroup = (title, headerColor, rows) => {
    if (rows.length === 0) {
      return;
    }
    container.appendChild(
      createEl(ctx, "div", {
        className: "group-section",
        children: [
          createEl(ctx, "div", {
            className: "group-header",
            text: title,
            style: headerColor ? { color: headerColor } : undefined,
          }),
          createEl(ctx, "div", { className: "group-items", children: rows }),
        ],
      }),
    );
  };

  appendGroup(
    `📦 LFS Tracked Files (${lfs.length})`,
    "#00e5ff",
    lfs.map((f) =>
      createWorkingFileRow(ctx, f, {
        isLfs: true,
        isStaged: Boolean(f.is_staged),
        checked: Boolean(f.is_staged || !f.is_untracked),
        badgeClass: f.is_staged ? "status-a" : f.is_untracked ? "status-untracked" : "status-m",
        isActive: state.activeFile === f.path,
      }),
    ),
  );

  appendGroup(
    `✓ Staged Changes (${staged.length})`,
    "var(--quake-green)",
    staged.map((f) =>
      createWorkingFileRow(ctx, f, {
        isStaged: true,
        checked: true,
        badgeClass: "status-a",
        isActive: state.activeFile === f.path,
      }),
    ),
  );

  appendGroup(
    `✎ Unstaged Changes (${unstaged.length})`,
    "var(--quake-gold)",
    unstaged.map((f) =>
      createWorkingFileRow(ctx, f, {
        isStaged: false,
        checked: true,
        badgeClass: "status-m",
        isActive: state.activeFile === f.path,
      }),
    ),
  );

  appendGroup(
    `? Untracked Files (${untracked.length})`,
    "var(--quake-purple)",
    untracked.map((f) =>
      createWorkingFileRow(ctx, f, {
        isStaged: false,
        checked: false,
        statusLabel: "??",
        badgeClass: "status-untracked",
        isActive: state.activeFile === f.path,
      }),
    ),
  );

  if (feedback.length > 0) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "group-section",
        children: [
          createEl(ctx, "div", {
            className: "group-header",
            dataset: { action: "toggle-feedback-group" },
            children: [
              createEl(ctx, "span", { text: `🤖 Agent Feedback (${feedback.length})` }),
              createEl(ctx, "span", { text: state.feedbackCollapsed ? "▶" : "▼" }),
            ],
          }),
          createEl(ctx, "div", {
            className: "group-items",
            style: state.feedbackCollapsed ? { display: "none" } : undefined,
            children: feedback.map((f) =>
              createWorkingFileRow(ctx, f, {
                isStaged: Boolean(f.is_staged),
                isFeedback: true,
                checked: false,
                badgeStyle: { color: "var(--quake-text-muted)" },
                isActive: state.activeFile === f.path,
              }),
            ),
          }),
        ],
      }),
    );
  }

  if (workingFiles.length === 0 && conflicts.length === 0) {
    container.appendChild(
      createEl(ctx, "div", {
        text: "Working tree is clean.",
        style: { textAlign: "center", padding: "30px", color: "var(--quake-text-dim)" },
      }),
    );
    return;
  }

  if (!state.activeFile && typeof onAutoSelectFile === "function") {
    const first =
      (conflicts[0] && conflicts[0].path) ||
      (staged[0] && staged[0].path) ||
      (unstaged[0] && unstaged[0].path) ||
      (untracked[0] && untracked[0].path) ||
      (lfs[0] && lfs[0].path) ||
      (feedback[0] && feedback[0].path);
    if (first) {
      onAutoSelectFile(first);
    }
  }
}

/**
 * Render committed revision file list into `container`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} containerOrId - `#filesContainer` element or ID.
 * @param {object} state - Mutable VCS state.
 * @param {Function} [onAutoSelectFile] - Optional `(filePath) => void` when no file is selected yet.
 */
export function renderCommitFiles(ctx, containerOrId, state, onAutoSelectFile) {
  const container = resolveElement(ctx, containerOrId);
  if (!container) {
    return;
  }
  clearChildren(container);

  const files = Array.isArray(state.files) ? state.files : [];
  const lfs = files.filter((f) => f.is_lfs && !f.is_feedback);
  const regular = files.filter((f) => !f.is_feedback && !f.is_lfs);
  const feedback = files.filter((f) => f.is_feedback);

  const countBadge = resolveElement(ctx, "filesCountBadge");
  if (countBadge) {
    countBadge.textContent = `${files.length} files`;
  }

  const buildCommitRow = (f, extraClass = "") => {
    const filePath = String(f.path || "");
    const statusClass =
      f.status === "A" ? "status-a" : f.status === "D" ? "status-d" : "status-m";
    const children = [];
    if (f.is_lfs && !f.is_feedback) {
      children.push(createEl(ctx, "span", { className: "file-status-badge status-lfs", text: "LFS" }));
    }
    children.push(
      createEl(ctx, "span", {
        className: f.is_feedback ? "file-status-badge" : `file-status-badge ${statusClass}`,
        text: String(f.status || "M"),
        style: f.is_feedback ? { color: "var(--quake-text-muted)" } : undefined,
      }),
      createEl(ctx, "span", {
        className: "file-path",
        text: filePath,
        attrs: { title: filePath },
      }),
      createEl(ctx, "span", {
        text: `+${f.additions || 0} -${f.deletions || 0}`,
        style: { fontSize: "8px", color: "var(--quake-text-dim)" },
      }),
    );
    return createEl(ctx, "div", {
      className: `file-item${extraClass ? ` ${extraClass}` : ""}${state.activeFile === filePath ? " active" : ""}`,
      dataset: { path: filePath },
      children,
    });
  };

  if (lfs.length > 0) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "group-section",
        children: [
          createEl(ctx, "div", {
            className: "group-header",
            text: `📦 LFS Tracked Files (${lfs.length})`,
            style: { color: "#00e5ff" },
          }),
          createEl(ctx, "div", {
            className: "group-items",
            children: lfs.map((f) => buildCommitRow(f, "lfs-file-item")),
          }),
        ],
      }),
    );
  }

  if (regular.length > 0) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "group-section",
        children: [
          createEl(ctx, "div", {
            className: "group-header",
            text: `Changed Files (${regular.length})`,
          }),
          createEl(ctx, "div", {
            className: "group-items",
            children: regular.map((f) => buildCommitRow(f)),
          }),
        ],
      }),
    );
  }

  if (feedback.length > 0) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "group-section",
        children: [
          createEl(ctx, "div", {
            className: "group-header",
            dataset: { action: "toggle-feedback-group" },
            children: [
              createEl(ctx, "span", { text: `🤖 Agent Feedback (${feedback.length})` }),
              createEl(ctx, "span", { text: state.feedbackCollapsed ? "▶" : "▼" }),
            ],
          }),
          createEl(ctx, "div", {
            className: "group-items",
            style: state.feedbackCollapsed ? { display: "none" } : undefined,
            children: feedback.map((f) => buildCommitRow(f, "agent-feedback")),
          }),
        ],
      }),
    );
  }

  if (files.length === 0) {
    container.appendChild(
      createEl(ctx, "div", {
        text: "No files changed in this revision.",
        style: { textAlign: "center", padding: "30px", color: "var(--quake-text-dim)" },
      }),
    );
    return;
  }

  if (!state.activeFile && typeof onAutoSelectFile === "function") {
    const first =
      (regular[0] && regular[0].path) ||
      (lfs[0] && lfs[0].path) ||
      (feedback[0] && feedback[0].path);
    if (first) {
      onAutoSelectFile(first);
    }
  }
}

/**
 * Stage a single working-tree file via `/api/stage`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} filePath - Path to stage.
 * @param {Function} [onRefresh] - Refresh callback after success.
 */
export async function stageFile(ctx, filePath, onRefresh) {
  const resp = await ctx.fetchRaw("/api/stage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: filePath }),
  });
  const payload = await resp.json();
  if (!resp.ok || (payload && payload.error)) {
    showToast(ctx, `Error: ${(payload && payload.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Staged ${filePath}`);
  if (typeof onRefresh === "function") {
    await onRefresh();
  }
}

/**
 * Unstage a single staged file via `/api/unstage`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} filePath - Path to unstage.
 * @param {Function} [onRefresh] - Refresh callback after success.
 */
export async function unstageFile(ctx, filePath, onRefresh) {
  const resp = await ctx.fetchRaw("/api/unstage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: filePath }),
  });
  const payload = await resp.json();
  if (!resp.ok || (payload && payload.error)) {
    showToast(ctx, `Error: ${(payload && payload.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Unstaged ${filePath}`);
  if (typeof onRefresh === "function") {
    await onRefresh();
  }
}

/**
 * Discard uncommitted changes in a single file after modal confirmation.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} filePath - Path to discard.
 * @param {Function} [onRefresh] - Refresh callback after success.
 */
export async function discardFile(ctx, filePath, onRefresh) {
  const confirmed = await showConfirmModal(ctx, {
    title: "Discard File Changes",
    message: `Discard all uncommitted changes in ${filePath}?`,
    confirmLabel: "Discard",
    danger: true,
  });
  if (!confirmed) {
    return;
  }
  const resp = await ctx.fetchRaw("/api/discard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: filePath }),
  });
  const payload = await resp.json();
  if (!resp.ok || (payload && payload.error)) {
    showToast(ctx, `Error: ${(payload && payload.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Discarded ${filePath}`);
  if (typeof onRefresh === "function") {
    await onRefresh();
  }
}

/**
 * Discard all checked `.working-file-cb` files after modal confirmation.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {Function} [onRefresh] - Refresh callback after success.
 */
export async function discardSelectedWorkingFiles(ctx, onRefresh) {
  const selected = queryAll(ctx, ".working-file-cb")
    .filter((cb) => Boolean(cb.checked) && Boolean(cb.value))
    .map((cb) => cb.value);

  if (selected.length === 0) {
    showToast(ctx, "Select at least one file checkbox to discard.", "error");
    return;
  }

  const confirmed = await showConfirmModal(ctx, {
    title: "Discard Selected Files",
    message: `Discard changes in ${selected.length} selected file(s)? This cannot be undone.`,
    confirmLabel: "Discard Selected",
    danger: true,
  });
  if (!confirmed) {
    return;
  }

  const resp = await ctx.fetchRaw("/api/discard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files: selected }),
  });
  const payload = await resp.json();
  if (!resp.ok || (payload && payload.error)) {
    showToast(ctx, `Error: ${(payload && payload.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Discarded ${selected.length} files`);
  if (typeof onRefresh === "function") {
    await onRefresh();
  }
}

/**
 * Commit currently staged working-tree changes using the quick-commit textarea.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export async function quickCommitStaged(ctx) {
  const msgInput = resolveElement(ctx, "commitMessageInput");
  const msg = msgInput && msgInput.value ? msgInput.value.trim() : "";
  if (!msg) {
    showToast(ctx, "Please enter a commit message.", "error");
    return;
  }

  const resp = await ctx.fetchRaw("/api/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msg }),
  });
  const payload = await resp.json();
  if (!resp.ok || (payload && payload.error)) {
    showToast(ctx, `Commit failed: ${(payload && payload.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  const shortHash = String(payload.commit_hash || "").slice(0, 7);
  showToast(ctx, `Committed ${shortHash}`);
  if (msgInput) {
    msgInput.value = "";
  }
  ctx.setTimeout(() => ctx.reload(), 500);
}

/**
 * Bind delegated click handlers for working-tree and commit file rows inside `container`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} containerOrId - `#filesContainer` element or ID.
 * @param {object} state - Mutable VCS state.
 * @param {object} callbacks - `{ onSelectFile, onRefreshFiles }` handlers.
 */
export function bindFilesContainerEvents(ctx, containerOrId, state, callbacks) {
  const container = resolveElement(ctx, containerOrId);
  if (!container) {
    return;
  }

  container.addEventListener("click", (event) => {
    const target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }

    const cb = target.closest(".working-file-cb");
    if (cb) {
      if (typeof event.stopPropagation === "function") {
        event.stopPropagation();
      }
      return;
    }

    const isInsideContainer = (node) => {
      let cur = node;
      while (cur) {
        if (cur === container) return true;
        cur = cur.parentNode;
      }
      return false;
    };

    const actionEl = target.closest("[data-action]");
    if (actionEl && isInsideContainer(actionEl)) {
      if (typeof event.stopPropagation === "function") {
        event.stopPropagation();
      }
      const action = actionEl.dataset.action;
      const path = actionEl.dataset.path || "";
      switch (action) {
        case "stage-file":
          stageFile(ctx, path, callbacks.onRefreshFiles);
          return;
        case "unstage-file":
          unstageFile(ctx, path, callbacks.onRefreshFiles);
          return;
        case "discard-file":
          discardFile(ctx, path, callbacks.onRefreshFiles);
          return;
        case "resolve-conflict":
          resolveConflictFile(
            ctx,
            path,
            actionEl.dataset.resolution || "mark_resolved",
            callbacks.onRefreshFiles,
          );
          return;
        case "toggle-feedback-group":
          state.feedbackCollapsed = !state.feedbackCollapsed;
          if (state.activeCommit === "working") {
            renderWorkingTreeFiles(ctx, container, state, callbacks.onSelectFile);
          } else {
            renderCommitFiles(ctx, container, state, callbacks.onSelectFile);
          }
          return;
        default:
          break;
      }
    }

    const fileRow = target.closest(".file-item");
    if (fileRow && isInsideContainer(fileRow)) {
      const filePath = fileRow.dataset.path || "";
      if (filePath && typeof callbacks.onSelectFile === "function") {
        callbacks.onSelectFile(filePath);
      }
    }
  });
}
