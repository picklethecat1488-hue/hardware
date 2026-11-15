/**
 * Shared Zero-Globals Diff & Syntax Highlighting Engine (`diff_engine.js`).
 *
 * Used identically by both the VCS Diff Workstation (`js/vcs/`) and the
 * Code Review Terminal (`js/review/`) across `hardware` and `firmware`.
 * All DOM creation, syntax highlighting (`hljs`), viewport events, and storage
 * access are routed strictly through an explicit `RuntimeContext` (`ctx`).
 */

import { bindDelegatedEvent, clearChildren, createEl, resolveElement } from "../core/dom.js";
import { escapeHtml } from "../core/sanitize.js";

export const MAX_LINE_LENGTH = 1000;
export const MAX_HIGHLIGHT_LINES = 3000;
export const MAX_HIGHLIGHT_CHARS = 300000;

const MIN_SPLIT_RATIO = 0.15;
const MAX_SPLIT_RATIO = 0.85;
const DEFAULT_SBS_STORAGE_KEY = "vcs_sbs_split_ratio";
const BORDER_GRAB_MAX_OFFSET_PX = 8;
const BORDER_GRAB_MIN_OFFSET_PX = -4;
const TRUNCATION_SUFFIX = "… [line truncated]";
const IMAGE_EXTENSION_PATTERN = /\.(png|jpe?g|gif|svg|webp|ico)$/i;

const EXTENSION_LANGUAGE_MAP = Object.freeze({
  py: "python",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  rs: "rust",
  html: "xml",
  htm: "xml",
  j2: "xml",
  xml: "xml",
  svg: "xml",
  yaml: "yaml",
  yml: "yaml",
  json: "json",
  md: "markdown",
  css: "css",
  scss: "css",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hpp: "cpp",
  glsl: "cpp",
  vert: "cpp",
  frag: "cpp",
  sql: "sql",
  ini: "ini",
  toml: "ini",
  cfg: "ini",
});

/**
 * Detect the syntax-highlighting language identifier from a file path.
 *
 * @param {string} filePath - Repository-relative or absolute file path.
 * @returns {string} Highlight.js language identifier (`"plaintext"` fallback).
 */
export function detectLanguage(filePath) {
  if (!filePath || typeof filePath !== "string") {
    return "plaintext";
  }
  const slashIdx = Math.max(filePath.lastIndexOf("/"), filePath.lastIndexOf("\\"));
  const baseName = (slashIdx >= 0 ? filePath.slice(slashIdx + 1) : filePath).toLowerCase();
  if (baseName === "makefile" || baseName === "gnumakefile") {
    return "makefile";
  }
  if (baseName === "dockerfile" || baseName.startsWith("dockerfile.")) {
    return "dockerfile";
  }
  const parts = baseName.split(".");
  if (parts.length < 2) {
    return "plaintext";
  }
  const ext = parts[parts.length - 1];
  return EXTENSION_LANGUAGE_MAP[ext] || "plaintext";
}

/**
 * Truncate an excessively long source line to prevent layout and regex stalls.
 *
 * @param {string} text - Raw single-line text.
 * @param {number} [maxLen] - Maximum allowed character count before truncation.
 * @returns {string} Truncated line string.
 */
export function truncateLine(text, maxLen = MAX_LINE_LENGTH) {
  if (!text) {
    return "";
  }
  const str = String(text);
  const limit = typeof maxLen === "number" && maxLen > 0 ? maxLen : MAX_LINE_LENGTH;
  if (str.length > limit) {
    return `${str.slice(0, limit)}${TRUNCATION_SUFFIX}`;
  }
  return str;
}

/**
 * Balance multi-line `<span ...>...</span>` highlight tags across line breaks
 * so every rendered table cell or grid row has self-contained, valid HTML.
 * Orphan closing `</span>` tags are stripped so they never close parent containers.
 *
 * @param {string[]} rawLines - Highlighted HTML split on line boundaries.
 * @returns {string[]} Span-balanced HTML lines.
 */
