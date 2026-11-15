/**
 * Fast Subsequence & Word-Boundary Fuzzy Search Engine.
 *
 * Shared across Scope component/net search, Forge file-tree & commit search,
 * and `Ctrl+R` reverse CLI history modals in both `hardware` and `firmware`.
 */

const BONUS_CONSECUTIVE = 12;
const BONUS_BOUNDARY = 16;
const BONUS_EXACT_CASE = 3;
const BONUS_PREFIX = 24;
const PENALTY_GAP = -1;
const BASE_CHAR_MATCH = 8;

const BOUNDARY_CHARS = new Set(["/", "\\", "_", "-", ".", ":", " ", "(", "["]);

/**
 * Score `query` against `candidate` using subsequence matching with path/word boundary bonuses.
 *
 * @param {string} query - User search query.
 * @param {string} candidate - Candidate string.
 * @returns {{score: number, indices: Array<number>}|null} Match score and matched character indices, or `null`.
 */
export function fuzzyScore(query, candidate) {
  const cleanQuery = String(query || "").trim();
  const text = String(candidate || "");
  if (!cleanQuery) {
    return { score: 0, indices: [] };
  }
  if (!text) {
    return null;
  }

  const qLower = cleanQuery.toLowerCase();
  const tLower = text.toLowerCase();

  // Fast substring check for contiguous matches
  const substrIdx = tLower.indexOf(qLower);
  if (substrIdx !== -1) {
    const indices = [];
    for (let i = 0; i < qLower.length; i += 1) {
      indices.push(substrIdx + i);
    }
    let score = qLower.length * (BASE_CHAR_MATCH + BONUS_CONSECUTIVE);
    if (substrIdx === 0) {
      score += BONUS_PREFIX;
    } else if (BOUNDARY_CHARS.has(text[substrIdx - 1])) {
      score += BONUS_BOUNDARY;
    }
    score -= Math.min(30, Math.max(0, text.length - qLower.length));
    return { score, indices };
  }

  const indices = [];
  let qIdx = 0;
  let score = 0;
  let prevMatchIdx = -2;

  for (let tIdx = 0; tIdx < text.length && qIdx < qLower.length; tIdx += 1) {
    if (tLower[tIdx] === qLower[qIdx]) {
      indices.push(tIdx);
      score += BASE_CHAR_MATCH;
      if (text[tIdx] === cleanQuery[qIdx]) {
        score += BONUS_EXACT_CASE;
      }
      if (tIdx === 0) {
        score += BONUS_PREFIX;
      } else if (BOUNDARY_CHARS.has(text[tIdx - 1])) {
        score += BONUS_BOUNDARY;
      }
      if (tIdx === prevMatchIdx + 1) {
        score += BONUS_CONSECUTIVE;
      } else if (prevMatchIdx >= 0) {
        score += PENALTY_GAP * Math.min(10, tIdx - prevMatchIdx - 1);
      }
      prevMatchIdx = tIdx;
      qIdx += 1;
    }
  }

  if (qIdx < qLower.length) {
    return null;
  }
  return { score, indices };
}

/**
 * Filter and rank `items` by fuzzy match score against `query`.
 *
 * @template T
 * @param {string} query - Search query string.
 * @param {Array<T>} items - Source candidate items.
 * @param {function(T): string} [getText] - Accessor extracting searchable string from an item.
 * @param {number} [limit] - Optional maximum result count.
 * @returns {Array<{item: T, score: number, indices: Array<number>}>}
 */
export function fuzzyFilterAndRank(
  query,
  items,
  getText = (item) => String(item),
  limit = Infinity,
) {
  if (!Array.isArray(items) || items.length === 0) {
    return [];
  }
  const cleanQuery = String(query || "").trim();
  if (!cleanQuery) {
    return items.slice(0, limit).map((item) => ({ item, score: 0, indices: [] }));
  }

  const scored = [];
  for (const item of items) {
    const candidate = getText(item);
    const res = fuzzyScore(cleanQuery, candidate);
    if (res !== null) {
      scored.push({ item, score: res.score, indices: res.indices });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return Number.isFinite(limit) ? scored.slice(0, limit) : scored;
}
