# Centralized Engineering Standards Framework for AI Tooling
## Comprehensive Repository Architecture & Core Java/Spring Boot Blueprints

This framework establishes a scalable, automated repository structure designed to ingest, validate, and distribute engineering standards across all development teams. By transforming engineering standards into machine-parseable Markdown files with structural metadata, our CI/CD pipeline dynamically compiles context-minimized rule sets (`.cursorrules`, `.github/copilot-instructions.md`) optimized for AI code generation tools.

---

## 1. Vision & Strategic Focus: Fixing AI "Logic Holes"

Traditional coding standards focus heavily on stylistic elements, naming conventions, and basic boilerplate structures (e.g., DTO layouts). Modern LLMs (such as Claude 3.5 Sonnet and GPT-4o) already generate high-quality stylistic code out of the box. 

Therefore, this repository **intentionally skips trivial styling and naming standards**. Instead, it focuses exclusively on deep architectural rules and critical behavioral patterns that AI models frequently get wrong—referred to as **AI Logic Holes**. 

### Primary Behavioral Targets
1. **Strong Typification of Failures**: Forcing the AI to abandon the generation of generic `RuntimeException` or `HttpStatus.INTERNAL_SERVER_ERROR` responses, replacing them with strictly bounded, domain-specific exception models.
2. **Eliminating Blind Catch Blocks**: Preventing the AI pattern of wrapping code blocks in generic `catch (Exception e)` wrappers that swallow traces or break transaction boundary cleanups.
3. **Context Minimization**: Structuring the repository so that the automation pipeline only loads rules matching the exact environment stack, preventing context window degradation and minimizing enterprise infrastructure token spend.

---

## 2. Scalable Repository Directory Hierarchy

To accommodate hundreds of repositories, multiple languages, and varying tool formats, the repository utilizes a stack-scoped layout.

```text
engineering-standards-central/
│
├── .github/
│   └── workflows/
│       └── export-rules.yml          # CI/CD automation script for rule compilation & distribution
│
├── schemas/
│   └── rule-schema.json              # Strict JSON Schema defining valid frontmatter metadata
│
├── global/                           # Cross-cutting concerns applied to ALL repositories
│   ├── clean-architecture.md         # Layer boundaries and dependency inversion laws
│   ├── security-baselines.md         # OWASP top 10 mapping, input sanitation patterns
│   └── logging-telemetry.md          # Structured JSON logging, tracing context injection
│
└── languages/                        # Stack-scoped standards (hierarchical inheritance)
    ├── java/                         # Language-level core rules
    │   ├── java-core.md              # Functional pipelines, concurrency, stream limitations
    │   │
    │   └── spring-boot/              # Framework-level extensions (Your starting focus)
    │       ├── architecture.md       # Controller-Service-Repository strict separation
    │       ├── error-handling.md     # GlobalExceptionHandler, Custom Domain Exceptions
    │       ├── data-access.md        # Transaction boundaries (@Transactional), JPA lifecycle
    │       └── testing.md            # Slicing contexts (@WebMvcTest vs @SpringBootTest)
    │
    ├── typescript/                   # Scalable extension path
    │   ├── ts-core.md                # Strict type casting, utility types usage
    │   └── nestjs/                   # Framework extension
    │       └── exception-filters.md  # NestJS-specific global error boundaries
    │
    └── python/                       # Scalable extension path
        └── fastapi/
            └── dependencies.md
```

---

## 3. Metadata Frontmatter Schema Specification

Every Markdown file within the system must be prefixed with a valid YAML frontmatter block. This structured data is parsed by the automated compilation script to validate permissions, determine compilation targets, and scope tool deployment.

```yaml
---
id: java-spring-error-handling
title: Spring Boot Structural Exception Handling and Anti-Patterns
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
  layer: cross-cutting
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
dependencies:
  - global/logging-telemetry.md
---
```

### Metadata Fields Defined
* `id`: Unique string identifying the rule segment globally.
* `scope`: Granular technical filters. The distribution pipeline cross-references these fields with the project's dependency manifest (e.g., `pom.xml`, `package.json`) to determine if this file's contents belong in that repository's AI instruction file.
* `target_tools`: Flags determining which developer tools will receive this exported rule block during compilation.

---

## 4. Deep-Dive Standards Blueprint: Java & Spring Boot

