"""Phase 4 acceptance tests for ``compiler.core.build_graph``."""
from __future__ import annotations

import pathlib

import pytest

from compiler.core.build_graph import GraphError, RuleGraph, build_graph, topo_sort_relaxed
from compiler.core.parse_source import (
    Activation,
    Scope,
    SourceRule,
    TargetTools,
    parse_all,
)


def _rule(rid: str, *deps: str, language: str = "java") -> SourceRule:
    """Constructs a SourceRule with the minimum frontmatter to satisfy the dataclass."""
    return SourceRule(
        id=rid,
        title=rid,
        version="1.0.0",
        status="approved",
        scope=Scope(language=language, framework="spring-boot", layers=("controller",)),
        target_tools=TargetTools(
            cursor=True, github_copilot=True, claude_skills=True, junie=True, agents_md=True
        ),
        activation=Activation(cursor_mode="auto-attach", agents_md_priority="high"),
        dependencies=tuple(deps),
        related_logic_holes=(),
        archunit_test=None,
        body=f"# {rid}\n",
        source_path=pathlib.Path(f"source/{rid}.md"),
    )


def test_empty_rule_list_produces_empty_graph() -> None:
    graph = build_graph([])
    assert graph.rule_ids() == []
    assert graph.topo_sorted() == []


# ---------------------------------------------------------------------------
# topo_sort_relaxed — Phase 5
# ---------------------------------------------------------------------------


def test_topo_sort_relaxed_ignores_missing_deps() -> None:
    """A dependency on an out-of-subset rule is silently dropped (Phase 5 transformers)."""
    a = _rule("a", "missing-dep")
    b = _rule("b")
    ordered = topo_sort_relaxed([a, b])
    assert sorted(r.id for r in ordered) == ["a", "b"]


def test_topo_sort_relaxed_preserves_intra_subset_order() -> None:
    """Intra-subset edges still enforce dependencies-first order."""
    a = _rule("a", "b")
    b = _rule("b")
    ordered = [r.id for r in topo_sort_relaxed([a, b])]
    assert ordered.index("b") < ordered.index("a")


def test_topo_sort_relaxed_detects_cycle_within_subset() -> None:
    a = _rule("a", "b")
    b = _rule("b", "a")
    with pytest.raises(GraphError) as exc_info:
        topo_sort_relaxed([a, b])
    assert "cycle" in str(exc_info.value).lower()


def test_topo_sort_relaxed_empty_input() -> None:
    assert topo_sort_relaxed([]) == []


def test_single_rule_no_dependencies() -> None:
    graph = build_graph([_rule("a")])
    assert graph.rule_ids() == ["a"]
    assert [r.id for r in graph.topo_sorted()] == ["a"]


def test_linear_chain_topologically_sorted() -> None:
    """``A → B → C`` produces emission order ``C, B, A`` (dependencies first)."""
    rules = [_rule("a", "b"), _rule("b", "c"), _rule("c")]
    graph = build_graph(rules)
    assert [r.id for r in graph.topo_sorted()] == ["c", "b", "a"]


def test_independent_rules_alpha_ordered_for_determinism() -> None:
    rules = [_rule("c"), _rule("a"), _rule("b")]
    graph = build_graph(rules)
    assert [r.id for r in graph.topo_sorted()] == ["a", "b", "c"]


def test_cycle_detected_and_raises_with_trace() -> None:
    """``A → B → A`` (two-node cycle) raises ``GraphError`` listing the cycle."""
    rules = [_rule("a", "b"), _rule("b", "a")]
    with pytest.raises(GraphError) as exc:
        build_graph(rules)
    msg = str(exc.value)
    assert "cycle" in msg.lower()
    assert "a" in msg and "b" in msg


def test_three_node_cycle_detected() -> None:
    rules = [_rule("a", "b"), _rule("b", "c"), _rule("c", "a")]
    with pytest.raises(GraphError):
        build_graph(rules)


def test_self_dependency_raises() -> None:
    with pytest.raises(GraphError) as exc:
        build_graph([_rule("a", "a")])
    assert "themselves" in str(exc.value).lower() or "self" in str(exc.value).lower()


def test_missing_dependency_raises_with_rule_id() -> None:
    with pytest.raises(GraphError) as exc:
        build_graph([_rule("a", "nonexistent")])
    msg = str(exc.value)
    assert "nonexistent" in msg
    assert "a" in msg


def test_duplicate_rule_id_raises() -> None:
    with pytest.raises(GraphError) as exc:
        build_graph([_rule("a"), _rule("a")])
    assert "duplicate" in str(exc.value).lower() or "id" in str(exc.value).lower()


def test_transitive_dependencies_returns_closure() -> None:
    rules = [_rule("a", "b"), _rule("b", "c"), _rule("c"), _rule("d")]
    graph = build_graph(rules)
    assert graph.transitive_dependencies("a") == {"b", "c"}
    assert graph.transitive_dependencies("b") == {"c"}
    assert graph.transitive_dependencies("c") == set()
    assert graph.transitive_dependencies("d") == set()


def test_diamond_dependency_emits_dep_once() -> None:
    """``A → {B, C}`` and ``B → D`` and ``C → D``: topo sort emits D once, before B/C, before A."""
    rules = [_rule("a", "b", "c"), _rule("b", "d"), _rule("c", "d"), _rule("d")]
    graph = build_graph(rules)
    order = [r.id for r in graph.topo_sorted()]
    assert len(order) == 4
    assert order.index("d") < order.index("b")
    assert order.index("d") < order.index("c")
    assert order.index("b") < order.index("a")
    assert order.index("c") < order.index("a")


def test_live_corpus_dag_is_acyclic() -> None:
    """Acceptance criterion: the 18-rule Phase-3 corpus must form a DAG."""
    rules = parse_all()
    graph = build_graph(rules)
    order = graph.topo_sorted()
    assert len(order) == len(rules)
    emitted = []
    for r in order:
        for dep in graph.dependencies_of(r.id):
            assert dep in emitted, (
                f"Topo order violated: {r.id} appears before its dep {dep}. "
                f"emitted so far: {emitted}"
            )
        emitted.append(r.id)
