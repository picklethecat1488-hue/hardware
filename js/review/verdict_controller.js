/**
 * Code Review Verdict Controller, Session Metrics HUD, & Markdown Export (`verdict_controller.js`).
 *
 * Shared 100% byte-identically across `hardware` and `firmware` Code Review workstations.
 */

import { clearChildren, createEl, resolveElement } from "../core/dom.js";
import { showToast } from "../core/toast.js";

const VERDICT_RETURN_DELAY_MS = 800;

/**
 * Synchronize header metrics, verdict badges, severity pills, and document title
 * from `state.session`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} state - Review application state.
 * @param {object} [config] - Boot configuration (`repoName`, `titleBrand`).
 */
export function updateSessionMetricsUI(ctx, state, config = {}) {
  if (!state.session) {
    return;
  }

  const doc = ctx.getDocument();
  const repo = state.session.repo_name || config.repoName || "repo";
  const brand = config.titleBrand || "Code Review";
  const filePrefix = state.selectedFile ? `${state.selectedFile} — ` : "";
  if (doc) {
    doc.title = `${filePrefix}${brand}: ${repo}`;
  }

  const verdict = String(state.session.verdict || "IN_REVIEW");
  const badge = resolveElement(ctx, "reviewVerdictBadge");
  if (badge) {
    badge.textContent = verdict;
    const colorClass =
      verdict === "APPROVED"
        ? "quake-badge-green"
        : verdict === "CHANGES_REQUESTED"
          ? "quake-badge-red"
          : "quake-badge-amber";
    badge.className = `quake-badge ${colorClass}`;
  }

  const btnApprove = resolveElement(ctx, "btnVerdictApprove");
  const btnChanges = resolveElement(ctx, "btnVerdictChanges");
  if (btnApprove) {
    btnApprove.classList.toggle("quake-btn-active", verdict === "APPROVED");
  }
  if (btnChanges) {
    btnChanges.classList.toggle("quake-btn-active", verdict === "CHANGES_REQUESTED");
  }

  const sessionFiles = state.session.files || {};
  const reviewedCount = Object.values(sessionFiles).filter(
    (entry) => entry && entry.status === "REVIEWED",
  ).length;
  const totalCount =
    (Array.isArray(state.files) && state.files.length) ||
    Object.keys(sessionFiles).length ||
    1;
  const pct = Math.round((reviewedCount / totalCount) * 100);
  const progressEl = resolveElement(ctx, "filesProgressText");
  if (progressEl) {
    progressEl.textContent = `${reviewedCount}/${totalCount} (${pct}%)`;
  }

  const comments = Array.isArray(state.session.comments) ? state.session.comments : [];
  const commentsCountEl = resolveElement(ctx, "commentsCountText");
  if (commentsCountEl) {
    commentsCountEl.textContent = `${comments.length} findings`;
  }

  const counts = { MUST_FIX: 0, PROPOSAL: 0, NIT: 0 };
  for (const comment of comments) {
    const sev = String(comment.severity || "").toUpperCase();
    if (sev === "MUST_FIX") {
      counts.MUST_FIX += 1;
    } else if (sev === "PROPOSAL") {
      counts.PROPOSAL += 1;
    } else {
      counts.NIT += 1;
    }
  }

  const pillsEl = resolveElement(ctx, "severityPills");
  if (pillsEl) {
    clearChildren(pillsEl);
    pillsEl.appendChild(
      createEl(ctx, "span", {
        className: "quake-badge quake-badge-red",
        text: `MUST FIX: ${counts.MUST_FIX}`,
      }),
    );
    pillsEl.appendChild(
      createEl(ctx, "span", {
        className: "quake-badge quake-badge-gold",
        text: `PROPOSAL: ${counts.PROPOSAL}`,
      }),
    );
    pillsEl.appendChild(
      createEl(ctx, "span", {
        className: "quake-badge quake-badge-cyan",
        text: `NIT: ${counts.NIT}`,
      }),
    );
  }
}

/**
 * Display the full-screen `#terminationOverlay` when a standalone review session concludes.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} verdict - `"APPROVED"` | `"CHANGES_REQUESTED"`.
 * @param {string} [exportedTo] - Exported Markdown report path.
 * @param {Function|null} [logFn] - Optional `(msg, colorClass) => void` logger.
 */
