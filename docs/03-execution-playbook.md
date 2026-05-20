# Deliverable 3: Execution Playbook
## Single-Phase-Per-Session Workflow for Implementing the Engineering Standards Framework

> **Purpose**: A reusable session prompt + deliverable contract that lets you execute one phase of `02-implementation-plan.md` per Cursor session, ending each session with a clean handoff to the next.
> **Audience**: The human operator (you) and the AI agent picked up by each new session.
> **Pre-requisite reading for every session**: `01-architecture-upgrade-report.md`, `02-implementation-plan.md`, and any prior `docs/execution-log/phase-*-log.md` files.

---

## 1. How the Workflow Operates

```text
┌─────────────────────────────────────────────────────────────────┐
│ Session N                                                        │
│                                                                  │
│   1. Operator opens new Cursor chat                              │
│   2. Operator pastes the Master Session Prompt with PHASE = N    │
│   3. Agent reads plan + last log + relevant docs                 │
│   4. Agent executes EVERY task in Phase N                        │
│   5. Agent verifies EVERY acceptance criterion                   │
│   6. Agent produces 4 deliverables (see §3)                      │
│   7. Agent prints the Phase N+1 prompt for next session          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
              [Operator reviews + closes session]
                                │
                                ▼
              [New Cursor chat for Session N+1]
```

Each session is **self-contained**: the agent reads the plan and the prior log, executes one phase, and writes a log so the next session has continuity. The agent has zero memory between sessions; the log is the memory.

---

## 2. How to Use This Playbook (Operator Instructions)

### Starting the very first session (Phase 0)

1. Open a new Cursor chat in this workspace.
2. Copy the **Phase 0 Kickoff Prompt** from §7 below.
3. Paste it as the first message of the session.
4. Let the agent run to completion.
5. At the end, the agent will print the **Phase 1 Prompt** as a code block. Save it; you'll paste it next session.

### Starting any subsequent session (Phase N)

1. Open a new Cursor chat in this workspace.
2. Use the prompt that was printed at the end of the previous session (also saved to `docs/execution-log/next-session-prompt.md`).
3. Paste it as the first message.
4. Let the agent run to completion.
5. Save the Phase N+1 prompt for next time.

### If a session ends incomplete

If the agent reports that the phase could NOT be fully completed (blocker hit, time ran out, etc.):

1. The agent will mark the phase as **`status: in-progress`** in the implementation plan and write a **Resumption Prompt** instead of a Next-Phase Prompt.
2. Use the Resumption Prompt next session — it instructs the agent to *continue* Phase N, not start Phase N+1.

### Reviewing what happened

After each session, you can read `docs/execution-log/phase-{N}-log.md` to see exactly what was done, what was decided, and what is now ready for the next phase.

---

## 3. End-of-Session Deliverables Contract

Every session, regardless of which phase it executes, MUST produce these four deliverables in order:

### Deliverable A — Phase Implementation Artifacts

The actual files, code, schemas, configs, etc. specified by the phase's task list. These land in the appropriate paths under the repository (`source/`, `compiler/`, `schemas/`, `dist/`, `.github/`, etc.).

**Quality bar**: Every acceptance criterion in the implementation plan for this phase is verified — either checked off as "done" or flagged with a documented blocker.

### Deliverable B — Updated Implementation Plan

`docs/02-implementation-plan.md` is edited in-place to reflect:

- Phase status changed from `pending` → `completed` (or `in-progress` if blocked).
- All acceptance-criteria checkboxes for the phase are marked `[x]` (or annotated `[!]` with the blocker reason inline).
- Any lessons learned that change subsequent phases (e.g., "Phase 5 needs an extra task") are added with a clearly-marked `> ⚠️ Revision N` callout.
- The Indicative Timeline section is updated if actual elapsed time deviates from the original estimate.

### Deliverable C — Session Log

A new file at `docs/execution-log/phase-{N}-log.md` using the **Session Log Template** in §5. This file is permanent project history.

### Deliverable D — Next-Session Prompt

A code block printed in the chat AND saved to `docs/execution-log/next-session-prompt.md`, containing the exact prompt to paste in the next session. The agent must overwrite the prior prompt; only the most-recent next-session prompt is kept.

---

## 4. The Master Session Prompt