export function balanceLines(rawLines) {
  if (!Array.isArray(rawLines) || rawLines.length === 0) {
    return [];
  }
  const resultLines = [];
  const openTags = [];

  for (const rawLine of rawLines) {
    const line = String(rawLine ?? "");
    const prefix = openTags.join("");
    let processedLine = "";
    let lastIndex = 0;
    const tagRegex = /<(\/?)span([^>]*)>/g;
    let match = tagRegex.exec(line);

    while (match !== null) {
      const isClosing = match[1] === "/";
      const fullTag = match[0];
      if (isClosing) {
        if (openTags.length > 0) {
          openTags.pop();
          processedLine += line.slice(lastIndex, match.index) + fullTag;
        } else {
          processedLine += line.slice(lastIndex, match.index);
        }
      } else {
        openTags.push(fullTag);
        processedLine += line.slice(lastIndex, match.index) + fullTag;
      }
      lastIndex = tagRegex.lastIndex;
      match = tagRegex.exec(line);
    }
    processedLine += line.slice(lastIndex);

    let suffix = "";
    for (let idx = openTags.length - 1; idx >= 0; idx -= 1) {
      suffix += "</span>";
    }
    resultLines.push(prefix + processedLine + suffix);
  }

  return resultLines;
}

/**
 * Invoke the page's syntax highlighter (`hljs`) if present and valid for `lang`.
 *
 * @param {object} highlighter - Highlight.js instance from `ctx.getSyntaxHighlighter()`.
 * @param {string} code - Source text to highlight.
 * @param {string} lang - Language identifier.
 * @returns {string|null} Highlighted HTML string, or `null` if unavailable.
 */
function runHighlighter(highlighter, code, lang) {
  if (!highlighter) {
    return null;
  }
  const hasNamedLang =
    Boolean(lang) &&
    lang !== "plaintext" &&
    typeof highlighter.getLanguage === "function" &&
    Boolean(highlighter.getLanguage(lang));

  if (hasNamedLang && typeof highlighter.highlight === "function") {
    const res = highlighter.highlight(code, { language: lang, ignoreIllegals: true });
    return res && typeof res.value === "string" ? res.value : null;
  }
  if (typeof highlighter.highlightAuto === "function" && lang !== "plaintext") {
    const res = highlighter.highlightAuto(code);
    return res && typeof res.value === "string" ? res.value : null;
  }
  return null;
}

/**
 * Syntax-highlight a single line of code safely with span balancing.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} text - Single source line.
 * @param {string} lang - Highlight language name.
 * @returns {string} Escaped or highlighted HTML for the line.
 */
export function highlightLine(ctx, text, lang) {
  if (!text) {
    return "";
  }
  const truncated = truncateLine(text);
  const highlighter = ctx ? ctx.getSyntaxHighlighter() : null;
  const highlighted = runHighlighter(highlighter, truncated, lang);
  if (highlighted === null) {
    return escapeHtml(truncated);
  }
  return balanceLines([highlighted])[0] || "";
}

/**
 * Syntax-highlight a full document and return span-balanced per-line HTML strings.
 * Falls back to fast HTML escaping when the file exceeds highlight thresholds.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} code - Complete document source text.
 * @param {string} lang - Highlight language name.
 * @returns {string[]} Array of span-balanced HTML strings, one per line.
 */
export function highlightFullDocument(ctx, code, lang) {
  if (!code) {
    return [];
  }
  const rawLines = String(code).split(/\r?\n/);
  const truncatedLines = rawLines.map((line) => truncateLine(line));
  const highlighter = ctx ? ctx.getSyntaxHighlighter() : null;

  if (
    !highlighter ||
    truncatedLines.length > MAX_HIGHLIGHT_LINES ||
    code.length > MAX_HIGHLIGHT_CHARS
  ) {
    return truncatedLines.map((line) => escapeHtml(line));
  }

  const joined = truncatedLines.join("\n");
  const highlighted = runHighlighter(highlighter, joined, lang);
  if (highlighted === null) {
    return truncatedLines.map((line) => escapeHtml(line));
  }
  return balanceLines(highlighted.split(/\r?\n/));
}

/**
 * Syntax-highlight a multi-line code snippet (e.g. fenced Markdown block).
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} code - Code snippet text.
 * @param {string} lang - Language identifier.
 * @returns {string} Highlighted HTML string.
 */
export function highlightCodeBlock(ctx, code, lang) {
  if (!code) {
    return "";
  }
  return highlightFullDocument(ctx, code, lang).join("\n");
}

/**
 * Check whether a 1-based line number falls within an active selection range.
 *
 * @param {{start: number, end: number, side?: string}|null} selectedRange - Active range.
 * @param {number|null|undefined} lineNo - Candidate 1-based line number.
 * @param {string} [side] - `"old"` or `"new"` side tag.
 * @returns {boolean} True when selected.
 */
