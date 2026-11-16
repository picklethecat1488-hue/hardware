/**
 * Asymptotic Progress Bar & Action Progress Modal Runner.
 *
 * Uses `RuntimeContext` timers (`setInterval`, `setTimeout`, `nowMs`) with zero globals.
 */

import { resolveElement } from "./dom.js";

const DEFAULT_INITIAL_PROGRESS = 12;
const DEFAULT_MAX_PROGRESS = 95;
const DEFAULT_TICK_INTERVAL_MS = 50;
const DEFAULT_MODAL_DELAY_MS = 1000;
const MS_PER_SECOND = 1000;

const STAGE_1_END_SEC = 0.6;
const STAGE_2_END_SEC = 2.0;
const STAGE_3_END_SEC = 4.5;
const ASYMPTOTIC_DECAY = 0.015;

/**
 * Multi-phase asymptotic progress bar controller.
 */
export class AsymptoticProgressBar {
  /**
   * Construct an `AsymptoticProgressBar`.
   *
   * @param {object} ctx - Explicit `RuntimeContext`.
   * @param {object} [options] - Element bindings and timing thresholds.
   */
  constructor(ctx, options = {}) {
    this.ctx = ctx;
    this.progressBar = resolveElement(ctx, options.progressBar || options.barEl);
    this.percentEl = resolveElement(ctx, options.percentEl);
    this.statusEl = resolveElement(ctx, options.statusEl || options.statusTextEl);
    this.elapsedEl = resolveElement(ctx, options.elapsedEl);
    this.initialProgress =
      options.initialProgress !== undefined ? options.initialProgress : DEFAULT_INITIAL_PROGRESS;
    this.maxProgress =
      options.maxProgress !== undefined ? options.maxProgress : DEFAULT_MAX_PROGRESS;
    this.intervalMs = options.intervalMs || DEFAULT_TICK_INTERVAL_MS;
    this.stages = options.stages || [];
    this.getStageMessage = options.getStageMessage || null;
    this.customTick = options.onTick || null;

    this.progress = this.initialProgress;
    this.startTimeMs = null;
    this.timer = null;
    this.isRunning = false;
  }

  /**
   * Start periodic progress updates.
   *
   * @returns {AsymptoticProgressBar}
   */
  start() {
    this.stop();
    this.isRunning = true;
    this.startTimeMs = this.ctx.nowMs();
    this.progress = this.initialProgress;
    this.updateDom(this.progress, 0.0);
    this.timer = this.ctx.setInterval(() => this.tick(), this.intervalMs);
    this.tick();
    return this;
  }

  /**
   * Advance asymptotic progress curve based on elapsed wall time.
   */
  tick() {
    if (!this.isRunning) {
      return;
    }
    const elapsedSec = Math.max(0, (this.ctx.nowMs() - this.startTimeMs) / MS_PER_SECOND);
    if (this.progress < this.maxProgress) {
      if (elapsedSec < STAGE_1_END_SEC) {
        this.progress = this.initialProgress + (elapsedSec / STAGE_1_END_SEC) * 23;
      } else if (elapsedSec < STAGE_2_END_SEC) {
        this.progress =
          35 + ((elapsedSec - STAGE_1_END_SEC) / (STAGE_2_END_SEC - STAGE_1_END_SEC)) * 30;
      } else if (elapsedSec < STAGE_3_END_SEC) {
        this.progress =
          65 + ((elapsedSec - STAGE_2_END_SEC) / (STAGE_3_END_SEC - STAGE_2_END_SEC)) * 22;
      } else {
        this.progress += (this.maxProgress + 1 - this.progress) * ASYMPTOTIC_DECAY;
      }
    }

    const clampedPct = Math.min(this.maxProgress, Math.floor(this.progress));
    this.updateDom(clampedPct, elapsedSec);
    if (typeof this.customTick === "function") {
      this.customTick(clampedPct, elapsedSec);
    }
  }

