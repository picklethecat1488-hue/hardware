/**
 * Explicit Host & Browser Runtime Context Accessor Module.
 *
 * ARCHITECTURAL INVARIANT:
 * This file (`js/core/runtime_context.js`) is the ONLY JavaScript module in the
 * repository permitted to reference `globalThis` or browser globals (`window`,
 * `document`, `localStorage`, `navigator`, `fetch`, `requestAnimationFrame`,
 * `hljs`, `eel`, `pywebview`). All other modules MUST obtain host services via
 * an injected `RuntimeContext` from `createBrowserRuntimeContext()` or
 * `createMockRuntimeContext()`.
 */

export const DEFAULT_BOOT_CONFIG_ID = "app-boot-config";
const DEFAULT_VIEWPORT_WIDTH_PX = 1280;
const DEFAULT_VIEWPORT_HEIGHT_PX = 800;
const DEFAULT_FRAME_DT_MS = 16.6667;

/**
 * Create an in-memory key-value store matching the Web Storage API.
 *
 * @param {Record<string, string>} [initialEntries] - Optional seed entries.
 * @returns {{getItem: function(string): string|null, setItem: function(string, string): void, removeItem: function(string): void, clear: function(): void}}
 */
export function createMemoryStorage(initialEntries = {}) {
  const map = new Map(Object.entries(initialEntries).map(([k, v]) => [k, String(v)]));
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      map.set(String(key), String(value));
    },
    removeItem(key) {
      map.delete(String(key));
    },
    clear() {
      map.clear();
    },
  };
}

/**
 * Resolve native `localStorage` when accessible, falling back to in-memory storage
 * in sandboxed webviews or headless environments.
 *
 * @returns {{getItem: function(string): string|null, setItem: function(string, string): void, removeItem: function(string): void}}
 */
function resolveBrowserStorage() {
  const fallback = createMemoryStorage();
  const rawStorage = globalThis.document ? globalThis.localStorage : null;
  if (!rawStorage) {
    return fallback;
  }
  return {
    getItem(key) {
      try {
        return rawStorage.getItem(key);
      } catch {
        return fallback.getItem(key);
      }
    },
    setItem(key, value) {
      try {
        rawStorage.setItem(key, String(value));
      } catch {
        fallback.setItem(key, String(value));
      }
    },
    removeItem(key) {
      try {
        rawStorage.removeItem(key);
      } catch {
        fallback.removeItem(key);
      }
    },
  };
}

/**
 * Create the production browser `RuntimeContext` backed by `globalThis`.
 *
 * @returns {object} Explicit runtime capability object.
 */
