# `@org/standards-sync`

> Consumer-side sync CLI for the Engineering Standards Framework
> (Plan §11 / Phase 8 — `docs/02-implementation-plan.md`).

## What it does

Detects your project's stack (Spring Boot 3, Spring Boot 2.7, NestJS 10, FastAPI 0.110),
resolves the standards corpus version (pinned via `.standards-version` or floating to
the latest GitHub release), downloads the matching `dist/stacks/<stack>/` subtree from
`engineering-standards-central`, and copies the files into the conventional consumer
locations defined in the Architecture Upgrade Report §5.3.

Idempotent: re-running with the same version produces zero git diff. Refuses to
overwrite locally-edited files unless `--force` is passed.

## Quick start

```bash
# Detect, resolve latest, sync into the current directory:
npx --yes @org/standards-sync@latest

# Pin to a specific tag (the reproducible default for CI):
echo "v0.1.0" > .standards-version
npx --yes @org/standards-sync

# Preview what would change without writing:
npx --yes @org/standards-sync --dry-run --write-report sync-report.md
```

The CLI requires Node ≥18. Network access is needed only when resolving the
floating version (a GitHub API call) and when downloading the tarball; `--local-dist
<path>` short-circuits both for air-gapped or offline use.

## File layout produced

| Source in `dist/stacks/<stack>/` | Destination in your repo |
|---|---|
| `cursor/rules/*.mdc` | `.cursor/rules/*.mdc` |
| `copilot/copilot-instructions.md` | `.github/copilot-instructions.md` |
| `claude/CLAUDE.md` | `CLAUDE.md` |
| `junie/AGENTS.md` | `.junie/AGENTS.md` |
| `agents-md/AGENTS.md` | `AGENTS.md` |
| `archunit/**` (when present) | `src/test/java/com/_org/standards/**` |
| `memory-bank/**` (opt-in via `--with-memory-bank`) | `memory-bank/**` |

Plus `.standards-sync-manifest.json` at the repo root — SHA-256 checksums of every
file the sync wrote, used on the next run to detect manual edits.

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--repo-root <path>` | `.` (cwd) | Consumer project root. |
| `--version <vX.Y.Z>` | (none) | Explicit version override. Wins over `.standards-version` and floating mode. |
| `--local-dist <path>` | (none) | Use a local `dist/` directory (skips GitHub fetch). |
| `--with-memory-bank` | off | Scaffold the six-file Memory Bank under `memory-bank/`. |
| `--dry-run` | off | Plan + report without writing. |
| `--force` | off | Overwrite manually-edited files (the next run resets the manifest baseline). |
| `--write-report <path>` | off | Write the Markdown sync report to a file (also printed on stdout). |
| `--print-version` | off | Print the CLI version and exit. |

## Stack detection

Stacks and their detection signals live in [`stacks.json`](./stacks.json) — a copy of
the canonical [`schemas/stacks.json`](../../schemas/stacks.json) bundled at publish
time. The Node `npm run sync-stacks-catalog` script refreshes the bundled copy from
the workspace catalog so they cannot drift.

Adding a fifth stack is a one-entry append to `schemas/stacks.json` (plus a fixture
under `fixtures/` and a golden tree under `tests/golden/`). No code changes here are
required.

## Build-system integration

JVM teams who do not want to invoke `npx` from a shell can bind the CLI to a Maven
or Gradle phase using the drop-in recipes under [`plugins/`](./plugins/).

## Development

```bash
cd packages/standards-sync
npm test
# Or, equivalently:
node --test 'test/*.test.js'
```

The test suite covers semver-range parsing, stacks-catalog loading, manifest parsing
for each supported manifest format, version resolution (with a stubbed `fetch`),
placement planning, idempotency / conflict detection, end-to-end syncs against each
of the four fixtures, and the three Phase-8 acceptance criteria (AC1 layout, AC2
zero-diff re-run, AC3 unsupported-stack exit 0).

Cleanup of the stale `tests/.tmp/` scratch directories is handled by per-file
`after()` hooks pointing at `FILE_TMP_ROOT`; see `test/_helpers.js`.
