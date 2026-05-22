# I00103_S01_Backend_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`, and `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` / `alembic downgrade` / `alembic stamp` against the live orch DB. This work item adds NO migration — `daemon_events.metadata` is JSONB and new keys are additive.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00103 --json` for current step list.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document (read first).
- `ai-dev/active/I-00103/I-00103_Functional.md` -- Human-facing summary.
- `orch/daemon/auto_merge.py` -- The file you'll modify (lines 268-282 for `LLMCallResult`, 931-981 for the event-emission code path).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md` -- Step report.

## Context

You are fixing an observability gap. When an auto-merge LLM call fails (timeout / non-zero exit / subprocess exception), the resulting `merge_auto_resolution_failed` DaemonEvent currently lists the *file paths* that errored but drops the actual *error reason string*. The string already exists in memory at the point of emission — it's stored on each `LLMCallResult.error` — but the event-payload builder at `orch/daemon/auto_merge.py:961-981` never includes it in the metadata dict.

Read `ai-dev/active/I-00103/I-00103_Issue_Design.md` fully before changing code. Pay particular attention to the §Root Cause Analysis section for the file:line landmarks, and to AC1 / AC5 for the contract you must satisfy.

## Requirements

### 1. Add `per_file_errors` to the failed-event metadata payload

At `orch/daemon/auto_merge.py:961-981`, the `EVENT_AUTO_RESOLUTION_FAILED` event is emitted with a metadata dict containing `phase`, `abstained_files`, `error_files`, `proposed_files`, `runtime_option_id`, and the two token totals. You must add a new key `per_file_errors` to that dict, derived from the `llm_calls` accumulator built at lines 931-956.

**Schema for the new field** (list of dicts; one entry per errored call):

```python
{
    "file_path": str,    # call.file_path
    "error":     str,    # call.error, truncated to 500 chars
    "cli_tool":  str,    # call.cli_tool
    "model":     str,    # call.model
}
```

Only `LLMCallResult` entries with `error is not None` go into the list. ABSTAIN entries and proposed-content entries MUST NOT appear in `per_file_errors` (they continue to flow through `abstained_files` / `proposed_files` exactly as today).

### 2. Truncate each `error` string at 500 characters

Match the cap that already exists at `auto_merge.py:784` for `result.stderr[:500]`. Cap the persisted `error` value with the same idiom — `call.error[:500]` is sufficient — so a runaway stderr or a long stack trace from the subprocess exception path (lines 753-771) cannot inflate the JSONB row beyond reasonable bounds.

Do NOT change the in-memory `LLMCallResult.error` field itself or the `logger.warning(...)` callsites at lines 738 / 754 / 774; those continue to log the full untruncated string. Only the *persisted* per-file copy is capped.

### 3. Preserve the existing event payload shape

`abstained_files`, `error_files`, `proposed_files`, `total_input_tokens`, `total_output_tokens`, `runtime_option_id`, and `phase` MUST remain in the metadata dict with identical semantics. The new field is purely additive.

The dashboard renderer and the per-file-errors test in S05 will rely on the existing `error_files` list being the canonical "which file paths errored" view (a flat list of paths for quick scanning), and on `per_file_errors` being the parallel structured view (path + reason + runtime, with the same path order). Keep the two consistent — the order of `per_file_errors[i].file_path` must match the order of `error_files`.

### 4. Respect the `max_event_metadata_bytes` cap

The existing truncation logic at `auto_merge.py:1003-1009` enforces `config.max_event_metadata_bytes` only on the `merge_auto_resolved` payload (the `metadata` dict that includes `per_file` with `proposed_content`). The `merge_auto_resolution_failed` payload does NOT currently honour that cap — your new field MUST keep the failed-event payload well under it. With a 500-char cap per `error` and at most `max_conflicted_files_per_merge = 5` entries, the worst-case `per_file_errors` payload is ≈ 5 × (500 + path + 80 metadata) ≈ 3.5 KB, comfortably under the 256 KB cap. No new truncation pass is required, but DO add a one-line comment noting this analysis so future readers don't have to redo it.

### 5. Test verification

Run targeted tests only; do NOT run `make test-unit` or `make test-integration` from this step (those are the S13 and S15 QV gates). For this S01 step, exercise the existing coverage of the `attempt_resolution` failed-event path:

```bash
uv run pytest tests/integration/test_auto_merge_phase1.py -v 2>&1 | tail -30
```

`tests/integration/test_auto_merge_phase1.py` already covers the `merge_auto_resolution_failed` emission path (`test_ac4_operator_ux_unchanged_on_abstain`, `test_ac4_operator_ux_unchanged_on_llm_error`), so running this single file confirms you have not broken the failed-event payload. Note there is **no** `tests/unit/test_auto_merge.py` — `attempt_resolution` has no unit-level coverage because it needs a real DB session. This is one targeted file, not the full `make test-integration` suite. The new S05 test file does not exist yet when S01 runs.

### 6. TDD note

This step is a **Backend** step that adds behaviour-implementing code. Because the dedicated tests live in S05, the recommended workflow is:

1. Implement the change in `orch/daemon/auto_merge.py`.
2. Run existing unit coverage (step 5 above) to verify no regression.
3. Report `tdd_red_evidence` as `"n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach"`.

This is consistent with the design doc's File Manifest, which assigns the new test files to S05.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for layer boundaries and naming.

Specific rules that apply here:

- `DaemonEvent.metadata` is named `event_metadata` in Python; the DB column is `metadata`. Make sure your reads use the SQLAlchemy attribute name (none needed for this fix — you're writing to the dict before persistence) but the persisted JSON key remains `per_file_errors`.
- Match the existing `_emit_event(...)` call pattern at lines 962-981 (positional args: `db`, `project_id`, `event_type`, `item_id`, `"work_item"`, `message`, `metadata_dict`).
- Match existing key-naming style: `snake_case`, plural collection name, dict entries match the schema above.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, you MUST run:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the file you touched.
3. **`make lint`** — must report zero errors involving the file you touched.

If a tool isn't available, STOP and raise a blocker.

Record results in the `preflight` field of your result contract.

## Test Verification (NON-NEGOTIABLE)

After implementation, run the targeted tests that exercise the auto_merge module (see Requirement 5). Do NOT run `make test-integration` or the full unit suite — those are the S13 / S15 QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00103",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/auto_merge.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — reproduction + regression tests delegated to S05 tests-impl per design doc TDD Approach",
  "blockers": [],
  "notes": ""
}
```
