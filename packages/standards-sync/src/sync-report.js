// @org/standards-sync — sync report (Plan §11 task 5).
//
// Renders a single Markdown summary covering:
//
//   * Stack detected (with the rationale string from detect-stack.js).
//   * Version resolved (with source — explicit / pinned / floating).
//   * Per-rule counts (cursor mdcs copied, copilot file copied, ...).
//   * Skipped rules with reasons.
//   * Files whose glob would match no consumer source (warning surface — for example, a
//     repository-layer rule installed into a project with no `repository/` package).
//
// The report can either be returned as a string (CLI prints it to stdout) or written to
// `<consumer>/standards-sync-report.md`. The CLI invokes the renderer once at the end of
// every run; the caller decides where it lands.

import { existsSync, readdirSync, statSync, readFileSync } from "node:fs";
import path from "node:path";

// Minimal MDC frontmatter parser — extracts the `globs:` field as an array of strings.
// We don't need the full YAML grammar; the compiler emits MDC frontmatter in a fixed shape.
function _readMdcGlobs(mdcPath) {
  let text;
  try {
    text = readFileSync(mdcPath, "utf8");
  } catch {
    return [];
  }
  // Frontmatter is delimited by leading "---\n" and trailing "\n---\n".
  if (!text.startsWith("---\n")) return [];
  const end = text.indexOf("\n---\n", 4);
  if (end < 0) return [];
  const fm = text.slice(4, end);
  // Look for `globs: ["...", "..."]` on its own line.
  const m = fm.match(/^globs:\s*(.+)$/m);
  if (!m) return [];
  const value = m[1].trim();
  // Compact YAML list (Cursor MDC convention).
  if (value.startsWith("[") && value.endsWith("]")) {
    try {
      return JSON.parse(value.replace(/'/g, '"'));
    } catch {
      return [];
    }
  }
  return [];
}

function _matchesAnyFile(glob, projectDir) {
  // Compile a very small glob → regex translator. We support `**`, `*`, and `?` because
  // the compiler emits only those — no character classes, no brace expansion. If a future
  // rule introduces extended syntax, swap this for the `picomatch` library.
  const re = _globToRegex(glob);
  const stack = [projectDir];
  // Skip a few canonical directories that aren't application source.
  const SKIP_DIRS = new Set([
    "node_modules",
    ".git",
    "target",
    "build",
    "dist",
    "out",
    ".gradle",
    ".idea",
    "venv",
    ".venv",
    "__pycache__",
    ".cursor",
    ".github",
    ".junie",
    "memory-bank",
  ]);
  let visited = 0;
  const MAX_VISIT = 5000; // hard cap so we never traverse a 1M-file monorepo
  while (stack.length > 0 && visited < MAX_VISIT) {
    const dir = stack.pop();
    let entries;
    try {
      entries = readdirSync(dir);
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (SKIP_DIRS.has(entry)) continue;
      const full = path.join(dir, entry);
      let st;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      visited++;
      if (st.isDirectory()) {
        stack.push(full);
        continue;
      }
      const rel = path.relative(projectDir, full);
      if (re.test(rel) || re.test("/" + rel)) return true;
    }
  }
  return false;
}

function _globToRegex(glob) {
  let re = "";
  let i = 0;
  while (i < glob.length) {
    const ch = glob[i];
    if (ch === "*" && glob[i + 1] === "*") {
      re += ".*";
      i += 2;
      if (glob[i] === "/") i++;
    } else if (ch === "*") {
      re += "[^/]*";
      i++;
    } else if (ch === "?") {
      re += ".";
      i++;
    } else if (ch === ".") {
      re += "\\.";
      i++;
    } else if (ch === "/") {
      re += "/";
      i++;
    } else if (/[A-Za-z0-9_-]/.test(ch)) {
      re += ch;
      i++;
    } else {
      re += "\\" + ch;
      i++;
    }
  }
  return new RegExp("^" + re + "$");
}

// Render the sync report. `state` is the assembled result from a sync run.
export function renderSyncReport(state) {
  const lines = [];
  lines.push("# Standards Sync Report");
  lines.push("");
  lines.push(`- **Generated**: ${state.generatedAt}`);
  lines.push(`- **Project**: \`${state.projectDir}\``);
  lines.push(`- **Stack detected**: \`${state.stackId}\``);
  if (state.detectedVersion) {
    lines.push(`- **Manifest version**: \`${state.detectedVersion}\` (from \`${state.manifestFile}\`)`);
  }
  lines.push(`- **Standards version**: \`${state.version}\` (resolution: ${state.versionSource})`);
  lines.push(`- **Dist source**: ${state.distSource}`);
  if (state.dryRun) lines.push(`- **Mode**: dry-run (no files were written)`);
  lines.push("");
  lines.push("## Stack detection rationale");
  lines.push("");
  lines.push("```");
  lines.push(state.detectionRationale);
  lines.push("```");
  lines.push("");

  lines.push("## Files synced");
  lines.push("");
  if (state.summary.length === 0) {
    lines.push("_No files were synced._");
  } else {
    lines.push("| Rule | Wrote | Identical (no-op) | Changed | Added |");
    lines.push("| --- | --: | --: | --: | --: |");
    for (const row of state.summary) {
      lines.push(
        `| \`${row.ruleId}\` | ${row.wrote} | ${row.identical} | ${row.changed} | ${row.added} |`,
      );
    }
  }
  lines.push("");

  if (state.skippedRules.length > 0) {
    lines.push("## Skipped rules");
    lines.push("");
    for (const sk of state.skippedRules) {
      lines.push(`- \`${sk.ruleId}\` — ${sk.reason}`);
    }
    lines.push("");
  }

  if (state.unmatchedGlobs && state.unmatchedGlobs.length > 0) {
    lines.push("## Warnings — Cursor rules whose globs match zero consumer files");
    lines.push("");
    lines.push(
      "The following rules were installed but their `globs:` patterns do not match any " +
        "file in your project. Either the rule is genuinely irrelevant to this repository " +
        "(safe to ignore) or you may be missing a layer (e.g., no `repository/` package).",
    );
    lines.push("");
    for (const w of state.unmatchedGlobs) {
      lines.push(`- \`${w.rule}\` — globs: ${w.globs.map((g) => `\`${g}\``).join(", ")}`);
    }
    lines.push("");
  }

  if (state.conflicts && state.conflicts.length > 0) {
    lines.push("## Manual-edit conflicts");
    lines.push("");
    lines.push("The following files were edited locally since the last sync. They were NOT overwritten.");
    lines.push("Re-run with `--force` to overwrite (your edits will be lost).");
    lines.push("");
    for (const c of state.conflicts) {
      const lsv = c.lastSyncedVersion ? `last-synced=${c.lastSyncedVersion}` : "untracked";
      lines.push(`- \`${c.targetRel}\` (${c.reason}; ${lsv})`);
    }
    lines.push("");
  }

  lines.push("## Next steps");
  lines.push("");
  if (state.conflicts && state.conflicts.length > 0) {
    lines.push("1. Review the manual-edit conflicts above.");
    lines.push("2. If your edits should stay: leave them; the sync skipped those files.");
    lines.push("3. If the standards version's content should win: re-run with `--force`.");
  } else if (state.dryRun) {
    lines.push("1. Review the planned writes above.");
    lines.push("2. Re-run WITHOUT `--dry-run` to apply.");
  } else {
    lines.push("1. Commit the synced files alongside `.standards-version` (or set the file from this report).");
    lines.push("2. Optionally add `.standards-sync-manifest.json` to `.gitignore` (or commit it for auditability).");
    lines.push("3. Re-run the sync after a release bump (see project changelog).");
  }
  lines.push("");
  return lines.join("\n");
}

