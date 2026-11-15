/**
 * Zero-globals Split-Pane Panel Resizer with Pointer Capture & Storage Persistence.
 */

import { resolveElement } from "./dom.js";

const DEFAULT_MIN_SIZE_PX = 160;
const DEFAULT_MAX_SIZE_PX = 800;

/**
 * Bind interactive pointer drag resizing between `resizerElOrId` and `targetPaneElOrId`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} resizerElOrId - Splitter handle element or ID.
 * @param {Element|string} targetPaneElOrId - Resizable pane element or ID.
 * @param {string|null} storageKey - Optional storage key for persisting pixel size.
 * @param {object} [options] - `{ minSize, maxSize, axis: "x"|"y", invert: boolean, onResize: Function }`.
 * @returns {function(): void} Cleanup function.
 */
export function setupPanelResizer(
  ctx,
  resizerElOrId,
  targetPaneElOrId,
  storageKey = null,
  options = {},
) {
  const resizer = resolveElement(ctx, resizerElOrId);
  const targetPane = resolveElement(ctx, targetPaneElOrId);
  if (!resizer || !targetPane) {
    return () => {};
  }

  const axis = options.axis === "y" ? "y" : "x";
  const minSize = options.minSize ?? options.minW ?? DEFAULT_MIN_SIZE_PX;
  const maxSize = options.maxSize ?? options.maxW ?? DEFAULT_MAX_SIZE_PX;
  const invert = Boolean(options.invert);
  const propName = axis === "y" ? "height" : "width";
  const storage = ctx.getStorage();

  if (storageKey) {
    const savedRaw = storage.getItem(storageKey);
    const savedNum = savedRaw ? Number(savedRaw) : NaN;
    if (Number.isFinite(savedNum) && savedNum >= minSize && !targetPane.classList.contains("collapsed")) {
      targetPane.style[propName] = `${Math.min(maxSize, savedNum)}px`;
    }
  }

  let activePointerId = null;
  let startCoord = 0;
  let startSize = 0;

  const onPointerMove = (event) => {
    if (activePointerId === null || event.pointerId !== activePointerId) {
      return;
    }
    const currentCoord = axis === "y" ? event.clientY : event.clientX;
    const rawDelta = currentCoord - startCoord;
    const signedDelta = invert ? -rawDelta : rawDelta;
    const clamped = Math.max(minSize, Math.min(maxSize, Math.round(startSize + signedDelta)));
    targetPane.style[propName] = `${clamped}px`;
    if (storageKey) {
      storage.setItem(storageKey, String(clamped));
    }
    if (typeof options.onResize === "function") {
      options.onResize(clamped);
    }
  };

  const onPointerUp = (event) => {
    if (activePointerId === null || event.pointerId !== activePointerId) {
      return;
    }
    if (resizer.hasPointerCapture && resizer.hasPointerCapture(activePointerId)) {
      resizer.releasePointerCapture(activePointerId);
    }
    activePointerId = null;
    resizer.classList.remove("resizing");
    targetPane.classList.remove("resizing");
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.style.cursor = "";
      doc.body.style.userSelect = "";
    }
  };

  const onPointerDown = (event) => {
    event.preventDefault();
    activePointerId = event.pointerId;
    startCoord = axis === "y" ? event.clientY : event.clientX;
    const rect = targetPane.getBoundingClientRect();
    startSize = axis === "y" ? rect.height : rect.width;
    resizer.classList.add("resizing");
    targetPane.classList.add("resizing");
    if (resizer.setPointerCapture) {
      resizer.setPointerCapture(activePointerId);
    }
    const doc = ctx.getDocument();
    if (doc && doc.body) {
      doc.body.style.cursor = axis === "y" ? "row-resize" : "col-resize";
      doc.body.style.userSelect = "none";
    }
  };

  resizer.addEventListener("pointerdown", onPointerDown);
  resizer.addEventListener("pointermove", onPointerMove);
  resizer.addEventListener("pointerup", onPointerUp);
  resizer.addEventListener("pointercancel", onPointerUp);

  return () => {
    resizer.removeEventListener("pointerdown", onPointerDown);
    resizer.removeEventListener("pointermove", onPointerMove);
    resizer.removeEventListener("pointerup", onPointerUp);
    resizer.removeEventListener("pointercancel", onPointerUp);
  };
}