This is the reusable prompt template. The operator (or the prior session's agent) substitutes `{PHASE_NUMBER}` and `{PHASE_TITLE}` before pasting.

```markdown
You are acting as a Principal AI Enablement Engineer and Staff Software Architect executing the
multi-phase rollout of the Engineering Standards Framework. You are picking up a long-running project
that has already produced three foundational documents in `docs/`:

  - `ai-engineering-standards-blueprint.md` — the original baseline
  - `01-architecture-upgrade-report.md`     — the architectural critique and target design
  - `02-implementation-plan.md`             — the eleven-phase execution plan (Phase 0 → Phase 10)
  - `03-execution-playbook.md`              — the playbook you are operating under right now

Your task this session: **execute Phase {PHASE_NUMBER} — {PHASE_TITLE}** end-to-end.

You have NO memory of any prior session. Treat the implementation plan and any logs in
`docs/execution-log/` as your only source of context.

────────────────────────────────────────────────────────────────────
PROCEDURE (follow in order)
────────────────────────────────────────────────────────────────────

Step 1. ORIENT
  - Read `docs/02-implementation-plan.md`. Find the section for Phase {PHASE_NUMBER}.
  - Read every prior log under `docs/execution-log/phase-*-log.md`. Pay attention to the
    "Decisions made" and "Lessons that affect later phases" sections of each.
  - Read any other documents referenced by the phase's task list (ADRs, architecture report sections, etc.).

Step 2. PLAN
  - Use the TodoWrite tool to enumerate every task and every acceptance criterion in Phase {PHASE_NUMBER}
    as separate todos. Mark the first one in_progress.
  - If the phase depends on artifacts from earlier phases, verify those artifacts exist on disk.
    If any are missing, STOP and report the gap — do not invent missing prerequisites.

Step 3. EXECUTE
  - Work through every task in order.
  - Use specialized tools (Read, Write, StrReplace, Shell, Glob, Grep) for file operations.
  - For each meaningful artifact you create, run linters / tests / validators where applicable.
  - Update the TodoWrite list in real time as tasks move from in_progress → completed.

Step 4. VERIFY
  - Walk through every acceptance criterion in the implementation plan for Phase {PHASE_NUMBER}.
  - For each, perform an objective verification (file exists, command succeeds, output matches expected).
  - If a criterion cannot be met, document the blocker explicitly — do not silently skip it.

Step 5. PRODUCE THE FOUR DELIVERABLES (per `03-execution-playbook.md` §3)

  Deliverable A — Phase Implementation Artifacts
    - Already produced in Step 3.

  Deliverable B — Update `docs/02-implementation-plan.md`
    - Mark this phase's status (status comment beside the phase header):
        > **Status (as of <YYYY-MM-DD>): COMPLETED** OR
        > **Status (as of <YYYY-MM-DD>): IN-PROGRESS — see phase-{N}-log.md for blockers**
    - Tick every acceptance-criteria checkbox `[ ]` → `[x]` for met criteria.
      For unmet criteria, change to `[!]` and append a one-line reason after the criterion text.
    - If you discovered something that changes subsequent phases, add a callout block:
        > ⚠️ Revision (Phase {N} session, <date>): <description of the change>
    - Update §16 Indicative Timeline if actual elapsed time deviated noticeably from the estimate.

  Deliverable C — Write `docs/execution-log/phase-{N}-log.md`
    - Use the template in `03-execution-playbook.md` §5.
    - Be specific. List exact file paths created/modified. Quote exact command output for verifications.
    - Capture every decision you made under uncertainty (and why).
    - Capture every blocker, even if you worked around it.

  Deliverable D — Print + Save the Next-Session Prompt
    - If Phase {PHASE_NUMBER} is fully complete, generate the prompt for Phase {PHASE_NUMBER + 1}
      using the Master Session Prompt template in `03-execution-playbook.md` §4 with the next phase
      number and title substituted.
    - If Phase {PHASE_NUMBER} is incomplete, generate a Resumption Prompt instead, instructing the
      next session to continue Phase {PHASE_NUMBER} with explicit pointers to the unfinished tasks.
    - Write the prompt to `docs/execution-log/next-session-prompt.md` (overwrite any prior content).
    - ALSO print it as a fenced code block in the chat as the very last thing in your final message,
      with the heading `## Next Session Prompt`, so the operator can copy it directly.

────────────────────────────────────────────────────────────────────
HARD RULES
────────────────────────────────────────────────────────────────────

  - DO NOT skip an acceptance criterion silently. If you cannot meet it, mark `[!]` and explain.
  - DO NOT execute work outside the scope of Phase {PHASE_NUMBER}. Stay in scope.
  - DO NOT invent file paths or command names. If a path is unclear, read the implementation plan again.
  - DO NOT modify any phase's plan retroactively without using a `> ⚠️ Revision` callout.
  - DO NOT create the next-session prompt before the four deliverables are complete.
  - DO use the TodoWrite tool from the start; it is the operator's primary visibility into progress.
  - DO commit every meaningful artifact to disk; nothing in this workflow is transient.
  - DO NOT run `git commit` or `git push` unless the operator explicitly asks. The Engineering
    Standards Council reviews commits in PRs, not autonomously.

Begin Step 1 now.
```

---

## 5. Session Log Template

Every session writes one of these to `docs/execution-log/phase-{N}-log.md`. Replace bracketed placeholders.

```markdown
# Phase {N} Execution Log — {Phase Title}

- **Phase**: {N} — {Phase Title}
- **Date**: {YYYY-MM-DD}
- **Status**: COMPLETED | IN-PROGRESS | BLOCKED
- **Estimated duration (per plan)**: {N} days
- **Actual duration**: {N} session(s) of ~{N} hours

## 1. Summary

{Two- or three-sentence summary of what this phase accomplished and the key outcome.}

## 2. Files Created

- `path/to/file1` — {one-line description}
- `path/to/file2` — {one-line description}

## 3. Files Modified

- `path/to/file3` — {what changed and why}

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan) | Status | Evidence / Notes |
|---|---|---|
| {criterion 1} | ✅ | {how you verified — file path, command output, etc.} |
| {criterion 2} | ✅ | {evidence} |
| {criterion 3} | ⚠️ | {why not met; mitigation} |

