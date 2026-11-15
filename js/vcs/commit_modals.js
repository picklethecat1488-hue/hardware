/**
 * Commit, Amend, Branch Picker, Rebase, Sync, Split/Combine & PR Modals (`commit_modals.js`).
 *
 * Implements all VCS modal workflows with zero browser globals (`prompt`, `alert`,
 * `confirm`, `window`, `document`, `fetch`, `setTimeout` are never referenced directly).
 */

import { clearChildren, createEl, queryAll, resolveElement } from "../core/dom.js";
import { hideModal, showConfirmModal, showModal } from "../core/modal.js";
import { AsymptoticProgressBar, performActionWithProgress } from "../core/progress.js";
import { copyToClipboard, showToast } from "../core/toast.js";

const PROMPT_MODAL_ID = "forgePromptModalOverlay";
const PR_PROGRESS_TICK_MS = 50;
const INITIAL_SYNC_FINISH_DELAY_MS = 400;

/**
 * Display a promise-based text input modal in place of browser `prompt()`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} options - Prompt options.
 * @param {string} [options.title] - Header title.
 * @param {string} [options.label] - Input field label.
 * @param {string} [options.placeholder] - Input placeholder.
 * @param {string} [options.defaultValue] - Initial input value.
 * @param {string} [options.confirmLabel] - Submit button label.
 * @returns {Promise<string|null>} Trimmed input value or `null` if cancelled.
 */
export function showPromptModal(
  ctx,
  {
    title = "Input Required",
    label = "Enter value:",
    placeholder = "",
    defaultValue = "",
    confirmLabel = "Submit",
  } = {},
) {
  const doc = ctx.getDocument();
  if (!doc || !doc.body) {
    return Promise.resolve(defaultValue ? String(defaultValue).trim() : null);
  }

  let overlay = resolveElement(ctx, PROMPT_MODAL_ID);
  if (overlay) {
    overlay.remove();
  }

  return new Promise((resolve) => {
    let settled = false;
    const inputEl = createEl(ctx, "input", {
      id: "forgePromptInput",
      className: "commit-input",
      attrs: {
        type: "text",
        placeholder,
        value: defaultValue,
      },
      style: { minHeight: "32px", padding: "6px 10px", width: "100%" },
    });
    inputEl.value = defaultValue;

    const finish = (result) => {
      if (settled) {
        return;
      }
      settled = true;
      ctx.getDocument()?.removeEventListener("keydown", onKeyDown);
      hideModal(ctx, overlay);
      overlay.remove();
      resolve(result);
    };

    const onSubmit = () => {
      const trimmed = String(inputEl.value || "").trim();
      finish(trimmed || null);
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        finish(null);
      } else if (event.key === "Enter") {
        if (typeof event.preventDefault === "function") {
          event.preventDefault();
        }
        onSubmit();
      }
    };

    const cancelBtn = createEl(ctx, "button", {
      className: "quake-btn quake-btn-default",
      text: "Cancel",
      attrs: { type: "button" },
      on: { click: () => finish(null) },
    });
    const submitBtn = createEl(ctx, "button", {
      id: "forgePromptSubmitBtn",
      className: "quake-btn quake-btn-gold",
      text: confirmLabel,
      attrs: { type: "button" },
      on: { click: onSubmit },
    });

    overlay = createEl(ctx, "div", {
      id: PROMPT_MODAL_ID,
      className: "quake-modal-overlay",
      style: { zIndex: "2500" },
      on: {
        click: (event) => {
          if (event.target === overlay) {
            finish(null);
          }
        },
      },
      children: [
        createEl(ctx, "div", {
          className: "quake-modal",
          style: { width: "460px" },
          children: [
            createEl(ctx, "div", {
              className: "quake-modal-header",
              children: [
                createEl(ctx, "span", { text: title }),
                createEl(ctx, "button", {
                  className: "quake-btn quake-btn-default quake-btn-icon",
                  text: "✕",
                  attrs: { type: "button" },
                  on: { click: () => finish(null) },
                }),
              ],
            }),
            createEl(ctx, "div", {
              className: "quake-modal-body",
              children: [
                createEl(ctx, "label", {
                  text: label,
                  style: {
                    fontSize: "9px",
                    fontWeight: "700",
                    textTransform: "uppercase",
                  },
                }),
                inputEl,
              ],
            }),
            createEl(ctx, "div", {
              className: "quake-modal-footer",
              style: { justifyContent: "flex-end" },
              children: [cancelBtn, submitBtn],
            }),
          ],
        }),
      ],
    });

    doc.body.appendChild(overlay);
    showModal(ctx, overlay);
    ctx.getDocument()?.addEventListener("keydown", onKeyDown);
    ctx.setTimeout(() => inputEl.focus(), 20);
  });
}

