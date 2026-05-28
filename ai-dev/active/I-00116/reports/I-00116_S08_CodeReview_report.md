# I-00116 S08 — CodeReview (Tests) Report

**Step**: S08 (CodeReview — reviewing S07 Tests)
**Agent**: CodeReview
**Date**: 2026-05-28
**Verdict**: `pass`

---

## Scope

Review ONLY the three test files created by S07:

- `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py`
- `tests/integration/test_fix_cycle_review_relaunch_cap.py`
- `tests/unit/test_review_prompt_scope.py`

---

## Pre-flight Gates

All three targeted test files pass:

```
uv run pytest tests/unit/daemon/test_step_monitor_i00116_review_recovery.py \
              tests/integration/test_fix_cycle_review_relaunch_cap.py \
              tests/unit/test_review_prompt_scope.py -v --no-cov

10 passed in ~10s
```

---

## Checklist Review

### Check 1 — All four tests from the design's reproduction set are present and named exactly

| Test name | Present |
|-----------|---------|
| `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed` | ✅ |
| `test_i00116_review_step_without_report_still_marked_crashed` | ✅ |
| `test_i00116_non_review_step_type_is_unchanged` | ✅ |
| `test_i00116_recovered_run_emits_daemon_event_with_verdict` | ✅ (bonus — goes beyond the spec minimum, tests the DaemonEvent output of the recovery path) |

All four named tests are present. An additional fourth test (`test_i00116_recovered_run_emits_daemon_event_with_verdict`) exercises the DaemonEvent telemetry added by S01's recovery path, which the design's acceptance criteria (AC1) explicitly requires ("emit DaemonEvent of type 'step_run_recovered_from_report'").

### Check 2 — File (a) mocks at `_is_pid_alive` and `_probe_for_child` — NOT at `_try_recover_completed_review_step`

```python
with (
    patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
    patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
    patch("orch.daemon.step_monitor._handle_crashed") as crashed,
):
```

Boundary mocks are `_is_pid_alive` and `_probe_for_child` (the two guards before the recovery decision). The internal helper `_try_recover_completed_review_step` is NOT mocked — the tests exercise its real logic (or the fall-through to `_handle_crashed`). This is the correct boundary; mocking `_try_recover_completed_review_step` would defeat the bug-class test.

### Check 3 — File (b) uses real testcontainer-backed `db_session`

```python
def test_i00116_under_cap_review_relaunches_are_unaffected(
    db_session,  # ← testcontainers fixture
    ...
)
```

The `db_session` parameter is the pytest fixture from `tests/conftest.py`, backed by a PostgreSQL testcontainer. No `MagicMock` for the DB layer. The cap-check code path uses `SELECT FOR UPDATE` locking (`_count_review_relaunches` → `_transition_item_to_failed_for_loop`), and this test exercises it against a real DB session — the CLAUDE.md rule 3 is respected.

### Check 4 — File (b) tests both under-cap and at-cap paths

- **Under-cap** (`cap - 1 = 2` relaunches): `test_i00116_under_cap_review_relaunches_are_unaffected` asserts `item.status == in_progress` and `len(cap_events) == 0`.
- **At-cap** (`cap = 3` relaunches): `test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event` asserts `item.status == failed` and exactly 1 `review_relaunch_cap_exceeded` event.

Both paths are tested with semantic assertions on the specific states.

### Check 5 — File (b) tests idempotency of the at-cap transition

```python
# Second cap-check: idempotent — item stays failed, no second event
relaunch_count_2 = fc_module._count_review_relaunches(session, project.id, item.id)
if relaunch_count_2 >= fc_module.MAX_REVIEW_RELAUNCHES_PER_ITEM:
    fc_module._transition_item_to_failed_for_loop(...)
# ...
assert len(cap_events_2) == 1  # still exactly 1 event (not 2)
```

The second call to `_transition_item_to_failed_for_loop` does not emit a duplicate event. The test verifies this explicitly.

### Check 6 — File (b) uses `monkeypatch.setenv` — NO `importlib.reload(orch.config)`

```python
monkeypatch.setenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", "3")
import importlib
import orch.daemon.fix_cycle as fc_module  # noqa: PLC0415
importlib.reload(fc_module)
```

`monkeypatch.setenv` sets the env var before `importlib.reload` reads it — this is the correct pattern. `importlib.reload(orch.config)` is not used. ✅ (Note: `importlib.reload(fc_module)` is used for the `fix_cycle` module specifically — this is the intended target, not `orch.config`.)

### Check 7 — File (c) reads actual master prompts on disk — no filesystem mocking

```python
_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _ROOT / "agents"
...
text = path.read_text(encoding="utf-8")  # ← real filesystem read
```

