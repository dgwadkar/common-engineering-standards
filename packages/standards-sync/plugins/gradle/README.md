# Gradle integration — `@org/standards-sync`

See `../README.md` for the full rationale. This directory exists so a Java/Kotlin team
can land a single PR that adds the recipe verbatim.

## Quick-start

1. Ensure Node ≥20 is installed on the build agent (CI image or local dev).
2. Append the snippet from `build.gradle.kts.snippet` (Kotlin DSL) or
   `build.gradle.snippet` (Groovy DSL) to your project's build script.
3. Run `./gradlew syncEngineeringStandards` once locally; commit the resulting
   `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
   `.junie/AGENTS.md`, `.standards-sync-manifest.json`, and (if you opted in)
   `memory-bank/`.
4. Pin the standards version by dropping `v0.1.0` (or whichever tag you tested
   against) into a `.standards-version` file at the project root.

## Files in this directory

- `build.gradle.kts.snippet` — drop-in Kotlin DSL block.
- `build.gradle.snippet` — drop-in Groovy DSL block.
- `README.md` — this file.
