"""Filters a rule set down to those that apply to a given target stack.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 4.

A stack is a (language, framework, pinned-version) triple identifying one of the consumer
shapes the standards corpus ships for. The Phase-1 scaffold reserved four stack directories
under ``dist/stacks/``:

* ``java-spring-boot-3``       (Java + Spring Boot 3.x)
* ``java-spring-boot-2``       (Java + Spring Boot 2.7 legacy)
* ``typescript-nestjs-10``     (NestJS 10)
* ``python-fastapi-0-110``     (FastAPI 0.110.x)

A rule applies to a stack iff:

1. ``scope.language`` matches the stack's language OR is the ``global`` pseudo-language
   (Phase-3 lesson: global rules apply to every stack).
2. ``scope.framework`` is ``None`` (language-core / global rules) OR equals the stack's
   framework id.
3. ``scope.framework_version`` is unspecified (applies to all versions) OR its semver-range
   expression satisfies the stack's pinned version.

The semver-range grammar accepted by ``scope.framework_version`` (per the schema's regex):

* Bare version:           ``3.0.0``, ``3.0``, ``3``
* Comparator + version:   ``>=3.0``, ``<=2.7.18``, ``>3.0``, ``<4.0``, ``=3.2.0``
* Caret range:            ``^2.7.0``       → ``>=2.7.0 <3.0.0``
* Tilde range:            ``~3.1``         → ``>=3.1.0 <3.2.0``
* Conjunction:            ``>=2.0 <4.0``   (whitespace-separated AND)

Disjunction (``||``) is intentionally NOT supported — the schema's pattern does not accept it,
and the corpus has not needed it. Phase 4+ may extend if a real rule demands it.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from typing import Iterable, List, Optional, Sequence, Tuple

from compiler.core.parse_source import SourceRule
from compiler.core.resolve_globs import GLOBAL_LANGUAGE


@dataclasses.dataclass(frozen=True)
class Stack:
    """One target stack the compiler can build for."""

    id: str  # e.g., "java-spring-boot-3"
    language: str  # "java" | "typescript" | "python"
    framework: str  # "spring-boot" | "nestjs" | "fastapi"
    framework_version: str  # pinned to one full semver, e.g., "3.2.0"
    human_name: str  # human-readable name for the description line


# Path to the Phase-8 canonical catalog (`schemas/stacks.json`). Both the Python compiler
# (this module) and the Node consumer-sync CLI consume this file so the two implementations
# cannot drift. The lookup walks up from this file's parent to the repo root because the
# module may be imported from various working directories (CI runners, ad-hoc scripts).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_STACKS_CATALOG_PATH = _REPO_ROOT / "schemas" / "stacks.json"


def _load_stack_catalog() -> dict[str, Stack]:
    """Loads the canonical stack catalog from `schemas/stacks.json`.

    Phase-8 lesson: this used to be a hard-coded dict in this module that drifted from a
    parallel hard-coded dict in `tools/generate_dist_readme.py`. Both now read the same
    JSON file. The previous dict layout is preserved so existing imports of `STACKS`
    continue to work.
    """
    with open(_STACKS_CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    # The JSON's `properties.stacks.const` holds the canonical descriptor list. We read it
    # from `.const` rather than a top-level array because the file is also a JSON Schema —
    # the const-array embedding lets `jsonschema.validate()` validate any future schema-only
    # consumer's input shape against the same source.
    descriptors = catalog["properties"]["stacks"]["const"]
    out: dict[str, Stack] = {}
    for desc in descriptors:
        out[desc["id"]] = Stack(
            id=desc["id"],
            language=desc["language"],
            framework=desc["framework"],
            framework_version=desc["framework_version"],
            human_name=desc["human_name"],
        )
    return out


# The canonical stack catalog, loaded lazily at import time from schemas/stacks.json.
# Bump pinned versions in that JSON file (not here) — this constant is a typed view onto
# the catalog. Phase 8 (consumer sync) reads the SAME file from Node so detection logic
# stays aligned with what the compiler emits.
STACKS: dict[str, Stack] = _load_stack_catalog()


class StackFilterError(ValueError):
    """Raised when an unknown stack id is referenced or a version expression is unparseable."""


def known_stack_ids() -> List[str]:
    """Returns the canonical stack ids in alphabetical order."""
    return sorted(STACKS.keys())


def stack_by_id(stack_id: str) -> Stack:
    """Looks up the canonical stack descriptor by id. Raises if unknown."""
    if stack_id not in STACKS:
        raise StackFilterError(
            f"Unknown stack id: {stack_id!r}. Known stacks: {known_stack_ids()}"
        )
    return STACKS[stack_id]


# ---------------------------------------------------------------------------
# Semver-range matching
# ---------------------------------------------------------------------------


def _parse_version(v: str) -> Tuple[int, int, int]:
    """Parses a version string into a (major, minor, patch) triple. Missing parts default to 0."""
    parts = v.strip().split(".")
    if not 1 <= len(parts) <= 3:
        raise StackFilterError(f"Cannot parse version {v!r}: expected 1–3 dotted numeric parts.")
    try:
        triple = tuple(int(p) for p in parts) + (0,) * (3 - len(parts))
    except ValueError as e:
        raise StackFilterError(f"Cannot parse version {v!r}: non-integer component ({e})") from e
    return triple  # type: ignore[return-value]


_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|~|\^)?\s*(\d+(?:\.\d+){0,2})$")


def _expand_comparator(token: str) -> List[Tuple[str, Tuple[int, int, int]]]:
    """Expands a single token like ``^2.7.0`` into a list of (op, version) primitives.

    Caret and tilde each expand to two primitives (>= lower AND < upper). Other comparators
    expand to one primitive.
    """
    m = _COMPARATOR_RE.match(token)
    if not m:
        raise StackFilterError(f"Unparseable comparator token: {token!r}")
    op, ver_str = m.group(1) or "=", m.group(2)
    major, minor, patch = _parse_version(ver_str)

    if op == "^":
        # ^X.Y.Z is "compatible with X.Y.Z" — same major, version >= X.Y.Z.
        # ^0.Y.Z keeps minor (npm semantics). ^0.0.Z keeps patch (npm semantics).
        if major > 0:
            upper = (major + 1, 0, 0)
        elif minor > 0:
            upper = (major, minor + 1, 0)
        else:
            upper = (major, minor, patch + 1)
        return [(">=", (major, minor, patch)), ("<", upper)]
    if op == "~":
        # ~X.Y.Z is "approximately X.Y" — same major and minor, patch >= Z.
        # ~X.Y is the same as ~X.Y.0.
        # ~X is the same as ^X (major-only).
        if len(ver_str.split(".")) == 1:
            return [(">=", (major, 0, 0)), ("<", (major + 1, 0, 0))]
        upper = (major, minor + 1, 0)
        return [(">=", (major, minor, patch)), ("<", upper)]
    if op == "=":
        return [("=", (major, minor, patch))]
    return [(op, (major, minor, patch))]


def _matches_primitive(target: Tuple[int, int, int], op: str, ref: Tuple[int, int, int]) -> bool:
    if op == "=":
        return target == ref
    if op == ">=":
        return target >= ref
    if op == "<=":
        return target <= ref
    if op == ">":
        return target > ref
    if op == "<":
        return target < ref
    raise StackFilterError(f"Internal error: unknown operator {op!r}")  # pragma: no cover


def matches_framework_version_range(expression: str, pinned_version: str) -> bool:
    """Returns True iff the pinned version satisfies the range expression.

    Tokens in a conjunction expression are separated by whitespace; ALL must match.
    """
    target = _parse_version(pinned_version)
    primitives: List[Tuple[str, Tuple[int, int, int]]] = []
    for token in expression.strip().split():
        primitives.extend(_expand_comparator(token))
    return all(_matches_primitive(target, op, ref) for op, ref in primitives)


# ---------------------------------------------------------------------------
# Stack filter
# ---------------------------------------------------------------------------


def applies_to_stack(rule: SourceRule, stack: Stack) -> bool:
    """Returns True iff ``rule`` should ship to ``stack``."""
    scope = rule.scope

    # 1. Language match: exact OR the `global` pseudo-language.
    if scope.language != stack.language and scope.language != GLOBAL_LANGUAGE:
        return False

    # 2. Framework match: a None scope.framework applies to every stack with the same language,
    # provided #1 passed. A string must exact-match the stack's framework.
    if scope.framework is not None and scope.framework != stack.framework:
        return False

    # 3. Framework-version range match: omitted → applies to every version of the framework.
    if scope.framework_version:
        if not matches_framework_version_range(scope.framework_version, stack.framework_version):
            return False

    return True


def filter_for_stack(
    rules: Iterable[SourceRule],
    stack: Stack,
    *,
    include_drafts: bool = False,
) -> List[SourceRule]:
    """Returns the subset of ``rules`` that should ship to ``stack``.

    By default, only ``status == "approved"`` rules ship. ``status == "draft"`` rules are
    excluded; ``status == "deprecated"`` rules are INCLUDED (they ship with a deprecation
    banner; that banner is the Phase 5 transformer's responsibility). Pass
    ``include_drafts=True`` in tests to bypass the status filter.
    """
    out: List[SourceRule] = []
    for rule in rules:
        if not include_drafts and rule.status == "draft":
            continue
        if applies_to_stack(rule, stack):
            out.append(rule)
    return out


__all__ = [
    "STACKS",
    "Stack",
    "StackFilterError",
    "applies_to_stack",
    "filter_for_stack",
    "known_stack_ids",
    "matches_framework_version_range",
    "stack_by_id",
]
