# I-00079_S04_CodeReview_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00079 --json`.
- `ai-dev/active/I-00079/I-00079_Issue_Design.md` — design document (`## Test to Reproduce`, `## Acceptance Criteria`, `## TDD Approach`, `## Regression Prevention`)
- `ai-dev/active/I-00079/reports/I-00079_S03_tests-impl_report.md` — S03 report
- `ai-dev/active/I-00079/reports/I-00079_S01_frontend-impl_report.md` — S01 report (the exact `primary_href` values that shipped)
- `tests/dashboard/test_empty_states.py` — the file S03 extended
- `dashboard/templates/macros/empty_state.html` — confirms the `<a href="..." class="empty-state__cta-primary">` shape the regex must match
- `dashboard/routers/help.py`, `dashboard/routers/system.py` — referenced by the consistency / resolves-to-200 tests

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S04_CodeReview_report.md` — review report

## Context

You are reviewing the reproduction + regression tests S03 added to `tests/dashboard/test_empty_states.py` for I-00079. The bug was: empty-state CTAs pointed at `/docs/<name>.md` and 404'd. S01 fixed the templates; S03's tests must (a) prove the fix and (b) prevent recurrence.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC1 (CTAs no longer 404), AC2 (regression test exists & fails pre-fix), AC3 (CTA targets agree with `help.py`'s `_SLUG_TO_DOC`).
- `## Test to Reproduce` and `## TDD Approach` — the expected test shapes and the attribute-scoping note (key on `class="empty-state__cta-primary"`, not bare substrings).
- `## Regression Prevention` — there must be a structural guard that scans `dashboard/templates/**` for any remaining `/docs/*.md` link target.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

New violations in the changed file → CRITICAL (`"category":"conventions"`). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Coverage vs the ACs

- Is there a per-page resolves-to-200 test for **all six** empty-state pages — queue (both CTA blocks), history, batches, all-active, docs library, research library? A missing page → HIGH.
- Does each per-page test assert the **specific expected destination** (`startswith("/system/docs/IW_AI_Core_CLI_Spec")` for queue, `…_Architecture` for history, `…_Daemon_Design` for batches & all-active, `…implementation/00_INDEX` for docs & research libraries) — not merely "some link returns 200"? Shape-only → MEDIUM (fixable).
- Does each per-page test assert the *negative* invariants too — `not href.startswith("/docs/")` and `".md" not in href.split("#")[0]`? These are what make the test FAIL against pre-fix code. Missing → HIGH (the test wouldn't have caught the bug).
- Is there a templates-wide scan test (`test_i00079_no_legacy_docs_md_links_in_templates` or equivalent) that walks `dashboard/templates/**/*.html` and asserts no `primary_href="/docs/` and no `"/docs/...md"` link target remains? Missing → HIGH (this is the Regression-Prevention requirement).
- Is there an AC3 consistency test comparing the CTA targets to `help.py`'s `_SLUG_TO_DOC`? Missing → MEDIUM (fixable).

### 2. Semantic correctness (I003 lesson)

- The href-extraction must be **attribute-scoped** on `class="empty-state__cta-primary"` — not a bare `"IW_AI_Core_CLI_Spec" in html` (false-positives on the help-popover link) and not `"empty-state__cta-primary" in html` (only proves the element exists, which it always did).
- The resolves-to-200 check must actually issue `client.get(target)` and assert `status_code == 200` — not just assert the string looks plausible.
- If S03 weakened any assertion (e.g. accepts any 2xx, or `!= 404` instead of `== 200`, or skips the docs-library 00_INDEX check) without a documented reason, that's a MEDIUM (fixable) — the design says do not weaken; report a real blocker instead.

### 3. Test hygiene

- Tests live in `tests/dashboard/test_empty_states.py` (correct location for `client`/`test_project` fixtures — I-00067).
- No live-DB usage (port 5433); no testcontainer needed; `encoding="utf-8"` on file reads.
- Existing marker tests in the file are not deleted or weakened.
- Style matches the rest of the file.

### 4. Did the tests actually run green?

Re-run them yourself: `uv run pytest tests/dashboard/test_empty_states.py -v`. Also `make test-unit` for a quick regression sanity. If S03 claimed `tests_passed: true` but they fail for you → CRITICAL. Report the actual counts.

### 5. Security

- No hardcoded secrets/URLs/ports. (None expected.)

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Tests don't run / fail; lint or format violation; a claimed pass that isn't | Must fix |
| HIGH | A page uncovered; missing negative invariants; missing templates-wide scan | Must fix |
| MEDIUM (fixable) | Shape-only assertion; weakened check; missing AC3 consistency test | Should fix |
| MEDIUM (suggestion) / LOW | Optional / informational | — |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00079",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "testing|code_quality|conventions|security", "file": "path", "line": 0, "description": "...", "suggestion": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
