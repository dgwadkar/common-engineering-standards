# ADR-0004 — Single-Repo Distribution via a Protected `dist/` Folder

- **Status**: Accepted
- **Date**: 2026-05-18
- **Deciders**: Standards Architect, Compiler Engineer, AI Enablement PM (sign-off pending operator review)
- **Phase**: 0 — Pre-Flight Decisions and ADRs
- **Related documents**:
  - `docs/02-implementation-plan.md` Architecture Note (Revision 2) — single-repo decision summary
  - `docs/02-implementation-plan.md` §3 (Phase 0 task list — explicit ADR-0004 content)
  - `docs/02-implementation-plan.md` §4 (Phase 1 scaffolding — `dist/`, CODEOWNERS, branch protection)
  - `docs/02-implementation-plan.md` §10 (Phase 7 release workflow + `dist/` protection)
  - `docs/02-implementation-plan.md` §14 R-11, R-12, R-13 (risk register entries that bound this decision)
  - `docs/01-architecture-upgrade-report.md` §5.2 (target distribution-repo layout — preserved as `dist/` subtree)

---

## 1. Context

`docs/01-architecture-upgrade-report.md` §5.2 proposed a separate `engineering-standards-distribution` repository as the destination for compiled artifacts. The two-repo model is industry-conventional (Backstage/Roadie service-catalog patterns, JetBrains' `junie-guidelines` separation, etc.) and provides four functional guarantees:

1. **Humans cannot write to compiled output** — the distribution repo's write access is granted only to a release bot.
2. **Compiled output has clean semver tags** decoupled from source-history noise.
3. **Releases are auditable** — every commit is bot-authored.
4. **Rollback is mechanical** — revert to the previous tag in the distribution repo.

However, the two-repo model also imposes nontrivial operational costs:

- **Permissions surface doubles.** Two repos to grant access to, two CODEOWNERS files, two branch-protection configs, two CI pipelines.
- **Source↔output commits are non-atomic.** A change to a source rule and the regenerated `dist/` artifact live in different repos with different timestamps; reasoning about "what does v2.4.0 look like end-to-end" requires crossing a repo boundary.
- **Cross-repo CI choreography.** Phase 5's compile.yml had to open a PR against a second repo, complicating the failure modes (PR rejected? merged out-of-order? credentials rotated?).
- **Consumer URL drift.** Every consumer (`@org/standards-sync` and its Maven/Gradle wrappers) points at a second hostname/path.

Late in Phase 0 reading, the Architect and Compiler Engineer revisited whether these costs are bought back by the four guarantees — or whether the same guarantees can be reproduced inside a single repository at substantially lower operational cost.

The conclusion (reflected in `docs/02-implementation-plan.md`'s Revision 2 architecture note): **the four guarantees can be preserved inside a single repository via four layered guards**, and the cost reduction is large enough to justify the change for the MVP and for the foreseeable post-MVP horizon. The two-repo split remains a designed graduation path for the day it becomes necessary.

The decision to be recorded: **does the project use one repository (`engineering-standards-central`) for both source and compiled distribution, or two (`engineering-standards-central` for source + `engineering-standards-distribution` for compiled)?**

---

## 2. Decision

**The project uses a single repository, `engineering-standards-central`. Compiled artifacts live in a protected `dist/` folder inside that repository. The previously-proposed second repo is preserved only as a documented graduation path.**

### 2.1 Repository shape

```
engineering-standards-central/
├── source/                # authored Markdown (humans write)
├── compiler/              # transformer pipeline (humans write)
├── schemas/               # frontmatter & layer-glob contracts (humans write)
├── fixtures/, tests/      # CI verification (humans write)
├── docs/                  # ADRs, plans, authoring guides (humans write)
├── dist/                  # ★ compiled outputs (humans NEVER write)
│   ├── README.md          # auto-generated index
│   ├── CHANGELOG.md       # auto-generated
│   └── stacks/
│       ├── java-spring-boot-3/...
│       ├── java-spring-boot-2/...
│       ├── typescript-nestjs-10/...
│       └── python-fastapi-0-110/...
├── .github/
│   ├── CODEOWNERS         # /dist/ owned by @standards-bot
│   └── workflows/
│       ├── validate.yml
│       ├── dist-protection-lint.yml
│       └── release.yml    # manual dispatch; the only writer of /dist/
└── .cursor/, AGENTS.md    # the central repo's own dogfood rules
```

### 2.2 The four guards that keep `dist/` effectively read-only to humans

| Guard | Mechanism | Owner | Phase that ships it |
|---|---|---|---|
| **G1 — CODEOWNERS routing** | `.github/CODEOWNERS` routes `/dist/` to `@standards-bot` (a non-human GitHub App account). Humans editing `/dist/` see review auto-requested from a bot that never approves. | Phase 1 | `docs/02-implementation-plan.md` §4 Task 5 |
| **G2 — Required status check** | `.github/workflows/dist-protection-lint.yml` is a blocking PR check. It fails any PR whose diff includes `/dist/**` unless every commit's author is the `@standards-bot` GitHub App. | Phase 7 | `docs/02-implementation-plan.md` §10 Task 3 |
| **G3 — Branch protection on `main`** | `main` requires PR before merge, requires the `validate`, `golden-tests`, and `dist-protection-lint` checks, restricts pushes to the `@standards-bot` App (release commits only), and requires linear history with force-push disabled. | Phase 1 (documented), Phase 7 (enforced in GitHub UI) | `docs/02-implementation-plan.md` §4 Task 6 + §10 Task 4 |
| **G4 — Client-side pre-commit hook** | `tools/git-hooks/pre-commit` fails any commit whose staged changes include both `source/**` and `dist/**` paths when the author is a human. Opt-in via `git config core.hooksPath tools/git-hooks/`. Defense-in-depth only. | Phase 1 | `docs/02-implementation-plan.md` §4 Task 10 |

R-13 in `docs/02-implementation-plan.md` §14 captures the residual risk: all three required guards (G1+G2+G3) would have to fail simultaneously for a human-authored `/dist/` change to land. G4 is a fourth, opt-in, local safety net.

### 2.3 Release identity

A dedicated **GitHub App named `@standards-bot`** is registered with `contents: write` and `pull-requests: write` scoped to **only** `engineering-standards-central`. Its App ID and private key live in repo secrets (`STANDARDS_BOT_APP_ID`, `STANDARDS_BOT_PRIVATE_KEY`). Every commit produced by the `release.yml` workflow is authored as `@standards-bot`. This makes `git log --author=standards-bot` the audit log of every release, and the branch-protection "restrict who can push" setting is keyed to this single non-human identity (R-11 mitigation).

### 2.4 Graduation triggers (documented escape hatch)

If **any one** of the following becomes true, the team migrates to the two-repo model (`engineering-standards-distribution` extracted via `git filter-repo`). The migration mechanics are scripted: one `git filter-repo` invocation, one consumer URL update.

- **(GT-1)** The standards become a **public artifact consumed outside the org**, requiring a publishing repo with a different access model than the source repo.
- **(GT-2)** `dist/` history **bloats sync performance**. Concretely: repo total size > 500 MB **or** `dist/` history alone > 250 MB **or** sparse-archive download latency on the consumer side > 5s at p95.
- **(GT-3)** **Security or compliance** mandates a separately-audited publishing repo (e.g., SOC 2 separation-of-duties finding, regulator request).
- **(GT-4)** **Read access on the dist artifact must be granted to a wider audience than read on source** (e.g., contractors get standards but not authoring history).

The graduation migration cost is bounded: `git filter-repo --path dist/` produces the new repo; the consumer sync tool (`@org/standards-sync`) flips a single URL constant; the central repo's `release.yml` updates its push target. Estimated effort: one engineer-day.

### 2.5 Compatibility with the architecture report

`docs/01-architecture-upgrade-report.md` §5.2 describes a tree under "Distribution Repository (`engineering-standards-distribution`)". That tree is preserved **verbatim** as the subtree under `dist/` in this single-repo model. No content shape changes — only the surrounding repository identity. Consumers see the same `stacks/<stack>/cursor/`, `stacks/<stack>/copilot/`, etc. layout (now under `engineering-standards-central/dist/`, fetched via the GitHub tarball API at a release tag).

---

## 3. Status

**Accepted** — effective 2026-05-18. Revises the two-repo model proposed in `docs/01-architecture-upgrade-report.md` §5.2. The graduation triggers in §2.4 are the formal mechanism for revisiting this decision. Subject to AI Enablement PM sign-off in the closing Phase 0 PR.

---

## 4. Consequences

### Positive

- **Atomic source↔dist commits at release time.** A `v2.4.0` release is one commit on `main` containing the regenerated `dist/` tree. Reverting a release is reverting one commit. There is no "the source was updated in repo A but repo B hasn't caught up yet" failure mode.
- **One permissions surface, not two.** A single CODEOWNERS, a single branch-protection config, a single GitHub App scope. Reduces the failure modes per `docs/02-implementation-plan.md` §14 R-11.
- **Faster MVP critical path.** `docs/02-implementation-plan.md` §16 shows Phase 7 dropping from a previous 4 days (two-repo) to 2 days here. The total critical path is ~8.5 weeks instead of ~9.
- **Easier debugging.** "What does v2.4.0 of rule X look like?" answered by checking out tag `v2.4.0` and reading `dist/stacks/<stack>/cursor/rules/X.mdc`. No second-repo lookup.
- **Simpler consumer fetch.** `@org/standards-sync` fetches the tarball of `engineering-standards-central` at tag `v2.4.0`, scoped to `dist/stacks/<stack>/`. One URL, one auth scope.
- **`dist/README.md` lives next to its source.** Generated docs about the distribution shape live next to the compiler that produced them.

### Negative / Costs

- **`dist/` history accumulates in the source repo.** Markdown text is small (~50 KB per release × ~24 releases/year ≈ 1.2 MB/year), but it is monotonic. Mitigated by: (a) R-12 monitoring at quarterly cadence, (b) the GT-2 graduation trigger fires deterministically before consumer-side performance degrades.
- **Branch protection on `main` must be strict from day one.** A misconfigured "Allow force pushes" setting could destroy release history. Mitigated by: (a) documenting the exact branch-protection settings in `docs/branch-protection-config.md` (Phase 1), (b) screenshot-verified application in the closing PR of Phase 1 and Phase 7.
- **The `dist-protection-lint` check must be defensive.** A bug in its diff analysis could let a human-authored `/dist/` change slip past CI. Mitigated by: (a) pytest unit tests for the check itself (Phase 7), (b) G1 (CODEOWNERS) catches the change at review-request time even if G2 misfires, (c) G4 (pre-commit hook) catches it locally for opted-in authors.
- **The `@standards-bot` GitHub App is a high-value secret.** Its private key compromises release identity. Mitigated by: (a) scope limited to a single repo with `contents: write` only, (b) annual key rotation per R-11 mitigation, (c) quarterly audit of `git log --author=standards-bot`.
- **Loss of read-access asymmetry.** With two repos, you could grant outside contractors read on `engineering-standards-distribution` while keeping source private. The single-repo model makes that asymmetry unreachable without graduating. Acceptable for the current org scope (all consumers are internal); GT-4 fires the day this assumption breaks.
- **Loss of "publish to public" asymmetry.** If the standards corpus ever becomes a public artifact (open-sourcing the catalog), the source repo's full history goes with it unless we graduate first. GT-1 fires here.
- **Some external observers may expect a `org/engineering-standards-distribution` repo by convention.** Mitigated by: (a) `dist/README.md` explicitly documenting the single-repo decision and pointing back to this ADR, (b) the consumer sync tool's docs explaining the layout.

---

## 5. Alternatives Considered

### Alt 5.1 — Two-repo split (the original `docs/01-architecture-upgrade-report.md` §5.2 proposal)

**Why considered**: Industry-conventional; clearer read-permission separation; smaller source-repo history.

**Why rejected for MVP**: The four guarantees the two-repo split provides (humans-can't-write, semver tags, audit trail, mechanical rollback) are all reproducible inside a single repository with the four guards in §2.2, **and** preserving them inside one repo halves the operational surface, removes a cross-repo CI dance, and lets source↔dist changes land atomically. The two-repo model is correctly the **graduation target**, not the starting point. The graduation path is documented (§2.4), and the migration is a scripted one-day task — not a lock-in.

### Alt 5.2 — Single repo, no protection on `dist/` (trust the release workflow only)

**Why considered**: Simplest possible model.

**Why rejected**: One human commit to `/dist/` would corrupt the audit trail and could ship broken content to every consumer that pins the affected tag. The audit-trail guarantee from the two-repo model is genuinely valuable; preserving it via the four guards is the entire reason this decision is viable. Removing the guards collapses the model into "compiled output is whatever the last person typed," which we explicitly rejected when we chose to author in `source/` and compile to `dist/` rather than letting humans edit MDC directly.

### Alt 5.3 — Single repo, but `dist/` lives on an orphan branch (e.g., `gh-pages`-style)

**Why considered**: Keeps `main`'s file count smaller; one common GitHub pattern for compiled docs.

**Why rejected**: Loses the *atomic source↔dist commit* benefit that is one of the strongest reasons to choose single-repo. A release on an orphan branch is a separate commit graph; correlating a `dist/` state with the `source/` state that produced it requires a side-channel mapping (e.g., commit-message metadata). Defeats the "one git checkout shows the entire system at a point in time" property.

### Alt 5.4 — Publish `dist/` to a package registry (npm, Maven Central, PyPI) instead of a repo path

**Why considered**: Most consumer-friendly fetch story; standard package-manager UX.

**Why rejected**: Three reasons.
1. **Heterogeneous consumers.** Our consumers are a mix of Java, TypeScript, and Python projects; no single registry serves them all natively. The current sync model (`npx` CLI fetching a GitHub tarball) does.
2. **Atomicity loss.** A registry publish is a side effect of CI, not a commit. The "what did v2.4.0 look like" property weakens.
3. **Public-by-default.** Most package registries are public; making them private adds auth complexity our consumers don't need.

Revisit if/when GT-1 fires (public artifact).

---

## 6. References

- `docs/02-implementation-plan.md` Architecture Note (Revision 2) — the plan-level summary of this decision.
- `docs/02-implementation-plan.md` §3 — Phase 0 task list specifying this ADR's content in detail.
- `docs/02-implementation-plan.md` §4 — Phase 1 tasks: CODEOWNERS, branch-protection config doc, pre-commit hook.
- `docs/02-implementation-plan.md` §10 — Phase 7 tasks: `@standards-bot` registration, `release.yml`, `dist-protection-lint.yml`.
- `docs/02-implementation-plan.md` §10 "Why This Replaces a Second Repo" — the guarantee-by-guarantee comparison table.
- `docs/02-implementation-plan.md` §14 — risk register entries R-11 (single-repo blast radius), R-12 (`dist/` history bloat), R-13 (accidental `dist/` edit).
- `docs/01-architecture-upgrade-report.md` §5.2 — the original two-repo proposal this ADR revises.
- `decision-records/0001-mdc-over-cursorrules.md` — what `dist/stacks/<stack>/cursor/rules/` contains.
- `decision-records/0002-layer-keyed-source-split.md` — what `source/` looks like upstream of `dist/`.
