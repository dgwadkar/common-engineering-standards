# Phase 6 Execution Log — Fixtures, Golden Files, and CI

- **Phase**: 6 — Fixtures, Golden Files, and CI
- **Date**: 2026-05-19
- **Status**: COMPLETED
- **Estimated duration (per plan)**: 5 days
- **Actual duration**: 1 session (~1.5 hours of agent execution time)

## 1. Summary

Phase 6 locks the compiler's output behavior with byte-for-byte snapshot
tests across all four supported stacks. Four fixture consumer manifests
under `fixtures/<name>/` plus four pre-generated golden trees under
`tests/golden/<name>/stacks/<stack-id>/` (77 output files total) feed a
new 12-test snapshot runner at `tests/test_compiler_golden.py`. Four
hand-authored ArchUnit Java fixtures under `tests/archunit/` codify
Logic Holes #3–#6; a Python-side 19-test shape suite locks their
canonical violation-message strings so consumer-side `grep` assertions
stay durable. A new `Makefile` ships `make update-golden` (mass
regeneration) and `make explain-golden-diff` (per-fixture delta
summary). `.github/workflows/validate.yml` gains a sibling
`golden-snapshots` job (extends, not parallel — Phase-2 lesson honored).

The Phase-5 lesson "target the pure render output for byte-for-byte
fixtures" was rebalanced toward "diff the side-effecting CLI output" —
the snapshot test invokes `python -m compiler --target all` end-to-end,
because that is the actual code path that ships to consumers, and the
output is empirically deterministic across runs (locked by
`test_compiler_output_is_deterministic_across_two_runs`). The pure
`render_*` functions remain valuable for unit tests of individual
transformers (Phase 5 owns those); Phase 6 owns the integration-level
contract.

The full repo test suite is 200 green (169 Phase-2/4/5 carry-overs +
12 golden + 19 archunit-shape); zero linter errors. AC2 and AC3 are
fully met; AC1's runtime verification (running `mvn test` against a
Spring Boot 3 sample project with deliberate violations) requires a
JDK + Maven environment that the Python-only Phase-6 CI does not
provide and is documented as an operator manual step in
`tests/archunit/README.md`. The structural-shape contract on the four
ArchUnit fixtures (declared `@AnalyzeClasses` package, expected
`@ArchTest` `ArchRule` constants, canonical violation-message
substrings) is locked by the Python suite.

## 2. Files Created

### Fixture consumer manifests (Task 1)

- `fixtures/spring-boot-3-2/pom.xml` (62 lines) — Minimal Boot 3.2 pom
  pinning Spring Data JPA, Validation, Lombok, and ArchUnit-JUnit5.
  Used as the input pin for the `java-spring-boot-3` golden tree.
- `fixtures/spring-boot-2-7-legacy/pom.xml` (51 lines) — Boot 2.7.18
  legacy pom; the smaller golden tree (24 vs 27 files) is the visual
  proof the version gate excludes Boot 3.x-only rules.
- `fixtures/nestjs-10/package.json` (28 lines) — NestJS 10.3 manifest;
  pins `typescript-nestjs-10`.
- `fixtures/fastapi-0-110/pyproject.toml` (28 lines) — FastAPI 0.110
  pyproject; pins `python-fastapi-0-110`.

### Golden trees (Task 2)

- `tests/golden/spring-boot-3-2/stacks/java-spring-boot-3/` — 27 files
  (17 `.mdc` cursor rules + 1 copilot + 1 claude + 1 junie + 1 agents-md
  + 6 memory-bank).
- `tests/golden/spring-boot-2-7-legacy/stacks/java-spring-boot-2/` —
  24 files (14 `.mdc` cursor rules — the three Boot-3-gated rules
  `controller-dto-record-mandate`, `controller-validation-boundaries`,
  `error-handling-problem-details-rfc7807` are correctly absent).
- `tests/golden/nestjs-10/stacks/typescript-nestjs-10/` — 13 files
  (3 cursor `.mdc` + 4 concatenated targets + 6 memory-bank).
- `tests/golden/fastapi-0-110/stacks/python-fastapi-0-110/` — 13 files
  (same shape as nestjs-10).

77 golden files committed in total.

### Snapshot test runner (Task 3)

