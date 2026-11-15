/**
 * Quake / Xerxes Code Review CLI Console Drawer, `@file` Autocomplete, & `Ctrl+R` History (`cli_drawer.js`).
 *
 * Shared 100% byte-identically across `hardware` and `firmware` Code Review workstations.
 */

import { parseAnsiToHtml } from "../core/ansi.js";
import { clearChildren, createEl, resolveElement } from "../core/dom.js";
import { fuzzyFilterAndRank } from "../core/fuzzy_search.js";

const MAX_AUTOCOMPLETE_SUGGESTIONS = 8;
const AT_MENTION_CURSOR_REGEX = /@([a-zA-Z0-9_./\\-]*)$/;

/**
 * Append a formatted line (supporting ANSI SGR colors and OSC-8 links) to `#cliLog`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} message - Message string (plain or ANSI-encoded).
 * @param {string} [colorClass] - Optional theme color suffix (`"gold"`, `"cyan"`, `"green"`, `"red"`, `"amber"`, `"dim"`).
 */
export function logCli(ctx, message, colorClass = "") {
  const screen = resolveElement(ctx, "cliLog");
  if (!screen) {
    return;
  }
  const classNames = ["cli-log-line"];
  if (colorClass) {
    classNames.push(`cli-log-${colorClass}`);
  }
  const line = createEl(ctx, "div", {
    className: classNames.join(" "),
  });
  line.innerHTML = parseAnsiToHtml(String(message ?? ""));
  screen.appendChild(line);
  screen.scrollTop = screen.scrollHeight;
}

/**
 * Update `#cliTargetPill`, `#cliPromptPrefix`, and `#selectionLabel` to reflect
 * the currently selected file and diff line range.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Review application state.
 * @param {boolean} [logSelection] - Log target priming to `#cliLog` when range > 0.
 */
export function updateTargetUI(ctx, state, logSelection = false) {
  const targetPill = resolveElement(ctx, "cliTargetPill");
  const promptPrefix = resolveElement(ctx, "cliPromptPrefix");
  const selLabel = resolveElement(ctx, "selectionLabel");

  if (!state.selectedFile) {
    if (targetPill) targetPill.textContent = "TARGET: NO FILE SELECTED";
    if (promptPrefix) promptPrefix.textContent = "[NO FILE] >";
    if (selLabel) selLabel.style.display = "none";
    return;
  }

  const rawStart = (state.selectedRange && state.selectedRange.start) || 0;
  const rawEnd = (state.selectedRange && state.selectedRange.end) || rawStart;
  const startLine = Math.min(rawStart, rawEnd);
  const endLine = Math.max(rawStart, rawEnd);

  if (startLine > 0) {
    const rangeText = startLine === endLine ? `L${startLine}` : `L${startLine}-L${endLine}`;
    const targetStr = `${state.selectedFile}:${rangeText}`;
    if (targetPill) targetPill.textContent = `TARGET: ${targetStr}`;
    if (promptPrefix) promptPrefix.textContent = `[${rangeText}] >`;
    if (selLabel) {
      selLabel.textContent = `Selected: ${rangeText}`;
      selLabel.style.display = "inline-block";
    }
    if (logSelection) {
      logCli(ctx, `Target primed: ${targetStr}`, "dim");
    }
  } else {
    if (targetPill) targetPill.textContent = `TARGET: ${state.selectedFile} (FILE LEVEL)`;
    if (promptPrefix) promptPrefix.textContent = "[FILE] >";
    if (selLabel) selLabel.style.display = "none";
  }
}

/**
 * Deduplicate command history in reverse chronological order and rank via `fuzzyFilterAndRank`.
 *
 * @param {Array<string>} cmdHistory - Chronological command history list.
 * @param {string} query - Reverse-search query string.
 * @returns {Array<string>} Matching commands in reverse-i-search priority order.
 */
