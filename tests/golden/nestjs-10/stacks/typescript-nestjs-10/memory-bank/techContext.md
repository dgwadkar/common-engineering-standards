# Tech Context — NestJS 10

Pre-populated by `engineering-standards-central` from the stack descriptor
`source/typescript/nestjs/_meta.yml`. Update via the central repo,
not in the consumer.

## Stack

- **Language**: typescript
- **Runtime**: Node.js 20 LTS
- **Framework**: NestJS 10.3.0
- **Stack id**: `typescript-nestjs-10`

_NestJS 10.x line._

## Required Dependencies

- `@nestjs/core`
- `@nestjs/common`
- `@nestjs/platform-express`
- `class-validator`
- `class-transformer`

## Optional Dependencies

- @nestjs/typeorm (when using TypeORM)
- @nestjs/swagger (for OpenAPI generation)

## Required Environment Variables

| Name | Description |
|---|---|
| `NODE_ENV` | Standard Node runtime mode flag. |
| `PORT` | HTTP port. |

## Local Development

Override in the consumer with project-specific bootstrap commands (Docker Compose,
DB seed scripts, etc.). The central baseline assumes only language- and framework-level
conventions.
