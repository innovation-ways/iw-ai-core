# F-00091_S08_Tests_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S08
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations (the round-trip test for S04's migration was added in S04 itself).

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read AC1–AC4, Boundary Behavior, Invariants 1–7, TDD Approach)
- All prior step reports:
  - `ai-dev/work/F-00091/reports/F-00091_S01_API_report.md`
  - `ai-dev/work/F-00091/reports/F-00091_S02_Frontend_report.md`
  - `ai-dev/work/F-00091/reports/F-00091_S03_Frontend_report.md`
  - `ai-dev/work/F-00091/reports/F-00091_S04_Database_report.md`
  - `ai-dev/work/F-00091/reports/F-00091_S06_Backend_report.md`
  - `ai-dev/work/F-00091/reports/F-00091_S07_Frontend_report.md`
- `tests/CLAUDE.md`
- `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S08_Tests_report.md`

## Context

S01–S07 each added focused, RED-first tests for the contract they introduced. Your job is to extend coverage across the seams: cross-step integration cases that no single step's prompt covered. You are NOT re-creating S04's migration round-trip or S07's markup test — you are filling gaps surfaced by reading the design's Boundary Behavior and Invariants tables together.

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` BEFORE writing a single line. The IW AI Core testing skill contains the rules on assertion strength, testcontainer usage, the live-DB write guard, and the cross-project isolation pattern.

## Requirements

### 1. Integration test — cross-project chat-tabs isolation

Create `tests/integration/test_chat_panel_project_decoupling.py`:

- Use the testcontainer fixture from `tests/conftest.py`.
- Insert two `Project` rows (both enabled), and two `ChatTab` rows per project.
- Hit `GET /api/chat/tabs?project_id=<A>` — assert only project A's tabs appear.
- Hit `GET /api/chat/tabs?project_id=<B>` — assert only project B's tabs appear.
- Assert that mutating a tab in project A via `PATCH /api/chat/tabs/<id>` does not affect any tab in project B.
- Assert `GET /api/chat/projects` (from S01) returns BOTH project rows with the expected shape.

This test exists to lock down Invariant 4 and AC1's server-side contract.

### 2. Integration test — context-pct payload across runtimes

Create `tests/integration/test_chat_tabs_context_pct_payload.py`:

- Use the testcontainer fixture.
- For the Pi runtime: insert an `AgentRuntimeOption` row with `context_window_tokens=200000` for a synthetic Pi model; insert a `ChatTab` with `runtime='pi'` and `model='pi/<that model>'`; hit `GET /api/chat/tabs/{id}` with a mocked Pi runtime returning a session and two messages whose token shape resolves to a known percentage.
- Assert the response carries `session.context_pct_status == "known"` AND all four fields are populated AND Invariant 7 holds.
- Same fixture but with `context_window_tokens=NULL` → assert `context_pct_status == "unknown_window"`.
- Same fixture but with the Pi runtime mocked as `pi_healthy=False` → assert `context_pct_status == "unknown_runtime"`.

### 3. Boundary tests — Boundary Behavior table coverage check

For EVERY row in the design's Boundary Behavior table, confirm there is at least one test covering it (search test files added in S01–S07 and your two new files). If a row has NO coverage:

- Add a small test in the most appropriate file (or extend yours). Do NOT inflate by adding redundant tests for rows already covered.
- The "stream events during project switch" row is hard to exercise without a full browser harness — that's the S19 browser verification job. Note in your report that this row is covered by S19, not by an automated unit/integration test.

### 4. Cross-cutting smoke — TestClient render of the panel

Create `tests/dashboard/test_chat_panel_html_smoke.py`:

- Hit the home route `/`.
- Assert the served HTML contains:
  - `<select id="chat-assistant-project-select"` (S02 deliverable)
  - `<div id="chat-assistant-context-pct"` (S07 deliverable)
  - `.chat-assistant-context-pct__bar` (S07 deliverable)
  - **No reference to `_currentProjectId`** in the served `chat.js` (Invariant 1)

This is a smoke check; it does NOT exercise client-side JS execution. That is S19's domain.

### 5. Semantic Correctness Warning (I003)

> **SEMANTIC CORRECTNESS WARNING**: Tests must assert semantically correct behaviour, not merely that the code compiles or that HTTP 200 is returned. A test that only checks `assert response.status_code == 200` or `assert result is not None` provides no regression protection. Every test must make at least one specific, value-level assertion that would fail if the feature's behaviour regressed.

### 6. Verify assertion strength

For every test you add, apply the `iw-ai-core-testing` red-flag checklist:

- No `assert True`, no `assert response.status_code == 200` as the only assertion, no `assert response is not None` as the primary assertion.
- Every test asserts at least one specific value, shape, or absence claim that would only hold if the feature is correctly implemented.

### 7. Run only your new tests

```bash
uv run pytest \
  tests/integration/test_chat_panel_project_decoupling.py \
  tests/integration/test_chat_tabs_context_pct_payload.py \
  tests/dashboard/test_chat_panel_html_smoke.py \
  -v
```

Do NOT run the full unit or integration suites — those are QV gates S16/S18.

### 8. Do NOT modify production code

This step is tests only. If during writing you discover a code defect, raise it in `notes` and the consolidated CodeReview (S09) will route it for fix. Do NOT silently patch.

## Project Conventions

- testcontainers only (per CLAUDE.md): never connect tests to live DB on 5433.
- Replace `postgresql+psycopg2://` with `postgresql+psycopg://` in any testcontainer URL.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` if your test fixture builds the schema from models. The existing `conftest.py` does this — reuse the fixture, don't reinvent it.
- Use the cross-project isolation helpers (`pytest.fixture` `seed_two_projects`, etc.) if they exist; otherwise inline the inserts.

## TDD Requirement

This is the dedicated tests step — TDD `RED` evidence is `n/a` per the skill's exempt clause. State `"n/a — dedicated coverage step adding tests against already-implemented behaviour"` in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the test files you wrote:

```bash
uv run pytest \
  tests/integration/test_chat_panel_project_decoupling.py \
  tests/integration/test_chat_tabs_context_pct_payload.py \
  tests/dashboard/test_chat_panel_html_smoke.py \
  -v
```

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "tests-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_chat_panel_project_decoupling.py",
    "tests/integration/test_chat_tabs_context_pct_payload.py",
    "tests/dashboard/test_chat_panel_html_smoke.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step adding tests against already-implemented behaviour",
  "blockers": [],
  "notes": "Confirm in the report which Boundary Behavior rows are covered automated vs. via S19 browser verification."
}
```
