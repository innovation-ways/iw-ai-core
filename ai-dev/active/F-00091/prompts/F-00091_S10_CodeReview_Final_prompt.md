# F-00091_S10_CodeReview_Final_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Review Step**: S10
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design doc
- `ai-dev/active/F-00091/F-00091_Functional.md` — Functional doc
- All seven impl reports under `ai-dev/work/F-00091/reports/` (S01, S02, S03, S04, S06, S07, S08)
- `ai-dev/work/F-00091/reports/F-00091_S09_CodeReview_report.md` — S09's per-step findings

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S10_CodeReview_Final_report.md`

## Context

This is the GLOBAL cross-agent review. S09 reviewed each step's deliverables in isolation. Your job is to spot issues that emerge ONLY when you look at the seven steps together:

- The S01 endpoint's JSON contract matches what S02's frontend actually consumes.
- S03's localStorage key shape doesn't clash with any other localStorage key elsewhere in `chat.js` (e.g., `iw-chat-assistant-project` from S02 vs. `iw-chat-active-tab:<projectId>` from S03 — colon vs dash difference, intentional).
- S06's payload shape exactly matches what S07's `_applyContextPct` consumes (`context_pct_status`, `used_tokens`, `window_tokens`, `context_pct_reason`). Field names match byte-for-byte.
- S04's backfilled values get exercised through the live get_tab path in S06 (no orphaned data).
- S08's tests reference real symbols and routes from S01/S02/S03/S06/S07.
- The functional doc and the technical design tell the same story.

Do NOT re-review what S09 already covered. Address gaps S09 missed because each step looked correct in isolation.

## Cross-Cutting Checklist

### 1. Wire compatibility

- The keys S07 reads (`session.context_pct_status`, `session.used_tokens`, `session.window_tokens`, `session.context_pct_reason`) match exactly what S06 emits. NO typo asymmetry.
- The endpoint URL S02 fetches (`/api/chat/projects`) matches what S01 registers (prefix included).
- The localStorage key S02 writes (`iw-chat-assistant-project`) matches what S03 reads when computing `_activeTabKey(...)`.

### 2. Acceptance Criteria coverage

For each AC in the design:

- AC1: tested by S08's integration test + S19's browser verification.
- AC2: tested by S03's storage test + S19's browser verification.
- AC3: tested by S06's known-state payload test + S07's markup test + S19's known-state browser shot.
- AC4: tested by S06's unknown-state payload test + S07's markup test + S19's unknown-state browser shot.

If any AC has zero automated test coverage and the failing automation gate would not catch a regression, that is a HIGH finding.

### 3. No regressions to existing chat features

- The two settings panel dropdowns (runtime / model) still work — S02's selector lives in the header, NOT in the settings panel.
- The "Clear" button's chat-history-load behaviour is unchanged.
- The slash-menu skills loader (referenced in the uncommitted diff of `chat.js`) still works.
- The tab strip's tab strip / close / duplicate / rename context menu still functions.
- The `/api/chat/tabs` endpoint's `default_runtime` field still appears.

### 4. Style and convention consistency

- All new JS matches the ES5 IIFE style. No `const`/`let`/arrow functions in helpers.
- All new CSS is appended to `chat.css` (NOT regenerated `styles.css`).
- All new HTML keeps Jinja2 `format` filter calls in `%`-style if any were added.
- Type annotations on new Python use `dict[str, Any]` and `int | None` etc. (PEP 604), consistent with the surrounding code.

### 5. Performance and DB load

- The new `/api/chat/projects` endpoint runs ONE query per request. No N+1.
- `get_tab`'s additional context-usage computation is bounded — providers cache is reused, no extra round-trips per call.
- The migration in S04 is a single UPDATE batch, not a per-row script-loop.

### 6. Security and scope

- No new endpoint added unsigned auth (existing chat router has none — consistent).
- No tokens, credentials, model API keys leaked into responses or logs.
- No new file outside `scope.allowed_paths` was committed.

### 7. S09 fix verification

For every CRITICAL or HIGH finding in S09's report:

- Confirm the implementer addressed it OR documented why it does not apply.
- If still open and unaddressed, escalate to your own report as a CRITICAL.

## Pre-Final Gates

Run on the integrated tree:

```bash
make lint
make format-check
```

Any NEW violations are CRITICAL findings.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-final-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00091/reports/F-00091_S10_CodeReview_Final_report.md"
  ],
  "preflight": {
    "format": "ok|skipped:review-only",
    "typecheck": "ok|skipped:review-only",
    "lint": "ok|skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "review-only step; no tests run",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW", "category": "wire-compat|ac-coverage|regression|conventions|perf|security", "path": "...", "summary": "..."}
  ],
  "blockers": [],
  "notes": ""
}
```