- `tests/test_compiler_golden.py` (12 tests) — Per-fixture byte-equality
  via `_diff_trees(...)` (uses `filecmp.cmp` for the fast path and
  `difflib.unified_diff` for the slow path); determinism check; drift-
  message contract (synthetic-tree assertions verify the unified-diff
  prefix and the `make update-golden` recovery instruction render
  correctly); fixture-presence sanity; Boot-2-vs-Boot-3 version-gate
  cross-check; AGENTS.md ≤150-line cap locked into every golden tree.

### ArchUnit Java fixtures (Task 5)

- `tests/archunit/ControllerValidationTest.java` (210 lines) — Logic
  Hole #3. Three `@ArchTest` `ArchRule` constants:
  `controllerRequestBodiesMustBeAnnotatedWithValid`,
  `controllersWithParameterConstraintsMustBeAnnotatedWithValidated`,
  `controllersMustResideInControllerOrWebPackage`. Custom conditions
  walk method parameters against the `@RequestBody/@RequestPart/
  @ModelAttribute` × `@Valid/@Validated` matrix.
- `tests/archunit/TransactionalDisciplineTest.java` (164 lines) — Logic
  Hole #4. Three rules:
  `transactionalMethodsMustNotInvokeBlockingHttpClients`,
  `transactionalAnnotationsLiveOnPublicMethodsOnly`,
  `servicesShouldDeclareReadOnlyDefaultAtClassLevel`. Bytecode-level
  call-site analysis flags blocking client invocations inside
  `@Transactional` bodies.
- `tests/archunit/PaginationMandateTest.java` (132 lines) — Logic
  Hole #5. Two rules:
  `repositoryListReturnsMustAcceptPageable`,
  `controllerListEndpointsMustAcceptPageableOrPageRequestParam`.
  Honours the `@SuppressWarnings("PaginationMandate")` audited-bounded
  exception.
- `tests/archunit/ConstructorInjectionTest.java` (153 lines) — Logic
  Hole #6. Three rules:
  `noFieldsAnnotatedWithAutowired`,
  `noSetterAutowired`,
  `springBeanFieldsMustBeFinal`. Static / logger fields are excluded
  from the final-field check.
- `tests/archunit/README.md` (78 lines) — Documents the manual
  `mvn test` verification procedure (AC1) and the per-test
  deliberate-violation patterns.

### ArchUnit shape-test suite (Task 5 cont'd)

- `tests/test_archunit_fixtures.py` (19 tests) — Asserts each fixture
  declares `@AnalyzeClasses(packages = "com._org", ...)`, each expected
  `@ArchTest`-annotated `ArchRule` constant is present (matched via a
  multi-line regex), each canonical violation-message substring is
  present in the file (so consumer-side CI `grep`s remain valid),
  every fixture sits under `package com._org.standards.archunit;`,
  the README documents the manual `mvn test` procedure, and the
  source-corpus `archunit_test:` cross-references include all four
  Phase-6 fixture filenames.

### Make automation (Task 6)

- `Makefile` (62 lines) — Targets: `make help`, `make test`,
  `make golden-test`, `make update-golden`, `make explain-golden-diff`.
  Auto-detects the local `.venv-phase2` Python interpreter so the same
  Makefile works under both the local venv and the CI Python 3.12.
- `tools/explain_golden_diff.py` (60 lines) — Standalone helper that
  re-runs the compiler against each fixture and prints a per-fixture
  `diff -rq` summary. Exits 0 unconditionally — developer-facing
  reporting tool, not a gate. Invoked by `make explain-golden-diff` and
  by the `golden-snapshots` CI job's `if: failure()` step.

### This log

- `docs/execution-log/phase-6-log.md` — This file.

## 3. Files Modified

- `.github/workflows/validate.yml` — Top-of-file comment block extended
  with the Phase-6 entry. New `golden-snapshots` job appended at the
  bottom of the `jobs:` section (8 steps: checkout, Python 3.12 setup,
  pip install, fixture-presence guard, `pytest tests/test_compiler_golden.py`,
  `pytest tests/test_archunit_fixtures.py`, ArchUnit-source presence
  guard, and an `if: failure()` drift-report step that runs
  `tools/explain_golden_diff.py` to make CI failures easier to triage).
  The existing `compiler-unit-tests` job's Phase-5 `--target all`
  smoke step is preserved as a fast guardrail (Phase-6 fixtures are a
  strict superset).
