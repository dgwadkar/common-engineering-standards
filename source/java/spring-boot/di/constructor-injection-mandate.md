---
id: java-spring-di-constructor-injection-mandate
title: Constructor Injection Mandate — No Field or Setter @Autowired
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=4.3"
  layers:
    - di
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
  junie: true
  agents_md: true
activation:
  cursor_mode: agent-requested
  agents_md_priority: high
dependencies: []
related_logic_holes: [6]
archunit_test: testing/archunit/ConstructorInjectionTest.java
---

# Constructor Injection Mandate — No Field or Setter @Autowired

## 1. Context & Architectural Intent

Field injection (`@Autowired` on a private field) was the dominant Spring pattern in
pre-2017 code and remains heavily represented in AI training corpora — roughly 40% of
Stack Overflow Spring snippets still use it (Orange & Bronze Insights 2025 survey). Spring
itself officially discourages it since 4.3 (2016) and reinforced this in Spring Boot 3+.

Field injection creates four concrete defects: (a) the bean cannot be unit-tested without a
Spring context — `new OrderService(mockRepo, mockClient)` is impossible; (b) dependencies
cannot be `final`, so reflection or a misbehaving subclass can null them; (c) the class
signature lies — its true contract is invisible until you read the body; (d) circular
dependencies are masked by lazy proxy resolution and surface at runtime instead of at boot.

This rule mandates constructor injection with `final` fields. It uses
`activation.cursor_mode: agent-requested` because the scope (`layers: [di]` resolves to all
`**/*.java`) is too broad for auto-attach — Cursor's agent decides relevance based on the
task description ("compose a Spring bean", "refactor a service for testability").

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Every Spring Bean Uses Constructor Injection With `final` Fields

* **Rule**: Every class annotated `@Component`, `@Service`, `@Repository`, `@Controller`,
  `@RestController`, or `@Configuration` MUST declare its dependencies as `private final`
  fields, populated via a single explicit constructor (Spring 4.3+ auto-wires the sole
  constructor — no `@Autowired` annotation is required). Lombok's `@RequiredArgsConstructor`
  MAY be used if and only if the project's build manifest already declares Lombok as a
  dependency.
* **Rationale**: (a) `final` enforces immutability — dependencies cannot be null'd after
  construction; (b) the constructor signature IS the bean's contract — readable in one place;
  (c) unit tests instantiate with `new TheService(mockA, mockB)` — sub-millisecond startup;
  (d) circular dependencies fail at boot with a clear "circular reference" error instead of
  silently working until traffic exposes the proxy hazard.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — field injection
  @Service
  public class OrderService {
      @Autowired private OrderRepository orderRepository;
      @Autowired private PaymentClient paymentClient;
  }

  // ❌ ANTI-PATTERN — setter injection
  @Service
  public class OrderService {
      private OrderRepository orderRepository;
      @Autowired
      public void setOrderRepository(OrderRepository r) { this.orderRepository = r; }
  }

  // ✅ CORRECT — explicit constructor
  @Service
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;

      public OrderService(OrderRepository orderRepository, PaymentClient paymentClient) {
          this.orderRepository = orderRepository;
          this.paymentClient = paymentClient;
      }
  }

  // ✅ CORRECT — Lombok-generated constructor (project already uses Lombok)
  @Service
  @RequiredArgsConstructor
  public class OrderService {
      private final OrderRepository orderRepository;
      private final PaymentClient paymentClient;
  }
  ```

### 2.2. `@Autowired` MUST NOT Appear on Fields or Setters

* **Rule**: The `@Autowired` annotation MUST NOT appear on a field declaration, a setter
  method, a `@Configuration`-class field, or a `@TestConfiguration`-class field. Its only
  legal site is a constructor parameter — and even there, it is unnecessary if the class has
  exactly one constructor.
* **Rationale**: Field-site `@Autowired` is the marker of the field-injection anti-pattern.
  Banning it at the annotation site forces the design into constructor injection at
  authoring time.

### 2.3. Optional Dependencies Use `Optional<T>` in the Constructor

* **Rule**: Optional dependencies MUST be expressed as `Optional<T>` in the constructor, not
  as `@Autowired(required = false)` on a field.
* **Rationale**: `Optional<T>` is the explicit, type-checked optional contract. The
  field-level `required = false` is silent (the reader cannot see at a glance that the
  dependency may be null) and brittle (a misconfiguration produces a `NullPointerException`
  far from the field declaration).
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN
  @Autowired(required = false)
  private MetricsClient metricsClient;

  // ✅ CORRECT
  public OrderService(OrderRepository orderRepository, Optional<MetricsClient> metricsClient) {
      this.orderRepository = orderRepository;
      this.metricsClient = metricsClient;
  }
  ```

### 2.4. Tests MUST Instantiate Beans Via the Constructor, Not Via `@Autowired` Fields

* **Rule**: A unit test (NOT a Spring-context-loading integration test) MUST construct the
  class under test via `new TheService(mockA, mockB)`. It MUST NOT use Mockito's
  `@InjectMocks` + `@Mock` field magic to populate field-injected dependencies.
* **Rationale**: If a unit test needs `@InjectMocks` against a field-injected bean, the
  production design has already failed the testability bar. The correct fix is to refactor
  the production code to constructor injection.

## 3. AI Directives

When generating, modifying, or refactoring Java code that declares a Spring bean
(`@Component`, `@Service`, `@Repository`, `@Controller`, `@RestController`, `@Configuration`):

1. **Default to constructor injection with `final` fields.** Never emit `@Autowired` on a
   field, setter, or method.
2. **Use Lombok's `@RequiredArgsConstructor`** if and only if the project's `pom.xml` /
   `build.gradle` already declares the Lombok dependency. Otherwise emit an explicit
   constructor.
3. **Express optional dependencies as `Optional<T>` constructor parameters,** not
   `@Autowired(required = false)` on fields.
4. **When refactoring a field-injected bean, migrate it in-place to constructor injection** in
   the same change. Surface a one-line PR comment about the testability and immutability gain.
5. **When the user pastes a class with `@Autowired private`, flag every field and propose the
   refactor** even if the user's prompt did not mention DI.
