/**
 * Forge / Xerxes Shared Frontend Library (common.js)
 *
 * Provides shared client-side components and utilities across all dashboard and
 * workstation views (diff_view, worm_report, bug_report, code_review):
 * - AsymptoticProgressBar: Smooth 50ms interval progress bar controller with
 *   multi-phase easing, dynamic stage-specific text, elapsed time tracking,
 *   and completion/failure transitions.
 * - Modal & Action Progress: Reusable performAction runner and modal controllers.
 * - Panel Resizing: Draggable split-pane layout managers with localStorage persistence.
 * - Author Sanitization: Client-side privacy redaction for authors and committer emails.
 * - DOM & Clipboard Utilities: escapeHtml, copyToClipboard, toast notifications, UI scale.
 */

(function (global) {
  "use strict";

  // =========================================================================
  // 1. Author & Personal Identifier Sanitization
  // =========================================================================
  const RESERVED_IDENTIFIERS = new Set([
    "user", "system", "anonymous", "root", "bot", "author", "committer",
    "reviewer", "admin", "null", "undefined", "workspace", "nobody"
  ]);

  function sanitizeAuthor(str) {
    if (!str || typeof str !== "string") return "User";
    const trimmed = str.trim();
    if (!trimmed) return "User";

    // If it looks like "Name <email@domain>"
    const emailMatch = trimmed.match(/^(.*?)\s*<([^>]+)>$/);
    if (emailMatch) {
      return "User <user@workspace>";
    }

    // Direct email
    if (trimmed.includes("@")) {
      return "user@workspace";
    }

    // Known placeholder or generic name
    if (RESERVED_IDENTIFIERS.has(trimmed.toLowerCase())) {
      return trimmed;
    }

    // Sanitize any individual person's name or handle to "User"
    return "User";
  }

  // =========================================================================
  // 2. DOM, HTML & Utility Helpers
  // =========================================================================
  function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function resolveElement(elOrId) {
    if (!elOrId) return null;
    if (typeof elOrId === "string") {
      return typeof document !== "undefined" ? document.getElementById(elOrId) : null;
    }
    return elOrId;
  }

  function copyToClipboard(text, successToastMsg) {
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(successToastMsg || "Copied to clipboard!", "success");
      }).catch(() => {
        fallbackCopyText(text, successToastMsg);
      });
    } else {
      fallbackCopyText(text, successToastMsg);
    }
  }

  function fallbackCopyText(text, successToastMsg) {
    if (typeof document === "undefined") return;
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
      showToast(successToastMsg || "Copied to clipboard!", "success");
    } catch (err) {
      showToast("Failed to copy to clipboard", "error");
    } finally {
      textArea.remove();
    }
  }

  function showToast(message, type = "info", durationMs = 3000) {
    if (typeof document === "undefined") return;
    let container = document.getElementById("forge-toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "forge-toast-container";
      container.style.cssText =
        "position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `forge-toast forge-toast-${type}`;
    let borderCol = "#00e5ff";
    let bgCol = "rgba(10, 28, 36, 0.95)";
    if (type === "success") borderCol = "#00ff66";
    if (type === "error") borderCol = "#ff3333";
    if (type === "warning") borderCol = "#ffaa00";

    toast.style.cssText = `background:${bgCol};border:1px solid ${borderCol};color:#fff;padding:8px 14px;border-radius:3px;font-family:monospace;font-size:12px;box-shadow:0 4px 12px rgba(0,0,0,0.5);pointer-events:auto;transition:opacity 0.2s ease;opacity:0;`;
    toast.textContent = message;
    container.appendChild(toast);

    if (typeof requestAnimationFrame !== "undefined") {
      requestAnimationFrame(() => {
        toast.style.opacity = "1";
      });
    } else {
      toast.style.opacity = "1";
    }

    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 250);
    }, durationMs);
  }

  function showModal(modalElOrId, display = "flex") {
    const el = resolveElement(modalElOrId);
    if (el) {
      el.style.display = display;
    }
  }

  function hideModal(modalElOrId) {
    const el = resolveElement(modalElOrId);
    if (el) {
      el.style.display = "none";
    }
  }

  // =========================================================================
  // 3. Continuous Asymptotic Progress Bar Controller
  // =========================================================================
  class AsymptoticProgressBar {
    constructor(options = {}) {
      this.progressBar = resolveElement(options.progressBar || options.barEl);
      this.percentEl = resolveElement(options.percentEl);
      this.statusEl = resolveElement(options.statusEl || options.statusTextEl);
      this.elapsedEl = resolveElement(options.elapsedEl);
      this.initialProgress = options.initialProgress !== undefined ? options.initialProgress : 12;
      this.maxProgress = options.maxProgress !== undefined ? options.maxProgress : 95;
      this.intervalMs = options.intervalMs || 50;
      this.stages = options.stages || [];
      this.getStageMessage = options.getStageMessage || null;
      this.customTick = options.onTick || null;

      this.progress = this.initialProgress;
      this.startTime = null;
      this.timer = null;
      this.isRunning = false;
    }

    start() {
      this.stop();
      this.isRunning = true;
      this.startTime = Date.now();
      this.progress = this.initialProgress;
      this.updateDom(this.progress, 0.0);

      this.timer = setInterval(() => this.tick(), this.intervalMs);
      this.tick();
      return this;
    }

    tick() {
      if (!this.isRunning) return;
      const elapsedSec = (Date.now() - this.startTime) / 1000;

      // Continuous multi-stage acceleration with asymptotic deceleration approaching maxProgress
      if (this.progress < this.maxProgress) {
        if (elapsedSec < 0.6) {
          this.progress = this.initialProgress + (elapsedSec / 0.6) * 23;
        } else if (elapsedSec < 2.0) {
          this.progress = 35 + ((elapsedSec - 0.6) / 1.4) * 30;
        } else if (elapsedSec < 4.5) {
          this.progress = 65 + ((elapsedSec - 2.0) / 2.5) * 22;
        } else {
          this.progress += (this.maxProgress + 1 - this.progress) * 0.015;
        }
      }

      const clampedPct = Math.min(this.maxProgress, Math.floor(this.progress));
      this.updateDom(clampedPct, elapsedSec);

      if (this.customTick) {
        this.customTick(clampedPct, elapsedSec);
      }
    }

    resolveStageMessage(pct, elapsedSec) {
      if (typeof this.getStageMessage === "function") {
        return this.getStageMessage(pct, elapsedSec);
      }
      if (Array.isArray(this.stages) && this.stages.length > 0) {
        for (const stage of this.stages) {
          if (pct <= stage.at) return stage.text;
        }
        return this.stages[this.stages.length - 1].text;
      }
      return null;
    }

    updateDom(pct, elapsedSec) {
      if (this.progressBar) this.progressBar.style.width = `${pct}%`;
      if (this.percentEl) this.percentEl.textContent = `${pct}%`;
      if (this.elapsedEl && elapsedSec !== undefined) {
        this.elapsedEl.textContent = `${elapsedSec.toFixed(1)}s`;
      }
      if (this.statusEl) {
        const msg = this.resolveStageMessage(pct, elapsedSec);
        if (msg) this.statusEl.textContent = msg;
      }
    }

    setProgress(pct, statusText) {
      this.progress = pct;
      const elapsedSec = this.startTime ? (Date.now() - this.startTime) / 1000 : 0.0;
      this.updateDom(pct, elapsedSec);
      if (statusText && this.statusEl) {
        this.statusEl.textContent = statusText;
      }
    }

    finish(completionText, callback, delayMs = 300) {
      this.stop();
      if (this.progressBar) this.progressBar.style.width = "100%";
      if (this.percentEl) this.percentEl.textContent = "100%";
      if (this.statusEl && completionText) {
        this.statusEl.textContent = completionText;
      }
      setTimeout(() => {
        if (typeof callback === "function") callback();
      }, delayMs);
    }

    fail(errorText, callback, delayMs = 800) {
      this.stop();
      if (this.statusEl && errorText) {
        this.statusEl.textContent = errorText;
      }
      setTimeout(() => {
        if (typeof callback === "function") callback();
      }, delayMs);
    }

    stop() {
      this.isRunning = false;
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
    }
  }

  function createProgressBar(options) {
    return new AsymptoticProgressBar(options);
  }

  // =========================================================================
  // 4. Shared Action Progress Modal Runner (performAction)
  // =========================================================================
  function resolveActionStageMessage(title, pct, options) {
    if (options && options.stages && Array.isArray(options.stages)) {
      for (const s of options.stages) {
        if (pct <= s.at) return s.text;
      }
      return options.stages[options.stages.length - 1].text;
    }

    const titleUpper = (title || "").toUpperCase();
    if (titleUpper.includes("SYNC") || titleUpper.includes("SYNCHRONIZ")) {
      if (pct < 28) return "Scanning working tree and local feedback files...";
      if (pct < 55) return "Reconciling feedback worktree database...";
      if (pct < 78) return "Synchronizing commits and remote refs...";
      if (pct < 92) return "Recomputing smartlog DAG and commit tags...";
      return "Finalizing workspace synchronization...";
    } else if (titleUpper.includes("REBASE")) {
      if (pct < 30) return "Locating upstream ancestor merge-base...";
      if (pct < 60) return "Replaying commits onto target branch...";
      if (pct < 85) return "Verifying tree integrity and merge conflicts...";
      return "Updating working tree and branch HEAD...";
    } else if (titleUpper.includes("PR") || titleUpper.includes("SUBMIT")) {
      if (pct < 30) return "Analyzing commit stack hierarchy...";
      if (pct < 60) return "Pushing feature branches to origin...";
      if (pct < 85) return "Creating and linking GitHub pull requests...";
      return "Registering upstream tracking references...";
    } else if (titleUpper.includes("SAVE") || titleUpper.includes("WORM") || titleUpper.includes("BUG")) {
      if (pct < 30) return "Validating issue fields and markdown syntax...";
      if (pct < 60) return "Writing records to SQLite and feedback worktree...";
      if (pct < 85) return "Updating review tasks and checklist invariants...";
      return "Finalizing issue status...";
    } else if (titleUpper.includes("STAGE") || titleUpper.includes("COMMIT")) {
      if (pct < 35) return "Inspecting index and staged file changes...";
      if (pct < 70) return "Writing tree object and commit hash...";
      return "Updating HEAD reference and branch state...";
    }

    if (pct < 30) return (options && options.stepText) || "Initializing operation...";
    if (pct < 60) return "Executing operation...";
    if (pct < 85) return "Reconciling changes with repository...";
    return "Finalizing updates...";
  }

  async function performActionWithProgress(actionFn, options = {}) {
    if (typeof document === "undefined") {
      return await actionFn();
    }
    const overlay = document.getElementById("actionProgressModalOverlay");
    const titleEl = document.getElementById("actionProgressTitle");
    const descEl = document.getElementById("actionProgressDescription");
    const statusEl = document.getElementById("actionProgressStatus");
    const elapsedEl = document.getElementById("actionProgressElapsed");
    const barEl = document.getElementById("actionProgressBar");
    const percentEl = document.getElementById("actionProgressPercent");
    const iconEl = document.getElementById("actionProgressIcon");

    const thresholdMs = options.delayMs !== undefined ? options.delayMs : 1000;
    const title = options.title || "PROCESSING ACTION";
    let isModalVisible = false;

    const progressTracker = new AsymptoticProgressBar({
      barEl: barEl,
      percentEl: percentEl,
      statusEl: statusEl,
      elapsedEl: elapsedEl,
      initialProgress: 14,
      maxProgress: 95,
      getStageMessage: (pct) => resolveActionStageMessage(title, pct, options)
    });

    const modalDelayTimer = setTimeout(() => {
      if (!overlay) return;
      isModalVisible = true;
      if (titleEl) titleEl.textContent = title;
      if (descEl) descEl.textContent = options.description || "Please wait while the operation completes...";
      if (iconEl && options.icon) iconEl.textContent = options.icon;
      overlay.style.display = "flex";
      progressTracker.start();
    }, thresholdMs);

    try {
      const result = await actionFn();
      clearTimeout(modalDelayTimer);

      if (isModalVisible) {
        progressTracker.finish(options.successText || "✓ Operation completed successfully.", () => {
          if (overlay) overlay.style.display = "none";
        }, 250);
      }
      return result;
    } catch (err) {
      clearTimeout(modalDelayTimer);
      if (isModalVisible) {
        progressTracker.fail(`Error: ${err.message || "Operation failed"}`, () => {
          if (overlay) overlay.style.display = "none";
        }, 600);
      }
      throw err;
    }
  }

  // =========================================================================
  // 5. Panel Resizers (Split-Pane Drag & Drop)
  // =========================================================================
  function setupPanelResizer(resizerElOrId, targetPaneElOrId, storageKey, minW = 160, maxW = 800) {
    if (typeof document === "undefined") return;
    const resizer = resolveElement(resizerElOrId);
    const targetPane = resolveElement(targetPaneElOrId);
    if (!resizer || !targetPane) return;

    if (storageKey && typeof localStorage !== "undefined") {
      const savedWidth = localStorage.getItem(storageKey);
      if (savedWidth && !targetPane.classList.contains("collapsed")) {
        targetPane.style.width = `${savedWidth}px`;
      }
    }

    let startX = 0;
    let startWidth = 0;

    function onMouseMove(e) {
      const dx = e.clientX - startX;
      let newWidth = startWidth + dx;
      if (newWidth < minW) newWidth = minW;
      if (newWidth > maxW) newWidth = maxW;
      targetPane.style.width = `${newWidth}px`;
      if (storageKey && typeof localStorage !== "undefined") {
        localStorage.setItem(storageKey, newWidth);
      }
    }

    function onMouseUp() {
      resizer.classList.remove("resizing");
      targetPane.classList.remove("resizing");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    resizer.addEventListener("mousedown", (e) => {
      e.preventDefault();
      startX = e.clientX;
      startWidth = targetPane.getBoundingClientRect().width;
      resizer.classList.add("resizing");
      targetPane.classList.add("resizing");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });
  }

  // =========================================================================
  // 6. UI Scale Selector
  // =========================================================================
  function setUiScale(scale) {
    if (typeof document === "undefined") return;
    const val = parseInt(scale, 10) || 80;
    document.documentElement.style.fontSize = `${val}%`;
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("forge_ui_scale", val);
    }
  }

  function initUiScale() {
    if (typeof document === "undefined" || typeof localStorage === "undefined") return;
    const saved = localStorage.getItem("forge_ui_scale");
    if (saved) {
      document.documentElement.style.fontSize = `${saved}%`;
    }
  }

  // =========================================================================
  // 7. Global API Export & Namespace Exposure
  // =========================================================================
  const Forge = {
    // Progress
    AsymptoticProgressBar,
    createProgressBar,
    performActionWithProgress,
    resolveActionStageMessage,

    // Layout & Resizers
    setupPanelResizer,

    // Utilities
    sanitizeAuthor,
    escapeHtml,
    showModal,
    hideModal,
    showToast,
    copyToClipboard,

    // UI Scale
    setUiScale,
    initUiScale
  };

  // Expose on namespace and globally for convenience
  global.Forge = Forge;
  global.Xerxes = Forge; // Retro theme alias
  global.sanitizeAuthor = sanitizeAuthor;
  global.escapeHtml = escapeHtml;
  global.copyToClipboard = copyToClipboard;
  global.showToast = showToast;
  global.setupPanelResizer = setupPanelResizer;
  global.createProgressBarTracker = createProgressBar;
  global.performActionWithProgress = performActionWithProgress;

  // Initialize UI scale on script load if DOM is ready
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initUiScale);
    } else {
      initUiScale();
    }
  }

})(typeof window !== "undefined" ? window : globalThis);
