// End-to-end sync tests — drives the public `sync()` API against every Phase-6 fixture
// using the workspace's `dist/` tree as the dist source. These are the tests that prove
// the three Plan §11 acceptance criteria.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, writeFileSync, cpSync } from "node:fs";
import path from "node:path";

import { sync, SYNC_OUTCOMES } from "../src/index.js";
import { createRecordingLogger } from "../src/logger.js";
import {
  copyFixtureManifest,
  mkTempProject,
  rmDir,
  FILE_TMP_ROOT,
  ensureTmpRoot,
  DIST_DIR,
} from "./_helpers.js";

const COMMON_OPTS = {
  localDist: DIST_DIR,
  logger: createRecordingLogger(),
};

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

// -----------------------------------------------------------------------------------
// AC1: Architecture Upgrade Report §5.3 file layout against the spring-boot-3-2 fixture
// -----------------------------------------------------------------------------------

test("AC1: spring-boot-3-2 fixture produces the §5.3 file layout (excluding opt-in scaffolds)", async () => {
  const project = mkTempProject("ac1-sb3");
  copyFixtureManifest("spring-boot-3-2", project);

  const result = await sync({ projectDir: project, ...COMMON_OPTS });
  assert.equal(result.outcome, SYNC_OUTCOMES.Synced);
  assert.equal(result.detection.stackId, "java-spring-boot-3");

  // The §5.3 layout: every path below MUST exist.
  for (const p of [
    ".github/copilot-instructions.md",
    ".junie/AGENTS.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".standards-sync-manifest.json",
  ]) {
    assert.ok(
      existsSync(path.join(project, p)),
      `AC1: ${p} should exist after sync`,
    );
  }
  // Cursor MDC files: spring-boot-3 has 17 applicable rules per the Phase-6 golden tree.
  const mdcs = readdirSync(path.join(project, ".cursor", "rules"))
    .filter((f) => f.endsWith(".mdc"))
    .sort();
  assert.equal(mdcs.length, 17, `Expected 17 cursor MDCs for spring-boot-3, got ${mdcs.length}`);

  // The §5.3 sample names specific MDC filenames — spot-check a few.
  for (const expected of [
    "controller-validation-boundaries.mdc",
    "service-transactional-boundaries.mdc",
    "repository-n-plus-one-prevention.mdc",
    "_global-clean-architecture.mdc",
  ]) {
    assert.ok(mdcs.includes(expected), `AC1: ${expected} should be present`);
  }

  // The Memory Bank scaffold is OPT-IN per Plan §11 task 3 — it should NOT be present by default.
  assert.ok(
    !existsSync(path.join(project, "memory-bank")),
    "AC1: memory-bank/ should NOT exist without --with-memory-bank",
  );
});

test("AC1 (opt-in): --with-memory-bank scaffolds the six canonical files", async () => {
  const project = mkTempProject("ac1-sb3-mb");
  copyFixtureManifest("spring-boot-3-2", project);

  await sync({ projectDir: project, withMemoryBank: true, ...COMMON_OPTS });
  for (const f of [
    "memory-bank/activeContext.md",
    "memory-bank/productContext.md",
    "memory-bank/progress.md",
    "memory-bank/projectbrief.md",
    "memory-bank/systemPatterns.md",
    "memory-bank/techContext.md",
  ]) {
    assert.ok(existsSync(path.join(project, f)), `${f} should exist with --with-memory-bank`);
  }
});

// -----------------------------------------------------------------------------------
// AC2: zero git-diff on consecutive re-runs
// -----------------------------------------------------------------------------------

test("AC2: two consecutive sync runs leave every file byte-for-byte identical", async () => {
  const project = mkTempProject("ac2-rerun");
  copyFixtureManifest("spring-boot-3-2", project);

  // First sync.
  const first = await sync({ projectDir: project, ...COMMON_OPTS });
  assert.equal(first.outcome, SYNC_OUTCOMES.Synced);

  // Snapshot every file under the project.
  const snapshot = _snapshotDir(project);

  // Second sync.
  const second = await sync({ projectDir: project, ...COMMON_OPTS });
  assert.equal(
    second.outcome,
    SYNC_OUTCOMES.SyncedNoChanges,
    "second sync should report no changes",
  );

  // Compare snapshots — must be IDENTICAL (zero diff, including the manifest).
  const after2 = _snapshotDir(project);
  assert.deepEqual(
    after2,
    snapshot,
    "AC2: re-sync changed at least one file (see snapshot diff)",
  );
});

test("AC2 (same fixture, different fixture): swapping the manifest WITHOUT a version bump still produces a no-op on identical content", async () => {
  // Sanity guard against accidental cross-stack state leakage.
  const projectA = mkTempProject("ac2-sanityA");
  const projectB = mkTempProject("ac2-sanityB");
  copyFixtureManifest("nestjs-10", projectA);
  copyFixtureManifest("nestjs-10", projectB);
  await sync({ projectDir: projectA, ...COMMON_OPTS });
  await sync({ projectDir: projectB, ...COMMON_OPTS });
  const snapA = _snapshotDir(projectA, /pom\.xml|package\.json|pyproject\.toml/);
  const snapB = _snapshotDir(projectB, /pom\.xml|package\.json|pyproject\.toml/);
  // Both NestJS-10 projects should produce identical synced files (the manifest itself may
  // differ in `syncedAt` because they synced at different moments, so exclude the manifest).
  const stripManifest = (snap) => {
    const out = { ...snap };
    delete out[".standards-sync-manifest.json"];
    return out;
  };
  assert.deepEqual(stripManifest(snapA), stripManifest(snapB));
});

// -----------------------------------------------------------------------------------
// AC3: a non-supported stack emits a clear message and exits 0
// -----------------------------------------------------------------------------------

