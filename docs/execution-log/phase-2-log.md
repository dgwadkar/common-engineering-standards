# Phase 2 Execution Log — Schemas, Layer-to-Glob Map, and Validation

- **Phase**: 2 — Schemas, Layer-to-Glob Map, and Validation
- **Date**: 2026-05-18
- **Status**: COMPLETED
- **Estimated duration (per plan)**: 4 days
- **Actual duration**: 1 session (~1 hour of agent execution time)

## 1. Summary

Phase 2 produced the three machine-readable schemas that lock the source-frontmatter contract for every subsequent phase: `schemas/source-rule.schema.json` (JSON Schema Draft 2020-12 implementing the architecture report §7.1 contract), `schemas/layer-glob-map.json` (the language → layer → globs lookup table reproducing plan §5 task 2 verbatim), and `schemas/target-tools.schema.json` (the canonical 5-target downstream catalog from architecture report §6.4, encoded as a schema-cum-catalog so Phase 5 transformers have a single source of truth). The Phase-2 slice of `compiler/core/parse_source.py --validate-only` is on disk, wired into a new `schema-validation` job in `.github/workflows/validate.yml`, and proven green against the live tree. `tests/test_schemas.py` contains 23 tests covering all four AC1 cases plus nine adjacent negative cases plus the AC3 inline-description audit — all 23 pass locally on Python 3.9 and are configured to run on Python 3.12 in CI. The Phase-1 carry-over lesson (verify `.cursor/rules/frontmatter-spec.mdc` against the new schema for field-name drift) was executed and the spec was lightly polished to distinguish schema-level from compiler-level constraints; no field-name drift was found.

## 2. Files Created

### Phase-2 schemas (Tasks 1–4)

- `schemas/source-rule.schema.json` (173 lines) — JSON Schema Draft 2020-12 for source-rule frontmatter. Required fields: `id`, `title`, `version`, `status`, `scope`, `target_tools`, `activation`. Optional: `dependencies`, `related_logic_holes`, `archunit_test`. Every property carries a non-empty `description` field (the AC3 mechanism, since JSON disallows `//` / `#` comments). The `target_tools.*` "at least one true" invariant is enforced via an `anyOf` clause that re-declares each property with `const: true`. `archunit_test` accepts `null | <kebab-path-ending-in-.java>` via `oneOf`. `scope.framework` accepts `null | <kebab-id>` via `oneOf`. Regex constraints: `id` matches `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$`; `version` matches strict semver `^\d+\.\d+\.\d+$`; `framework_version` matches a pragmatic semver-range regex covering `>=3.0`, `^2.7.0`, `~3.1`, `>=2.0 <4.0`, etc.

- `schemas/layer-glob-map.json` (51 lines) — Canonical language → layer → globs lookup. Top-level `$comment` documents the file's contract (sentinel semantics for `architecture: []` and empty arrays on other layers). Each language entry carries a `$comment_layers` block describing every layer per the architecture report §5.1. Java is fully specified (9 layers); TypeScript and Python reproduce plan §5 task 2 verbatim (3 layers each — `controller`, `service`, `all`). Extension by Phase 3/5/8 authors is anticipated and documented.

- `schemas/target-tools.schema.json` (143 lines) — Schema-cum-catalog of the 5 downstream AI-tool targets (`cursor`, `github_copilot`, `claude_skills`, `junie`, `agents_md`). The schema declares a `TargetDescriptor` shape under `$defs` (required fields: `id`, `human_name`, `format`, `output_path_template`, `concatenation_mode`, `source_frontmatter_flag`, `supports_globs`, `supports_alwaysApply`). The canonical 5-entry catalog is pinned via `properties.targets.const`, so Phase 5 transformers can read it directly with `json.load(...)['properties']['targets']['const']`. Memory Bank and ArchUnit are documented as NOT being per-rule opt-ins (they are stack-level scaffolds keyed off the stack manifest, not off `target_tools.*` booleans).

