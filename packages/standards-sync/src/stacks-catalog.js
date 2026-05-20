// @org/standards-sync — stacks-catalog loader.
//
// Phase 8 lesson §7-b (from the Phase-7 log): the stack catalog is the single source of
// truth shared between the Python compiler (`compiler/core/stack_filter.py`) and this Node
// CLI. The catalog file is `schemas/stacks.json` at the repository root. When this package
// is published to npm, a copy of `stacks.json` is bundled at the package root (see
// `package.json::files`); when running from the workspace, we look upward to find
// `schemas/stacks.json`. The lookup order is: bundled copy → workspace schemas dir.

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Possible catalog locations, in priority order.
const _BUNDLED_PATH = path.resolve(__dirname, "..", "stacks.json");
const _WORKSPACE_PATH = path.resolve(__dirname, "..", "..", "..", "schemas", "stacks.json");

export function resolveCatalogPath() {
  if (existsSync(_BUNDLED_PATH)) return _BUNDLED_PATH;
  if (existsSync(_WORKSPACE_PATH)) return _WORKSPACE_PATH;
  throw new Error(
    `Could not find stacks.json catalog. Looked at:\n  - ${_BUNDLED_PATH}\n  - ${_WORKSPACE_PATH}`,
  );
}

export function loadCatalog(catalogPath = resolveCatalogPath()) {
  const raw = readFileSync(catalogPath, "utf8");
  const json = JSON.parse(raw);
  // The catalog file is BOTH a JSON Schema AND the live data; the live data lives at
  // properties.stacks.const so the schema and data can be authored once.
  const stacks = json.properties?.stacks?.const;
  if (!Array.isArray(stacks) || stacks.length === 0) {
    throw new Error(
      `Malformed stacks catalog at ${catalogPath}: properties.stacks.const is missing or empty.`,
    );
  }
  return Object.freeze({
    path: catalogPath,
    stacks: Object.freeze(stacks.map((s) => Object.freeze(s))),
    byId: Object.freeze(
      Object.fromEntries(stacks.map((s) => [s.id, Object.freeze(s)])),
    ),
  });
}

export function getStackById(catalog, id) {
  const stack = catalog.byId[id];
  if (!stack) {
    throw new Error(
      `Unknown stack id: ${JSON.stringify(id)}. Known ids: ${Object.keys(catalog.byId).join(", ")}.`,
    );
  }
  return stack;
}
