"""Phase 5 acceptance tests for ``compiler.transformers.claude_md``."""
from __future__ import annotations

import io
import json
import pathlib
from typing import Optional

from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)
from compiler.core.stack_filter import filter_for_stack, stack_by_id
from compiler.transformers import claude_md


def _rule(
    rid: str,
    *,
    title: str = "Sample Title",
    language: str = "java",
    framework: Optional[str] = "spring-boot",
    framework_version: Optional[str] = ">=3.0",
    layers: tuple[str, ...] = ("controller",),
    claude_target: bool = True,
    body: str = "# Sample Title\n\n## 1. Context\n\nIntro.\n\n## 2. Enforced Standards\n\nMore.\n",
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
            cursor=True,
            github_copilot=True,
            claude_skills=claude_target,
            junie=True,
            agents_md=True,
        ),
        activation=Activation(cursor_mode="auto-attach", agents_md_priority="high"),
        dependencies=(),
        related_logic_holes=(),
        archunit_test=None,
        body=body,
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


def test_render_starts_with_claude_h1() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = claude_md.render_claude_md([_rule("a")], stack)
    assert out.startswith("# Claude Code Instructions — Spring Boot 3")


def test_render_contains_you_must_directive_per_rule() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = claude_md.render_claude_md([_rule("a", title="Use Records")], stack)
    assert "**You MUST: Use Records.**" in out


def test_render_directive_strips_trailing_period_from_title() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = claude_md.render_claude_md([_rule("a", title="Use Records.")], stack)
    # Directive should not double-period.
    assert "**You MUST: Use Records.**" in out
    assert "**You MUST: Use Records..**" not in out


def test_render_uses_language_human_name_in_preamble() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = claude_md.render_claude_md([_rule("a")], stack)
    assert "When generating, modifying, or reviewing Java code" in out


def test_render_skips_rules_with_claude_target_false() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a", title="Yes"), _rule("b", title="Skipped", claude_target=False)]
    out = claude_md.render_claude_md(rules, stack)
    assert "### Yes" in out
    assert "### Skipped" not in out


def test_emit_writes_claude_md_under_claude_dir(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    emitted = claude_md.emit_for_stack([_rule("a")], stack, dist_root=tmp_path)
    assert len(emitted) == 1
    record = emitted[0]
    assert record.target_id == "claude_skills"
    expected = tmp_path / "stacks" / "java-spring-boot-3" / "claude" / "CLAUDE.md"
    assert record.output_path == expected
    assert record.output_path.is_file()


def test_emit_logs_structured_json(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test-claude", stream=stream)
    claude_md.emit_for_stack(
        [_rule("a")], stack_by_id("java-spring-boot-3"), dist_root=tmp_path, logger=logger
    )
    payloads = [json.loads(ln) for ln in stream.getvalue().splitlines() if ln.strip()]
    assert any(p.get("event") == "emit" and p.get("target") == "claude_skills" for p in payloads)


def test_live_corpus_claude_includes_every_rule_title(tmp_path: pathlib.Path) -> None:
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    emitted = claude_md.emit_for_stack(filtered, stack, dist_root=tmp_path)
    assert len(emitted) == 1
    content = emitted[0].output_path.read_text(encoding="utf-8")
    for rule in filtered:
        if rule.target_tools.claude_skills:
            assert rule.title in content, f"Missing in CLAUDE.md: {rule.title}"
