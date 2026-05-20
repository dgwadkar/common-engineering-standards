# Phase 7 Execution Log — Release Workflow & `dist/` Folder Protection

- **Phase**: 7 — Release Workflow & `dist/` Folder Protection
- **Date**: 2026-05-20
- **Status**: COMPLETED (mechanical artifacts) — five operator-handoff items track to PR-close
- **Estimated duration (per plan)**: 2 days
- **Actual duration**: 1 session (~2.5 hours of agent execution time)

## 1. Summary

Phase 7 establishes the automated release flow that regenerates `dist/`, commits it
under the `@standards-bot` GitHub App identity, and tags semver releases — all
within the single repository per ADR-0004. The deliverables are: a 15-step
`workflow_dispatch` `release.yml`, a sibling PR-only `dist-protection-lint` job
appended to `validate.yml`, the new `--all-stacks` CLI flag on `python -m compiler`
that closes the Phase-6-named gap (the release workflow regenerates the entire
`dist/stacks/` tree in one CLI invocation), three release-helper tools under
`tools/` (Conventional-Commits semver bump computer, rule-delta CHANGELOG
generator, dist README index generator), and three docs
(`docs/release-bot-setup.md` operator runbook for the App, `docs/release-rollback.md`
the no-moved-tags rollback procedure, plus a reconciliation of
`docs/branch-protection-config.md` to use the live `golden-snapshots` job name and
document the §2.4 push-restriction update).

Determinism is preserved: `python -m compiler --all-stacks --target all` is
byte-identical to four per-stack invocations (locked by
`test_all_stacks_byte_identical_to_four_per_stack_runs`) and byte-identical across
runs (locked by the Phase-6 determinism test, which still passes after the
refactor). The full repo suite is 269 passing + 7 skipped (the skipped tests are
git-touching integration tests for `compute_semver_bump.py` that the local sandbox
blocks via `.git/hooks/` permission denials; CI runners on GitHub Actions have no
such restriction so the same tests run unconditionally there). Zero linter errors
on every Phase-7 artifact.

The five Phase-7 acceptance criteria all depend on operator-side actions that the
agent cannot perform — App registration, repo-secret provisioning, branch-protection
apply in the GitHub UI, a live `workflow_dispatch` run, an actual test PR with
`dist/` changes. Each AC is marked `[!]` with a clear handoff note pointing at the
runbook step that closes it. None of these handoffs block Phase 8 (consumer sync),
which depends only on the mechanical contract of `dist/stacks/<stack>/` paths
already locked by the Phase-6 golden tree.

## 2. Files Created

### Documentation (Tasks 1, 6, plus branch-protection updates)

- `docs/release-bot-setup.md` (257 lines) — Operator runbook for the
  `@standards-bot` GitHub App: registration form fields verbatim, App-ID +
  private-key secret storage, installation, post-install verification, branch-
  protection reconciliation, annual key rotation, quarterly audit procedure,
  disaster-recovery on a lost private key, and a copy-into-PR checklist.
- `docs/release-rollback.md` (224 lines) — Documents Path A (re-dispatch
  `release.yml` against the prior-good commit, produces a new tag with
  byte-identical content) and Path B (manual revert PR for cases where source
  also needs cleanup). Names four operations the operator must NEVER do
  (delete the bad tag, move the bad tag, force-push `main`, edit `dist/`
  directly), documents the post-mortem trigger, and proposes a quarterly
  recovery drill.

### CI workflow (Task 2)

- `.github/workflows/release.yml` (265 lines) — Manual `workflow_dispatch`
  workflow with three inputs (`ref`, `force-bump`, `dry-run`), single
  `release` job with 15 steps that map to plan §10 task 2 steps 1–8 plus
  safety guards and the operator-facing summary. Authenticates via
  `actions/create-github-app-token@v1` using the two repo secrets; runs git
  as `standards-bot[bot]`; refuses to commit any paths outside `dist/` via
  a pre-commit guard; concurrency-locks against parallel releases.

### Compiler CLI (Task 2 sub-task — Phase-6 lesson)

- (Modified) `compiler/__main__.py` — Added the `--all-stacks` flag in a
  mutually-exclusive argparse group with `--stack`. The per-stack pipeline
  was extracted into a single loop so `parse_all` and `build_graph` run once
  across all stacks. A new `all-stacks-complete` structured log event is
  emitted at the end of an `--all-stacks` run for downstream observability.

### Release-helper tools (Task 2 sub-tasks)

