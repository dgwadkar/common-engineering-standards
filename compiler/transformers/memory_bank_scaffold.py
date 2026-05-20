"""Memory Bank scaffold transformer — six canonical files per stack.

Phase 5 deliverable per `docs/02-implementation-plan.md` §8 task 5.

Output contract
---------------

For each stack, this transformer writes six Markdown files under
``<dist_root>/stacks/<stack_id>/memory-bank/``:

* ``projectbrief.md``    — Stub, marked ``<!-- TEAM-MAINTAINED -->``.
* ``productContext.md``  — Stub, marked ``<!-- TEAM-MAINTAINED -->``.
* ``activeContext.md``   — Stub, marked ``<!-- TEAM-MAINTAINED -->``.
* ``systemPatterns.md``  — Pre-populated with the stack's layered architecture diagram +
                           boundary discipline summary (from ``_meta.yml``).
* ``techContext.md``     — Pre-populated with framework version, dependencies, env vars
                           (from ``_meta.yml``).
* ``progress.md``        — Stub, marked ``<!-- TEAM-MAINTAINED -->``.

Memory Bank is the consumer-side runtime context layer popularized by `vanzan01/cursor-memory-bank`
(Architecture Upgrade Report §3.2). Cursor's agent reads all six at the start of every session.
The four stub files are intentionally empty-of-content because they are team-maintained; the
two pre-populated files give consumers a working baseline they can extend.

Source of stack metadata
------------------------

Each stack's metadata lives at ``source/<lang>/<framework>/_meta.yml``. The transformer reads
this file at render time. If the file is missing, the two pre-populated files fall back to a
minimal template derived purely from the ``Stack`` descriptor.
"""
from __future__ import annotations

import dataclasses
import logging
import pathlib
from typing import Iterable, List, Optional

import yaml

from compiler.core.logging_setup import get_logger, log_event
from compiler.core.parse_source import REPO_ROOT, SourceRule
from compiler.core.stack_filter import Stack

TARGET_ID = "memory_bank"
OUTPUT_RELATIVE_DIR = "memory-bank"

# All six canonical Memory Bank filenames per the vanzan01/cursor-memory-bank convention.
PROJECT_BRIEF_FILENAME = "projectbrief.md"
PRODUCT_CONTEXT_FILENAME = "productContext.md"
ACTIVE_CONTEXT_FILENAME = "activeContext.md"
SYSTEM_PATTERNS_FILENAME = "systemPatterns.md"
TECH_CONTEXT_FILENAME = "techContext.md"
PROGRESS_FILENAME = "progress.md"

MEMORY_BANK_FILES: tuple[str, ...] = (
    PROJECT_BRIEF_FILENAME,
    PRODUCT_CONTEXT_FILENAME,
    ACTIVE_CONTEXT_FILENAME,
    SYSTEM_PATTERNS_FILENAME,
    TECH_CONTEXT_FILENAME,
    PROGRESS_FILENAME,
)

TEAM_MAINTAINED_TAG = "<!-- TEAM-MAINTAINED -->"


@dataclasses.dataclass(frozen=True)
class EmittedFile:
    """Record of one written memory-bank file."""

    target_id: str
    stack_id: str
    output_path: pathlib.Path
    relative_output_path: str
    bytes_written: int
    filename: str


def _meta_yaml_path(stack: Stack) -> pathlib.Path:
    """Resolves ``source/<lang>/<framework>/_meta.yml`` for the stack."""
    return REPO_ROOT / "source" / stack.language / stack.framework / "_meta.yml"


def _load_meta(stack: Stack) -> dict:
    """Returns the ``_meta.yml`` dict for ``stack``, or an empty dict if the file is absent."""
    path = _meta_yaml_path(stack)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def render_project_brief(stack: Stack) -> str:
    return (
        f"# Project Brief — {stack.human_name} Service\n\n"
        f"{TEAM_MAINTAINED_TAG}\n\n"
        f"This file is a stub. The pilot team owns its content.\n\n"
        f"Fill in:\n\n"
        f"- **Service mission** — What does this service do? Who depends on it?\n"
        f"- **Key constraints** — SLOs, regulatory, integration points.\n"
        f"- **Out of scope** — What this service explicitly does NOT do.\n"
    )


