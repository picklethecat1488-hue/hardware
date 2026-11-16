import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createEl } from "../../js/core/dom.js";
import { createMockRuntimeContext } from "../../js/core/runtime_context.js";
import {
  classifyAttachmentType,
  encodeBytesToBase64,
  processFileForUpload,
  renderAttachmentsGrid,
} from "../../js/tracker/attachment_dropzone.js";
import {
  computeIssueMetrics,
  extractUniqueComponents,
  filterAndSortIssues,
} from "../../js/tracker/issue_filter.js";
import { renderMarkdownPreview } from "../../js/tracker/markdown_preview.js";
import {
  bindReviewTasksEvents,
  renderReviewTasksList,
  runReviewTaskCommand,
} from "../../js/tracker/review_tasks.js";
import {
  generateFallbackIssueId,
  initTrackerApp,
} from "../../js/tracker/tracker_app.js";

function populateTrackerDom(ctx, prefix) {
  const doc = ctx.getDocument();
  for (const id of ["m-total", "m-open", "m-resolved", `active-${prefix}-id-display`]) {
    doc.body.appendChild(createEl(ctx, "span", { id }));
  }
  doc.body.appendChild(createEl(ctx, "button", { id: `btn-copy-active-${prefix}` }));
  doc.body.appendChild(createEl(ctx, "input", { id: "search-input" }));
  for (const f of ["open", "planned", "all", "resolved"]) {
    doc.body.appendChild(
      createEl(ctx, "button", {
        id: `filter-${f}`,
        dataset: { action: "set-filter", filter: f },
      }),
    );
  }
  for (const selId of [
    "select-filter-category",
    "select-filter-severity",
    `select-${prefix}-sort`,
    `${prefix}-severity`,
    `${prefix}-status`,
    `${prefix}-category`,
  ]) {
    doc.body.appendChild(createEl(ctx, "select", { id: selId }));
  }
  doc.body.appendChild(createEl(ctx, "ul", { id: `${prefix}-list` }));
  doc.body.appendChild(createEl(ctx, "datalist", { id: `${prefix}-component-list` }));
  for (const inputSuffix of ["title", "component"]) {
    doc.body.appendChild(createEl(ctx, "input", { id: `${prefix}-${inputSuffix}` }));
  }
  for (const taSuffix of [
    "description",
    "steps",
    "expected",
    "actual",
    "logs",
    "resolution",
  ]) {
    doc.body.appendChild(createEl(ctx, "textarea", { id: `${prefix}-${taSuffix}` }));
  }
  doc.body.appendChild(createEl(ctx, "div", { id: "review-action-banner" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "rejection-feedback-card" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "rejection-feedback-text" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "accepted-feedback-card" }));
  doc.body.appendChild(createEl(ctx, "span", { id: "accepted-timestamp-display" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "attachments-grid" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "attached-commits-list" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "review-tasks-list" }));
  doc.body.appendChild(createEl(ctx, "input", { id: "input-attach-commit" }));
  doc.body.appendChild(createEl(ctx, "input", { id: "input-task-title" }));
  doc.body.appendChild(createEl(ctx, "input", { id: "input-task-command" }));
  doc.body.appendChild(createEl(ctx, "div", { id: "dropzone" }));
  doc.body.appendChild(
    createEl(ctx, "input", {
      id: prefix === "worm" ? "file-input" : "file-upload",
      attrs: { type: "file" },
    }),
  );
}

