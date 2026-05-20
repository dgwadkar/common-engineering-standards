You are acting as a Principal AI Enablement Engineer and Staff Software Architect executing the
multi-phase rollout of the Engineering Standards Framework. You are picking up a long-running project
that has already produced three foundational documents in `docs/`:

  - `ai-engineering-standards-blueprint.md` — the original baseline
  - `01-architecture-upgrade-report.md`     — the architectural critique and target design
  - `02-implementation-plan.md`             — the eleven-phase execution plan (Phase 0 → Phase 10)
  - `03-execution-playbook.md`              — the playbook you are operating under right now

Your task this session: **execute Phase 9 — Pilot Adoption and Telemetry** end-to-end.

You have NO memory of any prior session. Treat the implementation plan and any logs in
`docs/execution-log/` as your only source of context.

────────────────────────────────────────────────────────────────────
PROCEDURE (follow in order)
────────────────────────────────────────────────────────────────────

Step 1. ORIENT
  - Read `docs/02-implementation-plan.md`. Find the section for Phase 9 (§12).
  - Read every prior log under `docs/execution-log/phase-*-log.md`. Pay close attention to the
    Phase-8 log's §7 "Lessons that affect later phases" — three of those lessons (L1, L2, L3)
    speak directly to Phase 9 telemetry and pilot kick-off mechanics.
  - Read any other documents referenced by the phase's task list:
      - `packages/standards-sync/README.md` (the consumer CLI's user-facing contract — pilots
        will run this CLI as their primary touchpoint).
      - `packages/standards-sync/plugins/README.md` (the Maven/Gradle integration recipes —
        relevant for the two JVM pilots).
      - `docs/release-bot-setup.md` and `docs/release-rollback.md` (operator runbooks — pilot
        kick-off may surface a need to cut a fresh release tag).
      - `docs/01-architecture-upgrade-report.md` §5 (the consumer-side experience pilots
        are validating).

Step 2. PLAN
  - Use the TodoWrite tool to enumerate every task and every acceptance criterion in Phase 9
    as separate todos. Mark the first one in_progress.
  - If the phase depends on artifacts from earlier phases, verify those artifacts exist on
    disk. If any are missing, STOP and report the gap — do not invent missing prerequisites.

Step 3. EXECUTE
  - Work through every task in order.
  - Use specialized tools (Read, Write, StrReplace, Shell, Glob, Grep) for file operations.
  - For each meaningful artifact you create, run linters / tests / validators where applicable.
  - Update the TodoWrite list in real time as tasks move from in_progress → completed.

Step 4. VERIFY
  - Walk through every acceptance criterion in the implementation plan for Phase 9.
  - For each, perform an objective verification (file exists, command succeeds, output
    matches expected).
  - If a criterion cannot be met, document the blocker explicitly — do not silently skip it.

Step 5. PRODUCE THE FOUR DELIVERABLES (per `03-execution-playbook.md` §3)

  Deliverable A — Phase Implementation Artifacts
    - Already produced in Step 3.

  Deliverable B — Update `docs/02-implementation-plan.md`
    - Mark this phase's status (status comment beside the phase header):
        > **Status (as of <YYYY-MM-DD>): COMPLETED** OR
        > **Status (as of <YYYY-MM-DD>): IN-PROGRESS — see phase-9-log.md for blockers**
    - Tick every acceptance-criteria checkbox `[ ]` → `[x]` for met criteria.
      For unmet criteria, change to `[!]` and append a one-line reason after the criterion text.
    - If you discovered something that changes subsequent phases, add a callout block:
        > ⚠️ Revision (Phase 9 session, <date>): <description of the change>
    - Update §16 Indicative Timeline if actual elapsed time deviated noticeably from the estimate.

  Deliverable C — Write `docs/execution-log/phase-9-log.md`
    - Use the template in `03-execution-playbook.md` §5.
    - Be specific. List exact file paths created/modified. Quote exact command output for
      verifications.
    - Capture every decision you made under uncertainty (and why).
    - Capture every blocker, even if you worked around it.

  Deliverable D — Print + Save the Next-Session Prompt
    - If Phase 9 is fully complete, generate the prompt for Phase 10
      using the Master Session Prompt template in `03-execution-playbook.md` §4 with the next
      phase number and title substituted.
    - If Phase 9 is incomplete, generate a Resumption Prompt instead, instructing the
      next session to continue Phase 9 with explicit pointers to the unfinished tasks.
    - Write the prompt to `docs/execution-log/next-session-prompt.md` (overwrite any prior
      content).
    - ALSO print it as a fenced code block in the chat as the very last thing in your final
      message, with the heading `## Next Session Prompt`, so the operator can copy it
      directly.

