"""GitHub Copilot transformer — one concatenated ``copilot-instructions.md`` per stack.

Phase 5 deliverable per `docs/02-implementation-plan.md` §8 task 1.

Output contract
---------------

For each stack, this transformer writes a single Markdown file at
``<dist_root>/stacks/<stack_id>/copilot/copilot-instructions.md``. The file is dropped verbatim
into a consumer repo's ``.github/copilot-instructions.md`` by the Phase-8 sync tool.

Content structure (Architecture Upgrade Report §6.4):

1. A short heading-level preamble identifying the stack (human-readable name + pinned version).
2. The full rule corpus that opts into ``target_tools.github_copilot: true``, grouped under H2
   section headers keyed by ``scope.layers``. Rules within a section appear in dependency-first
   topological order so prerequisites read before dependents.
3. Each rule contributes its title (as H3) followed by its Markdown body — but with the source
   ``# <title>`` H1 heading stripped (the H3 replaces it). The compiler also strips the
   ``archunit_test`` metadata and any other non-AI-relevant content; the body's narrative prose
   carries the AI guidance verbatim.

Group ordering: ``architecture`` first (cross-cutting), then the alphabetical concrete layers
(``config``, ``controller``, ``di``, ``error-handling``, ``repository``, ``service``, ``test``),
then ``all`` last. Rules whose ``scope.layers`` contain multiple values appear under EACH section
they touch — Copilot users grep by section, and duplication is cheaper than under-coverage.
"""
from __future__ import annotations

import dataclasses
import logging
import pathlib
import re
from typing import Iterable, List, Optional

from compiler.core.build_graph import topo_sort_relaxed
from compiler.core.logging_setup import get_logger, log_event
from compiler.core.parse_source import SourceRule
from compiler.core.stack_filter import Stack

TARGET_ID = "github_copilot"
OUTPUT_RELATIVE_DIR = "copilot"
OUTPUT_FILENAME = "copilot-instructions.md"

# Canonical layer presentation order. Architecture leads (cross-cutting baseline), `all` trails.
_LAYER_ORDER: tuple[str, ...] = (
    "architecture",
    "config",
    "controller",
    "di",
    "error-handling",
    "repository",
    "service",
    "test",
    "all",
)

_HUMAN_LAYER_TITLES: dict[str, str] = {
    "architecture": "Architecture (Cross-Cutting)",
    "config": "Configuration Layer",
    "controller": "Controller Layer",
    "di": "Dependency Injection",
    "error-handling": "Error Handling",
    "repository": "Repository Layer",
    "service": "Service Layer",
    "test": "Testing Layer",
    "all": "All Code",
}


@dataclasses.dataclass(frozen=True)
class EmittedFile:
    """Record of one written file. Returned by ``emit_for_stack`` for caller-side reporting."""

    target_id: str
    stack_id: str
    output_path: pathlib.Path
    relative_output_path: str
    bytes_written: int
    rule_count: int


def _strip_h1_heading(body: str) -> str:
    """Removes the leading ``# Heading`` line (and any blank line that follows it).

    The H1 always matches ``title:`` per the schema's ``title`` description; we replace it with
    an H3 per-rule heading in the concatenated output.
    """
    lines = body.splitlines(keepends=True)
    i = 0
    # Skip leading blank lines.
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        i += 1
        # Skip a single trailing blank line after the H1.
        if i < len(lines) and lines[i].strip() == "":
            i += 1
    return "".join(lines[i:])


def _demote_headings(body: str) -> str:
    """Demotes all remaining ATX headings by one level so the per-rule H3 stays dominant.

    Source rules use H2 (``## 1. Context...``) for top-level sections; after demotion they
    become H4 inside the concatenated file. Headings already at H6 are left as-is (Markdown
    has no H7).
    """
    out_lines: List[str] = []
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            # Count leading `#` characters.
            n = 0
            while n < len(stripped) and stripped[n] == "#":
                n += 1
            # ATX headings: 1..6 `#` followed by a space.
            if 1 <= n <= 6 and n < len(stripped) and stripped[n] == " " and n < 6:
                indent_len = len(line) - len(stripped)
                line = line[:indent_len] + "#" * (n + 1) + stripped[n:]
        out_lines.append(line)
    return "".join(out_lines)


def _grouping_for_rule(rule: SourceRule) -> tuple[str, ...]:
    """Returns the layer keys this rule appears under, preserving the schema's enum order."""
    return tuple(layer for layer in _LAYER_ORDER if layer in rule.scope.layers)


