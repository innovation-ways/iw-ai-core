# I-00086_S02_CodeReview_API_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step Being Reviewed**: S01 (api-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`docker logs`/`docker inspect` allowed. No state-changing commands.

## ⛔ Migrations: agents generate, daemon applies

This item does not touch migrations. Read-only `alembic history`/`current`/`show` allowed.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document
- `ai-dev/active/I-00086/reports/I-00086_S01_API_report.md` — S01 step report
- All files listed in S01 report's `files_changed`

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the work done in S01 (`api-impl`) for **I-00086 — runtime override controls give no UI feedback**.

S01 was supposed to change the response shape of both PATCH endpoints in `dashboard/routers/runtime_overrides.py`:

- Body becomes the rendered steps-table HTML fragment (200, not 204).
- An `HX-Trigger` header carries `{"showToast": {"message": "...", "type": "success|info"}}`.
- Bulk endpoint reports the **actual** number of editable steps updated (not total step count).
- Bulk endpoint's "zero editable steps" branch returns an `info` toast `"No editable steps to update"` with no DaemonEvent.

## Read the Design Document FIRST

Read `ai-dev/active/I-00086/I-00086_Issue_Design.md`. Specifically:

- **Acceptance Criteria** (AC1, AC2, AC3) — every one is a check.
- **TDD Approach** — note the test file path called out by name (`tests/dashboard/test_runtime_override_response.py` is illustrative; the agent may have placed it differently).
- The constraint in **Notes** that `hx-disabled-elt="this"` MUST be preserved (this is S03's responsibility but verify the endpoint logic doesn't depend on the dropdown being non-disabled).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in S01's `files_changed` are **CRITICAL** findings with `"category": "conventions"`.

## Review Checklist

### 1. Architecture Compliance

- Is the new render helper placed in the right module (close to existing render code, NOT inline in the router)?
- Does the fragment template name match what S03 expects (`fragments/item_steps_table.html`)? If S01 used the fallback (rendering the full `item_overview.html`), is that documented and consistent?
- Are layer boundaries respected? Business logic stays out of the router (per `dashboard/CLAUDE.md`).
- Is the response built using FastAPI primitives only (`HTMLResponse` or `Response` with explicit media type) — no new framework imports?

### 2. Response-Contract Correctness

- Does the bulk endpoint compute `updated_count` from `len(editable_steps)` AFTER filtering for editable statuses (not total step count)?
- Does the success toast message use the exact string `Model updated for N step(s)` (N substituted; the parenthetical plural marker `(s)` is intentional and the tests will assert it literally)?
- Does the per-step toast use the exact string `Model updated`?
- Does the zero-editable-steps branch use `"No editable steps to update"` with `"type": "info"` and emit NO DaemonEvent?
- Are validation paths (item 404, option_id 404) unchanged? They MUST NOT carry an `HX-Trigger`.
- Is `HX-Trigger` JSON-encoded via `json.dumps`, not f-string-built? (Prevents shell-style quoting bugs.)
- Does the `Content-Type` resolve to `text/html`? Browsers must NOT interpret the fragment as JSON.

### 3. Project Conventions

- Read `dashboard/CLAUDE.md` and `CLAUDE.md`. Fragment templates do not extend `base.html`. Naming matches existing routers.
- Imports are at the top, alphabetized in their group.

### 4. Security

- No new user-facing log line dumps `option_id` or `step_id` unsanitized.
- The fragment renderer does NOT use raw user input in template paths.

### 5. Testing

- Did S01 actually verify its own work? Look for a meaningful `tdd_red_evidence` snippet in the S01 report (proves the test would fail pre-change).
- Are existing tests against these endpoints (`tests/dashboard/test_runtime_overrides.py` or similar) flagged in the report as needing S05 updates? Per-step / bulk tests that pinned `status_code == 204` will now break — that is **expected** and S05 fixes them.

### 5a. TDD RED Evidence (behaviour-implementing steps only)

The S01 report's `tdd_red_evidence` field must record a plausible failure snippet from running a targeted test (or a captured `curl -i` showing the pre-change 204). If S01 reports `"n/a — ..."`, verify the reason is sound (e.g. "endpoint contract change, RED captured via curl") — if there is no evidence at all, that is a **HIGH** finding.

## Test Verification (NON-NEGOTIABLE)

Run the targeted runtime-override tests (do NOT run the full suite):

```bash
uv run pytest tests/ -k runtime_override -v
```

Report whether they pass. If existing tests fail because they pinned the old 204 contract, do NOT raise a finding for that — record it in `notes` and confirm S05's prompt covers updating them.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Endpoint crashes / wrong status / missing `HX-Trigger` / wrong DB writes |
| **HIGH** | Wrong toast message / wrong count for bulk / inconsistent helper location |
| **MEDIUM (fixable)** | Lint/format/typecheck violations in changed files; sub-optimal helper placement |
| **MEDIUM (suggestion)** | Naming / refactor ideas |
| **LOW** | Style nitpicks |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00086",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
