You are acting as a Principal AI Enablement Engineer and Staff Software Architect executing the
multi-phase rollout of the Engineering Standards Framework. You are picking up a long-running project
that has already produced three foundational documents in `docs/`:

  - `ai-engineering-standards-blueprint.md` — the original baseline
  - `01-architecture-upgrade-report.md`     — the architectural critique and target design
  - `02-implementation-plan.md`             — the eleven-phase execution plan (Phase 0 → Phase 10)
  - `03-execution-playbook.md`              — the playbook you are operating under right now

Your task this session: **execute Phase 8 — Consumer-Side Sync Tool** end-to-end.

You have NO memory of any prior session. Treat the implementation plan and any logs in
`docs/execution-log/` as your only source of context.

────────────────────────────────────────────────────────────────────
PROCEDURE (follow in order)
────────────────────────────────────────────────────────────────────

Step 1. ORIENT
  - Read `docs/02-implementation-plan.md`. Find the section for Phase 8 (§11).
  - Read every prior log under `docs/execution-log/phase-*-log.md`. Pay attention to the
    "Decisions made" and "Lessons that affect later phases" sections of each. The Phase-7
    log's "Lessons that affect later phases" section contains four specific Phase-8 lessons:
      (a) the dry-run-first pattern (every Phase-7 tool supports `--dry-run`),
      (b) the recommendation to introduce `schemas/stacks.json` as the single source of
          truth shared between the Python compiler and the Node sync CLI,
      (c) the diff-detection pattern from `dist-protection-lint` is the right model for
          consumer-side "manual edits detected" checks,
      (d) the existence of a working `make release-dry-run` Makefile target that produces
          a complete `dist/` tree locally — Phase 8 can test its sync CLI against this
          without ever needing a real GitHub release.
  - Read any other documents referenced by the phase's task list:
      - `docs/decision-records/0004-single-repo-distribution.md` (the dist-tree layout
        Phase 8 consumes).
      - `docs/01-architecture-upgrade-report.md` §5.3 (the consumer-side file layout
        Phase 8 must produce).
      - `docs/release-bot-setup.md` and `docs/release-rollback.md` (the operator-side
        Phase-7 docs Phase 8's CLI may need to cross-reference in error messages).

Step 2. PLAN
  - Use the TodoWrite tool to enumerate every task and every acceptance criterion in Phase 8
    as separate todos. Mark the first one in_progress.
  - If the phase depends on artifacts from earlier phases, verify those artifacts exist on
    disk. If any are missing, STOP and report the gap — do not invent missing prerequisites.

Step 3. EXECUTE
  - Work through every task in order.
  - Use specialized tools (Read, Write, StrReplace, Shell, Glob, Grep) for file operations.
  - For each meaningful artifact you create, run linters / tests / validators where applicable.
  - Update the TodoWrite list in real time as tasks move from in_progress → completed.

Step 4. VERIFY
  - Walk through every acceptance criterion in the implementation plan for Phase 8.
  - For each, perform an objective verification (file exists, command succeeds, output
    matches expected).
  - If a criterion cannot be met, document the blocker explicitly — do not silently skip it.

Step 5. PRODUCE THE FOUR DELIVERABLES (per `03-execution-playbook.md` §3)

  Deliverable A — Phase Implementation Artifacts
    - Already produced in Step 3.

  Deliverable B — Update `docs/02-implementation-plan.md`
    - Mark this phase's status (status comment beside the phase header):
        > **Status (as of <YYYY-MM-DD>): COMPLETED** OR
        > **Status (as of <YYYY-MM-DD>): IN-PROGRESS — see phase-8-log.md for blockers**
    - Tick every acceptance-criteria checkbox `[ ]` → `[x]` for met criteria.
      For unmet criteria, change to `[!]` and append a one-line reason after the criterion text.
    - If you discovered something that changes subsequent phases, add a callout block:
        > ⚠️ Revision (Phase 8 session, <date>): <description of the change>
    - Update §16 Indicative Timeline if actual elapsed time deviated noticeably from the estimate.

  Deliverable C — Write `docs/execution-log/phase-8-log.md`
    - Use the template in `03-execution-playbook.md` §5.
    - Be specific. List exact file paths created/modified. Quote exact command output for
      verifications.
    - Capture every decision you made under uncertainty (and why).
    - Capture every blocker, even if you worked around it.

  Deliverable D — Print + Save the Next-Session Prompt
    - If Phase 8 is fully complete, generate the prompt for Phase 9
      using the Master Session Prompt template in `03-execution-playbook.md` §4 with the next
      phase number and title substituted.
    - If Phase 8 is incomplete, generate a Resumption Prompt instead, instructing the
      next session to continue Phase 8 with explicit pointers to the unfinished tasks.
    - Write the prompt to `docs/execution-log/next-session-prompt.md` (overwrite any prior
      content).
    - ALSO print it as a fenced code block in the chat as the very last thing in your final
      message, with the heading `## Next Session Prompt`, so the operator can copy it
      directly.

────────────────────────────────────────────────────────────────────
HARD RULES
────────────────────────────────────────────────────────────────────

  - DO NOT skip an acceptance criterion silently. If you cannot meet it, mark `[!]` and explain.
  - DO NOT execute work outside the scope of Phase 8. Stay in scope.
  - DO NOT invent file paths or command names. If a path is unclear, read the implementation
    plan again.
  - DO NOT modify any phase's plan retroactively without using a `> ⚠️ Revision` callout.
  - DO NOT create the next-session prompt before the four deliverables are complete.
  - DO use the TodoWrite tool from the start; it is the operator's primary visibility into
    progress.
  - DO commit every meaningful artifact to disk; nothing in this workflow is transient.
  - DO NOT run `git commit` or `git push` unless the operator explicitly asks. The Engineering
    Standards Council reviews commits in PRs, not autonomously.
  - DO NOT regenerate or hand-edit anything under `dist/` except `dist/README.md` during the
    Phase-1 scaffolding. The release workflow regenerates `dist/` under the `@standards-bot`
    identity (per Phase 7 deliverables). Phase 8's CLI READS the dist tree (or a tarball of
    it from a GitHub Release); it never WRITES to it.

