"""Unit tests for tools/generate_dist_readme.py (Phase-7)."""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import generate_dist_readme as gdr  # noqa: E402


# ---------------------------------------------------------------------------
# Static structure
# ---------------------------------------------------------------------------


def test_render_includes_adr_0004_reference():
    """Phase-1 validate.yml's tree-shape job greps for this string. If it disappears,
    the next CI run on main breaks. This test pins the contract."""
    rendered = gdr._render("v0.1.0", pathlib.Path("/nonexistent"))
    assert "0004-single-repo-distribution" in rendered


def test_render_includes_version_and_changelog_link():
    rendered = gdr._render("v2.4.0", pathlib.Path("/nonexistent"))
    assert "`v2.4.0`" in rendered
    assert "CHANGELOG.md" in rendered


def test_render_lists_every_known_stack():
    rendered = gdr._render("v1.0.0", pathlib.Path("/nonexistent"))
    for entry in gdr.KNOWN_STACKS:
        assert f"`{entry['id']}`" in rendered


def test_known_stacks_align_with_compiler_stack_filter():
    """Defense-in-depth: the inline catalog in generate_dist_readme.py mirrors the runtime
    STACKS catalog in compiler.core.stack_filter. If a future PR adds a stack to one but
    not the other, this test fails loudly."""
    sys.path.insert(0, str(REPO_ROOT))
    from compiler.core.stack_filter import STACKS  # noqa: WPS433

    runtime_ids = set(STACKS.keys())
    readme_ids = {entry["id"] for entry in gdr.KNOWN_STACKS}
    assert runtime_ids == readme_ids, (
        f"Stack catalog drift detected. "
        f"Runtime has: {runtime_ids - readme_ids}, "
        f"README has: {readme_ids - runtime_ids}"
    )


def test_render_with_no_dist_root_marks_stacks_not_built():
    rendered = gdr._render("v1.0.0", pathlib.Path("/this/path/does/not/exist"))
    assert "_(not built)_" in rendered


# ---------------------------------------------------------------------------
# Live tree introspection
# ---------------------------------------------------------------------------


def test_render_against_freshly_built_tree(tmp_path):
    """Compile the live source corpus into tmp_path/dist/, then render. The Cursor-rules
    count column should report a non-zero integer for every stack."""
    out = tmp_path / "dist"
    out.mkdir()
    env = {"PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        [sys.executable, "-m", "compiler", "--all-stacks", "--target", "all", "--out", str(out)],
        capture_output=True,
        text=True,
        env={**env, **{k: v for k, v in __import__("os").environ.items() if k not in env}},
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        pytest.skip(f"compiler run failed in this env: {result.stderr[:200]}")

    rendered = gdr._render("v0.1.0", out)
    # Each stack has at least one cursor mdc; verify by absence of "0 `.mdc` files".
    assert "0 `.mdc` files" not in rendered
    # Each stack should list its non-cursor targets too.
    assert "Copilot" in rendered
    assert "Claude" in rendered
    assert "Junie" in rendered
    assert "AGENTS.md" in rendered
    assert "Memory Bank" in rendered


def test_count_cursor_rules_returns_zero_for_missing_dir():
    assert gdr._count_cursor_rules(pathlib.Path("/nonexistent")) == 0


def test_present_targets_returns_empty_for_missing_dir():
    assert gdr._present_targets(pathlib.Path("/nonexistent")) == []


def test_present_targets_skips_empty_subdirectories(tmp_path):
    """An empty cursor/ directory should NOT count as present — empty dirs don't ship."""
    stack = tmp_path / "stack"
    (stack / "cursor").mkdir(parents=True)
    assert gdr._present_targets(stack) == []


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------


def test_cli_dry_run_writes_to_stdout(tmp_path):
    result = subprocess.run(
        [sys.executable, "tools/generate_dist_readme.py", "--version", "v1.0.0",
         "--dist-root", str(tmp_path), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
    assert "0004-single-repo-distribution" in result.stdout
    assert "`v1.0.0`" in result.stdout


def test_cli_writes_to_output_path(tmp_path):
    out_file = tmp_path / "dist-readme.md"
    result = subprocess.run(
        [sys.executable, "tools/generate_dist_readme.py", "--version", "v1.2.3",
         "--dist-root", str(tmp_path), "--output", str(out_file)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "`v1.2.3`" in content
    assert "0004-single-repo-distribution" in content
