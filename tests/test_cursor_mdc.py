"""Phase 4 acceptance tests for ``compiler.transformers.cursor_mdc`` plus the CLI driver."""
from __future__ import annotations

import io
import json
import pathlib
import re
import subprocess
import sys
from typing import Optional

import pytest
import yaml

from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)
from compiler.core.stack_filter import STACKS, Stack, filter_for_stack, stack_by_id
from compiler.transformers import cursor_mdc

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule(
    rid: str,
    *,
    title: str = "Sample Title",
    language: str = "java",
    framework: Optional[str] = "spring-boot",
    framework_version: Optional[str] = ">=3.0",
    layers: tuple[str, ...] = ("controller",),
    cursor_mode: str = "auto-attach",
    cursor_target: bool = True,
    body: str = "# Sample Title\n\nBody.\n",
) -> SourceRule:
    return SourceRule(
        id=rid,
        title=title,
        version="1.0.0",
        status="approved",
        scope=Scope(
            language=language,
            framework=framework,
            framework_version=framework_version,
            layers=layers,
        ),
        target_tools=TargetTools(
            cursor=cursor_target,
            github_copilot=True,
            claude_skills=True,
            junie=True,
            agents_md=True,
        ),
        activation=Activation(cursor_mode=cursor_mode, agents_md_priority="high"),
        dependencies=(),
        related_logic_holes=(),
        archunit_test=None,
        body=body,
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


def _parse_mdc_frontmatter(content: str) -> dict:
    """Splits an MDC file into a frontmatter dict (uses YAML) and verifies the shape.

    Handles three frontmatter shapes:
      - Non-empty body: ``---\\n<yaml>\\n---\\n``
      - Empty body with explicit blank line: ``---\\n\\n---\\n``
      - Empty body, fences only: ``---\\n---\\n`` (manual mode)
    """
    m = re.match(r"\A---\s*\n(?:(?P<body>.*?)\n)?---\s*(?:\n|$)", content, re.DOTALL)
    assert m, f"MDC file must begin with a `---` frontmatter block. Got: {content[:100]!r}"
    body = m.group("body") or ""
    if not body.strip():
        return {}
    return yaml.safe_load(body)


# ---------------------------------------------------------------------------
# filename_for_rule
# ---------------------------------------------------------------------------


def test_filename_strips_lang_framework_prefix_for_framework_scoped_rules() -> None:
    assert (
        cursor_mdc.filename_for_rule(_rule("java-spring-controller-validation-boundaries"))
        == "controller-validation-boundaries.mdc"
    )


def test_filename_uses_underscore_prefix_for_global_rules() -> None:
    assert (
        cursor_mdc.filename_for_rule(_rule("global-clean-architecture", language="global"))
        == "_global-clean-architecture.mdc"
    )


def test_filename_falls_back_to_rule_id_for_unrecognized_pattern() -> None:
    assert cursor_mdc.filename_for_rule(_rule("foo-bar")) == "foo-bar.mdc"


# ---------------------------------------------------------------------------
# render_mdc — activation-mode decision tree
# ---------------------------------------------------------------------------


def test_render_mdc_auto_attach_emits_globs_and_alwaysapply_false() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule("java-spring-controller-validation-boundaries", cursor_mode="auto-attach")
    out = cursor_mdc.render_mdc(rule, stack)

    fm = _parse_mdc_frontmatter(out)
    assert fm["alwaysApply"] is False
    assert isinstance(fm["globs"], list)
    assert "**/controller/**/*.java" in fm["globs"]
    assert "Spring Boot 3" in fm["description"]


def test_render_mdc_always_mode_omits_globs() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule(
        "global-clean-architecture",
        language="global",
        framework=None,
        framework_version=None,
        layers=("architecture",),
        cursor_mode="always",
    )
    out = cursor_mdc.render_mdc(rule, stack)
    fm = _parse_mdc_frontmatter(out)
    assert fm["alwaysApply"] is True
    assert "globs" not in fm


def test_render_mdc_agent_requested_mode_omits_globs() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule(
        "java-spring-di-constructor-injection-mandate",
        layers=("di",),
        cursor_mode="agent-requested",
    )
    out = cursor_mdc.render_mdc(rule, stack)
    fm = _parse_mdc_frontmatter(out)
    assert fm["alwaysApply"] is False
    assert "globs" not in fm
    assert "description" in fm


def test_render_mdc_manual_mode_emits_empty_frontmatter() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule("playbook-runbook", cursor_mode="manual")
    out = cursor_mdc.render_mdc(rule, stack)
    fm = _parse_mdc_frontmatter(out)
    assert fm == {} or fm is None


def test_render_mdc_architecture_layer_promotes_to_always() -> None:
    """Even when cursor_mode is auto-attach, [architecture] cross-cuts → alwaysApply: true."""
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule("x", layers=("architecture",), cursor_mode="auto-attach")
    out = cursor_mdc.render_mdc(rule, stack)
    fm = _parse_mdc_frontmatter(out)
    assert fm["alwaysApply"] is True
    assert "globs" not in fm


def test_render_mdc_preserves_body_verbatim() -> None:
    stack = stack_by_id("java-spring-boot-3")
    body = "# Sample Title\n\nLine 1.\n\n## Heading 2\n\n- bullet\n"
    rule = _rule("x", body=body)
    out = cursor_mdc.render_mdc(rule, stack)
    # Strip frontmatter — body should appear verbatim after the closing `---` + blank line.
    assert body in out


def test_render_mdc_description_uses_stack_human_name() -> None:
    rule = _rule("x", title="My Rule")
    out_sb3 = cursor_mdc.render_mdc(rule, stack_by_id("java-spring-boot-3"))
    out_sb2 = cursor_mdc.render_mdc(rule, stack_by_id("java-spring-boot-2"))
    assert "Spring Boot 3" in _parse_mdc_frontmatter(out_sb3)["description"]
    assert "Spring Boot 2.7" in _parse_mdc_frontmatter(out_sb2)["description"]


def test_render_mdc_description_quotes_yaml_special_characters() -> None:
    """Titles containing colons or quotes are double-quoted in the frontmatter to avoid plain-scalar pitfalls."""
    rule = _rule("x", title='Rule with "quotes" and: a colon')
    out = cursor_mdc.render_mdc(rule, stack_by_id("java-spring-boot-3"))
    fm = _parse_mdc_frontmatter(out)
    assert 'quotes' in fm["description"]
    assert 'colon' in fm["description"]


# ---------------------------------------------------------------------------
# emit_for_stack — writes files, returns records, logs JSON
# ---------------------------------------------------------------------------


def test_emit_for_stack_writes_one_mdc_per_rule(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("java-spring-controller-validation-boundaries"),
        _rule("java-spring-service-transactional-boundaries", layers=("service",)),
    ]
    emitted = cursor_mdc.emit_for_stack(rules, stack, dist_root=tmp_path)
    assert len(emitted) == 2
    paths = sorted(p.output_path.name for p in emitted)
    assert paths == ["controller-validation-boundaries.mdc", "service-transactional-boundaries.mdc"]
    # Each file actually exists and has non-zero content.
    for record in emitted:
        assert record.output_path.is_file()
        assert record.bytes_written > 0
        assert record.bytes_written == len(record.output_path.read_bytes())


def test_emit_for_stack_skips_rules_with_cursor_target_false(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a"), _rule("b", cursor_target=False)]
    emitted = cursor_mdc.emit_for_stack(rules, stack, dist_root=tmp_path)
    assert {r.rule_id for r in emitted} == {"a"}


def test_emit_for_stack_emits_structured_json_logs(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test", stream=stream)

    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a"), _rule("b", cursor_target=False)]
    cursor_mdc.emit_for_stack(rules, stack, dist_root=tmp_path, logger=logger)

    log_lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert any('"event": "emit"' in ln for ln in log_lines)
    assert any('"event": "skip"' in ln for ln in log_lines)
    for ln in log_lines:
        payload = json.loads(ln)
        assert "ts" in payload
        assert "level" in payload
        assert "event" in payload


# ---------------------------------------------------------------------------
# Live-corpus end-to-end (AC2 + AC3)
# ---------------------------------------------------------------------------


def test_live_corpus_emit_for_sb3_produces_all_expected_files(tmp_path: pathlib.Path) -> None:
    """AC2: every rule in the filtered Spring Boot 3 subset produces an ``.mdc`` file."""
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    emitted = cursor_mdc.emit_for_stack(filtered, stack, dist_root=tmp_path)

    assert len(emitted) == len([r for r in filtered if r.target_tools.cursor])
    out_dir = tmp_path / "stacks" / stack.id / "cursor" / "rules"
    assert out_dir.is_dir()
    on_disk = sorted(p.name for p in out_dir.glob("*.mdc"))
    assert "_global-clean-architecture.mdc" in on_disk
    assert "controller-validation-boundaries.mdc" in on_disk
    assert "controller-dto-record-mandate.mdc" in on_disk


def test_each_emitted_mdc_validates_cursor_frontmatter_shape(tmp_path: pathlib.Path) -> None:
    """AC3: every emitted ``.mdc`` parses as YAML and uses only known Cursor MDC fields."""
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    emitted = cursor_mdc.emit_for_stack(filtered, stack, dist_root=tmp_path)

    allowed_keys = {"description", "globs", "alwaysApply"}
    for record in emitted:
        text = record.output_path.read_text(encoding="utf-8")
        fm = _parse_mdc_frontmatter(text)
        if fm is None:
            continue  # manual-mode files have empty frontmatter.
        extra = set(fm.keys()) - allowed_keys
        assert not extra, f"{record.output_path} has unknown frontmatter keys: {extra}"
        if "alwaysApply" in fm:
            assert isinstance(fm["alwaysApply"], bool)
        if "globs" in fm:
            assert isinstance(fm["globs"], list)
            assert all(isinstance(g, str) for g in fm["globs"])
        if "description" in fm:
            assert isinstance(fm["description"], str)
            assert len(fm["description"]) > 0
        body_start = text.find("\n---\n") + len("\n---\n")
        body = text[body_start:].lstrip("\n")
        assert body.startswith("#"), f"{record.output_path}: body must start with an H1 heading"


# ---------------------------------------------------------------------------
# CLI driver — invokes the full pipeline as the operator would
# ---------------------------------------------------------------------------


def test_cli_invocation_smoke(tmp_path: pathlib.Path) -> None:
    """AC2 verbatim: ``python -m compiler --stack java-spring-boot-3 --target cursor --out <tmp>``."""
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "compiler",
            "--stack",
            "java-spring-boot-3",
            "--target",
            "cursor",
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
    rules_dir = out_dir / "stacks" / "java-spring-boot-3" / "cursor" / "rules"
    assert rules_dir.is_dir()
    files = sorted(p.name for p in rules_dir.glob("*.mdc"))
    assert len(files) >= 15  # 18 rules - draft - excluded-by-version ≈ 17
    # Verify the JSON log lines on stderr.
    log_lines = [ln for ln in result.stderr.splitlines() if ln.strip()]
    payloads = [json.loads(ln) for ln in log_lines]
    events = {p["event"] for p in payloads}
    assert "emit" in events
    assert "transformer-complete" in events


def test_cli_rejects_unknown_stack(tmp_path: pathlib.Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "compiler",
            "--stack",
            "ruby-rails-7",
            "--target",
            "cursor",
            "--out",
            str(tmp_path / "x"),
        ],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "ruby-rails-7" in result.stderr


def test_cli_rejects_unknown_target(tmp_path: pathlib.Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "compiler",
            "--stack",
            "java-spring-boot-3",
            "--target",
            "amazon-q",
            "--out",
            str(tmp_path / "x"),
        ],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "amazon-q" in result.stderr or "invalid choice" in result.stderr
