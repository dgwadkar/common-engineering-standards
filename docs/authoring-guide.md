# Authoring Guide for Engineering-Standards Source Rules

> **Status**: Phase 3 deliverable per `docs/02-implementation-plan.md` §6 task 4.
> **Audience**: Anyone authoring or editing a file under `source/**/*.md`.
> **Related artifacts**: `.cursor/rules/authoring-style.mdc` (always-loaded checklist),
> `.cursor/rules/frontmatter-spec.mdc` (always-loaded frontmatter contract),
> `schemas/source-rule.schema.json` (machine-readable contract),
> `schemas/layer-glob-map.json` (language → layer → globs lookup),
> `schemas/examples/valid-source-rule.md` (copy-paste reference example).

This guide is the long-form prose companion to the two `.cursor/rules/*.mdc` checklists. Open it
when you are about to write your first source rule, when you have a question that is not
mechanically captured by the schema, or when you need to extend the corpus into a new language
or layer.

---

## Table of Contents

1. [The Three-Document Pattern Every Rule Follows](#1-the-three-document-pattern-every-rule-follows)
2. [The Mandatory Paired ❌/✅ Code-Block Convention](#2-the-mandatory-paired--code-block-convention)
3. [Mapping `scope.layers` to Cursor Activation Modes](#3-mapping-scopelayers-to-cursor-activation-modes)
4. [When To Choose `cursor_mode: always` (Rarely)](#4-when-to-choose-cursor_mode-always-rarely)
5. [How To Cross-Reference Dependencies](#5-how-to-cross-reference-dependencies)
6. [Crafting the `description` Line for Agent-Requested Mode](#6-crafting-the-description-line-for-agent-requested-mode)
7. [Choosing `agents_md_priority`](#7-choosing-agents_md_priority)
8. [Where to Place a New Rule in `source/`](#8-where-to-place-a-new-rule-in-source)
9. [Working With the Schema Validator](#9-working-with-the-schema-validator)
10. [Pre-Save Checklist](#10-pre-save-checklist)

---

## 1. The Three-Document Pattern Every Rule Follows

Every source rule has three top-level Markdown sections, in this order, after the YAML
frontmatter:

```markdown
# <Title — verbatim from frontmatter `title`>

## 1. Context & Architectural Intent
2–6 paragraphs explaining the *why*: the architectural problem the rule prevents, the
AI failure mode that motivates it, and how the rule fits into the broader corpus
(which Logic Hole, which sibling rules).

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. <First enforced standard, short imperative title>
* **Rule**: <one sentence, imperative>
* **Rationale**: <one paragraph; the engineering tradeoff>
* **Implementation Requirement**:
  ```<lang>
  // ❌ ANTI-PATTERN
  ...
  // ✅ CORRECT
  ...
  ```

### 2.2. <Second enforced standard>
... (same shape; aim for 2–5 enforced standards per rule)

## 3. AI Directives
Imperative bullet list aimed at the agent. Each bullet starts with a verb:
"Default to ...", "Never emit ...", "When refactoring X, propose Y ...".
```

Why this shape, specifically?

- **Section 1 is the human reader's onboarding.** Reviewers and new authors read it to decide
  whether the rule belongs in the corpus at all. It is the only section that may be read by a
  person debugging an unfamiliar rule in production.
- **Section 2 is the LLM's ingestion core.** The `Rule` / `Rationale` / `Implementation
  Requirement` shape is what downstream tools (Cursor, Copilot, Claude, Junie) actually use to
  guide generation. Keep it dense, specific, and example-driven.
- **Section 3 is the agent-instruction layer.** It restates the rule in a format the agent can
  match against an in-flight task: "If you are about to do X, instead do Y."

The compiler does not parse the section structure (yet) — but the Phase-6 golden snapshot tests
will compare the compiled output across rule edits, and an inconsistent body shape produces
noisy diffs. Stick to the structure.

---

## 2. The Mandatory Paired ❌/✅ Code-Block Convention

Every enforced standard in §2 of a rule MUST contain at least one paired code block:

```markdown
* **Implementation Requirement**:
  ```java
  // ❌ ANTI-PATTERN
  @PostMapping("/users")
  public UserResponse create(@RequestBody UserCreateRequest req) { /* ... */ }

  // ✅ CORRECT
  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) { /* ... */ }
  ```
```

The literal markers `❌ ANTI-PATTERN` and `✅ CORRECT` MUST be used (not "BAD"/"GOOD",
"OLD"/"NEW", or any variation). The Phase-6 golden snapshot tests will assert their presence.

### Why paired?

A single side (only ❌ or only ✅) halves the signal. The LLM learns the contrast — what to do
*instead of* what — much better than it learns either side in isolation. The empirical evidence
for this is JetBrains Junie's `guidelines-with-explanations.md` model and Anthropic's published
work on contrastive training data.

### Style notes for the paired blocks

- **Both blocks use the same language fence** (`java`, `typescript`, `python`, `yaml`).
  Different languages defeat the visual contrast.
- **Keep both blocks minimal.** Strip imports, package declarations, and unrelated boilerplate.
  Only the lines that demonstrate the contrast.
- **Annotate the ❌ block with a comment naming the defect** when it is not obvious:
  `// attacker can set role=ADMIN, balance=99999`. The defect annotation is what makes the
  contrast actionable.
- **The ✅ block should be runnable.** Don't pseudocode it. A reviewer should be able to copy
  it into an IDE and see it compile.
- **Use comments inside the block, not prose between blocks.** The blocks are meant to be
  read as a single visual contrast.

### When more than one paired block per standard is needed

If an enforced standard has multiple distinct correct shapes (e.g., the constructor-injection
rule has both an explicit-constructor form and a Lombok form), include all of them as
sequential ✅ blocks under the same `Implementation Requirement`. Do not split into multiple
enforced standards if the standards share the same `Rule` sentence.

---

## 3. Mapping `scope.layers` to Cursor Activation Modes

The layer-keyed source split (ADR-0002) is the engine that makes the corpus token-efficient.
This table is the canonical decision matrix for mapping `scope.layers` to `activation.cursor_mode`.

| `scope.layers` Value | Typical `cursor_mode` | Why |
|---|---|---|
| `[controller]` | `auto-attach` | The compiler resolves to `**/controller/**/*.java` etc.; Cursor auto-loads when a matching file is in context. |
| `[service]` | `auto-attach` | Resolves to `**/service/**/*.java`; same auto-attach behavior. |
| `[repository]` | `auto-attach` | Resolves to `**/repository/**/*.java`, `**/dao/**/*.java`, `**/persistence/**/*.java`. |
| `[config]` | `auto-attach` | Resolves to `**/config/**/*.java` + `application*.yml` + `application*.properties`. |
| `[test]` | `auto-attach` | Resolves to `**/*Test.java`, `**/*Tests.java`, `**/*IT.java`. |
| `[error-handling]` | `auto-attach` | Resolves to `**/exception/**`, `**/advice/**`, `**/errors/**`. |
| `[di]` | `agent-requested` | `di` resolves to `**/*.java` (every Java file may declare a Spring bean) — too broad for auto-attach. Use `agent-requested` so Cursor's agent decides relevance based on task description. |
| `[architecture]` | `always` | Architecture rules cross-cut every file. The compiler routes `architecture` to `alwaysApply: true` with no globs. |
| `[all]` | `agent-requested` | Same reasoning as `di` — too broad for auto-attach. |
| Multiple layers, e.g. `[controller, repository]` | `auto-attach` | Compiler produces the union of all resolved globs. Use when a rule legitimately spans two narrow layers (e.g., the pagination rule, which fires at both the HTTP boundary and the data-access boundary). |
| Mixed broad + narrow, e.g. `[all, controller]` | `agent-requested` | `all` swamps the narrow layer; pick the broader semantic and let the agent decide. |

### Special case: `_global/` rules

Rules under `source/_global/` are cross-cutting and language-agnostic. They use:

```yaml
scope:
  language: global       # pseudo-language; NOT _global (leading underscores rejected)
  framework: null
  layers: [architecture] # signals "no globs, always-apply"
activation:
  cursor_mode: always    # consistent with layers: [architecture]
```

The `global` pseudo-language is intentionally absent from `schemas/layer-glob-map.json`
because `layers: [architecture]` already encodes "no globs needed."

---

## 4. When To Choose `cursor_mode: always` (Rarely)

`cursor_mode: always` maps to MDC `alwaysApply: true` — the rule loads on every prompt in
every chat / composer / agent session in every consumer repo. This is **expensive**: it
defeats the token-budget gain that motivated the layer-keyed split. Use it ONLY when one of
the following is true:

1. **The rule is architectural and cross-cuts every file.** Examples:
   `source/_global/clean-architecture.md` (the four-layer boundary doctrine),
   `source/_global/logging-telemetry.md` (every log call must follow the structured shape).
2. **The rule is safety-critical and applies regardless of file type.** Example:
   `source/_global/security-baselines.md` (no hard-coded secrets, ever).
3. **A reviewer has explicitly approved the choice in the PR description.** The reviewer is
   the gate that prevents `always` from being the lazy default.

If you find yourself reaching for `always` because "the rule is important," that is NOT a
sufficient reason. Every rule is important; that's why it's in the corpus. The right question
is "does this rule apply to every file the agent could be editing right now?" If the answer is
no (it applies to controllers only, or to tests only, or to YAML configs only), use
`auto-attach` and let the layer-glob map do its job.

The Phase-2 schema and the Phase-4 compiler will eventually emit a build-time warning if more
than ~5 rules in any stack are `cursor_mode: always` (see `docs/02-implementation-plan.md`
§14 R-06). Keep the always-on set small.

---

## 5. How To Cross-Reference Dependencies

The `dependencies:` array in a rule's frontmatter declares prerequisite rules. Examples:

```yaml
# From: source/java/spring-boot/error-handling/problem-details-rfc7807.md
dependencies:
  - java-spring-error-handling-unified-api-error

# From: source/java/spring-boot/controller/dto-record-mandate.md
dependencies:
  - java-spring-controller-validation-boundaries
  - global-security-baselines
```

### What the dependency does

The Phase-4 compiler computes the rule dependency DAG, detects cycles (which fail the build),
and **topologically sorts** so dependencies are emitted before dependents when concatenating
into single-file targets (Copilot, Claude, Junie, the universal AGENTS.md). For Cursor MDC
output (per-rule-file), the dependency information is recorded in the rule's `description`
field but does not affect file ordering.

### When to declare a dependency

- **The rule reads as "extends X."** Example: `problem-details-rfc7807` extends
  `unified-api-error` with the RFC 7807 wire format on Spring Boot 3+.
- **The rule reads as "operationalizes X."** Example: `disable-open-session-in-view`
  operationalizes the `n-plus-one-prevention` rule by removing the silent-failure escape
  hatch.
- **The rule references a fixture or contract owned by another rule.** Example:
  `dto-record-mandate` references the `ApiErrorResponse` contract owned by `unified-api-error`.

### When NOT to declare a dependency

- **Coincidental topical proximity.** Two rules being in the same layer is not a dependency.
- **Cross-references in prose only.** A "see also X" pointer in a body paragraph does not
  warrant a `dependencies` entry.
- **Soft sequencing.** "It's nice to read rule A before rule B" is not a dependency. The
  dependency array is for compile-time ordering, not human reading order.

### How to cite ADRs and the architecture report in the body

In Markdown prose, use relative links to other docs in the repo:

```markdown
See [ADR-0002](../../../docs/decision-records/0002-layer-keyed-source-split.md) for the
layer-keyed source split rationale, and `docs/01-architecture-upgrade-report.md` §5.1 for
the target directory tree.
```

Don't use absolute paths or external URLs to internal docs — relative links keep the corpus
movable.

---

## 6. Crafting the `description` Line for Agent-Requested Mode

The compiler derives the Cursor MDC `description` field from the source frontmatter `title`
plus a suffix indicating the stack:

```
description: "<title> — apply to <stack-human-name>"
```

For rules with `cursor_mode: agent-requested`, this `description` is **critical**: it is the
single field Cursor's agent uses to decide whether to load the rule for an in-flight task. A
bland title produces a rule that is never loaded; a precise, action-oriented title produces a
rule that fires exactly when needed.

### Title craft for agent-requested rules

Good agent-requested titles:

- ✅ `Constructor Injection Mandate — No Field or Setter @Autowired`
- ✅ `Disciplined @Transactional Boundaries — No External I/O Inside Transactions`
- ✅ `Mandatory Request and Response Record Types at the Controller Boundary`

Bad agent-requested titles:

- ❌ `Spring DI Best Practices` (too generic; agent cannot match)
- ❌ `Service Layer Guidelines` (no concrete trigger)
- ❌ `Architecture` (one word; matches everything and nothing)

The title should answer the agent's implicit question: "What in-flight task should make me
load this rule?" If the answer is concrete ("I'm composing a Spring `@Service`"), the rule
will fire reliably. If the answer is fuzzy ("I'm thinking about architecture"), the rule
will not.

### For `auto-attach` rules, the title can be shorter

`auto-attach` rules load deterministically based on glob match — the agent does not consult
the description for activation. The title is still important for human reviewers, but the
matching is mechanical.

---

## 7. Choosing `agents_md_priority`

The `activation.agents_md_priority` field gates inclusion in the universal `AGENTS.md`
distribution target. That file has a hard 150-line cap (per the AGENTS.md spec); rules tagged
`high` are included, rules tagged `medium` or `low` are excluded.

- **`high`**: The rule represents foundational guidance every agent should know about this
  stack — the layer-boundary doctrine, the security baselines, the constructor-injection
  mandate, the transactional discipline. Roughly 10–15 rules per stack should be `high`.
- **`medium`**: The rule is important within its layer but does not need to surface in the
  cross-tool baseline. Most layer-specific rules are `medium`.
- **`low`**: The rule is narrow or edge-case (e.g., a specific configuration tweak). Rarely
  used; consider whether the rule belongs in the corpus at all.

If you mark too many rules `high`, the Phase-5 transformer fails the build with a "demote
rules to medium priority" diagnostic and points at the longest rules. The cap is a forcing
function for the editor (Standards Architect) to make explicit trade-offs.

---

## 8. Where to Place a New Rule in `source/`

The directory tree under `source/` is the layer-keyed split (ADR-0002):

```text
source/
├── _global/                         # global pseudo-language, layers: [architecture]
├── java/
│   ├── _core/                       # java-only, framework: null
│   └── spring-boot/
│       ├── architecture/            # layers: [architecture]
│       ├── controller/              # layers: [controller]
│       ├── service/                 # layers: [service]
│       ├── repository/              # layers: [repository]
│       ├── error-handling/          # layers: [error-handling]
│       ├── di/                      # layers: [di]
│       ├── config/                  # layers: [config]
│       └── testing/                 # layers: [test]
├── typescript/
│   ├── _core/
│   └── nestjs/
│       ├── controller/              # layers: [controller]
│       └── service/                 # layers: [service]
└── python/
    └── fastapi/
        ├── controller/              # layers: [controller]
        └── service/                 # layers: [service]
```

### Choosing the directory

- The directory determines the rule's primary layer in the directory-shape sense, but the
  authoritative layer driver is the `scope.layers` array in the frontmatter — the compiler
  reads frontmatter, not directory.
- Place the rule in the directory whose layer matches `scope.layers[0]`. When the array
  contains multiple layers (e.g., `[controller, repository]` for the pageable-defaults rule),
  pick the layer where the rule's primary teaching site lives. The pageable-defaults rule
  lives in `controller/` because the controller-boundary contract is what authors need to
  recognize.

### Adding a new layer or language

If you need a layer that doesn't exist in `schemas/layer-glob-map.json` (e.g., a TypeScript
`repository` layer for a TypeORM project), you MUST:

1. Add the language → layer → globs entry to `schemas/layer-glob-map.json` in the same PR.
2. Update the entry's `$comment_layers` block to document the new layer.
3. Cite the layer addition in the rule's PR description so reviewers can sanity-check the
   globs against the consumer-repo convention.

`schemas/**` is owned by `@platform-team @standards-council` per `.github/CODEOWNERS`, so the
co-edit will surface in the same review.

---

## 9. Working With the Schema Validator

The Phase-2 validator (`compiler/core/parse_source.py --validate-only`) is the local
pre-flight check. Run it before every PR:

```bash
# Validate every source/**/*.md and schemas/examples/*.md:
python compiler/core/parse_source.py --validate-only

# Validate a single file (handy while authoring):
python compiler/core/parse_source.py --validate-only --path source/java/spring-boot/controller/my-new-rule.md
```

Exit codes: `0` = all valid; `1` = validation failed; `2` = invocation error.

Common validation failures and their fixes:

| Error | Fix |
|---|---|
| `scope.layers: 'controllers' is not one of …` | Layer names are singular: `controller`, not `controllers`. |
| `'language' does not match '^[a-z][a-z0-9_-]*$'` | Don't use a leading underscore. For `_global/` rules, use `language: global`. |
| `'1.0' does not match '^\d+\.\d+\.\d+$'` | Use full three-part semver: `1.0.0`. |
| `target_tools must satisfy one of …` (anyOf failure) | At least one of `cursor`, `github_copilot`, `claude_skills`, `junie`, `agents_md` must be `true`. |
| `framework_version: '>=3' does not match …` | Use `">=3.0"` or `"3.0.0"` — partial versions are rejected. |
| `'cursor-mode' was unexpected` (typo) | Field names are snake_case: `cursor_mode`, not `cursor-mode`. |

The CI workflow (`.github/workflows/validate.yml` `schema-validation` job) runs the same
validator on every PR, so a green local run mirrors the on-GitHub gate.

---

## 10. Pre-Save Checklist

Before opening a PR for a new or modified source rule, walk this list:

- [ ] Frontmatter parses as YAML and contains every required field
      (`id`, `title`, `version`, `status`, `scope`, `target_tools`, `activation`).
- [ ] `id` is kebab-case, lowercase, prefixed `<lang>-<framework>-<layer>-` (framework-scoped)
      or `global-` (global rules), and is unique across `source/`.
- [ ] `title` is human-readable, sentence case, no trailing period; matches the H1 in the body.
- [ ] `version` is strict three-part semver (`1.0.0`, not `1.0`).
- [ ] `status` is `draft` while authoring; flipped to `approved` before merge.
- [ ] `scope.language` and `scope.framework` match the directory the file lives in.
- [ ] `scope.layers` matches the directory's layer.
- [ ] `target_tools` has at least one `true`.
- [ ] `activation.cursor_mode` matches the §3 table above.
- [ ] `activation.agents_md_priority` matches the §7 criteria.
- [ ] `dependencies` lists IDs that actually exist under `source/` (otherwise Phase-4 build
      fails).
- [ ] `archunit_test` points to a real path (Phase-6 will create the file) OR is `null`.
- [ ] Body has the three top-level sections in order (Context, Enforced Standards, AI Directives).
- [ ] At least one paired ❌/✅ block per enforced standard.
- [ ] Cross-references to ADRs and the architecture report use relative links.
- [ ] `python compiler/core/parse_source.py --validate-only` returns exit code 0.
- [ ] `python -m pytest tests/test_schemas.py` passes.

---

## Appendix — Worked Example: Authoring a New Rule

Below is a 90-second authoring walkthrough for a hypothetical new rule
`source/java/spring-boot/controller/idempotency-keys.md`. The shape applies to every rule.

1. **Copy** `schemas/examples/valid-source-rule.md` to the new path.
2. **Edit the frontmatter**:
   - `id: java-spring-controller-idempotency-keys`
   - `title: Mandatory Idempotency Keys on Non-Safe Controller Endpoints`
   - `scope.layers: [controller]`
   - `activation.cursor_mode: auto-attach`
   - `activation.agents_md_priority: medium`
   - `archunit_test: testing/archunit/IdempotencyKeysTest.java`
3. **Write Section 1 (Context)**: 2 paragraphs — what idempotency keys are, why AI omits them,
   what the production consequence is.
4. **Write Section 2 (Enforced Standards)**: 3 standards, each with a paired ❌/✅ block.
5. **Write Section 3 (AI Directives)**: 4 imperative bullets aimed at the agent.
6. **Run** `python compiler/core/parse_source.py --validate-only --path source/java/spring-boot/controller/idempotency-keys.md`.
7. **Open the PR.** CODEOWNERS routes it to `@platform-team @standards-council`. The CI
   `schema-validation` job re-runs the validator.

---

## Document End

This concludes the authoring guide. The most-current authoritative artifacts are always the
JSON Schema (`schemas/source-rule.schema.json`) and the two MDC checklists
(`.cursor/rules/authoring-style.mdc`, `.cursor/rules/frontmatter-spec.mdc`). When this guide
and any of those three drift, the schema wins and an issue should be filed to reconcile.
