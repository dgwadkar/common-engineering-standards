# Phase 8 Execution Log — Consumer-Side Sync Tool

- **Phase**: 8 — Consumer-Side Sync Tool
- **Date**: 2026-05-20
- **Status**: COMPLETED
- **Estimated duration (per plan)**: 6 days
- **Actual duration**: 1 session (~3 hours of agent execution time)

## 1. Summary

Phase 8 ships `@org/standards-sync@0.1.0` — a Node ≥18 CLI under
`packages/standards-sync/` that consumer repositories run (`npx @org/standards-sync`)
to detect their stack, resolve a pinned-or-floating standards version, and copy the
matching `dist/stacks/<stack-id>/` subtree into the conventional consumer locations
defined in Architecture Upgrade Report §5.3. The CLI is idempotent (re-runs produce
zero git diff, locked by AC2 tests), surfaces a Markdown sync report on every run,
refuses to overwrite manually-edited files unless `--force` is passed (mirrors the
Phase-7 `dist-protection-lint` "fail with explicit reason" pattern), and degrades
gracefully on non-supported stacks (exits 0 with a `no-applicable-stack` rationale,
per AC3).

The Phase-7 lesson §7-b recommendation (single source of truth for the stack
catalog) was incorporated as a prerequisite: `schemas/stacks.json` is the new
canonical catalog, consumed by both `compiler/core/stack_filter.py` and
`tools/generate_dist_readme.py` (Python compiler side) AND
`packages/standards-sync/stacks.json` (a byte-for-byte bundled copy refreshed via
`npm run sync-stacks-catalog`, with a Node-side test that locks the parity). This
eliminates the previous duplication between `STACKS` and `KNOWN_STACKS` flagged in
the Phase-7 forward-questions list.

The task-6 optional Maven/Gradle integration ships as **copy-pastable build-tool
recipes** under `packages/standards-sync/plugins/` rather than a native JVM build
plugin. The recipes wrap `npx --yes @org/standards-sync@<version>` from
`exec-maven-plugin` or a Gradle `Exec` task so Java teams can bind sync to
`generate-resources` / `processResources` without adding a second supply chain. The
rationale (and explicit ADR-style trade-off table) lives in
`packages/standards-sync/plugins/README.md`.

Full test results: 63 Node tests passing (`node --test 'test/*.test.js'`) plus
279–286 Python tests passing (the variance comes from 7 sandbox-conditional
integration tests carried over from Phase 7 — they skip when `.git/hooks/` is
unwritable and run unconditionally otherwise; both states are correct).
Zero linter errors on every Phase-8 artifact.

## 2. Files Created

### Canonical stack catalog (Phase-7 lesson §7-b prerequisite)

- `schemas/stacks.json` (261 lines) — JSON Schema **and** live catalog of the four
  supported stacks. The `$defs/StackDescriptor` / `$defs/StackIndicator` blocks
  validate the shape of each stack; `properties.stacks.const` pins the canonical
  four (java-spring-boot-3, java-spring-boot-2, typescript-nestjs-10,
  python-fastapi-0-110). Each stack includes a `detection` recipe (manifest files +
  ordered indicators) that the Node sync CLI consumes; the Python compiler ignores
  the `detection` block and reads only `id` / `language` / `framework` /
  `framework_version` for stack filtering. Adding a fifth stack is now a one-entry
  append here plus a fixture under `fixtures/` plus a golden tree under
  `tests/golden/`.
- `tests/test_stacks_catalog.py` (163 lines) — Python regression test ensuring
  `schemas/stacks.json` parses against its own schema, contains the canonical four
  stacks, each `detection.indicators[]` uses a supported `kind`, `_meta.yml`
  framework-version values align with `stacks.json` descriptors, and that
  `compiler.core.stack_filter` + `tools.generate_dist_readme` both successfully load
  the catalog at import time.

### Node package — `@org/standards-sync@0.1.0`

- `packages/standards-sync/package.json` — npm manifest. `type: module`, `bin`
  entry at `bin/standards-sync.js`, `engines.node: ">=18.0.0"`, two runtime deps
  (`commander@^12.1.0`, `tar@^7.4.3`), `scripts.test: "node --test 'test/*.test.js'"`,
  `scripts.sync-stacks-catalog` that re-bundles `stacks.json` from
  `schemas/stacks.json`.
