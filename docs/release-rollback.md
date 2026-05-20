# Release Rollback Procedure — `engineering-standards-central`

> **Audience**: Standards Architect, AI Enablement PM, on-call Compiler Engineer.
> **Purpose**: Document the canonical procedure for rolling back a bad release. The procedure
> is shaped by ADR-0004's "no moved tags, no force-pushes" invariant — every rollback produces
> a new tag, never a mutation of an existing one.
>
> **Source of authority**: `docs/02-implementation-plan.md` §10 task 6;
> `docs/decision-records/0004-single-repo-distribution.md` §4.

---

## 1. When to Roll Back

A release is rolled back when any of the following is true for the just-cut tag:

| Symptom | Severity | Pilot/consumer impact |
|---|---|---|
| `dist-protection-lint` or `golden-snapshots` was red on the release commit but the operator pressed `Run workflow` anyway | High | A consumer's `npx @org/standards-sync` will fetch broken content. |
| A pilot reports `npx @org/standards-sync` writes a malformed `.cursor/rules/*.mdc` | High | Cursor silently ignores the malformed file; pilot's AI behavior degrades. |
| A pilot reports CI failure in their own repo after pulling the new release | Medium | Pilot's build is red but the pilot's previous pin still works locally; revert is non-urgent. |
| A regression in source rules is discovered post-release (e.g., a rule was over-broadened and now incorrectly fires on legitimate code) | Medium | AI guidance becomes annoying / wrong; pilots will pin to the prior version. |
| Compiler bug shipped a non-deterministic field (e.g., a generation timestamp leaked into `dist/`) | Low | The next release diff is noisy; downstream `git diff` reviews degrade. Roll forward, don't roll back. |

For Low-severity issues, **roll forward** with the fix as the next release. Roll BACK only when
the symptom actively harms a consumer's working repository.

---

## 2. The Two Rollback Paths

Both paths produce a **new tag**. Neither path mutates the bad tag (`v2.4.0` continues to exist
in git history with the bad content; consumers pinning to `v2.4.0` see exactly what shipped).

### Path A — Re-release against the prior good commit

This is the **default** rollback path. It is mechanical, takes ~5 minutes, and produces a tag
with the same content as the prior good release.

```text
Sequence:
  v2.3.5  (good, prior release)
  v2.4.0  (bad release — DO NOT delete or move)
  v2.4.1  (rollback release — re-cut at v2.3.5's commit content, with the new tag)
```

**Procedure**:

1. Identify the prior good commit. Most commonly this is the commit at the prior release tag:
   ```bash
   git log --tags --simplify-by-decoration --pretty='%H %D' | head -5
   ```
2. Navigate to **Actions → release → Run workflow**.
3. Fill in the form:
   - **ref**: the SHA of the prior-good commit (e.g., the commit at `v2.3.5`). NOT the tag —
     the workflow reads from the SHA, and reusing the prior commit gives byte-identical content.
   - **force-bump**: leave on `(auto)`. The default classifier sees zero new feat/fix commits
     since `v2.4.0` and emits a patch bump → `v2.4.1`.
   - **dry-run**: `false`.
4. Click **Run workflow**.
5. After completion, verify:
   ```bash
   git fetch --tags
   git diff v2.3.5..v2.4.1 -- dist/   # Expected: empty (byte-identical dist trees).
   ```
6. Announce the rollback:
   - GitHub Release page for `v2.4.1` — append "**Rollback of v2.4.0.** See
     `docs/release-rollback.md` Path A."
   - `#engineering-standards-central` Slack channel — link the new Release and the failure
     mode of `v2.4.0`.
   - If any pilot is already pinned to `v2.4.0`, file a ticket in their repo with the pin-bump
     diff.

**Why this works**: re-cutting at the prior-good commit reuses the prior-good source tree, so
the compiler regenerates the prior-good `dist/` content. The tag is new (`v2.4.1`); the content
is the same as `v2.3.5`. Consumers who pin to a tag see a clean upgrade path.

### Path B — Manual revert PR

Use Path B when the bad release **also** included a malformed source-rule change that needs
explicit cleanup before the next release. For example, if `v2.4.0` introduced a new source
rule whose `framework_version` regex was wrong AND the bad dist tree, Path A would correctly
restore the dist tree but the broken source rule would still be on `main`.

**Procedure**:

1. Open a PR titled `revert(release): roll back v2.4.0`.
2. The PR body must reference this document and explain the failure mode.
3. The PR's diff must:
   - Revert the offending source/ rule changes (use `git revert <commit-sha>` to preserve the
     bisect history).
   - Leave `dist/` UNCHANGED in the PR (the `dist-protection-lint` check will otherwise block
     the PR).
4. After the PR merges, dispatch `release.yml` against the new `main` tip. The auto-classifier
   sees one or more `revert:`-prefixed commits — these are classified as `none` by the
   Conventional Commits parser, so the bump defaults to patch (`v2.4.0` → `v2.4.1`).
5. Same announcement steps as Path A step 6.

