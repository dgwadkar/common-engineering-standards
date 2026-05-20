# Branch Protection Configuration — `engineering-standards-central`

> **Purpose**: GitHub branch-protection rules cannot be expressed in repo files. This document is the
> canonical checklist that the repository administrator applies in the GitHub UI (Settings → Branches →
> Branch protection rules). A screenshot of the final settings is attached to the closing PR for each
> phase that modifies them.
>
> **Source of authority**: `docs/02-implementation-plan.md` §4 (Phase 1, task 6) and §10 (Phase 7, task 4),
> plus `docs/decision-records/0004-single-repo-distribution.md` §2 (the protected-`dist/` decision).

---

## 1. Scope

These rules apply to the protected branch: **`main`**.

The repository operates a trunk-based-development model on `main`. There is no long-lived `develop`
branch. Release tags (`v<X.Y.Z>`) are cut directly off `main` by the release workflow (Phase 7).

---

## 2. Required Settings (Phase 1 baseline)

When applying these in the GitHub UI, tick every checkbox in the order listed. Items marked
**(Phase 7)** require the corresponding CI workflow or GitHub App to exist before the setting can be
saved without breaking PRs; until then the setting is left **off** and marked TODO.

### 2.1 Pull-request review

- [x] **Require a pull request before merging.**
- [x] **Require approvals**: minimum **1** approval.
  - Phase 3 onwards: bump to **2** (one Standards Architect + one Compiler Engineer) per
    `docs/02-implementation-plan.md` §2.1 review SLA.
- [x] **Dismiss stale pull-request approvals when new commits are pushed.**
- [x] **Require review from Code Owners.** Routes `/dist/` PRs to `@engineering-standards-bot` per
      `.github/CODEOWNERS`.

### 2.2 Status checks

- [x] **Require status checks to pass before merging.**
- [x] **Require branches to be up to date before merging.**
- Required status checks (must all pass — names are the **job names** in
  `.github/workflows/validate.yml`, not the workflow file names):
  - [x] `Repository tree shape (Phase 1 baseline)` — Phase 1 scaffold checks (job
        `tree-shape`).
  - [x] `Source-rule schema validation (Phase 2)` — Phase 2 schema-validation job
        (job `schema-validation`).
  - [x] `Compiler unit + end-to-end tests (Phase 4)` — Phases 4 and 5 compiler tests
        (job `compiler-unit-tests`).
  - [x] `Golden snapshots + ArchUnit fixture shape (Phase 6)` — Phase 6 snapshot tests
        (job `golden-snapshots`).
        > **Phase-7 reconciliation note (2026-05-20):** the original Phase-1 plan
        > entry referenced this as `golden-tests`. The Phase-6 implementation named
        > the job `golden-snapshots` (it covers both golden-snapshot tests and
        > ArchUnit-fixture shape tests, hence the more descriptive name). Phase 7
        > reconciles the doc to match the live job name — renaming the established
        > Phase-6 job would invalidate any operator's existing branch-protection
        > configuration without benefit. Decision recorded in
        > `docs/execution-log/phase-7-log.md` §5.
  - [x] `Dist protection (Phase 7 — block human edits to dist/)` — **(Phase 7)**
        the new PR-only job (`dist-protection-lint`) that blocks human authors from
        modifying `dist/**` per ADR-0004. The job is conditional on
        `github.event_name == 'pull_request'`, so on `push: branches: [main]`
        events it is correctly skipped (not failed). When configuring required
        status checks, mark this one as required only on PR contexts — GitHub's
        required-status-check matching is by job name, so the conditional skip
        does not block direct pushes to `main` from `@engineering-standards-bot`.

### 2.3 Conversation and merge rules

- [x] **Require conversation resolution before merging.**
- [x] **Require linear history.** Disallows merge commits on `main`; PRs must rebase or squash.
- [x] **Do not allow bypassing the above settings.** Applies to administrators too.

### 2.4 Push restrictions

- [x] **Restrict who can push to matching branches.**
- Allowed pushers (Phase 1 baseline): **empty** — i.e., nobody pushes directly; all changes flow
      through PRs.
- [x] **(Phase 7)** Add the `@engineering-standards-bot` GitHub App as an allowed pusher so that
      `release.yml` can push the regenerated `dist/` commit and the annotated tag.
      - The App is provisioned per `docs/release-bot-setup.md`. The operator action is:
        Settings → Branches → `main` → Edit → **Restrict who can push** →
        add `engineering-standards-bot` (the App appears as a selectable actor once installed).
      - **CRITICAL**: this setting must be applied BEFORE the first `release.yml` dispatch.
        Without it, the workflow fails at the push step with
        `refusing to update protected branch`. This is the gating operator action for
        Phase-7 AC2 (manual dispatch produces a single bot-authored commit + tag).
      - Verify the actor name renders correctly with the `verify_actors` API:
        `gh api /repos/{owner}/{repo}/branches/main/protection \
         --jq '.restrictions.apps[].slug'` should return `engineering-standards-bot`.