def render_product_context(stack: Stack) -> str:
    return (
        f"# Product Context — {stack.human_name} Service\n\n"
        f"{TEAM_MAINTAINED_TAG}\n\n"
        f"This file is a stub. The pilot team owns its content.\n\n"
        f"Fill in:\n\n"
        f"- **Why this service exists** — The product problem it solves.\n"
        f"- **User personas** — Who consumes it (internal or external).\n"
        f"- **Success metrics** — How adoption / value is measured.\n"
    )


def render_active_context(stack: Stack) -> str:
    return (
        f"# Active Context — {stack.human_name} Service\n\n"
        f"{TEAM_MAINTAINED_TAG}\n\n"
        f"This file is a stub. The pilot team owns its content and updates it WEEKLY.\n\n"
        f"Fill in:\n\n"
        f"- **Current focus** — What the team is working on this sprint.\n"
        f"- **Recent changes** — High-impact merges in the last 7 days.\n"
        f"- **Immediate next steps** — Top three items on the team's queue.\n"
    )


def render_system_patterns(stack: Stack, meta: dict) -> str:
    parts: List[str] = []
    parts.append(f"# System Patterns — {stack.human_name}\n\n")
    parts.append(
        "Pre-populated by `engineering-standards-central`. Augment with service-specific\n"
        "patterns (e.g., event-sourcing details, sharding strategy, idempotency design).\n\n"
    )

    parts.append("## Layered Architecture\n\n")
    diagram = meta.get("architecture_diagram") or _default_diagram(stack)
    parts.append(f"{diagram.rstrip()}\n\n")

    boundaries = meta.get("layer_boundaries") or []
    if boundaries:
        parts.append("## Layer Boundaries\n\n")
        for b in boundaries:
            parts.append(f"- {b}\n")
        parts.append("\n")

    parts.append("## Cross-Cutting Concerns\n\n")
    parts.append(
        "Logging, tracing, security, and error handling are governed by the canonical\n"
        "engineering standards (see `.cursor/rules/`, `CLAUDE.md`, `AGENTS.md`).\n"
    )
    return "".join(parts)


def render_tech_context(stack: Stack, meta: dict) -> str:
    parts: List[str] = []
    parts.append(f"# Tech Context — {stack.human_name}\n\n")
    parts.append(
        "Pre-populated by `engineering-standards-central` from the stack descriptor\n"
        f"`source/{stack.language}/{stack.framework}/_meta.yml`. Update via the central repo,\n"
        "not in the consumer.\n\n"
    )

    parts.append("## Stack\n\n")
    parts.append(f"- **Language**: {meta.get('language', stack.language)}\n")
    parts.append(f"- **Runtime**: {meta.get('language_runtime', '—')}\n")
    parts.append(
        f"- **Framework**: {meta.get('framework_name', stack.framework)} "
        f"{stack.framework_version}\n"
    )
    parts.append(f"- **Stack id**: `{stack.id}`\n\n")

    sv = meta.get("stack_versions", {}) or {}
    if isinstance(sv, dict):
        stack_meta = sv.get(stack.id)
        if isinstance(stack_meta, dict) and stack_meta.get("description"):
            parts.append(f"_{stack_meta['description']}_\n\n")

    required_deps = meta.get("required_dependencies") or []
    if required_deps:
        parts.append("## Required Dependencies\n\n")
        for d in required_deps:
            parts.append(f"- `{d}`\n")
        parts.append("\n")

    optional_deps = meta.get("optional_dependencies") or []
    if optional_deps:
        parts.append("## Optional Dependencies\n\n")
        for d in optional_deps:
            parts.append(f"- {d}\n")
        parts.append("\n")

    env_vars = meta.get("required_env_vars") or []
    if env_vars:
        parts.append("## Required Environment Variables\n\n")
        parts.append("| Name | Description |\n|---|---|\n")
        for entry in env_vars:
            if isinstance(entry, dict):
                name = entry.get("name", "—")
                description = entry.get("description", "")
                parts.append(f"| `{name}` | {description} |\n")
        parts.append("\n")

    parts.append("## Local Development\n\n")
    parts.append(
        "Override in the consumer with project-specific bootstrap commands (Docker Compose,\n"
        "DB seed scripts, etc.). The central baseline assumes only language- and framework-level\n"
        "conventions.\n"
    )
    return "".join(parts)


