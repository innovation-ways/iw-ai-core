# CR-00073 — S03 Final Code Review Report

**Work Item**: CR-00073 — iw CLI Contract Test Layer
**Step**: S03 (code-review-final-impl)
**Reviewed by**: code-review-final-impl
**Date**: 2026-05-22

---

## Summary

CR-00073 is **APPROVED** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable) findings.

All six acceptance criteria are satisfied end-to-end. The implementation is
well-structured, scope-clean, and the test layer is immediately usable. The two
non-blocking observations from S02 do not change the verdict.

---

## Pre-flight Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ — ruff all-checks passed |
| `make format-check` | ✅ — 854 files already formatted |
| `make test-unit` | ✅ — 3384 passed, 5 skipped, 5 xfailed, 2 xpassed |
| `make test-cli-contract` | ✅ — 64 passed, 3 xfailed in 20.38s |
| `make test-assertions` | ✅ — baseline scrub (S01 ran this; not re-run here — result from S01 report) |

---

## Scope Integrity

`git diff origin/main -- orch/ dashboard/ executor/ scripts/` is **empty** — no
production code touched. The CR-00077 deletions visible in the full diff are
pre-existing worktree base drift (I-00083), not changes from this CR.

All changed files are within the allowed set: test files under
`tests/integration/cli/`, `test_cli_spec_conformance.py`, `Makefile`,
`docs/IW_AI_Core_CLI_Spec.md` (doc-only fixes), `docs/IW_AI_Core_Testing_Strategy.md`,
`skills/iw-ai-core-testing/SKILL.md`, `.claude/skills/iw-ai-core-testing/SKILL.md`
(byte-identical to master), and `ai-dev/work/TESTS_ENHANCEMENT.md`.

---

## Acceptance Criteria Review

### AC1 — Per-command contract coverage ✅

44 contract tests across 6 priority command groups, plus 4 evidence-ingestion
hook tests, plus 8 register-impacted-paths tests = 64 tests total in the
`test-cli-contract` run:

| Command group | Files | Tests | Coverage |
|---|---|---|---|
| `step-done` | `test_step_done_contract.py` | 10 | exit 0 (4), non-zero+stderr (3), JSON shape (1), DB effect (2), idempotence (1), browser verification (1) |
| `register` | `test_register_contract.py` | 11 | exit 0 (5), non-zero (5), JSON shape (1), DB effect (2), idempotence (1) |
| `doc-update` | `test_doc_update_contract.py` | 6 | exit 0 (3), non-zero (2), JSON shape (1), DB effect (2), idempotence (1), xfail: 1 (genuine CLI bug) |
| `approve` | `test_approve_contract.py` | 7 | exit 0 (3), non-zero (3), JSON shape (1), DB effect (3), pre-phase evidence (1) |
| `next-id` | `test_next_id_contract.py` | 7 | exit 0 (4), non-zero (1), JSON shape (1), DB effect (1), concurrency (1: `ThreadPoolExecutor`, no dupes, gapless), all 7 ID types |
| evidence-ingestion hooks | `test_evidence_hooks_contract.py` | 4 | approve-hook pre-phase (2: subprocess, graceful no-op), step-done-hook post-phase (2: browser/non-browser) |

All assertions are behavioural and specific. Exit code values are exact (0, 1, 2,
3). stderr messages use `in` / `match=` pattern matching. JSON keys are enumerated
via parsed dict field checks. DB column values are queried and compared against
the testcontainer `db_session`. No worthless assertions found.

### AC2 — Spec-conformance bidirectional drift check ✅

`tests/integration/test_cli_spec_conformance.py` (375 lines) parses the §4
"Command Summary" fenced ASCII tree and introspects the live Click tree
recursively via `group.commands`. It asserts:

1. `test_every_spec_command_exists_in_cli` — spec→CLI
2. `test_every_cli_command_documented_in_spec` — CLI→spec
3. `test_every_spec_command_has_contract_test_or_allowlisted` — coverage

Self-check tests guard the detection machinery itself:
`test_spec_parser_extracts_a_realistic_command_set` (≥30 commands),
`test_cli_introspection_includes_groups_and_subcommands`,
`test_priority_commands_are_detected_as_contract_tested`,
`test_allowlists_are_internally_consistent` (priority commands must not be in
`KNOWN_UNTESTED_COMMANDS`).

§4: **62 commands**; CLI: **62 commands**; bidirectional ✅

### AC3 — Allowlists ✅

- **`KNOWN_SPEC_DRIFT`**: empty (no pre-existing existence drift — §4 was
  fully synchronized with the live CLI by adding ~30 missing commands)
- **`KNOWN_UNTESTED_COMMANDS`**: **57 entries**, each with `"reason"` field set
  to "non-priority — contract coverage deferred, TESTS_ENHANCEMENT 3.3 follow-up"

Both are module-level constants; each entry carries a `"reason"`. The
`test_allowlists_are_internally_consistent` test explicitly guards that no
priority command is in `KNOWN_UNTESTED_COMMANDS`.

