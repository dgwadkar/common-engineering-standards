"""Builds the rule dependency DAG, detects cycles, and topologically sorts.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 3.

Why this exists
---------------

Cursor MDC emission is per-rule-file (independent files in ``.cursor/rules/``), so ordering does
not matter for the Phase-4 transformer. The dependency graph is still needed because:

1. **Reference integrity**: a rule with ``dependencies: [foo]`` whose ``foo`` does not exist
   would silently ship — the compiler must fail loudly so the author can fix it.
2. **Cycle detection**: a misconfigured author who lists ``A → B → A`` should see a build
   failure with a precise cycle trace, not surprising downstream behavior.
3. **Topological order**: Phase 5 transformers (Copilot, Claude, Junie, AGENTS.md) emit a single
   concatenated file, and they need dependencies emitted before dependents so the reader's eye
   meets prerequisites first. Phase 4 builds the DAG so Phase 5 can topologically sort against
   it with one Kahn's-algorithm call.

API
---

* ``build_graph(rules)`` → ``RuleGraph`` — validates references, raises on cycle or missing
  edge.
* ``RuleGraph.topo_sorted()`` → ``list[SourceRule]`` — Kahn's algorithm, deterministic
  tie-break by rule id for reproducible builds.
* ``RuleGraph.transitive_dependencies(rule_id)`` → ``set[str]`` — Phase-5 transformers need
  this for "include with closure" semantics.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set

from compiler.core.parse_source import SourceRule


class GraphError(ValueError):
    """Raised when the dependency graph cannot be built (cycle, missing reference, etc.)."""


@dataclasses.dataclass(frozen=True)
class RuleGraph:
    """Immutable representation of the dependency graph across a rule set.

    Edges point from a rule to each rule it depends on (``A → B`` means "A declares B as a
    dependency"). For topological emission of concatenated targets, dependencies are emitted
    BEFORE dependents — i.e., B comes before A in the topo order.
    """

    rules_by_id: Dict[str, SourceRule]
    edges: Dict[str, FrozenSet[str]]  # rule_id -> set of dependency rule_ids

    def __post_init__(self) -> None:  # pragma: no cover — invariant check
        assert set(self.rules_by_id.keys()) == set(self.edges.keys()), (
            "rules_by_id and edges must share the same key set; "
            f"missing in edges: {set(self.rules_by_id) - set(self.edges)}; "
            f"extra in edges: {set(self.edges) - set(self.rules_by_id)}"
        )

    def rule_ids(self) -> List[str]:
        """Returns rule ids sorted alphabetically (deterministic)."""
        return sorted(self.rules_by_id.keys())

    def dependencies_of(self, rule_id: str) -> List[str]:
        """Direct dependencies declared by ``rule_id``, sorted alphabetically."""
        return sorted(self.edges[rule_id])

    def transitive_dependencies(self, rule_id: str) -> Set[str]:
        """All transitive dependencies of ``rule_id`` (excluding ``rule_id`` itself)."""
        if rule_id not in self.edges:
            raise GraphError(f"Unknown rule id: {rule_id!r}")
        seen: Set[str] = set()
        stack = list(self.edges[rule_id])
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.edges.get(cur, ()))
        return seen

    def topo_sorted(self) -> List[SourceRule]:
        """Topological order: dependencies come BEFORE dependents.

        Kahn's algorithm. Ties broken by rule id alphabetically so the output is reproducible.
        Raises ``GraphError`` if the graph contains a cycle (with the offending cycle traced).
        """
        # in_degree[rule] = number of edges going INTO rule (i.e., number of rules that depend on it).
        # We start from rules with no dependencies (out-edges of zero) and emit them first.
        # Note: ``edges[rule_id]`` is rule_id's outgoing edges (dependencies of rule_id), so
        # "in-degree" in the dependency graph corresponds to "len(edges[rule_id])" in our
        # rule-→-dependency direction.
        # Tie-break: deterministic via sorted() at insertion.
        remaining_deps = {rid: set(self.edges[rid]) for rid in self.rules_by_id}
        emitted_order: List[str] = []

        # Reverse adjacency: dep_id -> {rule_ids that depend on dep_id}
        dependents: Dict[str, Set[str]] = {rid: set() for rid in self.rules_by_id}
        for rid, deps in self.edges.items():
            for dep in deps:
                dependents[dep].add(rid)

        ready: List[str] = sorted(rid for rid, deps in remaining_deps.items() if not deps)
        while ready:
            # Pop the lexicographically smallest for deterministic output.
            cur = ready.pop(0)
            emitted_order.append(cur)
            for d in sorted(dependents[cur]):
                remaining_deps[d].discard(cur)
                if not remaining_deps[d] and d not in emitted_order and d not in ready:
                    # Insert maintaining sorted order so the next pop is still deterministic.
                    _insort(ready, d)

        if len(emitted_order) != len(self.rules_by_id):
            unresolved = {
                rid: sorted(remaining_deps[rid])
                for rid in self.rules_by_id
                if rid not in emitted_order
            }
            cycle = _find_cycle(unresolved)
            raise GraphError(
                f"Dependency cycle detected among {len(unresolved)} rule(s). "
                f"Example cycle: {' → '.join(cycle)} → {cycle[0]}. "
                f"Unresolved nodes: {sorted(unresolved.keys())}"
            )

        return [self.rules_by_id[rid] for rid in emitted_order]


def _insort(lst: List[str], item: str) -> None:
    """Bisect-style insert preserving ascending order. Avoids importing bisect for one call."""
    lo, hi = 0, len(lst)
    while lo < hi:
        mid = (lo + hi) // 2
        if lst[mid] < item:
            lo = mid + 1
        else:
            hi = mid
    lst.insert(lo, item)


def _find_cycle(unresolved: Dict[str, List[str]]) -> List[str]:
    """Returns one cycle as a list of node ids (e.g., ``['a', 'b', 'c']`` means ``a→b→c→a``)."""
    start = sorted(unresolved.keys())[0]
    path: List[str] = []
    in_path: Set[str] = set()

    def dfs(node: str) -> Optional[List[str]]:
        if node in in_path:
            cycle_start = path.index(node)
            return path[cycle_start:]
        if node not in unresolved:
            return None
        path.append(node)
        in_path.add(node)
        for dep in unresolved[node]:
            res = dfs(dep)
            if res is not None:
                return res
        path.pop()
        in_path.remove(node)
        return None

    result = dfs(start)
    return result if result is not None else [start]


def topo_sort_relaxed(rules: Iterable[SourceRule]) -> List[SourceRule]:
    """Topologically sorts ``rules`` while ignoring dependency edges that fall OUTSIDE the input set.

    Phase 5 transformers receive a stack-filtered subset of the full corpus. Some rules in the
    subset declare dependencies on rules that the stack filter excluded (different
    ``framework_version`` range, for example). The strict ``build_graph`` validates that every
    dependency reference resolves to an authored rule — which is true for the FULL corpus but
    not for an arbitrary subset. ``topo_sort_relaxed`` is the subset-friendly counterpart: it
    keeps only intra-subset edges, drops the rest, and Kahn-sorts within the subset.

    Cycle detection within the subset still applies; a cycle is a build failure.

    Use this for concatenated targets (Copilot, Claude, Junie, AGENTS.md). For the full-corpus
    pipeline (e.g., Phase 7 release validation), keep using ``build_graph`` — the strict
    validation is the right guardrail at that level.
    """
    rules_list = list(rules)
    subset_ids = {r.id for r in rules_list}
    rules_by_id = {r.id: r for r in rules_list}

    # Build subset-local adjacency: edge from rule_id -> dep_id only when dep_id is in subset.
    remaining_deps: Dict[str, Set[str]] = {
        rid: {d for d in rules_by_id[rid].dependencies if d in subset_ids} for rid in subset_ids
    }
    dependents: Dict[str, Set[str]] = {rid: set() for rid in subset_ids}
    for rid, deps in remaining_deps.items():
        for dep in deps:
            dependents[dep].add(rid)

    emitted_order: List[str] = []
    ready: List[str] = sorted(rid for rid, deps in remaining_deps.items() if not deps)
    while ready:
        cur = ready.pop(0)
        emitted_order.append(cur)
        for d in sorted(dependents[cur]):
            remaining_deps[d].discard(cur)
            if not remaining_deps[d] and d not in emitted_order and d not in ready:
                _insort(ready, d)

    if len(emitted_order) != len(subset_ids):
        unresolved = {
            rid: sorted(remaining_deps[rid]) for rid in subset_ids if rid not in emitted_order
        }
        cycle = _find_cycle(unresolved)
        raise GraphError(
            f"Dependency cycle detected within filtered subset of {len(unresolved)} rule(s). "
            f"Example cycle: {' → '.join(cycle)} → {cycle[0]}. "
            f"Unresolved nodes: {sorted(unresolved.keys())}"
        )

    return [rules_by_id[rid] for rid in emitted_order]


def build_graph(rules: Iterable[SourceRule]) -> RuleGraph:
    """Builds and validates a ``RuleGraph`` from a rule set.

    Validation checks:

    1. Every rule has a unique ``id``. Duplicates are a build failure.
    2. Every ``dependencies:`` entry resolves to an authored rule. Missing references are a
       build failure with a clear error message.
    3. No self-dependency. ``A → A`` is a degenerate cycle and unambiguously authoring error.
    4. No cycle anywhere in the graph (deferred to ``topo_sorted()``).

    Raises ``GraphError`` on any of the above.
    """
    rules_list = list(rules)
    rules_by_id: Dict[str, SourceRule] = {}
    for r in rules_list:
        if r.id in rules_by_id:
            raise GraphError(
                f"Duplicate rule id '{r.id}': "
                f"first declared in {rules_by_id[r.id].relative_path}, "
                f"re-declared in {r.relative_path}."
            )
        rules_by_id[r.id] = r

    edges: Dict[str, FrozenSet[str]] = {}
    missing: List[str] = []
    self_loops: List[str] = []
    for rule in rules_list:
        deps = set(rule.dependencies)
        if rule.id in deps:
            self_loops.append(rule.id)
        for d in deps:
            if d not in rules_by_id:
                missing.append(f"{rule.id} → {d} (declared in {rule.relative_path})")
        edges[rule.id] = frozenset(deps)

    if self_loops:
        raise GraphError(
            f"Rule(s) declare themselves as a dependency (degenerate cycle): {sorted(self_loops)}"
        )
    if missing:
        raise GraphError(
            "Dependency reference(s) do not resolve to any authored rule:\n  - "
            + "\n  - ".join(sorted(missing))
        )

    graph = RuleGraph(rules_by_id=rules_by_id, edges=edges)
    # Probe for cycles eagerly so callers see the failure here rather than on first topo use.
    graph.topo_sorted()
    return graph


__all__ = ["GraphError", "RuleGraph", "build_graph", "topo_sort_relaxed"]
