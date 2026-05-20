// Parity tests for the tiny semver-range parser. Mirrors the grammar accepted by
// `compiler/core/stack_filter.py::matches_framework_version_range` so the Python compiler
// and the Node sync CLI agree on which versions match a given range string.

import { test } from "node:test";
import assert from "node:assert/strict";
import { satisfies, parseVersion } from "../src/semver-range.js";

test("parseVersion accepts 1-3 dotted parts and pads zeros", () => {
  assert.deepEqual(parseVersion("3"), [3, 0, 0]);
  assert.deepEqual(parseVersion("3.2"), [3, 2, 0]);
  assert.deepEqual(parseVersion("3.2.5"), [3, 2, 5]);
});

test("parseVersion strips a leading v and trailing pre-release/build suffix", () => {
  assert.deepEqual(parseVersion("v3.2.5"), [3, 2, 5]);
  assert.deepEqual(parseVersion("3.2.5-rc.1"), [3, 2, 5]);
  assert.deepEqual(parseVersion("3.2.5+build.7"), [3, 2, 5]);
});

test("bare and = comparators match exactly", () => {
  assert.equal(satisfies("3.2.5", "3.2.5"), true);
  assert.equal(satisfies("3.2.5", "=3.2.5"), true);
  assert.equal(satisfies("3.2.6", "=3.2.5"), false);
});

test(">=, <=, >, < behave as one-sided bounds", () => {
  assert.equal(satisfies("3.2.5", ">=3.0"), true);
  assert.equal(satisfies("3.0.0", ">=3.0"), true);
  assert.equal(satisfies("2.7.18", ">=3.0"), false);
  assert.equal(satisfies("2.7.18", "<3.0"), true);
  assert.equal(satisfies("3.0.0", "<3.0"), false);
  assert.equal(satisfies("3.0.0", "<=3.0"), true);
});

test("caret expands to same-major lower-inclusive upper-exclusive range", () => {
  assert.equal(satisfies("2.7.18", "^2.7.0"), true);
  assert.equal(satisfies("2.99.0", "^2.7.0"), true);
  assert.equal(satisfies("3.0.0", "^2.7.0"), false);
});

test("tilde expands to same-minor when 3 parts; same-major when 1 part", () => {
  assert.equal(satisfies("3.1.0", "~3.1"), true);
  assert.equal(satisfies("3.1.7", "~3.1"), true);
  assert.equal(satisfies("3.2.0", "~3.1"), false);
  // ~X is shorthand for ^X (same major)
  assert.equal(satisfies("3.7.0", "~3"), true);
  assert.equal(satisfies("4.0.0", "~3"), false);
});

test("conjunction (whitespace-separated) requires ALL primitives to match", () => {
  assert.equal(satisfies("3.2.5", ">=2.0 <4.0"), true);
  assert.equal(satisfies("4.0.0", ">=2.0 <4.0"), false);
  assert.equal(satisfies("1.9.9", ">=2.0 <4.0"), false);
});

test("empty range string matches anything (no primitives)", () => {
  assert.equal(satisfies("3.2.5", ""), true);
  assert.equal(satisfies("3.2.5", "   "), true);
});

test("unparseable tokens throw a descriptive error", () => {
  assert.throws(() => satisfies("3.2.5", "wat?"), /Unparseable range token/);
  assert.throws(() => parseVersion("not-a-version"), /Cannot parse version/);
});

test("parity with stacks.json: every indicator version_range parses", async () => {
  // Load the bundled catalog and verify every indicator's `version_range` is parseable.
  // Catches the case where someone adds a stack with a malformed range string.
  const { loadCatalog } = await import("../src/stacks-catalog.js");
  const catalog = loadCatalog();
  for (const stack of catalog.stacks) {
    for (const ind of stack.detection.indicators) {
      assert.doesNotThrow(
        () => satisfies("0.0.0", ind.version_range),
        `Stack '${stack.id}' indicator with kind=${ind.kind} has malformed version_range ${JSON.stringify(ind.version_range)}`,
      );
    }
  }
});
