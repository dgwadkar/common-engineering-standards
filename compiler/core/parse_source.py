#!/usr/bin/env python3
"""Source-rule frontmatter parser and validator.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 1. Extends the Phase-2 slice
that shipped under the same module name (the `--validate-only` CLI entry point) with the typed
``SourceRule`` dataclass return path the rest of the compiler consumes.

Public surface
--------------

CLI:
  - ``--validate-only`` (Phase 2 behavior, preserved): walks ``source/**/*.md`` and
    ``schemas/examples/*.md``, validates each frontmatter object against
    ``schemas/source-rule.schema.json``, exits 0/1/2.

Library:
  - ``SourceRule`` — typed dataclass mirroring the source frontmatter schema. The Markdown body
    is preserved verbatim on ``body`` for downstream transformers.
  - ``parse_source_file(path)`` — parse one file into a ``SourceRule``. Validates against the
    schema; raises ``SourceRuleError`` on any failure.
  - ``parse_all(roots=None)`` — parse every ``source/**/*.md`` under each root (default: the
    repo's ``source/`` directory). Returns a list of ``SourceRule`` instances in deterministic
    sorted-by-path order. Aggregates all errors before raising so a single run surfaces every
    failure.

The schema is the single source of truth — this module never duplicates validation logic. Bumps
to the schema (e.g., adding a new enum value to ``cursor_mode``) take effect here automatically.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys
from typing import Any, Iterable, List, Optional, Sequence

import jsonschema
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "source-rule.schema.json"
DEFAULT_SOURCE_ROOTS: tuple[pathlib.Path, ...] = (REPO_ROOT / "source",)

# Conservative frontmatter detector. Matches a leading `---`, captures the YAML body up to the
# next `---` line, and allows either a trailing newline or EOF after the closing fence.
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n(?P<md>.*))?\Z", re.DOTALL)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Scope:
    """The ``scope`` block of a source rule's frontmatter."""

    language: str
    framework: Optional[str]
    layers: tuple[str, ...]
    framework_version: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class TargetTools:
    """Per-target opt-in booleans. The schema's ``anyOf`` clause guarantees at least one true."""

    cursor: bool
    github_copilot: bool
    claude_skills: bool
    junie: bool
    agents_md: bool

    def is_enabled(self, target_id: str) -> bool:
        """Returns True when this rule opts into the named target id (e.g., ``cursor``)."""
        return bool(getattr(self, target_id))


@dataclasses.dataclass(frozen=True)
class Activation:
    """The ``activation`` block of a source rule's frontmatter."""

    cursor_mode: str  # always | auto-attach | agent-requested | manual
    agents_md_priority: str  # high | medium | low


