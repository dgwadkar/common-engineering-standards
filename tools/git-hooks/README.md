# Client-Side Git Hooks (Opt-In)

This directory ships a defensive **pre-commit hook** that blocks commits which
modify both `source/**` and `dist/**` in the same change. The hook is one of
three layered guards described in `docs/02-implementation-plan.md` §14 R-13
and in `docs/decision-records/0004-single-repo-distribution.md`.

## Why It Is Opt-In

GitHub branch-protection + the `dist-protection-lint` PR status check
(server-side, Phase 7) are the **authoritative** guards. The client-side hook
exists to surface the failure earlier — at `git commit` time, before a push
— but it is not authoritative because git hooks can be bypassed
(`git commit --no-verify`) and are not present on a fresh clone. Making it
opt-in respects developer autonomy on local tooling while still documenting
the org's recommendation.

## Enable

From the repository root:

```bash
git config core.hooksPath tools/git-hooks
chmod +x tools/git-hooks/pre-commit
```

`core.hooksPath` is a repo-local setting; it does not affect other repos on
the same machine.

## Disable

```bash
git config --unset core.hooksPath
```

## What the Hook Does

- Reads the list of files staged for the in-flight commit.
- If the staged set contains BOTH a path under `source/` AND a path under
  `dist/`, the hook aborts the commit with a clear message and lists the
  offending paths.
- Otherwise the hook is a no-op.

## Escape Hatch for the Release Workflow

The release workflow (Phase 7, `release.yml`) sets the environment variable
`STANDARDS_BOT_RELEASE_COMMIT=1` before running `git commit`. When the hook
sees that variable, it exits 0 unconditionally. This is safe because:

- The variable is set only inside the GitHub Actions runner.
- The release workflow runs as the `@engineering-standards-bot` GitHub App, whose commits
  are routed through CODEOWNERS to a non-human reviewer that never approves
  human PRs.

## What the Hook Does NOT Do

- It does NOT validate frontmatter (that is the job of the Phase 2
  `validate.yml` workflow).
- It does NOT compile or sync (those are the jobs of `release.yml` and the
  Node consumer-sync CLI).
- It does NOT block edits to `dist/` if no `source/` paths are staged in the
  same commit. The server-side `dist-protection-lint` check is responsible
  for that case; the client-side hook deliberately stays focused on the
  *mixed-commit* failure mode so it does not get in the way of the rare
  legitimate `dist/`-only manual edit (e.g., the Phase 1 scaffold edit to
  `dist/README.md`).
