import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createEl } from "../../js/core/dom.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import {
  MAX_LINE_LENGTH,
  balanceLines,
  detectLanguage,
  highlightCodeBlock,
  highlightFullDocument,
  highlightLine,
  renderDiff,
  setupSbsResizer,
  truncateLine,
} from "../../js/diff/diff_engine.js";

function createMockHighlighter() {
  return {
    getLanguage(lang) {
      return lang === "python" || lang === "rust" ? { name: lang } : null;
    },
    highlight(text, opts) {
      const escaped = String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return {
        value: `<span class="hljs-keyword" data-lang="${opts.language}">${escaped}</span>`,
      };
    },
  };
}

describe("Shared Diff Engine (Language, Balancing, Highlighting, SBS/Unified/Full/Binary)", () => {
  it("detects languages accurately and truncates ultra-long lines safely", () => {
    assert.equal(detectLanguage("projects/carrier_board/carrier_board.py"), "python");
    assert.equal(detectLanguage("crates/firmware/src/main.rs"), "rust");
    assert.equal(detectLanguage("provider/templates/diff_view.html.j2"), "xml");
    assert.equal(detectLanguage("Makefile"), "makefile");
    assert.equal(detectLanguage("Dockerfile"), "dockerfile");
    assert.equal(detectLanguage("UNKNOWN_EXT.xyz"), "plaintext");

    const longLine = "A".repeat(MAX_LINE_LENGTH + 45);
    const truncated = truncateLine(longLine);
    assert.ok(truncated.startsWith("A".repeat(MAX_LINE_LENGTH)));
    assert.ok(truncated.includes("truncated"));
    assert.equal(truncateLine("short line"), "short line");
  });

  it("balances multi-line highlight spans across newline boundaries", () => {
    const raw = [
      '<span class="hljs-string">"multi',
      "line",
      'literal"</span>',
    ];
    const balanced = balanceLines(raw);
    assert.equal(balanced.length, 3);
    assert.equal(balanced[0], '<span class="hljs-string">"multi</span>');
    assert.equal(balanced[1], '<span class="hljs-string">line</span>');
    assert.equal(balanced[2], '<span class="hljs-string">literal"</span>');
  });

  it("highlights lines and full documents with XSS fallback when highlighter is absent", () => {
    const plainCtx = createMockRuntimeContext();
    assert.equal(
      highlightLine(plainCtx, 'const x = "<svg onload=1>";', "javascript"),
      "const x = &quot;&lt;svg onload=1&gt;&quot;;",
    );

    const hlCtx = createMockRuntimeContext({ syntaxHighlighter: createMockHighlighter() });
    const pyLine = highlightLine(hlCtx, "def compute():", "python");
    assert.ok(pyLine.includes('class="hljs-keyword"'));
    assert.ok(pyLine.includes("def compute():"));

    const docLines = highlightFullDocument(hlCtx, "fn a() {}\nfn b() {}", "rust");
    assert.equal(docLines.length, 2);
    assert.ok(docLines[0].includes('data-lang="rust"'));
    assert.ok(highlightCodeBlock(hlCtx, "x = 1", "python").includes("x = 1"));
  });

  it("renders side-by-side, unified (with del delete class), and full-file diffs with line selection and inline cards", () => {
    const ctx = createMockRuntimeContext({ syntaxHighlighter: createMockHighlighter() });
    const doc = ctx.getDocument();
    const container = createEl(ctx, "div", { id: "diff-root" });
    doc.body.appendChild(container);

    const sampleDiff = {
      file_path: "src/engine.py",
      old_content: "alpha = 1\nbeta = 2\ngamma = 3",
      new_content: "alpha = 1\nbeta = 20\ndelta = 4\ngamma = 3",
      side_by_side: [
        { row_type: "equal", old_no: 1, new_no: 1, old_text: "alpha = 1", new_text: "alpha = 1" },
        { row_type: "replace", old_no: 2, new_no: 2, old_text: "beta = 2", new_text: "beta = 20" },
        { row_type: "insert", old_no: null, new_no: 3, old_text: "", new_text: "delta = 4" },
        { row_type: "equal", old_no: 3, new_no: 4, old_text: "gamma = 3", new_text: "gamma = 3" },
      ],
      hunks: [
        {
          header: "@@ -1,3 +1,4 @@",
          old_start: 1,
          new_start: 1,
          lines: [
            { type: "context", old_line_no: 1, new_line_no: 1, content: "alpha = 1" },
            { type: "del", old_line_no: 2, new_line_no: null, content: "beta = 2" },
            { type: "add", old_line_no: null, new_line_no: 2, content: "beta = 20" },
            { type: "add", old_line_no: null, new_line_no: 3, content: "delta = 4" },
            { type: "context", old_line_no: 3, new_line_no: 4, content: "gamma = 3" },
          ],
        },
      ],
    };

    const clickedLines = [];
    renderDiff(ctx, container, sampleDiff, {
      mode: "side_by_side",
      interactive: true,
      selectedRange: { start: 2, end: 3 },
      comments: [{ id: "c-1", start_line: 2, end_line: 2, body: "Verify gain" }],
      renderCommentCard: (c) =>
        createEl(ctx, "div", { className: "test-inline-comment", text: c.body }),
      onLineClick: ({ line, side, shiftKey }) => {
        clickedLines.push({ line, side, shiftKey });
      },
    });

    const sbsTable = container.querySelector(".sbs-table");
    assert.ok(sbsTable);
    const selectedRows = container.querySelectorAll(".selected");
    assert.ok(selectedRows.length >= 2);
    const commentNodes = container.querySelectorAll(".test-inline-comment");
    assert.equal(commentNodes.length, 1);
    assert.equal(commentNodes[0].textContent, "Verify gain");

    // Click right-hand cell to trigger interactive line click callback
    const rightCells = container.querySelectorAll(".new-code");
    assert.ok(rightCells.length > 0);
    rightCells[0].dispatchEvent({ type: "click", bubbles: true, shiftKey: true });
    assert.equal(clickedLines.length, 1);
    assert.deepEqual(clickedLines[0], { line: 1, side: "new", shiftKey: true });

    // Unified mode preserves both `del` and `delete` classes on removed rows
    renderDiff(ctx, container, sampleDiff, { mode: "unified" });
    const deletedRows = container.querySelectorAll(".delete");
    assert.equal(deletedRows.length, 1);
    assert.equal(deletedRows[0].classList.contains("del"), true);

    // Full-file mode renders every line of new_content
    renderDiff(ctx, container, sampleDiff, { mode: "full_file" });
    const fullRows = container.querySelectorAll(".diff-full-row");
    assert.equal(fullRows.length, 4);
  });

  it("renders binary image previews with error-hiding listener, oversized banners, and SBS column resizer", () => {
    const ctx = createMockRuntimeContext();
    const doc = ctx.getDocument();
    const container = createEl(ctx, "div", { id: "bin-root" });
    doc.body.appendChild(container);

    renderDiff(ctx, container, {
      file_path: "attachments/board_render.png",
      status: "M",
      is_binary: true,
      old_commit: "1111111",
      new_commit: "2222222",
    });

    const imgs = container.querySelectorAll("img");
    assert.equal(imgs.length, 2);
    assert.equal(imgs[0].hasAttribute("onerror"), false);
    imgs[0].dispatchEvent({ type: "error" });
    assert.equal(imgs[0].style.display, "none");

    renderDiff(ctx, container, {
      file_path: "recordings/trace.csv",
      is_oversized: true,
      size_bytes: 5 * 1024 * 1024,
    });
    assert.ok(container.textContent.includes("LARGE FILE DIFF COLLAPSED"));

    // SBS column resizer updates colgroup percentages and persists to storage
    const diffWrap = createEl(ctx, "div", { className: "diff-container" });
    diffWrap.setBoundingClientRect({ left: 0, top: 0, width: 1000, height: 400 });
    const table = createEl(ctx, "table", { className: "sbs-table" });
    const colOld = createEl(ctx, "col", { className: "col-old-code" });
    const colNew = createEl(ctx, "col", { className: "col-new-code" });
    const resizer = createEl(ctx, "div", { className: "sbs-split-resizer" });
    table.appendChild(colOld);
    table.appendChild(colNew);
    table.appendChild(resizer);
    diffWrap.appendChild(table);
    doc.body.appendChild(diffWrap);

    setupSbsResizer(ctx, table, "test_sbs_pct");
    resizer.dispatchEvent({ type: "mousedown", clientX: 600 });
    ctx.emitViewportEvent("mousemove", { clientX: 600 });
    ctx.emitViewportEvent("mouseup", {});
    assert.equal(ctx.getStorage().getItem("test_sbs_pct"), "0.6000");
    assert.equal(colOld.style.width, "60.0%");
    assert.equal(colNew.style.width, "40.0%");
  });
});