## 5. Decisions Made

For each non-trivial choice made during this session under conditions of ambiguity:

- **Decision**: {what was chosen}
  - **Alternatives considered**: {what was not chosen}
  - **Rationale**: {why}
  - **Reversible?**: yes / no — {if no, why}

## 6. Blockers Encountered

- **Blocker**: {description}
  - **Resolution**: {how it was resolved or worked around}
  - **Carry-forward**: {what next sessions need to know}

## 7. Lessons that Affect Later Phases

- {lesson 1 — and which phase it affects}
- {lesson 2 — and which phase it affects}

(If any lesson here is non-trivial, a `> ⚠️ Revision` callout has been added to `02-implementation-plan.md`.)

## 8. Verification Commands Run

```bash
# Paste the actual commands and their (truncated) outputs that prove the acceptance criteria.
```

## 9. Handoff to Next Session

- **Next phase**: {N+1} — {Phase Title}
- **Next-session prompt**: written to `docs/execution-log/next-session-prompt.md`
- **Pre-requisites for next phase that are now satisfied**: {list}
- **Open questions for the operator (if any)**: {list, or "none"}
```

---

## 6. Phase Sequence Reference

Quick lookup so the operator (or the agent generating the next-session prompt) always has the right `{PHASE_NUMBER}` / `{PHASE_TITLE}` to substitute.

| Phase | Title | Duration | Reference Section |
|---|---|---|---|
| 0 | Pre-Flight Decisions and ADRs | 4 days | Plan §3 |
| 1 | Repository Scaffolding | 2 days | Plan §4 |
| 2 | Schemas, Layer-to-Glob Map, and Validation | 4 days | Plan §5 |
| 3 | Source Content Migration & Authoring of New Logic Holes | 8 days | Plan §6 |
| 4 | Compiler Core Engine | 7 days | Plan §7 |
| 5 | Per-Tool Transformers | 6 days | Plan §8 |
| 6 | Fixtures, Golden Files, and CI | 5 days | Plan §9 |
| 7 | Release Workflow & `dist/` Folder Protection | 2 days | Plan §10 |
| 8 | Consumer-Side Sync Tool | 6 days | Plan §11 |
| 9 | Pilot Adoption and Telemetry | 4 weeks | Plan §12 |
| 10 | Org-Wide Rollout, Governance, and MCP Roadmap | 6+ weeks | Plan §13 |

> **Mapping a phase to multiple sessions**: Phases 3, 4, 5, 8, 9, and 10 are each estimated to need more than one session. The agent should track sub-progress in TodoWrite and, when a session ends mid-phase, generate a Resumption Prompt (not a Next-Phase Prompt) per the Master Session Prompt's "Hard Rules."

---

## 7. Phase 0 Kickoff Prompt (Paste This in Your Very First Session)

Copy everything inside the fenced block below into a fresh Cursor chat to begin execution.

````markdown
You are acting as a Principal AI Enablement Engineer and Staff Software Architect executing the
multi-phase rollout of the Engineering Standards Framework. You are picking up a long-running project
that has already produced three foundational documents in `docs/`:

  - `ai-engineering-standards-blueprint.md` — the original baseline
  - `01-architecture-upgrade-report.md`     — the architectural critique and target design
  - `02-implementation-plan.md`             — the eleven-phase execution plan (Phase 0 → Phase 10)
  - `03-execution-playbook.md`              — the playbook you are operating under right now

Your task this session: **execute Phase 0 — Pre-Flight Decisions and ADRs** end-to-end.

You have NO memory of any prior session. Treat the implementation plan and any logs in
`docs/execution-log/` as your only source of context.

────────────────────────────────────────────────────────────────────
PROCEDURE (follow in order)
────────────────────────────────────────────────────────────────────

Step 1. ORIENT
  - Read `docs/02-implementation-plan.md`. Find the section for Phase 0.
  - Read every prior log under `docs/execution-log/phase-*-log.md` (likely none on the first run —
    create the directory if absent as part of Deliverable C).
  - Read any other documents referenced by the phase's task list (the architecture report's §3 and §4
    are particularly relevant for ADR-0001 and ADR-0002; ADR-0004 is detailed in plan §3 itself).

Step 2. PLAN
  - Use the TodoWrite tool to enumerate every task and every acceptance criterion in Phase 0 as
    separate todos. Mark the first one in_progress.
  - Verify there are no missing prerequisites (Phase 0 has none — it is the first phase).

Step 3. EXECUTE
  - Author all four ADRs as separate Markdown files under `docs/decision-records/`:
      0001-mdc-over-cursorrules.md
      0002-layer-keyed-source-split.md
      0003-deferred-mcp-server.md
      0004-single-repo-distribution.md
  - Each ADR follows the standard structure: Context, Decision, Status, Consequences, Alternatives Considered.
  - Update `README.md` (create one if it does not exist) with links to the ADRs and to the three
    foundational documents.

Step 4. VERIFY
  - Confirm: all four ADR files exist under `docs/decision-records/`.
  - Confirm: each ADR has the standard sections.
  - Confirm: README links to all four ADRs and the three foundational docs.
  - Confirm (if applicable): AI Enablement PM sign-off can be deferred to the operator — note as
    "pending operator review" in the log if no human review has happened yet.

Step 5. PRODUCE THE FOUR DELIVERABLES per `03-execution-playbook.md` §3:

  A. Phase Implementation Artifacts (the four ADRs + README updates) — already done in Step 3.

  B. Update `docs/02-implementation-plan.md`:
     - Mark Phase 0 status as COMPLETED with today's date.
     - Tick every Phase 0 acceptance-criteria checkbox `[ ]` → `[x]`.

  C. Create `docs/execution-log/` directory and write `docs/execution-log/phase-0-log.md` using the
     template in `03-execution-playbook.md` §5.

  D. Generate the Phase 1 prompt by substituting `{PHASE_NUMBER}` = 1 and
     `{PHASE_TITLE}` = "Repository Scaffolding" into the Master Session Prompt template in
     `03-execution-playbook.md` §4. Save to `docs/execution-log/next-session-prompt.md` and ALSO
     print it as a fenced code block at the end of your final chat message under the heading
     "## Next Session Prompt".

────────────────────────────────────────────────────────────────────
HARD RULES
────────────────────────────────────────────────────────────────────

  - DO NOT skip an acceptance criterion silently. If you cannot meet it, mark `[!]` and explain.
  - DO NOT execute work outside the scope of Phase 0. Stay in scope.
  - DO NOT invent file paths or command names. If a path is unclear, read the implementation plan again.
  - DO NOT modify any phase's plan retroactively without using a `> ⚠️ Revision` callout.
  - DO NOT create the next-session prompt before the four deliverables are complete.
  - DO use the TodoWrite tool from the start; it is the operator's primary visibility into progress.
  - DO commit every meaningful artifact to disk; nothing in this workflow is transient.
  - DO NOT run `git commit` or `git push` unless the operator explicitly asks.

Begin Step 1 now.
````

---

## 8. Resumption Prompt Template (When a Session Ends Mid-Phase)

If the previous session marked the phase as `IN-PROGRESS` rather than `COMPLETED`, the agent generates THIS variant of the next-session prompt instead, substituting `{PHASE_NUMBER}` and `{PHASE_TITLE}`.

```markdown
You are acting as a Principal AI Enablement Engineer and Staff Software Architect resuming a
multi-session phase of the Engineering Standards Framework rollout.

