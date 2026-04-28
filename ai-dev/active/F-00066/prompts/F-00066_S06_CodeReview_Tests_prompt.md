# F-00066_S06_CodeReview_Tests_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `ai-dev/active/F-00066/reports/F-00066_S05_Tests_report.md`
- `tests/unit/dashboard/test_code_qa_diagram_intercept.py`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S06_CodeReview_Tests_report.md`

## Review Checklist

- [ ] All 6 `_find_new_diagram_blocks` tests present and correct
- [ ] `test_sse_generator_emits_image_event_when_render_succeeds` — correctly decodes base64 SVG
- [ ] `test_sse_generator_no_image_event_when_render_returns_none` — no `image` event
- [ ] `test_sse_generator_no_image_event_when_render_unavailable` — flag gates the feature
- [ ] No live DB connections, no testcontainers — all external deps mocked (`MagicMock`/`AsyncMock`)
- [ ] Tests match project conventions (`tests/CLAUDE.md`)
- [ ] `pytest.mark.asyncio` used for all async tests

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
