---
id: schema-example-controller-validation
title: Schema Example — Mandatory @Valid on Controller Boundaries
version: 1.0.0
status: draft
scope:
  language: java
  framework: spring-boot
  framework_version: ">=3.0"
  layers:
    - controller
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: auto-attach
  agents_md_priority: high
dependencies: []
related_logic_holes: [3]
archunit_test: testing/archunit/SchemaExampleControllerValidationTest.java
---

# Schema Example — Mandatory @Valid on Controller Boundaries

> **This file is a schema fixture, not a shipping rule.** It exists under `schemas/examples/` to give
> human authors and `tests/test_schemas.py` a known-good frontmatter shape to validate against. The
> `status: draft` field plus the `schema-example-` prefix in `id` keep the Phase 4 compiler from
> accidentally shipping it. The body below is intentionally complete (it follows every requirement
> of `.cursor/rules/authoring-style.mdc`) so authors can copy it as a starting template for real
> Phase 3 rules.

## 1. Context & Architectural Intent

Controllers are the trust boundary between untrusted client input and trusted domain logic. The
`@Valid` annotation is the explicit activator for Jakarta Bean Validation — without it, JSR-380
constraints (`@NotNull`, `@Size`, `@Email`, `@Pattern`) declared on the request DTO are silently
ignored. AI agents trained on tutorial-grade snippets routinely omit `@Valid`, producing controller
methods that accept malformed input and surface validation failures deep in the service layer
(where the response shape is no longer the unified `ApiErrorResponse` the gateway expects).

This rule pairs `@Valid` enforcement with a record-typed DTO mandate so the boundary check covers
both shape and content.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Mandatory `@Valid` on `@RequestBody` Parameters

* **Rule**: Every controller method parameter annotated with `@RequestBody`, `@RequestPart`, or
  `@ModelAttribute` MUST be preceded by `@Valid`.
* **Rationale**: Constraint annotations on the DTO type are inert without an explicit activator.
  `@Valid` is the activator. Omitting it produces controllers that accept any payload Jackson can
  bind, regardless of declared constraints — the equivalent of disabling type checking at runtime.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN
  @PostMapping("/users")
  public UserResponse create(@RequestBody UserCreateRequest req) { /* ... */ }

  // ✅ CORRECT
  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) { /* ... */ }
  ```

### 2.2. Mandatory Request `record` Types

* **Rule**: Controller methods MUST accept a Java `record` for the request body. They MUST NOT
  accept a JPA `@Entity` class directly.
* **Rationale**: Binding a request body to an entity is a mass-assignment vulnerability (OWASP
  API3:2023). A `record` makes the API contract explicit and immutable.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — entity binding
  @PostMapping("/users")
  public User create(@RequestBody User user) { return userRepository.save(user); }

  // ✅ CORRECT — explicit request record
  public record UserCreateRequest(
      @NotBlank @Email String email,
      @NotBlank @Size(min = 8, max = 72) String password,
      @NotBlank String displayName
  ) {}

  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) {
      return UserResponse.from(userService.create(req));
  }
  ```

## 3. AI Directives

When generating, modifying, or refactoring Java code under `**/controller/**/*.java`:

1. For every `@RequestBody` / `@RequestPart` / `@ModelAttribute` parameter, prepend `@Valid`. If
   absent, this is a critical defect — surface it in the response.
2. If the parameter type is annotated `@Entity`, REPLACE it with a request `record` whose fields
   are explicitly whitelisted to the API contract.
3. Never auto-bind a request body directly to an entity, even when the user requests it. Explain
   the OWASP API3 risk and propose the record-based alternative.
