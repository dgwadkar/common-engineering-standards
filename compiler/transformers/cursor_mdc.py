"""Cursor MDC transformer — one ``.mdc`` file per applicable source rule.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 5.

Output contract
---------------

For each source rule that opts into Cursor (``target_tools.cursor: true``) and applies to the
target stack (``stack_filter.applies_to_stack(...)``), this transformer writes one file at
``<dist_root>/stacks/<stack_id>/cursor/rules/<rule_filename>.mdc``.

The MDC frontmatter is derived from the source rule per the decision tree in Architecture
Upgrade Report §6.3:

* ``cursor_mode == "always"`` (or the rule cross-cuts every file — i.e., ``layers: [architecture]``
  or ``language: global``) → emits ``alwaysApply: true`` with NO ``globs:`` line. Cursor's MDC
  parser treats the absence of ``globs:`` as "no glob filter."
* ``cursor_mode == "auto-attach"`` → emits ``alwaysApply: false`` and ``globs: [...]`` resolved
  from ``schemas/layer-glob-map.json``.
* ``cursor_mode == "agent-requested"`` → emits ``alwaysApply: false`` and a rich ``description:``
  line; no ``globs:`` (so Cursor's agent decides relevance based on task intent).
* ``cursor_mode == "manual"`` → emits an empty frontmatter (only ``@<rule-id>`` chat references
  activate the rule).

The body is the source rule's Markdown body verbatim (frontmatter stripped). Phase 6 golden
tests will lock this exact output shape.

File naming
-----------

Source rule ids are kebab-case and conventionally prefixed ``<lang>-<framework>-<layer>-`` for
framework-scoped rules and ``global-`` for cross-cutting ones. The generated filename strips the
``<lang>-<framework>-`` prefix to match the convention in Architecture Upgrade Report §5.2
(e.g., ``controller-validation.mdc``, not ``java-spring-controller-validation.mdc``). The
prefix-strip rule:

* ``java-spring-<layer>-<name>``  → ``<layer>-<name>.mdc``
* ``global-<name>``               → ``_global-<name>.mdc``  (matches the report's example file
                                    names like ``_global-architecture.mdc``)
* Anything else                   → ``<rule_id>.mdc`` (verbatim fallback)
"""
from __future__ import annotations

import dataclasses
import logging
import pathlib
from typing import Iterable, List, Optional

from compiler.core.logging_setup import get_logger, log_event
from compiler.core.parse_source import SourceRule
from compiler.core.resolve_globs import cross_cuts_every_file, resolve_globs
from compiler.core.stack_filter import Stack

# Activation modes per `schemas/source-rule.schema.json#activation.cursor_mode`.
MODE_ALWAYS = "always"
MODE_AUTO_ATTACH = "auto-attach"
MODE_AGENT_REQUESTED = "agent-requested"
MODE_MANUAL = "manual"

TARGET_ID = "cursor"


@dataclasses.dataclass(frozen=True)
class EmittedFile:
    """Record of one written file. Returned by ``emit_for_stack`` for caller-side reporting."""

    rule_id: str
    output_path: pathlib.Path
    relative_output_path: str  # repo/dist-relative for log payloads
    bytes_written: int


def filename_for_rule(rule: SourceRule) -> str:
    """Returns the ``.mdc`` filename for a source rule per the §5.2 convention."""
    rid = rule.id
    if rid.startswith("global-"):
        return f"_global-{rid[len('global-') :]}.mdc"
    parts = rid.split("-")
    # Framework-scoped: java-spring-<layer>-<name...> — strip the first two segments.
    if len(parts) >= 4 and parts[0] in {"java", "typescript", "python"}:
        return "-".join(parts[2:]) + ".mdc"
    return rid + ".mdc"


