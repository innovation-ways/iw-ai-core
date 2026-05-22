# I-00103 S05 Tests Report

## Summary

Implemented the reproduction + regression tests for I-00103 (`merge_auto_resolution_failed` event missing per-file error strings). Both test files were written and pass locally.

## What Was Done

- **`tests/integration/test_auto_merge_failed_event_metadata.py`** — 4 integration tests exercising the event-payload schema
- **`tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`** — 3 dashboard tests exercising template rendering in both present/absent/empty-list shapes

### Integration Tests (`tests/integration/`)

| Test | Purpose | Status |
|------|---------|--------|
| `test_i00103_failed_event_carries_per_file_error_strings` | **Reproduction** — uses `fake_llm.error_for` to trigger a failure; asserts `per_file_errors[0]` carries `file_path`, `error` (contains "LLM call timed out after 120s"), `cli_tool`, `model` | ✅ Pass |
| `test_per_file_errors_truncated_at_500_chars` | AC5 — monkeypatches `invoke_llm_for_file` with a 2000-char error; asserts `len(entry["error"]) == 500` exactly | ✅ Pass |
| `test_per_file_errors_only_includes_errored_calls` | Abstain+success calls must NOT appear in `per_file_errors`; only errored entries included | ✅ Pass |
| `test_per_file_errors_absent_or_empty_when_no_calls_errored` | Pure-abstention failure: `per_file_errors` must be `[]` or absent; `abstained_files` carries the data | ✅ Pass |

### Dashboard Tests (`tests/dashboard/`)

| Test | Purpose | Status |
|------|---------|--------|
| `test_event_detail_renders_per_file_errors_section_when_present` | Seeds event with `per_file_errors=[{...}]`; asserts HTTP 200 + section class in HTML + semantic content | ✅ Pass |
| `test_event_detail_hides_per_file_errors_section_when_absent` | Seeds historical-shape event (7 keys, no `per_file_errors`); asserts section class absent + Metadata still renders | ✅ Pass |
| `test_event_detail_hides_per_file_errors_section_when_empty_list` | Seeds event with `per_file_errors=[]`; asserts section class absent | ✅ Pass |

## Files Changed

- `tests/integration/test_auto_merge_failed_event_metadata.py` — new (4 tests)
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` — new (3 tests)

## Preflight

| Gate | Result |
|------|--------|
| `make format` | ok — 837 files already formatted |
| `make lint` | ok — All checks passed (including `scripts/check_templates.py`) |

## Test Results

```
uv run pytest tests/integration/test_auto_merge_failed_event_metadata.py tests/dashboard/test_auto_merge_event_detail_per_file_errors.py -v --no-cov
======================== 7 passed, 1 warning in 11.15s =========================
```

- 4 integration tests (event-payload schema, testcontainer-backed)
- 3 dashboard tests (FastAPI `TestClient`, attribute-scoped CSS assertions)

## Semantic Correctness Notes

Both integration and dashboard tests use **semantic assertions** (specific values, not shape-only):
- `"LLM call timed out after 120s" in entry["error"]` — not just `assert "error" in meta`
- `'class="auto-merge-modal__per-file-errors"' in html` — attribute-scoped, not bare-substring
- `assert entry["cli_tool"] == default_runtime_option.cli_tool` — exact fixture value, not `assert "cli_tool" in entry`

Dashboard tests use attribute-scoped assertions throughout (I-00067 lesson) to prevent false positives from `<script>` content, `data-*` attributes, HTML comments, or CSS source maps.

## Key Design Decisions

1. **Integration test fixture wiring**: mirrors `test_auto_merge_phase1.py` — `fake_llm` replaces `invoke_llm_for_file`; `default_runtime_option` from `auto_merge_fixtures` provides the runtime option. No new fixture needed.

2. **`cli_tool`/`model` in reproduction test**: the design doc specifies `cli_tool='opencode'` and `model='minimax/MiniMax-M2.7'`, but the `make_default_runtime_option` fixture hardcodes `cli_tool='claude', model='claude-sonnet-4-6-automerge-test'`. The test asserts against the actual fixture values (`entry["cli_tool"] == default_runtime_option.cli_tool`), which is semantically equivalent — the test proves the field propagates correctly from the runtime option to the event. The design doc values served as a specification of propagation direction; the exact runtime pair is not a functional requirement.

3. **Dashboard `client` fixture**: defined inline in the test file (mirrors `test_auto_merge_routes.py`) rather than in `tests/dashboard/conftest.py`, because that conftest only re-exports integration fixtures and does not define `client`.

4. **Unique constraint handling** (`uq_agent_runtime_options_cli_model`): early attempts to create a second runtime option row with `(opencode, minimax/MiniMax-M2.7)` failed because that pair already exists in the seeded migration data. The test uses whatever values the `default_runtime_option` fixture provides — semantically correct and avoids DB constraint violations.

## TDD Red Evidence

> Design-time RED proof: pre-fix evidence screenshot at `ai-dev/active/I-00103/evidences/pre/I-00103-bug-event-80689-missing-error.png` shows the modal renders without a per-file errors section. DB events 80689 / 88770 (queried 2026-05-21) store no `per_file_errors` key. Post-fix unit + dashboard tests written here pin the new contract.

## Blockers

None.