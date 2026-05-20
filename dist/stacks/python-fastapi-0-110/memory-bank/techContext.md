# Tech Context — FastAPI 0.110

Pre-populated by `engineering-standards-central` from the stack descriptor
`source/python/fastapi/_meta.yml`. Update via the central repo,
not in the consumer.

## Stack

- **Language**: python
- **Runtime**: Python 3.12
- **Framework**: FastAPI 0.110.0
- **Stack id**: `python-fastapi-0-110`

_FastAPI 0.110.x line._

## Required Dependencies

- `fastapi`
- `pydantic>=2.0`
- `uvicorn[standard]`

## Optional Dependencies

- sqlalchemy[asyncio] (when using SQLAlchemy)
- alembic (for migrations)
- httpx (for outbound HTTP calls)

## Required Environment Variables

| Name | Description |
|---|---|
| `ENV` | Environment tag (dev/staging/prod). |
| `DATABASE_URL` | Database URL for the application datasource. |

## Local Development

Override in the consumer with project-specific bootstrap commands (Docker Compose,
DB seed scripts, etc.). The central baseline assumes only language- and framework-level
conventions.
