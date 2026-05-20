# Maven integration — `@org/standards-sync`

See `../README.md` for the full rationale. This directory exists so a Java team can
land a single PR that adds the recipe verbatim.

## Quick-start

1. Ensure Node ≥20 is installed on the build agent (CI image or local dev).
2. Append the `<plugin>` block from `pom-snippet.xml` to your project's
   `pom.xml` (under `<build><plugins>`).
3. Run `mvn generate-resources` once locally; commit the resulting
   `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
   `.junie/AGENTS.md`, `.standards-sync-manifest.json`, and (if you opted in)
   `memory-bank/`.
4. Pin the standards version by dropping `v0.1.0` (or whichever tag you tested
   against) into a `.standards-version` file at the project root.

## Files in this directory

- `pom-snippet.xml` — drop-in `<plugin>` block for `pom.xml`.
- `README.md` — this file.
