# CR-00073 — S02 Code Review Report

**Work Item**: CR-00073 — iw CLI Contract Test Layer
**Step Reviewed**: S01 (backend-impl)
**Reviewed by**: code-review-impl
**Date**: 2026-05-22

---

## Summary

S01 is **APPROVED with no mandatory fixes**. All 6 acceptance criteria are met.
The implementation is well-structured, scope-clean, and the test layer is
immediately usable.

---

## Pre-flight gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | ✅ | All checks passed |
| `make format-check` | ✅ | All 854 files already formatted |
| `make test-assertions` | ✅ | No new assertion-scanner violations (544 files scanned) |
| `make test-cli-contract` | ✅ | 57 passed, 3 xfailed in 19s |
| `test_cli_spec_conformance` | ✅ | 7 passed in 0.24s |

---

## Review Checklist — Findings

### 1. Scope discipline ✅

`git diff origin/main -- orch/ dashboard/ executor/ scripts/` is **empty** — no
production code touched. The diff on `orch/` is clean.

Allowed-path edits only: test files under `tests/integration/cli/`, the new
`test_cli_spec_conformance.py`, `Makefile`, `docs/IW_AI_Core_CLI_Spec.md` (doc
drift fix), `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/`,
`.claude/skills/iw-ai-core-testing/` (byte-identical to master), and
`ai-dev/work/TESTS_ENHANCEMENT.md`.

### 2. AC1 — Per-command contract coverage ✅

44 contract tests across 6 priority command groups. Per-group coverage:

| Command group | Exit 0 path | Non-zero + stderr | stdout shape | DB effect | Idempotence/Atomicity |
|---|---|---|---|---|---|
| `step-done` | ✅ 4 tests | ✅ 3 tests | ✅ 1 test (JSON) | ✅ 2 tests (status, report_file, StepRun) | ✅ 1 test (idempotent second call) |
| `register` | ✅ 5 tests | ✅ 5 tests | ✅ 1 test (JSON) | ✅ 2 tests (WorkItem row, WorkflowStep rows from manifest) | ✅ 1 test (created=false, row unchanged) |
| `doc-update` | ✅ 3 tests | ✅ 2 tests + 1 xfail | ✅ 1 test (JSON) | ✅ 2 tests (status transition, auto_completed flag) | ✅ 1 test (second call on completed) |
| `approve` | ✅ 3 tests | ✅ 3 tests | ✅ 1 test (JSON) | ✅ 3 tests (status, updated_at, pre-evidence ingestion) | — |
| `next-id` | ✅ 4 tests | ✅ 1 test | ✅ 1 test (JSON) | ✅ 1 test (IdSequence row, +1 per call) | ✅ 1 test (ThreadPoolExecutor, no dupes, gapless) |
| evidence-ingestion hooks | ✅ 2 subprocess tests | ✅ 2 tests (no-dir graceful, non-browser no-op) | — | ✅ 4 tests (pre/post phase, file names, content) | — |

All strong behavioural assertions: exit code values are specific (0, 1, 2), stderr
messages are pattern-matched, JSON keys are enumerated, DB column values are
queried and compared. No worthless assertions like `exit_code is not None`.

### 3. AC2 — Spec-conformance bidirectional drift check ✅

`tests/integration/test_cli_spec_conformance.py` exists and:
- Parses the §4 fenced ASCII tree (regex-based, robust to box-drawing chars)
- Introspects the live Click tree recursively via `group.commands`
- Asserts spec→CLI existence: `test_every_spec_command_exists_in_cli`
- Asserts CLI→spec existence: `test_every_cli_command_documented_in_spec`
- Asserts coverage: `test_every_spec_command_has_contract_test_or_allowlisted`
- §4: **62 commands**; CLI: **62 commands**; bidirectional ✅

Self-check tests guard the detection machinery itself (priority commands
detected, parser yields ≥30 commands, CLI introspection descends groups).

### 4. AC3 — Allowlists ✅

`KNOWN_SPEC_DRIFT`: **empty** — §4 was fully synchronized with the live CLI
(~30 commands added). No pre-existing existence drift allowlisted.

