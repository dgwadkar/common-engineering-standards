"""Unit + integration tests for tools/compute_semver_bump.py (Phase-7).

The unit suite covers the four pure helpers:

* ``_classify_commit`` — header parsing + bump classification.
* ``_highest_bump``    — fold over multiple commits.
* ``_apply_bump``      — version increment.
* ``_parse_version``   — ``vX.Y.Z`` parser.

The integration suite spins up a temporary git repo, commits a synthetic history, and
invokes the CLI end-to-end to confirm the (header → bump → next-version) pipeline lines up.

The integration tests use a workspace-rooted temp directory (under ``tests/.tmp/``) instead
of the system tmp because some CI / sandbox environments deny write access to ``/tmp/.git/``
hooks. A ``conftest.py``-equivalent cleanup at the end of each test removes the temp tree.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

# Make tools/ importable without a setup file.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import compute_semver_bump as csb  # noqa: E402


# ---------------------------------------------------------------------------
# Workspace-rooted temp fixture (avoids /tmp sandbox restrictions)
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_tmp_path():
    """Yields a fresh per-test directory under ``tests/.tmp/`` (workspace-rooted).

    The system ``/tmp`` is unwritable to git hooks under some sandboxes; rooting under the
    workspace keeps every git operation inside writable space. The directory is removed
    after each test.
    """
    root = REPO_ROOT / "tests" / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = pathlib.Path(tempfile.mkdtemp(dir=str(root)))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Shared git env: empty template dir suppresses `.git/hooks/` population that some
# sandboxes block. Identity vars keep commits deterministic across machines.
_GIT_EMPTY_TEMPLATE = REPO_ROOT / "tests" / ".tmp" / "_empty_git_template"


def _make_git_env() -> dict:
    _GIT_EMPTY_TEMPLATE.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_TEMPLATE_DIR": str(_GIT_EMPTY_TEMPLATE),
    }


def _git_init_works_in_this_env() -> bool:
    """Probes whether `git init` can create a working repo in tests/.tmp/.

    Some sandboxes (including the one used for local agent development) deny writes to any
    nested ``.git/`` directory regardless of path. CI runners on GitHub Actions have no
    such restriction. When git init fails here, the integration tests skip gracefully so
    the unit suite (which covers the same logic) still runs.
    """
    probe_root = REPO_ROOT / "tests" / ".tmp"
    probe_root.mkdir(parents=True, exist_ok=True)
    probe = pathlib.Path(tempfile.mkdtemp(dir=str(probe_root), prefix="_git_probe_"))
    try:
        result = subprocess.run(
            ["git", "init", "-q", "-b", "main"],
            cwd=str(probe),
            capture_output=True,
            text=True,
            env=_make_git_env(),
        )
        return result.returncode == 0
    finally:
        shutil.rmtree(probe, ignore_errors=True)


_GIT_AVAILABLE = _git_init_works_in_this_env()
_GIT_SKIP_REASON = (
    "git init is blocked by the sandbox/environment; integration tests skipped. "
    "Unit tests above cover the same logic. CI runners do not have this restriction."
)
requires_git = pytest.mark.skipif(not _GIT_AVAILABLE, reason=_GIT_SKIP_REASON)


# ---------------------------------------------------------------------------
# Unit tests — pure helpers
# ---------------------------------------------------------------------------


def test_parse_version_strips_leading_v():
    assert csb._parse_version("v1.2.3") == (1, 2, 3)


def test_parse_version_accepts_no_leading_v():
    assert csb._parse_version("0.1.0") == (0, 1, 0)


def test_parse_version_rejects_two_part():
    with pytest.raises(ValueError):
        csb._parse_version("v1.2")


def test_parse_version_rejects_non_integer():
    with pytest.raises(ValueError):
        csb._parse_version("v1.x.3")


@pytest.mark.parametrize(
    ("header", "expected_type", "expected_bump"),
    [
        ("feat: add a new rule", "feat", "minor"),
        ("feat(controller): scope to controllers", "feat", "minor"),
        ("fix: typo in description", "fix", "patch"),
        ("fix(service): bad regex", "fix", "patch"),
        ("docs: update README", "docs", "none"),
        ("chore: bump dep", "chore", "none"),
        ("refactor(compiler): rename helper", "refactor", "none"),
        ("not a conventional commit", None, "none"),
        ("Merge pull request #42 from foo/bar", None, "none"),
    ],
)
def test_classify_commit_no_breaking(header, expected_type, expected_bump):
    c = csb._classify_commit("abc1234", header)
    assert c.type_ == expected_type
    assert c.bump == expected_bump
    assert c.is_breaking is False


def test_classify_commit_bang_marks_breaking_major():
    c = csb._classify_commit("abc1234", "feat!: drop deprecated API")
    assert c.is_breaking is True
    assert c.bump == "major"


def test_classify_commit_scoped_bang_marks_breaking_major():
    c = csb._classify_commit("abc1234", "feat(api)!: rewrite REST surface")
    assert c.is_breaking is True
    assert c.bump == "major"


def test_classify_commit_breaking_change_footer_marks_major():
    msg = "fix: cleanup\n\nBody text.\n\nBREAKING CHANGE: removes the old endpoint."
    c = csb._classify_commit("abc1234", msg)
    assert c.is_breaking is True
    assert c.bump == "major"


def test_classify_commit_breaking_change_dash_footer_also_recognized():
    msg = "fix: cleanup\n\nBREAKING-CHANGE: removes the old endpoint."
    c = csb._classify_commit("abc1234", msg)
    assert c.is_breaking is True
    assert c.bump == "major"


@pytest.mark.parametrize(
    ("bumps", "expected"),
    [
        (["minor", "patch", "none"], "minor"),
        (["patch", "none"], "patch"),
        (["none", "none"], "none"),
        (["major", "minor", "patch"], "major"),
        ([], "none"),
    ],
)
def test_highest_bump(bumps, expected):
    classifications = [
        csb.CommitClassification(sha=str(i), header="", type_=None, is_breaking=False, bump=b)
        for i, b in enumerate(bumps)
    ]
    assert csb._highest_bump(classifications) == expected


@pytest.mark.parametrize(
    ("prev", "bump", "expected"),
    [
        ((1, 2, 3), "major", (2, 0, 0)),
        ((1, 2, 3), "minor", (1, 3, 0)),
        ((1, 2, 3), "patch", (1, 2, 4)),
        ((1, 2, 3), "none", (1, 2, 3)),
        ((0, 0, 0), "minor", (0, 1, 0)),
    ],
)
def test_apply_bump(prev, bump, expected):
    assert csb._apply_bump(prev, bump) == expected


# ---------------------------------------------------------------------------
# Integration test — drive the CLI against a real temp git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_git_repo(workspace_tmp_path: pathlib.Path):
    """Yields a path to a fresh git repo containing a deterministic history."""
    repo = workspace_tmp_path / "repo"
    repo.mkdir()
    env = _make_git_env()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    git("init", "-q", "-b", "main")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.com")

    # Copy the compute_semver_bump.py script into the temp repo so the CLI can be invoked
    # from there (it uses `git` subprocess calls scoped to cwd).
    tools_dir = repo / "tools"
    tools_dir.mkdir()
    shutil.copy(REPO_ROOT / "tools" / "compute_semver_bump.py", tools_dir / "compute_semver_bump.py")
    git("add", "tools/compute_semver_bump.py")
    git("commit", "-m", "chore: scaffold")
    git("tag", "v1.0.0")

    yield repo, git


@requires_git
def test_cli_minor_bump_after_feat_commit(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "x.txt").write_text("hello", encoding="utf-8")
    git("add", "x.txt")
    git("commit", "-m", "feat: add x")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py", "--print-rationale"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    assert result.stdout.strip() == "v1.1.0"
    assert "minor" in result.stderr


@requires_git
def test_cli_patch_bump_after_fix_commit(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "y.txt").write_text("hello", encoding="utf-8")
    git("add", "y.txt")
    git("commit", "-m", "fix: correct y")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    assert result.stdout.strip() == "v1.0.1"


@requires_git
def test_cli_major_bump_on_breaking_change(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "z.txt").write_text("hello", encoding="utf-8")
    git("add", "z.txt")
    git("commit", "-m", "feat!: drop old API")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    assert result.stdout.strip() == "v2.0.0"


@requires_git
def test_cli_defaults_to_patch_with_no_conventional_commits(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "q.txt").write_text("hello", encoding="utf-8")
    git("add", "q.txt")
    git("commit", "-m", "rebase work")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    # Default behavior: defaults to patch when no feat/fix/breaking commits.
    assert result.stdout.strip() == "v1.0.1"


@requires_git
def test_cli_allow_empty_exits_4_when_no_bump_worthy_commits(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "q.txt").write_text("hello", encoding="utf-8")
    git("add", "q.txt")
    git("commit", "-m", "rebase work")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py", "--allow-empty"],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert result.returncode == 4
    assert "No bump-worthy commits" in result.stderr


@requires_git
def test_cli_force_bump_overrides_classification(temp_git_repo):
    repo, git = temp_git_repo
    (repo / "q.txt").write_text("hello", encoding="utf-8")
    git("add", "q.txt")
    git("commit", "-m", "fix: small")
    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py", "--force-bump", "major"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    assert result.stdout.strip() == "v2.0.0"


@requires_git
def test_cli_first_release_emits_v0_1_0(workspace_tmp_path: pathlib.Path):
    """When there is no previous tag, the CLI emits v0.1.0 regardless of commit signals."""
    repo = workspace_tmp_path / "fresh"
    repo.mkdir()
    env = _make_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True, env=env)
    (repo / "tools").mkdir()
    shutil.copy(REPO_ROOT / "tools" / "compute_semver_bump.py", repo / "tools" / "compute_semver_bump.py")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=str(repo), check=True, env=env)

    result = subprocess.run(
        [sys.executable, "tools/compute_semver_bump.py"],
        check=True, capture_output=True, text=True, cwd=str(repo),
    )
    assert result.stdout.strip() == "v0.1.0"
    assert "First release" in result.stderr
