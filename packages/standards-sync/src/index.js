// @org/standards-sync — main entrypoint.
//
// `sync()` orchestrates the six Phase-8 tasks end-to-end. It returns a structured result so
// tests can inspect every decision; `runCli()` (in cli.js) wraps it with commander, argv
// parsing, and process-exit semantics.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadCatalog } from "./stacks-catalog.js";
import { detectStack } from "./detect-stack.js";
import { resolveVersion, DEFAULT_REPO } from "./version-resolver.js";
import { locateDistTree } from "./dist-fetcher.js";
import { planPlacements, applyPlacements } from "./placement.js";
import {
  classifyPlacements,
  planShas,
  writeManifest,
  readManifest,
  ManualEditConflictError,
} from "./idempotency.js";
import {
  renderSyncReport,
  summarisePlacements,
  findUnmatchedGlobs,
} from "./sync-report.js";
import { createLogger } from "./logger.js";

export const NO_APPLICABLE_STACK_EXIT_CODE = 0; // AC3: graceful exit, not an error

export const SYNC_OUTCOMES = Object.freeze({
  Synced: "synced",
  SyncedNoChanges: "synced-no-changes",
  ManualEditsBlocked: "manual-edits-blocked",
  NoApplicableStack: "no-applicable-stack",
  DryRun: "dry-run",
});

