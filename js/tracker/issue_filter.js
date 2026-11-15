/**
 * Issue Filtering, Sorting, Metrics, and Badge Formatting Utilities.
 *
 * Shared zero-globals implementation for both Hardware Bug Tracker (`BUG-*`)
 * and Firmware Xerxes Worm Matrix (`WORM-*`).
 */

export const SEVERITY_ORDER = Object.freeze({
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
});

export const STATUS_ORDER = Object.freeze({
  OPEN: 0,
  IN_PROGRESS: 1,
  PLANNED: 2,
  RESOLVED: 3,
  CLOSED: 4,
});

/**
 * Parse a tracker UTC timestamp string into comparable epoch milliseconds or raw string.
 *
 * @param {string|undefined|null} raw - Timestamp string such as `"2026-11-12 20:00:00 UTC"`.
 * @returns {number|string}
 */
export function parseIssueTimestamp(raw) {
  if (!raw || typeof raw !== "string") {
    return "";
  }
  const normalized = raw.replace(" UTC", "Z");
  const parsed = Date.parse(normalized);
  return Number.isNaN(parsed) ? raw : parsed;
}

/**
 * Extract trailing or embedded numeric sequence from an issue ID for deterministic fallback sorting.
 *
 * @param {string|undefined|null} id - Issue identifier.
 * @returns {number}
 */
function extractNumericId(id) {
  const digits = String(id || "").replace(/\D/g, "");
  return Number.parseInt(digits, 10) || 0;
}

/**
 * Filter and sort an array of tracker issues (bugs or worms).
 *
 * @param {Array<object>} issues - Raw array of issue objects.
 * @param {object} [options] - Filter & sort criteria.
 * @param {string} [options.statusFilter="open"] - `"open" | "planned" | "resolved" | "all"`.
 * @param {string} [options.categoryFilter="ALL"] - Category name or `"ALL"`.
 * @param {string} [options.severityFilter="ALL"] - Severity level or `"ALL"`.
 * @param {string} [options.query=""] - Case-insensitive substring query across ID, title, and component.
 * @param {string} [options.sortBy="id_desc"] - `"id_desc" | "id_asc" | "severity" | "status" | "component" | "title"`.
 * @returns {Array<object>} Filtered and sorted shallow copy.
 */
export function filterAndSortIssues(issues, options = {}) {
  const list = Array.isArray(issues) ? issues : [];
  const statusFilter = options.statusFilter || "open";
  const categoryFilter = options.categoryFilter || "ALL";
  const severityFilter = options.severityFilter || "ALL";
  const query = String(options.query || "").trim().toLowerCase();
  const sortBy = options.sortBy || "id_desc";

  const filtered = list.filter((issue) => {
    if (!issue) {
      return false;
    }
    const status = String(issue.status || "OPEN");
    if (statusFilter === "open" && (status === "CLOSED" || status === "PLANNED")) {
      return false;
    }
    if (statusFilter === "planned" && status !== "PLANNED") {
      return false;
    }
    if (statusFilter === "resolved" && status !== "RESOLVED" && status !== "CLOSED") {
      return false;
    }
    if (categoryFilter && categoryFilter !== "ALL" && issue.category !== categoryFilter) {
      return false;
    }
    if (severityFilter && severityFilter !== "ALL" && issue.severity !== severityFilter) {
      return false;
    }
    if (query) {
      const title = String(issue.title || "").toLowerCase();
      const id = String(issue.id || "").toLowerCase();
      const comp = String(issue.component || "").toLowerCase();
      if (!title.includes(query) && !id.includes(query) && !comp.includes(query)) {
        return false;
      }
    }
    return true;
  });

  filtered.sort((a, b) => {
    switch (sortBy) {
      case "id_asc": {
        const timeA = parseIssueTimestamp(a.created_at);
        const timeB = parseIssueTimestamp(b.created_at);
        if (timeA && timeB && timeA !== timeB) {
          return timeA < timeB ? -1 : 1;
        }
        if (timeA && !timeB) return -1;
        if (!timeA && timeB) return 1;
        const numA = extractNumericId(a.id);
        const numB = extractNumericId(b.id);
        if (numA !== numB) return numA - numB;
        return String(a.id || "").localeCompare(String(b.id || ""));
      }
      case "id_desc": {
        const timeA = parseIssueTimestamp(a.created_at);
        const timeB = parseIssueTimestamp(b.created_at);
        if (timeA && timeB && timeA !== timeB) {
          return timeA > timeB ? -1 : 1;
        }
        if (timeA && !timeB) return -1;
        if (!timeA && timeB) return 1;
        const numA = extractNumericId(a.id);
        const numB = extractNumericId(b.id);
        if (numA !== numB) return numB - numA;
        return String(b.id || "").localeCompare(String(a.id || ""));
      }
      case "severity": {
        const rankA = SEVERITY_ORDER[a.severity] ?? 99;
        const rankB = SEVERITY_ORDER[b.severity] ?? 99;
        if (rankA !== rankB) return rankA - rankB;
        const timeA = parseIssueTimestamp(a.created_at);
        const timeB = parseIssueTimestamp(b.created_at);
        if (timeA && timeB && timeA !== timeB) return timeA > timeB ? -1 : 1;
        return String(b.id || "").localeCompare(String(a.id || ""));
      }
      case "status": {
        const rankA = STATUS_ORDER[a.status] ?? 99;
        const rankB = STATUS_ORDER[b.status] ?? 99;
        if (rankA !== rankB) return rankA - rankB;
        const timeA = parseIssueTimestamp(a.created_at);
        const timeB = parseIssueTimestamp(b.created_at);
        if (timeA && timeB && timeA !== timeB) return timeA > timeB ? -1 : 1;
        return String(b.id || "").localeCompare(String(a.id || ""));
      }
      case "component": {
        return String(a.component || "")
          .toLowerCase()
          .localeCompare(String(b.component || "").toLowerCase());
      }
      case "title": {
        return String(a.title || "")
          .toLowerCase()
          .localeCompare(String(b.title || "").toLowerCase());
      }
      default:
        return 0;
    }
  });

  return filtered;
}

