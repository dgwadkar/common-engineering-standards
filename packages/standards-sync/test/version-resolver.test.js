// Version-resolver unit tests (Plan §11 task 2).

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
import path from "node:path";

import {
  readPinnedVersion,
  resolveVersion,
  fetchLatestReleaseTag,
  VersionResolutionError,
} from "../src/version-resolver.js";
import { createRecordingLogger } from "../src/logger.js";
import { mkTempProject, rmDir, FILE_TMP_ROOT, ensureTmpRoot } from "./_helpers.js";

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

test("readPinnedVersion returns null when .standards-version is absent", () => {
  const project = mkTempProject("ver-none");
  assert.equal(readPinnedVersion(project), null);
});

test("readPinnedVersion returns the trimmed tag and ignores comments", () => {
  const project = mkTempProject("ver-pinned");
  writeFileSync(
    path.join(project, ".standards-version"),
    "# pinned for compliance\n\nv0.2.0\n",
  );
  assert.equal(readPinnedVersion(project), "v0.2.0");
});

test("resolveVersion: explicit override wins over both pinned and floating", async () => {
  const project = mkTempProject("ver-explicit");
  writeFileSync(path.join(project, ".standards-version"), "v0.1.0\n");
  const logger = createRecordingLogger();
  const result = await resolveVersion({
    projectDir: project,
    explicitVersion: "v0.9.9",
    logger,
  });
  assert.deepEqual(result, { version: "v0.9.9", source: "explicit" });
});

test("resolveVersion: pinned mode reads .standards-version", async () => {
  const project = mkTempProject("ver-pinned-mode");
  writeFileSync(path.join(project, ".standards-version"), "v0.1.0\n");
  const result = await resolveVersion({ projectDir: project });
  assert.deepEqual(result, { version: "v0.1.0", source: "pinned" });
});

test("resolveVersion: floating mode calls the GitHub Releases API with the injected fetch", async () => {
  const project = mkTempProject("ver-floating");
  const fakeFetch = async (url, opts) => {
    assert.match(url, /\/repos\/owner\/repo\/releases\/latest$/);
    assert.equal(opts.headers["user-agent"], "@org/standards-sync");
    return {
      ok: true,
      status: 200,
      json: async () => ({ tag_name: "v1.2.3" }),
    };
  };
  const result = await resolveVersion({
    projectDir: project,
    repo: "owner/repo",
    fetchImpl: fakeFetch,
  });
  assert.deepEqual(result, { version: "v1.2.3", source: "floating" });
});

test("fetchLatestReleaseTag: 404 raises a VersionResolutionError with a helpful hint", async () => {
  const fakeFetch = async () => ({
    ok: false,
    status: 404,
    statusText: "Not Found",
  });
  await assert.rejects(
    () => fetchLatestReleaseTag({ repo: "owner/repo", fetchImpl: fakeFetch }),
    (err) => {
      assert.ok(err instanceof VersionResolutionError);
      assert.match(err.message, /No releases found/);
      assert.match(err.hint, /release\.yml/);
      return true;
    },
  );
});

test("fetchLatestReleaseTag: non-404 errors include the URL in the message", async () => {
  const fakeFetch = async () => ({
    ok: false,
    status: 500,
    statusText: "Internal Server Error",
  });
  await assert.rejects(
    () => fetchLatestReleaseTag({ repo: "x/y", fetchImpl: fakeFetch }),
    /500/,
  );
});

test("fetchLatestReleaseTag forwards a bearer token when GITHUB_TOKEN is set", async () => {
  const prev = process.env.GITHUB_TOKEN;
  process.env.GITHUB_TOKEN = "ghp_dummytoken";
  try {
    let observed = null;
    const fakeFetch = async (_url, opts) => {
      observed = opts.headers.authorization;
      return { ok: true, status: 200, json: async () => ({ tag_name: "v0.1.0" }) };
    };
    await fetchLatestReleaseTag({ repo: "x/y", fetchImpl: fakeFetch });
    assert.equal(observed, "Bearer ghp_dummytoken");
  } finally {
    if (prev === undefined) delete process.env.GITHUB_TOKEN;
    else process.env.GITHUB_TOKEN = prev;
  }
});
