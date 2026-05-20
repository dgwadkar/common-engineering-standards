# `@standards-bot` GitHub App — Registration & Operational Setup

> **Purpose**: GitHub Apps cannot be registered from inside a repository. This document is the
> canonical, step-by-step checklist that the repository administrator (Standards Architect OR
> AI Enablement PM) follows in the GitHub UI to provision the `@standards-bot` GitHub App that
> is the sole authorized writer of `dist/` per
> `docs/decision-records/0004-single-repo-distribution.md` §2.3.
>
> **Authoring agent has NO ability to execute these steps.** Every step below is an
> operator-only action. The Phase 7 acceptance criterion §10.AC1 / §10.AC2 / §10.AC5 cannot be
> ticked `[x]` until the App is registered, installed, and its credentials are stored in repo
> secrets.
>
> **Source of authority**: `docs/02-implementation-plan.md` §10 task 1 (App registration);
> ADR-0004 §2.3 (release identity); `docs/branch-protection-config.md` §2.4 (App as the only
> allowed pusher to `main`).

---

## 1. Why a GitHub App and not a Personal Access Token

A Personal Access Token (PAT) is tied to a human user and inherits that user's permissions
(including write access to every repo the user can touch). The single-repo distribution model
(ADR-0004) requires the opposite property: a release-only identity scoped to **exactly one
repository**, with `contents: write` and nothing else.

GitHub Apps give us:

1. **Identity isolation** — `@standards-bot` is a non-human author. `git log --author=standards-bot dist/`
   becomes the audit log of every release (AC5 of plan §10).
2. **Permission scoping** — the App is installed on **only** `engineering-standards-central`,
   not on the entire org. A leaked App key compromises one repo, not the whole org (R-11
   mitigation in plan §14).
3. **Auditable installation** — the App's installation, permission updates, and key rotations
   are recorded in the org's audit log.
4. **No human seat consumed** — Apps don't count against the org's user license; the App can
   commit and tag forever without paying for a bot user account.

---

## 2. Registration Procedure (Org Owner Only)

The operator performing these steps MUST have **Organization Owner** rights. If you only have
admin rights on the repository, you cannot register the App — escalate to the org owner.

### 2.1 Create the App

1. Navigate to **GitHub → Your organization → Settings → Developer settings → GitHub Apps**.
2. Click **New GitHub App**.
3. Fill in the form:

| Field | Value |
|---|---|
| GitHub App name | `standards-bot` |
| Description | Release identity for `engineering-standards-central`. Regenerates `dist/` on manual `release.yml` dispatch. See `docs/decision-records/0004-single-repo-distribution.md`. |
| Homepage URL | `https://github.com/<org>/engineering-standards-central` |
| Webhook → Active | **Unchecked** (no webhook events needed; the App is only invoked by `release.yml`). |
| Repository permissions → Contents | **Read and write** |
| Repository permissions → Pull requests | **Read and write** |
| Repository permissions → Metadata | **Read-only** (default, cannot be removed) |
| Organization permissions | **None** |
| Account permissions | **None** |
| Where can this GitHub App be installed | **Only on this account** |

4. Click **Create GitHub App**.

### 2.2 Capture the credentials

On the App's settings page, capture two values:

| Value | Where to find it | Stored as |
|---|---|---|
| **App ID** | Top of the App's settings page; numeric (e.g., `1234567`). | Repo secret: `STANDARDS_BOT_APP_ID` |
| **Private key** | Scroll to "Private keys" → **Generate a private key** → downloads a `.pem` file. **DO NOT lose this file** — GitHub does not retain a copy. | Repo secret: `STANDARDS_BOT_PRIVATE_KEY` (full file contents including the `-----BEGIN/END-----` lines) |

Both secrets are stored at **repository → Settings → Secrets and variables → Actions →
New repository secret**. Repository secrets (not environment secrets, not organization
secrets) are correct because `release.yml` runs in this repo only.

### 2.3 Install the App on the repository

1. From the App's settings page, click **Install App** in the left sidebar.
2. Select the org.
3. Select **Only select repositories** → `engineering-standards-central`.
4. Click **Install**.

After installation, the App appears under
**repo → Settings → GitHub Apps → standards-bot** with the granted permissions visible.

### 2.4 Verify the installation

Run this once-off sanity check from a workstation with `gh` CLI installed (no agent access
required):

```bash
# Replace <APP_ID> with the value from §2.2.
gh api /repos/<org>/engineering-standards-central/installation \
  --jq '.app_slug + " installed (id=" + (.id|tostring) + ")"'
# Expected: "standards-bot installed (id=<some-number>)"
```

If the output is `404`, the App is not installed on the repo — repeat §2.3.

---

## 3. Configure `release.yml` to Authenticate as the App

The release workflow at `.github/workflows/release.yml` uses the App credentials to mint a
short-lived installation token, then performs `git commit` + `git push` + `git tag` as the
App. The exact workflow YAML is already in the repo; what the operator needs to do is **only
store the two secrets from §2.2**. After that, the workflow runs without further setup.

The workflow authenticates with the official `actions/create-github-app-token@v1` action:

```yaml
- name: Mint an installation token for @standards-bot
  id: app-token
  uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ secrets.STANDARDS_BOT_APP_ID }}
    private-key: ${{ secrets.STANDARDS_BOT_PRIVATE_KEY }}
```

Every subsequent `git` operation in the workflow uses `${{ steps.app-token.outputs.token }}`
as the credential. The token expires one hour after issue, which is more than enough for a
single release run.

The commit author is set to the App's bot identity via:

```yaml
- name: Configure git as @standards-bot
  run: |
    git config user.name "standards-bot[bot]"
    git config user.email "<APP_ID>+standards-bot[bot]@users.noreply.github.com"
```

