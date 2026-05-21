# CR-00071_S02_CodeReview_prompt

**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Steps Being Reviewed**: S01
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00071 --json`
- `ai-dev/active/CR-00071/CR-00071_CR_Design.md` — Design document
- Report from S01 in `ai-dev/work/CR-00071/reports/`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/work/CR-00071/reports/CR-00071_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Review Checklist

### 1. `get_tab` Pi branch — `dashboard/routers/chat.py`

- The Pi branch now computes and injects `context_pct` into the `session` dict
  before its `return`.
- The computation is wrapped in `contextlib.suppress(Exception)` (or equivalent)
  — `get_tab` can never start returning an HTTP error because the percentage
  could not be computed.
- `context_pct` is injected **only** when `session` is a dict and a numeric
  value was computed; otherwise the field is **absent** — never `0`, never `None`.
- The return shape stays `{tab, session, messages}`; `context_pct` lives inside
  `session`.
- The Pi context-window lookup queries `agent_runtime_options.context_window_tokens`
  for `(cli_tool="pi", model=<model>)`, resolving the model from `tab.model`
  (`"pi/<model>"`). It returns `None` when no row matches or the column is `NULL`.
- The DB query lives in the **router** — not in `orch/chat/context_usage.py`.
- The router stays thin: arithmetic / token-shape normalisation is delegated to
  `context_usage.py`, not inlined.

### 2. `orch/chat/context_usage.py` (only if modified)

- If a Pi token normalizer was added, it is **pure** — no DB, no HTTP, no I/O.
- It defaults every token sub-field safely — no `KeyError` / `TypeError` on a
  partial or malformed Pi message.
- It does not alter the existing `compute_context_pct` / `lookup_context_window`
  / `resolve_model_from_tab` behaviour relied on by the OpenCode path.
- If S01 found Pi token keys already match the OpenCode shape, this file should
  be **unchanged** — confirm that is consistent with the S01 report.

### 3. No-regression for OpenCode

- The OpenCode branch of `get_tab` is **byte-for-byte unchanged** (AC4).
- `_providers_cache` / `_get_providers_cached` and the OpenCode `context_pct`
  block are untouched.

### 4. Graceful degradation

- AC2: no token data in Pi messages → `context_pct` omitted.
- AC3: model has `context_window_tokens = NULL` → `context_pct` omitted.
- No `0%` placeholder is ever produced for a "no data" case.

### 5. Performance

- No new uncached HTTP round-trip added to `get_tab` (it is polled every 5 s).
- The Pi context-window read is a single indexed DB query — acceptable
  uncached; confirm no accidental N+1 or per-message query.

### 6. Tests

- Integration tests assert AC1 (numeric `context_pct` with token data + a
  `context_window_tokens` row), AC2 (omitted, no token data), AC3 (omitted,
  `NULL` context window) for a **Pi** tab.
- Tests seed `agent_runtime_options` in a testcontainer — no live-DB connection.
- If a normalizer was added, `tests/unit/test_context_usage.py` covers it with
  assertions strong enough to fail on a logic regression.
- The S01 report records RED output (TDD compliance) for the new behavioural
  test, with a real `AssertionError`-class failure (not an import error).

### 7. Scope check

Changed files MUST be a subset of the design's **Impacted Paths**:
`dashboard/routers/chat.py`, `orch/chat/context_usage.py`, `tests/unit/**`,
`tests/integration/**`, `tests/dashboard/**`. Any other change is a CRITICAL
scope violation. No DB schema change, no migration, no frontend file change.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks functionality, scope violation |
| HIGH | Significant bug, missing requirement |
| MEDIUM_FIXABLE | Convention violation, missing edge case |
| MEDIUM_SUGGESTION | Optional improvement |
| LOW | Nitpick |

## Review Result Contract

```bash
uv run iw step-done CR-00071 --step S02 \
  --report ai-dev/work/CR-00071/reports/CR-00071_S02_CodeReview_report.md
```

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00071",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
