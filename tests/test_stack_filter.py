"""Phase 4 acceptance tests for ``compiler.core.stack_filter``."""
from __future__ import annotations

import pathlib

import pytest

from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)
from compiler.core.stack_filter import (
    STACKS,
    Stack,
    StackFilterError,
    applies_to_stack,
    filter_for_stack,
    known_stack_ids,
    matches_framework_version_range,
    stack_by_id,
)


def _rule(
    rid: str,
    *,
    language: str = "java",
    framework: str = "spring-boot",
    framework_version: str | None = ">=3.0",
    layers: tuple[str, ...] = ("controller",),
    status: str = "approved",
) -> SourceRule:
    return SourceRule(
        id=rid,
        title=rid,
        version="1.0.0",
        status=status,
        scope=Scope(
            language=language,
            framework=framework,
            framework_version=framework_version,
            layers=layers,
        ),
        target_tools=TargetTools(
            cursor=True, github_copilot=True, claude_skills=True, junie=True, agents_md=True
        ),
        activation=Activation(cursor_mode="auto-attach", agents_md_priority="high"),
        dependencies=(),
        related_logic_holes=(),
        archunit_test=None,
        body=f"# {rid}\n",
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


# ---------------------------------------------------------------------------
# Stack catalog
# ---------------------------------------------------------------------------


def test_known_stack_ids_returns_canonical_four() -> None:
    assert known_stack_ids() == [
        "java-spring-boot-2",
        "java-spring-boot-3",
        "python-fastapi-0-110",
        "typescript-nestjs-10",
    ]


def test_stack_by_id_returns_descriptor() -> None:
    s = stack_by_id("java-spring-boot-3")
    assert s.language == "java"
    assert s.framework == "spring-boot"
    assert s.framework_version == "3.2.0"


def test_stack_by_id_unknown_raises() -> None:
    with pytest.raises(StackFilterError):
        stack_by_id("ruby-rails-7")


# ---------------------------------------------------------------------------
# matches_framework_version_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expr,pinned,want",
    [
        # Greater/less-than-or-equal comparators.
        (">=3.0", "3.2.0", True),
        (">=3.0", "2.7.18", False),
        (">=2.7", "3.2.0", True),
        (">=2.7", "2.7.18", True),
        (">=4.3", "3.2.0", False),
        ("<=3.0", "3.0.0", True),
        ("<=3.0", "3.0.1", False),
        # Strict comparators.
        (">3.0", "3.0.1", True),
        (">3.0", "3.0.0", False),
        ("<3.0", "2.9.9", True),
        # Bare version (exact match).
        ("3.0.0", "3.0.0", True),
        ("3.0.0", "3.0.1", False),
        # Caret.
        ("^2.7.0", "2.7.18", True),
        ("^2.7.0", "3.0.0", False),
        ("^3.0.0", "3.99.99", True),
        # Tilde.
        ("~3.1", "3.1.5", True),
        ("~3.1", "3.2.0", False),
        ("~3.1.0", "3.1.99", True),
        ("~3.1.0", "3.2.0", False),
        # Conjunction (AND).
        (">=2.0 <4.0", "3.2.0", True),
        (">=2.0 <4.0", "4.0.0", False),
        (">=2.0 <4.0", "1.9.9", False),
    ],
)
def test_matches_framework_version_range(expr: str, pinned: str, want: bool) -> None:
    assert matches_framework_version_range(expr, pinned) is want


def test_matches_framework_version_range_unparseable_raises() -> None:
    with pytest.raises(StackFilterError):
        matches_framework_version_range("not-a-range", "3.0.0")


# ---------------------------------------------------------------------------
# applies_to_stack
# ---------------------------------------------------------------------------


def _sb3() -> Stack:
    return stack_by_id("java-spring-boot-3")


def _sb2() -> Stack:
    return stack_by_id("java-spring-boot-2")


def _nest() -> Stack:
    return stack_by_id("typescript-nestjs-10")