- `packages/standards-sync/README.md` (95 lines) — User-facing docs: what the CLI
  does, the file layout it produces, the eight flags, stack-detection algorithm,
  pointer to `plugins/` for JVM integration, test instructions.
- `packages/standards-sync/.gitignore` — Ignores `node_modules/` and the legacy
  in-package `tests/` scratch dir (since-fixed).
- `packages/standards-sync/stacks.json` (byte-for-byte copy of
  `schemas/stacks.json`) — Bundled at publish time so the npm package is
  self-contained. The Node test `stacks-catalog.test.js::"the bundled stacks.json
  equals the workspace schemas/stacks.json (byte-for-byte)"` locks the parity.

### Node package — source modules (`packages/standards-sync/src/`)

- `cli.js` (101 lines) — Commander argv parser, flag definitions, exit-code policy.
- `index.js` (272 lines) — Orchestrates: detect → resolve → fetch → plan → classify →
  apply → report. Exposes `sync()`, `SYNC_OUTCOMES`, `DEFAULT_REPO`. Idempotency
  short-circuit lives here (skips manifest rewrite when the run is a true no-op).
- `detect-stack.js` (419 lines) — Manifest parsers for `pom.xml`,
  `build.gradle.kts` / `build.gradle`, `package.json`, `pyproject.toml` plus
  evaluators for the five indicator kinds (`maven_parent`, `maven_dependency`,
  `gradle_plugin`, `npm_dependency`, `pep621_dependency`). Returns
  `{stackId, detectedVersion, manifestFile, rationale, candidatesConsidered}`.
- `version-resolver.js` (109 lines) — Reads `.standards-version` (pinned mode) or
  hits `GET https://api.github.com/repos/<owner>/<repo>/releases/latest` (floating
  mode). Honors `GITHUB_TOKEN` for higher rate limits. Wraps 404/network errors in a
  `VersionResolutionError` with `hint`.
- `dist-fetcher.js` (133 lines) — Resolves `dist/stacks/<stackId>/`. Local mode
  (`--local-dist <path>`) short-circuits to a filesystem read. Remote mode downloads
  a tarball from `https://codeload.github.com/.../tar.gz/<tag>` and extracts only
  the relevant subtree.
- `placement.js` (160 lines) — Maps each `dist/stacks/<stackId>/<subtree>/` to its
  conventional consumer location per Architecture Report §5.3, applies
  `--with-memory-bank` gating, and writes files (or returns the plan for `--dry-run`).
- `idempotency.js` (175 lines) — SHA-256 checksumming, manifest read/write
  (`.standards-sync-manifest.json`), and the `classifyPlacements` four-bucket
  categoriser (wouldAdd / wouldChange / identical / conflicts). The
  `ManualEditConflictError` carries the conflicts list for the report.
- `sync-report.js` (281 lines) — Renders the Markdown report consumed by both
  stdout and `--write-report`. Includes the no-matching-globs warning section
  (Plan §11 task 5).
- `stacks-catalog.js` (56 lines) — Loads the bundled `stacks.json` (or the
  workspace `schemas/stacks.json` during dev), exposes `loadCatalog`,
  `getStackById`, `resolveCatalogPath`.
- `semver-range.js` (88 lines) — Minimal semver-range parser (`>=`, `<`, `^`, `~`,
  conjunctions) that mirrors the Python compiler's range logic.
- `logger.js` (41 lines) — Pluggable logger with `info`/`warn`/`error`/`success`
  levels; a recording sink for tests.

### Node package — bin shim

- `packages/standards-sync/bin/standards-sync.js` (17 lines) — `#!/usr/bin/env
  node` shim that imports `runCli` from `src/cli.js`; marked executable. This is the
  `npx @org/standards-sync` entry point.

### Node package — test suite (`packages/standards-sync/test/`)

- `_helpers.js` (48 lines) — Test infrastructure: `mkTempProject`, `rmDir`,
  `FIXTURES_DIR`, `DIST_DIR`, and a per-process `FILE_TMP_ROOT` so parallel test
  workers do not clobber each other's `after()` cleanup. **Decision §5.4 below**
  documents the rationale for the per-file scoping after the first integration
  run revealed the conflict.