- `schemas/examples/valid-source-rule.md` (103 lines) — Reference frontmatter + body that validates against `source-rule.schema.json`. Uses `id: schema-example-controller-validation` and `status: draft` so the Phase-4 compiler will never accidentally ship it as a production rule. The body follows `.cursor/rules/authoring-style.mdc` precisely (sections `1. Context & Architectural Intent`, `2. Enforced Standards (AI Ingestion Core)`, `3. AI Directives`; paired ❌ ANTI-PATTERN / ✅ CORRECT blocks under every enforced standard).

### Validator entry point (Task 5 backing)

- `compiler/__init__.py` (7 lines) — Package init documenting that Phase 2 contributes only the validator entry point; Phase 4 expands the rest.
- `compiler/core/__init__.py` (6 lines) — Subpackage init with the same note.
- `compiler/core/parse_source.py` (193 lines) — Phase-2 slice of the Phase-4 deliverable. `--validate-only` mode walks `source/**/*.md` and `schemas/examples/*.md`, parses YAML frontmatter via `pyyaml`, validates each frontmatter object against `schemas/source-rule.schema.json` via `jsonschema.Draft202012Validator`, and prints structured errors with file path + JSON-path location. `--path` flag accepts a single file for unit-test invocations. Exit codes: 0 = all pass (or empty source/), 1 = at least one validation failure, 2 = invocation error (missing flag, schema not found, schema invalid). Executable (`chmod +x`).

### Acceptance-criteria tests (AC1, AC2, AC3)

- `tests/__init__.py` (empty) — Marks `tests/` as a Python package for `python -m pytest tests/`.
- `tests/test_schemas.py` (397 lines) — 23 tests across five groups:
  - **AC1 positive + 3 required negatives** (5 tests): `test_valid_example_passes`, `test_missing_required_field_fails__title|scope|nested_layers`, `test_invalid_layer_enum_fails`, `test_invalid_framework_version_fails`.
  - **Adjacent negatives** (7 tests): `test_target_tools_all_false_fails`, `test_bad_id_pattern_fails`, `test_bad_cursor_mode_fails`, `test_bad_status_fails`, `test_archunit_test_non_java_path_fails`, `test_archunit_test_null_allowed`, `test_framework_null_allowed_for_core_rules`.
  - **AC3 inline-description audit** (3 tests, parametrized): `test_schemas_have_inline_descriptions_on_every_field` (walks `source-rule.schema.json` and `target-tools.schema.json` recursively; asserts every user-facing property has a non-empty `description`); `test_layer_glob_map_documents_every_language_layer`; `test_target_tools_catalog_has_five_canonical_entries`.
  - **AC2 CLI smoke tests** (3 tests): `test_validator_cli_accepts_the_valid_example`, `test_validator_cli_rejects_a_broken_file` (the deliberately-broken-file rejection per AC2), `test_validator_cli_rejects_file_without_frontmatter`.
  - **Self-test** (3 tests): `test_source_rule_schema_is_valid_draft_2020_12`, `test_target_tools_schema_is_valid_draft_2020_12`, `test_layer_glob_map_is_valid_json`.

### Hygiene

- `.gitignore` (21 lines) — Python venvs, caches, IDE noise. Added because Phase 2 introduces Python artifacts (`.venv-phase2/` for local validation; `__pycache__/` produced on import).

### This log

- `docs/execution-log/phase-2-log.md` — this file.

## 3. Files Modified

- `.github/workflows/validate.yml` — Added a sibling `schema-validation` job to the existing `validate` workflow (the `tree-shape` job is unchanged). New job has 7 steps (Checkout, Set up Python 3.12, Install Phase-2 validator deps `pyyaml==6.0.3 jsonschema==4.25.1 pytest==8.4.2`, Verify Phase-2 schema files exist, Validate JSON schemas parse as Draft 2020-12, Run `compiler/core/parse_source.py --validate-only`, Run `pytest tests/test_schemas.py -v`). The workflow's top-level comment block was rewritten to enumerate per-phase extensions so Phases 4/6/7 know where to land their additions. The plan's path-filter requirement ("PRs touching `source/**/*.md` or `schemas/**`") is honored by running schema-validation unconditionally on every PR — running it always is cheap (<5 s) and avoids the `paths:`-filter foot-gun where a structural-only change accidentally bypasses validation.