function isLineSelected(selectedRange, lineNo, side) {
  if (!selectedRange || !lineNo) {
    return false;
  }
  if (selectedRange.side && side && selectedRange.side !== side) {
    return false;
  }
  const minLine = Math.min(selectedRange.start, selectedRange.end);
  const maxLine = Math.max(selectedRange.start, selectedRange.end);
  return lineNo >= minLine && lineNo <= maxLine;
}

/**
 * Collect inline comments anchored to a specific line number and side.
 *
 * @param {Array<object>} comments - File comments list.
 * @param {number|null|undefined} oldNo - Old revision line number.
 * @param {number|null|undefined} newNo - New revision line number.
 * @returns {Array<object>} Matching comment records.
 */
function matchingCommentsForRow(comments, oldNo, newNo) {
  if (!Array.isArray(comments) || comments.length === 0) {
    return [];
  }
  return comments.filter((comment) => {
    const anchorLine = comment.end_line || comment.line || comment.start_line || 0;
    if (!anchorLine) {
      return false;
    }
    if (comment.side === "old") {
      return Boolean(oldNo) && anchorLine === oldNo;
    }
    if (newNo && anchorLine === newNo) {
      return true;
    }
    return !newNo && Boolean(oldNo) && anchorLine === oldNo;
  });
}

/**
 * Attach horizontal column split dragging to a side-by-side diff table.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|null} table - `.diff-sbs-table` element.
 * @param {string} [storageKey] - Persistent storage key for split ratio.
 */
export function setupSbsResizer(ctx, table, storageKey = DEFAULT_SBS_STORAGE_KEY) {
  if (!ctx || !table) {
    return;
  }
  const resizer = table.querySelector(".sbs-split-resizer");
  if (!resizer) {
    return;
  }

  const applyRatio = (ratio) => {
    const clamped = Math.max(MIN_SPLIT_RATIO, Math.min(MAX_SPLIT_RATIO, ratio));
    const pctOld = (clamped * 100).toFixed(1);
    const pctNew = ((1 - clamped) * 100).toFixed(1);
    const oldCol = table.querySelector(".col-old-code");
    const newCol = table.querySelector(".col-new-code");
    if (oldCol && newCol) {
      oldCol.style.width = `${pctOld}%`;
      newCol.style.width = `${pctNew}%`;
    }
    const oldTh = table.querySelector(".th-old");
    const newTh = table.querySelector(".th-new");
    if (oldTh && newTh) {
      oldTh.style.width = `${pctOld}%`;
      newTh.style.width = `${pctNew}%`;
    }
  };

  const storage = ctx.getStorage();
  const saved = storage.getItem(storageKey);
  if (saved !== null) {
    const parsed = Number.parseFloat(saved);
    if (!Number.isNaN(parsed) && parsed >= MIN_SPLIT_RATIO && parsed <= MAX_SPLIT_RATIO) {
      applyRatio(parsed);
    }
  }

  const startDrag = (event) => {
    if (typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    if (typeof event.stopPropagation === "function") {
      event.stopPropagation();
    }
    resizer.classList.add("resizing");
    table.classList.add("resizing-sbs");
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.style.cursor = "col-resize";
      doc.body.style.userSelect = "none";
    }
    const scrollParent =
      table.closest(".diff-scroll-body") ||
      table.closest(".diff-container") ||
      table.parentElement ||
      table;
    const rect = scrollParent.getBoundingClientRect();
    const width = rect.width > 0 ? rect.width : 1;

    const onMouseMove = (moveEvent) => {
      const offsetX = (moveEvent.clientX ?? 0) - rect.left;
      const ratio = Math.max(MIN_SPLIT_RATIO, Math.min(MAX_SPLIT_RATIO, offsetX / width));
      applyRatio(ratio);
      storage.setItem(storageKey, ratio.toFixed(4));
    };

    const onMouseUp = () => {
      resizer.classList.remove("resizing");
      table.classList.remove("resizing-sbs");
      if (doc && doc.body) {
        doc.body.style.cursor = "";
        doc.body.style.userSelect = "";
      }
      ctx.removeViewportListener("mousemove", onMouseMove);
      ctx.removeViewportListener("mouseup", onMouseUp);
    };

    ctx.addViewportListener("mousemove", onMouseMove);
    ctx.addViewportListener("mouseup", onMouseUp);
  };

  resizer.addEventListener("mousedown", startDrag);
  table.addEventListener("mousedown", (event) => {
    const target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }
    const cell = target.closest(".old-code") || target.closest(".th-old");
    if (!cell) {
      return;
    }
    const rect = cell.getBoundingClientRect();
    const delta = rect.right - (event.clientX ?? 0);
    if (delta <= BORDER_GRAB_MAX_OFFSET_PX && delta >= BORDER_GRAB_MIN_OFFSET_PX) {
      startDrag(event);
    }
  });
}

