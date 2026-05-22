# I00106_S05_Tests_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed exceptions: testcontainer fixtures spun up by pytest, read-only `docker ps`/`docker logs`/
`docker inspect`, and `./ai-core.sh` / `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic migrations against the live orch DB. This work item adds NO migration.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document (read §Test to Reproduce and §TDD Approach in full).
- `ai-dev/active/I-00106/I-00106_Functional.md` -- Human-facing summary.
- `ai-dev/active/I-00106/reports/I-00106_S01_Backend_report.md` -- S01 report (exact helper name).
- `ai-dev/active/I-00106/reports/I-00106_S03_Frontend_report.md` -- S03 report (router + template changes).
- `orch/daemon/session_reader.py` -- Contains the helper under test.
- `dashboard/routers/items.py` -- Contains the `item_session_log` route under test.
- `tests/unit/test_session_reader.py` -- EXISTING unit test file; you append to it.
- `tests/dashboard/test_items_session_log.py` -- EXISTING dashboard test file for the **exact route** under test (`item_session_log`). Copy its file-local `client` fixture and its `_make_project` / `_make_pi_jsonl` seed helpers — this is your pattern source.
- `tests/dashboard/conftest.py` -- Re-exports the testcontainer DB fixtures (`db_session`, `test_project`) that the file-local `client` fixture depends on. It does NOT define `client` and has no factories.

## Output Files

- `tests/unit/test_session_reader.py` -- Existing file; append the helper unit tests.
- `tests/dashboard/test_session_log_modal_ordering.py` -- New file; the reproduction + render-order tests.
- `ai-dev/active/I-00106/reports/I-00106_S05_Tests_report.md` -- Step report.

## Context

I-00106 fixes the Agent Session Log modal so the newest agent turn renders at the top. S01 added
a pure turn-grouping helper to `orch/daemon/session_reader.py`; S03 wired it into the
`item_session_log` route and the `session_log_popup_content.html` fragment.

Your job in S05 is to write the **reproduction test** (proves the bug is fixed) and the
**regression tests** (lock the helper's contract so this class of bug cannot return).

Read `ai-dev/active/I-00106/I-00106_Issue_Design.md` — §Test to Reproduce gives the reproduction
test shape, §TDD Approach lists every test by name, and Acceptance Criteria AC1–AC5 are the
contract you are pinning.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this work item, "shape" assertions are the trap. The bug is purely about **order**, so every
test MUST assert concrete ordering — index comparisons of specific marker strings, the exact
position of a named turn, the exact sequence of segment types inside a turn. A test that only
checks "the result has 2 turns" or "the response contains some segments" would pass against the
**buggy** code and is worthless. Assert the *order*, with specific values.

## Requirements

### 1. Reproduction test — modal renders newest turn first

Create `tests/dashboard/test_session_log_modal_ordering.py`. It MUST be under `tests/dashboard/`
because it drives the `item_session_log` route through a FastAPI `TestClient`. There is **no**
shared `client` fixture in `conftest.py` — every dashboard test file defines its own. Copy the
file-local `client` fixture verbatim from `tests/dashboard/test_items_session_log.py` (the
existing test file for this exact route); it depends on the `db_session` testcontainer fixture
that `tests/dashboard/conftest.py` re-exports, which is why this test must live under
`tests/dashboard/` (I-00067 lesson).

Write `test_i00106_session_log_modal_renders_newest_turn_first`:

- Seed a `pi` step run whose session content has **two clearly distinct turns**. The simplest
  no-file path: a `StepRun` with `cli_tool="pi"`, `session_file=None`, and `log_content` set to a
  JSONL string — `read_session_content` parses `log_content` line-by-line for pi runs without a
  session file. Build the JSONL so it yields:
  - an **older** turn whose assistant reply text contains the marker `OLDEST_TURN_MARKER`, then
  - a **newer** turn whose assistant reply text contains the marker `NEWEST_TURN_MARKER`.
  Inspect `orch/daemon/session_reader.py` (`_process_pi_object` / `_process_assistant_content_item`)
  for the exact JSONL object shapes that produce `thinking` / `tool_call` / `assistant` segments,
  and mirror the JSONL fixtures already used in `tests/unit/test_session_reader.py`.
- Seed the owning `Project` / `WorkItem` / `WorkflowStep` / `StepRun` rows the route needs by
  copying the `_make_project` seed helper from `tests/dashboard/test_items_session_log.py`
  (there are no shared factories — each dashboard test file carries its own seed helpers).
- `GET` the session-log route
  (`/project/{project_id}/item/{item_id}/step/{step_id}/session-log`).
- Assert HTTP 200, then assert the **order** semantically:

  ```python
  html = resp.text
  assert "NEWEST_TURN_MARKER" in html and "OLDEST_TURN_MARKER" in html
  assert html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER"), (
      "I-00106 bug: newest turn must render above the oldest turn"
  )
  ```

This test fails against pre-fix code (chronological order → oldest marker first) and passes
after the fix.

Also write `test_session_log_modal_empty_state_still_renders` in the same file: seed a step run
with no readable session content, `GET` the route, assert HTTP 200 and that the existing
empty-state copy (e.g. `"No log content available"`) is present and no template exception
occurred (AC5).

### 2. Regression tests — the turn-grouping helper

Append to the **existing** `tests/unit/test_session_reader.py`. Import the helper from
`orch.daemon.session_reader` (use the exact name from the S01 report). These are pure unit tests —
build synthetic segment lists by hand (lists of plain dicts with a `"type"` and `"text"` key);
no files or DB needed. Cover, with **order-asserting** checks:

- `test_group_turns_reverses_turn_order` — two complete turns; assert the result's first turn is
  the **newest** one (check a marker in its assistant segment) and the last turn is the oldest.
- `test_group_turns_preserves_within_turn_order` — one turn built as
  `[thinking, tool_call, tool_result, assistant]`; assert the returned turn's segment `type`
  sequence is **exactly** `["thinking", "tool_call", "tool_result", "assistant"]` (AC3).
- `test_group_turns_in_progress_trailing_turn_first` — segments ending with `thinking` + `tool_call`
  and NO assistant reply after a complete earlier turn; assert the trailing (unfinished) turn is a
  separate turn AND is at index 0 of the result.
- `test_group_turns_compaction_is_standalone_turn` — a `compaction` segment between two turns;
  assert it is its own single-segment turn and sits in the correct position relative to the
  newest/oldest turns.
- `test_group_turns_error_terminates_turn` — a turn ending in an `error` segment followed by a
  later turn; assert the `error` closes its turn and the later turn is separate.
- `test_group_turns_consecutive_assistant_segments_stay_in_one_turn` — two adjacent `assistant`
  segments; assert they land in the **same** turn (one turn containing both), not two turns.
- `test_group_turns_log_segment_lines_reversed` — a single `log` segment whose `text` has several
  distinct lines; assert the returned segment's `text` has those lines in reversed order, AND
  assert the original input dict's `text` is unchanged (purity).
- `test_group_turns_empty_input_returns_empty_list` — `[]` in → `[]` out.

### 3. Test placement and naming

- Unit tests → appended to `tests/unit/test_session_reader.py`.
- Reproduction + render-order tests → new file `tests/dashboard/test_session_log_modal_ordering.py`.
- Match the naming and fixture style already used in those directories.
- Do NOT modify `orch/daemon/session_reader.py`, `dashboard/routers/items.py`, or the template —
  if a test cannot pass because of a real product bug, STOP and raise a blocker; do not patch
  product code from this step.

### 4. Targeted verification only

Run ONLY the test files you wrote or modified:

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -40
uv run pytest tests/dashboard/test_session_log_modal_ordering.py -v 2>&1 | tail -40
```

