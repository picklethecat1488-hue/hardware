/**
 * ANSI SGR Color & OSC-8 Clickable Hyperlink Parser.
 *
 * Shared across Forge CLI drawers (`code_review`, `diff_view`) and Firmware
 * Host Daemon (`rtt_stream`, `cli_console`) for rendering terminal output and
 * interactive `[P]ass` / `[F]ail` / `file://` OSC-8 links safely without XSS.
 */

import { escapeHtml } from "./sanitize.js";

const ANSI_FG_COLORS = {
  30: "#4a4a4a",
  31: "#ff5555",
  32: "#50fa7b",
  33: "#f1fa8c",
  34: "#6272a4",
  35: "#ff79c6",
  36: "#8be9fd",
  37: "#f8f8f2",
  90: "#7f848e",
  91: "#ff6e6e",
  92: "#69ff94",
  93: "#ffffa5",
  94: "#d6acff",
  95: "#ff92df",
  96: "#a4ffff",
  97: "#ffffff",
};

const ANSI_BG_COLORS = {
  40: "#1e1e1e",
  41: "#661b1b",
  42: "#164a26",
  43: "#5c4d12",
  44: "#1c2d5a",
  45: "#5a1c48",
  46: "#144954",
  47: "#555555",
};

// Matches OSC-8 hyperlinks: ESC ] 8 ; params ; uri (BEL | ESC \) label ESC ] 8 ; ; (BEL | ESC \)
// eslint-disable-next-line no-control-regex
const OSC8_REGEX = /\x1b\]8;[^;]*;([^\x07\x1b]*)(?:\x07|\x1b\\)([\s\S]*?)\x1b\]8;;(?:\x07|\x1b\\)/g;
// Matches CSI SGR sequences: ESC [ <codes> m
// eslint-disable-next-line no-control-regex
const CSI_SGR_REGEX = /\x1b\[([0-9;]*)m/g;
// Matches all ANSI CSI/OSC sequences for plain-text stripping
// eslint-disable-next-line no-control-regex
const ALL_ANSI_REGEX = /\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-9;?]*[A-Za-z])/g;

/**
 * Strip all ANSI CSI escape codes and OSC-8 hyperlink wrappers from `text`.
 *
 * @param {string} text - Raw terminal output.
 * @returns {string} Plain text.
 */
export function stripAnsi(text) {
  if (!text) {
    return "";
  }
  return String(text)
    .replace(OSC8_REGEX, "$2")
    .replace(ALL_ANSI_REGEX, "");
}

/**
 * Render an SGR-colored text chunk (with HTML already escaped at segment level) into HTML spans.
 *
 * @param {string} rawSegment - Plain text containing optional `\x1b[...m` SGR codes.
 * @param {object} state - Mutable style state `{ fg, bg, bold, dim, underline }`.
 * @returns {string} Safe HTML fragment.
 */
function renderSgrSegment(rawSegment, state) {
  let html = "";
  let lastIdx = 0;

  const flushStyledText = (plainChunk) => {
    if (!plainChunk) {
      return;
    }
    const escaped = escapeHtml(plainChunk);
    const styles = [];
    if (state.fg) styles.push(`color:${state.fg}`);
    if (state.bg) styles.push(`background-color:${state.bg}`);
    if (state.bold) styles.push("font-weight:700");
    if (state.dim) styles.push("opacity:0.7");
    if (state.underline) styles.push("text-decoration:underline");
    if (styles.length === 0) {
      html += escaped;
    } else {
      html += `<span style="${styles.join(";")}">${escaped}</span>`;
    }
  };

  CSI_SGR_REGEX.lastIndex = 0;
  let match = CSI_SGR_REGEX.exec(rawSegment);
  while (match !== null) {
    flushStyledText(rawSegment.slice(lastIdx, match.index));
    lastIdx = match.index + match[0].length;

    const codes = match[1] === "" ? [0] : match[1].split(";").map((c) => Number(c || 0));
    for (let idx = 0; idx < codes.length; idx += 1) {
      const code = codes[idx];
      if (code === 0) {
        state.fg = null;
        state.bg = null;
        state.bold = false;
        state.dim = false;
        state.underline = false;
      } else if (code === 1) {
        state.bold = true;
      } else if (code === 2) {
        state.dim = true;
      } else if (code === 4) {
        state.underline = true;
      } else if (code === 22) {
        state.bold = false;
        state.dim = false;
      } else if (code === 24) {
        state.underline = false;
      } else if (code === 39) {
        state.fg = null;
      } else if (code === 49) {
        state.bg = null;
      } else if (ANSI_FG_COLORS[code]) {
        state.fg = ANSI_FG_COLORS[code];
      } else if (ANSI_BG_COLORS[code]) {
        state.bg = ANSI_BG_COLORS[code];
      } else if (code === 38 && codes[idx + 1] === 5 && codes[idx + 2] !== undefined) {
        state.fg = xterm256ToHex(codes[idx + 2]);
        idx += 2;
      }
    }
    match = CSI_SGR_REGEX.exec(rawSegment);
  }

  flushStyledText(rawSegment.slice(lastIdx));
  return html;
}

