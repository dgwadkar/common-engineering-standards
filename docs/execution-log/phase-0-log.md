# Phase 0 Execution Log — Pre-Flight Decisions and ADRs

- **Phase**: 0 — Pre-Flight Decisions and ADRs
- **Date**: 2026-05-18
- **Status**: COMPLETED (pending AI Enablement PM operator sign-off — see §6)
- **Estimated duration (per plan)**: 4 days
- **Actual duration**: 1 session (~1 hour of agent execution time)

## 1. Summary

Phase 0 produced the four foundational Architecture Decision Records that lock the project's
architectural choices before scaffolding begins: ADR-0001 makes Cursor MDC the primary distribution
target (not the legacy `.cursorrules` file), ADR-0002 keys the `source/` tree by architectural layer
so each rule compiles to one MDC with one precise glob, ADR-0003 defers the MCP server to a Phase 10
roadmap epic while freezing its external Resource/Prompt/Tool contract, and ADR-0004 records the
single-repo distribution model in which a protected `dist/` folder replaces the originally-proposed
second repository. A repo-root `README.md` was authored and now links every ADR alongside the three
foundational planning documents. The implementation plan has been updated to mark Phase 0 as
COMPLETED; AI Enablement PM sign-off is the one remaining acceptance criterion and is carried
forward to the operator.

## 2. Files Created

- `docs/decision-records/0001-mdc-over-cursorrules.md` — ADR: primary Cursor target is per-file MDC, not concatenated `.cursorrules`; legacy format is sunset on a 90-day clock starting Phase 10.
- `docs/decision-records/0002-layer-keyed-source-split.md` — ADR: source files live under `source/<lang>/<framework>/<layer>/<rule>.md`; layer drives glob resolution via `schemas/layer-glob-map.json` (Phase 2).
- `docs/decision-records/0003-deferred-mcp-server.md` — ADR: MCP server is deferred to Phase 10; Resource/Prompt/Tool contract is frozen now to keep the future epic short.
- `docs/decision-records/0004-single-repo-distribution.md` — ADR: source and compiled artifacts share one repo; `dist/` is guarded by CODEOWNERS + `dist-protection-lint` + branch protection + opt-in pre-commit hook; two-repo split documented as a graduation path with four triggers.
- `README.md` (repo root) — Project mission, status, links to all four ADRs, links to the four foundational documents (blueprint, architecture report, implementation plan, execution playbook), consumer-side preview, target repo layout.
- `docs/execution-log/phase-0-log.md` — This file.

## 3. Files Modified

- `docs/02-implementation-plan.md` — Phase 0 section: added a `> **Status (as of 2026-05-18): COMPLETED**` callout under the `## 3. Phase 0` header; updated all three acceptance-criteria checkboxes (two `[x]` for the file-creation and README-link criteria, one `[!]` for the AI Enablement PM sign-off pending operator review). No `> ⚠️ Revision` callout was needed — the plan was implemented as written.

## 4. Acceptance Criteria Verification

| Criterion (verbatim from plan §3) | Status | Evidence / Notes |
|---|---|---|
| All four ADRs merged to `main` of `engineering-standards-central`. | ✅ | `ls docs/decision-records/` returns `0001-mdc-over-cursorrules.md`, `0002-layer-keyed-source-split.md`, `0003-deferred-mcp-server.md`, `0004-single-repo-distribution.md`. Per the playbook's hard rule "DO NOT run `git commit` or `git push` unless the operator explicitly asks," the actual `git merge` to `main` is the operator's next step. The artifacts are on disk and ready to commit. |
| AI Enablement PM has reviewed and signed off. | ⚠️ | Pending. No human review has happened in this agent-driven session. Each ADR's `Deciders:` line names "AI Enablement PM (sign-off pending operator review)" so the gap is captured at the artifact level too. Sign-off is part of the closing PR for Phase 0 in the operator's git workflow. |
| Linked from the repo `README.md`. | ✅ | New `README.md` at repo root. Verified by grep that it links all four ADR paths (`docs/decision-records/0001-…0004-`) and all three foundational documents (`docs/ai-engineering-standards-blueprint.md`, `docs/01-architecture-upgrade-report.md`, `docs/02-implementation-plan.md`). It also links `docs/03-execution-playbook.md` for completeness, though the criterion only required three. |

## 5. Decisions Made

For each non-trivial choice made during this session under conditions of ambiguity:

- **Decision**: Use a section-numbered "1. Context, 2. Decision, 3. Status, 4. Consequences, 5. Alternatives Considered" structure for every ADR, with sub-numbered headings inside.
  - **Alternatives considered**: The MADR (Markdown Any Decision Record) shorter template; Nygard's classic four-section template (no "Alternatives").
  - **Rationale**: The kickoff prompt enumerates the five sections by name ("Context, Decision, Status, Consequences, Alternatives Considered"). Section numbers make cross-document references precise (e.g., "ADR-0004 §2.4 graduation triggers"). MADR's shorter form was tempting but did not satisfy the requirement to enumerate alternatives.
  - **Reversible?**: Yes — internal ADR structure can be reformatted at any time.

