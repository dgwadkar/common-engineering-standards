---
id: java-spring-error-handling-unified-api-error
title: Unified ApiErrorResponse Contract for All REST Error Pathways
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers:
    - error-handling
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
  - java-spring-error-handling-prohibit-generic-runtime
  - java-spring-error-handling-prohibit-blind-catch
related_logic_holes: [1, 2]
archunit_test: testing/archunit/UnifiedApiErrorTest.java
---

# Unified ApiErrorResponse Contract for All REST Error Pathways

## 1. Context & Architectural Intent

Every error that crosses a REST boundary in this organization MUST serialize to the same
`ApiErrorResponse` shape. The contract is owned by the central `@RestControllerAdvice` and is
the only legal serialization path for failure responses. Without enforcement, AI-generated
controllers tend to return ad-hoc shapes (`Map.of("error", "...")`, `ResponseEntity.badRequest()
.body("text")`, raw strings) — fragmenting the contract and breaking every downstream consumer
that depends on `errorCode`, `developerMessage`, and the per-field validation map.

This rule depends on `prohibit-generic-runtime` (typed exceptions) and `prohibit-blind-catch`
(exceptions actually reach the advice). Without those two foundations, the advice cannot route
failures to the correct status + payload.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. The `ApiErrorResponse` Record Is the Sole Error Shape

* **Rule**: Every REST error response body MUST be an instance of `ApiErrorResponse` (or its
  RFC 7807 superset `ProblemDetail` per `problem-details-rfc7807.md` for Spring Boot 3+). No
  ad-hoc maps, no string-bodied `ResponseEntity`, no controller-local error records.
* **Rationale**: A single shape across the org lets every consumer (web SPA, mobile, partner
  integrations, internal services) write one error-handling code path. Drift between endpoints
  forces consumers into per-endpoint conditionals or generic "the call failed somehow"
  alerting.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — ad-hoc error shape
  @PostMapping("/orders")
  public ResponseEntity<?> create(@RequestBody OrderRequest req) {
      try {
          return ResponseEntity.ok(orderService.create(req));
      } catch (InventoryUnavailableException e) {
          return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
      }
  }

  // ✅ CORRECT — let the typed exception propagate to the central advice
  @PostMapping("/orders")
  public OrderResponse create(@Valid @RequestBody OrderCreateRequest req) {
      return OrderResponse.from(orderService.create(req));   // InventoryUnavailableException
                                                             // is handled by @RestControllerAdvice
  }

  public record ApiErrorResponse(
      String errorCode,                         // stable, kebab-case (e.g., "inventory-unavailable")
      String developerMessage,                  // free-form, never leak internals
      Map<String, String> fieldValidationErrors, // empty map when not a validation failure
      Instant timestamp,
      String traceId                            // OTel/Sleuth trace id; required for prod
  ) {}
  ```

### 2.2. The `@RestControllerAdvice` Has an `@ExceptionHandler` for Every Domain Exception

* **Rule**: Every concrete subclass of `DomainException` MUST have a dedicated
  `@ExceptionHandler(SomeDomainException.class)` method in the central advice that maps the
  exception to the correct HTTP status and constructs the `ApiErrorResponse`. Bulk handlers
  (`@ExceptionHandler(DomainException.class)` that routes by reflection) are forbidden — they
  hide the per-status mapping in runtime logic instead of in type-checked code.
* **Rationale**: Per-type handlers make the status mapping reviewable in source. A reviewer can
  search for `@ExceptionHandler(OrderNotFoundException.class)` and immediately verify it returns
  `404 NOT_FOUND`. A reflective bulk handler defers that verification to runtime.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — reflective routing
  @RestControllerAdvice
  public class GlobalErrorHandler {
      @ExceptionHandler(DomainException.class)
      public ResponseEntity<ApiErrorResponse> handle(DomainException e) {
          return ResponseEntity.status(e.getHttpStatus())   // status hidden inside exception
              .body(new ApiErrorResponse(e.getErrorCode(), e.getMessage(), Map.of(), Instant.now(), traceId()));
      }
  }

  // ✅ CORRECT — per-type handlers, explicit status binding
  @RestControllerAdvice
  public class GlobalErrorHandler {
      @ExceptionHandler(OrderNotFoundException.class)
      public ResponseEntity<ApiErrorResponse> handle(OrderNotFoundException e) {
          return ResponseEntity.status(HttpStatus.NOT_FOUND)
              .body(error("order-not-found", e.getMessage()));
      }
      @ExceptionHandler(PaymentDeclinedException.class)
      public ResponseEntity<ApiErrorResponse> handle(PaymentDeclinedException e) {
          return ResponseEntity.status(HttpStatus.PAYMENT_REQUIRED)
              .body(error("payment-declined", e.getMessage()));
      }
      // ... one method per concrete domain exception.
  }
  ```

### 2.3. The Fallback `@ExceptionHandler(Throwable.class)` Returns `500` With a Generic Body

* **Rule**: The advice MUST contain a final `@ExceptionHandler(Throwable.class)` (or
  `@ExceptionHandler(Exception.class)`) that returns HTTP 500 with `errorCode: "internal-error"`
  and a developer message that does NOT leak the stack trace or exception class name. The
  trace ID is the operator's debugging hook.
* **Rationale**: Unanticipated exceptions must still return the canonical shape — never an HTML
  Whitelabel error page, never a raw stack trace. Information disclosure on unhandled paths is
  the most common error-handling security defect.
* **Implementation Requirement**:

  ```java
  // ✅ CORRECT
  @ExceptionHandler(Throwable.class)
  public ResponseEntity<ApiErrorResponse> fallback(Throwable t) {
      log.error("Unhandled exception (traceId={})", traceId(), t);
      return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
          .body(new ApiErrorResponse(
              "internal-error",
              "An unexpected error occurred. Reference traceId for support.",
              Map.of(),
              Instant.now(),
              traceId()
          ));
  }
  ```

### 2.4. Validation Failures Populate `fieldValidationErrors`

* **Rule**: The handler for `MethodArgumentNotValidException` MUST flatten the binding result
  into the `fieldValidationErrors` map of `ApiErrorResponse` (field name → human message). The
  HTTP status MUST be `400 BAD_REQUEST` and `errorCode` MUST be `"validation-failed"`.
* **Rationale**: Default Spring behavior returns a verbose `BindingResult` payload that leaks
  framework internals (e.g., `objectName`, `bindingFailure`). Flattening into the unified shape
  keeps consumers on a single contract.

## 3. AI Directives

When generating, modifying, or refactoring Java code in `**/exception/**`, `**/advice/**`,
`**/errors/**`, or anywhere a controller returns an error body:

1. **Never construct an ad-hoc error response shape.** Always return the unified
   `ApiErrorResponse` (or RFC 7807 `ProblemDetail` on Spring Boot 3+).
2. **When adding a new domain exception, also add its `@ExceptionHandler`** to the central
   advice in the same change. Do not leave the exception unrouted.
3. **Never expose stack traces, exception class names, or framework internals** in the
   `developerMessage`. The trace ID is the diagnostic surface for operators.
4. **Reject controllers that wrap a service call in `try/catch` and return a custom error
   shape.** Let the typed exception propagate to the advice.
