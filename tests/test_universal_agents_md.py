"""Phase 5 acceptance tests for ``compiler.transformers.universal_agents_md``."""
from __future__ import annotations

import io
import json
import pathlib

import pytest

from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)
from compiler.core.stack_filter import filter_for_stack, stack_by_id
from compiler.transformers import universal_agents_md
from compiler.transformers.universal_agents_md import AgentsMdTooLongError


def _rule(
    rid: str,
    *,
    title: str = "Sample Title",
    layers: tuple[str, ...] = ("controller",),
    agents_md_priority: str = "high",
    agents_md_target: bool = True,
) -> SourceRule:
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
            junie=True,
            agents_md=agents_md_target,
        ),
        activation=Activation(cursor_mode="auto-attach", agents_md_priority=agents_md_priority),
        dependencies=(),
        related_logic_holes=(),
        archunit_test=None,
        body=f"# {title}\n\n## 1. Context\n\nIntro.\n",
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


def test_render_includes_all_canonical_sections() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = universal_agents_md.render_universal_agents_md([_rule("a")], stack)
    for section in [
        "## Tech Stack",
        "## Commands",
        "## Code Style",
        "## Testing",
        "## Boundaries",
    ]:
        assert section in out


def test_render_omits_non_high_priority_rules() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("a", title="High Rule", agents_md_priority="high"),
        _rule("b", title="Medium Rule", agents_md_priority="medium"),
        _rule("c", title="Low Rule", agents_md_priority="low"),
    ]
    out = universal_agents_md.render_universal_agents_md(rules, stack)
    assert "High Rule" in out
    assert "Medium Rule" not in out
    assert "Low Rule" not in out


def test_render_omits_rules_with_agents_md_target_false() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("a", title="Included"),
        _rule("b", title="Excluded", agents_md_target=False),
    ]
    out = universal_agents_md.render_universal_agents_md(rules, stack)
    assert "Included" in out
    assert "Excluded" not in out


def test_render_under_150_lines_for_live_corpus() -> None:
    """AC2: the generated AGENTS.md is ≤150 lines for the live corpus."""
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    out = universal_agents_md.render_universal_agents_md(filtered, stack)
    line_count = out.count("\n")
    assert line_count <= 150, f"AGENTS.md is {line_count} lines (cap 150). Content:\n{out}"


def test_render_raises_when_cap_exceeded() -> None:
    """A tiny cap forces the diagnostic to fire."""
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule(f"r{i}", title=f"Rule {i}") for i in range(50)]
    with pytest.raises(AgentsMdTooLongError) as exc_info:
        universal_agents_md.render_universal_agents_md(rules, stack, max_lines=20)
    assert "Demote" in str(exc_info.value)


def test_render_routes_test_layer_rules_to_testing_section() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("c", title="Controller Rule", layers=("controller",)),
        _rule("t", title="Test Rule", layers=("test",)),
    ]
    out = universal_agents_md.render_universal_agents_md(rules, stack)
    testing_idx = out.index("## Testing")
    boundaries_idx = out.index("## Boundaries")
    assert "Test Rule" in out
    # Test Rule appears inside the Testing section (between ## Testing and ## Boundaries).
    test_section = out[testing_idx:boundaries_idx]
    assert "Test Rule" in test_section


def test_render_routes_architecture_layer_rules_to_boundaries_section() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("a", title="Arch Rule", layers=("architecture",)),
        _rule("c", title="Controller Rule", layers=("controller",)),
    ]
    out = universal_agents_md.render_universal_agents_md(rules, stack)
    boundaries_idx = out.index("## Boundaries")
    # "Arch Rule" appears after the ## Boundaries header.
    assert "Arch Rule" in out[boundaries_idx:]


def test_emit_writes_agents_md_under_agents_md_dir(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    emitted = universal_agents_md.emit_for_stack([_rule("a")], stack, dist_root=tmp_path)
    assert len(emitted) == 1
    expected = tmp_path / "stacks" / "java-spring-boot-3" / "agents-md" / "AGENTS.md"
    assert emitted[0].output_path == expected
    assert emitted[0].output_path.is_file()
    assert emitted[0].line_count <= universal_agents_md.MAX_LINES


def test_emit_logs_structured_json(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test-agents-md", stream=stream)
    universal_agents_md.emit_for_stack(
        [_rule("a")], stack_by_id("java-spring-boot-3"), dist_root=tmp_path, logger=logger
    )
    payloads = [json.loads(ln) for ln in stream.getvalue().splitlines() if ln.strip()]
    matched = [
        p
        for p in payloads
        if p.get("event") == "emit" and p.get("target") == "agents_md"
    ]
    assert matched
    assert matched[0]["line_count"] <= matched[0]["max_lines"]
