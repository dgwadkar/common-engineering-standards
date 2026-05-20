# ADR-0001 — Adopt `.cursor/rules/*.mdc` Over the Legacy `.cursorrules` File

- **Status**: Accepted
- **Date**: 2026-05-18
- **Deciders**: Standards Architect, Compiler Engineer, AI Enablement PM (sign-off pending operator review)
- **Phase**: 0 — Pre-Flight Decisions and ADRs
- **Related documents**:
  - `docs/01-architecture-upgrade-report.md` §3.1 ("Cursor `.cursor/rules/*.mdc` — The Native Standard (2026)")
  - `docs/01-architecture-upgrade-report.md` §4.2 Critique 2 ("Compilation Strategy Is 'Concatenate to `.cursorrules`' — A Deprecated Target")
  - `docs/02-implementation-plan.md` §3 (Phase 0 task list)
  - `docs/ai-engineering-standards-blueprint.md` §5.3 (the legacy concatenated `.cursorrules` model this ADR supersedes)

---

## 1. Context

The original `ai-engineering-standards-blueprint.md` proposed a CI pipeline that concatenates every applicable rule into a **single `.cursorrules` file** dropped at the root of each consumer repository. That model was idiomatic when Cursor shipped only the "Ask"/"Edit"/"Composer" modes against a single rules blob.

Three independent facts about the 2026 Cursor product surface invalidate that model:

1. **Cursor Agent mode silently ignores `.cursorrules`.** The authoritative Cursor docs (`cursor.com/docs/rules`) and corroborating community references (PromptShelf 2026, design.dev, localskills.sh) all converge on this point. Agent mode is the dominant Cursor mode in 2026; a distribution that is invisible to Agent mode reaches roughly 0% of its target surface.
2. **MDC is the only Cursor format with per-file-pattern activation.** The `.cursor/rules/*.mdc` format introduces a YAML frontmatter contract with four activation modes:
   - **Always Apply** — loaded on every prompt (`alwaysApply: true`).
   - **Auto-Attached** — loaded only when a file matching the `globs:` pattern is in context.
   - **Agent-Requested** — loaded when the agent semantically decides it is relevant (rich `description:` required).
   - **Manual** — loaded only when the user `@rule-name`s it.
3. **A monolithic `.cursorrules` defeats the prompt-token economics that justify the system at all.** Compiling everything to "always apply" means **100% of our rules pay context cost on 100% of prompts**, even when the developer is editing a CSS file or a YAML config. Internal benchmarks against Vibecoding/PromptShelf 2026 suggest a >70% token reduction when MDC glob targeting replaces concatenation.

The decision to be recorded: **what is the primary Cursor distribution target for the Engineering Standards Framework?**

---

## 2. Decision

**The primary Cursor distribution target is `.cursor/rules/*.mdc` (one MDC file per source rule), authored once in `source/**/*.md` and compiled per stack into a fan of `.mdc` files under `dist/stacks/<stack>/cursor/rules/`.**

Concrete commitments:

- Every source rule produces exactly one MDC file per stack it applies to.
- MDC frontmatter is generated mechanically by `compiler/transformers/cursor_mdc.py` from the source rule's `scope.layers` (via `schemas/layer-glob-map.json`) and `activation.cursor_mode` fields.
- The default activation mode is **Auto-Attach** with a layer-resolved `globs:` array. `alwaysApply: true` is **reserved** for foundational rules (e.g., the generic-exception ban) and requires an explicit `activation.cursor_mode: always` in the source frontmatter — it is never the implicit default.
- Legacy `.cursorrules` is **deprecated as a first-class target**. If any internal consumer still ships one, it is sunset on a 90-day clock starting at Phase 10 kickoff per `docs/02-implementation-plan.md` §13 Task 3. The compiler will not emit `.cursorrules`; no transformer module exists for it.
- This ADR also forecloses authoring directly in MDC. Source remains in the richer two-layer Markdown schema defined in `docs/01-architecture-upgrade-report.md` §7; MDC is the *output*, not the *input*.

---

## 3. Status

**Accepted** — effective 2026-05-18. Supersedes the `.cursorrules` distribution model in `docs/ai-engineering-standards-blueprint.md` §5.3. Subject to AI Enablement PM sign-off in the closing Phase 0 PR.

---

## 4. Consequences

### Positive

