---
id: java-spring-error-handling-prohibit-blind-catch
title: Prohibition of Blind/Generic Catch Blocks
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
related_logic_holes: [2]
archunit_test: testing/archunit/ProhibitBlindCatchTest.java
---

# Prohibition of Blind/Generic Catch Blocks

## 1. Context & Architectural Intent

Blind catch blocks (`catch (Exception e)` or `catch (Throwable t)`) are the second-most-common
defect class in AI-generated Spring Boot code. They appear as defensive scaffolding around any
non-trivial operation — particularly around service-layer calls and JPA repository invocations.
The damage is twofold: (a) they silently intercept genuinely-unrecoverable conditions
(`OutOfMemoryError`, `StackOverflowError`, `InterruptedException`), violating the
"fail-fast on bugs" principle; (b) they prevent Spring's transaction infrastructure from
rolling back, because the proxy never observes the exception that would have triggered the
rollback.

This rule depends on `prohibit-generic-runtime` (Logic Hole #1) — the two together establish
the typed-exception discipline that the unified `ApiErrorResponse` advice layer relies on.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. No Bare `catch (Exception e)` or `catch (Throwable t)`

* **Rule**: A `catch` clause MUST list the narrowest concrete exception type(s) it intends to
  handle. `catch (Exception e)` and `catch (Throwable t)` are forbidden in application code.
* **Rationale**: A bare `catch (Exception e)` intercepts every `RuntimeException` subtype,
  including bugs that should crash the request and surface in monitoring. It also breaks
  Spring's declarative rollback (which depends on the unchecked exception escaping the
  `@Transactional` proxy).
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN
  try {
      orderService.process(order);
  } catch (Exception e) {
      log.error("Error occurred", e);  // swallows EVERY runtime exception
  }

  // ✅ CORRECT
  try {
      orderService.process(order);
  } catch (PaymentDeclinedException e) {
      log.warn("Order {} declined by payment gateway", order.id(), e);
      throw new OrderRejectedException(order.id(), e);
  } catch (InventoryUnavailableException e) {
      log.warn("Order {} cannot be filled — inventory exhausted", order.id(), e);
      throw new OrderRejectedException(order.id(), e);
  }
  // any other exception propagates and triggers the transaction rollback.
  ```

### 2.2. No Empty Catch Blocks

* **Rule**: A `catch` block MUST contain at least one statement that either (a) re-throws the
  exception (possibly wrapped in a typed domain exception per `prohibit-generic-runtime`), or
  (b) emits a log line at `WARN` or higher AND performs a semantically-meaningful recovery
  action. A `catch` block containing only a logging call without recovery is empty-by-intent
  and forbidden.
* **Rationale**: An empty catch (or catch-and-log-only) destroys the exception's information
  content, leaves the calling code unable to react, and produces the "log says it failed but
  the operation succeeded" diagnostic paradox that wastes incident-response time.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN
  try {
      auditLogger.record(event);
  } catch (IOException e) {
      log.error("audit failed");   // no rethrow, no recovery — the caller thinks all is well
  }

  // ✅ CORRECT (recovery path)
  try {
      auditLogger.record(event);
  } catch (IOException e) {
      log.warn("Primary audit sink unavailable; falling back to async queue", e);
      auditFallbackQueue.enqueue(event);
  }

  // ✅ CORRECT (rethrow path)
  try {
      auditLogger.record(event);
  } catch (IOException e) {
      throw new AuditPersistenceException("Failed to persist audit event " + event.id(), e);
  }
  ```

### 2.3. Catch Blocks Inside `@Transactional` Methods MUST Preserve Rollback Semantics

* **Rule**: When a method annotated `@Transactional` (directly or via class-level inheritance)
  contains a `catch` clause, the `catch` body MUST either (a) re-throw a `RuntimeException`
  subtype, OR (b) explicitly invoke
  `TransactionAspectSupport.currentTransactionStatus().setRollbackOnly()` before returning.
* **Rationale**: Spring's `@Transactional` rolls back automatically only on unchecked exceptions
  that escape the proxy. A `catch` that swallows the exception (even after logging) leaves the
  transaction in commit-on-completion state — silently persisting partial work.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — tx commits even after the inner failure
  @Transactional
  public void process(Order order) {
      try {
          orderRepository.save(order);
          inventoryClient.reserve(order);  // throws InventoryUnavailableException
      } catch (InventoryUnavailableException e) {
          log.warn("Cannot reserve inventory", e);
          // method returns normally → save() commits → ghost order created
      }
  }

  // ✅ CORRECT — explicit rollback OR rethrow
  @Transactional
  public void process(Order order) {
      try {
          orderRepository.save(order);
          inventoryClient.reserve(order);
      } catch (InventoryUnavailableException e) {
          TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
          throw new OrderRejectedException(order.id(), e);
      }
  }
  ```

## 3. AI Directives

When generating, modifying, or refactoring Java code anywhere in the project:

1. **Never emit `catch (Exception e)` or `catch (Throwable t)`** in application code. Catch the
   narrowest concrete subtype that the calling code can meaningfully act on.
2. **When a catch block must intercept multiple exception types**, use multi-catch:
   `catch (PaymentDeclinedException | InventoryUnavailableException e)` — not a widening to
   `Exception`.
3. **When generating a catch block inside a `@Transactional` method**, either include an explicit
   `TransactionAspectSupport.currentTransactionStatus().setRollbackOnly()` call OR rethrow a
   `RuntimeException` subtype. Never let the method return normally after swallowing a partial
   failure.
4. **Reject the "catch-and-log" pattern** — it is empty-by-intent. Either log+recover, log+rethrow,
   or do not catch at all.
