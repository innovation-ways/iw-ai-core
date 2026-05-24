# I-00107_S05_CodeReview_Final_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only. Testcontainer fixtures in tests are exempt.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration expected for this item. Any migration file in any of S01–S04's diffs → **CRITICAL**.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00107 --json` is authoritative.
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` — Design
- `ai-dev/active/I-00107/I-00107_Functional.md` — Functional doc
- All implementation step reports: `ai-dev/active/I-00107/reports/I-00107_S0{1,3}_*_report.md`
- All per-agent code review reports: `ai-dev/active/I-00107/reports/I-00107_S0{2,4}_CodeReview_report.md`
- All files listed across S01's and S03's `files_changed`:
  - `orch/daemon/project_registry.py`
  - `orch/daemon/main.py`
  - `tests/unit/daemon/test_daemon_config_reload.py`

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_S05_CodeReview_Final_report.md`

## Context

You are the **final cross-agent review** for **I-00107**. Per-agent reviews (S02, S04) have already happened; your job is to catch issues those could not — issues that only show when you look at the whole package at once.

## Read the Design Document FIRST

- **Acceptance Criteria** AC1–AC5 — every one is a mandatory check. AC5 is structural ("regression tests exist") and must be cross-checked against S03's `files_changed`.
- **TDD Approach** — lists FIVE test names. Cross-check every name against the new test file's contents. Any test the design names that does not exist → **CRITICAL**.
- **Root Cause Analysis** — confirms the gap is at `ProjectRegistry.reload()` and `Daemon._reload_projects_if_stale()`. Verify the fix lives in exactly those two production files (plus the test file). Scope creep → MEDIUM_FIXABLE.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations across any changed file → **CRITICAL** with `"category": "conventions"`.

## Cross-Cutting Review Checklist

### 1. End-to-end coverage of every AC

| AC | What to verify | Where to verify |
|----|---------------|-----------------|
| AC1 | manager rebuilt on `.iw-orch.json` content drift | `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` |
| AC2 | next `_process_batch` reads the new config | Implicit in AC1 — the BatchManager's `self.project_config` is the source `_process_batch` reads. Verify no caching layer slipped between. |
| AC3 | enabled/disabled toggle also rebuilds | `test_reload_rebuilds_manager_on_enabled_toggle` |
| AC4 | `project_config_reloaded` DaemonEvent emitted | `test_reload_emits_project_config_reloaded_event` |
| AC5 | regression test exists | The whole new test file `tests/unit/daemon/test_daemon_config_reload.py` |

Any AC without a corresponding test, or whose test only verifies shape → flag with the appropriate severity (typically HIGH or CRITICAL for missing AC1/AC4 coverage).

### 2. The fix does not drop in-flight state

The S01 fix rebuilds `self.managers[project_id]` mid-run. Verify by reading the BatchManager constructor (`orch/daemon/batch_manager.py:85-110`) and the surrounding `Daemon.run()` loop that:

- The old `BatchManager` had no in-memory state that the new one would lose. (BatchManager is effectively stateless per-cycle — it re-queries the DB each `_process_batch`. There is no per-item progress kept in memory; that's all in `batch_items` + `step_runs` + `daemon_events`.)
- The new BatchManager's `_session_factory` is the same factory the old one used (same session lifecycle).
- The new BatchManager picks up where the old one left off on the next `_process_batch` call — i.e. no item gets double-launched or skipped.

If any of these is unclear from reading the code, raise a HIGH finding asking for an in-flight-state safety note in the design's Notes section.

### 3. Behavioural symmetry — `disabled` branch removes the manager cleanly

S01 should have made the `disabled` branch remove `self.managers[project_id]` (or otherwise mark it skippable) — verify the `Daemon.run()` / `_process_batch` callsites tolerate a missing manager entry for a previously-known project. If `self.projects[pid].enabled is False` is the gate the loop reads, removing from `self.managers` is fine; if the loop dispatches via `self.managers` regardless, the old (stale) manager will keep firing — that's a bug.

### 4. Backward compatibility / no migration

No `daemon_events` schema change, no `projects.config` JSONB shape change, no new alembic revision. Confirm by `grep -rn 'orch/db/migrations/versions' --include='*.py'` over the diff (should match nothing new).

### 5. Functional doc faithfulness

Read `I-00107_Functional.md`. Verify:
- Body is ≤ 500 words (review skill blocks >500).
- No file paths, class names, code fences, SQL, or `orch/`/`dashboard/`/`scripts/` mentions.
- "What Changed" describes operator-visible behaviour (reload actually applies, new event for confirmation), not implementation mechanics.

### 6. Test verification

Run the new test file AND the broader unit suite to catch any unintended regression:

```bash
uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v
uv run pytest tests/unit/ -v --no-cov 2>&1 | tail -20
```

Failures → CRITICAL (if related to this change) or HIGH (if pre-existing — note that, do not fix).

### 7. Convention sweep

Re-read `CLAUDE.md` and `orch/CLAUDE.md`. Spot-check:
- `DaemonEvent.metadata` Python attribute is `event_metadata` everywhere the diff writes to it.
- Logger calls use `%r`/`%d`-style placeholders, not f-strings.
- No hardcoded ports, URLs, credentials.
- Imports organised correctly; no `from foo import *`.

## Severity Levels

(See S02 prompt — same table.)

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00107",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