/**
 * Render binary diff card and optional previous/active image comparison without inline handlers.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement} container - Target container.
 * @param {object} diffData - Diff payload.
 * @param {string} rawEndpoint - Base endpoint for raw binary downloads.
 */
function renderBinaryDiff(ctx, container, diffData, rawEndpoint) {
  const filePath = String(diffData.file_path || "");
  const commitRef = String(diffData.commit || "HEAD");
  const oldUrl = `${rawEndpoint}?commit=${encodeURIComponent(commitRef)}&file=${encodeURIComponent(filePath)}&parent=true`;
  const newUrl = `${rawEndpoint}?commit=${encodeURIComponent(commitRef)}&file=${encodeURIComponent(filePath)}&parent=false`;

  const box = createEl(ctx, "div", {
    className: "diff-binary-box binary-diff-view",
    children: [
      createEl(ctx, "div", { className: "diff-binary-icon", text: "💾" }),
      createEl(ctx, "div", {
        className: "binary-diff-badge",
        text: "BINARY FILE DIFF",
      }),
      createEl(ctx, "div", { className: "binary-diff-msg", text: filePath }),
      createEl(ctx, "div", {
        className: "diff-binary-links binary-diff-links",
        children: [
          createEl(ctx, "a", {
            className: "quake-btn quake-btn-default binary-diff-link",
            text: "Download Old",
            attrs: { href: oldUrl, download: "" },
          }),
          createEl(ctx, "a", {
            className: "quake-btn quake-btn-gold binary-diff-link",
            text: "Download New",
            attrs: { href: newUrl, download: "" },
          }),
        ],
      }),
    ],
  });

  if (IMAGE_EXTENSION_PATTERN.test(filePath)) {
    const oldImg = createEl(ctx, "img", {
      attrs: { src: oldUrl, alt: "Previous image" },
      style: {
        maxWidth: "240px",
        maxHeight: "240px",
        border: "1px solid #5a381e",
        background: "#120c08",
      },
    });
    oldImg.addEventListener("error", () => {
      oldImg.style.display = "none";
    });

    const newImg = createEl(ctx, "img", {
      attrs: { src: newUrl, alt: "Active image" },
      style: {
        maxWidth: "240px",
        maxHeight: "240px",
        border: "1px solid #ffb800",
        background: "#120c08",
      },
    });
    newImg.addEventListener("error", () => {
      newImg.style.display = "none";
    });

    const compareRow = createEl(ctx, "div", {
      className: "binary-image-comparison",
      style: {
        display: "flex",
        gap: "20px",
        justifyContent: "center",
        alignItems: "center",
        marginTop: "12px",
      },
      children: [
        createEl(ctx, "div", {
          className: "binary-image-box",
          children: [
            createEl(ctx, "div", { className: "binary-image-title", text: "Previous" }),
            oldImg,
          ],
        }),
        createEl(ctx, "div", {
          className: "binary-image-box",
          children: [
            createEl(ctx, "div", { className: "binary-image-title", text: "Active" }),
            newImg,
          ],
        }),
      ],
    });
    box.appendChild(compareRow);
  }

  container.appendChild(box);
}

/**
 * Render an oversized-diff warning panel with a raw file link.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement} container - Target container.
 * @param {object} diffData - Diff payload.
 * @param {string} rawEndpoint - Base endpoint for raw file inspection.
 */