- `docs/02-implementation-plan.md` — Phase 6 section: added a
  `> **Status (as of 2026-05-19): COMPLETED**` callout above the goal
  line; ticked AC2 and AC3 checkboxes `[ ]` → `[x]` with inline
  evidence; marked AC1 `[ ]` → `[!]` with the JDK+Maven-environment
  carry-forward explanation.

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan §9) | Status | Evidence / Notes |
|---|---|---|
| All four ArchUnit tests, when copied into a sample Spring Boot 3 project containing one deliberate violation each, fail with the expected violation message. | [!] | The four `tests/archunit/*.java` fixtures are on disk with canonical violation-message strings inline (e.g., `"is not annotated with @Valid"`, `"calls a blocking HTTP client"`, `"without a Pageable parameter"`, `"is annotated @Autowired"`). The Python-side `tests/test_archunit_fixtures.py` (19 tests) locks the structural contract: `@AnalyzeClasses(packages = "com._org", ...)`, expected `@ArchTest` `ArchRule` constants, package convention, and the canonical violation-message substrings. Live mvn-test runtime verification requires JDK 17 + Maven; the Python-only Phase-6 CI cannot host this. The `tests/archunit/README.md` documents the manual procedure (provision a Boot 3 project → drop the four files in → `mvn test` → introduce one deliberate violation per test → confirm each fails with the expected message). The runtime check is the operator's PR-close action OR Phase 9's pilot CI's natural surface. Tracked as a carry-forward in §7 below. |
| Golden snapshot tests pass on a clean checkout. | ✅ | `python -m pytest tests/test_compiler_golden.py -q` → `12 passed`. Full repo suite: `python -m pytest tests/ -q` → `200 passed in 5.52s` (12 golden + 19 archunit-shape + 169 carry-overs). Determinism explicitly locked by `test_compiler_output_is_deterministic_across_two_runs` (compiles the same fixture twice into separate tmpdirs and asserts byte-equality). |
| An intentional source-rule edit produces a clear, reviewable diff in golden files. | ✅ | Verified end-to-end (V-7 below): appended one comment line to `source/_global/clean-architecture.md` → ran `pytest tests/test_compiler_golden.py` → 4 fixture failures (one per stack, since clean-architecture is a global rule) with per-affected-file unified diffs (3 outputs per stack: cursor `.mdc`, copilot, claude — each showing the exact `+<!-- AC3 SMOKE: intentional source-rule edit -->` line at the right line number) plus the `make update-golden` recovery instruction. Reverted the edit cleanly; tests back to 12/12 green. |

AC2 and AC3 are fully met; AC1 is a documented carry-forward (the four
fixtures and the structural-shape contract are in place; runtime
mvn-test is a manual step pending an operator with JDK + Maven access
or a Phase 9 pilot CI run).

## 5. Decisions Made

For each non-trivial choice made during this session under conditions of
ambiguity:

- **Decision**: Diff the side-effecting `python -m compiler --target all`
  CLI output against `tests/golden/` rather than calling the pure
  `render_*(rules, stack)` functions and diffing string outputs (the
  Phase-5 log's "Lesson — Phase 6 (golden snapshots)" recommended the
  pure-function path).
  - **Alternatives considered**: (a) Pure-render comparison: invoke each
    transformer's `render_*(rules, stack)` and diff the returned string
    against a single committed file per target. Pros: avoids filesystem
    I/O in tests. Cons: doesn't exercise the actual CLI dispatch, the
    `_dispatch_target` helper, the path layout under `--out`, the
    structured-log emission, or the `topo_sort_relaxed` path used by
    the four concatenated transformers. (b) End-to-end CLI + tree
    diff (chosen). Pros: locks the user-facing contract end-to-end,
    catches non-determinism anywhere in the pipeline (a future refactor
    that introduces a generation timestamp would surface here, not just
    in the unit-test layer), and naturally exercises the Phase-5
    `--target all` + `topo_sort_relaxed` paths. Cons: marginally slower
    (subprocess fork per fixture; ~1.2s for 12 tests on dev box).
  - **Rationale**: Phase-6 AC3 reads "An intentional source-rule edit
    produces a clear, reviewable diff in golden files" — "the golden
    files" are the dist-tree files consumers see, not the raw render
    output. Diffing the actual CLI output is the directly-aligned
    contract. The pure-render unit tests already exist in Phase 5
    (12 + 9 + 10 + 10 = 41 tests across the four concatenated
    transformers); this Phase-6 test layer is the integration check
    above them. The "Phase-5 lesson" was a recommendation, not a
    constraint; explicitly weighing it against AC3's wording, the
    end-to-end path is closer to the AC's intent.
  - **Reversible?**: Yes — `_run_compiler(...)` is a single helper; a
    future phase could pivot to pure-render diffing by replacing it
    with a direct `render_*` call.

