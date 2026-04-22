# F-00058_S09_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S08 (tests-impl)
**Review Step**: S09

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (2026-04-22 incident).

Allowed:
  1. Testcontainers spun up by pytest fixtures (they self-destruct via Ryuk).
  2. Read-only introspection: docker ps | inspect | logs.
  3. Invocations through ./ai-core.sh or make targets.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule. If a testcontainer appears
stuck, rely on pytest teardown / Ryuk — never `docker kill` it.

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — Boundary Behavior + Invariants
- `ai-dev/active/F-00058/reports/F-00058_S08_Tests_report.md`
- Files listed in S08 report

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S09_CodeReview_report.md`

## Review Checklist

### 1. Coverage
- Every Boundary Behavior row has a dedicated test.
- Every Invariant (1–7) has at least one dedicated assertion.
- AC5 freshness scenarios exercised.
- SSE reconnect + heartbeat scenarios exercised.

### 2. Isolation (CLAUDE.md)
- Testcontainer Postgres, never the live DB on 5433.
- No `importlib.reload(orch.config)`.
- URL dialect replacement applied.
- FTS trigger installed post create_all().
- Tests order-independent.

### 3. TDD evidence
- S08 report's notes field should confirm red-before-green for new invariant / boundary tests.

### 4. Quality
- Test names describe behavior, not shape.
- Semantic assertions.
- Fixtures reused where sensible.
- No sleeps; SSE heartbeat tests use time mocks, not real time.

### 5. Performance
- Integration test file total runtime under 90s (SSE tests add overhead).

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make test-unit` + `make lint` pass.

## Review Result Contract

Standard JSON. `verdict: pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
