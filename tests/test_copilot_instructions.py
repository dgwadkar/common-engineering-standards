"""Phase 5 acceptance tests for ``compiler.transformers.copilot_instructions``."""
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
from compiler.transformers import copilot_instructions

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _rule(
    rid: str,
    *,
    title: str = "Sample Title",
    language: str = "java",
    framework: Optional[str] = "spring-boot",
    framework_version: Optional[str] = ">=3.0",
    layers: tuple[str, ...] = ("controller",),
    cursor_mode: str = "auto-attach",
    agents_md_priority: str = "high",
    copilot_target: bool = True,
    body: str = "# Sample Title\n\n## 1. Context\n\nIntro.\n\n## 2. Enforced Standards\n\n### 2.1. Rule One\n\nText.\n",
    dependencies: tuple[str, ...] = (),
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
            github_copilot=copilot_target,
            claude_skills=True,
            junie=True,
            agents_md=True,
        ),
        activation=Activation(cursor_mode=cursor_mode, agents_md_priority=agents_md_priority),
        dependencies=dependencies,
        related_logic_holes=(),
        archunit_test=None,
        body=body,
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


# ---------------------------------------------------------------------------
# Render + emit basics
# ---------------------------------------------------------------------------


def test_render_uses_stack_human_name_in_header() -> None:
    stack = stack_by_id("java-spring-boot-3")
    out = copilot_instructions.render_copilot_instructions([_rule("a")], stack)
    assert out.startswith("# GitHub Copilot Instructions — Spring Boot 3")


def test_render_groups_rules_under_layer_headers() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [
        _rule("ctrl", title="Controller Rule", layers=("controller",)),
        _rule("svc", title="Service Rule", layers=("service",)),
    ]
    out = copilot_instructions.render_copilot_instructions(rules, stack)
    assert "## Controller Layer" in out
    assert "## Service Layer" in out
    # Controller appears BEFORE Service in the canonical ordering.
    assert out.index("## Controller Layer") < out.index("## Service Layer")


def test_render_skips_rules_with_copilot_target_false() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a", title="Yes"), _rule("b", title="Skipped", copilot_target=False)]
    out = copilot_instructions.render_copilot_instructions(rules, stack)
    assert "### Yes" in out
    assert "### Skipped" not in out


def test_render_strips_h1_heading_and_demotes_h2() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule(
        "a",
        title="The Title",
        body="# The Title\n\n## 1. Context\n\nIntro line.\n\n## 2. Enforced Standards\n\nMore.\n",
    )
    out = copilot_instructions.render_copilot_instructions([rule], stack)
    # The source H1 is dropped (replaced by H3 per-rule header).
    assert "\n# The Title\n" not in out
    # Source H2 (## 1. Context) becomes H3 (### 1. Context) AFTER the rule H3 (### The Title).
    assert "### The Title" in out
    assert "### 1. Context" in out


def test_render_includes_dependency_first_topological_order() -> None:
    stack = stack_by_id("java-spring-boot-3")
    a = _rule("aa-rule", title="Aa", dependencies=("bb-rule",))
    b = _rule("bb-rule", title="Bb")
    out = copilot_instructions.render_copilot_instructions([a, b], stack)
    # B is a dependency of A; B should appear before A in the output.
    assert out.index("### Bb") < out.index("### Aa")


def test_render_appears_in_each_layer_for_multi_layer_rules() -> None:
    stack = stack_by_id("java-spring-boot-3")
    rule = _rule(
        "multi",
        title="Multi-Layer Rule",
        layers=("controller", "repository"),
    )
    out = copilot_instructions.render_copilot_instructions([rule], stack)
    # Rule title should appear twice — once per layer section.
    assert out.count("### Multi-Layer Rule") == 2


# ---------------------------------------------------------------------------
# emit_for_stack — writes one concatenated file
# ---------------------------------------------------------------------------


def test_emit_writes_one_file_under_copilot_dir(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a"), _rule("b", layers=("service",))]
    emitted = copilot_instructions.emit_for_stack(rules, stack, dist_root=tmp_path)
    assert len(emitted) == 1
    record = emitted[0]
    assert record.target_id == "github_copilot"
    expected = tmp_path / "stacks" / "java-spring-boot-3" / "copilot" / "copilot-instructions.md"
    assert record.output_path == expected
    assert record.output_path.is_file()
    assert record.bytes_written == len(record.output_path.read_bytes())
    assert record.rule_count == 2


def test_emit_skips_when_no_rules_opt_in(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    rules = [_rule("a", copilot_target=False), _rule("b", copilot_target=False)]
    emitted = copilot_instructions.emit_for_stack(rules, stack, dist_root=tmp_path)
    assert emitted == []


def test_emit_logs_structured_json_event(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test-copilot", stream=stream)

    stack = stack_by_id("java-spring-boot-3")
    copilot_instructions.emit_for_stack([_rule("a")], stack, dist_root=tmp_path, logger=logger)
    lines = [ln for ln in stream.getvalue().splitlines() if ln.strip()]
    payloads = [json.loads(ln) for ln in lines]
    assert any(p.get("event") == "emit" and p.get("target") == "github_copilot" for p in payloads)


# ---------------------------------------------------------------------------
# Live-corpus end-to-end
# ---------------------------------------------------------------------------


def test_live_corpus_emits_non_empty_concatenated_file(tmp_path: pathlib.Path) -> None:
    rules = parse_all()
    stack = stack_by_id("java-spring-boot-3")
    filtered = filter_for_stack(rules, stack)
    emitted = copilot_instructions.emit_for_stack(filtered, stack, dist_root=tmp_path)
    assert len(emitted) == 1
    content = emitted[0].output_path.read_text(encoding="utf-8")
    assert content.startswith("# GitHub Copilot Instructions —")
    # Every rule's title should appear at least once.
    for rule in filtered:
        if rule.target_tools.github_copilot:
            assert rule.title in content, f"Missing rule title in copilot output: {rule.title}"
