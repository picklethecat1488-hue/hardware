/**
 * Code Review Commit Stream, Proximity-Ranked File Tree, & Hunk Navigation (`file_tree.js`).
 *
 * Shared 100% byte-identically across `hardware` and `firmware` Code Review workstations.
 */

import { bindDelegatedEvent, clearChildren, createEl, resolveElement } from "../core/dom.js";
import { fuzzyScore } from "../core/fuzzy_search.js";
import { sanitizeAuthor } from "../core/sanitize.js";
import { COMMENT_STATUS, isCommentVisible, resolveCommentStatus } from "./comment_threads.js";

const ATTACHMENT_PREFIXES = Object.freeze([
  "attachments/",
  "target/attachments/",
  "build/attachments/",
  "feedback/attachments/",
]);

/**
 * Determine whether `comment` belongs to the active `selectedCommit` revision.
 *
 * Prevents historical comments from past commits (e.g. resolved review comments
 * on `app/carrier_board.md` across prior commits) from leaking into `working`
 * or unrelated commit views.
 *
 * @param {object|null|undefined} comment - Review comment model (`{ commit }`).
 * @param {string|null|undefined} selectedCommit - Currently selected commit hash or `"working"`.
 * @returns {boolean} True when `comment` belongs to `selectedCommit`.
 */
export function commentMatchesCommit(comment, selectedCommit) {
  if (!comment || typeof comment !== "object") {
    return false;
  }
  const active = String(selectedCommit || "").trim();
  if (!active) {
    return true;
  }
  const cCommit = String(comment.commit || "").trim();
  if (!cCommit) {
    return active === "working";
  }
  if (cCommit === active) {
    return true;
  }
  if (active !== "working" && cCommit !== "working") {
    return active.startsWith(cCommit) || cCommit.startsWith(active);
  }
  return false;
}

/**
 * Return true when `filePath` resides inside an issue-tracker attachment directory.
 *
 * @param {string} filePath - Repository-relative path.
 * @returns {boolean}
 */
export function isAttachmentPath(filePath) {
  if (!filePath || typeof filePath !== "string") {
    return false;
  }
  return ATTACHMENT_PREFIXES.some((prefix) => filePath.startsWith(prefix));
}

/**
 * Determine whether a file entry or diff payload represents a Git LFS asset.
 *
 * @param {object|string|null} fileObjOrPath - File entry object or path string.
 * @param {object|null} [diffData] - Optional loaded diff payload.
 * @returns {boolean}
 */
export function isLfsFile(fileObjOrPath, diffData = null) {
  const pathStr =
    typeof fileObjOrPath === "string"
      ? fileObjOrPath
      : String((fileObjOrPath && fileObjOrPath.path) || "");
  if (fileObjOrPath && typeof fileObjOrPath === "object" && fileObjOrPath.is_lfs) {
    return true;
  }
  if (diffData && diffData.is_lfs) {
    return true;
  }
  return isAttachmentPath(pathStr);
}

/**
 * Compute directory-tree hop distance between `candidatePath` and `currentPath`
 * so fuzzy file filtering ranks sibling and nearby files first.
 *
 * @param {string} candidatePath - Candidate file path.
 * @param {string} currentPath - Currently open file path.
 * @returns {number} Directory tree distance (`0` when identical, `1` in same directory).
 */
export function fileProximityDistance(candidatePath, currentPath) {
  if (!currentPath || !candidatePath || candidatePath === currentPath) {
    return 0;
  }
  const currDirs = currentPath.includes("/") ? currentPath.split("/").slice(0, -1) : [];
  const candDirs = candidatePath.includes("/") ? candidatePath.split("/").slice(0, -1) : [];
  let common = 0;
  while (
    common < currDirs.length &&
    common < candDirs.length &&
    currDirs[common] === candDirs[common]
  ) {
    common += 1;
  }
  return 1 + (currDirs.length - common) + (candDirs.length - common);
}

