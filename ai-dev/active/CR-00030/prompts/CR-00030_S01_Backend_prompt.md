# CR-00030_S01_Backend_prompt

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps`, `docker inspect`, `docker logs`), and
invocations via `./ai-core.sh` or `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This change touches NO migrations and NO database schema. If you find
yourself running any `alembic` command, stop — you are off-track.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00030 --json` over the manifest file.
- `ai-dev/active/CR-00030/CR-00030_CR_Design.md` — Design document (read **Current Behavior**, **Desired Behavior**, **Acceptance Criteria**, and **Notes** in full).
- `orch/llm_usage.py` — the file to edit.
- `dashboard/templates/fragments/llm_usage_footer.html` — read-only reference; do NOT edit.

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S01_Backend_report.md` — Step report.

## Context

You are implementing the only code change in CR-00030. The user wants the Claude 5h footer label changed from a wall-clock end time (`"15:00"`) to a remaining-time string in the same format MiniMax already uses (`"4h 32m"`, `"25m"`).

Read `CLAUDE.md` and `orch/CLAUDE.md` first.

## Requirements

### 1. Add a new private helper `_format_remaining_from_ts`

In `orch/llm_usage.py`, add a new private function next to `_format_resets_at`:

```python
def _format_remaining_from_ts(resets_at: float) -> str | None:
    """Render a Unix timestamp as a remaining-time label (MiniMax-style).

    - >=1h ahead → 'Hh Mm'   (e.g. '4h 32m', '1h 0m')
    - <1h ahead  → 'Mm'      (e.g. '25m', '0m' for under one minute)
    - past or zero → None
    """
```

Implementation notes:
- Compute `remaining_s = int(resets_at - datetime.now(UTC).timestamp())`. If `resets_at <= 0` or `remaining_s < 0`, return `None`.
- For `remaining_s == 0`, return `"0m"` (not `None`) — the slot is technically not yet reset; the next poll will catch the past-deadline case and return `None` then.
  - Boundary clarification: a `resets_at` strictly less than `datetime.now(UTC).timestamp()` returns `None`. A `resets_at` equal to or greater than `now` (with non-negative `remaining_s`) returns the formatted string.
- For `remaining_s < 3600`, return `f"{remaining_s // 60}m"`.
- For `remaining_s >= 3600`, return `f"{hours}h {minutes}m"` where `hours = remaining_s // 3600`, `minutes = (remaining_s % 3600) // 60`.
- Do NOT introduce a new datetime/time module — use the existing `from datetime import UTC, datetime` import.
- Do NOT couple the implementation to milliseconds — the existing `_format_reset(remains_ms)` works in milliseconds and is for MiniMax. The new helper takes a Unix-timestamp `float`, just like `_format_resets_at`.

### 2. Switch `_claude_usage`'s 5h branch to the new helper

In `_claude_usage()`, replace the 5h `block_reset` derivation:

```python
# BEFORE
block_reset = _format_resets_at(five_hour.get("resets_at", 0))

# AFTER
block_reset = _format_remaining_from_ts(five_hour.get("resets_at", 0))
```

The 7d branch must remain on `_format_resets_at`:

```python
# UNCHANGED
week_reset = _format_resets_at(seven_day.get("resets_at", 0))
```

Do NOT remove `_format_resets_at` or its tests. The 7d slot still needs it.

### 3. Update the module docstring

The existing module docstring (lines 1-23) describes Claude reset labels indirectly. Add or amend a short sentence explaining that the **5h** label is rendered as time remaining (`Hh Mm` / `Mm`) while the **7d** label stays as a wall-clock string. Keep it concise — one or two sentences.

### 4. Do NOT touch

- `dashboard/templates/fragments/llm_usage_footer.html` — the template renders whatever string we put in `block_reset`; no edit needed.
- `dashboard/routers/usage.py` — the router passes `block_reset` through unchanged.
- `_format_reset` (MiniMax helper) — unrelated.
- `_format_resets_at` — keep it intact, the 7d branch still uses it.
- The 60-second `_cache` TTL — it caches the *string*, which becomes stale near the deadline; this is pre-existing behavior, not a regression. Do NOT add deadline-aware invalidation.
- `block_pct` / `week_pct` percentage values — unchanged.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:
- Architecture patterns and layer boundaries (orch is pure logic; dashboard renders).
- Coding conventions (`from __future__ import annotations`; `Mapped[]` for ORM; `UTC, datetime` import shape; `psycopg` v3, never `psycopg2`).
- Test organization (`tests/unit/` for fast tests, never connect to live DB).

When in doubt, match the style of the existing `_format_resets_at` and `_format_reset` helpers — same module, same neighbourhood.

## TDD Requirement

Follow Red-Green-Refactor:
1. **RED**: Coordinate with S03 (Tests step) — the failing tests for `_format_remaining_from_ts` belong there. For your own confidence loop, write throw-away pytest cases locally and verify they fail before adding the helper, then pass after. Do not commit those throw-aways.
2. **GREEN**: Add the helper and the one-line `_claude_usage` swap.
3. **REFACTOR**: If `_format_remaining_from_ts` and `_format_reset` share enough logic, extract a tiny shared `_format_h_m(seconds: int) -> str` inner helper. Acceptable, not required. Keep both public-call signatures (timestamps for one, milliseconds for the other) intact.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in this order and fix what they flag:

1. `make format`
2. `make typecheck`
3. `make lint`

Populate `preflight` in your result contract.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` after your edit. The existing `tests/unit/test_llm_usage.py::TestClaudeRateLimitsCache::test_claude_usage_uses_seven_day_from_cache` will currently assert `block_reset is not None` — that still holds for any future timestamp, so the test should pass even before S03 strengthens it. If that test fails after your edit, your helper has a bug — fix it, do not weaken the test.

Do NOT report `tests_passed: true` unless `make test-unit` passes with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00030",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/llm_usage.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
