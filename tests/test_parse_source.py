"""Phase 4 acceptance tests for ``compiler.core.parse_source``.

Covers the typed ``SourceRule`` dataclass return path (the Phase-4 addition). The Phase-2
``--validate-only`` CLI behavior is exercised by ``tests/test_schemas.py``; this file focuses
on what's new in Phase 4.
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest

from compiler.core.parse_source import (
    SourceRule,
    SourceRuleError,
    extract_frontmatter_and_body,
    parse_all,
    parse_source_file,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _well_formed_frontmatter(**overrides) -> str:
    """Returns a minimal schema-valid frontmatter dict serialised as YAML."""
    fields = {
        "id": "test-rule-id",
        "title": "Test Rule",
        "version": "1.0.0",
        "status": "approved",
        "language": "java",
        "framework": "spring-boot",
        "framework_version": ">=3.0",
        "layers": "[controller]",
        "cursor_mode": "auto-attach",
        "agents_md_priority": "high",
    }
    fields.update(overrides)
    return textwrap.dedent(
        f"""\
        ---
        id: {fields['id']}
        title: {fields['title']}
        version: {fields['version']}
        status: {fields['status']}
        scope:
          language: {fields['language']}
          framework: {fields['framework']}
          framework_version: "{fields['framework_version']}"
          layers: {fields['layers']}
        target_tools:
          cursor: true
          github_copilot: true
          claude_skills: true
          junie: true
          agents_md: true
        activation:
          cursor_mode: {fields['cursor_mode']}
          agents_md_priority: {fields['agents_md_priority']}
        ---

        # {fields['title']}

        Body content.
        """
    )


# ---------------------------------------------------------------------------
# extract_frontmatter_and_body
# ---------------------------------------------------------------------------


def test_extract_returns_frontmatter_and_body() -> None:
    text = "---\nid: foo\n---\n\n# Heading\n\nBody.\n"
    fm, body = extract_frontmatter_and_body(text)
    assert fm == {"id": "foo"}
    assert body == "# Heading\n\nBody.\n"


def test_extract_returns_none_when_no_frontmatter() -> None:
    fm, body = extract_frontmatter_and_body("# Just a heading\n\nNo frontmatter here.\n")
    assert fm is None
    assert body.startswith("# Just a heading")


def test_extract_handles_yaml_scalar_frontmatter_as_invalid_object() -> None:
    fm, _ = extract_frontmatter_and_body("---\njust-a-string\n---\n\nbody\n")
    assert fm is not None
    assert "__INVALID_FRONTMATTER_NOT_OBJECT__" in fm


# ---------------------------------------------------------------------------
# parse_source_file
# ---------------------------------------------------------------------------


def test_parse_source_file_returns_typed_dataclass(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "rule.md"
    p.write_text(_well_formed_frontmatter(), encoding="utf-8")

    rule = parse_source_file(p)

    assert isinstance(rule, SourceRule)
    assert rule.id == "test-rule-id"
    assert rule.title == "Test Rule"
    assert rule.version == "1.0.0"
    assert rule.status == "approved"
    assert rule.scope.language == "java"
    assert rule.scope.framework == "spring-boot"
    assert rule.scope.framework_version == ">=3.0"
    assert rule.scope.layers == ("controller",)
    assert rule.target_tools.cursor is True
    assert rule.target_tools.is_enabled("cursor") is True
    assert rule.activation.cursor_mode == "auto-attach"
    assert rule.activation.agents_md_priority == "high"
    assert rule.dependencies == ()
    assert rule.body.startswith("# Test Rule")
    assert rule.body.endswith("\n")


def test_parse_source_file_raises_on_missing_required_field(tmp_path: pathlib.Path) -> None:
    text = _well_formed_frontmatter().replace("title: Test Rule\n", "")
    p = tmp_path / "broken.md"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(SourceRuleError) as exc_info:
        parse_source_file(p)
    assert "title" in str(exc_info.value)


def test_parse_source_file_raises_on_missing_frontmatter(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "no-fm.md"
    p.write_text("# Just a heading, no frontmatter\n", encoding="utf-8")
    with pytest.raises(SourceRuleError) as exc_info:
        parse_source_file(p)
    assert "frontmatter" in str(exc_info.value).lower()


def test_parse_source_file_accepts_global_pseudo_language(tmp_path: pathlib.Path) -> None:
    """Phase-3 lesson: ``language: global`` is the convention for ``source/_global/*.md`` rules."""
    text = textwrap.dedent(
        """\
        ---
        id: global-test
        title: Global Test
        version: 1.0.0
        status: approved
        scope:
          language: global
          framework: null
          layers: [architecture]
        target_tools:
          cursor: true
          github_copilot: false
          claude_skills: false
          junie: false
          agents_md: false
        activation:
          cursor_mode: always
          agents_md_priority: high
        ---

        # Global Test
        """
    )
    p = tmp_path / "global.md"
    p.write_text(text, encoding="utf-8")
    rule = parse_source_file(p)
    assert rule.scope.language == "global"
    assert rule.scope.framework is None
    assert rule.scope.layers == ("architecture",)


def test_parse_source_file_aggregates_optional_arrays(tmp_path: pathlib.Path) -> None:
    """Optional list fields default to empty tuples, even when omitted from frontmatter."""
    text = _well_formed_frontmatter()
    p = tmp_path / "no-opts.md"
    p.write_text(text, encoding="utf-8")
    rule = parse_source_file(p)
    assert rule.dependencies == ()
    assert rule.related_logic_holes == ()
    assert rule.archunit_test is None


# ---------------------------------------------------------------------------
# parse_all
# ---------------------------------------------------------------------------


def test_parse_all_against_live_source_tree() -> None:
    """Phase-3 deliverable + Phase-4 parser: every authored rule parses cleanly."""
    rules = parse_all()
    assert len(rules) >= 18, f"Expected at least 18 rules in source/, got {len(rules)}"
    ids = {r.id for r in rules}
    # A handful of the canonical Logic-Hole rule ids must be present.
    for canonical in (
        "global-clean-architecture",
        "global-security-baselines",
        "java-spring-controller-validation-boundaries",
        "java-spring-controller-dto-record-mandate",
        "java-spring-service-transactional-boundaries",
        "java-spring-repository-n-plus-one-prevention",
        "java-spring-di-constructor-injection-mandate",
        "java-spring-error-handling-prohibit-generic-runtime",
    ):
        assert canonical in ids, f"Expected rule id '{canonical}' in the corpus"


def test_parse_all_aggregates_errors_before_raising(tmp_path: pathlib.Path) -> None:
    """``parse_all`` surfaces every broken file at once — a single CI run lists every failure."""
    (tmp_path / "a.md").write_text(_well_formed_frontmatter(id="rule-a"), encoding="utf-8")
    (tmp_path / "b.md").write_text(
        _well_formed_frontmatter(id="rule-b").replace("title: Test Rule\n", ""),
        encoding="utf-8",
    )
    (tmp_path / "c.md").write_text(
        _well_formed_frontmatter(id="rule-c").replace("status: approved\n", "status: not-a-status\n"),
        encoding="utf-8",
    )
    with pytest.raises(SourceRuleError) as exc_info:
        parse_all(roots=[tmp_path])
    msg = str(exc_info.value)
    # Both broken files (b and c) must be referenced; the valid file (a) must not.
    assert "b.md" in msg
    assert "c.md" in msg
    assert msg.count("title") >= 1  # the missing-title error
    assert "not-a-status" in msg or "enum" in msg.lower()
