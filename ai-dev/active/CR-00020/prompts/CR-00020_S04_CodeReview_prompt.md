# CR-00020_S04_CodeReview_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design (ACs authoritative)
- `ai-dev/active/CR-00020/reports/CR-00020_S03_Backend_report.md` — S03 report
- All files listed in S03 `files_changed`
- `ai-dev/active/CR-00020/reports/CR-00020_S02_CodeReview_report.md` — S02 verdict (schema baseline)

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S04_CodeReview_report.md`

## Context

Review the ingest helper (`orch/evidences.py`), the config var, and the two CLI hooks (`approve` / `step_done`) produced in S03. Focus on transactional guarantees and the exact semantics the ACs demand.

## Review Checklist

### 1. Transactional scope (AC4)

- The ingest in `approve` runs INSIDE the same `with get_session() as session:` block as the status flip, BEFORE the outer `session.flush()`. An oversize failure MUST roll back both the status flip and any partial ingest.
- The ingest in `step_done` runs INSIDE the existing session, AFTER `validate_browser_evidence_present`, BEFORE flush. Same rollback guarantee.
- Confirm by tracing: what happens if `ingest_phase_from_disk` raises `EvidenceOversizeError`? The `output_error` call `sys.exit(1)`. Does the session roll back cleanly? (SQLAlchemy's context-manager `with get_session()` should — verify against `orch/db/session.py`.)

### 2. Two-pass oversize check (AC4)

- The helper MUST stat every file first and raise BEFORE any insert. If the first file is 100KB and the second is 10MB, zero rows should be inserted, not one. If the implementation inserts-as-it-goes and raises mid-loop, flag CRITICAL.

### 3. Idempotent upsert (AC3)

- Must use `postgresql.insert(...).on_conflict_do_update(...)` with `index_elements=['project_id', 'work_item_id', 'phase', 'filename']`.
- The SET clause must update `content`, `content_type`, `size_bytes`, `captured_at` on conflict.
- It MUST NOT update `id` — the primary key stays stable.

### 4. Non-browser no-op (AC8)

- The `step_done` hook is gated on `step.step_type == StepType.browser_verification`. No other step type should run ingest.
- The `approve` hook unconditionally runs for phase=pre — but if `pre/` doesn't exist, `ingest_phase_from_disk` returns empty (no error).

### 5. Path resolution

- `approve` uses `ctx.obj.get("repo_root")` or `Path.cwd()` — confirm `repo_root` is populated by `resolve_project(ctx)` for all approve invocations, even when `-p <id>` is passed from outside the repo.
- `step_done` uses `Path.cwd()` — correct for daemon-launched agents (`cwd=worktree_path`). But test flows that invoke `step-done` from outside the worktree (e.g. developer from repo root) would get the repo's active dir, which is also fine (files are there for live items).

### 6. MIME detection

- `mimetypes.guess_type(filename)` returns `(type, encoding)`. Use only `type`; fall back to `"application/octet-stream"` for None/unknown.
- Unknown extensions (`.yml` on some systems) → verify the fallback works. YAML is a common evidence format (snapshot files).

### 7. Non-regular files skipped

- Symlinks, devices, sockets, and directories inside `base_dir` must be skipped silently. Use `entry.is_file()` for the check (it follows symlinks; test whether that matches AC intent — symlinks-to-files OK, symlinks-to-dirs filtered out by `is_file()` returning False).
- This is a security consideration: a rogue symlink to `/etc/passwd` would be read as bytes. `entry.is_file()` + `entry.is_symlink()` combined is safer — flag as HIGH if symlinks are followed unchecked.

### 8. Config

- `IW_CORE_EVIDENCE_MAX_BYTES` default is `5 * 1024 * 1024` (5242880 bytes).
- Exposed via `load_config()` return value; the attribute name is consistent with existing config vars.
- If the env var is set to 0 or negative, config loading should fail fast (not silently accept).

### 9. Error messages

- The oversize error message includes the filename and its size_bytes in a human-readable format matching AC4's implied shape.

### 10. Test verification

- `make test-unit` passes.
- `make lint` / `make format` / `make typecheck` all pass against S03 files.

## Severity Levels

Same table as prior reviews (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

### Items to flag CRITICAL

- Ingest runs OUTSIDE the session-with-status-flip (no rollback on oversize)
- First-insert-then-check-size ordering (partial ingest)
- `ondelete="CASCADE"` sneaking into FK handling
- Symlink following without `is_symlink()` guard

### Items to flag HIGH

- Missing `on_conflict_do_update` (duplicates accumulate)
- `step_done` hook runs for non-browser step types
- MIME fallback missing for unknown extensions
- Config var missing the default

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00020",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