function renderOversizedDiff(ctx, container, diffData, rawEndpoint) {
  const filePath = String(diffData.file_path || "");
  const commitRef = String(diffData.commit || "working");
  const rawUrl = `${rawEndpoint}?commit=${encodeURIComponent(commitRef)}&file=${encodeURIComponent(filePath)}&side=new`;
  const message =
    diffData.full_content ||
    "This file exceeds the interactive diff limit. Syntax highlighting and side-by-side rendering are collapsed to prevent browser freeze.";

  const box = createEl(ctx, "div", {
    className: "diff-oversized-box",
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "60px 20px",
      textAlign: "center",
    },
    children: [
      createEl(ctx, "div", {
        text: "⚠️",
        style: { fontSize: "32px", marginBottom: "12px" },
      }),
      createEl(ctx, "div", {
        text: "LARGE FILE DIFF COLLAPSED",
        style: {
          fontWeight: "700",
          fontSize: "14px",
          marginBottom: "8px",
          letterSpacing: "0.5px",
        },
      }),
      createEl(ctx, "div", {
        text: message,
        style: { fontSize: "11px", maxWidth: "520px", margin: "0 auto 18px", lineHeight: "1.6" },
      }),
      createEl(ctx, "a", {
        className: "quake-btn quake-btn-gold quake-btn-sm",
        text: "📄 View Raw File",
        attrs: { href: rawUrl, target: "_blank", rel: "noopener noreferrer" },
      }),
    ],
  });
  container.appendChild(box);
}

/**
 * Render side-by-side diff table into `container`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement} container - Target container.
 * @param {object} diffData - Diff payload.
 * @param {string} lang - Language identifier.
 * @param {string[]} oldHighlighted - Pre-highlighted old lines.
 * @param {string[]} newHighlighted - Pre-highlighted new lines.
 * @param {object} options - Render options.
 */
function renderSideBySideDiff(
  ctx,
  container,
  diffData,
  lang,
  oldHighlighted,
  newHighlighted,
  options,
) {
  const rows = Array.isArray(diffData.side_by_side) ? diffData.side_by_side : [];
  const colgroup = createEl(ctx, "colgroup", {
    children: [
      createEl(ctx, "col", { className: "col-lineno", style: { width: "44px", minWidth: "44px" } }),
      createEl(ctx, "col", { className: "col-marker", style: { width: "20px", minWidth: "20px" } }),
      createEl(ctx, "col", { className: "col-code col-old-code", style: { width: "50%" } }),
      createEl(ctx, "col", { className: "col-lineno", style: { width: "44px", minWidth: "44px" } }),
      createEl(ctx, "col", { className: "col-marker", style: { width: "20px", minWidth: "20px" } }),
      createEl(ctx, "col", { className: "col-code col-new-code", style: { width: "50%" } }),
    ],
  });

  const thead = createEl(ctx, "thead", {
    children: [
      createEl(ctx, "tr", {
        children: [
          createEl(ctx, "th", {
            className: "th-old",
            attrs: { colspan: "3" },
            style: { position: "relative" },
            children: [
              createEl(ctx, "span", { text: options.oldHeader || "Previous Revision" }),
              createEl(ctx, "div", {
                className: "sbs-split-resizer",
                attrs: { title: "Drag horizontally to resize split panes" },
              }),
            ],
          }),
          createEl(ctx, "th", {
            className: "th-new",
            attrs: { colspan: "3" },
            text: options.newHeader || "Active Revision",
          }),
        ],
      }),
    ],
  });

  const tbody = createEl(ctx, "tbody");
  for (const row of rows) {
    const rowType = row.row_type || "equal";
    const rowClass = rowType === "equal" ? "row-equal" : `row-${rowType}`;
    const oldNo = row.old_no || null;
    const newNo = row.new_no || null;
    const effectiveLine = newNo || oldNo || 0;
    const effectiveSide = newNo ? "new" : "old";
    const selected =
      isLineSelected(options.selectedRange, newNo, "new") ||
      isLineSelected(options.selectedRange, oldNo, "old");

    let oldHtml = "";
    if (oldNo && oldHighlighted[oldNo - 1] !== undefined) {
      oldHtml = oldHighlighted[oldNo - 1];
    } else if (row.old_text) {
      oldHtml = highlightLine(ctx, row.old_text, lang);
    }

    let newHtml = "";
    if (newNo && newHighlighted[newNo - 1] !== undefined) {
      newHtml = newHighlighted[newNo - 1];
    } else if (row.new_text) {
      newHtml = highlightLine(ctx, row.new_text, lang);
    }

    const oldMarker = rowType === "delete" || rowType === "replace" ? "-" : " ";
    const newMarker = rowType === "insert" || rowType === "replace" ? "+" : " ";

    const oldCodeCell = createEl(ctx, "td", {
      className: "diff-code-cell code-cell old-code hljs",
      dataset: { side: "old", line: oldNo ? String(oldNo) : "" },
    });
    oldCodeCell.innerHTML = oldHtml;

    const newCodeCell = createEl(ctx, "td", {
      className: "diff-code-cell code-cell new-code hljs",
      dataset: { side: "new", line: newNo ? String(newNo) : "" },
    });
    newCodeCell.innerHTML = newHtml;

    const tr = createEl(ctx, "tr", {
      className: `diff-sbs-row sbs-row ${rowClass}${selected ? " selected" : ""}`,
      dataset: {
        line: effectiveLine ? String(effectiveLine) : "",
        oldLine: oldNo ? String(oldNo) : "",
        newLine: newNo ? String(newNo) : "",
        side: effectiveSide,
      },
      children: [
        createEl(ctx, "td", {
          className: "diff-lineno lineno old-lineno",
          dataset: { side: "old", line: oldNo ? String(oldNo) : "" },
          text: oldNo ? String(oldNo) : "",
        }),
        createEl(ctx, "td", {
          className: "diff-marker-cell diff-marker old-marker",
          dataset: { side: "old", line: oldNo ? String(oldNo) : "" },
          text: oldMarker,
        }),
        oldCodeCell,
        createEl(ctx, "td", {
          className: "diff-lineno lineno new-lineno",
          dataset: { side: "new", line: newNo ? String(newNo) : "" },
          text: newNo ? String(newNo) : "",
        }),
        createEl(ctx, "td", {
          className: "diff-marker-cell diff-marker new-marker",
          dataset: { side: "new", line: newNo ? String(newNo) : "" },
          text: newMarker,
        }),
        newCodeCell,
      ],
    });
    tbody.appendChild(tr);

    if (typeof options.renderCommentCard === "function") {
      const rowComments = matchingCommentsForRow(options.comments, oldNo, newNo);
      for (const comment of rowComments) {
        const cardEl = options.renderCommentCard(comment);
        if (cardEl) {
          const commentTr = createEl(ctx, "tr", {
            className: "diff-comment-row",
            children: [
              createEl(ctx, "td", {
                attrs: { colspan: "6" },
                children: [cardEl],
              }),
            ],
          });
          tbody.appendChild(commentTr);
        }
      }
    }
  }

  const table = createEl(ctx, "table", {
    className: "diff-sbs-table sbs-table",
    children: [colgroup, thead, tbody],
  });

  if (typeof options.onLineClick === "function") {
    bindDelegatedEvent(table, "click", ".diff-sbs-row", (event, rowEl) => {
      const target = event.target;
      const cellEl =
        target && typeof target.closest === "function" ? target.closest("td") : null;
      const side = (cellEl && cellEl.dataset && cellEl.dataset.side) || rowEl.dataset.side || "new";
      const lineStr =
        side === "old"
          ? rowEl.dataset.oldLine || rowEl.dataset.line
          : rowEl.dataset.newLine || rowEl.dataset.line;
      const lineNo = Number.parseInt(lineStr || "0", 10);
      if (lineNo > 0) {
        options.onLineClick({
          line: lineNo,
          side,
          shiftKey: Boolean(event.shiftKey),
          rowEl,
          event,
        });
      }
    });
  }

  container.appendChild(table);
  setupSbsResizer(ctx, table, options.storageKey || DEFAULT_SBS_STORAGE_KEY);
}

