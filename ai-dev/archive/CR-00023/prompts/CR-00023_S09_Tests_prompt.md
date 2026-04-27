# CR-00023_S09_Tests_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same Docker rules as other steps. **In tests:** the only allowed docker usage
is via testcontainers fixtures (which self-label and self-destruct via Ryuk).
NEVER stop/remove containers from test teardown. NEVER invoke `docker compose`
from test code.

## ⛔ Tests must NOT connect to the live orch DB

Every DB-touching test must use the testcontainer-backed fixtures from
`tests/conftest.py`. The conftest sets `IW_CORE_TEST_CONTEXT=true` which
arms the live-DB guard from I-00041 — do not bypass.

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (all 7 ACs incl. AC7 fold-in for I-00041 finding [3], "TDD Approach" section)
- All prior step reports (S01–S08)
- `tests/conftest.py` — fixture patterns
- `tests/CLAUDE.md` — testing rules

## Output Files

- `tests/unit/test_item_commands_register.py` — new (or extend if exists)
- `tests/unit/test_item_commands_item_status.py` — new (or extend if exists)
- `tests/integration/test_register_to_item_status_roundtrip.py` — new
- `tests/integration/test_daemon_legacy_fallback.py` — new
- `ai-dev/active/CR-00023/reports/CR-00023_S09_Tests_report.md`

## Context

This step writes the formal regression coverage for CR-00023. Each test maps to
one or more acceptance criteria from the design doc. Use TDD: write the test
expecting the new behavior, run it (RED), then verify implementation already
makes it pass (GREEN — since S01–S07 have already shipped the implementation).
If a test fails for a reason other than "implementation not yet present", that
is a real bug — file a fix-cycle finding.

## Required Tests

### 1. `tests/unit/test_item_commands_register.py` (covers AC2 + part of AC1)

#### test_register_populates_command_gate_timeout_columns
Given a manifest with a qv-gate step containing `command: "make lint", gate: "lint", timeout: 600`,
when `iw register --steps-from <manifest>` runs against an in-memory testcontainer DB,
then the resulting `WorkflowStep` row has `command="make lint"`, `gate="lint"`, `timeout_secs=600`.

#### test_register_leaves_implementation_step_columns_null
Given a manifest with an implementation step (no `command`/`gate`/`timeout`),
when `iw register` runs,
then the `WorkflowStep` row has `command=None`, `gate=None`, `timeout_secs=None`.

#### test_register_stamps_manifest_with_note (AC2 — primary)
Given a manifest file at a temp path that does NOT contain a `_note` field,
when `iw register --steps-from <path>` completes,
then the file on disk has been rewritten with a top-level `_note` key whose value contains both substrings "design-time snapshot" and "iw item-status",
and every original key (`id`, `type`, `title`, `browser_verification`, `steps`) is preserved with identical content,
and the file is valid JSON.

#### test_register_stamping_is_idempotent (AC2 — idempotency)
Given a manifest already stamped by a prior `iw register` run,
when `iw register` runs a second time on the same file,
then the file content is byte-identical to the first stamping (no double-`_note`, no formatting churn).

#### test_register_stamping_preserves_unicode
Given a manifest containing non-ASCII characters (em-dash, accented letters) in `title` or `description`,
when stamping runs,
then the rewritten file preserves the UTF-8 characters (assert via `read_text(encoding="utf-8")` and substring match).

#### test_register_invalid_timeout_fails_clearly
Given a manifest where a step has `timeout: "not-a-number"`,
when `iw register` runs,
then it exits with non-zero and a message mentioning "timeout" and the step ID.

### 2. `tests/unit/test_item_commands_item_status.py` (covers AC1 — primary)

#### test_item_status_json_contains_all_per_step_fields
Given a `WorkflowStep` fixture with all fields populated (including the new `command`, `gate`, `timeout_secs`),
when `iw item-status --json` is invoked,
then each entry in `steps[]` contains keys: `step_id`, `step_number`, `label`, `agent_label`, `opencode_agent`, `type`, `step_type`, `step_label`, `status`, `description`, `prompt_file`, `command`, `gate`, `timeout_secs`.

#### test_item_status_json_null_columns_serialize_as_null
Given a `WorkflowStep` row with `command=None, gate=None, timeout_secs=None, prompt_file=None`,
when `iw item-status --json` is invoked,
then those keys are present in the JSON output with value `null` (not `""`, not omitted).

#### test_item_status_back_compat_keys_retained
Given any `WorkflowStep`,
when `iw item-status --json` is invoked,
then the existing keys `step_id`, `label`, `type`, `status` are present alongside the new explicit aliases (`agent_label`, `step_type`).

