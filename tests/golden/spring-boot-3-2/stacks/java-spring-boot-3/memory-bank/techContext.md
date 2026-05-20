# Tech Context — Spring Boot 3

Pre-populated by `engineering-standards-central` from the stack descriptor
`source/java/spring-boot/_meta.yml`. Update via the central repo,
not in the consumer.

## Stack

- **Language**: java
- **Runtime**: Java 17 (LTS)
- **Framework**: Spring Boot 3.2.0
- **Stack id**: `java-spring-boot-3`

_Spring Boot 3.x line. Jakarta EE 10 (jakarta.* packages). Spring Framework 6.x._

## Required Dependencies

- `org.springframework.boot:spring-boot-starter-web`
- `org.springframework.boot:spring-boot-starter-data-jpa`
- `org.springframework.boot:spring-boot-starter-validation`
- `org.springframework.boot:spring-boot-starter-actuator`

## Optional Dependencies

- org.projectlombok:lombok (only if the project elects to use Lombok per the di rule)
- io.micrometer:micrometer-tracing (for the logging-telemetry rule)
- org.testcontainers:junit-jupiter (for the testing rule)

## Required Environment Variables

| Name | Description |
|---|---|
| `SPRING_DATASOURCE_URL` | JDBC URL for the primary application datasource. |
| `SPRING_DATASOURCE_USERNAME` | Datasource credentials. Production setups MUST source these from a secret manager. |
| `SPRING_DATASOURCE_PASSWORD` | Datasource credentials. Never commit literal values. |
| `SPRING_PROFILES_ACTIVE` | Comma-separated active profiles (e.g., 'prod,observability'). |

## Local Development

Override in the consumer with project-specific bootstrap commands (Docker Compose,
DB seed scripts, etc.). The central baseline assumes only language- and framework-level
conventions.