- `semver-range.test.js` (80 lines, 10 tests) — Parser unit tests plus a parity
  test that every `version_range` in `stacks.json` parses cleanly.
- `stacks-catalog.test.js` (78 lines, 6 tests) — Catalog loader tests + the
  workspace-vs-bundled byte-for-byte parity test.
- `detect-stack.test.js` (139 lines, 5 tests) — One test per fixture
  (spring-boot-3-2, spring-boot-2-7-legacy, nestjs-10, fastapi-0-110) plus an
  AC3-style "no manifest matches" test.
- `version-resolver.test.js` (116 lines, 8 tests) — Explicit / pinned / floating
  resolution with an injected `fetch` (no real network), error paths,
  GITHUB_TOKEN forwarding.
- `placement.test.js` (85 lines, 5 tests) — Plan against Architecture §5.3,
  `--with-memory-bank` gating, dry-run behaviour, the `optionalIfMissing` path for
  `archunit/`.
- `idempotency.test.js` (175 lines, 6 tests) — SHA-256 stability, four-bucket
  classification, manifest stable-key-order serialisation, malformed-file
  tolerance.
- `end-to-end.test.js` (275 lines, 11 tests) — AC1 (full §5.3 layout) + AC1
  opt-in (memory-bank), AC2 (two consecutive runs byte-for-byte identical) +
  AC2-sibling (different fixture manifest, same dist → still no-op), AC3 (Rails
  Gemfile → NoApplicableStack, exit 0), per-fixture end-to-end happy paths, manual
  edit detected + blocked, `--force` overwrites + rebases manifest.
- `cli.test.js` (104 lines, 12 tests) — `--help`, `--print-version`, dry-run
  produces no writes, `--write-report` writes the report file, end-to-end exit
  codes for SB3 + Rails fixtures.

### Maven / Gradle integration recipes (Plan §11 task 6)

- `packages/standards-sync/plugins/README.md` (145 lines) — Rationale for shipping
  recipes instead of a native build plugin (single supply chain, no duplicated
  detection), three drop-in snippets (Maven `exec-maven-plugin`, Gradle Groovy
  DSL, Gradle Kotlin DSL), version-pinning patterns, and a CI smoke-test
  workflow that converts AC2 into a permanent consumer-side guard.
- `packages/standards-sync/plugins/maven/README.md` (21 lines) — Maven quick-start.
- `packages/standards-sync/plugins/maven/pom-snippet.xml` (30 lines) — Drop-in
  `<plugin>` block.
- `packages/standards-sync/plugins/gradle/README.md` (22 lines) — Gradle
  quick-start.
- `packages/standards-sync/plugins/gradle/build.gradle.kts.snippet` (18 lines) —
  Kotlin DSL snippet.
- `packages/standards-sync/plugins/gradle/build.gradle.snippet` (15 lines) —
  Groovy DSL snippet.

## 3. Files Modified

- `compiler/core/stack_filter.py` (76 lines, +25/-19) — Replaced the inline
  `STACKS = {...}` dict with `_load_stack_catalog()` that reads
  `schemas/stacks.json` at module import time and converts each descriptor to the
  existing `_StackDef` dataclass. The public API (`stack_versions_for`,
  `iter_known_stacks`, etc.) is unchanged.
- `tools/generate_dist_readme.py` (55 lines, +23/-19) — Replaced the inline
  `KNOWN_STACKS = [...]` list with `_load_known_stacks()` reading
  `schemas/stacks.json`. The Phase-7 drift-guard test
  `test_known_stacks_align_with_compiler_stack_filter` is now a trivial identity
  check (both functions read the same file).