#### test_item_status_current_step_enriched
Given a workflow with one step in `in_progress` status,
when `iw item-status --json` is invoked,
then the top-level `current_step` object contains the same enriched field set (plus `duration`).

### 3. `tests/integration/test_register_to_item_status_roundtrip.py` (covers AC1 + AC2 end-to-end)

#### test_register_then_item_status_returns_manifest_superset
Given a manifest file written to a temp dir with a mix of implementation and qv-gate steps,
when `iw register --steps-from <manifest>` runs followed by `iw item-status <ID> --json`,
then for each step the JSON entry contains every field that was in the manifest entry, with identical values, plus the runtime `status` ("pending" before any execution).

#### test_round_trip_preserves_scope_block
Given a manifest that includes a `scope.allowed_paths` block,
when `iw register` runs and stamps the manifest,
then the on-disk manifest's `scope` block is byte-identical to the original (only `_note` was added at the top).

### 4. `tests/integration/test_daemon_legacy_fallback.py` (covers AC4 — primary)

#### test_build_claude_prompt_falls_back_to_manifest_for_null_columns
Given a `WorkflowStep` row with `command=None, prompt_file=None` (simulating a pre-CR-00023 item) and a matching on-disk manifest containing the step's command,
when `_build_claude_prompt(step, worktree_path)` is called,
then the returned prompt content matches what would have been produced from the manifest read alone (compare against a fixture of the expected prompt body).

#### test_get_gate_name_and_command_falls_back
Given a `WorkflowStep` with `command=None, gate=None` and a matching manifest,
when `_get_gate_name_and_command(step, worktree_path)` is called,
then it returns the manifest's `gate`/`command` values.

#### test_compute_qv_baselines_uses_db_first_when_populated
Given a `WorkflowStep` with `command="make lint", gate="lint"` populated AND an on-disk manifest with DIFFERENT values for the same step,
when `_compute_qv_baselines` iterates the step,
then the DB values are used (proving DB-first is winning over the manifest read).

### 5. `tests/unit/test_template_hints.py` (covers AC5 + AC7)

#### test_implementation_templates_mention_iw_item_status (AC5)
For each of the 8 in-scope templates listed in CR-00023's design,
assert the file contents contain both substrings `iw item-status` and `CR-00023`.

#### test_fix_templates_unchanged (AC5 — defensive)
For each of the 8 OUT-of-scope templates (FIX variants + Browser),
assert the file does NOT contain `iw item-status` (defensive — they were not supposed to be modified).

#### test_implementation_template_has_preflight_section (AC7 — primary)
For BOTH copies of `Implementation_Prompt_Template.md` (`templates/design/` and `ai-dev/templates/`):
- Assert the file contains the exact heading `## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023`.
- Assert the file mentions all three of `make format`, `make typecheck`, `make lint`.
- Assert the heading appears BEFORE `## Test Verification (NON-NEGOTIABLE)` (compare `file.find()` indices).
- Assert the file's Subagent Result Contract example contains a `preflight` object — search for the substring `"preflight":` and assert the surrounding text contains keys `format`, `typecheck`, `lint`.

#### test_implementation_template_copies_are_byte_identical (AC7 — sync)
Read both copies of `Implementation_Prompt_Template.md` and assert they are byte-identical (`open(...).read() == open(...).read()`).

#### test_preflight_section_absent_from_non_implementation_templates (AC7 — defensive)
For each of the 6 OUT-of-scope templates that are NOT Implementation (CodeReview / CodeReview_Final / QualityValidation in both dirs):
- Assert the file does NOT contain `Pre-flight Quality Gates`.
- Assert the file does NOT contain `"preflight":` in any code block.

For the FIX / Browser templates (8 files):
- Assert the file does NOT contain `Pre-flight Quality Gates`.

### 6. AC6 — explicit I-00041 S14/S15 regression (covers AC6 — primary)

Add this test to `tests/integration/test_register_to_item_status_roundtrip.py`
(it shares the round-trip fixtures and stays close to AC1):

#### test_item_status_surfaces_db_only_step_not_in_manifest
This is the literal reproduction of the I-00041 S14 catch-22: the DB has more
steps than the on-disk manifest, and the agent must be able to discover the
extra step without ever opening `workflow-manifest.json`.

