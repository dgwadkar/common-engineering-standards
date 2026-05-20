// @org/standards-sync — minimal semver range matcher.
//
// Mirrors the semver-range grammar that `compiler/core/stack_filter.py` accepts:
//
//   * Bare:          "3.0.0", "3.0", "3"
//   * Comparator:    ">=3.0", "<=2.7.18", ">3.0", "<4.0", "=3.2.0"
//   * Caret:         "^2.7.0"          → ">=2.7.0 <3.0.0"
//   * Tilde:         "~3.1"            → ">=3.1.0 <3.2.0"
//   * Conjunction:   ">=2.0 <4.0"      (whitespace-separated AND)
//
// We re-implement here (rather than depending on the `semver` npm package) to keep the
// runtime-dependency footprint small. The Python side has its own implementation; the
// Phase-8 acceptance test suite verifies parity on the indicator ranges in
// `schemas/stacks.json`.

const COMPARATOR_RE = /^(>=|<=|>|<|=|~|\^)?\s*(\d+(?:\.\d+){0,2})$/;

export function parseVersion(input) {
  if (typeof input !== "string") throw new TypeError("version must be a string");
  // Strip a leading "v" if present (GitHub tag names) and any pre-release/build suffix.
  const cleaned = input.trim().replace(/^v/i, "").split(/[-+]/, 1)[0];
  const parts = cleaned.split(".");
  if (parts.length < 1 || parts.length > 3) {
    throw new Error(`Cannot parse version ${JSON.stringify(input)}: expected 1-3 dotted parts.`);
  }
  const triple = [0, 0, 0];
  for (let i = 0; i < parts.length; i++) {
    const n = Number(parts[i]);
    if (!Number.isInteger(n) || n < 0) {
      throw new Error(`Cannot parse version ${JSON.stringify(input)}: non-numeric component.`);
    }
    triple[i] = n;
  }
  return triple;
}

function cmp(a, b) {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

function expandComparator(token) {
  const m = COMPARATOR_RE.exec(token);
  if (!m) throw new Error(`Unparseable range token: ${JSON.stringify(token)}`);
  const op = m[1] || "=";
  const ver = parseVersion(m[2]);
  const [major, minor, patch] = ver;
  if (op === "^") {
    let upper;
    if (major > 0) upper = [major + 1, 0, 0];
    else if (minor > 0) upper = [major, minor + 1, 0];
    else upper = [major, minor, patch + 1];
    return [[">=", ver], ["<", upper]];
  }
  if (op === "~") {
    // Tilde with only major (e.g., "~3") matches the entire major like "^3"; with two or
    // more parts ("~3.1" or "~3.1.0") it locks the minor.
    if (m[2].split(".").length === 1) {
      return [[">=", [major, 0, 0]], ["<", [major + 1, 0, 0]]];
    }
    return [[">=", ver], ["<", [major, minor + 1, 0]]];
  }
  return [[op, ver]];
}

function matchPrimitive(target, op, ref) {
  const c = cmp(target, ref);
  if (op === "=") return c === 0;
  if (op === ">=") return c >= 0;
  if (op === "<=") return c <= 0;
  if (op === ">") return c > 0;
  if (op === "<") return c < 0;
  throw new Error(`Unknown comparator: ${op}`);
}

export function satisfies(version, range) {
  const target = parseVersion(version);
  const tokens = range.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true; // empty range matches anything
  for (const tok of tokens) {
    for (const [op, ref] of expandComparator(tok)) {
      if (!matchPrimitive(target, op, ref)) return false;
    }
  }
  return true;
}