export async function sync(options = {}) {
  const {
    projectDir = process.cwd(),
    version: explicitVersion = null,
    localDist = null,
    repo = DEFAULT_REPO,
    withMemoryBank = false,
    force = false,
    dryRun = false,
    quiet = false,
    writeReport = false,
    reportPath = null,
    fetchImpl = globalThis.fetch,
    logger = createLogger({ level: quiet ? "warn" : "info" }),
    catalog = loadCatalog(),
  } = options;

  const generatedAt = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

  // ---------- Task 1: stack detection ----------------------------------------------------
  const detection = detectStack({ projectDir, catalog });
  logger.info(detection.rationale.split("\n")[0]);
  if (!detection.stackId) {
    // AC3: clear "no applicable stack found" and exit 0 (not an error).
    const reportState = {
      generatedAt,
      projectDir,
      stackId: null,
      detectedVersion: null,
      manifestFile: null,
      version: null,
      versionSource: "n/a",
      distSource: "n/a",
      dryRun,
      detectionRationale: detection.rationale,
      summary: [],
      skippedRules: [],
      unmatchedGlobs: [],
      conflicts: [],
    };
    return {
      outcome: SYNC_OUTCOMES.NoApplicableStack,
      detection,
      report: renderSyncReport({
        ...reportState,
        stackId: "(none)",
      }),
      exitCode: NO_APPLICABLE_STACK_EXIT_CODE,
    };
  }

  // ---------- Task 2: version resolution -------------------------------------------------
  // Skip when --local-dist is set; the local tree has no version concept.
  let version, versionSource;
  if (localDist) {
    version = explicitVersion || "(local-dist)";
    versionSource = "local-dist";
  } else {
    const resolved = await resolveVersion({
      projectDir,
      explicitVersion,
      repo,
      fetchImpl,
      logger,
    });
    version = resolved.version;
    versionSource = resolved.source;
  }

  // ---------- Task 2 (cont.): locate dist tree -------------------------------------------
  const { distRoot, stackRoot, cleanup } = await locateDistTree({
    localDist,
    repo,
    version,
    stackId: detection.stackId,
    fetchImpl,
    logger,
  });

  let outcome = SYNC_OUTCOMES.Synced;
  try {
    // ---------- Task 3: file placement plan ---------------------------------------------
    const { placements, skipped } = planPlacements({
      stackRoot,
      projectDir,
      options: { withMemoryBank },
    });
    logger.info(`Planned placements: ${placements.length} file(s) across ${new Set(placements.map((p) => p.ruleId)).size} rule group(s).`);

    // ---------- Task 4: idempotency / manual-edit detection -----------------------------
    const plannedShas = planShas(placements);
    const manifest = readManifest(projectDir);
    const classification = classifyPlacements(placements, {
      projectDir,
      manifest,
      plannedShas,
    });

    if (classification.conflicts.length > 0 && !force) {
      logger.warn(
        `${classification.conflicts.length} file(s) have manual edits since the last sync. Aborting (re-run with --force to overwrite).`,
      );
      const summary = summarisePlacements({ placements, classification });
      const unmatchedGlobs = findUnmatchedGlobs({ projectDir, stackRoot });
      const report = renderSyncReport({
        generatedAt,
        projectDir,
        stackId: detection.stackId,
        detectedVersion: detection.detectedVersion,
        manifestFile: detection.manifestFile,
        version,
        versionSource,
        distSource: localDist ? `local-dist=${localDist}` : `github ${repo}@${version}`,
        dryRun,
        detectionRationale: detection.rationale,
        summary,
        skippedRules: skipped,
        unmatchedGlobs,
        conflicts: classification.conflicts,
      });
      if (writeReport) await _writeReport(projectDir, reportPath, report);
      return {
        outcome: SYNC_OUTCOMES.ManualEditsBlocked,
        detection,
        version,
        versionSource,
        conflicts: classification.conflicts,
        report,
        exitCode: 0, // soft refusal — operator chooses next move
      };
    }

    // ---------- Apply / dry-run ---------------------------------------------------------
    const isNoOp =
      classification.identical.length === placements.length &&
      classification.conflicts.length === 0 &&
      classification.wouldAdd.length === 0 &&
      classification.wouldChange.length === 0;

    const applied = await applyPlacements(placements, { dryRun, logger });
    logger.success(
      dryRun
        ? `(dry-run) Would write ${applied.length} file(s) under ${projectDir}.`
        : `Wrote ${applied.length} file(s) under ${projectDir}.`,
    );

    if (!dryRun) {
      // AC2 contract: a re-sync at the same version must produce zero `git diff`. If every
      // planned file is byte-identical to disk AND the manifest already records the same
      // (version, files) shape, we skip the manifest rewrite to keep the on-disk
      // `syncedAt` field stable. Any real change (add, modify, version bump) rewrites the
      // manifest so the audit trail stays accurate.
      const manifestStillCurrent =
        isNoOp &&
        manifest &&
        manifest.syncedVersion === version &&
        manifest.stackId === detection.stackId &&
        Object.keys(manifest.files || {}).length === placements.length;
      if (!manifestStillCurrent) {
        await writeManifest({
          projectDir,
          version,
          stackId: detection.stackId,
          placements,
          plannedShas,
        });
        logger.info(
          `Manifest updated: ${path.join(projectDir, ".standards-sync-manifest.json")}`,
        );
      } else {
        logger.info("Manifest already current — skipped re-write to keep `git diff` empty.");
      }
    }

    if (isNoOp) outcome = SYNC_OUTCOMES.SyncedNoChanges;
    if (dryRun) outcome = SYNC_OUTCOMES.DryRun;

    // ---------- Task 5: sync report -----------------------------------------------------
    const summary = summarisePlacements({ placements, classification });
    const unmatchedGlobs = findUnmatchedGlobs({ projectDir, stackRoot });
    const report = renderSyncReport({
      generatedAt,
      projectDir,
      stackId: detection.stackId,
      detectedVersion: detection.detectedVersion,
      manifestFile: detection.manifestFile,
      version,
      versionSource,
      distSource: localDist ? `local-dist=${localDist}` : `github ${repo}@${version}`,
      dryRun,
      detectionRationale: detection.rationale,
      summary,
      skippedRules: skipped,
      unmatchedGlobs,
      conflicts: [],
    });
    if (writeReport) await _writeReport(projectDir, reportPath, report);

    return {
      outcome,
      detection,
      version,
      versionSource,
      placements,
      applied,
      classification,
      report,
      exitCode: 0,
    };
  } finally {
    await cleanup();
  }
}

async function _writeReport(projectDir, reportPath, content) {
  const targetPath = reportPath || path.join(projectDir, "standards-sync-report.md");
  await mkdir(path.dirname(targetPath), { recursive: true });
  await writeFile(targetPath, content, "utf8");
}

// Re-export selected primitives so adopters can compose them in their own scripts.
export {
  detectStack,
  resolveVersion,
  loadCatalog,
  planPlacements,
  applyPlacements,
  classifyPlacements,
  planShas,
  writeManifest,
  readManifest,
  renderSyncReport,
  ManualEditConflictError,
  DEFAULT_REPO,
};