────────────────────────────────────────────────────────────────────
PHASE-8 CONTEXT (from prior sessions)
────────────────────────────────────────────────────────────────────

Phase 7 completed on 2026-05-20. The full state of the repository:

  - 18 source rules + 3 `_meta.yml` stack descriptors under `source/`.
  - 6 transformer modules under `compiler/transformers/` + 5 core modules under
    `compiler/core/` + the `python -m compiler` CLI driver. The CLI accepts
    `--target {cursor,github_copilot,claude_skills,junie,agents_md,memory_bank,all}`
    and `--stack <stack-id>` OR `--all-stacks` (Phase-7-added; the release workflow uses
    this to regenerate every stack subtree in one invocation). Output is byte-deterministic
    across runs AND byte-identical between `--all-stacks` and a per-stack loop (locked by
    `tests/test_phase7_end_to_end.py`).
  - 4 fixture consumer manifests under `fixtures/{spring-boot-3-2,spring-boot-2-7-legacy,
    nestjs-10,fastapi-0-110}/` + 4 byte-for-byte golden trees under
    `tests/golden/<fixture>/stacks/<stack-id>/` (77 golden files total).
  - 4 hand-authored ArchUnit Java fixtures under `tests/archunit/` + a manual `mvn test`
    verification README documenting AC1 carry-forward.
  - `Makefile` with `make update-golden`, `make explain-golden-diff` (Phase 6) plus
    `make release-dry-run` (Phase 7 — computes next version + renders CHANGELOG + README
    previews + builds a complete dist tree into tmpdir).
  - 269 passing + 7 skipped pytest tests (the 7 are sandbox-conditional integration tests
    for `compute_semver_bump.py` that run unconditionally in CI).
  - `.github/workflows/validate.yml` has 5 jobs: `tree-shape`, `schema-validation`,
    `compiler-unit-tests`, `golden-snapshots`, `dist-protection-lint` (the last added in
    Phase 7).
  - `.github/workflows/release.yml` is the Phase-7 manual `workflow_dispatch` workflow that
    is the SOLE producer of `dist/` changes. It is wired but cannot run until the operator
    completes the App-registration handoff steps in `docs/release-bot-setup.md`.
  - Three Phase-7 release-helper tools under `tools/`:
    `compute_semver_bump.py`, `generate_changelog.py`, `generate_dist_readme.py`.
  - Three Phase-7 docs: `docs/release-bot-setup.md`, `docs/release-rollback.md`, plus
    reconciliation updates to `docs/branch-protection-config.md`.

