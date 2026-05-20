# ADR-0002 — Layer-Keyed Source Split (`source/<lang>/<framework>/<layer>/<rule>.md`)

- **Status**: Accepted
- **Date**: 2026-05-18
- **Deciders**: Standards Architect, Compiler Engineer, AI Enablement PM (sign-off pending operator review)
- **Phase**: 0 — Pre-Flight Decisions and ADRs
- **Related documents**:
  - `docs/01-architecture-upgrade-report.md` §4.2 Critique 1 ("One Markdown File per Concern Is Too Coarse for MDC Glob Matching")
  - `docs/01-architecture-upgrade-report.md` §4.2 Critique 3 ("No Layer-Level Targeting Metadata")
  - `docs/01-architecture-upgrade-report.md` §5.1 (target authoring repository hierarchy)
  - `docs/01-architecture-upgrade-report.md` §6.2 (compiled MDC frontmatter; layer-glob-map example)
  - `docs/02-implementation-plan.md` §3 (Phase 0 task list), §5 (Phase 2 schemas)

---

## 1. Context

The baseline blueprint organizes source under `languages/<lang>/<framework>/<concern>.md` — one Markdown file per concern, e.g., `languages/java/spring-boot/data-access.md` covering both transactions and JPA repository patterns.

Two facts about the activation model proposed in ADR-0001 invalidate this layout:

1. **MDC frontmatter binds *one* `globs:` pattern per file.** A single source file cannot compile to two MDC files with different globs. So a "data-access" file that mixes `@Transactional` rules (which apply to `**/service/**/*.java`) with N+1 prevention (which applies to `**/repository/**/*.java`) must either:
   - Compile to a *union* glob (`["**/service/**/*.java", "**/repository/**/*.java"]`), over-applying transaction rules to repository files and vice versa; **or**
   - Compile with no glob and `alwaysApply: true`, restoring the token-cost problem ADR-0001 set out to fix.
   Neither is acceptable.
2. **AI Logic Holes are deeply layer-specific.** Per `docs/01-architecture-upgrade-report.md` §2 and §4.2 Critique 3:
   - Validation/DTO rules apply to the **controller** layer only.
   - `@Transactional` discipline applies to the **service** layer only.
   - N+1 / `@EntityGraph` rules apply to the **repository** layer only.
   - Constructor-injection rules apply to **all** Spring components (broad).
   - "Disable Open-Session-in-View" applies to **config** (`application.yml`).
   The mapping from rule to layer is the *primary* metadata; concatenating multiple layers into one Markdown file destroys it at the source.

The decision to be recorded: **how should the `source/` tree be structured so that one source file compiles to one MDC file with one precise glob?**

---

## 2. Decision

**Source files are split by architectural layer.** The canonical authoring path is:

```
source/<language>/[_core | <framework>/<layer>/]<rule>.md
```

Concrete commitments:

- The recognized **layer catalog** is closed and enumerated in `schemas/source-rule.schema.json` (Phase 2 deliverable):
  `controller | service | repository | config | test | di | error-handling | architecture | all`.
- Every source rule's frontmatter declares `scope.layers:` as an **array of one or more** values from this catalog (e.g., `[controller]`, `[repository, controller]`, `[all]`).
- A **layer-to-glob lookup table** lives at `schemas/layer-glob-map.json` (Phase 2 deliverable) and maps each `(language, layer)` pair to a deduplicated list of file globs. Example:
  ```json
  {
    "java": {
      "controller": ["**/controller/**/*.java", "**/web/**/*.java", "**/rest/**/*.java"],
      "service":    ["**/service/**/*.java", "**/usecase/**/*.java"],
      "repository": ["**/repository/**/*.java", "**/dao/**/*.java", "**/persistence/**/*.java"]
    }
  }
  ```
- The directory tree mirrors the layer keys 1:1. Concretely (subset, full tree in `docs/01-architecture-upgrade-report.md` §5.1):
  ```
  source/
    _global/
    java/
      _core/
      spring-boot/
        architecture/
        controller/
        service/
        repository/
        error-handling/
        di/
        config/
        testing/
  ```
- The empty-glob convention: when **every** layer in `scope.layers` resolves to `[]` in the layer-glob map (today, only `architecture` does), the compiler routes that rule to Cursor's `alwaysApply: true` mode. This is the one and only mechanism by which "always-apply" is reachable from a non-explicit author declaration.
- One file per rule. Even if two rules conceptually belong to the same layer (e.g., `controller/validation-boundaries.md` and `controller/dto-record-mandate.md`), they remain separate files so each compiles to its own MDC with its own description and its own change history.
- The `_global/` and `_core/` directories carry rules that are **language-** or **framework-agnostic** (e.g., security baselines, logging conventions). They use the `all` or `architecture` layers and follow the same compilation rules.

---

## 3. Status

**Accepted** — effective 2026-05-18. Supersedes the `languages/<lang>/<framework>/<concern>.md` layout in `docs/ai-engineering-standards-blueprint.md` §2. Implementation begins in Phase 1 (scaffolding) and is binding on all content authored in Phase 3 and beyond. Subject to AI Enablement PM sign-off in the closing Phase 0 PR.

---

## 4. Consequences

### Positive

