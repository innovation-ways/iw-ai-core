# F-00041_S09_QVBrowser_prompt

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S09
**Agent**: QVBrowser
**Parallel With**: None — browser verification after integration tests pass

---

## Input Files

- `ai-dev/active/F-00041/F-00041_Feature_Design.md` — Design document
- `ai-dev/active/F-00041/reports/F-00041_S03_Tests_report.md` — Integration test report

## Output Files

- `ai-dev/active/F-00041/reports/F-00041_S09_QVBrowser_report.md`

## Context

Browser verification via `playwright-cli` for the F-00041 IDE tab UI.

**ALWAYS** run `playwright-cli kill-all` before starting.

The dashboard runs at **http://localhost:9900**.

## Requirements

### 1. Kill stale sessions

```bash
playwright-cli kill-all
```

### 2. Open the document detail page

Find a document in the iw-ai-core project that has published content. Use the dashboard
to navigate to any document, or use a known doc_id from the database.

```bash
playwright-cli open http://localhost:9900/project/iw-ai-core/docs
playwright-cli snapshot
# Find a doc link and click it
playwright-cli click <element-ref>
playwright-cli snapshot
```

### 3. Verify IDE tab exists

```bash
playwright-cli snapshot
# Find IDE tab button in the snapshot
```

Assert: IDE tab button is present in the page.

### 4. Click IDE tab and verify content loads

```bash
playwright-cli click <ide-tab-button-ref>
playwright-cli snapshot
```

Assert: IDE panel has loaded (guide editor panels are visible).

### 5. Verify type guide editor

Assert: A textarea for the type guide is visible with "Type Guide" label.

### 6. Screenshot

```bash
playwright-cli screenshot --filename=ai-dev/active/F-00041/evidences/post/ide_tab_loaded.png
```

### 7. Close

```bash
playwright-cli close
```

## Verification Criteria

- IDE tab button present on document detail page
- Clicking IDE tab loads guide editor panel without page reload
- Type guide textarea visible
- No JavaScript errors in console

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "QVBrowser",
  "work_item": "F-00041",
  "completion_status": "complete|partial|blocked",
  "verification_passed": true,
  "screenshot_path": "ai-dev/active/F-00041/evidences/post/ide_tab_loaded.png",
  "blockers": [],
  "notes": ""
}
```
