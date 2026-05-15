# CR-00053_S04_Tests_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S04
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(You do not generate or apply migrations.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design document (Sections "Acceptance Criteria", "TDD Approach")
- `ai-dev/work/CR-00053/reports/CR-00053_S01_Database_report.md` -- S01 report
- `ai-dev/work/CR-00053/reports/CR-00053_S03_Backend_report.md` -- S03 report (the unit tests are already in place; you add the CLI-level integration test)
- `tests/integration/` -- existing integration test patterns (testcontainer fixture, Click `CliRunner` use)
- `tests/CLAUDE.md` -- test conventions (testcontainer-only DB, FTS trigger SQL after `create_all`, etc.)

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S04_Tests_report.md` -- Step report
- `tests/integration/test_idempotency_key_cli.py` -- new end-to-end CLI test

## Context

S03 covered AC1–AC4 at the unit level (function signature + transactional semantics). This step covers **AC2 end-to-end through the Click command**: that the CLI surface delivers the same idempotency guarantee a user/agent will rely on. AC5 (migration round-trip) is already enforced by S02's `make migration-check` gate — do NOT duplicate it here.

## Requirements

### 1. Integration test: CLI idempotent replay

Create `tests/integration/test_idempotency_key_cli.py` with at least these tests:

- `test_cli_repeat_with_same_key_returns_same_id` — use Click's `CliRunner` (or the project's existing pattern; check neighbours under `tests/integration/`) to invoke `iw next-id --type research --idempotency-key abc-CR00053` twice against a fresh testcontainer DB. Assert:
  - Both invocations exit 0.
  - Both invocations print the same ID on stdout.
  - Exactly one row exists in `id_allocations` after both calls.
  - `id_sequences.next_number` for `R` advanced by exactly 1.

- `test_cli_no_key_still_works` — invoke `iw next-id --type research` (no key) twice. Assert distinct IDs, no rows in `id_allocations`, counter advanced by 2. This guards the backwards-compatibility path at the CLI level (one of the most common breakage modes for "optional flag" CRs).

- `test_cli_repeat_with_same_key_json_output` — invoke once with `--json --type research --idempotency-key abc`, then again with the same flags. Assert both stdout payloads parse as JSON and contain identical `id` fields. (Click's `--json` flag is global on `iw`; check `orch/cli/main.py` for the exact spelling.)

Match the testcontainer fixture pattern used elsewhere in `tests/integration/` — do NOT use sqlite-in-memory for these tests (the partial unique index uses Postgres-specific `WHERE` syntax).

### 2. Run ONLY the new file before reporting

```bash
uv run pytest tests/integration/test_idempotency_key_cli.py -v
```

Do NOT run `make test-integration` — that's the S14 QV gate.

## Project Conventions

Read `tests/CLAUDE.md`:
- **NEVER** connect tests to the live DB (port 5433); testcontainer only.
- **MUST** replace `postgresql+psycopg2://` with `postgresql+psycopg://` on testcontainer URLs.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` (the project-wide rule for testcontainer setup).
- **NEVER** `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead.

Click testing pattern (one of the canonical IW AI Core variants):

```python
from click.testing import CliRunner
from orch.cli.main import cli

def test_foo(testcontainer_session):
    runner = CliRunner()
    result = runner.invoke(cli, ["next-id", "--type", "research", "--idempotency-key", "abc"])
    assert result.exit_code == 0
    first_id = result.output.strip()
    # second call
    result2 = runner.invoke(cli, ["next-id", "--type", "research", "--idempotency-key", "abc"])
    assert result2.exit_code == 0
    assert result2.output.strip() == first_id
```

## TDD Requirement

This step is a `tests-impl` step — it is **exempt** from the strict RED-first requirement per the standard template note ("Dedicated coverage steps (`tests-impl`) are exempt — they add tests after the code exists and are not RED-first by nature"). Use the `tdd_red_evidence: "n/a — tests-impl step, code already in place per S03"` form.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only — the new file. Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "tests-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_idempotency_key_cli.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "3 passed, 0 failed",
  "tdd_red_evidence": "n/a — tests-impl step, code already in place per S03",
  "blockers": [],
  "notes": ""
}
```
