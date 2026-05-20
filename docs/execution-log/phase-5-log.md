# Phase 5 Execution Log — Per-Tool Transformers

- **Phase**: 5 — Per-Tool Transformers
- **Date**: 2026-05-18
- **Status**: COMPLETED
- **Estimated duration (per plan)**: 6 days
- **Actual duration**: 1 session (~2 hours of agent execution time)

## 1. Summary

Phase 5 closes the per-target compilation surface. Five new transformer modules under
`compiler/transformers/` plus a `topo_sort_relaxed` helper in `compiler/core/build_graph.py`
turn the 18-rule source corpus into the full Architecture-Upgrade-Report §5.2 distribution
tree for every supported stack. The `python -m compiler` CLI driver gained dispatch for the
five new targets (`github_copilot`, `claude_skills`, `junie`, `agents_md`, `memory_bank`)
plus a `--target all` mode that runs every transformer for one stack. Three new
`source/<lang>/<framework>/_meta.yml` stack-descriptor files feed the Memory Bank's
pre-populated `techContext.md` and `systemPatterns.md`.

The verbatim AC1 invocation `python -m compiler --stack java-spring-boot-3 --target all
--out <tmp>` now writes the complete §5.2 subtree under `<tmp>/stacks/java-spring-boot-3/`:
17 `.mdc` files under `cursor/rules/`; one `copilot/copilot-instructions.md` (2214 lines);
one `claude/CLAUDE.md` (2254 lines); one `junie/AGENTS.md` (195 lines); one
`agents-md/AGENTS.md` (66 lines — well under the 150-line cap); and six Memory Bank files
under `memory-bank/`. The `archunit/` tree is explicitly out of scope for Phase 5 (Phase 6
deliverable).

52 new pytest tests landed across six new test modules (`test_copilot_instructions.py`,
`test_claude_md.py`, `test_junie_agents_md.py`, `test_universal_agents_md.py`,
`test_memory_bank_scaffold.py`, `test_phase5_end_to_end.py`) plus 4 new tests in
`test_build_graph.py` for `topo_sort_relaxed`. The full repo test suite is 169 green
(117 Phase-2 + Phase-4 carry-overs + 52 new); zero linter errors.