def test_applies_to_stack_matches_language_framework_version() -> None:
    assert applies_to_stack(_rule("a", framework_version=">=3.0"), _sb3()) is True
    assert applies_to_stack(_rule("a", framework_version=">=3.0"), _sb2()) is False


def test_applies_to_stack_omitted_version_applies_to_all() -> None:
    r = _rule("a", framework_version=None)
    assert applies_to_stack(r, _sb3()) is True
    assert applies_to_stack(r, _sb2()) is True


def test_applies_to_stack_global_language_applies_to_every_stack() -> None:
    """Phase-3 lesson: ``language: global`` rules apply to every stack."""
    r = _rule("global-rule", language="global", framework=None, framework_version=None,
              layers=("architecture",))
    assert applies_to_stack(r, _sb3()) is True
    assert applies_to_stack(r, _sb2()) is True
    assert applies_to_stack(r, _nest()) is True


def test_applies_to_stack_language_mismatch_excludes() -> None:
    assert applies_to_stack(_rule("a", language="java"), _nest()) is False


def test_applies_to_stack_framework_mismatch_excludes() -> None:
    r = _rule("a", framework="quarkus")
    assert applies_to_stack(r, _sb3()) is False


# ---------------------------------------------------------------------------
# filter_for_stack
# ---------------------------------------------------------------------------


def test_filter_for_stack_excludes_drafts_by_default() -> None:
    rules = [_rule("a", status="approved"), _rule("b", status="draft")]
    out = filter_for_stack(rules, _sb3())
    assert {r.id for r in out} == {"a"}


def test_filter_for_stack_includes_drafts_when_requested() -> None:
    rules = [_rule("a", status="approved"), _rule("b", status="draft")]
    out = filter_for_stack(rules, _sb3(), include_drafts=True)
    assert {r.id for r in out} == {"a", "b"}


def test_filter_for_stack_includes_deprecated() -> None:
    rules = [_rule("a", status="approved"), _rule("b", status="deprecated")]
    out = filter_for_stack(rules, _sb3())
    assert {r.id for r in out} == {"a", "b"}


def test_live_corpus_sb3_count_matches_expected() -> None:
    """The 18-rule corpus filtered to Spring Boot 3.2.0 should include all globals + most java rules."""
    rules = parse_all()
    out = filter_for_stack(rules, _sb3())
    ids = {r.id for r in out}
    # Globals always apply.
    assert "global-clean-architecture" in ids
    assert "global-security-baselines" in ids
    assert "global-logging-telemetry" in ids
    # Spring Boot 3-only rules (require >=3.0).
    assert "java-spring-controller-validation-boundaries" in ids
    assert "java-spring-controller-dto-record-mandate" in ids
    assert "java-spring-error-handling-problem-details-rfc7807" in ids
    # Spring Boot 2.7+ rules apply to 3.x too.
    assert "java-spring-error-handling-prohibit-generic-runtime" in ids


def test_live_corpus_sb2_excludes_spring_boot_3_only_rules() -> None:
    """Boot 2.7 stack must exclude rules that declare ``framework_version: ">=3.0"``."""
    rules = parse_all()
    out = filter_for_stack(rules, _sb2())
    ids = {r.id for r in out}
    # These three require Boot 3+ — they must NOT be in the Boot-2 set.
    assert "java-spring-controller-validation-boundaries" not in ids
    assert "java-spring-controller-dto-record-mandate" not in ids
    assert "java-spring-error-handling-problem-details-rfc7807" not in ids
    # Globals still apply.
    assert "global-clean-architecture" in ids


def test_live_corpus_typescript_stack_gets_only_globals() -> None:
    """No TypeScript rules are authored in Phase 3 — the TypeScript stack only ships globals."""
    rules = parse_all()
    out = filter_for_stack(rules, _nest())
    languages = {r.scope.language for r in out}
    assert languages.issubset({"global"})
    assert len(out) == 3  # the three globals
