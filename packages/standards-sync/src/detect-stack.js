// @org/standards-sync — stack detection (Plan §11 task 1).
//
// Reads the consumer's project root and returns:
//   {
//     stackId,                  // e.g., "java-spring-boot-3"
//     detectedVersion,          // e.g., "3.2.5" (raw from the manifest, when extractable)
//     manifestFile,             // e.g., "pom.xml"
//     rationale,                // human-readable string explaining WHY this stack matched
//     candidatesConsidered,     // array of {stackId, reason} for stacks evaluated but skipped
//   }
//
// OR — when nothing matches — a sentinel:
//   { stackId: null, manifestFile: null, rationale: "...", candidatesConsidered: [...] }
//
// The detector evaluates stacks in catalog order; the FIRST stack whose `detection.indicators`
// all match the manifest wins. Each indicator's `kind` corresponds to a parser below:
//
//   maven_parent         — <project><parent><groupId>X</groupId><artifactId>Y</artifactId><version>Z</version>
//   maven_dependency     — <dependency> in <dependencies>
//   gradle_plugin        — id("X") version "Y" in build.gradle.kts plugins {} block
//   npm_dependency       — entries in package.json `dependencies` / `devDependencies` / `peerDependencies`
//   pep621_dependency    — entries in pyproject.toml `[project].dependencies` list

import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { satisfies } from "./semver-range.js";

// ---------- helpers (XML / TOML / Gradle parsers) -----------------------------------------

function readIfExists(file) {
  try {
    return existsSync(file) ? readFileSync(file, "utf8") : null;
  } catch {
    return null;
  }
}

// Naive but adequate Maven parent reader: we look for the first <parent>...</parent> block
// and pull groupId/artifactId/version out of it. Spring Boot's `spring-boot-starter-parent`
// is always the top-level parent in practice, so a single-pass extraction is correct.
function readMavenParent(pomXml) {
  const parent = pomXml.match(/<parent\b[\s\S]*?<\/parent>/);
  if (!parent) return null;
  const block = parent[0];
  const groupId = block.match(/<groupId>\s*([^<]+?)\s*<\/groupId>/)?.[1];
  const artifactId = block.match(/<artifactId>\s*([^<]+?)\s*<\/artifactId>/)?.[1];
  const version = block.match(/<version>\s*([^<]+?)\s*<\/version>/)?.[1];
  if (!groupId || !artifactId) return null;
  return { groupId, artifactId, version };
}

// Returns all <dependency> entries (groupId, artifactId, version may be undefined).
function readMavenDependencies(pomXml) {
  const out = [];
  const re = /<dependency\b[\s\S]*?<\/dependency>/g;
  let m;
  while ((m = re.exec(pomXml)) !== null) {
    const block = m[0];
    const groupId = block.match(/<groupId>\s*([^<]+?)\s*<\/groupId>/)?.[1];
    const artifactId = block.match(/<artifactId>\s*([^<]+?)\s*<\/artifactId>/)?.[1];
    const version = block.match(/<version>\s*([^<]+?)\s*<\/version>/)?.[1];
    if (groupId && artifactId) out.push({ groupId, artifactId, version });
  }
  return out;
}

// Extracts `id("foo") version "1.2.3"` and `id 'foo' version '1.2.3'` entries from the
// plugins {} block of a Gradle (Groovy or Kotlin DSL) file. Returns an array of {pluginId, version}.
function readGradlePlugins(buildScript) {
  const out = [];
  const re = /id\s*[(]?\s*['"]([^'"]+)['"]\s*[)]?\s*version\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(buildScript)) !== null) {
    out.push({ pluginId: m[1], version: m[2] });
  }
  return out;
}

// Returns a flat {packageName: versionSpec} map merging dependencies + devDependencies +
// peerDependencies + optionalDependencies. NestJS lives in `dependencies` typically.
function readNpmDependencies(packageJsonText) {
  let pkg;
  try {
    pkg = JSON.parse(packageJsonText);
  } catch {
    return {};
  }
  return {
    ...(pkg.dependencies || {}),
    ...(pkg.devDependencies || {}),
    ...(pkg.peerDependencies || {}),
    ...(pkg.optionalDependencies || {}),
  };
}

