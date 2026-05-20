// @org/standards-sync — argv parsing & process wiring (the bin/ shim delegates here).
//
// The CLI surface is intentionally small:
//
//   standards-sync [options]
//     --project-dir <path>     consumer project root (default: cwd)
//     --version <tag>          explicit version override (skips .standards-version + GH API)
//     --local-dist <path>      use a local dist/ tree instead of downloading from GitHub
//     --repo <owner/name>      GitHub repo holding the dist tree (default: engineering-standards-central/engineering-standards-central)
//     --with-memory-bank       also copy the Memory Bank scaffold (opt-in)
//     --force                  overwrite manually-edited files (default: refuse + report)
//     --dry-run                plan and report; do not write any files
//     --quiet                  suppress info-level logs (warn/error still print)
//     --write-report [path]    write the sync report to <path> (default: ./standards-sync-report.md)
//
// Exit codes:
//   0 — success (synced, no-op, dry-run, no-applicable-stack, OR manual edits blocked)
//   1 — unexpected error (network failure, malformed manifest, etc.)
//
// AC3: a "no-applicable-stack" outcome is exit 0 — by design, since the absence of an
// applicable stack is a valid outcome (e.g., a Ruby project) and should not break CI.

import { Command, Option } from "commander";
import { sync, SYNC_OUTCOMES, DEFAULT_REPO } from "./index.js";
import { createLogger } from "./logger.js";

export function buildProgram() {
  const program = new Command();
  program
    .name("standards-sync")
    .description(
      "Sync the Engineering Standards distribution into the current project. " +
        "Detects your stack, resolves a pinned or floating version, and copies the matching " +
        "dist/stacks/<stack>/ subtree into the conventional consumer locations.",
    )
    .version("0.1.0", "-V, --print-version", "Print the CLI version and exit")
    .option("--project-dir <path>", "Consumer project root", process.cwd())
    .option("--version <tag>", "Explicit version (e.g., v0.2.0); overrides .standards-version and the GitHub API")
    .option("--local-dist <path>", "Use a local dist/ tree instead of downloading from GitHub (for testing or air-gapped use)")
    .option("--repo <owner/name>", "GitHub repo hosting the dist tree", DEFAULT_REPO)
    .option("--with-memory-bank", "Also copy the Memory Bank scaffold (opt-in)", false)
    .option("--force", "Overwrite manually-edited files (default: refuse and report conflicts)", false)
    .option("--dry-run", "Plan and report; do not write any files", false)
    .option("--quiet", "Suppress info-level logs (warn/error still print)", false)
    .addOption(
      new Option(
        "--write-report [path]",
        "Write the sync report to <path> (default: ./standards-sync-report.md)",
      ).default(false),
    );
  return program;
}

export async function runCli(argv = process.argv) {
  const program = buildProgram();
  program.parse(argv);
  const opts = program.opts();

  const logger = createLogger({ level: opts.quiet ? "warn" : "info" });

  let result;
  try {
    result = await sync({
      projectDir: opts.projectDir,
      version: opts.version,
      localDist: opts.localDist,
      repo: opts.repo,
      withMemoryBank: opts.withMemoryBank,
      force: opts.force,
      dryRun: opts.dryRun,
      quiet: opts.quiet,
      writeReport: !!opts.writeReport,
      reportPath: typeof opts.writeReport === "string" ? opts.writeReport : null,
      logger,
    });
  } catch (err) {
    logger.error(err.message);
    if (err.hint) logger.error(`Hint: ${err.hint}`);
    return 1;
  }

  // Print the report to stdout regardless of outcome — it's the operator-visible artifact.
  process.stdout.write(result.report);
  if (!result.report.endsWith("\n")) process.stdout.write("\n");

  if (result.outcome === SYNC_OUTCOMES.NoApplicableStack) {
    logger.info("No applicable stack found — nothing to sync. See report above.");
  } else if (result.outcome === SYNC_OUTCOMES.ManualEditsBlocked) {
    logger.warn(
      "Sync aborted: manual edits detected (see Manual-edit conflicts section). " +
        "Re-run with --force to overwrite.",
    );
  } else if (result.outcome === SYNC_OUTCOMES.DryRun) {
    logger.info("Dry-run complete — no files written.");
  } else if (result.outcome === SYNC_OUTCOMES.SyncedNoChanges) {
    logger.success("Sync complete — every file was already up to date (zero git diff).");
  } else {
    logger.success("Sync complete.");
  }
  return result.exitCode || 0;
}