/**
 * Render unified diff view into `container`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement} container - Target container.
 * @param {object} diffData - Diff payload.
 * @param {string} lang - Language identifier.
 * @param {string[]} oldHighlighted - Pre-highlighted old lines.
 * @param {string[]} newHighlighted - Pre-highlighted new lines.
 * @param {object} options - Render options.
 */
function renderUnifiedDiff(
  ctx,
  container,
  diffData,
  lang,
  oldHighlighted,
  newHighlighted,
  options,
) {
  const hunks = Array.isArray(diffData.hunks) ? diffData.hunks : [];
  const wrap = createEl(ctx, "div", { className: "diff-unified-wrap unified-wrap" });

  for (const hunk of hunks) {
    wrap.appendChild(
      createEl(ctx, "div", {
        className: "diff-unified-hunk-bar unified-hunk-bar",
        text: String(hunk.header || ""),
      }),
    );

    const lines = Array.isArray(hunk.lines) ? hunk.lines : [];
    for (const line of lines) {
      const rawType = line.type || "context";
      let rowType = rawType;
      let markerChar = " ";
      if (rawType === "delete" || rawType === "del") {
        rowType = "del delete";
        markerChar = "-";
      } else if (rawType === "add" || rawType === "insert") {
        rowType = "add insert";
        markerChar = "+";
      }

      const oldNo = line.old_line_no || null;
      const newNo = line.new_line_no || null;
      const effectiveLine = newNo || oldNo || 0;
      const effectiveSide = newNo ? "new" : "old";
      const selected =
        isLineSelected(options.selectedRange, newNo, "new") ||
        isLineSelected(options.selectedRange, oldNo, "old");

      let lineHtml = "";
      if ((rawType === "add" || rawType === "insert") && newNo && newHighlighted[newNo - 1] !== undefined) {
        lineHtml = newHighlighted[newNo - 1];
      } else if ((rawType === "delete" || rawType === "del") && oldNo && oldHighlighted[oldNo - 1] !== undefined) {
        lineHtml = oldHighlighted[oldNo - 1];
      } else if (newNo && newHighlighted[newNo - 1] !== undefined) {
        lineHtml = newHighlighted[newNo - 1];
      } else if (oldNo && oldHighlighted[oldNo - 1] !== undefined) {
        lineHtml = oldHighlighted[oldNo - 1];
      } else {
        lineHtml = highlightLine(ctx, line.content || "", lang);
      }

      const unifiedTextEl = createEl(ctx, "div", {
        className: "diff-unified-text unified-text hljs",
      });
      unifiedTextEl.innerHTML = lineHtml;

      const rowEl = createEl(ctx, "div", {
        className: `diff-unified-row unified-row ${rowType}${selected ? " selected" : ""}`,
        dataset: {
          line: effectiveLine ? String(effectiveLine) : "",
          oldLine: oldNo ? String(oldNo) : "",
          newLine: newNo ? String(newNo) : "",
          side: effectiveSide,
        },
        children: [
          createEl(ctx, "span", {
            className: "diff-unified-num-old unified-num-old",
            text: oldNo ? String(oldNo) : "",
          }),
          createEl(ctx, "span", {
            className: "diff-unified-num-new unified-num-new",
            text: newNo ? String(newNo) : "",
          }),
          createEl(ctx, "span", {
            className: "diff-unified-marker unified-marker",
            text: markerChar,
          }),
          unifiedTextEl,
        ],
      });
      wrap.appendChild(rowEl);

      if (typeof options.renderCommentCard === "function") {
        const rowComments = matchingCommentsForRow(options.comments, oldNo, newNo);
        for (const comment of rowComments) {
          const cardEl = options.renderCommentCard(comment);
          if (cardEl) {
            wrap.appendChild(cardEl);
          }
        }
      }
    }
  }

  if (typeof options.onLineClick === "function") {
    bindDelegatedEvent(wrap, "click", ".diff-unified-row", (event, rowEl) => {
      const side = rowEl.dataset.side || "new";
      const lineStr =
        side === "old"
          ? rowEl.dataset.oldLine || rowEl.dataset.line
          : rowEl.dataset.newLine || rowEl.dataset.line;
      const lineNo = Number.parseInt(lineStr || "0", 10);
      if (lineNo > 0) {
        options.onLineClick({
          line: lineNo,
          side,
          shiftKey: Boolean(event.shiftKey),
          rowEl,
          event,
        });
      }
    });
  }

  container.appendChild(wrap);
}

