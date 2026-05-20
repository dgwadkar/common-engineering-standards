---
id: java-spring-service-transactional-boundaries
title: Disciplined @Transactional Boundaries — No External I/O Inside Transactions
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers:
    - service
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
  - java-spring-error-handling-prohibit-blind-catch
related_logic_holes: [4]
archunit_test: testing/archunit/TransactionalDisciplineTest.java
---

# Disciplined @Transactional Boundaries — No External I/O Inside Transactions

## 1. Context & Architectural Intent

`@Transactional` is the most-misused annotation in Spring Boot. AI agents apply it
indiscriminately — pattern-matching `@Service` ⇒ `@Transactional` from a vast tutorial corpus —
producing three latent defect classes: (a) blocking connection-pool exhaustion when long I/O
runs inside a transaction; (b) silently-broken self-invocation (see `self-invocation-trap.md`);
(c) read-write transactions on read-only paths (see `transactional-readonly.md`).

This rule addresses defect class (a): forbidding external I/O inside `@Transactional` method
bodies. While a transaction is open, the calling thread holds a database connection from the
HikariCP pool for the entire duration of the method — including any blocking HTTP, gRPC, or
broker call that happens to occur. Under load this produces the canonical "p99 latency
hockey-sticks at 80% load while DB metrics show healthy" pathology: the pool exhausts because
threads waiting on downstream I/O are also waiting on a connection they're holding hostage.

This rule is the central piece of Logic Hole #4. Its siblings (`transactional-readonly.md`,
`self-invocation-trap.md`, `n-plus-one-prevention.md`, `entity-graph-strategy.md`,
`disable-open-session-in-view.md`) cover the readOnly default, the proxy-invocation gotcha,
the N+1 prevention strategy, the entity-graph composition rule, and the OSIV ban respectively.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. No HTTP, gRPC, Message-Broker, or File I/O Inside `@Transactional`

* **Rule**: A method annotated `@Transactional` (directly or by class-level inheritance) MUST
  NOT invoke any blocking external I/O — HTTP clients (`RestClient`, `WebClient.block()`,
  `RestTemplate`), gRPC stubs, message-broker publishes (`KafkaTemplate.send().get()`,
  `RabbitTemplate.convertAndSend`), or filesystem operations on remote-mounted paths. If the
  workflow requires both DB writes and external I/O, the method MUST extract the DB-only
  critical section into a `TransactionTemplate.execute(...)` block and perform the I/O outside
  it.
* **Rationale**: A connection is held for the entire method duration. A 2-second HTTP call
  holds a connection for 2 seconds — orders of magnitude longer than the DB work itself. The
  pool exhausts; threads queue; p99 collapses while CPU and DB load remain nominal. The fix
  is to narrow the transaction to the DB-only operations.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — HTTP call inside @Transactional holds DB connection
  @Service
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;

      @Transactional
      public Order create(OrderRequest req) {
          Order saved = orderRepository.save(new Order(req));
          paymentClient.charge(saved.getId(), saved.getTotal());   // 800ms HTTP, connection held
          saved.markPaid();
          return orderRepository.save(saved);
      }
  }

  // ✅ CORRECT — narrow transactions, I/O outside
  @Service
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;
      private final TransactionTemplate txTemplate;

      public Order create(OrderRequest req) {
          Order saved = txTemplate.execute(status -> orderRepository.save(new Order(req)));
          paymentClient.charge(saved.getId(), saved.getTotal());   // I/O outside any tx
          return txTemplate.execute(status -> {
              Order reattached = orderRepository.findById(saved.getId()).orElseThrow();
              reattached.markPaid();
              return orderRepository.save(reattached);
          });
      }
  }
  ```

### 2.2. No `@Transactional` on `@Scheduled` Methods

* **Rule**: A method MUST NOT carry both `@Scheduled` and `@Transactional`. If a scheduled job
  needs a transaction, the `@Scheduled` method MUST delegate to a separate `@Service`'s
  `@Transactional` method.
* **Rationale**: Spring's scheduling proxy and transactional proxy compose poorly. Depending
  on bean post-processor ordering, the transactional proxy may be lost — producing silent
  no-op transactions that COMMIT every individual write inline. This is documented in Spring's
  reference and reinforced in the JetBrains Junie Spring Boot guidelines.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN
  @Scheduled(fixedRate = 60_000)
  @Transactional
  public void purgeStaleSessions() {
      sessionRepository.deleteOlderThan(Instant.now().minus(Duration.ofHours(24)));
  }

  // ✅ CORRECT — delegate to a separate bean
  @Component
  @RequiredArgsConstructor
  public class StaleSessionPurger {
      private final SessionMaintenanceService maintenance;

      @Scheduled(fixedRate = 60_000)
      public void runPurge() {
          maintenance.purgeStaleSessions();   // proxy-mediated call into the @Transactional bean
      }
  }

  @Service
  @RequiredArgsConstructor
  public class SessionMaintenanceService {
      private final SessionRepository sessionRepository;

      @Transactional
      public void purgeStaleSessions() {
          sessionRepository.deleteOlderThan(Instant.now().minus(Duration.ofHours(24)));
      }
  }
  ```

### 2.3. Transaction Timeout MUST Be Explicit on Mutating Methods

* **Rule**: Every `@Transactional` annotation on a mutating method MUST declare an explicit
  `timeout` (in seconds) sized to the operation's expected duration plus a small headroom
  (typically `timeout = 5` for a normal write, `timeout = 30` for a batch). The default
  (`timeout = -1`, "no timeout") MUST NOT be relied on.
* **Rationale**: Without a timeout, a runaway transaction (lock contention, slow query) holds
  its connection indefinitely. An explicit timeout is the per-transaction circuit breaker; it
  surfaces the problem as a `TransactionTimedOutException` instead of pool exhaustion.

## 3. AI Directives

When generating, modifying, or refactoring Java code under `**/service/**/*.java` or
`**/usecase/**/*.java`:

1. **Before placing `@Transactional` on a method, scan the body for HTTP clients, gRPC stubs,
   message publishers, file I/O on remote paths, and `Thread.sleep` / `.await()` calls.** If
   any are found, refactor to use `TransactionTemplate` and move the I/O outside the
   `execute(...)` lambda.
2. **Never combine `@Scheduled` and `@Transactional` on the same method.** Always delegate the
   scheduled trigger into a separate bean that holds the `@Transactional`.
3. **When emitting a `@Transactional` annotation on a mutating method, include an explicit
   `timeout`.** Use 5 seconds as the default; raise only for documented batch operations.
4. **When the user pastes a `@Transactional` method that calls `paymentClient`, `kafkaTemplate`,
   or any client-like dependency, flag the connection-holding risk** even if the user's request
   did not mention transactions.
