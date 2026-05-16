# CR-00056_S11_Tests_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. Testcontainers are exempt.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `TDD Approach` and `Acceptance Criteria`
- All S01..S10 reports
- `tests/CLAUDE.md` — test patterns, FTS trigger requirement, no live-DB rule, no `importlib.reload`
- `skills/iw-ai-core-testing/SKILL.md` — testing standards
- Existing fixture files in `tests/integration/conftest.py`, `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S11_Tests_report.md`

## Context

S01..S09 built the feature. S04 and S06 added one RED-first test each as TDD evidence. Your job is to add the **rest of the test coverage** — every AC must be covered by at least one test, and each test must be assertion-strong (no smoke tests).

## Read the Design Document FIRST

Re-read `TDD Approach` section. Every test file the design names by path MUST exist after this step. The files are:

- `tests/unit/test_step_run_prompt_columns.py`
- `tests/integration/test_daemon_prompt_snapshot.py` (started in S04 — extend it here)
- `tests/dashboard/test_prompt_modal_route.py` (started in S06 — extend it here)
- `tests/dashboard/test_item_steps_table_render.py` (new — for column-header / cell-rendering assertions)

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make format
make typecheck
make lint
```

## Requirements

### 1. Unit tests (`tests/unit/test_step_run_prompt_columns.py`)

```python
def test_step_run_accepts_prompt_text():
    # Constructing StepRun with prompt_text='...' does not raise; the attribute round-trips.

def test_step_run_accepts_fix_prompt_text():
    # Same, for fix_prompt_text.

def test_step_run_defaults_prompt_columns_to_none():
    # When constructed without those kwargs, both attributes are None.
```

Use SQLAlchemy in-memory or fixture session — these tests do NOT need a DB connection. The point is to prove the ORM model accepts the kwargs.

### 2. Integration tests (`tests/integration/test_daemon_prompt_snapshot.py`)

Extend the file started by S04 with:

- `test_initial_run_snapshots_prompt_text` — happy path (already added in S04 as RED; extend if S04 left it minimal).
- `test_initial_run_with_missing_prompt_file_sets_null_and_does_not_raise` — when prompt_file points to a non-existent path, the StepRun is still created with `prompt_text=None`.
- `test_fix_cycle_retry_snapshots_fix_prompt_text_and_preserves_base_prompt_text` — covers AC3 end-to-end.
- `test_qv_gate_step_run_has_null_prompt_text` — gate-style steps (with `command`/`gate` set, no prompt file) leave both columns NULL.

All tests use the `testcontainer_db` (or equivalent) fixture from `tests/integration/conftest.py`. NEVER connect to live DB port 5433.

After `Base.metadata.create_all()`, remember to run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` if your fixture inserts into `work_items` or `project_docs` (per `CLAUDE.md`).

### 3. Dashboard tests (`tests/dashboard/test_prompt_modal_route.py`)

Extend the file started by S06 with:

- `test_returns_200_with_initial_prompt_section` — happy path with one StepRun having `prompt_text`.
- `test_returns_200_with_initial_and_fix_sections` — covers AC7: a step with two StepRuns (run_number=1 with prompt_text, run_number=2 with fix_prompt_text). The response contains both labels in order.
- `test_returns_404_when_step_belongs_to_other_project` — covers AC9.
- `test_returns_404_when_step_has_no_prompt_text` — when no StepRun has any prompt text.
- `test_returns_404_when_item_id_mismatch` — same project, different item.
- `test_fragment_has_aria_modal_dialog` — response body contains `role="dialog"` AND `aria-modal="true"` AND `aria-labelledby="prompt-modal-title"`.
- `test_fragment_does_not_extend_base_html` — response body does NOT contain `<html` or `<!DOCTYPE` (fragment-only).
- `test_prompt_text_is_html_escaped` — feed a prompt containing `<script>alert(1)</script>`. Response body must contain `&lt;script&gt;` (escaped) and must NOT contain raw `<script>`.

Use FastAPI's `TestClient`. Use the existing `client` / `db` fixtures from `tests/dashboard/conftest.py`.

### 4. Template-render tests (`tests/dashboard/test_item_steps_table_render.py`)

If the existing dashboard test suite already covers `item_steps_table.html` rendering, extend that file. Otherwise create the new one.

- `test_prompt_column_header_present_between_model_and_status` — render the steps-table fragment with a fixture step that has `has_prompt=True`. The response HTML's `<th>` order is verifiable; the index of the new `<th>Prompt</th>` should be exactly the position between Model and Status.
- `test_synthetic_step_renders_dash_in_prompt_column` — for a synthetic step (e.g., S00), the prompt cell renders `—`, not a View button.
- `test_step_without_prompt_renders_dash` — for `has_prompt=False`, the cell renders `—`.
- `test_step_with_prompt_renders_view_button_with_correct_hx_get` — for `has_prompt=True`, the cell contains a `<button>` with `hx-get="/project/{pid}/item/{iid}/step/{step_id}/prompt-modal"` (exact URL match).
- `test_empty_state_colspan_matches_new_column_count` — the "No steps found" row's `colspan` equals the new header count.

### 5. Assertion strength rules (per `tests/CLAUDE.md`)

- No `assert response.status_code == 200` standing alone for a route that returns content — also assert on body content.
- No `assert "View" in response.text` without verifying it's in the right cell (use `BeautifulSoup` or precise regex).
- No "smoke tests" that exercise code but assert nothing meaningful.

### 6. NEVER

- Connect tests to live DB (port 5433). Use testcontainer fixtures.
- Use `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- Mock the database in integration tests.
- Run real LLM calls. (This CR doesn't add any, but stay alert.)

## TDD Requirement

Add tests for any test that's truly new behaviour. For pure "describe the existing static-render contract" tests, write them targeted (RED with the current implementation) — if they pass without any code change, ensure they're meaningful: do they catch a regression if you swap two columns or drop a button? If not, strengthen.

`tdd_red_evidence`: pick **one** new behavioural test and record its RED snippet. For pure coverage tests use `"n/a — coverage tests; no behavioural RED required for this batch"`.

## Test Verification (NON-NEGOTIABLE)

Run only the new/modified files:

```bash
uv run pytest tests/unit/test_step_run_prompt_columns.py -v
uv run pytest tests/integration/test_daemon_prompt_snapshot.py -v
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
uv run pytest tests/dashboard/test_item_steps_table_render.py -v
```

Do NOT run the full suite (S18/S19 QV gates own that).

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "CR-00056",
  "completion_status": "complete",
  "files_changed": [
    "tests/unit/test_step_run_prompt_columns.py",
    "tests/integration/test_daemon_prompt_snapshot.py",
    "tests/dashboard/test_prompt_modal_route.py",
    "tests/dashboard/test_item_steps_table_render.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_prompt_modal_route.py::test_returns_200_with_initial_and_fix_sections — AssertionError: 'Fix Prompt (cycle 1)' not in response.text",
  "blockers": [],
  "notes": ""
}
```