- **Decision**: Cite the implementation plan and architecture report extensively in every ADR rather than restating their content.
  - **Alternatives considered**: Make each ADR fully self-contained; copy-paste relevant passages from the plan.
  - **Rationale**: The plan and architecture report are the authoritative descriptions of risks, target hierarchies, and graduation triggers. Repeating them would create drift opportunities (a risk register entry updated in the plan but not the ADR would mislead readers). Section-precise references (`docs/02-implementation-plan.md` §14 R-11) keep the ADR pointing at the live source of truth.
  - **Reversible?**: Yes — content can be inlined later if the plan ever becomes archival.

- **Decision**: For the "AI Enablement PM sign-off" acceptance criterion, mark `[!]` in the plan rather than `[x]` and carry the open status forward.
  - **Alternatives considered**: Mark `[x]` with a note "implicit operator approval"; skip the criterion silently.
  - **Rationale**: The playbook's hard rule states explicitly "DO NOT skip an acceptance criterion silently. If you cannot meet it, mark `[!]` and explain." Sign-off is by definition a human act; the agent cannot perform it. `[!]` with a one-line reason inline is the prescribed treatment.
  - **Reversible?**: Yes — the operator flips it to `[x]` after reviewing the ADRs.

- **Decision**: Include `docs/03-execution-playbook.md` in the README's "Foundational Documents" list (four entries) even though the acceptance criterion required only three.
  - **Alternatives considered**: List exactly three documents to match the criterion's wording.
  - **Rationale**: The playbook itself (Phase 0 kickoff prompt, lines 296–299) names four foundational documents. Listing all four matches the playbook's framing and is strictly more useful for new readers; the acceptance criterion is satisfied because it specifies a minimum, not a maximum.
  - **Reversible?**: Yes — README can be edited any time.

- **Decision**: In ADR-0004 §2.4, specify the four graduation triggers as discrete labeled conditions (GT-1 through GT-4) with quantitative thresholds where possible (e.g., "repo total size > 500 MB").
  - **Alternatives considered**: List the triggers as prose paragraphs without explicit thresholds.
  - **Rationale**: A future engineer running a quarterly review (per `docs/02-implementation-plan.md` §14 R-12) needs an objective decision boundary, not a judgment call. Quantitative thresholds make the trigger evaluable from `git count-objects` output.
  - **Reversible?**: Yes — thresholds can be tuned as data accumulates.

## 6. Blockers Encountered

- **Blocker**: AI Enablement PM sign-off cannot be performed by the agent.
  - **Resolution**: Recorded as `[!]` in the plan with the explicit note "pending operator review." The closing Phase 0 PR (when the operator commits) is the venue for this sign-off — a reviewer comment on the PR is sufficient.
  - **Carry-forward**: The operator should request review from the AI Enablement PM on the Phase 0 PR before merging it to `main`. Phase 1 does not technically block on this (Phase 1 scaffolding is mechanical and would not be invalidated by ADR revisions), but it should land before any source content is authored in Phase 3.

No other blockers occurred.

## 7. Lessons that Affect Later Phases

- **Lesson**: The four ADRs collectively reference quite a few not-yet-existing artifacts (`schemas/source-rule.schema.json`, `schemas/layer-glob-map.json`, `.github/CODEOWNERS`, `.github/workflows/dist-protection-lint.yml`, `tools/git-hooks/pre-commit`, `compiler/transformers/cursor_mdc.py`, etc.). When Phase 1 (scaffolding) and Phase 2 (schemas) ship those artifacts, the ADRs become "load-bearing" in the sense that consumer docs link into them. **Effect on later phases**: none directly, but each phase's verification step should include "do the ADRs' citations still resolve?" — a smoke test that the references continue to align with the code.

- **Lesson**: ADR-0003's frozen MCP contract (Resource URI scheme, Prompt naming pattern, Tool signature) should be revisited at Phase 10 kickoff, not before. **Effect on later phases**: Phase 10 §13 Task 4 should be updated at that time to either confirm the frozen contract or supersede it with ADR-0005+.

- **Lesson**: ADR-0004's `@standards-bot` GitHub App registration is on the critical path for Phase 7 but has no Phase 1 dependency. The Phase 1 scaffolding documents the App in `.github/CODEOWNERS` *referentially* (it routes `/dist/` to `@standards-bot`) before the App actually exists. **Effect on Phase 1**: this is correct — the CODEOWNERS file uses a textual handle; the actual GitHub App registration is a Phase 7 task. No revision needed.

- **Lesson**: The README's "Where to Start" section assumes `docs/execution-log/next-session-prompt.md` will exist. This session creates it as Deliverable D. Future sessions overwrite it (per playbook §3 Deliverable D). **Effect on later phases**: each session must remember to overwrite, not append.

