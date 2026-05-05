# CR-00034: Robust `data-full-text` test assertions using `html.escape`

**Type**: Change Request
**Priority**: Low
**Reason**: Tech debt — fragile test assertion flagged in I-00067 self-assess (finding [4]). Test passes today only because the fixtures contain no characters Jinja2 auto-escapes; will silently break the moment a future fixture contains `"`, `<`, `>`, or `&`.
**Created**: 2026-05-05
**Status**: Draft

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

This CR does NOT modify the schema and adds NO migrations. If you find
yourself drafting a migration, STOP — you have drifted from the spec.

---

## Description

Two test assertions in `tests/dashboard/test_i00067_recent_activity_truncation.py` interpolate the raw fixture string into the expected `data-full-text` attribute value. The Jinja2 template emits the value HTML-escaped; the assertions only pass today because the test messages (`"E"*200`, `"X"*101`) contain no characters that get escaped. Replace the literal interpolation with `html.escape(...)` so the assertion compares against the actual rendered DOM regardless of message content.

## Project Context

Read `CLAUDE.md` and `tests/CLAUDE.md`. Relevant rules: integration tests live under `tests/dashboard/`, `tests/integration/`, or `tests/unit/`; the `db_session` and `test_project` fixtures come from `tests/conftest.py`; the file under change uses the FastAPI `TestClient` pattern (no testcontainer interaction needed beyond the existing fixtures).

## Current Behavior

`tests/dashboard/test_i00067_recent_activity_truncation.py` contains two assertions that match the raw fixture string against the rendered HTML attribute value:

- Line 95 (`test_long_message_truncated_and_full_text_in_dom`):
  `assert f'data-full-text="{long_msg}"' in html, "Full text should be in data-full-text attribute"`
- Line 241 (`test_101_char_message_is_truncated`):
  `assert f'data-full-text="{msg}"' in html`

Both pass today because the fixtures (`"E"*200` and `"X"*101`) contain no characters subject to Jinja2's `|e` filter. The template that emits the attribute (`dashboard/templates/fragments/dashboard_overview.html` or its include) goes through Jinja2 auto-escaping, so any `"`, `<`, `>`, or `&` in the input is rendered as `&quot;`, `&lt;`, `&gt;`, or `&amp;` in the actual DOM.

If a future contributor copies one of these tests and changes the fixture to a message containing any of those characters (for example, an actual error message such as `KeyError: "missing"`), the assertion will silently fail to find a match — but the test author may not realise the failure is due to escaping rather than a template regression.

## Desired Behavior

The two assertions match against the HTML-escaped form of the fixture using Python's standard-library `html.escape(s, quote=True)`. With the existing fixtures the assertion still passes (escaping `"E"*200` yields `"E"*200`); the test now also passes for any future message regardless of which characters it contains.

Concretely, after the change:

- Line 95 reads `assert f'data-full-text="{html.escape(long_msg, quote=True)}"' in html, "Full text should be in data-full-text attribute"`.
- Line 241 reads `assert f'data-full-text="{html.escape(msg, quote=True)}"' in html`.
- The file imports `html` from the standard library (added alongside the existing `import os`).

No production code, template, or schema changes. The asserted DOM substring is the same as what Jinja2 actually emits.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/dashboard/test_i00067_recent_activity_truncation.py` | Two assertions interpolate raw fixture; passes only because fixture has no escapable characters | Two assertions wrap fixture in `html.escape(..., quote=True)`; passes regardless of fixture content |

### Breaking Changes

None. Test-only change. No public APIs, schemas, contracts, or runtime behaviour are altered.

### Data Migration

None. No schema changes, no migrations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | tests-impl | Add `import html`; rewrite the two `data-full-text` assertions to use `html.escape(..., quote=True)` | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-step review | — |
| S04 | qv-gate (lint) | `make lint` | — |
| S05 | qv-gate (format) | `make format-check` | — |
| S06 | qv-gate (typecheck) | `make typecheck` | — |
| S07 | qv-gate (unit-tests) | `make test-unit` | — |
| S08 | qv-gate (integration-tests) | `make allure-integration` | — |
| S09 | self-assess-impl | Self-assessment via `iw-item-analyze` skill | — |

Fix cycles (`code-review-fix-impl`, `code-review-fix-final-impl`) are created dynamically by the orchestrator if reviews fail; they are not static steps.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00034/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00034_CR_Design.md` | Design | This document |
| `CR-00034_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00034_S01_Tests_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00034_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00034_S03_CodeReview_Final_prompt.md` | Prompt | S03 global review |
| `prompts/CR-00034_S09_SelfAssess_prompt.md` | Prompt | S09 self-assessment |

QV gate steps (S04..S08) declare their `command` inline in the manifest and do not need a prompt file.

Reports are created during execution under `ai-dev/work/CR-00034/reports/` (or the active worktree equivalent).

## Acceptance Criteria

### AC1: Existing fixtures still pass after the change

```
Given the test file currently passes against main with fixtures "E"*200 and "X"*101
When the assertions are wrapped in html.escape(..., quote=True)
Then both test_long_message_truncated_and_full_text_in_dom and test_101_char_message_is_truncated still pass
And `make test-integration` reports the same pass count as before for this file
```

### AC2: Assertion is robust against escapable characters

```
Given a temporary fixture message containing a double-quote (e.g. 'KeyError: "missing"')
When the test renders the project dashboard and the template emits data-full-text="…"
Then the assertion matches because both sides of the comparison are HTML-escaped
And had the assertion not used html.escape, the assertion would have failed (proving the fix is load-bearing)
```

(AC2 is conceptual evidence — the implementation does NOT need to commit a new test for the escaped path, only fix the existing two assertions. The reviewer may verify by manually substituting a fixture and observing the diff.)

### AC3: `import html` is present and the file passes lint/format

```
Given the file is edited
When `make lint` and `make format` are run
Then both report zero violations in tests/dashboard/test_i00067_recent_activity_truncation.py
And the new `import html` line is placed in stdlib-import group with `os`
```

## Rollback Plan

- **Database**: Not applicable — no schema change.
- **Code**: `git revert <merge-commit>` restores the prior assertions. The change is two lines plus one import; reversal is mechanical.
- **Data**: No data loss possible — test-only change.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `tests/dashboard/test_i00067_recent_activity_truncation.py`

## TDD Approach

- Unit tests: None (test-only change; the file under modification IS the test).
- Integration tests: The existing 7 tests in the file must continue to pass; no new tests are added.
- Updated tests: The two assertions on lines 95 and 241 are rewritten to use `html.escape`. No other test in the file changes.

The S01 agent's "RED" phase is the existing run: confirm the file currently passes against main, then make the edit, confirm it still passes. The test of correctness is that the assertion now matches the actual rendered DOM (escaped form), which is verifiable by inspecting the template output and the `html.escape` documentation.

## Notes

- Use `html.escape(s, quote=True)` — the default `quote=True` already escapes `"` to `&quot;`, which is what Jinja2 emits inside attribute values. Do NOT call `html.escape(s)` without arguments and assume the default; explicit `quote=True` documents intent.
- Do NOT introduce a regex-based attribute-existence check as an alternative; the user-approved approach is `html.escape`. Regex would weaken the assertion (it would no longer verify the value, only the attribute's presence).
- Keep the change strictly to the two flagged lines plus the `import html`. Do not "improve" other assertions in the file, even if they look similar — finding [4] only flagged these two.
