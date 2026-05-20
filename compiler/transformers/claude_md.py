"""Claude Code transformer — one concatenated ``CLAUDE.md`` per stack.

Phase 5 deliverable per `docs/02-implementation-plan.md` §8 task 2.

Output contract
---------------

For each stack, this transformer writes a single Markdown file at
``<dist_root>/stacks/<stack_id>/claude/CLAUDE.md``. The file is dropped verbatim into a consumer
repo's root-level ``CLAUDE.md`` by the Phase-8 sync tool.

The Claude-tone differs from the Copilot variant in three ways:

1. **Directive preamble**: A short "When generating <lang> code, you MUST follow these rules"
   framing block at the top, because Claude responds best to explicit, role-anchored directives
   (Anthropic's Claude-3.5/Opus/Sonnet system-prompt guidance, 2025–2026).
2. **Rule lead-in**: Each rule's H3 heading is followed by a one-line "**You MUST: …**" lead-in
   derived from the rule's title before the rule body, so a Claude session reads each rule as a
   directive even when the body is referenced out of order.
3. **No archunit_test or other meta-fields**: Same as Copilot; AI-irrelevant metadata is stripped.

Group ordering matches the Copilot transformer: ``architecture`` first, then alphabetical
concrete layers, then ``all`` last.
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

TARGET_ID = "claude_skills"
OUTPUT_RELATIVE_DIR = "claude"
OUTPUT_FILENAME = "CLAUDE.md"

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

_LANGUAGE_HUMAN_NAMES: dict[str, str] = {
    "java": "Java",
    "typescript": "TypeScript",
    "python": "Python",
}


@dataclasses.dataclass(frozen=True)
class EmittedFile:
    """Record of one written file."""

    target_id: str
    stack_id: str
    output_path: pathlib.Path
    relative_output_path: str
    bytes_written: int
    rule_count: int


def _strip_h1_heading(body: str) -> str:
    """Drops the leading ``# Heading`` line + a single trailing blank line if any."""
    lines = body.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        i += 1
        if i < len(lines) and lines[i].strip() == "":
            i += 1
    return "".join(lines[i:])


def _demote_headings(body: str) -> str:
    """Demotes ATX headings by one level (H2 → H3, ...) up to H5 (H6 stays at H6)."""
    out_lines: List[str] = []
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            n = 0
            while n < len(stripped) and stripped[n] == "#":
                n += 1
            if 1 <= n <= 6 and n < len(stripped) and stripped[n] == " " and n < 6:
                indent_len = len(line) - len(stripped)
                line = line[:indent_len] + "#" * (n + 1) + stripped[n:]
        out_lines.append(line)
    return "".join(out_lines)


def _grouping_for_rule(rule: SourceRule) -> tuple[str, ...]:
    return tuple(layer for layer in _LAYER_ORDER if layer in rule.scope.layers)


def _filter_target_rules(rules: Iterable[SourceRule], target_id: str) -> List[SourceRule]:
    return [r for r in rules if r.target_tools.is_enabled(target_id)]


def _topological_order(rules: List[SourceRule]) -> List[SourceRule]:
    if not rules:
        return []
    return topo_sort_relaxed(rules)


def _directive_for(rule: SourceRule) -> str:
    """Produces a single-line ``**You MUST: …**`` directive derived from the rule title."""
    title = rule.title.strip()
    if title.endswith("."):
        title = title[:-1]
    return f"**You MUST: {title}.**"


def render_claude_md(rules: List[SourceRule], stack: Stack) -> str:
    """Renders the concatenated ``CLAUDE.md`` for one stack. Pure function."""
    target_rules = _filter_target_rules(rules, TARGET_ID)
    ordered = _topological_order(target_rules)

    grouped: dict[str, List[SourceRule]] = {layer: [] for layer in _LAYER_ORDER}
    for rule in ordered:
        for layer in _grouping_for_rule(rule):
            grouped[layer].append(rule)

    language_human = _LANGUAGE_HUMAN_NAMES.get(stack.language, stack.language.capitalize())

    parts: List[str] = []
    parts.append(f"# Claude Code Instructions — {stack.human_name}\n\n")
    parts.append(
        "This file is generated by `engineering-standards-central` from canonical source rules.\n"
        "Do not edit by hand. Claude Code reads `CLAUDE.md` at the repository root automatically.\n\n"
    )
    parts.append("## How to Read This File\n\n")
    parts.append(
        f"When generating, modifying, or reviewing {language_human} code in this repository,\n"
        f"you MUST follow every rule listed below. Each rule is grouped by the architectural\n"
        f"layer it applies to. Rules within a layer appear in dependency-first order: if Rule A\n"
        f"depends on Rule B, B appears first.\n\n"
    )
    parts.append(
        f"**Stack**: `{stack.id}` — {stack.human_name} (framework `{stack.framework}` "
        f"`{stack.framework_version}`).\n\n"
    )
    parts.append(
        f"**Rule count**: {len(ordered)} rule(s) opt into Claude Code for this stack.\n\n"
    )
    parts.append("---\n\n")

    for layer in _LAYER_ORDER:
        layer_rules = grouped[layer]
        if not layer_rules:
            continue
        parts.append(f"## {_HUMAN_LAYER_TITLES[layer]}\n\n")
        for rule in layer_rules:
            parts.append(f"### {rule.title}\n\n")
            parts.append(f"{_directive_for(rule)}\n\n")
            body = _strip_h1_heading(rule.body)
            body = _demote_headings(body)
            body = body.rstrip() + "\n\n"
            parts.append(body)
        parts.append("---\n\n")

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
    """Writes the concatenated ``CLAUDE.md`` file for the stack."""
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
            reason="no rules opt into claude_skills for this stack",
        )
        return []

    content = render_claude_md(rules_list, stack)
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
    "render_claude_md",
]