// Strips a leading `^`, `~`, `>=`, etc. plus pre-release noise from an npm or PEP-621 spec
// to recover a base version we can test against an indicator's `version_range`.
function _normalizeVersionSpec(spec) {
  if (!spec) return null;
  const m = String(spec).match(/(\d+(?:\.\d+){0,2})/);
  return m ? m[1] : null;
}

// Returns an array of {packageName, versionSpec} pairs from pyproject.toml's
// `[project].dependencies = [...]` list. The parser is a tiny line-based reader sufficient
// for PEP-621 dependency strings — we DO NOT pull in a full TOML library.
function readPep621Dependencies(pyprojectText) {
  const out = [];
  const lines = pyprojectText.split(/\r?\n/);
  let inProject = false;
  let inDepsList = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("[")) {
      inProject = line === "[project]";
      inDepsList = false;
      continue;
    }
    if (!inProject) continue;
    if (line.startsWith("dependencies")) {
      // Either inline (`dependencies = ["fastapi>=0.110.0"]`) or block form.
      const inline = line.match(/dependencies\s*=\s*\[(.*)\]\s*$/);
      if (inline) {
        for (const tok of inline[1].split(",")) {
          const m = tok.trim().match(/^["']([^"']+)["']/);
          if (m) out.push(parseDependencyToken(m[1]));
        }
      } else if (/dependencies\s*=\s*\[/.test(line)) {
        inDepsList = true;
      }
      continue;
    }
    if (inDepsList) {
      if (line.startsWith("]")) {
        inDepsList = false;
        continue;
      }
      const m = line.match(/^["']([^"']+)["']/);
      if (m) out.push(parseDependencyToken(m[1]));
    }
  }
  return out;
}

// Parse "fastapi>=0.110.0,<0.111.0" → {packageName: "fastapi", versionSpec: ">=0.110.0,<0.111.0"}
function parseDependencyToken(token) {
  const m = token.match(/^([A-Za-z0-9_.-]+)\s*(\[[^\]]+\])?\s*([<>=!~^]+.*)?$/);
  if (!m) return { packageName: token, versionSpec: null };
  return {
    packageName: m[1],
    versionSpec: m[3] ? m[3].trim().replace(/,/g, " ") : null,
  };
}

// ---------- indicator evaluators ----------------------------------------------------------

function evalMavenParent(indicator, manifest) {
  if (manifest.kind !== "pom") return false;
  const parent = manifest.parent;
  if (!parent) return false;
  if (parent.groupId !== indicator.group_id) return false;
  if (parent.artifactId !== indicator.artifact_id) return false;
  if (!parent.version) return false;
  return satisfies(parent.version, indicator.version_range);
}

function evalMavenDependency(indicator, manifest) {
  if (manifest.kind !== "pom") return false;
  for (const dep of manifest.dependencies) {
    if (dep.groupId !== indicator.group_id) continue;
    if (indicator.artifact_id && dep.artifactId !== indicator.artifact_id) continue;
    if (
      indicator.artifact_id_prefix &&
      !dep.artifactId.startsWith(indicator.artifact_id_prefix)
    ) {
      continue;
    }
    if (!dep.version) {
      // Spring Boot starter dependencies usually omit <version> because they inherit from
      // the parent BOM. Treat "version-from-parent" as a match ONLY when the parent's
      // recorded version satisfies the indicator's range. Without this check the SB3
      // dependency indicator would incorrectly fire on an SB2 fixture (whose starter
      // dependencies also omit <version>) — see Phase-8 detect-stack tests.
      const parent = manifest.parent;
      if (!parent || !parent.version) continue;
      if (parent.groupId !== indicator.group_id) continue;
      if (satisfies(parent.version, indicator.version_range)) return true;
      continue;
    }
    if (satisfies(dep.version, indicator.version_range)) return true;
  }
  return false;
}