────────────────────────────────────────────────────────────────────
HARD RULES
────────────────────────────────────────────────────────────────────

  - DO NOT skip an acceptance criterion silently. If you cannot meet it, mark `[!]` and explain.
  - DO NOT execute work outside the scope of Phase 9. Stay in scope.
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
    identity (per Phase 7 deliverables). Phase 9 only READS the dist tree (via the Phase-8
    consumer sync CLI); it never WRITES to it.
  - DO NOT publish `@org/standards-sync` to npm without explicit operator approval — that
    requires npm-org credentials (see Phase-8 log §9 open question on publish gating).

────────────────────────────────────────────────────────────────────
PHASE-9 CONTEXT (from prior sessions)
────────────────────────────────────────────────────────────────────

Phase 8 completed on 2026-05-20. The full state of the repository:

  - 18 source rules + 3 `_meta.yml` stack descriptors under `source/`.
  - 6 transformer modules under `compiler/transformers/` + 5 core modules under
    `compiler/core/` + the `python -m compiler` CLI driver with `--target {cursor,
    github_copilot,claude_skills,junie,agents_md,memory_bank,all}` and
    `--stack <stack-id>` OR `--all-stacks`. Output is byte-deterministic and
    byte-identical between `--all-stacks` and a per-stack loop.
  - The canonical stack catalog lives in `schemas/stacks.json` (Phase 8 lift).
    Both `compiler/core/stack_filter.py` and `tools/generate_dist_readme.py` load
    it at import time; the Node sync CLI consumes a byte-for-byte bundled copy
    at `packages/standards-sync/stacks.json`. Adding a fifth stack is a one-entry
    append to `schemas/stacks.json` plus a fixture under `fixtures/` plus a golden
    tree under `tests/golden/`.
  - 4 fixture consumer manifests under `fixtures/{spring-boot-3-2,
    spring-boot-2-7-legacy,nestjs-10,fastapi-0-110}/` + 4 byte-for-byte golden
    trees under `tests/golden/<fixture>/stacks/<stack-id>/` (77 golden files).
  - 4 hand-authored ArchUnit Java fixtures under `tests/archunit/`.
  - `Makefile` with `make update-golden`, `make explain-golden-diff`,
    `make release-dry-run`.
  - **279 passing + 7 skipped pytest tests** (the 7 are sandbox-conditional;
    they run unconditionally in CI).
  - **63 passing Node tests** (`cd packages/standards-sync && npm test`).
  - `.github/workflows/validate.yml` has 5 jobs: `tree-shape`,
    `schema-validation`, `compiler-unit-tests`, `golden-snapshots`,
    `dist-protection-lint`.
  - `.github/workflows/release.yml` is the Phase-7 manual `workflow_dispatch`
    workflow that is the SOLE producer of `dist/` changes. The first release
    (`v0.1.0`) has been published; subsequent releases are operator-dispatched
    per the `docs/release-bot-setup.md` runbook.
  - **Phase 8's deliverable: `@org/standards-sync@0.1.0` lives under
    `packages/standards-sync/`** — a Node ≥18 CLI that consumer repos run to
    sync the Engineering Standards distribution. Commands of note:
      - `cd packages/standards-sync && npm test` — runs the 63-test suite.
      - `node packages/standards-sync/bin/standards-sync.js --project-dir <path>
         --local-dist dist --version v0.1.0` — local smoke test against any
         consumer project.
      - Drop-in JVM recipes in `packages/standards-sync/plugins/{maven,gradle}/`.