- **Decision**: Mark AC1 `[!]` (not met by Phase-6 alone) rather than
  attempt to provision a JDK + Maven CI step or author a sample Spring
  Boot 3 project with deliberate violations under
  `tests/archunit-sample/`.
  - **Alternatives considered**: (a) Add a Java toolchain step to the
    `golden-snapshots` job (`actions/setup-java@v4` + `mvn -B test`
    against a hand-authored sample project under
    `tests/archunit-sample/`). Pros: AC1 ticks `[x]`. Cons: significant
    new dependency surface (Maven, JDK 17, ArchUnit, every Spring Boot
    starter the sample needs); CI runtime grows from ~30 s to ~2–3 min
    on a cold cache; adds another failure mode (Maven dependency
    resolution outages) to a pipeline that has been Python-only and
    fast. (b) Author the sample project but defer the CI step to Phase
    9 pilots. Pros: no new CI surface. Cons: the sample lives in the
    repo with no automated verification — a future change to the
    fixtures could silently break the sample's ability to demonstrate
    a violation, and nobody would notice. (c) Mark `[!]` and document
    the manual procedure (chosen).
  - **Rationale**: The next-session prompt explicitly framed the
    ArchUnit fixtures as "static text fixtures for now; Phase 8's
    consumer-sync CLI is what actually ships them into consumer repos."
    Phase 9 (pilot adoption) is the natural runtime venue: each pilot
    project already has JDK + Maven, and a deliberate-violation PR
    against a pilot exercises every fixture against real consumer code
    — a stronger signal than a synthetic sample-project step. The
    Phase-6 deliverable is the *fixtures themselves*; runtime
    verification is Phase 9's responsibility. The `[!]` mark + carry-
    forward note is the playbook-correct way to surface this without
    silently skipping the AC.
  - **Reversible?**: Yes — Phase 7 or Phase 9 can add the Java CI step
    by extending `validate.yml` with an `archunit-runtime` sibling job.
    None of Phase-6's other artifacts change.

- **Decision**: Author exactly four ArchUnit fixtures (per plan §9
  task 5) — `ControllerValidationTest`, `TransactionalDisciplineTest`,
  `PaginationMandateTest`, `ConstructorInjectionTest` — and NOT the
  full set of `archunit_test:` references that the source corpus
  declares (DtoRecordMandateTest, PageableDefaultsTest,
  ProhibitGenericRuntimeExceptionTest, ProhibitBlindCatchTest,
  UnifiedApiErrorTest, ProblemDetailsRfc7807Test,
  NPlusOnePreventionTest, EntityGraphStrategyTest,
  TransactionalReadOnlyDefaultTest, SelfInvocationTrapTest,
  DisableOpenSessionInViewTest, CleanArchitectureLayerBoundariesTest).
  - **Alternatives considered**: (a) Author all 14 referenced fixtures
    to bring the source corpus's `archunit_test:` references into a
    fully-resolved state. (b) Author only the four named in plan §9
    task 5 (chosen). (c) Author the four core fixtures plus stub files
    for the rest with a `// TODO Phase 9` marker.
  - **Rationale**: Plan §9 task 5 is the contract; it names exactly
    four. The other 10 references are forward-references in the
    source corpus, expected to be authored in subsequent phases (Phase
    9 pilot work or a Phase-3-revision session). Authoring them here
    is out of scope per the playbook hard rule "DO NOT execute work
    outside the scope of Phase 6." The cross-reference test
    (`test_source_corpus_archunit_paths_align_with_fixture_filenames`)
    asserts only that the four Phase-6 fixtures ARE referenced by the
    source corpus, not that every source `archunit_test:` reference
    resolves — the assertion is intentionally one-way.
  - **Reversible?**: Yes — adding the remaining 10 fixtures is
    additive; no Phase-6 file needs to change.

