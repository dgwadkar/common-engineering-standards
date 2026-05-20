"""Phase 2 acceptance tests for the source-rule schema and the validator entry point.

Acceptance criterion §5 AC1 (per `docs/02-implementation-plan.md` §5):

    `pytest tests/test_schemas.py` covers: valid example passes; missing required field fails;
    invalid layer enum value fails; invalid semver in `framework_version` fails.

These four cases plus several adjacent ones (target_tools all-false, bad id pattern, etc.) live
below. AC3 ("Schema files have inline comments documenting every field") is enforced by
`test_schemas_have_inline_descriptions_on_every_field` further down.
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import textwrap

import jsonschema
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
SOURCE_RULE_SCHEMA_PATH = SCHEMAS_DIR / "source-rule.schema.json"
LAYER_GLOB_MAP_PATH = SCHEMAS_DIR / "layer-glob-map.json"
TARGET_TOOLS_SCHEMA_PATH = SCHEMAS_DIR / "target-tools.schema.json"
VALID_EXAMPLE_PATH = SCHEMAS_DIR / "examples" / "valid-source-rule.md"
VALIDATOR_SCRIPT = REPO_ROOT / "compiler" / "core" / "parse_source.py"

FRONTMATTER_RE = __import__("re").compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", __import__("re").DOTALL
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def source_rule_schema() -> dict:
    return json.loads(SOURCE_RULE_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(source_rule_schema: dict) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(source_rule_schema)
    return jsonschema.Draft202012Validator(source_rule_schema)


@pytest.fixture(scope="module")
def valid_frontmatter() -> dict:
    """Loads the canonical valid frontmatter from `schemas/examples/valid-source-rule.md`."""
    text = VALID_EXAMPLE_PATH.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    assert match, "schemas/examples/valid-source-rule.md must begin with a YAML frontmatter block"
    return yaml.safe_load(match.group("body"))


def _mutate(base: dict, **overrides) -> dict:
    """Returns a deep copy of `base` with top-level keys replaced/removed via `overrides`.

    Pass `SENTINEL_DELETE` as the value to remove a key. For nested updates, pass a sub-dict.
    """
    out = copy.deepcopy(base)
    for k, v in overrides.items():
        if v is _SENTINEL_DELETE:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            for sk, sv in v.items():
                if sv is _SENTINEL_DELETE:
                    out[k].pop(sk, None)
                else:
                    out[k][sk] = sv
        else:
            out[k] = v
    return out


_SENTINEL_DELETE = object()


# ---------------------------------------------------------------------------
# AC1 — required positive + negative cases
# ---------------------------------------------------------------------------


def test_valid_example_passes(validator, valid_frontmatter):
    """AC1 case 1: valid example passes."""
    errors = list(validator.iter_errors(valid_frontmatter))
    assert errors == [], f"Expected no errors, got: {[e.message for e in errors]}"


def test_missing_required_field_fails__title(validator, valid_frontmatter):
    """AC1 case 2 (variant a): omitting top-level required `title` fails."""
    bad = _mutate(valid_frontmatter, title=_SENTINEL_DELETE)
    errors = list(validator.iter_errors(bad))
    assert any("title" in e.message for e in errors), \
        f"Expected an error mentioning `title`, got: {[e.message for e in errors]}"


def test_missing_required_field_fails__scope(validator, valid_frontmatter):
    """AC1 case 2 (variant b): omitting top-level required `scope` fails."""
    bad = _mutate(valid_frontmatter, scope=_SENTINEL_DELETE)
    errors = list(validator.iter_errors(bad))
    assert any("scope" in e.message for e in errors), \
        f"Expected an error mentioning `scope`, got: {[e.message for e in errors]}"


def test_missing_required_field_fails__nested_layers(validator, valid_frontmatter):
    """AC1 case 2 (variant c): omitting nested required `scope.layers` fails."""
    bad = _mutate(valid_frontmatter, scope={"layers": _SENTINEL_DELETE})
    errors = list(validator.iter_errors(bad))
    assert any("layers" in e.message for e in errors), \
        f"Expected an error mentioning `layers`, got: {[e.message for e in errors]}"


def test_invalid_layer_enum_fails(validator, valid_frontmatter):
    """AC1 case 3: invalid layer enum value fails (plural typo)."""
    bad = _mutate(valid_frontmatter, scope={"layers": ["controllers"]})  # plural — not in enum
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected at least one error for `layers: ['controllers']`"
    # Specifically the enum should be the source of the failure.
    assert any(
        "controllers" in e.message or "enum" in e.message.lower() for e in errors
    ), f"Expected an enum-related error, got: {[e.message for e in errors]}"


def test_invalid_framework_version_fails(validator, valid_frontmatter):
    """AC1 case 4: invalid semver in `framework_version` fails."""
    bad = _mutate(valid_frontmatter, scope={"framework_version": "not-a-semver"})
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected at least one error for `framework_version: 'not-a-semver'`"
    assert any(
        "framework_version" in str(list(e.absolute_path))
        or "pattern" in e.message.lower()
        or "not-a-semver" in e.message
        for e in errors
    ), f"Expected pattern-related error, got: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# Adjacent negative cases — strengthen confidence in the schema's coverage
# ---------------------------------------------------------------------------


def test_target_tools_all_false_fails(validator, valid_frontmatter):
    """A rule with every `target_tools.*` set to `false` is dead code; the schema must reject it."""
    bad = _mutate(
        valid_frontmatter,
        target_tools={
            "cursor": False,
            "github_copilot": False,
            "claude_skills": False,
            "junie": False,
            "agents_md": False,
        },
    )
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected at least one error when every target_tools.* boolean is false"


def test_bad_id_pattern_fails(validator, valid_frontmatter):
    """`id` must be kebab-case ASCII; mixed-case or spaces must fail."""
    for bad_id in ("Bad ID", "BadID", "bad_id_underscore", "trailing-", "-leading"):
        bad = _mutate(valid_frontmatter, id=bad_id)
        errors = list(validator.iter_errors(bad))
        assert errors, f"Expected error for id={bad_id!r}"


def test_bad_cursor_mode_fails(validator, valid_frontmatter):
    bad = _mutate(valid_frontmatter, activation={"cursor_mode": "auto_attach"})  # underscore typo
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected error for activation.cursor_mode='auto_attach' (must be hyphenated)"


def test_bad_status_fails(validator, valid_frontmatter):
    bad = _mutate(valid_frontmatter, status="published")  # not in enum
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected error for status='published'"


def test_archunit_test_non_java_path_fails(validator, valid_frontmatter):
    bad = _mutate(valid_frontmatter, archunit_test="testing/archunit/Foo.kt")
    errors = list(validator.iter_errors(bad))
    assert errors, "Expected error for archunit_test ending in `.kt`"


def test_archunit_test_null_allowed(validator, valid_frontmatter):
    ok = _mutate(valid_frontmatter, archunit_test=None)
    errors = list(validator.iter_errors(ok))
    assert errors == [], f"`archunit_test: null` must be allowed; got: {[e.message for e in errors]}"


def test_framework_null_allowed_for_core_rules(validator, valid_frontmatter):
    """`scope.framework: null` is required for language-core rules under `<lang>/_core/`."""
    ok = _mutate(valid_frontmatter, scope={"framework": None, "framework_version": _SENTINEL_DELETE})
    errors = list(validator.iter_errors(ok))
    assert errors == [], f"`framework: null` must be allowed; got: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# AC3 — every field has an inline description
# ---------------------------------------------------------------------------


def _iter_properties(schema_node, path=()):
    """Recursively yield (path, prop_name, prop_schema) for every user-facing property declaration.

    A "user-facing declaration" lives under `properties`, `items`, or `$defs.<name>`. The
    `anyOf`/`oneOf`/`allOf` keywords are constraint-encoding contexts (e.g., the `anyOf` clause
    that enforces "at least one target_tools.* must be true" re-declares property names for the
    constraint mechanism but does NOT declare new user-facing fields); their nested `properties`
    blocks are deliberately NOT walked.
    """
    if not isinstance(schema_node, dict):
        return
    if "properties" in schema_node and isinstance(schema_node["properties"], dict):
        for name, sub in schema_node["properties"].items():
            yield (path + (name,), name, sub)
            yield from _iter_properties(sub, path + (name,))
    if "$defs" in schema_node and isinstance(schema_node["$defs"], dict):
        for name, sub in schema_node["$defs"].items():
            yield from _iter_properties(sub, path + ("$defs", name))
    if "items" in schema_node and isinstance(schema_node["items"], dict):
        yield from _iter_properties(schema_node["items"], path + ("items",))


@pytest.mark.parametrize("schema_path", [
    SOURCE_RULE_SCHEMA_PATH,
    TARGET_TOOLS_SCHEMA_PATH,
])
def test_schemas_have_inline_descriptions_on_every_field(schema_path: pathlib.Path):
    """AC3: every `properties.<name>` entry in the schema files must carry a `description`.

    The audit walks `properties`, `items`, `oneOf`/`anyOf`/`allOf`, and `$defs` recursively.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    missing = []
    for path, name, sub in _iter_properties(schema):
        if not isinstance(sub, dict):
            continue
        # `$comment_*` siblings inside layer-glob-map are documentation, not properties — skip.
        if name.startswith("$"):
            continue
        if not sub.get("description"):
            missing.append("/".join(path))
    assert not missing, (
        f"{schema_path.name}: the following properties lack a `description`:\n  - "
        + "\n  - ".join(missing)
    )


