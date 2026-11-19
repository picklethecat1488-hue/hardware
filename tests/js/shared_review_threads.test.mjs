import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createEl } from "../../js/core/dom.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import {
  executeParsedCliCommand,
  getReverseHistoryMatches,
  logCli,
  updateTargetUI,
} from "../../js/review/cli_drawer.js";
import { initCodeReviewApp } from "../../js/review/code_review_app.js";
import {
  COMMENT_STATUS,
  createInlineCommentCard,
  isCommentVisible,
  parseFileReferences,
  renderCommentBody,
  resolveCommentStatus,
  resolveSeverityBadge,
} from "../../js/review/comment_threads.js";
import {
  commentMatchesCommit,
  filterAndSortReviewFiles,
  getFileChanges,
  isAttachmentPath,
  isLfsFile,
  renderFilesList,
} from "../../js/review/file_tree.js";
import {
  handleSessionTermination,
  setReviewVerdict,
  updateSessionMetricsUI,
} from "../../js/review/verdict_controller.js";

describe("Shared Code Review Modules (Comment Threads, File Tree, Verdicts, CLI Drawer, App)", () => {
  it("parses @file:line references and renders comment markdown safely without XSS", () => {
    const parsed = parseFileReferences(
      "Check @provider/pcb/router.py:42 and @crates/mcu/src/lib.rs:12.",
    );
    assert.ok(parsed.includes('data-file="provider/pcb/router.py"'));
    assert.ok(parsed.includes('data-line="42"'));
    assert.ok(parsed.includes('data-file="crates/mcu/src/lib.rs"'));

    const ctx = createMockRuntimeContext();
    const html = renderCommentBody(
      ctx,
      'Fix `<img onerror=alert(1)>` in @src/app.py:10:\n```python\nx = "<unsafe>"\n```',
      "python",
    );
    assert.equal(html.includes("<img onerror"), false);
    assert.ok(html.includes("&lt;img onerror=alert(1)&gt;"));
    assert.ok(html.includes('data-file="src/app.py"'));
    assert.ok(html.includes("&lt;unsafe&gt;"));
    assert.equal(resolveSeverityBadge("MUST_FIX").displayLabel, "MUST FIX");
  });

  it("builds inline comment cards with author redaction and Edit/Delete actions", () => {
    const ctx = createMockRuntimeContext();
    const actions = [];
    const card = createInlineCommentCard(
      ctx,
      {
        id: "cmt-99",
        author: "Private Name <private@domain.com>",
        created_at: "2026-11-12 18:00:00 UTC",
        severity: "MUST_FIX",
        start_line: 10,
        end_line: 14,
        code_snippet: "let mut reg = 0;",
        body: "Guard register write",
      },
      {
        language: "rust",
        authorBlacklist: ["Private Name"],
        onEdit: (id) => actions.push({ op: "edit", id }),
        onDelete: (id) => actions.push({ op: "delete", id }),
      },
    );

    assert.equal(card.textContent.includes("Private Name"), false);
    assert.equal(card.textContent.includes("private@domain.com"), false);
    assert.equal(card.textContent.includes("User"), true);
    assert.equal(card.textContent.includes("Lines L10-L14"), true);

    const editBtn = card.querySelector('[data-action="edit-comment"]');
    const delBtn = card.querySelector('[data-action="delete-comment"]');
    assert.ok(editBtn);
    assert.ok(delBtn);
    editBtn.click();
    delBtn.click();
    assert.deepEqual(actions, [
      { op: "edit", id: "cmt-99" },
      { op: "delete", id: "cmt-99" },
    ]);
  });

  it("extracts hunk navigation blocks, classifies LFS/attachments, and sorts files by proximity", () => {
    assert.equal(isAttachmentPath("feedback/attachments/shot.png"), true);
    assert.equal(isAttachmentPath("projects/carrier_board.py"), false);
    assert.equal(isLfsFile("model.stl", { is_lfs: true }), true);

    const blocks = getFileChanges({
      side_by_side: [
        { row_type: "equal", old_no: 1, new_no: 1 },
        { row_type: "insert", old_no: null, new_no: 2 },
        { row_type: "insert", old_no: null, new_no: 3 },
        { row_type: "equal", old_no: 2, new_no: 4 },
        { row_type: "delete", old_no: 3, new_no: null },
      ],
    });
    assert.equal(blocks.length, 2);
    assert.equal(blocks[0].startLine, 2);
    assert.equal(blocks[0].endLine, 3);
    assert.equal(blocks[1].startLine, 3);

    const sorted = filterAndSortReviewFiles(
      [
        { path: "tools/pcb_helper.py", additions: 1, deletions: 0 },
        { path: "provider/pcb/pcb_footprints.py", additions: 10, deletions: 2 },
        { path: "feedback/attachments/pcb_shot.png", additions: 0, deletions: 0 },
      ],
      {
        query: "pcb",
        activeFilePath: "provider/pcb/router.py",
        hideAttachments: true,
      },
    );
    assert.equal(sorted.length, 2);
    assert.equal(sorted[0].path, "provider/pcb/pcb_footprints.py");
  });

  it("executes CLI commands (must_fix, edit, goto, nc/pc, sel) and updates review verdicts", async () => {
    const postedVerdicts = [];
    const ctx = createMockRuntimeContext({
      inIframe: true,
      fetchRoutes: {
        "POST /api/verdict": (_url, opts) => {
          postedVerdicts.push(JSON.parse(opts.body));
          return { status: "ok", exported_to: "feedback/CR.md" };
        },
      },
    });
    const doc = ctx.getDocument();
    doc.body.appendChild(createEl(ctx, "div", { id: "cliLog" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "cliTargetPill" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "cliPromptPrefix" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "reviewVerdictBadge" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "filesProgressText" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "commentsCountText" }));
    doc.body.appendChild(createEl(ctx, "div", { id: "terminationOverlay", style: { display: "none" } }));
    doc.body.appendChild(createEl(ctx, "div", { id: "terminationSub" }));
    doc.body.appendChild(createEl(ctx, "div", { id: "terminationBanner" }));

    const state = {
      selectedFile: "src/main.rs",
      selectedRange: { start: 12, end: 15 },
      currentSeverity: "PROPOSAL",
      files: [{ path: "src/main.rs" }],
      session: {
        repo_name: "firmware",
        verdict: "IN_REVIEW",
        files: { "src/main.rs": { status: "REVIEWED" } },
        comments: [{ id: "c1", severity: "MUST_FIX", start_line: 12, body: "Initial" }],
      },
    };

    updateTargetUI(ctx, state, true);
    updateSessionMetricsUI(ctx, state);
    assert.equal(doc.getElementById("filesProgressText").textContent, "1/1 (100%)");
    assert.equal(doc.getElementById("commentsCountText").textContent, "1 findings");

    const submitted = [];
    const navEvents = [];
    const handlers = {
      postComment: async (body, sev) => submitted.push({ sev, body }),
      editComment: async (id, body) => submitted.push({ editId: id, body }),
      goto: async (target, line) => navEvents.push({ goto: target, line }),
      navigateChange: async (dir) => navEvents.push({ changeDir: dir }),
      navigateCommit: async (dir) => navEvents.push({ commitDir: dir }),
      navigateFile: async (dir) => navEvents.push({ fileDir: dir }),
      selectLines: (start, end) => {
        state.selectedRange = { start, end };
      },
      setFileStatus: async () => {},
      setVerdict: async () => {},
    };

    await executeParsedCliCommand(ctx, "must_fix Race condition on IRQ", state, handlers);
    assert.deepEqual(submitted[0], { sev: "MUST_FIX", body: "Race condition on IRQ" });

    await executeParsedCliCommand(ctx, "edit c1 Updated explanation", state, handlers);
    assert.deepEqual(submitted[1], { editId: "c1", body: "Updated explanation" });

    await executeParsedCliCommand(ctx, "goto src/lib.rs 88", state, handlers);
    assert.deepEqual(navEvents[0], { goto: "src/lib.rs", line: 88 });

    await executeParsedCliCommand(ctx, "nc", state, handlers);
    assert.deepEqual(navEvents[1], { changeDir: 1 });

    await executeParsedCliCommand(ctx, "sel 20 25", state, handlers);
    assert.deepEqual(state.selectedRange, { start: 20, end: 25 });

    assert.equal(
      getReverseHistoryMatches(["help", "must_fix DMA", "reviewed"], "dma")[0],
      "must_fix DMA",
    );

    await setReviewVerdict(ctx, "APPROVED", {
      logCli: (msg) => logCli(ctx, msg),
      onConclude: () => ctx.postParentMessage({ action: "close_workstation" }),
    });
    assert.deepEqual(postedVerdicts[0], { verdict: "APPROVED", terminate: false });
    ctx.advanceTime(850);
    assert.ok(ctx.parentMessages.some((m) => m.message.action === "close_workstation"));

    handleSessionTermination(ctx, "APPROVED", "feedback/CR.md");
    assert.equal(doc.getElementById("terminationOverlay").style.display, "flex");
  });

  it("boots initCodeReviewApp cleanly against MockRuntimeContext", async () => {
    const ctx = createMockRuntimeContext({
      bootConfig: {
        repoName: "firmware",
        issueKind: "worm",
        trackerRoute: "/worms",
        issueLabel: "WORM",
        singleCommit: false,
      },
      fetchRoutes: {
        "GET /api/session": {
          repo_name: "firmware",
          verdict: "IN_REVIEW",
          files: {},
          comments: [],
        },
        "GET /api/commits": [
          {
            commit_hash: "deadbeef1234",
            short_hash: "deadbee",
            author: "Author <a@b.com>",
            subject: "Test commit",
          },
        ],
        "GET /api/files?commit=deadbeef1234": [
          { path: "src/lib.rs", status: "M", additions: 3, deletions: 1 },
        ],
        "GET /api/diff?file=src%2Flib.rs&commit=deadbeef1234": {
          file_path: "src/lib.rs",
          old_content: "fn a() {}",
          new_content: "fn a() {}\nfn b() {}",
          side_by_side: [
            { row_type: "equal", old_no: 1, new_no: 1, old_text: "fn a() {}", new_text: "fn a() {}" },
            { row_type: "insert", old_no: null, new_no: 2, old_text: "", new_text: "fn b() {}" },
          ],
        },
      },
    });
    const doc = ctx.getDocument();
    for (const id of ["commitsList", "filesList", "diffContent", "cliLog"]) {
      doc.body.appendChild(createEl(ctx, "div", { id }));
    }
    doc.body.appendChild(createEl(ctx, "input", { id: "cliInput" }));

    const app = initCodeReviewApp(ctx);
    await app.ready;
    assert.ok(doc.getElementById("filesList").textContent.includes("lib.rs"));
    app.dispose();
  });

  it("isolates inline comments and file badges by selectedCommit so historical comments never leak into working", async () => {
    assert.equal(commentMatchesCommit({ commit: "7c6e41fdf0f8" }, "working"), false);
    assert.equal(commentMatchesCommit({ commit: "7c6e41fdf0f8" }, "7c6e41fd"), true);
    assert.equal(commentMatchesCommit({ commit: "working" }, "working"), true);
    assert.equal(commentMatchesCommit({ commit: "" }, "working"), true);
    assert.equal(commentMatchesCommit({ commit: "" }, "7c6e41fdf0f8"), false);

    const historicalComments = Array.from({ length: 83 }, (_, idx) => ({
      id: `hist-${idx}`,
      commit: "7c6e41fdf0f88a209379baa8a1a9996778b3a938",
      file_path: "app/carrier_board.md",
      start_line: 1,
      end_line: 1,
      severity: "MUST_FIX",
      resolved: true,
      body: `Historical comment #${idx}`,
    }));

    const ctx = createMockRuntimeContext({
      bootConfig: {
        repoName: "firmware",
        issueKind: "worm",
        trackerRoute: "/worms",
        issueLabel: "WORM",
        singleCommit: false,
      },
      fetchRoutes: {
        "GET /api/session": {
          repo_name: "firmware",
          verdict: "IN_REVIEW",
          files: {},
          comments: historicalComments,
        },
        "GET /api/commits": [
          {
            commit_hash: "working",
            short_hash: "working",
            author: "User",
            subject: "Working Tree Changes",
          },
          {
            commit_hash: "7c6e41fdf0f88a209379baa8a1a9996778b3a938",
            short_hash: "7c6e41fd",
            author: "User",
            subject: "Historical Carrier Board Doc Commit",
          },
        ],
        "GET /api/files?commit=working": [
          { path: "app/carrier_board.md", status: "M", additions: 2, deletions: 2 },
        ],
        "GET /api/files?commit=7c6e41fdf0f88a209379baa8a1a9996778b3a938": [
          { path: "app/carrier_board.md", status: "M", additions: 50, deletions: 10 },
        ],
        "GET /api/diff?commit=working&file=app%2Fcarrier_board.md": {
          file_path: "app/carrier_board.md",
          old_content: "# Carrier Board",
          new_content: "# Carrier Board 2.0",
          side_by_side: [
            {
              row_type: "replace",
              old_no: 1,
              new_no: 1,
              old_text: "# Carrier Board",
              new_text: "# Carrier Board 2.0",
            },
          ],
        },
      },
    });

    const doc = ctx.getDocument();
    for (const id of ["commitsList", "filesList", "diffContent", "cliLog", "commentsCountText"]) {
      doc.body.appendChild(createEl(ctx, "div", { id }));
    }
    doc.body.appendChild(createEl(ctx, "input", { id: "cliInput" }));

    const app = initCodeReviewApp(ctx);
    await app.ready;

    // On `working`, all 83 historical comments from 7c6e41fd must be excluded!
    assert.equal(doc.getElementById("filesList").textContent.includes("83"), false);
    assert.equal(doc.getElementById("diffContent").textContent.includes("Historical comment"), false);
    assert.equal(doc.getElementById("commentsCountText").textContent, "0 findings");

    // When inspecting commit 7c6e41fd directly, its 83 comments appear on `app/carrier_board.md`
    renderFilesList(ctx, {
      selectedCommit: "7c6e41fdf0f88a209379baa8a1a9996778b3a938",
      selectedFile: "app/carrier_board.md",
      commits: [],
      files: [{ path: "app/carrier_board.md", status: "M", additions: 50, deletions: 10 }],
      session: { files: {}, comments: historicalComments },
    });
    assert.equal(doc.getElementById("filesList").textContent.includes("83"), true);
    app.dispose();
  });

  it("supports OPEN -> RESOLVED -> CLOSED lifecycle actions, CLI status commands, and Show Closed filtering", async () => {
    assert.equal(resolveCommentStatus({ resolved: false }), COMMENT_STATUS.OPEN);
    assert.equal(resolveCommentStatus({ resolved: true }), COMMENT_STATUS.RESOLVED);
    assert.equal(
      resolveCommentStatus({ status: "CLOSED", resolved: true }),
      COMMENT_STATUS.CLOSED,
    );
    assert.equal(isCommentVisible({ status: "OPEN" }, false), true);
    assert.equal(isCommentVisible({ status: "RESOLVED", resolved: true }, false), true);
    assert.equal(isCommentVisible({ status: "CLOSED", resolved: true }, false), false);
    assert.equal(isCommentVisible({ status: "CLOSED", resolved: true }, true), true);

    const ctx = createMockRuntimeContext();
    const doc = ctx.getDocument();
    doc.body.appendChild(createEl(ctx, "div", { id: "cliLog" }));
    doc.body.appendChild(createEl(ctx, "ul", { id: "filesList" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "filesCountHeader" }));
    doc.body.appendChild(createEl(ctx, "span", { id: "commentsCountText" }));
    const showClosedCb = createEl(ctx, "input", {
      id: "showClosedCommentsCb",
      attrs: { type: "checkbox" },
    });
    showClosedCb.checked = false;
    doc.body.appendChild(showClosedCb);

    const statusTransitions = [];
    const openCard = createInlineCommentCard(
      ctx,
      { id: "c-open", severity: "MUST_FIX", status: "OPEN", start_line: 5, body: "Fix bounds" },
      { onStatusChange: (id, status) => statusTransitions.push({ id, status }) },
    );
    assert.ok(openCard.textContent.includes("[OPEN]"));
    const resolveBtn = openCard.querySelector('[data-status="RESOLVED"]');
    assert.ok(resolveBtn);
    resolveBtn.click();

    const resolvedCard = createInlineCommentCard(
      ctx,
      {
        id: "c-res",
        severity: "PROPOSAL",
        status: "RESOLVED",
        resolved: true,
        resolution_notes: "Added bounds check",
        start_line: 8,
        body: "Validate index",
      },
      { onStatusChange: (id, status) => statusTransitions.push({ id, status }) },
    );
    assert.ok(resolvedCard.textContent.includes("[RESOLVED]"));
    const notesBlock = resolvedCard.querySelector(".inline-comment-resolution");
    assert.ok(notesBlock);
    assert.ok(notesBlock.innerHTML.includes("Added bounds check"));
    const closeBtn = resolvedCard.querySelector('[data-status="CLOSED"]');
    const reopenBtn = resolvedCard.querySelector('[data-status="OPEN"]');
    assert.ok(closeBtn);
    assert.ok(reopenBtn);
    closeBtn.click();
    reopenBtn.click();

    assert.deepEqual(statusTransitions, [
      { id: "c-open", status: "RESOLVED" },
      { id: "c-res", status: "CLOSED" },
      { id: "c-res", status: "OPEN" },
    ]);

    // Verify CLOSED comments are hidden from file badges and metrics until Show Closed is checked
    const reviewState = {
      selectedCommit: "working",
      selectedFile: "src/main.rs",
      commits: [],
      files: [{ path: "src/main.rs", status: "M", additions: 4, deletions: 1 }],
      session: {
        repo_name: "firmware",
        verdict: "IN_REVIEW",
        files: {},
        comments: [
          { id: "c1", commit: "working", file_path: "src/main.rs", status: "RESOLVED", resolved: true, severity: "MUST_FIX", start_line: 1, body: "Fixed" },
          { id: "c2", commit: "working", file_path: "src/main.rs", status: "CLOSED", resolved: true, severity: "NIT", start_line: 2, body: "Closed" },
        ],
      },
    };

    renderFilesList(ctx, reviewState);
    updateSessionMetricsUI(ctx, reviewState);
    assert.ok(doc.getElementById("filesList").textContent.includes("💬 1"));
    assert.ok(doc.getElementById("filesList").querySelector(".quake-badge-green"));
    assert.equal(doc.getElementById("commentsCountText").textContent, "1 findings (0 open)");

    showClosedCb.checked = true;
    renderFilesList(ctx, reviewState);
    updateSessionMetricsUI(ctx, reviewState);
    assert.ok(doc.getElementById("filesList").textContent.includes("💬 2"));
    assert.equal(doc.getElementById("commentsCountText").textContent, "2 findings (0 open)");

    // Verify CLI commands: resolve, close, reopen
    const cliStatusCalls = [];
    const handlers = {
      updateCommentStatus: async (id, status, notes) => cliStatusCalls.push({ id, status, notes }),
    };
    await executeParsedCliCommand(ctx, "resolve c1 Fixed IRQ", reviewState, handlers);
    await executeParsedCliCommand(ctx, "close c1 Verified LGTM", reviewState, handlers);
    await executeParsedCliCommand(ctx, "reopen c1 Still reproduces", reviewState, handlers);
    assert.deepEqual(cliStatusCalls, [
      { id: "c1", status: "RESOLVED", notes: "Fixed IRQ" },
      { id: "c1", status: "CLOSED", notes: "Verified LGTM" },
      { id: "c1", status: "OPEN", notes: "Still reproduces" },
    ]);
  });
});
