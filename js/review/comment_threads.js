/**
 * Inline Code Review Comment Rendering, File Reference Linking, & Comment CRUD (`comment_threads.js`).
 *
 * Shared 100% byte-identically across `hardware` and `firmware` Code Review workstations.
 * Zero browser globals: all DOM construction, syntax highlighting, and HTTP requests
 * flow through an explicit `RuntimeContext` (`ctx`).
 */

import { bindDelegatedEvent, createEl } from "../core/dom.js";
import { escapeHtml, sanitizeAuthor } from "../core/sanitize.js";
import { highlightCodeBlock } from "../diff/diff_engine.js";

const FILE_REF_REGEX =
  /(@\[([^\]]+)\]|(?:^|(?<=\s))@([a-zA-Z0-9_./\\-]+(?::L?\d+(?:-L?\d+)?)?))/g;
const TRAILING_PUNCT_REGEX = /[.,;:!?)]+$/;
const FENCED_CODE_REGEX = /```(\w*)\r?\n([\s\S]*?)```/g;
const INLINE_CODE_REGEX = /`([^`\r\n]+)`/g;
const CLOSED_CARD_OPACITY = "0.72";

/**
 * Canonical lifecycle statuses for Code Review comments.
 */
export const COMMENT_STATUS = Object.freeze({
  OPEN: "OPEN",
  RESOLVED: "RESOLVED",
  CLOSED: "CLOSED",
});

/**
 * Normalize the lifecycle status of a review comment (`OPEN`, `RESOLVED`, or `CLOSED`).
 *
 * Falls back to `comment.resolved ? "RESOLVED" : "OPEN"` when `comment.status` is absent.
 *
 * @param {object|null|undefined} comment - Review comment model.
 * @returns {string} `"OPEN"` | `"RESOLVED"` | `"CLOSED"`.
 */
export function resolveCommentStatus(comment) {
  if (!comment) {
    return COMMENT_STATUS.OPEN;
  }
  const raw = String(comment.status || "").trim().toUpperCase();
  if (raw === COMMENT_STATUS.CLOSED) {
    return COMMENT_STATUS.CLOSED;
  }
  if (raw === COMMENT_STATUS.RESOLVED) {
    return COMMENT_STATUS.RESOLVED;
  }
  if (raw === COMMENT_STATUS.OPEN) {
    return comment.resolved ? COMMENT_STATUS.RESOLVED : COMMENT_STATUS.OPEN;
  }
  return comment.resolved ? COMMENT_STATUS.RESOLVED : COMMENT_STATUS.OPEN;
}

/**
 * Determine whether `comment` should be displayed in active diff/file views.
 *
 * `OPEN` and `RESOLVED` comments are always visible; `CLOSED` comments are hidden
 * unless `showClosed` is enabled.
 *
 * @param {object|null|undefined} comment - Review comment model.
 * @param {boolean} [showClosed] - Whether closed comments should be shown.
 * @returns {boolean} True when comment should be displayed.
 */
export function isCommentVisible(comment, showClosed = false) {
  if (showClosed) {
    return true;
  }
  return resolveCommentStatus(comment) !== COMMENT_STATUS.CLOSED;
}

/**
 * Resolve badge CSS class and display label for a comment lifecycle status.
 *
 * @param {string} status - `"OPEN"` | `"RESOLVED"` | `"CLOSED"`.
 * @returns {{badgeClass: string, displayLabel: string}}
 */
export function resolveStatusBadge(status) {
  const upper = String(status || "").toUpperCase();
  switch (upper) {
    case COMMENT_STATUS.RESOLVED:
      return { badgeClass: "quake-badge-green", displayLabel: "RESOLVED" };
    case COMMENT_STATUS.CLOSED:
      return { badgeClass: "quake-badge-default", displayLabel: "CLOSED" };
    default:
      return { badgeClass: "quake-badge-amber", displayLabel: "OPEN" };
  }
}

/**
 * Reverse basic HTML entity escaping inside fenced code blocks prior to syntax highlighting.
 *
 * @param {string} str - Escaped HTML text.
 * @returns {string} Raw code string.
 */
export function unescapeHtml(str) {
  if (!str) {
    return "";
  }
  return String(str)
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'");
}

/**
 * Convert `@path/to/file.py:42` and `@[path/to/file.py:42]` references in already-escaped
 * comment prose into delegated `.quake-file-ref` elements with `data-action="goto-ref"`
 * (zero inline `onclick=` attributes).
 *
 * @param {string} escapedText - HTML-escaped prose text.
 * @returns {string} HTML string with interactive `.quake-file-ref` spans.
 */
export function parseFileReferences(escapedText) {
  if (!escapedText) {
    return "";
  }
  return String(escapedText).replace(
    FILE_REF_REGEX,
    (match, _full, bracketed, plain) => {
      let trailingPunct = "";
      let rawRef = bracketed || plain;
      if (plain) {
        const punctMatch = plain.match(TRAILING_PUNCT_REGEX);
        if (punctMatch) {
          trailingPunct = punctMatch[0];
          rawRef = plain.slice(0, -trailingPunct.length);
        }
      }
      if (!rawRef) {
        return match;
      }
      if (plain && !(rawRef.includes("/") || rawRef.includes(".") || rawRef.includes(":"))) {
        return match;
      }

      const trimmed = rawRef.trim();
      let filePart = trimmed;
      let linePart = null;
      if (trimmed.includes(":")) {
        const colonIdx = trimmed.indexOf(":");
        filePart = trimmed.slice(0, colonIdx);
        const rawLine = trimmed.slice(colonIdx + 1).replace(/^L/i, "");
        const parsedLine = Number.parseInt(rawLine, 10);
        if (Number.isFinite(parsedLine) && parsedLine > 0) {
          linePart = parsedLine;
        }
      }

      const unescapedFile = unescapeHtml(filePart);
      const unescapedTrimmed = unescapeHtml(trimmed);
      const safeFileAttr = escapeHtml(unescapedFile);
      const safeLabel = escapeHtml(unescapedTrimmed);
      const lineAttr = linePart !== null ? ` data-line="${linePart}"` : "";
      return `<span class="quake-file-ref" data-action="goto-ref" data-file="${safeFileAttr}"${lineAttr} title="Jump to @${safeLabel}">📁 @${safeLabel}</span>${trailingPunct}`;
    },
  );
}

/**
 * Render a Markdown-lite review comment body safely into HTML:
 * - Escapes raw HTML tags to prevent XSS
 * - Syntax-highlights fenced ```` ```lang ```` code blocks via `highlightCodeBlock`
 * - Preserves inline `` `code` `` spans
 * - Converts `@file:line` references into delegated `.quake-file-ref` spans
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} text - Raw comment Markdown text.
 * @param {string} [defaultLang] - Fallback language for unlabeled fenced blocks.
 * @returns {string} Safe HTML fragment.
 */