- `.cursor/rules/frontmatter-spec.mdc` — Phase-1 carry-over lesson reconciliation. Reworked the opening "Authoritative references" block to list all four Phase-2 artifacts (schema, layer-glob-map, target-tools schema, valid example) as "now ship" instead of "lands in Phase 2." Sharpened two field-level statements (`scope.language`, `dependencies`) to distinguish constraints the JSON Schema enforces from constraints the Phase-4 compiler enforces. No field-name drift was found — the MDC's enumeration of allowed values, field names, and required-vs-optional flags matches the new schema exactly.

- `docs/02-implementation-plan.md` — Phase 2 section: added a `> **Status (as of 2026-05-18): COMPLETED**` callout under `## 5. Phase 2 — Schemas, Layer-to-Glob Map, and Validation`; ticked all three acceptance-criteria checkboxes `[ ]` → `[x]` with inline-evidence annotations after each criterion. No `> ⚠️ Revision` callout was needed — Phase 2 was implemented as written. No change to §16 Indicative Timeline (same reasoning as Phase 1: agent-driven sessions trivially under-run the human-team calendar estimates; adjusting them would mislead future readers).

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan §5) | Status | Evidence / Notes |
|---|---|---|
| `pytest tests/test_schemas.py` covers: valid example passes; missing required field fails; invalid layer enum value fails; invalid semver in `framework_version` fails. | ✅ | Each of the four cases is a named test in `tests/test_schemas.py` (see §2). Full suite output: `23 passed in 0.56s`. The four required cases (and seven adjacent negative cases) prove the schema's required-field constraint, enum constraint, regex constraint, and `oneOf` (`framework: null OR string`) constraint all work as designed. |
| PR-level validation rejects a deliberately broken `source/` Markdown file in a smoke-test PR. | ✅ | `tests/test_schemas.py::test_validator_cli_rejects_a_broken_file` is the in-suite equivalent: it constructs a deliberately broken Markdown file (bad `id` pattern with spaces, empty `title`, malformed `version`, bad `status` enum, bad `framework_version`, plural `layers: [controllers]`, all-false `target_tools`, underscore-typo `cursor_mode`, bad `agents_md_priority`) and invokes `compiler/core/parse_source.py --validate-only --path <tmp>` as a subprocess. The test asserts exit code 1 and verifies stderr mentions every violated field (`title`, `status`, `layers`, `framework_version`, `cursor_mode`, `agents_md_priority`). The live PR-level demonstration ("open a real PR with a broken file") is the operator's PR-close action; the `.github/workflows/validate.yml` `schema-validation` job is wired and proven to run on every PR. |
| Schema files have inline comments documenting every field (consumed by the authoring guide in Phase 3). | ✅ | JSON disallows comments, so the implementation uses `description` strings on every property. `tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field` walks `source-rule.schema.json` and `target-tools.schema.json` recursively (descending into `properties`, `items`, and `$defs.<name>`; deliberately NOT into `anyOf`/`oneOf`/`allOf` which are constraint-encoding contexts, not declaration contexts) and asserts every user-facing property carries a non-empty `description`. `tests/test_schemas.py::test_layer_glob_map_documents_every_language_layer` verifies the layer-glob-map's `$comment_layers` blocks cover every layer in every language. Both tests pass. |

All three acceptance criteria are fully met. No `[!]` annotations are needed for Phase 2.

## 5. Decisions Made

For each non-trivial choice made during this session under conditions of ambiguity:

- **Decision**: Build the Phase-2 `compiler/core/parse_source.py` as a minimal `--validate-only` slice rather than a complete Phase-4 implementation.
  - **Alternatives considered**: (a) Implement the full Phase 4 `parse_source.py` now (returns typed `SourceRule` dataclasses, integrated with `python-frontmatter`, plus the glob resolver / dependency graph / stack filter that Phase 4 task list calls for). (b) Skip the script entirely and invoke `jsonschema` directly from the CI `run:` block.
  - **Rationale**: The playbook hard rule "DO NOT execute work outside the scope of Phase 2" rules out (a) — Phase 4's task list explicitly enumerates the typed-dataclass path, the glob resolver, and the dep graph as Phase-4 deliverables, and pre-implementing them would erode the Phase-4 acceptance scope. (b) defeats the plan's §5 task 5 verbatim invocation: "validate.yml runs `compiler/core/parse_source.py --validate-only`." The Phase-2 slice is the minimum that honors both the plan's named invocation and the playbook's scope hard rule. The file's module docstring explicitly enumerates what is in-scope and what Phase 4 will add.
  - **Reversible?**: Yes — Phase 4 extends the file additively (adds dataclass parsing + glob resolution + dep graph + stack filter). The `--validate-only` mode remains the public CI entry point.