/**
 * Synchronize the Commit Modal's "Select All" master checkbox with row checkboxes.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export function updateModalSelectAllState(ctx) {
  const all = queryAll(ctx, ".modal-file-cb");
  const checked = all.filter((cb) => Boolean(cb.checked));
  const master = resolveElement(ctx, "modalSelectAll");
  if (master) {
    master.checked = all.length > 0 && all.length === checked.length;
  }
}

/**
 * Toggle all `.modal-file-cb` checkboxes inside the Commit / Amend modal.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {boolean} checked - Desired checked state.
 */
export function toggleModalSelectAll(ctx, checked) {
  for (const cb of queryAll(ctx, ".modal-file-cb")) {
    cb.checked = Boolean(checked);
  }
}

/**
 * Return the list of file paths currently checked inside the Commit / Amend modal.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @returns {string[]} Selected repository-relative file paths.
 */
export function getSelectedModalFiles(ctx) {
  return queryAll(ctx, ".modal-file-cb")
    .filter((cb) => Boolean(cb.checked) && Boolean(cb.value))
    .map((cb) => cb.value);
}

/**
 * Refresh the file checklist inside `#commitModalOverlay`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 * @param {Function} [onRefreshMainFiles] - Callback to refresh main working-tree list on discard.
 */
export async function refreshModalFilesList(ctx, state, onRefreshMainFiles) {
  const listEl = resolveElement(ctx, "modalFilesList");
  if (!listEl) {
    return;
  }
  clearChildren(listEl);
  listEl.appendChild(
    createEl(ctx, "div", {
      text: "Loading changed files...",
      style: { textAlign: "center", padding: "10px", color: "var(--quake-text-muted)" },
    }),
  );

  const resp = await ctx.fetchRaw("/api/working");
  if (!resp.ok) {
    clearChildren(listEl);
    listEl.appendChild(
      createEl(ctx, "div", {
        text: `Failed to load files (HTTP ${resp.status})`,
        style: { color: "var(--quake-red)", padding: "10px" },
      }),
    );
    return;
  }
  const workingFiles = await resp.json();
  state.workingFiles = Array.isArray(workingFiles) ? workingFiles : [];
  clearChildren(listEl);

  if (state.workingFiles.length === 0) {
    listEl.appendChild(
      createEl(ctx, "div", {
        text: "No uncommitted changes in working tree.",
        style: { textAlign: "center", padding: "12px", color: "var(--quake-text-dim)" },
      }),
    );
    updateModalSelectAllState(ctx);
    return;
  }

  const mainChecked = queryAll(ctx, ".working-file-cb")
    .filter((cb) => Boolean(cb.checked) && Boolean(cb.value))
    .map((cb) => cb.value);

  for (const file of state.workingFiles) {
    const filePath = String(file.path || "");
    const isLfs = Boolean(file.is_lfs || filePath.startsWith("attachments/"));
    const isChecked =
      mainChecked.length > 0
        ? mainChecked.includes(filePath)
        : Boolean(file.is_staged || !file.is_untracked);
    const badgeClass = file.is_staged
      ? "status-a"
      : file.is_untracked
        ? "status-untracked"
        : "status-m";

    const cb = createEl(ctx, "input", {
      className: "modal-file-cb",
      attrs: { type: "checkbox", value: filePath },
      on: { change: () => updateModalSelectAllState(ctx) },
    });
    cb.value = filePath;
    cb.checked = isChecked;

    const labelChildren = [cb];
    if (isLfs) {
      labelChildren.push(
        createEl(ctx, "span", { className: "file-status-badge status-lfs", text: "LFS" }),
      );
    }
    labelChildren.push(
      createEl(ctx, "span", {
        className: `file-status-badge ${badgeClass}`,
        text: String(file.status || "M"),
      }),
      createEl(ctx, "span", {
        className: "file-path",
        text: filePath,
        attrs: { title: filePath },
      }),
    );

    const discardBtn = createEl(ctx, "button", {
      className: "quake-btn quake-btn-red quake-btn-icon",
      text: "🗑",
      attrs: { type: "button", title: `Discard ${filePath}` },
      on: {
        click: async () => {
          const confirmed = await showConfirmModal(ctx, {
            title: "Discard File",
            message: `Discard all changes in ${filePath}?`,
            confirmLabel: "Discard",
            danger: true,
          });
          if (!confirmed) {
            return;
          }
          const discardResp = await ctx.fetchRaw("/api/discard", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file: filePath }),
          });
          const res = await discardResp.json();
          if (!discardResp.ok || (res && res.error)) {
            showToast(ctx, `Error: ${(res && res.error) || "Discard failed"}`, "error");
            return;
          }
          showToast(ctx, `Discarded ${filePath}`);
          await refreshModalFilesList(ctx, state, onRefreshMainFiles);
          if (typeof onRefreshMainFiles === "function") {
            await onRefreshMainFiles();
          }
        },
      },
    });

    listEl.appendChild(
      createEl(ctx, "div", {
        className: `modal-file-row${isLfs ? " lfs-file-item" : ""}`,
        children: [
          createEl(ctx, "label", {
            style: {
              display: "flex",
              alignItems: "center",
              gap: "6px",
              flex: "1",
              overflow: "hidden",
              cursor: "pointer",
            },
            children: labelChildren,
          }),
          discardBtn,
        ],
      }),
    );
  }

  updateModalSelectAllState(ctx);
}

