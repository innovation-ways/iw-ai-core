# F-00055_S09_Tests_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S09
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — full doc; pay special attention to Acceptance Criteria (AC1–AC10), Boundary Behavior, and Invariants
- All previous step reports (`S01`–`S08`)
- `tests/conftest.py` — fixtures (session, project, PostgreSQL testcontainer)
- `tests/CLAUDE.md` — testing conventions, rules
- `orch/rag/qa.py`, `orch/rag/evidence.py`, `orch/rag/git_log_resolver.py`, `orch/rag/classifier.py` (as delivered in S03)
- `dashboard/routers/code_qa.py` (as modified in S05)
- `CLAUDE.md`

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S09_Tests_report.md`

## Context

Previous steps authored tight RED-GREEN tests for their own code. This step adds higher-order integration tests and the **evaluation set** that exercises the full pipeline end-to-end against realistic data, and fills any coverage gaps the reviewers flagged.

## Requirements

### 1. Integration test — full SSE flow

`tests/integration/test_code_qa_workitem_flow.py`:

- Spin up a PostgreSQL testcontainer (per `tests/CLAUDE.md`).
- Seed a project with 3 work items (1 feature, 1 CR, 1 incident), each with `design_doc_content` set.
- Seed a minimal LanceDB code table and docs table (or mock the LanceDB client — follow the existing pattern from `test_qa_engine.py`).
- POST to `/api/projects/{project_id}/code/qa` with `context_chips: ["why"]` and a question that matches the seeded items.
- Parse the SSE response and assert:
  - Event order: `phase:retrieving → phase:finding_items → phase:reading_docs → N × citation → phase:composing → token+ → done`.
  - `phase:finding_items` payload contains `count` ≥ 1.
  - Exactly 3 `citation` events with the 3 seeded work-item IDs.
  - Each citation has `work_item_type` and `work_item_id` fields.
  - At least one token event is emitted.
  - `done` arrives last.
- Assert Invariant 9 (project isolation): insert a fourth work item under a **different** project and confirm it does NOT appear in citations.

### 2. Integration test — slash override and classifier auto-detect

`tests/integration/test_code_qa_routing.py`:

- Case A (slash override, AC2): submit with `context_chips: ["why"]` and a query that looks like code ("show me parse_id"). Confirm the work-item-aware pipeline runs anyway (phase events present).
- Case B (classifier auto-detect, AC3): submit without chips with a behavior query ("why does the daemon retry 3 times?"). Confirm the work-item-aware pipeline runs (phase events present).
- Case C (default code-only, AC9): submit without chips with a structural query ("where is CodeIndexJob defined?"). Confirm NO phase events; token events only; no work-item citations.

Mock the LLM classifier for deterministic outputs — do not rely on a live Ollama call in CI.

### 3. Integration test — `/findusages` consolidation (AC7)

`tests/integration/test_code_qa_findusages.py`:

- Seed a project with a known symbol referenced in multiple work items.
- Submit with `context_chips: ["findusages"]` and a question containing the symbol name.
- Assert: symbol-hint flows to retrieval; code chunks containing the symbol rank highest; work-item citations for items that introduced/modified the symbol appear.

### 4. Boundary-behavior tests

One test per row of the Boundary Behavior table in the design doc. Create `tests/unit/test_f00055_boundaries.py` (or split across appropriate files):

- Empty `docs_{project_id}` — falls back to FTS + code; no crash.
- `design_doc_content = NULL` — summary-only fallback; feed row renders with `(no design document)` placeholder.
- Hallucinated citation — stripped + logged.
- File with no git-log match — resolver returns empty; pipeline still produces results.
- Low-confidence classifier — defaults to code-only.
- `/why` with zero matching items — emits `finding_items:count=0`; answer includes "no matching items"; no fictional items synthesized.
- Tone-switch before `done` — chip is disabled (frontend test, skip if no JS test infra).
- SSE connection drops mid-phase — router emits `error` event; no partial citations persist.
- Missing `docs_{project_id}` LanceDB table — graceful FTS-only fallback.
- Feed overflow (>5 items) — top-5 visible; overflow link renders.
- `project_id` with hyphens — table name conversion correct.

### 5. Evaluation set — `tests/fixtures/eval_set_f00055.json` + regeneration script

Curate at least 10 tuples using the **current iw-ai-core project** as the baseline, and ship a regeneration script so the fixture stays honest as the project's work items evolve.

**`scripts/regen_eval_set_f00055.py`** — a CLI script that:
- Connects to the configured platform DB (reads `IW_CORE_DB_*` env vars via `orch.config`; same pattern as `orch/cli/`).
- Queries `WorkItem` rows with `phase == 'done'` for the `iw-ai-core` project (or a `--project-id` flag, defaulting to `iw-ai-core`).
- Picks a maintainer-curated subset (the script reads a sibling `scripts/eval_set_f00055_curation.json` that lists question + must_cite IDs; the script fills in titles/summaries/expected_terms from the DB so the fixture stays in sync with the current titles).
- Writes the updated `tests/fixtures/eval_set_f00055.json`.
- Fails loudly if any `must_cite` ID in the curation file no longer exists in the DB (prevents silent rot).
- Includes a top-of-file docstring stating: "Run manually after significant work-item churn. NOT automatically invoked by tests."

Also: the fixture JSON gets a top-level `"_generated_at"` ISO timestamp and a `"_generator": "scripts/regen_eval_set_f00055.py"` marker so reviewers can see how stale it is. The eval-set runner (§6) checks the age and emits a test warning (not failure) if `> 180 days` old.

For each tuple:

```json
{
  "question": "why is the daemon polling interval 60 seconds?",
  "context_chips": ["why"],
  "expected_phase_sequence": ["retrieving", "finding_items", "reading_docs", "composing"],
  "must_cite_work_items": ["F-00001"],
  "may_cite_work_items": ["CR-00002", "F-00055"],
  "expected_terms": ["poll", "60", "daemon"]
}
```

Sourcing:
- Read `ai-dev/active/*/` and `orch/db/models.py` comments to find merged features.
- Reference concrete project items where possible — the eval set becomes a regression harness as more features land.
- Include at least 3 functional-register queries, 3 technical-register queries, 2 slash-override queries, and 2 queries that should route to the default code-only pipeline (as negative controls).

### 6. Evaluation runner — `tests/integration/test_code_qa_eval_set.py`

- Load `tests/fixtures/eval_set_f00055.json`.
- For each tuple, invoke the SSE endpoint and assert:
  - Phase sequence matches `expected_phase_sequence` (or is empty for the code-only negative-control tuples).
  - At least one ID in `must_cite_work_items` appears in emitted `citation` events.
  - Every term in `expected_terms` appears in the concatenated token stream (case-insensitive).
- Mock the LLM output for the token stream in CI (deterministic), but validate the retrieval and citation layers against real DB data.

### 7. No-regression tests

`tests/integration/test_code_qa_no_regression.py`:

- Replay a known code-only question that was working before F-00055 (e.g., from existing `test_qa_engine.py` fixtures).
- Assert bit-for-bit-equivalent SSE output: only `token` and `done` events; no `phase`; no work-item `citation`.
- Confirms AC9 and Invariant 3.

## Project Conventions

Read `tests/CLAUDE.md`:
- **NEVER** connect tests to live DB (port 5433) — testcontainers only.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **NEVER** mock the DB in integration tests.
- **MUST** replace psycopg2 URLs in testcontainers: `.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests that seed work items.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this to F-00055 in particular:
- BAD: `assert len(events["citation"]) > 0` (shape only — a hallucinated bundle passes)
- GOOD: `assert {"F-00042", "CR-00007"} <= {e["work_item_id"] for e in events["citation"]}` (semantic — verifies the expected IDs appear)
- BAD: `assert "phase" in event_types` (shape only — a single phase passes)
- GOOD: `assert event_types == ["retrieving", "finding_items", "reading_docs", "composing"]` (semantic — verifies the exact sequence and order from Invariant 2)
- BAD: `assert "daemon" in answer.lower()` (a generic match passes)
- GOOD: `assert all(term in answer.lower() for term in expected_terms)` AND `assert "[F-00042]" in answer_raw_tokens` (semantic — verifies every expected term plus the specific citation anchor)

## TDD Requirement

These tests are the verification layer. Some will fail against the S03/S05/S07 deliverables initially — that's fine; failures indicate real issues to be fixed in S12 (Final Review Fix). Report any pre-existing regressions you detect.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — must pass.
2. `make test-integration` — must pass (this step creates the integration suite; treat any failure as a blocker to report).
3. `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy orch/ dashboard/` — must pass.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_code_qa_workitem_flow.py",
    "tests/integration/test_code_qa_routing.py",
    "tests/integration/test_code_qa_findusages.py",
    "tests/integration/test_code_qa_eval_set.py",
    "tests/integration/test_code_qa_no_regression.py",
    "tests/unit/test_f00055_boundaries.py",
    "tests/fixtures/eval_set_f00055.json",
    "scripts/regen_eval_set_f00055.py",
    "scripts/eval_set_f00055_curation.json"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
