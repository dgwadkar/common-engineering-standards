# ArchUnit Fixtures — Phase 6 Deliverable

Hand-authored ArchUnit JUnit-5 test fixtures that codify the four canonical
Logic Holes from the Architecture Upgrade Report. Phase 8's
`@org/standards-sync` CLI ships these tests into consumer projects under
`src/test/java/com/_org/standards/archunit/`; this directory is the source
of truth.

## File Index

| File | Logic Hole | Source rule |
|---|---|---|
| `ControllerValidationTest.java` | #3 — controller validation | `source/java/spring-boot/controller/validation-boundaries.md` |
| `TransactionalDisciplineTest.java` | #4 — transactional discipline | `source/java/spring-boot/service/transactional-boundaries.md` (+ self-invocation, readonly) |
| `PaginationMandateTest.java` | #5 — pagination mandate | `source/java/spring-boot/repository/findall-pagination-mandate.md` |
| `ConstructorInjectionTest.java` | #6 — constructor injection | `source/java/spring-boot/di/constructor-injection-mandate.md` |

## Why This Directory Is Java Source, Not Compiled Artifacts

Per ADR-0004 (single-repo distribution), the four files in this directory
are **the** source for the ArchUnit fixtures. Phase 7's `release.yml`
copies them verbatim into `dist/stacks/java-spring-boot-3/archunit/` (no
transformation), and Phase 8's consumer-sync CLI fans them out to consumer
projects.

The Phase-2 schema's `archunit_test:` field on each source rule references
the destination filename here so the rule corpus and these fixtures stay
in lock-step.

## Manual Verification Procedure (AC1)

The Phase-6 acceptance criterion AC1 reads:

> All four ArchUnit tests, when copied into a sample Spring Boot 3
> project containing one deliberate violation each, fail with the
> expected violation message.

Runtime verification requires a JDK 17 + Maven environment (not present
in the Python-only CI surface that Phase 6 extends). The procedure is:

1. **Provision a sample Spring Boot 3 project** — any greenfield Boot 3.2
   project with `archunit-junit5` (`com.tngtech.archunit:archunit-junit5:1.3.0+`)
   on the test classpath.
2. **Copy each test file** from this directory into the consumer's
   `src/test/java/com/_org/standards/archunit/`.
3. **Confirm clean code passes**: `mvn test` against the project with no
   deliberate violations passes all four tests.
4. **Introduce one deliberate violation per test** (see the docstring at the
   top of each `*.java` file for the exact violation pattern):
   - For `ControllerValidationTest`: a `@RestController` method declaring
     `@RequestBody UserCreateRequest req` without `@Valid`.
   - For `TransactionalDisciplineTest`: a `@Service` method that calls
     `RestTemplate.getForObject(...)` inside a `@Transactional` block.
   - For `PaginationMandateTest`: a repository declaring
     `List<Order> findByCustomerId(Long id)` (unbounded).
   - For `ConstructorInjectionTest`: a `@Service` field annotated
     `@Autowired private OrderRepository repo;`.
5. **Confirm each test now fails with the expected message** (each
   docstring at the top of the test file lists the exact violation message
   string).

This procedure is the operator's PR-close action for the Phase-6 closing
PR. Phase 9's pilot adoption is the natural ongoing-CI venue for this
runtime check (each pilot's CI runs `mvn test`, and a deliberate-violation
PR there proves the fixture works in production conditions).

## Why the Shape-Only Python Test Is Not the Whole Story

`tests/test_archunit_fixtures.py` parses each `.java` file as text and
asserts the presence of:

- The `@AnalyzeClasses(packages = "com._org", ...)` annotation.
- The expected `@ArchTest`-annotated `ArchRule` declarations.
- The expected violation message strings (so consumer-side assertions
  can `grep` them in CI logs).

This is **shape verification, not behavior verification.** The bytecode
analysis itself only runs when ArchUnit is on the classpath in a Java
test runtime. Phase 6's Python CI does NOT execute these tests; it
guarantees only that they compile structurally and that the canonical
violation messages are present. AC1's runtime verification is the
operator's manual step (or Phase 9's pilot CI).
