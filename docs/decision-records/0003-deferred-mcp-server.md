# ADR-0003 — Defer the MCP Server to a Post-MVP Roadmap Epic

- **Status**: Accepted
- **Date**: 2026-05-18
- **Deciders**: Standards Architect, Compiler Engineer, AI Enablement PM (sign-off pending operator review)
- **Phase**: 0 — Pre-Flight Decisions and ADRs
- **Related documents**:
  - `docs/01-architecture-upgrade-report.md` §3.5 ("Model Context Protocol (MCP) Servers — The Live-Query Frontier")
  - `docs/01-architecture-upgrade-report.md` §3.6 (cross-pattern synthesis — MCP positioned as a Phase-3 roadmap item)
  - `docs/02-implementation-plan.md` §13 Task 4 ("MCP server roadmap (deferred from Phase 0)")
  - `docs/02-implementation-plan.md` §14 R-07 (risk register entry for MCP attack surface)

---

## 1. Context

Model Context Protocol (MCP), governed by the Linux Foundation as of late 2025 and powering >10,000 production servers by Q1 2026, standardizes how AI hosts (Cursor, Claude Desktop, Zed, VS Code) discover external **Resources**, **Prompts**, and **Tools** over JSON-RPC 2.0. An MCP server in front of the standards corpus would let any MCP-aware client:

- Fetch any rule by URI (e.g., `engineering://java/spring-boot/controller/validation-boundaries`) on demand, with no local sync.
- Invoke pre-templated review **Prompts** ("Review this controller for Logic Hole #3 violations").
- Call programmatic **Tools** such as `lint_against_standards(file_path) → StructuredViolations[]`.

This is a genuinely strict superset of the static-file distribution model proposed in ADR-0001/ADR-0002/ADR-0004: anything the MDC fan can do, the MCP server can also do, *and* it adds live query, programmatic lint, and authentication-scoped access.

However, the *first* deliverable promise of this project — per `docs/02-implementation-plan.md` §1 Guiding Principle 7 ("Phased adoption, never big-bang") and the MVP definition in §15 — is to put **better AI behavior into developers' hands in under 9 weeks**. The MVP path runs through Phase 0 → Phase 8 (MDC distribution + consumer sync). An MCP server adds new dimensions of complexity that are orthogonal to that path:

1. **A second runtime artifact to operate.** The MDC distribution is static files committed to a Git tag; consumer sync is `npx`-runnable. An MCP server is a long-running JSON-RPC service that must be deployed, monitored, authenticated, scaled, and on-called.
2. **A new attack surface.** A live RPC service exposing the entire corpus and a `lint_against_standards` tool that reads consumer file paths is a security-review boundary that the static distribution does not have. This is tracked as risk **R-07** in `docs/02-implementation-plan.md` §14.
3. **A protocol whose maturity outside Anthropic's reference clients is uneven** at the time of Phase 0. By the time we reach Phase 10, MCP client coverage will be broader and more battle-tested. Building against a moving target during MVP would compound the Cursor MDC drift risk (R-01) without compensating value.

The decision to be recorded: **does the MCP server ship in the MVP path, in parallel with it, or only after MVP is in production?**

---

## 2. Decision

**The MCP server is deferred to Phase 10 as a roadmap epic. The MVP path (Phase 0 → Phase 8) ships only the static MDC + cross-tool distribution.** When the MCP epic is kicked off, it implements the contract recorded below.

Concrete commitments:

- The MDC + Copilot + Claude + Junie + `AGENTS.md` distribution proceeds independently and is the single deliverable promise of the MVP (`docs/02-implementation-plan.md` §15 MVP DoD).
- The MCP server is **roadmap-tracked**, not abandoned. Its kickoff is recorded as an acceptance criterion of Phase 10 (`docs/02-implementation-plan.md` §13 AC: *"MCP-server epic has a kickoff date and named owners"*).
- The MCP server's external contract is **frozen at the Resource/Prompt/Tool shape below** so future implementation work does not relitigate the API design:
  - **Resources** — one per source rule, addressable by URI:
    `engineering://<language>/<framework>/<layer>/<rule-id>`
    Resource content is the canonical source Markdown body (frontmatter stripped) of the rule at the latest released semver. Versioned URIs (`engineering://...@v2.4.0`) are optional but defined.
  - **Prompts** — one per Logic Hole (and per future Logic Hole as the catalog grows). Prompt template name pattern: `review-for-logic-hole-<n>`. Prompt input: the current file or selection. Prompt body: a calibrated review checklist scoped to that Logic Hole's rules.
  - **Tools** — at minimum, `lint_against_standards(file_path: string, stack?: string) → { violations: StructuredViolation[] }`. The `StructuredViolation` shape mirrors what ArchUnit emits so the same data structure flows from build-time (ArchUnit) and runtime (MCP) enforcement paths.
- The static distribution and the MCP server share a single corpus. **Both consume `source/` directly**; the MCP server is *not* allowed to define a parallel rule store. This preserves the "single source of truth" guiding principle (`docs/02-implementation-plan.md` §1.1).
- Implementation language for the MCP server is **explicitly left open** until the kickoff session. Python (consistent with the compiler) and Java (familiar to the Spring-heavy consumer base) are both viable; the choice depends on the deploy target chosen during Phase 10 epic scoping.
- Security & authn/authz design must precede implementation (`docs/02-implementation-plan.md` §14 R-07 mitigation): the MCP epic charter requires a signed-off security review before any production deployment.

---

## 3. Status

