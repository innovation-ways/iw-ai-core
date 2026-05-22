# I00106_S01_Backend_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm`,
`docker system prune`, etc.).

Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`,
and `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` / `alembic downgrade` / `alembic stamp` against the
live orch DB. **This work item adds NO migration** — it is a pure presentation-layer fix.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document (read first).
- `ai-dev/active/I-00106/I-00106_Functional.md` -- Human-facing summary.
- `orch/daemon/session_reader.py` -- The file you will modify.
- `tests/unit/test_session_reader.py` -- Existing unit tests for this module (read to learn the segment shapes; do NOT modify it — S05 owns the test additions).

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S01_Backend_report.md` -- Step report.

## Context

The Agent Session Log modal (feature CR-00065) renders the agent runtime log oldest-first: the
agent's very first action sits at the top and the newest activity is buried at the bottom.
`orch/daemon/session_reader.py:read_session_content` returns a flat list of segment dicts in
strict chronological order, and every consumer renders that list as-is.

Your job in S01 is to add **one pure helper function** to `orch/daemon/session_reader.py` that
groups that flat chronological segment list into *turns* and returns the turns **newest-first**,
while preserving the order of segments **within** each turn. You do NOT touch the router or the
template — that is S03.

Read `ai-dev/active/I-00106/I-00106_Issue_Design.md` fully before writing code. The section
**"The turn-grouping helper (S01 contract)"** is your exact specification; §Root Cause Analysis
and §Acceptance Criteria (AC3, AC4) give the supporting detail.

## Requirements

### 1. Add the turn-grouping helper to `orch/daemon/session_reader.py`

Add a new public, pure function — suggested name `group_into_turns_newest_first` — with this
signature:

```python
def group_into_turns_newest_first(
    segments: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
```

It takes the chronological flat segment list produced by `read_session_content` and returns a
list of *turns*, where each turn is a list of segment dicts. The list of turns is ordered
**newest turn first**; the segments **inside** each turn keep their original chronological order.

Segment dicts have a `"type"` key whose value is one of the existing constants in this module:
`assistant`, `tool_call`, `tool_result`, `thinking`, `compaction`, `error`, `log`
(see `_SEG_*` constants at the top of the file). Segments are plain `dict` objects.

### 2. Turn-boundary rule

Walk the input in order, accumulating segments into the current turn. A turn is **terminated**
by either:

- an `assistant` segment that is **not** immediately followed by another `assistant` segment.
  Consecutive `assistant` segments (a pi message whose `content` list carries multiple `text`
  items produces adjacent `assistant` segments) MUST stay in the **same** turn — only the last
  of a consecutive run terminates the turn; or
- an `error` segment — always terminates its turn.

When a turn is terminated, push it to the turn list and start a fresh empty turn. After the walk,
any segments still accumulated (no terminating `assistant`/`error` yet — common while a step is
still running) form a **final in-progress turn**; push it too.

### 3. Special segments

- **`compaction`**: emit it as its **own single-segment turn**. Before doing so, flush any
  in-progress turn so the compaction marker sits between turns, exactly where it occurred
  chronologically.
- **`log`**: this is the claude/opencode whole-dump fallback — `read_session_content` returns
  exactly one `log` segment for those runs. Emit it as its own turn, and **reverse the lines of
  its `text`** (split on line boundaries, reverse, re-join) so the newest line is on top —
  consistent with the `_reverse_log` behaviour already used by the Logs tab. Add a tiny private
  line-reversing helper inside `session_reader.py` for this (a 2–3 line function); do **NOT**
  import anything from `dashboard/` — `orch/` must not depend on `dashboard/` (see `orch/CLAUDE.md`).

### 4. Ordering and purity

- Group the turns in chronological order first, then reverse the **list of turns** so the newest
  turn is at index `0`. Never reverse the order of segments *within* a turn.
- The function MUST be **pure**: do not mutate the input `segments` list or the dicts inside it.
  Where you rewrite a `log` segment's `text`, return a **new** dict (e.g. `{**seg, "text": ...}`).
- Empty input (`[]`) returns `[]`.

### 5. Docstring

Give the function a clear docstring stating the turn definition, the newest-first ordering, the
within-turn-order guarantee, and the `compaction` / `log` special cases. Match the existing
documentation style in `session_reader.py` (see its module docstring and `read_session_content`).

### 6. Do NOT change `read_session_content` or the parsing functions

`read_session_content` and the `_render_*` / `_process_*` functions MUST keep returning
chronological segments — they are the canonical parse and other behaviour depends on it. Your
helper is a **separate, additive** function. Do not wire it into the router (that is S03).

### 7. TDD note

This is a **Backend** step that adds behaviour-implementing code, but the dedicated reproduction
and regression tests are assigned to **S05 `tests-impl`** per the design doc's File Manifest and
TDD Approach. Recommended workflow:

1. Implement `group_into_turns_newest_first` in `orch/daemon/session_reader.py`.
2. Sanity-check it yourself with a quick targeted run of the existing module tests (Requirement 8).
3. Report `tdd_red_evidence` as
   `"n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach"`.

You MAY, if you wish, add a throwaway local check while developing, but the committed tests are
S05's deliverable — do not add test code to `tests/unit/test_session_reader.py` yourself.

### 8. Test verification

Run only the existing tests for this module — do NOT run `make test-unit` or `make test-integration`
(those are the S13 / S15 QV gates):

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -30
```

All existing tests must still pass — your change is purely additive, so nothing should break.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for layer boundaries and naming. Specific rules here:

- `orch/` MUST NOT import from `dashboard/`. The line-reversing helper for the `log` segment
  lives inside `session_reader.py`.
- Match the module's existing style: `from __future__ import annotations` is already in effect,
  type hints use `list[dict[str, Any]]`, private helpers are `_snake_case`, public functions have
  full docstrings.
- Keep the helper self-contained and side-effect free.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, you MUST run, in order, and fix anything they report:

1. **`make format`** — auto-fixes formatting drift; inspect and re-stage the diff.
2. **`make typecheck`** — zero errors involving `orch/daemon/session_reader.py`.
3. **`make lint`** — zero errors involving `orch/daemon/session_reader.py`.

If a tool is unavailable, STOP and raise a blocker. Record each result in the `preflight` field
of your result contract.

## Test Verification (NON-NEGOTIABLE)

Run the targeted command in Requirement 8 only. Do NOT run the full unit or integration suites —
those are the S13 / S15 QV gates and duplicating them here burns this step's budget.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00106",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/session_reader.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach",
  "blockers": [],
  "notes": ""
}
```