def render_mdc(rule: SourceRule, stack: Stack) -> str:
    """Renders the full ``.mdc`` file content for one rule (frontmatter + body).

    Pure function — no I/O. Returns a string with deterministic content so golden-snapshot
    tests (Phase 6) catch any unintended drift.
    """
    cursor_mode = rule.activation.cursor_mode
    description = f"{rule.title} — apply to {stack.human_name}"
    globs: List[str] = resolve_globs(rule.scope.language, list(rule.scope.layers))
    cross_cut = cross_cuts_every_file(rule.scope.language, list(rule.scope.layers))

    if cursor_mode == MODE_MANUAL:
        # Manual mode: empty frontmatter — Cursor only fires on `@<rule-id>` mentions.
        frontmatter_lines: List[str] = []
    elif cursor_mode == MODE_ALWAYS or cross_cut:
        frontmatter_lines = [
            f"description: {_quote(description)}",
            "alwaysApply: true",
        ]
    elif cursor_mode == MODE_AGENT_REQUESTED:
        frontmatter_lines = [
            f"description: {_quote(description)}",
            "alwaysApply: false",
        ]
    elif cursor_mode == MODE_AUTO_ATTACH:
        # auto-attach is the most common case — emit globs from layer-glob-map.
        frontmatter_lines = [
            f"description: {_quote(description)}",
            f"globs: {_render_globs(globs)}",
            "alwaysApply: false",
        ]
    else:  # pragma: no cover — schema enum guarantees one of the four above
        raise ValueError(f"Unknown cursor_mode: {cursor_mode!r}")

    parts = ["---\n"]
    parts.extend(line + "\n" for line in frontmatter_lines)
    parts.append("---\n")
    parts.append("\n")
    parts.append(rule.body if rule.body.endswith("\n") else rule.body + "\n")
    return "".join(parts)


def _quote(value: str) -> str:
    """Quotes a YAML scalar value with double quotes, escaping ``\\`` and ``"``.

    The MDC frontmatter examples in Architecture Upgrade Report §6.2 use double-quoted strings,
    and YAML's plain-scalar rules are surprising (a colon, dash, or leading question mark
    breaks plain parsing). Always-quote is safe and predictable.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_globs(globs: List[str]) -> str:
    """Renders the globs list as a YAML flow sequence."""
    if not globs:
        return "[]"
    return "[" + ", ".join(_quote(g) for g in globs) + "]"


def emit_for_stack(
    rules: Iterable[SourceRule],
    stack: Stack,
    *,
    dist_root: pathlib.Path,
    logger: Optional[logging.Logger] = None,
) -> List[EmittedFile]:
    """Writes one ``.mdc`` per applicable rule and returns the list of emitted files.

    The directory is ``<dist_root>/stacks/<stack.id>/cursor/rules/`` per
    ``schemas/target-tools.schema.json``'s ``output_path_template``. ``dist_root`` is typically
    ``dist/`` (the central-repo distribution root); tests pass ``tmp_path``.
    """
    if logger is None:
        logger = get_logger()

    out_dir = pathlib.Path(dist_root) / "stacks" / stack.id / "cursor" / "rules"
    out_dir.mkdir(parents=True, exist_ok=True)

    emitted: List[EmittedFile] = []
    for rule in rules:
        if not rule.target_tools.cursor:
            log_event(
                logger,
                "skip",
                target=TARGET_ID,
                stack=stack.id,
                rule_id=rule.id,
                reason="target_tools.cursor=false",
            )
            continue

        content = render_mdc(rule, stack)
        filename = filename_for_rule(rule)
        out_path = out_dir / filename
        out_path.write_text(content, encoding="utf-8")
        rel_path = str(out_path.resolve()).replace("\\", "/")
        try:
            rel_path = str(out_path.resolve().relative_to(pathlib.Path(dist_root).resolve())).replace(
                "\\", "/"
            )
            rel_path = f"{dist_root}/{rel_path}" if str(dist_root) else rel_path
        except ValueError:
            pass
        emitted.append(
            EmittedFile(
                rule_id=rule.id,
                output_path=out_path,
                relative_output_path=rel_path,
                bytes_written=len(content.encode("utf-8")),
            )
        )
        log_event(
            logger,
            "emit",
            target=TARGET_ID,
            stack=stack.id,
            rule_id=rule.id,
            output_path=rel_path,
            bytes=len(content.encode("utf-8")),
        )
    return emitted


__all__ = [
    "EmittedFile",
    "MODE_AGENT_REQUESTED",
    "MODE_ALWAYS",
    "MODE_AUTO_ATTACH",
    "MODE_MANUAL",
    "TARGET_ID",
    "emit_for_stack",
    "filename_for_rule",
    "render_mdc",
]
