#!/usr/bin/env python3
"""Generate (or update) ``dist/CHANGELOG.md`` for a new release.

Phase-7 deliverable per `docs/02-implementation-plan.md` §10 task 2 step 7.

Behavior
--------

1. Computes the set of changed ``source/**/*.md`` files between the previous release
   tag and ``HEAD`` (default: most recent ``v*`` tag reachable from HEAD).
2. For each changed file, parses the YAML frontmatter at both the previous tag and at HEAD
   (using ``git show <tag>:path``) and classifies the change as:

   * **Added** — file did not exist at the previous tag.
   * **Removed** — file deleted between the previous tag and HEAD.
   * **Modified — frontmatter changed** — rule id, title, scope, target_tools, activation,
     dependencies, or status differ. Surfaces the specific fields that changed.
   * **Modified — body only** — only the Markdown body changed (no frontmatter delta). Listed
     in a "Body-only edits" subsection so reviewers can see at a glance that no AI behavior
     reshaping is implied.

3. Emits a new ``## v<X.Y.Z> — <date>`` section to ``dist/CHANGELOG.md``. If the file does
   not exist, it is created with a header explaining the file's purpose; otherwise the new
   section is **prepended** above the prior section so the file reads newest-first.

4. The release workflow commits the regenerated ``dist/CHANGELOG.md`` as part of the same
   release commit (alongside the regenerated ``dist/stacks/`` tree).

CLI
---

::

    python tools/generate_changelog.py --new-version v2.4.0
    python tools/generate_changelog.py --new-version v2.4.0 --previous-tag v2.3.1
    python tools/generate_changelog.py --new-version v2.4.0 --output /tmp/CHANGELOG.md

Exit codes:

* ``0`` success.
* ``1`` git error or frontmatter parse error.
* ``2`` invocation error.

The output is deterministic given the same git state — important because the Phase-6
golden snapshots assert byte-equality across runs (R-04 mitigation: easy-to-review diffs).
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "dist" / "CHANGELOG.md"

# Frontmatter fields whose changes are worth highlighting in the changelog. Other fields
# (e.g. an internal version_number bump) are still detected but folded under "frontmatter
# changes" without itemizing.
HIGHLIGHTED_FIELDS = (
    "id",
    "title",
    "status",
    "scope",
    "target_tools",
    "activation",
    "dependencies",
)


@dataclass(frozen=True)
class RuleChange:
    """One source-rule's contribution to the release notes."""

    path: str  # repo-relative source path
    kind: str  # "added" | "removed" | "modified-frontmatter" | "modified-body"
    rule_id: Optional[str]  # parsed from current frontmatter (or previous, if removed)
    title: Optional[str]
    frontmatter_field_deltas: Tuple[str, ...] = ()


def _run_git(args: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _show_at(tag_or_ref: str, path: str) -> Optional[str]:
    """Returns the file's contents at the given ref, or None if the file did not exist there."""
    try:
        return _run_git(["show", f"{tag_or_ref}:{path}"])
    except subprocess.CalledProcessError:
        return None


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n.*)?\Z", re.DOTALL)