- `tools/compute_semver_bump.py` (311 lines) — Conventional-Commits parser
  that classifies each commit since the previous tag as `major` (bang or
  `BREAKING CHANGE:` footer), `minor` (`feat:`), `patch` (`fix:`), or `none`,
  then folds via `_highest_bump` and applies via `_apply_bump`. CLI accepts
  `--previous-tag`, `--force-bump`, `--allow-empty`, `--print-rationale`.
  Exit codes: 0 success, 1 git error, 2 invocation error, 4 `--allow-empty`
  + no bump-worthy commits.
- `tools/generate_changelog.py` (363 lines) — Diffs `source/**/*.md`
  frontmatter between the previous tag and `HEAD` via `git show <tag>:path`,
  classifies each change as Added / Removed / Modified-frontmatter (lists
  the specific fields that changed) / Modified-body, and renders a Markdown
  section that is **prepended** above any prior section in
  `dist/CHANGELOG.md`. Falls back to listing every `source/` rule under
  Added when no previous tag exists (first-release path).
- `tools/generate_dist_readme.py` (282 lines) — Walks the live
  `dist/stacks/` subtree, counts cursor MDC files per stack, detects which
  non-cursor targets are present, and renders a versioned index. Preserves
  the `0004-single-repo-distribution` reference the Phase-1 `tree-shape` CI
  job greps for.

### Tests (Task 7)

- `tests/test_compute_semver_bump.py` (345 lines, 34 tests — 27 run locally,
  7 skipped in sandbox).
  Unit suite covers `_parse_version`, `_classify_commit` (parametrized over
  feat/fix/docs/chore/refactor + bang + BREAKING CHANGE: footer + non-CC
  headers + Merge commits), `_highest_bump`, `_apply_bump`. Integration
  suite spins up a temp git repo and drives the CLI end-to-end against a
  synthetic history.
- `tests/test_generate_changelog.py` (147 lines, 11 tests). Covers the pure
  helpers `_parse_frontmatter`, `_format_section`, `_splice_section`, plus
  a regression guard on the `HIGHLIGHTED_FIELDS` catalog so a future PR
  cannot silently drop scope/target_tools/etc. from changelog reporting.
- `tests/test_generate_dist_readme.py` (140 lines, 11 tests). Asserts the
  ADR-0004 reference, the version + changelog link, the per-stack table,
  and a defense-in-depth check that the inline `KNOWN_STACKS` catalog
  matches the runtime `compiler.core.stack_filter.STACKS`. The
  live-tree introspection test compiles the corpus and confirms non-zero
  cursor-rule counts in the rendered table.
- `tests/test_phase7_end_to_end.py` (255 lines, 20 tests). Covers
  `--all-stacks` shape + mutual-exclusion + byte-equality vs the per-stack
  loop, parses `release.yml` and asserts every plan §10 task-2 step is
  present, confirms `dist-protection-lint` is PR-only and cites ADR-0004
  on failure, and verifies the three Phase-7 docs reference each other.

### This log

- `docs/execution-log/phase-7-log.md` — This file.

## 3. Files Modified

- `.github/workflows/validate.yml` — Top-of-file comment block extended with
  the Phase-7 entry (the comment explicitly cites the Phase-2 / Phase-6
  "extend, don't fork" lesson that drove the choice to host
  `dist-protection-lint` as a sibling job rather than a parallel workflow
  file). New `dist-protection-lint` job appended at the bottom (3 steps:
  checkout PR head with full history, fetch base ref, run the lint check
  itself with both an explicit dist-path guard and a non-bot-author detector;
  conditional `if: github.event_name == 'pull_request'` so the job is
  correctly skipped on direct pushes to `main` by `@standards-bot`). The
  existing `compiler-unit-tests` job was extended in two ways: (a) the
  pytest invocation now includes the four new Phase-7 test modules, (b)
  two new smoke steps — `End-to-end smoke (--all-stacks) — Phase 7` and
  `Phase-7 release-tools dry-run smoke` — exercise the new CLI flag and
  the three release-tools in the same job to keep CI cache hits high.
- `docs/02-implementation-plan.md` — Phase 7 section: added the
  `> **Status (as of 2026-05-20): COMPLETED**` callout, marked each of the
  five acceptance criteria `[!]` with a per-AC operator-handoff note, and
  updated §16 with the actual elapsed time (1 session vs. the 2-day
  estimate; faster because Phase-6's `--all-stacks` precursor lesson was
  ready to consume).