def render_progress(stack: Stack) -> str:
    return (
        f"# Progress — {stack.human_name} Service\n\n"
        f"{TEAM_MAINTAINED_TAG}\n\n"
        f"This file is a stub. The pilot team owns its content.\n\n"
        f"Fill in:\n\n"
        f"- **What works** — Production-shipped features and their owners.\n"
        f"- **What's left** — Roadmap items and rough effort estimates.\n"
        f"- **Known issues** — Open bugs / tech debt with links to tickets.\n"
    )


def _default_diagram(stack: Stack) -> str:
    """Minimal fallback diagram used when ``_meta.yml`` is absent."""
    return (
        "```mermaid\n"
        "flowchart TD\n"
        "  Client[HTTP client] --> Controller\n"
        "  Controller --> Service\n"
        "  Service --> Repository\n"
        "  Repository --> Database[(Database)]\n"
        "```\n"
    )


def render_memory_bank(stack: Stack) -> dict[str, str]:
    """Renders the full six-file content map for one stack. Pure function (modulo _meta.yml read)."""
    meta = _load_meta(stack)
    return {
        PROJECT_BRIEF_FILENAME: render_project_brief(stack),
        PRODUCT_CONTEXT_FILENAME: render_product_context(stack),
        ACTIVE_CONTEXT_FILENAME: render_active_context(stack),
        SYSTEM_PATTERNS_FILENAME: render_system_patterns(stack, meta),
        TECH_CONTEXT_FILENAME: render_tech_context(stack, meta),
        PROGRESS_FILENAME: render_progress(stack),
    }


def emit_for_stack(
    rules: Iterable[SourceRule],
    stack: Stack,
    *,
    dist_root: pathlib.Path,
    logger: Optional[logging.Logger] = None,
) -> List[EmittedFile]:
    """Writes the six Memory Bank files for the stack.

    ``rules`` is accepted for API uniformity with the other transformers but not consumed —
    Memory Bank content is derived entirely from the stack descriptor, not from rules.
    """
    if logger is None:
        logger = get_logger()
    _ = list(rules)  # exhaust the iterable so callers see the consumed shape consistently.

    content_map = render_memory_bank(stack)
    out_dir = pathlib.Path(dist_root) / "stacks" / stack.id / OUTPUT_RELATIVE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    emitted: List[EmittedFile] = []
    for filename in MEMORY_BANK_FILES:
        content = content_map[filename]
        out_path = out_dir / filename
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
            filename=filename,
        )
        emitted.append(record)
        log_event(
            logger,
            "emit",
            target=TARGET_ID,
            stack=stack.id,
            output_path=rel_path,
            bytes=record.bytes_written,
            memory_bank_file=filename,
        )
    return emitted


__all__ = [
    "ACTIVE_CONTEXT_FILENAME",
    "EmittedFile",
    "MEMORY_BANK_FILES",
    "PROGRESS_FILENAME",
    "PROJECT_BRIEF_FILENAME",
    "PRODUCT_CONTEXT_FILENAME",
    "SYSTEM_PATTERNS_FILENAME",
    "TARGET_ID",
    "TECH_CONTEXT_FILENAME",
    "emit_for_stack",
    "render_memory_bank",
]
