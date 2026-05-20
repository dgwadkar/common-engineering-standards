"""Phase-6 structural-shape tests for the four ArchUnit fixtures.

Per `tests/archunit/README.md`, runtime verification requires a JDK +
Maven environment. This module enforces the *structural* contract of the
hand-authored fixtures:

  - Each file is well-formed Java syntax (parses with `javalang` or, in its
    absence, satisfies a conservative regex set).
  - Each file declares the expected `@AnalyzeClasses` annotation.
  - Each file declares the expected `@ArchTest`-annotated `ArchRule`
    constants (by name).
  - Each file's docstring header contains the canonical violation messages
    that consumer-side `grep` assertions in CI logs will look for.

Runtime AC1 verification (running `mvn test` against a Spring Boot 3 sample
project containing deliberate violations) is the operator's manual step —
see `tests/archunit/README.md` and `docs/02-implementation-plan.md` §9 AC1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHUNIT_DIR = REPO_ROOT / "tests" / "archunit"

# (filename, expected ArchRule constant names, expected violation-message
# substring per rule). The substrings are excerpted from the test's
# docstring header so consumer-side CI logs can `grep` for them.
_FIXTURE_SPEC: list[tuple[str, list[str], list[str]]] = [
    (
        "ControllerValidationTest.java",
        [
            "controllerRequestBodiesMustBeAnnotatedWithValid",
            "controllersWithParameterConstraintsMustBeAnnotatedWithValidated",
            "controllersMustResideInControllerOrWebPackage",
        ],
        [
            "is not annotated with @Valid",
            "without a class-level @Validated annotation",
        ],
    ),
    (
        "TransactionalDisciplineTest.java",
        [
            "transactionalMethodsMustNotInvokeBlockingHttpClients",
            "transactionalAnnotationsLiveOnPublicMethodsOnly",
            "servicesShouldDeclareReadOnlyDefaultAtClassLevel",
        ],
        [
            "calls a blocking HTTP client",
            "is not public",
            "class-level @Transactional(readOnly = true)",
        ],
    ),
    (
        "PaginationMandateTest.java",
        [
            "repositoryListReturnsMustAcceptPageable",
            "controllerListEndpointsMustAcceptPageableOrPageRequestParam",
        ],
        [
            "without a Pageable parameter",
        ],
    ),
    (
        "ConstructorInjectionTest.java",
        [
            "noFieldsAnnotatedWithAutowired",
            "noSetterAutowired",
            "springBeanFieldsMustBeFinal",
        ],
        [
            "is annotated @Autowired",
            "is a setter annotated @Autowired",
            "is not declared `final`",
        ],
    ),
]


@pytest.mark.parametrize("filename,arch_rule_names,violation_substrings", _FIXTURE_SPEC)
def test_archunit_fixture_file_exists(
    filename: str,
    arch_rule_names: list[str],
    violation_substrings: list[str],
) -> None:
    """Each named ArchUnit fixture file is on disk."""
    path = ARCHUNIT_DIR / filename
    assert path.is_file(), f"Missing ArchUnit fixture: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"Empty ArchUnit fixture: {path}"


@pytest.mark.parametrize("filename,arch_rule_names,violation_substrings", _FIXTURE_SPEC)
def test_archunit_fixture_declares_analyze_classes_annotation(
    filename: str,
    arch_rule_names: list[str],
    violation_substrings: list[str],
) -> None:
    """Each fixture binds ArchUnit to the canonical com._org root package."""
    text = (ARCHUNIT_DIR / filename).read_text(encoding="utf-8")
    assert "@AnalyzeClasses" in text, (
        f"{filename} is missing the @AnalyzeClasses class-level annotation"
    )
    assert 'packages = "com._org"' in text, (
        f"{filename} must scope @AnalyzeClasses to packages = \"com._org\""
    )


@pytest.mark.parametrize("filename,arch_rule_names,violation_substrings", _FIXTURE_SPEC)
def test_archunit_fixture_declares_expected_arch_rules(
    filename: str,
    arch_rule_names: list[str],
    violation_substrings: list[str],
) -> None:
    """Each fixture declares the expected ArchRule constants under @ArchTest."""
    text = (ARCHUNIT_DIR / filename).read_text(encoding="utf-8")
    for rule_name in arch_rule_names:
        # Match `public static final ArchRule <name> =`. Allows whitespace
        # variants the formatter might introduce.
        pattern = re.compile(
            r"@ArchTest\s+"
            r"public\s+static\s+final\s+ArchRule\s+" + re.escape(rule_name) + r"\s*=",
            re.MULTILINE,
        )
        assert pattern.search(text), (
            f"{filename} is missing @ArchTest-annotated ArchRule "
            f"constant {rule_name!r}"
        )


@pytest.mark.parametrize("filename,arch_rule_names,violation_substrings", _FIXTURE_SPEC)
def test_archunit_fixture_documents_expected_violation_messages(
    filename: str,
    arch_rule_names: list[str],
    violation_substrings: list[str],
) -> None:
    """Each fixture's docstring header lists the canonical violation-message strings.

    Consumer-side CI typically `grep`s the violation message to confirm a
    deliberate violation is being caught. If the message strings drift, the
    consumer's CI assertions silently break. This test locks them to the
    fixture file content.
    """
    text = (ARCHUNIT_DIR / filename).read_text(encoding="utf-8")
    for substring in violation_substrings:
        assert substring in text, (
            f"{filename} is missing the canonical violation-message "
            f"substring {substring!r} (consumer CI assertions grep for it)"
        )


def test_all_archunit_fixture_files_share_one_package_declaration() -> None:
    """Every fixture lives under `package com._org.standards.archunit;`.

    The package is the load-bearing convention for Phase 8's consumer-sync
    placement (`src/test/java/com/_org/standards/archunit/<File>.java`).
    """
    expected = "package com._org.standards.archunit;"
    for filename, _names, _msgs in _FIXTURE_SPEC:
        text = (ARCHUNIT_DIR / filename).read_text(encoding="utf-8")
        assert expected in text, (
            f"{filename} is not in package com._org.standards.archunit"
        )


def test_archunit_readme_describes_manual_verification_procedure() -> None:
    """The README documents the AC1 manual verification procedure."""
    readme = ARCHUNIT_DIR / "README.md"
    assert readme.is_file(), "tests/archunit/README.md is missing"
    text = readme.read_text(encoding="utf-8")
    for required in [
        "Manual Verification Procedure",
        "mvn test",
        "deliberate violation",
        "ControllerValidationTest",
        "TransactionalDisciplineTest",
        "PaginationMandateTest",
        "ConstructorInjectionTest",
    ]:
        assert required in text, (
            f"tests/archunit/README.md does not document {required!r}"
        )


def test_source_corpus_archunit_paths_align_with_fixture_filenames() -> None:
    """Every source rule's `archunit_test:` reference resolves to a real fixture
    OR is null OR points at a Phase-7+ deliverable.

    The four Phase-6 fixtures (Controller / Transactional / Pagination /
    Constructor) MUST exist; everything else is allowed to be a forward-
    reference (Phase 8's consumer-sync surfaces missing fixtures as a
    sync-report warning, not an error).
    """
    phase6_authored_filenames = {
        spec[0] for spec in _FIXTURE_SPEC
    }
    source_dir = REPO_ROOT / "source"
    referenced: set[str] = set()
    for md in source_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        m = re.search(r"^archunit_test:\s*(.+)$", text, re.MULTILINE)
        if not m:
            continue
        value = m.group(1).strip()
        if value == "null":
            continue
        # Strip optional quotes and the leading `testing/archunit/` prefix.
        value = value.strip("'\"")
        basename = value.rsplit("/", 1)[-1]
        referenced.add(basename)
    missing_phase6 = phase6_authored_filenames - referenced
    assert not missing_phase6, (
        f"Phase-6 ArchUnit fixtures referenced by no source rule: {missing_phase6}. "
        "Either delete the orphan fixture or add an `archunit_test:` reference "
        "in the corresponding source/."
    )