function evalGradlePlugin(indicator, manifest) {
  if (manifest.kind !== "gradle") return false;
  for (const p of manifest.plugins) {
    if (p.pluginId !== indicator.plugin_id) continue;
    if (satisfies(p.version, indicator.version_range)) return true;
  }
  return false;
}

function evalNpmDependency(indicator, manifest) {
  if (manifest.kind !== "package-json") return false;
  const spec = manifest.dependencies[indicator.package_name];
  if (!spec) return false;
  const base = _normalizeVersionSpec(spec);
  if (!base) return false;
  return satisfies(base, indicator.version_range);
}

function evalPep621Dependency(indicator, manifest) {
  if (manifest.kind !== "pyproject") return false;
  for (const dep of manifest.dependencies) {
    if (dep.packageName !== indicator.package_name) continue;
    const base = _normalizeVersionSpec(dep.versionSpec);
    if (!base) return false;
    return satisfies(base, indicator.version_range);
  }
  return false;
}

const INDICATOR_EVALUATORS = {
  maven_parent: evalMavenParent,
  maven_dependency: evalMavenDependency,
  gradle_plugin: evalGradlePlugin,
  npm_dependency: evalNpmDependency,
  pep621_dependency: evalPep621Dependency,
};

// ---------- public API --------------------------------------------------------------------

// Load each manifest file the catalog might care about from `projectDir`, returning a
// `{filename: parsedManifest}` map. We parse lazily but cache to avoid re-reading.
export function loadProjectManifests(projectDir) {
  const map = {};
  const pomPath = path.join(projectDir, "pom.xml");
  const pomXml = readIfExists(pomPath);
  if (pomXml !== null) {
    map["pom.xml"] = {
      kind: "pom",
      file: pomPath,
      parent: readMavenParent(pomXml),
      dependencies: readMavenDependencies(pomXml),
    };
  }
  for (const gradleName of ["build.gradle.kts", "build.gradle"]) {
    const p = path.join(projectDir, gradleName);
    const src = readIfExists(p);
    if (src !== null) {
      map[gradleName] = {
        kind: "gradle",
        file: p,
        plugins: readGradlePlugins(src),
      };
    }
  }
  const pkgPath = path.join(projectDir, "package.json");
  const pkgText = readIfExists(pkgPath);
  if (pkgText !== null) {
    map["package.json"] = {
      kind: "package-json",
      file: pkgPath,
      dependencies: readNpmDependencies(pkgText),
    };
  }
  const pyPath = path.join(projectDir, "pyproject.toml");
  const pyText = readIfExists(pyPath);
  if (pyText !== null) {
    map["pyproject.toml"] = {
      kind: "pyproject",
      file: pyPath,
      dependencies: readPep621Dependencies(pyText),
    };
  }
  return map;
}

