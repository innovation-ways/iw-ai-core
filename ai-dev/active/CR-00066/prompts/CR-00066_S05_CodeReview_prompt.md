# CR-00066_S05_CodeReview_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Steps Being Reviewed**: S01–S04
**Review Step**: S05

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- Reports from S01–S04 in `ai-dev/work/CR-00066/reports/`
- All files in each step's `files_changed`

## Output Files

- `ai-dev/work/CR-00066/reports/CR-00066_S05_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in changed files = CRITICAL finding.

## Review Checklist

### 1. Database (S01)

- Three columns added with correct names, types (`Integer` nullable), and comments referencing CR-00066.
- Seed UPDATE targets only the 4 known models (claude-opus-4-7, claude-sonnet-4-6, haiku-4-5-20251001, MiniMax-M2.7) with value 200000.
- `downgrade()` drops all three columns cleanly.
- No unrelated drift in the migration.

### 2. Backend — token extraction (S03)

- `_extract_latest_tokens` reads from end of file (reverse iteration or tail-read) — must not read the entire file into memory for large sessions.
- Handles: FileNotFoundError, empty file, malformed JSON — all return `None`, no exception propagates.
- Only iterates `type == "message"` with `role == "assistant"` and `usage` present.
- `context_tokens_peak` is never decremented — guard `if latest_tokens > run.context_tokens_peak` is correct.
- `context_tokens_last` is updated unconditionally (can decrease after compaction).
- Only runs for `cli_tool == "pi"` and `session_file is not None`.
- Wrapped in try/except that logs but does not re-raise.

### 3. Frontend (S04)

- `StepInfo` dataclass has the three new nullable fields with correct types.
- `context_window_tokens` lookup uses `runtime_options` list (already loaded) — no extra DB query.
- Template uses `is not none` check (not just truthiness — `0` tokens is falsy but valid, though unlikely).
- `ctx_pct` is capped at 100 before passing to the `style="width: X%"` — no bar exceeds 100%.
- CSS color classes are `.ctx-bar-green`, `.ctx-bar-yellow`, `.ctx-bar-red` — consistent with design.
- CSS appended to `dashboard/static/styles.css`, not a new file.
- No Jinja2 `"{}"|format(...)` filter usage (use `"%s"|format(...)` style).
- Column header and cell align structurally with adjacent columns.

### 4. Tests (S01 + S03)

- S01 integration tests (`test_context_tokens_migration.py`): migration round-trip, seed values for known models, ORM read/write, downgrade drops all three columns.
- S03 unit tests (`test_step_monitor_token_poll.py`): 6 unit tests all cover the specified scenarios.
- Test for "peak never decreases" constructs a StepRun mock with existing `context_tokens_peak`, calls the helper with a lower value, verifies peak is unchanged.

### 5. Scope check

Changed files must be a subset of the design's **Impacted Paths**.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks functionality, scope violation |
| HIGH | Significant bug, missing requirement |
| MEDIUM_FIXABLE | Convention violation, missing edge case |
| MEDIUM_SUGGESTION | Optional improvement |
| LOW | Nitpick |

## Review Result Contract

```bash
uv run iw step-done CR-00066 --step S05 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S05_CodeReview_report.md
```

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00066",
  "steps_reviewed": ["S01", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint + format-check passed",
  "notes": ""
}
```
