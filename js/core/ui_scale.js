/**
 * Retina-Safe CSS `--ui-scale` Controller.
 *
 * Updates the root `--ui-scale` CSS custom property without setting `html { zoom }`,
 * preventing macOS `WKWebView` / CoreAnimation compositor upscaling blur on WebGL
 * and 2D `<canvas>` viewports.
 */

import { resolveElement } from "./dom.js";

export const DEFAULT_UI_SCALE_STORAGE_KEY = "forge_ui_scale";
const MIN_UI_SCALE_FACTOR = 0.65;
const MAX_UI_SCALE_FACTOR = 1.75;
const PERCENT_THRESHOLD = 10;
const BASE_FONT_PERCENT = 80;

/**
 * Normalize a scale value expressed either as a ratio (`1.0`, `1.15`) or percentage (`80`, `100`, `125`).
 *
 * When a legacy percentage like `80` (corresponding to `common.css` base `80%`) is supplied
 * in `percentMode = "fontPercent"`, `80 -> 1.0`, `100 -> 1.25`. Otherwise `100 -> 1.0`.
 *
 * @param {number|string} rawScale - Input scale ratio or percentage.
 * @param {"ratio"|"fontPercent"} [mode] - Interpretation mode for values >= 10.
 * @returns {number} Clamped UI scale multiplier around `1.0`.
 */
export function normalizeUiScale(rawScale, mode = "ratio") {
  const num = Number(rawScale);
  if (!Number.isFinite(num) || num <= 0) {
    return 1.0;
  }
  let factor = num;
  if (num >= PERCENT_THRESHOLD) {
    factor = mode === "fontPercent" ? num / BASE_FONT_PERCENT : num / 100;
  }
  return Math.max(MIN_UI_SCALE_FACTOR, Math.min(MAX_UI_SCALE_FACTOR, factor));
}

/**
 * Apply `--ui-scale` to `document.documentElement` and persist to storage.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {number|string} rawScale - Desired scale ratio (`0.8..1.5`) or percentage.
 * @param {object} [options] - `{ storageKey, mode, persistValue, onScaleChange }`.
 * @returns {number} Applied normalized scale factor.
 */
export function applyUiScale(ctx, rawScale, options = {}) {
  const mode = options.mode || "ratio";
  const factor = normalizeUiScale(rawScale, mode);
  const doc = ctx.getDocument();
  if (doc && doc.documentElement) {
    doc.documentElement.style.setProperty("--ui-scale", factor.toFixed(4));
  }
  const storageKey =
    options.storageKey !== undefined ? options.storageKey : DEFAULT_UI_SCALE_STORAGE_KEY;
  if (storageKey) {
    const storedVal =
      options.persistValue !== undefined ? String(options.persistValue) : String(rawScale);
    ctx.getStorage().setItem(storageKey, storedVal);
  }
  if (typeof options.onScaleChange === "function") {
    options.onScaleChange(factor);
  }
  return factor;
}

/**
 * Initialize `--ui-scale` from persistent storage and optionally bind a `<select>` control.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string|null} [selectElOrId] - Optional `<select>` element or ID.
 * @param {object} [options] - `{ storageKey, defaultValue, mode, onScaleChange }`.
 * @returns {number} Active normalized UI scale factor.
 */
export function initUiScaleControl(ctx, selectElOrId = null, options = {}) {
  const storageKey = options.storageKey || DEFAULT_UI_SCALE_STORAGE_KEY;
  const mode = options.mode || "ratio";
  const saved = ctx.getStorage().getItem(storageKey);
  const selectEl = resolveElement(ctx, selectElOrId);
  const initialRaw =
    saved !== null && saved !== ""
      ? saved
      : (selectEl && selectEl.value) || options.defaultValue || (mode === "fontPercent" ? "80" : "1");

  const applied = applyUiScale(ctx, initialRaw, {
    storageKey,
    mode,
    persistValue: initialRaw,
    onScaleChange: options.onScaleChange,
  });

  if (selectEl) {
    selectEl.value = String(initialRaw);
    selectEl.addEventListener("change", () => {
      applyUiScale(ctx, selectEl.value, {
        storageKey,
        mode,
        persistValue: selectEl.value,
        onScaleChange: options.onScaleChange,
      });
    });
  }

  return applied;
}