export function renderCommentBody(ctx, text, defaultLang = "plaintext") {
  if (!text) {
    return "";
  }
  let html = escapeHtml(text);
  const codeBlocks = [];

  html = html.replace(FENCED_CODE_REGEX, (_match, lang, code) => {
    const unescaped = unescapeHtml(code);
    const highlighted = highlightCodeBlock(ctx, unescaped, lang || defaultLang);
    const token = `__CR_CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push(`<pre class="hljs comment-code-block"><code>${highlighted}</code></pre>`);
    return token;
  });

  const inlineCodes = [];
  html = html.replace(INLINE_CODE_REGEX, (_match, code) => {
    const token = `__CR_INLINE_CODE_${inlineCodes.length}__`;
    inlineCodes.push(`<code class="comment-inline-code">${code}</code>`);
    return token;
  });

  html = parseFileReferences(html);

  for (let idx = 0; idx < inlineCodes.length; idx += 1) {
    html = html.replace(`__CR_INLINE_CODE_${idx}__`, inlineCodes[idx]);
  }
  for (let idx = 0; idx < codeBlocks.length; idx += 1) {
    html = html.replace(`__CR_CODE_BLOCK_${idx}__`, codeBlocks[idx]);
  }

  return html;
}

/**
 * Resolve badge CSS class and display label for a comment severity string.
 *
 * @param {string} severity - `"MUST_FIX"` | `"PROPOSAL"` | `"NIT"`.
 * @returns {{badgeClass: string, displayLabel: string}}
 */
export function resolveSeverityBadge(severity) {
  const upper = String(severity || "").toUpperCase();
  switch (upper) {
    case "MUST_FIX":
      return { badgeClass: "quake-badge-red", displayLabel: "MUST FIX" };
    case "PROPOSAL":
      return { badgeClass: "quake-badge-gold", displayLabel: "PROPOSAL" };
    default:
      return { badgeClass: "quake-badge-cyan", displayLabel: "NIT" };
  }
}

/**
 * Build a `.inline-comment-card` DOM element for an inline diff comment with delegated
 * lifecycle status (`Resolve`, `Close`, `Reopen`), Edit, Delete, and `@file:line` handlers.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} comment - Review comment model (`id`, `severity`, `status`, `resolved`, `start_line`, `end_line`, `author`, `created_at`, `body`, `code_snippet`, `resolution_notes`).
 * @param {object} [options] - Card rendering options.
 * @param {string} [options.language] - Active file language for snippet/code highlighting.
 * @param {Array<string>} [options.authorBlacklist] - Dynamic personal tokens to redact.
 * @param {Function|null} [options.onStatusChange] - `(commentId, newStatus) => void` callback.
 * @param {Function|null} [options.onEdit] - `(commentId) => void` callback.
 * @param {Function|null} [options.onDelete] - `(commentId) => void` callback.
 * @param {Function|null} [options.onGotoRef] - `(filePath, lineNo) => void` callback.
 * @returns {HTMLElement} Rendered `.inline-comment-card` element.
 */
export function createInlineCommentCard(ctx, comment, options = {}) {
  const language = options.language || "plaintext";
  const blacklist = options.authorBlacklist || [];
  const { badgeClass, displayLabel } = resolveSeverityBadge(comment.severity);
  const commentStatus = resolveCommentStatus(comment);
  const { badgeClass: statusBadgeClass, displayLabel: statusLabel } =
    resolveStatusBadge(commentStatus);

  const startLine = Number(comment.start_line || 1);
  const endLine = Number(comment.end_line || startLine);
  const rangeText = startLine !== endLine ? `Lines L${startLine}-L${endLine}` : `Lines L${startLine}`;

  const safeAuthor = sanitizeAuthor(comment.author, blacklist);
  const createdRaw = String(comment.created_at || "");
  const timePart = createdRaw.length >= 19 ? ` (${createdRaw.slice(11, 19)})` : "";
  const cidStr = String(comment.id || "");

  const actionButtons = [];
  if (commentStatus === COMMENT_STATUS.OPEN) {
    actionButtons.push(
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-green",
        style: { padding: "1px 6px", fontSize: "8px" },
        attrs: { type: "button", title: "Mark comment as RESOLVED" },
        dataset: {
          action: "set-comment-status",
          status: COMMENT_STATUS.RESOLVED,
          commentId: cidStr,
        },
        text: "Resolve ✓",
      }),
    );
  } else if (commentStatus === COMMENT_STATUS.RESOLVED) {
    actionButtons.push(
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-cyan",
        style: { padding: "1px 6px", fontSize: "8px" },
        attrs: { type: "button", title: "Verify and CLOSE resolved comment" },
        dataset: {
          action: "set-comment-status",
          status: COMMENT_STATUS.CLOSED,
          commentId: cidStr,
        },
        text: "Close ✓✓",
      }),
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-default",
        style: { padding: "1px 6px", fontSize: "8px" },
        attrs: { type: "button", title: "Reopen comment to OPEN" },
        dataset: {
          action: "set-comment-status",
          status: COMMENT_STATUS.OPEN,
          commentId: cidStr,
        },
        text: "Reopen ↺",
      }),
    );
  } else {
    actionButtons.push(
      createEl(ctx, "button", {
        className: "quake-btn quake-btn-default",
        style: { padding: "1px 6px", fontSize: "8px" },
        attrs: { type: "button", title: "Reopen closed comment to OPEN" },
        dataset: {
          action: "set-comment-status",
          status: COMMENT_STATUS.OPEN,
          commentId: cidStr,
        },
        text: "Reopen ↺",
      }),
    );
  }

  actionButtons.push(
    createEl(ctx, "button", {
      className: "quake-btn quake-btn-default",
      style: { padding: "1px 6px", fontSize: "8px" },
      attrs: { type: "button" },
      dataset: { action: "edit-comment", commentId: cidStr },
      text: "Edit ✎",
    }),
    createEl(ctx, "button", {
      className: "quake-btn quake-btn-default",
      style: { padding: "1px 6px", fontSize: "8px" },
      attrs: { type: "button" },
      dataset: { action: "delete-comment", commentId: cidStr },
      text: "Delete ✕",
    }),
  );

  const children = [
    createEl(ctx, "div", {
      className: "inline-comment-header",
      children: [
        createEl(ctx, "div", {
          style: { display: "flex", alignItems: "center", gap: "8px" },
          children: [
            createEl(ctx, "span", {
              className: `quake-badge ${badgeClass}`,
              text: `[${displayLabel}]`,
            }),
            createEl(ctx, "span", {
              className: `quake-badge ${statusBadgeClass}`,
              dataset: { commentStatus },
              text: `[${statusLabel}]`,
            }),
            createEl(ctx, "span", {
              style: { fontSize: "9px", color: "var(--quake-gold)", fontWeight: "700" },
              text: rangeText,
            }),
            createEl(ctx, "span", {
              className: "inline-comment-author",
              style: { fontSize: "8px", color: "var(--quake-text-dim)" },
              text: `by ${safeAuthor}${timePart}`,
            }),
          ],
        }),
        createEl(ctx, "div", {
          style: { display: "flex", alignItems: "center", gap: "4px" },
          children: actionButtons,
        }),
      ],
    }),
  ];

  if (comment.code_snippet) {
    const highlightedSnippet = highlightCodeBlock(ctx, String(comment.code_snippet), language);
    const snippetPre = createEl(ctx, "pre", { className: "hljs snippet-pre" });
    snippetPre.innerHTML = `<code>${highlightedSnippet}</code>`;
    children.push(
      createEl(ctx, "div", {
        className: "inline-comment-snippet",
        children: [
          createEl(ctx, "div", { className: "snippet-label", text: "SNIPPET:" }),
          snippetPre,
        ],
      }),
    );
  }

  const bodyEl = createEl(ctx, "div", { className: "inline-comment-body" });
  bodyEl.innerHTML = renderCommentBody(ctx, String(comment.body || ""), language);
  children.push(bodyEl);

  if (comment.resolution_notes && String(comment.resolution_notes).trim()) {
    const notesEl = createEl(ctx, "div", {
      className: "inline-comment-resolution",
      style: {
        marginTop: "6px",
        paddingTop: "4px",
        borderTop: "1px dashed var(--quake-border)",
        fontSize: "9px",
        color: "var(--quake-green)",
      },
    });
    notesEl.innerHTML = `<strong>Resolution:</strong> ${renderCommentBody(
      ctx,
      String(comment.resolution_notes).trim(),
      language,
    )}`;
    children.push(notesEl);
  }

  const cardStyle =
    commentStatus === COMMENT_STATUS.CLOSED ? { opacity: CLOSED_CARD_OPACITY } : undefined;
  const card = createEl(ctx, "div", {
    className: "inline-comment-card",
    style: cardStyle,
    dataset: { commentId: cidStr, commentStatus },
    children,
  });

  // Prevent clicks inside comment cards from bubbling up to diff row selection
  card.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  bindDelegatedEvent(card, "click", "[data-action]", (event, actionEl) => {
    event.stopPropagation();
    const action = actionEl.dataset.action;
    if (action === "set-comment-status" && typeof options.onStatusChange === "function") {
      options.onStatusChange(
        actionEl.dataset.commentId || cidStr,
        actionEl.dataset.status || COMMENT_STATUS.RESOLVED,
      );
    } else if (action === "edit-comment" && typeof options.onEdit === "function") {
      options.onEdit(actionEl.dataset.commentId || cidStr);
    } else if (action === "delete-comment" && typeof options.onDelete === "function") {
      options.onDelete(actionEl.dataset.commentId || cidStr);
    } else if (action === "goto-ref" && typeof options.onGotoRef === "function") {
      const targetFile = actionEl.dataset.file || "";
      const rawLine = actionEl.dataset.line;
      const parsedLine = rawLine ? Number.parseInt(rawLine, 10) : null;
      options.onGotoRef(targetFile, Number.isFinite(parsedLine) ? parsedLine : null);
    }
  });

  return card;
}

/**
 * Update the lifecycle status (`OPEN`, `RESOLVED`, `CLOSED`) of an existing review comment
 * via `POST /api/comment/status`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} commentId - Target comment ID.
 * @param {string} status - `"OPEN"` | `"RESOLVED"` | `"CLOSED"`.
 * @param {string} [notes] - Optional resolution/acceptance/reopen notes.
 * @returns {Promise<object>} Parsed JSON response.
 */
export async function updateReviewCommentStatus(ctx, commentId, status, notes = "") {
  const payload = { id: commentId, status };
  if (notes) {
    payload.notes = notes;
  }
  return ctx.postJson("/api/comment/status", payload);
}

/**
 * Submit a new inline or file-level review comment to `POST /api/comment`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} payload - Comment creation payload.
 * @returns {Promise<object>} Parsed JSON response.
 */
export async function postReviewComment(ctx, payload) {
  return ctx.postJson("/api/comment", payload);
}

/**
 * Update an existing review comment body via `POST /api/comment/edit`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} commentId - Target comment ID.
 * @param {string} newBody - Updated Markdown body.
 * @returns {Promise<object>} Parsed JSON response.
 */
export async function editReviewComment(ctx, commentId, newBody) {
  return ctx.postJson("/api/comment/edit", { id: commentId, body: newBody });
}

/**
 * Delete an existing review comment via `DELETE /api/comment?id=...`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} commentId - Target comment ID.
 * @returns {Promise<object>} Parsed JSON response.
 */
export async function deleteReviewComment(ctx, commentId) {
  return ctx.fetchJson(`/api/comment?id=${encodeURIComponent(commentId)}`, {
    method: "DELETE",
  });
}
