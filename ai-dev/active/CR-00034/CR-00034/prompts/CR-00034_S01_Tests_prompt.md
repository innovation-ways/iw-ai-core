# CR-00034_S01_Tests_prompt

**Work Item**: CR-00034 -- Robust `data-full-text` test assertions using `html.escape`
**Step**: S01
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migrations. If you find yourself drafting one, STOP — you have
drifted from the spec.

## Input Files

- **Runtime step state** — for current step list and gate commands prefer `uv run iw item-status CR-00034 --json`.
- `ai-dev/active/CR-00034/CR-00034_CR_Design.md` — Design document (READ FIRST).
- `tests/dashboard/test_i00067_recent_activity_truncation.py` — the file you will edit.
- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` — finding [4] is the source motivation.

## Output Files

- `ai-dev/work/CR-00034/reports/CR-00034_S01_Tests_report.md` — Step report.

## Context

You are implementing the **only** code change in CR-00034. The change is exactly two assertions plus one import in one file.

Read the design document first — Sections **Current Behavior**, **Desired Behavior**, and **Acceptance Criteria** describe the change in full. Then read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions.

## Requirements

### 1. Add `html` to stdlib imports

In `tests/dashboard/test_i00067_recent_activity_truncation.py`, add `import html` to the standard-library import group, alphabetically next to `import os` (which is already present near the top of the file).

### 2. Rewrite assertion at line 95

In `test_long_message_truncated_and_full_text_in_dom`, replace:

```python
assert f'data-full-text="{long_msg}"' in html, "Full text should be in data-full-text attribute"
```

with:

```python
assert (
    f'data-full-text="{html.escape(long_msg, quote=True)}"' in html
), "Full text should be in data-full-text attribute"
```

(Or the equivalent single-line form if `ruff format` keeps it under the line limit. Use whatever shape `make format` produces.)

⚠️ **Naming collision warning**: the local parameter `html` (the response body string) shadows the module-level `import html`. Read the function carefully — the response body is bound to a local named `html` after `html = response.text`. You have two options:

- (Preferred) Rename the local from `html` to `body` (or `page_html`) inside this one test function so `html.escape` resolves to the stdlib module. This is the cleanest fix.
- (Alternative) Compute the escaped value into a local before the assignment, e.g. `escaped = html.escape(long_msg, quote=True)` placed BEFORE `html = response.text`, then reference `escaped` in the assertion.

Pick one approach and apply it consistently in **both** affected test functions. Document which one you chose in the step report's `notes` field.

### 3. Rewrite assertion at line 241

In `test_101_char_message_is_truncated`, replace:

```python
assert f'data-full-text="{msg}"' in html
```

with the equivalent using `html.escape(msg, quote=True)`, applying the same shadowing fix you chose in requirement 2.

### 4. Verify the existing test suite still passes

Run:

```bash
uv run pytest tests/dashboard/test_i00067_recent_activity_truncation.py -v
```

All 7 tests must pass. The two affected tests (`test_long_message_truncated_and_full_text_in_dom`, `test_101_char_message_is_truncated`) must still pass — escaping plain `E` and `X` characters yields the same string, so behaviour is preserved.

### 5. Do NOT change anything else

- Do NOT touch any production code (no `dashboard/`, no `orch/`, no templates).
- Do NOT add new tests, new fixtures, or new escape characters to assert against. The CR scope is strictly the two flagged assertions + the import.
- Do NOT "improve" other assertions in the same file even if they look similar.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for:

- Test file location rules (this file is correctly placed under `tests/dashboard/`).
- Lint/format commands.
- The non-negotiable testing rules (don't connect to live DB, etc.) — none of those are at risk here, but be aware.

## TDD Requirement

The "RED" phase here is verifying the file currently passes against main BEFORE editing. Then make the edit and verify it still passes. Because the existing fixtures (`"E"*200`, `"X"*101`) escape to themselves, the test passes both before and after — that is correct and expected. The semantic improvement is that the assertion now matches the rendered DOM regardless of fixture content.

You do NOT need to add a new test that proves the escape-handling is load-bearing. The reviewer can manually verify by substituting a `"`-containing fixture during code review.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the file you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `uv run pytest tests/dashboard/test_i00067_recent_activity_truncation.py -v` — all 7 tests pass.
2. `make lint` and `make format` and `make typecheck` — all clean.
3. Do **NOT** report `tests_passed: true` unless the targeted file's tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "tests-impl",
  "work_item": "CR-00034",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_i00067_recent_activity_truncation.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed (tests/dashboard/test_i00067_recent_activity_truncation.py)",
  "blockers": [],
  "notes": "State which shadowing-fix approach you chose (rename local `html` → `body`/`page_html`, OR pre-compute escaped value before reassignment). Reviewer needs this to verify both functions are consistent."
}
```
