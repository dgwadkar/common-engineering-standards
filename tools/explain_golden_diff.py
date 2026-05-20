#!/usr/bin/env python3
"""Phase-6 helper: summarize per-fixture deltas between live compiler output
and the committed `tests/golden/` trees.

Used by `make explain-golden-diff`. The full byte-level diff lives in the
pytest failure message; this helper is the human-readable per-fixture view
when the diff is large (e.g., a single source-rule edit ripples through the
~2200-line concatenated Copilot output).

Exits 0 unconditionally — this is a developer-facing reporting tool, not a
gate.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FIXTURES = [
    ("spring-boot-3-2", "java-spring-boot-3"),
    ("spring-boot-2-7-legacy", "java-spring-boot-2"),
    ("nestjs-10", "typescript-nestjs-10"),
    ("fastapi-0-110", "python-fastapi-0-110"),
]


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    print("Per-fixture delta summary (tests/golden/ vs. live compiler output):")
    print("")
    overall_drift = False
    for fixture, stack in FIXTURES:
        tmp = tempfile.mkdtemp(prefix=f"golden-explain-{fixture}-")
        compile_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "compiler",
                "--stack",
                stack,
                "--target",
                "all",
                "--out",
                tmp,
            ],
            env=env,
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if compile_proc.returncode != 0:
            print(f"[{fixture}] compiler FAILED:")
            print(compile_proc.stderr)
            overall_drift = True
            continue
        diff_proc = subprocess.run(
            ["diff", "-rq", str(REPO_ROOT / "tests" / "golden" / fixture), tmp],
            capture_output=True,
            text=True,
        )
        if diff_proc.stdout.strip():
            print(f"[{fixture}] DRIFT:")
            for line in diff_proc.stdout.splitlines():
                print(f"  {line}")
            print("")
            overall_drift = True
        else:
            print(f"[{fixture}] no drift")

    print("")
    if overall_drift:
        print("=" * 64)
        print("If the drift is intentional, refresh the golden tree:")
        print("    make update-golden")
        print("Then commit the resulting tests/golden/ diff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