- `docs/branch-protection-config.md` — §2.2: reconciled the
  `golden-tests` placeholder to the live `golden-snapshots` job name, added
  the `dist-protection-lint` required-status-check entry with the
  PR-conditional caveat, and noted that GitHub's required-status-check
  matching is by job name (not workflow file name). §2.4: ticked the
  Phase-7 `(Phase 7)` push-restriction box, added the verification
  procedure for the App-actor listing. §5: added a 2026-05-20 status block
  that names the two operator prerequisites (App + secrets, push
  restriction) that gate Phase-7 AC2. §6: added cross-links to the two
  new Phase-7 docs and to the two workflow files.
- `compiler/__main__.py` — Module docstring + argparse extended for
  `--all-stacks`. The per-stack pipeline is now a single loop; `parse_all`
  and `build_graph` run once. New `all-stacks-complete` structured-log
  event emitted at end-of-run.
- `Makefile` — Added `make release-dry-run` target that mirrors the
  `workflow_dispatch` dry-run path locally (compute next version, render
  CHANGELOG + README into `/tmp/`, no commit). Help text extended with a
  Phase-7 section.
- `.gitignore` — Added `tests/.tmp/` so the workspace-rooted temp dir used
  by the new integration tests is never accidentally committed if a test
  crashes mid-cleanup.

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan §10) | Status | Evidence / Notes |
|---|---|---|
| Merging an example PR that adds a new source rule does NOT modify `/dist/`. The dist tree is regenerated only on manual release. | [!] | **Mechanical guards in place**: `release.yml` has only `workflow_dispatch:` triggers — there is no `on: push` or `on: pull_request` that would touch `dist/` automatically. `dist-protection-lint` rejects any PR whose diff includes `dist/**` from a non-bot author. **Live PR experiment** (open a PR adding one source rule and confirm `dist/` is untouched on green merge) is the operator's PR-close action — the agent cannot push to GitHub. Tracked as the live-experiment carry-forward in §9 below. |
| Manually dispatching `release.yml` produces a single commit authored by `@standards-bot`, a `v<X.Y.Z>` tag, a populated `dist/CHANGELOG.md`, and a GitHub Release. | [!] | **All mechanical artifacts ship in this phase** (15-step `release.yml` with App-token auth, semver-bump tool, changelog generator, README generator). The actual dispatch requires three prerequisite operator actions documented in `docs/release-bot-setup.md`: (a) register the `@standards-bot` GitHub App, (b) store `STANDARDS_BOT_APP_ID` + `STANDARDS_BOT_PRIVATE_KEY` repo secrets, (c) update branch protection to allow the App to push to `main` per `docs/branch-protection-config.md` §2.4. Dry-run mode is available locally (`make release-dry-run`) and via `workflow_dispatch` (`dry-run: true`). |
| A test PR by a human that touches a file under `dist/` is blocked by the `dist-protection-lint` status check with a clear error message. | [!] | **Mechanical guard locked**: `tests/test_phase7_end_to_end.py::test_dist_protection_lint_failure_message_cites_adr_0004` asserts the literal failure-message strings "Human authors cannot modify dist/" + ADR-0004 reference are present in the workflow YAML. **Live test PR** (a human commit that touches `dist/README.md` triggering the red status check) is the operator's PR-close action. |
| Branch protection on `main` is verified via screenshot in the closing PR for Phase 7. | [!] | `docs/branch-protection-config.md` is now reconciled with the live CI job names and lists every required setting. **GitHub-UI apply + screenshot** is the operator's PR-close action. The doc's §3 verification procedure (V-1 through V-6) is the operator's checklist. |
| `git log --author=standards-bot dist/` returns the complete history of dist regenerations and nothing else. | [!] | Until the operator runs the first `release.yml` dispatch, `git log --author=standards-bot` is correctly empty. The audit-query template + the quarterly audit procedure are documented in `docs/release-bot-setup.md` §6. This AC ticks `[x]` after the first release lands. |

All five ACs depend on operator-side actions that the agent cannot perform. None
of these handoffs block Phase 8; the consumer-side sync tool depends only on the
mechanical contract of `dist/stacks/<stack>/` paths already locked by Phase-6's
golden tree (the contract `release.yml` regenerates).

## 5. Decisions Made

For each non-trivial choice made under conditions of ambiguity:

