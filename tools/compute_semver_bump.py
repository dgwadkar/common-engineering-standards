#!/usr/bin/env python3
"""Compute the next semver tag from Conventional Commits since the previous tag.

Phase-7 deliverable per `docs/02-implementation-plan.md` §10 task 2 step 2.

Behavior
--------

1. Reads the previous release tag (default: `git describe --tags --abbrev=0 --match 'v*'`).
2. Reads every commit subject between that tag and HEAD via `git log --format=%s%n%b%x00`.
3. Classifies each commit using Conventional Commits prefixes:

   * Any commit with a ``BREAKING CHANGE:`` footer or a ``!`` after the type/scope
     (e.g., ``feat!:`` or ``feat(api)!:``) ⇒ **major** bump.
   * ``feat:`` (or ``feat(scope):``) ⇒ **minor** bump.
   * ``fix:`` (or ``fix(scope):``) ⇒ **patch** bump.
   * Anything else (``chore:``, ``docs:``, ``refactor:``, ``test:``, ``ci:``, etc.) ⇒
     no bump on its own — but a release run with zero bump-worthy commits still emits
     ``patch`` (per the SemVer "any release is at minimum a patch" convention) unless
     ``--allow-empty`` is passed, in which case it exits 4 (no release needed).

4. Prints the next version (e.g., ``v2.4.0``) to stdout. Prints the rationale to stderr.
5. Exit codes:

   * ``0`` success — next-version printed to stdout.
   * ``1`` git error or unparseable previous tag.
   * ``2`` invocation error (unknown arg).
   * ``4`` no release needed (only if ``--allow-empty`` is passed).

Examples
--------

::

    # Inside the release workflow checkout
    $ python tools/compute_semver_bump.py
    v2.5.0

    # Override the previous tag (CI uses this when the tag fetch is incomplete).
    $ python tools/compute_semver_bump.py --previous-tag v2.4.1

    # Refuse to emit a release tag when no feat/fix/breaking commits exist.
    $ python tools/compute_semver_bump.py --allow-empty
    (exit 4, stderr: "No bump-worthy commits since v2.4.0.")

The classification logic is intentionally simple and conservative. The Phase-7 lesson:
``release.yml`` calls this once per dispatch; if the operator disagrees with the computed
bump (e.g., wants a major release for a docs-only change because it renames a rule id),
they pass ``--force-bump major`` to override.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# Conventional Commits header regex. Matches:
#   type
#   type(scope)
#   type!
#   type(scope)!
# Followed by ': '. The trailing description is captured but unused.
_HEADER_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?P<scope>\([^)]*\))?(?P<bang>!)?:\s+(?P<desc>.+)$"
)
# Footer detector for explicit BREAKING CHANGE footers.
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING(?:[ -])CHANGE:\s", re.MULTILINE)


@dataclass(frozen=True)
class CommitClassification:
    """One commit's contribution to the bump decision."""

    sha: str
    header: str
    type_: Optional[str]
    is_breaking: bool
    bump: str  # "major" | "minor" | "patch" | "none"


def _run_git(args: Sequence[str]) -> str:
    """Runs `git <args...>` and returns stdout. Raises CalledProcessError on non-zero exit."""
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _parse_version(tag: str) -> Tuple[int, int, int]:
    """Parses a ``vMAJOR.MINOR.PATCH`` tag into a 3-tuple of ints. Strips any leading ``v``."""
    cleaned = tag.lstrip("v")
    parts = cleaned.split(".")
    if len(parts) != 3:
        raise ValueError(f"Tag {tag!r} is not in vMAJOR.MINOR.PATCH form")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError as e:
        raise ValueError(f"Tag {tag!r} has non-integer parts: {e}") from e


def _classify_commit(sha: str, message: str) -> CommitClassification:
    """Classifies one commit message. The first line is the header; the rest is the body."""
    lines = message.splitlines() or [""]
    header = lines[0].strip()
    body = "\n".join(lines[1:])

    m = _HEADER_RE.match(header)
    if not m:
        # Not a Conventional Commit — contributes no bump on its own.
        return CommitClassification(
            sha=sha, header=header, type_=None, is_breaking=False, bump="none"
        )

    type_ = m.group("type").lower()
    bang = bool(m.group("bang"))
    has_breaking_footer = bool(_BREAKING_FOOTER_RE.search(message))
    is_breaking = bang or has_breaking_footer

    if is_breaking:
        bump = "major"
    elif type_ == "feat":
        bump = "minor"
    elif type_ == "fix":
        bump = "patch"
    else:
        bump = "none"

    return CommitClassification(
        sha=sha, header=header, type_=type_, is_breaking=is_breaking, bump=bump
    )