  /**
   * Resolve human-readable stage text for the current percentage.
   *
   * @param {number} pct - Progress percentage `[0, 100]`.
   * @param {number} elapsedSec - Elapsed seconds.
   * @returns {string|null}
   */
  resolveStageMessage(pct, elapsedSec) {
    if (typeof this.getStageMessage === "function") {
      return this.getStageMessage(pct, elapsedSec);
    }
    if (Array.isArray(this.stages) && this.stages.length > 0) {
      for (const stage of this.stages) {
        if (pct <= stage.at) {
          return stage.text;
        }
      }
      return this.stages[this.stages.length - 1].text;
    }
    return null;
  }

  /**
   * Synchronize bound DOM elements with current percentage and elapsed time.
   *
   * @param {number} pct - Clamped percentage.
   * @param {number} elapsedSec - Elapsed seconds.
   */
  updateDom(pct, elapsedSec) {
    if (this.progressBar) {
      this.progressBar.style.width = `${pct}%`;
    }
    if (this.percentEl) {
      this.percentEl.textContent = `${pct}%`;
    }
    if (this.elapsedEl && elapsedSec !== undefined) {
      this.elapsedEl.textContent = `${elapsedSec.toFixed(1)}s`;
    }
    if (this.statusEl) {
      const msg = this.resolveStageMessage(pct, elapsedSec);
      if (msg) {
        this.statusEl.textContent = msg;
      }
    }
  }

  /**
   * Manually set explicit progress percentage and status message.
   *
   * @param {number} pct - Progress percentage.
   * @param {string} [statusText] - Optional status override.
   */
  setProgress(pct, statusText) {
    this.progress = pct;
    const elapsedSec =
      this.startTimeMs !== null ? (this.ctx.nowMs() - this.startTimeMs) / MS_PER_SECOND : 0.0;
    this.updateDom(pct, elapsedSec);
    if (statusText && this.statusEl) {
      this.statusEl.textContent = statusText;
    }
  }

  /**
   * Complete the progress bar at `100%` and invoke `callback` after `delayMs`.
   *
   * @param {string} [completionText] - Final status text.
   * @param {Function} [callback] - Completion callback.
   * @param {number} [delayMs] - Hold duration before `callback`.
   */
  finish(completionText, callback, delayMs = 300) {
    this.stop();
    if (this.progressBar) {
      this.progressBar.style.width = "100%";
    }
    if (this.percentEl) {
      this.percentEl.textContent = "100%";
    }
    if (this.statusEl && completionText) {
      this.statusEl.textContent = completionText;
    }
    this.ctx.setTimeout(() => {
      if (typeof callback === "function") {
        callback();
      }
    }, delayMs);
  }

  /**
   * Halt progress bar on failure and invoke `callback` after `delayMs`.
   *
   * @param {string} [errorText] - Failure status text.
   * @param {Function} [callback] - Cleanup callback.
   * @param {number} [delayMs] - Hold duration before `callback`.
   */
  fail(errorText, callback, delayMs = 800) {
    this.stop();
    if (this.statusEl && errorText) {
      this.statusEl.textContent = errorText;
    }
    this.ctx.setTimeout(() => {
      if (typeof callback === "function") {
        callback();
      }
    }, delayMs);
  }

  /**
   * Stop the internal interval timer.
   */
  stop() {
    this.isRunning = false;
    if (this.timer !== null) {
      this.ctx.clearInterval(this.timer);
      this.timer = null;
    }
  }
}

/**
 * Resolve contextual status copy for common Git, Review, Issue, and Sync operations.
 *
 * @param {string} title - Action title.
 * @param {number} pct - Current progress percentage.
 * @param {object} [options] - Optional custom stages or `stepText`.
 * @returns {string}
 */