**Accepted** — effective 2026-05-18. The contract above is **frozen** for the purposes of forward compatibility; subsequent revisions to it require a superseding ADR (`docs/decision-records/0005-...`). Implementation timing is governed by Phase 10 of the implementation plan. Subject to AI Enablement PM sign-off in the closing Phase 0 PR.

---

## 4. Consequences

### Positive

- **MVP critical path stays short** (~8.5 weeks to MVP per `docs/02-implementation-plan.md` §16). Adding a service tier would push MVP to ~14 weeks at minimum.
- **MVP scope is minimal-surface-area**. Static Git tags + a `npx` sync command is auditable, debuggable, and operationally cheap. No on-call. No service-level objectives to negotiate.
- **The protocol contract is captured now**, so the team that picks up the MCP epic in Phase 10 inherits a clear scope and is not forced to re-derive the Resource/Prompt/Tool shapes under deadline pressure.
- **R-07 (attack surface) is closed for the MVP horizon.** A static file distribution has well-understood threat properties; an MCP service does not.
- **Pilot feedback (Phase 9) can shape the MCP design**. By the time the epic kicks off, we will know which Tools consumer teams actually want, not just which Tools we *guess* they want.

### Negative / Costs

- **Live-query capability ships late.** Teams wanting to ask "which rule fires on this file *right now*" must either wait or run the ArchUnit tests locally. Mitigated by the fact that Cursor MDC's per-glob loading is already a form of live filtering — the gap is narrow.
- **`lint_against_standards` is unavailable in MVP**. The build-time ArchUnit tests (Phase 6) cover the same logic for a Java/Spring consumer; the gap is for non-build runtime queries (e.g., a code-review bot). Mitigated by: (a) ArchUnit tests cover the four Logic Holes that matter most, (b) the bot use case is on the Phase 10 backlog with a defined interface.
- **A future organization decision to standardize on MCP-first AI tooling** could leave us a phase behind. Mitigated by: (a) the contract is frozen now so the MCP epic is short, (b) Phase 10 timing is flexible — if pressure rises, the epic can move earlier as long as MVP DoD is met.
- **Protocol drift between Q2 2026 and the eventual implementation date.** MCP is governed by an open foundation; spec changes are likely. Mitigated by: (a) the frozen contract here is at the *application* level (URIs, prompt names, tool shape), not the *protocol* level — protocol-level changes are absorbed by the MCP client library, (b) the epic charter mandates a fresh spec review at kickoff.

---

## 5. Alternatives Considered

### Alt 5.1 — Build the MCP server in parallel with the MDC pipeline (concurrent MVP)

**Why considered**: Maximum capability at GA; positions the org as MCP-native from day one.

**Why rejected**: Doubles the surface area of the MVP for a capability that pilot teams (Phase 9) have not yet asked for. The MDC pipeline alone delivers the largest single behavior improvement (>70% token reduction, Agent-mode coverage from 0% to 100%). Bundling the MCP server in defers that win behind a service-engineering project. Also conflicts with `docs/02-implementation-plan.md` §1 Guiding Principle 7 (phased adoption).

### Alt 5.2 — Build MCP first, skip static MDC distribution entirely

**Why considered**: MCP is the eventual end state per `docs/01-architecture-upgrade-report.md` §3.5; why ship the intermediate?

**Why rejected**: Three reasons.
1. **Tool coverage**. As of Phase 0, the dominant clients (Cursor in IDE/Agent mode, Copilot, Claude Desktop, Junie) all consume static files reliably; MCP support is uneven. A static-first distribution reaches every developer immediately.
2. **Operational maturity**. A live service requires SLOs, paging, capacity planning. The org's AI Enablement function does not yet have that operational muscle for an AI-content service; the MDC distribution does not require it.
3. **Risk diversification**. If the MCP epic stalls or pivots, the static distribution still works. The reverse is not true.

### Alt 5.3 — Skip MCP entirely (don't even roadmap it)

**Why considered**: YAGNI; the static distribution may suffice indefinitely.

**Why rejected**: Closes the door on real future capability (programmatic lint, live audit, cross-repo migration tooling). The MVP path doesn't *require* MCP, but the long-term governance story (`docs/02-implementation-plan.md` §13 Governance) is materially better with it. The cost of recording a deferred-but-designed contract now is one ADR; the cost of re-deriving it under deadline pressure in Phase 10 is significantly higher.

### Alt 5.4 — Freeze a different protocol shape (e.g., REST-only, no MCP)

**Why considered**: Avoids betting on an emergent protocol.

**Why rejected**: MCP is the standard the host clients we care about (Cursor, Claude Desktop, VS Code, Zed) speak natively as of 2026. A bespoke REST endpoint would be reachable only via custom integrations — every consumer team would have to wire its own bridge. MCP is *the* interop layer here; choosing not to use it eliminates the entire value of a live-query frontier.

---

## 6. References

- `docs/01-architecture-upgrade-report.md` §3.5 — MCP capability analysis and strategic positioning.
- `docs/01-architecture-upgrade-report.md` §3.6 — cross-pattern synthesis identifying MCP as a Phase-3 roadmap item.
- `docs/02-implementation-plan.md` §13 Task 4 — concrete Phase 10 roadmap items: Resource URI scheme, Prompt naming, Tool signature.
- `docs/02-implementation-plan.md` §14 R-07 — risk register entry for MCP attack surface.
- `docs/02-implementation-plan.md` §15 MVP DoD — confirms MCP is **not** required for MVP.
- `decision-records/0001-mdc-over-cursorrules.md` — the static distribution path that ships first.
- `decision-records/0002-layer-keyed-source-split.md` — the source layout that both static and MCP consumers will share.
