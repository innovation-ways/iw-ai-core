## I-00095 — S06 Code Review (reviewing S05 frontend-impl)

### Scope reviewed
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/static/styles.css`
- Inputs consulted:
  - `uv run iw item-status I-00095 --json`
  - `ai-dev/active/I-00095/I-00095_Issue_Design.md`
  - `ai-dev/active/I-00095/reports/I-00095_S05_Frontend_report.md`

### Pre-review gates run
- `make lint` ✅ passed
- `make format` ✅ passed

### Checklist verification
1. **Sortable columns** ✅
   - Exactly 4 sortable headers render `<button type="button" ...>` for:
     - `timestamp` (`sort=created_at`)
     - `event_type`
     - `entity_id`
     - `verdict`
   - `message` and `actions` remain plain `<th>` text.

2. **`type="button"` on every button** ✅
   - Sort, filter, show-all, and pagination controls all explicitly set `type="button"`.

3. **URL construction** ✅
   - Sort buttons include: `page=0&page_size={{ page_size }}&sort={{ col_key }}&dir={{ next_dir }}`.
   - Active `type` filter is preserved via `request.query_params.get('type')`.
   - Sort changes reset to `page=0`.

4. **`next_dir` logic** ✅
   - Active column toggles desc↔asc.
   - Inactive column starts at desc.

5. **Chevron + `aria-sort`** ✅
   - Active desc: `↓`; active asc: `↑`; inactive: none.
   - Active `<th>` sets `aria-sort="ascending|descending"`.
   - Exactly one active `<th>` expected per render from validated route defaults.

6. **Pagination preserves sort/dir** ✅
   - Prev/Next include `&sort={{ sort }}&dir={{ direction }}`.

7. **CSS changes** ✅
   - Appended in `styles.css`.
   - New classes use `auto-merge-` prefix.
   - No conflict introduced with `bg-primary` / `border-primary` chip styles.

8. **Jinja2 `format` filter style** ✅
   - No new `format` filters introduced; no `%`-style violations.

9. **No `| safe` filter added** ✅
   - Confirmed none added.

### TDD RED evidence
- `n/a — template change`

### Test verification
- Command required by step:
  - `uv run pytest tests/dashboard/test_auto_merge_routes.py -v`
- Result:
  - Functional test outcomes: **51 passed**
  - Process exit: **non-zero** due repo-wide coverage gate (`20.07% < fail-under 50%`)

### Findings
1. **MEDIUM** — Required test command exits non-zero due coverage threshold
   - **File**: `tests/dashboard/test_auto_merge_routes.py` (command target; failure originates in global coverage gate)
   - **Line(s)**: n/a (runtime gate)
   - **Description**: The mandated verification command does not pass as an overall command, even though all targeted tests pass, because global coverage enforcement fails.
   - **Suggested fix**: For this step/workflow, run the scoped verification without coverage (`--no-cov`) or adjust CI/local gate strategy so targeted step checks are not blocked by repository-wide coverage unrelated to the touched frontend template/CSS files.

---

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S05",
  "verdict": "fail",
  "findings": [
    {
      "severity": "MEDIUM",
      "file": "tests/dashboard/test_auto_merge_routes.py",
      "lines": "n/a (runtime coverage gate)",
      "description": "Required test verification command exits non-zero due global coverage threshold, despite 51/51 targeted tests passing.",
      "suggested_fix": "Use scoped test verification without coverage for this step or decouple this workflow gate from global repository coverage fail-under."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": false,
  "test_summary": "make lint and make format passed. Required pytest command ran with 51 passed tests but failed overall due coverage fail-under 50% (actual 20.07%).",
  "notes": "Frontend S05 implementation satisfies the sortable-header acceptance checklist; only blocking issue is command-level coverage gate behavior."
}
```