export function createBrowserRuntimeContext() {
  const storage = resolveBrowserStorage();

  const ctx = {
    /**
     * Return the active DOM `Document` or `null` if unavailable.
     * @returns {Document|null}
     */
    getDocument() {
      return globalThis.document ?? null;
    },

    /**
     * Parse structured JSON boot configuration from `<script id="..." type="application/json">`.
     *
     * @param {string} [elementId] - Script element ID.
     * @returns {object} Parsed configuration object (or `{}` if absent).
     */
    getBootConfig(elementId = DEFAULT_BOOT_CONFIG_ID) {
      const doc = globalThis.document;
      if (!doc) {
        return {};
      }
      const el = doc.getElementById(elementId);
      if (!el) {
        return {};
      }
      const rawText = (el.textContent || "").trim();
      if (!rawText) {
        return {};
      }
      return JSON.parse(rawText);
    },

    /**
     * Return logical CSS viewport dimensions `{ width, height }`.
     * @returns {{width: number, height: number}}
     */
    getViewportSize() {
      return {
        width: Number(globalThis.innerWidth) || DEFAULT_VIEWPORT_WIDTH_PX,
        height: Number(globalThis.innerHeight) || DEFAULT_VIEWPORT_HEIGHT_PX,
      };
    },

    /**
     * Return physical-to-CSS pixel ratio (`2.0` on Apple Retina displays).
     * @returns {number}
     */
    getDevicePixelRatio() {
      const dpr = Number(globalThis.devicePixelRatio);
      return Number.isFinite(dpr) && dpr > 0 ? dpr : 1;
    },

    /**
     * Detect whether the current document is hosted inside an `<iframe>`.
     * @returns {boolean}
     */
    isEmbeddedInFrame() {
      try {
        return Boolean(globalThis.self && globalThis.top && globalThis.self !== globalThis.top);
      } catch {
        return true;
      }
    },

    /**
     * Attach a viewport/window-level event listener (`resize`, `keydown`, `popstate`, `message`, etc.).
     *
     * @param {string} eventType - Event name.
     * @param {Function} listener - Event callback.
     * @param {boolean|object} [options] - Listener options.
     */
    addViewportListener(eventType, listener, options) {
      if (typeof globalThis.addEventListener === "function") {
        globalThis.addEventListener(eventType, listener, options);
      }
    },

    /**
     * Remove a previously registered viewport/window-level event listener.
     *
     * @param {string} eventType - Event name.
     * @param {Function} listener - Event callback.
     * @param {boolean|object} [options] - Listener options.
     */
    removeViewportListener(eventType, listener, options) {
      if (typeof globalThis.removeEventListener === "function") {
        globalThis.removeEventListener(eventType, listener, options);
      }
    },

    /**
     * Return persistent key-value storage accessor.
     * @returns {{getItem: function(string): string|null, setItem: function(string, string): void, removeItem: function(string): void}}
     */
    getStorage() {
      return storage;
    },

    /**
     * Perform an HTTP request via native `fetch`.
     *
     * @param {string} url - Request URL.
     * @param {RequestInit} [options] - Fetch options.
     * @returns {Promise<Response>}
     */
    fetchRaw(url, options = {}) {
      if (typeof globalThis.fetch !== "function") {
        return Promise.reject(new Error("RuntimeContext: fetch API is unavailable"));
      }
      return globalThis.fetch(url, options);
    },

    /**
     * Perform an HTTP request and parse its JSON body, throwing a descriptive `Error` on HTTP error status.
     *
     * @param {string} url - Request URL.
     * @param {RequestInit} [options] - Fetch options.
     * @returns {Promise<any>}
     */
    async fetchJson(url, options = {}) {
      const response = await ctx.fetchRaw(url, options);
      const rawText = await response.text();
      let payload = null;
      if (rawText) {
        try {
          payload = JSON.parse(rawText);
        } catch {
          if (response.ok) {
            throw new SyntaxError(`Invalid JSON response from ${url}`);
          }
        }
      }
      if (!response.ok) {
        const detail =
          (payload && (payload.error || payload.message || payload.detail)) ||
          rawText ||
          `HTTP ${response.status}`;
        const err = new Error(String(detail));
        err.status = response.status;
        err.payload = payload;
        throw err;
      }
      return payload;
    },

    /**
     * Send a JSON `POST` request and parse its JSON response.
     *
     * @param {string} url - Endpoint URL.
     * @param {object} bodyObj - Serializable request payload.
     * @param {RequestInit} [options] - Additional fetch options.
     * @returns {Promise<any>}
     */
    postJson(url, bodyObj, options = {}) {
      const headers = {
        "Content-Type": "application/json",
        ...options.headers,
      };
      return ctx.fetchJson(url, {
        ...options,
        method: options.method || "POST",
        headers,
        body: JSON.stringify(bodyObj ?? {}),
      });
    },

    /**
     * Schedule a callback for the next display refresh frame.
     *
     * @param {FrameRequestCallback} callback - Frame callback.
     * @returns {number} Handle ID.
     */
    requestAnimationFrame(callback) {
      if (typeof globalThis.requestAnimationFrame === "function") {
        return globalThis.requestAnimationFrame(callback);
      }
      return globalThis.setTimeout(() => callback(ctx.nowMs()), DEFAULT_FRAME_DT_MS);
    },

    /**
     * Cancel a scheduled animation frame callback.
     *
     * @param {number} handle - Handle returned by `requestAnimationFrame`.
     */
    cancelAnimationFrame(handle) {
      if (typeof globalThis.cancelAnimationFrame === "function") {
        globalThis.cancelAnimationFrame(handle);
      } else {
        globalThis.clearTimeout(handle);
      }
    },

    /**
     * Schedule a one-shot timer.
     *
     * @param {Function} callback - Timer callback.
     * @param {number} delayMs - Delay in milliseconds.
     * @returns {any} Timer handle.
     */
    setTimeout(callback, delayMs) {
      return globalThis.setTimeout(callback, delayMs);
    },

    /**
     * Cancel a one-shot timer.
     *
     * @param {any} handle - Timer handle.
     */
    clearTimeout(handle) {
      globalThis.clearTimeout(handle);
    },

    /**
     * Schedule a repeating interval timer.
     *
     * @param {Function} callback - Interval callback.
     * @param {number} intervalMs - Period in milliseconds.
     * @returns {any} Interval handle.
     */
    setInterval(callback, intervalMs) {
      return globalThis.setInterval(callback, intervalMs);
    },

    /**
     * Cancel a repeating interval timer.
     *
     * @param {any} handle - Interval handle.
     */
    clearInterval(handle) {
      globalThis.clearInterval(handle);
    },

    /**
     * Return monotonic high-resolution timestamp in milliseconds.
     * @returns {number}
     */
    nowMs() {
      if (globalThis.performance && typeof globalThis.performance.now === "function") {
        return globalThis.performance.now();
      }
      return Date.now();
    },

    /**
     * Return current browser URL location components.
     * @returns {{href: string, pathname: string, search: string, hash: string, origin: string}}
     */
    getLocation() {
      const loc = globalThis.location;
      if (!loc) {
        return {
          href: "http://127.0.0.1/",
          pathname: "/",
          search: "",
          hash: "",
          origin: "http://127.0.0.1",
        };
      }
      return {
        href: loc.href || "",
        pathname: loc.pathname || "/",
        search: loc.search || "",
        hash: loc.hash || "",
        origin: loc.origin || "",
      };
    },

    /**
     * Navigate to `url`.
     * @param {string} url - Destination URL.
     */
    navigate(url) {
      if (globalThis.location) {
        globalThis.location.href = url;
      }
    },

    /**
     * Reload the active document.
     */
    reload() {
      if (globalThis.location && typeof globalThis.location.reload === "function") {
        globalThis.location.reload();
      }
    },

    /**
     * Update URL history state without triggering a full page reload.
     *
     * @param {object} state - History state payload.
     * @param {string} title - Document title string.
     * @param {string} url - Replacement URL.
     */
    replaceHistoryState(state, title, url) {
      if (globalThis.history && typeof globalThis.history.replaceState === "function") {
        globalThis.history.replaceState(state, title, url);
      }
    },

    /**
     * Push a new URL entry onto browser history.
     *
     * @param {object} state - History state payload.
     * @param {string} title - Document title string.
     * @param {string} url - Pushed URL.
     */
    pushHistoryState(state, title, url) {
      if (globalThis.history && typeof globalThis.history.pushState === "function") {
        globalThis.history.pushState(state, title, url);
      }
    },

    /**
     * Open a URL in a secondary tab/window.
     *
     * @param {string} url - Target URL.
     * @param {string} [target] - Window target (`_blank` default).
     */
    openExternalUrl(url, target = "_blank") {
      if (typeof globalThis.open === "function") {
        globalThis.open(url, target, "noopener,noreferrer");
      }
    },

    /**
     * Post a structured message to the parent window when embedded in an `<iframe>`.
     *
     * @param {any} message - Serializable payload.
     * @param {string} [targetOrigin] - Target origin filter.
     */
    postParentMessage(message, targetOrigin = "*") {
      if (
        globalThis.parent &&
        globalThis.parent !== globalThis &&
        typeof globalThis.parent.postMessage === "function"
      ) {
        globalThis.parent.postMessage(message, targetOrigin);
      }
    },

    /**
     * Copy plain text to the system clipboard, falling back to an offscreen `<textarea>`.
     *
     * @param {string} text - Text to copy.
     * @returns {Promise<boolean>} True if copy succeeded.
     */
    async copyTextToClipboard(text) {
      const str = String(text ?? "");
      if (
        globalThis.navigator &&
        globalThis.navigator.clipboard &&
        typeof globalThis.navigator.clipboard.writeText === "function"
      ) {
        try {
          await globalThis.navigator.clipboard.writeText(str);
          return true;
        } catch {
          // Fall through to offscreen textarea fallback.
        }
      }
      const doc = globalThis.document;
      if (!doc || !doc.body) {
        return false;
      }
      const area = doc.createElement("textarea");
      area.value = str;
      area.style.position = "fixed";
      area.style.left = "-999999px";
      area.style.top = "-999999px";
      doc.body.appendChild(area);
      area.focus();
      area.select();
      let copied = false;
      try {
        copied = Boolean(doc.execCommand && doc.execCommand("copy"));
      } catch {
        copied = false;
      } finally {
        area.remove();
      }
      return copied;
    },

    /**
     * Return syntax highlighter (`hljs`) if loaded on the page, or `null`.
     * @returns {object|null}
     */
    getSyntaxHighlighter() {
      return globalThis.hljs ?? null;
    },

    /**
     * Return optional desktop shell bridges (`eel`, `pywebview`).
     * @returns {{eel: object|null, pywebview: object|null}}
     */
    getDesktopBridge() {
      return {
        eel: globalThis.eel ?? null,
        pywebview: globalThis.pywebview ?? null,
      };
    },

    /**
     * Create a DOM element via the active `Document`.
     *
     * @param {string} tagName - HTML tag name.
     * @returns {HTMLElement}
     */
    createElement(tagName) {
      const doc = globalThis.document;
      if (!doc) {
        throw new Error("RuntimeContext.createElement called without an active Document");
      }
      return doc.createElement(tagName);
    },

    /**
     * Create a namespaced DOM element (e.g. SVG).
     *
     * @param {string} namespaceUri - XML namespace URI.
     * @param {string} qualifiedName - Qualified tag name.
     * @returns {Element}
     */
    createElementNS(namespaceUri, qualifiedName) {
      const doc = globalThis.document;
      if (!doc) {
        throw new Error("RuntimeContext.createElementNS called without an active Document");
      }
      return doc.createElementNS(namespaceUri, qualifiedName);
    },

    /**
     * Create an HTML `<canvas>` element with initial pixel dimensions.
     *
     * @param {number} [width] - Initial pixel width.
     * @param {number} [height] - Initial pixel height.
     * @returns {HTMLCanvasElement}
     */
    createCanvas(width = 1, height = 1) {
      const canvas = ctx.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      return canvas;
    },

    /**
     * Trigger a client-side file download for text or binary content.
     *
     * @param {string} filename - Suggested download filename.
     * @param {string|Blob|Uint8Array} content - File payload.
     * @param {string} [mimeType] - Content MIME type.
     */
    triggerDownload(filename, content, mimeType = "text/plain;charset=utf-8") {
      const doc = globalThis.document;
      const urlApi = globalThis.URL;
      if (!doc || !doc.body || !urlApi) {
        return;
      }
      const blob =
        content instanceof globalThis.Blob
          ? content
          : new globalThis.Blob([content], { type: mimeType });
      const objectUrl = urlApi.createObjectURL(blob);
      const anchor = doc.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.style.display = "none";
      doc.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      globalThis.setTimeout(() => urlApi.revokeObjectURL(objectUrl), 1000);
    },

    /**
     * Decode a base64 string into a `Uint8Array` without touching globals in callers.
     *
     * @param {string} base64 - Standard base64 string.
     * @returns {Uint8Array}
     */
    decodeBase64Bytes(base64) {
      const clean = String(base64 || "").trim();
      if (!clean) {
        return new Uint8Array(0);
      }
      if (typeof globalThis.Buffer === "function") {
        const buf = globalThis.Buffer.from(clean, "base64");
        return new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
      }
      const binary = globalThis.atob(clean);
      const bytes = new Uint8Array(binary.length);
      for (let idx = 0; idx < binary.length; idx += 1) {
        bytes[idx] = binary.charCodeAt(idx);
      }
      return bytes;
    },

    /**
     * Create a `WebSocket` connection if supported by the host runtime.
     *
     * @param {string} url - WebSocket `ws://` or `wss://` URL.
     * @returns {WebSocket}
     */
    createWebSocket(url) {
      if (typeof globalThis.WebSocket !== "function") {
        throw new Error("RuntimeContext: WebSocket is unavailable");
      }
      return new globalThis.WebSocket(url);
    },
  };

  return ctx;
}