- `docs/02-implementation-plan.md` (+12/-2) — Marked Phase 8 status COMPLETED;
  ticked all three acceptance criteria with detailed evidence; added a status
  callout next to the §11 header.

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan) | Status | Evidence / Notes |
|---|---|---|
| Running `npx @org/standards-sync` in a fresh Spring Boot 3.2 fixture project produces the file layout in Architecture Upgrade Report §5.3. | ✅ | Locked by `packages/standards-sync/test/end-to-end.test.js::AC1: spring-boot-3-2 fixture produces the §5.3 file layout (excluding opt-in scaffolds)` plus an opt-in sibling test for `--with-memory-bank`. Independently smoke-tested on disk: copied `fixtures/spring-boot-3-2/` → `tests/.tmp/phase8-smoke/`, ran the bin script with `--local-dist dist --version v0.1.0`, observed the produced tree contains `.cursor/rules/` (15 mdcs), `.github/copilot-instructions.md`, `.junie/AGENTS.md`, `AGENTS.md`, `CLAUDE.md`, and `.standards-sync-manifest.json` (no `memory-bank/` — correctly opt-in). |
| Running it twice consecutively produces zero `git diff`. | ✅ | Locked by `end-to-end.test.js::AC2: two consecutive sync runs leave every file byte-for-byte identical` plus an AC2-sibling test that swapping in a different fixture manifest without a version bump still no-ops on identical content. Smoke-test: ran the CLI twice against the SB3 fixture; `diff` of `shasum` before vs after returned empty (literal output: `AC2: ZERO DIFF (PASS)`). The implementation achieves this by (a) skipping write for `identical` placements and (b) skipping `writeManifest` entirely when the run is a complete no-op (manifest already up to date — `syncedAt` does not rewrite). |
| Running in a non-supported stack (e.g., a Ruby on Rails project) emits a clear "no applicable stack found" message and exits 0 (not an error). | ✅ | Locked by `end-to-end.test.js::AC3: a Rails-only project (Gemfile) returns NoApplicableStack with exit 0` plus the CLI integration test `cli.test.js::end-to-end: Rails project (no recognised manifest) exits 0 with no-applicable-stack rationale`. Smoke-test: created `tests/.tmp/phase8-rails/Gemfile` with a single `source "https://rubygems.org"` line; ran the CLI; observed exit code 0 plus the rationale `"No applicable stack found: project root contains none of the manifest files we recognise (pom.xml, build.gradle.kts, build.gradle, package.json, pyproject.toml)."` followed by a `[info] No applicable stack found — nothing to sync.` log line. |

All three acceptance criteria are objectively verified. The Phase-8 contract is met.

## 5. Decisions Made

- **Decision §5.1**: Introduce `schemas/stacks.json` as the canonical stack
  catalog **before** writing the Node sync CLI (rather than after, as a follow-up).
  - **Alternatives considered**: (a) Hard-code the four stacks in the Node CLI and
    accept drift with `compiler.core.stack_filter.STACKS`; (b) build a thin Python
    script that exports the existing `STACKS` dict to JSON at build time.
  - **Rationale**: Phase 7 explicitly raised this as a Phase-8 forward question
    (Phase-7 log §9). Doing the refactor up-front kept both producers (Python
    compiler) and consumer (Node CLI) reading the same source for the same file
    layout, and reduced the Phase-7 drift-guard test
    (`test_known_stacks_align_with_compiler_stack_filter`) to a trivial identity
    check. The Node-side bundled-vs-workspace parity test
    (`stacks-catalog.test.js::"the bundled stacks.json equals the workspace
    schemas/stacks.json (byte-for-byte)"`) is the second half of the same guard.
  - **Reversible?**: Yes — if a future stack genuinely needs different metadata
    on the Python vs Node sides, we can split the catalog with a `$ref`. No
    plausible scenario forces that today.

- **Decision §5.2**: Ship Plan-§11-task-6 (Maven/Gradle integration) as
  **copy-pastable recipes** under `plugins/`, not as native JVM build plugins.
  - **Alternatives considered**: (a) Write a true Maven MOJO + Gradle
    `Plugin<Project>`; (b) ship a thin shell script wrapper.
  - **Rationale**: A native plugin would either re-implement the entire detection
    + placement pipeline in Java/Kotlin (direct violation of the "single source of
    truth" principle from Plan §1) or shell out to the Node CLI (which is exactly
    what the recipes already do, minus the install/maintenance burden of a second
    package). The Plan §11 task explicitly marks this task as "optional"; the
    recipes meet the spirit (Java teams can bind sync to `generate-resources`)
    without taking on a second supply chain. The rationale is documented in
    `packages/standards-sync/plugins/README.md` so a future pilot team can
    revisit if their CI pipeline forbids `npx`.
  - **Reversible?**: Yes — a native plugin can be added later under
    `plugins/maven-mojo/` or `plugins/gradle-plugin/` without touching the
    recipes (which would coexist for teams that prefer the lightweight wiring).