/**
 * Render full-file view with line numbers, optional selection highlights, and comments.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement} container - Target container.
 * @param {object} diffData - Diff payload (`new_content` or `full_content`).
 * @param {string[]} newHighlighted - Pre-highlighted lines.
 * @param {object} options - Render options.
 */
function renderFullFileDiff(ctx, container, diffData, newHighlighted, options) {
  const sourceText = diffData.new_content || diffData.full_content || "";
  if (!sourceText && newHighlighted.length === 0) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "diff-empty-state",
        children: [createEl(ctx, "span", { text: "Empty or deleted file." })],
      }),
    );
    return;
  }

  const tbody = createEl(ctx, "tbody");
  for (let idx = 0; idx < newHighlighted.length; idx += 1) {
    const lineNo = idx + 1;
    const selected = isLineSelected(options.selectedRange, lineNo, "new");
    const fullCodeCell = createEl(ctx, "td", {
      className: "diff-code-cell code-cell new-code diff-full-text hljs",
      dataset: { side: "new", line: String(lineNo) },
    });
    fullCodeCell.innerHTML = newHighlighted[idx];

    const tr = createEl(ctx, "tr", {
      className: `diff-full-row diff-sbs-row sbs-row row-equal${selected ? " selected" : ""}`,
      dataset: {
        line: String(lineNo),
        newLine: String(lineNo),
        side: "new",
      },
      children: [
        createEl(ctx, "td", {
          className: "diff-lineno lineno new-lineno diff-full-num",
          dataset: { side: "new", line: String(lineNo) },
          text: String(lineNo),
        }),
        fullCodeCell,
      ],
    });
    tbody.appendChild(tr);

    if (typeof options.renderCommentCard === "function") {
      const rowComments = matchingCommentsForRow(options.comments, null, lineNo);
      for (const comment of rowComments) {
        const cardEl = options.renderCommentCard(comment);
        if (cardEl) {
          tbody.appendChild(
            createEl(ctx, "tr", {
              className: "diff-comment-row",
              children: [
                createEl(ctx, "td", {
                  attrs: { colspan: "2" },
                  children: [cardEl],
                }),
              ],
            }),
          );
        }
      }
    }
  }

  const table = createEl(ctx, "table", {
    className: "diff-sbs-table sbs-table diff-full-table",
    children: [
      createEl(ctx, "colgroup", {
        children: [
          createEl(ctx, "col", { className: "col-lineno", style: { width: "52px", minWidth: "52px" } }),
          createEl(ctx, "col", { className: "col-code", style: { width: "100%" } }),
        ],
      }),
      tbody,
    ],
  });

  if (typeof options.onLineClick === "function") {
    bindDelegatedEvent(table, "click", ".diff-full-row", (event, rowEl) => {
      const lineNo = Number.parseInt(rowEl.dataset.line || "0", 10);
      if (lineNo > 0) {
        options.onLineClick({
          line: lineNo,
          side: "new",
          shiftKey: Boolean(event.shiftKey),
          rowEl,
          event,
        });
      }
    });
  }

  container.appendChild(table);
}

