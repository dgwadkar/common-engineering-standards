"""Phase 4 acceptance tests for ``compiler.core.resolve_globs``."""
from __future__ import annotations

import pytest

from compiler.core.resolve_globs import (
    ARCHITECTURE_LAYER,
    GLOBAL_LANGUAGE,
    GlobResolutionError,
    cross_cuts_every_file,
    load_layer_glob_map,
    resolve_globs,
    supported_languages,
    supported_layers,
)


def test_load_layer_glob_map_returns_dict_with_languages() -> None:
    m = load_layer_glob_map()
    assert "java" in m
    assert "typescript" in m
    assert "python" in m


def test_supported_languages_excludes_schema_metadata() -> None:
    langs = supported_languages()
    assert "java" in langs
    assert "$schema" not in langs
    assert "$comment" not in langs


def test_supported_layers_excludes_comment_keys() -> None:
    layers = supported_layers("java")
    assert "controller" in layers
    assert "service" in layers
    assert "$comment_layers" not in layers


def test_java_controller_resolves_to_three_globs() -> None:
    globs = resolve_globs("java", ["controller"])
    assert globs == sorted(
        ["**/controller/**/*.java", "**/web/**/*.java", "**/rest/**/*.java"]
    )


def test_java_architecture_layer_returns_empty_globs() -> None:
    """The ``architecture`` sentinel routes to ``alwaysApply: true`` (no globs)."""
    assert resolve_globs("java", ["architecture"]) == []


def test_global_pseudo_language_returns_empty_globs() -> None:
    """Phase-3 lesson: ``language: global`` rules cross-cut every stack and have no globs."""
    assert resolve_globs(GLOBAL_LANGUAGE, ["architecture"]) == []


def test_multiple_layers_dedupe_and_sort() -> None:
    """Multi-layer rules merge globs from each layer and dedupe."""
    globs = resolve_globs("java", ["controller", "service"])
    # 3 controller globs + 2 service globs, all unique.
    assert len(globs) == 5
    assert globs == sorted(globs)
    assert "**/service/**/*.java" in globs
    assert "**/controller/**/*.java" in globs


def test_unknown_language_raises() -> None:
    with pytest.raises(GlobResolutionError) as exc:
        resolve_globs("haskell", ["controller"])
    assert "haskell" in str(exc.value)


def test_unknown_layer_for_known_language_raises() -> None:
    with pytest.raises(GlobResolutionError) as exc:
        resolve_globs("java", ["does-not-exist"])
    assert "does-not-exist" in str(exc.value)


def test_empty_layers_raises() -> None:
    """The source-rule schema requires ``minItems: 1`` for ``layers``; mirror that here."""
    with pytest.raises(GlobResolutionError):
        resolve_globs("java", [])


def test_cross_cuts_every_file_returns_true_for_architecture() -> None:
    assert cross_cuts_every_file("java", ["architecture"]) is True


def test_cross_cuts_every_file_returns_true_for_global() -> None:
    assert cross_cuts_every_file(GLOBAL_LANGUAGE, ["architecture"]) is True


def test_cross_cuts_every_file_returns_false_for_narrow_layer() -> None:
    assert cross_cuts_every_file("java", ["controller"]) is False


def test_resolve_globs_accepts_test_override_map() -> None:
    """Tests can pass a synthetic layer-glob map to exercise edge cases without live state."""
    fake_map = {
        "$schema": "ignored",
        "kotlin": {
            "controller": ["**/*Controller.kt"],
            "all": ["**/*.kt"],
            "architecture": [],
        },
    }
    assert resolve_globs("kotlin", ["controller"], fake_map) == ["**/*Controller.kt"]
    assert resolve_globs("kotlin", ["architecture"], fake_map) == []


def test_architecture_takes_precedence_when_mixed_with_other_layers() -> None:
    """``[architecture, controller]`` is permitted by the schema; architecture wins."""
    assert resolve_globs("java", ["architecture", "controller"]) == []


def test_empty_layer_globs_falls_back_to_all() -> None:
    """A layer defined but empty falls back to the language's ``all`` glob."""
    fake_map = {
        "kotlin": {
            "controller": [],
            "all": ["**/*.kt"],
        },
    }
    assert resolve_globs("kotlin", ["controller"], fake_map) == ["**/*.kt"]
