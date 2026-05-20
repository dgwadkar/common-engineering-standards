"""Resolves ``scope.language + scope.layers[]`` into a deduplicated globs array.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 2.

The canonical translation table lives at ``schemas/layer-glob-map.json``. This module loads it
once at import time and exposes a single function, ``resolve_globs(...)``, plus a small set of
helpers used by the Cursor MDC transformer.

Sentinel semantics (from the schema's own ``$comment``):

* ``architecture`` layer  → an empty array, signaling the Cursor MDC transformer to emit
  ``alwaysApply: true`` with no ``globs:`` line.
* ``global`` pseudo-language (from ``source/_global/*.md``) → always returns ``[]`` for the same
  reason. The Phase-3 log surfaced that ``global`` is intentionally absent from the layer-glob
  map because cross-cutting global rules always pair with ``cursor_mode: always``.
* Any other layer with an empty layer-glob entry falls back to the language's ``all`` glob list
  (the catch-all per-language pattern), so a future language addition that documents only ``all``
  still produces a usable rule.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, List, Optional, Sequence

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LAYER_GLOB_MAP_PATH = REPO_ROOT / "schemas" / "layer-glob-map.json"

# Layer that signals "cross-cuts every file" — the compiler routes the rule to alwaysApply:true.
ARCHITECTURE_LAYER = "architecture"

# Pseudo-language for `source/_global/*.md` rules. Intentionally absent from layer-glob-map.json
# because global rules always pair with `cursor_mode: always`.
GLOBAL_LANGUAGE = "global"


class GlobResolutionError(ValueError):
    """Raised when a (language, layers) pair cannot be resolved to a globs list."""


_LAYER_GLOB_MAP_CACHE: Optional[dict] = None


def load_layer_glob_map(path: Optional[pathlib.Path] = None) -> dict:
    """Loads ``schemas/layer-glob-map.json`` (or a test override) and returns the parsed dict.

    Result is cached when ``path`` is omitted so repeated calls during a compiler run are free.
    Pass an explicit path in tests to bypass the cache.
    """
    global _LAYER_GLOB_MAP_CACHE
    if path is None:
        if _LAYER_GLOB_MAP_CACHE is None:
            _LAYER_GLOB_MAP_CACHE = json.loads(LAYER_GLOB_MAP_PATH.read_text(encoding="utf-8"))
        return _LAYER_GLOB_MAP_CACHE
    return json.loads(path.read_text(encoding="utf-8"))


def _is_schema_metadata_key(key: str) -> bool:
    """Top-level keys like ``$schema``, ``$id``, ``$comment`` are not language entries."""
    return key.startswith("$")


def supported_languages(layer_glob_map: Optional[dict] = None) -> List[str]:
    """Returns the language identifiers present in the layer-glob-map (e.g., ``['java', ...]``)."""
    m = layer_glob_map or load_layer_glob_map()
    return sorted(k for k in m.keys() if not _is_schema_metadata_key(k))


def supported_layers(language: str, layer_glob_map: Optional[dict] = None) -> List[str]:
    """Returns the layer identifiers defined for ``language`` (excluding ``$comment_layers``)."""
    m = layer_glob_map or load_layer_glob_map()
    if language not in m:
        raise GlobResolutionError(
            f"Language '{language}' is not present in {LAYER_GLOB_MAP_PATH.name}. "
            f"Known languages: {supported_languages(m)}"
        )
    lang_entry = m[language]
    return sorted(k for k in lang_entry.keys() if not _is_schema_metadata_key(k))


def resolve_globs(
    language: str,
    layers: Sequence[str],
    layer_glob_map: Optional[dict] = None,
) -> List[str]:
    """Joins ``language + layers[]`` against the layer-glob-map.

    Returns
    -------
    list[str]
        A deduplicated, sorted globs list. Returns ``[]`` for the architecture sentinel and for
        the ``global`` pseudo-language (the Cursor MDC transformer interprets ``[]`` together
        with ``cursor_mode == "always"`` as ``alwaysApply: true``).

    Raises
    ------
    GlobResolutionError
        If ``language`` is unknown OR any entry in ``layers`` is unknown for that language. The
        compiler treats this as a build failure — better to fail loudly than to silently emit a
        rule with no scope.
    """
    if not layers:
        raise GlobResolutionError(
            f"resolve_globs(language={language!r}, layers=[]) — `layers` must be non-empty "
            "(the schema requires `minItems: 1`)."
        )

    m = layer_glob_map or load_layer_glob_map()

    # Sentinel: the `global` pseudo-language always returns []. Cross-cutting global rules pair
    # with cursor_mode: always and never need a glob list.
    if language == GLOBAL_LANGUAGE:
        return []

    if language not in m:
        raise GlobResolutionError(
            f"Language '{language}' is not present in {LAYER_GLOB_MAP_PATH.name}. "
            f"Known languages: {supported_languages(m)}. "
            f"Add a new top-level entry to extend coverage (Standards-Architect approval per CODEOWNERS)."
        )
    lang_entry = m[language]

    # Sentinel: an exclusive [architecture] (single layer) returns []. Mixed layers like
    # [architecture, controller] would be ambiguous — the schema permits the combination, but
    # the architecture sentinel takes precedence to keep behavior predictable.
    if ARCHITECTURE_LAYER in layers:
        return []

    collected: List[str] = []
    seen: set[str] = set()
    unknown: List[str] = []
    for layer in layers:
        if layer not in lang_entry:
            unknown.append(layer)
            continue
        layer_globs = lang_entry[layer]
        # Fall back to the language's `all` glob when a layer is defined but empty (rare).
        if not layer_globs and layer != ARCHITECTURE_LAYER:
            layer_globs = lang_entry.get("all", [])
        for g in layer_globs:
            if g not in seen:
                seen.add(g)
                collected.append(g)

    if unknown:
        raise GlobResolutionError(
            f"Unknown layer(s) {unknown!r} for language '{language}'. "
            f"Known layers: {supported_layers(language, m)}."
        )

    return sorted(collected)


def cross_cuts_every_file(language: str, layers: Sequence[str]) -> bool:
    """True when the (language, layers) pair routes to ``alwaysApply: true`` (no globs)."""
    if language == GLOBAL_LANGUAGE:
        return True
    return ARCHITECTURE_LAYER in layers


__all__ = [
    "ARCHITECTURE_LAYER",
    "GLOBAL_LANGUAGE",
    "GlobResolutionError",
    "cross_cuts_every_file",
    "load_layer_glob_map",
    "resolve_globs",
    "supported_languages",
    "supported_layers",
]
