# CR-00056_S12_CodeReview_Tests_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — `TDD Approach` + `Acceptance Criteria`
- `ai-dev/work/CR-00056/reports/CR-00056_S11_Tests_report.md`
- All test files in S11 `files_changed`
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S12_CodeReview_report.md`

## Context

You are reviewing the test coverage added in S11 against the design's `Acceptance Criteria` and `TDD Approach`.

## Read the Design Document FIRST

Build the AC × test matrix:

| AC | Required behaviour | Test file → test name |
|---|---|---|
| AC1 | Schema columns exist | implicit (S03 migration-check) + `test_step_run_prompt_columns.py` |
| AC2 | Initial run snapshots prompt | `test_daemon_prompt_snapshot.py::test_initial_run_snapshots_prompt_text` |
| AC3 | Fix-cycle snapshots fix prompt + base prompt | `test_daemon_prompt_snapshot.py::test_fix_cycle_retry_*` |
| AC4 | Prompt column renders with View/— | `test_item_steps_table_render.py::test_prompt_column_header_present_*` + `test_step_with_prompt_renders_view_button_*` |
| AC5 | Modal returns 200 with `<pre>` + aria | `test_prompt_modal_route.py::test_returns_200_*` + `test_fragment_has_aria_modal_dialog` |
| AC6 | Dismissal a11y | qv-browser S22 (frontend behaviour, not unit-testable) |
| AC7 | Stacked Initial + Fix sections | `test_prompt_modal_route.py::test_returns_200_with_initial_and_fix_sections` |
| AC8 | Copy works | qv-browser S22 |
| AC9 | 404 on project mismatch | `test_prompt_modal_route.py::test_returns_404_when_step_belongs_to_other_project` |

Any AC without a covering test (excluding the two delegated to qv-browser) → CRITICAL.

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Coverage matrix completeness

Walk the table above. Any missing AC → CRITICAL "missing test for AC{N}".

### 2. Assertion strength (per `tests/CLAUDE.md` + iw-ai-core-testing skill)

- Tests assert on **specific content**, not just status codes.
- HTML assertions use `BeautifulSoup` or precise regex, not `"View" in response.text` substring soup.
- No "tautological" assertions (`assert x == x`).
- No tests that exercise code but assert nothing meaningful (smoke tests are forbidden).

### 3. Test isolation

- Integration tests use the project's testcontainer fixture (`testcontainer_db` or similar).
- No test connects to live DB port 5433 — grep:
  ```bash
  grep -RIn '5433' tests/  # MUST be zero hits in new test files
  ```
- No test calls `importlib.reload(orch.config)` — grep:
  ```bash
  grep -RIn 'importlib.reload' tests/
  ```
  Should be zero.
- Tests are deterministic (no `time.sleep()` for flakiness, no real network).

### 4. Fixture usage

- Dashboard tests use `TestClient` from `tests/dashboard/conftest.py`.
- Integration tests reset DB state between tests (transactional rollback or truncate).
- After `Base.metadata.create_all()` in any fixture: `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` are run if `work_items` or `project_docs` rows are inserted (per `CLAUDE.md`).

### 5. Database driver discipline

- No `psycopg2` imports in tests — grep:
  ```bash
  grep -RIn 'psycopg2' tests/
  ```
  Should be zero in new files.
- Testcontainer URL replacements: `"postgresql+psycopg2://"` → `"postgresql+psycopg://"` (per `CLAUDE.md`). If S11 added any URL construction, confirm.

### 6. XSS test exists

- One test feeds a prompt containing `<script>` and asserts the rendered fragment contains `&lt;script&gt;` (escaped). If absent, CRITICAL.

### 7. TDD RED evidence

- For at least one new behavioural test, `tdd_red_evidence` records a plausible AssertionError snippet. If the field uses the `n/a` form, the reasoning must justify it (e.g., coverage tests for an existing static contract).

## Test Verification (NON-NEGOTIABLE)

Run only S11's files:

```bash
uv run pytest tests/unit/test_step_run_prompt_columns.py -v
uv run pytest tests/integration/test_daemon_prompt_snapshot.py -v
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
uv run pytest tests/dashboard/test_item_steps_table_render.py -v
```

All must pass. Any failure → CRITICAL.

## Review Result Contract

```json
{
  "step": "S12",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S11",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
