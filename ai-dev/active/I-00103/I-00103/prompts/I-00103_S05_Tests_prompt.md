# I00103_S05_Tests_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in pytest are the only allowed exception. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document (TDD Approach section pins exact test file names and cases).
- `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md` -- Backend report (confirms the `per_file_errors` schema landed).
- `ai-dev/active/I-00103/reports/I-00103_S03_Frontend_report.md` -- Frontend report (confirms the class name and rendering shape).
- `orch/daemon/auto_merge.py` -- Source under test for the integration test.
- `dashboard/templates/fragments/auto_merge_event_detail.html` -- Source under test for the dashboard tests.
- `tests/integration/test_auto_merge_phase1.py` -- **Reference pattern.** Its `test_ac4_operator_ux_unchanged_on_llm_error` / `test_ac4_operator_ux_unchanged_on_abstain` already drive `attempt_resolution` to the `merge_auto_resolution_failed` event. Mirror its fixture usage exactly.
- `tests/integration/conftest.py` -- For the testcontainer-backed `db_session` used by the integration test.
- `tests/dashboard/conftest.py` -- For the `client` fixture used by the dashboard tests.
- `tests/fixtures/auto_merge_observability/fixtures.py` -- The FakeLLM fixture that replaces `invoke_llm_for_file` in the integration tests.
- `skills/iw-ai-core-testing/SKILL.md` (or `.claude/skills/iw-ai-core-testing/SKILL.md`) -- Project testing standards and red-flag checklist.

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S05_Tests_report.md` -- Step report.
- `tests/integration/test_auto_merge_failed_event_metadata.py` -- New integration test file.
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` -- New dashboard test file.

## Context

You are writing the **reproduction test** (would fail before S01) and the **regression tests** (pin behaviour going forward) for I-00103. Both layers — event-payload schema (backend) and template rendering (dashboard) — need test coverage.

