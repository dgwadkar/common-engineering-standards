"""Phase 5 acceptance tests for ``compiler.transformers.junie_agents_md``."""
from __future__ import annotations

import io
import json
import pathlib
import re
from typing import Optional

from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)
from compiler.core.stack_filter import filter_for_stack, stack_by_id
from compiler.transformers import junie_agents_md


def _rule(
    rid: str,
    *,
    title: str = "Sample Title",
    junie_target: bool = True,
    layers: tuple[str, ...] = ("controller",),
    dependencies: tuple[str, ...] = (),
    body: Optional[str] = None,
) -> SourceRule:
    if body is None:
        body = (
            f"# {title}\n\n"
            "## 1. Context & Architectural Intent\n\n"
            "This is the intro paragraph for the rule.\n\n"
            "## 2. Enforced Standards\n\n"
            "### 2.1. First sub-rule\n\nText.\n\n"
            "### 2.2. Second sub-rule\n\nText.\n"
        )
    return SourceRule(
        id=rid,
        title=title,
        version="1.0.0",
        status="approved",
        scope=Scope(
            language="java",
            framework="spring-boot",
            framework_version=">=3.0",
            layers=layers,
        ),
        target_tools=TargetTools(
            cursor=True,
            github_copilot=True,
            claude_skills=True,
            junie=junie_target,
            agents_md=True,
        ),
        activation=Activation(cursor_mode="auto-attach", agents_md_priority="high"),
        dependencies=dependencies,
        related_logic_holes=(),
        archunit_test=None,
        body=body,
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


def test_render_uses_stack_human_name_in_h1() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = junie_agents_md.render_junie_agents_md([_rule("a")], stack)
    assert out.startswith("# Spring Boot 3 Guidelines (JetBrains Junie)")


def test_render_emits_numbered_list_entries() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a", title="Alpha"), _rule("b", title="Bravo")]
    out = junie_agents_md.render_junie_agents_md(rules, stack)
    # Both numbered entries appear.
    assert re.search(r"^1\. \*\*", out, re.MULTILINE)
    assert re.search(r"^2\. \*\*", out, re.MULTILINE)


def test_render_extracts_context_paragraph() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = junie_agents_md.render_junie_agents_md([_rule("a")], stack)
    assert "This is the intro paragraph for the rule." in out


def test_render_extracts_enforced_standards_titles() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = junie_agents_md.render_junie_agents_md([_rule("a")], stack)
    assert "First sub-rule" in out
    assert "Second sub-rule" in out


def test_render_topological_order_dependencies_first() -> None:
    stack = stack_by_id("java-spring-boot-3")
    a = _rule("aa", title="Aa", dependencies=("bb",))
    b = _rule("bb", title="Bb")
    out = junie_agents_md.render_junie_agents_md([a, b], stack)
    assert out.index("**Bb**") < out.index("**Aa**")


def test_render_skips_junie_target_false() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a", title="Yes"), _rule("b", title="Skipped", junie_target=False)]
    out = junie_agents_md.render_junie_agents_md(rules, stack)
    assert "**Yes**" in out
    assert "**Skipped**" not in out


def test_emit_writes_agents_md_under_junie_dir(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    emitted = junie_agents_md.emit_for_stack([_rule("a")], stack, dist_root=tmp_path)
    assert len(emitted) == 1
    expected = tmp_path / "stacks" / "java-spring-boot-3" / "junie" / "AGENTS.md"
    assert emitted[0].output_path == expected
    assert emitted[0].output_path.is_file()


def test_emit_logs_structured_json(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test-junie", stream=stream)
    junie_agents_md.emit_for_stack(
        [_rule("a")], stack_by_id("java-spring-boot-3"), dist_root=tmp_path, logger=logger
    )
    payloads = [json.loads(ln) for ln in stream.getvalue().splitlines() if ln.strip()]
    assert any(p.get("event") == "emit" and p.get("target") == "junie" for p in payloads)


def test_live_corpus_junie_numbered_count_matches_filtered(tmp_path: pathlib.Path) -> None:
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    emitted = junie_agents_md.emit_for_stack(filtered, stack, dist_root=tmp_path)
    content = emitted[0].output_path.read_text(encoding="utf-8")
    junie_rules = [r for r in filtered if r.target_tools.junie]
    # Numbered entries (^N. **) — count matches the filtered junie subset.
    numbered = re.findall(r"^\d+\. \*\*", content, re.MULTILINE)
    assert len(numbered) == len(junie_rules)
