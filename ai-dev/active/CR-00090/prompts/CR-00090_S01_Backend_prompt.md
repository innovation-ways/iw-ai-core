# CR-00090_S01_Backend_prompt

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S01
**Agent**: backend-impl

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
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration is required for this CR. Do not create or modify any Alembic
migration file.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00090 --json`
- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document (authoritative spec)
- `orch/config.py` — Module where `get_e2e_mode()` is added
- `dashboard/app.py` — Module where `_e2e_mode` global is injected

## Output Files

- `ai-dev/active/CR-00090/reports/CR-00090_S01_Backend_report.md` — Step report

## Context

You are implementing the backend changes for CR-00090. Read the design document
first — it is the authoritative spec.

The problem: HTMX polling on `worktree-badge` and `staleness-dot` elements fires
during E2E browser verification runs, causing `ERR_CONNECTION_REFUSED` errors when
the E2E container restarts between fix cycles. Templates tried to suppress polling
by checking the browser User-Agent for `headlesschrome` or `playwright`, but modern
Playwright v1.27+ with `--headless=new` sends a normal Chrome UA — the detection
always returns False.

The fix: add an explicit `IW_CORE_E2E_MODE` env var that the compose template injects
into the E2E app container. Read it in `orch/config.py` and inject the result into
the global Jinja2 template context in `dashboard/app.py`.

## Requirements

### 1. Add `get_e2e_mode()` to `orch/config.py`

Add a new public function at module level, following the existing pattern of other
`get_*()` functions in the file:

```python
def get_e2e_mode() -> bool:
    return os.environ.get("IW_CORE_E2E_MODE", "").lower() in ("1", "true")
```

Rules:
- Values `"true"`, `"1"`, `"TRUE"` (case-insensitive) → `True`
- Absent, empty, or any other value → `False`
- Use `os.environ.get()` — do NOT call `importlib.reload()` (critical rule in CLAUDE.md)
- The function reads the env var at call time (not at import time) so tests can
  monkeypatch it via `monkeypatch.setenv()` or `monkeypatch.delenv()`

### 2. Inject `_e2e_mode` into the global Jinja2 template context in `dashboard/app.py`

Locate the block where `templates.env.globals` is populated (it already sets
`is_db_stale` and `static_v`). Add one line immediately after those, importing
`get_e2e_mode` from `orch.config`:

```python
templates.env.globals["_e2e_mode"] = get_e2e_mode()
```

The variable name MUST be `_e2e_mode` (underscore prefix — matches the convention
used by the existing template global `_headless`). This makes it available in every
Jinja2 template without requiring each route handler to pass it explicitly.

Read `dashboard/app.py` carefully to identify the exact injection site. The
injection must happen at application startup (not per-request). Calling
`get_e2e_mode()` once at startup is correct — the E2E flag is an immutable property
of the container's environment, not a per-request value.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:
- Module-level function pattern in `orch/config.py`
- App startup lifecycle in `dashboard/app.py`
- Import conventions

NEVER use `importlib.reload(orch.config)` — see the CRITICAL rule in CLAUDE.md.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first in `tests/unit/test_config.py`:
   - Parametrize `get_e2e_mode()` over `IW_CORE_E2E_MODE` values:
     `"true"` → True, `"1"` → True, `"TRUE"` → True, `""` → False, `"false"` → False, absent → False
   - Run the targeted test file: `uv run pytest tests/unit/test_config.py::test_get_e2e_mode -v`
   - Confirm: `AttributeError: module 'orch.config' has no attribute 'get_e2e_mode'` (or similar)
   - Record the RED output in your report's `tdd_red_evidence` field

2. **GREEN**: Add `get_e2e_mode()` to `orch/config.py`. Re-run; all param cases pass.

3. **REFACTOR**: No refactor needed for a one-liner function.

For the `dashboard/app.py` injection, no new test is needed at this step — the
dashboard tests (`tests/dashboard/test_e2e_mode.py`) that verify context injection
are written in S03.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors in files you touched
3. `make lint` — must report zero errors

## Test Verification (NON-NEGOTIABLE)

Run ONLY the targeted unit test (do NOT run the full suite):

```bash
uv run pytest tests/unit/test_config.py -v -k "e2e"
```

Report exact results in your result contract.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/config.py",
    "dashboard/app.py",
    "tests/unit/test_config.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_config.py::test_get_e2e_mode — AttributeError: ...",
  "blockers": [],
  "notes": ""
}
```
