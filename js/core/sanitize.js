/**
 * Author Identity Redaction & HTML Sanitization Utilities.
 *
 * Enforces Workspace Rule 6: Zero Personal Name & Email Leaks across all
 * client-side VCS, Code Review, Issue Tracker, and Daemon workstation views.
 */

const RESERVED_IDENTIFIERS = new Set([
  "user",
  "system",
  "anonymous",
  "root",
  "bot",
  "author",
  "committer",
  "reviewer",
  "admin",
  "null",
  "undefined",
  "workspace",
  "nobody",
]);

const DEFAULT_REDACTED_NAME = "User";
const DEFAULT_REDACTED_EMAIL = "user@workspace";
const DEFAULT_REDACTED_COMBINED = "User <user@workspace>";
const EMAIL_BRACKET_PATTERN = /^(.*?)\s*<([^>]+)>$/;

/**
 * Redact personal author names, handles, and email addresses to `User` / `user@workspace`.
 *
 * @param {string|null|undefined} rawAuthor - Raw author/committer name or `Name <email>`.
 * @param {Array<string>} [blacklist] - Optional list of dynamic tokens to redact.
 * @returns {string} Sanitized author string.
 */
export function sanitizeAuthor(rawAuthor, blacklist = []) {
  if (!rawAuthor || typeof rawAuthor !== "string") {
    return DEFAULT_REDACTED_NAME;
  }
  const trimmed = rawAuthor.trim();
  if (!trimmed) {
    return DEFAULT_REDACTED_NAME;
  }

  if (EMAIL_BRACKET_PATTERN.test(trimmed)) {
    return DEFAULT_REDACTED_COMBINED;
  }

  if (trimmed.includes("@")) {
    return DEFAULT_REDACTED_EMAIL;
  }

  const lower = trimmed.toLowerCase();
  if (Array.isArray(blacklist)) {
    for (const token of blacklist) {
      if (token && lower.includes(String(token).toLowerCase())) {
        return DEFAULT_REDACTED_NAME;
      }
    }
  }

  if (RESERVED_IDENTIFIERS.has(lower)) {
    return trimmed;
  }

  return DEFAULT_REDACTED_NAME;
}

/**
 * Redact any occurrence of dynamic `author_blacklist` tokens inside arbitrary text.
 *
 * @param {string|null|undefined} text - Input text (commit message, log line, etc.).
 * @param {Array<string>} [blacklist] - Case-insensitive personal tokens to scrub.
 * @returns {string} Sanitized text.
 */
export function sanitizeTextWithBlacklist(text, blacklist = []) {
  if (text === null || text === undefined) {
    return "";
  }
  let output = String(text);
  if (!Array.isArray(blacklist) || blacklist.length === 0) {
    return output;
  }
  for (const rawToken of blacklist) {
    const token = String(rawToken || "").trim();
    if (token.length < 2) {
      continue;
    }
    const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const replacement = token.includes("@") ? DEFAULT_REDACTED_EMAIL : DEFAULT_REDACTED_NAME;
    output = output.replace(new RegExp(escaped, "gi"), replacement);
  }
  return output;
}

/**
 * Escape `&`, `<`, `>`, `"`, and `'` for safe HTML text interpolation.
 *
 * @param {any} value - Value to escape.
 * @returns {string} HTML-safe string.
 */
export function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
