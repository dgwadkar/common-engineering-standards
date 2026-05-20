// @org/standards-sync — version resolution (Plan §11 task 2).
//
// Resolution order:
//
//   1. Explicit operator override: `--version v0.2.3` on the CLI.
//   2. Pinned mode: read `<projectDir>/.standards-version`. The file holds the bare tag
//      (e.g., "v0.1.0"). Whitespace and comments (#-prefixed lines) are tolerated.
//   3. Floating mode: query the GitHub Releases API for the latest `v<X.Y.Z>` release of
//      the central repo.
//
// The CLI's `--local-dist <path>` flag short-circuits this entire flow — version resolution
// is bypassed and the local dist path is used verbatim. This is the path used by Phase 8's
// own test suite (testing against the workspace's `dist/` tree) and by anyone running
// `make release-dry-run` and pointing the CLI at the tmpdir.

import { readFileSync, existsSync } from "node:fs";
import path from "node:path";

export const DEFAULT_REPO = "engineering-standards-central/engineering-standards-central";

export class VersionResolutionError extends Error {
  constructor(message, { hint } = {}) {
    super(message);
    this.name = "VersionResolutionError";
    this.hint = hint;
  }
}

export function readPinnedVersion(projectDir) {
  const file = path.join(projectDir, ".standards-version");
  if (!existsSync(file)) return null;
  const raw = readFileSync(file, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    return trimmed;
  }
  return null;
}

// Floating-mode resolver. Wraps `fetch` so tests can pass a mock.
// Returns the tag name (e.g., "v0.1.0").
export async function fetchLatestReleaseTag({
  repo = DEFAULT_REPO,
  fetchImpl = globalThis.fetch,
  token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN,
} = {}) {
  if (!fetchImpl) {
    throw new VersionResolutionError(
      "Node.js global `fetch` is unavailable. Upgrade to Node 18+ or pass a fetchImpl.",
    );
  }
  const url = `https://api.github.com/repos/${repo}/releases/latest`;
  const headers = {
    accept: "application/vnd.github+json",
    "user-agent": "@org/standards-sync",
  };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetchImpl(url, { headers });
  if (!res.ok) {
    if (res.status === 404) {
      throw new VersionResolutionError(
        `No releases found at https://github.com/${repo}/releases. The standards corpus may not have been released yet.`,
        {
          hint:
            "Ask the Standards Council to run the `release.yml` workflow at least once, or pin a known tag via `.standards-version`. " +
            "See docs/release-bot-setup.md.",
        },
      );
    }
    throw new VersionResolutionError(
      `GitHub Releases API returned ${res.status} ${res.statusText} for ${url}.`,
      { hint: "Check repo permissions; pass --repo <owner>/<repo> if the default is wrong." },
    );
  }
  const body = await res.json();
  if (typeof body.tag_name !== "string") {
    throw new VersionResolutionError(
      `GitHub Releases API response for ${url} omitted tag_name.`,
    );
  }
  return body.tag_name;
}

export async function resolveVersion({
  projectDir,
  explicitVersion,
  repo = DEFAULT_REPO,
  fetchImpl,
  logger,
}) {
  if (explicitVersion) {
    logger?.info(`Version resolution: using --version override ${JSON.stringify(explicitVersion)}.`);
    return { version: explicitVersion, source: "explicit" };
  }
  const pinned = readPinnedVersion(projectDir);
  if (pinned) {
    logger?.info(
      `Version resolution: pinned to ${JSON.stringify(pinned)} via .standards-version (${path.join(projectDir, ".standards-version")}).`,
    );
    return { version: pinned, source: "pinned" };
  }
  logger?.info(
    `Version resolution: no .standards-version file; querying GitHub Releases API for latest tag in ${repo}.`,
  );
  const tag = await fetchLatestReleaseTag({ repo, fetchImpl });
  logger?.info(`Version resolution: latest release is ${JSON.stringify(tag)}.`);
  return { version: tag, source: "floating" };
}
