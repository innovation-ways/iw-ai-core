# I-00061_S02_CodeReview_Backend_prompt

**Work Item**: I-00061 — Auto-skip phantom QV gates at item approval
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

(Standard policy — see `ai-dev/templates/CodeReview_Prompt_Template.md` for the full text. Read-only `docker ps`/`inspect`/`logs` are allowed.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. S01 should add NO migrations. If you find any alembic file modifications in S01's `files_changed`, that is an immediate CRITICAL finding.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00061 --json`.
- `ai-dev/active/I-00061/I-00061_Issue_Design.md` — Design document
- `ai-dev/active/I-00061/reports/I-00061_S01_Backend_report.md` — S01 report
- All files listed in S01's `files_changed`:
  - `orch/qv_gate_validator.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/batch_commands.py`

## Output Files

- `ai-dev/active/I-00061/reports/I-00061_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the validator + CLI hooks built in S01. Read the design document first — pay special attention to the `Validator Design`, `Hook Points`, and `Daemon Event Schema` sections. Then read the S01 report and the actual code.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files in `files_changed`:

```bash
make lint
make format-check
```

If either reports NEW violations in the changed files, classify each as a CRITICAL `conventions` finding. Do NOT fix anything yourself.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Validator Purity

- `validate_qv_gate` and `classify_qv_gate` (or whatever pure function S01 produced) MUST not import `Session`, MUST not query the DB, MUST not log inside the function body, MUST not write files. They take a `Path`, the gate name, and the command string; they return a verdict. **Anywhere these constraints break is a CRITICAL `architecture` finding.**
- The validator MUST be importable WITHOUT a database connection. If you can't do `python -c "from orch.qv_gate_validator import validate_qv_gate"` without env-var-loading side effects, that is HIGH `architecture`.

### 2. Conservative Default

- For every code path in the pure validator, ask: "If a future refactor mistypes a regex, can this branch return False on a real, runnable command?" The default catch-all MUST return True (runnable). If you find any catch-all returning False, that is CRITICAL `code_quality`.
- The pattern registry order matters — verify `make <target>` is matched before `_bare_executable` (otherwise `make` would be looked up via `shutil.which`, miss the Makefile-target check entirely, and silently treat real `make` commands as "runnable bare exec" — losing the phantom detection).

### 3. Hook Placement

- The `approve` hook MUST run AFTER `item.status = WorkItemStatus.approved` and AFTER the existing `session.flush()`. If it runs before, the auto-skip and the approval are non-atomic with respect to the daemon poll loop — HIGH `architecture`.
- Both hooks MUST run inside the same `with get_session() as session:` block as the original status mutation. If S01 created a fresh session for the auto-skip call, that is CRITICAL — the auto-skip writes will commit independently of the approve, and a crash between them leaves an item approved with stale phantom-gate rows.
- The `approve` and `batch_approve` commands MUST exit 0 even if zero gates were skipped (no-op case) AND even if many were skipped. Any non-zero exit on a normal phantom-skip is CRITICAL `architecture`.

### 4. DaemonEvent Schema

- Verify the inserted event has `event_type = "step_auto_skipped_phantom_gate"` exactly (no typos, no underscores-to-dashes drift).
- `entity_type = "workflow_step"`, `entity_id = "{work_item_id}/{step_id}"`.
- `metadata` (DB column) populated via the Python attribute name — REMEMBER: `DaemonEvent.metadata` is `event_metadata` in Python. If S01 wrote `event.metadata = {...}`, that's a CRITICAL bug — SQLAlchemy reserves `metadata`. Verify it's `event.event_metadata = {...}`.
- The metadata dict MUST contain at minimum `work_item_id`, `step_id`, `gate`, `command`, `reason`, and `trigger`. Missing any of those is HIGH `code_quality`.

### 5. Pattern Coverage

Walk through these representative commands and confirm each is correctly classified by reading the validator code (do NOT execute against a real Makefile):

| Command | Expected verdict | Reason |
|---------|------------------|--------|
| `make lint` (target exists) | runnable | — |
| `make arch-check` (target missing) | phantom | `missing_makefile_target` |
| `cd frontend && npx tsc --noEmit` (no `frontend/`) | phantom | `missing_directory` |
| `cd frontend && npx tsc --noEmit` (`frontend/` exists) | runnable | — |
| `pytest -q tests/` | runnable iff `pytest` on PATH | — |
| `playwright-cli kill-all` (binary missing) | phantom | `missing_executable` |
| `make` with no target | conservative — should NOT mark phantom | unrecognised → True |
| `bash some-script.sh && echo done` | conservative — should NOT mark phantom | shell metachar → True |

If any are mis-classified, that is HIGH `code_quality`.

### 6. Code Quality

- Are there any obvious bugs, logic errors, or edge cases missed?
- Is error handling appropriate? File-not-found on `Makefile` should NOT raise — the validator should handle it gracefully and return phantom (or runnable if no `make` target was claimed).
- Is there unnecessary duplication?

### 7. Project Conventions

- Read `orch/CLAUDE.md`. Verify SQLAlchemy 2.0 style (`Mapped[]`) is used in any model interactions; psycopg v3 imports only.
- `from __future__ import annotations` at the top of the new module.
- `datetime.now(UTC)` for timestamps.
- Click command output handles both `--json` and human modes consistently.

### 8. Security

- The validator reads the project's Makefile. Confirm it does NOT execute it (`subprocess.run(["make", ...])` is forbidden — that would broaden blast radius and slow the CLI). Reading via `Path.read_text()` only.
- The `cd <dir>` parser MUST handle malicious dirs safely — at minimum, refuse to follow symlinks if it's checking `is_dir()` on attacker-controlled paths. Use `Path(repo_root, dir).resolve()` and verify it's within `repo_root` (or simpler: just `(repo_root / dir).is_dir()` without resolving symlinks).

### 9. Testing

- Note: S01 does NOT deliver tests. Tests come in S03. Do NOT mark "missing tests" as a finding here — flag it for S03 if S03's prompt fails to specify the case.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review, run `make test-unit` to verify no regression in existing tests. Note: there are no tests for the validator yet — that's expected (S03's job).

## Severity Levels

(Standard table — see template.)

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00061",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "orch/qv_gate_validator.py",
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

`verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
`mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
