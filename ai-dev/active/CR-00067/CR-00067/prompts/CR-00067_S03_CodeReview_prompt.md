# CR-00067_S03_CodeReview_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Steps Being Reviewed**: S01, S02
**Review Step**: S03
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- Reports from S01 and S02 in `ai-dev/work/CR-00067/reports/`
- All files in S01's and S02's `files_changed`

## Output Files

- `ai-dev/work/CR-00067/reports/CR-00067_S03_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = CRITICAL finding.

## Review Checklist

### 1. Backend — `orch/chat/context_usage.py`

- The module is **pure** — no DB, no HTTP, no I/O. Computation logic lives here,
  not inline in the router.
- Token summing defaults **every** sub-field (`input`, `output`, `reasoning`,
  `cache.read`, `cache.write`) to `0` when absent — no `KeyError` / `TypeError`
  on a partial `tokens` object.
- The "no data" path returns `None` — never `0`. A missing assistant message,
  empty `messages`, or `context_window` of `None` / `0` / negative all yield
  `None`.
- The percentage is clamped to `[0, 100]`.
- The most-recent assistant message is selected (not the first).

### 2. Backend — `dashboard/routers/chat.py` (`get_tab`)

- `context_pct` is injected into the `session` dict only when `session` is a
  dict and a numeric value was computed; otherwise the field is **absent** (not
  `0`, not `None`).
- The `{tab, session, messages}` return shape is preserved.
- The `/config/providers` model-limit lookup is **cached** — no new uncached
  HTTP round-trip is added to every `get_tab` call (it is polled every 5 s).
- Any failure to fetch providers / compute usage is swallowed — `get_tab` never
  starts returning an error because the percentage could not be computed.
- The router stays thin — it delegates arithmetic to `context_usage.py`.
- Pi path: `context_pct` is computed when Pi data allows, or cleanly omitted.

### 3. Frontend — `composer.html`

- A `<span id="chat-assistant-context-pct">` exists in the Send/Abort row.
- It is positioned **before** `#chat-assistant-clear` in DOM order (renders to
  the left of "Clear").
- It carries the `hidden` class by default.
- It has an `aria-label` and `title` for accessibility.
- No other composer control (model bar, Clear, Abort, Send) was modified.

### 4. Frontend — `chat.css`

- Rules were **appended** to `dashboard/static/chat_assistant/chat.css` — not a
  new file, not `styles.css`.
- `.chat-assistant-context-pct` base rule uses the neutral muted colour.
- `.is-warn` (amber) and `.is-crit` (`var(--destructive)`) modifier rules exist.
- The `hidden` utility class is NOT redefined.

### 5. Frontend — `chat.js`

- A single shared helper (`_refreshContextPct` or equivalent) performs the
  fetch — the `fetch('/api/chat/tabs/...')` block is NOT duplicated between the
  poll and the on-activation call.
- The percentage is `Math.round`-ed — no fractional `%` rendered.
- A missing / `null` / `NaN` `context_pct` results in the element being
  `hidden` with empty `textContent` — NOT `0%`.
- Colour-band logic: `>=90` → `is-crit`; `>=70 && <90` → `is-warn`; `<70` →
  neither. Both modifier classes are removed before the correct one is applied.
- The immediate fetch on activation is inside `_activateTab()` — value shows
  without waiting for a message to be sent.
- When there is no active tab, the element is hidden with empty text — no stale
  percentage left on screen.
- `title` / `aria-label` are updated to include the live percentage.
- Fetch errors are swallowed silently (matches existing convention).

### 6. Tests

- `tests/unit/test_context_usage.py`: assertions are strong enough to fail on a
  regression of the helper (token summing, clamping, every `None` path). The S01
  report records RED output (TDD compliance).
- Integration test: `GET /api/chat/tabs/{id}` returns a correct numeric
  `session.context_pct` with token data, and omits it without.
- `tests/dashboard/test_chat_context_pct_template.py`: asserts element exists,
  is before `#chat-assistant-clear`, and is `hidden` by default.

### 7. Scope check

Changed files MUST be a subset of the design's **Impacted Paths**:
`orch/chat/context_usage.py`, `dashboard/routers/chat.py`, `composer.html`,
`chat.css`, `chat.js`, `tests/unit/**`, `tests/integration/**`,
`tests/dashboard/**`. Any other change is a CRITICAL scope violation.

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
uv run iw step-done CR-00067 --step S03 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S03_CodeReview_report.md
```

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "CR-00067",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