- **Decision**: Host the `dist-protection-lint` job inside the existing
  `.github/workflows/validate.yml` as a sibling job, rather than authoring a
  separate `.github/workflows/dist-protection-lint.yml` (as the plan §10 task
  3 wording suggested).
  - **Alternatives considered**: (a) Separate workflow file
    `dist-protection-lint.yml` triggered on `pull_request` only. Pros:
    matches the plan's literal task name (`dist-protection-lint.yml`). Cons:
    two workflow files for what is one logical CI surface; two CI cache
    misses; two YAML files to keep in sync when the lint logic evolves; the
    Phase-2 and Phase-6 lessons ("extend, don't fork") explicitly counsel
    against this pattern. (b) Sibling job in `validate.yml` with an `if:
    github.event_name == 'pull_request'` conditional (chosen). Pros: one
    workflow, one cache hit, one file to maintain, follows the Phase-2 /
    Phase-6 lesson verbatim. Cons: GitHub's required-status-check matching
    is by job name (not workflow file name), so the operator must add the
    job-name string `Dist protection (Phase 7 — block human edits to dist/)`
    rather than a workflow-file-name string in the branch-protection UI.
  - **Rationale**: The Phase-2/Phase-6 lesson is the dominant constraint —
    the plan §10 task 3's `.yml` filename was a placeholder, not a contract.
    `docs/branch-protection-config.md` §2.2 now explicitly documents that
    required status checks are matched by job name, closing the only
    operator-confusion vector this introduces. The next-session prompt's
    "PHASE-7 CONTEXT" block ratifies this exact choice ahead of time.
  - **Reversible?**: Yes — a future phase could split into a separate
    workflow file with a no-content change to `validate.yml`.

- **Decision**: Reconcile the `golden-tests` placeholder in
  `docs/branch-protection-config.md` to match the live `golden-snapshots`
  job name (Phase 6) rather than renaming the Phase-6 job to match the
  doc's older language.
  - **Alternatives considered**: (a) Rename the Phase-6 `golden-snapshots`
    job to `golden-tests`. Pros: matches the original plan text verbatim.
    Cons: invalidates any operator's existing branch-protection
    configuration that references `golden-snapshots`; the rename surfaces
    in every operator's audit log; the existing job name is actually MORE
    descriptive (it covers both golden-snapshot tests AND ArchUnit-fixture
    shape tests). (b) Update the doc to match the live job name (chosen).
    Pros: zero churn on a working CI job; the more descriptive name is
    preserved; one targeted doc edit closes the gap.
  - **Rationale**: The plan's `golden-tests` name was a placeholder
    authored before the Phase-6 job was implemented. The Phase-6 author
    chose the more descriptive `golden-snapshots` deliberately (because
    the job also covers archunit-fixture shape tests, not just golden
    snapshots). Renaming an established CI job for documentation symmetry
    is a strict net loss. The doc update includes an explicit historical
    note explaining the reconciliation so operators reading this in 6
    months understand the lineage.
  - **Reversible?**: Yes, but no good reason to do so.

- **Decision**: Mint the App installation token via
  `actions/create-github-app-token@v1` (official action) rather than
  inlining the JWT-and-token-exchange flow with `curl` calls in the
  workflow.
  - **Alternatives considered**: (a) Inline JWT-mint via `openssl` + `curl
    POST /app/installations/{id}/access_tokens`. Pros: zero dependency on a
    third-party action. Cons: ~30 lines of bash that hand-rolls a JWT,
    including base64-encoding the header, payload, and signature; rotation
    of the action's algorithm (RS256 → newer) becomes a manual workflow
    edit; debugging is harder. (b) Use the official action (chosen). Pros:
    one line; the action is maintained by GitHub's own Actions team
    (`actions/`); rotation and algorithm updates are transparent. Cons:
    introduces a pinned third-party dependency at `@v1`.
  - **Rationale**: The action is published under the `actions/` GitHub
    organization (i.e., GitHub itself) and is the canonical recommendation
    in GitHub's own docs for App-token minting in workflows. The
    third-party-risk surface is the same as `actions/checkout` and
    `actions/setup-python` which the repo already uses. The token expiry
    (one hour) is more than enough for a single release run.
  - **Reversible?**: Trivial — replace with an inline `curl` step if the
    Standards Architect ever requires zero non-`actions/` deps.