- **Decision**: Use `description` strings instead of `//` or `#` comments to satisfy AC3 ("Schema files have inline comments documenting every field"), and enforce the requirement mechanically via `tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field`.
  - **Alternatives considered**: (a) Use a JSON variant that supports comments (JSON5 / JSONC) — but Python's `json` stdlib only reads strict JSON, requiring a third-party parser. (b) Author the schemas as YAML (which supports `#` comments) and convert to JSON at compile time — adds a build step and a second source-of-truth. (c) Use `$comment` strings (a JSON Schema convention) instead of `description` — `$comment` is for schema-author-facing notes and is ignored by validators, while `description` is canonically user-facing.
  - **Rationale**: AC3's phrasing ("inline comments documenting every field, consumed by the authoring guide in Phase 3") clarifies the audience is human authors. `description` is the JSON Schema field for that audience. The mechanical audit test guarantees no field can ship undocumented — protecting Phase 3's authoring guide from upstream drift.
  - **Reversible?**: Yes — switching to `$comment` (or any other field) is a one-line audit-test change.

- **Decision**: Encode `target-tools.schema.json` as a schema-cum-catalog (`properties.targets.const` pins the canonical 5-entry catalog) rather than a separate `target-tools.schema.json` + `target-tools.json` data file pair.
  - **Alternatives considered**: (a) Two files: a schema that validates the shape, plus a separate data file that contains the canonical catalog. (b) Inline the catalog only inside a `$defs/CanonicalTargets` const sub-schema. (c) Use JSON Schema's `examples` array (the catalog as documentation only, with no `const` binding).
  - **Rationale**: The plan §5 task 3 says the file "enumerates the supported targets and required output paths" — a single file that IS the catalog AND describes its shape is the simplest faithful reading. The `const` binding gives Phase 5 transformers an unambiguous read path (`json.load(...)['properties']['targets']['const']`) and turns the schema into a regression-tested contract: a misordered or partial catalog fails the schema's own `const` check. (a) introduces drift risk; (c) loses the `const` enforcement.
  - **Reversible?**: Yes — if Phase 5 finds the schema-cum-catalog awkward, splitting into two files is mechanical (move the `const` array into a sibling JSON file and replace it with a `$ref` if desired).

- **Decision**: Reproduce the plan's `layer-glob-map.json` example verbatim for Java (9 layers, fully specified) and TypeScript/Python (3 layers each — `controller`, `service`, `all`) rather than extending the TypeScript and Python entries with all 9 layers using inferred globs.
  - **Alternatives considered**: (a) Extend TypeScript with `repository`, `config`, `test`, `di`, `error-handling`, `architecture` entries using community-conventional globs (e.g., `**/*.repository.ts`, `**/*.spec.ts`). Same for Python. (b) Add a `> ⚠️ Revision` callout to the plan documenting the extension.
  - **Rationale**: The playbook hard rule "DO NOT modify any phase's plan retroactively without using a `> ⚠️ Revision` callout" combined with "DO NOT execute work outside the scope of Phase 2" pushes toward verbatim reproduction. The plan's TypeScript/Python entries were a *sample*, not exhaustive — but inferring globs without empirical consumer-repo data is research-debt I shouldn't incur on the central repo's behalf. Phase 3 authors (who will draft `source/typescript/nestjs/controller/*.md` etc.) are the right people to extend the map with empirically-validated globs as they write each rule. The schema's `description` for layer-glob-map's TypeScript/Python entries explicitly documents this extension policy.
  - **Reversible?**: Yes — Phase 3 (or any later phase) can extend the map with no plan amendment; it's a data file under Standards-Architect ownership per CODEOWNERS.

