# CR-00008 S02 — Code Review of S01 (API wire format)

**Work Item**: CR-00008
**Step**: S02
**Agent**: code-review-impl
**Reviews**: S01 (api-impl)

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/prompts/CR-00008_S01_Api_prompt.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S01_Api_report.md`
- `dashboard/routers/code_qa.py`
- `tests/dashboard/test_code_qa_sse_wire.py`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S02_CodeReview_report.md`

## Review Checklist

### Wire-format correctness

- [ ] Every emitted frame uses both `event:` and `data:` lines, separated from the next frame by `\n\n`.
- [ ] `token` events carry `{"b64": "..."}`; `b64` is base64 of UTF-8 bytes; round-trips exactly.
- [ ] `citation` events carry `n` (int, 1-based, monotonic), `label`, `url`, `snippet`.
- [ ] `done` events carry `{"ok": true}` and close the stream.
- [ ] `error` events carry `{"message": "..."}` and close the stream.
- [ ] Exactly one terminal event (`done` XOR `error`). No double-close. No silent hang.
- [ ] `ConnectionRefusedError`, `OSError` paths emit `error` then return.
- [ ] Request body shape unchanged; headers (`Cache-Control`, `X-Accel-Buffering`, `Connection`) preserved.

### Image stub

- [ ] Multipart POST returns 501 with the exact `{"detail": "Image attachments coming soon"}`.
- [ ] No part of the multipart body is persisted to disk or memory beyond recognition.

### Citations

- [ ] If citations are emitted, `n` is strictly increasing and unique.
- [ ] If citations are deferred (engine has no clean hook), the report explains it and no stubbed / hallucinated citations are emitted.

### Code hygiene

- [ ] Module ≤ 250 lines.
- [ ] `ruff check` clean. `mypy` clean (allow narrow `# type: ignore` with a reason).
- [ ] No new global state. No `asyncio.run(...)` in the main request loop.
- [ ] Base64 encoding is `b64encode(utf8_bytes).decode('ascii')` (the ASCII decode is safe; document it).

### Tests

- [ ] All five S01 tests exist, assert what their names claim, and pass.
- [ ] Tests mock `QAEngine.answer_stream`; no network calls.
- [ ] Test file uses `pytest` idioms consistent with `tests/CLAUDE.md`.

## Severity definitions

- **CRITICAL** — blocks merge; wire-format contract violated, security / injection risk, or tests fabricate a pass.
- **HIGH** — must-fix; correctness issue that a reasonable consumer would trip on.
- **MEDIUM** — should-fix in S02/S12 window; style/clarity/maintainability.
- **LOW** — optional polish.

## Report structure

Produce a markdown report with one section per finding:

```markdown
## Finding N: <short title>
- Severity: CRITICAL|HIGH|MEDIUM|LOW
- File: path:line
- Issue: ...
- Recommended fix: ...
```

End with a verdict block:

```
## Verdict
- Gating issues (CRITICAL+HIGH): N
- Non-gating issues (MEDIUM+LOW): N
- Ready for next step: yes|no
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S01",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blocking_next_step": false,
  "notes": ""
}
```