### 2.5 Force-push and deletion

- [x] **Disallow force pushes.** Even for administrators.
- [x] **Disallow deletions.**

### 2.6 Signed commits (optional but recommended)

- [ ] **Require signed commits.** Enable once org policy mandates it; the `@engineering-standards-bot` App must
      be configured to sign with a key the org's verification policy accepts.

---

## 3. Verification Procedure

After applying the settings, verify with the following manual checks. Each check should be repeated
whenever the configuration changes.

| # | Check | Expected result |
|---|---|---|
| V-1 | Push a commit directly to `main` from an admin account. | Rejected: "Protected branch update failed." |
| V-2 | Open a PR with no approvals; click Merge. | Disabled until ≥1 approval. |
| V-3 | Open a PR; force-push to the PR branch; confirm the prior approval was dismissed. | Approval is dismissed; PR returns to "Review required" state. |
| V-4 | (Phase 7) Open a PR that modifies `/dist/README.md` from a human account. | `dist-protection-lint` fails the PR with the message in plan §10 task 3. |
| V-5 | Force-push `main` from an admin. | Rejected. |
| V-6 | Delete `main` from the UI. | Rejected (option greyed out). |

---

## 4. Change-management Procedure

Branch-protection settings are themselves governed. Any change MUST:

1. Be proposed in a PR that modifies this file.
2. Be approved by the Standards Architect AND the AI Enablement PM.
3. Be accompanied by a screenshot in the PR description that shows the new settings applied in the
   GitHub UI immediately after merge.

The rationale: branch protection is the last line of defence between human error and the contents of
`dist/` (per `docs/decision-records/0004-single-repo-distribution.md` §2). Drift between the
documented checklist and the live settings is a governance bug.

---

## 5. Current Status

- **Phase 1**: this document is the deliverable. Acceptance criterion §4 of the Phase 1 task list
  is "Branch protection settings on `main` are documented in `docs/branch-protection-config.md` and
  applied in the GitHub UI (a screenshot is attached to the Phase-1 closing PR)." The **document is
  in place**; the **GitHub-UI apply step + screenshot** is the operator's action and is recorded in
  `docs/execution-log/phase-1-log.md` as a carry-forward acceptance criterion. The agent has no
  GitHub-API access in this session.
- **Phase 7 (as of 2026-05-20)**: the document is now reconciled with the live CI job names —
  `golden-snapshots` replaces the placeholder `golden-tests`, and the new `dist-protection-lint`
  job is listed as a required status check. The `@engineering-standards-bot` push permission entry is ticked
  in §2.4 with operator-action notes. **Apply-in-UI + screenshot remain operator actions** for
  Phase-7 AC4. The `release.yml` workflow has hard runtime dependencies on:
    1. The `STANDARDS_BOT_APP_ID` and `STANDARDS_BOT_PRIVATE_KEY` repo secrets being set
       (per `docs/release-bot-setup.md`).
    2. The §2.4 "Restrict who can push" setting allowing the `engineering-standards-bot` App.
  Until both are in place, `release.yml` will fail at the push step. This is by design — the
  failure mode is a clear operator-action prompt rather than a silent half-release.
- **Post-Phase-7 slug reconciliation (2026-05-20)**: The GitHub App was actually registered
  under the slug `engineering-standards-bot` (the bare `standards-bot` was unavailable on
  github.com). All references in this document and across the live workflow / test / doc
  surface have been updated to match. The two repo-secret NAMES
  (`STANDARDS_BOT_APP_ID`, `STANDARDS_BOT_PRIVATE_KEY`) are kept as-is — they are GitHub
  Actions context keys, not user-visible identity, and were already provisioned at the
  pre-reconciliation values. The first live release (`v0.1.0`, commit
  `28c02fb5`, 2026-05-20 06:31 UTC) shipped before the slug was fully reconciled and
  records `git author.name = "standards-bot[bot]"` in the commit metadata, but the
  GitHub-side commit attribution and Release author both correctly resolve to
  `engineering-standards-bot[bot]`. From `v0.1.1` onwards the git `user.name` will
  match the App slug.

---

## 6. References

- `docs/02-implementation-plan.md` §4 (Phase 1 task list).
- `docs/02-implementation-plan.md` §10 (Phase 7 release workflow & dist protection).
- `docs/decision-records/0004-single-repo-distribution.md` (single-repo distribution rationale).
- `docs/release-bot-setup.md` (the `@engineering-standards-bot` GitHub App provisioning checklist).
- `docs/release-rollback.md` (the release rollback procedure).
- `.github/CODEOWNERS` (review routing).
- `.github/workflows/validate.yml` (the live PR status checks).
- `.github/workflows/release.yml` (the release workflow whose only allowed pusher is the App).
