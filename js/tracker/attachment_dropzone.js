/**
 * Zero-Globals Attachment Grid, Pure ES2024 Base64 Encoder, & Drag/Drop/Paste Uploader.
 *
 * Avoids `FileReader`, `btoa`, `Buffer`, and `navigator.clipboard` globals by reading
 * `Blob.prototype.arrayBuffer()` into `Uint8Array` and encoding directly in ES2024.
 */

import { bindDelegatedEvent, clearChildren, createEl, resolveElement } from "../core/dom.js";
import { showToast } from "../core/toast.js";

export const MAX_ATTACHMENT_SIZE_BYTES = 2 * 1024 * 1024 * 1024; // 2 GiB GitHub LFS limit

const BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const IMAGE_EXT_RE = /\.(png|jpg|jpeg|gif|svg|webp)$/i;
const DOC_EXT_RE = /\.(pdf|txt|log|json|yaml|yml|md|csv)$/i;
const GENERIC_PASTE_NAMES = new Set(["image.png", "blob", "screenshot.png"]);

/**
 * Encode a `Uint8Array` (or `ArrayBuffer`) into a standard Base64 string without globals.
 *
 * @param {Uint8Array|ArrayBuffer} input - Raw binary bytes.
 * @returns {string} Base64-encoded string.
 */
export function encodeBytesToBase64(input) {
  const bytes =
    input instanceof Uint8Array
      ? input
      : input instanceof ArrayBuffer
        ? new Uint8Array(input)
        : new Uint8Array(0);
  const len = bytes.length;
  if (len === 0) {
    return "";
  }

  const chunks = [];
  let i = 0;
  for (; i + 2 < len; i += 3) {
    const triplet = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    chunks.push(
      BASE64_CHARS[(triplet >> 18) & 63] +
        BASE64_CHARS[(triplet >> 12) & 63] +
        BASE64_CHARS[(triplet >> 6) & 63] +
        BASE64_CHARS[triplet & 63],
    );
  }

  const remaining = len - i;
  if (remaining === 1) {
    const val = bytes[i];
    chunks.push(
      BASE64_CHARS[(val >> 2) & 63] + BASE64_CHARS[(val & 3) << 4] + "==",
    );
  } else if (remaining === 2) {
    const val = (bytes[i] << 8) | bytes[i + 1];
    chunks.push(
      BASE64_CHARS[(val >> 10) & 63] +
        BASE64_CHARS[(val >> 4) & 63] +
        BASE64_CHARS[(val & 15) << 2] +
        "=",
    );
  }

  return chunks.join("");
}

/**
 * Classify an attachment filename or MIME type into `"screenshot"`, `"document"`, or `"reference"`.
 *
 * @param {string} filename - File name.
 * @param {string} [mimeType=""] - Optional MIME type.
 * @returns {string}
 */
export function classifyAttachmentType(filename, mimeType = "") {
  const lower = String(filename || "").toLowerCase();
  const mime = String(mimeType || "").toLowerCase();
  if (IMAGE_EXT_RE.test(lower) || mime.startsWith("image/")) {
    return "screenshot";
  }
  if (DOC_EXT_RE.test(lower) || mime === "application/pdf" || mime.startsWith("text/")) {
    return "document";
  }
  return "reference";
}

/**
 * Format byte size into human-readable `"KB"` or `"B"` label.
 *
 * @param {number|undefined} sizeBytes - File byte count.
 * @returns {string}
 */
export function formatAttachmentSize(sizeBytes) {
  if (!sizeBytes || sizeBytes <= 0) {
    return "";
  }
  return sizeBytes > 1024 ? `${Math.round(sizeBytes / 1024)} KB` : `${sizeBytes} B`;
}

/**
 * Render attachment cards into `#attachments-grid` and wire Remove delegation.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} gridElOrId - Grid container or ID.
 * @param {Array<object>} attachments - Attachment objects `{ filename, file_path, file_type, size_bytes, created_at }`.
 * @param {function(number): void} [onRemove] - Callback invoked with attachment index on removal.
 */