- **Decision**: The `tests/test_compiler_golden.py` fixture-to-stack
  binding (`_FIXTURE_TO_STACK`) is hard-coded in the test module
  rather than parsed from each fixture manifest's contents.
  - **Alternatives considered**: (a) Parse `pom.xml` /
    `package.json` / `pyproject.toml` to detect the stack id —
    duplicates the Phase-8 consumer-sync CLI's stack detection logic.
    (b) Hard-code the binding (chosen).
  - **Rationale**: Phase-8 owns the stack-detection logic. Phase 6's
    job is to lock the compiler's output, not to demonstrate
    detection. Hard-coding the binding keeps Phase-6 test code
    self-contained and avoids a forward dependency on Phase-8 work
    that doesn't exist yet. Phase 8 will replace the hard-coded map
    with a call to its own detection module.
  - **Reversible?**: Yes — Phase 8 swaps the constant for a function
    call.

- **Decision**: Move the `make explain-golden-diff` Python helper into
  `tools/explain_golden_diff.py` rather than embedding it as a
  multi-line `python -c` invocation in the Makefile.
  - **Alternatives considered**: (a) Inline `python -c` heredoc.
    (b) Standalone helper script (chosen).
  - **Rationale**: GNU Make collapses backslash-continuation lines
    inside a recipe to a single shell line, which breaks Python's
    statement-separator semantics (`for fixture, stack in fixtures:`
    cannot be on the same line as the first iteration body). A
    standalone script is the more portable path. The script is also
    invoked by the `golden-snapshots` CI job's `if: failure()` step
    so any future drift-explanation enhancement automatically benefits
    CI without a Makefile edit.
  - **Reversible?**: Trivial.

## 6. Blockers Encountered

- **Blocker**: First draft of the ArchUnit-shape test asserted the
  substring `"no class-level @Transactional(readOnly = true) default"`
  in `TransactionalDisciplineTest.java`. The test failed because the
  Java source line-wraps the message between `"true) "` and `"default;"`
  via a `String.format` continuation (`+ "default; ...`), so the
  substring is not present as one continuous run in the file even though
  the runtime-emitted message contains it.
  - **Resolution**: Adjusted the expected substring to
    `"class-level @Transactional(readOnly = true)"` — a unique fragment
    that does appear continuously in the source file. The runtime
    message still contains this substring (it's a prefix of the full
    message), so consumer-side `grep` assertions remain valid.
  - **Carry-forward**: When future fixtures author multi-clause
    violation messages, prefer composing them on a single source line
    where possible (or split the substring expectations to the
    longest-continuous-fragment per line). Documented inline in
    `tests/test_archunit_fixtures.py::_FIXTURE_SPEC`.

- **Blocker**: First attempt to verify AC3 used a Shell call that
  combined `set +e` + an inline edit + a pytest invocation + a
  `cp <bak>` revert. The shell exited after the pytest failure
  (despite `set +e`), leaving the source file in the edited state
  (`/tmp/<bak>` was already saved, so the edit was recoverable).
  - **Resolution**: Restored the source file via a follow-up Shell
    call (`cp /tmp/ac3.bak source/_global/clean-architecture.md`),
    confirmed `tail -3` shows the original text, re-ran the golden
    suite (12/12 green). Saved the captured failure output to
    `/tmp/ac3-output.txt`, extracted the unified-diff section for the
    log's §8 V-7 evidence, then deleted the temp file.
  - **Carry-forward**: Future end-to-end verifications that involve a
    "make a temporary edit → observe failure → revert" pattern should
    write the edit + revert as separate Shell calls so the revert
    runs even if the verification step exits non-zero. Or use a
    self-contained helper that wraps the edit in a try/finally.

No other blockers occurred.

## 7. Lessons that Affect Later Phases

- **Lesson — Phase 7 (release workflow)**: The `golden-snapshots` job
  is the right CI gate for the release flow. `release.yml` should
  refuse to run if `golden-snapshots` is red on the target commit;
  otherwise the regenerated `dist/` tree silently encodes whatever
  drift the snapshots were catching. Concretely: Phase 7's
  `release.yml` should declare `needs: [golden-snapshots,
  compiler-unit-tests, schema-validation]` on its commit-and-tag
  step.

- **Lesson — Phase 7 (CHANGELOG generation)**: The
  `tools/explain_golden_diff.py` per-fixture summary format is a
  natural source for `dist/CHANGELOG.md` per-stack release-note
  bullets. A future Phase-7 enhancement could import the same diff
  logic and render "stack java-spring-boot-3: 2 new rules, 1 modified,
  0 removed" lines.