/**
 * Open the Commit or Amend modal and populate candidate files and message.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 * @param {boolean} isAmend - True for Amend HEAD mode, false for new Commit.
 * @param {Function} [onRefreshMainFiles] - Main working-tree refresh callback.
 */
export async function openCommitModal(ctx, state, isAmend = false, onRefreshMainFiles) {
  state.isAmendMode = Boolean(isAmend);
  const titleEl = resolveElement(ctx, "commitModalTitle");
  const submitBtn = resolveElement(ctx, "btnSubmitModalCommit");
  const msgInput = resolveElement(ctx, "modalCommitMessage");

  if (titleEl) {
    titleEl.textContent = state.isAmendMode ? "Amend Last Commit (HEAD)" : "Commit Changes";
  }
  if (submitBtn) {
    clearChildren(submitBtn);
    submitBtn.appendChild(
      createEl(ctx, "span", {
        text: state.isAmendMode ? "✓ Amend Commit" : "✓ Commit",
      }),
    );
  }

  if (msgInput) {
    if (state.isAmendMode) {
      const resp = await ctx.fetchRaw("/api/head_commit_message");
      if (resp.ok) {
        const data = await resp.json();
        msgInput.value = (data && data.message) || "";
      } else {
        msgInput.value = "";
      }
    } else {
      const quickInput = resolveElement(ctx, "commitMessageInput");
      msgInput.value = quickInput && quickInput.value ? quickInput.value.trim() : "";
    }
  }

  await refreshModalFilesList(ctx, state, onRefreshMainFiles);
  showModal(ctx, "commitModalOverlay");
}

/**
 * Close the Commit / Amend modal.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export function closeCommitModal(ctx) {
  hideModal(ctx, "commitModalOverlay");
}

/**
 * Discard all files checked inside `#commitModalOverlay`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 * @param {Function} [onRefreshMainFiles] - Main working-tree refresh callback.
 */