Phase 9 is the "pilot adoption and telemetry" phase. Its six task pillars per
`docs/02-implementation-plan.md` §12 are:

  1. **Pilot selection** — three repos:
       - One greenfield Spring Boot 3 microservice.
       - One existing Spring Boot 2.7 monolith mid-migration to 3.x.
       - One TypeScript/NestJS service.
       Selection is operator-driven; the agent's deliverable is the selection
       *criteria document* + the kick-off PR template each pilot lands.

  2. **Embedded liaison** — a Pilot Liaison joins each pilot's standup for the
     four-week window. The agent cannot perform the staffing; the deliverable
     is the Pilot Liaison job description + the four-week schedule template.

  3. **Telemetry collection** — opt-in, privacy-preserving:
       - Sync invocations (count, version pinned, stack detected).
       - Rule-set delta on every sync (rules added/removed in the consumer's
         `.cursor/rules/`).
       - Per-rule "applied" counts via Cursor's rule-application telemetry
         (where available).
     The Phase-8 log §7 L3 notes the obvious telemetry source: the sync
     report's no-matching-globs warning section. The agent should add an
     `--emit-telemetry <path-or-url>` flag to `@org/standards-sync` and a
     telemetry-schema document that pilots' CI pipelines POST to.

  4. **Adoption metrics dashboard** — pilot repos per `.standards-version`,
     rule activations per repo per week, broken syncs + root causes. The
     agent's deliverable is the dashboard *spec* + a starter implementation
     using whatever observability stack the org has standardised on (or a
     stand-alone Grafana/Datadog config the operator can drop in).

  5. **Feedback loop** — weekly retrospective with the three liaisons; every
     issue files a GitHub issue with a `pilot-feedback` label. The agent's
     deliverable is the retro-meeting template + the `pilot-feedback` issue
     template under `.github/ISSUE_TEMPLATE/`.

  6. **Outcome review at week 4** — Go/No-Go decision. The agent's deliverable
     is the review *agenda template* + the decision-record format under
     `docs/decision-records/0005-phase-9-pilot-outcome.md` (or similar).

Acceptance criteria (verbatim from plan §12):

  - [ ] All three pilots are running on a tagged release of the distribution.
  - [ ] Telemetry dashboard exists and shows non-trivial activation counts.
  - [ ] The week-4 retro produces either a Go decision OR a documented blocker
        list with owners.

Several of these ACs depend on operator-side actions that the agent cannot
perform — recruiting three pilot teams, staffing a Pilot Liaison, accumulating
four weeks of real telemetry. The agent's contract is to land the *mechanical
infrastructure* (telemetry flag in the CLI, telemetry schema, dashboard spec
+ starter config, retro/decision-record templates, pilot-onboarding PR
template) so the pilot teams can run with minimal friction. Each AC that
requires elapsed time should be marked `[!]` with a clear handoff note
pointing at the runbook step that closes it.

Important Phase-9 boundary: the agent does NOT recruit pilot teams or
publish `@org/standards-sync` to npm. Both are operator actions (and the
publish action depends on npm-org credentials per Phase-8 log §9). The
agent's Phase-9 deliverables make those operator actions one-step PRs
or one-command runs.

The Phase-8 log §7 lessons (L1–L5) carry forward to Phase 9 as concrete
nudges:

  - L1 — Add `--write-report sync-report.md` + a `git status --porcelain` check
        to every pilot's CI workflow on day one (converts AC2 into a permanent
        drift guard).
  - L2 — Default pilots to PINNED mode (`.standards-version` file) for week
        one; floating mode is an explicit week-3 graduation step.
  - L3 — Aggregate sync-report no-match warnings per consumer per week — this
        is the cleanest signal for rule-glob refinement.
  - L4 — Adding a fifth stack is a one-entry append to `schemas/stacks.json`
        + fixture + golden tree (now in scope for Phase 10 governance, not
        Phase 9).
  - L5 — Maven/Gradle integration is **recipes, not native plugins** (the
        Phase-10 governance doc encodes this; Phase 9 should not revisit).

Begin Step 1 now.
