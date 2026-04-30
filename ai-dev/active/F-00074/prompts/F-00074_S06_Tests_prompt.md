# F-00074_S06_Tests_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S06
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Testcontainer fixtures are exempt from the Docker restriction.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md` — read first
- `ai-dev/active/F-00074/reports/F-00074_S04_API_report.md`
- `ai-dev/active/F-00074/reports/F-00074_S05_Frontend_report.md`
- `orch/keep_alive_service.py`
- `orch/daemon/keep_alive_poller.py`
- `dashboard/routers/keep_alive.py`
- `tests/conftest.py` — testcontainer fixtures
- `tests/CLAUDE.md` — strict rules (read before writing a single line)

## Output Files

- New: `tests/unit/test_keep_alive_service.py`
- New: `tests/integration/test_keep_alive_integration.py`
- New: `tests/dashboard/test_keep_alive_routes.py`
- `ai-dev/active/F-00074/reports/F-00074_S06_Tests_report.md`

## Context

Write comprehensive test coverage for the Keep-Alive Scheduler. Three test files covering unit (pure logic with mocks), integration (real testcontainer DB), and dashboard (FastAPI TestClient) layers. Follow `tests/CLAUDE.md` strictly — especially the testcontainer rules and the prohibition on connecting to port 5433.

## Requirements

### 1. `tests/unit/test_keep_alive_service.py`

Use `pytest` + `unittest.mock`. No database.

#### Due-slot detection (mock DB query results)

```python
def test_get_due_slots_fires_when_slot_in_window():
    # Slot at current time → returned

def test_get_due_slots_fires_when_slot_missed_within_30min():
    # Slot 25 minutes ago, no run today → returned

def test_get_due_slots_skips_when_slot_missed_beyond_30min():
    # Slot 35 minutes ago → not returned

def test_get_due_slots_skips_when_already_fired_today_success():
    # Slot due, but KeepAliveRun(status='success') exists for today → not returned

def test_get_due_slots_skips_when_already_fired_today_retried_success():
    # Slot due, but KeepAliveRun(status='retried_success') exists for today → not returned

def test_get_due_slots_fires_when_only_failed_run_today():
    # Slot due, only KeepAliveRun(status='failed') exists for today → returned (failure doesn't block retry)

def test_get_due_slots_skips_disabled_slot():
    # Slot.enabled=False → not returned
```

#### Retry logic (mock fire_claude)

```python
def test_poller_logs_success_on_first_attempt():
    # fire_claude returns (True, None) → log_run called with status='success'

def test_poller_retries_on_first_failure_success():
    # fire_claude returns (False, "err") first, (True, None) second → log_run called with status='retried_success'

def test_poller_logs_retried_failed_when_both_fail():
    # fire_claude returns (False, "err") twice → log_run called with status='retried_failed'

def test_poller_continues_after_one_slot_fails():
    # Two due slots; first fires and fails both retries; second fires successfully
    # Both log_run calls are made
```

#### Message randomization

```python
def test_pick_message_returns_string():
    assert isinstance(pick_message(), str)
    assert len(pick_message()) > 0

def test_pick_message_is_random():
    # Call 100 times, collect unique results; assert at least 3 distinct messages
    messages = {pick_message() for _ in range(100)}
    assert len(messages) >= 3
```

#### `fire_claude` (mock subprocess.run)

```python
def test_fire_claude_returns_true_on_success():
    # subprocess.run returns CompletedProcess(returncode=0) → (True, None)

def test_fire_claude_returns_false_on_nonzero():
    # returncode=1, stderr="error" → (False, "error")

def test_fire_claude_returns_false_on_timeout():
    # subprocess.run raises TimeoutExpired → (False, <exception str>)
```

#### Time parsing

```python
def test_add_slot_rejects_invalid_format():
    # "25:00", "5:00", "abc", "12:60" all raise ValueError
```

### 2. `tests/integration/test_keep_alive_integration.py`

Use testcontainer fixture from `tests/conftest.py`. **NEVER connect to port 5433.**

Remember: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` as required by `CLAUDE.md`.

After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` and `FTS_TRIGGER_SQL` if used by conftest.

```python
def test_get_config_creates_default_if_missing(db_session):
    # No row exists → get_config() creates and returns default (model='claude-sonnet-4-6', window_duration_hours=5)

def test_upsert_config_updates_without_duplicate(db_session):
    # First upsert: creates row. Second upsert: updates. Assert only one row exists.

