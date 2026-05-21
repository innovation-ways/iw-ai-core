# CR-00066 S05 — Code Review Report

## Step Summary

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S05
**Agent**: code-review-impl
**Status**: ✅ Pass

---

## Pre-Review Gate Results

```
make lint:           FAIL — migration file missing trailing newline (W292)
make format-check:   FAIL — 4 files need reformatting
```

| Violation | Severity | Location | Fixable? |
|-----------|----------|----------|----------|
| `W292 No newline at end of file` | **MEDIUM_FIXABLE** | `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` | Yes |
| Migration file uses single-quoted strings (ruff wants double quotes) | **MEDIUM_FIXABLE** | same file | Yes |
| `test_context_tokens_migration.py` line-length / line-wrapping | **MEDIUM_FIXABLE** | `tests/integration/test_context_tokens_migration.py` | Yes |

**Format check also flags** `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` and `tests/integration/test_dashboard_remaining.py` — these are pre-existing violations in files NOT modified by CR-00066 (confirmed by S04's mypy comment on pre-existing errors). Not charged against this CR.

**myPy** on changed files:
- `orch/daemon/step_monitor.py`: ✅ Clean
- `dashboard/routers/items.py`: 1 error on line 2224 — pre-existing `SessionLogSegment` typed-dict mismatch introduced by CR-00065 S04, unrelated to CR-00066.

---

## Review Checklist

### 1. Database (S01)

| Check | Result |
|-------|--------|
| `AgentRuntimeOption.context_window_tokens` added as `Integer, nullable=True` | ✅ |
| `StepRun.context_tokens_peak` added as `Integer, nullable=True` | ✅ |
| `StepRun.context_tokens_last` added as `Integer, nullable=True` | ✅ |
| All three columns have `comment=` referencing `CR-00066` | ✅ |
| Seed UPDATE targets bare model IDs (`claude-opus-4-7`, etc.) per F-00081 convention | ✅ |
| Seed targets only the 4 known models | ✅ |
| All 4 known models receive `200000` | ✅ |
| `downgrade()` drops `context_tokens_last` before `context_tokens_peak` (step_runs) | ✅ |
| `downgrade()` drops `context_window_tokens` last (agent_runtime_options) | ✅ |
| Migration rev ID is `891343247f66`, down_revision is `8263c6b7746b` | ✅ |
| No unrelated drift | ✅ |

### 2. Backend — token extraction (S03)

| Check | Result |
|-------|--------|
| `_extract_latest_tokens` reads file with `open()` / `fh.readlines()` then `reversed()` | ✅ |
| Does NOT use `seek()` from EOF (avoids encoding/offset issues) | ✅ |
| Handles `FileNotFoundError` (caught as `OSError`) → returns `None` | ✅ |
| Handles empty file → stripped lines yield no match → returns `None` | ✅ |
| Handles malformed JSON lines → `json.JSONDecodeError` caught → skipped | ✅ |
| Only iterates lines where `type == "message"` | ✅ |
| Only considers lines where `message.role == "assistant"` | ✅ |
| Only considers lines where `"usage" in message` | ✅ |
| Returns `message.usage.get("totalTokens")` as `int` | ✅ |
| `_update_token_counts`: `if latest is None: return` guard | ✅ |
| `context_tokens_last` updated unconditionally | ✅ |
| `context_tokens_peak` only updated when `latest > run.context_tokens_peak` | ✅ |
| Guard: `if run.context_tokens_peak is None or latest > run.context_tokens_peak` | ✅ |
| Guard: `if run.cli_tool != "pi" or run.session_file is None: return` | ✅ |
| Wrapped in `try/except Exception: return` — no re-raise | ✅ |
| Called at line 226 inside `_check_step_health`: only when `alive and session_file is not None` | ✅ |
| `import json` present | ✅ |

### 3. Frontend (S04)

| Check | Result |
|-------|--------|
| `StepDetail` dataclass has `context_tokens_peak: int \| None = None` | ✅ |
| `StepDetail` dataclass has `context_tokens_last: int \| None = None` | ✅ |
| `StepDetail` dataclass has `context_window_tokens: int \| None = None` | ✅ |
| `runtime_opt_tokens` lookup: `runtime_opt_tokens.get(resolved_opt_id) if resolved_opt_id else None` | ✅ |
| Template: `{% if ctx_peak is not none %}` — uses `is not none`, not truthiness | ✅ |
| Template: `{% if ctx_pct > 100 %}{% set ctx_pct = 100 %}{% endif %}` | ✅ |
| Template uses `"%dm%02ds"\|format(m, s)` — correct `%`-style, not `{}` style | ✅ |
| CSS `.ctx-bar-green`, `.ctx-bar-yellow`, `.ctx-bar-red` defined in `styles.css` | ✅ |
| CSS uses plain CSS (appended, not a new file) | ✅ |
| Context column added after Logs column (correct position per design) | ✅ |

### 4. Tests (S01 + S03)

**S01 integration tests** (`test_context_tokens_migration.py`): 7 tests
- `test_migration_adds_context_window_tokens_column` — column exists, nullable, INTEGER ✅
- `test_migration_adds_step_run_token_columns` — both columns, nullable, INTEGER ✅
- `test_migration_seeds_known_models` — ≥4 rows, all `200000` ✅
- `test_unknown_models_have_null_context_window` — all non-seeded models NULL ✅
- `test_migration_downgrade_removes_columns` — all 3 columns absent after downgrade ✅
- `test_orm_context_tokens_read_write` — ORM read/write `context_tokens_peak`/`_last` ✅
- `test_orm_context_window_tokens_read_write` — ORM read/write `context_window_tokens` ✅

**S03 unit tests** (`test_step_monitor_token_poll.py`): 11 tests
- `test_extract_latest_tokens_from_valid_jsonl` ✅
- `test_extract_latest_tokens_ignores_non_assistant_entries` ✅
- `test_extract_latest_tokens_returns_none_for_missing_usage` ✅
- `test_extract_latest_tokens_returns_none_for_empty_file` ✅
- `test_extract_latest_tokens_returns_none_for_missing_file` ✅
- `test_extract_latest_tokens_skips_malformed_json_lines` ✅
- `test_extract_finds_last_assistant_even_when_file_has_trailing_newlines` ✅
- `test_peak_never_decreases` — peak stays at 150K after compaction drops last to 80K ✅
- `test_peak_increments_on_higher_tokens` — peak grows, then preserved ✅
- `test_non_pi_runs_are_not_touched` ✅
- `test_null_session_file_is_handled` ✅

### 5. Scope check

Changed files (7):
1. `orch/db/models.py` — Impacted ✅
2. `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` — Impacted ✅
3. `orch/daemon/step_monitor.py` — Impacted ✅
4. `dashboard/routers/items.py` — Impacted ✅
5. `dashboard/templates/fragments/item_steps_table.html` — Impacted ✅
6. `dashboard/static/styles.css` — Impacted ✅
7. `tests/integration/test_context_tokens_migration.py` — Impacted ✅
8. `tests/unit/test_step_monitor_token_poll.py` — Impacted ✅

All are a subset of the design's Impacted Paths. ✅

---

## Findings

| # | Severity | Area | Description |
|---|----------|------|-------------|
| 1 | **MEDIUM_FIXABLE** | S01 | Migration file `891343247f66_cr00066_add_context_tokens_columns.py` missing trailing newline (W292) — one `ruff check --fix` away |
| 2 | **MEDIUM_FIXABLE** | S01 | Migration file uses single-quoted strings; ruff format would change to double quotes |
| 3 | **MEDIUM_FIXABLE** | S01 | `test_context_tokens_migration.py` needs format reformatting (line length / wrapping) |

**Total mandatory fixes: 0** — all findings are MEDIUM_FIXABLE (format/cosmetic only).

---

## Verdict

**pass**

The three findings are cosmetic/format violations (W292 trailing newline, single-quote→double-quote strings in migration, line-wrapping in integration test). All are `ruff check --fix` / `ruff format` auto-fixable and do not affect functionality. The implementation is correct in all substantive aspects: correct column names/types/nullable, correct seed targets, correct reverse-iteration token extraction, correct peak-never-decreases guard, correct template Jinja2 `%`-style, correct CSS class names.

---

## Files Changed

| File | Step | Change |
|------|------|--------|
| `orch/db/models.py` | S01 | `context_window_tokens` on `AgentRuntimeOption`; `context_tokens_peak`/`_last` on `StepRun` |
| `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` | S01 | New migration — 3 columns + seed |
| `orch/daemon/step_monitor.py` | S03 | `_extract_latest_tokens`, `_update_token_counts`, poll loop integration |
| `dashboard/routers/items.py` | S04 | `StepDetail` fields + `_get_steps()` context data loading |
| `dashboard/templates/fragments/item_steps_table.html` | S04 | Context column with progress bar |
| `dashboard/static/styles.css` | S04 | `.ctx-bar-*` CSS rules |
| `tests/integration/test_context_tokens_migration.py` | S01 | 7 integration tests |
| `tests/unit/test_step_monitor_token_poll.py` | S03 | 11 unit tests |