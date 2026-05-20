// Placement-planner unit tests (Plan §11 task 3).

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync } from "node:fs";
import path from "node:path";

import { planPlacements, applyPlacements } from "../src/placement.js";
import { mkTempProject, rmDir, FILE_TMP_ROOT, ensureTmpRoot, DIST_DIR } from "./_helpers.js";

const STACK_ROOT = path.join(DIST_DIR, "stacks", "java-spring-boot-3");

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

test("planPlacements maps each dist subtree to its consumer location (Architecture §5.3)", () => {
  const project = mkTempProject("plan-sb3");
  const { placements, skipped } = planPlacements({ stackRoot: STACK_ROOT, projectDir: project });
  const targets = placements.map((p) => p.targetRel).sort();

  // Spot-check the five concrete contract paths from §5.3.
  assert.ok(targets.includes(".github/copilot-instructions.md"));
  assert.ok(targets.includes(".junie/AGENTS.md"));
  assert.ok(targets.includes("AGENTS.md"));
  assert.ok(targets.includes("CLAUDE.md"));
  assert.ok(targets.some((t) => t.startsWith(".cursor/rules/") && t.endsWith(".mdc")));

  // Memory Bank is opt-in and therefore skipped by default.
  const memSkip = skipped.find((s) => s.ruleId === "memory-bank");
  assert.ok(memSkip);
  assert.match(memSkip.reason, /--with-memory-bank/);
});

test("--with-memory-bank includes the six-file Memory Bank scaffold", () => {
  const project = mkTempProject("plan-with-mb");
  const { placements } = planPlacements({
    stackRoot: STACK_ROOT,
    projectDir: project,
    options: { withMemoryBank: true },
  });
  const memTargets = placements.filter((p) => p.ruleId === "memory-bank").map((p) => p.targetRel);
  assert.equal(memTargets.length, 6, `expected 6 memory-bank files; got ${memTargets.join(",")}`);
  for (const f of [
    "memory-bank/activeContext.md",
    "memory-bank/productContext.md",
    "memory-bank/progress.md",
    "memory-bank/projectbrief.md",
    "memory-bank/systemPatterns.md",
    "memory-bank/techContext.md",
  ]) {
    assert.ok(memTargets.includes(f), `missing ${f}`);
  }
});

test("missing archunit/ subtree is silently skipped (optionalIfMissing)", () => {
  // The Spring Boot 3 dist tree currently does not include archunit/ — Phase-6 carry-over.
  // The planner must report it as a friendly skip, not an error.
  const project = mkTempProject("plan-no-archunit");
  const { skipped } = planPlacements({ stackRoot: STACK_ROOT, projectDir: project });
  const archSkip = skipped.find((s) => s.ruleId === "archunit-java");
  assert.ok(archSkip);
  assert.match(archSkip.reason, /archunit/);
});

test("applyPlacements actually writes every planned file to disk", async () => {
  const project = mkTempProject("apply-files");
  const { placements } = planPlacements({ stackRoot: STACK_ROOT, projectDir: project });
  await applyPlacements(placements, { dryRun: false });
  for (const p of placements) {
    assert.ok(existsSync(p.targetAbs), `${p.targetRel} should exist`);
  }
  // Cursor MDC files should land under .cursor/rules with the expected count.
  const cursorDir = path.join(project, ".cursor", "rules");
  const mdcs = readdirSync(cursorDir).filter((f) => f.endsWith(".mdc"));
  assert.ok(mdcs.length >= 17, `expected ≥17 cursor MDCs for spring-boot-3, got ${mdcs.length}`);
});

test("applyPlacements with dryRun: true writes nothing", async () => {
  const project = mkTempProject("apply-dryrun");
  const { placements } = planPlacements({ stackRoot: STACK_ROOT, projectDir: project });
  await applyPlacements(placements, { dryRun: true });
  for (const p of placements) {
    assert.ok(!existsSync(p.targetAbs), `${p.targetRel} should NOT exist after dry-run`);
  }
});
