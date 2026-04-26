# F-00063_S02_CodeReview_Backend_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers in pytest fixtures; read-only `docker ps`/`inspect`/`logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orchestration DB. Read-only alembic commands and `alembic revision --autogenerate` are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- `ai-dev/active/F-00063/reports/F-00063_S01_Backend_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S02_CodeReview_report.md`

## Context

You are reviewing the backend foundation built in S01: `orch/staleness/` package, `project_registry.py` extension, the dashboard self-restart helper, and the `projects.toml` seed.

Read the design doc and the S01 report. Then review every file the implementer touched.

## Review Checklist

### 1. Architecture Compliance

- Is `orch/staleness/` a clean module without cross-layer imports? Specifically: it must not import from `dashboard/` (one-way: dashboard → orch).
- Does it follow the conventions in `orch/CLAUDE.md` (SQLAlchemy 2.0 sync style if any DB use; psycopg v3; dotenv at module import; no async)?
- Is the staleness config validation in `project_registry.py` non-breaking — does it log and skip on bad config rather than refusing to load the entire registry?

### 2. Code Quality

- Subprocess invocations: every shell-out has an explicit timeout and `check=False`. No `shell=True` with interpolation of user/config strings (command-injection vector — `restart_command` is operator-controlled but still: the BACKEND step does not invoke the commands; that is S03's concern).
- Detection engine handles all four `detect.type` values; all unknown types raise from config parsing, never reach detection.
- Path handling: `pathlib.Path` throughout; `repo_root.resolve()` used for cwd cross-check; no string concatenation of paths.
- Time handling: UTC `datetime` everywhere; explicit `tzinfo=timezone.utc` on `datetime.fromtimestamp`.
- `compute_project_staleness` re-reads `projects.toml` on every call (no module-level cache).
- Error handling: detection failures return None / status="not_running" / "unknown" rather than raising. Alembic `unreachable` status correctly distinguished from `stale`.

### 3. Project Conventions

- ruff and mypy clean for all new files.
- Imports organised (stdlib → third-party → first-party).
- Naming follows existing project style (snake_case for modules and functions, PascalCase for dataclasses).
- Docstrings on public functions, brief and useful (no "Sets the value of x" filler).

### 4. Security

- `restart_command`/`start_command`/`stop_command` are config-only strings; the backend step does NOT execute them — confirm.
- No hardcoded secrets, ports, or credentials.
- Subprocess timeouts present everywhere.
- Reading `/proc` is purely informational; no escalation paths.

### 5. Testing

- TDD evidence: test files exist for every public function in the new package (`test_config.py`, `test_detection.py`, `test_git_lookup.py`, `test_alembic_check.py`, `test_service.py`).
- Tests cover at least: each `detect.type`, cwd-outside-repo rejection, multiple-pgrep-match warning, stale pidfile, gitignore-style include/exclude, alembic up-to-date / stale / unreachable, opt-out projects.
- Tests use temp git repos and mocked subprocess; no live `git` command on the iw-ai-core repo itself, no live `alembic` against port 5433.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green
2. `make lint`
3. `make typecheck`

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality / data loss / security | Must fix |
| HIGH | Significant bug / missing requirement | Must fix |
| MEDIUM_FIXABLE | Code quality / convention violation / missing edge case | Must fix |
| MEDIUM_SUGGESTION | Optional improvement | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict` = `pass` only when zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
