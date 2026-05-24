# I-00107_S02_CodeReview_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. You are reviewing — not running infrastructure. `docker ps`/`inspect`/`logs` only. Testcontainer fixtures in tests are the only exception.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item must not add or modify any migration. If the S01 implementation snuck in a migration file, flag it as **CRITICAL**.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00107 --json` is authoritative.
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` — Design document
- `ai-dev/active/I-00107/reports/I-00107_S01_Backend_report.md` — S01 step report
- All files listed in S01's `files_changed` (expect: `orch/daemon/project_registry.py`, `orch/daemon/main.py`)

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the backend fix S01 wrote for **I-00107**.

Read the design document — especially the Root Cause Analysis and Acceptance Criteria sections — *before* you open the changed files. The design tells you exactly what the fix must do; your review checks that what was written matches what was designed.

## Read the Design Document FIRST

Specifically:

- Read **Acceptance Criteria** AC1–AC5 in full. AC1 (manager rebuild on `.iw-orch.json` drift) and AC3 (manager rebuild on enabled/disabled toggle) and AC4 (`project_config_reloaded` event emission) are the load-bearing checks for this step.
- Read **TDD Approach** — note that S03 (`tests-impl`) owns the regression tests. S01's `tdd_red_evidence` should be `"n/a — … delegated to S03 …"`.
- Read **Root Cause Analysis** so you understand the gap S01 is closing.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint           # ruff check
make format-check   # ruff format --check (does NOT auto-fix)
```

If either reports NEW violations in the changed files (i.e., violations that do not appear on `main` before this step), classify each as a **CRITICAL** finding with `"category": "conventions"`, the file/line, and the exact violation code/message. Fix nothing yourself.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture & change-set match the design

- `ProjectRegistry.reload()` now emits a new change-type (recommended `"changed"`) when both old and new `ProjectConfig` exist and differ. The comparison is structural (`==` on the `ProjectConfig` dataclass), not just a presence/enabled check.
- `Daemon._reload_projects_if_stale()` has a branch for the new change-type that:
  - Replaces `self.projects[project_id]` with the new ProjectConfig.
  - Rebuilds `self.managers[project_id]` via the existing `BatchManager(...)` constructor signature.
  - Calls `sync_project_to_db(...)`.
  - Emits a `project_config_reloaded` DaemonEvent with `entity_id = project_id`, `entity_type = "project"`, and a `metadata` dict naming `project_id` + the list of changed fields.
  - Logs an INFO line.
- The `"enabled"` and `"disabled"` branches now also rebuild (`enabled`) or remove (`disabled`) `self.managers[project_id]`, fixing the secondary sub-bug noted in the design.
- The `"unchanged"` branch still does nothing (no churn on identical configs).
- No new module created; the fix lives in the two named files.
- No migration added.

### 2. Code quality

- Diff is small (design estimates 30-50 added lines). Substantial growth beyond that is a flag — what extra scope crept in?
- The "changed fields" list is computed deterministically (sorted, dataclass-field-driven). No spurious diffs from unstable dict-ordering, set ordering, etc.
- Imports are minimal and additive (`from dataclasses import fields`).
- No leaking of internals: the new change-type string is internal to `ProjectRegistry.reload()` ↔ `Daemon._reload_projects_if_stale()`.
- Error handling: a `_build_project_config` that returned a defaults-fallback `ProjectConfig` (because `.iw-orch.json` was malformed) does NOT crash the new branch — it just compares as a normal `ProjectConfig`. The S03 test `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable` will pin this.

### 3. Project conventions (read `CLAUDE.md` + `orch/CLAUDE.md`)

- `DaemonEvent.metadata` ↔ Python attribute `event_metadata`: any direct construction or reads use `event_metadata`, the DB key remains `metadata`. (The existing `emit_event` helper hides this — verify S01 used it rather than constructing `DaemonEvent(...)` directly.)
- Logger calls use `%r`/`%d`-style placeholders, not f-strings, matching the surrounding code.
- No hard-coded port, URL, or credential anywhere in the diff.

### 4. Security

- No secrets in the diff. The diff is daemon control-flow code — minimal attack surface.
- No SQL-injection risk: all DB writes go through the existing `emit_event` / `sync_project_to_db` helpers.

### 5. Testing

- S03 owns the regression tests — they should NOT appear in S01's `files_changed`. If they do, S01 over-reached — flag as MEDIUM.
- S01's report `tdd_red_evidence` should be `"n/a — reproduction + regression tests delegated to S03 tests-impl per design doc TDD Approach"`. Anything else is a finding.

### 5a. TDD RED Evidence

Per the template's standing rule:

- S01 is a Backend step but delegates behavioural tests to S03; the `n/a` evidence form is correct as long as the wording matches the design doc's expectation. No stash-recheck required for this step.

## Test Verification (NON-NEGOTIABLE)

Run the unit suite to confirm no regression:

```bash
uv run pytest tests/unit/daemon/ -v 2>&1 | tail -30
```

Report results accurately in the result contract. Do NOT run `make test-integration` here — that's S12's gate.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00107",
  "step_reviewed": "S01",
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

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