def test_layer_glob_map_documents_every_language_layer():
    """AC3 for the layer-glob-map: every language has a `$comment_layers` block listing each layer."""
    doc = json.loads(LAYER_GLOB_MAP_PATH.read_text(encoding="utf-8"))
    for lang_key, lang_val in doc.items():
        if lang_key.startswith("$"):
            continue
        assert isinstance(lang_val, dict), f"{lang_key} must be an object"
        assert "$comment_layers" in lang_val, f"{lang_key} is missing `$comment_layers` block"
        documented = set(lang_val["$comment_layers"].keys())
        # Every non-`$` key under the language must have a `$comment_layers` description.
        actual_layers = {k for k in lang_val.keys() if not k.startswith("$")}
        undocumented = actual_layers - documented
        assert not undocumented, (
            f"layer-glob-map.json[{lang_key}]: layers without documentation: {sorted(undocumented)}"
        )


def test_target_tools_catalog_has_five_canonical_entries():
    """The target-tools catalog must enumerate exactly the five canonical AI-tool targets."""
    schema = json.loads(TARGET_TOOLS_SCHEMA_PATH.read_text(encoding="utf-8"))
    catalog = schema["properties"]["targets"]["const"]
    ids = [entry["id"] for entry in catalog]
    assert ids == ["cursor", "github_copilot", "claude_skills", "junie", "agents_md"], (
        f"Catalog ids drifted: {ids}"
    )
    for entry in catalog:
        assert entry["source_frontmatter_flag"] == f"target_tools.{entry['id']}"