export function getReverseHistoryMatches(cmdHistory, query) {
  const reversedUnique = [];
  const seen = new Set();
  const list = Array.isArray(cmdHistory) ? cmdHistory : [];
  for (let idx = list.length - 1; idx >= 0; idx -= 1) {
    const entry = list[idx];
    if (entry && !seen.has(entry)) {
      seen.add(entry);
      reversedUnique.push(entry);
    }
  }
  return fuzzyFilterAndRank(query, reversedUnique).map((hit) => hit.item);
}

/**
 * Parse and dispatch a single Quake/Xerxes CLI review command against `handlers`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} rawCmd - Trimmed command line input.
 * @param {object} state - Mutable review state (`selectedFile`, `selectedRange`, `currentSeverity`).
 * @param {object} handlers - Action callbacks (`goto`, `postComment`, `editComment`, `setFileStatus`, `navigateChange`, `navigateCommit`, `navigateFile`, `onRangeChanged`, `exportMarkdown`, `setVerdict`, `clearConsole`).
 */
export async function executeParsedCliCommand(ctx, rawCmd, state, handlers) {
  if (!rawCmd) {
    return;
  }

  if (rawCmd.startsWith("@")) {
    logCli(ctx, `> ${rawCmd}`, "gold");
    await handlers.goto(rawCmd);
    return;
  }

  const parts = rawCmd.split(/\s+/);
  const rawVerb = parts[0].toLowerCase();
  const verb = rawVerb.startsWith("/") ? rawVerb.slice(1) : rawVerb;

  logCli(ctx, `> ${rawCmd}`, "gold");

  switch (verb) {
    case "help":
      logCli(ctx, "--- GLQUAKE REVIEW CLI COMMANDS ---", "cyan");
      logCli(ctx, "  goto / g <file> [line]       : Navigate to file or line in active file", "cyan");
      logCli(ctx, "  next change / nc             : Jump to next change/hunk in diff", "cyan");
      logCli(ctx, "  prev change / pc             : Jump to previous change/hunk in diff", "cyan");
      logCli(ctx, "  next commit / prev commit    : Navigate to next or previous commit in the stack", "cyan");
      logCli(ctx, "  next / n, prev / p           : Jump to next or previous file", "cyan");
      logCli(ctx, "  must_fix / fix / mf <text>   : Post comment as MUST FIX", "cyan");
      logCli(ctx, "  proposal / prop <text>       : Post comment as PROPOSAL", "cyan");
      logCli(ctx, "  nit <text>                   : Post comment as NIT", "cyan");
      logCli(ctx, "  comment / c <text>           : Post comment on currently selected lines", "cyan");
      logCli(ctx, "  reviewed / done / todo       : Toggle reviewed status on current file", "cyan");
      logCli(ctx, "  sel / line <start> [end]     : Select line range in active file", "cyan");
      logCli(ctx, "  edit <id> <text>             : Edit existing comment body", "cyan");
      logCli(ctx, "  approve / lgtm               : Conclude review with APPROVAL and export CR.md", "cyan");
      logCli(ctx, "  reject / changes             : Conclude review with CHANGES REQUESTED and export CR.md", "cyan");
      logCli(ctx, "  clear                        : Clear CLI screen log or selection", "cyan");
      break;

    case "goto":
    case "g": {
      const target = parts[1];
      const lineParam = parts[2] ? Number.parseInt(parts[2], 10) : null;
      if (!target) {
        logCli(
          ctx,
          "Usage: goto <file> [line] or goto <line> (e.g. 'goto pcb.py:42', 'goto 80')",
          "red",
        );
      } else {
        await handlers.goto(target, Number.isFinite(lineParam) ? lineParam : null);
      }
      break;
    }

    case "must_fix":
    case "mustfix":
    case "fix":
    case "mf": {
      const body = rawCmd.slice(parts[0].length).trim();
      if (!body) {
        logCli(ctx, `Error: Please supply comment text after ${verb.toUpperCase()}`, "red");
        return;
      }
      await handlers.postComment(body, "MUST_FIX");
      break;
    }

    case "proposal":
    case "prop": {
      const body = rawCmd.slice(parts[0].length).trim();
      if (!body) {
        logCli(ctx, `Error: Please supply comment text after ${verb.toUpperCase()}`, "red");
        return;
      }
      await handlers.postComment(body, "PROPOSAL");
      break;
    }

    case "nit": {
      const body = rawCmd.slice(parts[0].length).trim();
      if (!body) {
        logCli(ctx, `Error: Please supply comment text after ${verb.toUpperCase()}`, "red");
        return;
      }
      await handlers.postComment(body, "NIT");
      break;
    }

    case "comment":
    case "c": {
      const body = rawCmd.slice(parts[0].length).trim();
      if (!body) {
        logCli(ctx, "Error: Please supply comment text after 'comment'", "red");
        return;
      }
      await handlers.postComment(body, "PROPOSAL");
      break;
    }

    case "edit": {
      const commentId = parts[1];
      const newBody = parts.slice(2).join(" ").trim();
      if (!commentId || !newBody) {
        logCli(ctx, "Usage: edit <comment_id> <new_text>", "red");
        return;
      }
      await handlers.editComment(commentId, newBody);
      break;
    }

    case "reviewed":
    case "done":
      if (state.selectedFile) {
        await handlers.setFileStatus(state.selectedFile, "REVIEWED");
      }
      break;

    case "todo":
    case "unreview":
      if (state.selectedFile) {
        await handlers.setFileStatus(state.selectedFile, "PENDING");
      }
      break;

    case "next":
    case "n": {
      const sub = parts[1] ? parts[1].toLowerCase() : "";
      if (sub === "change" || sub === "hunk" || sub === "c" || sub === "diff") {
        await handlers.navigateChange(1);
      } else if (sub === "commit" || sub === "rev" || sub === "revision") {
        await handlers.navigateCommit(1);
      } else {
        await handlers.navigateFile(1);
      }
      break;
    }

    case "prev":
    case "p": {
      const sub = parts[1] ? parts[1].toLowerCase() : "";
      if (sub === "change" || sub === "hunk" || sub === "c" || sub === "diff") {
        await handlers.navigateChange(-1);
      } else if (sub === "commit" || sub === "rev" || sub === "revision") {
        await handlers.navigateCommit(-1);
      } else {
        await handlers.navigateFile(-1);
      }
      break;
    }

    case "next_commit":
    case "next-commit":
    case "nextcommit":
    case "nc_commit":
      await handlers.navigateCommit(1);
      break;

    case "prev_commit":
    case "prev-commit":
    case "prevcommit":
    case "pc_commit":
      await handlers.navigateCommit(-1);
      break;

    case "next_change":
    case "next-change":
    case "nextchange":
    case "nc":
    case "next_hunk":
    case "nexthunk":
      await handlers.navigateChange(1);
      break;

    case "prev_change":
    case "prev-change":
    case "prevchange":
    case "pc":
    case "prev_hunk":
    case "prevhunk":
      await handlers.navigateChange(-1);
      break;

    case "sel":
    case "line": {
      const startLine = Number.parseInt(parts[1], 10);
      const endLine = parts[2] ? Number.parseInt(parts[2], 10) : startLine;
      if (!Number.isFinite(startLine) || startLine <= 0) {
        logCli(ctx, "Usage: sel <start_line> [end_line]", "red");
      } else {
        state.selectedRange = {
          start: startLine,
          end: Number.isFinite(endLine) && endLine > 0 ? endLine : startLine,
        };
        updateTargetUI(ctx, state, false);
        if (typeof handlers.onRangeChanged === "function") {
          handlers.onRangeChanged();
        }
      }
      break;
    }

    case "feedback":
    case "export":
    case "save":
      await handlers.exportMarkdown();
      break;

    case "approve":
    case "lgtm":
      await handlers.setVerdict("APPROVED");
      break;

    case "review":
    case "in_review":
    case "in-review":
      logCli(
        ctx,
        "Note: Review session is currently active. Conclude the review with 'approve' or 'reject'.",
        "amber",
      );
      break;

    case "changes":
    case "reject":
    case "request_changes":
    case "request-changes":
      await handlers.setVerdict("CHANGES_REQUESTED");
      break;

    case "clear": {
      const logScreen = resolveElement(ctx, "cliLog");
      if (logScreen) {
        clearChildren(logScreen);
      }
      state.selectedRange = { start: null, end: null };
      updateTargetUI(ctx, state, false);
      if (typeof handlers.onRangeChanged === "function") {
        handlers.onRangeChanged();
      }
      break;
    }

    default:
      if (state.selectedFile && state.selectedRange && state.selectedRange.start) {
        await handlers.postComment(rawCmd, state.currentSeverity || "MUST_FIX");
      } else {
        logCli(
          ctx,
          `Unrecognized command '${verb}'. Type 'help' for available commands.`,
          "red",
        );
      }
      break;
  }
}

