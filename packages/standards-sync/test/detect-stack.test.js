// Stack-detection tests (Plan §11 task 1).
//
// Exercises the detector against every Phase-6 fixture under `fixtures/` plus a synthetic
// "Ruby on Rails" project (a Gemfile-only project) that none of the indicators should
// match — that is the AC3 path.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

import { detectStack } from "../src/detect-stack.js";
import { loadCatalog } from "../src/stacks-catalog.js";
import {
  copyFixtureManifest,
  mkTempProject,
  rmDir,
  FILE_TMP_ROOT,
  ensureTmpRoot,
} from "./_helpers.js";

const CATALOG = loadCatalog();

before(() => ensureTmpRoot());
after(() => rmDir(FILE_TMP_ROOT));

test("spring-boot-3-2 fixture → java-spring-boot-3", () => {
  const project = mkTempProject("detect-sb3");
  copyFixtureManifest("spring-boot-3-2", project);
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "java-spring-boot-3");
  assert.equal(result.manifestFile, "pom.xml");
  assert.match(result.rationale, /matched indicator kind=maven_parent/);
  assert.equal(result.detectedVersion, "3.2.5");
});

test("spring-boot-2-7-legacy fixture → java-spring-boot-2", () => {
  const project = mkTempProject("detect-sb2");
  copyFixtureManifest("spring-boot-2-7-legacy", project);
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "java-spring-boot-2");
  assert.equal(result.manifestFile, "pom.xml");
  assert.equal(result.detectedVersion, "2.7.18");
});

test("nestjs-10 fixture → typescript-nestjs-10", () => {
  const project = mkTempProject("detect-nest");
  copyFixtureManifest("nestjs-10", project);
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "typescript-nestjs-10");
  assert.equal(result.manifestFile, "package.json");
  assert.match(result.rationale, /matched indicator kind=npm_dependency/);
});

test("fastapi-0-110 fixture → python-fastapi-0-110", () => {
  const project = mkTempProject("detect-fastapi");
  copyFixtureManifest("fastapi-0-110", project);
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "python-fastapi-0-110");
  assert.equal(result.manifestFile, "pyproject.toml");
  assert.match(result.rationale, /matched indicator kind=pep621_dependency/);
});

test("a Rails-only project (Gemfile) returns stackId=null with a clear rationale (AC3)", () => {
  const project = mkTempProject("detect-rails");
  writeFileSync(
    path.join(project, "Gemfile"),
    'source "https://rubygems.org"\ngem "rails", "~> 7.0"\n',
  );
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, null);
  assert.equal(result.manifestFile, null);
  assert.match(result.rationale, /No applicable stack found/);
  assert.match(result.rationale, /pom\.xml.*package\.json.*pyproject\.toml/);
});

test("a Maven project with a non-Boot parent returns stackId=null with per-stack reasons", () => {
  const project = mkTempProject("detect-non-boot");
  writeFileSync(
    path.join(project, "pom.xml"),
    `<?xml version="1.0"?>
<project>
  <parent>
    <groupId>org.apache.maven</groupId>
    <artifactId>maven-parent</artifactId>
    <version>40</version>
  </parent>
</project>`,
  );
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, null);
  assert.match(result.rationale, /No applicable stack found/);
  // Both Spring Boot stacks should be in candidatesConsidered with a "no indicator matched" reason.
  const sb3 = result.candidatesConsidered.find((c) => c.stackId === "java-spring-boot-3");
  const sb2 = result.candidatesConsidered.find((c) => c.stackId === "java-spring-boot-2");
  assert.ok(sb3, "java-spring-boot-3 should be in candidatesConsidered");
  assert.ok(sb2, "java-spring-boot-2 should be in candidatesConsidered");
  assert.match(sb3.reason, /no indicator matched/);
});

test("a Spring Boot 3 build.gradle.kts is also recognised as java-spring-boot-3", () => {
  const project = mkTempProject("detect-gradle-sb3");
  writeFileSync(
    path.join(project, "build.gradle.kts"),
    `plugins {
  id("org.springframework.boot") version "3.2.5"
  id("io.spring.dependency-management") version "1.1.4"
}
`,
  );
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "java-spring-boot-3");
  assert.equal(result.manifestFile, "build.gradle.kts");
  assert.match(result.rationale, /matched indicator kind=gradle_plugin/);
});

test("when both pom.xml and package.json exist, the first catalog-order match wins", () => {
  // Mirrors the case where a Spring Boot service has a frontend `package.json` for
  // dev tooling — the Java stack must win because it appears first in the catalog.
  const project = mkTempProject("detect-poly");
  copyFixtureManifest("spring-boot-3-2", project);
  writeFileSync(
    path.join(project, "package.json"),
    JSON.stringify({
      name: "frontend-tooling",
      dependencies: { "@nestjs/core": "^10.3.0" },
    }),
  );
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, "java-spring-boot-3");
});

test("an empty project (no manifest) returns the friendly no-manifest rationale", () => {
  const project = mkTempProject("detect-empty");
  mkdirSync(project, { recursive: true });
  const result = detectStack({ projectDir: project, catalog: CATALOG });
  assert.equal(result.stackId, null);
  assert.match(result.rationale, /contains none of the manifest files we recognise/);
});
