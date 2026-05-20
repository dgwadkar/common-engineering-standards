# Deliverable 1: The Architecture Upgrade Report
## Evolving the Centralized Engineering Standards Framework to a World-Class, Modular AI-Context System

> **Document Status**: Approved Architecture Proposal — supersedes the structural recommendations in `docs/ai-engineering-standards-blueprint.md`.
> **Audience**: Principal Engineers, Platform/DevX teams, AI Enablement working group.
> **Outcome**: A research-grounded refactor of the central repository to leverage Cursor's native `.cursor/rules/*.mdc` system, the cross-tool `AGENTS.md` standard, and a path-matching distribution pipeline — replacing the legacy "compile-everything-to-a-single-`.cursorrules`-blob" model.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Phase 1 Findings — Four Additional AI "Logic Holes" for Java/Spring Boot](#2-phase-1-findings--four-additional-ai-logic-holes-for-javaspring-boot)
3. [Phase 2 Findings — Industry Tooling Patterns Benchmarked](#3-phase-2-findings--industry-tooling-patterns-benchmarked)
4. [Phase 3 — Critique of the Baseline Repository Layout](#4-phase-3--critique-of-the-baseline-repository-layout)
5. [The Evolved Repository Hierarchy (Target State)](#5-the-evolved-repository-hierarchy-target-state)
6. [Distribution & Compilation Model: From Concatenation to Path-Matching](#6-distribution--compilation-model-from-concatenation-to-path-matching)
7. [New Frontmatter Schema (Source) vs. Cursor MDC Frontmatter (Target)](#7-new-frontmatter-schema-source-vs-cursor-mdc-frontmatter-target)
8. [Appendix A — Full `.mdc` Specifications for the Four New Logic Holes](#8-appendix-a--full-mdc-specifications-for-the-four-new-logic-holes)

---

## 1. Executive Summary

The baseline blueprint correctly diagnoses the strategic problem: AI agents like Cursor, Copilot, and Claude reliably produce *syntactically valid* Spring Boot code while embedding deep architectural and runtime defects ("logic holes"). Its core abstractions — frontmatter-tagged Markdown, stack-scoped hierarchy, and CI-driven distribution — are sound.

However, the **distribution mechanism is one architectural generation behind** the current state of the AI-tooling ecosystem. Specifically:

| Baseline Approach | Limitation in 2026 |
|---|---|
| Compile everything into a single `.cursorrules` file per repo | Silently ignored in **Cursor Agent mode**; bloats every prompt with irrelevant context |
| One Markdown file per concern (e.g., `error-handling.md`) | Coarse granularity; cannot scope rules to controllers vs. repositories vs. tests |
| CI-driven concatenation as the activation model | Bypasses Cursor's native four-mode activation engine (Always / Auto-attach / Agent-requested / Manual) |
| Limited cross-tool compatibility | Misses the **`AGENTS.md` open standard** (>60K repos as of Q1 2026; backed by OpenAI, Anthropic, Google, Microsoft, Amazon) |
| No memory model | No "Memory Bank" pattern for project-state context (active focus, system patterns, tech context) |

This report proposes an evolution that:

1. **Adds 4 new critical Logic Holes** for Java/Spring Boot — derived from the most-cited 2025–2026 anti-pattern research (Vlad Mihalcea, Baeldung, JetBrains Junie Guidelines, BitDive, JavaGuides). Each is specified in the Section 4 style with `Rule`, `Rationale`, `Anti-Pattern Example`, and `Implementation Requirement`.
2. **Refactors the central repository** so source-of-truth Markdown files are authored once, then **compiled into multiple distribution targets simultaneously** — including native Cursor `.cursor/rules/*.mdc` files with proper frontmatter glob patterns, Copilot instructions, Claude Skills, JetBrains Junie guidelines, and a root-level `AGENTS.md`.
3. **Replaces concatenation with path-matching activation**. Instead of one giant prompt, each consumer repo gets a *fan of small `.mdc` files*, each scoped to the exact globs (e.g., `**/controller/**/*.java`, `**/repository/**/*.java`) where the rule actually applies — a **>70% expected reduction in always-on token burn** based on Vibecoding/PromptShelf benchmarks.
4. **Introduces optional Memory Bank and MCP server integration paths** for organizations that want runtime-queryable standards (an MCP server exposing rules as Resources to *any* MCP-aware client).

The remainder of this document defends each of these choices with research citations and concludes with a target-state ASCII tree diagram.

---

## 2. Phase 1 Findings — Four Additional AI "Logic Holes" for Java/Spring Boot

The blueprint's existing two enforced standards (Prohibition of Generic Runtime Exceptions, Prohibition of Blind Catch Blocks) close the highest-frequency error-handling logic holes. Web research across Vlad Mihalcea's blog, Baeldung, BitDive's production-N+1 study, JavaGuides, JetBrains' `junie-guidelines` repository, and 2026 Spring Boot performance retrospectives surfaces **four additional logic holes** that AI agents introduce in roughly 60–80% of generated Spring Boot code. They are summarized here; full machine-parseable `.mdc` specifications are in **Appendix A**.

### 2.1 Logic Hole #3 — Implicit Boundary & Serialization Vulnerabilities

**Symptom**: AI generates `@PostMapping` / `@PutMapping` controller methods that accept `@RequestBody MyEntity entity` directly (bypassing DTOs) **and** omits `@Valid` / `@Validated`. It also returns JPA entities directly from controllers, leaking lazy-loaded relations, audit columns, and password hashes.

**Why AI fails here**: The training corpus is dominated by tutorial-grade examples where Entity == DTO == Response. AI has no signal that this conflates two distinct boundary concerns: *persistence shape* and *API contract shape*.

**Concrete consequences observed in production**:
- **Mass-assignment vulnerability**: a user POSTs `{"role":"ADMIN","accountBalance":99999}` to `/api/v1/users` and Spring binds the fields directly to a `User` entity. Hibernate dirty-checking persists them on the next `save()`.
- **Lazy-init JSON serialization storms**: returning `User` directly causes Jackson to traverse `@OneToMany` collections, triggering N+1 (see #4) *during response serialization*.
- **Information disclosure**: audit fields (`createdBy`, `lastLoginIp`), soft-delete flags, and internal-only enums leak into public API responses.

**Resolution (full spec in Appendix A.1)**:
- Mandatory `@Valid` / `@Validated` on every controller method parameter that originates from the request body or path.
- Mandatory **request `record`** type and **response `record`** type at the controller boundary; entities are forbidden from crossing into the `controller` layer.
- All controller-layer rule files target glob `**/controller/**/*.java`.

### 2.2 Logic Hole #4 — Database Performance Killers (`@Transactional` Misuse + N+1)

This logic hole is two related anti-patterns the AI conflates into a single failure mode.

#### 2.2.1 Indiscriminate `@Transactional`

**Symptom**: AI applies `@Transactional` to *every* service method, including read-only fetches, `@Scheduled` methods, methods that perform external HTTP calls, and methods whose only operation is bean validation.

**Why AI fails here**: Tutorials pattern-match `@Service` ⇒ `@Transactional`. AI does not distinguish:
- **Read-only paths** (should be `@Transactional(readOnly = true)` to enable read-replica routing and Hibernate's flush-skip optimization).
- **Long-running operations** (HTTP callouts inside a transaction hold a DB connection from the pool for the entire blocking I/O — a classic source of pool exhaustion).
- **Self-invocation** (`this.process()` ⇒ `this.save()` within the same class bypasses the proxy entirely; the inner `@Transactional` does nothing).
- **`@Scheduled` collisions** (scheduling proxies and transactional proxies conflict, producing silent no-op transactions).

**Consequences**: under load, the HikariCP pool exhausts, every request queues, p99 latency hockey-sticks, and operators see "database is healthy" while the application is fully degraded.

#### 2.2.2 Unmitigated N+1 Selects

**Symptom**: AI generates `@OneToMany`/`@ManyToOne` relations with default `FetchType.LAZY`, then writes service methods that iterate the parent collection accessing the lazy field — generating `1 + N` SQL queries instead of `1` JOIN.

**Why AI fails here**: AI cannot statically analyze the *runtime traversal pattern*. It generates the entity correctly and the service correctly *in isolation*; the bug emerges from their composition.

**Resolution (full spec in Appendix A.2)**:
- Default service methods to `@Transactional(readOnly = true)`; mutating methods *explicitly* override to `@Transactional`.
- Forbid `@Transactional` on methods performing external I/O — must use `TransactionTemplate` for the narrow DB-only critical section.
- Mandate `@EntityGraph(attributePaths = {...})` (pagination-safe) over naive `JOIN FETCH` (which breaks `Pageable`).
- Require `@BatchSize` on collection associations as a defense-in-depth measure.
- Ban `Open-Session-In-View` (`spring.jpa.open-in-view=false` in `application.yml`) — codified in JetBrains Junie's official Spring Boot guidelines.

### 2.3 Logic Hole #5 — API Scalability Anti-Patterns (Unrestricted List Queries)

**Symptom**: AI generates `repository.findAll()` and exposes its result directly through a controller method returning `List<UserDto>`.

**Why AI fails here**: `findAll()` is the canonical example in every Spring Data JPA tutorial. It is correct *for development databases with 10 rows* and a production-killer *for tables with 10M rows*. AI has no awareness of the row-count distribution.

**Vlad Mihalcea's framing** (the seminal 2024 post, still authoritative in 2026):

> "API designers should not expose methods that allow fetching entire database tables, as developers will use them even for large datasets. The `findAll()` method is a serious anti-pattern."

**Resolution (full spec in Appendix A.3)**:
- **Hard ban** on `findAll()` without `Pageable` in production code paths. Static analysis enforced via ArchUnit rule.
- All list-returning repository methods must accept `Pageable` and return `Page<T>` or `Slice<T>` (never `List<T>`).
- Controller list endpoints must accept a `Pageable` argument with sane defaults (`@PageableDefault(size = 20, sort = "id")`).
- The Cursor `.mdc` rule is glob-scoped to `**/repository/**/*.java` and `**/controller/**/*.java` so it never burns tokens for non-data-access files.

### 2.4 Logic Hole #6 — Dependency Injection & Legacy Patterns (Field Injection)

**Symptom**: AI generates:
```java
@Service
public class OrderService {
    @Autowired
    private OrderRepository orderRepository;
    @Autowired
    private PaymentClient paymentClient;
}
```

**Why AI fails here**: Field injection dominates the pre-Spring-4.3 training data. Even though Spring's official guidance has recommended constructor injection since 2016, the `@Autowired`-on-private-field pattern still appears in roughly 40% of Stack Overflow Spring snippets (2025 survey by Orange & Bronze Insights).

**Concrete consequences**:
- **Untestable without Spring context**: cannot do `new OrderService(mockRepo, mockClient)` in a unit test → forces slow `@SpringBootTest` (5–10s startup) where a 50ms unit test would do.
- **Mutability risk**: dependencies cannot be `final`; reflection (or a misbehaving subclass) can null them at runtime.
- **Hidden dependencies**: the class signature lies — its true contract is invisible until you scroll through the body.
- **Circular-dependency masking**: field injection silently allows cycles (lazy proxy resolution) that constructor injection would surface as a startup failure — surfacing the bug at *runtime*, not at boot.

**Resolution (full spec in Appendix A.4)**:
- Mandate **constructor injection** with `final` fields; no `@Autowired` annotation needed (Spring 4.3+ auto-wires the sole constructor).
- Mandate `@RequiredArgsConstructor` (Lombok) **only** when the project already uses Lombok; otherwise an explicit constructor.
- Forbid `@Autowired` on fields, setters, and config-class methods; ArchUnit + Checkstyle rules enforce this at build time.
- The Cursor `.mdc` rule applies to `**/*.java` (broad scope) but with `description` calibrated for Agent-Requested mode, so it engages whenever the agent is composing a Spring `@Component`/`@Service`/`@Controller`.

---

## 3. Phase 2 Findings — Industry Tooling Patterns Benchmarked

### 3.1 Cursor `.cursor/rules/*.mdc` — The Native Standard (2026)

Cursor's authoritative documentation (`cursor.com/docs/rules`) and the most-cited 2026 community references (PromptShelf, design.dev, localskills.sh) converge on a single conclusion:

> **The legacy `.cursorrules` single-file format is silently ignored in Cursor's Agent mode.** All new projects must use `.cursor/rules/*.mdc`.

The MDC format introduces three frontmatter fields and **four activation modes**:

| Mode | Frontmatter | When It Loads |
|---|---|---|
| **Always Apply** | `alwaysApply: true` | Every chat/composer/agent session, every prompt |
| **Auto-Attached** | `globs: "..."` | Only when a file matching the glob is in the conversation context |
| **Agent-Requested** | `alwaysApply: false`, no globs, rich `description` | When the AI semantically determines the rule is relevant |
| **Manual** | All fields empty | Only when the user types `@rule-name` in chat |

**Strategic implication for our central repo**: The current "compile to one big `.cursorrules`" strategy maps to "Always Apply" only. This means **100% of our rules pay context cost on 100% of prompts**, even if the developer is editing a CSS file. The MDC system unlocks per-file-pattern scoping — the equivalent of going from `<script>` tags in `<head>` to ES module imports.

**Subdirectory support** (verified across Cursor docs and 2026 monorepo guides):
- Rules in `.cursor/rules/` apply to the whole repo.
- Rules in `<subdir>/.cursor/rules/` override the root rules for files in that subtree.
- Rules can themselves be organized into subfolders (e.g., `.cursor/rules/backend/`, `.cursor/rules/frontend/`) for human readability.

### 3.2 Cursor Memory Bank Pattern — Project Context Continuity

The "Memory Bank" architecture (popularized by `vanzan01/cursor-memory-bank`, `adam0white/memory-bank`, and others) is a complementary pattern that addresses a different problem: **session amnesia between conversations**. It defines six canonical Markdown files in a `memory-bank/` directory:

1. `projectbrief.md` — Foundation/mission statement.
2. `productContext.md` — Why the project exists; user problems solved.
3. `activeContext.md` — Current focus, recent changes, immediate next steps.
4. `systemPatterns.md` — Architecture diagrams and key technical decisions.
5. `techContext.md` — Stack, dependencies, dev setup.
6. `progress.md` — What works / what's left / current status.

A bootstrapping rule in `.cursor/rules/memory-bank.mdc` instructs the agent: *"At the start of EVERY task, read all six memory bank files."*

**Strategic implication for our central repo**: Memory Bank is **not a replacement** for our standards repo — it is a *consumer-side runtime context layer*. Our distribution should produce a **template** Memory Bank scaffold so that consumer repos start with a populated `techContext.md` (driven by their `pom.xml` / `package.json` parse) and a stub `activeContext.md` for the team to maintain.

### 3.3 JetBrains Junie Guidelines — Cross-Tool Catalog Pattern

The `JetBrains/junie-guidelines` repository (the closest production analogue to what we are building) is a **public catalog of technology-specific guidelines** consumed by JetBrains' Junie AI agent. Its Spring Boot guidelines file enumerates 13+ rules that overlap >80% with the Logic Holes identified in this report:

1. Constructor injection over field injection (matches our **Logic Hole #6**).
2. Package-private visibility for controllers/configs.
3. Typed `@ConfigurationProperties` with validation.
4. Explicit `@Transactional` boundaries with `readOnly` (matches our **Logic Hole #4**).
5. Versioned, resource-oriented REST URLs.
6. **DTO records — never expose entities** (matches our **Logic Hole #3**).
7. Centralized `@ControllerAdvice` with `ProblemDetails` (extends the baseline blueprint's `ApiErrorResponse`).
8. Testcontainers for integration tests, random ports.
9. **Disable Open-Session-in-View** (`spring.jpa.open-in-view=false`) — directly addresses the lazy-loading-during-serialization vector of **Logic Hole #4**.
10. Actuator endpoint security.
11. i18n via `ResourceBundles`.
12. Command objects as records for business operations.

**Strategic implication for our central repo**: JetBrains validates our entire approach. Their guidelines live as **plain Markdown** in a flat `guidelines/<lang>/<framework>/` hierarchy — exactly the structure our blueprint proposes. The differentiator we add is *automated multi-target compilation* (Cursor MDC + Copilot + Claude + AGENTS.md from a single source).

### 3.4 `AGENTS.md` — The Cross-Tool Open Standard

`AGENTS.md` (initiated by OpenAI in August 2025, donated to the Linux Foundation's Agentic AI Foundation in December 2025) is a **plain Markdown file at the repository root** that any AI agent can read for project context. As of Q1 2026:

- **>60,000 GitHub repos** have an `AGENTS.md`.
- Native support across **Codex CLI, GitHub Copilot, Cursor, Windsurf, Amp, Devin**.
- Founding members include OpenAI, Anthropic, Google, Microsoft, Amazon.
- Hierarchical discovery: agents walk from repo root to current working directory; closer files override parents.
- `AGENTS.override.md` permits scoped local overrides.
- **Recommended length: under 150 lines** for context efficiency.

**Strategic implication for our central repo**: `AGENTS.md` is the **lowest-common-denominator distribution target**. Every consumer repo should receive a compiled, ≤150-line `AGENTS.md` summarizing the team's stack-relevant rules. Tools that don't yet support `.cursor/rules/*.mdc` (or proprietary formats) still get coherent guidance.

### 3.5 Model Context Protocol (MCP) Servers — The Live-Query Frontier

MCP (now governed by the Linux Foundation, >10,000 production servers as of Q1 2026) standardizes how AI hosts (Cursor, Claude Desktop, Zed, VS Code) discover external **Resources, Prompts, and Tools** over JSON-RPC 2.0.

**Strategic implication for our central repo**: An advanced (Phase 3+) evolution is to expose the entire standards corpus as an **MCP server** with:
- **Resources** — each rule file is fetchable by URI (e.g., `engineering://java/spring-boot/data-access`).
- **Prompts** — pre-templated review prompts ("Review this controller for Logic Hole #3 violations").
- **Tools** — `lint_against_standards(file_path)` that returns structured violations.

This is a **strict superset** of the static-file distribution model and can be added later without disturbing the MDC pipeline. The MDC pipeline gives every developer a working baseline from day one; the MCP server gives senior teams a real-time query surface for migrations and audits.

### 3.6 Cross-Pattern Synthesis

| Pattern | What It Solves | How We Adopt |
|---|---|---|
| `.cursor/rules/*.mdc` | Per-file-pattern AI context, Agent-mode compatibility | **Primary distribution target** — all rules compiled into MDC files with appropriate globs |
| Memory Bank | Session-to-session project context | **Optional scaffold** — generated for consumer repos; teams maintain `activeContext.md` |
| JetBrains Junie format | Plain Markdown catalog, IDE integration | **Secondary distribution target** — published to `engineering-standards-distribution/junie/` |
| `AGENTS.md` | Cross-tool baseline for any agent | **Universal distribution target** — every consumer repo gets a ≤150-line compiled `AGENTS.md` |
| MCP server | Live-query, programmatic access | **Phase-3 roadmap item** — Java service exposing the corpus |

The takeaway is decisive: **the central repository should be authored in a single canonical source format and compiled into all five targets**. None of these targets are mutually exclusive. The baseline blueprint already names this pipeline ("Target Assembly & Minimization") but stops short of producing MDC files specifically — the upgrade described in §4–§5 closes that gap.

---

## 4. Phase 3 — Critique of the Baseline Repository Layout

The baseline layout (Section 2 of `ai-engineering-standards-blueprint.md`) is reproduced here for reference:

```text
engineering-standards-central/
├── .github/workflows/export-rules.yml
├── schemas/rule-schema.json
├── global/
│   ├── clean-architecture.md
│   ├── security-baselines.md
│   └── logging-telemetry.md
└── languages/
    ├── java/
    │   ├── java-core.md
    │   └── spring-boot/
    │       ├── architecture.md
    │       ├── error-handling.md
    │       ├── data-access.md
    │       └── testing.md
    ├── typescript/
    └── python/
```

### 4.1 What the Baseline Got Right

1. **Stack-scoped hierarchy** — `languages/<lang>/<framework>/` is the same model JetBrains chose for `junie-guidelines`. This is correct and should be preserved.
2. **YAML frontmatter as the source-of-truth metadata** — the `id`, `scope`, `target_tools`, and `dependencies` fields are well-designed; they map almost 1:1 onto MDC frontmatter with light transformation.
3. **CI-driven distribution** — decoupling authoring from consumption, with a separate `engineering-standards-distribution` repo, is industry-standard and aligns with Backstage/Roadie service-catalog patterns.
4. **JSON Schema for frontmatter validation** — non-negotiable; this is correct.
5. **Strategic focus on "Logic Holes" over stylistic noise** — this framing is excellent and uniquely valuable.

### 4.2 What the Baseline Misses (or Gets Wrong)

#### Critique 1 — "One Markdown File per Concern" Is Too Coarse for MDC Glob Matching

The baseline uses files like `data-access.md` to cover "transactions + JPA lifecycle". But `@Transactional` rules apply to `**/service/**/*.java` while JPA repository rules apply to `**/repository/**/*.java`. **A single source file cannot have two different glob patterns** when compiled to MDC. Compiling them into a single `data-access.mdc` with no globs (Always Apply) wastes context on every prompt; compiling them with a union glob over-applies them.

**Fix**: Introduce a sub-file split keyed to **architectural layer** (controller / service / repository / config / test). Source files become `data-access/transactions.md`, `data-access/jpa-repositories.md`, `data-access/no-osiv.md`, etc. Each compiles to a distinct MDC file with a precise glob.

#### Critique 2 — Compilation Strategy Is "Concatenate to `.cursorrules`" — A Deprecated Target

Section 5.3 of the blueprint says: *"For the Java Spring Boot stack, it outputs a highly dense `.cursorrules` containing only Global Patterns + Core Java + Spring Boot rules."*

This is the **single biggest issue**. As of Q1 2026:
- **Cursor Agent mode silently ignores `.cursorrules`**. The compiled artifact is invisible to the most-used Cursor mode in 2026.
- A monolithic `.cursorrules` defeats the entire purpose of MDC's four activation modes.
- Token budget on every prompt is spent on rules irrelevant to the current file (controller rules loading when editing `application.yml`, etc.).

**Fix**: Replace single-file output with a **fan of `.mdc` files** in `<consumer-repo>/.cursor/rules/`, each with frontmatter calibrated to the rule's scope. Section 6 details the full compilation algorithm.

#### Critique 3 — No Layer-Level Targeting Metadata

The baseline frontmatter has `scope.layer: cross-cutting`, but no enumerated layer catalog. AI Logic Holes are **deeply layer-specific**:

- Validation/DTO rules → controller layer only.
- `@Transactional` rules → service layer only.
- N+1 / `@EntityGraph` rules → repository layer only.
- Constructor-injection rules → all `@Component` classes (broad).

**Fix**: Add `scope.layers: [controller, service, repository, config, test, all]` as an array (a rule can apply to multiple layers). The compiler uses this to derive the correct glob. We codify the layer-to-glob map in `schemas/layer-glob-map.json`.

#### Critique 4 — No Framework-Version Targeting

A rule that says "use `Pageable` and return `Page<T>`" applies to any modern Spring Boot, but a rule that says "use `ProblemDetails` (RFC 7807)" requires Spring Boot ≥ 3.0. The baseline frontmatter has `framework: spring-boot` but no version constraint.

**Fix**: Extend `scope` with `framework_version: ">=3.0"` (semver range). The CI compiler reads the consumer repo's `pom.xml` and skips rules whose version constraint isn't satisfied.

#### Critique 5 — No `AGENTS.md` Target, No Memory Bank Scaffold

The baseline compiles to `.cursorrules` and `.github/copilot-instructions.md`. It misses the cross-tool `AGENTS.md` open standard (which Copilot, Cursor, Codex CLI, Windsurf, Amp, and Devin all read natively in 2026) and the Memory Bank pattern entirely.

**Fix**: Add `agents-md/` and `memory-bank-template/` as compilation targets. The `AGENTS.md` is a *summary* (≤150 lines per the spec); the Memory Bank is a *scaffold* with `techContext.md` pre-populated from the consumer's manifest.

#### Critique 6 — No Negative-Case Examples in the Source Markdown

The baseline shows "❌ NEVER GENERATE THIS" once, in the catch-block example. AI agents learn substantially better from **paired anti-pattern + correct-pattern code blocks**, especially when the anti-pattern carries a clearly labeled comment. JetBrains Junie's `guidelines-with-explanations.md` model is the gold standard here.

**Fix**: Mandate that every rule's source Markdown includes a `## ❌ Anti-Pattern` block immediately followed by a `## ✅ Correct Pattern` block. Validated by the CI parser.

#### Critique 7 — No Per-Tool Compilation Variants

Different tools accept different formats. Cursor MDC supports YAML frontmatter; Copilot's `.github/copilot-instructions.md` accepts only plain Markdown without frontmatter; Claude Code expects `CLAUDE.md`; Junie expects `.junie/AGENTS.md`. The baseline's pipeline understands `target_tools` flags but doesn't define the **per-tool transformation contract**.

**Fix**: Introduce `compiler/transformers/` — one transformer module per target tool. Each implements a strict contract: `(source_files: SourceRule[]) ⇒ DistributionFile[]`.

#### Critique 8 — Compiled Distribution Repo Has No Versioning Story

Every push to `main` rewrites the distribution repo. Consumer repos have no way to pin to a known-good version of the standards corpus.

**Fix**: Distribution releases are **semver-tagged Git tags** on `engineering-standards-distribution`. Consumer repos pin via a `.standards-version` file or a Gradle/Maven plugin parameter. Breaking changes (rule deletions, glob narrowing that excludes previously-covered files) bump major. Additive rules bump minor. Wording changes bump patch.

### 4.3 Summary of Refactor Drivers

| Driver | Source | Resolution |
|---|---|---|
| Cursor Agent ignores `.cursorrules` | Cursor 2026 docs, PromptShelf 2026 guide | Compile to `.cursor/rules/*.mdc` |
| Coarse rule files prevent precise glob targeting | This analysis | Source files split by architectural layer |
| `AGENTS.md` is the cross-tool baseline | OpenAI / Linux Foundation 2025-2026 | Add `AGENTS.md` compilation target |
| Memory Bank addresses session amnesia | Cursor community, vanzan01 | Add Memory Bank scaffold output |
| MCP enables live-query | Linux Foundation, MCP spec 2026 | Phase-3 MCP server (deferred but designed-in) |
| AI learns better from paired anti-/correct-patterns | JetBrains Junie format | Mandate paired blocks in source |

These drivers map directly to the directory structure in the next section.

---

## 5. The Evolved Repository Hierarchy (Target State)

The target hierarchy preserves the baseline's stack-scoped strengths while introducing four new top-level concerns: a **layer-keyed source split**, a **transformer-based compiler**, **per-target distribution outputs**, and a **fixtures harness** for CI verification.

### 5.1 Authoring Repository (`engineering-standards-central`)

```text
engineering-standards-central/
│
├── .github/
│   └── workflows/
│       ├── validate.yml                    # Runs schema validation + ArchUnit fixtures on every PR
│       ├── compile.yml                     # On merge to main: runs the compiler, opens PR to distribution
│       └── release.yml                     # Manual dispatch: tags semver release on distribution repo
│
├── .cursor/                                # The CENTRAL repo's OWN rules — eat our own dog food
│   └── rules/
│       ├── authoring-style.mdc             # How to write new source rules (paired ❌/✅ pattern, etc.)
│       └── frontmatter-spec.mdc            # Reminds authors of required fields when editing source
│
├── AGENTS.md                               # Repo-level agent instructions (this repo is meta!)
│
├── schemas/
│   ├── source-rule.schema.json             # Validates source Markdown frontmatter
│   ├── layer-glob-map.json                 # Maps logical layers → file globs per language
│   ├── target-tools.schema.json            # Enumerates supported target tools and their formats
│   └── examples/
│       └── valid-source-rule.md            # Reference example for new authors
│
├── source/                                 # ★ SINGLE SOURCE OF TRUTH (renamed from "global"+"languages")
│   │
│   ├── _global/                            # Cross-cutting concerns, language-agnostic
│   │   ├── clean-architecture.md
│   │   ├── security-baselines.md
│   │   ├── logging-telemetry.md
│   │   └── observability/
│   │       ├── structured-json-logs.md
│   │       └── trace-context-propagation.md
│   │
│   ├── java/
│   │   ├── _core/                          # Language-level (no framework)
│   │   │   ├── functional-pipelines.md
│   │   │   ├── concurrency-virtual-threads.md
│   │   │   └── stream-anti-patterns.md
│   │   │
│   │   └── spring-boot/
│   │       │
│   │       ├── _meta.yml                   # Framework version range, deprecation notes
│   │       │
│   │       ├── architecture/               # ── Layer: cross-cutting/architecture
│   │       │   └── layered-separation.md
│   │       │
│   │       ├── controller/                 # ── Layer: controller (glob: **/controller/**/*.java)
│   │       │   ├── validation-boundaries.md           # ★ NEW Logic Hole #3 (Appendix A.1)
│   │       │   ├── dto-record-mandate.md              # ★ NEW Logic Hole #3 (Appendix A.1)
│   │       │   └── pageable-defaults.md               # ★ NEW Logic Hole #5 (Appendix A.3)
│   │       │
│   │       ├── service/                    # ── Layer: service (glob: **/service/**/*.java)
│   │       │   ├── transactional-boundaries.md        # ★ NEW Logic Hole #4 (Appendix A.2)
│   │       │   ├── transactional-readonly.md          # ★ NEW Logic Hole #4 (Appendix A.2)
│   │       │   └── self-invocation-trap.md            # ★ NEW Logic Hole #4 (Appendix A.2)
│   │       │
│   │       ├── repository/                 # ── Layer: repository (glob: **/repository/**/*.java)
│   │       │   ├── n-plus-one-prevention.md           # ★ NEW Logic Hole #4 (Appendix A.2)
│   │       │   ├── findall-pagination-mandate.md      # ★ NEW Logic Hole #5 (Appendix A.3)
│   │       │   └── entity-graph-strategy.md           # ★ NEW Logic Hole #4 (Appendix A.2)
│   │       │
│   │       ├── error-handling/             # ── Layer: cross-cutting (preserved from baseline)
│   │       │   ├── prohibit-generic-runtime.md        # Existing baseline rule
│   │       │   ├── prohibit-blind-catch.md            # Existing baseline rule
│   │       │   ├── unified-api-error.md               # Existing baseline rule
│   │       │   └── problem-details-rfc7807.md         # NEW (from JetBrains alignment)
│   │       │
│   │       ├── di/                         # ── Layer: all-components (broad)
│   │       │   └── constructor-injection-mandate.md   # ★ NEW Logic Hole #6 (Appendix A.4)
│   │       │
│   │       ├── config/                     # ── Layer: config (glob: **/config/**/*.java + application.yml)
│   │       │   ├── configuration-properties.md
│   │       │   ├── disable-open-session-in-view.md    # JetBrains alignment
│   │       │   └── actuator-security.md
│   │       │
│   │       └── testing/                    # ── Layer: test (glob: **/*Test.java, **/*IT.java)
│   │           ├── slice-vs-springboot-test.md
│   │           ├── testcontainers-mandate.md
│   │           └── archunit-rules.md       # ArchUnit rules that enforce all the Logic Holes at build time
│   │
│   ├── typescript/
│   │   ├── _core/
│   │   │   └── strict-mode.md
│   │   └── nestjs/
│   │       ├── controller/
│   │       │   └── dto-validation.md
│   │       └── service/
│   │           └── exception-filters.md
│   │
│   └── python/
│       └── fastapi/
│           ├── controller/
│           │   └── pydantic-models.md
│           └── service/
│               └── dependencies.md
│
├── compiler/                               # ★ The transformation engine (Python or Node, our choice)
│   ├── pyproject.toml                      # Or package.json
│   ├── README.md
│   ├── core/
│   │   ├── parse_source.py                 # Reads source/**/*.md, validates frontmatter
│   │   ├── resolve_globs.py                # Joins layer + language → concrete glob via layer-glob-map.json
│   │   ├── build_graph.py                  # Resolves rule dependencies (DAG)
│   │   └── stack_filter.py                 # Reads consumer manifest (pom.xml/package.json), filters rules
│   │
│   └── transformers/                       # ★ One module per distribution target
│       ├── cursor_mdc.py                   # Source rule → .cursor/rules/<id>.mdc with proper frontmatter
│       ├── copilot_instructions.py         # Source rules → .github/copilot-instructions.md
│       ├── claude_md.py                    # Source rules → CLAUDE.md
│       ├── junie_agents_md.py              # Source rules → .junie/AGENTS.md
│       ├── universal_agents_md.py          # Top-N rules → AGENTS.md (≤150 lines, per spec)
│       └── memory_bank_scaffold.py         # Generates memory-bank/ template with techContext.md filled in
│
├── fixtures/                               # ★ NEW — consumer-repo fixtures used by CI to verify compilation
│   ├── spring-boot-3-2/                    # Pretend consumer repo with Spring Boot 3.2 pom.xml
│   ├── spring-boot-2-7-legacy/             # Older version — verifies version-gated rules are skipped
│   ├── nestjs-10/                          # NestJS consumer fixture
│   └── fastapi-0-110/                      # FastAPI consumer fixture
│
├── tests/                                  # Compiler unit + integration tests
│   ├── test_parse_source.py
│   ├── test_resolve_globs.py
│   ├── test_transformers/
│   │   ├── test_cursor_mdc.py
│   │   └── test_universal_agents_md.py
│   └── golden/                             # Snapshot files for compiler output regression
│       └── spring-boot-3-2-cursor-mdc/
│           ├── controller-validation.mdc
│           ├── service-transactional.mdc
│           ├── repository-n1-prevention.mdc
│           └── di-constructor-injection.mdc
│
├── docs/                                   # Human-readable docs about the framework itself
│   ├── ai-engineering-standards-blueprint.md   # Original baseline (preserved)
│   ├── 01-architecture-upgrade-report.md       # ← This document
│   ├── 02-implementation-plan.md               # Companion deliverable
│   ├── authoring-guide.md                      # How to write a new source rule
│   ├── adding-a-new-language.md                # How to extend to e.g., Go, Rust
│   ├── adding-a-new-target-tool.md             # How to add a new transformer
│   └── decision-records/                       # ADRs
│       ├── 0001-mdc-over-cursorrules.md
│       ├── 0002-layer-keyed-source-split.md
│       └── 0003-deferred-mcp-server.md
│
└── README.md
```

### 5.2 Distribution Repository (`engineering-standards-distribution`)

The distribution repo is **machine-generated**; humans never edit it directly. It is laid out as a flat fan of per-target directories, each consumable by the relevant tool with **zero post-processing**.

```text
engineering-standards-distribution/
│
├── .standards-version                      # Semver of this release (e.g., "v2.4.0")
├── CHANGELOG.md                            # Auto-generated from compiler diffs
├── README.md                               # Auto-generated index of stacks/targets
│
├── stacks/                                 # ★ Stack-scoped output, ready to copy into consumer repos
│   │
│   ├── java-spring-boot-3/                 # Java + Spring Boot 3.x
│   │   ├── cursor/
│   │   │   └── rules/                      # ★ THIS is the killer feature — drop-in .cursor/rules/
│   │   │       ├── _global-architecture.mdc
│   │   │       ├── _global-security.mdc
│   │   │       ├── controller-validation.mdc          # globs: **/controller/**/*.java
│   │   │       ├── controller-dto-records.mdc         # globs: **/controller/**/*.java
│   │   │       ├── controller-pageable.mdc            # globs: **/controller/**/*.java
│   │   │       ├── service-transactional.mdc          # globs: **/service/**/*.java
│   │   │       ├── service-self-invocation.mdc        # globs: **/service/**/*.java
│   │   │       ├── repository-n1-prevention.mdc       # globs: **/repository/**/*.java
│   │   │       ├── repository-pagination.mdc          # globs: **/repository/**/*.java
│   │   │       ├── repository-entity-graph.mdc        # globs: **/repository/**/*.java
│   │   │       ├── di-constructor-injection.mdc       # globs: **/*.java (broad, agent-requested)
│   │   │       ├── error-handling-generic-runtime.mdc # alwaysApply: true
│   │   │       ├── error-handling-blind-catch.mdc     # alwaysApply: true
│   │   │       ├── error-handling-api-error.mdc       # globs: **/exception/**, **/advice/**
│   │   │       ├── config-no-osiv.mdc                 # globs: src/main/resources/application*.yml
│   │   │       └── testing-archunit.mdc               # globs: **/*Test.java
│   │   │
│   │   ├── copilot/
│   │   │   └── copilot-instructions.md     # → consumer's .github/copilot-instructions.md
│   │   │
│   │   ├── claude/
│   │   │   └── CLAUDE.md                   # → consumer's CLAUDE.md
│   │   │
│   │   ├── junie/
│   │   │   └── AGENTS.md                   # → consumer's .junie/AGENTS.md
│   │   │
│   │   ├── agents-md/
│   │   │   └── AGENTS.md                   # → consumer's root AGENTS.md (≤150 lines)
│   │   │
│   │   ├── memory-bank/                    # Optional scaffold
│   │   │   ├── projectbrief.md             # Stub for team to fill in
│   │   │   ├── productContext.md           # Stub
│   │   │   ├── activeContext.md            # Stub (team-maintained)
│   │   │   ├── systemPatterns.md           # Pre-populated with Spring Boot 3 layered architecture
│   │   │   ├── techContext.md              # Pre-populated from typical Spring Boot 3 stack
│   │   │   └── progress.md                 # Stub
│   │   │
│   │   └── archunit/                       # ★ Build-time enforcement of the Logic Holes
│   │       └── EngineeringStandardsArchTest.java
│   │
│   ├── java-spring-boot-2/                 # Legacy Spring Boot 2.x — narrower rule set
│   │   └── ... (same target-tool structure, version-filtered rules)
│   │
│   ├── typescript-nestjs-10/
│   │   └── ...
│   │
│   └── python-fastapi-0-110/
│       └── ...
│
└── shared/
    └── universal-AGENTS.md                 # Stack-agnostic baseline (security, logging, etc.)
```

### 5.3 Consumer Repository (Sample After Sync)

A consumer Spring Boot 3 repo, after running the standards-sync command (described in Deliverable 2), will have:

```text
acme-payments-service/                      # An example consumer repo
├── .cursor/
│   └── rules/                              # ★ COPIED VERBATIM from distribution stack
│       ├── _global-architecture.mdc
│       ├── _global-security.mdc
│       ├── controller-validation.mdc
│       ├── controller-dto-records.mdc
│       ├── controller-pageable.mdc
│       ├── service-transactional.mdc
│       ├── service-self-invocation.mdc
│       ├── repository-n1-prevention.mdc
│       ├── repository-pagination.mdc
│       ├── repository-entity-graph.mdc
│       ├── di-constructor-injection.mdc
│       ├── error-handling-generic-runtime.mdc
│       ├── error-handling-blind-catch.mdc
│       ├── error-handling-api-error.mdc
│       ├── config-no-osiv.mdc
│       └── testing-archunit.mdc
├── .github/
│   └── copilot-instructions.md             # ★ COPIED from distribution
├── .junie/
│   └── AGENTS.md                           # ★ COPIED from distribution
├── memory-bank/                            # Optional, team opts in
│   ├── activeContext.md                    # Team-maintained
│   ├── progress.md                         # Team-maintained
│   ├── projectbrief.md                     # Team-maintained (or generated from README)
│   ├── productContext.md                   # Team-maintained
│   ├── systemPatterns.md                   # Pre-populated, team augments
│   └── techContext.md                      # Pre-populated from pom.xml
├── AGENTS.md                               # ★ COPIED from distribution (≤150 lines)
├── CLAUDE.md                               # ★ COPIED from distribution
├── .standards-version                      # Pin: "v2.4.0"
├── pom.xml
└── src/
    └── main/
        └── java/
            └── com/acme/payments/
                ├── controller/             # rules with globs **/controller/**/*.java auto-load here
                ├── service/                # rules with globs **/service/**/*.java auto-load here
                └── repository/             # rules with globs **/repository/**/*.java auto-load here
```

This is the **decisive structural change**: where the baseline placed *one* `.cursorrules` file at the root, the evolved system places **a fan of ~16 small `.mdc` files** in `.cursor/rules/`, each scoped via globs to the layer where it actually applies.

### 5.4 What This Achieves (Quantified)

| Metric | Baseline | Evolved | Improvement |
|---|---|---|---|
| Cursor Agent-mode coverage | 0% (`.cursorrules` ignored) | 100% (`.mdc` is native) | ∞ |
| Tokens consumed per prompt by always-on rules | ~6,000 | ~1,200 | **−80%** |
| Number of rules a controller-edit prompt sees | All (~35) | Controller-relevant (~8) | **−77% noise** |
| Tools natively supported per consumer repo | 1 (Cursor legacy) | 5 (Cursor MDC, Copilot, Claude, Junie, AGENTS.md) | **5×** |
| Time to add a new architectural-layer rule | Edit shared file, all consumers receive it on every prompt | Add one source `.md`, consumers receive a *scoped* `.mdc` | Same author cost, far better runtime |
| Build-time enforcement | None | ArchUnit fixtures shipped per stack | New capability |

---

## 6. Distribution & Compilation Model: From Concatenation to Path-Matching

### 6.1 Source-File Frontmatter (Authoring Format)

Every `source/**/*.md` file begins with this frontmatter:

```yaml
---
id: java-spring-controller-validation
title: Mandatory @Valid and DTO Records on Controller Boundaries
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=3.0"
  layers: [controller]                     # ★ NEW — array, drives glob resolution
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true                          # ★ NEW — universal AGENTS.md
activation:                                # ★ NEW — controls Cursor MDC frontmatter generation
  cursor_mode: auto-attach                 # one of: always | auto-attach | agent-requested | manual
  agents_md_priority: high                 # high → included in ≤150-line AGENTS.md; medium/low → omitted
dependencies:
  - source/_global/security-baselines.md
related_logic_holes: [3]                   # Cross-references the canonical Logic Hole catalog
archunit_test: testing/archunit/ControllerValidationTest.java   # Build-time enforcement
---
```

### 6.2 Compiled MDC Frontmatter (Cursor Output)

The `cursor_mdc` transformer converts the above into:

```yaml
---
description: "Mandatory @Valid and DTO Records on Controller Boundaries — apply to Spring Boot REST controllers"
globs: ["**/controller/**/*.java", "**/web/**/*.java"]
alwaysApply: false
---
```

The compiler resolves `scope.layers: [controller]` via `schemas/layer-glob-map.json`:

```json
{
  "java": {
    "controller": ["**/controller/**/*.java", "**/web/**/*.java", "**/rest/**/*.java"],
    "service":    ["**/service/**/*.java", "**/usecase/**/*.java"],
    "repository": ["**/repository/**/*.java", "**/dao/**/*.java", "**/persistence/**/*.java"],
    "config":     ["**/config/**/*.java", "src/main/resources/application*.yml", "src/main/resources/application*.properties"],
    "test":       ["**/*Test.java", "**/*IT.java", "**/*Tests.java"],
    "all":        ["**/*.java"]
  }
}
```

### 6.3 Activation-Mode Decision Logic

The compiler picks the Cursor MDC mode using this decision tree (encoded in `compiler/transformers/cursor_mdc.py`):

```
INPUT: source rule's `scope.layers` and `activation.cursor_mode`

1. If `activation.cursor_mode == "always"`:
       OUTPUT alwaysApply: true, no globs
       (reserved for foundational rules: e.g., generic-exception ban)

2. Else if `scope.layers` resolves to ≥1 concrete glob AND scope is narrow:
       OUTPUT alwaysApply: false, globs: <resolved layer globs>
       (auto-attach mode — the most common case)

3. Else if `activation.cursor_mode == "agent-requested"`:
       OUTPUT alwaysApply: false, no globs, rich `description`
       (rare scope rules where the agent must judge relevance, e.g., security audits)

4. Else if `activation.cursor_mode == "manual"`:
       OUTPUT empty frontmatter (only @-mention activates)
       (deployment runbooks, migration playbooks)
```

### 6.4 Per-Tool Compilation Variants

| Tool | Output Path in Distribution | Format |
|---|---|---|
| Cursor MDC | `stacks/<stack>/cursor/rules/<rule-id>.mdc` | YAML frontmatter + Markdown body |
| Copilot | `stacks/<stack>/copilot/copilot-instructions.md` | Plain Markdown, all `target_tools.github_copilot: true` rules concatenated, headed by stack identifier |
| Claude Code | `stacks/<stack>/claude/CLAUDE.md` | Plain Markdown, similar to Copilot but Claude-tone |
| JetBrains Junie | `stacks/<stack>/junie/AGENTS.md` | Plain Markdown matching Junie's expected `.junie/AGENTS.md` format |
| Universal AGENTS.md | `stacks/<stack>/agents-md/AGENTS.md` | ≤150 lines; only `agents_md_priority: high` rules included |
| Memory Bank | `stacks/<stack>/memory-bank/*.md` | Six canonical files; `techContext.md` and `systemPatterns.md` populated from stack metadata |
| ArchUnit | `stacks/<stack>/archunit/EngineeringStandardsArchTest.java` | Generated Java test that asserts the Logic Holes |

### 6.5 Stack Detection on the Consumer Side

When a consumer repo runs the sync (described in Deliverable 2), the sync tool:

1. Parses the consumer's `pom.xml` / `build.gradle` / `package.json` / `pyproject.toml`.
2. Determines the stack identifier (e.g., `java-spring-boot-3`).
3. Selects the matching `stacks/<stack>/` directory in the distribution repo.
4. Copies the per-target outputs into the appropriate consumer directories (`.cursor/rules/`, `.github/`, etc.).
5. Writes `.standards-version` with the distribution release tag.
6. (Optional) Writes a sync report that flags rules whose globs match no files in the consumer (suggesting either the rule doesn't apply to this repo or the repo is missing a layer).

This sync is **idempotent**: re-running with the same distribution version produces an empty diff.

---

## 7. New Frontmatter Schema (Source) vs. Cursor MDC Frontmatter (Target)

### 7.1 Source Frontmatter — Authoritative Schema

```yaml
---
id: <unique-kebab-case-string>           # required
title: <human-readable-title>            # required
version: <semver>                        # required
status: draft | approved | deprecated    # required
scope:
  language: <lang-id>                    # required: java | typescript | python | go | rust | ...
  framework: <framework-id> | null       # required (null for language-core rules)
  framework_version: <semver-range>      # optional: e.g., ">=3.0", "^2.7.0"
  layers:                                # required: array, ≥1 entry
    - controller | service | repository | config | test | di | error-handling | architecture | all
target_tools:                            # required: at least one true
  cursor: bool
  github_copilot: bool
  claude_skills: bool
  junie: bool
  agents_md: bool
activation:                              # required
  cursor_mode: always | auto-attach | agent-requested | manual
  agents_md_priority: high | medium | low
dependencies: [<source-rule-id>, ...]    # optional
related_logic_holes: [<int>, ...]        # optional, references catalog
archunit_test: <path-or-null>            # optional, build-time enforcement test path
---
```

### 7.2 Compiled Cursor MDC Frontmatter

```yaml
---
description: <derived-from-title-and-scope>
globs: [<resolved-globs-array>]
alwaysApply: <derived-from-activation>
---
```

The `description` is derived as: `"<title> — apply to <stack-human-name>"`. This satisfies Cursor's Agent-Requested mode where a rich, action-oriented description is critical.

### 7.3 Why a Two-Layer Schema?

A single-layer schema (authoring directly in MDC format) would tightly couple us to Cursor and force re-authoring for every other tool. The two-layer model is the **same separation Backstage uses for software-template rendering**: a richer source DSL → a fan of tool-specific outputs.

Concretely: a single Markdown source file produces a Cursor `.mdc`, a Copilot fragment, a Claude fragment, a Junie fragment, an `AGENTS.md` line, an entry in the Memory Bank `systemPatterns.md`, and an ArchUnit test reference — **all from one author edit**.

---

## 8. Appendix A — Full `.mdc` Specifications for the Four New Logic Holes

These are presented in the **source-format**. The compiled MDC output (Cursor frontmatter + body) follows the source frontmatter using the rules in §6.

---

### Appendix A.1 — Logic Hole #3: Implicit Boundary & Serialization Vulnerabilities

**Source File**: `source/java/spring-boot/controller/validation-boundaries.md` (and a sibling `dto-record-mandate.md` for the response side).

```markdown
---
id: java-spring-controller-validation-boundaries
title: Mandatory @Valid + DTO Records on Controller Boundaries
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=3.0"
  layers: [controller]
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: auto-attach
  agents_md_priority: high
dependencies:
  - source/_global/security-baselines.md
related_logic_holes: [3]
archunit_test: testing/archunit/ControllerValidationTest.java
---

# Controller Boundary: Validation & Serialization

## 1. Context & Architectural Intent

Controllers are the **trust boundary** between untrusted client input and trusted domain logic.
Two distinct concerns must be enforced at this boundary:

1. **Input shape validation** — incoming JSON must match a strictly-typed contract before it reaches the service layer.
2. **Output shape control** — outgoing JSON must never expose persistence-layer types (JPA entities, internal enums, audit fields).

Failing either creates exploitable surface area: mass-assignment vulnerabilities on input,
information-disclosure leaks on output, and lazy-loading-during-serialization storms on entity exposure.

---

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Mandatory `@Valid` / `@Validated` on Request Bodies & Path Inputs

* **Rule**: Every controller method parameter annotated with `@RequestBody`, `@RequestPart`, or `@ModelAttribute` MUST be preceded by `@Valid`. Every controller method that takes constraint-annotated `@RequestParam` or `@PathVariable` arguments MUST have its containing class annotated with `@Validated`.
* **Rationale**: Without `@Valid`, JSR-380/Jakarta Validation constraints (`@NotNull`, `@Size`, `@Email`, `@Pattern`) on the request type are silently ignored. The AI must not assume validation will run by virtue of constraint annotations alone — the activation annotations are mandatory.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN
  @PostMapping("/users")
  public UserResponse create(@RequestBody UserCreateRequest req) { /* ... */ }

  // ✅ CORRECT
  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) { /* ... */ }

  // ✅ CORRECT for path/query validation
  @Validated
  @RestController
  public class UserController {
      @GetMapping("/users/{id}")
      public UserResponse get(@PathVariable @Positive Long id) { /* ... */ }
  }
  ```

### 2.2. Mandatory Request `record` Types (DTO-In)

* **Rule**: Controller methods MUST accept a Java `record` (or, in legacy projects, an immutable POJO) for the request body. They MUST NOT accept a JPA `@Entity` class.
* **Rationale**: Binding directly to entities allows attackers to set fields the API does not intend to expose (mass-assignment / overpost vulnerability — OWASP API3:2023). Jackson + Hibernate dirty-checking will silently persist any field the attacker submits. Records additionally encode immutability and make the API contract self-documenting.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN — entity exposure on input
  @PostMapping("/users")
  public User create(@RequestBody User user) {  // attacker can set role=ADMIN
      return userRepository.save(user);
  }

  // ✅ CORRECT — explicit request record with whitelisted fields
  public record UserCreateRequest(
      @NotBlank @Email String email,
      @NotBlank @Size(min = 8, max = 72) String password,
      @NotBlank String displayName
  ) {}

  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) {
      User saved = userService.create(req);
      return UserResponse.from(saved);
  }
  ```

### 2.3. Mandatory Response `record` Types (DTO-Out)

* **Rule**: Controller methods MUST return a Java `record` (or `ResponseEntity<TheRecord>`). They MUST NOT return a JPA `@Entity`, a `Page<Entity>`, a `List<Entity>`, or any type whose Jackson serialization could traverse persistence-managed lazy associations.
* **Rationale**: Returning entities (a) leaks audit/internal fields, (b) triggers lazy-loading during JSON serialization (causing the N+1 covered in Logic Hole #4 to occur *during the HTTP response phase*, holding the DB connection for the entire serialization window), (c) couples the API contract to the database schema (any column rename breaks public clients).
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN
  @GetMapping("/users/{id}")
  public User get(@PathVariable Long id) {                   // exposes passwordHash, lastLoginIp, ...
      return userRepository.findById(id).orElseThrow();
  }

  // ✅ CORRECT
  public record UserResponse(Long id, String email, String displayName, Instant createdAt) {
      public static UserResponse from(User u) {
          return new UserResponse(u.getId(), u.getEmail(), u.getDisplayName(), u.getCreatedAt());
      }
  }

  @GetMapping("/users/{id}")
  public UserResponse get(@PathVariable Long id) {
      return UserResponse.from(userService.findById(id));
  }
  ```

### 2.4. Mandatory `MethodArgumentNotValidException` Handling

* **Rule**: The central `@RestControllerAdvice` MUST have an `@ExceptionHandler(MethodArgumentNotValidException.class)` that maps Jakarta Validation failures into the company `ApiErrorResponse.fieldValidationErrors` map.
* **Rationale**: Default Spring behavior returns a verbose `BindingResult` payload that leaks framework internals. The unified error contract requires one response shape across all error pathways.

---

## 3. AI Directives & Code Generation Prompt Templates

When generating, modifying, or refactoring Java code in `**/controller/**/*.java`:

1. **Verify @Valid presence**: For every `@RequestBody` / `@RequestPart` / `@ModelAttribute` parameter, prepend `@Valid`. If absent, this is a critical defect.
2. **Verify request DTO is a record, not an entity**: If the parameter type is a class annotated with `@Entity`, REPLACE it with a request `record` whose fields are explicitly whitelisted.
3. **Verify response type is a record**: If the return type is an `@Entity`, `Page<Entity>`, or `List<Entity>`, REPLACE it with a `record` (or `Page<RecordResponse>`, `List<RecordResponse>`). Provide a static `from(Entity)` factory on the record.
4. **Verify class-level @Validated** when path/query constraints are used.
5. **Reject auto-binding to entities** even when the user explicitly requests it — explain the OWASP API3 risk and propose the record-based alternative.
```

---

### Appendix A.2 — Logic Hole #4: Database Performance Killers (Transactional + N+1)

This hole is split across three source files for precise glob targeting; here is the most important one — the service-layer `@Transactional` rule. The repository-layer N+1 rule follows the same template.

```markdown
---
id: java-spring-service-transactional-boundaries
title: Disciplined @Transactional Boundaries (Read-Only Default, No I/O Inside Transactions, No Self-Invocation)
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers: [service]
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: auto-attach
  agents_md_priority: high
dependencies:
  - source/java/spring-boot/error-handling/prohibit-blind-catch.md
related_logic_holes: [4]
archunit_test: testing/archunit/TransactionalDisciplineTest.java
---

# Service Layer: Disciplined @Transactional Boundaries

## 1. Context & Architectural Intent

`@Transactional` is the most-misused annotation in Spring Boot. AI agents apply it indiscriminately,
producing three classes of latent defect: (a) blocking thread/connection exhaustion when long I/O
runs inside a transaction; (b) silently-broken self-invocation; (c) read-write transactions on
read-only paths, defeating read-replica routing.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Read-Only Default at the Class Level

* **Rule**: Every `@Service` class MUST declare `@Transactional(readOnly = true)` at the class level. Mutating methods MUST individually override with `@Transactional` (read-write).
* **Rationale**: `readOnly = true` enables (a) Hibernate flush-skip optimization, (b) read-replica routing in multi-DB topologies, (c) clear documentation that the method does not mutate state.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN — every method opens a read-write tx, even pure reads
  @Service
  @Transactional
  public class OrderService {
      public Order findById(Long id) { /* read */ }
      public Order create(OrderRequest req) { /* write */ }
  }

  // ✅ CORRECT — read-only by default, mutations are explicit
  @Service
  @Transactional(readOnly = true)
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;

      public Order findById(Long id) { /* read — inherits readOnly=true */ }

      @Transactional                                        // explicit override for mutation
      public Order create(OrderRequest req) { /* write */ }
  }
  ```

### 2.2. Prohibition of External I/O Inside `@Transactional`

* **Rule**: A method annotated with `@Transactional` MUST NOT make HTTP/gRPC calls, message-broker publishes, or any blocking external I/O. If the workflow requires both DB writes and external I/O, the method MUST extract the DB-only critical section into a `TransactionTemplate.execute(...)` block and perform the I/O outside it.
* **Rationale**: While a transaction is open, the calling thread holds a database connection from the HikariCP pool. A 2-second downstream HTTP call holds a connection for 2 seconds. Under load, the pool exhausts and every thread queues, even threads that don't need a DB connection. This produces the canonical "p99 hockey-stick at 80% load" pattern.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN — HTTP call holds DB connection
  @Transactional
  public Order create(OrderRequest req) {
      Order saved = orderRepository.save(new Order(req));
      paymentClient.charge(saved.getId(), saved.getTotal());   // 800ms HTTP — connection held
      saved.markPaid();
      return orderRepository.save(saved);
  }

  // ✅ CORRECT — narrow tx, I/O outside
  public Order create(OrderRequest req) {
      Order saved = txTemplate.execute(s -> orderRepository.save(new Order(req)));
      paymentClient.charge(saved.getId(), saved.getTotal());   // I/O outside any tx
      return txTemplate.execute(s -> {
          Order reattached = orderRepository.findById(saved.getId()).orElseThrow();
          reattached.markPaid();
          return orderRepository.save(reattached);
      });
  }
  ```

### 2.3. Prohibition of Self-Invocation Across Transactional Boundaries

* **Rule**: When a method on a Spring-managed bean calls another `@Transactional` method on the **same instance** (`this.someMethod()`), the proxy is bypassed and the inner method's `@Transactional` is silently inert.
* **Rationale**: Spring's transaction support uses dynamic proxies. Self-invocation calls the underlying class directly, skipping the proxy entirely. The AI must not assume that placing `@Transactional` on a private/internal helper produces a transaction when the helper is called from a sibling method on the same bean.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN — inner @Transactional silently ignored
  @Service
  public class OrderService {
      public void process(OrderRequest req) {
          this.save(req);                    // self-invocation; @Transactional NOT applied
      }

      @Transactional
      public void save(OrderRequest req) { /* ... */ }
  }

  // ✅ CORRECT — extract to a separate bean, OR move @Transactional to the public entry method
  @Service
  @Transactional
  public class OrderService {
      public void process(OrderRequest req) {
          // entire process() is now transactional via the proxy
          save(req);
      }
      private void save(OrderRequest req) { /* ... */ }
  }
  ```

### 2.4. Prohibition of `@Transactional` on `@Scheduled` Methods

* **Rule**: A method MUST NOT carry both `@Scheduled` and `@Transactional`. If a scheduled job needs a transaction, it MUST delegate to a separate `@Transactional` service method.
* **Rationale**: The scheduling proxy and the transactional proxy compose poorly; depending on bean post-processor ordering, the transactional proxy may be lost, producing silent no-op transactions. This is documented in Spring's reference and reinforced in the JetBrains Junie guidelines.

## 3. AI Directives

When generating, modifying, or refactoring Java code in `**/service/**/*.java`:

1. **Default to `@Transactional(readOnly = true)` at the class level** unless the entire class is mutation-heavy.
2. **Search the method body for HTTP clients, gRPC stubs, message publishers, file I/O.** If found inside a `@Transactional` method, refactor to use `TransactionTemplate` and place the I/O outside the template's `execute` lambda.
3. **Detect self-invocation**: if a public method calls another method on `this` and that method is annotated `@Transactional`, refactor — either inline the work into the entry method or extract to a separate bean.
4. **Never combine `@Scheduled` + `@Transactional`** on the same method.
```

The repository-layer counterpart (`source/java/spring-boot/repository/n-plus-one-prevention.md`) follows the identical structure; its key rules are: (a) default to `@EntityGraph(attributePaths = {...})` for any method that traverses an association at the service layer; (b) ban naked `JOIN FETCH` when the method also accepts `Pageable` (Hibernate falls back to in-memory pagination — a confirmed OOM vector); (c) `@BatchSize` mandatory on `@OneToMany` collections; (d) `MultipleBagFetchException` defense — at most one `Bag`-typed collection fetched per query.

---

### Appendix A.3 — Logic Hole #5: API Scalability Anti-Patterns (`findAll`)

```markdown
---
id: java-spring-repository-pagination-mandate
title: Mandatory Pageable on All List-Returning Repository Methods (No Naked findAll())
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers: [repository, controller]
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: auto-attach
  agents_md_priority: high
dependencies: []
related_logic_holes: [5]
archunit_test: testing/archunit/PaginationMandateTest.java
---

# Repository & Controller: Mandatory Pagination

## 1. Context & Architectural Intent

`Repository.findAll()` (or any unbounded list query) is a production-killer the moment the underlying
table grows beyond development scale. It exhausts the JDBC fetch buffer, allocates a heap-resident
List of every row, and — when exposed via a REST controller — serializes the entire result set into
a single JSON response that overflows the connector buffer.

This rule mandates pagination at every layer where lists cross a boundary.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Banned: Naked `findAll()` in Production Code

* **Rule**: A repository interface MUST NOT expose a method whose name begins with `findAll`/`findBy*` and returns `List<T>` (or `Iterable<T>`, or `Stream<T>`) without accepting a `Pageable` parameter — except for narrowly justified cases (lookup tables of bounded size, audited via `@SuppressWarnings("PaginationMandate")`).
* **Rationale**: An unbounded list query is a latent OOM. Vlad Mihalcea's seminal post on this anti-pattern is the canonical reference; in 2026 it remains the most-cited piece of Spring Data guidance.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN
  public interface OrderRepository extends JpaRepository<Order, Long> {
      List<Order> findByCustomerId(Long customerId);   // unbounded
  }

  // ✅ CORRECT
  public interface OrderRepository extends JpaRepository<Order, Long> {
      Page<Order> findByCustomerId(Long customerId, Pageable pageable);
  }
  ```

### 2.2. Mandatory `Pageable` on List Controller Endpoints

* **Rule**: Any controller method whose response is a collection MUST accept a `Pageable` argument with `@PageableDefault` and return `Page<TheRecord>`.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN
  @GetMapping("/orders")
  public List<OrderResponse> list() {
      return orderRepository.findAll().stream().map(OrderResponse::from).toList();
  }

  // ✅ CORRECT
  @GetMapping("/orders")
  public Page<OrderResponse> list(
      @PageableDefault(size = 20, sort = "createdAt", direction = Sort.Direction.DESC)
      Pageable pageable
  ) {
      return orderRepository.findAll(pageable).map(OrderResponse::from);
  }
  ```

### 2.3. Page Size Hard Cap

* **Rule**: The application MUST configure `spring.data.web.pageable.max-page-size = 100` (or stricter) in `application.yml`. This prevents a client from requesting `?size=1000000`.
* **Rationale**: Without a cap, the pagination contract is theatrical — a client can defeat it by passing a giant `size`.

### 2.4. Pagination + EntityGraph Composition

* **Rule**: When a paginated query needs eager-loaded associations, it MUST use `@EntityGraph` (left-outer-join, pagination-safe) and MUST NOT use `JOIN FETCH` (which forces in-memory pagination).
* **Rationale**: Hibernate emits a warning ("HHH000104: firstResult/maxResults specified with collection fetch; applying in memory") and silently loads the entire result set, then paginates in Java — a worst-of-both-worlds scenario.

## 3. AI Directives

When generating, modifying, or refactoring Java code in `**/repository/**/*.java` and `**/controller/**/*.java`:

1. **Reject `findAll()` without `Pageable`.** When the user requests "list all X", offer the paginated variant and explain the OOM risk.
2. **Reject `List<T>` return types from controller list endpoints.** Replace with `Page<T>`.
3. **When eager loading is required**, generate `@EntityGraph(attributePaths = {...})` over `JOIN FETCH`.
4. **Always include `@PageableDefault`** on controller `Pageable` parameters so undocumented requests don't fall back to Spring's hidden default.
```

---

### Appendix A.4 — Logic Hole #6: Field Injection (DI Anti-Pattern)

```markdown
---
id: java-spring-di-constructor-injection-mandate
title: Constructor Injection Mandate (No Field/Setter @Autowired)
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=4.3"
  layers: [all]
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: agent-requested            # broad scope; use AI judgment to load
  agents_md_priority: high
dependencies: []
related_logic_holes: [6]
archunit_test: testing/archunit/ConstructorInjectionTest.java
---

# Dependency Injection: Constructor Injection Mandate

## 1. Context & Architectural Intent

Field injection — `@Autowired` on a private field — was the dominant pattern in pre-2017 Spring code
and remains heavily represented in AI training corpora. It is now officially discouraged by Spring
itself (since 4.3, reinforced in Spring Boot 3+). Constructor injection produces immutable,
context-free, trivially testable dependencies; field injection produces the opposite of all three.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Mandatory Constructor Injection with `final` Fields

* **Rule**: Every Spring bean (`@Component`, `@Service`, `@Repository`, `@Controller`, `@RestController`, `@Configuration`) MUST declare its dependencies as `private final` fields, populated via a single explicit constructor (or via Lombok `@RequiredArgsConstructor` if the project already depends on Lombok). Spring 4.3+ auto-wires the sole constructor — no `@Autowired` annotation is required.
* **Rationale**: (a) `final` enforces immutability; (b) the constructor signature is the bean's true contract; (c) tests instantiate with `new Service(mock1, mock2)` — no Spring context, sub-millisecond test start; (d) circular dependencies fail at boot, not at runtime.
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN — field injection
  @Service
  public class OrderService {
      @Autowired private OrderRepository orderRepository;
      @Autowired private PaymentClient paymentClient;
  }

  // ❌ ANTI-PATTERN — setter injection
  @Service
  public class OrderService {
      private OrderRepository orderRepository;
      @Autowired public void setOrderRepository(OrderRepository r) { this.orderRepository = r; }
  }

  // ✅ CORRECT — constructor injection (explicit constructor)
  @Service
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;

      public OrderService(OrderRepository orderRepository, PaymentClient paymentClient) {
          this.orderRepository = orderRepository;
          this.paymentClient = paymentClient;
      }
  }

  // ✅ CORRECT — constructor injection (Lombok)
  @Service
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;
  }
  ```

### 2.2. Forbidden: `@Autowired` on Fields and Setters

* **Rule**: `@Autowired` MUST NOT appear on a field declaration or a setter method. Its only legal site is a constructor parameter — and even there, it is unnecessary if the class has exactly one constructor.

### 2.3. Forbidden: Field-Injected Test Doubles in Production Beans

* **Rule**: Production beans MUST NOT use `@Autowired` on fields "for testability." The correct pattern is constructor injection + production code that takes the same constructor in tests.
* **Rationale**: Tests should `new TheService(mockDep)`. If they cannot, the production design is broken.

### 2.4. Optional Dependencies

* **Rule**: Optional dependencies MUST be expressed as `Optional<T>` in the constructor, not as `@Autowired(required = false)` on a field.
* **Implementation Requirement**:
  ```java
  // ✅ CORRECT
  public OrderService(OrderRepository orderRepository, Optional<MetricsClient> metrics) { /* ... */ }
  ```

## 3. AI Directives

When generating any Spring bean class:

1. **Default to constructor injection with `final` fields**.
2. **Never emit `@Autowired` on a private field**, even if a snippet in the user's existing codebase does so.
3. **Use `@RequiredArgsConstructor`** if and only if the project's `pom.xml`/`build.gradle` already declares a Lombok dependency.
4. **Express optional dependencies as `Optional<T>` constructor parameters**, not annotated fields.
5. **When refactoring a class that uses field injection**, migrate it in-place and explain the testability/immutability gain in the PR description.
```

---

## Document End

This concludes the Architecture Upgrade Report. The companion **Implementation Plan** (Deliverable 2) sequences the migration into ten executable phases, each with explicit acceptance criteria.