/**
 * Filter changed files by optional attachment visibility and multi-token fuzzy query,
 * ranking matches by directory proximity to `activeFilePath` and fuzzy match score.
 *
 * @param {Array<object>} files - Changed file models (`{ path, status, additions, deletions, is_lfs }`).
 * @param {object} [options] - Filtering options.
 * @param {boolean} [options.hideAttachments] - Exclude attachment directories when true.
 * @param {string} [options.query] - Search input text.
 * @param {string} [options.activeFilePath] - Currently inspected file path for proximity sorting.
 * @returns {Array<object>} Filtered and ranked file entries.
 */
export function filterAndSortReviewFiles(files, options = {}) {
  if (!Array.isArray(files) || files.length === 0) {
    return [];
  }
  const hideAttachments = Boolean(options.hideAttachments);
  const query = String(options.query || "").trim();
  const activeFilePath = String(options.activeFilePath || "");

  const visible = files.filter((fileObj) => {
    if (hideAttachments && isAttachmentPath(fileObj.path)) {
      return false;
    }
    return true;
  });

  if (!query) {
    return visible;
  }

  const tokens = query.split(/\s+/).filter(Boolean);
  const matched = [];
  for (const fileObj of visible) {
    let totalScore = 0;
    let allMatched = true;
    for (const token of tokens) {
      const res = fuzzyScore(token, fileObj.path);
      if (res === null) {
        allMatched = false;
        break;
      }
      totalScore += res.score;
    }
    if (allMatched) {
      matched.push({
        fileObj,
        dist: fileProximityDistance(fileObj.path, activeFilePath),
        score: totalScore,
      });
    }
  }

  matched.sort((a, b) => {
    if (a.dist !== b.dist) {
      return a.dist - b.dist;
    }
    return b.score - a.score;
  });

  return matched.map((entry) => entry.fileObj);
}

/**
 * Render the Commit Stream list (`#commitsList`) with search filtering, author redaction,
 * `TRACKER ONLY` / ancestor badges, and delegated selection & SHA copy handlers.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Review application state.
 * @param {object} [config] - Boot config (`authorBlacklist`).
 * @param {object} [callbacks] - `{ onSelectCommit, onCopySha }`.
 */