The Phase-4 lesson ("`logging_setup` is the singleton path; `RuleGraph.topo_sorted()` is the
right ordering API") was followed for four of the five new transformers. One adjustment
surfaced and is captured below: the strict `build_graph` cannot validate dependency closure
across a stack-filter-pruned subset (a rule kept by version `>=2.7` may declare a dependency
on a rule excluded by `>=3.0`). The new `topo_sort_relaxed` is the subset-friendly variant —
strict validation remains the right guardrail at the full-corpus level (Phase 7 release).

## 2. Files Created

### Per-tool transformers (Tasks 1–5)

- `compiler/transformers/copilot_instructions.py` (264 lines) — GitHub Copilot transformer.
  Concatenates rules with `target_tools.github_copilot: true` into one
  `dist/stacks/<stack>/copilot/copilot-instructions.md`. Groups rules under H2 layer headers
  (`## Controller Layer`, `## Service Layer`, etc.) with canonical ordering (`architecture`
  first, alphabetical concrete layers, `all` last). Source `# Title` H1s are stripped and
  replaced with per-rule H3s (`### <title>`), with all remaining ATX headings demoted one
  level. Multi-layer rules appear under each layer they touch (intentional — Copilot users
  grep by section, duplication is cheaper than under-coverage). Pure
  `render_copilot_instructions(rules, stack)` plus side-effecting `emit_for_stack(...)`.

- `compiler/transformers/claude_md.py` (253 lines) — Claude Code transformer. Same shape as
  Copilot but tone is directive ("When generating, modifying, or reviewing Java code in this
  repository, you MUST follow every rule listed below"). Each rule's H3 is followed by a
  one-line **You MUST: …** lead-in derived from the rule's title. Output at
  `dist/stacks/<stack>/claude/CLAUDE.md`. Language-name humanization via
  `_LANGUAGE_HUMAN_NAMES` (`java` → "Java", `typescript` → "TypeScript", `python` → "Python").

- `compiler/transformers/junie_agents_md.py` (211 lines) — JetBrains Junie transformer.
  Numbered-list format matching `JetBrains/junie-guidelines`. Each entry is a top-level
  numbered item with a bold title, a one-paragraph context summary (extracted from §1 Context
  & Architectural Intent), and a "Rules:" sub-list (one bullet per H3 sub-rule under §2
  Enforced Standards). Regex extraction (`_CONTEXT_HEADING_RE`, `_ENFORCED_HEADING_RE`,
  `_H3_RULE_RE`) handles the source corpus's authoring conventions. Output at
  `dist/stacks/<stack>/junie/AGENTS.md`.

- `compiler/transformers/universal_agents_md.py` (280 lines) — Universal AGENTS.md
  transformer. ≤150-line cap per the AGENTS.md spec (Architecture Upgrade Report §3.4).
  Selection: only rules with `target_tools.agents_md: true` AND
  `activation.agents_md_priority: high`. Canonical sections per the spec: Tech Stack,
  Commands, Code Style, Testing, Boundaries, plus a "Where AI Should and Should Not
  Generate" table and a Provenance footer. Rules grouped by layer hint: `test`-layer rules
  → Testing; `architecture`-layer rules → Boundaries; everything else → Code Style. Length
  enforcement raises `AgentsMdTooLongError` with a "demote rules to medium priority"
  diagnostic if the rendered output exceeds the cap; the CLI catches this and exits 1.

- `compiler/transformers/memory_bank_scaffold.py` (318 lines) — Memory Bank scaffold
  transformer. Writes the six canonical Memory Bank files per the
  `vanzan01/cursor-memory-bank` convention (Architecture Upgrade Report §3.2):
  `projectbrief.md`, `productContext.md`, `activeContext.md`, `systemPatterns.md`,
  `techContext.md`, `progress.md`. The four `<!-- TEAM-MAINTAINED -->`-tagged stubs are
  empty-of-content (consumers fill them in); `techContext.md` and `systemPatterns.md` are
  pre-populated from `source/<lang>/<framework>/_meta.yml`. Falls back to a minimal default
  diagram if `_meta.yml` is absent.

### Stack descriptors (prerequisite for Task 5)

- `source/java/spring-boot/_meta.yml` (72 lines) — Framework name, stack versions
  (`java-spring-boot-3` → 3.2.0, `java-spring-boot-2` → 2.7.18), required & optional
  dependencies, required env vars, a Mermaid four-layer architecture diagram, and the
  layered-boundary summary points.

- `source/typescript/nestjs/_meta.yml` (45 lines) — NestJS 10 stack descriptor mirroring
  the Spring Boot file's schema; smaller because the NestJS rule corpus is currently
  globals-only.

- `source/python/fastapi/_meta.yml` (44 lines) — FastAPI 0.110 stack descriptor.

### Phase-5 tests (AC3)

- `tests/test_copilot_instructions.py` (186 lines) — 12 tests. Header naming, layer
  grouping order, copilot-target filtering, H1 strip + heading demotion, dependency-first
  topo, multi-layer duplication, single-file emit shape, skip-on-empty-subset, structured
  JSON logging, live-corpus round-trip.

- `tests/test_claude_md.py` (124 lines) — 9 tests. Header naming, **You MUST: …** directive
  generation, trailing-period normalization, language-name humanization, target filtering,
  output path, log shape, live-corpus rule-title presence.

- `tests/test_junie_agents_md.py` (140 lines) — 10 tests. Header naming, numbered-list
  shape, §1 Context paragraph extraction, §2 H3 sub-rule extraction, topological order,
  target filtering, output path, log shape, numbered-count matches filtered-subset count
  on the live corpus.

- `tests/test_universal_agents_md.py` (165 lines) — 10 tests. Canonical-sections presence,
  `medium`/`low` priority exclusion, `agents_md: false` exclusion, ≤150-line cap on the
  live corpus, cap diagnostic via `AgentsMdTooLongError`, test-layer routing to Testing
  section, architecture-layer routing to Boundaries section, output path, log shape with
  `line_count` ≤ `max_lines`.

- `tests/test_memory_bank_scaffold.py` (106 lines) — 8 tests. Six canonical filenames,
  `<!-- TEAM-MAINTAINED -->` tag on stubs, `techContext.md` pre-population from
  `_meta.yml`, `systemPatterns.md` includes diagram + layer boundaries, fallback diagram
  when `_meta.yml` is absent, all six files emitted, per-file metadata in `EmittedFile`
  records, structured-JSON log shape.

- `tests/test_phase5_end_to_end.py` (121 lines) — 4 tests. AC1 verification (full §5.2
  subtree present after `--target all`); per-target `transformer-complete` log emission;
  AC2 verification (AGENTS.md ≤150 lines via the CLI); cross-stack sanity (`--target all`
  succeeds for every stack in the catalog AND Memory Bank always emits six files).

### This log

- `docs/execution-log/phase-5-log.md` — This file.

## 3. Files Modified

- `compiler/__main__.py` (224 lines, was 158) — Extended `SUPPORTED_TARGETS` to include
  `github_copilot`, `claude_skills`, `junie`, `agents_md`, `memory_bank`, and `all`.
  Replaced the inline cursor-only dispatch with a `_dispatch_target(...)` helper that
  routes by target id. `--target all` iterates over the canonical six targets in the
  fixed order (cursor → copilot → claude → junie → agents_md → memory_bank), emitting
  one `transformer-complete` log per target. `AgentsMdTooLongError` is caught and
  surfaced as exit code 1. Help text updated.

- `compiler/core/build_graph.py` (274 lines, was 221) — Added `topo_sort_relaxed(rules)`
  for Phase-5 transformers. Builds a subset-local Kahn-sort over `rules`, dropping
  dependency edges that point to rules NOT in the subset. Cycle detection within the
  subset still applies. The strict `build_graph(...)` is unchanged (full-corpus
  validation remains the right guardrail for Phase 7 release).

- `compiler/transformers/__init__.py` (24 lines, was 9) — Rewrote the docstring to
  enumerate every transformer that ships with Phase 5, including the pure-function /
  side-effecting split that each module follows.

- `tests/test_build_graph.py` (166 lines, was 133) — Added 4 tests for
  `topo_sort_relaxed`: missing-dep tolerance, intra-subset order preservation, cycle
  detection within subset, empty input.

- `.github/workflows/validate.yml` — Top-of-file comment extended with the Phase-5
  block (transformer modules + AC1+AC2 smoke step). The `compiler-unit-tests` job's
  pytest invocation now includes the six Phase-5 test files. A new
  "End-to-end smoke (--target all) — Phase 5 AC1 + AC2" step runs
  `--target all` and asserts both the §5.2 paths and the AGENTS.md line cap.

- `docs/02-implementation-plan.md` — Phase 5 section: added a
  `> **Status (as of 2026-05-18): COMPLETED**` callout above the goal line; ticked
  all three acceptance-criteria checkboxes `[ ]` → `[x]` with inline evidence.

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan §8) | Status | Evidence / Notes |
|---|---|---|
| Running the compiler against `source/` for the `java-spring-boot-3` stack produces a directory tree exactly matching Architecture Upgrade Report §5.2 under `stacks/java-spring-boot-3/`. | ✅ | `python -m compiler --stack java-spring-boot-3 --target all --out <tmp>` produces (verified end-to-end via `find` after invocation): `cursor/rules/` (17 `.mdc` files), `copilot/copilot-instructions.md`, `claude/CLAUDE.md`, `junie/AGENTS.md`, `agents-md/AGENTS.md`, `memory-bank/{projectbrief,productContext,activeContext,systemPatterns,techContext,progress}.md`. The §5.2 `archunit/EngineeringStandardsArchTest.java` is explicitly a Phase-6 deliverable (per plan §9 task 5). Verified by `tests/test_phase5_end_to_end.py::test_cli_target_all_produces_expected_stack_tree` AND the new validate.yml end-to-end step. |
| The generated `AGENTS.md` is ≤150 lines. | ✅ | Live corpus produces a 66-line AGENTS.md for `java-spring-boot-3`. Cap enforcement is in `universal_agents_md.render_universal_agents_md`: if `output.count("\n") > max_lines`, raises `AgentsMdTooLongError("Universal AGENTS.md ... would be N lines (cap 150). Demote some rules from `agents_md_priority: high` to `medium` ...")`. The CLI catches this and exits 1 with the diagnostic on stderr. Verified by `tests/test_universal_agents_md.py::test_render_under_150_lines_for_live_corpus` AND `tests/test_phase5_end_to_end.py::test_universal_agents_md_under_150_lines`. |
| Each transformer has unit tests that verify both file *presence* and content shape. | ✅ | Six new test modules: `test_copilot_instructions.py` (12 tests), `test_claude_md.py` (9), `test_junie_agents_md.py` (10), `test_universal_agents_md.py` (10), `test_memory_bank_scaffold.py` (8), `test_phase5_end_to_end.py` (4) — 53 new tests. Plus 4 new tests in `test_build_graph.py` for the `topo_sort_relaxed` helper. Each transformer test module covers: file presence (output path exists, is a regular file, has non-zero bytes); content shape (per-rule sections present, target-filtering correctness, ordering, structured-log JSON, live-corpus round-trip). Full repo suite: 169/169 passing. |

All three acceptance criteria are fully met. No `[!]` annotations are needed for Phase 5.

## 5. Decisions Made

For each non-trivial choice made during this session under conditions of ambiguity:

- **Decision**: Add `topo_sort_relaxed(rules)` to `compiler/core/build_graph.py` (subset-friendly
  topo sort that drops cross-subset dependency edges) instead of using the strict
  `build_graph(rules).topo_sorted()` for the four concatenated transformers (Copilot, Claude,
  Junie, Universal AGENTS.md).
  - **Alternatives considered**: (a) Use the strict `build_graph(rules)` on the
    stack-filtered subset — fails with a `GraphError` when a kept rule depends on an
    excluded rule (real case: `controller-pageable-defaults` is kept by Boot-2's
    `framework_version: ">=2.7"` but its dependency `controller-dto-record-mandate` is
    excluded by `>=3.0`). (b) Change the transformer API to accept BOTH the full corpus
    AND the filtered subset, build the full graph once, then walk the topo-sorted full
    list keeping only filtered entries. (c) Construct synthetic `SourceRule` copies with
    cross-subset deps stripped, then call `build_graph`.
  - **Rationale**: (a) is wrong — it spuriously fails legitimate builds. (b) requires
    changing every transformer's signature AND the CLI dispatch, expanding the surface for
    little gain (the relaxed sort is functionally identical to the "walk full topo, keep
    subset" approach when no cycles exist within the subset). (c) requires unfreezing the
    dataclass or building synthetic copies — invasive. The chosen `topo_sort_relaxed` is
    37 lines, well-tested (4 new tests), and exposes a clean public API for any future
    transformer that operates over a pruned subset. The strict `build_graph` is preserved
    unchanged because it's the right guardrail for full-corpus validation (Phase 7 release
    workflow MUST surface a dangling `dependencies:` reference as a build failure; the
    relaxed sort would hide that at release time). The two functions co-exist with clearly
    separated roles.
  - **Reversible?**: Yes — if a future phase requires stricter behavior, switch the
    transformers' imports back to `build_graph` and supply a closure-augmented subset.

- **Decision**: Author three `source/<lang>/<framework>/_meta.yml` files
  (`source/java/spring-boot/_meta.yml`, `source/typescript/nestjs/_meta.yml`,
  `source/python/fastapi/_meta.yml`) as part of this session, even though Phase 3 was the
  primary content-authoring phase and the playbook hard rule says "DO NOT execute work
  outside the scope of Phase 5."
  - **Alternatives considered**: (a) Hard-code the Memory Bank's `techContext.md` and
    `systemPatterns.md` content inside `memory_bank_scaffold.py`. (b) Make the Memory Bank
    scaffold a no-op stub for now and defer the populated-content variant to Phase 6.
    (c) Author the `_meta.yml` files as part of Phase 5.
  - **Rationale**: Plan §8 task 5 explicitly names `source/<lang>/<framework>/_meta.yml` as
    the data source for the Memory Bank's `techContext.md` and `systemPatterns.md`. Without
    these files the transformer cannot produce a meaningful artifact. Architecture Upgrade
    Report §5.1 already shows `_meta.yml` as a planned file under `source/java/spring-boot/`.
    These files are stack-descriptor data, NOT rules — they don't validate against
    `schemas/source-rule.schema.json` and don't participate in the rule graph. Authoring
    them is a Phase-5 prerequisite under the plan's own task list, not a Phase-3 retroactive
    edit. The files are small (~50 lines each), purely additive (no existing content is
    modified), and the schema is intentionally loose (no JSON Schema validates them). The
    `memory_bank_scaffold.py` transformer's `_load_meta(stack)` returns an empty dict when
    the file is absent and falls back to a minimal default diagram, so future stacks can
    ship without their `_meta.yml` if Standards Architect prefers to author it later.
  - **Reversible?**: Yes — delete the files; the transformer falls back to a minimal
    default-diagram + empty-fields output.

- **Decision**: Universal AGENTS.md emits **one-line summaries** (`- <title>.`) per
  high-priority rule rather than the full Enforced Standards body.
  - **Alternatives considered**: (a) Include the full body of each high-priority rule
    (would exceed 150 lines for 16 high rules). (b) Include a paragraph summary per rule
    (would land at ~3 lines × 16 rules = 48 lines just for Code Style). (c) Title-only
    one-liners.
  - **Rationale**: The Phase-4 log's Phase-5 lesson explicitly anticipated this:
    > The 18-rule corpus's `agents_md_priority` distribution is heavily weighted toward
    > `high` (16 of 18). The Phase-3 lesson already warned: the universal AGENTS.md's
    > ≤150-line cap will be exceeded if Phase 5 emits ~10 lines per rule. Mitigation
    > options Phase 5 should plan for: (a) emit only `title` + one-line summary per rule
    > (NOT the full Enforced Standards body) ...
    The AGENTS.md spec (per Architecture Upgrade Report §3.4) recommends ≤150 lines for
    context-budget efficiency; the canonical-sections wrapper (Tech Stack, Commands, Code
    Style, Testing, Boundaries, plus the AI-generation table and Provenance) takes ~40
    lines on its own. Title-only one-liners are the only shape that fits the spec + the
    16-high-rule reality. Full bodies still ship to Cursor, Copilot, Claude, and Junie
    where length is not capped — AGENTS.md is the lowest-common-denominator surface,
    pointing AI agents at the tool-specific files for full content.
  - **Reversible?**: Yes — a future phase can emit longer summaries if the high-priority
    count drops (Standards Architect demotes rules to `medium`) or if the AGENTS.md spec
    relaxes the cap.

- **Decision**: Strip the source `# Title` H1 and replace it with an H3 per-rule heading in
  the concatenated targets (Copilot, Claude), AND demote every remaining ATX heading by
  one level (H2 → H3, H3 → H4, …).
  - **Alternatives considered**: (a) Preserve source H1s as-is — produces a file with
    ~17 H1s and no logical hierarchy. (b) Strip the H1 and preserve H2 ordering (no
    demotion) — the per-rule heading would be at the same level as the rule's body
    sections, breaking the visual hierarchy.
  - **Rationale**: A concatenated file needs one H1 (the file title), H2 for layer
    grouping, H3 for per-rule headings, H4+ for the rule body's sub-sections. Stripping
    the source H1 + demoting all remaining headings achieves this without ambiguity.
    H6 stays at H6 (Markdown has no H7).
  - **Reversible?**: Yes — the strip/demote logic is in two small helpers
    (`_strip_h1_heading`, `_demote_headings`) per transformer.

- **Decision**: Multi-layer rules appear under EACH layer section in the Copilot/Claude
  output (e.g., `findall-pagination-mandate` with `layers: [repository, controller]`
  appears once under `## Controller Layer` AND once under `## Repository Layer`) rather
  than deduplicating to the first layer.
  - **Alternatives considered**: (a) Place the rule under only its first layer (canonical
    enum order). (b) Place it under a special "multi-layer" section. (c) Duplicate under
    every layer.
  - **Rationale**: Copilot/Claude users scroll to the layer section relevant to their
    current file and expect to see EVERY rule that applies there. Deduplicating to the
    first layer hides the rule from users looking under the second layer (a real
    failure mode for multi-layer rules like pagination). Duplication is cheaper than
    under-coverage; the rule's body is identical in both places. A dedicated "multi-layer"
    section would scatter the related rules and force users to read both sections to be
    sure.
  - **Reversible?**: Yes — flip `_grouping_for_rule` to return only the first matching
    layer.

- **Decision**: The `memory_bank_scaffold` transformer accepts a `rules` parameter but
  does not consume it; Memory Bank content is derived entirely from the stack descriptor
  + `_meta.yml`.
  - **Alternatives considered**: (a) Drop the `rules` parameter from
    `memory_bank_scaffold.emit_for_stack` and make its signature `(stack, *, dist_root,
    logger=None)`. (b) Keep the parameter for API uniformity.
  - **Rationale**: The CLI dispatch in `__main__.py::_dispatch_target` calls every
    transformer with the same `(filtered_rules, stack, dist_root, logger)` shape. Keeping
    the parameter — even unused — lets the dispatch stay uniform and lets a future
    Memory-Bank-extension (e.g., generate `activeContext.md` from rule-recency telemetry
    in Phase 9) plug in without touching the CLI. The parameter is documented as accepted
    for API uniformity.
  - **Reversible?**: Yes — drop the parameter; the dispatch becomes a two-line if-else.

## 6. Blockers Encountered

- **Blocker**: First end-to-end smoke run of `python -m compiler --stack java-spring-boot-2
  --target all` failed with `GraphError: Dependency reference(s) do not resolve to any
  authored rule:  - java-spring-controller-pageable-defaults →
  java-spring-controller-dto-record-mandate (declared in source/java/spring-boot/controller/pageable-defaults.md)`.
  Root cause: the Copilot transformer's `_topological_order` called the strict
  `build_graph(rules)` on the stack-filtered subset, but `pageable-defaults`
  (`framework_version: ">=2.7"`) is kept by the Boot-2 filter while its dependency
  `dto-record-mandate` (`framework_version: ">=3.0"`) is excluded.
  - **Resolution**: Added `compiler.core.build_graph.topo_sort_relaxed(rules)` — a
    subset-friendly topo sort that drops cross-subset dependency edges. Updated the four
    concatenated transformers (Copilot, Claude, Junie, Universal AGENTS.md) to use it.
    Added 4 new tests in `test_build_graph.py` to lock the behavior. All 169 tests now
    pass.
  - **Carry-forward**: None — `topo_sort_relaxed` is a clean public API; the strict
    `build_graph` is preserved unchanged for Phase 7's full-corpus validation.

- **Blocker**: First end-to-end smoke run crashed during the Memory Bank emit phase with
  `KeyError: "Attempt to overwrite 'filename' in LogRecord"`. Root cause: Python's
  `logging.LogRecord` reserves the attribute name `filename` for the source file emitting
  the log; passing `filename=...` via `log_event(...)` collides.
  - **Resolution**: Renamed the kwarg to `memory_bank_file` in
    `memory_bank_scaffold.emit_for_stack`. The structured JSON log line now carries
    `"memory_bank_file": "techContext.md"` instead of `"filename": "techContext.md"`.
    Test `test_emit_logs_structured_json` was authored against the renamed field.
  - **Carry-forward**: Phase-5/Phase-7 transformers should avoid Python `logging`
    reserved names. The full reserved set is in `compiler/core/logging_setup.py`
    (`_STANDARD_LOGRECORD_FIELDS` constant — already filtered in the formatter, but the
    underlying `logger.log(..., extra=...)` rejects the keys at submit time).

No other blockers occurred.

## 7. Lessons that Affect Later Phases

- **Lesson — Phase 6 (golden snapshots)**: The Phase-5 transformers all expose a pure
  `render_*(rules, stack)` function plus a side-effecting `emit_for_stack(...)`. Phase-6
  golden snapshots should target the pure render function for byte-for-byte fixtures —
  this avoids needing a real filesystem in golden tests. Suggested directory layout:
  `tests/golden/<stack-id>/{cursor/,copilot/copilot-instructions.md,claude/CLAUDE.md,
  junie/AGENTS.md,agents-md/AGENTS.md,memory-bank/*.md}`.

- **Lesson — Phase 6 (golden snapshots)**: The Memory Bank `techContext.md` and
  `systemPatterns.md` content depends on `source/<lang>/<framework>/_meta.yml`. Golden
  fixtures for Memory Bank must lock the `_meta.yml` content too — or accept that bumping
  `_meta.yml` is a golden-file refresh trigger (use `make update-golden`).

- **Lesson — Phase 6 (golden snapshots)**: The four concatenated targets emit large files
  (Copilot ~2200 lines, Claude ~2250, Junie ~200, AGENTS.md ~66). Golden diffs for the
  concatenated targets will be visually noisy when a single source rule changes. Consider
  per-rule fixture splits OR a `make explain-golden-diff` target that summarizes "rule X
  changed" instead of dumping the full byte diff.

- **Lesson — Phase 6 (fixtures)**: The end-to-end `--target all` smoke step in
  `.github/workflows/validate.yml` checks for the presence of specific marker files
  (cursor/rules dir, copilot/copilot-instructions.md, etc.) — this is the minimal AC1
  check. Phase 6's fixture-driven tests should be a strict superset (full byte-level
  diff) so the smoke step can stay as a fast guardrail.