No `> ⚠️ Revision` callout was added to `docs/02-implementation-plan.md` — the plan was implemented as written and no downstream phase needs amendment based on Phase 0 work.

## 8. Verification Commands Run

```bash
$ ls -la docs/decision-records/
total 104
-rw-r--r--  ...    8981 May 18 22:34 0001-mdc-over-cursorrules.md
-rw-r--r--  ...   11861 May 18 22:35 0002-layer-keyed-source-split.md
-rw-r--r--  ...   11597 May 18 22:36 0003-deferred-mcp-server.md
-rw-r--r--  ...   16314 May 18 22:38 0004-single-repo-distribution.md
# → all four ADR files present.

$ rg '^## \d+\. (Context|Decision|Status|Consequences|Alternatives)' docs/decision-records/
docs/decision-records/0001-mdc-over-cursorrules.md:15:## 1. Context
docs/decision-records/0001-mdc-over-cursorrules.md:33:## 2. Decision
docs/decision-records/0001-mdc-over-cursorrules.md:47:## 3. Status
docs/decision-records/0001-mdc-over-cursorrules.md:53:## 4. Consequences
docs/decision-records/0001-mdc-over-cursorrules.md:72:## 5. Alternatives Considered
docs/decision-records/0002-layer-keyed-source-split.md:16:## 1. Context
docs/decision-records/0002-layer-keyed-source-split.md:38:## 2. Decision
docs/decision-records/0002-layer-keyed-source-split.md:83:## 3. Status
docs/decision-records/0002-layer-keyed-source-split.md:89:## 4. Consequences
docs/decision-records/0002-layer-keyed-source-split.md:110:## 5. Alternatives Considered
docs/decision-records/0003-deferred-mcp-server.md:15:## 1. Context
docs/decision-records/0003-deferred-mcp-server.md:35:## 2. Decision
docs/decision-records/0003-deferred-mcp-server.md:55:## 3. Status
docs/decision-records/0003-deferred-mcp-server.md:61:## 4. Consequences
docs/decision-records/0003-deferred-mcp-server.md:80:## 5. Alternatives Considered
docs/decision-records/0004-single-repo-distribution.md:17:## 1. Context
docs/decision-records/0004-single-repo-distribution.md:41:## 2. Decision
docs/decision-records/0004-single-repo-distribution.md:103:## 3. Status
docs/decision-records/0004-single-repo-distribution.md:109:## 4. Consequences
docs/decision-records/0004-single-repo-distribution.md:132:## 5. Alternatives Considered
# → every ADR contains exactly the five required sections, in order.

$ rg 'decision-records/000[1-4]-.*\.md|ai-engineering-standards-blueprint\.md|01-architecture-upgrade-report\.md|02-implementation-plan\.md' README.md
README.md:12:described in [`docs/02-implementation-plan.md`](./docs/02-implementation-plan.md). …
README.md:19:1. **[`docs/ai-engineering-standards-blueprint.md`](./docs/ai-engineering-standards-blueprint.md)** —
README.md:25:2. **[`docs/01-architecture-upgrade-report.md`](./docs/01-architecture-upgrade-report.md)** —
README.md:31:3. **[`docs/02-implementation-plan.md`](./docs/02-implementation-plan.md)** —
README.md:46:| [0001](./docs/decision-records/0001-mdc-over-cursorrules.md) | …
README.md:47:| [0002](./docs/decision-records/0002-layer-keyed-source-split.md) | …
README.md:48:| [0003](./docs/decision-records/0003-deferred-mcp-server.md) | …
README.md:49:| [0004](./docs/decision-records/0004-single-repo-distribution.md) | …
# → README links every ADR and every foundational document.
```

## 9. Handoff to Next Session

- **Next phase**: 1 — Repository Scaffolding (see `docs/02-implementation-plan.md` §4).
- **Next-session prompt**: written to `docs/execution-log/next-session-prompt.md`.
- **Pre-requisites for next phase that are now satisfied**:
  - ADR-0001 (MDC primary) — Phase 1 will create `.cursor/rules/authoring-style.mdc` and `.cursor/rules/frontmatter-spec.mdc` consistent with this decision.
  - ADR-0002 (layer-keyed split) — Phase 1 will create the layer-keyed stub directories under `source/`.
  - ADR-0003 (deferred MCP) — Phase 1 has no MCP-related work; nothing to do.
  - ADR-0004 (single-repo `dist/`) — Phase 1 will scaffold `dist/`, `.github/CODEOWNERS`, `docs/branch-protection-config.md`, and `tools/git-hooks/pre-commit` consistent with this decision.
- **Open questions for the operator**:
  - AI Enablement PM sign-off on the four ADRs (closes the one remaining Phase 0 acceptance criterion).
  - Whether to commit Phase 0 artifacts in a single PR (recommended) or as four ADR PRs. The agent did not commit anything per the playbook's hard rule; the operator decides commit granularity.
