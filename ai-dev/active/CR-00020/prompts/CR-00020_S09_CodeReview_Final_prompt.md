# CR-00020_S09_CodeReview_Final_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S08

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design (ACs are authoritative)
- `ai-dev/active/CR-00020/reports/CR-00020_S01_Database_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S02_CodeReview_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S03_Backend_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S04_CodeReview_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S05_API_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S06_CodeReview_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S07_Tests_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S08_CodeReview_report.md`
- All production + test files touched by any step
- `docs/IW_AI_Core_Database_Schema.md`, `CLAUDE.md` — verify doc updates

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S09_CodeReviewFinal_report.md`

## Context

Cross-layer final review. Each per-step reviewer already validated their step in isolation. You are looking for **integration defects** — contracts between layers — and **completeness against the design doc**. The qv-browser step (S15) comes after you, so you are the last line before quality gates.

## Review Checklist

### 1. End-to-end path for AC1 (pre ingest)

Trace: `iw approve <item>` → `orch/cli/item_commands.py approve` → `ingest_phase_from_disk(phase='pre', step_id=None)` → `orch/evidences.py` → PostgreSQL INSERT ON CONFLICT → unique key matches schema from S01.

Integration bugs to catch:
- Enum name mismatch between Python `EvidencePhase.pre` and SQL `evidence_phase` type
- Unique constraint column order mismatch between schema and upsert `index_elements=[...]`
- `step_id` defaulting to something non-None in the ORM (should be NULL in DB for pre)

### 2. End-to-end path for AC2 (post ingest)

Trace: `iw step-done` → `step_commands.py step_done` → gated on `step.step_type == StepType.browser_verification` → `validate_browser_evidence_present` passes → `ingest_phase_from_disk(phase='post', step_id=<S>)`.

Catch:
- Missing gate (ingest runs for non-browser steps)
- Wrong cwd (uses repo_root when it should use Path.cwd()) — daemon launches from worktree
- `step_id` not set (NULL on post rows when it shouldn't be)

### 3. AC4 (rollback) — session scope

Walk the transactional boundary: if `ingest_phase_from_disk` raises `EvidenceOversizeError` inside the `approve` flow, does `output_error` → `sys.exit(1)` → context-manager rollback actually roll back the status flip? Check `orch/db/session.py` `get_session()` context — it should `rollback` on exception.

If `approve` does `session.flush()` BEFORE calling the ingest, the status flip is already persisted — flag CRITICAL.

### 4. AC5 + AC7 — dashboard source of truth

Verify the router reads DB first, FS fallback is scoped correctly, pre-phase never falls back. Trace the request:

- `GET /tab/evidences` → `_list_evidences(item, project, worktree_path)` → DB query by (project_id, item_id) → returns list. For post: if DB empty AND `worktree_path` set, FS fallback is triggered.
- `GET /evidence/<phase>/<filename>` → DB lookup first → returns `Response(content=row.content, media_type=row.content_type)`. Fallback only for post + active worktree.

### 5. AC6 — FK no cascade

Inspect the migration file. `op.create_table(... ForeignKeyConstraint(..., ondelete=None or omitted))`. Grep the migration for `'CASCADE'` — must be absent on the FK.

### 6. AC8 — graceful no-op

`ingest_phase_from_disk(base_dir=<missing_dir>)` returns empty result without error. Confirmed in unit tests (S07). Confirm the CLI hooks don't error on missing `evidences/` dir.

### 7. Template compatibility

`dashboard/templates/fragments/item_evidences.html` renders successfully against the new `_list_evidences` return shape. If the template references `evidence.abs_path`, verify the dict/dataclass returned still has that attribute.

### 8. Docs updates

- `docs/IW_AI_Core_Database_Schema.md`: new table entry, 19→20 tables, FK-no-cascade explicitly documented.
- `CLAUDE.md`: Quick Navigation row for `orch/evidences.py`.

### 9. `projects.toml` / `.iw-orch.json`

No changes expected. Verify none were accidentally made.

### 10. Unused code

Any leftover dead FS-reading code in `_list_evidences` / `item_evidence_file` that's unreachable after the rewrite should be removed. Flag MEDIUM_SUGGESTION if kept.

### 11. Skills / agents

No changes expected to `agents/opencode/qv-browser.md`, `skills/iw-execute/SKILL.md`, or the browser verification template. If any were modified, flag HIGH — out of scope for this CR.

### 12. Daemon archive behavior

`orch/daemon/batch_manager.py` archive hook still deletes `ai-dev/active/<id>/`. This is **expected** — the DB is now the durable copy. Verify no test relies on the FS directory surviving archive.

### 13. Quality gates

- `make lint`, `make format --check`, `make typecheck` all pass
- `make test-unit` + `make test-integration` + dashboard suite all pass
- No new pre-existing failures introduced (baseline was 8 lint errors in unrelated files — still exactly 8, no new ones)

### 14. Scope compliance

The design's File Manifest listed exact files to change. Any file modified that isn't in the manifest (beyond lock files, generated files) needs explicit justification in the review report.

## Severity Items to flag

- CRITICAL: AC1/AC2/AC4/AC5/AC6 not met by the integrated code path (even if individual steps passed their isolated review)
- CRITICAL: session.flush/commit happens before ingest in approve — rollback broken
- HIGH: template breaks with the new data shape
- HIGH: scope creep (changes outside the File Manifest)
- MEDIUM_FIXABLE: dead FS code left behind, docs not updated

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "CR-00020",
  "steps_reviewed": ["S01","S02","S03","S04","S05","S06","S07","S08"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_coverage": {
    "AC1": "pass",
    "AC2": "pass",
    "AC3": "pass",
    "AC4": "pass",
    "AC5": "pass",
    "AC6": "pass",
    "AC7": "pass",
    "AC8": "pass"
  },
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
