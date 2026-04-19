# F-00055_S04_CodeReview_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` — (AC1, AC2, AC3, AC4, AC6, AC9; Invariants 1–7, 9, 10)
- `ai-dev/active/F-00055/reports/F-00055_S03_Backend_report.md`
- `orch/rag/qa.py`, `orch/rag/evidence.py`, `orch/rag/git_log_resolver.py`, `orch/rag/classifier.py` (or equivalent paths from S03)
- Test files from S03

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S04_CodeReview_report.md`

## Review Focus

Review S03 (phase-aware QAEngine + hybrid retrieval + classifier + citation allowlist). Produce findings with CRITICAL/HIGH/MEDIUM/LOW severities.

### Must-check items

1. **Phase sequence correctness (Invariant 2)** — phases emit in exact order `retrieving → finding_items → reading_docs → composing`; no phase fires twice; no phase skipped in work-item-aware path; no phase events in code-only path (Invariant 3).
2. **Citation allowlist (AC4, Invariant 1)** — every emitted citation chip references an ID in the evidence bundle; structural enforcement (not prompt-only).
3. **Per-project isolation (Invariant 9)** — every retrieval layer scopes by `project_id`; no cross-project leakage.
4. **Git-log resolver safety** — subprocess has timeout; no shell-injection risk; handles files with spaces / unicode; falls back gracefully on errors.
5. **Classifier fallback (AC3)** — LLM timeout defaults to `code_only`; slash commands (`/why`, `/history`, `/findusages`) always force `workitem_aware`.
6. **Default pipeline preserved (AC9, Invariant 10)** — `context_level == "module"` filter, `/diagram` block, and all existing behavior in `_build_system_prompt` are untouched when classifier returns `code_only`.
7. **Retrieval parallelism** — three retrieval sources run concurrently; no accidental serialization.
8. **Evidence bundle completeness** — retrieval cutoff timestamp populated; work items sorted ASC by `created_at`.
9. **Error handling** — LanceDB unavailable, Postgres FTS empty, git log empty, subprocess timeout: all handled gracefully without 500-ing the stream.
10. **Type safety** — `answer_stream` yield type change is backwards-compatible OR a new method is introduced; mypy passes.
11. **Test coverage** — all 5 required unit test files exist and cover the surface areas listed in S03.

### Project conventions

- psycopg v3, sync SQLAlchemy 2.0.
- `monkeypatch.delenv()`, never `importlib.reload`.
- Testcontainers only — no port 5433 in tests.
- No hardcoded model names; use `config.resolved_*_model()`.

## Review Output Format

Same as S02: findings table + verdict + result contract JSON.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve|approve-with-fixes|reject",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "notes": ""
}
```
