# CR-00066 S07 — Code Review Final Report

## Step Summary

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S07
**Agent**: code-review-final-impl
**Status**: ✅ Pass

---

## Pre-Flight Gate Results

| Check | Result | Notes |
|-------|--------|-------|
| `make lint` | ✅ All checks passed | W292 trailing newline, single-quote migration strings — fixed in S06 |
| `make format-check` | ✅ CR-00066 files clean | 2 pre-existing violations in unrelated files (excluded) |
| `make typecheck` | ✅ 272 source files, no issues | Pre-existing CR-00065 typecheck error resolved in S06 |
| `make test-unit` | ✅ 18/18 targeted tests passed | `test_step_monitor_token_poll.py` (11 tests) + `test_context_tokens_migration.py` (7 tests) |

---

## 1. S05 Finding Resolution

All 3 MEDIUM_FIXABLE findings from S05 were fully addressed by S06:

| Finding | Severity | Location | Status |
|---------|----------|----------|--------|
| W292 missing trailing newline in migration file | MEDIUM_FIXABLE | `891343247f66_cr00066_add_context_tokens_columns.py` | ✅ Fixed (S06) |
| Single-quoted strings in migration file | MEDIUM_FIXABLE | same file | ✅ Fixed (S06) |
| Integration test formatting (line-length) | MEDIUM_FIXABLE | `test_context_tokens_migration.py` | ✅ Fixed (S06) |
| Pre-existing typecheck error on `items.py` (CR-00065) | N/A | `dashboard/routers/items.py` | ✅ Fixed (S06) |

**Total mandatory fixes: 0** — no CRITICAL/HIGH findings were ever present.

---

## 2. AC Coverage Verification

### AC1: `context_window_tokens` seeded for known models

**Status: ✅ satisfied**

The seed UPDATE targets bare model IDs as stored in the DB column (`model`, not `display_name`):
```sql
UPDATE agent_runtime_options
SET context_window_tokens = 200000
WHERE model IN (
    'claude-opus-4-7',
    'claude-sonnet-4-6',
    'claude-haiku-4-5-20251001',
    'minimax/MiniMax-M2.7'
)
```

All 4 models are seeded to `200000`. Unknown models remain NULL (no backfill). The migration file uses double-quoted strings and has a trailing newline (S06 fixes applied).

Verified by `test_migration_seeds_known_models` and `test_unknown_models_have_null_context_window` (both passing).

### AC2: `context_tokens_peak` / `context_tokens_last` updated by daemon

**Status: ✅ satisfied**

In `_check_step_health` (step_monitor.py):
- Call guard: `if alive and run.session_file is not None` — only for alive pi runs with resolved session file
- `_update_token_counts` wrapped in `try/except Exception: return` — no re-raise
- `context_tokens_last` updated unconditionally with latest value
- `context_tokens_peak` only updated when `latest > run.context_tokens_peak` (never decreases on compaction)
- `_extract_latest_tokens` reads file with `readlines()` then `reversed()` — no `seek()` from EOF

Verified by `test_peak_never_decreases`, `test_peak_increments_on_higher_tokens`, `test_non_pi_runs_are_not_touched`, `test_null_session_file_is_handled` (all passing).

### AC3: Context column visible in step table

**Status: ✅ satisfied**

`item_steps_table.html` has a Context `<th>` header positioned immediately right of the Logs column. The `<td>` cell renders:
- `ctx_peak is not none` check (uses `is not none`, not truthiness) → shows content
- Pending/NULL steps show `—`

Verified by manual template review and `make lint` (Jinja2 `%`-style check passed).

### AC4: Correct color coding per threshold

**Status: ✅ satisfied**

Template logic:
```jinja2
{% if ctx_pct <= 60 %}{% set ctx_color_class = "ctx-bar-green" %}
{% elif ctx_pct <= 85 %}{% set ctx_color_class = "ctx-bar-yellow" %}
{% else %}{% set ctx_color_class = "ctx-bar-red" %}{% endif %}
```

CSS rules in `styles.css`:
- `.ctx-bar-green  { background-color: #22c55e; }` — 0–60% green ✅
- `.ctx-bar-yellow { background-color: #f59e0b; }` — 61–85% yellow ✅
- `.ctx-bar-red    { background-color: #ef4444; }` — >85% red ✅

### AC5: Completed step shows peak, not current