export function renderAttachmentsGrid(ctx, gridElOrId, attachments, onRemove) {
  const grid = resolveElement(ctx, gridElOrId);
  if (!grid) {
    return;
  }
  clearChildren(grid);

  if (typeof onRemove === "function") {
    grid._onRemoveAttachment = onRemove;
    if (!grid.dataset?.boundAttachments) {
      if (grid.dataset) {
        grid.dataset.boundAttachments = "1";
      }
      bindDelegatedEvent(grid, "click", '[data-action="remove-attachment"]', (_ev, btn) => {
        const idx = Number.parseInt(btn.dataset?.index || "-1", 10);
        if (idx >= 0 && typeof grid._onRemoveAttachment === "function") {
          grid._onRemoveAttachment(idx);
        }
      });
    }
  }

  const list = Array.isArray(attachments) ? attachments : [];
  for (let idx = 0; idx < list.length; idx += 1) {
    const att = list[idx];
    if (!att) continue;
    const filename = String(att.filename || "attachment");
    const filePath = String(att.file_path || "").replace(/^\/+/, "");
    const lower = filename.toLowerCase();
    const isImg = IMAGE_EXT_RE.test(lower);
    const isPdf = lower.endsWith(".pdf");
    const stamp = encodeURIComponent(att.created_at || String(ctx.nowMs()));

    const card = createEl(ctx, "div", { className: "attachment-card" });
    if (isImg) {
      const link = createEl(ctx, "a", {
        attrs: {
          href: `/${filePath}`,
          target: "_blank",
          rel: "noopener noreferrer",
        },
        children: [
          createEl(ctx, "img", {
            className: "attachment-preview",
            attrs: {
              src: `/${filePath}?t=${stamp}`,
              alt: filename,
            },
          }),
        ],
      });
      card.appendChild(link);
    } else {
      const icon = isPdf ? "📕" : "📄";
      const docTypeLabel = isPdf
        ? "PDF DOCUMENT"
        : att.file_type
          ? String(att.file_type).toUpperCase()
          : "DOCUMENT";
      const link = createEl(ctx, "a", {
        attrs: {
          href: `/${filePath}`,
          target: "_blank",
          rel: "noopener noreferrer",
        },
        style: { textDecoration: "none" },
        children: [
          createEl(ctx, "div", {
            className: "document-preview-box",
            children: [
              createEl(ctx, "div", { className: "doc-icon", text: icon }),
              createEl(ctx, "div", { className: "doc-type", text: docTypeLabel }),
            ],
          }),
        ],
      });
      card.appendChild(link);
    }

    card.appendChild(
      createEl(ctx, "div", {
        className: "attachment-name",
        text: filename,
        attrs: { title: filename },
      }),
    );
    card.appendChild(
      createEl(ctx, "div", {
        className: "attachment-footer",
        children: [
          createEl(ctx, "span", { text: formatAttachmentSize(att.size_bytes) }),
          createEl(ctx, "button", {
            className: "quake-btn quake-btn-red",
            text: "Remove",
            attrs: { type: "button" },
            dataset: { action: "remove-attachment", index: String(idx) },
            style: { fontSize: "9.5px", padding: "2px 6px" },
          }),
        ],
      }),
    );
    grid.appendChild(card);
  }
}

/**
 * Read a `File` / `Blob` (or mock file object `{ name, size, type, arrayBuffer }`) and emit an upload payload.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} file - Browser `File`/`Blob` or mock file object.
 * @param {object} options - `{ isPaste, getActiveId, entityIdParam, onUploadPayload }`.
 * @returns {Promise<any>}
 */
export async function processFileForUpload(ctx, file, options = {}) {
  if (!file) {
    return null;
  }
  const rawName = String(file.name || "");
  const mimeType = String(file.type || "");
  const fileSize = Number(file.size || 0);

  if (fileSize >= MAX_ATTACHMENT_SIZE_BYTES) {
    showToast(
      ctx,
      `Error: ${rawName || "Attachment"} exceeds maximum allowed size of 2 GB (GitHub LFS limit).`,
      "error",
      5000,
    );
    return null;
  }

  let bytes;
  if (typeof file.arrayBuffer === "function") {
    const ab = await file.arrayBuffer();
    bytes = ab instanceof Uint8Array ? ab : new Uint8Array(ab);
  } else if (file.bytes instanceof Uint8Array) {
    bytes = file.bytes;
  } else {
    bytes = new Uint8Array(0);
  }

  const contentBase64 = encodeBytesToBase64(bytes);
  const fileType = classifyAttachmentType(rawName, mimeType);
  const isGeneric = !rawName || GENERIC_PASTE_NAMES.has(rawName.toLowerCase());
  let targetName = rawName;
  if (options.isPaste || isGeneric) {
    const randSuffix = Math.random().toString(36).slice(2, 7);
    const extMatch = rawName.toLowerCase().match(IMAGE_EXT_RE);
    const ext = extMatch ? extMatch[0] : fileType === "screenshot" ? ".png" : ".txt";
    const prefix = fileType === "screenshot" ? "screenshot_paste" : "doc_paste";
    targetName = `${prefix}_${ctx.nowMs()}_${randSuffix}${ext}`;
  }

  const payload = {
    filename: targetName,
    file_type: fileType,
    content_base64: contentBase64,
    description: `${options.isPaste ? "Pasted" : "Uploaded"} ${fileType} ${targetName}`,
  };
  const activeId = typeof options.getActiveId === "function" ? options.getActiveId() : "";
  const idKey = options.entityIdParam || "bug_id";
  if (activeId) {
    payload[idKey] = activeId;
  }

  if (typeof options.onUploadPayload === "function") {
    return options.onUploadPayload(payload);
  }
  return payload;
}

