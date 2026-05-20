"""Per-tool transformers.

Each module under this package takes a filtered list of ``SourceRule`` instances plus a
``Stack`` descriptor and produces a tree of output files for one downstream tool.

* ``cursor_mdc``              — Phase 4. Cursor MDC (``.cursor/rules/*.mdc``).
* ``copilot_instructions``    — Phase 5. GitHub Copilot (``.github/copilot-instructions.md``).
* ``claude_md``               — Phase 5. Claude Code (``CLAUDE.md``).
* ``junie_agents_md``         — Phase 5. JetBrains Junie (``.junie/AGENTS.md``).
* ``universal_agents_md``     — Phase 5. Universal cross-tool baseline (``AGENTS.md``, ≤150 lines).
* ``memory_bank_scaffold``    — Phase 5. Six-file Memory Bank scaffold under ``memory-bank/``.

Each transformer ships a pure ``render_*(rules, stack)`` function (no I/O, deterministic output
for Phase-6 golden snapshots) plus a side-effecting ``emit_for_stack(rules, stack, *, dist_root,
logger=None)`` that writes the files and returns a list of typed ``EmittedFile`` records.
"""