The `<APP_ID>+standards-bot[bot]@users.noreply.github.com` pattern is GitHub's canonical
no-reply email for a GitHub App identity. Substitute the App ID from §2.2; the workflow YAML
reads it from `${{ steps.app-token.outputs.app-slug }}` so this is computed dynamically and
does **not** need a code edit on App registration.

---

## 4. Branch-Protection Reconciliation

After the App is installed, the branch-protection settings on `main` must be updated to
allow the App to push directly (humans always go through PRs; the release workflow does not).
This is documented in `docs/branch-protection-config.md` §2.4 — the operator action is:

1. Navigate to **repo → Settings → Branches → Branch protection rules → `main` → Edit**.
2. Scroll to **Restrict who can push to matching branches**.
3. Add **standards-bot** under the actor list.
4. Save.
5. Update the screenshot in the Phase-7 closing PR.

Until this step is complete, `release.yml` will fail at the push step with a
`refusing to update protected branch` error. This is expected and is **the operator's
gating action** for §10.AC2 of the implementation plan.

---

## 5. Key Rotation (Annual)

The App's private key has no expiration on GitHub's side, but the org's security policy
should rotate it annually. The procedure is:

1. **Generate the new key**: App settings → Private keys → Generate a private key.
2. **Update the secret**: repo → Settings → Secrets → `STANDARDS_BOT_PRIVATE_KEY` → Update.
   - Paste the contents of the newly-downloaded `.pem`.
3. **Verify**: trigger a dry-run `release.yml` (a no-op release against the current `main`
   tip when no commits since last tag) and confirm it completes green.
4. **Revoke the old key**: App settings → Private keys → next to the **old** key → Delete.

The window between step 2 and step 4 is the brief period where both keys are accepted. After
step 4 the old key is invalid; any leaked copy of the old `.pem` is now harmless.

Rotation cadence is documented as a calendar reminder for the Standards Architect AND the
AI Enablement PM (two-person mitigation per R-11).

---

## 6. Audit Procedure (Quarterly)

The Standards Architect runs this audit each quarter to verify the App's behavior remains
within scope:

```bash
# 1. Confirm every commit on `main` whose diff touches `dist/` was authored by the App.
git log --pretty='%H %an' main -- dist/ \
  | awk '$2 != "standards-bot[bot]" { print "VIOLATION:", $0; found=1 } END { exit found }'
# Exit 0 → audit passes. Exit 1 → at least one human-authored `dist/` commit slipped through;
# investigate immediately (G2/G3 misfire).

# 2. Confirm the App has no commits OUTSIDE `dist/`.
git log --author='standards-bot' --pretty='%H' main \
  | while read sha; do
      paths_outside=$(git show --name-only --pretty='' "$sha" | grep -v '^dist/' | grep -v '^$' || true)
      if [[ -n "$paths_outside" ]]; then
        echo "VIOLATION: $sha touched non-dist/ paths:"; echo "$paths_outside"
      fi
    done
# No output → audit passes. Any output → the App was used outside its intended scope.

# 3. Confirm the App's installed permissions still match §2.1.
gh api /repos/<org>/engineering-standards-central/installation/permissions
# Expected: { "contents": "write", "metadata": "read", "pull_requests": "write" }
```

Findings are recorded in the Standards Council meeting minutes for the quarter.

---

## 7. Disaster-Recovery: Lost Private Key

If the `.pem` file from §2.2 is lost (laptop dies, key file deleted, etc.) the workflow
breaks but the data is not lost. The recovery is:

1. The org owner navigates to the App's settings → Private keys → **Generate a private key**.
   A second key is generated; the old one (which only exists locally on the lost device) is
   useless without the corresponding key data on disk.
2. Update `STANDARDS_BOT_PRIVATE_KEY` repo secret with the new `.pem` contents.
3. Trigger a release run to verify.
4. (Optional but recommended) Delete the orphaned old key from the App's settings.

There is **no need** to re-register the App or re-install it. The App identity, App ID, and
all installed permissions persist across key rotations.

---

## 8. Operator Checklist (Copy into the Phase 7 Closing PR)

When closing the Phase 7 PR, paste the checklist below and tick each box as the operator
action completes:

```markdown
- [ ] `standards-bot` App registered per `docs/release-bot-setup.md` §2.1
- [ ] `STANDARDS_BOT_APP_ID` repo secret stored per §2.2
- [ ] `STANDARDS_BOT_PRIVATE_KEY` repo secret stored per §2.2
- [ ] App installed on `engineering-standards-central` per §2.3
- [ ] `gh api .../installation` returns 200 per §2.4
- [ ] Branch-protection "Restrict who can push" updated to include `standards-bot` per §4
- [ ] Screenshot of branch-protection settings attached to this PR per §4
- [ ] Annual key-rotation reminder set on Standards Architect's calendar per §5
- [ ] Quarterly audit reminder set on Standards Architect's calendar per §6
```

---

## 9. References

- `docs/02-implementation-plan.md` §10 task 1 — the original Phase 7 task list entry for App registration.
- `docs/decision-records/0004-single-repo-distribution.md` §2.3 — the release-identity decision and the four-guard model.
- `docs/decision-records/0004-single-repo-distribution.md` §4 R-11 mitigation — annual key rotation + quarterly audit cadence.
- `docs/branch-protection-config.md` §2.4 — push-restriction settings keyed to the App identity.
- `.github/workflows/release.yml` — the workflow that consumes the App credentials.
- GitHub docs: [Authenticating with a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- `actions/create-github-app-token@v1` — the official Action used for installation-token minting.