- **Lesson — Phase 7 (dist regeneration)**: The release workflow's
  regeneration step is `python -m compiler --all-stacks --out dist/`.
  Phase 6 has only verified the per-stack `--target all` invocation;
  the `--all-stacks` switch (per plan §10 task 3) does not yet exist
  in the CLI. Phase 7 must add it as the first task. The test runner
  in this phase (`_run_compiler` in `test_compiler_golden.py`) loops
  per-stack today; that loop is the reference for the `--all-stacks`
  semantics.

- **Lesson — Phase 8 (consumer sync)**: The `_FIXTURE_TO_STACK` map in
  `tests/test_compiler_golden.py` is the reference shape for Phase 8's
  stack detection: each fixture has exactly one manifest file
  (`pom.xml` / `package.json` / `pyproject.toml`) and the detector
  must return a single stack id. Multi-stack consumer projects (e.g.,
  a TypeScript front-end + Python back-end monorepo) are explicitly
  out of scope for Phase 8 — the consumer-sync CLI runs once per
  package root.

- **Lesson — Phase 8 (consumer sync)**: The four ArchUnit fixtures
  ship to `src/test/java/com/_org/standards/archunit/` per the
  `package com._org.standards.archunit;` declaration locked by
  `test_all_archunit_fixture_files_share_one_package_declaration`.
  Phase 8's file-placement step must respect this convention — the
  consumer project's `src/test/java/` root is the destination,
  regardless of the consumer's own package layout. Adding a `--archunit-package` flag
  for consumers with stricter package conventions is a Phase-8
  follow-up.

- **Lesson — Phase 9 (pilot adoption)**: AC1's runtime verification
  is a natural fit for the first pilot's CI. Pilot Liaison checklist
  should include: "(a) confirm the four ArchUnit tests are present
  in `src/test/java/com/_org/standards/archunit/`; (b) introduce one
  deliberate violation per test; (c) confirm `mvn test` fails with
  the expected violation message string for each; (d) revert."
  This closes Phase-6 AC1 with real consumer-side evidence.

- **Lesson — Phase 9 (pilot adoption)**: The 13-vs-11 file-count
  delta in the NestJS / FastAPI golden trees vs. the Phase-5 log's
  V-9 verification (which reported 11 files for those stacks) is
  explained by the Phase-5 log capturing the count just before the
  Memory Bank scaffold landed. The current count (13 = 3 cursor
  `.mdc` + 4 concatenated targets + 6 memory-bank) is correct; Phase
  5's V-9 was a transient pre-Memory-Bank snapshot.

