/**
 * Zero-globals Modal Overlay & Confirmation Dialog Controllers.
 *
 * Replaces native browser `window.alert`, `window.confirm`, and `window.prompt`
 * with keyboard-accessible Quake/Xerxes HUD modals.
 */

import { createEl, resolveElement } from "./dom.js";

const CONFIRM_MODAL_ID = "forge-dynamic-confirm-modal";

/**
 * Show a modal overlay element.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} modalElOrId - Modal element or ID.
 * @param {string} [display] - CSS display mode (`"flex"` default).
 */
export function showModal(ctx, modalElOrId, display = "flex") {
  const el = resolveElement(ctx, modalElOrId);
  if (el) {
    el.style.display = display;
  }
}

/**
 * Hide a modal overlay element.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} modalElOrId - Modal element or ID.
 */
export function hideModal(ctx, modalElOrId) {
  const el = resolveElement(ctx, modalElOrId);
  if (el) {
    el.style.display = "none";
  }
}

/**
 * Close a modal when clicking directly on its backdrop overlay.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} overlayElOrId - Backdrop overlay element or ID.
 * @param {Function} [onClose] - Optional custom close handler.
 */
export function bindModalBackdropClose(ctx, overlayElOrId, onClose) {
  const overlay = resolveElement(ctx, overlayElOrId);
  if (!overlay) {
    return;
  }
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      if (typeof onClose === "function") {
        onClose();
      } else {
        hideModal(ctx, overlay);
      }
    }
  });
}

/**
 * Present an asynchronous confirmation modal dialog (replacing `window.confirm`).
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} options - Dialog options `{ title, message, confirmLabel, cancelLabel, danger }`.
 * @returns {Promise<boolean>} Resolves `true` if confirmed, `false` if cancelled.
 */
export function showConfirmModal(ctx, options = {}) {
  const doc = ctx.getDocument();
  if (!doc || !doc.body) {
    return Promise.resolve(Boolean(options.defaultWhenHeadless));
  }

  const existing = doc.getElementById(CONFIRM_MODAL_ID);
  if (existing) {
    existing.remove();
  }

  return new Promise((resolve) => {
    const accent = options.danger ? "#ff4444" : "#ffb800";

    const cleanup = (result) => {
      ctx.removeViewportListener("keydown", onKeyDown);
      overlay.remove();
      resolve(result);
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cleanup(false);
      } else if (event.key === "Enter") {
        event.preventDefault();
        cleanup(true);
      }
    };

    const cancelBtn = createEl(ctx, "button", {
      text: options.cancelLabel || "Cancel",
      attrs: { type: "button" },
      style: {
        background: "transparent",
        color: "#c9b6a3",
        border: "1px solid #5a381e",
        borderRadius: "3px",
        padding: "6px 14px",
        cursor: "pointer",
        fontFamily: "ui-monospace, monospace",
        fontSize: "11px",
      },
      on: { click: () => cleanup(false) },
    });

    const confirmBtn = createEl(ctx, "button", {
      text: options.confirmLabel || "Confirm",
      attrs: { type: "button" },
      style: {
        background: accent,
        color: "#110a05",
        border: `1px solid ${accent}`,
        borderRadius: "3px",
        padding: "6px 14px",
        cursor: "pointer",
        fontWeight: "700",
        fontFamily: "ui-monospace, monospace",
        fontSize: "11px",
      },
      on: { click: () => cleanup(true) },
    });

    const card = createEl(ctx, "div", {
      style: {
        background: "#1b120a",
        border: `1px solid ${accent}`,
        borderRadius: "4px",
        padding: "16px 20px",
        minWidth: "320px",
        maxWidth: "480px",
        color: "#f2e5d5",
        fontFamily: "ui-monospace, monospace",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.75)",
      },
      children: [
        createEl(ctx, "div", {
          text: options.title || "CONFIRM ACTION",
          style: {
            color: accent,
            fontWeight: "700",
            fontSize: "12px",
            marginBottom: "10px",
            letterSpacing: "0.06em",
          },
        }),
        createEl(ctx, "div", {
          text: options.message || "Proceed with this action?",
          style: {
            fontSize: "11.5px",
            lineHeight: "1.5",
            marginBottom: "16px",
            whiteSpace: "pre-wrap",
          },
        }),
        createEl(ctx, "div", {
          style: {
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
          },
          children: [cancelBtn, confirmBtn],
        }),
      ],
    });

    const overlay = createEl(ctx, "div", {
      id: CONFIRM_MODAL_ID,
      className: "quake-modal-overlay",
      style: { display: "flex", zIndex: "12000" },
      on: {
        click: (event) => {
          if (event.target === overlay) {
            cleanup(false);
          }
        },
      },
      children: [card],
    });

    doc.body.appendChild(overlay);
    ctx.addViewportListener("keydown", onKeyDown);
    confirmBtn.focus();
  });
}
