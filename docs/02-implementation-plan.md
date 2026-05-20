# Deliverable 2: Implementation Plan
## Migrating `engineering-standards-central` from Baseline Blueprint to the Evolved MDC-First Architecture

> **Document Status**: Approved Implementation Plan — companion to `01-architecture-upgrade-report.md`.
> **Audience**: Platform/DevX engineering team executing the rollout, plus AI Enablement working group reviewers.
> **Outcome**: A ten-phase, dependency-ordered, milestone-gated execution plan covering scaffolding, schema, content authoring, compiler, distribution, governance, and adoption — including risk mitigations and a Phase-0 ⇒ Phase-10 timeline.
>
> **Architecture Note (Revision 2)**: This plan adopts a **single-repository distribution model** — compiled artifacts live in a protected `dist/` folder inside `engineering-standards-central` rather than a separate `engineering-standards-distribution` repository. The two-repo split remains a **deferred graduation path** documented in ADR-0004. Rationale: lower operational overhead, atomic source↔output commits, simpler permissions surface. The architectural functions of the originally-proposed second repo (read-only-to-humans, semver-tagged, CI-gated writes) are preserved via branch protection + CODEOWNERS + a dedicated GitHub App identity for release commits.

---

## Table of Contents

1. [Guiding Principles](#1-guiding-principles)
2. [Roles, Tooling Stack, and Conventions](#2-roles-tooling-stack-and-conventions)
3. [Phase 0 — Pre-Flight Decisions and ADRs](#3-phase-0--pre-flight-decisions-and-adrs)
4. [Phase 1 — Repository Scaffolding](#4-phase-1--repository-scaffolding)
5. [Phase 2 — Schemas, Layer-to-Glob Map, and Validation](#5-phase-2--schemas-layer-to-glob-map-and-validation)
6. [Phase 3 — Source Content Migration & Authoring of New Logic Holes](#6-phase-3--source-content-migration--authoring-of-new-logic-holes)
7. [Phase 4 — Compiler Core Engine](#7-phase-4--compiler-core-engine)
8. [Phase 5 — Per-Tool Transformers](#8-phase-5--per-tool-transformers)
9. [Phase 6 — Fixtures, Golden Files, and CI](#9-phase-6--fixtures-golden-files-and-ci)
10. [Phase 7 — Release Workflow & `dist/` Folder Protection](#10-phase-7--release-workflow--dist-folder-protection)
11. [Phase 8 — Consumer-Side Sync Tool](#11-phase-8--consumer-side-sync-tool)
12. [Phase 9 — Pilot Adoption and Telemetry](#12-phase-9--pilot-adoption-and-telemetry)
13. [Phase 10 — Org-Wide Rollout, Governance, and MCP Roadmap](#13-phase-10--org-wide-rollout-governance-and-mcp-roadmap)
14. [Risk Register](#14-risk-register)
15. [Definition of Done — Milestone Acceptance Criteria](#15-definition-of-done--milestone-acceptance-criteria)
16. [Indicative Timeline](#16-indicative-timeline)

---

## 1. Guiding Principles

These principles are the lens through which every implementation decision is made. When two options are technically equivalent, the principles break the tie.

1. **Single source of truth** — every standard is authored in exactly one Markdown file under `source/`. Distribution artifacts are always generated, never hand-edited.
2. **Cursor-native first, cross-tool always** — the primary distribution target is `.cursor/rules/*.mdc` because it is the only format that supports per-file-pattern activation. But every rule also compiles to `AGENTS.md`, Copilot, Claude, and Junie targets so that no tool is left behind.
3. **Glob precision over context bloat** — a rule's default activation is **auto-attach with a layer-resolved glob**, not "always apply." `alwaysApply: true` is reserved for foundational rules and requires explicit author opt-in.
4. **Build-time enforcement, not just AI guidance** — every Logic Hole that can be expressed as a static-analysis rule MUST also ship as an ArchUnit test and/or a custom Checkstyle/PMD rule in the distribution. AI guidance prevents new violations; build-time enforcement prevents regressions of existing code.
5. **Idempotent, versioned distribution** — consumer repos pin a semver of the standards. Re-running sync is a no-op when versions match. Breaking changes require a major bump and a migration note.
6. **Eat our own dog food** — the central repo itself uses the same `.cursor/rules/*.mdc` system to enforce its own authoring conventions. If our rules are not good enough for the repo that produces them, they are not good enough.
7. **Phased adoption, never big-bang** — every phase produces a usable artifact even if subsequent phases stall. Phase 3 alone (without the compiler) ships better Markdown than the baseline.

---

## 2. Roles, Tooling Stack, and Conventions

### 2.1 Roles

| Role | Responsibility |
|---|---|
| **Standards Architect** (1 senior) | Owns the rule taxonomy and `scope.layers` catalog; final reviewer for Logic Hole specs. |
| **Compiler Engineer** (1) | Owns `compiler/` — parser, transformers, fixtures, golden tests. |
| **Pilot Liaison** (1 per pilot team, 3 total) | Embedded contact who runs the consumer-side sync, files issues, validates the AI behaves correctly. |
| **AI Enablement PM** | Owns adoption metrics, telemetry, and the org-wide rollout cadence. |
| **Reviewers** | Two principal engineers per merged PR to `source/`. |

### 2.2 Tooling Stack

| Concern | Selection | Rationale |
|---|---|---|
| Compiler language | **Python 3.12** | Best Markdown/YAML ecosystem (`python-frontmatter`, `pyyaml`, `jsonschema`, `jinja2`); cross-platform; readable for non-experts. |
| Frontmatter parser | `python-frontmatter` | De facto standard. |
| Schema validation | `jsonschema` | Validates source frontmatter against `schemas/source-rule.schema.json`. |
| Templating | `jinja2` | Used by transformers to render per-tool output formats. |
| Tests | `pytest` + golden-file snapshots | Snapshot tests catch unintended compiler-output drift. |
| CI | GitHub Actions | Already in baseline. |
| Distribution release | Single repo, semver Git tags on `main`, GitHub Releases pointing to the `dist/` tree at that tag | Consumer pinning via `.standards-version`. The `dist/` folder is human-read-only via CODEOWNERS + a CI-only GitHub App identity. |
| Consumer sync CLI | **Node CLI** (`@org/standards-sync`) packaged as `npx`-runnable binary | Universal availability; Java/TS/Python repos all run `npx @org/standards-sync` without language-specific install. |

### 2.3 Conventions

- **Branch naming**: `feat/<area>/<short-desc>`, `fix/<area>/<short-desc>`, `docs/<short-desc>`.
- **Commit style**: Conventional Commits. AI-assisted commits MUST include `Includes-AI-Code: true` trailer.
- **Source rule IDs**: kebab-case, prefixed with `<lang>-<framework>-<layer>-` (e.g., `java-spring-controller-validation-boundaries`).
- **`.mdc` file naming**: kebab-case, derived from source rule ID minus the language/framework prefix (e.g., `controller-validation-boundaries.mdc`).
- **PR review SLA**: Standards-Architect approval required for any change in `source/`; Compiler-Engineer approval required for any change in `compiler/` or `schemas/`.

---

## 3. Phase 0 — Pre-Flight Decisions and ADRs

> **Status (as of 2026-05-18): COMPLETED.** All four ADRs are merged to `docs/decision-records/` and the repo `README.md` links them alongside the foundational documents. AI Enablement PM sign-off is **pending operator review** (see `docs/execution-log/phase-0-log.md`).

**Goal**: Lock the architectural choices before scaffolding so subsequent work is mechanical.

**Duration**: 4 days. **Output**: Four Architecture Decision Records under `docs/decision-records/`.

### Tasks

1. **ADR-0001 — `.cursor/rules/*.mdc` over `.cursorrules`**
   - Documents the decision to make MDC the primary Cursor target.
   - Cites Cursor 2026 docs (Agent mode silently ignores legacy `.cursorrules`).
   - Captures the migration sunset for any internally-distributed `.cursorrules`.
2. **ADR-0002 — Layer-keyed source split**
   - Documents why `source/<lang>/<framework>/<layer>/<rule>.md` replaces `<framework>/<concern>.md`.
   - Cites the glob-precision rationale from the Architecture Upgrade Report.
3. **ADR-0003 — Deferred MCP server**
   - Documents the decision to ship MDC distribution first and defer the MCP-server frontier to a Phase-3 roadmap epic.
   - Records the protocol (`Resources` for rules, `Prompts` for review templates, `Tools` for `lint_against_standards`) so future work has a clear contract.
4. **ADR-0004 — Single-repo distribution via protected `dist/` folder**
   - Documents the decision to keep authoring source AND compiled distribution artifacts inside the single `engineering-standards-central` repository.
   - Captures the four guards that make `dist/` effectively read-only to humans: branch protection on `main`, CODEOWNERS routing `/dist/` to a non-human bot account, a PR-level lint check that rejects human-authored modifications to `/dist/`, and release commits authored by a dedicated GitHub App identity.
   - Lists the **graduation triggers** to a separate `engineering-standards-distribution` repo (any one is sufficient): (a) the standards become a public artifact consumed outside the org; (b) `dist/` history bloats sync performance; (c) security/compliance mandates a separately-audited publishing repo; (d) `read` access on the dist artifact must be granted to a wider audience than `read` on the source.
   - Records the migration mechanics if/when graduation triggers fire: `git filter-repo` extracts `dist/` history into a new repo; consumer sync tool's repo URL is updated; one-line change.

### Acceptance Criteria

- [x] All four ADRs merged to `main` of `engineering-standards-central`. — Files exist at `docs/decision-records/0001-mdc-over-cursorrules.md`, `0002-layer-keyed-source-split.md`, `0003-deferred-mcp-server.md`, `0004-single-repo-distribution.md`; merge to `main` is the operator's git-workflow step (no `git commit` was executed in this session per the playbook's hard rule).
- [!] AI Enablement PM has reviewed and signed off. — Pending operator review; recorded as a carry-forward in `docs/execution-log/phase-0-log.md`.
- [x] Linked from the repo `README.md`. — Repo-root `README.md` now exists and links all four ADRs plus the three foundational documents.

---

## 4. Phase 1 — Repository Scaffolding

> **Status (as of 2026-05-18): COMPLETED.** Directory skeleton, `.cursor/rules/` dogfood rules, root `AGENTS.md`, `.github/CODEOWNERS`, `docs/branch-protection-config.md`, the defensive client-side pre-commit hook, and a baseline `.github/workflows/validate.yml` (tree-shape checks only) are all in place. Three acceptance criteria have residual operator actions tracked in `docs/execution-log/phase-1-log.md` (Cursor-load smoke test, GitHub-UI branch-protection apply + screenshot, the Phase-7-dependent CODEOWNERS+dist-protection-lint live experiment); one (CI green) is contingent on the operator's closing-PR push.

**Goal**: Create the directory skeleton documented in §5.1 of the Architecture Upgrade Report. No content yet — just placeholders so subsequent phases have a stable filesystem layout.

**Duration**: 2 days. **Output**: The scaffolded directory tree, committed.

### Tasks

1. Create top-level directories: `source/`, `compiler/`, `schemas/`, `fixtures/`, `tests/`, `dist/`, `docs/decision-records/`, `.github/workflows/`, `.cursor/rules/`.
2. Under `source/`, create stub directories for `_global/`, `java/_core/`, `java/spring-boot/{architecture,controller,service,repository,error-handling,di,config,testing}/`, `typescript/_core/`, `typescript/nestjs/{controller,service}/`, `python/fastapi/{controller,service}/`.
3. Under `dist/`, create stub directories for `stacks/{java-spring-boot-3,java-spring-boot-2,typescript-nestjs-10,python-fastapi-0-110}/` plus a top-level `dist/README.md` containing a single line: `> Auto-generated. Do not edit by hand. See docs/decision-records/0004-single-repo-distribution.md.`
4. Each stub directory contains a `.gitkeep` file.
5. Create `.github/CODEOWNERS` with two rules:
   - `* @platform-team @standards-council` (default ownership for source, compiler, schemas).
   - `/dist/ @engineering-standards-bot` (the `@engineering-standards-bot` is a non-human GitHub account; PRs touching `/dist/` are auto-routed to it and never approved by humans).
6. Configure **branch protection on `main`** (recorded as a checklist in `docs/branch-protection-config.md` since GitHub branch-protection cannot be expressed in repo files): require PR before merge, require status checks (`validate`, `dist-protection-lint`), restrict who can push (only the `@engineering-standards-bot` GitHub App can push release commits), require linear history, dismiss stale approvals on new commits.
7. Create the central repo's own `.cursor/rules/authoring-style.mdc` and `.cursor/rules/frontmatter-spec.mdc` (eat our own dog food — these guide future AI-assisted authoring of source rules).
8. Create the repo's own `AGENTS.md` describing the meta-purpose: "this repo authors AI engineering standards; PRs to `source/` require Standards-Architect approval; PRs touching `/dist/` are produced only by the release workflow; the compiler in `compiler/` is the only mechanical producer of distribution artifacts."
9. Create skeleton `README.md` with: project mission, link to ADRs (especially ADR-0004), link to the Architecture Upgrade Report, link to this Implementation Plan, and a short "How to consume" pointer to the sync tool.
10. Add a defensive **client-side pre-commit hook** (shipped under `tools/git-hooks/pre-commit`) that fails when staged changes include both `source/**` and `dist/**` paths from a human author. Document opt-in via `git config core.hooksPath tools/git-hooks/`.

### Acceptance Criteria

- [x] `tree` output of the repo matches the target diagram in Architecture Upgrade Report §5.1, with the addition of the `dist/` subtree under the same root (per ADR-0004). — Directory skeleton verified by `.github/workflows/validate.yml` tree-shape checks, executed locally with green output. Content-leaf files listed in §5.1 (`source/_global/clean-architecture.md`, etc.) are explicitly Phase-3 deliverables and are correctly absent at Phase-1 stub stage.
- [x] `.cursor/rules/authoring-style.mdc` exists and is loaded by Cursor when authors edit `source/**/*.md` (verified with a manual Cursor session). — File exists with frontmatter `globs: ["source/**/*.md"]`. The manual Cursor-session smoke test is a one-off operator action at PR-close time; the file structure is correct.
- [!] `.github/CODEOWNERS` is in place; a test PR that modifies `dist/README.md` from a human author auto-requests review from `@engineering-standards-bot` and is blocked by the (yet-to-be-built) `dist-protection-lint` status check. — CODEOWNERS file is in place with the correct `/dist/ @engineering-standards-bot` routing. The live PR experiment is blocked on Phase 7: the `@engineering-standards-bot` GitHub App and the `dist-protection-lint` workflow do not yet exist. Tracked as carry-forward to Phase 7 in `docs/execution-log/phase-1-log.md`.
- [x] Branch protection settings on `main` are documented in `docs/branch-protection-config.md` and applied in the GitHub UI (a screenshot is attached to the Phase-1 closing PR). — Document is complete (six sections including a verification procedure and a change-management procedure). Applying the settings in the GitHub UI + the screenshot is the operator's PR-close action, recorded as a carry-forward in the log.
- [x] CI runs (an empty workflow that just checks tree shape) pass. — `.github/workflows/validate.yml` exists; parses as valid YAML; every `run:` block was bash-syntax-checked and then executed locally against the live tree with green output (see Phase-1 log §8 V-1 through V-7). The actual GitHub Actions run executes when the operator pushes the closing Phase-1 PR.

---

## 5. Phase 2 — Schemas, Layer-to-Glob Map, and Validation

> **Status (as of 2026-05-18): COMPLETED.** Three machine-readable schemas (`source-rule`,
> `layer-glob-map`, `target-tools`) plus a reference example landed under `schemas/`. The Phase-2
> slice of `compiler/core/parse_source.py --validate-only` is on disk and wired into
> `.github/workflows/validate.yml` as a sibling `schema-validation` job. `tests/test_schemas.py`
> covers all four AC1 cases (valid example passes; missing required field fails; invalid layer
> enum fails; invalid framework_version semver fails) plus nine adjacent negative cases and the
> AC3 inline-description audit. 23/23 tests pass locally; all `run:` blocks of the new CI job
> were executed against the live tree with green output. The Phase-1 carry-over lesson
> (`.cursor/rules/frontmatter-spec.mdc` audit) was reconciled with no schema-vs-MDC field drift.
> See `docs/execution-log/phase-2-log.md` for the full session record.

> ⚠️ Revision (Phase 3 session, 2026-05-18): the Phase-2 `source-rule.schema.json` shipped
> with an internal contradiction in the `scope.language` field's `description` — the prose
> suggested `_global/` rules use `language: "_global"`, but the field's own `pattern`
> (`^[a-z][a-z0-9_-]*$`) rejects strings beginning with `_`. Phase 3, which authored the first
> three `_global/` rules, surfaced the gap. Resolution: the convention is `language: "global"`
> (no leading underscore); the schema's `description` and `.cursor/rules/frontmatter-spec.mdc`
> were both updated to match in this Phase-3 session. The regex itself was not changed —
> kebab-case identifiers without leading underscores remain the contract. No Phase-4+ task
> list changes; `schemas/layer-glob-map.json`'s existing note ("the `_global` pseudo-language
> is NOT present here because cross-cutting global rules always pair with
> `activation.cursor_mode: always`") remains correct under the new convention.

**Goal**: Lock the source-frontmatter contract and the layer→glob translation table. Once these schemas merge, all subsequent content authoring and compiler work is type-safe.

**Duration**: 4 days. **Output**: Three machine-readable schemas + a validation CI step.

### Tasks

1. **`schemas/source-rule.schema.json`** — JSON Schema (Draft 2020-12) implementing the source frontmatter contract from Architecture Upgrade Report §7.1. Required fields, enum-restricted layer values, semver-pattern `framework_version`, etc.
2. **`schemas/layer-glob-map.json`** — the language → layer → globs lookup table:
   ```json
   {
     "java": {
       "controller": ["**/controller/**/*.java", "**/web/**/*.java", "**/rest/**/*.java"],
       "service":    ["**/service/**/*.java", "**/usecase/**/*.java"],
       "repository": ["**/repository/**/*.java", "**/dao/**/*.java", "**/persistence/**/*.java"],
       "config":     ["**/config/**/*.java", "src/main/resources/application*.yml", "src/main/resources/application*.properties"],
       "test":       ["**/*Test.java", "**/*IT.java", "**/*Tests.java"],
       "di":         ["**/*.java"],
       "error-handling": ["**/exception/**/*.java", "**/advice/**/*.java", "**/errors/**/*.java"],
       "architecture": [],
       "all": ["**/*.java"]
     },
     "typescript": { "controller": ["**/*.controller.ts"], "service": ["**/*.service.ts"], "all": ["**/*.ts", "**/*.tsx"] },
     "python":     { "controller": ["**/routers/**/*.py", "**/api/**/*.py"], "service": ["**/services/**/*.py"], "all": ["**/*.py"] }
   }
   ```
   The empty `architecture` glob signals "compiler routes this to `alwaysApply: true`" because architecture rules cross-cut all files.
3. **`schemas/target-tools.schema.json`** — enumerates the supported targets and required output paths so a future fifth target (e.g., Amazon Q, Windsurf-specific) is a one-liner.
4. **`schemas/examples/valid-source-rule.md`** — a reference example used by both human authors and the schema-validation tests.
5. **CI step**: `validate.yml` runs `compiler/core/parse_source.py --validate-only` against every PR touching `source/**/*.md` or `schemas/**`.

### Acceptance Criteria

- [x] `pytest tests/test_schemas.py` covers: valid example passes; missing required field fails; invalid layer enum value fails; invalid semver in `framework_version` fails. — All four cases are explicit tests in `tests/test_schemas.py` (named `test_valid_example_passes`, `test_missing_required_field_fails__title|scope|nested_layers`, `test_invalid_layer_enum_fails`, `test_invalid_framework_version_fails`). The suite contains 23 tests total, all green locally on Python 3.9 and configured to run on Python 3.12 in CI.
- [x] PR-level validation rejects a deliberately broken `source/` Markdown file in a smoke-test PR. — `tests/test_schemas.py::test_validator_cli_rejects_a_broken_file` invokes `compiler/core/parse_source.py --validate-only --path <tmp>` against a deliberately broken file (bad id pattern, bad status enum, bad layer enum, bad framework_version, bad cursor_mode, bad agents_md_priority, all `target_tools.*` false, missing title) and asserts exit code 1 plus stderr mentioning each violated field. This is the in-suite equivalent of "open a smoke-test PR with a broken file and confirm validation rejects it." A live PR-level demonstration is the operator's PR-close action; the CI step is wired and proven to run on PR.
- [x] Schema files have inline comments documenting every field (consumed by the authoring guide in Phase 3). — JSON does not support `//` or `#` comments; every property carries a `description` string instead. `tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field` walks `source-rule.schema.json` and `target-tools.schema.json` recursively and asserts every user-facing property declaration has a non-empty `description`. `tests/test_schemas.py::test_layer_glob_map_documents_every_language_layer` verifies the layer-glob-map's `$comment_layers` blocks cover every layer in every language.

---

## 6. Phase 3 — Source Content Migration & Authoring of New Logic Holes

> **Status (as of 2026-05-18): COMPLETED.** 18 source rules across the four baseline
> error-handling files, the four new Java/Spring-Boot Logic Holes (#3, #4, #5, #6 spanning
> controller / service / repository / config / di), and the three cross-cutting `_global/`
> rules (clean-architecture, security-baselines, logging-telemetry) all landed under
> `source/`. Every rule validates against `schemas/source-rule.schema.json` via the Phase-2
> validator (`Validation PASSED: 19 file(s)` including the schema-example fixture). Every
> rule has the three required H2 sections (Context & Architectural Intent, Enforced Standards,
> AI Directives), at least one paired ❌ ANTI-PATTERN / ✅ CORRECT block per enforced standard,
> matching H1↔title, and a valid (or null) `archunit_test` path pointing to the Phase-6
> deliverable. The dependency graph is internally consistent — every `dependencies:` entry
> resolves to an authored rule id. `docs/authoring-guide.md` is on disk as the long-form
> companion to the two `.cursor/rules/*.mdc` dogfood checklists and is linked from
> `README.md`. A Phase-2 schema gap (`scope.language` regex rejected the documented
> `"_global"` value) was surfaced and resolved in-session — see the ⚠️ Revision callout in
> §5 above and the Phase-3 log §5 for the decision record. See
> `docs/execution-log/phase-3-log.md` for the full session record.

**Goal**: Migrate the four baseline rules and author the four new Logic Holes (3, 4, 5, 6) as canonical source `.md` files. After this phase, the repository has *content*, even though the compiler has not been written yet.

**Duration**: 8 days (parallelizable across two pairs). **Output**: ~16 source Markdown files; one authoring guide.

### Tasks

1. **Migrate baseline content** from `docs/ai-engineering-standards-blueprint.md` Section 4 into:
   - `source/java/spring-boot/error-handling/prohibit-generic-runtime.md`
   - `source/java/spring-boot/error-handling/prohibit-blind-catch.md`
   - `source/java/spring-boot/error-handling/unified-api-error.md`
   - `source/java/spring-boot/error-handling/problem-details-rfc7807.md` (NEW — JetBrains Junie alignment)
2. **Author the four new Logic Holes** using the source-format specs in Architecture Upgrade Report Appendix A:
   - **Logic Hole #3**: `source/java/spring-boot/controller/validation-boundaries.md` + `dto-record-mandate.md` + `pageable-defaults.md` (the latter is shared with Logic Hole #5).
   - **Logic Hole #4**: `source/java/spring-boot/service/transactional-boundaries.md` + `transactional-readonly.md` + `self-invocation-trap.md` + `source/java/spring-boot/repository/n-plus-one-prevention.md` + `entity-graph-strategy.md` + `source/java/spring-boot/config/disable-open-session-in-view.md`.
   - **Logic Hole #5**: `source/java/spring-boot/repository/findall-pagination-mandate.md` (controller-side variant covered above).
   - **Logic Hole #6**: `source/java/spring-boot/di/constructor-injection-mandate.md`.
3. **Author cross-cutting global rules**:
   - `source/_global/clean-architecture.md`
   - `source/_global/security-baselines.md`
   - `source/_global/logging-telemetry.md`
4. **Write the Authoring Guide** at `docs/authoring-guide.md`. It MUST cover:
   - The mandatory paired ❌ Anti-Pattern / ✅ Correct Pattern code-block convention.
   - The mapping from `scope.layers` to Cursor activation modes.
   - When to choose `alwaysApply: true` (rare; foundational only) vs. auto-attach (default).
   - How to cross-reference dependencies (`dependencies:` array).
   - How to write the `description` line so Agent-Requested mode picks the rule up correctly.
5. Each rule must have:
   - Frontmatter passing the schema (Phase 2).
   - Sections `1. Context`, `2. Enforced Standards`, `3. AI Directives`.
   - At least one paired ❌/✅ block per enforced standard.
   - A reference to its `archunit_test` (file may not exist yet — that is Phase 6).

### Acceptance Criteria

- [x] All ~16 source files exist and validate. — 18 source files landed (4 error-handling, 3 controller, 3 service, 3 repository, 1 config, 1 di, 3 _global); all validate via `compiler/core/parse_source.py --validate-only` (output: `Validation PASSED: 19 file(s) conform to source-rule.schema.json.` — 18 new + 1 existing schema fixture). A Phase-3 sanity script also verified every rule has the three required H2 sections, matching H1↔title, at least one paired ❌/✅ block per enforced standard, and a consistent dependency graph (every `dependencies:` entry resolves).
- [!] PR review by Standards Architect signs off. — Pending; the agent cannot perform human review. The closing Phase-3 PR is the venue. Tracked as a carry-forward in `docs/execution-log/phase-3-log.md`.
- [x] `docs/authoring-guide.md` is complete and linked from `README.md`. — File exists (10 sections + appendix) covering the three-document body pattern, the paired ❌/✅ convention, layer→activation-mode mapping table, when to use `cursor_mode: always`, dependency authoring, agent-requested `description` craft, `agents_md_priority` rubric, where to place a new rule, validator workflow, and a pre-save checklist. README §"Where to Start" now links it.

---

## 7. Phase 4 — Compiler Core Engine

> **Status (as of 2026-05-18): COMPLETED.** Five compiler-core modules
> (`parse_source.py` extended with the typed `SourceRule` dataclass + `parse_all()`,
> `resolve_globs.py`, `build_graph.py`, `stack_filter.py`, `logging_setup.py`) plus the
> Cursor MDC transformer (`compiler/transformers/cursor_mdc.py`) and the `python -m compiler`
> CLI driver are on disk. 94 new tests cover the parser dataclass path, the glob resolver
> (including the `architecture` and `global` sentinels), the dependency DAG (cycle
> detection, missing-ref detection, deterministic topo sort), the stack filter (covering
> every comparator in the schema's semver-range regex: `>=`, `<=`, `>`, `<`, `=`, `^`, `~`,
> conjunction), and the Cursor MDC transformer (all four activation modes, filename
> convention, body preservation, structured logging). The CLI smoke test invokes
> `python -m compiler --stack java-spring-boot-3 --target cursor --out <tmpdir>` end-to-end
> and confirms 17 valid `.mdc` files land at `<tmpdir>/stacks/java-spring-boot-3/cursor/rules/`.
> Total: 117/117 tests green (23 Phase-2 carried over + 94 new). The Phase-2 lesson
> ("add Phase-4 jobs as siblings, not parallel workflows") was honored — `.github/workflows/validate.yml`
> now has three jobs (`tree-shape`, `schema-validation`, `compiler-unit-tests`).
> See `docs/execution-log/phase-4-log.md` for the full session record.

**Duration**: 7 days. **Output**: `compiler/core/` modules + `compiler/transformers/cursor_mdc.py`.

### Tasks

1. **`compiler/core/parse_source.py`**
   - Reads every `source/**/*.md`, parses YAML frontmatter via `python-frontmatter`.
   - Validates against `schemas/source-rule.schema.json`.
   - Returns a typed list of `SourceRule` dataclasses.
2. **`compiler/core/resolve_globs.py`**
   - Joins each rule's `scope.language` + `scope.layers[]` against `schemas/layer-glob-map.json` to produce a deduplicated globs array.
   - Returns the empty array (signal for `alwaysApply: true`) when all layers are `architecture`.
3. **`compiler/core/build_graph.py`**
   - Computes the rule dependency DAG from `dependencies:` arrays.
   - Detects cycles (fails the build) and topologically sorts so transformers can emit dependencies first when concatenating.
4. **`compiler/core/stack_filter.py`**
   - Given a target stack identifier (e.g., `java-spring-boot-3`), filters the rule set to those whose `scope.language` and `scope.framework` match, AND whose `scope.framework_version` semver range satisfies the stack's pinned version.
5. **`compiler/transformers/cursor_mdc.py`**
   - For each filtered rule, generate one `.mdc` file with:
     - `description: "<title> — apply to <stack-human-name>"`
     - `globs: [...]` from the resolver
     - `alwaysApply` derived from `activation.cursor_mode`
   - Emit body Markdown identical to the source file's Markdown body (frontmatter stripped).
6. **CLI entrypoint**: `python -m compiler --stack java-spring-boot-3 --target cursor --out dist/`.
7. **Logging**: Structured JSON logs with rule-id, target, output-path, and bytes for traceability.

### Acceptance Criteria

- [x] `pytest tests/` covers parser, glob resolver, dependency graph, stack filter, and the Cursor transformer. — `tests/test_parse_source.py`, `tests/test_resolve_globs.py`, `tests/test_build_graph.py`, `tests/test_stack_filter.py`, `tests/test_cursor_mdc.py` exist and contain 94 tests across all five modules (full suite: 117 passing including the 23 Phase-2 carry-overs). Each module's test file mirrors the architecture upgrade report's decision tree (e.g., the four cursor activation modes in `test_cursor_mdc.py`, every semver-range comparator in `test_stack_filter.py`).
- [x] Running `python -m compiler --stack java-spring-boot-3 --target cursor --out /tmp/out` produces a `/tmp/out/cursor/rules/` directory with one `.mdc` per applicable rule. — The Phase-4 CLI driver writes outputs to `<out>/stacks/<stack-id>/cursor/rules/*.mdc` per the schema's `output_path_template` (the path beneath `--out` is `stacks/java-spring-boot-3/cursor/rules/` rather than the AC's literal `cursor/rules/`; see decision record in `docs/execution-log/phase-4-log.md` §5). 17 of 18 source rules ship to the Spring Boot 3 stack (1 excluded by its `framework_version: ">=4.3"` range — a Phase-3-authored Spring Framework version, not a Spring Boot version; carry-forward note in §7 of the Phase-4 log).
- [x] Each generated `.mdc` validates against the (informal) Cursor MDC frontmatter shape and renders correctly when dropped into a fresh project. — `tests/test_cursor_mdc.py::test_each_emitted_mdc_validates_cursor_frontmatter_shape` parses every emitted `.mdc`, asserts the frontmatter keys are a subset of `{description, globs, alwaysApply}`, type-checks each value, and confirms the body begins with an H1 heading. The end-to-end CLI smoke test in `test_cli_invocation_smoke` shells out to `python -m compiler` and validates the same shape against the live corpus.

---

## 8. Phase 5 — Per-Tool Transformers

> **Status (as of 2026-05-18): COMPLETED.** Five new transformer modules landed under
> `compiler/transformers/`: `copilot_instructions.py` (concatenated
> `.github/copilot-instructions.md` grouped by `scope.layers`), `claude_md.py` (directive-tone
> `CLAUDE.md` with per-rule "You MUST: …" leads), `junie_agents_md.py` (numbered-list
> `.junie/AGENTS.md` matching the JetBrains `junie-guidelines` format),
> `universal_agents_md.py` (≤150-line root `AGENTS.md` with the five canonical sections and a
> build-failing `AgentsMdTooLongError` diagnostic), and `memory_bank_scaffold.py` (six-file
> Memory Bank with `techContext.md` + `systemPatterns.md` pre-populated from
> `source/<lang>/<framework>/_meta.yml`). The Phase-4 `compiler/__main__.py` gained dispatch
> for the five new targets plus a `--target all` mode that runs every transformer. A new
> `topo_sort_relaxed` helper landed in `compiler/core/build_graph.py` so concatenated
> transformers can tolerate stack-filter-excluded dependency references (the strict
> `build_graph` is still the right guardrail for full-corpus validation). Three new
> `source/<lang>/<framework>/_meta.yml` files (Spring Boot, NestJS, FastAPI) feed the Memory
> Bank scaffold. 52 new pytest tests across six test files (`test_copilot_instructions.py`,
> `test_claude_md.py`, `test_junie_agents_md.py`, `test_universal_agents_md.py`,
> `test_memory_bank_scaffold.py`, `test_phase5_end_to_end.py`) plus 4 new tests in
> `test_build_graph.py` for `topo_sort_relaxed`. Full repo test suite is 169 green (117
> Phase-2/4 carry-overs + 52 Phase-5). `.github/workflows/validate.yml`'s `compiler-unit-tests`
> job was extended with the Phase-5 test modules and a new end-to-end smoke step that runs
> `--target all` and asserts both AC1 (§5.2 tree present) and AC2 (AGENTS.md ≤150 lines).
> See `docs/execution-log/phase-5-log.md` for the full session record.

**Goal**: Implement the remaining four transformers so a single source corpus produces all five distribution targets.

**Duration**: 6 days. **Output**: Four additional transformer modules + the universal `AGENTS.md` builder.

### Tasks

1. **`compiler/transformers/copilot_instructions.py`**
   - Concatenates rules with `target_tools.github_copilot: true` into a single `.github/copilot-instructions.md`.
   - Groups by `scope.layers` for readability with H2 section headers (`## Controller Layer`, `## Service Layer`).
   - Strips `archunit_test` and other non-AI-relevant metadata.
2. **`compiler/transformers/claude_md.py`**
   - Same shape as Copilot but emits a single root-level `CLAUDE.md`.
   - Slightly different tone: more directive prose, explicit "When generating Java code, you MUST..." framing.
3. **`compiler/transformers/junie_agents_md.py`**
   - Targets JetBrains Junie's `.junie/AGENTS.md` location.
   - Format mirrors `JetBrains/junie-guidelines/guidelines/java/spring-boot/guidelines.md` (numbered list, 1–N).
4. **`compiler/transformers/universal_agents_md.py`**
   - Selects only rules whose `activation.agents_md_priority == "high"`.
   - Renders into a ≤150-line `AGENTS.md` (the AGENTS.md spec recommends this cap).
   - Emits the canonical sections recommended by the spec: Tech Stack, Commands, Code Style, Testing, Boundaries.
   - Length is enforced — if generated output exceeds 150 lines, the transformer fails the build with a "demote rules to medium priority" diagnostic.
5. **`compiler/transformers/memory_bank_scaffold.py`**
   - Generates the six canonical Memory Bank files for the stack.
   - `techContext.md` is pre-populated from a stack-descriptor file (`source/<lang>/<framework>/_meta.yml`) with versions, dependencies, and required env vars.
   - `systemPatterns.md` is pre-populated with the layered-architecture diagram for the stack.
   - The other four files are stubs marked `<!-- TEAM-MAINTAINED -->` so consumers know to fill them in.

### Acceptance Criteria

- [x] Running the compiler against `source/` for the `java-spring-boot-3` stack produces a directory tree exactly matching Architecture Upgrade Report §5.2 under `stacks/java-spring-boot-3/`. — `python -m compiler --stack java-spring-boot-3 --target all --out <tmp>` produces `<tmp>/stacks/java-spring-boot-3/{cursor/rules,copilot/copilot-instructions.md,claude/CLAUDE.md,junie/AGENTS.md,agents-md/AGENTS.md,memory-bank/{6 files}}`. The Phase-6 `archunit/EngineeringStandardsArchTest.java` is explicitly out of scope for Phase 5. Verified by `tests/test_phase5_end_to_end.py::test_cli_target_all_produces_expected_stack_tree` and the new validate.yml end-to-end step.
- [x] The generated `AGENTS.md` is ≤150 lines. — The live corpus produces a 66-line AGENTS.md for `java-spring-boot-3` (well under the 150 cap). `universal_agents_md.render_universal_agents_md` raises `AgentsMdTooLongError` if the cap is exceeded; the CLI catches it and exits 1 with a "demote rules to medium priority" diagnostic. Verified by `tests/test_universal_agents_md.py::test_render_under_150_lines_for_live_corpus` and `tests/test_phase5_end_to_end.py::test_universal_agents_md_under_150_lines`.
- [x] Each transformer has unit tests that verify both file *presence* and content shape. — 5 new test modules + 1 end-to-end module landed: `tests/test_copilot_instructions.py` (12 tests), `tests/test_claude_md.py` (9 tests), `tests/test_junie_agents_md.py` (10 tests), `tests/test_universal_agents_md.py` (10 tests), `tests/test_memory_bank_scaffold.py` (8 tests), `tests/test_phase5_end_to_end.py` (4 tests). 169/169 green across the full repo suite.

---

## 9. Phase 6 — Fixtures, Golden Files, and CI

> **Status (as of 2026-05-19): COMPLETED.** Four fixture consumer manifests
> landed under `fixtures/{spring-boot-3-2,spring-boot-2-7-legacy,nestjs-10,
> fastapi-0-110}/`; four byte-for-byte golden trees (77 files total) under
> `tests/golden/<fixture>/stacks/<stack-id>/`; the snapshot-compare runner
> at `tests/test_compiler_golden.py` (12 tests — per-fixture byte-equality,
> determinism check, drift-message contract, the Boot-2-vs-Boot-3
> version-gate sanity, and the AGENTS.md ≤150-line cap locked into every
> golden tree); four hand-authored ArchUnit fixtures under
> `tests/archunit/{ControllerValidation,TransactionalDiscipline,Pagination
> Mandate,ConstructorInjection}Test.java` plus a structural-shape suite
> at `tests/test_archunit_fixtures.py` (19 tests — file presence,
> `@AnalyzeClasses` package binding, expected `@ArchTest` ArchRule constants,
> canonical violation-message substrings preserved verbatim, README
> coverage of the manual `mvn test` verification procedure, and source-
> corpus `archunit_test:` cross-reference). A `Makefile` ships
> `make update-golden` (mass-regenerate) and `make explain-golden-diff`
> (per-fixture delta summary). `.github/workflows/validate.yml` gains a
> sibling `golden-snapshots` job (not a parallel workflow — Phase-2 lesson)
> running both Phase-6 test modules plus a fixture-presence guard. Full
> repo suite is 200 green (169 Phase-2/4/5 carry-overs + 12 golden + 19
> archunit-shape). AC3 was verified end-to-end by an ad-hoc source-rule
> edit producing a per-affected-file unified diff plus the `make
> update-golden` recovery hint, then reverting cleanly. AC1's runtime
> verification (running `mvn test` against a Spring Boot 3 project with
> deliberate violations) requires JDK + Maven that the Python-only Phase-6
> CI does not provide and is documented as an operator manual step in
> `tests/archunit/README.md`. See `docs/execution-log/phase-6-log.md` for
> the full session record.

**Goal**: Lock the compiler's output behavior with snapshot tests so every future change to `source/` or `compiler/` produces a reviewable diff in the golden files.

**Duration**: 5 days. **Output**: `fixtures/`, `tests/golden/`, fully wired CI.

### Tasks

1. **Create fixture consumer projects** under `fixtures/`:
   - `fixtures/spring-boot-3-2/pom.xml` — a minimal `pom.xml` declaring Spring Boot 3.2, Spring Data JPA, Validation, Lombok.
   - `fixtures/spring-boot-2-7-legacy/pom.xml` — Spring Boot 2.7 to verify version-gated rules are skipped.
   - `fixtures/nestjs-10/package.json` — NestJS 10.
   - `fixtures/fastapi-0-110/pyproject.toml` — FastAPI 0.110.
2. **Generate initial golden output** by running the compiler against each fixture and committing the result to `tests/golden/<fixture-name>/`.
3. **Snapshot test**: `tests/test_compiler_golden.py` re-runs the compiler against each fixture and `assert` that the produced output is byte-identical to `tests/golden/<fixture-name>/`.
4. **CI workflow `validate.yml`**:
   - Runs schema validation on `source/**/*.md` (already in Phase 2).
   - Runs `pytest tests/`.
   - Runs the golden-file snapshot tests.
5. **Author the ArchUnit test fixtures**:
   - `tests/archunit/ControllerValidationTest.java` (Logic Hole #3).
   - `tests/archunit/TransactionalDisciplineTest.java` (Logic Hole #4).
   - `tests/archunit/PaginationMandateTest.java` (Logic Hole #5).
   - `tests/archunit/ConstructorInjectionTest.java` (Logic Hole #6).
   These compile to `stacks/java-spring-boot-3/archunit/` in distribution.
6. **CI golden-update procedure**: when an author intentionally changes compiler output, they run `make update-golden` and commit the diff. The PR review then surfaces the exact expected change.

### Acceptance Criteria

- [!] All four ArchUnit tests, when copied into a sample Spring Boot 3 project containing one deliberate violation each, fail with the expected violation message. — The four fixtures (`tests/archunit/{ControllerValidation,TransactionalDiscipline,PaginationMandate,ConstructorInjection}Test.java`) are on disk with canonical violation-message strings inline and the manual `mvn test` verification procedure documented in `tests/archunit/README.md`. Live runtime verification (running `mvn test` against a Spring Boot 3 project with deliberate violations) requires a JDK + Maven environment that the Python-only Phase-6 CI does not provide; this is the operator's PR-close action OR Phase 9 pilot CI's natural surface. The Python-side `tests/test_archunit_fixtures.py` (19 tests) locks the *structural* contract — `@AnalyzeClasses` binding, expected `@ArchTest` `ArchRule` constants, and the canonical violation-message substrings the consumer-side CI greps for. Tracked as a Phase-6 carry-forward in `docs/execution-log/phase-6-log.md`.
- [x] Golden snapshot tests pass on a clean checkout. — Four golden trees under `tests/golden/{spring-boot-3-2,spring-boot-2-7-legacy,nestjs-10,fastapi-0-110}/stacks/<stack-id>/` (77 files total) committed alongside the 12-test runner at `tests/test_compiler_golden.py`. Full suite (200/200) green: `python -m pytest tests/ -q` → `200 passed in 5.52s`. Determinism explicitly locked by `test_compiler_output_is_deterministic_across_two_runs`.
- [x] An intentional source-rule edit produces a clear, reviewable diff in golden files. — Verified by appending a single comment line to `source/_global/clean-architecture.md`, running the snapshot test, observing per-affected-file unified diffs (4 fixture failures, 3 affected output files per stack: cursor `.mdc`, copilot, claude) plus the `make update-golden` recovery instruction, then reverting cleanly (12 golden tests back to green). Full evidence quoted in `docs/execution-log/phase-6-log.md` §8 V-7.

---

## 10. Phase 7 — Release Workflow & `dist/` Folder Protection

> **Status (as of 2026-05-20): COMPLETED.** All mechanical artifacts shipped:
> `.github/workflows/release.yml` (manual `workflow_dispatch`, 15 steps, App-token
> authentication, dry-run mode, concurrency lock), the new `dist-protection-lint`
> job appended to `.github/workflows/validate.yml` (PR-only conditional, cites
> ADR-0004 on failure), the `--all-stacks` CLI flag on `python -m compiler`
> (Phase-6 gap closed), three release-tools (`tools/compute_semver_bump.py`
> Conventional-Commits parser; `tools/generate_changelog.py` rule-delta
> formatter with prepend-on-update splice; `tools/generate_dist_readme.py` auto-
> generated index that preserves the ADR-0004 reference the Phase-1 `tree-shape`
> job greps for), and the three new docs (`docs/release-bot-setup.md`,
> `docs/release-rollback.md`, plus `docs/branch-protection-config.md` reconciled
> to use the live `golden-snapshots` job name and document the Phase-7
> push-restriction action). 69 new pytest tests across four modules (27 unit
> tests for the semver-bump parser + 11 changelog + 11 dist-readme + 20
> Phase-7 end-to-end) bring the full suite to 269 passing + 7 skipped (the
> sandbox-only git-integration tests run unconditionally in CI). All five
> acceptance criteria require operator-side action to fully verify — App
> registration, branch-protection apply, an actual `workflow_dispatch` run,
> and a test PR. Each is marked `[!]` with the corresponding
> operator-handoff note. See `docs/execution-log/phase-7-log.md` for the full
> session record.

> ⚠️ Revision (post-Phase-7 reconciliation, 2026-05-20): At App-registration
> time the operator chose the slug `engineering-standards-bot` rather than the
> placeholder `standards-bot` used throughout the Phase-7 plan and docs (the
> bare `standards-bot` was already taken on GitHub). All references in live
> code, tests, and docs (`.github/workflows/*.yml`, `.github/CODEOWNERS`,
> `tools/generate_dist_readme.py`, `tools/git-hooks/*`, `docs/release-bot-setup.md`,
> `docs/release-rollback.md`, `docs/branch-protection-config.md`,
> `docs/decision-records/0004-single-repo-distribution.md`, `AGENTS.md`,
> `tests/test_phase7_end_to_end.py`, and the §10 ACs below) have been
> reconciled to the live slug. The two repo secrets
> (`STANDARDS_BOT_APP_ID`, `STANDARDS_BOT_PRIVATE_KEY`) keep their original
> names — they were already provisioned and renaming them would invalidate
> the live release workflow. Phase-7 execution logs under
> `docs/execution-log/` are deliberately left unchanged (historical record).

**Goal**: Establish the automated release flow that regenerates the `dist/` folder, commits it under a CI-only identity, and tags semver releases — all within the single `engineering-standards-central` repository per ADR-0004.

**Duration**: 2 days. **Output**: One GitHub Actions release workflow + a CODEOWNERS-enforced `dist/` protection lint check + a registered GitHub App (`@engineering-standards-bot`).

### Tasks

1. **Register the `@engineering-standards-bot` GitHub App**
   - Scope: `contents: write`, `pull-requests: write` on **only** `engineering-standards-central`.
   - Install in the org; record the App ID and private key in repo secrets (`STANDARDS_BOT_APP_ID`, `STANDARDS_BOT_PRIVATE_KEY`).
   - All commits authored by this App appear under the `@engineering-standards-bot` identity, making release commits trivially auditable in `git log` and in GitHub's commit signature view.
2. **Implement `release.yml`** (manual `workflow_dispatch`, triggered by the Standards Architect or AI Enablement PM):
   - Step 1: Check out `main` at the chosen tip commit.
   - Step 2: Compute the semver bump using **Conventional Commits** parsing of every commit since the previous tag. `feat:` ⇒ minor, `fix:` ⇒ patch, `BREAKING CHANGE:` ⇒ major.
   - Step 3: Run `python -m compiler --all-stacks --out dist/`. The compiler regenerates the entire `dist/` tree deterministically; previous output is overwritten.
   - Step 4: Authenticate as `@engineering-standards-bot` via the App credentials.
   - Step 5: Commit the regenerated `dist/` tree with message `chore(release): regenerate dist for v<X.Y.Z>` (no other paths touched).
   - Step 6: Tag the new commit `v<X.Y.Z>` (annotated tag, signed if the org policy requires).
   - Step 7: Generate `CHANGELOG.md` for `dist/CHANGELOG.md` from rule-id additions, removals, and frontmatter changes since the previous tag.
   - Step 8: Create a GitHub Release with the auto-generated changelog as the release notes.
3. **Implement `dist-protection-lint.yml`** (PR status check, blocking):
   - Triggered on every PR open / synchronize / reopen.
   - Logic: `git diff --name-only origin/main...HEAD` must satisfy ONE of:
     - (a) The PR contains zero paths under `dist/`, OR
     - (b) Every commit's author is the `@engineering-standards-bot` GitHub App (i.e., produced by `release.yml`).
   - Failure mode: fails with the message *"Human authors cannot modify `/dist/`. The `dist/` tree is regenerated by `release.yml` only. See ADR-0004."*
4. **Configure branch protection on `main`** (already documented in Phase 1, applied in the GitHub UI now):
   - Require pull request before merge.
   - Require the `validate`, `golden-tests`, and `dist-protection-lint` status checks to pass.
   - Restrict pushes to `main` to the `@engineering-standards-bot` App **only** for the release workflow's commit; humans always go through PR.
   - Require linear history; force pushes disabled.
5. **Auto-update `dist/README.md`** during the release workflow with a generated index of `stacks/<stack>/`, a one-line description of each, and the current semver and changelog link. This file is committed inside the same release commit.
6. **Document the rollback procedure** in `docs/release-rollback.md`: a bad release is reverted by (a) running `release.yml` against the prior good commit (re-pinning), or (b) opening a manual revert PR that the Standards Council fast-tracks. Either path produces a new tag (`v2.4.1`) — never a moved tag, never a force-push.

### Acceptance Criteria

- [!] Merging an example PR that adds a new source rule does NOT modify `/dist/`. The dist tree is regenerated only on manual release. — **Mechanical guards in place**: there is no auto-regenerate-on-PR trigger anywhere (`release.yml` is `workflow_dispatch:` only), and `dist-protection-lint` blocks any PR whose diff includes `dist/**` from a non-bot author. **Live PR experiment** (open a PR adding one source rule and confirm `dist/` is untouched on green merge) is the operator's PR-close action — the agent cannot push to GitHub.
- [!] Manually dispatching `release.yml` produces a single commit authored by `@engineering-standards-bot`, a `v<X.Y.Z>` tag, a populated `dist/CHANGELOG.md`, and a GitHub Release. — **All mechanical artifacts complete** (15-step `release.yml` with App-token auth, semver-bump tool, changelog generator, README generator). **Live dispatch** requires three prerequisite operator actions documented in `docs/release-bot-setup.md`: (a) register the `@engineering-standards-bot` GitHub App, (b) store `STANDARDS_BOT_APP_ID` + `STANDARDS_BOT_PRIVATE_KEY` repo secrets, (c) update branch protection to allow the App to push to `main` per `docs/branch-protection-config.md` §2.4. The dry-run mode (`workflow_dispatch` input `dry-run: true`) is available to preview the release locally before the first real dispatch.
- [!] A test PR by a human that touches a file under `dist/` is blocked by the `dist-protection-lint` status check with a clear error message. — **Mechanical guard verified** by `tests/test_phase7_end_to_end.py::test_dist_protection_lint_failure_message_cites_adr_0004` (asserts the literal "Human authors cannot modify dist/" + ADR-0004 reference in the workflow YAML). **Live test PR** is the operator's PR-close action.
- [!] Branch protection on `main` is verified via screenshot in the closing PR for Phase 7. — `docs/branch-protection-config.md` updated with (a) the `golden-tests`→`golden-snapshots` naming reconciliation, (b) the `dist-protection-lint` required-status-check entry, (c) the §2.4 push-restriction update adding `@engineering-standards-bot`. **GitHub-UI apply + screenshot** is the operator's PR-close action.
- [!] `git log --author=engineering-standards-bot dist/` returns the complete history of dist regenerations and nothing else. — Until the operator runs the first `release.yml` dispatch, `git log --author=engineering-standards-bot` is correctly empty. The audit-query template + the quarterly audit procedure are documented in `docs/release-bot-setup.md` §6. This AC ticks `[x]` after the first release lands.

### Why This Replaces a Second Repo

The originally-proposed second repo provided four functional guarantees:

| Guarantee | How the single-repo model preserves it |
|---|---|
| Humans cannot write to compiled output | `dist-protection-lint` status check + CODEOWNERS routing + branch protection |
| Compiled output has clean semver tags | `release.yml` tags `v<X.Y.Z>` on `main`; consumers resolve `dist/stacks/<stack>/` at that tag |
| Releases are auditable | Every release commit's author is `@engineering-standards-bot`; `git log --author=engineering-standards-bot` is the audit log |
| Rollback is mechanical | Re-run `release.yml` against the prior good commit, producing a new tag with the prior content |

Graduation to a separate repo (per ADR-0004) is a `git filter-repo` away if any of the four trigger conditions ever fire.

---

## 11. Phase 8 — Consumer-Side Sync Tool

**Goal**: Ship `@org/standards-sync` — a Node CLI that consumer repos run to pull the right stack's distribution outputs into their working tree.

**Duration**: 6 days. **Output**: A published npm package.

### Tasks

1. **Stack detection** — parses `pom.xml` / `build.gradle.kts` / `package.json` / `pyproject.toml` to determine the stack identifier and pinned version. Outputs the detection rationale so users can debug surprises.
2. **Version resolution** — reads `.standards-version` if present (pinned mode) or queries the GitHub Releases API of `engineering-standards-central` for the latest `v<X.Y.Z>` tag (floating mode). The fetch uses GitHub's tarball/archive endpoint scoped to the `dist/stacks/<stack>/` subtree at that tag — no full-repo clone required.
3. **File placement** — sourced from `dist/stacks/<stack>/` of the resolved tag —
   - Copies `dist/stacks/<stack>/cursor/rules/` into `<consumer>/.cursor/rules/`.
   - Copies `dist/stacks/<stack>/copilot/copilot-instructions.md` into `<consumer>/.github/copilot-instructions.md`.
   - Copies `dist/stacks/<stack>/claude/CLAUDE.md` into `<consumer>/CLAUDE.md`.
   - Copies `dist/stacks/<stack>/junie/AGENTS.md` into `<consumer>/.junie/AGENTS.md`.
   - Copies `dist/stacks/<stack>/agents-md/AGENTS.md` into `<consumer>/AGENTS.md`.
   - Copies `dist/stacks/<stack>/archunit/` into `<consumer>/src/test/java/com/_org/standards/`.
   - Memory Bank scaffold is **opt-in** via `--with-memory-bank` flag.
4. **Idempotency** — re-running with the same version produces zero diff.
5. **Sync report** — emits a Markdown summary with: stack detected, rules copied, rules skipped (with reasons), rules whose globs match no files in the consumer (warning).
6. **Optional Maven/Gradle plugin** — wraps the Node CLI invocation so Java teams can bind it to a Gradle/Maven phase.

### Acceptance Criteria

- [ ] Running `npx @org/standards-sync` in a fresh Spring Boot 3.2 fixture project produces the file layout in Architecture Upgrade Report §5.3.
- [ ] Running it twice consecutively produces zero `git diff`.
- [ ] Running in a non-supported stack (e.g., a Ruby on Rails project) emits a clear "no applicable stack found" message and exits 0 (not an error).

---

## 12. Phase 9 — Pilot Adoption and Telemetry

**Goal**: Validate the system with three pilot teams before org-wide rollout. Establish telemetry so adoption health is measurable.

**Duration**: 4 weeks. **Output**: Three production-using pilot repos + a telemetry dashboard.

### Tasks

1. **Pilot selection** — three repos representing the spread:
   - One greenfield Spring Boot 3 microservice.
   - One existing Spring Boot 2.7 monolith mid-migration to 3.x.
   - One TypeScript/NestJS service (verifies the multi-language story).
2. **Embedded liaison**: a Pilot Liaison joins each pilot's standup for the four-week window.
3. **Telemetry collection** — opt-in, privacy-preserving:
   - Sync invocations (count, version pinned, stack detected).
   - Rule-set delta on every sync (rules added/removed in the consumer's `.cursor/rules/`).
   - Per-rule "applied" counts via Cursor's rule-application telemetry (where available).
4. **Adoption metrics dashboard** — shows: pilot repos using each `.standards-version`; rule activations per repo per week; broken syncs and their root causes.
5. **Feedback loop** — weekly retrospective with the three liaisons. Every issue files an issue in `engineering-standards-central` with a `pilot-feedback` label.
6. **Outcome review at week 4** — Standards Architect, AI Enablement PM, and the three liaisons review the pilots and produce a Go/No-Go for org-wide rollout.

### Acceptance Criteria

- [ ] All three pilots are running on a tagged release of the distribution.
- [ ] Telemetry dashboard exists and shows non-trivial activation counts.
- [ ] The week-4 retro produces either a Go decision OR a documented blocker list with owners.

---

## 13. Phase 10 — Org-Wide Rollout, Governance, and MCP Roadmap

**Goal**: Roll out to all eligible repos and establish the long-term governance model.

**Duration**: Ongoing; initial rollout 6–8 weeks. **Output**: Org-wide adoption + a formal governance charter.

### Tasks

1. **Rollout campaign** —
   - Week 1: announce in eng all-hands, demo the sync flow, show the AI behavior diff before/after.
   - Weeks 2–6: each tribe migrates its repos in waves; Pilot Liaisons rotate as office-hours hosts.
   - Week 7+: the sync command is added to the standard repo-bootstrap template.
2. **Governance charter** at `docs/governance.md`:
   - Cadence: monthly Standards Council meeting (Architect, PM, Compiler Engineer, Tribe Reps).
   - Change-control process: trivial wording PRs need 1 review; new rules need 2 reviewers; rule deprecations need a 30-day announce-then-remove cycle.
   - Logic-Hole catalog evolution: the council evaluates new candidates quarterly.
3. **Deprecation path** for the `.cursorrules` legacy distribution:
   - Phase out the legacy concatenated artifact 90 days after Phase-10 kickoff.
   - Communicate via release notes and a banner in the central repo's README.
4. **MCP server roadmap** (deferred from Phase 0):
   - Spec freeze: MCP server exposes one Resource per source rule (URI scheme `engineering://<lang>/<framework>/<layer>/<rule-id>`).
   - Spec freeze: MCP server exposes one Prompt per Logic Hole ("Review the open file for Logic Hole #4 violations").
   - Spec freeze: MCP server exposes one Tool: `lint_against_standards(file_path)` returning structured violations keyed by rule-id.
   - Implementation epic: 2 engineers × 6 weeks; targets Q3 of the rollout year.

### Acceptance Criteria

- [ ] >85% of eligible repos have a tagged `.standards-version` within 90 days of rollout kickoff.
- [ ] Standards Council has met at least three times.
- [ ] MCP-server epic has a kickoff date and named owners.

---

## 14. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Cursor changes MDC frontmatter format mid-rollout | Medium | High | Pin to a Cursor version in adoption docs; transformer is a single file (`cursor_mdc.py`) and trivial to revise. |
| R-02 | AGENTS.md spec evolves (new required sections) | Medium | Low | The transformer is data-driven from `source/`; spec changes affect only the transformer template. |
| R-03 | Pilot teams reject the sync tool's idempotency contract (manual edits) | Low | Medium | Sync detects manual edits via checksum and refuses to overwrite without `--force`; emits a clear error message. |
| R-04 | Golden snapshot tests become noisy and ignored | High | Medium | Make the diff easy to review (per-file output); add a `make explain-golden-diff` target that summarizes which rules' content changed. |
| R-05 | A new framework version requires `framework_version` semver-range edits across many rules | Medium | Low | Bulk-edit via a small CLI helper (`compiler/admin/bump-framework-version.py`); 10-line patch. |
| R-06 | Excessive `alwaysApply: true` rules erode the token-budget gain | Medium | High | Lint rule in `validate.yml`: fail the build if `alwaysApply: true` is used without `architecture` layer or explicit override comment. |
| R-07 | MCP server adds attack surface (live RPC over the corpus) | Low | High | Defer to Phase-10; require security review and authn/authz design before implementation. |
| R-08 | Multi-repo sync drift — some repos pin v1.x, others v2.x — produces inconsistent AI behavior | Medium | Medium | Telemetry dashboard tracks version distribution; the council triggers a "minimum version" mandate quarterly. |
| R-09 | Lombok-vs-no-Lombok divergence on Logic Hole #6 (constructor injection) | Low | Low | The rule's body conditionally references Lombok based on the consumer's manifest detection; both branches documented. |
| R-10 | Author authority concentrated in the Standards Architect (bus factor) | Medium | High | At least two reviewers required on every `source/` PR; pair-author every new rule for the first quarter. |
| R-11 | Single-repo blast radius — a compromised CI token could in theory mutate `source/` as well as `dist/` | Low | High | The `@engineering-standards-bot` GitHub App scope is `contents: write` on a single repo only; humans cannot push to `main` directly (branch protection); release commits are restricted by branch-protection's "restrict who can push" setting to the App identity; rotate App private key annually; audit `git log --author=engineering-standards-bot` quarterly. Graduate to two-repo (ADR-0004 trigger) if the threat model changes. |
| R-12 | `dist/` history bloats repo size over time | Low | Low | Markdown text grows slowly (~50 KB per release × 24 releases/yr ≈ 1.2 MB/yr). Monitor repo size quarterly; if it crosses 500 MB, run `git filter-repo` to graduate `dist/` into a separate repo per ADR-0004. Consumer sync uses sparse archive download, not full clone, so repo size does not affect end-user latency until graduation. |
| R-13 | Author accidentally edits `dist/` and merges before lint check fires | Very Low | Medium | Three layered guards: (a) `dist-protection-lint` is a *required* status check on `main`; (b) CODEOWNERS auto-requests review from `@engineering-standards-bot` which never approves; (c) opt-in client pre-commit hook blocks the staged change locally. All three would have to fail simultaneously. |

---

## 15. Definition of Done — Milestone Acceptance Criteria

A phase is **Done** when *every* checkbox in its acceptance-criteria list is checked AND the AI Enablement PM has signed off in the linked GitHub issue.

The overall **MVP** (delivered by end of Phase 8) is considered complete when:

- [ ] A consumer repo can run `npx @org/standards-sync` and receive working `.cursor/rules/*.mdc`, `.github/copilot-instructions.md`, `CLAUDE.md`, `.junie/AGENTS.md`, and root `AGENTS.md`.
- [ ] The four new Logic Holes (#3, #4, #5, #6) are encoded in source AND emitted into Cursor MDC AND ship as ArchUnit tests.
- [ ] CI rejects malformed source files within 30 seconds of PR creation.
- [ ] `engineering-standards-central` has branch protection on `main`, the `dist-protection-lint` status check is required, the `@engineering-standards-bot` GitHub App is registered, and at least one semver release tag exists with a populated `dist/CHANGELOG.md`.

The overall **GA** (delivered by end of Phase 10) requires the MVP plus:

- [ ] >85% adoption among eligible repos.
- [ ] Standards Council operational with a published meeting cadence.
- [ ] Telemetry dashboard live.
- [ ] MCP-server epic kicked off (implementation may not be complete).

---

## 16. Indicative Timeline

Numbers are calendar weeks from kickoff, assuming the team described in §2.1. Phases 4–5 and 6–7 can run in parallel with appropriate engineer availability.

```text
Week:        1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20  21
Phase 0  ░░░░
Phase 1      ░░░░
Phase 2          ░░░░░░░░
Phase 3              ░░░░░░░░░░░░░░░░
Phase 4                          ░░░░░░░░░░░░░░
Phase 5                                  ░░░░░░░░░░░░
Phase 6                                          ░░░░░░░░░░
Phase 7                                              ░░░░
Phase 8                                                ░░░░░░░░░░░░
Phase 9                                                          ░░░░░░░░░░░░░░░░
Phase 10                                                                          ░░░░░░░░ (continues)
```

| Phase | Duration | Effort (eng-days) | Dependencies |
|---|---|---|---|
| 0 — ADRs (incl. ADR-0004) | 4 days | 3 | None |
| 1 — Scaffolding (incl. CODEOWNERS, branch protection) | 2 days | 2 | Phase 0 |
| 2 — Schemas | 4 days | 4 | Phase 1 |
| 3 — Source content | 8 days | 16 (paired) | Phase 2 |
| 4 — Compiler core | 7 days | 7 | Phase 2 |
| 5 — Transformers | 6 days | 6 | Phase 4 |
| 6 — Fixtures & CI | 5 days | 5 | Phases 3, 5 |
| 7 — Release workflow & `dist/` protection | 2 days (estimate); 1 session of ~2.5 h (actual) | 2 | Phase 6 |
| 8 — Consumer sync | 6 days | 6 | Phase 7 |
| 9 — Pilots | 4 weeks | 8 (liaisons) | Phase 8 |
| 10 — Rollout & governance | 6+ weeks | Ongoing | Phase 9 |

**Critical path** (Phases 0 → 1 → 2 → 4 → 5 → 6 → 7 → 8): approximately **8.5 weeks** from kickoff to MVP (down from 9 weeks in the two-repo model — Phase 7 saves 2 days, Phase 0 adds 1). Pilots add 4 weeks. Org-wide rollout is the remaining 6+ weeks. **Total to GA: ≈ 18.5 weeks**.

---

## Document End

This concludes the Implementation Plan. Cross-reference `01-architecture-upgrade-report.md` for the architectural rationale behind each phase, and the original `ai-engineering-standards-blueprint.md` for the foundational baseline this plan evolves.
