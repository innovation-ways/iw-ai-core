# I-00040 S07 — Global code review (CodeReview_Final)

**Work Item**: I-00040
**Reviewing**: All work across S01, S03, S05 (and the per-step reviews S02/S04/S06)
**Agent**: code-review-final-impl

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- All reports under `ai-dev/active/I-00040/reports/`
- `orch/db/alembic_guard.py` (S01)
- `orch/daemon/main.py` (S01 wiring)
- `orch/daemon/batch_manager.py` (S01 wiring)
- `dashboard/app.py` (S01 + S03 wiring)
- `dashboard/utils/alembic_guard.py` or `dashboard/middlewares/alembic_guard.py` (S01)
- `dashboard/templates/base.html` (S03)
- `dashboard/templates/macros/db_guard.html` (S03)
- All test files added by S05

## Output Files

- `ai-dev/active/I-00040/reports/I-00040_S07_CodeReview_Final_report.md`

## Review Checklist

### 1. End-to-end consistency — CRITICAL

- [ ] Banner copy in `base.html` matches the strings asserted in the dashboard test (`Orch DB schema is behind head`, `make db-migrate`).
- [ ] Daemon stderr line format matches the assertion in the daemon test (`CRITICAL: orch DB schema mismatch — `).
- [ ] `BatchItem.notes` format matches the assertion in the `_launch_item` test.
- [ ] DaemonEvent payload schema matches between emitter and test (`phase=alembic_guard`, `reason=db_behind_head`).

### 2. The bug from the design is provably fixed — CRITICAL

The bug:
1. Daemon starts on stale DB → silently fails forever.
2. Dashboard 500s with no user-visible explanation.
3. `_launch_item` silently corrupts BatchItem state.

Verify each is now caught:
- [ ] Daemon: covered by `test_daemon_alembic_guard.py` — exits non-zero.
- [ ] Dashboard: covered by `test_alembic_guard_banner.py` — banner appears + write actions return 503.
- [ ] `_launch_item`: covered by `test_launch_item_alembic_guard.py` — BatchItem set to setup_failed with clear notes.

### 3. Architecture rules

- [ ] `orch/db/alembic_guard.py` does not import from `dashboard/`.
- [ ] `dashboard/utils/alembic_guard.py` (or middleware) imports the helper from `orch.db.alembic_guard`.
- [ ] No template imports from `orch/`.

### 4. Operational safety

- [ ] On startup, the dashboard does NOT abort on mismatch (must keep serving read pages).
- [ ] On startup, the daemon DOES abort on mismatch.
- [ ] `_launch_item`'s guard runs BEFORE any worktree filesystem mutation (no orphan `.worktrees/<id>` left behind on guard failure).
- [ ] Operator override (`IW_CORE_SKIP_ALEMBIC_GUARD=true`) works for daemon AND dashboard, refused in agent context.

### 5. Observability

- [ ] DaemonEvent rows are emitted at each detection point (startup, request middleware, launch).
- [ ] Dedup window prevents event-table flooding.
- [ ] Logger names are `orch.db.alembic_guard` and (if a middleware module exists) `dashboard.middlewares.alembic_guard`.

### 6. No scope drift

- [ ] No alembic migration file added in this issue.
- [ ] No refactor of `orch/db/safe_migrate.py` or `orch/db/identity.py`.
- [ ] No CSS overhaul beyond what `make css` regenerated.
- [ ] No new JavaScript files.

### 7. Documentation

- [ ] If `docs/IW_AI_Core_Daemon_Design.md` describes the startup sequence, it has been updated to mention the alembic guard. (If it doesn't currently describe startup, no update is required.)
- [ ] If `docs/IW_AI_Core_Dashboard_Design.md` describes app construction, it has been updated to mention the guard middleware. (Same — only if currently described.)

### 8. Tests pass cleanly

- [ ] S05's report shows all tests passing.
- [ ] S06 (per-step review) verdict is PASS.
- [ ] No regressions reported in the QV gates that would invalidate the merge.

## Output Report

Findings list with severity, file:line, and verdict. End with `PASS` / `NEEDS_FIX` / `BLOCKED` and the appropriate `iw step-done` / `iw step-fail` call.

## Lifecycle Commands

```bash
uv run iw step-start I-00040 --step S07
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S07 --report ai-dev/active/I-00040/reports/I-00040_S07_CodeReview_Final_report.md
```
