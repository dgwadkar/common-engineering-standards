// The Node-side counterpart to `tests/test_stacks_catalog.py` — locks the contract
// that the bundled `schemas/stacks.json` catalog has the four canonical stacks and
// that every detection indicator is something the Node detector knows how to evaluate.

import { test } from "node:test";
import assert from "node:assert/strict";
import { loadCatalog, getStackById, resolveCatalogPath } from "../src/stacks-catalog.js";

const SUPPORTED_KINDS = new Set([
  "maven_parent",
  "maven_dependency",
  "gradle_plugin",
  "npm_dependency",
  "pep621_dependency",
]);

test("resolveCatalogPath finds the bundled or workspace stacks.json", () => {
  const p = resolveCatalogPath();
  assert.match(p, /stacks\.json$/);
});

test("loadCatalog returns the four canonical stacks", () => {
  const catalog = loadCatalog();
  const ids = catalog.stacks.map((s) => s.id).sort();
  assert.deepEqual(ids, [
    "java-spring-boot-2",
    "java-spring-boot-3",
    "python-fastapi-0-110",
    "typescript-nestjs-10",
  ]);
});

test("every stack has at least one indicator", () => {
  const catalog = loadCatalog();
  for (const stack of catalog.stacks) {
    assert.ok(
      stack.detection.indicators.length >= 1,
      `Stack ${stack.id} has zero indicators`,
    );
  }
});

test("every indicator uses a supported kind", () => {
  const catalog = loadCatalog();
  for (const stack of catalog.stacks) {
    for (const ind of stack.detection.indicators) {
      assert.ok(
        SUPPORTED_KINDS.has(ind.kind),
        `Stack ${stack.id} indicator kind ${ind.kind} is not supported by detect-stack.js`,
      );
    }
  }
});

test("getStackById returns the descriptor and throws on unknown id", () => {
  const catalog = loadCatalog();
  const sb3 = getStackById(catalog, "java-spring-boot-3");
  assert.equal(sb3.language, "java");
  assert.equal(sb3.framework, "spring-boot");
  assert.throws(() => getStackById(catalog, "totally-fake"), /Unknown stack id/);
});

test("the bundled stacks.json equals the workspace schemas/stacks.json (byte-for-byte)", async () => {
  const { readFileSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { fileURLToPath } = await import("node:url");
  const here = path.dirname(fileURLToPath(import.meta.url));
  const bundled = readFileSync(path.resolve(here, "..", "stacks.json"));
  const workspace = readFileSync(
    path.resolve(here, "..", "..", "..", "schemas", "stacks.json"),
  );
  assert.equal(
    bundled.toString("hex"),
    workspace.toString("hex"),
    "packages/standards-sync/stacks.json drifted from schemas/stacks.json. " +
      "Run `npm run sync-stacks-catalog` (or copy the file manually).",
  );
});