- **Decision**: Make the integration tests for `compute_semver_bump.py`
  conditional via a `@requires_git` skip marker keyed to a runtime probe of
  whether `git init` works in the sandbox, rather than removing the
  integration tests entirely or making them run unconditionally (and fail
  in the local sandbox).
  - **Alternatives considered**: (a) Remove the integration tests; rely
    only on unit tests. Pros: zero test failures locally. Cons: loses
    coverage of the actual subprocess-and-git wiring that the release
    workflow depends on; a future regression in git invocation would slip
    through. (b) Run unconditionally; accept local failures. Pros:
    surfaces every test failure to the developer. Cons: the failures
    aren't real bugs — they're sandbox limitations — and noise destroys
    the developer's ability to spot real regressions. (c) Conditional skip
    via a runtime probe (chosen). Pros: integration tests run on CI
    (GitHub Actions has no `.git/hooks/` write restriction) AND are
    skipped locally when the sandbox blocks them; the skip reason is
    explicit so the next agent reading the test output understands why.
    Cons: the agent's local "all green" status is `267 passed + 7 skipped`
    rather than `274 passed`.
  - **Rationale**: The CI environment is the source of truth for whether
    these tests pass; the local environment is a development convenience.
    A probe that gracefully degrades when the environment cannot support
    the test type is exactly the pattern pytest's `@pytest.mark.skipif`
    is designed for.
  - **Reversible?**: Trivial — remove the marker if a future sandbox lifts
    the restriction.

- **Decision**: The `--all-stacks` CLI flag is mutually exclusive with
  `--stack` (argparse `add_mutually_exclusive_group(required=True)`)
  rather than allowing `--stack` to override `--all-stacks` or vice versa.
  - **Alternatives considered**: (a) Mutual exclusion (chosen). Pros: one
    unambiguous mode per invocation; argparse rejects ambiguous CLIs at
    parse time with a clear error. Cons: a `--all-stacks` user cannot
    additionally pass `--stack foo` to "do everything plus foo again."
    (b) `--stack` overrides `--all-stacks`. Pros: composable. Cons: every
    CI invocation that wants `--all-stacks` becomes a "did you forget to
    drop the earlier `--stack`?" debugging exercise. (c) `--all-stacks`
    overrides `--stack`. Same problem in reverse.
  - **Rationale**: The release workflow always uses `--all-stacks`. Local
    development always uses `--stack <one>`. There is no legitimate use
    case for both, so making them mutually exclusive eliminates an entire
    class of confusion. The test
    `test_all_stacks_is_mutually_exclusive_with_stack` locks this.
  - **Reversible?**: Trivial — drop the `add_mutually_exclusive_group`
    wrapper if a real use case for "both" emerges.

- **Decision**: The `release.yml` workflow always runs `rm -rf dist/stacks`
  before the compiler regenerates it, rather than relying on the compiler
  to overwrite individual files in place.
  - **Alternatives considered**: (a) Trust the compiler to overwrite all
    files. Pros: faster (no rm step). Cons: if a source rule is DELETED
    between releases, the corresponding output file would remain in
    `dist/stacks/` from the prior compile. The compiler does not currently
    detect "this output file is stale" — it only writes new files. (b)
    Wipe `dist/stacks/` before compile (chosen). Pros: deletes-then-recreates
    is the safest "regenerate from source" semantic; deletes of source
    rules propagate naturally. Cons: marginal extra disk I/O.
  - **Rationale**: The release semantic is "the dist tree at tag `v2.4.0`
    EQUALS the compiler's output for `main` at the release commit." Any
    drift from that equation is a bug. The wipe-then-regenerate pattern
    enforces the equation mechanically.
  - **Reversible?**: Yes — drop the `rm -rf` if a future compiler grows a
    delete-stale-outputs pass.

## 6. Blockers Encountered

- **Blocker**: First draft of the integration tests for
  `compute_semver_bump.py` used pytest's default `tmp_path` fixture,
  which resolves to `/private/var/folders/...` on macOS. The local
  sandbox blocks all writes to `.git/hooks/` and `.git/config` regardless
  of path — meaning `git init` itself fails with `Operation not permitted`
  before any test logic runs.
  - **Resolution**: Two changes — (a) switched to a workspace-rooted
    temp fixture under `tests/.tmp/` (added to `.gitignore`); (b) added a
    runtime `_git_init_works_in_this_env()` probe and an `@requires_git`
    skip marker on all seven git-touching tests. Unit tests (27) still run
    unconditionally and cover the same business logic; integration tests
    (7) run on CI (which has no such sandbox) and skip locally.
  - **Carry-forward**: When future phases author tests that touch `git`,
    the same skip-marker pattern is the path of least resistance. The
    `_git_init_works_in_this_env()` probe is a small helper that any
    future test file can copy; consider extracting to a shared
    `tests/conftest.py` if a third test file needs it.

- **Blocker**: First draft of `tools/generate_changelog.py` called
  `git diff HEAD -- source/` even on the first-release path (no previous
  tag), which fails on a fresh repo with no commits yet (`fatal: bad
  revision 'HEAD'`).
  - **Resolution**: Branched on `previous_tag is None` BEFORE calling git
    — the first-release path now walks `(REPO_ROOT / "source").rglob("*.md")`
    directly and lists every current source file as Added. Lines 247–254
    of `tools/generate_changelog.py` document this branching with an
    inline comment.
  - **Carry-forward**: Any future tool that diffs against the previous
    tag must handle the "no previous tag" case explicitly. The
    `_resolve_previous_tag(arg)` helper's return-None contract is the
    canonical signal.

