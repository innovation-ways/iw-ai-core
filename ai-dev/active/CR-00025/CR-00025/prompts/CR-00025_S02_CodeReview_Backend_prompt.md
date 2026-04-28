# CR-00025 S02 — Code review of S01 (backend ingestion + CLI hooks)

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S02
**Agent**: code-review-impl
**Reviewing**: S01 (backend-impl)

---

## ⛔ Docker is off-limits

Same constraints as S01 — see prompt for full text. Read-only `docker
inspect` / `docker logs` are allowed. No state-changing docker commands.

## Input Files

- `uv run iw item-status CR-00025 --json` — runtime step state
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md`
- `ai-dev/active/CR-00025/reports/CR-00025_S01_Backend_report.md`
- All files in S01's `files_changed`:
  - `orch/evidences.py`
  - `orch/config.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/step_commands.py`
  - `docs/IW_AI_Core_Database_Schema.md`
  - `CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00025/reports/CR-00025_S02_CodeReview_Backend_report.md`

## Context

You are reviewing S01's implementation of the evidence-ingestion
pipeline. The historical context is critical: CR-00020 introduced the
table and dashboard reads but its S03 backend agent silently descoped
the ingestion hooks, leaving the table empty in production. **Your job
is to ensure that gap does not reopen.**

## Review Checklist (CR-specific)

### 1. Transaction scope (CRITICAL — this is AC4)

- The ingestion call in `approve` must run inside the **same** `with
  get_session() as session:` block as the status flip. If
  `ingest_phase_from_disk` raises (e.g., `EvidenceTooLargeError`), the
  session context manager must roll back — leaving the work item in
  `draft` status with zero new rows in `work_item_evidences`.
- Same for `step_done` and the post-ingest of browser_verification steps.
- Confirm by reading `orch/db/session.py`'s `get_session` to verify it
  rolls back on exception.

### 2. `ingest_phase_from_disk` correctness

- Signature matches the design: `(session, project_id, work_item_id,
  phase, root, step_id=None, max_bytes=None)`.
- Returns `int` (count of upserted rows, NOT a list of model
  instances — agents may want the count for logging).
- Does **not** call `session.commit()` — caller owns the boundary.
- Skips non-regular-file entries (subdirs, symlinks).
- Tolerates missing dir + empty dir without raising.
- **Hard-fails** on oversize via `EvidenceTooLargeError` — does not
  silently skip (this is option `a` per the user's call; verify it is
  not silently downgraded).
- Uses PostgreSQL `INSERT ... ON CONFLICT (project_id, work_item_id,
  phase, filename) DO UPDATE SET content=..., size_bytes=...,
  content_type=..., captured_at=now(), step_id=...`. The conflict target
  must be the `uq_evidence_per_file` constraint columns. Reject if the
  implementation uses a manual `select-then-insert` pattern (race
  condition) or omits the `step_id` overwrite (AC3).
- MIME type for `.yaml` / `.yml` is registered (these are not in
  Python's stdlib `mimetypes` map by default).

### 3. CLI hook correctness (AC1, AC2)

- `approve` hook fires before `session.flush()` and after the status
  flip — order matters because the DaemonEvent (if any) must reflect
  successful ingestion.
- `step_done` hook fires **only** when `step.step_type ==
  StepType.browser_verification`. A simple equality check, not a string
  match on agent name.
- `step_done` passes `step.step_id` (the string `"S11"`-style id), not
  `step.id` (the UUID PK).
- Path arguments: `approve` uses `repo_root` (from CLI ctx),
  `step_done` uses `Path.cwd()` (the worktree). Verify that's what the
  design specifies and that `repo_root` is non-empty / falls back
  sensibly.

### 4. Config knob

- `IW_CORE_EVIDENCE_MAX_BYTES` defaults to `5 * 1024 * 1024` (5 MiB).
- Read via `os.getenv` with `int(...)` conversion and a clear error on
  bad values.
- Wired into `orch/evidences.py:_default_max_bytes()` (or equivalent).

### 5. No agent-facing surface change

- `iw approve --help` and `iw step-done --help` must show no new flags.
- Existing argument signatures are unchanged.
- `validate_browser_evidence_present` is **not** removed — it still
  guards against empty post/ dirs.

### 6. Documentation sync

- `docs/IW_AI_Core_Database_Schema.md` mentions CR-00025 wires up the
  ingestion.
- `CLAUDE.md` Quick Navigation has the new `Evidences ingestion` row
  pointing at `orch/evidences.py`.

### 7. No new external dependencies

- Imports only stdlib (`mimetypes`, `pathlib`, `dataclasses`) and
  existing project dependencies (SQLAlchemy, `orch.config`,
  `orch.db.models`). Reject if a new dep is introduced.

### 8. Project conventions

- Sync SQLAlchemy 2.0 style with `Mapped[]`-aware queries.
- psycopg v3 (`postgresql+psycopg://`) — never psycopg2.
- Match the existing `output_error` / `click.exceptions.Exit` flow used
  by `approve` and `step_done`.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

1. `make test-unit` — must pass (S03 will add tests; existing tests must
   still pass).
2. `make lint`, `make typecheck`, `make format-check` — all green.
3. Manually trace through the `approve` and `step_done` paths in a
   fresh testcontainer if you doubt the transaction-rollback semantics.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Breaks AC1–AC8, data-loss risk, security issue | Must fix |
| **HIGH** | Significant bug, missing requirement, architecture violation | Must fix |
| **MEDIUM (fixable)** | Code quality issue, missed edge case | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Style/readability nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00025",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