// Evaluate every stack in catalog order; return the first that matches.
//
// "Match" semantics:
//   * Iterate each stack's `detection.indicators` in order.
//   * The stack matches if AT LEAST ONE indicator evaluates true against the manifests
//     present in the project. (The catalog lists indicators most-specific-first; once one
//     wins, the stack is locked.)
//   * If multiple stacks claim the same project (e.g., a Maven project also has a
//     package.json for frontend tooling), the first stack in catalog order wins. The
//     `candidatesConsidered` array surfaces the also-rans so users can debug surprises.
export function detectStack({ projectDir, catalog }) {
  const manifests = loadProjectManifests(projectDir);
  const presentManifests = Object.keys(manifests);
  const candidatesConsidered = [];

  for (const stack of catalog.stacks) {
    const acceptableFiles = stack.detection.manifest_files;
    const intersect = presentManifests.filter((m) => acceptableFiles.includes(m));
    if (intersect.length === 0) {
      candidatesConsidered.push({
        stackId: stack.id,
        reason: `No matching manifest file (looked for: ${acceptableFiles.join(", ")})`,
      });
      continue;
    }
    let matchingIndicator = null;
    for (const ind of stack.detection.indicators) {
      const evaluator = INDICATOR_EVALUATORS[ind.kind];
      if (!evaluator) {
        candidatesConsidered.push({
          stackId: stack.id,
          reason: `Unsupported indicator kind: ${ind.kind}`,
        });
        continue;
      }
      for (const filename of intersect) {
        if (evaluator(ind, manifests[filename])) {
          matchingIndicator = { ind, filename };
          break;
        }
      }
      if (matchingIndicator) break;
    }
    if (matchingIndicator) {
      const { ind, filename } = matchingIndicator;
      const manifest = manifests[filename];
      const detectedVersion = _extractDetectedVersion(manifest, ind);
      return {
        stackId: stack.id,
        detectedVersion,
        manifestFile: filename,
        rationale:
          `Stack '${stack.id}' selected from ${filename}: matched indicator ` +
          `kind=${ind.kind} ${_describeIndicator(ind)}.`,
        candidatesConsidered,
      };
    }
    candidatesConsidered.push({
      stackId: stack.id,
      reason:
        `Manifest ${intersect.join(", ")} present but no indicator matched ` +
        `(checked ${stack.detection.indicators.length} indicator${stack.detection.indicators.length === 1 ? "" : "s"}).`,
    });
  }

  return {
    stackId: null,
    detectedVersion: null,
    manifestFile: null,
    rationale: _buildNoMatchRationale(presentManifests, candidatesConsidered),
    candidatesConsidered,
  };
}

function _extractDetectedVersion(manifest, indicator) {
  if (manifest.kind === "pom" && indicator.kind === "maven_parent") {
    return manifest.parent?.version || null;
  }
  if (manifest.kind === "pom" && indicator.kind === "maven_dependency") {
    for (const dep of manifest.dependencies) {
      if (dep.groupId !== indicator.group_id) continue;
      if (indicator.artifact_id && dep.artifactId !== indicator.artifact_id) continue;
      if (
        indicator.artifact_id_prefix &&
        !dep.artifactId.startsWith(indicator.artifact_id_prefix)
      ) {
        continue;
      }
      if (dep.version) return dep.version;
    }
    return null;
  }
  if (manifest.kind === "gradle" && indicator.kind === "gradle_plugin") {
    return manifest.plugins.find((p) => p.pluginId === indicator.plugin_id)?.version || null;
  }
  if (manifest.kind === "package-json" && indicator.kind === "npm_dependency") {
    return manifest.dependencies[indicator.package_name] || null;
  }
  if (manifest.kind === "pyproject" && indicator.kind === "pep621_dependency") {
    const dep = manifest.dependencies.find((d) => d.packageName === indicator.package_name);
    return dep?.versionSpec || null;
  }
  return null;
}

function _describeIndicator(ind) {
  if (ind.kind === "maven_parent") {
    return `${ind.group_id}:${ind.artifact_id} version ${ind.version_range}`;
  }
  if (ind.kind === "maven_dependency") {
    const aid = ind.artifact_id || `${ind.artifact_id_prefix}*`;
    return `${ind.group_id}:${aid} version ${ind.version_range}`;
  }
  if (ind.kind === "gradle_plugin") {
    return `plugin '${ind.plugin_id}' version ${ind.version_range}`;
  }
  if (ind.kind === "npm_dependency") {
    return `npm package '${ind.package_name}' version ${ind.version_range}`;
  }
  if (ind.kind === "pep621_dependency") {
    return `pypi package '${ind.package_name}' version ${ind.version_range}`;
  }
  return JSON.stringify(ind);
}

function _buildNoMatchRationale(presentManifests, candidates) {
  if (presentManifests.length === 0) {
    return (
      "No applicable stack found: project root contains none of the manifest files we " +
      "recognise (pom.xml, build.gradle.kts, build.gradle, package.json, pyproject.toml)."
    );
  }
  const lines = [
    `No applicable stack found. Manifests present: ${presentManifests.join(", ")}.`,
  ];
  for (const c of candidates) {
    lines.push(`  - ${c.stackId}: ${c.reason}`);
  }
  return lines.join("\n");
}
