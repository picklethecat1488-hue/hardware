/**
 * Smartlog Ancestor DAG Rendering, Multi-Select & Badge Actions (`smartlog_dag.js`).
 *
 * Parameterized via boot config (`issueKind`: `"bug"` | `"worm"`,
 * `issueLabel`: `"BUG"` | `"WORM"`) so `hardware` and `firmware` share 100%
 * byte-identical module code with zero browser globals.
 */

import { clearChildren, createEl, resolveElement } from "../core/dom.js";
import { sanitizeAuthor } from "../core/sanitize.js";
import { copyToClipboard, showToast } from "../core/toast.js";

export const HIDE_MERGED_STORAGE_KEY = "diffview_hide_merged";
const PR_BRANCH_PATTERN = /(?:^|\/)(?:pr|pull)[/-]?(\d+)\b/i;

/**
 * Compute the repository web base URL for external branch/tag/PR links.
 *
 * @param {object} config - Boot configuration object.
 * @returns {string} Base GitHub web URL without trailing slash.
 */
export function resolveRepoWebBase(config = {}) {
  if (config.repoWebUrl) {
    return String(config.repoWebUrl).replace(/\/+$/, "");
  }
  if (config.githubRepo) {
    return `https://github.com/${String(config.githubRepo).replace(/^\/+|\/+$/g, "")}`;
  }
  const repoName = config.repoName || "hardware";
  return `https://github.com/workspace/${repoName}`;
}

/**
 * Resolve what action should occur when a branch or tag badge is clicked.
 *
 * @param {string} branchName - Branch or tag name.
 * @param {string} prUrl - Explicit pull request URL if linked.
 * @param {string} repoBase - Repository web URL base.
 * @returns {{kind: "open_url", url: string} | {kind: "toast", message: string}}
 */
