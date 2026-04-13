# F-00021_S12_QVBrowser_prompt

**Work Item**: F-00021 — Research Panel in AI Dashboard
**Step**: S12
**Agent**: qv-browser

---

## Context

Capture post-implementation evidence for the Research panel and verify the feature works
end-to-end in the browser.

## Steps

1. Check that the dashboard is running:
   ```bash
   curl -sf http://localhost:9900/health && echo "Dashboard: UP" || echo "Dashboard: DOWN"
   ```
   If DOWN, report as BLOCKED.

2. Open the dashboard and navigate to the research panel:
   ```bash
   playwright-cli kill-all
   playwright-cli open http://localhost:9900
   playwright-cli snapshot
   ```

3. Navigate to the first available project's research page and screenshot:
   ```bash
   playwright-cli screenshot ai-dev/active/F-00021/evidences/post/F-00021-after.png
   ```

4. Verify the Research link appears in the sidebar.

5. Close and report.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "F-00021",
  "completion_status": "complete|blocked",
  "evidence_files": ["ai-dev/active/F-00021/evidences/post/F-00021-after.png"],
  "notes": ""
}
```
