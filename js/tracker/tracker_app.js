/**
 * Shared Issue Tracker Workstation Application (`BUG` & `WORM` Parameterized).
 *
 * Zero-globals ES2024 entry point driving both Hardware `bug_report.html.j2`
 * and Firmware `worm_report.html.j2` via `#app-boot-config` and `#initial-tracker-db`.
 */

import {
  applyIframeContextClass,
  bindDelegatedEvent,
  clearChildren,
  createEl,
} from "../core/dom.js";
import { showConfirmModal } from "../core/modal.js";
import { performActionWithProgress } from "../core/progress.js";
import { getRuntimeContext } from "../core/runtime_context.js";
import { copyToClipboard, showToast } from "../core/toast.js";
import { initUiScaleControl } from "../core/ui_scale.js";
import { bindAttachmentDropzone, renderAttachmentsGrid } from "./attachment_dropzone.js";
import {
  computeIssueMetrics,
  extractUniqueComponents,
  filterAndSortIssues,
  getSeverityBadgeClass,
  getStatusBadgeInfo,
} from "./issue_filter.js";
import { toggleMarkdownPreviewForButton } from "./markdown_preview.js";
import {
  addReviewTask,
  bindReviewTasksEvents,
  renderReviewTasksList,
  runReviewTaskCommand,
  toggleReviewTaskStatus,
} from "./review_tasks.js";

const BUG_ADJS =
  "AGILE AMBER ANTENNAL ARMORED BANDED BARBED BRIGHT BRISTLY BUZZING CAMOUFLAGED CHITINOUS CLICKING CREEPING CRIMSON DARTING DIURNAL DORSAL EMERALD FAST FEATHERED FIERCE FLEET FLITTING FLYING GLOWING GOLDEN HAIRY HARVEST HOVERING HUNTER IRIDESCENT JUMPING LEAPING LUMINESCENT LUSTROUS MANDIBLED METALLIC MIMIC MOTTLED NIMBLE NOCTURNAL OBSIDIAN PINCERED PLUMED POLLEN PROBOSCID PUNCTATE QUICK RADIANT RUSTY SCALED SEGMENTED SERRATED SHINING SILKEN SPECKLED SPOTTED SPRINGING STINGING STRIDULATING STRIPED SWARMING SWIFT TARSIAL THORACIC TRANSLUCENT VELVETY VIBRANT WINGED".split(
    " ",
  );
const BUG_NOUNS =
  "ANT APHID BACKSWIMMER BEE BEETLE BLOWFLY BUMBLEBEE BUTTERFLY CADDISFLY CATERPILLAR CENTIPEDE CHRYSALIS CICADA COCKROACH COCOON CRICKET DAMSELFLY DARNER DOBSONFLY DRAGONFLY EARWIG FIREBUG FIREFLY FLEA FLY FRUITFLY GNAT GRASSHOPPER GRUB HARVESTMAN HORNET HORSEFLY HOVERFLY INSTAR JEWELBEETLE KATYDID LACEWING LADYBUG LARVA LEAFHOPPER LOCUST LONGHORN MANTIS MAYFLY MIDGE MILLIPEDE MITE MOSQUITO MOTH NYMPH PLANTHOPPER PUPA ROACH ROVEBEETLE SAWFLY SCARAB SCORPION SILVERFISH SKIPPER SPIDER SPRINGTAIL STAGBEETLE STINKBUG STONEFLY TARANTULA TERMITE THRIPS TICK TIGERBEETLE TREEHOPPER WASP WATERSTRIDER WEEVIL WOODBORER".split(
    " ",
  );

const WORM_ADJS =
  "ANNELIDIC BLIND BRISTLY BURROWING CHITINOUS COILING COMPOSTED CREEPING DAMP DEEP DIRT EARTHEN EMBEDDED FERTILE FLESHY FLEXIBLE FOSSORIAL GLIDING GLOWING GROUNDED HUMIC INCHING LARVAL LITHE LOAMY LUBRICATED LUMINESCENT LUSTROUS MOIST MUDDY NOCTURNAL ORGANIC PEATY PINK PROBOSCID RADIANT ROOTED ROUND SEGMENTED SERPENTINE SETOSE SILKEN SLICK SLIMY SLITHERING SOILBOUND SQUIRMY SUBTERRANEAN SUPPLE TRANSLUCENT TUNNELING UNDULATING VELVETY VERMICULAR VERMIFORM WRIGGLY WRITHING".split(
    " ",
  );
const WORM_NOUNS =
  "ANNELID BEETLE BLOODWORM BOBBIT BOOKWORM BRISTLE BRISTLEWORM BURROWER CASTING CATERPILLAR CENTIPEDE CHAETOPOD CHRYSALIS CLITELLUM COCOON COMPOSTER CRAWLER CREEPER DIGGER EARTHWORM EEL ENCHYTRAEID FIREWORM FLATWORM GLOWWORM GRUB HELMINTH INCHWORM LARVA LEECH LOOPER LUGWORM LUMBRICUS MAGGOT MEALWORM MILLIPEDE MINER NEMATODE NIGHTCRAWLER NYMPH OLIGOCHAETE PALOLO PLANARIAN POLYCHAETE PUPA REDWORM RIBBONWORM ROOTER ROUNDWORM SANDWORM SEGMENT SERPULA SETAE SILKWORM SIPUNCULID SLUG SNAIL SQUIRMER TAPEWORM TUBEWORM TUNNELER VELVETWORM VERMIS VINEGARWORM WAXWORM WIREWORM WOODLOUSE WRIGGLER".split(
    " ",
  );

/**
 * Format current UTC timestamp in canonical `"YYYY-MM-DD HH:MM:SS UTC"` tracker format.
 *
 * @param {number} epochMs - Timestamp in milliseconds.
 * @returns {string}
 */