No other blockers occurred.

## 7. Lessons that Affect Later Phases

- **Lesson — Phase 8 (consumer sync)**: The four release-helper tools in
  `tools/` (semver bump, changelog, dist README, plus the older
  `explain_golden_diff.py`) are good models for the Phase-8 Node CLI's
  internal helpers. In particular, the "dry-run first, side-effect later"
  pattern (every Phase-7 generator supports `--dry-run` that prints to
  stdout) is the right pattern for a CLI that writes into a consumer's
  working tree. Phase 8's sync should support `npx @org/standards-sync
  --dry-run` from day one.

- **Lesson — Phase 8 (consumer sync)**: The inline `KNOWN_STACKS` catalog
  in `tools/generate_dist_readme.py` is a duplicate of the runtime
  `compiler.core.stack_filter.STACKS` catalog. The duplication is
  intentional (the release workflow runs in a barebones environment
  without `pip install -e compiler/`), but it requires a defense-in-depth
  test (`test_known_stacks_align_with_compiler_stack_filter`) to prevent
  drift. Phase-8's Node CLI will face the same pattern — it needs a stack
  catalog independent of the Python compiler module. The right move is
  for Phase 8 to read `schemas/target-tools.schema.json`'s stack catalog
  (or a parallel `schemas/stacks.json`) as the single source of truth that
  every language consumes. **Recommendation**: Phase 8 adds
  `schemas/stacks.json` (1 file, ~40 lines) and refactors both
  `compiler/core/stack_filter.py::STACKS` and
  `tools/generate_dist_readme.py::KNOWN_STACKS` to read from it. The
  Phase-7 test catches the drift; Phase 8's refactor eliminates the drift
  source.

- **Lesson — Phase 8 (consumer sync)**: The `dist-protection-lint` job's
  approach (read `git diff --name-only origin/main...HEAD -- dist/` and
  fail on non-bot authors) is the same pattern Phase 8's consumer-side
  CLI should use to detect "the consumer has manually edited a file we
  installed." Specifically, the sync CLI should refuse to overwrite a
  file whose checksum differs from what it shipped, unless `--force` is
  passed. Phase 8 task 4 (idempotency) names this; the Phase-7 job's bash
  is a useful reference for the diff-detection logic.

- **Lesson — Phase 9 (pilot adoption)**: Phase 7's five operator-handoff
  carry-overs (App registration + secrets + branch-protection apply +
  test PR + first release) cluster into one "Phase 7 closing PR" workflow
  the operator runs before Phase 9 kickoff. The Pilot Liaison checklist
  for the first pilot should explicitly verify (a) `dist/CHANGELOG.md`
  exists with a `v0.1.0`-or-later section, and (b) the pilot's
  `.standards-version` pin resolves to a real release tag. Without those,
  the pilot's `npx @org/standards-sync` will hit a 404 on the tarball
  endpoint.

- **Lesson — Phase 9 (pilot adoption)**: The release workflow's
  Conventional-Commits bump computer (`tools/compute_semver_bump.py`)
  classifies anything other than `feat:`, `fix:`, and `BREAKING CHANGE`
  as `none`. This means a pilot-feedback wave that lands as `chore:` or
  `docs:` commits will accumulate `none`-classified commits until a real
  `feat:` or `fix:` lands. Pilot Liaisons should be coached to use the
  `feat:` prefix when their feedback ships a new rule and `fix:` when
  it tightens an existing one — otherwise the auto-classifier defaults
  to a patch bump that under-signals the change.

- **Lesson — Phase 10 (rollout & governance)**: The quarterly audit
  procedure in `docs/release-bot-setup.md` §6 is the right anchor for
  Phase-10's Standards Council operating cadence. The audit's three
  queries (`git log --pretty='%H %an' main -- dist/` for unauthorized
  authors; `git log --author='standards-bot' --pretty='%H'` for App
  scope creep; `gh api /repos/.../installation/permissions` for permission
  drift) should be standing agenda items for the council's first meeting
  each quarter.

- **Lesson — global**: The "extend `validate.yml`, don't fork into a new
  workflow file" lesson is now load-bearing across three phases (2, 6, 7).
  Phases 8 and 9 may be tempted to introduce a new workflow file (e.g.,
  a `pilot-telemetry.yml` for Phase 9 dashboard pushes). The lesson is
  not a hard rule — different triggers genuinely justify different
  workflow files (e.g., `release.yml` lives separately because it has
  `workflow_dispatch` + a fundamentally different identity scope). But
  every "should this be a new workflow?" decision should reach for the
  Phase-2/Phase-6 lesson first. A useful framing: a new workflow file is
  justified iff its triggers, permissions, or identity differ from every
  existing workflow.

(No `> ⚠️ Revision` callout was added to `docs/02-implementation-plan.md`
because every Phase-8+ lesson here is operational guidance for that phase's
session, not a plan revision.)

## 8. Verification Commands Run

```bash
# V-1: Every Phase-7 artifact present and non-trivial in size.
$ for f in docs/release-bot-setup.md docs/release-rollback.md \
           .github/workflows/release.yml \
           tools/compute_semver_bump.py \
           tools/generate_changelog.py \
           tools/generate_dist_readme.py \
           tests/test_compute_semver_bump.py \
           tests/test_generate_changelog.py \
           tests/test_generate_dist_readme.py \
           tests/test_phase7_end_to_end.py; do
    [[ -f "$f" ]] && echo "OK   $f ($(wc -l <"$f" | tr -d ' ') lines)" || echo "MISS $f"
  done
