# CR-00066 S04 — Frontend: Context Window Progress Bar

## What was done

Extended the item steps table to display a **Context** column with a color-coded progress bar showing the peak context token usage vs. the configured context window for each step.

### 1. `dashboard/routers/items.py` — `StepDetail` dataclass extended

Added three new fields to `StepDetail`:
```python
context_tokens_peak: int | None = None
context_tokens_last: int | None = None
context_window_tokens: int | None = None
```

In `_get_steps()`, the `last_run_sub2` subquery was extended to fetch `context_tokens_peak` and `context_tokens_last` from the most recent StepRun per step. A lookup dict `runtime_opt_tokens` was built from all enabled `AgentRuntimeOption` rows. For each step, `context_window_tokens` is resolved via the resolved runtime option ID (run override → step override → item override priority). All three new fields are populated on the `StepDetail`.

### 2. `dashboard/templates/fragments/item_steps_table.html` — Context column added

Added a `Context` column header (after the `Logs` th from CR-00065). The cell logic:
- **With window**: shows `peak/limit` in kilo-tokens, a 4px progress bar (green ≤60%, yellow ≤85%, red >85%), and the percentage label.
- **Peak only (no window configured)**: shows `peak` in kilo-tokens.
- **No data**: renders `—`.

Used `{% if ctx_pct > 100 %}{% set ctx_pct = 100 %}{% endif %}` instead of `[ctx_pct, 100] | min` per the Jinja2 `%`-style format filter requirement.

### 3. `dashboard/static/styles.css` — CSS appended

Four CSS rules for `.ctx-bar-track`, `.ctx-bar-fill`, `.ctx-bar-green`, `.ctx-bar-yellow`, `.ctx-bar-red`. No Tailwind recompile required (plain CSS, served as-is).

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | `StepDetail` fields + data loading in `_get_steps()` |
| `dashboard/templates/fragments/item_steps_table.html` | `Context` `<th>` + `<td>` with progress bar |
| `dashboard/static/styles.css` | Context bar CSS rules appended |

## Test Results

- **ruff lint** (`dashboard/routers/items.py`): ✅ clean (ignoring W292 unrelated to this step)
- **Jinja2 template lint** (`scripts/check_templates.py`): ✅ clean
- **format-check**: `dashboard/routers/items.py` reformatted by ruff, no issues
- **mypy**: 1 pre-existing error in `read_session_content` exception handler (line 2224, unrelated to this step); 1 error fixed by this step (line 541 `int | None` key to `dict.get()`, now guarded with `if resolved_opt_id`)

## Observations

- The `SessionLogSegment` TypedDict vs. `dict` error on line 2224 was pre-existing (introduced by CR-00065 S04, not this step). It is out of scope for S04.
- The W292 trailing-newline error on the migration file is also pre-existing and not part of this step.
- All three output files are correct and consistent with the design document.