export function resolveBranchBadgeAction(branchName, prUrl, repoBase) {
  if (prUrl) {
    return { kind: "open_url", url: prUrl };
  }
  const name = String(branchName || "");
  const match = name.match(PR_BRANCH_PATTERN);
  const isRemote = name.startsWith("origin/") || name.startsWith("remotes/");
  if (match && isRemote) {
    return { kind: "open_url", url: `${repoBase}/pull/${match[1]}` };
  }
  if (isRemote) {
    const cleaned = name.replace(/^(?:remotes\/)?origin\//i, "");
    return { kind: "open_url", url: `${repoBase}/tree/${cleaned}` };
  }
  if (match) {
    return {
      kind: "toast",
      message: `PR #${match[1]} (branch "${name}") has not been created on GitHub yet.`,
    };
  }
  return {
    kind: "toast",
    message: `Branch "${name}" is local only and has not been pushed to GitHub.`,
  };
}

/**
 * Compute contiguous commit hashes selected between `anchorHash` and `targetHash`.
 *
 * @param {string[]} orderedHashes - Ordered commit hashes rendered in the DAG.
 * @param {string} anchorHash - Previously active commit hash.
 * @param {string} targetHash - Newly Shift-clicked commit hash.
 * @returns {string[]} Contiguous commit hashes (excluding `"working"`), or empty array.
 */
export function computeShiftRangeSelection(orderedHashes, anchorHash, targetHash) {
  if (!Array.isArray(orderedHashes) || !anchorHash || !targetHash) {
    return [];
  }
  const prevIdx = orderedHashes.indexOf(anchorHash);
  const currIdx = orderedHashes.indexOf(targetHash);
  if (prevIdx === -1 || currIdx === -1) {
    return [];
  }
  const start = Math.min(prevIdx, currIdx);
  const end = Math.max(prevIdx, currIdx);
  return orderedHashes.slice(start, end + 1).filter((hash) => hash && hash !== "working");
}

/**
 * Determine whether merged commits are currently hidden in the smartlog pane.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @returns {boolean} True when merged commits should be hidden.
 */
export function isHideMergedEnabled(ctx) {
  const stored = ctx.getStorage().getItem(HIDE_MERGED_STORAGE_KEY);
  return stored === null ? true : stored === "true";
}

/**
 * Synchronize merged-commit visibility classes and button labels with storage state.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export function updateMergedVisibility(ctx) {
  const hideMerged = isHideMergedEnabled(ctx);
  const listEl = resolveElement(ctx, "smartlogList");
  const iconEl = resolveElement(ctx, "mergedToggleIcon");
  const labelEl = resolveElement(ctx, "mergedToggleLabel");
  if (listEl) {
    listEl.classList.toggle("hide-merged", hideMerged);
  }
  if (iconEl) {
    iconEl.textContent = hideMerged ? "👁️" : "🙈";
  }
  if (labelEl) {
    labelEl.textContent = hideMerged ? "Show Merged" : "Hide Merged";
  }
}

/**
 * Toggle visibility of merged commits in the smartlog DAG.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 */
export function toggleMergedCommits(ctx) {
  const nextState = !isHideMergedEnabled(ctx);
  ctx.getStorage().setItem(HIDE_MERGED_STORAGE_KEY, nextState ? "true" : "false");
  updateMergedVisibility(ctx);
}

/**
 * Update the selected commit count badge and PR button tooltip.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state object.
 */
export function updateSelectedCount(ctx, state) {
  const selected = Array.isArray(state.selectedCommits) ? state.selectedCommits : [];
  const countEl = resolveElement(ctx, "selectedCount");
  if (countEl) {
    countEl.textContent = String(selected.length);
  }
  const btnCreate = resolveElement(ctx, "btnCreatePR");
  if (btnCreate) {
    let topCommit = "";
    if (selected.length > 0) {
      topCommit = selected[0].slice(0, 7);
    } else {
      const checkboxes = (ctx.getDocument() ? ctx.getDocument().querySelectorAll(".commit-checkbox") : []);
      for (const cb of checkboxes) {
        const node = cb.closest(".smartlog-node");
        if (node && !node.classList.contains("merged-commit") && cb.value) {
          topCommit = cb.value.slice(0, 7);
          break;
        }
      }
    }
    btnCreate.title = topCommit
      ? `Create Pull Request stack up to latest commit (${topCommit})`
      : "Create Pull Request for current commit stack";
  }
}

/**
 * Select all commit checkboxes in the smartlog tree.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state object.
 */
export function selectAllCommits(ctx, state) {
  const checkboxes = (ctx.getDocument() ? ctx.getDocument().querySelectorAll(".commit-checkbox") : []);
  const selected = [];
  for (const cb of checkboxes) {
    cb.checked = true;
    if (cb.value) {
      selected.push(cb.value);
    }
    const node = cb.closest(".smartlog-node");
    if (node) {
      node.classList.add("selected");
    }
  }
  state.selectedCommits = selected;
  updateSelectedCount(ctx, state);
}

/**
 * Deselect all commit checkboxes in the smartlog tree.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable VCS state object.
 */
export function selectNoneCommits(ctx, state) {
  const checkboxes = (ctx.getDocument() ? ctx.getDocument().querySelectorAll(".commit-checkbox") : []);
  for (const cb of checkboxes) {
    cb.checked = false;
    const node = cb.closest(".smartlog-node");
    if (node) {
      node.classList.remove("selected");
    }
  }
  state.selectedCommits = [];
  updateSelectedCount(ctx, state);
}

/**
 * Build a single smartlog commit node DOM element without any inline event handlers.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} node - Smartlog commit node record.
 * @param {object} state - Active VCS state.
 * @param {object} config - Boot configuration.
 * @returns {HTMLElement} `.smartlog-node` element.
 */
function buildCommitNodeElement(ctx, node, state, config) {
  const repoWebBase = resolveRepoWebBase(config);
  const issueLabel = config.issueLabel || "BUG";
  const commitHash = String(node.commit_hash || node.hash || "");
  const shortHash = String(node.short_hash || commitHash.slice(0, 7));
  const isMerged = Boolean(node.is_merged_into_tracking || node.is_merged);
  const isActive =
    state.activeCommit === commitHash ||
    (Boolean(state.activeCommit) &&
      state.activeCommit !== "working" &&
      commitHash.startsWith(state.activeCommit));
  const isChecked =
    Array.isArray(state.selectedCommits) && state.selectedCommits.includes(commitHash);

  const classes = ["smartlog-node"];
  if (node.is_head) classes.push("head-node");
  if (node.is_ancestor_top) classes.push("ancestor-top-node");
  if (node.pr_number) classes.push("has-pr");
  if (isActive) classes.push("active");
  if (isMerged) classes.push("merged-commit");
  if (isChecked) classes.push("selected");

  const checkboxEl = createEl(ctx, "input", {
    className: "commit-checkbox",
    attrs: { type: "checkbox", value: commitHash },
  });
  checkboxEl.value = commitHash;
  checkboxEl.checked = isChecked;

  const leftHeaderChildren = [
    checkboxEl,
    createEl(ctx, "span", {
      className: "node-graph-art",
      text: String(node.graph_art || node.graph_symbol || "o"),
    }),
    createEl(ctx, "span", { className: "node-sha", text: shortHash }),
    createEl(ctx, "button", {
      className: "copy-icon-btn copy-sha-btn",
      text: "📋",
      attrs: { type: "button", title: `Copy commit hash ${commitHash}` },
      dataset: { action: "copy-text", copyValue: commitHash },
    }),
  ];

  if (node.pr_number && node.pr_url) {
    leftHeaderChildren.push(
      createEl(ctx, "a", {
        className: "pr-highlight-badge",
        attrs: {
          href: String(node.pr_url),
          target: "_blank",
          rel: "noopener noreferrer",
          title: `Pull Request #${node.pr_number} (Click to open in GitHub)`,
        },
        dataset: { action: "external-pr-link" },
        children: [
          createEl(ctx, "span", { className: "pr-icon", text: "⎇" }),
          createEl(ctx, "span", {
            text: ` ${node.pr_status || `PR #${node.pr_number}`}`,
          }),
        ],
      }),
    );
  } else if (node.pr_number) {
    const prLabel = String(node.pr_status || `PR #${node.pr_number}`);
    leftHeaderChildren.push(
      createEl(ctx, "span", {
        className: "pr-highlight-badge pr-local-badge",
        attrs: { title: `${prLabel} (Local branch, not submitted to GitHub)` },
        dataset: {
          action: "local-pr-toast",
          toastMessage: `${prLabel} has not been created on GitHub yet`,
        },
        children: [
          createEl(ctx, "span", { className: "pr-icon", text: "⎇" }),
          createEl(ctx, "span", { text: ` ${prLabel}` }),
        ],
      }),
    );
  }

  const authorText = node.author
    ? `${sanitizeAuthor(node.author, config.authorBlacklist)} · `
    : "";
  const dateLabel = `${authorText}${node.relative_date || node.date || ""}`.trim();

  const tagsRow = createEl(ctx, "div", { className: "node-tags-row" });
  if (isMerged) {
    tagsRow.appendChild(
      createEl(ctx, "span", {
        className: "node-badge node-badge-merged",
        text: "✓ Merged",
        attrs: { title: "Already merged into tracking branch" },
      }),
    );
  }
  if (node.is_ancestor_top) {
    const ancestorName = String(node.ancestor_name || "main");
    tagsRow.appendChild(
      createEl(ctx, "span", {
        className: "node-badge node-badge-ancestor",
        text: `📌 ${ancestorName}`,
        attrs: { title: `Top of ancestor branch (${ancestorName})` },
      }),
    );
  }

  for (const br of node.branches || []) {
    const brStr = String(br);
    const lowerBr = brStr.toLowerCase();
    const isPrBr = lowerBr.includes("pr") || lowerBr.includes("pull");
    const brUrl =
      isPrBr && node.pr_url
        ? String(node.pr_url)
        : `${repoWebBase}/tree/${brStr.replace("origin/", "")}`;
    const extraClass =
      isPrBr && node.pr_url ? " pr-tag-link" : isPrBr ? " pr-local-badge" : "";

    tagsRow.appendChild(
      createEl(ctx, "span", {
        style: { display: "inline-flex", alignItems: "center" },
        children: [
          createEl(ctx, "a", {
            className: `node-badge node-badge-branch${extraClass}`,
            text: `⎇ ${brStr}`,
            attrs: {
              href: brUrl,
              target: "_blank",
              rel: "noopener noreferrer",
              title:
                isPrBr && node.pr_url
                  ? "Open PR in GitHub"
                  : isPrBr
                    ? `Local branch ${brStr} (not on GitHub)`
                    : `View branch ${brStr} on GitHub`,
            },
            dataset: {
              action: "branch-badge",
              branch: brStr,
              prUrl: node.pr_url ? String(node.pr_url) : "",
            },
          }),
          createEl(ctx, "button", {
            className: "copy-icon-btn copy-badge-btn",
            text: "📋",
            attrs: { type: "button", title: `Copy branch ${brStr}` },
            dataset: { action: "copy-text", copyValue: brStr },
          }),
        ],
      }),
    );
  }

  for (const tag of node.tags || []) {
    const tagStr = String(tag);
    const lowerTag = tagStr.toLowerCase();
    const isPrTag = lowerTag.includes("pr") || lowerTag.includes("pull");
    const tagUrl =
      isPrTag && node.pr_url
        ? String(node.pr_url)
        : `${repoWebBase}/releases/tag/${tagStr}`;
    const extraClass =
      isPrTag && node.pr_url ? " pr-tag-link" : isPrTag ? " pr-local-badge" : "";

    tagsRow.appendChild(
      createEl(ctx, "a", {
        className: `node-badge node-badge-tag${extraClass}`,
        text: `🏷 ${tagStr}`,
        attrs: {
          href: tagUrl,
          target: "_blank",
          rel: "noopener noreferrer",
        },
        dataset: {
          action: "branch-badge",
          branch: tagStr,
          prUrl: node.pr_url ? String(node.pr_url) : "",
        },
      }),
    );
  }

  if (node.pr_status && node.pr_url) {
    tagsRow.appendChild(
      createEl(ctx, "a", {
        className: "node-badge node-badge-pr pr-tag-link",
        text: `⎇ ${node.pr_status}`,
        attrs: {
          href: String(node.pr_url),
          target: "_blank",
          rel: "noopener noreferrer",
          title: "Open PR on GitHub",
        },
        dataset: { action: "external-pr-link" },
      }),
    );
  } else if (node.pr_status) {
    tagsRow.appendChild(
      createEl(ctx, "span", {
        className: "node-badge node-badge-pr pr-local-badge",
        text: `⎇ ${node.pr_status}`,
        attrs: { title: `${node.pr_status} (Not yet created on GitHub)` },
        dataset: {
          action: "local-pr-toast",
          toastMessage: `${node.pr_status} has not been created on GitHub yet`,
        },
      }),
    );
  }

  const issueTags =
    Array.isArray(node.worm_tags) && node.worm_tags.length > 0
      ? node.worm_tags
      : Array.isArray(node.bug_tags)
        ? node.bug_tags
        : [];
  for (const issue of issueTags) {
    const issueId = String(issue.id || "");
    const resolvedClass = issue.status === "RESOLVED" ? " resolved" : "";
    tagsRow.appendChild(
      createEl(ctx, "span", {
        style: { display: "inline-flex", alignItems: "center" },
        children: [
          createEl(ctx, "span", {
            className: `node-badge node-badge-bug${resolvedClass}`,
            text: `${issueId}: ${issue.status || "OPEN"}`,
            attrs: { title: String(issue.title || issueId) },
            dataset: { action: "open-issue", issueId },
          }),
          createEl(ctx, "button", {
            className: "copy-icon-btn copy-badge-btn",
            text: "📋",
            attrs: { type: "button", title: `Copy ${issueId}` },
            dataset: { action: "copy-text", copyValue: issueId },
          }),
        ],
      }),
    );
  }

  const crBtnChildren = [createEl(ctx, "span", { text: "🔍 CR" })];
  if (node.cr_total_count && node.cr_total_count > 0) {
    const badgeColor = node.cr_open_count > 0 ? "cr-open" : "cr-resolved";
    crBtnChildren.push(
      createEl(ctx, "span", {
        className: `cr-badge ${badgeColor}`,
        text: `${node.cr_open_count}/${node.cr_total_count}`,
      }),
    );
  }

  const actionsRow = createEl(ctx, "div", {
    className: "node-actions-row",
    children: [
      createEl(ctx, "button", {
        className: `quake-btn quake-btn-default quake-btn-icon jump-cr-btn${node.cr_reviewed ? " cr-reviewed" : ""}`,
        attrs: { type: "button", title: "Jump to Code Review for this commit" },
        dataset: { action: "jump-cr", commit: commitHash },
        children: crBtnChildren,
      }),
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-default quake-btn-icon",
        attrs: {
          type: "button",
          title: `Create ${issueLabel} referencing this commit`,
        },
        dataset: { action: "create-issue", commit: commitHash },
        children: [createEl(ctx, "span", { text: issueLabel === "WORM" ? "🪱+" : "🐞+" })],
      }),
    ],
  });

  return createEl(ctx, "div", {
    id: `node-${shortHash}`,
    className: classes.join(" "),
    dataset: { hash: commitHash },
    children: [
      createEl(ctx, "div", {
        className: "node-header-row",
        children: [
          createEl(ctx, "div", {
            style: { display: "flex", alignItems: "center", gap: "6px" },
            children: leftHeaderChildren,
          }),
          createEl(ctx, "span", { className: "node-author-date", text: dateLabel }),
        ],
      }),
      createEl(ctx, "div", {
        className: "node-subject",
        text: String(node.subject || ""),
      }),
      tagsRow,
      actionsRow,
    ],
  });
}