/**
 * Render a file diff (`side_by_side`, `unified`, `full_file`, `is_binary`, or `is_oversized`)
 * into `containerOrId` with zero global references and zero inline event attributes.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {HTMLElement|string} containerOrId - Target DOM element or element ID.
 * @param {object|null} diffData - Structured diff payload from server API.
 * @param {object} [options] - Rendering configuration.
 * @param {string} [options.mode] - `"side_by_side"` | `"unified"` | `"full_file"`.
 * @param {string} [options.storageKey] - Split ratio storage key.
 * @param {{start: number, end: number, side?: string}|null} [options.selectedRange] - Highlighted line range.
 * @param {Array<object>} [options.comments] - Inline review comments for this file.
 * @param {Function|null} [options.renderCommentCard] - `(comment) => HTMLElement` renderer.
 * @param {Function|null} [options.onLineClick] - `({line, side, shiftKey, rowEl, event}) => void`.
 * @param {string} [options.rawEndpoint] - Raw file endpoint (`"/api/raw"` default).
 * @param {string} [options.oldHeader] - Optional custom left column header.
 * @param {string} [options.newHeader] - Optional custom right column header.
 */
export function renderDiff(ctx, containerOrId, diffData, options = {}) {
  const container = resolveElement(ctx, containerOrId);
  if (!container) {
    return;
  }
  clearChildren(container);

  if (!diffData) {
    container.appendChild(
      createEl(ctx, "div", {
        className: "diff-empty-state",
        children: [createEl(ctx, "span", { text: "No diff content loaded." })],
      }),
    );
    return;
  }

  const rawEndpoint = options.rawEndpoint || "/api/raw";
  if (diffData.is_binary) {
    renderBinaryDiff(ctx, container, diffData, rawEndpoint);
    return;
  }

  if (diffData.is_oversized) {
    renderOversizedDiff(ctx, container, diffData, rawEndpoint);
    return;
  }

  const mode = options.mode || "side_by_side";
  const lang = detectLanguage(diffData.file_path);
  const oldHighlighted =
    mode === "full_file" ? [] : highlightFullDocument(ctx, diffData.old_content || "", lang);
  const newHighlighted = highlightFullDocument(
    ctx,
    diffData.new_content || diffData.full_content || "",
    lang,
  );

  if (mode === "unified") {
    renderUnifiedDiff(ctx, container, diffData, lang, oldHighlighted, newHighlighted, options);
    return;
  }
  if (mode === "full_file") {
    renderFullFileDiff(ctx, container, diffData, newHighlighted, options);
    return;
  }
  renderSideBySideDiff(ctx, container, diffData, lang, oldHighlighted, newHighlighted, options);
}