// Compute per-rule placement summary counts.
export function summarisePlacements({ placements, classification }) {
  const buckets = new Map();
  const get = (id) =>
    buckets.get(id) || buckets.set(id, { ruleId: id, wrote: 0, identical: 0, changed: 0, added: 0 }).get(id);
  // Build target → ruleId map.
  const targetToRule = new Map(placements.map((p) => [p.targetRel, p.ruleId]));
  const seen = new Set();
  for (const f of classification.identical) {
    const ruleId = targetToRule.get(f.targetRel) || "unknown";
    const row = get(ruleId);
    row.identical += 1;
    row.wrote += 1; // identical re-writes still happen on disk (same bytes → no git diff)
    seen.add(f.targetRel);
  }
  for (const f of classification.wouldChange) {
    const ruleId = targetToRule.get(f.targetRel) || "unknown";
    const row = get(ruleId);
    row.changed += 1;
    row.wrote += 1;
    seen.add(f.targetRel);
  }
  for (const f of classification.wouldAdd) {
    const ruleId = targetToRule.get(f.targetRel) || "unknown";
    const row = get(ruleId);
    row.added += 1;
    row.wrote += 1;
    seen.add(f.targetRel);
  }
  // Anything in `conflicts` is NOT in wrote — explicitly count zero for that row.
  for (const c of classification.conflicts) {
    if (seen.has(c.targetRel)) continue;
    const ruleId = targetToRule.get(c.targetRel) || "unknown";
    get(ruleId); // initialise row
  }
  return Array.from(buckets.values()).sort((a, b) => a.ruleId.localeCompare(b.ruleId));
}

// Walk the cursor MDC files we just installed and return any rule whose globs match no
// consumer files. Best-effort and capped at 5000 entries to keep large monorepos snappy.
export function findUnmatchedGlobs({ projectDir, stackRoot }) {
  const rulesDir = path.join(stackRoot, "cursor", "rules");
  if (!existsSync(rulesDir)) return [];
  const warnings = [];
  for (const entry of readdirSync(rulesDir).sort()) {
    if (!entry.endsWith(".mdc")) continue;
    const globs = _readMdcGlobs(path.join(rulesDir, entry));
    if (globs.length === 0) continue; // alwaysApply or agent-requested mode — no globs to check
    const matched = globs.some((g) => _matchesAnyFile(g, projectDir));
    if (!matched) {
      warnings.push({ rule: entry.replace(/\.mdc$/, ""), globs });
    }
  }
  return warnings;
}