- **Decision §5.3**: Implement semver-range matching in
  `packages/standards-sync/src/semver-range.js` rather than adding `semver` from
  npm.
  - **Alternatives considered**: Adding `semver@7.x` as a runtime dependency
    (universal de-facto).
  - **Rationale**: We need exactly four primitives (`>=`, `<`, `^`, `~`) plus
    whitespace conjunction. The `semver` package pulls in ~30 kB of code we do
    not need and adds a transitive supply-chain hop; a 88-line custom
    implementation that matches the Python compiler's range logic line-for-line
    is easier to reason about and easier to validate parity for (see the
    `semver-range.test.js::"parity with stacks.json"` test). If `--prerelease`
    or `||` (union) ranges enter the catalog later, we re-evaluate.
  - **Reversible?**: Yes — swap out `src/semver-range.js` for `import { satisfies
    } from "semver"` if the requirement set expands.

- **Decision §5.4**: Scope each test file's `after()` cleanup to a per-process
  `FILE_TMP_ROOT` rather than the shared workspace-rooted `TMP_ROOT`.
  - **Alternatives considered**: (a) Run tests serially with
    `--test-concurrency=1`; (b) move temp dirs back to `/tmp/` and accept the
    Phase-7 sandbox limitation.
  - **Rationale**: Node's `--test` runs files in parallel by default, one worker
    per file. Every test file's pre-fix `after(() => rmDir(TMP_ROOT))` deleted
    the shared dir while sibling workers were still writing into it, producing
    `ENOTEMPTY` and EPERM errors that masked the real test outcomes. Per-file
    scoping is correct (each worker only cleans up what it created); `/tmp/`
    remains unwritable for `.git/hooks/` reasons documented in Phase 7.
  - **Reversible?**: Yes — a future move to a centralised test-fixtures cleanup
    is straightforward, but per-file scoping is the simpler invariant.

- **Decision §5.5**: When a Maven dependency omits `<version>` (inheriting from
  parent), the SB3 `maven_dependency` indicator must verify the parent's version
  satisfies the indicator's range — not return `true` unconditionally.
  - **Alternatives considered**: Accept the false positive (SB3 indicator firing
    on an SB2 fixture) and rely on stack ordering to disambiguate.
  - **Rationale**: The detect-stack test exposed this bug:
    `spring-boot-2-7-legacy` was selecting `java-spring-boot-3` because the
    starter dependencies omit `<version>` and the original code returned `true`
    "since the parent indicator gates the version." The original code was
    incorrect when the SB3 dependency indicator was evaluated against an SB2
    fixture (a different stack's parent). The fix (commit-local change to
    `src/detect-stack.js::evalMavenDependency`) checks that the manifest's
    parent groupId matches and that the parent version satisfies the indicator's
    range before accepting the inheritance-implied version.
  - **Reversible?**: Yes — but doing so re-introduces the false positive, so
    practically: no.

## 6. Blockers Encountered

- **Blocker**: `npm install` failed initially with `ENOENT: no such file or
  directory, open '/Users/.../common-engineering-standards/package.json'` when
  `working_directory` was combined with `required_permissions: ["all"]` in the
  agent's shell-tool invocation. The "all" permission ran the command in a
  different shell context that did not honour `working_directory`.
  - **Resolution**: Chained `cd packages/standards-sync && npm install ...` into
    the command string instead of relying on `working_directory`. This is a
    sandbox-tool quirk, not a project bug; no source change needed.
  - **Carry-forward**: Phase 9 sessions that use `required_permissions: ["all"]`
    should `cd` explicitly in the command rather than relying on
    `working_directory` semantics.

- **Blocker**: Initial smoke-test writes to `/tmp/sync-smoke/` failed with
  `EPERM`. The Phase-7 log §6 documents this — the local sandbox blocks
  `/tmp/.git/hooks/` writes.
  - **Resolution**: Switched smoke-test directories to
    `tests/.tmp/<unique>/`, consistent with the Phase-7 convention.
  - **Carry-forward**: Already documented in Phase 7; reaffirmed here.