/**
 * Compute aggregate header pill counts (`total`, `open`, `resolved`).
 *
 * @param {Array<object>} issues - Tracker items.
 * @returns {{ total: number, open: number, resolved: number }}
 */
export function computeIssueMetrics(issues) {
  const list = Array.isArray(issues) ? issues : [];
  let open = 0;
  let resolved = 0;
  for (const item of list) {
    if (!item) continue;
    if (item.status === "OPEN" || item.status === "IN_PROGRESS") {
      open += 1;
    } else if (item.status === "RESOLVED" || item.status === "CLOSED") {
      resolved += 1;
    }
  }
  return { total: list.length, open, resolved };
}

/**
 * Extract sorted unique component names from tracker issues.
 *
 * @param {Array<object>} issues - Tracker items.
 * @returns {Array<string>}
 */
export function extractUniqueComponents(issues) {
  const list = Array.isArray(issues) ? issues : [];
  const seen = new Set();
  for (const item of list) {
    if (item && typeof item.component === "string") {
      const trimmed = item.component.trim();
      if (trimmed) {
        seen.add(trimmed);
      }
    }
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b));
}

/**
 * Resolve CSS badge classes for an issue severity level.
 *
 * @param {string} severity - Severity string.
 * @returns {string}
 */
export function getSeverityBadgeClass(severity) {
  switch (severity) {
    case "CRITICAL":
      return "quake-badge quake-badge-red";
    case "HIGH":
      return "quake-badge quake-badge-amber";
    case "MEDIUM":
      return "quake-badge quake-badge-gold";
    default:
      return "quake-badge quake-badge-muted";
  }
}

/**
 * Resolve CSS badge class and display text for an issue status.
 *
 * @param {string} status - Status string.
 * @returns {{ badgeClass: string, label: string }}
 */
export function getStatusBadgeInfo(status) {
  switch (status) {
    case "RESOLVED":
      return { badgeClass: "quake-badge quake-badge-gold", label: "AWAITING REVIEW" };
    case "CLOSED":
      return { badgeClass: "quake-badge quake-badge-green", label: "CLOSED" };
    case "PLANNED":
      return { badgeClass: "quake-badge quake-badge-muted", label: "PLANNED" };
    default:
      return { badgeClass: "quake-badge quake-badge-amber", label: status || "OPEN" };
  }
}
