/**
 * Zero-globals Toast Notification & Clipboard Feedback Helpers.
 */

const TOAST_CONTAINER_ID = "forge-toast-container";
const DEFAULT_TOAST_DURATION_MS = 3000;
const TOAST_FADE_OUT_MS = 250;

const BORDER_COLOR_BY_TYPE = {
  info: "#00e5ff",
  success: "#00ff66",
  warning: "#ffaa00",
  error: "#ff3333",
};

/**
 * Display an ephemeral workstation toast notification.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} message - Toast message text.
 * @param {"info"|"success"|"warning"|"error"} [type] - Visual severity style.
 * @param {number} [durationMs] - Display duration in milliseconds.
 * @returns {HTMLElement|null} Created toast element, or `null` when headless without DOM.
 */
export function showToast(ctx, message, type = "info", durationMs = DEFAULT_TOAST_DURATION_MS) {
  const doc = ctx.getDocument();
  if (!doc || !doc.body) {
    return null;
  }

  let container = doc.getElementById(TOAST_CONTAINER_ID);
  if (!container) {
    container = ctx.createElement("div");
    container.id = TOAST_CONTAINER_ID;
    container.style.cssText =
      "position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
    doc.body.appendChild(container);
  }

  const toast = ctx.createElement("div");
  toast.className = `forge-toast forge-toast-${type}`;
  const borderColor = BORDER_COLOR_BY_TYPE[type] || BORDER_COLOR_BY_TYPE.info;
  toast.style.cssText =
    `background:rgba(10, 28, 36, 0.95);border:1px solid ${borderColor};color:#ffffff;` +
    "padding:8px 14px;border-radius:3px;font-family:ui-monospace,monospace;font-size:12px;" +
    "box-shadow:0 4px 12px rgba(0,0,0,0.55);pointer-events:auto;transition:opacity 0.2s ease;opacity:0;";
  toast.textContent = String(message ?? "");
  container.appendChild(toast);

  ctx.requestAnimationFrame(() => {
    toast.style.opacity = "1";
  });

  ctx.setTimeout(() => {
    toast.style.opacity = "0";
    ctx.setTimeout(() => {
      toast.remove();
    }, TOAST_FADE_OUT_MS);
  }, durationMs);

  return toast;
}

/**
 * Copy `text` to clipboard via `ctx.copyTextToClipboard()` and display a confirmation toast.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} text - Text to copy.
 * @param {string} [successMessage] - Toast message on success.
 * @returns {Promise<boolean>}
 */
export async function copyToClipboard(ctx, text, successMessage = "Copied to clipboard!") {
  const ok = await ctx.copyTextToClipboard(text);
  if (ok) {
    showToast(ctx, successMessage, "success");
  } else {
    showToast(ctx, "Failed to copy to clipboard", "error");
  }
  return ok;
}