def _filter_target_rules(rules: Iterable[SourceRule], target_id: str) -> List[SourceRule]:
    """Drops rules whose ``target_tools.<target_id>`` is False."""
    return [r for r in rules if r.target_tools.is_enabled(target_id)]


def _topological_order(rules: List[SourceRule]) -> List[SourceRule]:
    """Returns ``rules`` in dependency-first topological order within the subset.

    Uses ``topo_sort_relaxed`` so cross-subset edges (a rule whose dependency was excluded by
    the stack filter, e.g., a different ``framework_version`` range) are ignored. Cycles within
    the subset are still surfaced as build failures.
    """
    if not rules:
        return []
    return topo_sort_relaxed(rules)


def render_copilot_instructions(rules: List[SourceRule], stack: Stack) -> str:
    """Renders the full concatenated Markdown for one stack.

    Pure function — no I/O. Phase-6 golden snapshots will lock the exact byte output.
    """
    target_rules = _filter_target_rules(rules, TARGET_ID)
    ordered = _topological_order(target_rules)

    grouped: dict[str, List[SourceRule]] = {layer: [] for layer in _LAYER_ORDER}
    for rule in ordered:
        for layer in _grouping_for_rule(rule):
            grouped[layer].append(rule)

    parts: List[str] = []
    parts.append(f"# GitHub Copilot Instructions — {stack.human_name}\n\n")
    parts.append(
        "This file is generated by `engineering-standards-central` from the canonical source\n"
        "rules under `source/`. Do not edit by hand. It is consumed automatically by GitHub\n"
        "Copilot Chat and Copilot Coding Agent when present at `.github/copilot-instructions.md`.\n\n"
    )
    parts.append(
        f"**Stack**: `{stack.id}` — {stack.human_name} (framework `{stack.framework}` "
        f"`{stack.framework_version}`).\n\n"
    )
    parts.append(
        f"**Rule count**: {len(ordered)} rule(s) opt into Copilot for this stack.\n\n"
    )
    parts.append("---\n\n")

    for layer in _LAYER_ORDER:
        layer_rules = grouped[layer]
        if not layer_rules:
            continue
        parts.append(f"## {_HUMAN_LAYER_TITLES[layer]}\n\n")
        for rule in layer_rules:
            parts.append(f"### {rule.title}\n\n")
            body = _strip_h1_heading(rule.body)
            body = _demote_headings(body)
            body = body.rstrip() + "\n\n"
            parts.append(body)
        parts.append("---\n\n")

    # Trim the trailing separator+blank.
    output = "".join(parts)
    output = re.sub(r"---\n\n\Z", "", output).rstrip() + "\n"
    return output


def emit_for_stack(
    rules: Iterable[SourceRule],
    stack: Stack,
    *,
    dist_root: pathlib.Path,
    logger: Optional[logging.Logger] = None,
) -> List[EmittedFile]:
    """Writes the concatenated ``copilot-instructions.md`` file for the stack.

    Returns a list with exactly one ``EmittedFile`` (since this is a concatenated target) — the
    list shape mirrors the cursor transformer's API so the CLI driver dispatches uniformly.
    Returns an empty list if no rules opt into the target.
    """
    if logger is None:
        logger = get_logger()

    rules_list = list(rules)
    target_rules = _filter_target_rules(rules_list, TARGET_ID)
    if not target_rules:
        log_event(
            logger,
            "skip",
            target=TARGET_ID,
            stack=stack.id,
            reason="no rules opt into github_copilot for this stack",
        )
        return []

    content = render_copilot_instructions(rules_list, stack)
    out_dir = pathlib.Path(dist_root) / "stacks" / stack.id / OUTPUT_RELATIVE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_FILENAME
    out_path.write_text(content, encoding="utf-8")

    try:
        rel = str(out_path.resolve().relative_to(pathlib.Path(dist_root).resolve())).replace(
            "\\", "/"
        )
        rel_path = f"{dist_root}/{rel}" if str(dist_root) else rel
    except ValueError:
        rel_path = str(out_path).replace("\\", "/")

    record = EmittedFile(
        target_id=TARGET_ID,
        stack_id=stack.id,
        output_path=out_path,
        relative_output_path=rel_path,
        bytes_written=len(content.encode("utf-8")),
        rule_count=len(target_rules),
    )
    log_event(
        logger,
        "emit",
        target=TARGET_ID,
        stack=stack.id,
        output_path=rel_path,
        bytes=record.bytes_written,
        rule_count=record.rule_count,
    )
    return [record]


__all__ = [
    "EmittedFile",
    "OUTPUT_FILENAME",
    "OUTPUT_RELATIVE_DIR",
    "TARGET_ID",
    "emit_for_stack",
    "render_copilot_instructions",
]