- **Glob precision becomes mechanical.** Each source file's compiled MDC has exactly the globs implied by its `scope.layers` — no manual tuning, no per-rule glob string in source frontmatter.
- **A controller-edit prompt sees only controller-relevant rules.** Per `docs/01-architecture-upgrade-report.md` §5.4, the expected reduction is from ~35 rules to ~8 (~77% noise reduction) on a typical controller file.
- **Rule renames stay local.** Moving `controller/validation-boundaries.md` to `controller/request-validation-boundaries.md` changes one rule-id and one file; nothing else.
- **Authoring stays in plain Markdown.** Despite the schema apparatus, the author edits exactly one Markdown file per rule. The layer is a directory, not a YAML field they have to remember to update.
- **The compiler's glob resolver is a pure function** of `(scope.layers, layer-glob-map.json)`. No business logic per rule. This makes Phase 4 (`compiler/core/resolve_globs.py`) a one-day task with full test coverage.
- **Cross-cutting rules remain expressible.** A rule that genuinely spans two layers declares `scope.layers: [repository, controller]` and the compiler produces a deduplicated union glob. Genuinely-everywhere rules use `[all]` (broad glob) or `[architecture]` (alwaysApply).

### Negative / Costs

- **More files in `source/`.** The baseline's ~6 Markdown files per stack expand to ~16. Mitigated by predictable directory shape and tooling (golden tests catch regressions; the authoring guide walks new contributors through it).
- **The layer catalog is closed.** Adding a new layer (e.g., `messaging`) requires updating `schemas/source-rule.schema.json` AND `schemas/layer-glob-map.json` AND, potentially, the compiler. This is by design — the schema is a contract — but it does add a small process step. Mitigated by treating the schemas themselves as a Phase 2 deliverable subject to the same PR review as any other code change.
- **A rule that *should* span layers may be over-split** by an author who hasn't internalized the catalog. Mitigated by the authoring guide (Phase 3) showing canonical examples and by Standards-Architect review on every source-PR (per `docs/02-implementation-plan.md` §2.3).
- **The layer-glob map becomes a coordination hot spot** across languages. Mitigated by golden-file tests: any change to the map produces a reviewable diff in every generated MDC and is caught at PR time.
- **Migration cost from the baseline layout is non-trivial.** Four baseline rules (the two existing error-handling rules + the unified API error + Problem Details RFC 7807) plus the four new Logic Holes' ~12 files = ~16 source files. This is the Phase 3 workload (`docs/02-implementation-plan.md` §6) and is accepted as a one-time cost.

---

## 5. Alternatives Considered

### Alt 5.1 — Keep "one file per concern"; encode the glob directly in source frontmatter

**Why considered**: Minimum-change path; preserves the baseline file count.

**Why rejected**: Pushes the glob-resolution responsibility from a deterministic schema (`layer-glob-map.json`) into every rule author's head. The two pathologies follow:
- **Inconsistent globs across rules** ("did the previous controller rule use `**/controller/**/*.java` or `**/controllers/**/*.java`?").
- **Globs that drift from filesystem conventions** as projects rename packages.
Centralizing the language→layer→glob map is the only way to keep the corpus internally consistent.

### Alt 5.2 — Use a flat `source/` directory and rely entirely on frontmatter `scope` fields

**Why considered**: Eliminates directory-tree-vs-frontmatter duplication; the layer becomes the frontmatter field, not the path.

**Why rejected**: Loses two affordances:
1. **Filesystem-navigable browsing.** Authors and reviewers can `ls source/java/spring-boot/controller/` to see "every controller rule." This is high-value during PR review and onboarding.
2. **Implicit invariant.** A misfiled rule (e.g., `controller/transactional-readonly.md`) is visually wrong. With flat layout, only the frontmatter catches it, and only at compile time.

The directory tree is a redundant encoding of `scope.layers[0]`, but it is a *human-checkable* one. Cost is low; value is meaningful.

### Alt 5.3 — Split by AI tool (a directory per Cursor/Copilot/Claude/Junie) rather than by layer

**Why considered**: Matches the eventual distribution shape (`dist/stacks/<stack>/cursor/`, `dist/stacks/<stack>/copilot/`, etc.).

**Why rejected**: Inverts the source-of-truth contract. Per `docs/01-architecture-upgrade-report.md` §3.6, the goal is **one authoring source → many distribution targets**. Splitting source by tool means a controller-validation rule has to be authored 5 times (once per tool), with all the duplication and drift problems multi-source duplication causes. The layer is a property of the *rule*; the tool is a property of the *distribution*. The two belong on different axes.

### Alt 5.4 — Split by Logic Hole number (`source/logic-hole-3/`, `source/logic-hole-4/`, ...)

**Why considered**: Matches the architecture report's narrative structure (§2.1–2.4).

**Why rejected**: The Logic Hole catalog is a *cross-cutting taxonomy of failure modes*, not a unit of activation. Logic Hole #4 alone produces 6 source files spanning the `service`, `repository`, and `config` layers — each needing a different glob. The catalog is preserved as the `related_logic_holes:` frontmatter field, which is the right axis (a property of the rule), not the directory shape.

### Alt 5.5 — Two-level split by layer + concern (`source/.../controller/validation/<rule>.md`)

**Why considered**: Even finer granularity for very large rule catalogs.

**Why rejected**: Premature. At ~3–4 rules per layer per stack, a third level is over-engineering. Revisit if/when any single `layer/` directory exceeds ~10 rules. (Tracked informally; no plan revision yet.)

---

## 6. References

- `docs/01-architecture-upgrade-report.md` §4.2 — full critique of the "one file per concern" baseline layout.
- `docs/01-architecture-upgrade-report.md` §5.1 — target authoring repo hierarchy with the layer-keyed split.
- `docs/01-architecture-upgrade-report.md` §6.2 — example `schemas/layer-glob-map.json` payload.
- `docs/02-implementation-plan.md` §5 — Phase 2 deliverables that codify this ADR (`schemas/source-rule.schema.json` and `schemas/layer-glob-map.json`).
- `docs/02-implementation-plan.md` §6 — Phase 3 content migration plan that creates the layer-keyed file fan.
- `decision-records/0001-mdc-over-cursorrules.md` — sibling ADR that makes MDC the primary target this split serves.