let sharedBrowserContext = null;

/**
 * Return the singleton production `RuntimeContext` for application entrypoints.
 *
 * @returns {object}
 */
export function getRuntimeContext() {
  if (sharedBrowserContext === null) {
    sharedBrowserContext = createBrowserRuntimeContext();
  }
  return sharedBrowserContext;
}

// =============================================================================
// Deterministic Headless Mock DOM & Mock RuntimeContext for `node --test`
// =============================================================================

/**
 * Minimal `DOMTokenList` implementation for headless unit tests.
 */
class MockClassList {
  constructor(owner) {
    this._owner = owner;
    this._tokens = new Set();
  }

  _syncFromString(str) {
    this._tokens.clear();
    for (const part of String(str || "").split(/\s+/)) {
      if (part) {
        this._tokens.add(part);
      }
    }
  }

  toString() {
    return Array.from(this._tokens).join(" ");
  }

  add(...tokens) {
    for (const token of tokens) {
      if (token) {
        this._tokens.add(token);
      }
    }
  }

  remove(...tokens) {
    for (const token of tokens) {
      this._tokens.delete(token);
    }
  }

  contains(token) {
    return this._tokens.has(token);
  }

  toggle(token, force) {
    if (force === true) {
      this._tokens.add(token);
      return true;
    }
    if (force === false) {
      this._tokens.delete(token);
      return false;
    }
    if (this._tokens.has(token)) {
      this._tokens.delete(token);
      return false;
    }
    this._tokens.add(token);
    return true;
  }
}