/**
 * Bind drag-and-drop, file input picker, browse/paste buttons, and document-level paste listeners.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {object} options - `{ dropzoneId, fileInputId, getActiveId, entityIdParam, onUploadPayload }`.
 */
export function bindAttachmentDropzone(ctx, options = {}) {
  const doc = ctx.getDocument();
  if (!doc) {
    return;
  }
  const dropzone = doc.getElementById(options.dropzoneId || "dropzone");
  const fileInput =
    doc.getElementById(options.fileInputId || "file-upload") ||
    doc.getElementById("file-input");

  const handleFileCollection = async (files, isPaste = false) => {
    if (!files || !files.length) {
      return;
    }
    for (const file of Array.from(files)) {
      await processFileForUpload(ctx, file, { ...options, isPaste });
    }
  };

  const uploadTextSnippet = async (text, filenamePrefix = "clipboard_text") => {
    const content = String(text || "");
    if (!content.trim()) {
      return;
    }
    if (content.length >= MAX_ATTACHMENT_SIZE_BYTES) {
      showToast(ctx, "Error: Document exceeds maximum allowed size of 2 GB.", "error", 5000);
      return;
    }
    const filename = `${filenamePrefix}_${ctx.nowMs()}.txt`;
    const payload = {
      filename,
      file_type: "document",
      content_text: content,
      description: "Pasted text document",
    };
    const activeId = typeof options.getActiveId === "function" ? options.getActiveId() : "";
    const idKey = options.entityIdParam || "bug_id";
    if (activeId) {
      payload[idKey] = activeId;
    }
    if (typeof options.onUploadPayload === "function") {
      await options.onUploadPayload(payload);
    }
  };

  if (dropzone) {
    dropzone.addEventListener("click", (ev) => {
      if (fileInput && ev.target !== fileInput) {
        fileInput.click();
      }
    });
    dropzone.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", (ev) => {
      ev.preventDefault();
      dropzone.classList.remove("dragover");
      const files = ev.dataTransfer?.files;
      if (files && files.length > 0) {
        void handleFileCollection(files, false);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        void handleFileCollection(fileInput.files, false);
        fileInput.value = "";
      }
    });
  }

  const browseBtns = doc.querySelectorAll('[data-action="browse-files"]');
  for (const btn of browseBtns) {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (fileInput) {
        fileInput.click();
      }
    });
  }

  const pasteBtns = doc.querySelectorAll('[data-action="paste-clipboard"]');
  for (const btn of pasteBtns) {
    btn.addEventListener("click", () => {
      if (dropzone && typeof dropzone.focus === "function") {
        dropzone.focus();
      }
      showToast(ctx, "Press ⌘V / Ctrl+V to paste screenshot or document from clipboard", "info");
    });
  }

  doc.addEventListener("paste", (ev) => {
    const activeElem = doc.activeElement;
    const tag = String(activeElem?.tagName || "").toUpperCase();
    const isTextInput = tag === "INPUT" || tag === "TEXTAREA";
    const clip = ev.clipboardData;
    if (!clip) {
      return;
    }
    const hasFiles = clip.files && clip.files.length > 0;

    if (isTextInput && !hasFiles) {
      const inAttachments =
        typeof activeElem?.closest === "function" &&
        Boolean(activeElem.closest("#attachments-section"));
      if (inAttachments) {
        ev.preventDefault();
        const pastedText = typeof clip.getData === "function" ? clip.getData("text") : "";
        if (pastedText && pastedText.trim()) {
          void uploadTextSnippet(pastedText, "clipboard_doc");
        }
      }
      return;
    }

    if (hasFiles) {
      ev.preventDefault();
      void handleFileCollection(clip.files, true);
      return;
    }

    if (clip.items) {
      const extracted = [];
      for (const item of Array.from(clip.items)) {
        if (item && item.kind === "file" && typeof item.getAsFile === "function") {
          const blob = item.getAsFile();
          if (blob) {
            extracted.push(blob);
          }
        }
      }
      if (extracted.length > 0) {
        ev.preventDefault();
        void handleFileCollection(extracted, true);
        return;
      }
    }

    const pastedText = typeof clip.getData === "function" ? clip.getData("text") : "";
    if (pastedText && pastedText.trim() && (!isTextInput || activeElem?.id === "dropzone")) {
      ev.preventDefault();
      void uploadTextSnippet(pastedText, "clipboard_text");
    }
  });
}
