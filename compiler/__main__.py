"""Compiler CLI driver — `python -m compiler ...`.

Phase 4 / Phase 5 / Phase 7 deliverable per `docs/02-implementation-plan.md` §7 task 6,
§8 task 6, and §10 task 2 (the Phase-7 release workflow calls this CLI with
``--all-stacks``).

Usage::

    python -m compiler --stack java-spring-boot-3 --target cursor --out dist/
    python -m compiler --stack java-spring-boot-3 --target all    --out dist/
    python -m compiler --all-stacks               --target all    --out dist/   # Phase 7

Behavior
--------

1. Parses every ``source/**/*.md`` file into a typed ``SourceRule``.
2. Builds and validates the dependency DAG (refs resolve; no cycles).
3. Filters rules down to those that apply to ``--stack`` (or each stack in turn under
   ``--all-stacks``).
4. Routes the filtered subset through the per-tool transformer named by ``--target``. Targets:

   * ``cursor``          — Cursor MDC files (Phase 4).
   * ``github_copilot``  — Concatenated ``.github/copilot-instructions.md`` (Phase 5).
   * ``claude_skills``   — Concatenated ``CLAUDE.md`` (Phase 5).
   * ``junie``           — Numbered-list ``.junie/AGENTS.md`` (Phase 5).
   * ``agents_md``       — Universal ≤150-line ``AGENTS.md`` (Phase 5).
   * ``memory_bank``     — Six-file Memory Bank scaffold (Phase 5).
   * ``all``             — Run every transformer above for the chosen stack.

5. Writes outputs under ``<--out>/stacks/<stack>/<target>/...`` per
   ``schemas/target-tools.schema.json``'s ``output_path_template``. Under ``--all-stacks``
   the path layout is identical, with one ``stacks/<stack-id>/`` subtree per known stack —
   this matches the byte-for-byte shape that ``release.yml`` commits into ``dist/`` and that
   the Phase-6 ``tests/test_compiler_golden.py`` fixtures already lock per-stack.
6. Emits one structured JSON log line per emit / skip event (stderr).

Exit codes::

    0  success
    1  build failure (parse error, schema validation error, cycle, missing dep,
       AGENTS.md ≤150-line cap exceeded, etc.)
    2  invocation error (unknown stack, unknown target, missing arg)
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Optional, Sequence

from compiler.core.build_graph import GraphError, build_graph
from compiler.core.logging_setup import get_logger, log_event
from compiler.core.parse_source import SourceRuleError, parse_all
from compiler.core.stack_filter import (
    STACKS,
    StackFilterError,
    filter_for_stack,
    known_stack_ids,
    stack_by_id,
)
from compiler.transformers import (
    claude_md,
    copilot_instructions,
    cursor_mdc,
    junie_agents_md,
    memory_bank_scaffold,
    universal_agents_md,
)
from compiler.transformers.universal_agents_md import AgentsMdTooLongError

# Targets dispatched by name. Phase 4 shipped `cursor`; Phase 5 adds the remaining five.
SUPPORTED_TARGETS = (
    "cursor",
    "github_copilot",
    "claude_skills",
    "junie",
    "agents_md",
    "memory_bank",
    "all",
)


def _make_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m compiler",
        description=(
            "Compile source rules under source/ into per-tool distribution artifacts under "
            "the directory passed to --out. The Phase-4 driver ships the Cursor MDC target; "
            "Phases 5-7 will add Copilot, Claude, Junie, AGENTS.md, Memory Bank, and "
            "ArchUnit emitters."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    stack_group = ap.add_mutually_exclusive_group(required=True)
    stack_group.add_argument(
        "--stack",
        help=f"Target a single stack id. Known: {', '.join(known_stack_ids())}.",
    )
    stack_group.add_argument(
        "--all-stacks",
        action="store_true",
        help=(
            "Compile for every known stack in turn. Equivalent to running --stack once per "
            "id in compiler.core.stack_filter.STACKS, in deterministic alphabetical order. "
            "This is the mode the Phase-7 release workflow uses to regenerate the entire "
            "dist/ tree in one invocation (docs/02-implementation-plan.md §10 task 2)."
        ),
    )
    ap.add_argument(
        "--target",
        required=True,
        choices=SUPPORTED_TARGETS,
        help=(
            "Which downstream tool to compile for. Choices: cursor, github_copilot, "
            "claude_skills, junie, agents_md, memory_bank, all. 'all' runs every transformer."
        ),
    )
    ap.add_argument(
        "--out",
        required=True,
        type=pathlib.Path,
        help=(
            "Output root directory. The compiler writes "
            "<out>/stacks/<stack>/<target>/... per the schema's output_path_template. "
            "Typical value in production: 'dist/'."
        ),
    )
    ap.add_argument(
        "--source-root",
        type=pathlib.Path,
        default=None,
        help="Override the source/ root (for tests). Defaults to repo's source/ directory.",
    )
    ap.add_argument(
        "--no-graph",
        action="store_true",
        help="Skip dependency-graph build (tests only). Cursor MDC emission is per-rule-file "
        "so this is safe in isolation; production runs always build the graph.",
    )
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _make_arg_parser().parse_args(argv)

    logger = get_logger()

    # ----- Resolve target stack list -----
    # The argparse mutually-exclusive group guarantees exactly one of {--stack, --all-stacks}
    # is set, so we don't have to defend against both/neither here.
    if args.all_stacks:
        # Deterministic alphabetical order — mirrors known_stack_ids() and the per-stack loop
        # in tests/test_compiler_golden.py::_FIXTURE_TO_STACK that Phase 6 already locked.
        try:
            stacks = [stack_by_id(sid) for sid in known_stack_ids()]
        except StackFilterError as e:  # pragma: no cover - known_stack_ids is curated
            print(f"Error: {e}", file=sys.stderr)
            return 2
    else:
        try:
            stacks = [stack_by_id(args.stack)]
        except StackFilterError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

    # ----- Parse source/ ONCE (independent of stack) -----
    roots = [args.source_root] if args.source_root else None
    try:
        rules = parse_all(roots=roots) if roots else parse_all()
    except SourceRuleError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    log_event(logger, "parse-complete", rule_count=len(rules))

    # ----- Validate dependency graph ONCE (independent of stack) -----
    if not args.no_graph:
        try:
            graph = build_graph(rules)
        except GraphError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        log_event(logger, "graph-complete", node_count=len(graph.rule_ids()))

    out_root: pathlib.Path = args.out.resolve()
    targets_to_run: tuple[str, ...] = (
        ("cursor", "github_copilot", "claude_skills", "junie", "agents_md", "memory_bank")
        if args.target == "all"
        else (args.target,)
    )

    # ----- Per-stack pipeline: filter → dispatch every requested target -----
    for stack in stacks:
        filtered = filter_for_stack(rules, stack)
        log_event(
            logger,
            "stack-filter-complete",
            stack=stack.id,
            kept=len(filtered),
            excluded=len(rules) - len(filtered),
        )

        for target_id in targets_to_run:
            try:
                emitted = _dispatch_target(target_id, filtered, stack, out_root, logger)
            except AgentsMdTooLongError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            log_event(
                logger,
                "transformer-complete",
                target=target_id,
                stack=stack.id,
                files_written=len(emitted),
                bytes_total=sum(e.bytes_written for e in emitted),
            )

    if args.all_stacks:
        log_event(
            logger,
            "all-stacks-complete",
            stacks_compiled=len(stacks),
            stack_ids=[s.id for s in stacks],
        )

    return 0


def _dispatch_target(
    target_id: str,
    filtered_rules,
    stack,
    out_root: pathlib.Path,
    logger,
):
    """Routes one target id to its transformer. Returns the list of emitted-file records."""
    if target_id == "cursor":
        return cursor_mdc.emit_for_stack(filtered_rules, stack, dist_root=out_root, logger=logger)
    if target_id == "github_copilot":
        return copilot_instructions.emit_for_stack(
            filtered_rules, stack, dist_root=out_root, logger=logger
        )
    if target_id == "claude_skills":
        return claude_md.emit_for_stack(filtered_rules, stack, dist_root=out_root, logger=logger)
    if target_id == "junie":
        return junie_agents_md.emit_for_stack(
            filtered_rules, stack, dist_root=out_root, logger=logger
        )
    if target_id == "agents_md":
        return universal_agents_md.emit_for_stack(
            filtered_rules, stack, dist_root=out_root, logger=logger
        )
    if target_id == "memory_bank":
        return memory_bank_scaffold.emit_for_stack(
            filtered_rules, stack, dist_root=out_root, logger=logger
        )
    raise ValueError(f"Unknown target id: {target_id!r}")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