/**
 * Create a spy-recording 2D canvas rendering context for headless unit tests.
 *
 * @param {MockElement} canvas - Owning canvas element.
 * @returns {object}
 */
function createMockCanvasContext2D(canvas) {
  const operations = [];
  let currentTransform = [1, 0, 0, 1, 0, 0];
  return {
    canvas,
    operations,
    fillStyle: "#000000",
    strokeStyle: "#000000",
    lineWidth: 1,
    lineCap: "butt",
    lineJoin: "miter",
    font: "10px monospace",
    textAlign: "start",
    textBaseline: "alphabetic",
    globalAlpha: 1,
    getTransform() {
      return [...currentTransform];
    },
    setTransform(a, b, c, d, e, f) {
      currentTransform = [a, b, c, d, e, f];
      operations.push({ op: "setTransform", args: [a, b, c, d, e, f] });
    },
    scale(sx, sy) {
      operations.push({ op: "scale", args: [sx, sy] });
    },
    save() {
      operations.push({ op: "save" });
    },
    restore() {
      operations.push({ op: "restore" });
    },
    clearRect(x, y, w, h) {
      operations.push({ op: "clearRect", args: [x, y, w, h] });
    },
    fillRect(x, y, w, h) {
      operations.push({ op: "fillRect", args: [x, y, w, h], fillStyle: this.fillStyle });
    },
    strokeRect(x, y, w, h) {
      operations.push({ op: "strokeRect", args: [x, y, w, h], strokeStyle: this.strokeStyle });
    },
    beginPath() {
      operations.push({ op: "beginPath" });
    },
    closePath() {
      operations.push({ op: "closePath" });
    },
    moveTo(x, y) {
      operations.push({ op: "moveTo", args: [x, y] });
    },
    lineTo(x, y) {
      operations.push({ op: "lineTo", args: [x, y] });
    },
    arc(x, y, r, sAngle, eAngle, ccw = false) {
      operations.push({ op: "arc", args: [x, y, r, sAngle, eAngle, ccw] });
    },
    roundRect(x, y, w, h, radii) {
      operations.push({ op: "roundRect", args: [x, y, w, h, radii] });
    },
    fill() {
      operations.push({ op: "fill", fillStyle: this.fillStyle });
    },
    stroke() {
      operations.push({ op: "stroke", strokeStyle: this.strokeStyle, lineWidth: this.lineWidth });
    },
    setLineDash(segments) {
      operations.push({ op: "setLineDash", args: [segments] });
    },
    fillText(text, x, y) {
      operations.push({ op: "fillText", text: String(text), x, y, font: this.font });
    },
    strokeText(text, x, y) {
      operations.push({ op: "strokeText", text: String(text), x, y });
    },
    measureText(text) {
      return { width: String(text || "").length * 6.5 };
    },
    drawImage(source, ...rest) {
      operations.push({ op: "drawImage", source, args: rest });
    },
  };
}