The previous session left **Phase {PHASE_NUMBER} — {PHASE_TITLE}** in IN-PROGRESS status.
Your task is to **complete it**, not to start the next phase.

Step 1. ORIENT
  - Read `docs/02-implementation-plan.md` for the full Phase {PHASE_NUMBER} task list and acceptance criteria.
  - Read `docs/execution-log/phase-{PHASE_NUMBER}-log.md` from the prior session to learn:
      - Which tasks are already done.
      - Which acceptance criteria are already met.
      - What blockers were noted.
  - Read `03-execution-playbook.md` §3, §4, §5 for the deliverable contract.

Step 2. PLAN
  - Use TodoWrite to list ONLY the unfinished tasks and unmet acceptance criteria.

Step 3. EXECUTE the remaining work.

Step 4. VERIFY all acceptance criteria are now met.

Step 5. PRODUCE THE FOUR DELIVERABLES (per playbook §3):
  - Update Phase {PHASE_NUMBER} status to COMPLETED in the implementation plan.
  - APPEND a new section to `docs/execution-log/phase-{PHASE_NUMBER}-log.md` titled
    "## Resumption Session — <YYYY-MM-DD>" with all the standard log subsections covering only
    the work done this session.
  - Generate the Phase {PHASE_NUMBER + 1} prompt (now that the current phase is complete) per playbook §4.