/**
 * Convert an xterm 256-color palette index `[0..255]` to CSS `#rrggbb`.
 *
 * @param {number} colorIdx - Palette index.
 * @returns {string}
 */
function xterm256ToHex(colorIdx) {
  const idx = Math.max(0, Math.min(255, Number(colorIdx) || 0));
  if (idx < 16) {
    const base = [
      "#000000", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc", "#11a8cd", "#e5e5e5",
      "#666666", "#f14c4c", "#23d18b", "#f5f543", "#3b8eea", "#d670d6", "#29b8db", "#ffffff",
    ];
    return base[idx];
  }
  if (idx >= 232) {
    const gray = 8 + (idx - 232) * 10;
    const hex = gray.toString(16).padStart(2, "0");
    return `#${hex}${hex}${hex}`;
  }
  const cube = idx - 16;
  const levels = [0, 95, 135, 175, 215, 255];
  const r = levels[Math.floor(cube / 36) % 6].toString(16).padStart(2, "0");
  const g = levels[Math.floor(cube / 6) % 6].toString(16).padStart(2, "0");
  const b = levels[cube % 6].toString(16).padStart(2, "0");
  return `#${r}${g}${b}`;
}

/**
 * Convert raw terminal text containing ANSI SGR colors and OSC-8 hyperlinks into safe HTML.
 *
 * OSC-8 URIs using `cmd://<command>` or `bringup://<choice>` emit `<button class="osc8-action-link" data-osc-uri="...">`
 * for zero-globals delegated click handling; `http(s)://` and `file://` URIs emit safe `<a>` elements.
 *
 * @param {string} rawText - Raw ANSI/OSC-8 terminal text.
 * @returns {string} Safe HTML string.
 */
export function parseAnsiToHtml(rawText) {
  if (!rawText) {
    return "";
  }
  const input = String(rawText);
  const styleState = { fg: null, bg: null, bold: false, dim: false, underline: false };

  let output = "";
  let cursor = 0;
  OSC8_REGEX.lastIndex = 0;
  let match = OSC8_REGEX.exec(input);

  while (match !== null) {
    output += renderSgrSegment(input.slice(cursor, match.index), styleState);
    cursor = match.index + match[0].length;

    const rawUri = match[1].trim();
    const labelHtml = renderSgrSegment(match[2], styleState);
    const safeUri = escapeHtml(rawUri);

    if (
      rawUri.startsWith("cmd:") ||
      rawUri.startsWith("prompt:") ||
      rawUri.startsWith("bringup:") ||
      rawUri.startsWith("rtt:")
    ) {
      output += `<button type="button" class="osc8-link osc8-cmd-btn" data-osc-uri="${safeUri}">${labelHtml}</button>`;
    } else if (
      rawUri.startsWith("http://") ||
      rawUri.startsWith("https://") ||
      rawUri.startsWith("file://")
    ) {
      output += `<a class="osc8-link" href="${safeUri}" data-osc-uri="${safeUri}" target="_blank" rel="noopener noreferrer">${labelHtml}</a>`;
    } else {
      output += `<button type="button" class="osc8-link osc8-cmd-btn" data-osc-uri="${safeUri}">${labelHtml}</button>`;
    }

    match = OSC8_REGEX.exec(input);
  }

  output += renderSgrSegment(input.slice(cursor), styleState);
  return output;
}