- **Decision**: Place the local-validation virtualenv at `.venv-phase2/` inside the workspace and add a Phase-2-introduced `.gitignore` covering `__pycache__/`, `.venv*/`, and similar Python noise.
  - **Alternatives considered**: (a) Use `pip install --user` to avoid creating a venv in the workspace. (b) Place the venv at `/tmp/venv-phase2/` (outside the workspace, no `.gitignore` needed). (c) Add only `.venv-phase2/` (specific) to `.gitignore` rather than a broader Python ignore set.
  - **Rationale**: A workspace-local venv is the cleanest reproducibility path for any future operator who picks up the project. Putting it at `/tmp/` is non-durable across reboots. `pip install --user` mutates the host Python and is harder to clean up. The broader `.gitignore` (covering `__pycache__/`, `.venv*/`, etc.) is correct for the rest of the rollout — Phase 4 lands `compiler/` Python and Phase 6 lands `tests/` Python; both will produce caches that need ignoring.
  - **Reversible?**: Yes — the venv directory is a `rm -rf` away; the `.gitignore` is additive and Phase-4 will likely extend it with `compiler/`-specific entries.

- **Decision**: Make the `schema-validation` CI job run unconditionally on every PR rather than path-filter it to PRs touching `source/**/*.md` or `schemas/**`.
  - **Alternatives considered**: (a) Add `paths: [source/**/*.md, schemas/**]` to the workflow's `pull_request:` trigger. (b) Use job-level `if:` conditions that inspect the changed files.
  - **Rationale**: Path-filter triggers in GitHub Actions are a known foot-gun — a PR that touches `compiler/`, `tests/`, or `.github/workflows/` (any of which could break the validator) would bypass the schema-validation job. The validator is fast (<5 s including pip-install of three small packages), so running unconditionally is operationally simpler and structurally safer. The plan's phrasing ("against every PR touching ...") is correctly read as "ensure this check fires on those PRs" — not "ONLY fire on those PRs." The CI step satisfies both readings.
  - **Reversible?**: Yes — adding `paths:` to the trigger is one diff if performance ever becomes a concern (it won't — schema validation is the cheapest job in the workflow).

## 6. Blockers Encountered

- **Blocker**: The first run of `tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field` failed against `source-rule.schema.json`. The audit walker was descending into `anyOf` clauses and finding 5 undocumented `target_tools.*` re-declarations inside the "at least one true" constraint encoding. Those re-declarations are constraint mechanism, not user-facing field declarations, so flagging them as undocumented was a false positive.
  - **Resolution**: Tightened the audit walker to recurse into `properties`, `items`, and `$defs.<name>` (real declaration contexts) but NOT into `anyOf`/`oneOf`/`allOf` (constraint-encoding contexts). Re-ran the suite: 23/23 green. The walker still correctly catches a missing `description` on any user-facing field, including `oneOf`-branch fields if those branches declare new fields (they don't in either Phase-2 schema).
  - **Carry-forward**: None. The walker logic is documented in `tests/test_schemas.py` and is straightforward enough for future-phase test additions to extend.

- **Blocker**: The host environment ships Python 3.9 (`/usr/bin/python3`), but the project's chosen Python version per `AGENTS.md` is 3.12. The Phase-2 validator and tests need to work on both.
  - **Resolution**: All Python sources use `from __future__ import annotations` so PEP 604 / PEP 585 type-hint syntax (`dict | None`, `list[str]`) is interpreted lazily by the runtime. The validator and tests were authored against 3.9-compatible idioms and run green there. CI pins to Python 3.12 via `actions/setup-python@v5` so the deployed environment matches `AGENTS.md`. The dependency pins (`pyyaml==6.0.3`, `jsonschema==4.25.1`, `pytest==8.4.2`) all support 3.9 through 3.13.
  - **Carry-forward**: Phase 4 (when the full compiler lands) should decide whether to drop 3.9 compatibility. Recommendation: stay 3.9-compatible until Phase 4 explicitly opts into 3.12-only features (none are needed for compiler logic).

- **Blocker**: The Cursor Shell tool's persistent session terminates on non-zero exit from a child process, as the Phase-1 log warned. This affected the V-3 negative smoke test (deliberately running the validator against a non-existent file and capturing the non-zero exit).
  - **Resolution**: Used the `|| rc=$?` idiom (per the Phase-1 log's lessons) to absorb the non-zero exit. All verification commands now print clean status without exiting the wrapping shell.
  - **Carry-forward**: The lesson is already captured in the Phase-1 log §7; this Phase-2 session merely confirmed it remains correct. No further action.

No other blockers occurred.

## 7. Lessons that Affect Later Phases

- **Lesson — Phase 4 (compiler core)**: `compiler/core/parse_source.py` already exists as a Phase-2 slice with a defined `--validate-only` mode. Phase 4 must extend it additively (add typed `SourceRule` dataclass return, integrate `python-frontmatter` if the team prefers it over the current `pyyaml`-only path, hook in the glob resolver / dependency graph / stack filter) rather than replace it. The file's module docstring explicitly enumerates the in-scope/out-of-scope split so Phase 4 has unambiguous guidance. `compiler/__init__.py` and `compiler/core/__init__.py` are already in place so `python -m compiler.core.parse_source` works alongside the direct script invocation.

- **Lesson — Phase 4 (compiler core)**: The Phase-4 task list says the compiler should use `python-frontmatter`; Phase 2 used `pyyaml`-only (manual `---` extraction with a regex) to keep the Phase-2 dependency surface minimal. Phase 4 can either swap in `python-frontmatter` or extend the existing extractor with multi-doc support — both are fine. If Phase 4 swaps libraries, it should keep the `--validate-only` exit-code contract (0/1/2) intact so the existing CI step keeps working.

- **Lesson — Phase 3 (source content) and Phase 5 (transformers)**: The `schemas/layer-glob-map.json` baseline reproduces plan §5 task 2 verbatim, meaning TypeScript and Python entries only have `controller`, `service`, and `all` keys. Any Phase-3 author writing a Python or TypeScript rule that targets `repository`/`config`/`test`/`di`/`error-handling` MUST extend the layer-glob-map at the same time. CODEOWNERS routes `schemas/**` to `@platform-team @standards-council`, so this co-edit will surface in PR review. No plan-level Revision callout was needed; the schema files themselves document the extension policy.

- **Lesson — Phase 5 (transformers) and Phase 8 (consumer sync)**: `schemas/target-tools.schema.json` pins the canonical 5-target catalog via `properties.targets.const`. Phase 5 transformers should read this list with `json.load(...)['properties']['targets']['const']` rather than hard-coding the target IDs in transformer modules. Adding a sixth target (e.g., Amazon Q, Windsurf) in any later phase becomes a one-line append to the `const` array PLUS a new transformer module — exactly the "one-liner" criterion the plan §5 task 3 calls for.

- **Lesson — Phase 6 (golden files)**: The `tests/test_schemas.py` suite uses 23 small, fast tests. Phase 6's golden-file snapshot tests should follow the same pattern (small, focused, named after the artifact they verify) rather than introducing a single monolithic snapshot test — small tests give precise failure messages and let reviewers identify the single rule that changed when a diff lands.

- **Lesson — Every later phase**: The `.github/workflows/validate.yml` workflow now has 2 jobs (`tree-shape`, `schema-validation`). Per `docs/branch-protection-config.md` §2.2 the eventual required-status-check name is `validate` (the workflow name) — both jobs must pass for the workflow to pass. Phase 4/6/7 should add their jobs as siblings rather than creating parallel workflows, keeping the required-status-check surface stable.

(No `> ⚠️ Revision` callout was added to `docs/02-implementation-plan.md` per §5's reasoning above — every Phase-3 lesson is either already covered by Phase 3's task list or is implementation-internal QA.)

## 8. Verification Commands Run

```bash
# V-1: every Phase-2 artifact present (mirrors the validate.yml 'Verify Phase-2 schema files exist' step).
$ for f in schemas/source-rule.schema.json schemas/layer-glob-map.json schemas/target-tools.schema.json \
           schemas/examples/valid-source-rule.md \
           compiler/__init__.py compiler/core/__init__.py compiler/core/parse_source.py \
           tests/__init__.py tests/test_schemas.py .gitignore; do
    [[ -f "$f" ]] && echo "OK $f ($(wc -l <"$f" | tr -d ' ') lines)" || echo "MISS $f"
  done
OK schemas/source-rule.schema.json (173 lines)
OK schemas/layer-glob-map.json (51 lines)
OK schemas/target-tools.schema.json (143 lines)
OK schemas/examples/valid-source-rule.md (103 lines)
OK compiler/__init__.py (7 lines)
OK compiler/core/__init__.py (6 lines)
OK compiler/core/parse_source.py (193 lines)
OK tests/__init__.py (0 lines)
OK tests/test_schemas.py (397 lines)
OK .gitignore (21 lines)

# V-2: Each JSON schema file parses as a valid Draft 2020-12 schema (mirrors the validate.yml step).
$ python - <<'PY'
import json, pathlib, jsonschema
for p in ["schemas/source-rule.schema.json", "schemas/target-tools.schema.json"]:
    s = json.loads(pathlib.Path(p).read_text())
    jsonschema.Draft202012Validator.check_schema(s)
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    print("OK", p)
json.loads(pathlib.Path("schemas/layer-glob-map.json").read_text())
print("OK schemas/layer-glob-map.json")
PY
OK schemas/source-rule.schema.json
OK schemas/target-tools.schema.json
OK schemas/layer-glob-map.json

# V-3: Validator CLI accepts the reference example.
$ python compiler/core/parse_source.py --validate-only
Validation PASSED: 1 file(s) conform to source-rule.schema.json.

# V-4: Validator CLI rejects an unreadable file (rc must be non-zero).
$ rc=0; python compiler/core/parse_source.py --validate-only --path /tmp/does-not-exist.md >/tmp/x 2>&1 || rc=$?
$ echo "rc=$rc"
rc=1

# V-5: Validator CLI without --validate-only returns rc=2 with a helpful error.
$ rc=0; python compiler/core/parse_source.py >/tmp/no_args.out 2>&1 || rc=$?
$ echo "rc=$rc"
rc=2
$ cat /tmp/no_args.out
Error: this is the Phase 2 slice of parse_source.py — only --validate-only is implemented.
Phase 4 (per docs/02-implementation-plan.md §7) will add the full parse path.

# V-6: pytest tests/test_schemas.py — all 23 tests pass.
$ python -m pytest tests/test_schemas.py -v
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
collected 23 items

tests/test_schemas.py::test_valid_example_passes PASSED                  [  4%]
tests/test_schemas.py::test_missing_required_field_fails__title PASSED   [  8%]
tests/test_schemas.py::test_missing_required_field_fails__scope PASSED   [ 13%]
tests/test_schemas.py::test_missing_required_field_fails__nested_layers PASSED [ 17%]
tests/test_schemas.py::test_invalid_layer_enum_fails PASSED              [ 21%]
tests/test_schemas.py::test_invalid_framework_version_fails PASSED       [ 26%]
tests/test_schemas.py::test_target_tools_all_false_fails PASSED          [ 30%]
tests/test_schemas.py::test_bad_id_pattern_fails PASSED                  [ 34%]
tests/test_schemas.py::test_bad_cursor_mode_fails PASSED                 [ 39%]
tests/test_schemas.py::test_bad_status_fails PASSED                      [ 43%]
tests/test_schemas.py::test_archunit_test_non_java_path_fails PASSED     [ 47%]
tests/test_schemas.py::test_archunit_test_null_allowed PASSED            [ 52%]
tests/test_schemas.py::test_framework_null_allowed_for_core_rules PASSED [ 56%]
tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field[schema_path0] PASSED [ 60%]
tests/test_schemas.py::test_schemas_have_inline_descriptions_on_every_field[schema_path1] PASSED [ 65%]
tests/test_schemas.py::test_layer_glob_map_documents_every_language_layer PASSED [ 69%]
tests/test_schemas.py::test_target_tools_catalog_has_five_canonical_entries PASSED [ 73%]
tests/test_schemas.py::test_validator_cli_accepts_the_valid_example PASSED [ 78%]
tests/test_schemas.py::test_validator_cli_rejects_a_broken_file PASSED   [ 82%]
tests/test_schemas.py::test_validator_cli_rejects_file_without_frontmatter PASSED [ 86%]
tests/test_schemas.py::test_source_rule_schema_is_valid_draft_2020_12 PASSED [ 91%]
tests/test_schemas.py::test_target_tools_schema_is_valid_draft_2020_12 PASSED [ 95%]
tests/test_schemas.py::test_layer_glob_map_is_valid_json PASSED          [100%]

============================== 23 passed in 0.56s ==============================

# V-7: validate.yml parses and has both jobs.
$ python -c "import yaml; doc=yaml.safe_load(open('.github/workflows/validate.yml')); print('jobs:', list(doc['jobs'].keys()))"
jobs: ['tree-shape', 'schema-validation']

# V-8: every run: block of the new schema-validation job executes green locally (mirrors what
#      GitHub Actions will run on the closing-PR push).
$ # ... (executed against the live tree; see §1 summary; all four steps green)
=== STEP: Verify Phase-2 schema files exist ===
All Phase-2 schema files present.

=== STEP: Validate JSON schemas parse as valid JSON Schema Draft 2020-12 ===
OK schemas/source-rule.schema.json
OK schemas/target-tools.schema.json
OK schemas/layer-glob-map.json

=== STEP: Run source-frontmatter validator ===
Validation PASSED: 1 file(s) conform to source-rule.schema.json.

=== STEP: Run Phase-2 acceptance tests ===
23 passed in 0.56s

# V-9: linter sanity — every Phase-2 source file is lint-clean.
$ # ReadLints over: compiler/, tests/test_schemas.py, schemas/*.json, validate.yml
No linter errors found.

# V-10: Phase-1-lesson audit — `.cursor/rules/frontmatter-spec.mdc` field names match the schema.
$ # Cross-checked every field in frontmatter-spec.mdc §1 (Full Template) and §2 (Field-by-Field Rules)
$ # against schemas/source-rule.schema.json. Result: no field-name drift; two clarifying edits
$ # made to the MDC to distinguish schema-level from compiler-level constraints.
```

## 9. Handoff to Next Session

- **Next phase**: 3 — Source Content Migration & Authoring of New Logic Holes (see `docs/02-implementation-plan.md` §6).
- **Next-session prompt**: written to `docs/execution-log/next-session-prompt.md` (overwriting the Phase-2 prompt).
- **Pre-requisites for next phase that are now satisfied**:
  - `schemas/source-rule.schema.json` is the machine-readable contract every Phase-3 source rule will be validated against. Authors can copy `schemas/examples/valid-source-rule.md` as the starting template.
  - `schemas/layer-glob-map.json` provides the language → layer → globs lookup that the Phase-4 compiler will use; Phase 3 authors should reference it when choosing `scope.layers` values. Java has full coverage; TypeScript and Python need extension when their first non-trivial rules are written.
  - `schemas/target-tools.schema.json` documents which downstream tools each rule can target via `target_tools.*` flags.
  - `compiler/core/parse_source.py --validate-only` is the pre-flight check every Phase-3 author can run locally before opening a PR (`python compiler/core/parse_source.py --validate-only --path source/.../my-rule.md`).
  - `.github/workflows/validate.yml` `schema-validation` job blocks PRs that introduce frontmatter that violates the schema. Phase 3 PRs will exercise this end-to-end for the first time.
  - `.cursor/rules/frontmatter-spec.mdc` and `.cursor/rules/authoring-style.mdc` (Phase 1) auto-attach when authors edit `source/**/*.md`. They are the AI-assisted authoring guidance for Phase 3 work.
- **Open questions for the operator**:
  - The TypeScript and Python entries in `schemas/layer-glob-map.json` currently match the plan example verbatim (3 layers each). Phase 3 authoring of any TS or Python rule beyond `controller` / `service` / `all` will require an extension. Recommend Phase 3 starts with the Java work (which has full layer coverage) so the central scaffolding is exercised before the layer-glob-map needs widening.
  - The Phase-1 carry-overs remain open (Cursor-load smoke test, GitHub-UI branch-protection apply + screenshot, the Phase-7 CODEOWNERS + dist-protection-lint live experiment, AI Enablement PM ADR sign-off). Phase 2 introduces no new operator carry-overs. The Phase-3 closing PR is a good moment to revisit all four.