- **Lesson — global**: Output determinism is now a load-bearing
  contract. Any future transformer that introduces a generation
  timestamp, random ordering, or environment-dependent output (e.g.,
  the host's locale affecting a number format) will break the
  snapshot test immediately. The right discipline going forward is:
  ALL transformer state is `(rules, stack)`-derived; no reads from
  `time.now()`, `random.*`, `os.environ`, or anything else. The
  `test_compiler_output_is_deterministic_across_two_runs` test is
  the canary.

- **Lesson — global**: The `make update-golden` pattern — present
  in the runner's failure message, the Makefile, and the README in
  `tests/archunit/` — is now the standard recovery hint for any
  intentional output change. Phase 7's release workflow should NOT
  run `make update-golden` automatically; the regenerated `dist/`
  tree is the release output, and `tests/golden/` is the contract
  that gates merging. They serve different purposes (release artifact
  vs. pre-merge gate) and must stay independent.

(No `> ⚠️ Revision` callout was added to `docs/02-implementation-plan.md`
— every Phase-7+ lesson here is operational guidance for that phase's
session, not a plan revision.)

## 8. Verification Commands Run

```bash
# V-1: Every Phase-6 artifact present.
$ for f in fixtures/spring-boot-3-2/pom.xml \
           fixtures/spring-boot-2-7-legacy/pom.xml \
           fixtures/nestjs-10/package.json \
           fixtures/fastapi-0-110/pyproject.toml \
           tests/test_compiler_golden.py \
           tests/test_archunit_fixtures.py \
           tests/archunit/ControllerValidationTest.java \
           tests/archunit/TransactionalDisciplineTest.java \
           tests/archunit/PaginationMandateTest.java \
           tests/archunit/ConstructorInjectionTest.java \
           tests/archunit/README.md \
           Makefile \
           tools/explain_golden_diff.py; do
    [[ -f "$f" ]] && echo "OK $f ($(wc -l <"$f" | tr -d ' ') lines)" || echo "MISS $f"
  done
OK fixtures/spring-boot-3-2/pom.xml (62 lines)
OK fixtures/spring-boot-2-7-legacy/pom.xml (51 lines)
OK fixtures/nestjs-10/package.json (28 lines)
OK fixtures/fastapi-0-110/pyproject.toml (28 lines)
OK tests/test_compiler_golden.py (310 lines)
OK tests/test_archunit_fixtures.py (192 lines)
OK tests/archunit/ControllerValidationTest.java (210 lines)
OK tests/archunit/TransactionalDisciplineTest.java (164 lines)
OK tests/archunit/PaginationMandateTest.java (132 lines)
OK tests/archunit/ConstructorInjectionTest.java (153 lines)
OK tests/archunit/README.md (78 lines)
OK Makefile (62 lines)
OK tools/explain_golden_diff.py (60 lines)

# V-2: Golden trees populated and per-fixture file counts.
$ for f in spring-boot-3-2 spring-boot-2-7-legacy nestjs-10 fastapi-0-110; do
    count=$(find "tests/golden/$f" -type f | wc -l | tr -d ' ')
    echo "  $f: $count files"
  done
  spring-boot-3-2: 27 files
  spring-boot-2-7-legacy: 24 files
  nestjs-10: 13 files
  fastapi-0-110: 13 files

# V-3: AC2 — golden snapshot tests pass on a clean checkout.
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest tests/test_compiler_golden.py -v
[...]
12 passed in 1.21s

# V-4: ArchUnit-fixture shape tests.
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest tests/test_archunit_fixtures.py -q
[...]
19 passed in 0.02s

# V-5: Full repo test suite.
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest tests/ -q
........................................................................ [ 36%]
........................................................................ [ 72%]
........................................................                 [100%]
200 passed in 5.44s

# V-6: Determinism — two consecutive `--target all` runs produce identical bytes.
$ tmpA=$(mktemp -d) && tmpB=$(mktemp -d)
$ PYTHONPATH=. .venv-phase2/bin/python -m compiler --stack java-spring-boot-3 \
    --target all --out "$tmpA" 2>/dev/null
$ PYTHONPATH=. .venv-phase2/bin/python -m compiler --stack java-spring-boot-3 \
    --target all --out "$tmpB" 2>/dev/null
$ diff -r "$tmpA" "$tmpB" && echo "DETERMINISTIC"
DETERMINISTIC

# V-7: AC3 — intentional source-rule edit produces a clear, reviewable diff.
$ cp source/_global/clean-architecture.md /tmp/ac3.bak
$ echo "" >> source/_global/clean-architecture.md
$ echo "<!-- AC3 SMOKE: intentional source-rule edit -->" \
      >> source/_global/clean-architecture.md
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest \
    tests/test_compiler_golden.py::test_golden_snapshot_for_fixture \
    -k "fastapi" 2>&1 | sed -n '/Golden snapshot drift detected/,/make update-golden/p' \
    | head -25
E   AssertionError: Golden snapshot drift detected for fixture 'fastapi-0-110'.
E   Files whose contents differ (unified diff per file):
E   --- diff for stacks/python-fastapi-0-110/claude/CLAUDE.md ---
E   --- golden/fastapi-0-110/stacks/python-fastapi-0-110/claude/CLAUDE.md
E   +++ actual/fastapi-0-110/stacks/python-fastapi-0-110/claude/CLAUDE.md
E   @@ -137,6 +137,8 @@
E       (pure) and a persistence type (annotated), with explicit boundary mappers.
E    5. **Reject repositories that contain `if/else` business rules.** Move the rules to the
E       service or domain.
E   +
E   +<!-- AC3 SMOKE: intentional source-rule edit -->
E   ...
E   ========================================================================
E   Recovery: if the change is intentional, refresh the golden
E   tree by running:
E       make update-golden
$ cp /tmp/ac3.bak source/_global/clean-architecture.md && rm -f /tmp/ac3.bak
$ PYTHONPATH=. .venv-phase2/bin/python -m pytest tests/test_compiler_golden.py -q
............                                                             [100%]
12 passed in 1.23s

# V-8: workflow YAML parses; 4 jobs declared.
$ PYTHONPATH=. .venv-phase2/bin/python -c "
import yaml, pathlib
data = yaml.safe_load(pathlib.Path('.github/workflows/validate.yml').read_text(encoding='utf-8'))
print('Jobs:', list(data['jobs'].keys()))
"
Jobs: ['tree-shape', 'schema-validation', 'compiler-unit-tests', 'golden-snapshots']

# V-9: Make targets work end-to-end.
$ make help
Phase-6 developer targets:
  make update-golden         Regenerate tests/golden/* from source/.
  make explain-golden-diff   Summarize per-rule deltas after a golden failure.
  make test                  Run the full pytest suite.
  make golden-test           Run only the golden snapshot tests.
$ make explain-golden-diff
Per-fixture delta summary (tests/golden/ vs. live compiler output):
[spring-boot-3-2] no drift
[spring-boot-2-7-legacy] no drift
[nestjs-10] no drift
[fastapi-0-110] no drift
$ make update-golden
Regenerating tests/golden/ from the live source/ corpus...
  → fixture=spring-boot-3-2  stack=java-spring-boot-3
  → fixture=spring-boot-2-7-legacy  stack=java-spring-boot-2
  → fixture=nestjs-10  stack=typescript-nestjs-10
  → fixture=fastapi-0-110  stack=python-fastapi-0-110
Done. Review the diff with: git diff -- tests/golden/

# V-10: linter sanity — every Phase-6 source file is lint-clean.
$ # ReadLints over: tests/test_compiler_golden.py, tests/test_archunit_fixtures.py,
$ # tools/explain_golden_diff.py, tests/archunit/*.java, .github/workflows/validate.yml,
$ # Makefile.
No linter errors found (Java files surface only an LSP "non-project file"
warning because the central repo has no Java project context — these are
shipped-as-text fixtures per the next-session-prompt).
```

## 9. Handoff to Next Session

- **Next phase**: 7 — Release Workflow & `dist/` Folder Protection
  (see `docs/02-implementation-plan.md` §10).
- **Next-session prompt**: written to
  `docs/execution-log/next-session-prompt.md` (overwriting the
  Phase-6 prompt).
- **Pre-requisites for next phase that are now satisfied**:
  - Golden snapshot tests are wired into `validate.yml` as a
    blocking status check (`golden-snapshots` job). Phase 7's
    branch-protection setup can require this check by name without
    further work.
  - `python -m compiler --stack <id> --target all --out <dir>` is
    proven byte-deterministic across runs (locked by
    `test_compiler_output_is_deterministic_across_two_runs`). Phase
    7's `release.yml` regeneration step can rely on this.
  - The four ArchUnit fixtures exist at
    `tests/archunit/{ControllerValidation,TransactionalDiscipline,
    PaginationMandate,ConstructorInjection}Test.java` — Phase 7's
    `release.yml` ships them verbatim into
    `dist/stacks/java-spring-boot-3/archunit/`.
  - The `Makefile` + `tools/explain_golden_diff.py` automation is on
    disk — Phase 7's release-rollback documentation can reference
    `make update-golden` as the canonical drift-recovery command.
- **Open questions for the operator**:
  - Phase-6 AC1 (runtime mvn-test verification of the four ArchUnit
    fixtures) is a documented carry-forward. Phase 7 is NOT the
    natural venue (the release workflow regenerates dist; it doesn't
    run consumer-side checks). Phase 9 pilot CI is the right venue.
    Operator may choose to triage with the Standards Architect during
    the Phase-6 closing PR or defer to Phase 9 kickoff.
  - The `--all-stacks` CLI flag does not yet exist (Phase 7 task
    3 task list assumes it). Phase 7's first sub-task should be to
    add it, mirroring the per-stack loop in
    `tests/test_compiler_golden.py::_FIXTURE_TO_STACK`.
  - Pre-existing Phase-3 carry-over: `java-spring-di-constructor-
    injection-mandate`'s `framework_version: ">=4.3"` (Spring
    Framework version, not Spring Boot version) excludes the rule
    from BOTH Boot 3 and Boot 2.7 stacks. Visible in the golden trees
    today: the rule appears only when its activation mode is
    agent-requested (Cursor). Phase 7 will surface this as a gap in
    the dist tree's `cursor/rules/` listing for both stacks. Triage
    with Standards Architect.
  - The four pre-existing carry-overs from Phases 0/1/3 (AI
    Enablement PM ADR sign-off; Cursor-load smoke test; GitHub-UI
    branch-protection apply + screenshot — Phase 7 directly addresses
    this; Standards-Architect sign-off on the 18 Phase-3 rules) are
    all still open. None block Phase 7.