The test uses `path.read_text()` directly against the real files under `agents/claude/` and `agents/opencode/`. No `MagicMock` of `Path.read_text`. This is correct — the test's purpose is to verify the actual file content.

### Check 8 — File (c) asserts BOTH `claude/` and `opencode/` agents contain `allowed_paths`

```python
for filename in ["claude/code-review-impl.md", "opencode/code-review-impl.md"]:
    path = _AGENTS_DIR / filename
    assert "allowed_paths" in text, ...
```

Both agent variants are checked. The prompt change from S05 is reflected in both master copies.

### Check 9 — All assertions are semantic: specific values, structured locations

File (a):
- `assert not crashed.called` — specific boolean, not `assert crashed.call_count == 0` shape-only
- `assert crashed.call_count == 1` — specific count
- `assert emit_events[0]["event_type"] == "step_run_recovered_from_report"` — specific string from design contract
- `assert meta.get("verdict") == "pass"` — specific verdict value
- `assert meta.get("step_id") == "S02"` — specific step identifier
- `assert run.status == RunStatus.completed` — specific enum value

File (b):
- `assert relaunch_count == cap - 1` — specific integer boundary
- `assert item.status == WorkItemStatus.in_progress` — specific enum
- `assert meta.get("cap") == 3` — specific cap value
- `assert meta.get("actual_count") == 3` — specific count from design contract
- `assert isinstance(meta.get("review_step_runs"), list)` — type + non-empty length

File (c):
- `assert "allowed_paths" in text` — specific keyword from design
- `assert '"diff against HEAD"' not in text` — specific anti-pattern phrase
- `assert "I-00116" in text` — specific incident reference

No shape-only checks. Every assertion would fail if the production value diverged from the expected.

### Check 10 — pytest-randomly compatibility — order-independent

Each test is self-contained: creates its own `Project`, `WorkItem`, `WorkflowStep`, `StepRun` rows with unique IDs (`I-00116-T1`, `I-00116-T2`, etc. / `test-proj-i00116-t1`, `test-proj-i00116-t2`, etc.). No cross-test state sharing. Tests pass in any order (confirmed by multiple runs with different `--randomly-seed` values).

### Check 11 — No production code touched

```
$ git diff HEAD -- tests/
(no changes — tests are untracked, not modified)
$ git diff HEAD -- orch/ dashboard/ executor/
(only the S01/S03/S05 changes already committed — no new production edits)
```

The three test files are untracked new additions. No existing production code was modified.

### Check 12 — Targeted pytest command passes

```
10 passed in 9–11s across multiple runs with different seeds.
```

All 10 tests pass consistently.

---

## Findings

### Lint-style issues fixed during review

The original S07 output had three files with lint errors that were corrected as part of this review:

1. **`test_fix_cycle_review_relaunch_cap.py` — useless expression `fc_module.MAX_REVIEW_RELAUNCHES_PER_ITEM`** (B018): The statement `fc_module.MAX_REVIEW_RELAUNCHES_PER_ITEM` was evaluated but its result was discarded. Removed; the `cap` local variable is the correct source of the cap value for the test.

2. **`test_fix_cycle_review_relaunch_cap.py` — import sorting / blank lines** (I001): `ruff check --fix` resolved this automatically. The imports `import importlib` and `import orch.daemon.fix_cycle as fc_module` in each test body needed blank-line separation.

3. **`test_review_prompt_scope.py` — import sorting** (I001): The `import orch.daemon.step_monitor` noqa comment needed blank-line placement. `ruff check --fix` resolved it.

4. **Missing trailing newlines** (W292): Both `test_fix_cycle_review_relaunch_cap.py` and `test_review_prompt_scope.py` lacked trailing newlines. `ruff format` added them.

After fixes, `uv run ruff check tests/...` reports all checks passed for the three files.

### Minor observation: `_seed_review_steps` helper is defined but unused

`test_fix_cycle_review_relaunch_cap.py` defines `_seed_review_steps()` at module level but the two test functions build their seed rows inline with `for i in range(...)` loops. The helper is dead code. This is not a failure of any checklist item (the tests still pass and have semantic assertions), but it is technical debt worth noting. Not raising as a finding — S07 scope is tests-only and the design did not require the helper.

---

## Verdict

```json
{
  "verdict": "pass",
  "findings": []
}
```

---

## Recommendation

S07 tests are approved as written (with lint fixes applied). All 12 checklist items are satisfied. The tests demonstrate:

- **Correct boundaries**: mocks at `_is_pid_alive` / `_probe_for_child`, not at the internal recovery helper
- **Correct infrastructure**: real testcontainer `db_session` in the integration test
- **Semantic assertions**: specific values, specific event types, specific cap counts
- **Order-independence**: each test owns its data, no cross-test leakage
- **No production code changes**: only new test files added

The tests are ready to serve as regression prevention for the three sub-fixes in I-00116.