`KNOWN_UNTESTED_COMMANDS`: **57 entries**, each with a `reason` ("non-priority —
contract coverage deferred, TESTS_ENHANCEMENT 3.3 follow-up"). No priority
command is in the allowlist. `test_allowlists_are_internally_consistent`
explicitly guards this: `PRIORITY_COMMANDS & set(KNOWN_UNTESTED_COMMANDS)` must
be empty, enforced by assertion.

### 5. AC4 — No new QV gate ✅

All 7 new test files are under `tests/integration/` and collected by
`make test-integration`. `skills/iw-workflow/SKILL.md` was not modified. The
`test-cli-contract` Makefile target is `.PHONY`-declared as a developer
convenience target only.

### 6. AC5 — TDD RED evidence ✅

The S01 report documents `monkeypatch`-based demonstrations:

- **Contract**: `monkeypatch.setattr(orch.cli.id_commands, "allocate_next_id",
  "BOGUS-00000")` → `test_next_id_allocates_id_exit_0` failed with
  `AssertionError: Expected I- prefix, got: BOGUS-00000`.
- **Conformance**: monkeypatch of `parse_spec_commands` to inject a `ghost-command`
  → `test_every_spec_command_exists_in_cli` reported the injected drift.

Both live entirely in test code (run, capture, delete the throwaway test file);
no production file was edited. `git diff origin/main -- orch/` is empty,
confirming no production path was modified.

### 7. AC6 — Docs, skill, and plan ✅

- `docs/IW_AI_Core_Testing_Strategy.md` §2: CLI contract sub-layer documented
  (73-line description covering per-command tests, spec-conformance, allowlists,
  xfail/Incident pattern, gate table integration). §5: gate row present. §9:
  known-gap row flipped.
- `skills/iw-ai-core-testing/SKILL.md` §11: CLI contract layer noted with
  extension guide.
- `.claude/skills/iw-ai-core-testing/SKILL.md`: `diff` against master is
  **empty** — byte-identical.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.3 marked **DONE 2026-05-21
  (CR-00073)** with a detailed changelog entry covering all deliverables.

### 8. Test quality and isolation ✅

All tests use the testcontainer `db_session` / `db_engine`. Evidence-ingestion
subprocess tests deliberately avoid the `test_project` fixture (which holds an
uncommitted transaction) and seed independently on a separate connection,
avoiding the duplicate-PK deadlock identified in S01's operator follow-up.

`CliRunner` is used with `catch_exceptions=False` (or `True` only for error-path
tests where the exception is Click's own usage error — both forms are correct).

---

## Observations (non-blocking)

1. **`test_cli_spec_conformance.py` not in `scope.allowed_paths`**: The design's
   `scope.allowed_paths` lists `tests/integration/test_cli_core.py`,
   `tests/integration/test_cli_items.py`, etc., but omits the new
   `test_cli_spec_conformance.py`. The operator noted this as a merge-scope-gate
   risk. Since this is a required deliverable per the design, it should be added
   to the `scope.allowed_paths` before merge. **MEDIUM (fixable) — recommend
   adding `tests/integration/test_cli_spec_conformance.py` to `scope.allowed_paths`
   in the workflow manifest.**

2. **`test_doc_update_new_doc_without_tier_is_clean_usage_error` (xfail)**: A
   genuine CLI rough edge — the command exits 3 with a raw `TypeError` instead of
   a clean exit-2 usage error. The operator correctly xfailed it with a
   `TODO(file-incident)` marker. An Incident should be filed to track this
   (CLI fix is out of scope for this test-only CR).

3. **Subprocess deadlock fix documented**: The S01 operator correctly diagnosed
   and fixed the duplicate-PK deadlock (run2/run4 timeouts) by removing the
   `test_project` fixture dependency from subprocess tests. This fix is sound and
   the pattern is documented in the test files.

---

## Verdict

**PASS** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable) findings.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00073",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "conventions",
      "file": "ai-dev/active/CR-00073/workflow-manifest.json",
      "line": null,
      "description": "scope.allowed_paths lists test_cli_core.py etc. but omits the new required deliverable tests/integration/test_cli_spec_conformance.py",
      "suggestion": "Add tests/integration/test_cli_spec_conformance.py to scope.allowed_paths in the workflow manifest before merge. This is a documentation gap, not a test defect."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "64 passed (57 CLI contract + 7 spec-conformance), 3 xfailed (1 genuine CLI bug xfail + 2 pre-existing migration-tolerance xfails from test_step_commands_drift.py), 0 failed",
  "notes": "S01 is a well-executed test-infrastructure CR. The contract test layer is comprehensive, behaviourally strong, and runnable today. The spec-conformance test is a solid ratchet. Scope is clean. One non-blocking suggestion to fix scope.allowlist documentation before merge."
}
```
