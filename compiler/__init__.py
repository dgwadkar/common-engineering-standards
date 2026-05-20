"""Engineering standards compiler package.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7. This package contains:

* ``compiler.core.parse_source``    — frontmatter parser + ``SourceRule`` dataclass + ``parse_all``.
* ``compiler.core.resolve_globs``   — language+layers → globs (via ``schemas/layer-glob-map.json``).
* ``compiler.core.build_graph``     — dependency-DAG construction, cycle detection, topo sort.
* ``compiler.core.stack_filter``    — filters rules to a target stack (semver-range matching).
* ``compiler.core.logging_setup``   — structured JSON-line logger used by every compiler module.
* ``compiler.transformers.cursor_mdc`` — Cursor MDC emitter (one ``.mdc`` per applicable rule).
* ``compiler.__main__``             — CLI entry point: ``python -m compiler --stack ... --target cursor --out ...``.

Phase 5 (`docs/02-implementation-plan.md` §8) will add the remaining four transformers
(Copilot, Claude, Junie, AGENTS.md) plus the Memory Bank scaffold under
``compiler.transformers``. Phase 6 (§9) adds golden-snapshot fixtures under ``fixtures/``
and ArchUnit test fixtures under ``testing/archunit/``.
"""