export function resolveActionStageMessage(title, pct, options = {}) {
  if (Array.isArray(options.stages) && options.stages.length > 0) {
    for (const stage of options.stages) {
      if (pct <= stage.at) {
        return stage.text;
      }
    }
    return options.stages[options.stages.length - 1].text;
  }

  const titleUpper = String(title || "").toUpperCase();
  if (titleUpper.includes("SYNC") || titleUpper.includes("SYNCHRONIZ")) {
    if (pct < 28) return "Scanning working tree and local feedback files...";
    if (pct < 55) return "Reconciling feedback worktree database...";
    if (pct < 78) return "Synchronizing commits and remote refs...";
    if (pct < 92) return "Recomputing smartlog DAG and commit tags...";
    return "Finalizing workspace synchronization...";
  }
  if (titleUpper.includes("REBASE")) {
    if (pct < 30) return "Locating upstream ancestor merge-base...";
    if (pct < 60) return "Replaying commits onto target branch...";
    if (pct < 85) return "Verifying tree integrity and merge conflicts...";
    return "Updating working tree and branch HEAD...";
  }
  if (titleUpper.includes("PR") || titleUpper.includes("SUBMIT")) {
    if (pct < 30) return "Analyzing commit stack hierarchy...";
    if (pct < 60) return "Pushing feature branches to origin...";
    if (pct < 85) return "Creating and linking GitHub pull requests...";
    return "Registering upstream tracking references...";
  }
  if (
    titleUpper.includes("SAVE") ||
    titleUpper.includes("WORM") ||
    titleUpper.includes("BUG")
  ) {
    if (pct < 30) return "Validating issue fields and markdown syntax...";
    if (pct < 60) return "Writing records to SQLite and feedback worktree...";
    if (pct < 85) return "Updating review tasks and checklist invariants...";
    return "Finalizing issue status...";
  }
  if (titleUpper.includes("STAGE") || titleUpper.includes("COMMIT")) {
    if (pct < 35) return "Inspecting index and staged file changes...";
    if (pct < 70) return "Writing tree object and commit hash...";
    return "Updating HEAD reference and branch state...";
  }

  if (pct < 30) return options.stepText || "Initializing operation...";
  if (pct < 60) return "Executing operation...";
  if (pct < 85) return "Reconciling changes with repository...";
  return "Finalizing updates...";
}

/**
 * Execute an async `actionFn`, displaying `#actionProgressModalOverlay` if it exceeds `delayMs`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {function(): Promise<any>} actionFn - Asynchronous task to execute.
 * @param {object} [options] - Modal title, description, icon, and threshold configuration.
 * @returns {Promise<any>} Result of `actionFn()`.
 */
export async function performActionWithProgress(ctx, actionFn, options = {}) {
  const doc = ctx.getDocument();
  if (!doc) {
    return actionFn();
  }

  const overlay = doc.getElementById("actionProgressModalOverlay");
  const titleEl = doc.getElementById("actionProgressTitle");
  const descEl = doc.getElementById("actionProgressDescription");
  const statusEl = doc.getElementById("actionProgressStatus");
  const elapsedEl = doc.getElementById("actionProgressElapsed");
  const barEl = doc.getElementById("actionProgressBar");
  const percentEl = doc.getElementById("actionProgressPercent");
  const iconEl = doc.getElementById("actionProgressIcon");

  const thresholdMs = options.delayMs !== undefined ? options.delayMs : DEFAULT_MODAL_DELAY_MS;
  const title = options.title || "PROCESSING ACTION";
  let isModalVisible = false;

  const tracker = new AsymptoticProgressBar(ctx, {
    barEl,
    percentEl,
    statusEl,
    elapsedEl,
    initialProgress: 14,
    maxProgress: DEFAULT_MAX_PROGRESS,
    getStageMessage: (pct) => resolveActionStageMessage(title, pct, options),
  });

  const modalDelayTimer = ctx.setTimeout(() => {
    if (!overlay) {
      return;
    }
    isModalVisible = true;
    if (titleEl) titleEl.textContent = title;
    if (descEl) {
      descEl.textContent =
        options.description || "Please wait while the operation completes...";
    }
    if (iconEl && options.icon) iconEl.textContent = options.icon;
    overlay.style.display = "flex";
    tracker.start();
  }, thresholdMs);

  try {
    const result = await actionFn();
    ctx.clearTimeout(modalDelayTimer);
    if (isModalVisible) {
      tracker.finish(
        options.successText || "✓ Operation completed successfully.",
        () => {
          if (overlay) overlay.style.display = "none";
        },
        250,
      );
    }
    return result;
  } catch (err) {
    ctx.clearTimeout(modalDelayTimer);
    if (isModalVisible) {
      tracker.fail(
        `Error: ${(err && err.message) || "Operation failed"}`,
        () => {
          if (overlay) overlay.style.display = "none";
        },
        600,
      );
    }
    throw err;
  }
}
