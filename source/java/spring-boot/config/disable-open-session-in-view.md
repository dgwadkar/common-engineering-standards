---
id: java-spring-config-disable-open-session-in-view
title: Disable Open-Session-In-View
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers:
    - config
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: auto-attach
  agents_md_priority: high
dependencies:
  - java-spring-repository-n-plus-one-prevention
related_logic_holes: [4]
archunit_test: testing/archunit/DisableOpenSessionInViewTest.java
---

# Disable Open-Session-In-View

## 1. Context & Architectural Intent

Open-Session-In-View (OSIV) is a Spring Boot feature enabled by default since Boot 2.0. It holds
the Hibernate session open for the entire HTTP request — including the JSON serialization phase
— so that lazy-loaded fields can be accessed without throwing `LazyInitializationException`.
This is **convenient and dangerous**: convenient because tutorial-grade code "just works";
dangerous because it hides N+1 selects, holds DB connections for the entire response
serialization window, and produces application-level pathologies (slow JSON renders correlated
with DB connection-pool saturation) that look like network issues.

This rule mandates `spring.jpa.open-in-view: false` in every `application.yml`. It is reinforced
by the JetBrains Junie official Spring Boot guidelines (item #9, "Disable Open-Session-in-View")
and is the operational complement to `n-plus-one-prevention.md`. When OSIV is off, the
controller-layer `dto-record-mandate.md` becomes load-bearing: serializing an entity with a
lazy field after the service returns will throw `LazyInitializationException` and surface the
defect at the point of authorship, not in production under load.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. `spring.jpa.open-in-view: false` in Every Profile

* **Rule**: `application.yml` (and every profile-scoped variant: `application-prod.yml`,
  `application-staging.yml`, `application-test.yml`) MUST contain `spring.jpa.open-in-view:
  false`. The Spring Boot default (`true`) MUST NOT be inherited silently.
* **Rationale**: The default `true` is the antithesis of explicit transaction boundaries. With
  OSIV on, every lazy field can be loaded from any thread that happens to be serializing the
  response — the database connection is held for the entire request duration even when the
  service has already returned. Setting it `false` ensures lazy loading is confined to the
  service-layer transaction and surfaces missed eager-load directives as
  `LazyInitializationException` during development.
* **Implementation Requirement**:

  ```yaml
  # ❌ ANTI-PATTERN — OSIV defaults to true, silently
  spring:
    jpa:
      hibernate:
        ddl-auto: validate

  # ✅ CORRECT — explicit disable
  spring:
    jpa:
      open-in-view: false
      hibernate:
        ddl-auto: validate
  ```

### 2.2. The Startup Warning Banner Is NOT a License to Silence

* **Rule**: When OSIV is disabled, Spring Boot logs a one-time INFO message
  (`spring.jpa.open-in-view is enabled by default. ... Disabling it makes ...`). This message
  MUST NOT be silenced by adjusting logger levels; if it appears in startup logs, OSIV is
  still enabled and the property has not been applied.
* **Rationale**: The startup message is the operator's audit trail that OSIV is correctly
  disabled. Silencing it removes the signal. The fact that the message appears at INFO instead
  of WARN is a Spring Boot quirk; the message should be treated as an audit confirmation, not
  a nuisance.

### 2.3. Application Code MUST NOT Re-Open Sessions in the View Layer

* **Rule**: Application code MUST NOT re-introduce session-in-view behavior via
  `OpenEntityManagerInViewFilter`, `OpenEntityManagerInViewInterceptor`, manual
  `EntityManager.joinTransaction()` calls in `@RestControllerAdvice`, or programmatic
  `SessionFactory.openSession()` in HTTP-handling code.
* **Rationale**: Re-opening sessions in the view layer reintroduces every defect OSIV-off was
  meant to prevent. The correct fix when a serialization needs a lazy field is the upstream
  repository method declaring `@EntityGraph` (per `entity-graph-strategy.md`), NOT the view
  layer compensating after the fact.

### 2.4. Tests Verify the Boot-Time Property

* **Rule**: The application's integration test suite MUST include one test that asserts
  `spring.jpa.open-in-view` is `false` at application startup. The test prevents accidental
  property drift across profile splits.
* **Implementation Requirement**:

  ```java
  // ✅ CORRECT
  @SpringBootTest
  class OsivConfigurationTest {
      @Value("${spring.jpa.open-in-view}")
      boolean openInView;

      @Test
      void osivMustBeDisabled() {
          assertThat(openInView).isFalse();
      }
  }
  ```

## 3. AI Directives

When generating, modifying, or refactoring Spring Boot configuration in `application.yml`,
`application*.properties`, or `**/config/**/*.java`:

1. **Whenever generating an `application.yml` for a new project, include
   `spring.jpa.open-in-view: false` as the first JPA property.** Surface a one-line PR comment
   explaining the connection-pool / N+1 impact.
2. **When an existing project has no `spring.jpa.open-in-view` entry, add it as `false`** in
   the same change that touches `application.yml` for any reason.
3. **Reject any proposal to enable OSIV "to fix a `LazyInitializationException`."** The
   correct fix is `@EntityGraph` on the upstream repository method, NOT re-enabling OSIV.
4. **When generating integration tests, propose the `spring.jpa.open-in-view == false`
   assertion** if not already present.