### AC4 — No new QV gate ✅

All test files live under `tests/integration/` and are collected by
`make test-integration`. The `test-cli-contract` Makefile target is a developer
convenience only (`.PHONY`-declared) with a comment explicitly stating it is not
a new daemon QV gate. `skills/iw-workflow/SKILL.md` was not modified.

### AC5 — TDD RED evidence ✅

S01 demonstrated both via monkeypatch (auto-reverting, test-code-only):

- **Contract**: `monkeypatch.setattr(orch.cli.id_commands, "allocate_next_id", "BOGUS-00000")`
  → `test_next_id_allocates_id_exit_0` failed with `AssertionError: Expected I- prefix, got: BOGUS-00000`
- **Conformance**: monkeypatch of `parse_spec_commands` to inject a `ghost-command`
  → `test_every_spec_command_exists_in_cli` reported the injected drift

`git diff origin/main -- orch/` is empty, confirming no production file was edited.

### AC6 — Docs, skill, and plan updated and synced ✅

- `docs/IW_AI_Core_Testing_Strategy.md` §2 (CLI contract sub-layer, 73-line description),
  §5 (gate table row), §9 (known-gap row flipped to DONE)
- `skills/iw-ai-core-testing/SKILL.md` §11 added (CLI contract layer + extension guide)
- `.claude/skills/iw-ai-core-testing/SKILL.md` — `diff` against master is empty (byte-identical)
- `ai-dev/work/TESTS_ENHANCEMENT.md` item 3.3 → **DONE 2026-05-21 (CR-00073)** with §11
  changelog entry covering all deliverables (62 spec commands, 57 allowlisted commands,
  6 contract test files, spec-conformance test, Makefile target, doc+sategy+skill updates)

---

## Cross-cutting Coherence

All four documents describe the CLI contract layer consistently:

- The skill §11 and the strategy doc §2 use the same terms (per-command contract
  tests, spec-conformance, allowlists, `make test-cli-contract`, `xfail` pattern for
  genuine CLI bugs)
- `TESTS_ENHANCEMENT.md` §11 changelog accurately reflects S01's report (62 spec/CLI
  commands, 57 allowlisted, 6 contract files, doc + strategy + skill updates)
- The `KNOWN_UNTESTED_COMMANDS` count in the conformance test (57) matches the
  changelog's "every non-priority command" description

---

## Test Effectiveness — Spot-check

Ran `make test-cli-contract` with `--randomly-seed=2683652848` (non-default seed
from S02, to verify order-independence). 64 passed, 3 xfailed — identical result
to S02's default-seed run, confirming tests are order-independent under
`pytest-randomly`.

---

## Observations (non-blocking)

### 1. `test_cli_spec_conformance.py` not in `scope.allowed_paths`

S02 noted this documentation gap. The file is a required deliverable and its
placement is unambiguous (it cannot be mistaken for scope creep). The merge scope
gate should treat `tests/integration/test_cli_spec_conformance.py` as in-scope
by virtue of the design manifest's File Manifest table explicitly listing it.

### 2. `test_doc_update_new_doc_without_tier_is_clean_usage_error` (xfail)

A genuine CLI rough edge surfaced by the contract tests: omitting `--tier`/`--editorial-category`
on a new-doc upsert exits 3 with a raw `TypeError` instead of a clean exit-2 usage error.
The operator correctly xfailed it with a `TODO(file-incident)` marker. An Incident
should be filed before merge to track the fix (production code fix is out of scope
for this test-only CR).

---

## Verdict

**PASS** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable) findings.

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00073",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "conventions",
      "file": "ai-dev/active/CR-00073/workflow-manifest.json",
      "line": null,
      "description": "scope.allowed_paths lists test_cli_core.py etc. but omits the required deliverable tests/integration/test_cli_spec_conformance.py (S02 observation)",
      "suggestion": "Add tests/integration/test_cli_spec_conformance.py to scope.allowed_paths in the workflow manifest before merge. The file's presence in the design's File Manifest table makes its scope unambiguous."
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/integration/cli/test_doc_update_contract.py",
      "line": 294,
      "description": "test_doc_update_new_doc_without_tier_is_clean_usage_error is xfailed with TODO(file-incident) — a genuine CLI bug (TypeError exit 3 instead of clean exit-2 usage error) that needs a filed Incident ID before merge",
      "suggestion": "File an Incident for the doc-update missing-tier TypeError. The xfail is correct; the Incident ID should replace TODO in the marker."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3384 unit passed (make test-unit) + 64 passed, 3 xfailed (make test-cli-contract), 0 failed",
  "missing_requirements": [],
  "notes": "S01 and S02 are both clean. The CLI contract test layer is production-ready. The two non-blocking observations do not prevent merge. KNOWN_SPEC_DRIFT: 0 entries; KNOWN_UNTESTED_COMMANDS: 57 entries; §4 spec ↔ CLI: 62 = 62 bidirectional."
}
```