- **Blocker**: AC2 ("zero diff on re-run") initially failed because
  `.standards-sync-manifest.json` rewrote `syncedAt` on every run, producing a
  one-line diff even when no content had changed.
  - **Resolution**: Added a no-op short-circuit in
    `packages/standards-sync/src/index.js::sync()`: if every placement
    classifies as `identical` AND the existing manifest already records the
    same `syncedVersion` + `stackId` + file set, skip `writeManifest` entirely.
    `syncedAt` is only updated on runs that actually did something.
  - **Carry-forward**: This is the correct definition of idempotency for the
    framework — a manifest update is itself a side effect that AC2 forbids when
    nothing else changed. Phase 9 telemetry can still capture
    `syncedAt` from the run that produced the current manifest; we just stop
    overwriting it with the same value.

- **Blocker**: Test files all called `rmDir(TMP_ROOT)` in their `after()` hooks
  and Node's default parallel `--test` runner caused races (`ENOTEMPTY`,
  `EPERM`) that masked real test outcomes.
  - **Resolution**: Documented as Decision §5.4 above. Each test file now
    cleans up only its own `FILE_TMP_ROOT` subdir.
  - **Carry-forward**: Future Node test files in this package must import
    `FILE_TMP_ROOT` (not `TMP_ROOT`) and use it in their `after()` hook.

- **Blocker**: Initial Maven/Gradle recipes used a non-existent `--repo-root`
  flag. The CLI actually exposes `--project-dir`.
  - **Resolution**: Found via direct smoke-test (`error: unknown option
    '--repo-root'`); fixed every recipe occurrence in `plugins/README.md`,
    `plugins/maven/pom-snippet.xml`, `plugins/gradle/*.snippet`.
  - **Carry-forward**: If `--project-dir` is ever renamed for symmetry with
    other tools, the recipes must be updated in lock-step. Consider adding a
    smoke test that greps the recipes for known flag names.

- **Blocker**: Node 24 (the local runtime) does not accept `node --test test/` —
  it interprets `test/` as a positional file and fails with `MODULE_NOT_FOUND`.
  Node 22 (and the package.json originally hard-coded) accepts the directory.
  - **Resolution**: Changed `scripts.test` and the README to use the glob
    pattern `'test/*.test.js'` which both Node 22 and Node 24 accept.
  - **Carry-forward**: Document Node version expectations in the package
    README. If a future test file lives outside `test/*.test.js`, the glob must
    be widened.

## 7. Lessons that Affect Later Phases

- **Lesson 1 (affects Phase 9 pilot rollout)**: The Node CLI's
  `--write-report <path>` flag should be the default in CI. The Phase-8
  recipe-README's "CI smoke test" section converts AC2 into a permanent
  consumer-side guard (`git status --porcelain` after the sync); pilot teams
  should land that workflow on day one.
- **Lesson 2 (affects Phase 9 pilot rollout)**: Pilot teams need to choose
  pinned vs floating mode explicitly. Drop a `.standards-version` file in week
  one (pinned, reproducible) and only adopt floating mode once their CI
  has a drift-detection alert. The CLI surfaces the resolution mode in the
  sync report; pilot kick-off docs should highlight this.
- **Lesson 3 (affects Phase 9 telemetry)**: The sync report's "Warnings — Cursor
  rules whose globs match zero consumer files" section is the obvious source of
  *real-world rule applicability data*. Phase 9 telemetry should aggregate this
  per-consumer-per-week to surface rules whose globs need refinement — a much
  cleaner signal than waiting for Cursor's per-rule activation telemetry.
- **Lesson 4 (affects Phase 10 governance)**: Adding a fifth stack is now a
  one-entry append to `schemas/stacks.json` plus a fixture and a golden tree.
  The Phase-10 governance doc should codify this as the "supported stacks"
  expansion procedure and route fifth-stack PRs through the Standards Architect
  (per AGENTS.md §7 routing rules) since they touch the canonical catalog.
