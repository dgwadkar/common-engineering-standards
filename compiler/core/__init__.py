"""Compiler core modules.

The four pure-data modules in this subpackage have no transformer-specific knowledge — they
turn the on-disk corpus into the typed graph the transformers consume:

* ``parse_source``  — frontmatter + Markdown body → ``SourceRule`` dataclass list.
* ``resolve_globs`` — ``(language, layers)`` → globs array (via ``schemas/layer-glob-map.json``).
* ``build_graph``   — ``[SourceRule]`` → ``RuleGraph`` (with topo sort and cycle detection).
* ``stack_filter``  — ``[SourceRule] × Stack`` → the subset shipped to that stack.
* ``logging_setup`` — structured JSON-line logger shared by every compiler module.
"""