export function renderCommitsList(ctx, state, config = {}, callbacks = {}) {
  const listEl = resolveElement(ctx, "commitsList");
  if (!listEl) {
    return;
  }
  clearChildren(listEl);

  const searchInput = resolveElement(ctx, "commitSearchInput");
  const filterQuery = String((searchInput && searchInput.value) || "").trim();
  const blacklist = config.authorBlacklist || [];
  const commits = Array.isArray(state.commits) ? state.commits : [];

  for (const commit of commits) {
    const safeAuthor = sanitizeAuthor(commit.author, blacklist);
    if (filterQuery) {
      const searchable = `${commit.short_hash || ""} ${commit.commit_hash || ""} ${commit.subject || ""} ${safeAuthor}`;
      if (fuzzyScore(filterQuery, searchable) === null) {
        continue;
      }
    }

    const commitHash = String(commit.commit_hash || "");
    const commitFiles = state.commitFiles ? state.commitFiles[commitHash] : null;
    const openedSet = state.openedFilesByCommit ? state.openedFilesByCommit[commitHash] : null;
    const isReviewed = Boolean(
      (commitFiles &&
        commitFiles.length > 0 &&
        commitFiles.every((filePath) => openedSet && openedSet.has(filePath))) ||
        commit.cr_reviewed,
    );
    const isTrackerOnly =
      commit.files_count === 0 &&
      Array.isArray(commit.ignored_files) &&
      commit.ignored_files.length > 0;
    const isActive = commitHash === state.selectedCommit;
    const isSelected =
      isActive ||
      (Array.isArray(state.selectedCommits) && state.selectedCommits.includes(commitHash));

    const rawDate = String(commit.date || "");
    const timePart = commit.time
      ? ` ${commit.time}`
      : rawDate.includes("T")
        ? ` ${rawDate.split("T")[1].slice(0, 8)}`
        : "";

    const topChildren = [
      createEl(ctx, "span", {
        className: "commit-hash",
        children: [
          createEl(ctx, "span", { text: `${commit.short_hash || commitHash.slice(0, 7)} ` }),
          createEl(ctx, "button", {
            className: "copy-icon-btn copy-sha-btn",
            attrs: {
              type: "button",
              title: `Copy full commit hash ${commitHash}`,
            },
            dataset: { action: "copy-sha", sha: commitHash },
            text: "📋",
          }),
        ],
      }),
    ];

    if (commit.is_ancestor_top) {
      const ancName = commit.ancestor_name || "main";
      topChildren.push(
        createEl(ctx, "span", {
          className: "quake-badge quake-badge-cyan",
          style: { fontSize: "0.65em", marginLeft: "6px" },
          attrs: { title: `Top of ancestor branch (${ancName})` },
          text: `📌 ${ancName}`,
        }),
      );
    }

    if (isTrackerOnly) {
      topChildren.push(
        createEl(ctx, "span", {
          className: "quake-badge quake-badge-yellow",
          style: { fontSize: "0.65em", marginLeft: "6px" },
          attrs: { title: `Only tracking files modified: ${commit.ignored_files.join(", ")}` },
          text: "TRACKER ONLY",
        }),
      );
    }

    topChildren.push(
      createEl(ctx, "span", {
        className: "commit-date",
        text: `${rawDate.slice(0, 10)}${timePart}`,
      }),
    );

    const statChildren = [
      createEl(ctx, "span", { className: "stat-add", text: `+${commit.additions || 0}` }),
      createEl(ctx, "span", { text: " / " }),
      createEl(ctx, "span", { className: "stat-del", text: `-${commit.deletions || 0}` }),
    ];
    if (isTrackerOnly) {
      statChildren.push(
        createEl(ctx, "span", {
          style: { opacity: "0.55", fontSize: "0.85em", marginLeft: "4px" },
          text: `(${commit.ignored_files.join(", ")} filtered)`,
        }),
      );
    }

    const classNames = ["commit-item"];
    if (isActive) classNames.push("active");
    if (isSelected) classNames.push("selected");
    if (isReviewed) classNames.push("reviewed");

    const li = createEl(ctx, "li", {
      className: classNames.join(" "),
      dataset: { commitHash },
      children: [
        createEl(ctx, "div", { className: "commit-top", children: topChildren }),
        createEl(ctx, "div", {
          className: "commit-subject",
          attrs: { title: String(commit.subject || "") },
          text: String(commit.subject || ""),
        }),
        createEl(ctx, "div", {
          className: "commit-bottom",
          children: [
            createEl(ctx, "span", { text: safeAuthor }),
            createEl(ctx, "span", { children: statChildren }),
          ],
        }),
      ],
    });

    listEl.appendChild(li);
  }

  if (!listEl.dataset.boundReviewCommits) {
    listEl.dataset.boundReviewCommits = "1";
    bindDelegatedEvent(listEl, "click", "[data-action='copy-sha']", (event, btnEl) => {
      event.stopPropagation();
      const sha = btnEl.dataset.sha || "";
      if (sha && typeof callbacks.onCopySha === "function") {
        callbacks.onCopySha(sha);
      }
    });
    bindDelegatedEvent(listEl, "click", ".commit-item", (event, itemEl) => {
      if (event.target && typeof event.target.closest === "function") {
        if (event.target.closest("[data-action='copy-sha']")) {
          return;
        }
      }
      const commitHash = itemEl.dataset.commitHash || "";
      if (commitHash && typeof callbacks.onSelectCommit === "function") {
        callbacks.onSelectCommit(commitHash);
      }
    });
  }
}

/**
 * Render the Changed Files pane (`#filesList` and `#filesCountHeader`) with proximity-aware
 * fuzzy filtering, LFS badges, review checkmarks, and comment count badges.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Review application state.
 * @param {object} [callbacks] - `{ onSelectFile }`.
 */
