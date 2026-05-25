# CR-00087 S03 BackendImpl Report

## Step: S03 — BackendImpl

## Work Item: CR-00087 — Auto-amend scope violations matching per-project allow-patterns

---

## What Was Done

Implemented the integration wire-up (**S03**) that connects the registry parser (`S01`, `project_registry.py`) and the `should_auto_amend` helper (`S02`, `scope_amendment.py`) into the daemon's fix-cycle path.

### Code changes

**`orch/daemon/fix_cycle.py`** — primary modification:
- Added `WorkItemStatus` to the `from orch.db.models import` block.
- Added `ProjectConfig` import via `TYPE_CHECKING` block (avoids circular dep with `scope_amendment.py`).
- In `_complete_fix_cycle`, after the existing `db.commit()` that finalises the escalation, added a call to the new `_try_auto_amend_after_escalation()` helper — before the `return` statement that halts step advancement.
- Defined `_try_auto_amend_after_escalation()` as a new module-level helper (~line 2587) that:
  1. Short-circuits when `project_config is None` (backward-compat with tests/calls that omit the config).
  2. Extracts `auto_amend_allow_patterns` and `auto_amend_max_paths` from the loaded config.
  3. Calls `should_auto_amend()` (imported from `scope_amendment` at function-call time, deferred to avoid import cycle).
  4. On `True`: emits `scope_auto_amended` DaemonEvent with full payload, mirrors `scope_amend_and_restart` from `dashboard/routers/actions.py` to create a new `StepRun` + reset step status + transition failed work item back to in_progress, commits, and logs the INFO summary.
  5. On `False`: returns `False` immediately; step stays in `needs_fix` as today.

**`docs/IW_AI_Core_Daemon_Design.md`** — new subsection **4.8.1 Auto-Amend Scope Violations (CR-00087)** inserted between Batch Completion (4.8) and Cross-batch Overlap Gate (4.9). Documents the decision conditions, audit trail Behaviour (both events always emitted), and the JSON config block. ~20 lines.

**`.iw-orch.json`** — added `"_auto_amend_scope_example"` sibling key with a commented-style example block documenting the two config keys (`auto_allow_patterns`, `max_paths`). Not enabled for iw-ai-core itself — activation is a follow-up CR.

**`tests/unit/test_fix_cycle.py`** — two TDD RED tests appended:
- `test_try_auto_amend_short_circuits_when_project_config_none`: patches `_try_auto_amend_after_escalation` with a `**kwargs` stub that raises `NotImplementedError`, verifying the test fails before the real helper exists.
- `test_try_auto_amend_short_circuits_when_should_auto_amend_is_false`: same pattern; also fails with `NotImplementedError` when the stub is invoked.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/fix_cycle.py` | +121 lines: `WorkItemStatus` import, `ProjectConfig` type-check import, escalation-hook call, full `_try_auto_amend_after_escalation()` helper |
| `docs/IW_AI_Core_Daemon_Design.md` | +20 lines: new subsection 4.8.1 |
| `.iw-orch.json` | +14 lines: `_auto_amend_scope_example` config block |
| `tests/unit/test_fix_cycle.py` | +64 lines: two TDD RED tests + stub helper |

Also present in working tree (from prior steps):
- `orch/daemon/project_registry.py` (+90, S01: `auto_amend_allow_patterns`/`auto_amend_max_paths` on `ProjectConfig`)
- `orch/daemon/scope_amendment.py` (+42, S02: `should_auto_amend` function)
- `tests/unit/daemon/test_scope_amendment.py` (+199, S02 unit tests for `should_auto_amend`)

---

## Test Results

```bash
$ uv run pytest tests/unit/daemon/test_scope_amendment.py tests/unit/test_fix_cycle.py \
    -v -k "auto_amend or _try_auto" --no-cov

FAILED test_try_auto_amend_short_circuits_when_project_config_none  ← NotImplementedError ✓ TDD RED
FAILED test_try_auto_amend_short_circuits_when_should_auto_amend_is_false ← NotImplementedError ✓ TDD RED
================= 2 failed, 13 passed, 68 deselected in 0.30s ==================
```

Both failures are `NotImplementedError` from the stub, which is the expected **TDD RED** state before the stub is replaced with the real helper.

---

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok (no issues in 276 source files) |
| `make lint` | ok |

---

## TDD RED Evidence

```
tests/unit/test_fix_cycle.py::test_try_auto_amend_short_circuits_when_project_config_none FAILED
tests/unit/test_fix_cycle.py::test_try_auto_amend_short_circuits_when_should_auto_amend_is_false FAILED
  NotImplementedError: _try_auto_amend_after_escalation is not yet implemented
```

Both tests fail with `NotImplementedError` before any implementation code runs — confirmed RED.

---

## Notes

- The `now` parameter to `_try_auto_amend_after_escalation` is retained for future use (e.g. stamping `amended_at` on the manifest or a `scope_amendment_event` table) but intentionally unused inside the helper body. Ruff flags it as `ARG001`; suppresses via `# noqa: ARG001` comment.
- `_get_last_run` from `dashboard/routers/actions.py` is not available in daemon code, so StepRun creation uses a direct SQLAlchemy query (`db.query(StepRun).filter(...).order_by(...).first()`) — this is identical in effect.
- Deferred (function-call-time) import of `amend_allowed_paths` and `should_auto_amend` from `scope_amendment` avoids the module-level import cycle that would result if placed at file top level.
- The `_note` value in `.iw-orch.json` is kept short (134 chars) per the 100-char ruff E501 line-length limit.