Do **NOT** run `make test-unit`, `make test-frontend`, or `make test-integration` — full-suite
execution is owned by the S13 / S14 / S15 QV gates. Duplicating it here blows this step's timeout
budget (I-00073/S03 post-mortem).

### 5. No manual revert RED-check

Do NOT `git checkout`, `git stash`, or otherwise revert product files to "prove" the test would
have failed pre-fix. The reproduction test's RED behaviour is established at design time. Just
write the tests and confirm they pass against the current (fixed) code.

## Project Conventions

Read `CLAUDE.md`, `tests/CLAUDE.md`, and the testing skill `skills/iw-ai-core-testing/SKILL.md`
for assertion-strength rules, the live-DB write guard, and fixture patterns. Key points:

- NEVER connect tests to the live DB (port 5433) — dashboard tests use the `client` fixture and
  its testcontainer/seeded DB.
- Assertions must be strong and semantic — see the I003 warning above. The assertion scanner
  (`make test-assertions`) rejects vacuous tests.
- Match the existing fixture/helper patterns in `tests/unit/test_session_reader.py` and
  `tests/dashboard/test_items_session_log.py` — copy the file-local `client` fixture and seed
  helpers; do not invent new infrastructure.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run, in order, and fix anything they report:

1. **`make format`** — auto-fixes formatting drift; inspect and re-stage the diff.
2. **`make typecheck`** — zero errors involving the test files you touched.
3. **`make lint`** — zero errors in the test files you touched.

If a tool is unavailable, STOP and raise a blocker. Record results in the `preflight` field.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00106",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_session_reader.py",
    "tests/dashboard/test_session_log_modal_ordering.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — tests-impl coverage step; tests added after the fix exists, not RED-first",
  "blockers": [],
  "notes": ""
}
```
