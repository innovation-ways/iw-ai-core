# I00106_S03_Frontend_prompt

**Work Item**: I-00106 -- Agent Session Log modal renders oldest-first — newest activity buried at the bottom
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`,
and `./ai-core.sh` / `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic migrations against the live orch DB. This work item adds NO migration.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00106 --json` for the current step list.
- `ai-dev/active/I-00106/I-00106_Issue_Design.md` -- Design document (read first).
- `ai-dev/active/I-00106/I-00106_Functional.md` -- Human-facing summary.
- `ai-dev/active/I-00106/reports/I-00106_S01_Backend_report.md` -- S01 report (names the new helper).
- `orch/daemon/session_reader.py` -- Contains the new helper from S01 (read it; do NOT modify it).
- `dashboard/routers/items.py` -- The router file you will modify (`item_session_log`, ~lines 2192-2281).
- `dashboard/templates/fragments/session_log_popup_content.html` -- The template you will modify.

## Output Files

- `ai-dev/active/I-00106/reports/I-00106_S03_Frontend_report.md` -- Step report.

## Context

S01 added a pure helper to `orch/daemon/session_reader.py` (named `group_into_turns_newest_first`
unless the S01 report says otherwise — confirm the exact name in that report) which groups the
flat chronological agent-session segment list into *turns* and returns them newest-first.

Your job in S03 is to **wire that helper into the Agent Session Log modal** so the modal renders
the newest turn at the top. You change two files: the router and the modal fragment template.

Read `ai-dev/active/I-00106/I-00106_Issue_Design.md` fully first — the section
**"The router + template change (S03 contract)"** is your exact specification; §Root Cause Analysis
gives the line landmarks and Acceptance Criteria AC1 / AC5 give the contract.

## Requirements

### 1. Router: `item_session_log` applies the helper (`dashboard/routers/items.py`)

`item_session_log` (around lines 2192-2281) currently does, in effect:

```python
raw_segments = read_session_content(run)
segments = raw_segments
...
return templates.TemplateResponse(request, "fragments/session_log_popup_content.html",
    {"segments": segments, ...})
```

Change it so the segments are grouped into newest-first turns before rendering:

- Import the new helper from `orch.daemon.session_reader` alongside the existing
  `from orch.daemon.session_reader import read_session_content` (that import is currently inside
  the function — keep it there and extend it, or follow whatever the S01 report indicates).
- After obtaining the segment list, call the helper to produce a `turns` value
  (`list[list[dict]]`).
- Pass it to the template under the context key **`turns`** (replacing the `segments` key).
- **Error-fallback branch** (the `except` around lines 2258-2265 that builds a single
  `SessionLogSegment(type="error", text="Failed to read session log.")`): this branch must also
  produce a `turns`-shaped value. Run its one-segment list through the same helper, or wrap it as
  `[[error_segment]]` — whichever is cleaner — so the template always receives `turns`.
- The empty case (`segments == []`) must yield `turns == []` so the template's empty-state branch
  still triggers.

Do NOT modify `read_session_content` or anything else in `session_reader.py`.

### 2. Template: iterate `turns` newest-first (`dashboard/templates/fragments/session_log_popup_content.html`)

The template currently guards on `{% if segments %}` and renders a single flat
`{% for seg in segments %}` loop. Change it to a two-level iteration over `turns`:

- Guard: `{% if turns %}` (and the `{% else %}` empty-state branch stays as-is).
- Outer loop: `{% for turn in turns %}`.
- Between turns, render a thin horizontal divider **before every turn except the first**
  (`{% if not loop.first %}<div class="my-3 border-t border-border"></div>{% endif %}` — use only
  Tailwind utility classes that ALREADY appear in this file, such as `border-t` / `border-border`;
  do NOT introduce a new CSS class and do NOT require a `make css` rebuild).
- Inner loop: `{% for seg in turn %}` — reuse the existing per-segment rendering blocks
  (`compaction`, `assistant`, `thinking`, `tool_call`, `tool_result`, `error`, `log`) **verbatim**.
  Only the iteration wrapper changes; the markup for each segment type is unchanged.
- The header block (step_id / run # / cli_tool / "● live") and the `is_live` htmx polling wrapper
  (`<div hx-get=... hx-trigger="every 3s" ...>`) are **preserved exactly**. The polling wrapper
  still wraps the whole body.

Fragment templates under `dashboard/templates/fragments/` MUST NOT extend `base.html` — this one
already does not; keep it that way.

### 3. No scroll-preservation JavaScript

Do NOT add scroll-position-saving JS. With newest-first ordering the latest turn is at the top,
which is where an `innerHTML` poll swap already lands. Preserving mid-scroll position across the
3-second live poll is explicitly out of scope (see design doc §Notes).

### 4. Keep behaviour intact

- The modal must still open from the steps-table "Logs" column and still live-poll every 3 s for
  running/stalled steps (AC5).
- The empty-state message ("No log content available yet." / "Step ended with: …") must still
  render when there is no content (AC5) — verify the `{% else %}` branch still works with the
  `turns` guard.
- Do NOT change the `item_steps_table.html` trigger button or the modal shell — only the fragment
  body template and the router handler.

### 5. Test verification

Run the existing dashboard tests for the session-log surface to confirm no regression — do NOT
run `make test-frontend` or the full suites (those are S14 / S13 / S15 QV gates):

```bash
uv run pytest tests/unit/test_session_reader.py -v 2>&1 | tail -20
uv run pytest tests/dashboard/ -k "session_log or session_reader or item" -v 2>&1 | tail -30
```

If the `-k` filter matches nothing relevant, fall back to running the smallest dashboard test
file that exercises `item_session_log`. The dedicated reproduction/regression tests are written
in S05 — they do not exist yet when S03 runs.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Specific rules here:

- Routers are thin — the reordering logic lives in the `orch/` helper, not inline in the router.
- htmx fragments under `templates/fragments/` MUST NOT extend `base.html`.
- Jinja2 `format`-filter calls must stay `%`-style — not relevant here unless you add one; do not.
- Use only Tailwind classes already present in the file; plain pre-built CSS, no `make css` needed.

## TDD note

This is a Frontend step. The reproduction and regression tests are S05's deliverable per the
design doc. Report `tdd_red_evidence` as
`"n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach"`.
Do NOT add test code yourself.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run, in order, and fix anything they report:

1. **`make format`** — auto-fixes formatting drift; inspect and re-stage the diff.
2. **`make typecheck`** — zero errors involving `dashboard/routers/items.py`.
3. **`make lint`** — zero errors involving the files you touched (this includes the Jinja2
   template check `scripts/check_templates.py`).

If a tool is unavailable, STOP and raise a blocker. Record results in the `preflight` field.

## Test Verification (NON-NEGOTIABLE)

Run the targeted commands in Requirement 5 only. Do NOT run `make test-frontend`,
`make test-unit`, or `make test-integration` — those are the S13 / S14 / S15 QV gates.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00106",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py",
    "dashboard/templates/fragments/session_log_popup_content.html"
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