/**
 * Lightweight DOM Element for deterministic Node unit testing without jsdom bloat.
 */
export class MockElement {
  /**
   * Construct a `MockElement`.
   *
   * @param {string} tagName - Element tag name.
   * @param {MockDocument|null} ownerDocument - Owning mock document.
   */
  constructor(tagName, ownerDocument = null) {
    this.tagName = String(tagName || "div").toUpperCase();
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.dataset = {};
    this.classList = new MockClassList(this);
    this.listeners = new Map();
    this._id = "";
    this._textContent = "";
    this._innerHTML = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.scrollTop = 0;
    this.scrollHeight = 0;
    this.clientHeight = 480;
    this.clientWidth = 640;
    this.width = 640;
    this.height = 480;
    this._boundingRect = { left: 0, top: 0, width: 640, height: 480, right: 640, bottom: 480 };
    this._pointerCaptures = new Set();
    this._ctx2d = null;

    const styleProps = new Map();
    this.style = new Proxy(
      {
        setProperty(name, val) {
          styleProps.set(name, String(val));
        },
        getPropertyValue(name) {
          return styleProps.get(name) || "";
        },
        removeProperty(name) {
          styleProps.delete(name);
        },
      },
      {
        get(target, prop) {
          if (prop in target) {
            return target[prop];
          }
          return styleProps.get(String(prop)) || "";
        },
        set(target, prop, val) {
          if (prop === "cssText") {
            styleProps.clear();
          }
          styleProps.set(String(prop), String(val));
          return true;
        },
      },
    );
  }

  get id() {
    return this._id;
  }

  set id(val) {
    const next = String(val || "");
    if (this.ownerDocument && this._id) {
      this.ownerDocument._unregisterId(this._id, this);
    }
    this._id = next;
    if (this.ownerDocument && next) {
      this.ownerDocument._registerId(next, this);
    }
  }

  get className() {
    return this.classList.toString();
  }

  set className(val) {
    this.classList._syncFromString(val);
  }

  get textContent() {
    if (this.children.length > 0) {
      return this.children.map((c) => c.textContent).join("");
    }
    return this._textContent;
  }

  set textContent(val) {
    this.children = [];
    this._innerHTML = "";
    this._textContent = String(val ?? "");
  }

  get innerHTML() {
    return this._innerHTML || this._textContent;
  }

  set innerHTML(val) {
    this.children = [];
    this._textContent = "";
    this._innerHTML = String(val ?? "");
  }

  setAttribute(name, value) {
    const strVal = String(value);
    this.attributes.set(name, strVal);
    if (name === "id") {
      this.id = strVal;
    } else if (name === "class") {
      this.className = strVal;
    } else if (name.startsWith("data-")) {
      const camel = name
        .slice(5)
        .replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
      this.dataset[camel] = strVal;
    }
  }

