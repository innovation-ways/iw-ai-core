# I-00097 S03 — Tests Report

## What was done

Added 5 regression tests to `tests/dashboard/test_auto_merge_routes.py` covering the two I-00097 polish changes (token cost formatting and entity_id linkification).

## Tests added

| Test | Covers | Key assertions |
|------|--------|----------------|
| `test_token_cost_zero_renders_as_dollar_zero` | AC1 | `$0.000000` absent; cost line has `$0` exactly |
| `test_token_cost_nonzero_keeps_precision` | AC2 | Non-zero cost is non-`"0"` and has no trailing zeros |
| `test_entity_id_renders_as_link_for_work_item_ids` | AC3 | `CR-00057` cell contains `<a href="/project/iw-ai-core/item/CR-00057">` |
| `test_entity_id_renders_plain_when_not_work_item_id` | AC4 | `iw-ai-core` appears as text; no `/item/iw-ai-core` link |
| `test_entity_id_renders_dash_when_null` | AC5 | Entity_id cell renders `—` for null |

## Design decisions

- **No separate `project_factory` fixture** — tests reuse the existing `test_project` fixture for AC1/AC2/AC5. Tests needing `project_id="iw-ai-core"` (AC3/AC4) create/fetch the project via `db_session.merge`.
- **`re` imported at module top** — moved from mid-file to top-level to satisfy `ruff` E402 (module-level import not at top of file).
- **`Session` type via `TYPE_CHECKING`** — avoids importing `Session` at runtime (not needed at execution time, only for type annotations); defined in the `if TYPE_CHECKING:` block.
- **`daemon_event_factory` not used** — S01's implementation uses `db_session.add(DaemonEvent(...))` directly; no factory abstraction exists for `DaemonEvent` in `tests/integration/conftest.py`, so the tests construct rows directly.
- **Scope of entity_id cell assertion** — for AC5, the `—` check uses `font-mono` class as scope delimiter to avoid matching other cells in the row.
- **AC1 regex uses `<p\b[^>]*>`** — targets the specific cost line `<p>` rather than any `<p>` in the page, using word-boundary `\b` after the tag name.

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | 750 files already formatted |
| `make typecheck` | no issues in 255 source files |
| `make lint` | all checks passed |

## Test results

```
uv run pytest tests/dashboard/test_auto_merge_routes.py -v -k "token_cost_zero or token_cost_nonzero or entity_id_renders"
====================== 5 passed, 25 deselected in 24.56s =======================
```

Full file (30 tests):
```
====================== 30 passed in 38.78s =======================
```

All 30 tests in `test_auto_merge_routes.py` pass.

## TDD evidence

n/a — coverage step (tests-impl)

## Notes

- Coverage failure (`total of 18 is less than fail-under=50`) is expected — running a targeted subset of tests against a dashboard module that covers all routers triggers the global coverage threshold. The tests themselves pass cleanly.
- The `model_pricing` lookup for `claude-sonnet-4-6` was verified to exist in `orch/auto_merge_aggregator.py` at `$3/M in / $15/M out`.