function formatUtcNow(epochMs) {
  const now = new Date(epochMs);
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`;
}

/**
 * Generate a collision-free fallback issue identifier (`BUG-ADJ-NOUN-N` or `WORM-ADJ-NOUN-N`).
 *
 * @param {string} entityLabel - `"BUG"` or `"WORM"`.
 * @param {Array<object>} existingItems - Existing issues to avoid collisions with.
 * @returns {string}
 */
export function generateFallbackIssueId(entityLabel, existingItems = []) {
  const isWorm = String(entityLabel || "").toUpperCase() === "WORM";
  const prefix = isWorm ? "WORM" : "BUG";
  const adjs = isWorm ? WORM_ADJS : BUG_ADJS;
  const nouns = isWorm ? WORM_NOUNS : BUG_NOUNS;
  const adj = adjs[Math.floor(Math.random() * adjs.length)];
  const noun = nouns[Math.floor(Math.random() * nouns.length)];
  const num = Math.floor(Math.random() * 999) + 1;
  let candidate = `${prefix}-${adj}-${noun}-${num}`;
  let attempts = 0;
  const items = Array.isArray(existingItems) ? existingItems : [];
  while (items.some((item) => item && item.id === candidate) && attempts < 100) {
    attempts += 1;
    const nextNum = Math.floor(Math.random() * 999) + 1;
    candidate = `${prefix}-${adj}-${noun}-${nextNum}`;
  }
  return candidate;
}

/**
 * Normalize normalized boot config fields for either `bug` or `worm` mode.
 *
 * @param {object} rawConfig - Parsed `#app-boot-config`.
 * @returns {object}
 */
export function resolveTrackerConfig(rawConfig = {}) {
  const isWorm =
    rawConfig.entityKind === "worm" ||
    String(rawConfig.entityLabel || "").toUpperCase() === "WORM" ||
    rawConfig.collectionKey === "worms";
  const entityKind = isWorm ? "worm" : "bug";
  const entityLabel = rawConfig.entityLabel || (isWorm ? "WORM" : "BUG");
  const entityTitle = rawConfig.entityTitle || (isWorm ? "Worm" : "Bug");
  const collectionKey = rawConfig.collectionKey || (isWorm ? "worms" : "bugs");
  const fieldPrefix = rawConfig.fieldPrefix || entityKind;

  return {
    entityKind,
    entityLabel,
    entityTitle,
    collectionKey,
    fieldPrefix,
    apiBase: rawConfig.apiBase || (isWorm ? "/api/worms" : "/api/bugs"),
    databaseEndpoint:
      rawConfig.databaseEndpoint || (isWorm ? "/api/worms" : "/api/database"),
    nextIdEndpoint:
      rawConfig.nextIdEndpoint || (isWorm ? "/api/next_worm_id" : "/api/next_bug_id"),
    uploadEndpoint: rawConfig.uploadEndpoint || "/api/upload",
    syncEndpoint: rawConfig.syncEndpoint || "/api/sync_feedback",
    exitEndpoint: rawConfig.exitEndpoint || "/api/exit",
    versionEndpoint: rawConfig.versionEndpoint || "/api/version",
    defaultCategory: rawConfig.defaultCategory || (isWorm ? "FIRMWARE" : "PCB"),
    fileInputId: rawConfig.fileInputId || (isWorm ? "file-input" : "file-upload"),
    itemIcon: rawConfig.itemIcon !== undefined ? rawConfig.itemIcon : isWorm ? "🪱 " : "",
    entityIdParam: rawConfig.entityIdParam || (isWorm ? "worm_id" : "bug_id"),
    reviewFromParam: rawConfig.reviewFromParam || (isWorm ? "worms" : "bugs"),
    pollIntervalMs:
      rawConfig.pollIntervalMs !== undefined ? Number(rawConfig.pollIntervalMs) : 2000,
    initialDatabase: rawConfig.initialDatabase || null,
  };
}

/**
 * Initialize and bind the Issue Tracker Workstation application.
 *
 * @param {object} [ctx] - Explicit `RuntimeContext`.
 * @returns {object} Controller handle for testing and programmatic inspection.
 */
export function initTrackerApp(ctx = getRuntimeContext()) {
  const doc = ctx.getDocument();
  if (!doc) {
    return null;
  }

  applyIframeContextClass(ctx);
  initUiScaleControl(ctx, "uiScaleSelect");

  const bootConfig = ctx.getBootConfig("app-boot-config");
  const cfg = resolveTrackerConfig(bootConfig);
  const embeddedDb = ctx.getBootConfig("initial-tracker-db");
  const rawDb =
    cfg.initialDatabase && typeof cfg.initialDatabase === "object"
      ? cfg.initialDatabase
      : embeddedDb;

  const storage = ctx.getStorage();
  const statusStorageKey = `${cfg.fieldPrefix}_filter_status`;
  const categoryStorageKey = `${cfg.fieldPrefix}_filter_category`;
  const severityStorageKey = `${cfg.fieldPrefix}_filter_severity`;
  const sortStorageKey = `${cfg.fieldPrefix}_sort`;

  const extractCollection = (dbPayload) => {
    if (!dbPayload || typeof dbPayload !== "object") {
      return [];
    }
    if (Array.isArray(dbPayload[cfg.collectionKey])) {
      return dbPayload[cfg.collectionKey];
    }
    if (Array.isArray(dbPayload.bugs)) {
      return dbPayload.bugs;
    }
    if (Array.isArray(dbPayload.worms)) {
      return dbPayload.worms;
    }
    return [];
  };

  let items = extractCollection(rawDb).map((item) => ({ ...item }));
  const seenIds = new Set();
  for (const item of items) {
    if (seenIds.has(item.id)) {
      item.id = generateFallbackIssueId(cfg.entityLabel, items);
    }
    seenIds.add(item.id);
  }

  let activeId = null;
  let currentFilter = storage.getItem(statusStorageKey) || "open";
  let currentCategoryFilter = storage.getItem(categoryStorageKey) || "ALL";
  let currentSeverityFilter = storage.getItem(severityStorageKey) || "ALL";
  let currentSort = storage.getItem(sortStorageKey) || "id_desc";
  let lastKnownVersion = null;
  let isUserTyping = false;
  let pollTimerId = null;

  const elByField = (suffix) => doc.getElementById(`${cfg.fieldPrefix}-${suffix}`);

  const autoResizeTextarea = (ta, maxLimit = 500) => {
    if (!ta) return;
    if (typeof ta.closest === "function" && ta.closest(".form-section.expanded-vertical")) {
      return;
    }
    ta.style.height = "auto";
    const scrollH = Number(ta.scrollHeight || 0);
    const minH = ta.dataset?.minHeight ? Number.parseInt(ta.dataset.minHeight, 10) : 80;
    const targetHeight = Math.min(Math.max(scrollH, minH), maxLimit);
    ta.style.height = `${targetHeight}px`;
    ta.style.overflowY = scrollH > maxLimit ? "auto" : "hidden";
  };

  const autoResizeAllTextareas = () => {
    const contentArea = doc.querySelector(".content-area") || doc;
    const textareas = contentArea.querySelectorAll("textarea");
    for (const ta of textareas) {
      autoResizeTextarea(ta);
    }
  };

  const getVisibleIssues = () => {
    const searchInput = doc.getElementById("search-input");
    const query = searchInput ? searchInput.value || "" : "";
    return filterAndSortIssues(items, {
      statusFilter: currentFilter,
      categoryFilter: currentCategoryFilter,
      severityFilter: currentSeverityFilter,
      query,
      sortBy: currentSort,
    });
  };

  const updateMetrics = () => {
    const metrics = computeIssueMetrics(items);
    const totalEl = doc.getElementById("m-total");
    const openEl = doc.getElementById("m-open");
    const resolvedEl = doc.getElementById("m-resolved");
    if (totalEl) totalEl.textContent = String(metrics.total);
    if (openEl) openEl.textContent = String(metrics.open);
    if (resolvedEl) resolvedEl.textContent = String(metrics.resolved);
  };

  const updateComponentDatalist = () => {
    const datalist =
      elByField("component-list") || doc.getElementById("component-list");
    if (!datalist) return;
    clearChildren(datalist);
    for (const comp of extractUniqueComponents(items)) {
      const opt = createEl(ctx, "option", { attrs: { value: comp } });
      datalist.appendChild(opt);
    }
  };

  const renderAttachedCommits = (commitIds) => {
    const container = doc.getElementById("attached-commits-list");
    if (!container) return;
    clearChildren(container);
    const commits = Array.isArray(commitIds) ? commitIds : [];
    if (commits.length === 0) {
      container.appendChild(
        createEl(ctx, "span", {
          text: "No commits attached yet.",
          style: { fontSize: "10px", color: "var(--quake-text-dim)" },
        }),
      );
      return;
    }

    for (const cid of commits) {
      const sha = String(cid || "");
      const entityQuery = activeId
        ? `&${cfg.entityIdParam}=${encodeURIComponent(activeId)}`
        : "";
      const crUrl = `/review?revisions=${encodeURIComponent(sha)}&from=${cfg.reviewFromParam}${entityQuery}`;
      const chip = createEl(ctx, "div", {
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          background: "#1b120c",
          border: "1px solid var(--quake-gold)",
          borderRadius: "3px",
          padding: "4px 8px",
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
        },
        children: [
          createEl(ctx, "a", {
            text: `🔍 ${sha.slice(0, 10)}`,
            attrs: {
              href: crUrl,
              title: `Review commit ${sha.slice(0, 10)} in Code Review`,
            },
            dataset: { action: "open-commit-cr", commit: sha },
            style: {
              color: "var(--quake-gold)",
              textDecoration: "none",
              fontWeight: "700",
              cursor: "pointer",
            },
          }),
          createEl(ctx, "button", {
            className: "copy-icon-btn copy-badge-btn",
            text: "📋",
            attrs: { type: "button", title: "Copy commit SHA" },
            dataset: { action: "copy-commit-sha", commit: sha },
          }),
        ],
      });
      container.appendChild(chip);
    }
  };

  const resetMarkdownPreviewsToEdit = () => {
    const previewBtns = doc.querySelectorAll('[data-action="toggle-md-preview"]');
    for (const btn of previewBtns) {
      const previewId = btn.dataset?.targetPreview || "";
      const textareaId = btn.dataset?.targetTextarea || "";
      const previewEl = previewId ? doc.getElementById(previewId) : null;
      const textareaEl = textareaId ? doc.getElementById(textareaId) : null;
      if (previewEl && previewEl.style.display !== "none") {
        previewEl.style.display = "none";
        if (textareaEl) textareaEl.style.display = "";
        btn.textContent = "👁 Preview";
        btn.classList.remove("quake-btn-gold");
        btn.classList.add("quake-btn-default");
      }
    }
  };

  const loadActiveIssue = () => {
    const issue = items.find((it) => it.id === activeId);
    if (!issue) {
      return;
    }
    resetMarkdownPreviewsToEdit();

    const idDisp = elByField("id-display") || doc.getElementById(`active-${cfg.fieldPrefix}-id-display`);
    const activeDisp = doc.getElementById(`active-${cfg.fieldPrefix}-id-display`) || idDisp;
    const copyActiveBtn = doc.getElementById(`btn-copy-active-${cfg.fieldPrefix}`);
    if (activeDisp) activeDisp.textContent = `[${issue.id}]`;
    if (copyActiveBtn) copyActiveBtn.style.display = "inline-flex";

    const reviewBanner = doc.getElementById("review-action-banner");
    if (reviewBanner) {
      reviewBanner.style.display = issue.status === "RESOLVED" ? "block" : "none";
    }

    const rejCard = doc.getElementById("rejection-feedback-card");
    const rejText = doc.getElementById("rejection-feedback-text");
    if (rejCard && rejText) {
      if (issue.rejection_notes && String(issue.rejection_notes).trim()) {
        rejCard.style.display = "block";
        const rejTime = issue.rejected_at ? `[${issue.rejected_at}]\n` : "";
        rejText.textContent = `${rejTime}${issue.rejection_notes}`;
      } else {
        rejCard.style.display = "none";
      }
    }

    const accCard = doc.getElementById("accepted-feedback-card");
    const accTime = doc.getElementById("accepted-timestamp-display");
    if (accCard) {
      if (issue.status === "CLOSED") {
        accCard.style.display = "block";
        if (accTime) {
          accTime.textContent = issue.accepted_at ? `ACCEPTED ${issue.accepted_at}` : "CLOSED";
        }
      } else {
        accCard.style.display = "none";
      }
    }

    const setFieldVal = (suffix, val) => {
      const el = elByField(suffix);
      if (el) el.value = val;
    };
    setFieldVal("title", issue.title || "");
    setFieldVal("severity", issue.severity || "MEDIUM");
    setFieldVal("status", issue.status || "OPEN");
    setFieldVal("category", issue.category || cfg.defaultCategory);
    setFieldVal("component", issue.component || "");
    setFieldVal("description", issue.description || "");
    setFieldVal(
      "steps",
      Array.isArray(issue.reproduction_steps) ? issue.reproduction_steps.join("\n") : "",
    );
    setFieldVal("expected", issue.expected_behavior || "");
    setFieldVal("actual", issue.actual_behavior || "");
    setFieldVal("logs", issue.logs || "");
    setFieldVal("resolution", issue.resolution_notes || "");

    renderAttachmentsGrid(ctx, "attachments-grid", issue.attachments || [], (removeIdx) => {
      const cur = items.find((it) => it.id === activeId);
      if (cur && Array.isArray(cur.attachments)) {
        cur.attachments.splice(removeIdx, 1);
        renderAttachmentsGrid(ctx, "attachments-grid", cur.attachments);
        void saveActiveIssue();
      }
    });
    renderAttachedCommits(issue.commit_ids || []);
    renderReviewTasksList(ctx, "review-tasks-list", issue.review_tasks || []);
    autoResizeAllTextareas();
  };

  const renderIssueList = () => {
    const listEl = elByField("list");
    if (!listEl) return;
    clearChildren(listEl);
    const visible = getVisibleIssues();
    const itemClassBase =
      cfg.entityKind === "worm" ? "worm-item bug-item" : "bug-item";
    const topClass =
      cfg.entityKind === "worm" ? "worm-item-top bug-item-top" : "bug-item-top";
    const idClass = cfg.entityKind === "worm" ? "worm-id bug-id" : "bug-id";
    const titleClass =
      cfg.entityKind === "worm" ? "worm-item-title bug-item-title" : "bug-item-title";

    for (const issue of visible) {
      const sevClass = getSeverityBadgeClass(issue.severity);
      const stInfo = getStatusBadgeInfo(issue.status);
      const idSpan = createEl(ctx, "span", {
        className: idClass,
        children: [
          createEl(ctx, "span", { text: `${cfg.itemIcon}${issue.id} ` }),
          createEl(ctx, "button", {
            className: "copy-icon-btn copy-badge-btn",
            text: "📋",
            attrs: {
              type: "button",
              title: `Copy ${cfg.entityTitle} ID ${issue.id}`,
            },
            dataset: { action: "copy-issue-id", issueId: issue.id },
          }),
        ],
      });
      const li = createEl(ctx, "li", {
        className: `${itemClassBase}${issue.id === activeId ? " active" : ""}`,
        dataset: { action: "select-issue", issueId: issue.id },
        children: [
          createEl(ctx, "div", {
            className: topClass,
            children: [
              idSpan,
              createEl(ctx, "span", {
                className: sevClass,
                text: issue.severity || "MEDIUM",
              }),
              createEl(ctx, "span", {
                className: stInfo.badgeClass,
                text: stInfo.label,
              }),
            ],
          }),
          createEl(ctx, "div", {
            className: titleClass,
            text: issue.title || `Untitled ${cfg.entityTitle}`,
          }),
        ],
      });
      listEl.appendChild(li);
    }
  };

  const selectIssue = (id) => {
    activeId = id;
    renderIssueList();
    loadActiveIssue();
  };

  const ensureActiveVisible = () => {
    const visible = getVisibleIssues();
    if (visible.length > 0 && !visible.some((it) => it.id === activeId)) {
      selectIssue(visible[0].id);
    }
  };

  const setStatusFilter = (filterValue) => {
    currentFilter = filterValue;
    storage.setItem(statusStorageKey, filterValue);
    const pills = ["open", "planned", "all", "resolved"];
    for (const name of pills) {
      const btn = doc.getElementById(`filter-${name}`);
      if (btn) {
        btn.classList.toggle("quake-btn-active", filterValue === name);
      }
    }
    renderIssueList();
    ensureActiveVisible();
  };

  const fetchNextIssueId = async () => {
    let fallback = generateFallbackIssueId(cfg.entityLabel, items);
    try {
      const data = await ctx.fetchJson(cfg.nextIdEndpoint);
      if (data && data.next_id && !items.some((it) => it.id === data.next_id)) {
        fallback = data.next_id;
      }
    } catch {
      // Offline/headless fallback ID already prepared
    }
    return fallback;
  };

  const readFormFields = () => {
    const valOf = (suffix, fallback = "") => {
      const el = elByField(suffix);
      return el && typeof el.value === "string" ? el.value : fallback;
    };
    return {
      title: valOf("title").trim(),
      severity: valOf("severity", "MEDIUM"),
      status: valOf("status", "OPEN"),
      category: valOf("category", cfg.defaultCategory),
      component: valOf("component").trim(),
      description: valOf("description"),
      reproduction_steps: valOf("steps")
        .split("\n")
        .filter((s) => s.trim()),
      expected_behavior: valOf("expected"),
      actual_behavior: valOf("actual"),
      logs: valOf("logs"),
      resolution_notes: valOf("resolution"),
    };
  };

  const saveActiveIssue = async () => {
    let issue = items.find((it) => it.id === activeId);
    const fields = readFormFields();

    return performActionWithProgress(
      ctx,
      async () => {
        if (!issue) {
          const newId = await fetchNextIssueId();
          issue = {
            id: newId,
            title: fields.title || `New ${cfg.entityTitle} Report`,
            status: fields.status || "OPEN",
            severity: fields.severity || "MEDIUM",
            category: fields.category || cfg.defaultCategory,
            component: fields.component,
            description: fields.description,
            reproduction_steps: fields.reproduction_steps,
            expected_behavior: fields.expected_behavior,
            actual_behavior: fields.actual_behavior,
            logs: fields.logs,
            attachments: [],
            created_at: formatUtcNow(ctx.nowMs()),
            resolution_notes: fields.resolution_notes,
          };
          items.unshift(issue);
          activeId = newId;
        } else {
          issue.title = fields.title || `Untitled ${cfg.entityTitle}`;
          issue.severity = fields.severity;
          issue.status = fields.status;
          issue.category = fields.category;
          issue.component = fields.component;
          issue.description = fields.description;
          issue.reproduction_steps = fields.reproduction_steps;
          issue.expected_behavior = fields.expected_behavior;
          issue.actual_behavior = fields.actual_behavior;
          issue.logs = fields.logs;
          issue.resolution_notes = fields.resolution_notes;
        }

        const saved = await ctx.postJson(cfg.apiBase, issue);
        if (saved && saved.id) {
          Object.assign(issue, saved);
          activeId = saved.id;
        }
        updateMetrics();
        renderIssueList();
        updateComponentDatalist();
        loadActiveIssue();
        showToast(ctx, `Saved ${cfg.entityKind} ${ (saved && saved.id) || issue.id }`, "success");
        return saved;
      },
      {
        title: `SAVING ${cfg.entityLabel} REPORT`,
        description: `Persisting ${cfg.entityKind} ${activeId || "record"} changes...`,
        stepText: `Saving ${activeId || cfg.entityKind}...`,
        icon: "💾",
      },
    );
  };

  const createNewIssue = async (prefillCommit = "") => {
    const newId = await fetchNextIssueId();
    const issue = {
      id: newId,
      title: `New ${cfg.entityTitle} Report`,
      status: "OPEN",
      severity: "MEDIUM",
      category: cfg.defaultCategory,
      component: "",
      description: prefillCommit ? `Affects commit: ${prefillCommit}\n\n` : "",
      reproduction_steps: [],
      expected_behavior: "",
      actual_behavior: "",
      logs: "",
      attachments: [],
      created_at: formatUtcNow(ctx.nowMs()),
      resolution_notes: "",
    };
    items.unshift(issue);
    activeId = newId;
    updateMetrics();
    renderIssueList();
    loadActiveIssue();
    return saveActiveIssue();
  };

  const deleteActiveIssue = async () => {
    if (!activeId) return;
    const confirmed = await showConfirmModal(ctx, {
      title: `DELETE ${cfg.entityLabel} REPORT`,
      message: `Are you sure you want to delete ${activeId}?`,
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      danger: true,
      defaultWhenHeadless: true,
    });
    if (!confirmed) return;

    const targetId = activeId;
    await performActionWithProgress(
      ctx,
      async () => {
        await ctx.postJson(`${cfg.apiBase}/delete`, { id: targetId });
        items = items.filter((it) => it.id !== targetId);
        activeId = items.length > 0 ? items[0].id : null;
        updateMetrics();
        renderIssueList();
        updateComponentDatalist();
        loadActiveIssue();
        showToast(ctx, `Deleted ${cfg.entityKind}`, "info");
      },
      {
        title: `DELETING ${cfg.entityLabel} REPORT`,
        description: `Deleting ${targetId}...`,
        stepText: `Deleting ${targetId}...`,
        icon: "🗑️",
      },
    );
  };

  const acceptActiveIssue = async () => {
    if (!activeId) return;
    await performActionWithProgress(
      ctx,
      async () => {
        try {
          await saveActiveIssue();
          const data = await ctx.postJson(`${cfg.apiBase}/accept`, {
            id: activeId,
            notes: "",
          });
          const updatedRecord = data[cfg.entityKind] || data.bug || data.worm || {};
          if (data.status === "ok") {
            const issue = items.find((it) => it.id === activeId);
            if (issue) {
              issue.status = "CLOSED";
              issue.accepted_at = updatedRecord.accepted_at;
              if (updatedRecord.resolution_notes) {
                issue.resolution_notes = updatedRecord.resolution_notes;
              }
            }
            loadActiveIssue();
            renderIssueList();
            updateMetrics();
            showToast(ctx, `${cfg.entityTitle} [${activeId}] accepted and closed.`, "success");
          } else {
            showToast(ctx, data.error || `Failed to accept ${cfg.entityKind}`, "error");
          }
        } catch (err) {
          showToast(
            ctx,
            `Error accepting ${cfg.entityKind}: ${(err && err.message) || err}`,
            "error",
          );
        }
      },
      {
        title: `ACCEPTING ${cfg.entityLabel} REPORT`,
        description: `Marking ${cfg.entityKind} ${activeId} as verified / closed...`,
        stepText: `Accepting ${activeId}...`,
        icon: "✓",
      },
    );
  };

  const rejectActiveIssue = async () => {
    if (!activeId) return;
    await performActionWithProgress(
      ctx,
      async () => {
        try {
          const resEl = elByField("resolution");
          const currentNotes = resEl ? String(resEl.value || "").trim() : "";
          await saveActiveIssue();
          const data = await ctx.postJson(`${cfg.apiBase}/reject`, {
            id: activeId,
            notes: currentNotes,
          });
          const updatedRecord = data[cfg.entityKind] || data.bug || data.worm || {};
          if (data.status === "ok") {
            const issue = items.find((it) => it.id === activeId);
            if (issue) {
              issue.status = "OPEN";
              issue.rejected_at = updatedRecord.rejected_at;
              issue.rejection_notes = updatedRecord.rejection_notes;
            }
            loadActiveIssue();
            renderIssueList();
            updateMetrics();
            showToast(
              ctx,
              `${cfg.entityTitle} [${activeId}] rejected and reopened.`,
              "info",
            );
          } else {
            showToast(ctx, data.error || `Failed to reject ${cfg.entityKind}`, "error");
          }
        } catch (err) {
          showToast(
            ctx,
            `Error rejecting ${cfg.entityKind}: ${(err && err.message) || err}`,
            "error",
          );
        }
      },
      {
        title: `REJECTING ${cfg.entityLabel} REPORT`,
        description: `Reopening ${cfg.entityKind} ${activeId} and saving review notes...`,
        stepText: `Rejecting ${activeId}...`,
        icon: "✕",
      },
    );
  };

  const attachCommitToActive = async () => {
    if (!activeId) return;
    const input = doc.getElementById("input-attach-commit");
    const commitSha = input ? String(input.value || "").trim() : "";
    if (!commitSha) {
      showToast(ctx, "Please enter a commit SHA", "error");
      return;
    }
    await performActionWithProgress(
      ctx,
      async () => {
        try {
          const data = await ctx.postJson(`${cfg.apiBase}/attach_commit`, {
            id: activeId,
            commit_id: commitSha,
          });
          const updatedRecord = data[cfg.entityKind] || data.bug || data.worm || {};
          if (data.status === "ok") {
            const issue = items.find((it) => it.id === activeId);
            if (issue) {
              issue.commit_ids = updatedRecord.commit_ids || [];
              renderAttachedCommits(issue.commit_ids);
            }
            if (input) input.value = "";
            showToast(ctx, `Attached commit ${commitSha}`, "success");
          } else {
            showToast(ctx, data.error || "Failed to attach commit", "error");
          }
        } catch (err) {
          showToast(ctx, `Error attaching commit: ${(err && err.message) || err}`, "error");
        }
      },
      {
        title: "ATTACHING COMMIT",
        description: `Linking commit ${commitSha} to ${activeId}...`,
        stepText: `Updating ${cfg.entityKind} commit linkages...`,
        icon: "🔗",
      },
    );
  };

  const openCommitInCodeReview = async (commitHash) => {
    if (!commitHash) return;
    const entityQuery = activeId
      ? `&${cfg.entityIdParam}=${encodeURIComponent(activeId)}`
      : "";
    const targetUrl = `/review?revisions=${encodeURIComponent(commitHash)}&from=${cfg.reviewFromParam}${entityQuery}`;

    try {
      await ctx.postJson("/api/open_code_review", { commits: [commitHash] });
    } catch {
      // Optional background session pre-warm
    }

    if (ctx.isEmbeddedInFrame()) {
      ctx.postParentMessage({
        action: "open_workstation",
        type: "open_workstation",
        url: targetUrl,
      });
    } else {
      ctx.navigate(targetUrl);
    }
  };

  const addTaskToActive = async () => {
    if (!activeId) return;
    const titleInput = doc.getElementById("input-task-title");
    const cmdInput = doc.getElementById("input-task-command");
    const title = titleInput ? String(titleInput.value || "").trim() : "";
    const cmd = cmdInput ? String(cmdInput.value || "").trim() : "";
    if (!title) {
      showToast(ctx, "Task title is required", "error");
      return;
    }
    try {
      const data = await addReviewTask(ctx, cfg.apiBase, activeId, title, cmd);
      const updatedRecord = data[cfg.entityKind] || data.bug || data.worm || {};
      if (data.status === "ok") {
        const issue = items.find((it) => it.id === activeId);
        if (issue) {
          issue.review_tasks = updatedRecord.review_tasks || [];
          renderReviewTasksList(ctx, "review-tasks-list", issue.review_tasks);
        }
        if (titleInput) titleInput.value = "";
        if (cmdInput) cmdInput.value = "";
        showToast(ctx, "Task added.", "success");
      } else {
        showToast(ctx, data.error || "Failed to add task", "error");
      }
    } catch (err) {
      showToast(ctx, `Error adding task: ${(err && err.message) || err}`, "error");
    }
  };

  const handleUploadPayload = async (payload) => {
    await performActionWithProgress(
      ctx,
      async () => {
        showToast(ctx, `Uploading ${payload.filename}...`, "info");
        const res = await ctx.fetchRaw(cfg.uploadEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.status === 413) {
          let errMsg = "Attachment exceeds maximum allowed size of 2 GB (GitHub LFS limit).";
          try {
            const errData = await res.json();
            if (errData && errData.error) errMsg = errData.error;
          } catch {
            // Keep default message
          }
          showToast(ctx, errMsg, "error", 5000);
          return;
        }
        if (!res.ok) {
          showToast(ctx, `Failed to upload attachment: HTTP ${res.status}`, "error");
          return;
        }
        const att = await res.json();
        const issue = items.find((it) => it.id === activeId);
        if (issue) {
          if (!Array.isArray(issue.attachments)) {
            issue.attachments = [];
          }
          issue.attachments.push(att);
          renderAttachmentsGrid(ctx, "attachments-grid", issue.attachments);
          await saveActiveIssue();
          showToast(ctx, `Attached ${att.filename}`, "success");
        }
      },
      {
        title: "UPLOADING ATTACHMENT",
        description: `Uploading ${payload.filename || "file"} and saving to repository...`,
        stepText: "Uploading file data...",
        icon: "📎",
      },
    );
  };

  const syncFeedback = async () => {
    await performActionWithProgress(
      ctx,
      async () => {
        try {
          const data = await ctx.postJson(cfg.syncEndpoint, {});
          if (data && data.status === "ok") {
            const stats = data.stats || {};
            showToast(
              ctx,
              `Feedback synced: ${stats.total || 0} total ${cfg.collectionKey}.`,
              "success",
            );
            const dbPayload = await ctx.fetchJson(cfg.databaseEndpoint);
            items = extractCollection(dbPayload).map((it) => ({ ...it }));
            updateMetrics();
            renderIssueList();
            updateComponentDatalist();
            loadActiveIssue();
          } else {
            showToast(
              ctx,
              `Sync failed: ${(data && data.message) || "Unknown error"}`,
              "error",
            );
          }
        } catch (err) {
          showToast(
            ctx,
            `Error syncing feedback: ${(err && err.message) || err}`,
            "error",
          );
        }
      },
      {
        title: "MERGING AGENT FEEDBACK",
        description:
          "Merging stored agent feedback from feedback/ directory into SQLite database...",
        stepText: `Scanning feedback/ directory for ${cfg.entityLabel}_*.md files...`,
        icon: "🔄",
      },
    );
  };

  const closeWorkstation = () => {
    ctx.postParentMessage({ action: "close_workstation", type: "close_modal" });
    if (!ctx.isEmbeddedInFrame()) {
      ctx.navigate("/");
    }
  };

  const saveAndExit = async () => {
    const btn = doc.getElementById("btn-save-exit");
    if (btn) {
      btn.textContent = "⏳ Saving...";
      btn.disabled = true;
    }
    try {
      await saveActiveIssue();
      await ctx.postJson(cfg.exitEndpoint, {});
      showToast(ctx, `${cfg.entityTitle} state saved. Returning to Dashboard...`, "success");
    } catch {
      showToast(ctx, "Saved state. Returning to Dashboard...", "info");
    }
    ctx.setTimeout(() => {
      closeWorkstation();
    }, 500);
  };

  const toggleExpandPanel = (btn) => {
    const section = typeof btn.closest === "function" ? btn.closest(".form-section") : null;
    if (!section) return;
    const isExpanded = section.classList.toggle("expanded-vertical");
    btn.textContent = isExpanded ? "⤡ Compact" : "⤢ Expand";
    btn.classList.toggle("quake-btn-gold", isExpanded);
    btn.classList.toggle("quake-btn-default", !isExpanded);
    if (!isExpanded) {
      const textareas = section.querySelectorAll("textarea");
      for (const ta of textareas) {
        autoResizeTextarea(ta);
      }
    }
  };

  const pollForExternalUpdates = async () => {
    try {
      const data = await ctx.fetchJson(cfg.versionEndpoint);
      if (!data) return;
      if (lastKnownVersion === null) {
        lastKnownVersion = data.version;
        return;
      }
      if (data.version !== lastKnownVersion) {
        lastKnownVersion = data.version;
        const dbPayload = await ctx.fetchJson(cfg.databaseEndpoint);
        items = extractCollection(dbPayload).map((it) => ({ ...it }));
        updateMetrics();
        renderIssueList();
        updateComponentDatalist();
        if (!isUserTyping && activeId) {
          loadActiveIssue();
        } else if (activeId) {
          const cur = items.find((it) => it.id === activeId);
          const statusSel = elByField("status");
          if (cur && statusSel && statusSel.value !== cur.status) {
            statusSel.value = cur.status;
          }
        }
      }
    } catch {
      // Ignore transient background polling glitches
    }
  };

  // Restore dropdown selections
  const sortSel = doc.getElementById(`select-${cfg.fieldPrefix}-sort`);
  if (sortSel) {
    sortSel.value = currentSort;
    sortSel.addEventListener("change", () => {
      currentSort = sortSel.value;
      storage.setItem(sortStorageKey, currentSort);
      renderIssueList();
    });
  }
  const catSel = doc.getElementById("select-filter-category");
  if (catSel) {
    catSel.value = currentCategoryFilter;
    catSel.addEventListener("change", () => {
      currentCategoryFilter = catSel.value;
      storage.setItem(categoryStorageKey, currentCategoryFilter);
      renderIssueList();
      ensureActiveVisible();
    });
  }
  const sevSel = doc.getElementById("select-filter-severity");
  if (sevSel) {
    sevSel.value = currentSeverityFilter;
    sevSel.addEventListener("change", () => {
      currentSeverityFilter = sevSel.value;
      storage.setItem(severityStorageKey, currentSeverityFilter);
      renderIssueList();
      ensureActiveVisible();
    });
  }
  const searchInput = doc.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      renderIssueList();
    });
  }

  // Initial active issue selection + URL hash deep-linking
  const initialVisible = getVisibleIssues();
  if (initialVisible.length > 0) {
    activeId = initialVisible[0].id;
  } else if (items.length > 0) {
    activeId = items[0].id;
  }

  const rawHash = String(ctx.getLocation().hash || "").replace(/^#/, "");
  let pendingNewCommitHash = "";
  if (rawHash) {
    if (rawHash.startsWith("new")) {
      const matchCommit = rawHash.match(/commit=([a-f0-9]+)/i);
      pendingNewCommitHash = matchCommit ? matchCommit[1] : "__NEW__";
    } else {
      const normalizedId = rawHash.startsWith(`${cfg.entityLabel}-`)
        ? rawHash
        : rawHash.startsWith("BUG-") && cfg.entityLabel === "WORM"
          ? rawHash.replace(/^BUG-/, "WORM-")
          : rawHash.startsWith("WORM-") && cfg.entityLabel === "BUG"
            ? rawHash.replace(/^WORM-/, "BUG-")
            : `${cfg.entityLabel}-${rawHash}`;
      const matched = items.find((it) => it.id === normalizedId || it.id === rawHash);
      if (matched) {
        activeId = matched.id;
        if (
          (matched.status === "CLOSED" && currentFilter === "open") ||
          (matched.status === "PLANNED" && currentFilter === "open")
        ) {
          currentFilter = "all";
        }
      }
    }
  }

  // Bind delegated UI actions on document
  bindDelegatedEvent(doc, "click", "[data-action]", (ev, actionEl) => {
    const action = actionEl.dataset?.action || "";
    switch (action) {
      case "sync-feedback":
        void syncFeedback();
        break;
      case "new-issue":
        void createNewIssue();
        break;
      case "save-exit":
        void saveAndExit();
        break;
      case "close-workstation":
        ev.preventDefault();
        closeWorkstation();
        break;
      case "set-filter":
        if (actionEl.dataset?.filter) {
          setStatusFilter(actionEl.dataset.filter);
        }
        break;
      case "select-issue":
        if (actionEl.dataset?.issueId) {
          selectIssue(actionEl.dataset.issueId);
        }
        break;
      case "copy-issue-id":
        ev.stopPropagation();
        if (actionEl.dataset?.issueId) {
          void copyToClipboard(
            ctx,
            actionEl.dataset.issueId,
            `Copied: ${actionEl.dataset.issueId}`,
          );
        }
        break;
      case "copy-active-id":
        if (activeId) {
          void copyToClipboard(ctx, activeId, `Copied: ${activeId}`);
        }
        break;
      case "save-issue":
        void saveActiveIssue();
        break;
      case "delete-issue":
        void deleteActiveIssue();
        break;
      case "accept-issue":
        void acceptActiveIssue();
        break;
      case "reject-issue":
        void rejectActiveIssue();
        break;
      case "attach-commit":
        void attachCommitToActive();
        break;
      case "open-commit-cr": {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey) {
          return;
        }
        ev.preventDefault();
        const sha = actionEl.dataset?.commit || "";
        void openCommitInCodeReview(sha);
        break;
      }
      case "copy-commit-sha":
        if (actionEl.dataset?.commit) {
          void copyToClipboard(
            ctx,
            actionEl.dataset.commit,
            `Copied: ${actionEl.dataset.commit}`,
          );
        }
        break;
      case "add-review-task":
        void addTaskToActive();
        break;
      case "toggle-expand-panel":
        toggleExpandPanel(actionEl);
        break;
      case "toggle-md-preview":
        toggleMarkdownPreviewForButton(ctx, actionEl);
        break;
      default:
        break;
    }
  });

  // Bind review tasks delegation
  bindReviewTasksEvents(ctx, "review-tasks-list", {
    onToggleTask: async (taskId, curStatus) => {
      if (!activeId) return;
      try {
        const data = await toggleReviewTaskStatus(
          ctx,
          cfg.apiBase,
          activeId,
          taskId,
          curStatus,
        );
        const updatedRecord = data[cfg.entityKind] || data.bug || data.worm || {};
        if (data && data.status === "ok") {
          const issue = items.find((it) => it.id === activeId);
          if (issue) {
            issue.review_tasks = updatedRecord.review_tasks || [];
            renderReviewTasksList(ctx, "review-tasks-list", issue.review_tasks);
          }
        }
      } catch (err) {
        showToast(ctx, `Error updating task: ${(err && err.message) || err}`, "error");
      }
    },
    onRunCommand: (taskId, command) => {
      if (!activeId) return;
      void runReviewTaskCommand(ctx, cfg.apiBase, activeId, taskId, command);
    },
  });

  // Bind attachments dropzone & paste
  bindAttachmentDropzone(ctx, {
    dropzoneId: "dropzone",
    fileInputId: cfg.fileInputId,
    getActiveId: () => activeId,
    entityIdParam: cfg.entityIdParam,
    onUploadPayload: handleUploadPayload,
  });

  // Textarea auto-resize and typing guard
  doc.addEventListener("input", (ev) => {
    if (String(ev.target?.tagName || "").toUpperCase() === "TEXTAREA") {
      autoResizeTextarea(ev.target);
    }
  });
  doc.addEventListener("focusin", (ev) => {
    const tag = String(ev.target?.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "INPUT") {
      isUserTyping = true;
    }
  });
  doc.addEventListener("focusout", (ev) => {
    const tag = String(ev.target?.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "INPUT") {
      isUserTyping = false;
    }
  });

  // Escape key closes workstation when no loading modal is open
  ctx.addViewportListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      const loadingModal = doc.getElementById("feedback-loading-modal");
      const progressModal = doc.getElementById("actionProgressModalOverlay");
      const loadingOpen = loadingModal && loadingModal.style.display !== "none";
      const progressOpen = progressModal && progressModal.style.display !== "none";
      if (!loadingOpen && !progressOpen) {
        closeWorkstation();
      }
    }
  });

  updateMetrics();
  updateComponentDatalist();
  setStatusFilter(currentFilter);
  loadActiveIssue();
  autoResizeAllTextareas();

  if (pendingNewCommitHash) {
    const commitArg = pendingNewCommitHash === "__NEW__" ? "" : pendingNewCommitHash;
    void createNewIssue(commitArg);
  }

  if (cfg.pollIntervalMs > 0) {
    pollTimerId = ctx.setInterval(() => {
      void pollForExternalUpdates();
    }, cfg.pollIntervalMs);
  }

  return {
    cfg,
    getItems: () => items,
    getActiveId: () => activeId,
    selectIssue,
    setStatusFilter,
    createNewIssue,
    saveActiveIssue,
    deleteActiveIssue,
    acceptActiveIssue,
    rejectActiveIssue,
    attachCommitToActive,
    addTaskToActive,
    syncFeedback,
    pollForExternalUpdates,
    destroy: () => {
      if (pollTimerId !== null) {
        ctx.clearInterval(pollTimerId);
        pollTimerId = null;
      }
    },
  };
}

// Auto-boot when loaded as browser `<script type="module">`
const defaultCtx = getRuntimeContext();
const bootDoc = defaultCtx.getDocument();
if (bootDoc && !bootDoc.documentElement?.dataset?.skipAutoBoot) {
  if (bootDoc.readyState === "loading") {
    bootDoc.addEventListener("DOMContentLoaded", () => {
      initTrackerApp(defaultCtx);
    });
  } else {
    initTrackerApp(defaultCtx);
  }
}
