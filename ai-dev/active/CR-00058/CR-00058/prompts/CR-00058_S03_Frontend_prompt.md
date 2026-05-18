# CR-00058_S03_Frontend_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutating command. Allowed: `docker ps`, `docker inspect`, `docker logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations involved.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md` — design doc; AC6
- `dashboard/routers/batches.py` — current `_held_reasons_for_items` builder (line ~74 onward; line ~130 onward queries `item_held_for_scope` DaemonEvents)
- `dashboard/templates/fragments/batch_items_rows.html` — current held-reason pill rendering
- `dashboard/templates/_partials/help/batches.html`, `_partials/help/queue.html`, `_partials/help/batch_detail.html` — relevant help partials
- `dashboard/templates/pages/project/batches.html`, `pages/project/queue.html`, `pages/project/batch_detail.html` — pages that include the rows fragment
- `dashboard/static/styles.css` — plain CSS sink (per `CLAUDE.md` `make css` rule)
- `dashboard/CLAUDE.md` (if present) — frontend conventions
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S03_Frontend_report.md`
- Modified: `dashboard/routers/batches.py`
- Modified: `dashboard/templates/fragments/batch_items_rows.html`
- Modified (if needed): page templates that render the rows fragment in a way that needs the new context key (likely none — the fragment context is shared)

## Context

The router already surfaces "held by scope overlap" reasons. We extend it to also surface "allowed by policy" decisions for items that were released by the new policy. The new pill is informational — operators should see *when the policy is actively working*, so they can correlate with merge-failure outcomes and decide whether the policy is helping.

## Requirements

### 1. Router: query both event types

In `dashboard/routers/batches.py`, find the helper that builds per-item held-reason data (around line 74; the SQLAlchemy query around line 130 reads `item_held_for_scope` events within `window_secs`).

Refactor or extend it so that:

- It returns a record per visible item with shape (Python dict or pydantic-like dataclass — match the existing style):
  - `status: Literal["held", "policy_allowed", "none"]`
  - `message: str` — short human-readable reason (held: existing format; policy_allowed: "Released by allow pattern X — overlapped with Y on Z")
  - `matched_globs: list[str]` — for held: conflicting; for policy_allowed: dropped globs
  - `matched_allow_patterns: list[str]` — for policy_allowed only
  - `blocking_item_ids: list[str]` — for both
- Held has precedence: if both event types exist within the window for the same item, render only the held badge.
- The same `window_secs` applies to both event types — re-use the existing constant.
- Use a single combined query if possible (e.g. `event_type IN ("item_held_for_scope", "item_overlap_allowed_by_policy")`) to keep request count flat as item count grows.

### 2. Template: new info-tone pill

In `dashboard/templates/fragments/batch_items_rows.html`, find where the held-reason pill is rendered. Add a new conditional branch for `record.status == "policy_allowed"`:

- Use the existing pill markup convention but with a distinct tone (info / blue) — re-use an existing utility class if available; otherwise add a plain CSS rule to `dashboard/static/styles.css` per `CLAUDE.md`'s "MUST append plain CSS rules" guidance when Tailwind isn't reliable in worktrees.
- Pill text: a short verb + matched pattern count, e.g. `policy allowed (dashboard/**)`. Truncate the pattern list at the first three; show the rest in the title/tooltip.
- The pill has an HTML `title` attribute (or matching tooltip mechanism used elsewhere) listing all `matched_allow_patterns` and the `blocking_item_ids`.

### 3. Accessibility

- Pill text must be visible (don't rely solely on color tone).
- `title` attribute is acceptable as a tooltip mechanism for this codebase — match what the existing held-reason pill does.
- No new console errors. Verify by tailing `dashboard/server.log` while rendering pages with seeded events (S02's integration test gives you the exact event shape).

### 4. Do not regress the existing held pill

When `status=="held"`, render the same pill markup as today — only add a branch, don't refactor existing rendering unless necessary.

### 5. Touch only what's needed

If the rows fragment is included by multiple pages and they share the context key for held reasons, you don't need to touch each page template. If a page template builds its own context dict for the fragment, update each (be thorough — `queue.html` and `batch_detail.html` may both include the fragment but build context differently).

Help partials (`_partials/help/*.html`) are owned by S04 (template-impl) — do NOT add help copy here.

## Project Conventions

- Plain CSS in `dashboard/static/styles.css` is fine when `make css` fails or Tailwind is unreliable.
- htmx fragments use `hx-target="#X"` patterns — any new `id="X"` must be referenced consistently.
- Jinja2 `format` filter calls MUST be %-style: `"%dm%02ds"|format(m, s)` not `"{}m{}s".format(...)` (lint will catch this via `scripts/check_templates.py`).

## TDD Requirement

For router changes, add a new dashboard-layer test file at `tests/dashboard/test_batches_router.py` (this path is listed in `scope.allowed_paths` for the CR). Mirror the fixture/style of existing sibling files (`tests/dashboard/test_help_router.py`, `tests/dashboard/test_staleness_router.py`, `tests/dashboard/test_chat_router.py`). The test should seed two `DaemonEvent` rows (one `item_held_for_scope`, one `item_overlap_allowed_by_policy`) and assert:

- An item with only an `item_overlap_allowed_by_policy` event in the window returns `record.status == "policy_allowed"` with `matched_allow_patterns` and `blocking_item_ids` populated from the event metadata.
- An item with both event types in the window returns `record.status == "held"` (held precedence rule).
- A combined query is used (single SQL round-trip) — assert via SQLAlchemy event listener or by counting issued statements.

For template changes, snapshot/render assertions are acceptable. RED-first: write the test against the new record shape, watch it fail, then add the router code.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` (this also runs `scripts/check_templates.py` — the Jinja %-format rule)

## Test Verification (NON-NEGOTIABLE)

Targeted run only — your new or modified router test files. Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/batches.py",
    "dashboard/templates/fragments/batch_items_rows.html",
    "dashboard/static/styles.css",
    "tests/dashboard/test_batches_router.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_batches_router.py::test_policy_allowed_record_emitted — AssertionError: 'none' != 'policy_allowed'",
  "blockers": [],
  "notes": ""
}
```