/**
 * Render the entire Smartlog tree (`WORKING TREE` + commit DAG nodes) into `listEl`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} listElOrId - `#smartlogList` container or ID.
 * @param {Array<object>} nodes - Smartlog node records.
 * @param {object} state - Mutable VCS state.
 * @param {object} [config] - Boot configuration.
 */
export function renderSmartlogNodes(ctx, listElOrId, nodes, state, config = {}) {
  const listEl = resolveElement(ctx, listElOrId);
  if (!listEl) {
    return;
  }
  clearChildren(listEl);

  const workingEl = createEl(ctx, "div", {
    id: "node-working",
    className: `smartlog-node${state.activeCommit === "working" ? " active" : ""}`,
    dataset: { hash: "working" },
    children: [
      createEl(ctx, "div", {
        className: "node-header-row",
        children: [
          createEl(ctx, "span", { className: "node-graph-art", text: "@" }),
          createEl(ctx, "span", {
            className: "node-sha",
            text: "WORKING TREE",
            style: { color: "var(--quake-cyan)" },
          }),
          createEl(ctx, "span", { className: "node-author-date", text: "Uncommitted" }),
        ],
      }),
      createEl(ctx, "div", {
        className: "node-subject",
        text: "Local working tree changes & staging area",
      }),
    ],
  });
  listEl.appendChild(workingEl);

  for (const node of nodes || []) {
    listEl.appendChild(buildCommitNodeElement(ctx, node, state, config));
  }

  updateMergedVisibility(ctx);
  updateSelectedCount(ctx, state);
}