**Status: ✅ satisfied**

The template uses `step.context_tokens_peak` (not `context_tokens_last`) for the display value. The backend loads from `last_run.context_tokens_peak`. Peak is the all-time high-water mark and never decreases. For completed/failed steps this is the final value. For in-progress steps it reflects the running peak.

Verified by template: `{% set ctx_peak = step.context_tokens_peak %}`.

### AC6: NULL `context_window_tokens` — raw count only, no bar

**Status: ✅ satisfied**

Template logic:
```jinja2
{% if ctx_window %}
  {# renders bar + percentage + "XK / YK" #}
{% else %}
  <div class="text-xs text-muted-foreground">{{ (ctx_peak / 1000) | round(0) | int }}K</div>
{% endif %}
```

When `ctx_window` is None/falsy (model has NULL `context_window_tokens`), only the raw token count (`ctx_peak / 1000` → e.g., "80K") is rendered, with no percentage or progress bar.

---

## 3. New Issues Introduced by S06

No new issues were found. The S06 fix was purely cosmetic:
- Migration file reformatted with double-quoted strings + trailing newline
- Test file reformatted by `ruff format`
- `items.py` reverted to clean base and CR-00066 changes re-applied correctly

---

## 4. Migration Cleanliness

The migration (`891343247f66_cr00066_add_context_tokens_columns.py`) is clean:
- 3 columns added only (no unrelated drift)
- Seed UPDATE targets exactly 4 bare model IDs
- `downgrade()` drops `context_tokens_last` before `context_tokens_peak` (correct order for FK ordering in PostgreSQL if implied)
- `downgrade()` drops `context_window_tokens` last (correct)
- No import of alembic `op` unused (marked `# noqa: F401`)
- No trailing whitespace or W292 violations

---

## 5. Scope Confirmation

All 8 changed files match the design's Impacted Paths:

| File | Step | Verified |
|------|------|----------|
| `orch/db/models.py` | S01 | `context_window_tokens` on `AgentRuntimeOption`; `context_tokens_peak`/`last` on `StepRun` |
| `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` | S01 | 3 columns + seed, S06 fixes applied |
| `orch/daemon/step_monitor.py` | S03 | `_extract_latest_tokens`, `_update_token_counts`, poll integration |
| `dashboard/routers/items.py` | S04 | `StepDetail` dataclass + `_get_steps()` context loading |
| `dashboard/templates/fragments/item_steps_table.html` | S04 | Context column + progress bar + color classes |
| `dashboard/static/styles.css` | S04 | `.ctx-bar-*` CSS rules (3 rules) |
| `tests/integration/test_context_tokens_migration.py` | S01 | 7 integration tests |
| `tests/unit/test_step_monitor_token_poll.py` | S03 | 11 unit tests |

---

## Findings

**New findings: 0** — no issues found in the final review.

---

## Verdict

**pass**

All S05 findings resolved. All 6 ACs satisfied. No new issues introduced. `make lint`, `make typecheck`, and targeted tests all pass. Migration is clean (3 columns, correct seed, correct downgrade order).

---

## AC Coverage Summary

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `context_window_tokens` seeded for 4 known models | ✅ satisfied |
| AC2 | Daemon updates `context_tokens_peak`/`last` for pi runs | ✅ satisfied |
| AC3 | Context column visible in step table | ✅ satisfied |
| AC4 | Color coding correct per threshold (green/yellow/red) | ✅ satisfied |
| AC5 | Completed steps show peak, not current | ✅ satisfied |
| AC6 | NULL `context_window_tokens` → raw count only | ✅ satisfied |

---

## Subagent Result

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00066",
  "verdict": "pass",
  "all_prior_findings_resolved": true,
  "ac_coverage": {
    "AC1": "satisfied",
    "AC2": "satisfied",
    "AC3": "satisfied",
    "AC4": "satisfied",
    "AC5": "satisfied",
    "AC6": "satisfied"
  },
  "new_findings": [],
  "mandatory_fix_count": 0,
  "notes": "No CRITICAL/HIGH issues were ever present. S05 MEDIUM_FIXABLE findings (W292, single-quote migration, test formatting) all resolved by S06. Pre-existing CR-00065 typecheck error also resolved by S06 revert/re-apply of items.py. make lint/format-check/typecheck all green. 18/18 targeted tests pass."
}
```
