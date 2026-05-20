// CLI exit-code + argv parsing tests. Spawns the bin/standards-sync.js entrypoint as a
// child process so we exercise the same execution path operators see when they run
// `npx @org/standards-sync` (or the `standards-sync` symlink installed by npm i -g).

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  copyFixtureManifest,
  mkTempProject,
  rmDir,
  FILE_TMP_ROOT,
  ensureTmpRoot,
  DIST_DIR,
  REPO_ROOT,
} from "./_helpers.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BIN = path.resolve(__dirname, "..", "bin", "standards-sync.js");

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

function runCli(args, opts = {}) {
  return spawnSync("node", [BIN, ...args], {
    encoding: "utf8",
    cwd: REPO_ROOT,
    ...opts,
  });
}

test("--help prints the program description and exits 0", () => {
  const res = runCli(["--help"]);
  assert.equal(res.status, 0);
  assert.match(res.stdout, /standards-sync/);
  assert.match(res.stdout, /--with-memory-bank/);
  assert.match(res.stdout, /--force/);
});

test("--print-version prints 0.1.0 and exits 0", () => {
  const res = runCli(["-V"]);
  assert.equal(res.status, 0);
  assert.match(res.stdout, /0\.1\.0/);
});

test("end-to-end: sync against spring-boot-3-2 fixture exits 0 with a populated report", () => {
  const project = mkTempProject("cli-sb3");
  copyFixtureManifest("spring-boot-3-2", project);
  const res = runCli([
    "--project-dir", project,
    "--local-dist", DIST_DIR,
    "--quiet",
  ]);
  assert.equal(res.status, 0, `non-zero exit\nstdout=${res.stdout}\nstderr=${res.stderr}`);
  assert.match(res.stdout, /# Standards Sync Report/);
  assert.match(res.stdout, /java-spring-boot-3/);
  assert.ok(existsSync(path.join(project, "AGENTS.md")));
});

test("end-to-end: Rails project (no recognised manifest) exits 0 with no-applicable-stack rationale", () => {
  const project = mkTempProject("cli-rails");
  writeFileSync(
    path.join(project, "Gemfile"),
    'source "https://rubygems.org"\ngem "rails", "~> 7.0"\n',
  );
  const res = runCli([
    "--project-dir", project,
    "--local-dist", DIST_DIR,
    "--quiet",
  ]);
  assert.equal(res.status, 0);
  assert.match(res.stdout, /No applicable stack found/);
});

test("--dry-run exits 0 without writing files", () => {
  const project = mkTempProject("cli-dry");
  copyFixtureManifest("spring-boot-3-2", project);
  const res = runCli([
    "--project-dir", project,
    "--local-dist", DIST_DIR,
    "--dry-run",
    "--quiet",
  ]);
  assert.equal(res.status, 0);
  assert.ok(!existsSync(path.join(project, "AGENTS.md")));
});

test("--write-report writes a Markdown summary to the consumer", () => {
  const project = mkTempProject("cli-report");
  copyFixtureManifest("spring-boot-3-2", project);
  const reportPath = path.join(project, "sync-out.md");
  const res = runCli([
    "--project-dir", project,
    "--local-dist", DIST_DIR,
    "--write-report", reportPath,
    "--quiet",
  ]);
  assert.equal(res.status, 0);
  assert.ok(existsSync(reportPath));
});