export function renderFilesList(ctx, state, callbacks = {}) {
  const listEl = resolveElement(ctx, "filesList");
  const headerEl = resolveElement(ctx, "filesCountHeader");
  if (!listEl) {
    return;
  }
  clearChildren(listEl);

  const commits = Array.isArray(state.commits) ? state.commits : [];
  const currentCommit = commits.find((c) => c.commit_hash === state.selectedCommit);
  const rawFiles = Array.isArray(state.files) ? state.files : [];

  if (
    rawFiles.length === 0 &&
    currentCommit &&
    Array.isArray(currentCommit.ignored_files) &&
    currentCommit.ignored_files.length > 0
  ) {
    if (headerEl) {
      headerEl.textContent = `Changed Files (0) — ${currentCommit.ignored_files.join(", ")} filtered`;
    }
    for (const ignoredPath of currentCommit.ignored_files) {
      listEl.appendChild(
        createEl(ctx, "li", {
          className: "file-item",
          style: { opacity: "0.6", cursor: "default", padding: "8px 12px" },
          children: [
            createEl(ctx, "span", {
              className: "quake-badge quake-badge-yellow",
              text: "TRACKER",
            }),
            createEl(ctx, "span", {
              style: { fontStyle: "italic", marginLeft: "6px" },
              text: `${ignoredPath} (hidden from review)`,
            }),
          ],
        }),
      );
    }
    return;
  }

  const hideCb = resolveElement(ctx, "hideAttachmentsCb");
  const hideAttachments = hideCb ? Boolean(hideCb.checked) : false;
  const showClosedCb = resolveElement(ctx, "showClosedCommentsCb");
  const showClosed = showClosedCb ? Boolean(showClosedCb.checked) : false;
  const searchInput = resolveElement(ctx, "fileSearchInput");
  const query = String((searchInput && searchInput.value) || "").trim();

  const visibleUnfilteredCount = rawFiles.filter(
    (f) => !(hideAttachments && isAttachmentPath(f.path)),
  ).length;
  if (headerEl) {
    headerEl.textContent = `Changed Files (${visibleUnfilteredCount})`;
  }

  const displayFiles = filterAndSortReviewFiles(rawFiles, {
    hideAttachments,
    query,
    activeFilePath: state.selectedFile || "",
  });

  const sessionComments = (state.session && state.session.comments) || [];
  const sessionFiles = (state.session && state.session.files) || {};
  const openedInCommit =
    state.openedFilesByCommit && state.selectedCommit
      ? state.openedFilesByCommit[state.selectedCommit]
      : null;

  for (const fileObj of displayFiles) {
    const filePath = String(fileObj.path || "");
    const commentsForFile = sessionComments.filter(
      (c) =>
        c.file_path === filePath &&
        commentMatchesCommit(c, state.selectedCommit) &&
        isCommentVisible(c, showClosed),
    );
    const openCommentsCount = commentsForFile.filter(
      (c) => resolveCommentStatus(c) === COMMENT_STATUS.OPEN,
    ).length;
    const fileState = sessionFiles[filePath];
    const isExplicitlyReviewed = Boolean(fileState && fileState.status === "REVIEWED");
    const isViewed = Boolean(
      openedInCommit && openedInCommit.has(filePath) && filePath !== state.selectedFile,
    );
    const isActive = filePath === state.selectedFile;
    const isLfs = isLfsFile(fileObj);

    const statusBadgeClass =
      fileObj.status === "A"
        ? "quake-badge-green"
        : fileObj.status === "D"
          ? "quake-badge-red"
          : "quake-badge-cyan";

    const parts = filePath.split("/");
    const baseName = parts.pop() || filePath;
    const dirName = parts.join("/");

    const leftChildren = [];
    if (isLfs) {
      leftChildren.push(
        createEl(ctx, "span", { className: "quake-badge quake-badge-lfs", text: "📦 LFS" }),
      );
    }
    leftChildren.push(
      createEl(ctx, "span", {
        className: `quake-badge ${statusBadgeClass}`,
        text: String(fileObj.status || "M"),
      }),
      createEl(ctx, "div", {
        className: "file-name-col",
        children: [
          createEl(ctx, "span", {
            className: "file-title",
            attrs: { title: filePath },
            text: baseName,
          }),
          createEl(ctx, "span", {
            className: "file-subpath",
            attrs: { title: dirName },
            text: dirName,
          }),
        ],
      }),
    );

    const rightChildren = [];
    if (commentsForFile.length > 0) {
      const commentBadgeClass =
        openCommentsCount > 0 ? "quake-badge-amber" : "quake-badge-green";
      rightChildren.push(
        createEl(ctx, "span", {
          className: `quake-badge ${commentBadgeClass}`,
          attrs: {
            title: `${openCommentsCount} open / ${commentsForFile.length - openCommentsCount} resolved`,
          },
          text: `💬 ${commentsForFile.length}`,
        }),
      );
    }
    if (isExplicitlyReviewed) {
      rightChildren.push(
        createEl(ctx, "span", {
          className: "quake-badge quake-badge-green",
          text: "✓",
        }),
      );
    }
    rightChildren.push(
      createEl(ctx, "span", {
        style: { fontSize: "8px", color: "var(--quake-text-dim)" },
        text: `+${fileObj.additions || 0}/-${fileObj.deletions || 0}`,
      }),
    );

    const itemClasses = ["file-item"];
    if (isActive) {
      itemClasses.push("active");
    } else if (isViewed) {
      itemClasses.push("viewed");
    }
    if (isLfs) {
      itemClasses.push("lfs-file-item");
    }

    listEl.appendChild(
      createEl(ctx, "li", {
        className: itemClasses.join(" "),
        dataset: { filePath },
        children: [
          createEl(ctx, "div", { className: "file-left", children: leftChildren }),
          createEl(ctx, "div", { className: "file-right", children: rightChildren }),
        ],
      }),
    );
  }

  if (!listEl.dataset.boundReviewFiles) {
    listEl.dataset.boundReviewFiles = "1";
    bindDelegatedEvent(listEl, "click", ".file-item", (_event, itemEl) => {
      const targetPath = itemEl.dataset.filePath || "";
      if (targetPath && typeof callbacks.onSelectFile === "function") {
        callbacks.onSelectFile(targetPath);
      }
    });
  }
}

