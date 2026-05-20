"""Unit tests for tools/generate_changelog.py (Phase-7).

The pure-helper layer is tested directly. The git-touching paths are exercised at a higher
level in ``tests/test_phase7_cli.py`` (also gracefully skipped under sandbox).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import generate_changelog as gc  # noqa: E402


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def test_parse_frontmatter_returns_dict_for_valid_frontmatter():
    content = "---\nid: foo-bar\ntitle: Hello\n---\n\nBody text.\n"
    parsed = gc._parse_frontmatter(content)
    assert parsed == {"id": "foo-bar", "title": "Hello"}


def test_parse_frontmatter_returns_empty_dict_when_no_frontmatter():
    assert gc._parse_frontmatter("Just a body.\n") == {}


def test_parse_frontmatter_returns_empty_dict_on_invalid_yaml():
    content = "---\nid: foo\n  : bad indentation\n---\nbody\n"
    assert gc._parse_frontmatter(content) == {}


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------


def _make_change(path, kind, rule_id="rule-x", title="Title X", deltas=()):
    return gc.RuleChange(
        path=path,
        kind=kind,
        rule_id=rule_id,
        title=title,
        frontmatter_field_deltas=tuple(deltas),
    )


def test_format_section_emits_each_subsection_present():
    changes = [
        _make_change("source/a.md", "added", "rule-a", "Title A"),
        _make_change("source/b.md", "removed", "rule-b", "Title B"),
        _make_change("source/c.md", "modified-frontmatter", "rule-c", "Title C", deltas=("scope",)),
        _make_change("source/d.md", "modified-body", "rule-d", "Title D"),
    ]
    section = gc._format_section("v2.0.0", "v1.5.0", changes)
    assert "## v2.0.0 — " in section
    assert "Changes since `v1.5.0`" in section
    assert "### Rules added" in section
    assert "### Rules removed" in section
    assert "### Rules modified (frontmatter)" in section
    assert "### Rules modified (body only)" in section
    assert "`rule-c` — Title C (changed: scope)" in section
    assert "`rule-a` — Title A" in section


def test_format_section_first_release_notes_no_previous_tag():
    section = gc._format_section("v0.1.0", None, [_make_change("source/a.md", "added", "rule-a", "Title A")])
    assert "First release — initial corpus snapshot." in section
    assert "### Rules added" in section


def test_format_section_empty_diff_emits_friendly_message():
    section = gc._format_section("v1.0.1", "v1.0.0", [])
    assert "_No source-rule changes since the previous release._" in section
    assert "compiler, schema, or template changes" in section


def test_format_section_sorts_within_each_subsection():
    changes = [
        _make_change("source/z.md", "added", "rule-z", "Z"),
        _make_change("source/a.md", "added", "rule-a", "A"),
        _make_change("source/m.md", "added", "rule-m", "M"),
    ]
    section = gc._format_section("v1.0.0", "v0.9.0", changes)
    # Paths are sorted within each subsection — rule-a appears before rule-m before rule-z.
    a_pos = section.index("`rule-a`")
    m_pos = section.index("`rule-m`")
    z_pos = section.index("`rule-z`")
    assert a_pos < m_pos < z_pos


# ---------------------------------------------------------------------------
# Splice logic
# ---------------------------------------------------------------------------


def test_splice_section_into_empty_file_prepends_header():
    section = "## v0.1.0 — 2026-05-20\n\nFirst.\n"
    result = gc._splice_section("", section)
    assert result.startswith("# Engineering Standards — Distribution Changelog")
    assert section in result


def test_splice_section_above_existing_section():
    existing = (
        "# Engineering Standards — Distribution Changelog\n"
        "\n"
        "> generated header\n"
        "\n"
        "## v1.0.0 — 2026-04-01\n"
        "\n"
        "Prior release.\n"
    )
    new = "## v1.1.0 — 2026-05-20\n\nNew release.\n"
    result = gc._splice_section(existing, new)
    # New section appears ABOVE the old.
    new_pos = result.index("## v1.1.0")
    old_pos = result.index("## v1.0.0")
    assert new_pos < old_pos
    # Header preserved.
    assert "Engineering Standards — Distribution Changelog" in result[: new_pos]


def test_splice_section_appends_when_no_prior_section_markers():
    existing = "# Title only — no prior release sections yet.\n"
    new = "## v0.1.0 — 2026-05-20\n\nFirst.\n"
    result = gc._splice_section(existing, new)
    assert result.endswith(new)
    assert "Title only" in result


# ---------------------------------------------------------------------------
# Highlighted fields catalog
# ---------------------------------------------------------------------------


def test_highlighted_fields_includes_every_critical_frontmatter_key():
    """Regression guard: if someone removes 'scope' from the highlighted catalog, the
    changelog stops surfacing scope changes — a silent loss of release-note signal."""
    for key in ("id", "title", "scope", "target_tools", "activation", "dependencies"):
        assert key in gc.HIGHLIGHTED_FIELDS
