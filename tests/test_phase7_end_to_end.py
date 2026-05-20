"""Phase-7 end-to-end + workflow-shape tests.

Covers:

1. The new ``--all-stacks`` flag emits a complete per-stack subtree under ``--out``.
2. ``--all-stacks`` and ``--stack`` are mutually exclusive; passing both fails parsing.
3. ``--all-stacks`` produces byte-identical output to four separate per-stack runs.
4. ``.github/workflows/release.yml`` parses, declares ``workflow_dispatch``, has every
   plan §10 task-2 step, and authenticates as ``@standards-bot``.
5. ``.github/workflows/validate.yml`` now has the ``dist-protection-lint`` job with the
   required PR-only conditional + the ADR-0004 reference in the failure message.
6. ``docs/release-bot-setup.md``, ``docs/release-rollback.md``, and
   ``docs/branch-protection-config.md`` exist and reference each other correctly.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# CLI --all-stacks behavior
# ---------------------------------------------------------------------------


def _run_compiler(*args, cwd=str(REPO_ROOT)):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "compiler", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


def test_all_stacks_produces_subtree_for_every_known_stack(tmp_path):
    out = tmp_path / "out"
    result = _run_compiler("--all-stacks", "--target", "all", "--out", str(out))
    assert result.returncode == 0, f"compiler failed: {result.stderr}"

    # Import the catalog dynamically so this test stays in sync with the runtime source.
    sys.path.insert(0, str(REPO_ROOT))
    from compiler.core.stack_filter import known_stack_ids  # noqa: WPS433

    for stack_id in known_stack_ids():
        stack_dir = out / "stacks" / stack_id
        assert stack_dir.is_dir(), f"--all-stacks did not emit {stack_dir}"
        # Each stack must have all five non-cursor target outputs + the cursor rules dir.
        assert (stack_dir / "cursor" / "rules").is_dir()
        assert (stack_dir / "copilot" / "copilot-instructions.md").is_file()
        assert (stack_dir / "claude" / "CLAUDE.md").is_file()
        assert (stack_dir / "junie" / "AGENTS.md").is_file()
        assert (stack_dir / "agents-md" / "AGENTS.md").is_file()
        # Memory bank emits 6 stub files.
        assert sum(1 for _ in (stack_dir / "memory-bank").iterdir()) == 6


def test_all_stacks_is_mutually_exclusive_with_stack(tmp_path):
    """Passing both --stack and --all-stacks must fail at argparse-time with exit code 2."""
    out = tmp_path / "out"
    result = _run_compiler(
        "--all-stacks", "--stack", "java-spring-boot-3", "--target", "all", "--out", str(out)
    )
    assert result.returncode == 2
    assert "not allowed with argument" in (result.stderr + result.stdout)


def test_all_stacks_byte_identical_to_four_per_stack_runs(tmp_path):
    """Confirms --all-stacks is a no-semantic-drift shortcut for four per-stack runs."""
    sys.path.insert(0, str(REPO_ROOT))
    from compiler.core.stack_filter import known_stack_ids  # noqa: WPS433

    # Path A — single --all-stacks invocation.
    out_a = tmp_path / "out_all"
    r_a = _run_compiler("--all-stacks", "--target", "all", "--out", str(out_a))
    assert r_a.returncode == 0

    # Path B — four per-stack invocations into a shared --out dir.
    out_b = tmp_path / "out_per_stack"
    for stack_id in known_stack_ids():
        r_b = _run_compiler("--stack", stack_id, "--target", "all", "--out", str(out_b))
        assert r_b.returncode == 0

    # Compare every file in both trees.
    files_a = sorted(p.relative_to(out_a) for p in out_a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(out_b) for p in out_b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes(), \
            f"--all-stacks vs per-stack drift at {rel}"


def test_all_stacks_emits_all_stacks_complete_log_event(tmp_path):
    out = tmp_path / "out"
    result = _run_compiler("--all-stacks", "--target", "cursor", "--out", str(out))
    assert result.returncode == 0
    assert '"event": "all-stacks-complete"' in result.stderr
    assert '"stacks_compiled": 4' in result.stderr


# ---------------------------------------------------------------------------
# release.yml workflow shape
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def release_yml():
    path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_release_yml_uses_workflow_dispatch_trigger(release_yml):
    # `on` is a YAML keyword (truthy); pyyaml parses it as the boolean True.
    trigger_block = release_yml.get(True) or release_yml.get("on")
    assert "workflow_dispatch" in trigger_block


def test_release_yml_has_inputs_for_ref_force_bump_and_dry_run(release_yml):
    trigger_block = release_yml.get(True) or release_yml.get("on")
    inputs = trigger_block["workflow_dispatch"]["inputs"]
    assert "ref" in inputs
    assert "force-bump" in inputs
    assert "dry-run" in inputs


def test_release_yml_concurrency_prevents_parallel_releases(release_yml):
    assert release_yml.get("concurrency", {}).get("group") == "release"
    assert release_yml["concurrency"].get("cancel-in-progress") is False


def test_release_yml_has_required_step_names(release_yml):
    step_names = [s["name"] for s in release_yml["jobs"]["release"]["steps"]]
    # Spot-check the canonical plan §10 task 2 steps.
    spot = [
        "Checkout target ref",
        "Set up Python",
        "Install release dependencies",
        "Compute next semver tag",
        "Regenerate dist/ via",
        "Regenerate dist/CHANGELOG.md",
        "Regenerate dist/README.md",
        "Mint an installation token for @standards-bot",
        "Configure git as standards-bot",
        "Commit, tag, and push",
        "Create GitHub Release",
    ]
    for needle in spot:
        assert any(needle in n for n in step_names), f"Missing step: {needle}"


def test_release_yml_authenticates_via_app_token_action(release_yml):
    """Confirms the App-token minting action is the official one."""
    yaml_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "actions/create-github-app-token@v1" in yaml_text
    assert "STANDARDS_BOT_APP_ID" in yaml_text
    assert "STANDARDS_BOT_PRIVATE_KEY" in yaml_text


def test_release_yml_uses_all_stacks_flag(release_yml):
    """Confirms release.yml actually consumes the Phase-7 CLI flag we just added."""
    yaml_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "--all-stacks" in yaml_text


def test_release_yml_refuses_to_commit_paths_outside_dist(release_yml):
    yaml_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "Release safety violation" in yaml_text
    assert "changed_outside_dist" in yaml_text


# ---------------------------------------------------------------------------
# validate.yml — the new dist-protection-lint job
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def validate_yml():
    path = REPO_ROOT / ".github" / "workflows" / "validate.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_validate_yml_now_has_dist_protection_lint_job(validate_yml):
    assert "dist-protection-lint" in validate_yml["jobs"]


def test_dist_protection_lint_runs_only_on_pull_request(validate_yml):
    job = validate_yml["jobs"]["dist-protection-lint"]
    assert "pull_request" in job["if"]


def test_dist_protection_lint_failure_message_cites_adr_0004(validate_yml):
    yaml_text = (REPO_ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert "0004-single-repo-distribution" in yaml_text
    assert "Human authors cannot modify dist/" in yaml_text


def test_dist_protection_lint_allows_both_bracketed_and_bare_bot_name(validate_yml):
    """Permits both `standards-bot[bot]` (the App identity) and `standards-bot` (the bare
    fallback). A future regex tightening that drops the fallback would block legitimate
    releases."""
    yaml_text = (REPO_ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    # Look for the bash regex pattern that accepts both forms.
    assert "standards-bot(\\[bot\\])?" in yaml_text


def test_validate_yml_total_job_count_is_five(validate_yml):
    """Defense-in-depth: catches accidental job removal (the original 4 + Phase-7's new one)."""
    assert len(validate_yml["jobs"]) == 5


# ---------------------------------------------------------------------------
# Doc presence + cross-references
# ---------------------------------------------------------------------------


def test_release_bot_setup_doc_exists_and_links_to_adr_0004():
    path = REPO_ROOT / "docs" / "release-bot-setup.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "0004-single-repo-distribution" in content
    assert "STANDARDS_BOT_APP_ID" in content
    assert "STANDARDS_BOT_PRIVATE_KEY" in content


def test_release_rollback_doc_exists_and_links_to_adr_0004():
    path = REPO_ROOT / "docs" / "release-rollback.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "0004-single-repo-distribution" in content
    assert "no moved tags" in content.lower() or "no force-push" in content.lower()


def test_branch_protection_doc_now_references_dist_protection_lint():
    path = REPO_ROOT / "docs" / "branch-protection-config.md"
    content = path.read_text(encoding="utf-8")
    assert "dist-protection-lint" in content
    # The golden-tests → golden-snapshots reconciliation must be explicit (operators
    # reading this in 6 months need the historical context).
    assert "golden-snapshots" in content
    assert "Phase-7" in content


def test_dist_readme_currently_at_phase1_scaffold_or_phase7_generated():
    """The dist/README.md file is either the Phase-1 placeholder OR the Phase-7 generated
    output. Both reference ADR-0004 (validate.yml's tree-shape job requires it)."""
    content = (REPO_ROOT / "dist" / "README.md").read_text(encoding="utf-8")
    assert "0004-single-repo-distribution" in content