- **Lesson 5 (affects Phase 10 governance)**: The Maven/Gradle integration is
  **recipes, not a native plugin** (Decision §5.2 above). The Phase-10
  governance doc should make this an explicit principle ("single supply chain
  for sync logic") so future "build a Maven plugin" requests get triaged
  against the same trade-off table that's already in
  `packages/standards-sync/plugins/README.md`.

A `> ⚠️ Revision` callout was NOT added to `02-implementation-plan.md` —
the lessons above affect Phase 9 and Phase 10 *operationally* but do not
require revisions to the as-written task lists or acceptance criteria of
those phases.

## 8. Verification Commands Run

```bash
# Full Node test suite (63 tests, ~600ms):
$ cd packages/standards-sync && npm test
...
ℹ tests 63
ℹ suites 0
ℹ pass 63
ℹ fail 0
ℹ duration_ms 379.77

# Python regression suite (Phase 0–7 + new tests/test_stacks_catalog.py):
$ .venv-phase2/bin/python -m pytest tests/ -q
...
286 passed in 7.99s
# (Earlier run in the same session: 279 passed, 7 skipped — the 7 are
# sandbox-conditional and skip when `.git/hooks/` is unwritable.)

# AC1 smoke (file layout) + AC2 smoke (zero diff) + AC3 smoke (Rails Gemfile):
$ mkdir -p tests/.tmp/phase8-smoke && cp -r fixtures/spring-boot-3-2/. tests/.tmp/phase8-smoke/ \
    && node packages/standards-sync/bin/standards-sync.js \
       --project-dir tests/.tmp/phase8-smoke --local-dist dist --version v0.1.0 \
       --write-report tests/.tmp/phase8-smoke/standards-sync-report.md
[ ok ] Sync complete.

$ cd tests/.tmp/phase8-smoke && find . -type f -not -name 'pom.xml' \
     -not -name 'standards-sync-report.md' | sort | xargs shasum > /tmp/before.shasum
$ cd $REPO_ROOT && node packages/standards-sync/bin/standards-sync.js \
     --project-dir tests/.tmp/phase8-smoke --local-dist dist --version v0.1.0 --quiet >/dev/null
$ cd tests/.tmp/phase8-smoke && find . -type f -not -name 'pom.xml' \
     -not -name 'standards-sync-report.md' | sort | xargs shasum > /tmp/after.shasum
$ diff /tmp/before.shasum /tmp/after.shasum && echo "AC2: ZERO DIFF (PASS)"
AC2: ZERO DIFF (PASS)

$ mkdir -p tests/.tmp/phase8-rails && echo 'source "https://rubygems.org"' \
     > tests/.tmp/phase8-rails/Gemfile
$ node packages/standards-sync/bin/standards-sync.js \
     --project-dir tests/.tmp/phase8-rails --local-dist dist --version v0.1.0
...
- **Stack detected**: `(none)`
[info] No applicable stack found — nothing to sync. See report above.
EXITCODE=0
```

## 9. Handoff to Next Session

- **Next phase**: 9 — Pilot Adoption and Telemetry
- **Next-session prompt**: written to `docs/execution-log/next-session-prompt.md`
  and printed at the end of this session's chat.
- **Pre-requisites for next phase that are now satisfied**:
  - A functional `@org/standards-sync@0.1.0` package under
    `packages/standards-sync/` that consumer repos can use locally
    (`npm pack` + `npm install ../engineering-standards-central/packages/standards-sync/org-standards-sync-0.1.0.tgz`)
    or via `npx --yes file:../engineering-standards-central/packages/standards-sync`.
  - All four fixture stacks are syncable end-to-end (Spring Boot 3.2,
    Spring Boot 2.7 legacy, NestJS 10, FastAPI 0.110), each with locked
    happy-path tests.
  - Maven/Gradle integration recipes for JVM teams in
    `packages/standards-sync/plugins/`.
  - The sync report's no-matching-globs warning provides the telemetry
    signal Phase 9 will aggregate.
- **Open questions for the operator**:
  - **Publish gating**: should `@org/standards-sync@0.1.0` be published to
    npm BEFORE Phase 9 starts (so pilot teams can `npx @org/standards-sync`
    directly), or AFTER first-pilot validation (in which case pilots use
    `npx --yes file:./node_modules/.local/standards-sync-0.1.0.tgz`)?
    Phase 8 produces the buildable artifact; the publish action is operator
    work that depends on npm-org credentials and a chosen scope name.
  - **Repo coordinates**: `package.json` currently declares
    `homepage` and `repository.url` as
    `engineering-standards-central/engineering-standards-central`. If the
    eventual GitHub org name differs (e.g., `dgwadkar` for the personal-fork
    review path), those fields and `DEFAULT_REPO` in
    `packages/standards-sync/src/index.js` need to be updated in the
    Phase-9 kickoff PR.