def _classify_range(previous_tag: Optional[str]) -> List[CommitClassification]:
    """Returns a classification for every commit in ``previous_tag..HEAD``."""
    if previous_tag:
        rev_range = f"{previous_tag}..HEAD"
    else:
        rev_range = "HEAD"

    # Use a NUL-byte separator so multi-line commit bodies cannot collide with the
    # delimiter. Each record begins with the abbreviated SHA, then a tab, then the
    # full subject+body.
    log_format = "%H%x09%B%x00"
    try:
        raw = _run_git(["log", f"--format={log_format}", rev_range])
    except subprocess.CalledProcessError as e:
        # An invalid range (e.g., previous_tag doesn't exist) lands here. Re-raise with a
        # clearer error message; the CLI maps it to exit code 1.
        raise RuntimeError(
            f"`git log {rev_range}` failed: {e.stderr.strip() or e.stdout.strip()}"
        ) from e

    records = [r for r in raw.split("\x00") if r.strip()]
    classifications: List[CommitClassification] = []
    for record in records:
        sha, _, message = record.partition("\t")
        classifications.append(_classify_commit(sha.strip(), message.strip()))
    return classifications


def _highest_bump(classifications: Sequence[CommitClassification]) -> str:
    """Returns ``major`` > ``minor`` > ``patch`` > ``none``."""
    order = {"major": 3, "minor": 2, "patch": 1, "none": 0}
    if not classifications:
        return "none"
    return max((c.bump for c in classifications), key=lambda b: order[b])


def _apply_bump(previous: Tuple[int, int, int], bump: str) -> Tuple[int, int, int]:
    major, minor, patch = previous
    if bump == "major":
        return (major + 1, 0, 0)
    if bump == "minor":
        return (major, minor + 1, 0)
    if bump == "patch":
        return (major, minor, patch + 1)
    # "none" keeps the version unchanged (caller decides whether to emit a release).
    return previous


def _latest_tag() -> Optional[str]:
    """Returns the most recent ``v*`` tag reachable from HEAD, or None if no tag exists."""
    try:
        out = _run_git(["describe", "--tags", "--abbrev=0", "--match", "v*"]).strip()
    except subprocess.CalledProcessError:
        return None
    return out or None


def _make_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="compute_semver_bump.py",
        description=(
            "Compute the next semver tag from Conventional Commits since the previous "
            "tag. Used by the Phase-7 release workflow (docs/02-implementation-plan.md "
            "§10 task 2 step 2)."
        ),
    )
    ap.add_argument(
        "--previous-tag",
        default=None,
        help=(
            "Override the previous release tag. Default: the most recent v* tag reachable "
            "from HEAD via `git describe`. Pass `--previous-tag none` to indicate this is "
            "the first release (the initial tag will be v0.1.0)."
        ),
    )
    ap.add_argument(
        "--force-bump",
        choices=("major", "minor", "patch"),
        default=None,
        help=(
            "Force a specific bump level regardless of the computed classification. Used "
            "by operators who want to override the auto-classification."
        ),
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help=(
            "When set, exit 4 (no release needed) if no feat/fix/BREAKING-CHANGE commits "
            "exist since the previous tag. Default: emit a patch bump anyway."
        ),
    )
    ap.add_argument(
        "--print-rationale",
        action="store_true",
        help="Print the per-commit classification breakdown to stderr for audit purposes.",
    )
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _make_arg_parser().parse_args(argv)

    previous_tag_arg = args.previous_tag
    if previous_tag_arg == "none":
        previous_tag: Optional[str] = None
    elif previous_tag_arg is None:
        previous_tag = _latest_tag()
    else:
        previous_tag = previous_tag_arg

    if previous_tag is None:
        previous = (0, 0, 0)
        print("No previous v* tag found; treating this as the first release.", file=sys.stderr)
    else:
        try:
            previous = _parse_version(previous_tag)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Previous tag: {previous_tag} (parsed as {previous}).", file=sys.stderr)

    try:
        classifications = _classify_range(previous_tag)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.force_bump:
        chosen = args.force_bump
        print(
            f"Force-bump requested via --force-bump {args.force_bump}; "
            f"ignoring auto-classification.",
            file=sys.stderr,
        )
    else:
        chosen = _highest_bump(classifications)

    if args.print_rationale:
        print(f"Classified {len(classifications)} commit(s) since {previous_tag or 'root'}:", file=sys.stderr)
        for c in classifications:
            print(f"  {c.sha[:8]} {c.bump:<6} {c.header}", file=sys.stderr)

    if chosen == "none":
        if args.allow_empty:
            print(
                f"No bump-worthy commits since {previous_tag or 'the root commit'}.",
                file=sys.stderr,
            )
            return 4
        chosen = "patch"
        print(
            "No feat/fix/BREAKING-CHANGE commits found; defaulting to patch bump.",
            file=sys.stderr,
        )

    if previous_tag is None and chosen != "major":
        # First-release convention: a brand-new project starts at v0.1.0 regardless of
        # commit signals (until somebody intentionally tags v1.0.0).
        next_version = (0, 1, 0)
        print(
            f"First release: starting at v0.1.0 (commits would have suggested {chosen}).",
            file=sys.stderr,
        )
    else:
        next_version = _apply_bump(previous, chosen)
        print(f"Selected bump: {chosen} ⇒ v{next_version[0]}.{next_version[1]}.{next_version[2]}.", file=sys.stderr)

    print(f"v{next_version[0]}.{next_version[1]}.{next_version[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
