# `@org/standards-sync` — Maven / Gradle integration recipes

> Plan §11 task 6 — *optional* JVM-side wrappers.
>
> **No new build plugin is shipped.** This directory holds **copy-pastable recipes** that
> bind the existing Node CLI to a JVM build phase (Maven `generate-resources` or Gradle
> task) without adding a second supply chain.

## Why no native plugin?

We considered a true Maven `MOJO` / Gradle `Plugin<Project>` (see ADR-0004 §3 alternatives).
The Node CLI is the **single supply chain** for sync logic — manifest parsing, version
resolution, idempotency, conflict detection, and the report. A native JVM plugin would
either:

1. **Re-implement the entire detection + placement pipeline in Java/Kotlin** — direct
   violation of the "single source of truth" principle (Plan §1) and a guaranteed
   drift target.
2. **Shell out to the Node CLI** — which is exactly what the recipes below already do,
   minus the install/maintenance burden of a second package.

If a future pilot team requires `mvn` / `gradle` to fully drive the sync (no `npx` in
their pipeline), we re-evaluate. Until then, the recipes are the integration.

The recipes use `npx --yes @org/standards-sync@<version>` so the Node CLI is fetched
on demand — JVM teams do not maintain a global Node install or commit a
`package.json`; only Node ≥20 on the build agent is required.

## Recipe 1 — Maven (`exec-maven-plugin`)

Drop the following into `pom.xml` under `<build><plugins>`. The plugin binds the
sync to the `generate-resources` phase so the standards land before compilation
(useful when an ArchUnit rule under `src/test/java/com/_org/standards/` references
the synced classes).

<!-- The literal `<` chars below are inside a code block so Markdown renderers won't
     interpret them as HTML; do NOT escape them. -->

```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>exec-maven-plugin</artifactId>
  <version>3.5.0</version>
  <executions>
    <execution>
      <id>sync-engineering-standards</id>
      <phase>generate-resources</phase>
      <goals><goal>exec</goal></goals>
      <configuration>
        <executable>npx</executable>
        <arguments>
          <argument>--yes</argument>
          <argument>@org/standards-sync@0.1.0</argument>
          <argument>--project-dir</argument>
          <argument>${project.basedir}</argument>
        </arguments>
        <!-- Fail the build if the sync surfaces manual-edit conflicts. -->
        <successCodes><successCode>0</successCode></successCodes>
      </configuration>
    </execution>
  </executions>
</plugin>
```

Pin the standards version explicitly via `<argument>--version</argument>` or — more
commonly — drop a `.standards-version` file at the repo root containing the tag
(e.g., `v0.1.0`). The CLI reads it automatically (Plan §11 task 2, pinned mode).

To run only on demand: change `<phase>generate-resources</phase>` to
`<phase>none</phase>` and invoke with `mvn exec:exec@sync-engineering-standards`.

## Recipe 2 — Gradle (Groovy DSL)

Add the following to `build.gradle`. The task is registered eagerly so it shows up in
`gradle tasks --group standards`; we wire it as a dependency of `processResources`
so the standards arrive before any test-source compilation that may consume them.

```groovy
tasks.register('syncEngineeringStandards', Exec) {
    group = 'standards'
    description = 'Sync the org engineering standards via @org/standards-sync (Plan §11).'
    executable 'npx'
    args '--yes', '@org/standards-sync@0.1.0', '--project-dir', projectDir.absolutePath
    // Treat manual-edit conflicts as a build failure.
    standardOutput = new ByteArrayOutputStream()
    errorOutput = new ByteArrayOutputStream()
    ignoreExitValue = false
}

tasks.named('processResources').configure { dependsOn 'syncEngineeringStandards' }
```

## Recipe 3 — Gradle (Kotlin DSL)

```kotlin
tasks.register<Exec>("syncEngineeringStandards") {
    group = "standards"
    description = "Sync the org engineering standards via @org/standards-sync (Plan §11)."
    executable = "npx"
    args(
        "--yes",
        "@org/standards-sync@0.1.0",
        "--project-dir",
        projectDir.absolutePath,
    )
    isIgnoreExitValue = false
}

tasks.named("processResources").configure { dependsOn("syncEngineeringStandards") }
```

## Pinning the version

All three recipes hard-code `@0.1.0` for reproducibility. Two recommended bump patterns:

| Pattern | When to use | How to bump |
|---|---|---|
| Drop a `.standards-version` file at repo root containing `v0.2.0` | The most common case — the CLI reads the file every run, so consumers stay on whatever the file says without editing `pom.xml` / `build.gradle.kts` | Renovate/Dependabot-style bot can `sed` the file; reviewers see a one-line diff |
| Edit the version in the recipe (`@org/standards-sync@0.2.0`) | When the CLI itself ships a breaking flag rename | Edit `pom.xml` / `build.gradle.kts`; commit alongside any flag changes |

The CLI's `--version` flag (and `.standards-version`) refers to the *standards corpus*
version (the `v<X.Y.Z>` tag in `engineering-standards-central`), which is decoupled from
the npm package version of `@org/standards-sync`. The two should be bumped together
during a coordinated standards release but are independent at install time.

## CI smoke test

We recommend adding a CI job that runs `mvn validate` (or `gradle help`) and then
verifies the sync produced zero diff vs the committed `.cursor/rules/`, `AGENTS.md`,
etc. The Node CLI emits exit code 0 + a `--write-report` Markdown that CI can attach
as an artifact for review.

```bash
# .github/workflows/standards-drift.yml (excerpt)
- run: npx --yes @org/standards-sync@0.1.0 --project-dir . --write-report sync-report.md
- run: |
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "::error::Engineering standards are out of sync. Run \`npx @org/standards-sync\` locally and commit the result."
      git status --porcelain
      exit 1
    fi
```

This converts AC2 ("two consecutive runs produce zero diff") into a permanent CI
guard for the consumer repository.
