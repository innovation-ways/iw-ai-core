# CR-00065_S06_CodeReview_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Steps Being Reviewed**: S01–S05
**Review Step**: S06

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document (source of truth)
- Reports from S01–S05 in `ai-dev/work/CR-00065/reports/`
- All files listed in each step's `files_changed`

## Output Files

- `ai-dev/work/CR-00065/reports/CR-00065_S06_CodeReview_report.md`

## Context

Review the complete implementation of **CR-00065 — Live Agent Session Log Viewer** across all implementation steps (S01 Database, S03 Backend, S04 API, S05 Frontend).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Report any new violations in changed files as CRITICAL findings before reviewing logic.

## Review Checklist

### 1. Database (S01)

- `StepRun.session_file` column added with `nullable=True`, correct comment, proper type (`Text`).
- Alembic migration only adds `session_file` — no unrelated drift.
- `downgrade()` drops the column cleanly.
- Migration filename follows project convention (`xxxx_cr00065_add_session_file_to_step_runs.py`).

### 2. Backend — session_reader (S03)

- `read_session_content` handles: valid JSONL (all entry types), malformed lines (silent skip), empty file, non-pi run (log_file/log_content fallback), missing file (returns empty list, no exception).
- No hardcoded `~/.pi/` expansion — use `Path.home() / ".pi"` or `os.path.expanduser`.
- No uncaught exceptions that could crash the daemon.
- Pi slug derivation matches actual pi behaviour (verify against `~/.pi/agent/sessions/` directory names).
- Segments have correct structure: `type`, `text`, `collapsible` keys present.
- `max_chars` limit respected for log file reads.

### 3. Backend — step_monitor (S03)

- Session file resolution is wrapped in try/except — filesystem errors do not propagate.
- Resolution only runs for `cli_tool == "pi"` runs.
- `session_file` is only set once (guard: `if run.session_file is None`).
- DB commit is scoped correctly (no accidental commit of unrelated state).

### 4. API endpoint (S04)

- Route is correctly registered in `dashboard/routers/items.py`.
- 404 returned for unknown `project_id`, `item_id`, `step_id`.
- 200 with empty/error segment when no StepRun exists (not 404).
- `is_live` correctly computed from `RunStatus`.
- Template context includes all variables referenced in `session_log_popup_content.html`.
- No N+1 query — `StepRun` fetched once.

### 5. Frontend (S05)

- Logs column header and cell align with existing table column structure.
- htmx attributes on the trigger button are correct: `hx-get`, `hx-target="#session-log-modal-body"`, `hx-trigger="click"`.
- Modal is accessible: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`.
- Escape key + backdrop click close the modal.
- `session_log_popup_content.html` uses no `str.format`-style Jinja2 filters (`"%s"|format(v)` not `"{}"|format(v)`).
- CSS appended to `dashboard/static/styles.css` (not a separate file, not via Tailwind compile).
- No hardcoded pixel sizes that break responsive layout.
- The `is_live` polling div is correctly opened and closed (no unclosed Jinja2 `{% if %}`).

### 6. Tests (S03 + S04)

- Unit tests for `session_reader` cover all 7 specified scenarios.
- Dashboard integration tests use testcontainer (not mocked DB).
- Tests do not import from `orch.daemon.batch_manager` internals unnecessarily.

### 7. Scope check

Changed files must be a subset of the design's **Impacted Paths**. Any file outside that list is a CRITICAL scope violation.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks functionality, scope violation, security issue |
| HIGH | Significant bug, missing requirement |
| MEDIUM_FIXABLE | Code quality, convention violation, missing edge case |
| MEDIUM_SUGGESTION | Optional improvement |
| LOW | Nitpick |

## Review Result Contract

```bash
uv run iw step-done CR-00065 --step S06 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S06_CodeReview_report.md
```

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00065",
  "steps_reviewed": ["S01", "S03", "S04", "S05"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed on changed files",
  "notes": ""
}
```