export function handleSessionTermination(ctx, verdict, exportedTo = "", logFn = null) {
  if (typeof logFn === "function") {
    logFn("==================================================", "gold");
    logFn(`*** REVIEW CONCLUDED: [${verdict}] ***`, verdict === "APPROVED" ? "green" : "red");
    if (exportedTo) {
      logFn(`Findings exported to: ${exportedTo}`, "cyan");
    }
    logFn("Review server shutting down. Terminal released.", "gold");
  }

  const overlay = resolveElement(ctx, "terminationOverlay");
  if (overlay) {
    const titleEl = resolveElement(ctx, "termOverlayVerdict");
    if (titleEl) {
      titleEl.textContent = verdict;
      titleEl.className = `quake-badge termination-badge ${
        verdict === "APPROVED" ? "quake-badge-green" : "quake-badge-red"
      }`;
    }
    const fileEl = resolveElement(ctx, "termOverlayFile");
    if (fileEl && exportedTo) {
      fileEl.textContent = exportedTo;
    }
    overlay.style.display = "flex";
  }
}

/**
 * Submit a review verdict (`"APPROVED"` | `"CHANGES_REQUESTED"` | `"IN_REVIEW"`) to `POST /api/verdict`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {string} verdict - Target verdict status.
 * @param {object} [callbacks] - `{ logCli, onSessionUpdated, onConclude }`.
 * @returns {Promise<object|null>} Server response payload or `null` on network failure.
 */
export async function setReviewVerdict(ctx, verdict, callbacks = {}) {
  const logFn = typeof callbacks.logCli === "function" ? callbacks.logCli : null;
  try {
    const data = await ctx.postJson("/api/verdict", { verdict, terminate: false });
    if (data.status === "ok") {
      if (logFn) {
        logFn(`Review verdict updated to: [${verdict}]`, "gold");
      }
      if (data.session && typeof callbacks.onSessionUpdated === "function") {
        callbacks.onSessionUpdated(data.session);
      }
      if (data.terminated) {
        handleSessionTermination(ctx, verdict, data.exported_to || "", logFn);
      } else if (verdict === "APPROVED" || verdict === "CHANGES_REQUESTED") {
        showToast(ctx, `Review verdict: [${verdict}]. Returning to Dashboard...`);
        if (typeof callbacks.onConclude === "function") {
          ctx.setTimeout(() => {
            callbacks.onConclude();
          }, VERDICT_RETURN_DELAY_MS);
        }
      } else {
        showToast(ctx, `Review verdict: ${verdict}`);
      }
    } else if (logFn) {
      logFn(`Error updating verdict: ${data.message || "Unknown error"}`, "red");
    }
    return data;
  } catch (err) {
    if (logFn) {
      logFn(`Error updating verdict: ${err.message}`, "red");
    }
    return null;
  }
}

/**
 * Export the current review session to Markdown via `POST /api/export`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {Function|null} [logFn] - Optional CLI logger.
 * @returns {Promise<object|null>}
 */
export async function exportReviewMarkdown(ctx, logFn = null) {
  try {
    const data = await ctx.postJson("/api/export", {});
    if (data.status === "ok") {
      if (logFn) {
        logFn(`✓ Review successfully exported to: ${data.path}`, "green");
      }
      showToast(ctx, `Exported to ${data.path}`);
    } else if (logFn) {
      logFn(`Export error: ${data.message || "Unknown error"}`, "red");
    }
    return data;
  } catch (err) {
    if (logFn) {
      logFn(`Export failed: ${err.message}`, "red");
    }
    return null;
  }
}

/**
 * Synchronize review feedback files from `feedback/` via `POST /api/sync_feedback`.
 *
 * @param {import("../core/runtime_context.js").RuntimeContext} ctx - Runtime context.
 * @param {object} [callbacks] - `{ logCli, onSynced }`.
 * @returns {Promise<object|null>}
 */
export async function syncReviewFeedback(ctx, callbacks = {}) {
  const logFn = typeof callbacks.logCli === "function" ? callbacks.logCli : null;
  const modal = resolveElement(ctx, "feedbackLoadingModal");
  if (modal) {
    modal.style.display = "flex";
  }
  if (logFn) {
    logFn("Synchronizing review feedback with feedback/ directory...", "cyan");
  }

  try {
    const data = await ctx.postJson("/api/sync_feedback", {});
    if (data.status === "ok") {
      const stats = data.stats || {};
      const msg = `Feedback synced: ${stats.merged || 0} commit reviews merged.`;
      if (logFn) {
        logFn(msg, "green");
      }
      showToast(ctx, msg);
      if (typeof callbacks.onSynced === "function") {
        await callbacks.onSynced();
      }
    } else {
      if (logFn) {
        logFn(`Sync failed: ${data.message || "Unknown error"}`, "red");
      }
      showToast(ctx, "Sync failed");
    }
    return data;
  } catch (err) {
    if (logFn) {
      logFn(`Error syncing feedback: ${err.message}`, "red");
    }
    showToast(ctx, "Error syncing feedback");
    return null;
  } finally {
    if (modal) {
      modal.style.display = "none";
    }
  }
}
