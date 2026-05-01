# I-00057_S03_Tests_prompt

**Work Item**: I-00057 -- Chat panel collapse toggle is intrusive and panel starts open
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Testcontainers via pytest fixtures allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00057 --json`
- `ai-dev/active/I-00057/I-00057_Issue_Design.md`
- `ai-dev/active/I-00057/reports/I-00057_S01_Frontend_report.md`
- `dashboard/templates/chat/panel.html` (post-S01)
- `tests/CLAUDE.md`, `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/active/I-00057/reports/I-00057_S03_Tests_report.md`
- `tests/dashboard/test_chat_panel_default_collapsed.py` (new)

## Context

Server-rendered HTML test for the chat panel. JS-driven behavior (localStorage round-trip) is covered by S11's browser verification — there's no JS unit harness in this repo.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify **specific values**:

- BAD: `assert "data-collapsed" in html` — passes regardless of whether it's `"true"` or `"false"`.
- GOOD: `assert 'data-collapsed="true"' in html` — proves the panel ships collapsed.
- BAD: `assert "chat-toggle-tab" not in html` — fails on a different ID. We want to assert the absolute-positioning pattern is gone.
- GOOD: `assert 'style="left: -48px;"' not in html` — guards against the actual visual bug.
- BAD: `assert "Expand" in html` — too loose, could match unrelated text.
- GOOD: `assert 'aria-label="Expand chat panel' in html` — proves the expand affordance exists with the right label.

## Requirements

### 1. Dashboard test: panel ships collapsed; no floating tab

Create `tests/dashboard/test_chat_panel_default_collapsed.py`. Use the existing dashboard test conventions (`tests/dashboard/conftest.py` — `client`, `db`, project fixtures). Read `tests/CLAUDE.md` for required FTS setup.

```python
def test_i00057_chat_panel_ships_collapsed(client, db):
    """RED until I-00057 lands. Asserts the chat panel renders with
    data-collapsed='true' so the user lands on a slim rail, not a wide
    open panel."""
    project = make_project(db, "p")
    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="chat-panel"' in html
    assert 'data-collapsed="true"' in html
    assert 'data-collapsed="false"' not in html


def test_i00057_no_floating_left_minus_48_toggle(client, db):
    """Guards against the absolute-positioned tab pattern returning."""
    project = make_project(db, "p")
    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    # Original bug: <button id="chat-toggle-tab" style="left: -48px;">
    assert 'style="left: -48px;"' not in html
    # The id itself should be gone — collapse/expand affordances live inside #chat-panel now.
    assert 'id="chat-toggle-tab"' not in html


def test_i00057_collapse_and_expand_affordances_present(client, db):
    """Both modes must offer a labelled control to toggle state."""
    project = make_project(db, "p")
    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    assert 'aria-label="Collapse chat panel' in html  # in expanded header
    assert 'aria-label="Expand chat panel' in html    # in collapsed rail
```

If the project's existing dashboard fixtures use a different `make_project` / project fixture name, reuse what's there — don't invent new fixtures.

### 2. Run the local gate

```bash
make test-unit
make test-integration   # if green on main
make lint && make typecheck
```

## Project Conventions

Read `tests/CLAUDE.md`. Critical rules:

- NEVER connect tests to the live DB (port 5433). Testcontainers only.
- Replace psycopg2 URLs with psycopg in testcontainers.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Don't mock the DB.

## Pre-flight Quality Gates

```bash
make format
make typecheck
make lint
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_chat_panel_default_collapsed.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
