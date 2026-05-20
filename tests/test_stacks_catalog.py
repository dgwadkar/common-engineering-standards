"""Regression tests for `schemas/stacks.json` (Phase-8 single source of truth).

Phase-7 lesson §7-b: the inline `KNOWN_STACKS` catalog in
``tools/generate_dist_readme.py`` was a duplicate of
``compiler.core.stack_filter.STACKS``. Phase 8 consolidated both into
``schemas/stacks.json``; both Python sites and the Node consumer-sync CLI now
read this file as the canonical catalog.

This module locks the catalog's:

  - Shape (validates against the same JSON Schema embedded in the file).
  - Identity (the four canonical stack ids are present).
  - Field consistency (every catalog entry's language + framework appears in
    at least one ``source/<lang>/<framework>/_meta.yml`` descriptor).
  - Cross-file alignment (the compiler's runtime ``STACKS`` and the README
    generator's ``KNOWN_STACKS`` both load from the same file and therefore
    produce identical id sets).

The Node sync CLI's parity is locked separately by ``packages/standards-sync``
unit tests; this module covers only the Python consumers.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
STACKS_CATALOG = REPO_ROOT / "schemas" / "stacks.json"


def _load() -> dict[str, Any]:
    return json.loads(STACKS_CATALOG.read_text(encoding="utf-8"))


def test_stacks_catalog_file_exists():
    assert STACKS_CATALOG.is_file(), (
        f"Phase-8 single-source-of-truth catalog missing: {STACKS_CATALOG}"
    )


def test_catalog_validates_against_its_own_schema():
    """The file is BOTH a JSON Schema AND a catalog. Validate the catalog
    against its own embedded schema to lock the shape contract.

    This catches structural drift (e.g., a future edit that adds a `runtime`
    field without updating `$defs/StackDescriptor.properties`) before either
    consumer chokes on it at runtime.
    """
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load()
    # The catalog itself is valid against its own root schema — the embedded
    # `const` array IS the data we're validating.
    jsonschema.validate({"stacks": schema["properties"]["stacks"]["const"]}, schema)


def test_catalog_lists_the_four_canonical_stacks():
    """The corpus, fixtures, golden trees, and dist all assume four stacks."""
    catalog = _load()
    descriptors = catalog["properties"]["stacks"]["const"]
    ids = sorted(d["id"] for d in descriptors)
    assert ids == [
        "java-spring-boot-2",
        "java-spring-boot-3",
        "python-fastapi-0-110",
        "typescript-nestjs-10",
    ]


def test_every_stack_has_a_detection_recipe():
    """The Node sync CLI relies on `detection.indicators[]` to be non-empty."""
    catalog = _load()
    for d in catalog["properties"]["stacks"]["const"]:
        assert d["detection"]["indicators"], (
            f"Stack {d['id']!r} has zero detection indicators; "
            "the Node sync CLI would never recognise it."
        )


def test_every_stack_has_framework_meta_descriptor():
    """Each catalog entry's (language, framework) pair must have a
    `source/<lang>/<framework>/_meta.yml` descriptor (the Phase-5 Memory Bank
    transformer consumes these). Catches the case where someone adds a stack
    to schemas/stacks.json but forgets the framework descriptor."""
    catalog = _load()
    for d in catalog["properties"]["stacks"]["const"]:
        # `_global` and language-core rules skip this check; the catalog
        # only contains framework-specific stacks.
        meta = REPO_ROOT / "source" / d["language"] / d["framework"] / "_meta.yml"
        assert meta.is_file(), (
            f"Stack {d['id']!r} declares language={d['language']!r} "
            f"framework={d['framework']!r} but {meta} is missing. "
            "Either author the _meta.yml or remove the stack from "
            "schemas/stacks.json."
        )


def test_python_compiler_loads_the_catalog():
    """The Phase-4 STACKS dict in compiler/core/stack_filter.py must be
    populated from the catalog (Phase-8 refactor of the hard-coded dict)."""
    sys.path.insert(0, str(REPO_ROOT))
    from compiler.core.stack_filter import STACKS  # noqa: WPS433

    catalog_ids = {
        d["id"]
        for d in _load()["properties"]["stacks"]["const"]
    }
    assert set(STACKS.keys()) == catalog_ids


def test_known_stacks_in_generator_loads_the_catalog():
    """tools/generate_dist_readme.py::KNOWN_STACKS must come from the
    catalog (Phase-8 refactor of the hard-coded list)."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import generate_dist_readme as gdr  # noqa: WPS433

    catalog_ids = {
        d["id"]
        for d in _load()["properties"]["stacks"]["const"]
    }
    assert {e["id"] for e in gdr.KNOWN_STACKS} == catalog_ids


def test_descriptions_in_dist_readme_match_catalog():
    """The README generator's per-stack description column must echo the
    catalog's `description` field verbatim. Locks the user-facing contract."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import generate_dist_readme as gdr  # noqa: WPS433

    catalog_by_id = {
        d["id"]: d
        for d in _load()["properties"]["stacks"]["const"]
    }
    for entry in gdr.KNOWN_STACKS:
        expected = catalog_by_id[entry["id"]]["description"]
        assert entry["description"] == expected, (
            f"Stack {entry['id']!r} description drifted from the catalog. "
            f"Catalog: {expected!r}; generator: {entry['description']!r}."
        )


def test_indicator_kinds_are_all_supported():
    """Lock the kinds the Node sync CLI knows how to evaluate. Adding a new
    `kind` requires adding the corresponding detector in
    `packages/standards-sync/src/detect-stack.js` and updating this set."""
    catalog = _load()
    supported = {
        "maven_parent",
        "maven_dependency",
        "gradle_plugin",
        "npm_dependency",
        "pep621_dependency",
    }
    for d in catalog["properties"]["stacks"]["const"]:
        for ind in d["detection"]["indicators"]:
            assert ind["kind"] in supported, (
                f"Stack {d['id']!r} uses unsupported indicator kind {ind['kind']!r}. "
                f"Supported: {sorted(supported)}. If this is intentional, "
                "update `packages/standards-sync/src/detect-stack.js` AND this test."
            )
