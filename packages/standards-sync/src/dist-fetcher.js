// @org/standards-sync — dist tree fetcher (Plan §11 task 2).
//
// Two modes:
//
//   1. LOCAL: `--local-dist <path>` points at a directory whose `stacks/<stackId>/` subtree
//      already exists on disk. Returns the path verbatim. Used by Phase 8's test suite
//      (against the workspace's `dist/` tree) and by anyone testing locally against
//      `make release-dry-run` output.
//
//   2. REMOTE: download the GitHub source tarball for the resolved tag, extract ONLY
//      `dist/stacks/<stackId>/` into a temp directory, and return that. Uses the official
//      `tar` package because Node ships no native tar reader.
//
// The fetcher writes nothing under the consumer's working tree — the placement module is
// responsible for the copy step.

import { existsSync, mkdtempSync, mkdirSync, createWriteStream } from "node:fs";
import { rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import * as tar from "tar";

export class DistFetchError extends Error {
  constructor(message, { hint } = {}) {
    super(message);
    this.name = "DistFetchError";
    this.hint = hint;
  }
}

export async function locateDistTree({
  localDist,
  repo,
  version,
  stackId,
  fetchImpl = globalThis.fetch,
  tempDirRoot = os.tmpdir(),
  logger,
} = {}) {
  if (localDist) {
    const expandedRoot = path.resolve(localDist);
    const stackPath = path.join(expandedRoot, "stacks", stackId);
    if (!existsSync(stackPath)) {
      throw new DistFetchError(
        `Local dist tree at ${expandedRoot} has no stacks/${stackId}/ subtree.`,
        {
          hint:
            "Run `python -m compiler --all-stacks --target all --out <dir>` to (re-)populate, " +
            "or omit --local-dist to download from GitHub.",
        },
      );
    }
    logger?.info(`Dist source: local tree at ${expandedRoot}.`);
    return { distRoot: expandedRoot, stackRoot: stackPath, cleanup: async () => {} };
  }

  if (!fetchImpl) {
    throw new DistFetchError(
      "Node.js global `fetch` is unavailable. Upgrade to Node 18+ or pass a fetchImpl.",
    );
  }
  if (!version) throw new DistFetchError("Cannot fetch remote dist without a `version`.");
  if (!repo) throw new DistFetchError("Cannot fetch remote dist without a `repo`.");
  if (!stackId) throw new DistFetchError("Cannot fetch remote dist without a `stackId`.");

  const url = `https://api.github.com/repos/${repo}/tarball/${version}`;
  logger?.info(`Dist source: downloading ${url} (this may take a few seconds)...`);
  const headers = {
    accept: "application/vnd.github+json",
    "user-agent": "@org/standards-sync",
  };
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetchImpl(url, { headers, redirect: "follow" });
  if (!res.ok) {
    throw new DistFetchError(
      `GitHub tarball API returned ${res.status} ${res.statusText} for ${url}.`,
      {
        hint:
          "Verify the tag exists and the repo is accessible. If the repo is private, " +
          "set GITHUB_TOKEN to a token with `repo:read` scope.",
      },
    );
  }
  if (!res.body) {
    throw new DistFetchError(`Empty response body from ${url}.`);
  }

  const tempDir = mkdtempSync(path.join(tempDirRoot, "standards-sync-"));
  const tarballPath = path.join(tempDir, "release.tar.gz");
  // The fetch body is a web ReadableStream; convert to a Node Readable for pipeline().
  const nodeStream = Readable.fromWeb(res.body);
  await pipeline(nodeStream, createWriteStream(tarballPath));

  // The tarball expands to `<repo>-<commit>/...`. We only need `dist/stacks/<stackId>/`.
  // tar.extract with `filter:` writes only the requested files; `strip: 1` removes the
  // top-level directory.
  const extractDir = path.join(tempDir, "extracted");
  mkdirSync(extractDir, { recursive: true });
  const wanted = `dist/stacks/${stackId}/`;
  await tar.extract({
    file: tarballPath,
    cwd: extractDir,
    strip: 1,
    filter: (entryPath) => {
      // GitHub tarballs have a top-level prefix like `engineering-standards-central-abc1234/`.
      // After `strip: 1` removes that, the path starts at `dist/...`. We accept anything
      // whose stripped form begins with `dist/stacks/<stackId>/`.
      const stripped = entryPath.split("/").slice(1).join("/");
      return stripped.startsWith(wanted);
    },
  });

  const stackRoot = path.join(extractDir, "dist", "stacks", stackId);
  if (!existsSync(stackRoot)) {
    throw new DistFetchError(
      `Tarball for ${version} did not contain dist/stacks/${stackId}/ — the release may be missing this stack.`,
      {
        hint: `Available stacks at the release tag can be listed via 'gh release view ${version}'.`,
      },
    );
  }

  return {
    distRoot: path.join(extractDir, "dist"),
    stackRoot,
    cleanup: async () => {
      await rm(tempDir, { recursive: true, force: true });
    },
  };
}
