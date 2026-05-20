# Engineering Standards Central

> The single source of truth for the organization's AI-assisted engineering standards.
> Source rules are authored once in Markdown, compiled into a fan of per-tool distribution artifacts
> (Cursor MDC, GitHub Copilot, Claude, JetBrains Junie, universal `AGENTS.md`), and shipped to consumer
> repositories via a versioned sync command. The goal: better AI code generation across every repo at
> the org, every day, with no per-repo authoring duplication.

## Status

Phase 0 — Pre-Flight Decisions and ADRs — is **COMPLETED** (pending AI Enablement PM sign-off).
Phase 1 — Repository Scaffolding — is **COMPLETED**: the directory skeleton, the central repo's own
`.cursor/rules/` dogfood rules, the root [`AGENTS.md`](./AGENTS.md), `.github/CODEOWNERS`, the
branch-protection checklist at [`docs/branch-protection-config.md`](./docs/branch-protection-config.md),
the defensive client-side pre-commit hook at `tools/git-hooks/pre-commit`, and the protected
`dist/` placeholder are all in place.
Phase 2 — Schemas, Layer-to-Glob Map, and Validation — is **COMPLETED**: the three machine-readable
schemas + the `compiler/core/parse_source.py --validate-only` Phase-2 slice + the `schema-validation`
CI job all ship.
Phase 3 — Source Content Migration & Authoring of New Logic Holes — is **COMPLETED**: 18 source
rules across the four baseline error-handling files, the four new Java/Spring-Boot Logic Holes
(#3, #4, #5, #6), and the three cross-cutting global rules are authored; the long-form
[`docs/authoring-guide.md`](./docs/authoring-guide.md) is the prose companion to the always-loaded
`.cursor/rules/*.mdc` checklists.
See the full 11-phase rollout in [`docs/02-implementation-plan.md`](./docs/02-implementation-plan.md).

## Foundational Documents

Read these in order to understand what is being built and why.

1. **[`docs/ai-engineering-standards-blueprint.md`](./docs/ai-engineering-standards-blueprint.md)** —
   the original baseline blueprint. Diagnoses the strategic problem (AI agents producing
   syntactically-valid Spring Boot code with latent architectural defects) and proposes the first-generation
   approach (concatenated `.cursorrules`). Preserved for historical context; superseded by the
   Architecture Upgrade Report.

2. **[`docs/01-architecture-upgrade-report.md`](./docs/01-architecture-upgrade-report.md)** —
   the architectural critique and target design. Identifies four additional Java/Spring-Boot
   "Logic Holes" beyond the baseline, benchmarks 2026 AI tooling patterns (Cursor MDC, Memory Bank,
   AGENTS.md, MCP), critiques the baseline layout, and proposes the evolved single-source →
   multi-target compilation pipeline.

3. **[`docs/02-implementation-plan.md`](./docs/02-implementation-plan.md)** —
   the eleven-phase execution plan (Phase 0 → Phase 10) with task lists, acceptance criteria,
   risk register, and timeline. The Standards Council operates against this plan.

4. **[`docs/03-execution-playbook.md`](./docs/03-execution-playbook.md)** —
   the single-phase-per-session workflow + master session prompt the AI agent uses to execute
   each phase end-to-end, with a session-log handoff between phases.

## Architecture Decision Records (ADRs)

ADRs live in [`docs/decision-records/`](./docs/decision-records/) and capture every non-trivial
architectural choice with Context, Decision, Status, Consequences, and Alternatives Considered.

| # | Title | Status | Summary |
|---|---|---|---|
| [0001](./docs/decision-records/0001-mdc-over-cursorrules.md) | Adopt `.cursor/rules/*.mdc` Over the Legacy `.cursorrules` File | Accepted | The primary Cursor distribution target is per-file MDC, not a concatenated `.cursorrules` (which Agent mode silently ignores). |
| [0002](./docs/decision-records/0002-layer-keyed-source-split.md) | Layer-Keyed Source Split | Accepted | Source files live under `source/<lang>/<framework>/<layer>/<rule>.md`; the layer (`controller`, `service`, `repository`, …) drives glob resolution via `schemas/layer-glob-map.json`. |
| [0003](./docs/decision-records/0003-deferred-mcp-server.md) | Defer the MCP Server to a Post-MVP Roadmap Epic | Accepted | The MVP (Phase 0 → Phase 8) ships static MDC + cross-tool distribution only. The MCP server is roadmap-tracked for Phase 10 with a frozen Resource/Prompt/Tool contract. |
| [0004](./docs/decision-records/0004-single-repo-distribution.md) | Single-Repo Distribution via a Protected `dist/` Folder | Accepted | Source and compiled artifacts both live in this repository; `dist/` is human-read-only via CODEOWNERS, a required CI lint check, branch protection, and a defensive client-side pre-commit hook. A two-repo graduation path is documented. |

## How to Consume the Standards (Future State)

Once Phase 8 ships, a consumer repository will run:

```bash
npx @org/standards-sync
```

The sync command parses the consumer's manifest (`pom.xml` / `build.gradle` / `package.json` /
`pyproject.toml`), selects the appropriate stack (`java-spring-boot-3`, `typescript-nestjs-10`,
`python-fastapi-0-110`, …), and copies the compiled artifacts from this repo's `dist/stacks/<stack>/`
into the right places in the consumer's working tree:

- `.cursor/rules/*.mdc` (per-file-pattern Cursor activation)
- `.github/copilot-instructions.md`
- `CLAUDE.md`
- `.junie/AGENTS.md`
- `AGENTS.md` (universal, ≤150 lines)
- `archunit/` (build-time enforcement tests, Java stacks only)

Detailed consumer-side documentation lands with Phase 8 (`docs/02-implementation-plan.md` §11).

## Repository Layout (Target State)

The full target tree is in `docs/01-architecture-upgrade-report.md` §5.1. Phase 1 scaffolds it;
subsequent phases fill it in. Top-level overview:

```
.
├── docs/                   # ADRs, plans, authoring guide
│   ├── ai-engineering-standards-blueprint.md
│   ├── 01-architecture-upgrade-report.md
│   ├── 02-implementation-plan.md
│   ├── 03-execution-playbook.md
│   ├── decision-records/   # ADRs 0001–0004 (and any future ADRs)
│   └── execution-log/      # Per-phase execution logs + next-session prompt
├── source/                 # Authored rule Markdown (Phase 3+)
├── compiler/               # Python compilation pipeline (Phase 4+)
├── schemas/                # JSON Schemas + layer-glob-map (Phase 2+)
├── dist/                   # ★ Compiled artifacts — read-only to humans (Phase 7+)
├── fixtures/, tests/       # Consumer fixtures + golden snapshots (Phase 6)
├── .github/workflows/      # CI: validate, golden-tests, release, dist-protection-lint
└── .cursor/rules/          # The central repo's own dogfood rules (Phase 1)
```

## Where to Start

- **You want to understand the design** → read the three foundational documents in order.
- **You want to know what decisions have been made and why** → read the ADRs.
- **You want to author a new source rule** → read
  [`docs/authoring-guide.md`](./docs/authoring-guide.md). The two `.cursor/rules/*.mdc`
  checklists auto-attach whenever you edit a `source/**/*.md` file.
- **You want to execute the next phase** → open the playbook and use the prompt in
  [`docs/execution-log/next-session-prompt.md`](./docs/execution-log/next-session-prompt.md).
- **You want to see what's been done so far** → read the logs under
  [`docs/execution-log/`](./docs/execution-log/).