# ---------------------------------------------------------------------------
# AC2 — CLI validator rejects a deliberately broken source file
# ---------------------------------------------------------------------------


def test_validator_cli_accepts_the_valid_example():
    """Sanity: the CLI should exit 0 when pointed at the canonical valid example."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "--validate-only", "--path", str(VALID_EXAMPLE_PATH)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"CLI returned {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "Validation PASSED" in result.stdout


def test_validator_cli_rejects_a_broken_file(tmp_path: pathlib.Path):
    """AC2: a deliberately broken source-style markdown file must be rejected non-zero by the CLI.

    This mirrors what the `.github/workflows/validate.yml` schema-validation step does on a PR
    that intentionally introduces a malformed source file.
    """
    broken = tmp_path / "broken-rule.md"
    broken.write_text(
        textwrap.dedent(
            """\
            ---
            id: Broken ID With Spaces
            title:
            version: 1.0
            status: published
            scope:
              language: java
              framework: spring-boot
              framework_version: "not-a-semver"
              layers:
                - controllers
            target_tools:
              cursor: false
              github_copilot: false
              claude_skills: false
              junie: false
              agents_md: false
            activation:
              cursor_mode: auto_attach
              agents_md_priority: critical
            ---

            # Broken rule body — should never validate.
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "--validate-only", "--path", str(broken)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 1, (
        f"CLI must exit 1 for a broken file; got {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "Validation FAILED" in result.stderr
    # The malformed file violates many constraints; spot-check several show up in stderr.
    for must_mention in ("title", "status", "layers", "framework_version", "cursor_mode", "agents_md_priority"):
        assert must_mention in result.stderr, (
            f"Expected stderr to mention {must_mention!r}; got:\n{result.stderr}"
        )


def test_validator_cli_rejects_file_without_frontmatter(tmp_path: pathlib.Path):
    """A `source/` file without any YAML frontmatter must be rejected."""
    bare = tmp_path / "no-frontmatter.md"
    bare.write_text("# Just a heading, no frontmatter at all.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "--validate-only", "--path", str(bare)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 1, (
        f"CLI must exit 1 for a frontmatter-less file; got {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "missing YAML frontmatter" in result.stderr


# ---------------------------------------------------------------------------
# AC1 — explicit positive checks against the schema's own meta-schema
# ---------------------------------------------------------------------------


def test_source_rule_schema_is_valid_draft_2020_12():
    schema = json.loads(SOURCE_RULE_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_target_tools_schema_is_valid_draft_2020_12():
    schema = json.loads(TARGET_TOOLS_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_layer_glob_map_is_valid_json():
    json.loads(LAYER_GLOB_MAP_PATH.read_text(encoding="utf-8"))
