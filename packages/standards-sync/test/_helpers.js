// Test helpers — shared workspace-rooted temp-directory factory.
//
// Phase-7 lesson §6: the system `/tmp` directory is unwritable under the local sandbox
// (`.git/hooks/` permission denials). All tests that need to write into a "consumer"
// project root therefore use `tests/.tmp/<unique>/` instead.
//
// Each test FILE gets its own subdir under TMP_ROOT so that Node's default parallel
// `--test` runner (one file per worker) cannot clobber another file's after() cleanup.

import { mkdirSync, rmSync, cpSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { randomUUID } from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
export const FIXTURES_DIR = path.join(REPO_ROOT, "fixtures");
export const DIST_DIR = path.join(REPO_ROOT, "dist");
export const TMP_ROOT = path.join(REPO_ROOT, "tests", ".tmp", "node-sync");

// Per-process unique root so parallel test files don't fight over cleanup. Each test
// file pays the small cost of importing this module once and gets its own subdir.
export const FILE_TMP_ROOT = path.join(TMP_ROOT, `pid-${process.pid}-${randomUUID().slice(0, 8)}`);

export function mkTempProject(seed) {
  const dir = path.join(FILE_TMP_ROOT, `${seed}-${randomUUID().slice(0, 8)}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

export function copyFixtureManifest(fixtureName, destDir) {
  const fixtureDir = path.join(FIXTURES_DIR, fixtureName);
  cpSync(fixtureDir, destDir, { recursive: true });
}

export function rmDir(dir) {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch (err) {
    // Tolerate races with parallel test workers — best-effort cleanup only.
    if (err && err.code !== "ENOTEMPTY" && err.code !== "ENOENT") throw err;
  }
}

export function ensureTmpRoot() {
  mkdirSync(FILE_TMP_ROOT, { recursive: true });
}
