"""Phase-6 golden-snapshot tests for the engineering-standards compiler.

Contract (per `docs/02-implementation-plan.md` §9 task 3):

    For each fixture under `fixtures/<fixture-name>/`, this test runs the
    compiler with `--target all --stack <stack-id>` against a temporary output
    directory and asserts that the resulting tree is **byte-identical** to the
    pre-committed snapshot under `tests/golden/<fixture-name>/`.

    On drift, the test prints a unified diff per drifted file plus a recovery
    instruction:

        Run `make update-golden` to refresh `tests/golden/`.

    See `Makefile` for the regeneration target.

Why this works against the *pure* §5.2 tree (not against a Java/TS/Python
runtime):

    Phase-5 transformers each expose a side-effecting `emit_for_stack(...)`
    that the CLI invokes. The output is deterministic — Phase-5 log §6 V-9
    ran `--target all` against every stack and confirmed identical bytes
    across runs (no timestamps, no random ordering). This test re-runs the
    CLI and diffs the produced bytes against the golden tree.

Fixture-to-stack binding is fixed by `_FIXTURE_TO_STACK` below. The fixture
manifest files (`pom.xml`, `package.json`, `pyproject.toml`) are themselves
not parsed by Phase 6 — they exist for Phase 8's consumer-sync detection
flow. Phase 6 hard-codes the binding to keep the golden test self-contained.

Phase-5 lesson honored: the strict `build_graph(...)` cannot validate the
java-spring-boot-2 stack subset (controller-pageable-defaults' dependency
on controller-dto-record-mandate, which is excluded by Boot-2's filter).
The CLI uses `topo_sort_relaxed(...)` for concatenated transformers; this
test exercises that path end-to-end.
"""

from __future__ import annotations

import difflib
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

# Fixture name → stack id (compiler/core/stack_filter.py::STACKS).
# Each fixture contains a manifest file (pom.xml / package.json /
# pyproject.toml) that pins the stack version; the binding here is the
# Phase-6 contract for the snapshot harness. Phase 8 will replace this map
# with auto-detection from the manifest.
_FIXTURE_TO_STACK = {
    "spring-boot-3-2": "java-spring-boot-3",
    "spring-boot-2-7-legacy": "java-spring-boot-2",
    "nestjs-10": "typescript-nestjs-10",
    "fastapi-0-110": "python-fastapi-0-110",
}

# Files under the golden tree that aren't compiler outputs (e.g., a stray
# `.gitkeep` placeholder if anyone adds one). Excluded from the diff.
_IGNORED_BASENAMES = {".gitkeep", ".DS_Store"}


def _list_files(root: Path) -> list[Path]:
    """Return every regular file under `root`, sorted, relative to `root`."""
    if not root.is_dir():
        return []
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name in _IGNORED_BASENAMES:
                continue
            abspath = Path(dirpath) / name
            out.append(abspath.relative_to(root))
    return sorted(out)


