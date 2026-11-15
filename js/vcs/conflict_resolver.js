/**
 * Merge Conflict Resolution Controls & API Actions (`conflict_resolver.js`).
 *
 * Renders conflict file rows (`ours`, `theirs`, `mark_resolved`, `discard`) and
 * posts conflict resolution actions via `RuntimeContext`.
 */

import { createEl } from "../core/dom.js";
import { showToast } from "../core/toast.js";

/**
 * Post a conflict resolution strategy (`"ours"`, `"theirs"`, `"mark_resolved"`) for `filePath`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} filePath - Conflicted repository-relative path.
 * @param {string} resolution - Resolution strategy identifier.
 * @param {Function} [onResolved] - Optional async refresh callback invoked on success.
 * @returns {Promise<boolean>} True if resolved without error.
 */
export async function resolveConflictFile(ctx, filePath, resolution, onResolved) {
  if (!filePath || !resolution) {
    return false;
  }
  const response = await ctx.fetchRaw("/api/resolve_conflict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: filePath, resolution }),
  });
  const payload = await response.json();
  if (!response.ok || (payload && payload.error)) {
    showToast(
      ctx,
      `Resolution error: ${(payload && payload.error) || `HTTP ${response.status}`}`,
      "error",
    );
    return false;
  }
  showToast(ctx, `Resolved ${filePath} (${resolution})`);
  if (typeof onResolved === "function") {
    await onResolved();
  }
  return true;
}

/**
 * Create the collapsible `.group-section` element listing conflicted working-tree files.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {Array<object>} conflicts - Conflict file records.
 * @param {string|null} activeFile - Currently selected file path.
 * @returns {HTMLElement|null} Group section element or `null` if no conflicts exist.
 */
export function createConflictGroupElement(ctx, conflicts, activeFile) {
  if (!Array.isArray(conflicts) || conflicts.length === 0) {
    return null;
  }

  const itemsContainer = createEl(ctx, "div", { className: "group-items" });
  for (const conflict of conflicts) {
    const filePath = String(conflict.path || "");
    const markerCount = Number(conflict.conflict_markers_count || 0);
    const checkbox = createEl(ctx, "input", {
      className: "working-file-cb",
      attrs: { type: "checkbox", value: filePath },
    });

    const row = createEl(ctx, "div", {
      className: `file-item${activeFile === filePath ? " active" : ""}`,
      dataset: { path: filePath },
      children: [
        checkbox,
        createEl(ctx, "span", { className: "file-status-badge status-conflict", text: "UU" }),
        createEl(ctx, "span", {
          className: "file-path",
          text: `${filePath} (${markerCount} markers)`,
          attrs: { title: filePath },
        }),
        createEl(ctx, "div", {
          className: "file-actions",
          children: [
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-default quake-btn-icon",
              text: "👈",
              attrs: { type: "button", title: "Accept Ours" },
              dataset: { action: "resolve-conflict", path: filePath, resolution: "ours" },
            }),
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-default quake-btn-icon",
              text: "👉",
              attrs: { type: "button", title: "Accept Theirs" },
              dataset: { action: "resolve-conflict", path: filePath, resolution: "theirs" },
            }),
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-gold quake-btn-icon",
              text: "✓",
              attrs: { type: "button", title: "Mark Resolved" },
              dataset: {
                action: "resolve-conflict",
                path: filePath,
                resolution: "mark_resolved",
              },
            }),
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-red quake-btn-icon",
              text: "🗑",
              attrs: { type: "button", title: "Discard conflict file" },
              dataset: { action: "discard-file", path: filePath },
            }),
          ],
        }),
      ],
    });
    itemsContainer.appendChild(row);
  }

  return createEl(ctx, "div", {
    className: "group-section",
    children: [
      createEl(ctx, "div", {
        className: "group-header",
        text: `⚠ Merge Conflicts (${conflicts.length})`,
        style: { color: "var(--quake-red)" },
      }),
      itemsContainer,
    ],
  });
}