@dataclasses.dataclass(frozen=True)
class SourceRule:
    """One parsed source rule. Frozen so downstream code cannot accidentally mutate it."""

    id: str
    title: str
    version: str
    status: str
    scope: Scope
    target_tools: TargetTools
    activation: Activation
    dependencies: tuple[str, ...]
    related_logic_holes: tuple[int, ...]
    archunit_test: Optional[str]
    body: str  # Markdown body verbatim, with frontmatter stripped. Always ends in a newline.
    source_path: pathlib.Path  # repo-relative path is preferred but absolute is accepted

    @property
    def relative_path(self) -> str:
        """Returns the path relative to the repo root, with forward slashes — for logs/diagnostics."""
        try:
            return str(self.source_path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            return str(self.source_path).replace("\\", "/")


class SourceRuleError(ValueError):
    """Raised when a source file cannot be parsed into a ``SourceRule``."""


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------


def extract_frontmatter_and_body(text: str) -> tuple[Optional[dict], str]:
    """Splits ``text`` into ``(frontmatter_obj, markdown_body)``.

    Returns ``(None, text)`` if the file has no leading ``---`` frontmatter block. The body
    always ends with a single trailing newline so the cursor MDC transformer can concatenate
    deterministically.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    body_yaml = match.group("body")
    md_body = match.group("md") or ""
    if not md_body.endswith("\n"):
        md_body += "\n"

    if not body_yaml.strip():
        return {}, md_body
    parsed = yaml.safe_load(body_yaml)
    if not isinstance(parsed, dict):
        return {"__INVALID_FRONTMATTER_NOT_OBJECT__": parsed}, md_body
    return parsed, md_body


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def _load_schema() -> dict:
    if not SCHEMA_PATH.is_file():
        raise SourceRuleError(f"Schema file not found at {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


_VALIDATOR_CACHE: Optional[jsonschema.Draft202012Validator] = None


def _validator() -> jsonschema.Draft202012Validator:
    global _VALIDATOR_CACHE
    if _VALIDATOR_CACHE is None:
        _VALIDATOR_CACHE = jsonschema.Draft202012Validator(_load_schema())
    return _VALIDATOR_CACHE


def _format_path(p: Sequence[Any]) -> str:
    parts = [str(seg) for seg in p]
    return ".".join(parts) if parts else "<root>"


# ---------------------------------------------------------------------------
# Public parse API
# ---------------------------------------------------------------------------


def _from_frontmatter(fm: dict, body: str, path: pathlib.Path) -> SourceRule:
    """Constructs a ``SourceRule`` from a schema-validated frontmatter object."""
    scope_obj = fm["scope"]
    tools_obj = fm["target_tools"]
    activation_obj = fm["activation"]
    return SourceRule(
        id=fm["id"],
        title=fm["title"],
        version=fm["version"],
        status=fm["status"],
        scope=Scope(
            language=scope_obj["language"],
            framework=scope_obj.get("framework"),
            layers=tuple(scope_obj["layers"]),
            framework_version=scope_obj.get("framework_version"),
        ),
        target_tools=TargetTools(
            cursor=bool(tools_obj["cursor"]),
            github_copilot=bool(tools_obj["github_copilot"]),
            claude_skills=bool(tools_obj["claude_skills"]),
            junie=bool(tools_obj["junie"]),
            agents_md=bool(tools_obj["agents_md"]),
        ),
        activation=Activation(
            cursor_mode=activation_obj["cursor_mode"],
            agents_md_priority=activation_obj["agents_md_priority"],
        ),
        dependencies=tuple(fm.get("dependencies") or ()),
        related_logic_holes=tuple(fm.get("related_logic_holes") or ()),
        archunit_test=fm.get("archunit_test"),
        body=body,
        source_path=path,
    )


def parse_source_file(path: pathlib.Path) -> SourceRule:
    """Reads ``path`` and returns a typed ``SourceRule``. Raises ``SourceRuleError`` on any failure."""
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise SourceRuleError(f"{path}: cannot read file: {e}") from e

    fm, body = extract_frontmatter_and_body(text)
    if fm is None:
        raise SourceRuleError(
            f"{path}: missing YAML frontmatter (file must begin with a `---` line)"
        )
    if "__INVALID_FRONTMATTER_NOT_OBJECT__" in fm:
        raise SourceRuleError(f"{path}: frontmatter parses as YAML but is not an object/mapping")

    errors = list(_validator().iter_errors(fm))
    if errors:
        msg_lines = [f"{path}: failed schema validation:"]
        for err in errors:
            loc = _format_path(err.absolute_path)
            msg_lines.append(f"  - {loc}: {err.message}")
        raise SourceRuleError("\n".join(msg_lines))

    return _from_frontmatter(fm, body, pathlib.Path(path))


def iter_markdown_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    """Yields every Markdown file under ``root`` in sorted order (skips dot-files)."""
    if not root.exists():
        return
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("."):
            continue
        yield p


def parse_all(roots: Optional[Sequence[pathlib.Path]] = None) -> List[SourceRule]:
    """Parses every ``*.md`` file under each root and returns a list of typed ``SourceRule``s.

    The default roots are ``[source/]`` relative to the repo. ``schemas/examples/*.md`` is NOT
    included by default — those are reference fixtures, not production rules. Tests that want
    the example included can pass ``roots=[REPO_ROOT / 'source', REPO_ROOT / 'schemas' / 'examples']``.

    Aggregates errors before raising so a single CI run surfaces every failure at once.
    """
    if roots is None:
        roots = DEFAULT_SOURCE_ROOTS

    rules: List[SourceRule] = []
    errors: List[str] = []
    for root in roots:
        for p in iter_markdown_files(pathlib.Path(root)):
            try:
                rules.append(parse_source_file(p))
            except SourceRuleError as e:
                errors.append(str(e))

    if errors:
        raise SourceRuleError(
            f"parse_all() encountered {len(errors)} parsing/validation failure(s):\n\n"
            + "\n\n".join(errors)
        )
    return rules


# ---------------------------------------------------------------------------
# CLI — preserves the Phase-2 `--validate-only` behavior verbatim
# ---------------------------------------------------------------------------


def _validate_file_for_cli(
    path: pathlib.Path,
    validator: jsonschema.Draft202012Validator,
    require_frontmatter: bool,
) -> List[str]:
    """Returns a list of error strings for a single file. Empty list means valid."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: cannot read file: {e}"]

    fm, _body = extract_frontmatter_and_body(text)
    if fm is None:
        if require_frontmatter:
            return [f"{path}: missing YAML frontmatter (file must begin with a `---` line)"]
        return []
    if "__INVALID_FRONTMATTER_NOT_OBJECT__" in fm:
        return [f"{path}: frontmatter parses as YAML but is not an object/mapping"]

    errors: List[str] = []
    for err in validator.iter_errors(fm):
        loc = _format_path(err.absolute_path)
        errors.append(f"{path}: {loc}: {err.message}")
    return errors


def _collect_cli_targets(explicit_path: Optional[str]) -> List[tuple[pathlib.Path, bool]]:
    if explicit_path:
        p = pathlib.Path(explicit_path).resolve()
        return [(p, True)]
    targets: List[tuple[pathlib.Path, bool]] = []
    for p in iter_markdown_files(REPO_ROOT / "source"):
        targets.append((p, True))
    for p in iter_markdown_files(REPO_ROOT / "schemas" / "examples"):
        targets.append((p, True))
    return targets


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate source-rule frontmatter against schemas/source-rule.schema.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate frontmatter and exit. The library API (parse_all, parse_source_file) is "
        "the recommended way to consume rules from Phase 4 onwards.",
    )
    ap.add_argument(
        "--path",
        help="Validate a single file instead of walking source/**/*.md and schemas/examples/*.md.",
    )
    args = ap.parse_args(argv)

    if not args.validate_only:
        print(
            "Error: parse_source.py CLI only implements --validate-only. To consume rules "
            "programmatically from Phase 4 onwards, import "
            "`compiler.core.parse_source.parse_all` (or invoke `python -m compiler ...` for "
            "the full pipeline — see compiler/__main__.py).",
            file=sys.stderr,
        )
        return 2

    try:
        validator = _validator()
    except SourceRuleError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"Error: {SCHEMA_PATH} is not valid JSON: {e}", file=sys.stderr)
        return 2
    except jsonschema.SchemaError as e:
        print(
            f"Error: {SCHEMA_PATH} is not a valid JSON Schema Draft 2020-12 document: {e}",
            file=sys.stderr,
        )
        return 2

    targets = _collect_cli_targets(args.path)

    if not targets:
        print(
            "No source files to validate. This is the expected state when source/ is empty. "
            "schemas/examples/ should still contain the reference valid-source-rule.md — if you "
            "see this message, that file is also missing."
        )
        return 0

    all_errors: List[str] = []
    files_validated = 0
    for path, require_fm in targets:
        files_validated += 1
        all_errors.extend(_validate_file_for_cli(path, validator, require_frontmatter=require_fm))

    if all_errors:
        print(
            f"Validation FAILED: {len(all_errors)} issue(s) across {files_validated} file(s):",
            file=sys.stderr,
        )
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Validation PASSED: {files_validated} file(s) conform to source-rule.schema.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