```
Given a manifest written to a temp dir with N=2 steps (S01 implementation, S02 qv-gate)
And `iw register --steps-from <manifest>` has populated those rows
When an extra `WorkflowStep` row (step_id="S03", agent_label="backend-impl",
  status=in_progress, command=NULL, gate=NULL, prompt_file="prompts/X_S03_Backend_prompt.md")
  is INSERTed directly into the DB (simulating a daemon-side step append)
And `iw item-status <ID> --json` is invoked
Then the response's `steps` array contains an entry with `step_id == "S03"`,
  `status == "in_progress"`, `prompt_file == "prompts/X_S03_Backend_prompt.md"`,
  and `agent_label == "backend-impl"`
And the response's `current_step.step_id == "S03"`
And the test does NOT need to open `workflow-manifest.json` to obtain any of this information
  (assert by patching `pathlib.Path.read_text` to raise on the manifest path and confirming the
  command still succeeds — or by asserting the manifest file's mtime is unchanged after the call).
```

The intent: prove that an agent armed only with `iw item-status <ID> --json` can
identify a step that exists in DB but not in the manifest. If this passes, the
I-00041 root cause is closed.

## ⚠️ Semantic Correctness Warning (I-00003 lesson)

Tests MUST verify **specific values**, not just shape. Shape-only assertions
let a buggy implementation pass — and the I-00003 post-mortem traced a
production regression directly to this anti-pattern. Apply this rule to
every assertion in this step:

- ❌ **BAD (shape-only)**: `assert "command" in step_entry`
- ✅ **GOOD (value-checked)**: `assert step_entry["command"] == "make lint"`

- ❌ **BAD (presence-only)**: `assert "_note" in stamped_json`
- ✅ **GOOD (substring-checked)**: `assert "design-time snapshot" in stamped_json["_note"] and "iw item-status" in stamped_json["_note"]`

- ❌ **BAD (status-only)**: `assert result.exit_code == 0`
- ✅ **GOOD (status + content)**: `assert result.exit_code == 0 and "expected text" in result.output`

If a test is asserting only a key/string is present without checking its
value, S10's review will flag it as HIGH and burn a fix-cycle. Don't.

## Hard Constraints

- All DB-touching tests MUST use testcontainer fixtures from `tests/conftest.py`. NEVER hit port 5433.
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` only (per `tests/CLAUDE.md` rule 2).
- NEVER mock the database in integration tests — `SELECT FOR UPDATE` semantics can't be tested with mocks (per rule 3).
- After `Base.metadata.create_all()`, MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (per rule 5).
- Replace psycopg2 URL: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- Tests must be deterministic and isolated — no test depends on another test's side effects.

## TDD Requirement

For each test:
1. **RED**: write the test, run it. If S01–S07 are correct, it passes immediately. If it fails for a reason like "key not present" or "value is wrong", that is a real implementation bug — capture in your report and let the fix-cycle handle.
2. **GREEN**: confirm the test passes with implementation as-is.
3. **REFACTOR**: factor common fixtures into `tests/conftest.py` if reused across multiple tests.

## Test Verification

Before reporting done:

```bash
make test-unit       # all unit tests must pass (existing + new)
make test-integration # all integration tests must pass (existing + new)
make lint            # must be clean
make typecheck       # must be clean
```

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "CR-00023",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_item_commands_register.py",
    "tests/unit/test_item_commands_item_status.py",
    "tests/unit/test_template_hints.py",
    "tests/integration/test_register_to_item_status_roundtrip.py",
    "tests/integration/test_daemon_legacy_fallback.py"
  ],
  "tests_passed": true,
  "test_summary": "X new tests added, all passing; full suite: Y passed, 0 failed",
  "ac_coverage": {
    "AC1": ["test_item_status_json_contains_all_per_step_fields", "test_register_then_item_status_returns_manifest_superset"],
    "AC2": ["test_register_stamps_manifest_with_note", "test_register_stamping_is_idempotent"],
    "AC3": "verified by S01's alembic check + S02 review (no DB-applied test possible from agent context)",
    "AC4": ["test_build_claude_prompt_falls_back_to_manifest_for_null_columns", "test_get_gate_name_and_command_falls_back", "test_compute_qv_baselines_uses_db_first_when_populated"],
    "AC5": ["test_implementation_templates_mention_iw_item_status", "test_fix_templates_unchanged"],
    "AC6": ["test_item_status_surfaces_db_only_step_not_in_manifest"],
    "AC7": ["test_implementation_template_has_preflight_section", "test_implementation_template_copies_are_byte_identical", "test_preflight_section_absent_from_non_implementation_templates"]
  },
  "blockers": [],
  "notes": ""
}
```