Below is the structured markdown specification for `languages/java/spring-boot/error-handling.md`, precisely targeted at closing AI logic holes in backend systems.

```markdown
---
id: java-spring-error-handling
title: Spring Boot Structural Exception Handling and Anti-Patterns
version: 1.0.0
status: approved
scope:
  language: java
  framework: spring-boot
target_tools:
  cursor: true
  github_copilot: true
  claude_skills: true
---

# Spring Boot Structural Exception Handling and Anti-Patterns

## 1. Context & Architectural Intent
We utilize a centralized, strongly-typed error resolution architecture via Controller Advices. AI tools must ensure that errors are caught at systemic boundaries, mapped to domain expressions, and exposed with clean, non-leaky API contracts.

---

## 2. Enforced Standards (AI Ingestion Core)

### 2.1. Prohibition of Generic Runtime Exceptions
* **Rule**: You must NEVER instantiate or throw `java.lang.RuntimeException`, `java.lang.Exception`, or `java.lang.Throwable` directly.
* **Rationale**: Generic exceptions conceal root causes, force upstream callers into blind catches, and result in uninformative `500 Internal Server Error` API responses that leak zero context to consumer clients.
* **Implementation Requirement**: Always extend an abstract, system-wide base exception class that captures structural error states.

### 2.2. Prohibition of Blind/Generic Catch Blocks
* **Rule**: Catch blocks capturing `Exception` or `Throwable` without immediate rethrowing or explicit mapping are strictly forbidden.
* ```java
  // CRITICAL ANTI-PATTERN: NEVER GENERATE THIS
  try {
      orderService.process(order);
  } catch (Exception e) {
      log.error("Error occurred"); // Swallows the specific exception type
  }
  ```
* **Rationale**: Catching generic `Exception` intercepts unexpected runtime bugs (like `NullPointerException` or `OutOfMemoryError`), prevents transaction rollbacks from completing natively in Spring Data JPA, and hides system instability.
* **Implementation Requirement**: Always catch the narrowest specific checked or unchecked exception possible. If a high-level exception must be intercepted, it must wrap the original cause into a domain-specific exception.

### 2.3. Mandatory Unified Error Representation
* **Rule**: All REST error pathways must serialize payload models conforming strictly to the company `ApiErrorResponse` record format.
* **Implementation Requirement**:
  ```java
  public record ApiErrorResponse(
      String errorCode,
      String developerMessage,
      Map<String, String> fieldValidationErrors,
      Instant timestamp
  ) {}
  ```

---

## 3. AI Directives & Code Generation Prompt Templates

When generating, modifying, or refactoring Java code that involves error boundaries, controller layers, or transactional service methods, apply these structural laws:

1. **Verify Exception Specificity**: If an operations pipeline fails (e.g., database entity missing, invalid status transition), construct a custom nested domain exception within the domain boundary class (e.g., `EntityNotFoundException`, `InvalidStateTransitionException`).
2. **Enforce Global Controller Advice Handling**: Ensure that any newly introduced exception has a dedicated handler method matching inside the central `@RestControllerAdvice` class using the `@ExceptionHandler` binding annotation.
3. **Preserve Spring Transaction Isolation**: If you write a `try-catch` inside a method annotated with `@Transactional`, you must explicitly throw a nested runtime exception or manually trigger a programmatic rollback via `TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();`. Failing to do so breaks our database data integrity rules.
```

---

## 5. Automated Conversion & Rule Distribution Pipeline

The centralized repository manages the operational state of standards, decoupling rule authoring from client-side execution environments.

### The Lifecycle Pipeline
1. **Merge Event**: A pull request containing a new or updated Markdown rule is approved and merged into the `main` branch of `engineering-standards-central`.
2. **Compilation Script Execution**: A GitHub Action is triggered. It scans all modified files, parses the frontmatter yaml metadata, and validates schema compliance.
3. **Target Assembly & Minimization**: 
   * The compiler packages the global instructions and stack-scoped files into precise target files.
   * For the Java Spring Boot stack, it outputs a highly dense `.cursorrules` containing only Global Patterns + Core Java + Spring Boot rules.
4. **Distribution Push**: The unified files are pushed to a read-only distribution repository (`engineering-standards-distribution`).
5. **IDE Synchronization**: Developer workstations pull down these aggregated rules seamlessly into their local `.cursor/rules/` directory or global IDE skill profiles during their automated project synchronization cycle.