Read `ai-dev/active/I-00103/I-00103_Issue_Design.md` fully. The §TDD Approach section names every test by path and by purpose; reproduce that table exactly.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "per_file_errors" in metadata` (shape only — would pass even if the list were `[{}]`)
- GOOD: `assert "LLM call timed out after 120s" in metadata["per_file_errors"][0]["error"]` (semantic — verifies the literal expected substring is present)
- GOOD: `assert metadata["per_file_errors"][0]["file_path"] == "tests/dashboard/test_auto_merge_routes.py"` (semantic — exact expected path)
- GOOD: `assert metadata["per_file_errors"][0]["cli_tool"] == "opencode"` (semantic — exact expected runtime)

### CRITICAL: CSS class assertions must be attribute-scoped (I-00067 lesson)

For dashboard tests, do NOT use bare-substring assertions like `assert "per-file-error" in html`. Bare substrings false-positive against `<script>` tag contents, `data-*` attributes, HTML comments, or CSS source maps. Use:

```python
assert 'class="auto-merge-modal__per-file-error"' in html
# OR a regex anchored on the attribute:
assert re.search(r'class\s*=\s*"[^"]*auto-merge-modal__per-file-error[^"]*"', html)
```

This is enforced in the design doc's TDD Approach note.

## Requirements

### 1. Reproduction test (integration) — `tests/integration/test_auto_merge_failed_event_metadata.py`

This file MUST contain at least the four cases listed in the design doc's §TDD Approach `Integration tests` block:

1. `test_i00103_failed_event_carries_per_file_error_strings` — the **reproduction** test. Invoke the auto-merge failed-event emission path (preferred: monkeypatch `invoke_llm_for_file` to return a synthetic `LLMCallResult` with `error="LLM call timed out after 120s: <exc>"`, `file_path="tests/dashboard/test_auto_merge_routes.py"`, `cli_tool="opencode"`, `model="minimax/MiniMax-M2.7"`; call `attempt_resolution(...)` in phase=1 mode). Read the latest `merge_auto_resolution_failed` DaemonEvent. Assert (semantic, not shape):
   - `event.event_metadata["per_file_errors"]` is a list of length 1.
   - `entry = event.event_metadata["per_file_errors"][0]`
   - `entry["file_path"] == "tests/dashboard/test_auto_merge_routes.py"`
   - `"LLM call timed out after 120s" in entry["error"]`
   - `entry["cli_tool"] == "opencode"`
   - `entry["model"] == "minimax/MiniMax-M2.7"`

2. `test_per_file_errors_truncated_at_500_chars` — feed an `LLMCallResult` with `error="x" * 2000`; assert `len(metadata["per_file_errors"][0]["error"]) == 500`. (Exact equality, not `<= 500` — the implementation slices `[:500]`.)

3. `test_per_file_errors_only_includes_errored_calls` — feed an `llm_calls` list with one error, one ABSTAIN, one proposed-content success (or whatever combination is needed to trigger the failed-event path — likely error + abstained). Assert `len(metadata["per_file_errors"]) == 1` AND that the single entry corresponds to the errored call. The ABSTAIN/success entries MUST NOT appear in `per_file_errors`.

4. `test_per_file_errors_absent_or_empty_when_no_calls_errored` — trigger the failed event via abstention only (no errors). Assert that `metadata.get("per_file_errors", [])` is either missing or `[]`. The existing `abstained_files` continues to carry the data.

**Test placement** — `tests/integration/` is **mandatory** for this file. The test drives `attempt_resolution(...)` → `_emit_event()` → `db.commit()` and then reads the persisted `DaemonEvent` JSONB metadata back, so it needs the testcontainer-backed `db_session` from `tests/integration/conftest.py`. It MUST NOT go under `tests/unit/`: the `tests/unit/conftest.py` `db_session` is a `MagicMock`, and the semantic assertions below cannot run against a mock. Mirror `tests/integration/test_auto_merge_phase1.py` for fixture wiring (`db_session` + FakeLLM). The dashboard tests still go under `tests/dashboard/` because they use the FastAPI `client` fixture (I-00067).

### 2. Dashboard tests — `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`

Three cases as per the design doc's §TDD Approach `Dashboard tests` block:

1. `test_event_detail_renders_per_file_errors_section_when_present` — Seed a `merge_auto_resolution_failed` DaemonEvent in the test DB whose `metadata` contains:
   ```python
   {
     "phase": 1,
     "abstained_files": [],
     "error_files": ["tests/dashboard/test_auto_merge_routes.py"],
     "proposed_files": [],
     "runtime_option_id": 1,
     "total_input_tokens": 0,
     "total_output_tokens": 0,
     "per_file_errors": [
       {
         "file_path": "tests/dashboard/test_auto_merge_routes.py",
         "error": "LLM call timed out after 120s: subprocess.TimeoutExpired(...)",
         "cli_tool": "opencode",
         "model": "minimax/MiniMax-M2.7",
       },
     ],
   }
   ```
   GET `/project/<test_project.id>/auto-merge/events/<event_id>`. Assert:
   - HTTP 200.
   - `assert 'class="auto-merge-modal__per-file-errors"' in html` (or whatever section class S03 used — derive from S03's report; if the class name differs, update the assertion to match).
   - `assert "LLM call timed out after 120s" in html` (semantic — the literal error substring renders).
   - `assert "tests/dashboard/test_auto_merge_routes.py" in html` (file path renders).
   - `assert "opencode/minimax/MiniMax-M2.7" in html` OR `assert "opencode" in html and "minimax/MiniMax-M2.7" in html` (runtime label renders, depending on S03's formatting choice).

2. `test_event_detail_hides_per_file_errors_section_when_absent` — Seed an event WITHOUT the `per_file_errors` key (historical shape: just the 7 keys originally in events 80689 / 88770). GET the detail route. Assert:
   - HTTP 200.
   - `assert 'class="auto-merge-modal__per-file-errors"' not in html` (attribute-scoped — the section is NOT rendered).
   - No template exception. (Implicit via HTTP 200.)

3. `test_event_detail_hides_per_file_errors_section_when_empty_list` — Same as case 2 but with `per_file_errors: []` (empty list, not missing). Same assertions: HTTP 200 + section class absent.

**Test placement** — `tests/dashboard/` because these tests use the FastAPI `client` fixture (required by I-00067). The `client` fixture lives in `tests/dashboard/conftest.py`.

### 3. Targeted verification only

After writing the tests, run **only your new test files**:

```bash
uv run pytest tests/integration/test_auto_merge_failed_event_metadata.py -v
uv run pytest tests/dashboard/test_auto_merge_event_detail_per_file_errors.py -v
```

**Do NOT** run `make test-unit`, `make test-integration`, `make test-frontend`, or `make test-dashboard` from this step — those are the S13 / S14 / S15 QV gates with their own (longer) budgets. Running them here is a common cause of step timeout (I-00073/S03 post-mortem, 2026-05-08).

**Do NOT** instruct the agent to `git checkout HEAD~1 -- ...` or `git stash` to verify RED — the bug was proven RED at design time (the pre-fix evidence screenshot in `evidences/pre/` is the RED evidence; the I-00091 / CR-00066 events in the DB are the RED evidence). Runtime reverts are thrash-prone and forbidden.

### 4. Capture targeted RED evidence in the report

Because this IS the `tests-impl` step (which IS the canonical TDD test-writer), the conventional `tdd_red_evidence` value is the failure mode of one of your new tests when run against pre-S01 code. Since S01 has already landed when S05 runs, you cannot literally re-run against pre-S01 code. Use:

```
"tdd_red_evidence": "Design-time RED proof: pre-fix evidence screenshot at ai-dev/active/I-00103/evidences/pre/I-00103-bug-event-80689-missing-error.png shows the modal renders without a per-file errors section. DB events 80689 / 88770 (queried 2026-05-21) store no per_file_errors key. Post-fix unit + dashboard tests written here pin the new contract."
```

## Project Conventions

Read `skills/iw-ai-core-testing/SKILL.md` for:

- live-DB write guard (testcontainer-only)
- cross-project isolation rules
- semantic-correctness over shape-checking
- the red-flag checklist

Specific points:

- **NEVER** connect to the live DB on port 5433 from tests. Use the testcontainer fixtures.
- **NEVER** mock the database in integration tests.
- **MUST** replace psycopg2 URLs in testcontainers with `psycopg`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests (handled by `tests/conftest.py` if you use the standard fixtures).
- **CRITICAL**: `DaemonEvent.metadata` is `event_metadata` in Python; the DB column is `metadata`. When asserting on the event, use `event.event_metadata`, not `event.metadata`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck       # may not type-check test files; that's OK — ensure no errors in YOUR files
make lint
```

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00103",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_auto_merge_failed_event_metadata.py",
    "tests/dashboard/test_auto_merge_event_detail_per_file_errors.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed (4 integration + 3 dashboard)",
  "tdd_red_evidence": "Design-time RED proof: pre-fix evidence screenshot at ai-dev/active/I-00103/evidences/pre/I-00103-bug-event-80689-missing-error.png shows the modal renders without a per-file errors section. DB events 80689 / 88770 (queried 2026-05-21) store no per_file_errors key. Post-fix unit + dashboard tests written here pin the new contract.",
  "blockers": [],
  "notes": ""
}
```
