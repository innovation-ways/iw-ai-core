# CR-00092_S02_Database_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub (wave 2: mid-size domain)
**Step**: S02
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection (`docker ps`, `docker inspect`, `docker logs`) are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do NOT run alembic. Do NOT touch `orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00092 --json`.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — Design document.
- `ai-dev/work/CR-00092/reports/CR-00092_S01_Database_report.md` — S01's report (read the `wave_scrub_count` and `remaining_baseline_count` keys).
- `orch/db/column_docs_baseline.txt` — baseline (already shrunk by S01's wave-1 scrub).
- `docs/IW_AI_Core_Database_Schema.md` — primary source for column descriptions.
- `orch/db/models.py` — the file you will edit.

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S02_Database_report.md`.
- Edits in `orch/db/models.py`.

## Context

You are implementing **wave 2 of 4**. Wave 2 owns the five mid-size domain classes:

| Class | Entries in baseline |
|-------|---------------------|
| `WorkflowStep` (line 755) | 20 |
| `DocGenerationJob` (line 1782) | 19 |
| `CodeIndexJob` (line 1944) | 18 |
| `TestRun` (line 1626) | 17 |
| `Batch` (line 1173) | 16 |
| **Total** | **90** |

Waves 3–4 (S03–S04) handle the remaining 31 classes. S04 also removes the baseline file and flips the gate — DO NOT do those in this step.

## Requirements

### 1. Read S01's report and the design

Read S01's report first — confirm wave-1 reported `completion_status: complete` and `wave_scrub_count: 103`. If S01 reported partial / blocked, STOP and raise a blocker — wave 2 inherits a broken tree otherwise.

Then re-read `ai-dev/active/CR-00092/CR-00092_CR_Design.md` (especially the **Notes → Description sourcing rule**).

### 2. Scrub all 90 columns in `orch/db/models.py`

Same rules as S01. For each of the five wave-2 classes, walk every `Column(...)` declaration and add a one-line `doc="..."` argument sourced from `docs/IW_AI_Core_Database_Schema.md` where possible, inferred otherwise. Do NOT touch classes outside the wave-2 set.

Wave-2 class-specific notes:
- `WorkflowStep` columns include `step_type` (SAEnum), `agent` (text), `gate` (nullable text — set for qv-gate steps only), `command` (the shell command for qv-gate steps), `timeout` (seconds). Reference enums by class name.
- `DocGenerationJob` rows track AI doc regen background jobs; `status` is a JobStatus SAEnum; `error_message` and `log_path` are nullable text. The job lifecycle is documented in `orch/doc_service.py`.
- `CodeIndexJob` rows track LanceDB indexing background jobs; columns mirror the DocGenerationJob shape with code-specific fields (`commit_sha`, `index_path`).
- `TestRun` rows are launched from the dashboard's Tests/Quality view; the `status` SAEnum is `TestRunStatus`. The run engine is `orch/test_runner.py`.
- `Batch` rows aggregate one or more `BatchItem`s; `status` is computed from member items by `compute_batch_status` (covered by CR-00060's property tests — see also `BatchStatus` enum).

### 3. Verify wave 2 is fully scrubbed

```bash
uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt 2>&1 | grep -E "(WorkflowStep|DocGenerationJob|CodeIndexJob|TestRun|Batch)\." | wc -l
# Expected: 0 new violations for these five classes
```

Do NOT run `--write-baseline`. S04 owns final regeneration.

### 4. Targeted test verification

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

All tests must pass.

## Pre-flight Quality Gates — same as S01

1. `make format` — auto-fix and re-stage if it modifies anything.
2. `make typecheck` — zero errors in `orch/db/models.py`.
3. `make lint` — zero errors.

## TDD Requirement

```
"tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests"
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "database-impl",
  "work_item": "CR-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/db/models.py"],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/orch/db/test_column_docs.py)",
  "tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests",
  "wave_scrub_count": 90,
  "cumulative_scrub_count": 193,
  "remaining_baseline_count": "<integer>",
  "blockers": [],
  "notes": "Wave 2 of 4 (WorkflowStep + DocGenerationJob + CodeIndexJob + TestRun + Batch). 90 columns documented. Cumulative through S02 = 193 of 450. Baseline file unchanged; S04 regenerates and deletes."
}
```
