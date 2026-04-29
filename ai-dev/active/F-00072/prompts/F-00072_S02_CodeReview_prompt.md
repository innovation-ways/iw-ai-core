# F-00072_S02_CodeReview_prompt

**Work Item**: F-00072 -- Pragmatic Migration Safety + Schema Validation
**Step Being Reviewed**: S01
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00072/F-00072_Feature_Design.md`
- `ai-dev/active/F-00072/reports/F-00072_S01_Backend_report.md`
- `tests/integration/test_migration_roundtrip.py`
- `.github/workflows/schema-validation.yml`
- Doc note (in either `docs/IW_AI_Core_Daemon_Design.md` or `tests/CLAUDE.md`)

## Output Files

- `ai-dev/active/F-00072/reports/F-00072_S02_CodeReview_report.md`

## Review Checklist

### 1. Test correctness

- [ ] Parametrises over the latest 3 revisions, dynamically read from `alembic history` (no hardcoded list).
- [ ] Handles fewer-than-3 revisions case (slice doesn't crash).
- [ ] Test ID includes revision short SHA.
- [ ] Each parametrized run executes upgrade(rev) -> downgrade(-1) -> upgrade(head).
- [ ] Final schema check verifies `Base.metadata` tables exist.
- [ ] Marked with `@pytest.mark.integration` so it runs under `make test-integration`.

### 2. Live-DB safety

- [ ] Test does NOT connect to live DB on port 5433. Verify by reading the URL/env construction.
- [ ] Uses its own module-scoped `PostgresContainer` (NOT the shared session-scoped `db_engine` from integration/conftest.py, which runs `Base.metadata.create_all()` and is incompatible).
- [ ] No `importlib.reload(orch.config)` (forbidden by `tests/CLAUDE.md`).
- [ ] Uses `psycopg` (not `psycopg2`) — string replacement performed if needed.
- [ ] Uses `pytest.MonkeyPatch.context()` to set `IW_CORE_DB_*` env vars (per `test_iw_core_instance_migration.py` pattern).
- [ ] Uses `alembic.command` Python API (not subprocess) — per established pattern.
- [ ] Rule 4a compliance: downgrade uses explicit parent revision ID from `ScriptDirectory`, **never** `-1`.

### 3. Workflow correctness

- [ ] `permissions: contents: read` only.
- [ ] Postgres service image major matches `docker-compose.bootstrap.yml`.
- [ ] All `uses:` are pinned to 40-char SHAs.
- [ ] Pin comments in `# vN.N.N` form per repo convention.
- [ ] Service container has healthcheck.
- [ ] Steps: checkout, install uv, sync deps, alembic upgrade head, alembic check.
- [ ] Triggers on PR + push to main.

### 4. No-edit invariant

- [ ] Adding a new migration would NOT require editing `test_migration_roundtrip.py` or `schema-validation.yml`. Verify by reading the implementation.

### 5. Documentation

- [ ] Note added (≤80 words) to either `docs/IW_AI_Core_Daemon_Design.md` or `tests/CLAUDE.md`.
- [ ] Mentions the latest-3 window and `alembic check`.

### 6. Conventions

- Read `tests/CLAUDE.md`, `CLAUDE.md`, `docs/IW_AI_Core_Agent_Constraints.md`.

## Test Verification

- `make lint`
- `make typecheck`
- `make test-unit`
- `make test-integration` (the new test must pass)

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Test connects to live DB; uses `-1` for downgrade (rule 4a violation); SHAs not pinned; workflow has elevated permissions |
| HIGH | Hardcoded revision list; no integration marker; missing alembic check; uses subprocess instead of alembic.command API; uses shared db_engine fixture (Base.metadata.create_all bypasses alembic) |
| MEDIUM (fixable) | Missing fewer-than-3 handling; missing pin comments; no `downgrade base` reset before each parametrized case |
| MEDIUM (suggestion) | Refactor opportunity |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00072",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