HARD RULES (same as the Master Session Prompt).

Begin Step 1 now.
```

---

## 9. Operator's Quick-Reference Card

Print this and pin it next to your keyboard.

| If… | Then… |
|---|---|
| You're starting fresh, never run a session | Use **Phase 0 Kickoff Prompt** (§7) |
| Last session printed a Next Session Prompt | Paste that prompt verbatim |
| Last session's status was IN-PROGRESS | Paste the Resumption Prompt (printed by that session) |
| You're unsure which phase is next | Read `docs/execution-log/next-session-prompt.md`; it always reflects the next move |
| The agent goes off-rails mid-session | Stop the session; the implementation plan is the source of truth — restart with the same prompt |
| You want to pause the project | No action needed; the log files preserve all state |
| You want to skip a phase | Don't. Phases have hard dependencies. Override only via a `> ⚠️ Revision` callout in the plan, with explicit rationale |

---

## 10. Why This Workflow Works

1. **Statelessness is the design constraint, not a bug.** Each session starts cold; the playbook + plan + logs are the entire memory surface. That makes the workflow resumable, reviewable, and auditable.
2. **The implementation plan is the contract.** The agent doesn't decide what to do — it executes pre-specified tasks against pre-specified acceptance criteria. Sessions cannot drift.
3. **Logs are permanent.** Every decision, blocker, and deviation is captured. Six months from now, anyone can read the logs and reconstruct the project history.
4. **The next-session prompt is generated, not remembered.** The agent ending Session N writes the prompt for Session N+1. The operator's only job between sessions is to paste.
5. **Quality is enforced by the deliverable contract.** A session is "done" only when all four deliverables are produced. No partial completion, no implicit handoffs.

---

## Document End

This concludes the Execution Playbook. With this in hand, the operator can drive the entire 11-phase rollout one session at a time, with full continuity, full traceability, and zero session-to-session memory loss.