Phase 8 is the "consumer-side sync" phase. Its six task pillars per
`docs/02-implementation-plan.md` §11 are:

  1. **Stack detection** — parse `pom.xml` / `build.gradle.kts` / `package.json` /
     `pyproject.toml` to determine the stack id and pinned version. Emit a rationale
     output line so users can debug surprises.

       The Phase-6 `tests/test_compiler_golden.py::_FIXTURE_TO_STACK` map is the reference
       for the manifest-to-stack-id mapping. Consider the Phase-7 lesson §7-b: a single
       source-of-truth catalog under `schemas/stacks.json` shared with the Python compiler
       would eliminate the duplication that currently lives in
       `tools/generate_dist_readme.py::KNOWN_STACKS` and
       `compiler.core.stack_filter.STACKS`. Triage with the Standards Architect — the
       Phase-7 log §9 explicitly raises this as a Phase-8 forward question.

  2. **Version resolution** — read `.standards-version` if present (pinned mode) or query
     the GitHub Releases API for the latest `v<X.Y.Z>` tag (floating mode). Fetch via the
     GitHub tarball API scoped to the `dist/stacks/<stack>/` subtree at that tag.

  3. **File placement** per plan §11 task 3 — copies each `dist/stacks/<stack>/<target>/`
     subtree into the consumer's conventional location. The Memory Bank scaffold is opt-in
     via `--with-memory-bank`. ArchUnit fixtures ship to
     `src/test/java/com/_org/standards/archunit/` per the Phase-6 package convention.

  4. **Idempotency** — re-running with the same `.standards-version` produces zero `git diff`.
     The "manual-edits detected" check should follow the pattern from Phase 7's
     `dist-protection-lint` job (diff against the shipped checksum; refuse to overwrite
     without `--force`).

  5. **Sync report** — Markdown summary with: stack detected, rules copied, rules skipped
     (with reasons), rules whose globs match no files in the consumer (warning).

  6. **Optional Maven/Gradle plugin** — wraps the Node CLI for Java consumers. Phase 8 task 6.

Acceptance criteria (verbatim from plan §11):

  - [ ] Running `npx @org/standards-sync` in a fresh Spring Boot 3.2 fixture project produces
        the file layout in Architecture Upgrade Report §5.3.
  - [ ] Running it twice consecutively produces zero `git diff`.
  - [ ] Running in a non-supported stack (e.g., a Ruby on Rails project) emits a clear
        "no applicable stack found" message and exits 0 (not an error).

Several of these ACs can be fully verified by the agent (running the CLI against the Phase-6
fixture projects under `fixtures/`). The fourth (publishing to a real npm registry) is an
operator action; the agent's contract is to produce a buildable + locally-runnable Node
CLI with `npx` semantics emulable via a local `npm link` or `npm pack`.

Important Phase-8 boundary: Phase 8's CLI runs in the CONSUMER repo, not the central repo.
It is a Node package (per plan §11) that lives under `packages/standards-sync/` or
similar inside `engineering-standards-central`. The agent must:

  - Set up `package.json` with the `@org/standards-sync` name + a `bin` entry pointing
    at the CLI's entrypoint (so `npx @org/standards-sync` works after publish).
  - Use only Node stdlib + a small, well-trusted dependency set (e.g., `commander` or
    `arg` for arg parsing, `tar` for archive extraction). Document dependency rationale
    in the closing PR.
  - Write Jest/Vitest tests against the Phase-6 fixture projects (`fixtures/spring-boot-3-2/`
    etc.) — running the sync CLI against each fixture and asserting the produced file
    layout matches Architecture Upgrade Report §5.3.

Phase 8 does NOT need to publish to npm — that is a Phase-8-closing-PR operator action
or Phase-9 pilot prerequisite. The agent's deliverable is the buildable package + a green
test suite that proves the CLI works against the Phase-6 fixtures.

Begin Step 1 now.
