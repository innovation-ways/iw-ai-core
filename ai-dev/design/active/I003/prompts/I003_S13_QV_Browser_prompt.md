# I003_S13_QV_Browser_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S13
**Agent**: QV_Browser

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document

## Output Files

- `ai-dev/design/active/I003/reports/I003_S13_QV_Browser_report.md` — Browser verification report
- `ai-dev/design/active/I003/evidences/post/` — Post-fix screenshots

## Context

You are performing browser verification for I003. The fix replaced server-side sorting (page reloads) with client-side JavaScript sorting on the History page.

## Browser Verification Script

Use `playwright-cli` (see `CLAUDE.md` for rules). **ALWAYS** run `playwright-cli kill-all` before starting.

```bash
# 1. Kill existing sessions
playwright-cli kill-all

# 2. Open the history page
playwright-cli open -s=i003 http://iw-dev-01:9900/project/iw-ai-core/history

# 3. Screenshot initial state
playwright-cli screenshot -s=i003 ai-dev/design/active/I003/evidences/post/I003-history-initial.png

# 4. Get accessibility snapshot to verify table structure
playwright-cli snapshot -s=i003

# 5. Click the "ID" column header to sort
playwright-cli click -s=i003 "th[data-sort-key='id']"

# 6. Screenshot after ID sort
playwright-cli screenshot -s=i003 ai-dev/design/active/I003/evidences/post/I003-history-sort-id.png

# 7. Click "ID" again to reverse sort
playwright-cli click -s=i003 "th[data-sort-key='id']"

# 8. Screenshot after reverse sort
playwright-cli screenshot -s=i003 ai-dev/design/active/I003/evidences/post/I003-history-sort-id-desc.png

# 9. Click "Duration" column to test numeric sort
playwright-cli click -s=i003 "th[data-sort-key='duration']"

# 10. Screenshot after duration sort
playwright-cli screenshot -s=i003 ai-dev/design/active/I003/evidences/post/I003-history-sort-duration.png

# 11. Verify NO page reload occurred (check network for no navigation requests)
playwright-cli network -s=i003

# 12. Verify no pagination UI exists
playwright-cli eval -s=i003 "document.querySelectorAll('a[href*=\"page=\"]').length === 0"

# 13. Verify sortTable function exists
playwright-cli eval -s=i003 "typeof window.sortTable === 'function'"

# 14. Verify data-sort attributes on rows
playwright-cli eval -s=i003 "document.querySelectorAll('tr[data-sort-id]').length > 0"

# 15. Clean up
playwright-cli close-all -s=i003
```

## Verification Criteria

1. **Sorting works**: Clicking column headers sorts the table instantly (no page reload)
2. **Sort direction toggles**: Clicking same header again reverses order
3. **Visual indicator**: Chevron icon appears on sorted column, rotates for direction
4. **All columns sortable**: ID, Type, Title, Status, Date, Duration all respond to clicks
5. **No pagination**: No "Prev/Next" buttons, no page numbers
6. **Filters work**: Type/Status/Date filters still function (if items exist to filter)
7. **No console errors**: Check browser console for JavaScript errors

## Pass/Fail Criteria

- **PASS**: All verification criteria met, screenshots captured
- **FAIL**: Any sorting column doesn't work, page reloads on sort click, pagination still visible, JS errors in console

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "QV_Browser",
  "work_item": "I003",
  "completion_status": "complete|partial|blocked",
  "verification_result": "pass|fail",
  "evidence_files": [],
  "findings": [],
  "blockers": [],
  "notes": ""
}
```
