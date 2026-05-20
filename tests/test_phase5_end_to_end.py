"""Phase 5 AC1 + AC2 end-to-end tests.

AC1 — Running the compiler against ``source/`` for the ``java-spring-boot-3`` stack produces a
directory tree exactly matching Architecture Upgrade Report §5.2 under ``stacks/java-spring-boot-3/``.

AC2 — The generated ``AGENTS.md`` is ≤150 lines.

(AC3 is verified per-transformer in the transformer-specific test modules.)
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# Per Architecture Upgrade Report §5.2: each stack ships these six target subtrees from Phase 5
# plus the Phase-4 `cursor/rules/` tree. The Phase-6 `archunit/` tree is not in scope for Phase 5.
_EXPECTED_TARGET_TREES: tuple[tuple[str, str], ...] = (
    ("cursor", "rules"),
    ("copilot", "copilot-instructions.md"),
    ("claude", "CLAUDE.md"),
    ("junie", "AGENTS.md"),
    ("agents-md", "AGENTS.md"),
    ("memory-bank", "techContext.md"),
)


def _run_compiler(out_dir: pathlib.Path, target: str = "all") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "compiler",
            "--stack",
            "java-spring-boot-3",
            "--target",
            target,
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )


def test_cli_target_all_produces_expected_stack_tree(tmp_path: pathlib.Path) -> None:
    """AC1: every target subtree from §5.2 exists after `--target all`."""
    out_dir = tmp_path / "p5"
    result = _run_compiler(out_dir, target="all")
    assert result.returncode == 0, f"CLI failed: stderr={result.stderr!r}"
    stack_root = out_dir / "stacks" / "java-spring-boot-3"
    assert stack_root.is_dir()

    for subdir, marker in _EXPECTED_TARGET_TREES:
        marker_path = stack_root / subdir / marker
        # cursor/rules/ is a directory; everything else is a file. Both must exist.
        assert marker_path.exists(), f"Missing §5.2 path: {marker_path.relative_to(out_dir)}"


def test_cli_target_all_emits_transformer_complete_per_target(tmp_path: pathlib.Path) -> None:
    out_dir = tmp_path / "p5b"
    result = _run_compiler(out_dir, target="all")
    assert result.returncode == 0
    payloads = [
        json.loads(ln) for ln in result.stderr.splitlines() if ln.strip().startswith("{")
    ]
    completed = {
        p.get("target") for p in payloads if p.get("event") == "transformer-complete"
    }
    assert {"cursor", "github_copilot", "claude_skills", "junie", "agents_md", "memory_bank"} <= completed


def test_universal_agents_md_under_150_lines(tmp_path: pathlib.Path) -> None:
    """AC2: the generated AGENTS.md is ≤150 lines."""
    out_dir = tmp_path / "p5c"
    result = _run_compiler(out_dir, target="agents_md")
    assert result.returncode == 0, f"agents_md compile failed: {result.stderr!r}"
    agents_md = out_dir / "stacks" / "java-spring-boot-3" / "agents-md" / "AGENTS.md"
    assert agents_md.is_file()
    line_count = agents_md.read_text(encoding="utf-8").count("\n")
    assert line_count <= 150, f"AGENTS.md exceeded cap: {line_count} lines"


def test_cli_target_all_runs_cleanly_for_every_known_stack(tmp_path: pathlib.Path) -> None:
    """Sanity: --target all completes (exit 0) for every stack in the catalog."""
    stacks = (
        "java-spring-boot-3",
        "java-spring-boot-2",
        "typescript-nestjs-10",
        "python-fastapi-0-110",
    )
    for sid in stacks:
        out_dir = tmp_path / f"all-{sid}"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "compiler",
                "--stack",
                sid,
                "--target",
                "all",
                "--out",
                str(out_dir),
            ],
            cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT)},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stack {sid} failed: stderr={result.stderr!r}"
        # Memory Bank always produces six files even if no rules ship.
        mb = out_dir / "stacks" / sid / "memory-bank"
        assert mb.is_dir()
        assert len(list(mb.glob("*.md"))) == 6