/**
 * Wire up `#cliInput`, `#cliSuggestions` (`@file` autocomplete), `#cliFuzzyHistory` (`Ctrl+R`),
 * and CLI quick-action buttons.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Mutable review application state.
 * @param {object} handlers - Command execution handlers passed to `executeParsedCliCommand`.
 * @returns {{ openFuzzyHistory: Function, closeFuzzyHistory: Function, executeCliInput: Function }}
 */
export function setupCliDrawer(ctx, state, handlers) {
  const input = resolveElement(ctx, "cliInput");
  const suggestionsEl = resolveElement(ctx, "cliSuggestions");
  const fuzzyContainer = resolveElement(ctx, "cliFuzzyHistory");
  const fuzzySearchInput = resolveElement(ctx, "fuzzySearchInput");
  const fuzzyResultsList = resolveElement(ctx, "fuzzyResultsList");

  let activeSuggestionIdx = -1;
  let fuzzySelectedIndex = 0;
  let currentFuzzyMatches = [];

  const closeFuzzyHistory = () => {
    if (fuzzyContainer) {
      fuzzyContainer.style.display = "none";
    }
    if (input) {
      input.focus();
    }
  };

  const selectFuzzyCommand = (cmd) => {
    if (input) {
      input.value = cmd;
    }
    closeFuzzyHistory();
  };

  const renderFuzzyResults = (query) => {
    if (!fuzzyResultsList) {
      return;
    }
    currentFuzzyMatches = getReverseHistoryMatches(state.cmdHistory, query);
    if (fuzzySelectedIndex >= currentFuzzyMatches.length) {
      fuzzySelectedIndex = Math.max(0, currentFuzzyMatches.length - 1);
    }
    clearChildren(fuzzyResultsList);

    if (currentFuzzyMatches.length === 0) {
      fuzzyResultsList.appendChild(
        createEl(ctx, "div", {
          className: "fuzzy-item",
          style: { color: "var(--quake-text-dim)" },
          text: "No matching commands",
        }),
      );
      return;
    }

    currentFuzzyMatches.forEach((cmd, idx) => {
      const itemEl = createEl(ctx, "div", {
        className: `fuzzy-item${idx === fuzzySelectedIndex ? " active" : ""}`,
        text: cmd,
      });
      itemEl.addEventListener("click", () => {
        selectFuzzyCommand(cmd);
      });
      fuzzyResultsList.appendChild(itemEl);
      if (idx === fuzzySelectedIndex && typeof itemEl.scrollIntoView === "function") {
        itemEl.scrollIntoView({ block: "nearest" });
      }
    });
  };

  const openFuzzyHistory = () => {
    if (!fuzzyContainer || !fuzzySearchInput) {
      return;
    }
    fuzzyContainer.style.display = "flex";
    fuzzySearchInput.value = "";
    fuzzySelectedIndex = 0;
    renderFuzzyResults("");
    fuzzySearchInput.focus();
  };

  const executeCliInput = async () => {
    if (!input || input.disabled) {
      return;
    }
    if (suggestionsEl) {
      suggestionsEl.style.display = "none";
      activeSuggestionIdx = -1;
    }

    let rawCmd = String(input.value || "").trim();
    if (!rawCmd) {
      if (Array.isArray(state.cmdHistory) && state.cmdHistory.length > 0) {
        rawCmd = state.cmdHistory[state.cmdHistory.length - 1];
      } else {
        return;
      }
    } else {
      state.cmdHistory.push(rawCmd);
      state.cmdHistoryIdx = state.cmdHistory.length;
    }
    input.value = "";

    const sendBtn = resolveElement(ctx, "btnCliSend");
    const prevPlaceholder = input.placeholder || "";
    input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    input.placeholder = `Running command: ${rawCmd}...`;

    try {
      await executeParsedCliCommand(ctx, rawCmd, state, handlers);
    } finally {
      input.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      input.placeholder = prevPlaceholder;
      input.focus();
    }
  };

  if (input) {
    input.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && (event.key === "r" || event.key === "R")) {
        event.preventDefault();
        openFuzzyHistory();
        return;
      }

      if (suggestionsEl && suggestionsEl.style.display === "block") {
        const items = suggestionsEl.querySelectorAll(".cli-suggestion-item");
        if (event.key === "ArrowDown" && items.length > 0) {
          event.preventDefault();
          activeSuggestionIdx = (activeSuggestionIdx + 1) % items.length;
          items.forEach((el, idx) => el.classList.toggle("active", idx === activeSuggestionIdx));
          return;
        }
        if (event.key === "ArrowUp" && items.length > 0) {
          event.preventDefault();
          activeSuggestionIdx = (activeSuggestionIdx - 1 + items.length) % items.length;
          items.forEach((el, idx) => el.classList.toggle("active", idx === activeSuggestionIdx));
          return;
        }
        if (
          (event.key === "Tab" || event.key === "Enter") &&
          activeSuggestionIdx >= 0 &&
          items[activeSuggestionIdx]
        ) {
          event.preventDefault();
          items[activeSuggestionIdx].click();
          return;
        }
        if (event.key === "Escape") {
          event.preventDefault();
          suggestionsEl.style.display = "none";
          activeSuggestionIdx = -1;
          return;
        }
      }

      if (event.key === "Enter") {
        event.preventDefault();
        executeCliInput();
      } else if (event.key === "ArrowUp") {
        if (state.cmdHistoryIdx > 0) {
          state.cmdHistoryIdx -= 1;
          input.value = state.cmdHistory[state.cmdHistoryIdx] || "";
        }
      } else if (event.key === "ArrowDown") {
        if (state.cmdHistoryIdx < state.cmdHistory.length - 1) {
          state.cmdHistoryIdx += 1;
          input.value = state.cmdHistory[state.cmdHistoryIdx] || "";
        } else {
          state.cmdHistoryIdx = state.cmdHistory.length;
          input.value = "";
        }
      }
    });

    if (suggestionsEl) {
      const insertSuggestion = (textToInsert, atIndex, matchLen) => {
        const val = String(input.value || "");
        const before = val.slice(0, atIndex);
        const after = val.slice(atIndex + matchLen);
        input.value = `${before}${textToInsert}${after}`;
        suggestionsEl.style.display = "none";
        activeSuggestionIdx = -1;
        input.focus();
        if (typeof input.setSelectionRange === "function") {
          const cursorPos = before.length + textToInsert.length;
          input.setSelectionRange(cursorPos, cursorPos);
        }
      };

      input.addEventListener("input", () => {
        const val = String(input.value || "");
        const cursor = typeof input.selectionStart === "number" ? input.selectionStart : val.length;
        const beforeCursor = val.slice(0, cursor);
        const match = beforeCursor.match(AT_MENTION_CURSOR_REGEX);
        if (!match) {
          suggestionsEl.style.display = "none";
          activeSuggestionIdx = -1;
          return;
        }

        const query = match[1].toLowerCase();
        const matches = (state.files || [])
          .filter((fileObj) => String(fileObj.path || "").toLowerCase().includes(query))
          .slice(0, MAX_AUTOCOMPLETE_SUGGESTIONS);

        if (matches.length === 0) {
          suggestionsEl.style.display = "none";
          activeSuggestionIdx = -1;
          return;
        }

        activeSuggestionIdx = 0;
        clearChildren(suggestionsEl);
        matches.forEach((fileObj, idx) => {
          const itemEl = createEl(ctx, "div", {
            className: `cli-suggestion-item${idx === 0 ? " active" : ""}`,
            children: [
              createEl(ctx, "span", {
                className: "cli-suggestion-path",
                text: `@${fileObj.path}`,
              }),
              createEl(ctx, "span", {
                className: "cli-suggestion-meta",
                text: `+${fileObj.additions || 0}/-${fileObj.deletions || 0}`,
              }),
            ],
          });
          itemEl.addEventListener("click", (ev) => {
            ev.stopPropagation();
            insertSuggestion(`@${fileObj.path} `, match.index, match[0].length);
          });
          suggestionsEl.appendChild(itemEl);
        });
        suggestionsEl.style.display = "block";
      });

      ctx.getDocument()?.addEventListener("click", (ev) => {
        if (ev.target !== input && (!suggestionsEl.contains || !suggestionsEl.contains(ev.target))) {
          suggestionsEl.style.display = "none";
          activeSuggestionIdx = -1;
        }
      });
    }
  }

  if (fuzzySearchInput) {
    fuzzySearchInput.addEventListener("input", (event) => {
      fuzzySelectedIndex = 0;
      renderFuzzyResults(event.target ? event.target.value : "");
    });
    fuzzySearchInput.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && (event.key === "r" || event.key === "R")) {
        event.preventDefault();
        if (currentFuzzyMatches.length > 0) {
          fuzzySelectedIndex = (fuzzySelectedIndex + 1) % currentFuzzyMatches.length;
          renderFuzzyResults(fuzzySearchInput.value);
        }
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeFuzzyHistory();
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (currentFuzzyMatches.length > 0 && currentFuzzyMatches[fuzzySelectedIndex]) {
          selectFuzzyCommand(currentFuzzyMatches[fuzzySelectedIndex]);
        } else {
          closeFuzzyHistory();
        }
      } else if (event.key === "ArrowUp" && currentFuzzyMatches.length > 0) {
        event.preventDefault();
        fuzzySelectedIndex =
          (fuzzySelectedIndex - 1 + currentFuzzyMatches.length) % currentFuzzyMatches.length;
        renderFuzzyResults(fuzzySearchInput.value);
      } else if (event.key === "ArrowDown" && currentFuzzyMatches.length > 0) {
        event.preventDefault();
        fuzzySelectedIndex = (fuzzySelectedIndex + 1) % currentFuzzyMatches.length;
        renderFuzzyResults(fuzzySearchInput.value);
      }
    });
  }

  const cliDrawer = resolveElement(ctx, "cliDrawer");
  if (cliDrawer && input) {
    cliDrawer.addEventListener("click", (event) => {
      const tag = event.target && event.target.tagName ? event.target.tagName : "";
      if (tag !== "BUTTON" && tag !== "INPUT") {
        input.focus();
      }
    });
  }

  return { openFuzzyHistory, closeFuzzyHistory, executeCliInput };
}
