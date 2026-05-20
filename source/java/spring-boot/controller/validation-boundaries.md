---
id: java-spring-controller-validation-boundaries
title: Mandatory @Valid and @Validated on Controller Boundaries
version: 1.0.0
status: approved
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
dependencies:
  - global-security-baselines
related_logic_holes: [3]
archunit_test: testing/archunit/ControllerValidationTest.java
---

# Mandatory @Valid and @Validated on Controller Boundaries

## 1. Context & Architectural Intent

Controllers are the trust boundary between untrusted client input and trusted domain logic.
Jakarta Bean Validation constraints (`@NotNull`, `@Size`, `@Email`, `@Pattern`, `@Positive`, …)
declared on the request DTO are **inert without an explicit activator**: `@Valid` for request
body / part / model-attribute parameters, and a class-level `@Validated` for path-variable and
query-parameter constraints. AI agents trained on tutorial-grade snippets routinely declare the
constraints on the DTO and omit the activator — producing controllers that accept any payload
Jackson can bind, regardless of the declared rules. This is functionally equivalent to disabling
type checking at runtime.

This rule is the input-side half of Logic Hole #3. The output-side (`dto-record-mandate.md`) and
the pagination-side (`pageable-defaults.md`) round out the controller boundary contract.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. `@Valid` on Every `@RequestBody`, `@RequestPart`, and `@ModelAttribute`

* **Rule**: Every controller method parameter annotated with `@RequestBody`, `@RequestPart`, or
  `@ModelAttribute` MUST be preceded by `@Valid` (or `@Validated(<group>.class)` when validation
  groups are in use). Cascade validation onto nested fields with `@Valid` on the field
  declaration.
* **Rationale**: Without `@Valid`, JSR-380/Jakarta Validation constraints on the DTO type are
  silently ignored. The controller accepts payloads that violate the declared contract;
  validation failures surface deep in the service layer (with the wrong response shape) or, in
  the worst case, persist invalid data.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — constraints declared but never activated
  @PostMapping("/users")
  public UserResponse create(@RequestBody UserCreateRequest req) { /* ... */ }

  // ✅ CORRECT
  @PostMapping("/users")
  public UserResponse create(@Valid @RequestBody UserCreateRequest req) { /* ... */ }
  ```

### 2.2. Class-Level `@Validated` for `@PathVariable` and `@RequestParam` Constraints

* **Rule**: A controller class that declares Jakarta Validation constraints directly on
  `@PathVariable` or `@RequestParam` parameters MUST be annotated `@Validated` at the class
  level.
* **Rationale**: `@Valid` activates validation for cascaded bean validation; path/query
  parameter constraints are method-level constraints and require Spring's `@Validated`
  meta-annotation to register the AOP interceptor that fires them.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — @Positive never enforced
  @RestController
  public class UserController {
      @GetMapping("/users/{id}")
      public UserResponse get(@PathVariable @Positive Long id) { /* ... */ }
  }

  // ✅ CORRECT — class-level @Validated activates the AOP interceptor
  @RestController
  @Validated
  public class UserController {
      @GetMapping("/users/{id}")
      public UserResponse get(@PathVariable @Positive Long id) { /* ... */ }
  }
  ```

### 2.3. The Advice Maps `MethodArgumentNotValidException` to `400` + `ApiErrorResponse`

* **Rule**: The central `@RestControllerAdvice` MUST handle both
  `MethodArgumentNotValidException` (raised by `@Valid` activation) AND
  `ConstraintViolationException` (raised by class-level `@Validated`), flattening the binding
  result into the unified `ApiErrorResponse.fieldValidationErrors` map (per
  `unified-api-error.md`) OR the RFC 7807 `ProblemDetail` extension member (per
  `problem-details-rfc7807.md` on Spring Boot 3+).
* **Rationale**: Default Spring behavior returns a verbose `BindingResult` payload that leaks
  framework internals. The unified shape keeps consumers on a single error contract.
* **Implementation Requirement**:

  ```java
  // ✅ CORRECT
  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ApiErrorResponse> handle(MethodArgumentNotValidException e) {
      Map<String, String> fieldErrors = e.getBindingResult().getFieldErrors().stream()
          .collect(Collectors.toMap(
              FieldError::getField,
              FieldError::getDefaultMessage,
              (a, b) -> a   // keep first on duplicate-field
          ));
      return ResponseEntity.badRequest().body(new ApiErrorResponse(
          "validation-failed",
          "Request validation failed",
          fieldErrors,
          Instant.now(),
          traceId()
      ));
  }

  @ExceptionHandler(ConstraintViolationException.class)
  public ResponseEntity<ApiErrorResponse> handle(ConstraintViolationException e) {
      Map<String, String> fieldErrors = e.getConstraintViolations().stream()
          .collect(Collectors.toMap(
              v -> v.getPropertyPath().toString(),
              ConstraintViolation::getMessage,
              (a, b) -> a
          ));
      return ResponseEntity.badRequest().body(new ApiErrorResponse(
          "validation-failed",
          "Request validation failed",
          fieldErrors,
          Instant.now(),
          traceId()
      ));
  }
  ```

## 3. AI Directives

When generating, modifying, or refactoring Java code under `**/controller/**/*.java`,
`**/web/**/*.java`, or `**/rest/**/*.java`:

1. **For every `@RequestBody` / `@RequestPart` / `@ModelAttribute` parameter, prepend `@Valid`.**
   If absent, this is a critical defect — surface it in the response, not just silently fix.
2. **When the controller class declares constraints on path/query parameters**, add the
   class-level `@Validated` annotation in the same change.
3. **When adding a new `@RestController`, verify the central advice has handlers for both
   `MethodArgumentNotValidException` and `ConstraintViolationException`.** If either is missing,
   propose adding them.
4. **Never propose disabling validation** (e.g., "remove `@Valid` to allow malformed input for
   testing"). Tests use validation-correct fixtures; production controllers always validate.