OK   docs/release-bot-setup.md (257 lines)
OK   docs/release-rollback.md (224 lines)
OK   .github/workflows/release.yml (265 lines)
OK   tools/compute_semver_bump.py (311 lines)
OK   tools/generate_changelog.py (363 lines)
OK   tools/generate_dist_readme.py (282 lines)
OK   tests/test_compute_semver_bump.py (345 lines)
OK   tests/test_generate_changelog.py (147 lines)
OK   tests/test_generate_dist_readme.py (140 lines)
OK   tests/test_phase7_end_to_end.py (255 lines)

# V-2: validate.yml + release.yml parse with expected job names.
$ python -c "import yaml, pathlib
for f in ['.github/workflows/release.yml', '.github/workflows/validate.yml']:
    data = yaml.safe_load(pathlib.Path(f).read_text())
    print(f, ':', list(data['jobs'].keys()))"
.github/workflows/release.yml : ['release']
.github/workflows/validate.yml : ['tree-shape', 'schema-validation', 'compiler-unit-tests', 'golden-snapshots', 'dist-protection-lint']

# V-3: --all-stacks --target all builds every stack subtree.
$ tmp=$(mktemp -d)
$ PYTHONPATH=. python -m compiler --all-stacks --target all --out "$tmp" 2>&1 | tail -2
{"ts": "...", "level": "INFO", "event": "all-stacks-complete", "stacks_compiled": 4, "stack_ids": ["java-spring-boot-2", "java-spring-boot-3", "python-fastapi-0-110", "typescript-nestjs-10"]}
$ find "$tmp/stacks" -maxdepth 1 -type d | sort | tail -4
/.../stacks/java-spring-boot-2
/.../stacks/java-spring-boot-3
/.../stacks/python-fastapi-0-110
/.../stacks/typescript-nestjs-10

# V-4: --all-stacks is byte-deterministic across runs.
$ tmpA=$(mktemp -d) && tmpB=$(mktemp -d)
$ PYTHONPATH=. python -m compiler --all-stacks --target all --out "$tmpA" 2>/dev/null
$ PYTHONPATH=. python -m compiler --all-stacks --target all --out "$tmpB" 2>/dev/null
$ diff -r "$tmpA" "$tmpB" && echo "DETERMINISTIC"
DETERMINISTIC

# V-5: --all-stacks is byte-identical to four per-stack invocations.
# (locked by tests/test_phase7_end_to_end.py::test_all_stacks_byte_identical_to_four_per_stack_runs)

# V-6: Changelog generator first-release dry-run (covers the no-previous-tag path).
$ python tools/generate_changelog.py --new-version v0.1.0 --previous-tag none --dry-run | head -10
## v0.1.0 — 2026-05-20

First release — initial corpus snapshot.

### Rules added

- `global-clean-architecture` — Clean Architecture Layer Boundaries and Dependency Inversion
- `global-logging-telemetry` — Logging and Telemetry — Structured JSON, Trace Context, Redaction
- ...

# V-7: dist README generator preserves the ADR-0004 reference (validate.yml's
# tree-shape job greps for this).
$ python tools/generate_dist_readme.py --version v0.1.0 --dry-run | grep -c '0004-single-repo-distribution'
2