export async function discardSelectedFromModal(ctx, state, onRefreshMainFiles) {
  const selected = getSelectedModalFiles(ctx);
  if (selected.length === 0) {
    showToast(ctx, "Please select files to discard.", "error");
    return;
  }
  const confirmed = await showConfirmModal(ctx, {
    title: "Discard Selected Files",
    message: `Discard all changes in ${selected.length} selected file(s)? This cannot be undone.`,
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
  const res = await resp.json();
  if (!resp.ok || (res && res.error)) {
    showToast(ctx, `Error: ${(res && res.error) || "Discard failed"}`, "error");
    return;
  }
  showToast(ctx, `Discarded ${selected.length} files`);
  await refreshModalFilesList(ctx, state, onRefreshMainFiles);
  if (typeof onRefreshMainFiles === "function") {
    await onRefreshMainFiles();
  }
}

/**
 * Submit the Commit or Amend request from `#commitModalOverlay`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 */
export async function submitCommitModal(ctx, state) {
  const msgInput = resolveElement(ctx, "modalCommitMessage");
  const msg = msgInput && msgInput.value ? msgInput.value.trim() : "";
  if (!msg) {
    showToast(ctx, "Please enter a commit message.", "error");
    return;
  }
  const selectedFiles = getSelectedModalFiles(ctx);
  if (!state.isAmendMode && selectedFiles.length === 0) {
    showToast(ctx, "Please select at least one file to commit.", "error");
    return;
  }

  const endpoint = state.isAmendMode ? "/api/amend" : "/api/commit";
  await performActionWithProgress(
    ctx,
    async () => {
      const resp = await ctx.fetchRaw(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, files: selectedFiles }),
      });
      const res = await resp.json();
      if (!resp.ok || (res && res.error)) {
        showToast(ctx, `Commit failed: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
        return;
      }
      const shortHash = String(res.commit_hash || "").slice(0, 7);
      showToast(ctx, `${state.isAmendMode ? "Amended" : "Committed"} ${shortHash}`);
      closeCommitModal(ctx);
      ctx.setTimeout(() => ctx.reload(), 500);
    },
    {
      title: state.isAmendMode ? "AMENDING COMMIT" : "CREATING COMMIT",
      description: state.isAmendMode
        ? "Amending current HEAD commit with selected changes..."
        : "Creating new commit with selected staged changes...",
      stepText: state.isAmendMode ? "Amending commit..." : "Writing commit tree...",
      icon: "📦",
    },
  );
}

/**
 * Render filtered mainline/release and feature/PR branch lists inside `#modalBranchPicker`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} config - Boot configuration (`branches`, `currentUser`).
 * @param {Function} onSelectBranch - `(branchName) => void` callback.
 */
export function renderBranchLists(ctx, config, onSelectBranch) {
  const searchInput = resolveElement(ctx, "branchSearchInput");
  const hideChk = resolveElement(ctx, "chkHideOtherUsers");
  const search = searchInput && searchInput.value ? searchInput.value.trim().toLowerCase() : "";
  const hideOtherUsers = hideChk ? Boolean(hideChk.checked) : true;
  const currentUser = String(config.currentUser || "User").toLowerCase();
  const branchData = Array.isArray(config.branches) ? config.branches : [];

  const mainContainer = resolveElement(ctx, "mainReleaseBranchList");
  const featContainer = resolveElement(ctx, "featureBranchList");
  const countEl = resolveElement(ctx, "featureBranchCount");
  if (!mainContainer || !featContainer) {
    return;
  }

  clearChildren(mainContainer);
  clearChildren(featContainer);

  const mainReleaseBranches = [];
  const featureBranches = [];

  for (const branch of branchData) {
    if (branch.is_main || branch.is_release) {
      mainReleaseBranches.push(branch);
    } else {
      const lowerName = String(branch.name || "").toLowerCase();
      if (hideOtherUsers) {
        const ghMatch = lowerName.match(/(?:remotes\/origin\/)?gh\/([^/]+)\//);
        if (ghMatch && ghMatch[1] !== currentUser) {
          continue;
        }
      }
      if (search && !lowerName.includes(search)) {
        continue;
      }
      featureBranches.push(branch);
    }
  }

  mainReleaseBranches.sort((a, b) => {
    if (a.is_main && !b.is_main) return -1;
    if (!a.is_main && b.is_main) return 1;
    return String(a.name).localeCompare(String(b.name), undefined, { numeric: true });
  });

  const buildBranchRow = (b, isMainSection) => {
    const branchName = String(b.name || "");
    const lower = branchName.toLowerCase();
    const isPr = lower.includes("pr") || lower.includes("pull");
    const copyBtn = createEl(ctx, "button", {
      className: "copy-icon-btn copy-badge-btn",
      text: "📋",
      attrs: { type: "button", title: `Copy branch ${branchName}` },
      on: {
        click: (event) => {
          if (typeof event.stopPropagation === "function") {
            event.stopPropagation();
          }
          copyToClipboard(ctx, branchName, branchName);
        },
      },
    });

    const leftChildren = [
      createEl(ctx, "span", {
        text: isMainSection ? (b.is_main ? "⭐" : "🏷️") : isPr ? "⎇" : "🌿",
        style: {
          color: isMainSection
            ? "var(--quake-gold)"
            : isPr
              ? "var(--quake-purple)"
              : "var(--quake-cyan)",
        },
      }),
      createEl(ctx, "span", { text: branchName }),
      copyBtn,
    ];
    if (b.is_current) {
      leftChildren.push(
        createEl(ctx, "span", {
          className: "node-badge node-badge-tag",
          text: "CURRENT",
          style: {
            background: "var(--quake-gold)",
            color: "#140a05",
            fontWeight: "700",
          },
        }),
      );
    }

    return createEl(ctx, "div", {
      className: `branch-item${isMainSection ? " branch-item-main" : ""}${b.is_current ? " active" : ""}`,
      on: {
        click: () => {
          hideModal(ctx, "modalBranchPicker");
          onSelectBranch(branchName);
        },
      },
      children: [
        createEl(ctx, "div", {
          style: { display: "flex", alignItems: "center", gap: "6px" },
          children: leftChildren,
        }),
        createEl(ctx, "span", {
          text: isMainSection ? (b.is_main ? "Mainline" : "Release") : isPr ? "PR Branch" : "Feature",
          style: {
            fontSize: "8px",
            color: isMainSection ? "var(--quake-text-muted)" : "var(--quake-text-dim)",
          },
        }),
      ],
    });
  };

  for (const branch of mainReleaseBranches) {
    mainContainer.appendChild(buildBranchRow(branch, true));
  }

  if (countEl) {
    countEl.textContent = `${featureBranches.length} branch${featureBranches.length === 1 ? "" : "es"}`;
  }

  if (featureBranches.length === 0) {
    featContainer.appendChild(
      createEl(ctx, "div", {
        text: "No matching branches found",
        style: {
          padding: "10px",
          textAlign: "center",
          color: "var(--quake-text-dim)",
          fontSize: "9px",
        },
      }),
    );
  } else {
    for (const branch of featureBranches) {
      featContainer.appendChild(buildBranchRow(branch, false));
    }
  }
}

/**
 * Open `#modalBranchPicker` and focus the search input.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} config - Boot configuration.
 * @param {Function} onSelectBranch - Branch checkout callback.
 */
export function openBranchModal(ctx, config, onSelectBranch) {
  showModal(ctx, "modalBranchPicker");
  const input = resolveElement(ctx, "branchSearchInput");
  if (input) {
    input.value = "";
    ctx.setTimeout(() => input.focus(), 50);
  }
  renderBranchLists(ctx, config, onSelectBranch);
}

/**
 * Close `#modalBranchPicker`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export function closeBranchModal(ctx) {
  hideModal(ctx, "modalBranchPicker");
}

/**
 * Checkout a git branch via `/api/checkout_branch`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 * @param {string} branchName - Target branch name.
 */
export async function checkoutBranch(ctx, state, branchName) {
  if (!branchName) {
    return;
  }
  state.currentBranch = branchName;
  const sel = resolveElement(ctx, "branchSelect");
  if (sel) {
    sel.value = branchName;
  }
  const btnBranch = resolveElement(ctx, "btnBranchDropdown");
  if (btnBranch) {
    const label = btnBranch.querySelector("span");
    if (label) {
      label.textContent = `🌿 ${branchName}`;
    }
  }
  const resp = await ctx.fetchRaw("/api/checkout_branch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ branch: branchName }),
  });
  const res = await resp.json();
  if (!resp.ok || (res && res.error)) {
    showToast(ctx, `Checkout error: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Switched to branch ${branchName}`);
  ctx.setTimeout(() => ctx.reload(), 500);
}

/**
 * Open a modal prompt to jump directly to a commit hash or branch reference.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {Function} onSelectCommit - `(targetHash) => Promise<void>` callback.
 */
export async function openGotoModal(ctx, onSelectCommit) {
  const target = await showPromptModal(ctx, {
    title: "Goto Revision",
    label: "Enter commit hash or branch name to inspect:",
    placeholder: "e.g. HEAD~1, main, 8715cab2",
    confirmLabel: "Goto",
  });
  if (!target) {
    return;
  }
  const resp = await ctx.fetchRaw("/api/goto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target }),
  });
  const res = await resp.json();
  if (!resp.ok || (res && res.error)) {
    showToast(ctx, `Goto error: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, `Loaded ${target}`);
  await onSelectCommit(target);
}

/**
 * Split the active commit (resetting changes into the working tree) after confirmation.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 */
export async function splitActiveCommit(ctx, state) {
  const target = state.activeCommit === "working" ? "HEAD" : state.activeCommit || "HEAD";
  const confirmed = await showConfirmModal(ctx, {
    title: "Split Commit",
    message: `Split commit ${target.slice(0, 7)}? This resets the commit and leaves its changes in the working tree for selective restaging.`,
    confirmLabel: "Split Commit",
    danger: true,
  });
  if (!confirmed) {
    return;
  }
  const resp = await ctx.fetchRaw("/api/split", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commit: target }),
  });
  const res = await resp.json();
  if (!resp.ok || (res && res.error)) {
    showToast(ctx, `Split failed: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  showToast(ctx, res.message || "Commit split successfully.");
  ctx.setTimeout(() => ctx.reload(), 800);
}

/**
 * Combine/squash 2+ selected commits using a modal message prompt.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 */
export async function combineSelectedCommits(ctx, state) {
  const selected = Array.isArray(state.selectedCommits) ? state.selectedCommits : [];
  if (selected.length < 2) {
    showToast(
      ctx,
      "Select 2 or more contiguous commits using checkboxes to combine/squash.",
      "error",
    );
    return;
  }
  const message = await showPromptModal(ctx, {
    title: "Combine / Squash Commits",
    label: `Enter commit message for ${selected.length} combined commits:`,
    defaultValue: "Combined commits",
    confirmLabel: "Combine",
  });
  if (!message) {
    return;
  }
  const resp = await ctx.fetchRaw("/api/combine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commits: selected, message }),
  });
  const res = await resp.json();
  if (!resp.ok || (res && res.error)) {
    showToast(ctx, `Combine failed: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
    return;
  }
  const shortHash = String(res.commit_hash || "").slice(0, 7);
  showToast(ctx, `Combined into ${shortHash}`);
  ctx.setTimeout(() => ctx.reload(), 800);
}

/**
 * Sync repository from remote via `/api/sync`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export async function syncRepository(ctx) {
  const spinner = resolveElement(ctx, "syncSpinner");
  if (spinner) spinner.style.display = "inline";
  showToast(ctx, "Syncing repository from remote...");

  await performActionWithProgress(
    ctx,
    async () => {
      const resp = await ctx.fetchRaw("/api/sync", { method: "POST" });
      const res = await resp.json();
      if (spinner) spinner.style.display = "none";
      if (!resp.ok || (res && res.error)) {
        showToast(ctx, `Sync failed: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
        return;
      }
      showToast(ctx, res.message || "Sync completed.");
      ctx.setTimeout(() => ctx.reload(), 1000);
    },
    {
      title: "SYNCHRONIZING REPOSITORY",
      description: "Pulling latest changes from remote and synchronizing review branches...",
      stepText: "Connecting to remote...",
      icon: "🔄",
    },
  );
}

/**
 * Rebase local stack onto target ancestor branch via `/api/rebase`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export async function rebaseRepository(ctx) {
  const spinner = resolveElement(ctx, "rebaseSpinner");
  if (spinner) spinner.style.display = "inline";
  showToast(ctx, "Rebasing onto ancestor branch...");

  await performActionWithProgress(
    ctx,
    async () => {
      const resp = await ctx.fetchRaw("/api/rebase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const res = await resp.json();
      if (spinner) spinner.style.display = "none";
      if (resp.ok && res && res.status === "ok") {
        showToast(ctx, res.message || "Rebase completed.");
        ctx.setTimeout(() => ctx.reload(), 1000);
      } else {
        showToast(
          ctx,
          `Rebase failed: ${(res && (res.message || res.error)) || "Unknown error"}`,
          { kind: "error", durationMs: 5000 },
        );
      }
    },
    {
      title: "REBASING COMMITS",
      description: "Rebasing local commits onto target ancestor branch...",
      stepText: "Rebasing branch...",
      icon: "⎇",
    },
  );
}

/**
 * Run initial SQLite feedback database synchronization (`/api/sync_feedback`).
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {boolean} initialSyncDone - Whether initial sync already ran before boot.
 * @param {boolean} [isManual] - Whether triggered explicitly by user.
 * @param {string} [issueLabel] - `"BUG"` or `"WORM"` label.
 */
export async function performInitialSync(
  ctx,
  initialSyncDone,
  isManual = false,
  issueLabel = "BUG",
) {
  const modal = resolveElement(ctx, "syncModalOverlay");
  const statusText = resolveElement(ctx, "syncStatusText");
  const progressBar = resolveElement(ctx, "syncProgressBar");
  const progressPercent = resolveElement(ctx, "syncProgressPercent");

  if (modal) modal.style.display = "flex";

  const tracker = new AsymptoticProgressBar(ctx, {
    barEl: progressBar,
    percentEl: progressPercent,
    statusEl: statusText,
    initialProgress: 12,
    maxProgress: 95,
    stages: [
      { at: 28, text: "Scanning feedback/ directory and discovering markdown files..." },
      { at: 58, text: "Merging feedback markdown records into SQLite store..." },
      { at: 84, text: "Reconciling review comments and issue tracking tags..." },
      { at: 100, text: "Building smartlog DAG and computing file changes..." },
    ],
  });
  tracker.start();

  try {
    const resp = await ctx.fetchRaw("/api/sync_feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (resp.ok) {
      const data = await resp.json();
      const issueStats = (data && (data.worms || data.bugs)) || {};
      const issueCount =
        issueStats.total_worms ??
        issueStats.worms_count ??
        issueStats.total_bugs ??
        issueStats.bugs_count ??
        issueStats.scanned ??
        0;
      const crCount = (data && data.review && data.review.total_comments) || 0;
      const noun = issueLabel.toLowerCase();
      const msg = `✓ Synchronized ${issueCount} ${noun}s and ${crCount} review comments.`;
      tracker.finish(
        msg,
        () => {
          if (modal) modal.style.display = "none";
          if (!initialSyncDone || isManual) {
            ctx.reload();
          }
        },
        INITIAL_SYNC_FINISH_DELAY_MS,
      );
    } else {
      tracker.fail(
        "Sync complete with warnings. Continuing...",
        () => {
          if (modal) modal.style.display = "none";
        },
        INITIAL_SYNC_FINISH_DELAY_MS,
      );
    }
  } catch (err) {
    const detail = (err && err.message) || "Network error";
    tracker.fail(
      `Feedback sync skipped (${detail}). Continuing...`,
      () => {
        if (modal) modal.style.display = "none";
      },
      INITIAL_SYNC_FINISH_DELAY_MS,
    );
  }
}

/**
 * Submit pull requests for selected (or unmerged stack) commits via `/api/pr/create`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 * @param {{intervalId: any}} prTimerRef - Mutable timer holder for clean modal dismissal.
 */
export async function createPullRequests(ctx, state, prTimerRef) {
  let targetCommits = Array.isArray(state.selectedCommits) ? state.selectedCommits.slice() : [];
  if (targetCommits.length === 0) {
    const unmergedCheckboxes = queryAll(ctx, ".commit-checkbox").filter((cb) => {
      const node = cb.closest(".smartlog-node");
      return Boolean(node && !node.classList.contains("merged-commit") && cb.value);
    });
    const eligible = unmergedCheckboxes.filter((cb) => {
      const node = cb.closest(".smartlog-node");
      return Boolean(node && !node.classList.contains("has-pr"));
    });
    const chosen = eligible.length > 0 ? eligible : unmergedCheckboxes;
    targetCommits = chosen.map((cb) => cb.value);
  }

  if (targetCommits.length === 0) {
    showToast(ctx, "No committed changes in current stack to create or submit PRs.", "error");
    return;
  }

  const topCommit = targetCommits[0].slice(0, 7);
  const overlay = resolveElement(ctx, "prSubmitModalOverlay");
  const pBar = resolveElement(ctx, "prSubmitProgressBar");
  const pText = resolveElement(ctx, "prSubmitProgressPercent");
  const sText = resolveElement(ctx, "prSubmitStatusText");
  const lOut = resolveElement(ctx, "prSubmitLogOutput");
  const btnDone = resolveElement(ctx, "btnPrSubmitDone");
  const btnClose = resolveElement(ctx, "btnPrSubmitClose");

  if (overlay) overlay.style.display = "flex";
  if (pBar) {
    pBar.style.width = "15%";
    pBar.style.background = "linear-gradient(90deg, #9333ea, #a855f7)";
  }
  if (pText) pText.textContent = "15%";
  if (sText) {
    sText.textContent = `Preparing submission for ${targetCommits.length} commit(s) up to ${topCommit}...`;
  }
  if (lOut) {
    lOut.textContent =
      "$ sl pr submit --config github.max-prs-to-create=-1\nInitializing stack submission...";
  }
  if (btnDone) btnDone.style.display = "none";
  if (btnClose) btnClose.style.display = "none";

  let progress = 14;
  const startTime = ctx.nowMs();
  if (prTimerRef.intervalId !== null) {
    ctx.clearInterval(prTimerRef.intervalId);
  }
  prTimerRef.intervalId = ctx.setInterval(() => {
    const elapsedSec = (ctx.nowMs() - startTime) / 1000;
    if (progress < 94) {
      if (elapsedSec < 1.0) {
        progress = 14 + (elapsedSec / 1.0) * 26;
      } else if (elapsedSec < 3.0) {
        progress = 40 + ((elapsedSec - 1.0) / 2.0) * 28;
      } else if (elapsedSec < 7.0) {
        progress = 68 + ((elapsedSec - 3.0) / 4.0) * 20;
      } else {
        progress += (96 - progress) * 0.015;
      }
    }
    const pct = Math.min(96, Math.floor(progress));
    if (pBar) pBar.style.width = `${pct}%`;
    if (pText) pText.textContent = `${pct}%`;
    if (sText) {
      if (pct < 35) {
        sText.textContent = "Inspecting commit stack and preparing branch references...";
      } else if (pct < 65) {
        sText.textContent = "Pushing feature branch commits to remote repository...";
      } else if (pct < 85) {
        sText.textContent = "Creating and synchronizing pull requests on GitHub...";
      } else {
        sText.textContent = "Awaiting remote GitHub API confirmation...";
      }
    }
  }, PR_PROGRESS_TICK_MS);

  const resp = await ctx.fetchRaw("/api/pr/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commits: targetCommits }),
  });
  const res = await resp.json();
  if (prTimerRef.intervalId !== null) {
    ctx.clearInterval(prTimerRef.intervalId);
    prTimerRef.intervalId = null;
  }

  if (resp.ok && res && res.status === "ok") {
    if (pBar) {
      pBar.style.width = "100%";
      pBar.style.background = "linear-gradient(90deg, #16a34a, #22c55e)";
    }
    if (pText) pText.textContent = "100%";
    const count = (res.created && res.created.length) || targetCommits.length;
    if (sText) sText.textContent = `✓ Successfully submitted ${count} PR(s) to GitHub!`;
    let logText = "$ sl pr submit --config github.max-prs-to-create=-1\n";
    if (Array.isArray(res.logs)) {
      logText += res.logs.join("\n");
    } else if (Array.isArray(res.created)) {
      for (const pr of res.created) {
        logText += `created new pull request: ${pr.pr_url || `#${pr.pr_number}`}\n`;
      }
    }
    if (lOut) {
      lOut.textContent = logText;
      lOut.scrollTop = lOut.scrollHeight;
    }
    if (btnDone) btnDone.style.display = "inline-flex";
    if (btnClose) btnClose.style.display = "inline-flex";
  } else {
    if (pBar) {
      pBar.style.width = "100%";
      pBar.style.background = "linear-gradient(90deg, #b91c1c, #ef4444)";
    }
    if (pText) pText.textContent = "ERROR";
    const errMsg = (res && res.error) || "Failed to submit PRs";
    if (sText) sText.textContent = `✗ Submission Error: ${errMsg}`;
    if (lOut) {
      lOut.textContent = `${lOut.textContent || ""}\n\nERROR: ${errMsg}`;
      lOut.scrollTop = lOut.scrollHeight;
    }
    if (btnClose) btnClose.style.display = "inline-flex";
  }
}

/**
 * Close the PR submission progress modal.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {{intervalId: any}} prTimerRef - Mutable timer holder.
 */
export function closePrSubmitModal(ctx, prTimerRef) {
  if (prTimerRef && prTimerRef.intervalId !== null) {
    ctx.clearInterval(prTimerRef.intervalId);
    prTimerRef.intervalId = null;
  }
  hideModal(ctx, "prSubmitModalOverlay");
}

/**
 * Close the PR submission modal and reload the smartlog view.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {{intervalId: any}} prTimerRef - Mutable timer holder.
 */
export function finishPrSubmitModal(ctx, prTimerRef) {
  closePrSubmitModal(ctx, prTimerRef);
  ctx.reload();
}

/**
 * Unlink PR metadata from selected commits via `/api/pr/unlink`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state.
 */
export async function unlinkPullRequests(ctx, state) {
  const selected = Array.isArray(state.selectedCommits) ? state.selectedCommits : [];
  if (selected.length === 0) {
    showToast(ctx, "Select one or more commits using checkboxes to unlink PR.", "error");
    return;
  }
  const confirmed = await showConfirmModal(ctx, {
    title: "Unlink Pull Requests",
    message: `Unlink PRs from ${selected.length} selected commit(s)?`,
    confirmLabel: "Unlink PR",
    danger: true,
  });
  if (!confirmed) {
    return;
  }
  showToast(ctx, `Unlinking PR from ${selected.length} commit(s)...`);
  const resp = await ctx.fetchRaw("/api/pr/unlink", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commits: selected }),
  });
  const res = await resp.json();
  if (resp.ok && res && res.status === "ok") {
    const count = Array.isArray(res.unlinked) ? res.unlinked.length : selected.length;
    showToast(ctx, `✓ Unlinked ${count} PR(s) successfully!`);
    ctx.setTimeout(() => ctx.reload(), 600);
  } else {
    showToast(ctx, `Error unlinking PR: ${(res && res.error) || `HTTP ${resp.status}`}`, "error");
  }
}