**Why this works**: the `revert:` commit ships through normal PR review (CODEOWNERS routes
to platform-team + standards-council per `.github/CODEOWNERS`), preserving the audit trail.
The release that follows ships a clean dist tree compiled from the corrected source.

---

## 3. What You Must NEVER Do

The following operations would violate ADR-0004's "no moved tags, no force-pushes" invariant
and break consumer trust in the version timeline.

### ❌ Never delete the bad tag

```bash
# DO NOT do this. Consumers pinning to v2.4.0 will get a 404 on archive fetch.
git push origin :refs/tags/v2.4.0
```

The bad tag is part of history. Leave it alone. The Release page on GitHub can be marked as
"pre-release" or have a top-line warning added; the underlying tag stays.

### ❌ Never move the bad tag to a new commit

```bash
# DO NOT do this. Consumers who already fetched v2.4.0 see one content;
# consumers who fetch after the move see different content; chaos ensues.
git tag -d v2.4.0
git tag -a v2.4.0 <good-sha>
git push --force origin refs/tags/v2.4.0
```

GitHub's tag-protection rules (when configured) will reject this push, but the operator
should know NOT to attempt it regardless. A tag is an immutable promise.

### ❌ Never force-push `main`

```bash
# DO NOT do this. Branch protection rejects it, but even if it didn't,
# every consumer who pulled main since the bad commit has the bad SHA in their
# local clone — re-syncing becomes manual.
git push --force origin main
```

The release workflow under the `@standards-bot` App identity does **not** have force-push
permission (per `docs/branch-protection-config.md` §2.5). Branch protection rejects the
attempt at the API layer. This is by design.

### ❌ Never edit `dist/` directly to "fix" the bad release

A human commit to `dist/` is blocked by:

1. CODEOWNERS routing the PR to `@standards-bot` for review (G1).
2. The `dist-protection-lint` PR status check failing the PR (G2).
3. Branch protection rejecting the direct push to `main` (G3).
4. The opt-in pre-commit hook at `tools/git-hooks/pre-commit` blocking the local commit (G4).

Even if all four guards failed simultaneously, the next `release.yml` dispatch would overwrite
the manual fix with the compiler's output. The dist tree is **machine-generated**; manual
fixes are not durable.

---

## 4. Communication Template

Use this template for the announcement after either rollback path completes. Adapt as needed.

```markdown
:rotating_light: **Engineering Standards rollback: v2.4.0 → v2.4.1**

**Symptom**: <one-line description of what consumers saw>
**Path**: <A or B>
**New tag**: `v2.4.1`
**Diff from prior good release**: ```git diff v2.3.5..v2.4.1 -- dist/``` → <expected: empty>
**Action required for pilots**:
  - If you are pinned to `v2.4.0`, update `.standards-version` to `v2.4.1` and re-run
    `npx @org/standards-sync`.
  - If you are pinned to `v2.3.5` (or earlier), no action required — `v2.4.0` was
    skippable for your repo.

Postmortem: <link to issue documenting root cause>
```

---

## 5. Post-Mortem Trigger

A rollback **always** triggers a postmortem. The postmortem is filed as an issue with the
label `release-postmortem` in `engineering-standards-central` and covers:

1. **What shipped wrong**: the specific source-rule change, compiler bug, or schema change
   that produced the bad output.
2. **Why CI missed it**: which of the existing checks (golden-snapshots, schema-validation,
   compiler-unit-tests) should have caught the regression but did not.
3. **Test gap to close**: the new test (added in the postmortem's own PR) that would catch a
   recurrence.
4. **Process change** (optional): if the failure was a CI configuration gap or an
   operator-action gap, the postmortem proposes the doc or workflow change that closes it.

The Standards Architect owns the postmortem. The AI Enablement PM signs off on closure.

---

## 6. Recovery Drill (Optional, Recommended Quarterly)

To verify Path A works end-to-end without an actual incident, run a recovery drill on a
non-production tag. The drill is:

1. Cut a no-op release (`workflow_dispatch` with `dry-run: true`) to confirm the workflow
   green-paths.
2. Cut an intentional patch release (`dry-run: false`) — e.g., `v2.X.Y` against current `main`.
3. Re-dispatch `release.yml` against the prior commit, producing `v2.X.(Y+1)` with byte-identical
   content to the prior release.
4. Confirm `git diff v2.X.Y..v2.X.(Y+1) -- dist/` is empty.

If step 4 is non-empty, there is non-determinism in the compiler that the Phase-6 golden
snapshots failed to catch. File a bug.

---

## 7. References

- `docs/02-implementation-plan.md` §10 task 6 — the rollback-doc task list entry.
- `docs/decision-records/0004-single-repo-distribution.md` §4 — the "no moved tags" invariant.
- `docs/branch-protection-config.md` §2.5 — force-push disabled.
- `.github/workflows/release.yml` — the workflow that re-dispatches produce rollbacks.
- `docs/release-bot-setup.md` — `@standards-bot` provisioning prerequisites.