def _run_compiler(stack_id: str, out_dir: Path) -> None:
    """Invoke `python -m compiler --stack <id> --target all --out <out_dir>`.

    Uses `sys.executable` so the harness works under any active interpreter
    (CI Python 3.12 OR the local `.venv-phase2`). Captures stderr only on
    failure to keep happy-path output clean.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "compiler",
            "--stack",
            stack_id,
            "--target",
            "all",
            "--out",
            str(out_dir),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"compiler exited {proc.returncode} for stack {stack_id!r}.\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )


def _format_drift_message(
    fixture: str,
    only_in_golden: list[Path],
    only_in_actual: list[Path],
    differing: list[tuple[Path, str]],
) -> str:
    """Compose the human-readable failure message for a snapshot drift."""
    lines: list[str] = []
    lines.append(f"Golden snapshot drift detected for fixture {fixture!r}.")
    lines.append("")
    if only_in_golden:
        lines.append("Files MISSING from compiler output (present in golden):")
        for p in only_in_golden:
            lines.append(f"  - {p}")
        lines.append("")
    if only_in_actual:
        lines.append("Files EXTRA in compiler output (absent from golden):")
        for p in only_in_actual:
            lines.append(f"  + {p}")
        lines.append("")
    if differing:
        lines.append("Files whose contents differ (unified diff per file):")
        lines.append("")
        for relpath, diff in differing:
            lines.append(f"--- diff for {relpath} ---")
            lines.append(diff)
            lines.append("")
    lines.append("=" * 72)
    lines.append("Recovery: if the change is intentional, refresh the golden")
    lines.append("tree by running:")
    lines.append("")
    lines.append("    make update-golden")
    lines.append("")
    lines.append("Then commit the resulting `tests/golden/` diff alongside")
    lines.append("the source change. The PR review surfaces the exact bytes")
    lines.append("that changed (per docs/02-implementation-plan.md §9 AC3).")
    return "\n".join(lines)


def _diff_trees(fixture: str, expected_root: Path, actual_root: Path) -> None:
    """Assert byte-equality of two directory trees; raise with rich diff on drift."""
    expected = _list_files(expected_root)
    actual = _list_files(actual_root)

    expected_set = set(expected)
    actual_set = set(actual)

    only_in_golden = sorted(expected_set - actual_set)
    only_in_actual = sorted(actual_set - expected_set)
    common = sorted(expected_set & actual_set)

    differing: list[tuple[Path, str]] = []
    for rel in common:
        gpath = expected_root / rel
        apath = actual_root / rel
        if filecmp.cmp(str(gpath), str(apath), shallow=False):
            continue
        # Slow path: compute a textual unified diff (safe for our markdown
        # outputs; binary outputs would surface as `Binary files differ`).
        try:
            golden_lines = gpath.read_text(encoding="utf-8").splitlines(keepends=True)
            actual_lines = apath.read_text(encoding="utf-8").splitlines(keepends=True)
            udiff = "".join(
                difflib.unified_diff(
                    golden_lines,
                    actual_lines,
                    fromfile=f"golden/{fixture}/{rel}",
                    tofile=f"actual/{fixture}/{rel}",
                    n=3,
                )
            )
        except UnicodeDecodeError:
            udiff = f"<binary file differs: {rel}>"
        differing.append((rel, udiff))

    if only_in_golden or only_in_actual or differing:
        raise AssertionError(
            _format_drift_message(fixture, only_in_golden, only_in_actual, differing)
        )


# --- Test cases ----------------------------------------------------------


@pytest.fixture(scope="session")
def _ensure_fixtures_present() -> None:
    """Sanity-check that fixtures + golden trees exist before parametrized cases run.

    A missing fixture or empty golden tree is a Phase-6 setup error, not a
    Phase-7+ change — fail fast with a pointer to the regeneration target.
    """
    missing_fixtures = [
        name for name in _FIXTURE_TO_STACK if not (FIXTURES_DIR / name).is_dir()
    ]
    if missing_fixtures:
        raise AssertionError(
            "Missing fixture directories under fixtures/: "
            + ", ".join(missing_fixtures)
        )
    missing_golden = [
        name for name in _FIXTURE_TO_STACK if not (GOLDEN_DIR / name).is_dir()
    ]
    if missing_golden:
        raise AssertionError(
            "Missing golden trees under tests/golden/: "
            + ", ".join(missing_golden)
            + ". Run `make update-golden` to populate."
        )


@pytest.mark.parametrize(
    "fixture,stack_id",
    sorted(_FIXTURE_TO_STACK.items()),
    ids=sorted(_FIXTURE_TO_STACK),
)
def test_golden_snapshot_for_fixture(
    fixture: str, stack_id: str, tmp_path: Path, _ensure_fixtures_present: None
) -> None:
    """Each fixture's compiler output is byte-identical to its golden tree."""
    out_dir = tmp_path / "out"
    _run_compiler(stack_id, out_dir)
    _diff_trees(fixture, GOLDEN_DIR / fixture, out_dir)


def test_compiler_output_is_deterministic_across_two_runs(tmp_path: Path) -> None:
    """Two consecutive runs against the same fixture produce identical bytes.

    Determinism is the load-bearing property of golden snapshots; if the
    compiler ever introduces a non-deterministic field (e.g., a generation
    timestamp), this test surfaces it before the snapshot test does, with a
    clearer failure message.
    """
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    _run_compiler("java-spring-boot-3", out_a)
    _run_compiler("java-spring-boot-3", out_b)
    _diff_trees("determinism-check", out_a, out_b)


def test_golden_tree_lists_at_least_one_file_per_fixture() -> None:
    """Sanity: a populated golden tree must have files; an empty tree is a setup bug."""
    for fixture in _FIXTURE_TO_STACK:
        files = _list_files(GOLDEN_DIR / fixture)
        assert files, (
            f"tests/golden/{fixture}/ has zero files. "
            "Run `make update-golden` to populate."
        )


