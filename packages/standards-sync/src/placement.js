// @org/standards-sync — file placement (Plan §11 task 3 + Architecture Upgrade Report §5.3).
//
// Given a populated `stacks/<stackId>/` source directory, produce the consumer-side file
// layout:
//
//   stacks/<stack>/cursor/rules/<rule>.mdc   → <consumer>/.cursor/rules/<rule>.mdc
//   stacks/<stack>/copilot/copilot-instructions.md → <consumer>/.github/copilot-instructions.md
//   stacks/<stack>/claude/CLAUDE.md          → <consumer>/CLAUDE.md
//   stacks/<stack>/junie/AGENTS.md           → <consumer>/.junie/AGENTS.md
//   stacks/<stack>/agents-md/AGENTS.md       → <consumer>/AGENTS.md
//   stacks/<stack>/archunit/*.java           → <consumer>/src/test/java/com/_org/standards/archunit/*.java
//   stacks/<stack>/memory-bank/*.md          → <consumer>/memory-bank/*.md  (only with --with-memory-bank)
//
// The module returns a planned-placements list FIRST (no FS writes); the caller can decide
// to apply, dry-run, or abort. This separation is what makes idempotency detection trivial —
// before writing, the idempotency module compares planned bytes against the manifest's
// recorded checksum.

import { existsSync, readdirSync, statSync, readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

// Each rule below is evaluated in order; missing source subtrees are silently skipped (e.g.,
// the `archunit/` subtree is only emitted for Java stacks, so non-Java sync runs skip it).
const PLACEMENT_RULES = [
  {
    id: "cursor-rules",
    source: "cursor/rules",
    target: ".cursor/rules",
    mode: "directory",
  },
  {
    id: "copilot-instructions",
    source: "copilot/copilot-instructions.md",
    target: ".github/copilot-instructions.md",
    mode: "file",
  },
  {
    id: "claude-md",
    source: "claude/CLAUDE.md",
    target: "CLAUDE.md",
    mode: "file",
  },
  {
    id: "junie-agents-md",
    source: "junie/AGENTS.md",
    target: ".junie/AGENTS.md",
    mode: "file",
  },
  {
    id: "agents-md",
    source: "agents-md/AGENTS.md",
    target: "AGENTS.md",
    mode: "file",
  },
  {
    id: "archunit-java",
    source: "archunit",
    target: "src/test/java/com/_org/standards/archunit",
    mode: "directory",
    optionalIfMissing: true,
  },
  {
    id: "memory-bank",
    source: "memory-bank",
    target: "memory-bank",
    mode: "directory",
    requiresFlag: "withMemoryBank",
  },
];

export function planPlacements({ stackRoot, projectDir, options = {} }) {
  const placements = [];
  const skipped = [];

  for (const rule of PLACEMENT_RULES) {
    if (rule.requiresFlag && !options[rule.requiresFlag]) {
      skipped.push({
        ruleId: rule.id,
        reason: `Skipped: requires --${_kebab(rule.requiresFlag)} flag (opt-in).`,
      });
      continue;
    }
    const sourceAbs = path.join(stackRoot, rule.source);
    if (!existsSync(sourceAbs)) {
      if (rule.optionalIfMissing) {
        skipped.push({
          ruleId: rule.id,
          reason: `Skipped: source path ${rule.source} not present in this stack's dist tree.`,
        });
        continue;
      }
      skipped.push({
        ruleId: rule.id,
        reason: `Skipped: source path ${rule.source} missing in stack tree (this is unusual — file an issue).`,
      });
      continue;
    }
    if (rule.mode === "file") {
      placements.push({
        ruleId: rule.id,
        sourceAbs,
        sourceRel: rule.source,
        targetAbs: path.join(projectDir, rule.target),
        targetRel: rule.target,
      });
    } else if (rule.mode === "directory") {
      for (const entry of _walkFiles(sourceAbs)) {
        const rel = path.relative(sourceAbs, entry);
        placements.push({
          ruleId: rule.id,
          sourceAbs: entry,
          sourceRel: path.join(rule.source, rel),
          targetAbs: path.join(projectDir, rule.target, rel),
          targetRel: path.join(rule.target, rel),
        });
      }
    } else {
      throw new Error(`Internal error: unknown placement mode ${rule.mode}`);
    }
  }

  return { placements, skipped };
}

export async function applyPlacements(placements, { dryRun = false, logger } = {}) {
  const applied = [];
  for (const p of placements) {
    if (dryRun) {
      logger?.debug(`(dry-run) would write ${p.targetRel}`);
      applied.push({ ...p, action: "would-write" });
      continue;
    }
    await mkdir(path.dirname(p.targetAbs), { recursive: true });
    const bytes = readFileSync(p.sourceAbs);
    await writeFile(p.targetAbs, bytes);
    applied.push({ ...p, action: "wrote" });
  }
  return applied;
}

function _walkFiles(root) {
  const out = [];
  const stack = [root];
  while (stack.length > 0) {
    const dir = stack.pop();
    for (const entry of readdirSync(dir)) {
      const full = path.join(dir, entry);
      const st = statSync(full);
      if (st.isDirectory()) stack.push(full);
      else if (st.isFile()) out.push(full);
    }
  }
  return out.sort();
}

// camelCase → kebab-case. e.g., `withMemoryBank` → `with-memory-bank`.
function _kebab(str) {
  return str.replace(/[A-Z]/g, (m, i) => (i === 0 ? "" : "-") + m.toLowerCase());
}
