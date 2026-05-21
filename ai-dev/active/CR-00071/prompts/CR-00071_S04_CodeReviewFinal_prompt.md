# CR-00071_S04_CodeReviewFinal_prompt

**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Step**: S04
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00071 --json`
- `ai-dev/active/CR-00071/CR-00071_CR_Design.md` — Design document
- All reports in `ai-dev/work/CR-00071/reports/`
- All files changed across S01 and S03

## Output Files

- `ai-dev/work/CR-00071/reports/CR-00071_S04_CodeReviewFinal_report.md`

## Task

Perform a global, cross-step review of the complete CR-00071 change. Verify the
Pi context-usage path is correct, consistent, and forms one working end-to-end
feature with the existing CR-00067 frontend.

### Final Review Checklist

- **Acceptance criteria** — AC1–AC5 in the design are satisfied by the combined
  S01 + S03 output.
- **End-to-end contract** — the field the Pi branch injects
  (`session.context_pct`) is exactly the field `chat.js` reads
  (`data.session.context_pct`). Same name, same nesting as the OpenCode path —
  the CR-00067 frontend consumes it with zero change.
- **OpenCode untouched** — the OpenCode branch of `get_tab`, `_providers_cache`,
  `_get_providers_cached`, and the existing `context_usage.py` public functions
  are byte-for-byte unchanged (AC4). Confirm via `git diff`.
- **Pi context-window source** — the lookup reads
  `agent_runtime_options.context_window_tokens` for `(cli_tool="pi", model)`;
  it correctly handles the no-row and `NULL` cases by yielding `None`.
- **Layer boundary** — the DB query is in `dashboard/routers/chat.py`; anything
  added to `orch/chat/context_usage.py` is pure (no DB, no I/O).
- **Graceful degradation** — when Pi has no token data, no `context_window_tokens`,
  or the computation raises, `context_pct` is omitted and `get_tab` still returns
  `{tab, session, messages}` with HTTP 200. No `0%` placeholder. Worst case is
  byte-equivalent to pre-CR behaviour.
- **Performance** — no uncached HTTP round-trip added to the 5-second `get_tab`
  poll; the Pi context-window read is a single indexed DB query.
- **Pi token-shape decision** — the S01 report states which of the three
  outcomes (keys match / keys differ + normalizer / no token data) was found,
  and the code matches that decision (normalizer present iff keys differ).
- **Scope** — every changed file is within the design's Impacted Paths. No DB
  schema change, no migration, no new/removed endpoints, no frontend file change.
- **Conventions** — `dashboard/CLAUDE.md` and `orch/CLAUDE.md` honoured; router
  stays thin.

## Pre-Review Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Subagent Result Contract

```bash
uv run iw step-done CR-00071 --step S04 \
  --report ai-dev/work/CR-00071/reports/CR-00071_S04_CodeReviewFinal_report.md
```

```json
{
  "step": "S04",
  "agent": "code-review-final-impl",
  "work_item": "CR-00071",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
