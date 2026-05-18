# I-00093_S04_CodeReview_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00093 --json`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `ai-dev/active/I-00093/reports/I-00093_S03_Tests_report.md`
- `tests/dashboard/test_auto_merge_routes.py` (post-S03)
- `tests/integration/auto_merge_fixtures.py` (post-S03, if extended)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)** — every new test uses `client` and
   lives under `tests/dashboard/`. CRITICAL otherwise.
2. **Semantic correctness (I003)** — every assertion targets specific
   values. Red flags:
   - `assert "message" in html.lower()` → HIGH
   - `assert "metadata" in html` → HIGH (the word appears in many
     contexts)
   - `assert response.status_code == 200` as only assertion → CRITICAL
   What you want: factory-set strings (`"probe latency 412ms"`,
   `"runtime_reachable"`, `"claude-sonnet-4-6"`) — strings that
   uniquely identify the metadata payload.
3. **Coverage** — at minimum the five tests named in the design:
   - `test_event_modal_renders_message_and_metadata_for_health_probe`
   - `test_event_modal_renders_old_new_for_config_updated`
   - `test_event_modal_renders_verdict_info_for_resolved`
   - `test_event_modal_no_verdict_form_for_non_resolved_events`
   - `test_event_modal_heading_is_humanized`
   Missing any → HIGH.
4. **Heading-scoped regex** — the humanized-heading test must scope to
   the `<h3 id="auto-merge-event-title">` element, not search the whole
   document. A `assert "auto_merge_health_probe" in html` alone is
   shape-only and passes because the event_type also appears in the
   `type` row of the summary `<dl>`.
5. **Factories commit real rows** — `daemon_event_factory` and
   `merge_verdict_factory` MUST insert into the test DB, not mock the
   ORM. (CLAUDE.md: never mock the DB in integration tests; dashboard
   tests use the same testcontainer.)
6. **Attribute-scoped CSS class assertions (I-00067)** — if any test
   asserts class names, use `class\s*=\s*"[^"]*…[^"]*"` regex.
7. **Targeted-run discipline** — `tests_passed` reflects ONLY the
   touched test file's run.

### TDD RED Evidence

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Missing named tests in collection → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00093",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