test("AC3: a Rails-only project (Gemfile) returns NoApplicableStack with exit 0", async () => {
  const project = mkTempProject("ac3-rails");
  writeFileSync(
    path.join(project, "Gemfile"),
    'source "https://rubygems.org"\ngem "rails", "~> 7.0"\n',
  );
  const result = await sync({ projectDir: project, ...COMMON_OPTS });
  assert.equal(result.outcome, SYNC_OUTCOMES.NoApplicableStack);
  assert.equal(result.exitCode, 0);
  assert.match(result.report, /No applicable stack found/);
  // No files should have been written.
  assert.ok(!existsSync(path.join(project, "AGENTS.md")));
  assert.ok(!existsSync(path.join(project, ".cursor")));
  assert.ok(!existsSync(path.join(project, ".standards-sync-manifest.json")));
});

// -----------------------------------------------------------------------------------
// Cross-stack coverage — every fixture syncs cleanly
// -----------------------------------------------------------------------------------

const FIXTURE_TO_STACK = {
  "spring-boot-3-2": "java-spring-boot-3",
  "spring-boot-2-7-legacy": "java-spring-boot-2",
  "nestjs-10": "typescript-nestjs-10",
  "fastapi-0-110": "python-fastapi-0-110",
};

for (const [fixture, expectedStackId] of Object.entries(FIXTURE_TO_STACK)) {
  test(`fixture ${fixture} → stack ${expectedStackId}, sync succeeds, AGENTS.md is present`, async () => {
    const project = mkTempProject(`xs-${fixture}`);
    copyFixtureManifest(fixture, project);
    const result = await sync({ projectDir: project, ...COMMON_OPTS });
    assert.equal(result.outcome, SYNC_OUTCOMES.Synced);
    assert.equal(result.detection.stackId, expectedStackId);
    assert.ok(
      existsSync(path.join(project, "AGENTS.md")),
      "every supported stack should ship a root AGENTS.md",
    );
    // The cursor rules count must equal the golden tree's count (Phase-6 invariant).
    // We don't pin exact numbers here to avoid coupling to corpus growth — but each
    // stack must have ≥ 1 cursor rule.
    const cursorDir = path.join(project, ".cursor", "rules");
    assert.ok(existsSync(cursorDir), `${expectedStackId}: .cursor/rules should exist`);
    assert.ok(
      readdirSync(cursorDir).filter((f) => f.endsWith(".mdc")).length >= 1,
      `${expectedStackId}: at least one cursor MDC should ship`,
    );
  });
}

// -----------------------------------------------------------------------------------
// Manual-edit detection — block without --force, accept with --force
// -----------------------------------------------------------------------------------

test("manual edit detected: sync blocks without --force and conflict is reported", async () => {
  const project = mkTempProject("manual-edit");
  copyFixtureManifest("spring-boot-3-2", project);
  await sync({ projectDir: project, ...COMMON_OPTS });

  // Manually edit AGENTS.md.
  const agentsPath = path.join(project, "AGENTS.md");
  writeFileSync(agentsPath, "I edited this manually!\n");

  const result = await sync({ projectDir: project, ...COMMON_OPTS });
  assert.equal(result.outcome, SYNC_OUTCOMES.ManualEditsBlocked);
  assert.ok(result.conflicts.length >= 1);
  const conflict = result.conflicts.find((c) => c.targetRel === "AGENTS.md");
  assert.ok(conflict, "AGENTS.md should be in the conflicts list");
  assert.match(conflict.reason, /manually edited/);
  // The on-disk file MUST still be the manual content — the sync did NOT overwrite it.
  assert.equal(readFileSync(agentsPath, "utf8"), "I edited this manually!\n");
});

test("--force overrides manual-edit conflicts and re-installs the standard content", async () => {
  const project = mkTempProject("manual-edit-force");
  copyFixtureManifest("spring-boot-3-2", project);
  await sync({ projectDir: project, ...COMMON_OPTS });

  const agentsPath = path.join(project, "AGENTS.md");
  const original = readFileSync(agentsPath, "utf8");
  writeFileSync(agentsPath, "MANUAL EDIT\n");

  const result = await sync({ projectDir: project, force: true, ...COMMON_OPTS });
  assert.equal(result.outcome, SYNC_OUTCOMES.Synced);
  assert.equal(readFileSync(agentsPath, "utf8"), original);
});

// -----------------------------------------------------------------------------------
// Dry-run — plans but writes nothing
// -----------------------------------------------------------------------------------

test("--dry-run produces the report without writing any consumer files", async () => {
  const project = mkTempProject("dryrun");
  copyFixtureManifest("spring-boot-3-2", project);

  const result = await sync({ projectDir: project, dryRun: true, ...COMMON_OPTS });
  assert.equal(result.outcome, SYNC_OUTCOMES.DryRun);
  assert.ok(!existsSync(path.join(project, "AGENTS.md")));
  assert.ok(!existsSync(path.join(project, ".cursor")));
  assert.ok(!existsSync(path.join(project, ".standards-sync-manifest.json")));
  // The report should still describe what would have happened.
  assert.match(result.report, /Mode.*dry-run/);
});

// -----------------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------------

function _snapshotDir(dir, excludeBasenameRegex = null) {
  const map = {};
  const stack = [dir];
  while (stack.length > 0) {
    const cur = stack.pop();
    for (const entry of readdirSync(cur, { withFileTypes: true })) {
      const full = path.join(cur, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      const rel = path.relative(dir, full);
      if (excludeBasenameRegex && excludeBasenameRegex.test(rel)) continue;
      map[rel] = readFileSync(full).toString("hex");
    }
  }
  return map;
}
