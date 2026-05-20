# System Patterns — Spring Boot 3

Pre-populated by `engineering-standards-central`. Augment with service-specific
patterns (e.g., event-sourcing details, sharding strategy, idempotency design).

## Layered Architecture

```mermaid
flowchart TD
  Client[HTTP / gRPC client] --> Controller
  Controller -->|request DTO record| Service
  Service -->|domain types| Repository
  Service --> ExternalIO[External I/O\n(payments, queues)]
  Repository --> Database[(Relational DB)]
  Service --> Domain[Domain types\n(framework-free)]
  Repository --> Domain
  classDef framework fill:#e3f2fd
  classDef domain fill:#fff3e0
  class Controller,Service,Repository framework
  class Domain domain
```

## Layer Boundaries

- Controllers depend only on services; never inject Repository types.
- Services depend on repositories and domain types; never on HttpServletRequest or controller types.
- Repositories contain persistence logic only; no business rules.
- Domain types import nothing from controller/service/repository or any framework annotation.

## Cross-Cutting Concerns

Logging, tracing, security, and error handling are governed by the canonical
engineering standards (see `.cursor/rules/`, `CLAUDE.md`, `AGENTS.md`).
