// Idempotency tests (Plan §11 task 4) — checksum-based manual-edit detection.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

import {
  sha256OfFile,
  classifyPlacements,
  planShas,
  writeManifest,
  readManifest,
  MANIFEST_FILENAME,
} from "../src/idempotency.js";
import { mkTempProject, rmDir, FILE_TMP_ROOT, ensureTmpRoot } from "./_helpers.js";

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

function fakePlacements(projectDir, files) {
  // Build a placements array with files whose source bytes are predictable.
  return files.map(({ targetRel, content }) => {
    // Write the "source" file under a sibling tmp dir to keep the API honest.
    const sourceAbs = path.join(projectDir, "__sources__", targetRel);
    return {
      ruleId: "test",
      sourceAbs,
      sourceRel: `__sources__/${targetRel}`,
      targetAbs: path.join(projectDir, targetRel),
      targetRel,
      // We'll synthesise the source files below.
      _content: content,
    };
  });
}

function materialiseSources(placements) {
  for (const p of placements) {
    mkdirSync(path.dirname(p.sourceAbs), { recursive: true });
    writeFileSync(p.sourceAbs, p._content);
  }
}

test("sha256OfFile is stable and matches the canonical hash", () => {
  const project = mkTempProject("sha-basic");
  const f = path.join(project, "x.txt");
  writeFileSync(f, "hello");
  const sha = sha256OfFile(f);
  // sha256 of "hello"
  assert.equal(
    sha,
    "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
  );
});

test("classifyPlacements: missing files go to wouldAdd", () => {
  const project = mkTempProject("classify-add");
  const placements = fakePlacements(project, [{ targetRel: "AGENTS.md", content: "new\n" }]);
  // Don't write the target — only the source.
  mkdirSync(path.dirname(placements[0].sourceAbs), { recursive: true });
  writeFileSync(placements[0].sourceAbs, placements[0]._content);
  const plannedShas = planShas(placements);

  const cls = classifyPlacements(placements, { projectDir: project, manifest: null, plannedShas });
  assert.equal(cls.wouldAdd.length, 1);
  assert.equal(cls.wouldChange.length, 0);
  assert.equal(cls.identical.length, 0);
  assert.equal(cls.conflicts.length, 0);
});

test("classifyPlacements: identical content recognises no-op", () => {
  const project = mkTempProject("classify-identical");
  const placements = fakePlacements(project, [{ targetRel: "AGENTS.md", content: "same\n" }]);
  materialiseSources(placements);
  // Write the target with the same content.
  writeFileSync(placements[0].targetAbs, "same\n");
  const plannedShas = planShas(placements);

  // No manifest yet, but the bytes match — should classify as identical (no-op).
  const cls = classifyPlacements(placements, { projectDir: project, manifest: null, plannedShas });
  assert.equal(cls.identical.length, 1);
  assert.equal(cls.conflicts.length, 0);
});

test("classifyPlacements: differing content with manifest mismatch → conflict", async () => {
  const project = mkTempProject("classify-conflict");
  const placements = fakePlacements(project, [{ targetRel: "AGENTS.md", content: "v2\n" }]);
  materialiseSources(placements);
  // First sync: write target as the v1 content + persist manifest tracking the v1 sha.
  writeFileSync(placements[0].targetAbs, "v1-original\n");
  // Build a fake manifest as if a prior sync had written v1-original and recorded its sha.
  const v1Sha = createHash("sha256").update("v1-original\n").digest("hex");
  const manifest = {
    schemaVersion: 1,
    syncedVersion: "v0.1.0",
    stackId: "java-spring-boot-3",
    files: {
      "AGENTS.md": {
        sha256: v1Sha,
        sourceRel: "agents-md/AGENTS.md",
        ruleId: "agents-md",
        lastSyncedVersion: "v0.1.0",
      },
    },
  };
  // Now the user has manually edited the file (target now contains "v1-MANUAL\n").
  writeFileSync(placements[0].targetAbs, "v1-MANUAL\n");
  const plannedShas = planShas(placements);
  const cls = classifyPlacements(placements, { projectDir: project, manifest, plannedShas });
  assert.equal(cls.conflicts.length, 1);
  assert.equal(cls.conflicts[0].lastSyncedVersion, "v0.1.0");
  assert.match(cls.conflicts[0].reason, /manually edited/);
});

test("classifyPlacements: pristine file that needs an update → wouldChange (not conflict)", () => {
  const project = mkTempProject("classify-change");
  const placements = fakePlacements(project, [{ targetRel: "AGENTS.md", content: "v2\n" }]);
  materialiseSources(placements);
  writeFileSync(placements[0].targetAbs, "v1\n");
  const v1Sha = createHash("sha256").update("v1\n").digest("hex");
  const manifest = {
    schemaVersion: 1,
    syncedVersion: "v0.1.0",
    stackId: "java-spring-boot-3",
    files: {
      "AGENTS.md": {
        sha256: v1Sha,
        sourceRel: "agents-md/AGENTS.md",
        ruleId: "agents-md",
        lastSyncedVersion: "v0.1.0",
      },
    },
  };
  const plannedShas = planShas(placements);
  const cls = classifyPlacements(placements, { projectDir: project, manifest, plannedShas });
  assert.equal(cls.wouldChange.length, 1);
  assert.equal(cls.conflicts.length, 0);
});

test("writeManifest produces a stable, sorted file", async () => {
  const project = mkTempProject("manifest-write");
  const placements = fakePlacements(project, [
    { targetRel: "z.md", content: "z" },
    { targetRel: "a.md", content: "a" },
    { targetRel: "m.md", content: "m" },
  ]);
  materialiseSources(placements);
  const plannedShas = planShas(placements);
  await writeManifest({
    projectDir: project,
    version: "v0.1.0",
    stackId: "java-spring-boot-3",
    placements,
    plannedShas,
  });
  const onDisk = readManifest(project);
  const keys = Object.keys(onDisk.files);
  assert.deepEqual(keys, ["a.md", "m.md", "z.md"]);
  // Each entry must have the four documented fields.
  for (const v of Object.values(onDisk.files)) {
    assert.ok(v.sha256);
    assert.equal(v.lastSyncedVersion, "v0.1.0");
    assert.ok(v.sourceRel);
    assert.ok(v.ruleId);
  }
});

test("readManifest tolerates a missing or malformed file", () => {
  const project = mkTempProject("manifest-missing");
  assert.equal(readManifest(project), null);
  writeFileSync(path.join(project, MANIFEST_FILENAME), "not-json{");
  assert.equal(readManifest(project), null);
});