  getAttribute(name) {
    if (name === "id") {
      return this._id || null;
    }
    if (name === "class") {
      return this.className || null;
    }
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.getAttribute(name) !== null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  appendChild(child) {
    if (!child) {
      return child;
    }
    if (child.parentNode) {
      child.remove();
    }
    child.parentNode = this;
    child.ownerDocument = this.ownerDocument;
    this.children.push(child);
    if (this.ownerDocument) {
      this.ownerDocument._registerSubtree(child);
    }
    return child;
  }

  prepend(child) {
    if (!child) {
      return;
    }
    if (child.parentNode) {
      child.remove();
    }
    child.parentNode = this;
    child.ownerDocument = this.ownerDocument;
    this.children.unshift(child);
    if (this.ownerDocument) {
      this.ownerDocument._registerSubtree(child);
    }
  }

  removeChild(child) {
    const idx = this.children.indexOf(child);
    if (idx !== -1) {
      this.children.splice(idx, 1);
      child.parentNode = null;
      if (this.ownerDocument) {
        this.ownerDocument._unregisterSubtree(child);
      }
    }
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(handler);
  }

  removeEventListener(type, handler) {
    const list = this.listeners.get(type);
    if (!list) {
      return;
    }
    const idx = list.indexOf(handler);
    if (idx !== -1) {
      list.splice(idx, 1);
    }
  }

  dispatchEvent(event) {
    const evt = {
      target: this,
      currentTarget: this,
      defaultPrevented: false,
      propagationStopped: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      stopPropagation() {
        this.propagationStopped = true;
      },
      ...event,
    };
    let node = this;
    while (node) {
      evt.currentTarget = node;
      const handlers = node.listeners.get(evt.type);
      if (handlers) {
        for (const fn of handlers.slice()) {
          fn.call(node, evt);
        }
      }
      if (evt.propagationStopped || evt.bubbles === false) {
        break;
      }
      node = node.parentNode;
    }
    return !evt.defaultPrevented;
  }

  click() {
    this.dispatchEvent({ type: "click", bubbles: true });
  }

  focus() {}

  select() {}

  setBoundingClientRect(rect) {
    this._boundingRect = {
      left: rect.left ?? 0,
      top: rect.top ?? 0,
      width: rect.width ?? this.clientWidth,
      height: rect.height ?? this.clientHeight,
      right: (rect.left ?? 0) + (rect.width ?? this.clientWidth),
      bottom: (rect.top ?? 0) + (rect.height ?? this.clientHeight),
    };
  }

  getBoundingClientRect() {
    return { ...this._boundingRect };
  }

  setPointerCapture(pointerId) {
    this._pointerCaptures.add(pointerId);
  }

  hasPointerCapture(pointerId) {
    return this._pointerCaptures.has(pointerId);
  }

  releasePointerCapture(pointerId) {
    this._pointerCaptures.delete(pointerId);
  }

  getContext(contextType) {
    if (contextType === "2d") {
      if (!this._ctx2d) {
        this._ctx2d = createMockCanvasContext2D(this);
      }
      return this._ctx2d;
    }
    return null;
  }

  toDataURL() {
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
  }

  matches(selector) {
    const trimmed = String(selector || "").trim();
    if (!trimmed) {
      return false;
    }
    if (trimmed.startsWith("#")) {
      return this._id === trimmed.slice(1);
    }
    if (trimmed.startsWith(".")) {
      return this.classList.contains(trimmed.slice(1));
    }
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      const inner = trimmed.slice(1, -1);
      const eqIdx = inner.indexOf("=");
      if (eqIdx === -1) {
        return this.hasAttribute(inner);
      }
      const attrName = inner.slice(0, eqIdx).trim();
      const attrVal = inner
        .slice(eqIdx + 1)
        .trim()
        .replace(/^['"]|['"]$/g, "");
      return this.getAttribute(attrName) === attrVal;
    }
    return this.tagName === trimmed.toUpperCase();
  }

  closest(selector) {
    let cur = this;
    while (cur && typeof cur.matches === "function") {
      if (cur.matches(selector)) {
        return cur;
      }
      cur = cur.parentNode;
    }
    return null;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const out = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (child.matches(selector)) {
          out.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return out;
  }
}

/**
 * Lightweight in-memory DOM Document for headless `node --test` suites.
 */
export class MockDocument {
  constructor() {
    this._elementsById = new Map();
    this.documentElement = new MockElement("html", this);
    this.head = new MockElement("head", this);
    this.body = new MockElement("body", this);
    this.documentElement.appendChild(this.head);
    this.documentElement.appendChild(this.body);
    this.readyState = "complete";
    this.title = "";
    this.listeners = new Map();
  }

  _registerId(id, el) {
    this._elementsById.set(id, el);
  }

  _unregisterId(id, el) {
    if (this._elementsById.get(id) === el) {
      this._elementsById.delete(id);
    }
  }

  _registerSubtree(node) {
    node.ownerDocument = this;
    if (node.id) {
      this._registerId(node.id, node);
    }
    for (const child of node.children) {
      this._registerSubtree(child);
    }
  }

  _unregisterSubtree(node) {
    if (node.id) {
      this._unregisterId(node.id, node);
    }
    for (const child of node.children) {
      this._unregisterSubtree(child);
    }
  }

  createElement(tagName) {
    return new MockElement(tagName, this);
  }

  createElementNS(_ns, tagName) {
    return new MockElement(tagName, this);
  }

  getElementById(id) {
    return this._elementsById.get(String(id)) || null;
  }

  querySelector(selector) {
    return this.documentElement.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.documentElement.querySelectorAll(selector);
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(handler);
  }

  removeEventListener(type, handler) {
    const list = this.listeners.get(type);
    if (!list) {
      return;
    }
    const idx = list.indexOf(handler);
    if (idx !== -1) {
      list.splice(idx, 1);
    }
  }

  dispatchEvent(event) {
    const list = this.listeners.get(event.type);
    if (list) {
      for (const fn of list.slice()) {
        fn(event);
      }
    }
  }
}

/**
 * Create a deterministic, zero-globals mock `RuntimeContext` for `node --test`.
 *
 * @param {object} [overrides] - Optional custom config, routes, DPR, viewport, or callbacks.
 * @returns {object} Mock `RuntimeContext` + inspection helpers (`flushAnimationFrames`, `advanceTime`, etc.).
 */
export function createMockRuntimeContext(overrides = {}) {
  const doc = overrides.document || new MockDocument();
  const storage = overrides.storage || createMemoryStorage(overrides.initialStorage || {});
  const viewportListeners = new Map();
  const fetchCalls = [];
  const parentMessages = [];
  const downloads = [];
  const openedUrls = [];
  const historyEntries = [];
  let copiedText = "";
  let clockMs = overrides.initialTimeMs ?? 1000;
  let nextHandleId = 1;
  const rafQueue = new Map();
  const timers = new Map();

  let viewport = {
    width: overrides.viewportWidth ?? DEFAULT_VIEWPORT_WIDTH_PX,
    height: overrides.viewportHeight ?? DEFAULT_VIEWPORT_HEIGHT_PX,
  };
  let dpr = overrides.devicePixelRatio ?? 2.0;
  let currentLocation = {
    href: "http://127.0.0.1:8765/",
    pathname: "/",
    search: "",
    hash: "",
    origin: "http://127.0.0.1:8765",
    ...overrides.location,
  };

  if (overrides.bootConfig !== undefined) {
    const scriptEl = doc.createElement("script");
    scriptEl.id = overrides.bootConfigId || DEFAULT_BOOT_CONFIG_ID;
    scriptEl.setAttribute("type", "application/json");
    scriptEl.textContent =
      typeof overrides.bootConfig === "string"
        ? overrides.bootConfig
        : JSON.stringify(overrides.bootConfig);
    doc.head.appendChild(scriptEl);
  }

  const fetchRoutes = overrides.fetchRoutes || {};

  const mockCtx = {
    getDocument() {
      return doc;
    },

    getBootConfig(elementId = DEFAULT_BOOT_CONFIG_ID) {
      const el = doc.getElementById(elementId);
      if (!el || !el.textContent.trim()) {
        return {};
      }
      return JSON.parse(el.textContent);
    },

    getViewportSize() {
      return { ...viewport };
    },

    setViewportSize(width, height) {
      viewport = { width, height };
      mockCtx.emitViewportEvent("resize", { type: "resize" });
    },

    getDevicePixelRatio() {
      return dpr;
    },

    setDevicePixelRatio(nextDpr) {
      dpr = nextDpr;
    },

    isEmbeddedInFrame() {
      return Boolean(overrides.inIframe);
    },

    addViewportListener(eventType, listener) {
      if (!viewportListeners.has(eventType)) {
        viewportListeners.set(eventType, []);
      }
      viewportListeners.get(eventType).push(listener);
    },

    removeViewportListener(eventType, listener) {
      const list = viewportListeners.get(eventType);
      if (!list) {
        return;
      }
      const idx = list.indexOf(listener);
      if (idx !== -1) {
        list.splice(idx, 1);
      }
    },

    emitViewportEvent(eventType, eventObj = {}) {
      const list = viewportListeners.get(eventType);
      const evt = {
        type: eventType,
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
        ...eventObj,
      };
      if (list) {
        for (const fn of list.slice()) {
          fn(evt);
        }
      }
      return evt;
    },

    getStorage() {
      return storage;
    },

    async fetchRaw(url, options = {}) {
      fetchCalls.push({ url, options });
      if (typeof overrides.fetchHandler === "function") {
        return overrides.fetchHandler(url, options);
      }
      const routeKey = `${(options.method || "GET").toUpperCase()} ${url}`;
      const matched = fetchRoutes[routeKey] !== undefined ? fetchRoutes[routeKey] : fetchRoutes[url];
      if (matched === undefined) {
        return {
          ok: false,
          status: 404,
          async text() {
            return JSON.stringify({ error: `Unmocked route: ${routeKey}` });
          },
          async json() {
            return { error: `Unmocked route: ${routeKey}` };
          },
        };
      }
      const resolved = typeof matched === "function" ? await matched(url, options) : matched;
      const status = resolved && typeof resolved.status === "number" ? resolved.status : 200;
      const bodyPayload =
        resolved && Object.prototype.hasOwnProperty.call(resolved, "body")
          ? resolved.body
          : resolved;
      const textBody =
        typeof bodyPayload === "string" ? bodyPayload : JSON.stringify(bodyPayload);
      return {
        ok: status >= 200 && status < 300,
        status,
        async text() {
          return textBody;
        },
        async json() {
          return JSON.parse(textBody);
        },
      };
    },

    async fetchJson(url, options = {}) {
      const response = await mockCtx.fetchRaw(url, options);
      const rawText = await response.text();
      const payload = rawText ? JSON.parse(rawText) : null;
      if (!response.ok) {
        const err = new Error(
          (payload && (payload.error || payload.message)) || `HTTP ${response.status}`,
        );
        err.status = response.status;
        err.payload = payload;
        throw err;
      }
      return payload;
    },

    postJson(url, bodyObj, options = {}) {
      return mockCtx.fetchJson(url, {
        ...options,
        method: options.method || "POST",
        headers: { "Content-Type": "application/json", ...options.headers },
        body: JSON.stringify(bodyObj ?? {}),
      });
    },

    requestAnimationFrame(callback) {
      const id = nextHandleId;
      nextHandleId += 1;
      rafQueue.set(id, callback);
      return id;
    },

    cancelAnimationFrame(handle) {
      rafQueue.delete(handle);
    },

    flushAnimationFrames(stepMs = DEFAULT_FRAME_DT_MS) {
      const pending = Array.from(rafQueue.entries());
      rafQueue.clear();
      clockMs += stepMs;
      for (const [, cb] of pending) {
        cb(clockMs);
      }
      return pending.length;
    },

    setTimeout(callback, delayMs = 0) {
      const id = nextHandleId;
      nextHandleId += 1;
      timers.set(id, { callback, dueMs: clockMs + Math.max(0, delayMs), intervalMs: null });
      return id;
    },

    clearTimeout(handle) {
      timers.delete(handle);
    },

    setInterval(callback, intervalMs = DEFAULT_FRAME_DT_MS) {
      const id = nextHandleId;
      nextHandleId += 1;
      const period = Math.max(1, intervalMs);
      timers.set(id, { callback, dueMs: clockMs + period, intervalMs: period });
      return id;
    },

    clearInterval(handle) {
      timers.delete(handle);
    },

    advanceTime(deltaMs) {
      const targetTime = clockMs + Math.max(0, deltaMs);
      while (true) {
        let earliestId = null;
        let earliestTimer = null;
        for (const [id, entry] of timers.entries()) {
          if (entry.dueMs <= targetTime) {
            if (!earliestTimer || entry.dueMs < earliestTimer.dueMs) {
              earliestId = id;
              earliestTimer = entry;
            }
          }
        }
        if (!earliestTimer) {
          break;
        }
        clockMs = earliestTimer.dueMs;
        if (earliestTimer.intervalMs !== null) {
          earliestTimer.dueMs = clockMs + earliestTimer.intervalMs;
        } else {
          timers.delete(earliestId);
        }
        earliestTimer.callback();
      }
      clockMs = targetTime;
    },

    nowMs() {
      return clockMs;
    },

    getLocation() {
      return { ...currentLocation };
    },

    navigate(url) {
      currentLocation.href = url;
      historyEntries.push({ action: "navigate", url });
    },

    reload() {
      historyEntries.push({ action: "reload", url: currentLocation.href });
    },

    replaceHistoryState(state, title, url) {
      currentLocation.href = url;
      historyEntries.push({ action: "replace", state, title, url });
    },

    pushHistoryState(state, title, url) {
      currentLocation.href = url;
      historyEntries.push({ action: "push", state, title, url });
    },

    openExternalUrl(url, target = "_blank") {
      openedUrls.push({ url, target });
    },

    postParentMessage(message, targetOrigin = "*") {
      parentMessages.push({ message, targetOrigin });
    },

    async copyTextToClipboard(text) {
      copiedText = String(text ?? "");
      return true;
    },

    getCopiedText() {
      return copiedText;
    },

    getSyntaxHighlighter() {
      return overrides.syntaxHighlighter ?? null;
    },

    getDesktopBridge() {
      return {
        eel: overrides.eel ?? null,
        pywebview: overrides.pywebview ?? null,
      };
    },

    createElement(tagName) {
      return doc.createElement(tagName);
    },

    createElementNS(ns, tagName) {
      return doc.createElementNS(ns, tagName);
    },

    createCanvas(width = 1, height = 1) {
      const c = doc.createElement("canvas");
      c.width = width;
      c.height = height;
      return c;
    },

    triggerDownload(filename, content, mimeType = "text/plain;charset=utf-8") {
      downloads.push({ filename, content, mimeType });
    },

    decodeBase64Bytes(base64) {
      const clean = String(base64 || "").trim();
      if (!clean) {
        return new Uint8Array(0);
      }
      const buf = globalThis.Buffer.from(clean, "base64");
      return new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
    },

    createWebSocket(url) {
      if (typeof overrides.webSocketFactory === "function") {
        return overrides.webSocketFactory(url);
      }
      throw new Error(`Unmocked WebSocket connection: ${url}`);
    },

    fetchCalls,
    parentMessages,
    downloads,
    openedUrls,
    historyEntries,
    rafQueue,
  };

  return mockCtx;
}