- **Lesson — Phase 7 (release workflow)**: The CLI's `--target all` flag is the right
  entry point for `release.yml` to invoke per stack. Recommendation for Phase 7's shell
  loop: `for stack in $(STACKS); do python -m compiler --stack $stack --target all --out
  dist/; done`. The `transformer-complete` JSON log line per target gives release.yml a
  natural progress-tracking surface.

- **Lesson — Phase 7 (CHANGELOG generation)**: The `emit` JSON log lines carry
  `rule_count`, `bytes`, `line_count` (for AGENTS.md) — Phase 7's CHANGELOG generation
  can `jq` these to produce a per-release size-delta report ("AGENTS.md grew from 66 to
  72 lines this release; 2 rules added; 0 removed").

- **Lesson — Phase 7 (release workflow)**: `AgentsMdTooLongError` is a clean signal that
  the build SHOULD fail at release time. Phase 7's `release.yml` must not catch this — let
  the workflow fail loudly and force the operator (Standards Architect) to demote some
  high-priority rules before re-running. This is the architectural-budget guardrail the
  Phase-4 log warned about.

- **Lesson — Phase 8 (consumer sync)**: The consumer-sync tool can read the `_meta.yml`
  files under `source/<lang>/<framework>/` (NOT the dist tree) to compute the required
  consumer-side dependencies and env vars. This is the alternative to bundling the
  metadata into every Memory Bank output file. The current Phase-5 implementation embeds
  the metadata into `techContext.md`, which is the simpler path for now.

- **Lesson — Phase 9 (telemetry)**: The new `transformer-complete` JSON log line per
  target is the natural source for adoption telemetry. Each line is self-contained
  (timestamp, stack, target, files_written, bytes_total).

- **Lesson — global**: `_meta.yml` files under `source/<lang>/<framework>/` are
  stack-descriptor data, not rules. The Phase-2 schema (`source-rule.schema.json`) does
  NOT validate them; `compiler/core/parse_source.py` does NOT pick them up (its
  `rglob("*.md")` excludes them). The schema is loose by design; the file is YAML, and
  the transformer treats unknown keys as no-ops. If the Standards Architect wants tighter
  validation in a future phase, add `schemas/meta-yaml.schema.json` and a validator
  step.

(No `> ⚠️ Revision` callout was added to `docs/02-implementation-plan.md` — every Phase-6+
lesson here is operational guidance or in-scope-of-that-phase recommendation, not a plan
revision.)

## 8. Verification Commands Run

```bash
# V-1: Every Phase-5 artifact present.
$ for f in compiler/transformers/copilot_instructions.py \
           compiler/transformers/claude_md.py \
           compiler/transformers/junie_agents_md.py \
           compiler/transformers/universal_agents_md.py \
           compiler/transformers/memory_bank_scaffold.py \
           source/java/spring-boot/_meta.yml \
           source/typescript/nestjs/_meta.yml \
           source/python/fastapi/_meta.yml \
           tests/test_copilot_instructions.py \
           tests/test_claude_md.py \
           tests/test_junie_agents_md.py \
           tests/test_universal_agents_md.py \
           tests/test_memory_bank_scaffold.py \
           tests/test_phase5_end_to_end.py; do
    [[ -f "$f" ]] && echo "OK $f ($(wc -l <"$f" | tr -d ' ') lines)" || echo "MISS $f"
  done
OK compiler/transformers/copilot_instructions.py (264 lines)
OK compiler/transformers/claude_md.py (253 lines)
OK compiler/transformers/junie_agents_md.py (211 lines)
OK compiler/transformers/universal_agents_md.py (280 lines)
OK compiler/transformers/memory_bank_scaffold.py (318 lines)
OK source/java/spring-boot/_meta.yml (72 lines)
OK source/typescript/nestjs/_meta.yml (45 lines)
OK source/python/fastapi/_meta.yml (44 lines)
OK tests/test_copilot_instructions.py (186 lines)
OK tests/test_claude_md.py (124 lines)
OK tests/test_junie_agents_md.py (140 lines)
OK tests/test_universal_agents_md.py (165 lines)
OK tests/test_memory_bank_scaffold.py (106 lines)
OK tests/test_phase5_end_to_end.py (121 lines)

# V-2: AC1 — `python -m compiler --stack java-spring-boot-3 --target all` produces the §5.2 tree.
$ rm -rf /tmp/p5-final && PYTHONPATH=. .venv-phase2/bin/python -m compiler \
    --stack java-spring-boot-3 --target all --out /tmp/p5-final 2>/dev/null
$ find /tmp/p5-final/stacks/java-spring-boot-3 -type f | sort | head -10
/tmp/p5-final/stacks/java-spring-boot-3/agents-md/AGENTS.md
/tmp/p5-final/stacks/java-spring-boot-3/claude/CLAUDE.md
/tmp/p5-final/stacks/java-spring-boot-3/copilot/copilot-instructions.md
/tmp/p5-final/stacks/java-spring-boot-3/cursor/rules/_global-clean-architecture.mdc
/tmp/p5-final/stacks/java-spring-boot-3/cursor/rules/_global-logging-telemetry.mdc
/tmp/p5-final/stacks/java-spring-boot-3/cursor/rules/_global-security-baselines.mdc
... (17 .mdc files + 1 copilot + 1 claude + 1 junie + 1 agents-md + 6 memory-bank = 27 files total)

# V-3: AC2 — AGENTS.md is ≤150 lines for the live corpus.
$ wc -l /tmp/p5-final/stacks/java-spring-boot-3/agents-md/AGENTS.md
      66 /tmp/p5-final/stacks/java-spring-boot-3/agents-md/AGENTS.md

# V-4: Per-target line counts for the four concatenated outputs.
$ wc -l /tmp/p5-final/stacks/java-spring-boot-3/{agents-md/AGENTS.md,copilot/copilot-instructions.md,claude/CLAUDE.md,junie/AGENTS.md}
      66 /tmp/p5-final/stacks/java-spring-boot-3/agents-md/AGENTS.md
    2214 /tmp/p5-final/stacks/java-spring-boot-3/copilot/copilot-instructions.md
    2254 /tmp/p5-final/stacks/java-spring-boot-3/claude/CLAUDE.md
     195 /tmp/p5-final/stacks/java-spring-boot-3/junie/AGENTS.md

# V-5: Universal AGENTS.md content sample — canonical sections present.
$ grep -E '^##' /tmp/p5-final/stacks/java-spring-boot-3/agents-md/AGENTS.md
## Tech Stack
## Commands
## Code Style
## Testing
## Boundaries
## Where AI Should and Should Not Generate
## Provenance

# V-6: All five Phase-5 transformers + Phase-5 end-to-end tests pass.
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest \
    tests/test_copilot_instructions.py \
    tests/test_claude_md.py \
    tests/test_junie_agents_md.py \
    tests/test_universal_agents_md.py \
    tests/test_memory_bank_scaffold.py \
    tests/test_phase5_end_to_end.py -q
............................................                              [100%]
53 passed in 1.97s

# V-7: Full repo test suite (Phase-2 + Phase-4 + Phase-5).
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest tests/ -q
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 4.13s

# V-8: Structured JSON logs cover every Phase-5 target.
$ rm -rf /tmp/p5-final && PYTHONPATH=. .venv-phase2/bin/python -m compiler \
    --stack java-spring-boot-3 --target all --out /tmp/p5-final 2>&1 >/dev/null | \
    grep '"transformer-complete"' | jq -r '"\(.target) \(.files_written) files \(.bytes_total) bytes"'
cursor 17 files 109363 bytes
github_copilot 1 files 106894 bytes
claude_skills 1 files 108383 bytes
junie 1 files 14314 bytes
agents_md 1 files 2899 bytes
memory_bank 6 files 4126 bytes

# V-9: --target all succeeds for every stack in the catalog.
$ for sid in java-spring-boot-3 java-spring-boot-2 typescript-nestjs-10 python-fastapi-0-110; do
    out=$(mktemp -d)
    PYTHONPATH=. .venv-phase2/bin/python -m compiler --stack "$sid" --target all --out "$out" >/dev/null 2>&1
    echo "$sid: exit=$? files=$(find "$out/stacks/$sid" -type f | wc -l | tr -d ' ')"
  done
java-spring-boot-3: exit=0 files=27
java-spring-boot-2: exit=0 files=24
typescript-nestjs-10: exit=0 files=11
python-fastapi-0-110: exit=0 files=11

# V-10: AgentsMdTooLongError fires when the cap is forced low (cap-diagnostic test).
$ PYTHONPATH=. .venv-phase2/bin/python -c "
from compiler.core.parse_source import parse_all
from compiler.core.stack_filter import stack_by_id, filter_for_stack
from compiler.transformers import universal_agents_md
rules = filter_for_stack(parse_all(), stack_by_id('java-spring-boot-3'))
try:
    universal_agents_md.render_universal_agents_md(rules, stack_by_id('java-spring-boot-3'), max_lines=20)
except universal_agents_md.AgentsMdTooLongError as e:
    print('OK:', str(e)[:80])
"
OK: Universal AGENTS.md for stack 'java-spring-boot-3' would be 66 lines (cap: 2

# V-11: validate.yml end-to-end --target all smoke (mirrors GitHub Actions on PR).
$ out_dir=$(mktemp -d) && PYTHONPATH=. .venv-phase2/bin/python -m compiler \
    --stack java-spring-boot-3 --target all --out "$out_dir" >/dev/null 2>&1
$ stack_root="$out_dir/stacks/java-spring-boot-3"
$ for path in "$stack_root/cursor/rules" "$stack_root/copilot/copilot-instructions.md" \
              "$stack_root/claude/CLAUDE.md" "$stack_root/junie/AGENTS.md" \
              "$stack_root/agents-md/AGENTS.md" "$stack_root/memory-bank/techContext.md"; do
    [[ -e "$path" ]] && echo "OK $path" || echo "MISS $path"
  done
OK <tmp>/stacks/java-spring-boot-3/cursor/rules
OK <tmp>/stacks/java-spring-boot-3/copilot/copilot-instructions.md
OK <tmp>/stacks/java-spring-boot-3/claude/CLAUDE.md
OK <tmp>/stacks/java-spring-boot-3/junie/AGENTS.md
OK <tmp>/stacks/java-spring-boot-3/agents-md/AGENTS.md
OK <tmp>/stacks/java-spring-boot-3/memory-bank/techContext.md

# V-12: linter sanity — every Phase-5 source file is lint-clean.
$ # ReadLints over: compiler/transformers/, compiler/core/build_graph.py, compiler/__main__.py,
$ # tests/test_{copilot_instructions,claude_md,junie_agents_md,universal_agents_md,memory_bank_scaffold,phase5_end_to_end,build_graph}.py
No linter errors found.
```

## 9. Handoff to Next Session

- **Next phase**: 6 — Fixtures, Golden Files, and CI (see `docs/02-implementation-plan.md` §9).
- **Next-session prompt**: written to `docs/execution-log/next-session-prompt.md`
  (overwriting the Phase-5 prompt).
- **Pre-requisites for next phase that are now satisfied**:
  - All five Phase-5 transformers expose a pure `render_*(rules, stack)` function — Phase 6
    golden snapshots can fixate output byte-for-byte without filesystem I/O.
  - `compiler.core.build_graph.topo_sort_relaxed(rules)` is the right entry point for any
    Phase-6 fixture that operates over a stack-filtered subset.
  - `python -m compiler --stack <id> --target all --out <dir>` is the canonical
    end-to-end invocation; Phase 6 fixtures can use the same path and assert byte-level
    equality against `tests/golden/<stack-id>/`.
  - The four `source/<lang>/<framework>/_meta.yml` files (Java/Spring-Boot, TS/NestJS,
    Python/FastAPI) are on disk; Memory Bank golden fixtures must include them in their
    fixture-root or accept that updates to `_meta.yml` are golden-refresh triggers.
  - `.github/workflows/validate.yml`'s `compiler-unit-tests` job already runs the
    Phase-5 tests AND the AC1+AC2 end-to-end smoke; Phase 6 should add a sibling
    `golden-snapshots` job per the Phase-2 lesson (each phase extends THIS workflow file
    rather than introducing parallel workflows).
  - The `transformer-complete` JSON log line per target is a natural surface for Phase-6
    fixtures to assert against (lets a fixture verify "6 targets ran, X files written")
    without re-parsing the disk.
- **Open questions for the operator**:
  - Phase 3's `java-spring-di-constructor-injection-mandate` carry-forward
    (`framework_version: ">=4.3"` excludes it from every Spring Boot stack) remains open
    from Phase 4. None of Phase 5's work blocks on it; the issue surfaces consistently in
    every Phase-5 transformer's stack-filter output. The closing Phase-5 PR is a natural
    moment to triage with Standards Architect.
  - The four pre-existing carry-overs from Phases 0/1/3 (AI Enablement PM ADR sign-off;
    Cursor-load smoke test; GitHub-UI branch-protection apply + screenshot; Phase-7
    CODEOWNERS+dist-protection-lint live experiment; Standards-Architect sign-off on the
    18 Phase-3 rules) remain open. None block Phase 6.
  - The Memory Bank scaffold writes six identical files across all four stacks; Phase 9
    (telemetry / pilot adoption) is the right moment to evaluate whether real pilot teams
    want richer pre-populated content (e.g., a real `activeContext.md` template instead of
    a stub). Phase 6 should not change the scaffold's contract — golden fixtures lock it.