def test_add_slot_creates_row(db_session):
    config = get_config(db_session)
    slot = add_slot(db_session, "10:02")
    assert slot.id is not None
    assert slot.time_hhmm == "10:02"
    assert slot.enabled is True

def test_add_slot_rejects_duplicate(db_session):
    add_slot(db_session, "10:02")
    with pytest.raises(IntegrityError):
        add_slot(db_session, "10:02")

def test_toggle_slot_flips_enabled(db_session):
    slot = add_slot(db_session, "05:00")
    assert slot.enabled is True
    toggled = toggle_slot(db_session, slot.id)
    assert toggled.enabled is False
    back = toggle_slot(db_session, slot.id)
    assert back.enabled is True

def test_delete_slot_nullifies_run_slot_id(db_session):
    slot = add_slot(db_session, "15:04")
    run = log_run(db_session, slot.id, "15:04", "success")
    delete_slot(db_session, slot.id)
    db_session.refresh(run)
    assert run.slot_id is None
    assert run.slot_time == "15:04"  # snapshot preserved

def test_get_recent_runs_returns_ten_newest(db_session):
    slot = add_slot(db_session, "20:06")
    for i in range(15):
        log_run(db_session, slot.id, "20:06", "success")
    runs = get_recent_runs(db_session, limit=10)
    assert len(runs) == 10
    # Ordered newest-first (assert fired_at descending)
    for i in range(len(runs) - 1):
        assert runs[i].fired_at >= runs[i+1].fired_at

def test_log_run_with_null_slot_id(db_session):
    run = log_run(db_session, None, "05:00", "retried_failed", error="claude not found")
    assert run.slot_id is None
    assert run.error == "claude not found"
```

### 3. `tests/dashboard/test_keep_alive_routes.py`

Use FastAPI `TestClient` with a testcontainer DB session override. Follow the pattern of other dashboard route tests.

```python
def test_get_keep_alive_page_returns_200(client):
    response = client.get("/system/keep-alive")
    assert response.status_code == 200
    assert "Keep-Alive Scheduler" in response.text

def test_post_config_valid(client):
    response = client.post("/api/keep-alive/config",
                           json={"model": "claude-sonnet-4-6", "window_duration_hours": 5})
    assert response.status_code == 200

def test_post_config_invalid_model(client):
    response = client.post("/api/keep-alive/config",
                           json={"model": "gpt-4", "window_duration_hours": 5})
    assert response.status_code == 422

def test_post_config_invalid_duration(client):
    response = client.post("/api/keep-alive/config",
                           json={"model": "claude-sonnet-4-6", "window_duration_hours": 99})
    assert response.status_code == 422

def test_post_slot_valid(client):
    response = client.post("/api/keep-alive/slots",
                           json={"time_hhmm": "10:02"})
    assert response.status_code == 200

def test_post_slot_invalid_format(client):
    response = client.post("/api/keep-alive/slots",
                           json={"time_hhmm": "25:00"})
    assert response.status_code == 422

def test_post_slot_duplicate(client):
    client.post("/api/keep-alive/slots", json={"time_hhmm": "10:02"})
    response = client.post("/api/keep-alive/slots", json={"time_hhmm": "10:02"})
    assert response.status_code == 409

def test_delete_slot_not_found(client):
    response = client.delete("/api/keep-alive/slots/99999")
    assert response.status_code == 404

def test_patch_toggle_not_found(client):
    response = client.patch("/api/keep-alive/slots/99999/toggle")
    assert response.status_code == 404

def test_get_runs_returns_200(client):
    response = client.get("/api/keep-alive/runs")
    assert response.status_code == 200
```

## Project Conventions

- NEVER call testcontainers from unit tests (unit tests are pure Python, no DB).
- NEVER connect to port 5433.
- Use `@pytest.mark.integration` for integration tests.
- Import from the service module directly in integration tests.
- `make test-unit` runs unit tests only; `make allure-integration` runs integration tests.

## Pre-flight Quality Gates

1. `make format`
2. `make lint`
3. `make typecheck`
4. `make test-unit` — all unit tests pass
5. `make allure-integration` — all integration tests pass

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "tests-impl",
  "work_item": "F-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_keep_alive_service.py",
    "tests/integration/test_keep_alive_integration.py",
    "tests/dashboard/test_keep_alive_routes.py"
  ],
  "preflight": {"format": "ok", "lint": "ok", "typecheck": "ok"},
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z dashboard passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