/**
 * Extract contiguous changed line blocks (`{ startLine, endLine, type }`) from a diff payload
 * for hunk-by-hunk navigation (`J`/`K`, `Prev`/`Next`, `nc`/`pc`).
 *
 * @param {object|null} diffData - Loaded diff payload.
 * @returns {Array<{startLine: number, endLine: number, type: string}>}
 */
export function getFileChanges(diffData) {
  if (!diffData) {
    return [];
  }
  const rows = Array.isArray(diffData.side_by_side) ? diffData.side_by_side : [];
  const changes = [];
  let currentChange = null;

  for (const row of rows) {
    if (row.row_type && row.row_type !== "equal") {
      const lineNo = row.new_no || row.old_no;
      if (!currentChange) {
        currentChange = {
          startLine: lineNo || 1,
          endLine: lineNo || 1,
          type: row.row_type,
        };
      } else if (lineNo) {
        currentChange.endLine = lineNo;
      }
    } else if (currentChange) {
      changes.push(currentChange);
      currentChange = null;
    }
  }
  if (currentChange) {
    changes.push(currentChange);
  }

  if (changes.length === 0 && Array.isArray(diffData.hunks) && diffData.hunks.length > 0) {
    for (const hunk of diffData.hunks) {
      const start = hunk.new_start || hunk.old_start || 1;
      const count = Math.max(hunk.new_count || 0, hunk.old_count || 0, 1);
      changes.push({
        startLine: start,
        endLine: start + count - 1,
        type: "hunk",
      });
    }
  }

  return changes;
}

/**
 * Persist a file's review status (`"REVIEWED"` | `"PENDING"`) via `POST /api/file_status`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} filePath - Target repository-relative file path.
 * @param {string} status - `"REVIEWED"` or `"PENDING"`.
 * @returns {Promise<object>} Parsed JSON response.
 */
export async function setFileReviewStatus(ctx, filePath, status) {
  return ctx.postJson("/api/file_status", { path: filePath, status });
}
