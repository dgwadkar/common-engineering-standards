---
id: java-spring-repository-n-plus-one-prevention
title: N+1 Select Prevention via Fetch Strategy and BatchSize
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  framework_version: ">=2.7"
  layers:
    - repository
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
  - java-spring-repository-entity-graph-strategy
related_logic_holes: [4]
archunit_test: testing/archunit/NPlusOnePreventionTest.java
---

# N+1 Select Prevention via Fetch Strategy and BatchSize

## 1. Context & Architectural Intent

The N+1 select problem is the single most-cited Spring Data JPA performance defect, profiled
extensively by Vlad Mihalcea and confirmed by BitDive's 2025 production study (~70% of
incident-grade Spring Boot performance issues trace to it). The shape: a service method loads
a parent collection (N rows) and iterates accessing a lazy `@ManyToOne` or `@OneToMany` field;
Hibernate emits one additional SELECT per row. A page of 100 orders with a lazy `customer`
field produces 101 queries instead of 1.

AI agents cannot statically analyze the runtime traversal pattern. They generate the entity
correctly (with `FetchType.LAZY` by default — which is correct) and the service correctly in
isolation. The bug emerges from their composition: the controller serializes the lazy field,
or the service method enriches a DTO from the lazy field, and 100 SELECTs fire.

This rule mandates the defense-in-depth combination: `@BatchSize` on every collection
association (Hibernate-level mitigation that turns N+1 into N/batch-size + 1) plus
`@EntityGraph` on repository methods that need eager loading (per
`entity-graph-strategy.md`). The Open-Session-in-View ban (`disable-open-session-in-view.md`)
makes lazy-loading-during-serialization fail loudly instead of silently triggering the storm.

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Every `@OneToMany` Collection Carries `@BatchSize`

* **Rule**: Every `@OneToMany`, `@ManyToMany`, and `@ElementCollection` field on a JPA entity
  MUST carry an `org.hibernate.annotations.BatchSize` annotation with `size` between 10 and 50
  (typical: 25). The default is the global `hibernate.default_batch_fetch_size` property,
  which MAY be set in `application.yml` for project-wide defaults.
* **Rationale**: `@BatchSize` instructs Hibernate to load lazy collections in batches when
  iterated. A 100-parent N+1 with `@BatchSize(25)` becomes 5 SELECTs (1 + ceil(100/25)) instead
  of 101. It is the cheapest, lowest-risk N+1 mitigation and SHOULD be the default on every
  collection association.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — no BatchSize; 1 + N queries on iteration
  @Entity
  public class Order {
      @Id Long id;
      @OneToMany(mappedBy = "order")
      private List<OrderLine> lines;
  }

  // ✅ CORRECT — @BatchSize converts N+1 into N/size + 1
  @Entity
  public class Order {
      @Id Long id;
      @OneToMany(mappedBy = "order")
      @org.hibernate.annotations.BatchSize(size = 25)
      private List<OrderLine> lines;
  }
  ```

  Or set the project-wide default:

  ```yaml
  spring:
    jpa:
      properties:
        hibernate:
          default_batch_fetch_size: 25
  ```

### 2.2. Service Methods That Traverse Lazy Fields MUST Use an `@EntityGraph` Repository Method

* **Rule**: When a service method iterates a parent collection and accesses a lazy field on
  each parent, the repository method that loads the parents MUST carry an
  `@EntityGraph(attributePaths = {…})` that eagerly fetches the traversed field. The service
  MUST NOT rely on `@BatchSize` alone when the traversal is statically obvious.
* **Rationale**: `@BatchSize` is the defense-in-depth fallback; `@EntityGraph` is the explicit
  contract that says "this query needs this association loaded." Reviewers can grep
  `@EntityGraph` and verify the loaded paths match the downstream usage. See
  `entity-graph-strategy.md` for the JOIN-FETCH-vs-EntityGraph rules.
* **Implementation Requirement**:

  ```java
  // ❌ ANTI-PATTERN — repository unaware; service triggers N+1
  public interface OrderRepository extends JpaRepository<Order, Long> {
      List<Order> findByStatus(OrderStatus status);
  }

  @Service
  public class OrderEnricher {
      public List<OrderSummary> enrich(OrderStatus status) {
          return orderRepository.findByStatus(status).stream()
              .map(o -> new OrderSummary(o.getId(), o.getCustomer().getName(), o.getTotalCents()))
              //                                    ^^^^^^^^^^^^^^^^^^^^^^^^ lazy → 1 SELECT per order
              .toList();
      }
  }

  // ✅ CORRECT — repository declares the load contract
  public interface OrderRepository extends JpaRepository<Order, Long> {
      @EntityGraph(attributePaths = {"customer"})
      List<Order> findByStatus(OrderStatus status);
  }
  ```

### 2.3. Defense: `MultipleBagFetchException` Detection

* **Rule**: A query that eagerly fetches more than one `Bag`-typed collection (a `List` whose
  element type does NOT have `@OrderColumn`) raises Hibernate's `MultipleBagFetchException`.
  Repository methods MUST NOT join-fetch two such collections from the same parent in a single
  query.
* **Rationale**: Hibernate cannot construct the Cartesian product cleanly when two `Bag`
  collections are fetched together. The error surfaces at the second query parse, often in
  staging when the second collection is added. The fix is to split the load into two queries
  (each fetching one collection) or use `@OrderColumn` to make them `List`s instead of `Bag`s.

### 2.4. No `FetchType.EAGER` on Collections

* **Rule**: `@OneToMany` and `@ManyToMany` fields MUST NOT use `FetchType.EAGER`. The default
  `LAZY` is correct; if a particular query needs the collection loaded, it does so via
  `@EntityGraph` on the repository method, NOT via a class-level eager fetch.
* **Rationale**: Eager-fetched collections execute on EVERY load of the parent — even when the
  caller doesn't need them. They are the N+1's worse cousin: silent, always-on, and impossible
  to opt out of without rewriting the entity.

## 3. AI Directives

When generating, modifying, or refactoring Java code under `**/repository/**/*.java`,
`**/dao/**/*.java`, `**/persistence/**/*.java`, or anywhere a JPA entity is declared:

1. **When generating a new JPA entity, add `@BatchSize(size = 25)` to every `@OneToMany`,
   `@ManyToMany`, and `@ElementCollection`.** Surface the property in `application.yml` if it
   is not yet set.
2. **When generating a service that iterates a parent collection and accesses a lazy field,
   propose an `@EntityGraph(attributePaths = {…})` on the upstream repository method in the
   same change.** Do not leave the N+1 latent.
3. **Reject `FetchType.EAGER` on collections.** Replace with `LAZY` + `@EntityGraph` at the
   query site.
4. **When two collections must be eagerly fetched together, detect the
   `MultipleBagFetchException` risk** and propose either splitting the query or using
   `@OrderColumn`.