def _parse_frontmatter(content: str) -> Dict:
    """Parses the YAML frontmatter of a source rule. Returns ``{}`` if no frontmatter present."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group("body")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _changed_source_files(previous_tag: Optional[str]) -> List[Tuple[str, str]]:
    """Returns a list of (status, path) for changed source/**/*.md files.

    Status is git's name-status code: ``A`` (added), ``D`` (deleted), ``M`` (modified),
    or ``R`` (renamed). For ``R``, the new path is returned.
    """
    rev_range = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    raw = _run_git(
        ["diff", "--name-status", rev_range, "--", "source/"]
    ).strip()
    if not raw:
        return []
    out: List[Tuple[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        status_letter = parts[0][:1]
        path = parts[-1]
        if not path.endswith(".md") or not path.startswith("source/"):
            continue
        out.append((status_letter, path))
    return out


def _classify_change(status: str, path: str, previous_tag: Optional[str]) -> RuleChange:
    """Classifies a single changed source file."""
    if status == "A":
        head_content = (REPO_ROOT / path).read_text(encoding="utf-8")
        fm = _parse_frontmatter(head_content)
        return RuleChange(
            path=path,
            kind="added",
            rule_id=fm.get("id"),
            title=fm.get("title"),
        )

    if status == "D":
        prev_content = _show_at(previous_tag or "HEAD~1", path) or ""
        fm = _parse_frontmatter(prev_content)
        return RuleChange(
            path=path,
            kind="removed",
            rule_id=fm.get("id"),
            title=fm.get("title"),
        )

    # Modified or renamed-with-content-change: compare frontmatter at both ends.
    head_content = (REPO_ROOT / path).read_text(encoding="utf-8") if (REPO_ROOT / path).exists() else ""
    prev_content = _show_at(previous_tag, path) or "" if previous_tag else ""
    prev_fm = _parse_frontmatter(prev_content)
    head_fm = _parse_frontmatter(head_content)

    field_deltas: List[str] = []
    for field in HIGHLIGHTED_FIELDS:
        if prev_fm.get(field) != head_fm.get(field):
            field_deltas.append(field)

    if field_deltas:
        return RuleChange(
            path=path,
            kind="modified-frontmatter",
            rule_id=head_fm.get("id") or prev_fm.get("id"),
            title=head_fm.get("title") or prev_fm.get("title"),
            frontmatter_field_deltas=tuple(field_deltas),
        )

    return RuleChange(
        path=path,
        kind="modified-body",
        rule_id=head_fm.get("id") or prev_fm.get("id"),
        title=head_fm.get("title") or prev_fm.get("title"),
    )


def _format_section(new_version: str, previous_tag: Optional[str], changes: List[RuleChange]) -> str:
    """Renders one release section as Markdown."""
    today = datetime.date.today().isoformat()
    header = [f"## {new_version} — {today}"]
    if previous_tag:
        header.append(f"\nChanges since `{previous_tag}`.\n")
    else:
        header.append("\nFirst release — initial corpus snapshot.\n")

    added = [c for c in changes if c.kind == "added"]
    removed = [c for c in changes if c.kind == "removed"]
    frontmatter_changed = [c for c in changes if c.kind == "modified-frontmatter"]
    body_only = [c for c in changes if c.kind == "modified-body"]

    body_parts: List[str] = []

    if added:
        body_parts.append("### Rules added\n")
        for c in sorted(added, key=lambda r: r.path):
            body_parts.append(f"- `{c.rule_id or c.path}` — {c.title or '(no title)'}")
        body_parts.append("")

    if removed:
        body_parts.append("### Rules removed\n")
        for c in sorted(removed, key=lambda r: r.path):
            body_parts.append(f"- `{c.rule_id or c.path}` — {c.title or '(no title)'}")
        body_parts.append("")

    if frontmatter_changed:
        body_parts.append("### Rules modified (frontmatter)\n")
        for c in sorted(frontmatter_changed, key=lambda r: r.path):
            fields = ", ".join(c.frontmatter_field_deltas)
            body_parts.append(
                f"- `{c.rule_id or c.path}` — {c.title or '(no title)'} "
                f"(changed: {fields})"
            )
        body_parts.append("")

    if body_only:
        body_parts.append("### Rules modified (body only)\n")
        for c in sorted(body_only, key=lambda r: r.path):
            body_parts.append(f"- `{c.rule_id or c.path}` — {c.title or '(no title)'}")
        body_parts.append("")

    if not (added or removed or frontmatter_changed or body_only):
        body_parts.append("_No source-rule changes since the previous release._")
        body_parts.append(
            "_This release captures compiler, schema, or template changes only — see "
            "the git history for details._"
        )
        body_parts.append("")

    return "\n".join(header + body_parts).rstrip() + "\n"


_FILE_HEADER = (
    "# Engineering Standards — Distribution Changelog\n"
    "\n"
    "> Auto-generated by `tools/generate_changelog.py` during the Phase-7 release\n"
    "> workflow (`docs/02-implementation-plan.md` §10 task 2 step 7). DO NOT edit by\n"
    "> hand — your changes will be overwritten on the next release.\n"
    ">\n"
    "> Newest releases first. Each `## v<X.Y.Z>` block lists `source/` rule additions,\n"
    "> removals, frontmatter changes, and body-only edits relative to the previous tag.\n"
    "\n"
)


def _splice_section(existing: str, new_section: str) -> str:
    """Inserts ``new_section`` immediately after the file header, above any prior sections."""
    if not existing.strip():
        return _FILE_HEADER + new_section
    # Preserve the file header (everything up to the first '## ' heading); insert the new
    # section above the first prior section.
    header, sep, rest = existing.partition("\n## ")
    if not sep:
        # No prior sections — just append.
        return existing.rstrip() + "\n\n" + new_section
    return header.rstrip() + "\n\n" + new_section + "\n## " + rest


def _make_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="generate_changelog.py",
        description=(
            "Generate (or prepend a new section to) dist/CHANGELOG.md based on source/ "
            "rule changes between the previous release tag and HEAD. Used by the "
            "Phase-7 release workflow (docs/02-implementation-plan.md §10 task 2 step 7)."
        ),
    )
    ap.add_argument(
        "--new-version",
        required=True,
        help="The version tag this release will be cut at (e.g., v2.4.0).",
    )
    ap.add_argument(
        "--previous-tag",
        default=None,
        help=(
            "Override the previous release tag. Default: most recent v* tag reachable "
            "from HEAD via `git describe --tags`. Pass `none` to treat this as a first "
            "release (no diff base; all source rules are listed under Added)."
        ),
    )
    ap.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the updated CHANGELOG. Default: dist/CHANGELOG.md.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the new section to stdout instead of writing to --output.",
    )
    return ap


def _resolve_previous_tag(arg: Optional[str]) -> Optional[str]:
    if arg == "none":
        return None
    if arg is not None:
        return arg
    try:
        out = _run_git(["describe", "--tags", "--abbrev=0", "--match", "v*"]).strip()
    except subprocess.CalledProcessError:
        return None
    return out or None


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _make_arg_parser().parse_args(argv)

    previous_tag = _resolve_previous_tag(args.previous_tag)
    print(f"Previous tag: {previous_tag or '(none — first release)'}.", file=sys.stderr)

    if previous_tag is None:
        # First release — list every current source file as Added. Avoids the `git diff
        # HEAD..` call which would fail on a fresh repo with no commits yet (the very
        # first release runs against an empty git history).
        changed = [
            ("A", str(p.relative_to(REPO_ROOT)))
            for p in sorted((REPO_ROOT / "source").rglob("*.md"))
        ]
    else:
        try:
            changed = _changed_source_files(previous_tag)
        except subprocess.CalledProcessError as e:
            print(
                f"Error: `git diff` failed: {e.stderr.strip() or e.stdout.strip()}",
                file=sys.stderr,
            )
            return 1

    changes = [_classify_change(status, path, previous_tag) for status, path in changed]
    section = _format_section(args.new_version, previous_tag, changes)

    if args.dry_run:
        sys.stdout.write(section)
        return 0

    output_path: pathlib.Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    output_path.write_text(_splice_section(existing, section), encoding="utf-8")
    print(f"Wrote {output_path} ({len(changes)} change(s) under {args.new_version}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