describe("Shared Tracker Modules (Filtering, Markdown, Base64 Upload, Review Tasks, BUG/WORM App)", () => {
  it("filters, sorts, and computes metrics across OPEN, PLANNED, RESOLVED, and CLOSED issues", () => {
    const issues = [
      {
        id: "BUG-001",
        title: "DRC clearance error",
        status: "OPEN",
        severity: "HIGH",
        category: "PCB",
        component: "carrier_board",
        created_at: "2026-11-10 10:00:00 UTC",
      },
      {
        id: "BUG-002",
        title: "Planned enclosure tweak",
        status: "PLANNED",
        severity: "LOW",
        category: "CAD",
        component: "shell",
        created_at: "2026-11-11 10:00:00 UTC",
      },
      {
        id: "BUG-003",
        title: "Pump stall on startup",
        status: "RESOLVED",
        severity: "CRITICAL",
        category: "PHYSICS",
        component: "impeller",
        created_at: "2026-11-12 10:00:00 UTC",
      },
    ];

    assert.deepEqual(computeIssueMetrics(issues), { total: 3, open: 1, resolved: 1 });
    assert.deepEqual(extractUniqueComponents(issues), ["carrier_board", "impeller", "shell"]);

    // Default "open" filter includes OPEN + RESOLVED (awaiting review), excluding PLANNED & CLOSED
    const openVisible = filterAndSortIssues(issues, { statusFilter: "open", sortBy: "severity" });
    assert.deepEqual(
      openVisible.map((i) => i.id),
      ["BUG-003", "BUG-001"],
    );

    const plannedOnly = filterAndSortIssues(issues, { statusFilter: "planned" });
    assert.deepEqual(
      plannedOnly.map((i) => i.id),
      ["BUG-002"],
    );
  });

  it("renders safe Markdown previews without XSS or unsafe link schemes", () => {
    const ctx = createMockRuntimeContext();
    const md = [
      "## Root Cause",
      "- Checked `NRST` pull-up & **decoupling**",
      "- Reject [bad](javascript:alert(1)) but allow [docs](https://example.com/spec)",
      "```python",
      'x = "<script>boom()</script>"',
      "```",
    ].join("\n");

    const html = renderMarkdownPreview(ctx, md);
    assert.ok(html.includes("<h2>Root Cause</h2>"));
    assert.ok(html.includes('<code class="md-inline-code">NRST</code>'));
    assert.ok(html.includes("<strong>decoupling</strong>"));
    assert.equal(html.includes('href="javascript:'), false);
    assert.ok(html.includes('href="https://example.com/spec"'));
    assert.equal(html.includes("<script>boom()"), false);
    assert.ok(html.includes("&lt;script&gt;boom()&lt;/script&gt;"));
  });

  it("encodes binary ArrayBuffers to Base64 without globals and processes attachment uploads", async () => {
    assert.equal(encodeBytesToBase64(new Uint8Array([77, 97, 110])), "TWFu");
    assert.equal(encodeBytesToBase64(new Uint8Array([77, 97])), "TWE=");
    assert.equal(encodeBytesToBase64(new Uint8Array([77])), "TQ==");
    assert.equal(classifyAttachmentType("capture.png"), "screenshot");
    assert.equal(classifyAttachmentType("trace.log"), "document");

    const ctx = createMockRuntimeContext();
    const doc = ctx.getDocument();
    const grid = createEl(ctx, "div", { id: "att-grid" });
    doc.body.appendChild(grid);

    const uploadedPayloads = [];
    const mockFile = {
      name: "scope_capture.png",
      size: 4,
      type: "image/png",
      async arrayBuffer() {
        return new Uint8Array([137, 80, 78, 71]).buffer;
      },
    };

    await processFileForUpload(ctx, mockFile, {
      isPaste: false,
      getActiveId: () => "WORM-042",
      entityIdParam: "worm_id",
      onUploadPayload: async (payload) => {
        uploadedPayloads.push(payload);
      },
    });

    assert.equal(uploadedPayloads.length, 1);
    assert.equal(uploadedPayloads[0].worm_id, "WORM-042");
    assert.equal(uploadedPayloads[0].file_type, "screenshot");
    assert.equal(uploadedPayloads[0].content_base64, "iVBORw==");

    let removedIndex = -1;
    renderAttachmentsGrid(
      ctx,
      grid,
      [
        {
          filename: "scope_capture.png",
          file_path: "attachments/scope_capture.png",
          size_bytes: 2048,
        },
      ],
      (idx) => {
        removedIndex = idx;
      },
    );
    const removeBtn = grid.querySelector('[data-action="remove-attachment"]');
    assert.ok(removeBtn);
    removeBtn.click();
    assert.equal(removedIndex, 0);
  });

  it("renders review tasks and executes demo commands into #task-output-<id>", async () => {
    const ctx = createMockRuntimeContext({
      fetchRoutes: {
        "POST /api/bugs/run_command": {
          status: "ok",
          exit_code: 0,
          stdout: "PING PONG OK",
          stderr: "",
        },
      },
    });
    const doc = ctx.getDocument();
    const list = createEl(ctx, "div", { id: "review-tasks-list" });
    doc.body.appendChild(list);

    const toggled = [];
    renderReviewTasksList(ctx, list, [
      {
        id: "t-1",
        title: "Verify CLI ping",
        status: "PENDING",
        command: "python tools/host.py cli ping",
      },
    ]);
    bindReviewTasksEvents(ctx, list, {
      onToggleTask: (id, st) => toggled.push({ id, st }),
      onRunCommand: (id, cmd) => {
        void runReviewTaskCommand(ctx, "/api/bugs", "BUG-009", id, cmd);
      },
    });

    const checkbox = list.querySelector('[data-action="toggle-review-task"]');
    checkbox.dispatchEvent({ type: "change", bubbles: true });
    assert.deepEqual(toggled, [{ id: "t-1", st: "PENDING" }]);

    const runBtn = list.querySelector('[data-action="run-task-cmd"]');
    runBtn.click();
    for (let i = 0; i < 6; i += 1) {
      await Promise.resolve();
    }
    const outPre = doc.getElementById("task-output-t-1");
    assert.ok(outPre.textContent.includes("[Exit Code 0]"));
    assert.ok(outPre.textContent.includes("PING PONG OK"));
  });

  it("drives initTrackerApp identically in both BUG (/api/bugs) and WORM (/api/worms) modes", async () => {
    assert.ok(generateFallbackIssueId("BUG", []).startsWith("BUG-"));
    assert.ok(generateFallbackIssueId("WORM", []).startsWith("WORM-"));

    for (const mode of [
      {
        entityKind: "bug",
        entityLabel: "BUG",
        collectionKey: "bugs",
        fieldPrefix: "bug",
        apiBase: "/api/bugs",
        nextIdEndpoint: "/api/next_bug_id",
        seedId: "BUG-100",
        nextId: "BUG-101",
      },
      {
        entityKind: "worm",
        entityLabel: "WORM",
        collectionKey: "worms",
        fieldPrefix: "worm",
        apiBase: "/api/worms",
        nextIdEndpoint: "/api/next_worm_id",
        seedId: "WORM-200",
        nextId: "WORM-201",
      },
    ]) {
      const savedPayloads = [];
      const acceptedPayloads = [];
      const ctx = createMockRuntimeContext({
        bootConfig: {
          ...mode,
          pollIntervalMs: 0,
          initialDatabase: {
            [mode.collectionKey]: [
              {
                id: mode.seedId,
                title: "Initial defect",
                status: "RESOLVED",
                severity: "HIGH",
                category: "FIRMWARE",
                component: "comms",
              },
            ],
          },
        },
        fetchRoutes: {
          [`GET ${mode.nextIdEndpoint}`]: { next_id: mode.nextId },
          [`POST ${mode.apiBase}`]: (_url, opts) => {
            const body = JSON.parse(opts.body);
            savedPayloads.push(body);
            return body;
          },
          [`POST ${mode.apiBase}/accept`]: (_url, opts) => {
            const body = JSON.parse(opts.body);
            acceptedPayloads.push(body);
            return {
              status: "ok",
              [mode.entityKind]: {
                id: body.id,
                status: "CLOSED",
                accepted_at: "2026-11-12 21:00:00 UTC",
              },
            };
          },
        },
      });

      populateTrackerDom(ctx, mode.fieldPrefix);
      const app = initTrackerApp(ctx);
      assert.equal(app.getActiveId(), mode.seedId);

      // Accept resolved issue transitions it to CLOSED via parameterized endpoint
      await app.acceptActiveIssue();
      assert.equal(acceptedPayloads.length, 1);
      assert.equal(acceptedPayloads[0].id, mode.seedId);
      assert.equal(app.getItems()[0].status, "CLOSED");

      // Creating a new issue fetches next_id from parameterized endpoint and saves
      await app.createNewIssue("deadbeef");
      assert.equal(app.getActiveId(), mode.nextId);
      assert.ok(savedPayloads.some((p) => p.id === mode.nextId && p.description.includes("deadbeef")));
      app.destroy();
    }
  });
});
