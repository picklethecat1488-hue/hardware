/**
 * Safe Zero-Globals Markdown Preview Renderer for Tracker Descriptions & Notes.
 *
 * Escapes raw HTML entities prior to formatting and rejects unsafe link schemes
 * (`javascript:`, `data:`, `vbscript:`). Supports headings, fenced code blocks
 * with optional syntax highlighting, lists, blockquotes, inline code, bold/italic,
 * and safe links.
 */

import { escapeHtml } from "../core/sanitize.js";
import { highlightFullDocument } from "../diff/diff_engine.js";

const SAFE_URL_PREFIX_RE = /^(https?:\/\/|\/|#)/i;

/**
 * Format inline markdown tokens on an already HTML-escaped line.
 *
 * @param {string} rawLine - Unescaped single line of markdown.
 * @returns {string} Safe HTML string.
 */
function formatInlineMarkdown(rawLine) {
  const codeSpans = [];
  const withPlaceholders = String(rawLine || "").replace(/`([^`]+)`/g, (_match, code) => {
    const idx = codeSpans.length;
    codeSpans.push(`<code class="md-inline-code">${escapeHtml(code)}</code>`);
    return `\u0000CODE${idx}\u0000`;
  });

  let escaped = escapeHtml(withPlaceholders);

  // Safe links: [label](url)
  escaped = escaped.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_match, label, hrefCandidate) => {
      const unescapedHref = hrefCandidate.replace(/&amp;/g, "&");
      if (!SAFE_URL_PREFIX_RE.test(unescapedHref)) {
        return `${label} (${hrefCandidate})`;
      }
      return `<a href="${escapeHtml(unescapedHref)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    },
  );

  // Bold **text** and Italic *text*
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");

  // Restore inline code spans
  return escaped.replace(/\u0000CODE(\d+)\u0000/g, (_m, idxStr) => {
    return codeSpans[Number.parseInt(idxStr, 10)] || "";
  });
}

/**
 * Render Markdown text into safe HTML using the provided `RuntimeContext`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} markdownText - Raw markdown source string.
 * @returns {string} Sanitized HTML representation.
 */
export function renderMarkdownPreview(ctx, markdownText) {
  const text = String(markdownText || "").replace(/\r\n/g, "\n");
  if (!text.trim()) {
    return '<span class="md-empty" style="color:var(--quake-text-dim);font-style:italic;">Nothing to preview.</span>';
  }

  const lines = text.split("\n");
  const blocks = [];
  let idx = 0;

  while (idx < lines.length) {
    const line = lines[idx];

    // Fenced code block ```lang
    const fenceMatch = line.match(/^```([\w+-]*)\s*$/);
    if (fenceMatch) {
      const lang = fenceMatch[1] || "";
      const codeLines = [];
      idx += 1;
      while (idx < lines.length && !/^```\s*$/.test(lines[idx])) {
        codeLines.push(lines[idx]);
        idx += 1;
      }
      if (idx < lines.length) {
        idx += 1; // consume closing ```
      }
      const rawCode = codeLines.join("\n");
      let highlightedHtml = "";
      if (lang && ctx && typeof ctx.getSyntaxHighlighter === "function") {
        const hlLines = highlightFullDocument(ctx, rawCode, lang);
        highlightedHtml = Array.isArray(hlLines) ? hlLines.join("\n") : escapeHtml(rawCode);
      } else {
        highlightedHtml = escapeHtml(rawCode);
      }
      const langAttr = lang ? ` class="language-${escapeHtml(lang)}"` : "";
      blocks.push(`<pre class="md-code-block"><code${langAttr}>${highlightedHtml}</code></pre>`);
      continue;
    }

    // Blank line
    if (!line.trim()) {
      idx += 1;
      continue;
    }

    // Heading # .. ####
    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${formatInlineMarkdown(headingMatch[2].trim())}</h${level}>`);
      idx += 1;
      continue;
    }

    // Blockquote > ...
    if (/^>\s?/.test(line)) {
      const quoteLines = [];
      while (idx < lines.length && /^>\s?/.test(lines[idx])) {
        quoteLines.push(formatInlineMarkdown(lines[idx].replace(/^>\s?/, "")));
        idx += 1;
      }
      blocks.push(`<blockquote>${quoteLines.join("<br>")}</blockquote>`);
      continue;
    }

    // Unordered list - / *
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (idx < lines.length && /^\s*[-*]\s+/.test(lines[idx])) {
        items.push(`<li>${formatInlineMarkdown(lines[idx].replace(/^\s*[-*]\s+/, ""))}</li>`);
        idx += 1;
      }
      blocks.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    // Ordered list 1.
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (idx < lines.length && /^\s*\d+\.\s+/.test(lines[idx])) {
        items.push(`<li>${formatInlineMarkdown(lines[idx].replace(/^\s*\d+\.\s+/, ""))}</li>`);
        idx += 1;
      }
      blocks.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    // Standard paragraph
    const paraLines = [];
    while (
      idx < lines.length &&
      lines[idx].trim() &&
      !lines[idx].startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[idx]) &&
      !/^>\s?/.test(lines[idx]) &&
      !/^\s*[-*]\s+/.test(lines[idx]) &&
      !/^\s*\d+\.\s+/.test(lines[idx])
    ) {
      paraLines.push(formatInlineMarkdown(lines[idx]));
      idx += 1;
    }
    blocks.push(`<p>${paraLines.join("<br>")}</p>`);
  }

  return blocks.join("\n");
}

/**
 * Toggle between raw `<textarea>` editing and rendered Markdown preview for a field.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element} toggleBtn - Button element carrying `data-target-textarea` and `data-target-preview`.
 */
export function toggleMarkdownPreviewForButton(ctx, toggleBtn) {
  const doc = ctx.getDocument();
  if (!doc || !toggleBtn) {
    return;
  }
  const textareaId = toggleBtn.dataset?.targetTextarea || "";
  const previewId = toggleBtn.dataset?.targetPreview || "";
  const textarea = textareaId ? doc.getElementById(textareaId) : null;
  const previewEl = previewId ? doc.getElementById(previewId) : null;
  if (!textarea || !previewEl) {
    return;
  }

  const showingPreview = previewEl.style.display !== "none";
  if (showingPreview) {
    previewEl.style.display = "none";
    textarea.style.display = "";
    toggleBtn.textContent = "👁 Preview";
    toggleBtn.classList.remove("quake-btn-gold");
    toggleBtn.classList.add("quake-btn-default");
  } else {
    previewEl.innerHTML = renderMarkdownPreview(ctx, textarea.value || "");
    textarea.style.display = "none";
    previewEl.style.display = "block";
    toggleBtn.textContent = "✎ Edit";
    toggleBtn.classList.add("quake-btn-gold");
    toggleBtn.classList.remove("quake-btn-default");
  }
}