# V-8: Full repo test suite.
$ PYTHONPATH=. python -m pytest tests/ -q
.............................................. (...) ...........            [100%]
269 passed, 7 skipped in 7.35s

# V-9: Linter sanity over every Phase-7 file.
$ # ReadLints over: tools/*.py, tests/test_*7*.py, tests/test_generate_*.py,
$ #                 tests/test_compute_semver_bump.py, .github/workflows/*.yml,
$ #                 compiler/__main__.py, docs/release-*.md, Makefile.
No linter errors found.

# V-10: Make targets work end-to-end.
$ make help
Phase-6 developer targets:
  make update-golden         Regenerate tests/golden/* from source/.
  make explain-golden-diff   Summarize per-rule deltas after a golden failure.
  make test                  Run the full pytest suite.
  make golden-test           Run only the golden snapshot tests.

Phase-7 developer targets:
  make release-dry-run       Compute the next version + render CHANGELOG/README
                             previews WITHOUT committing/tagging/pushing. Mirrors
                             the workflow_dispatch dry-run=true branch.

# V-11: Argparse mutual exclusion is enforced.
$ PYTHONPATH=. python -m compiler --stack java-spring-boot-3 --all-stacks --target all --out /tmp/out 2>&1 | head -2
usage: python -m compiler [-h] (--stack STACK | --all-stacks) --target ...
python -m compiler: error: argument --all-stacks: not allowed with argument --stack

# V-12: dist-protection-lint failure-message strings are pinned by tests.
$ PYTHONPATH=. python -m pytest \
    tests/test_phase7_end_to_end.py::test_dist_protection_lint_failure_message_cites_adr_0004 \
    -v
tests/test_phase7_end_to_end.py::test_dist_protection_lint_failure_message_cites_adr_0004 PASSED
```

## 9. Handoff to Next Session

- **Next phase**: 8 — Consumer-Side Sync Tool (see
  `docs/02-implementation-plan.md` §11).
- **Next-session prompt**: written to
  `docs/execution-log/next-session-prompt.md` (overwriting the Phase-7 prompt).
- **Pre-requisites for next phase that are now satisfied**:
  - `python -m compiler --all-stacks --target all --out <dir>` regenerates
    every stack's subtree in one invocation with byte-deterministic output
    — locked by `test_all_stacks_byte_identical_to_four_per_stack_runs` and
    by the Phase-6 determinism test. Phase 8's sync CLI fetches stacks from
    this layout.
  - The release workflow is wired and ready to dispatch as soon as the
    operator provisions the App + secrets + branch-protection update.
    Phase 8 can develop and test its sync CLI against a `dist/` tree built
    locally by `make release-dry-run` — no live tag required.
  - `docs/release-rollback.md` is the canonical reference Phase 8's
    consumer-side error messages should link to when a pilot's pinned tag
    breaks.
- **Open questions for the operator**:
  - **Phase 7 — five operator-handoff items** (none block Phase 8 kickoff;
    all should close before Phase 9 pilot kickoff):
    1. Register the `@standards-bot` GitHub App per
       `docs/release-bot-setup.md` §2.1.
    2. Store `STANDARDS_BOT_APP_ID` and `STANDARDS_BOT_PRIVATE_KEY`
       repo secrets per §2.2.
    3. Install the App on `engineering-standards-central` per §2.3.
    4. Apply the §2.4 branch-protection update (add `standards-bot` as
       an allowed pusher) and attach the screenshot to the Phase-7
       closing PR. This is Phase-7 AC4.
    5. Run the first `release.yml` dispatch (can be done with
       `dry-run: true` first to preview). Closes AC2 and AC5.
  - **Phase 8 forward-question**: should the Phase-8 sync CLI's stack
    detection share a single source of truth with the compiler's
    `STACKS` catalog (the Phase-7 lesson §7 recommends authoring
    `schemas/stacks.json` to host the canonical list)? Operator to
    triage with the Standards Architect during Phase 8 kickoff.
  - **Pre-existing carry-overs from Phases 0/1/3/6** (all still open;
    none block Phase 8):
    - AI Enablement PM ADR sign-off (Phase 0).
    - Cursor-load smoke test (Phase 1).
    - Standards-Architect sign-off on the 18 Phase-3 rules.
    - The `java-spring-di-constructor-injection-mandate`'s
      `framework_version: ">=4.3"` (Spring Framework version, not
      Spring Boot) exclusion gap from Phase 3.
    - The Phase-6 AC1 carry-forward (live `mvn test` against a Spring
      Boot 3 sample with deliberate violations) — natural Phase-9
      surface, not Phase-8's responsibility.
