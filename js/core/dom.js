/**
 * Zero-globals DOM query, construction, and delegated event helpers.
 */

/**
 * Resolve an element reference or string element ID via `ctx.getDocument()`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string|null|undefined} elOrId - Element handle or DOM `id`.
 * @returns {Element|null}
 */
export function resolveElement(ctx, elOrId) {
  if (!elOrId) {
    return null;
  }
  if (typeof elOrId === "string") {
    const doc = ctx.getDocument();
    return doc ? doc.getElementById(elOrId) : null;
  }
  return elOrId;
}

/**
 * Query a required descendant selector or throw a descriptive `Error`.
 *
 * @param {Element|Document} root - Parent container or document.
 * @param {string} selector - CSS selector.
 * @returns {Element}
 */
export function queryRequired(root, selector) {
  const found = root ? root.querySelector(selector) : null;
  if (!found) {
    throw new Error(`Required DOM element not found for selector: ${selector}`);
  }
  return found;
}

/**
 * Query all matching elements as a standard `Array` (safe for `.filter()` / `.map()` on browser `NodeList`s).
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} selector - CSS selector.
 * @param {Element|Document|null} [root] - Optional root container (defaults to `ctx.getDocument()`).
 * @returns {Element[]}
 */
export function queryAll(ctx, selector, root = null) {
  const target = root || (ctx && typeof ctx.getDocument === "function" ? ctx.getDocument() : null);
  if (!target || typeof target.querySelectorAll !== "function") {
    return [];
  }
  return Array.from(target.querySelectorAll(selector));
}

/**
 * Remove all child nodes from `element`.
 *
 * @param {Element|null} element - Target container.
 */
export function clearChildren(element) {
  if (!element) {
    return;
  }
  element.textContent = "";
}

/**
 * Declaratively construct a DOM element via `ctx.createElement()` with zero inline HTML strings.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} tagName - HTML tag name.
 * @param {object} [options] - Optional attributes, classes, dataset, styles, listeners, and children.
 * @returns {HTMLElement}
 */
export function createEl(ctx, tagName, options = {}) {
  const el = ctx.createElement(tagName);
  if (options.id) {
    el.id = options.id;
  }
  if (options.className) {
    el.className = options.className;
  }
  if (options.text !== undefined) {
    el.textContent = String(options.text);
  }
  if (options.attrs) {
    for (const [attrName, attrVal] of Object.entries(options.attrs)) {
      if (attrVal !== undefined && attrVal !== null && attrVal !== false) {
        el.setAttribute(attrName, attrVal === true ? "" : String(attrVal));
      }
    }
  }
  if (options.dataset) {
    for (const [dataKey, dataVal] of Object.entries(options.dataset)) {
      if (dataVal !== undefined && dataVal !== null) {
        const attrKey = `data-${dataKey.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}`;
        el.setAttribute(attrKey, String(dataVal));
      }
    }
  }
  if (options.style) {
    for (const [propName, propVal] of Object.entries(options.style)) {
      if (propVal !== undefined && propVal !== null) {
        if (propName.startsWith("--")) {
          el.style.setProperty(propName, String(propVal));
        } else {
          el.style[propName] = String(propVal);
        }
      }
    }
  }
  if (options.on) {
    for (const [evtName, handler] of Object.entries(options.on)) {
      if (typeof handler === "function") {
        el.addEventListener(evtName, handler);
      }
    }
  }
  if (Array.isArray(options.children)) {
    for (const child of options.children) {
      if (child !== null && child !== undefined && child !== false) {
        if (typeof child === "string") {
          const span = ctx.createElement("span");
          span.textContent = child;
          el.appendChild(span);
        } else {
          el.appendChild(child);
        }
      }
    }
  }
  return el;
}

/**
 * Attach a delegated event listener matching `selector` via `.closest(selector)`.
 *
 * Replaces legacy inline `onclick="..."` HTML attributes cleanly.
 *
 * @param {Element} container - Delegating root container.
 * @param {string} eventType - DOM event type (e.g. `"click"`, `"change"`).
 * @param {string} selector - CSS selector to match against `event.target.closest(selector)`.
 * @param {function(Event, Element): void} handler - Invoked with `(event, matchedElement)`.
 * @returns {function(): void} Unsubscribe callback.
 */
export function bindDelegatedEvent(container, eventType, selector, handler) {
  if (!container) {
    return () => {};
  }
  const listener = (event) => {
    const rawTarget = event.target;
    const target =
      rawTarget && typeof rawTarget.closest === "function"
        ? rawTarget
        : rawTarget &&
            rawTarget.parentElement &&
            typeof rawTarget.parentElement.closest === "function"
          ? rawTarget.parentElement
          : null;
    if (!target) {
      return;
    }
    const matched = target.closest(selector);
    if (matched) {
      handler(event, matched);
    }
  };
  container.addEventListener(eventType, listener);
  return () => container.removeEventListener(eventType, listener);
}

/**
 * Apply `.in-iframe` to `<html>` and `<body>` when hosted inside an embedded modal frame.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @returns {boolean} True if embedded in an iframe.
 */
export function applyIframeContextClass(ctx) {
  const embedded = ctx.isEmbeddedInFrame();
  const doc = ctx.getDocument();
  if (embedded && doc) {
    if (doc.documentElement) {
      doc.documentElement.classList.add("in-iframe");
    }
    if (doc.body) {
      doc.body.classList.add("in-iframe");
    }
  }
  return embedded;
}
