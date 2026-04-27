# CR-00023_S10_CodeReview_Tests_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S10
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (all 7 ACs, including AC7 pre-flight gates)
- `ai-dev/active/CR-00023/reports/CR-00023_S09_Tests_report.md` — S09 report including AC coverage map
- All test files added in S09:
  - `tests/unit/test_item_commands_register.py`
  - `tests/unit/test_item_commands_item_status.py`
  - `tests/unit/test_template_hints.py`
  - `tests/integration/test_register_to_item_status_roundtrip.py`
  - `tests/integration/test_daemon_legacy_fallback.py`

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S10_CodeReview_Tests_report.md`

## Review Checklist

### Acceptance criteria coverage
- [ ] AC1: at least one test asserts each of the 12 keys in the per-step JSON entry
- [ ] AC2: idempotency test exists; unicode preservation test exists; key-preservation test exists
- [ ] AC3: covered by S01's alembic check (verify S10 doesn't try to apply migrations from a test — that's against the rules)
- [ ] AC4: tests for ALL THREE daemon read paths (`_build_claude_prompt`, `_get_gate_name_and_command`, `_compute_qv_baselines`) with NULL columns
- [ ] AC5: a test inspects all 8 in-scope templates for the hint substring AND a test inspects 8 out-of-scope templates for absence
- [ ] AC6: a dedicated test (`test_item_status_surfaces_db_only_step_not_in_manifest` in `test_register_to_item_status_roundtrip.py`) actually inserts a DB-only step row, calls `iw item-status --json`, and asserts the response surfaces it without reading the manifest. Shape-only checks are NOT enough — the test must include the manifest-untouched assertion (mtime unchanged OR `Path.read_text` patched to raise on the manifest path).
- [ ] AC7: tests assert the pre-flight section heading exists in BOTH copies of `Implementation_Prompt_Template.md`, that all three commands (`make format`, `make typecheck`, `make lint`) are named, that the `preflight` field is present in the Subagent Result Contract example, that the two copies are byte-identical, AND defensive tests assert the section is ABSENT from the other 6 in-scope templates plus the FIX/Browser variants.

### Semantic correctness (per `tests/CLAUDE.md` lesson — I-00003)
- [ ] Tests verify SPECIFIC VALUES, not shape only
  - BAD: `assert "command" in step_entry`
  - GOOD: `assert step_entry["command"] == "make lint"`
- [ ] Stamping idempotency test compares byte-identical output (`assert content_after_first == content_after_second`)
- [ ] Unicode test asserts the actual em-dash or accented character round-trips
- [ ] Daemon fallback tests assert the EXACT prompt content matches the legacy-path expectation (or at least a substring uniquely identifying the manifest source)

### Test isolation
- [ ] No test depends on another test's side effects
- [ ] Each integration test uses fresh testcontainer DB state (or a transaction-rollback fixture)
- [ ] No test connects to the live orch DB (port 5433)
- [ ] No test calls `importlib.reload(orch.config)` — uses `monkeypatch.delenv()` instead
- [ ] No integration test mocks the database
- [ ] FTS DDL is run after `Base.metadata.create_all()` if a fresh testcontainer is created in the test
- [ ] Tests cleanup any temp files/directories they create

### Test quality
- [ ] Test names follow the project convention (`test_<unit>_<scenario>_<expectation>`)
- [ ] Each test has a docstring describing the scenario and expected behavior
- [ ] Common fixtures are factored into `conftest.py` (do not duplicate manifest-write boilerplate across files)
- [ ] No flaky patterns (sleeps, race-prone assertions, dependence on filesystem ordering)

### Hard rules (carried)
- [ ] No `docker compose` invocation in test code
- [ ] No `alembic upgrade/downgrade` against live DB
- [ ] All `psycopg2` URLs replaced with `psycopg`
- [ ] mypy clean on test files
- [ ] `make lint` clean

## Findings Severity

- **CRITICAL**: a test connects to live DB; an AC has zero coverage
- **HIGH**: shape-only assertions (no specific value); idempotency test doesn't actually re-run
- **MEDIUM**: missing edge-case coverage; flaky pattern; un-deduplicated boilerplate
- **LOW**: docstring missing, naming convention drift

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_reviewed": [
    "tests/unit/test_item_commands_register.py",
    "tests/unit/test_item_commands_item_status.py",
    "tests/unit/test_template_hints.py",
    "tests/integration/test_register_to_item_status_roundtrip.py",
    "tests/integration/test_daemon_legacy_fallback.py"
  ],
  "ac_coverage_assessment": {
    "AC1": "adequate|gaps:<list>",
    "AC2": "adequate|gaps:<list>",
    "AC3": "adequate|gaps:<list>",
    "AC4": "adequate|gaps:<list>",
    "AC5": "adequate|gaps:<list>",
    "AC6": "adequate|gaps:<list>",
    "AC7": "adequate|gaps:<list>"
  },
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
