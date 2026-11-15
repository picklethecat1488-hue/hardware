import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createEl } from "../../js/core/dom.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import { createConflictGroupElement, resolveConflictFile } from "../../js/vcs/conflict_resolver.js";
import { initDiffViewApp, parseQueryParams } from "../../js/vcs/diff_view_app.js";
import {
  bindSmartlogEvents,
  computeShiftRangeSelection,
  renderSmartlogNodes,
  resolveBranchBadgeAction,
} from "../../js/vcs/smartlog_dag.js";
import {
  bindFilesContainerEvents,
  discardSelectedWorkingFiles,
  renderWorkingTreeFiles,
} from "../../js/vcs/working_tree.js";

describe("Shared VCS Smartlog DAG, Working Tree, Conflict Resolver, & Diff View App", () => {
  it("resolves branch badge click actions and computes shift-range commit selections", () => {
    assert.deepEqual(
      resolveBranchBadgeAction("origin/feat", "https://github.com/org/repo/pull/9", ""),
      { kind: "open_url", url: "https://github.com/org/repo/pull/9" },
    );
    assert.deepEqual(
      resolveBranchBadgeAction("origin/main", "", "https://github.com/org/repo"),
      { kind: "open_url", url: "https://github.com/org/repo/tree/main" },
    );
    assert.equal(resolveBranchBadgeAction("local-topic", "", "").kind, "toast");

    const range = computeShiftRangeSelection(["c1", "c2", "c3", "c4"], "c4", "c2");
    assert.deepEqual(range, ["c2", "c3", "c4"]);
    assert.deepEqual(parseQueryParams("?commit=abc123&file=foo.py"), {
      commit: "abc123",
      file: "foo.py",
    });
  });

  it("renders Smartlog DAG nodes with author redaction and dispatches both BUG and WORM actions", () => {
    for (const mode of [
      { issueKind: "bug", issueLabel: "BUG", trackerRoute: "/bugs" },
      { issueKind: "worm", issueLabel: "WORM", trackerRoute: "/worms" },
    ]) {
      const ctx = createMockRuntimeContext();
      const doc = ctx.getDocument();
      const listEl = createEl(ctx, "div", { id: "smartlogList" });
      const countBadge = createEl(ctx, "span", { id: "selectedCountBadge" });
      doc.body.appendChild(listEl);
      doc.body.appendChild(countBadge);

      const state = {
        activeCommit: "a1b2c3d4e5f6",
        selectedCommits: [],
      };
      const nodes = [
        {
          commit_hash: "a1b2c3d4e5f6",
          short_hash: "a1b2c3d",
          author: "Real Person <personal@gmail.com>",
          date: "2 hours ago",
          subject: "Fix telemetry ring buffer",
          graph_art: "o ",
          is_head: true,
          is_merged: false,
          branches: ["feat-ring"],
          bug_tags:
            mode.issueKind === "bug"
              ? [{ id: "BUG-101", status: "OPEN", title: "Telemetry" }]
              : [],
          worm_tags:
            mode.issueKind === "worm"
              ? [{ id: "WORM-202", status: "OPEN", title: "Ring buffer" }]
              : [],
        },
        {
          commit_hash: "f6e5d4c3b2a1",
          short_hash: "f6e5d4c",
          author: "Another Handle",
          date: "1 day ago",
          subject: "Base commit",
          graph_art: "| ",
          is_head: false,
          is_merged: true,
          branches: ["origin/main"],
        },
      ];

      const events = [];
      renderSmartlogNodes(ctx, listEl, nodes, state, mode);
      bindSmartlogEvents(ctx, listEl, state, mode, {
        onSelectCommit: (hash) => events.push({ type: "select", hash }),
        onJumpToCR: (hash) => events.push({ type: "cr", hash }),
        onOpenIssue: (id) => events.push({ type: "issue", id }),
        onCreateIssueForCommit: (hash) => events.push({ type: "create-issue", hash }),
      });

      // Verify personal author/email was redacted in rendered DOM
      assert.equal(listEl.textContent.includes("Real Person"), false);
      assert.equal(listEl.textContent.includes("personal@gmail.com"), false);
      assert.equal(listEl.textContent.includes("User"), true);

      // Multi-select checkbox updates state.selectedCommits
      const checkboxes = listEl.querySelectorAll(".commit-checkbox");
      assert.equal(checkboxes.length, 2);
      checkboxes[0].checked = true;
      checkboxes[0].click();
      assert.deepEqual(state.selectedCommits, ["a1b2c3d4e5f6"]);

      // Click issue badge opens BUG-101 or WORM-202
      const issueBadges = listEl.querySelectorAll('[data-action="open-issue"]');
      assert.equal(issueBadges.length, 1);
      issueBadges[0].click();
      assert.deepEqual(events[0], {
        type: "issue",
        id: mode.issueKind === "bug" ? "BUG-101" : "WORM-202",
      });

      // Click CR badge dispatches jump-cr
      const crBtn = listEl.querySelector('[data-action="jump-cr"]');
      assert.ok(crBtn);
      crBtn.click();
      assert.deepEqual(events[1], { type: "cr", hash: "a1b2c3d4e5f6" });
    }
  });

  it("renders working tree staged/unstaged/conflict files and posts stage & conflict resolution requests", async () => {
    const stagedPayloads = [];
    const resolvedPayloads = [];
    const ctx = createMockRuntimeContext({
      fetchRoutes: {
        "POST /api/stage": (_url, opts) => {
          stagedPayloads.push(JSON.parse(opts.body));
          return { status: "ok" };
        },
        "POST /api/unstage": { status: "ok" },
        "POST /api/resolve_conflict": (_url, opts) => {
          resolvedPayloads.push(JSON.parse(opts.body));
          return { status: "ok" };
        },
      },
    });
    const doc = ctx.getDocument();
    const container = createEl(ctx, "div", { id: "filesContainer" });
    doc.body.appendChild(container);

    const state = {
      activeCommit: "working",
      activeFile: "src/driver.rs",
      feedbackCollapsed: true,
      conflicts: [{ path: "src/conflict.rs", status: "UU" }],
      workingFiles: [
        { path: "src/staged.rs", is_staged: true, status: "M", additions: 5, deletions: 1 },
        { path: "src/driver.rs", is_staged: false, status: "M", additions: 2, deletions: 0 },
        { path: "feedback/WORM_01.md", is_feedback: true, status: "?" },
      ],
    };

    let refreshCount = 0;
    const selectedFiles = [];
    renderWorkingTreeFiles(ctx, container, state, (autoPath) => selectedFiles.push(autoPath));
    bindFilesContainerEvents(ctx, container, state, {
      onRefreshFiles: async () => {
        refreshCount += 1;
      },
      onSelectFile: (p) => selectedFiles.push(p),
    });

    const stageBtn = container.querySelector('[data-action="stage-file"]');
    assert.ok(stageBtn);
    stageBtn.click();
    for (let i = 0; i < 4; i += 1) {
      await Promise.resolve();
    }
    assert.deepEqual(stagedPayloads[0], { file: "src/driver.rs" });
    assert.equal(refreshCount, 1);

    const conflictGroup = createConflictGroupElement(
      ctx,
      [{ path: "src/conflict.rs", status: "UU" }],
      "src/conflict.rs",
    );
    assert.ok(conflictGroup.textContent.includes("Conflicts"));
    await resolveConflictFile(ctx, "src/conflict.rs", "ours", async () => {
      refreshCount += 1;
    });
    assert.deepEqual(resolvedPayloads[0], { file: "src/conflict.rs", resolution: "ours" });
    assert.equal(refreshCount, 2);
  });

  it("boots initDiffViewApp cleanly with initialSyncDone: false, completes feedback sync, and handles modal/selection actions", async () => {
    let syncPostCalls = 0;
    const ctx = createMockRuntimeContext({
      bootConfig: {
        repoName: "hardware",
        issueKind: "bug",
        trackerRoute: "/bugs",
        issueLabel: "BUG",
        initialSyncDone: false,
      },
      fetchRoutes: {
        "GET /api/working": [],
        "GET /api/conflicts": [],
        "GET /api/session?type=diff": { working_files: [], conflicts: [] },
        "POST /api/sync_feedback": () => {
          syncPostCalls += 1;
          return {
            status: "ok",
            initial_sync_done: true,
            bugs: { total_bugs: 7, scanned: 7, merged: 0 },
            review: { total_comments: 3 },
          };
        },
      },
    });
    const doc = ctx.getDocument();
    const smartlogList = createEl(ctx, "div", {
      id: "smartlogList",
      children: [
        createEl(ctx, "div", {
          className: "smartlog-node",
          dataset: { hash: "c1" },
          children: [createEl(ctx, "input", { className: "commit-checkbox", attrs: { type: "checkbox", value: "c1" } })],
        }),
        createEl(ctx, "div", {
          className: "smartlog-node",
          dataset: { hash: "c2" },
          children: [createEl(ctx, "input", { className: "commit-checkbox", attrs: { type: "checkbox", value: "c2" } })],
        }),
        createEl(ctx, "div", {
          className: "smartlog-node",
          dataset: { hash: "c3" },
          children: [createEl(ctx, "input", { className: "commit-checkbox", attrs: { type: "checkbox", value: "c3" } })],
        }),
      ],
    });
    doc.body.appendChild(smartlogList);
    doc.body.appendChild(createEl(ctx, "span", { id: "selectedCountBadge" }));
    doc.body.appendChild(createEl(ctx, "div", { id: "filesContainer" }));
    doc.body.appendChild(createEl(ctx, "div", { id: "diffContent" }));

    const syncModal = createEl(ctx, "div", { id: "syncModalOverlay", style: { display: "flex" } });
    const syncBar = createEl(ctx, "div", { id: "syncProgressBar", style: { width: "20%" } });
    const syncPct = createEl(ctx, "div", { id: "syncProgressPercent", text: "20%" });
    const syncStatus = createEl(ctx, "div", { id: "syncStatusText", text: "Scanning..." });
    syncModal.appendChild(syncBar);
    syncModal.appendChild(syncPct);
    syncModal.appendChild(syncStatus);
    doc.body.appendChild(syncModal);

    const wsModal = createEl(ctx, "div", { id: "workstationModal", style: { display: "none" } });
    const wsIframe = createEl(ctx, "iframe", { id: "workstationIframe" });
    wsModal.appendChild(wsIframe);
    doc.body.appendChild(wsModal);

    const app = initDiffViewApp(ctx);
    for (let i = 0; i < 6; i += 1) {
      await Promise.resolve();
    }

    assert.equal(syncPostCalls, 1);
    assert.equal(syncPct.textContent, "100%");
    assert.ok(syncStatus.textContent.includes("Synchronized 7 bugs and 3 review comments"));
    ctx.advanceTime(500);
    assert.equal(syncModal.style.display, "none");
    assert.equal(ctx.historyEntries.some((entry) => entry.action === "reload"), true);

    // Verify Shift+click commit range selection works without ctx.querySelectorAll errors
    await app.selectCommit("c1");
    await app.selectCommit("c3", { shiftKey: true });
    assert.deepEqual(app.state.selectedCommits, ["c1", "c2", "c3"]);

    // Verify discardSelectedWorkingFiles handles empty selection cleanly via queryAll
    await discardSelectedWorkingFiles(ctx);

    // Child iframe message opens and closes workstation modal seamlessly
    ctx.emitViewportEvent("message", {
      data: { action: "open_workstation", url: "/review?revisions=abc123" },
    });
    assert.equal(wsModal.style.display, "flex");
    assert.equal(wsIframe.getAttribute("src"), "/review?revisions=abc123");

    ctx.emitViewportEvent("message", {
      data: { action: "close_workstation" },
    });
    assert.equal(wsModal.style.display, "none");
    app.dispose();
  });

  it("dismisses #syncModalOverlay cleanly even if /api/sync_feedback rejects on boot", async () => {
    const ctx = createMockRuntimeContext({
      bootConfig: {
        repoName: "hardware",
        issueKind: "bug",
        trackerRoute: "/bugs",
        issueLabel: "BUG",
        initialSyncDone: false,
      },
      fetchRoutes: {
        "GET /api/working": [],
        "GET /api/conflicts": [],
        "POST /api/sync_feedback": () => {
          throw new Error("Connection reset");
        },
      },
    });
    const doc = ctx.getDocument();
    doc.body.appendChild(createEl(ctx, "div", { id: "smartlogList" }));
    doc.body.appendChild(createEl(ctx, "div", { id: "filesContainer" }));
    const syncModal = createEl(ctx, "div", { id: "syncModalOverlay", style: { display: "flex" } });
    const syncStatus = createEl(ctx, "div", { id: "syncStatusText", text: "Scanning..." });
    syncModal.appendChild(syncStatus);
    doc.body.appendChild(syncModal);

    const app = initDiffViewApp(ctx);
    for (let i = 0; i < 6; i += 1) {
      await Promise.resolve();
    }
    ctx.advanceTime(600);
    assert.equal(syncModal.style.display, "none");
    app.dispose();
  });
});
