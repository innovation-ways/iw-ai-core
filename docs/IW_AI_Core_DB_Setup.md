# IW AI Core — Database Setup

> **⚠️ 2026-04-22 incident**: A contributor ran `docker compose down` against the shared development PostgreSQL container, causing multi-hour outage and data loss for all developers on the project. This document exists to prevent recurrence.

## Production path

The shared development database runs as a raw Docker container on port 5433. It is **not** managed by `docker compose`.

```bash
docker run -d \
  --name iw-postgres \
  -e POSTGRES_PASSWORD=iw \
  -e POSTGRES_USER=iw \
  -e POSTGRES_DB=iw_core \
  -v iw-postgres-data:/var/lib/postgresql/data \
  -p 5433:5433 \
  postgres:15
```

Do NOT use `docker compose` for this container. Do NOT `docker compose down`, `docker compose rm`, or any equivalent commands against it.

## Bootstrap compose path (fresh dev machines only)

For a brand-new development environment where no container exists at all, a bootstrap compose file is provided as a fallback:

```bash
docker compose -f docker-compose.bootstrap.yml up -d
```

This path is for **initial setup only**. Once the container is running, use the raw Docker commands above to manage it.

## Related policy

- [`docs/IW_AI_Core_Agent_Constraints.md`](IW_AI_Core_Agent_Constraints.md) — the
  Docker-is-off-limits rule that restricts agent behavior around this DB.