/**
 * Bind delegated click and checkbox interactions on `#smartlogList`.
 * Works identically for initial server-rendered Jinja2 HTML and dynamically rendered nodes.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} listElOrId - `#smartlogList` element or ID.
 * @param {object} state - Mutable VCS state.
 * @param {object} config - Boot configuration.
 * @param {object} callbacks - Action handlers (`onSelectCommit`, `onJumpToCR`, `onOpenIssue`, `onCreateIssueForCommit`).
 */
export function bindSmartlogEvents(ctx, listElOrId, state, config, callbacks) {
  const listEl = resolveElement(ctx, listElOrId);
  if (!listEl) {
    return;
  }
  let lastCheckedCommitIndex = -1;
  const repoBase = resolveRepoWebBase(config);

  listEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }

    const checkbox = target.closest(".commit-checkbox");
    if (checkbox) {
      if (typeof event.stopPropagation === "function") {
        event.stopPropagation();
      }
      const allCheckboxes = listEl.querySelectorAll(".commit-checkbox");
      const currentIndex = allCheckboxes.indexOf(checkbox);
      if (event.shiftKey && lastCheckedCommitIndex !== -1 && currentIndex !== -1) {
        const start = Math.min(lastCheckedCommitIndex, currentIndex);
        const end = Math.max(lastCheckedCommitIndex, currentIndex);
        const targetChecked = Boolean(checkbox.checked);
        for (let idx = start; idx <= end; idx += 1) {
          allCheckboxes[idx].checked = targetChecked;
          const rowNode = allCheckboxes[idx].closest(".smartlog-node");
          if (rowNode) {
            rowNode.classList.toggle("selected", targetChecked);
          }
        }
      } else {
        const rowNode = checkbox.closest(".smartlog-node");
        if (rowNode) {
          rowNode.classList.toggle("selected", Boolean(checkbox.checked));
        }
      }
      lastCheckedCommitIndex = currentIndex;
      state.selectedCommits = allCheckboxes
        .filter((cb) => Boolean(cb.checked) && Boolean(cb.value))
        .map((cb) => cb.value);
      updateSelectedCount(ctx, state);
      return;
    }

    const isInsideList = (node) => {
      let cur = node;
      while (cur) {
        if (cur === listEl) return true;
        cur = cur.parentNode;
      }
      return false;
    };

    const actionEl = target.closest("[data-action]");
    if (actionEl && isInsideList(actionEl)) {
      const action = actionEl.dataset.action;
      if (action === "external-pr-link") {
        if (typeof event.stopPropagation === "function") {
          event.stopPropagation();
        }
        return;
      }
      if (typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      if (typeof event.stopPropagation === "function") {
        event.stopPropagation();
      }

      switch (action) {
        case "copy-text":
          copyToClipboard(ctx, actionEl.dataset.copyValue || "", actionEl.dataset.copyValue || "");
          return;
        case "local-pr-toast":
          showToast(ctx, actionEl.dataset.toastMessage || "PR not created on GitHub yet");
          return;
        case "branch-badge": {
          const outcome = resolveBranchBadgeAction(
            actionEl.dataset.branch || "",
            actionEl.dataset.prUrl || "",
            repoBase,
          );
          if (outcome.kind === "open_url") {
            ctx.openExternalUrl(outcome.url, "_blank");
          } else {
            showToast(ctx, outcome.message);
          }
          return;
        }
        case "open-issue":
          if (typeof callbacks.onOpenIssue === "function") {
            callbacks.onOpenIssue(actionEl.dataset.issueId || "");
          }
          return;
        case "jump-cr":
          if (typeof callbacks.onJumpToCR === "function") {
            callbacks.onJumpToCR(actionEl.dataset.commit || "");
          }
          return;
        case "create-issue":
          if (typeof callbacks.onCreateIssueForCommit === "function") {
            callbacks.onCreateIssueForCommit(actionEl.dataset.commit || "");
          }
          return;
        default:
          break;
      }
    }

    const nodeEl = target.closest(".smartlog-node");
    if (nodeEl && isInsideList(nodeEl)) {
      const commitHash = nodeEl.dataset.hash || "working";
      if (typeof callbacks.onSelectCommit === "function") {
        callbacks.onSelectCommit(commitHash, event, nodeEl);
      }
    }
  });
}