def test_unified_diff_is_emitted_when_a_golden_file_drifts(tmp_path: Path) -> None:
    """The drift-message formatter produces a unified diff and the recovery hint.

    Synthetic test: build two trees that differ in one file; assert the
    AssertionError message contains both the unified-diff prefix and the
    `make update-golden` recovery instruction. Locks the operator-facing
    contract independently of the compiler's output.
    """
    expected = tmp_path / "golden"
    actual = tmp_path / "actual"
    (expected / "a").mkdir(parents=True)
    (actual / "a").mkdir(parents=True)
    (expected / "a" / "f.md").write_text("hello\nworld\n", encoding="utf-8")
    (actual / "a" / "f.md").write_text("hello\nplanet\n", encoding="utf-8")

    with pytest.raises(AssertionError) as exc:
        _diff_trees("synthetic", expected, actual)
    msg = str(exc.value)
    assert "unified diff" in msg
    assert "make update-golden" in msg
    assert "-world" in msg
    assert "+planet" in msg


def test_missing_files_surface_in_drift_message(tmp_path: Path) -> None:
    """Files present in golden but missing from actual are reported clearly."""
    expected = tmp_path / "golden"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "absent.md").write_text("x\n", encoding="utf-8")

    with pytest.raises(AssertionError) as exc:
        _diff_trees("synthetic", expected, actual)
    assert "MISSING from compiler output" in str(exc.value)
    assert "absent.md" in str(exc.value)


def test_extra_files_surface_in_drift_message(tmp_path: Path) -> None:
    """Files present in actual but absent from golden are reported clearly."""
    expected = tmp_path / "golden"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (actual / "stray.md").write_text("x\n", encoding="utf-8")

    with pytest.raises(AssertionError) as exc:
        _diff_trees("synthetic", expected, actual)
    assert "EXTRA in compiler output" in str(exc.value)
    assert "stray.md" in str(exc.value)


def test_fixture_manifest_files_are_present() -> None:
    """Each fixture has the expected stack-pinning manifest file."""
    expected_manifests = {
        "spring-boot-3-2": "pom.xml",
        "spring-boot-2-7-legacy": "pom.xml",
        "nestjs-10": "package.json",
        "fastapi-0-110": "pyproject.toml",
    }
    for fixture, manifest in expected_manifests.items():
        path = FIXTURES_DIR / fixture / manifest
        assert path.is_file(), f"Missing fixture manifest: {path}"


def test_legacy_boot_2_golden_excludes_boot_3_only_rules() -> None:
    """The Boot-2 golden tree must NOT contain rules gated on Boot 3.x.

    Verifies the stack-filter version-gate is exercised by the golden test,
    not just by the unit suite. Specifically, `controller-dto-record-mandate`
    declares `framework_version: ">=3.0"` and must therefore be absent from
    the Boot-2 cursor/rules tree (the rule SHOULD appear in the Boot-3
    fixture's tree as a paired sanity check).
    """
    boot2_rules = GOLDEN_DIR / "spring-boot-2-7-legacy" / "stacks" / "java-spring-boot-2" / "cursor" / "rules"
    boot3_rules = GOLDEN_DIR / "spring-boot-3-2" / "stacks" / "java-spring-boot-3" / "cursor" / "rules"

    assert not (boot2_rules / "controller-dto-record-mandate.mdc").exists(), (
        "Boot-2 golden contains controller-dto-record-mandate.mdc, but the "
        'rule declares framework_version ">=3.0" — the stack filter should '
        "exclude it. If this is intentional, revisit the rule's "
        "framework_version range OR the stack-filter logic."
    )
    assert (boot3_rules / "controller-dto-record-mandate.mdc").exists(), (
        "Boot-3 golden is missing controller-dto-record-mandate.mdc. "
        "The Boot-3 fixture should include this rule per its >=3.0 gate."
    )


def test_universal_agents_md_under_150_lines_in_every_golden_tree() -> None:
    """The AGENTS.md cap (Plan §8 AC2) is locked into every fixture's golden tree."""
    for fixture in _FIXTURE_TO_STACK:
        # Discover the agents-md/ path inside this fixture's golden tree.
        # Each tree has exactly one stack subdir, but we don't hard-code the
        # stack id here so the test stays robust to future fixture renames.
        stacks_root = GOLDEN_DIR / fixture / "stacks"
        if not stacks_root.is_dir():
            continue
        stack_dirs = [p for p in stacks_root.iterdir() if p.is_dir()]
        assert len(stack_dirs) == 1, (
            f"Expected exactly one stack subdir under {stacks_root}; "
            f"found {len(stack_dirs)}"
        )
        agents_md = stack_dirs[0] / "agents-md" / "AGENTS.md"
        assert agents_md.is_file(), f"Missing AGENTS.md at {agents_md}"
        line_count = sum(1 for _ in agents_md.read_text(encoding="utf-8").splitlines())
        assert line_count <= 150, (
            f"Golden AGENTS.md for fixture {fixture!r} is {line_count} lines "
            "(cap is 150). Demote some rules from agents_md_priority: high "
            "to medium, then run `make update-golden`."
        )