- **Reaches Cursor Agent mode**, which `.cursorrules` does not. This alone justifies the decision.
- **Per-prompt token cost drops** an expected >70% relative to the concatenated model — only rules whose globs match the current context file are loaded.
- **Per-layer authoring becomes natural.** A controller-validation rule lives in `source/<lang>/<framework>/controller/...` and produces an MDC with `globs: ["**/controller/**/*.java"]`. The activation surface matches the semantic surface.
- **The compiler transformer is small.** `cursor_mdc.py` is one file translating between two well-specified schemas; no business logic.
- **Consumers can override locally** via `<subdir>/.cursor/rules/` (Cursor's native subdirectory precedence), without forking the central repo.

### Negative / Costs

- **Authors must learn the source-vs-target distinction.** The two-layer schema is not as immediately obvious as "edit the file Cursor reads." Mitigated by `docs/authoring-guide.md` (Phase 3 deliverable) and the central repo's own `.cursor/rules/authoring-style.mdc` (Phase 1 deliverable).
- **The layer→glob map (`schemas/layer-glob-map.json`) becomes a tightly-coupled hot spot.** Any change ripples to every generated MDC. Mitigation: golden-file snapshot tests (Phase 6) make the blast radius explicit and reviewable on every change.
- **Cursor MDC frontmatter is an informal spec** maintained by a vendor. Mitigation: the transformer is a single Python file with frontmatter validation; pinning to a known-good Cursor version and adjusting the transformer is a small, well-bounded patch. This risk is tracked as R-01 in `docs/02-implementation-plan.md` §14.
- **`alwaysApply: true` is now a privileged setting.** Authors who used to put everything in `.cursorrules` may over-use it. Mitigation: a `validate.yml` lint check rejects `activation.cursor_mode: always` without either an `architecture` layer or an explicit override comment (planned in Phase 2, tracked as R-06).

---

## 5. Alternatives Considered

### Alt 5.1 — Keep `.cursorrules` as primary; emit MDC only as a secondary target

**Why considered**: Minimum-change path; preserves the existing blueprint's pipeline.

**Why rejected**: Inverts the importance gradient. The dominant Cursor mode in 2026 is Agent mode, which ignores `.cursorrules`. Treating the deprecated format as primary would mean our most-loved-by-users distribution would silently fail to apply, while the new MDC target would be an afterthought maintained on a slower cadence. This is the opposite of where the leverage lies.

### Alt 5.2 — Emit MDC and `.cursorrules` at equal priority (dual primary)

**Why considered**: Belt-and-suspenders coverage for consumers still on older Cursor.

**Why rejected**: Multiplies maintenance burden (two transformers, two golden-file sets, two doc paths) for a population that, per the rollout telemetry plan (`docs/02-implementation-plan.md` §12), is expected to be empty within 90 days of GA. The 90-day legacy sunset (§13 Task 3) is the right way to honor the long tail; a parallel-output policy is not.

### Alt 5.3 — Author directly in MDC; skip the source-format layer

**Why considered**: Eliminates the compile step; what authors write is what Cursor reads.

**Why rejected**: Tightly couples the standards corpus to Cursor's frontmatter format. We need to emit Copilot, Claude, Junie, and `AGENTS.md` outputs from the same source (see ADR-0002 and `docs/01-architecture-upgrade-report.md` §3.6). Authoring in MDC would force per-tool re-authoring or a lossy "MDC-as-source" parse. The two-layer model — richer source DSL → fan of tool-specific outputs — is the same pattern Backstage uses for software templates and is the industry-standard separation for multi-target documentation systems.

### Alt 5.4 — Ship `.cursor/rules/` as a single concatenated `.mdc`

**Why considered**: "Use the new format, but keep the single-file shape we know."

**Why rejected**: Defeats the entire reason the MDC format exists. A single `.mdc` can carry only one frontmatter block, so it would have to be `alwaysApply: true`, reproducing the token-cost problem `.cursorrules` had. The per-file glob targeting that makes MDC valuable requires a fan of files, one per scope.

---

## 6. References

- Cursor official docs: `https://cursor.com/docs/rules` (authoritative MDC specification).
- `docs/01-architecture-upgrade-report.md` §3.1 — Cursor MDC native-standard analysis.
- `docs/01-architecture-upgrade-report.md` §4.2 Critique 2 — why `.cursorrules` is a deprecated target.
- `docs/02-implementation-plan.md` §13 Task 3 — the 90-day legacy `.cursorrules` deprecation path.
- `docs/02-implementation-plan.md` §14 R-01 — risk register entry for Cursor MDC format drift.
