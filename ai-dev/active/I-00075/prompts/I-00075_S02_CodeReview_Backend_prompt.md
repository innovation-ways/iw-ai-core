# I-00075_S02_CodeReview_Backend_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

S01 produces a test-data fixture file only. There is no migration in scope.
If S01 generated a migration, that is a CRITICAL out-of-scope finding — flag it.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00075 --json`
- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- Design document. **Read § Notes carefully**: it specifies WORK_ITEM_ID=I-99001, exactly 2 fix cycles on S02, and references the F-00055 fixture as the canonical shape.
- `ai-dev/active/I-00075/reports/I-00075_S01_Backend_report.md` -- Implementation report
- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` -- The fixture file produced by S01
- `ai-dev/archive/F-00055/e2e_fixtures/001_f00055_workflow.py` -- Reference implementation S01 was instructed to mirror

## Output Files

- `ai-dev/active/I-00075/reports/I-00075_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the only code-producing step of I-00075. The implementation surface is small (one ~120-line fixture file) so the review is targeted: focus on **correctness against the design contract**, **idempotency**, **insert-order discipline**, and **shape symmetry with the F-00055 reference fixture**.

**Read the design doc BEFORE reading the code** (this is a finding from CR-00039 self-assess: code review prompts that skip the design doc miss design-mandated invariants).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the fixture file:

```bash
make lint
make format
```

Any NEW violation in `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` (compared to `main`) is a **CRITICAL** finding with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture / Contract Compliance — design doc

Verify ALL of the following against the design doc § Notes and § Affected Components:

- File path is **exactly** `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`. The `001_` prefix is required (lexical-order discovery in `scripts/e2e_seed.py:_discover_fixture_files`).
- File name does NOT start with `_` (the discoverer skips private modules — see `scripts/e2e_apply_item_fixtures.py:42`).
- The module exposes exactly one public top-level callable named `seed(db: Session) -> None`. Other top-level definitions (constants, helpers) are acceptable IF they mirror the F-00055 reference fixture's style.
- Module-level docstring exists, names what it seeds (item, step count, fix-cycle count), states idempotency, names `I-99001`, points back to the design doc.
- Module-level constants `PROJECT_ID = "iw-ai-core"`, `WORK_ITEM_ID = "I-99001"`, `AGENT_LABEL = "opencode"` are present and correctly typed.

### 2. Synthetic-data shape — semantic correctness

This is the most important check. The fixture must produce **exactly the rows specified** in the design's § Requirements 3:

- 1 `Batch` with `id="BATCH-I00075DEMO"`, `status=BatchStatus.completed`, `max_parallel=4`, `cli_tool="opencode"`, `auto_publish=False`
- 1 `BatchItem` linking the batch to `I-99001`, `status=BatchItemStatus.merged`, `execution_group=0`
- 1 `WorkItem` with `id="I-99001"`, `type=WorkItemType.Issue`, `status="completed"`, `phase="done"`, all string fields populated
- 3 `WorkflowStep` rows: `S01` (implementation), `S02` (code_review), `S03` (quality_validation), all `status=StepStatus.completed`
- 4 `StepRun` rows: 1 for S01, **3** for S02 (run_number 1/2/3), 1 for S03 — all `RunStatus.completed`
- **Exactly 2** `FixCycle` rows attached to S02 with `cycle_number=1` and `2`, `trigger_type=FixTrigger.code_review`, `status=FixStatus.completed`. **Two cycles is deliberate** (exercises `loop.index` formatting and multi-pill connectors); flag any deviation.

Reading hint: instantiate the fixture mentally — would `dashboard/templates/components/step_pipeline.html:33-41` render exactly 2 amber pills for S02 and 0 for S01/S03? If not, that is a CRITICAL finding.

### 3. Idempotency

The fixture MUST short-circuit on the second call against the same DB:

- Reads `WorkflowStep` (or another marker row) before any insert
- Returns early if the marker is found
- Does NOT call `db.commit()` (caller owns the commit — see `scripts/e2e_seed.py:457` and `scripts/e2e_apply_item_fixtures.py:73`)

Verify the early-return guard mirrors F-00055's pattern. A guard that checks only `WorkItem` (and not `WorkflowStep`) would partially re-insert child rows — flag as HIGH if you see that.

### 4. Insert-order discipline

Per `scripts/e2e_seed.py` docstring lines 32–43:

- `db.flush()` after `db.add(batch)` so `BatchItem.batch_id` resolves
- `db.flush()` after `db.add(work_item)` so `BatchItem.work_item_id` resolves (composite FK)
- `db.flush()` after each `WorkflowStep` insert (or after the WorkflowStep loop) so `StepRun.step_id` and `FixCycle.step_id` resolve to autoincrement IDs

Missing flushes are a HIGH finding (causes `ForeignKeyViolation` at runtime, which costs a full fix-cycle slot to diagnose because the symptom appears in the qv-browser step, not S01).

### 5. Code Quality

- Imports are organized (stdlib, third-party, first-party — ruff isort rules in `pyproject.toml`)
- `Session` is imported under `TYPE_CHECKING` (it is not used at runtime; runtime imports are unnecessary and ruff will flag them)
- No unused imports, no `from x import *`
- No `print()` statements (use the same silent style as F-00055; the caller logs).

### 6. Project Conventions — `CLAUDE.md`

- Read `CLAUDE.md` for the rule "**NEVER** connect tests to live DB (port 5433) — use testcontainers only". The fixture itself does not run against any DB at import time, so this rule is naturally satisfied — but verify the fixture does NOT import `orch.db.session.get_session` or otherwise resolve a live connection.
- Read `orch/CLAUDE.md` for "**NEVER** execute docker container/volume/network management commands from orch code or scripts" — the fixture is allowed to read DB models but MUST NOT spawn subprocesses, especially not docker.

### 7. Security

- No hardcoded credentials, tokens, or PII (the fixture only writes synthetic test rows with constant values)
- The fixture writes ONLY to `project_id="iw-ai-core"` — flag any other project_id as HIGH (could leak demo rows into another project's worktree)

### 8. Out-of-scope changes

The S01 step is allow-listed to ONLY touch `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` (per `workflow-manifest.json:scope.allowed_paths`). Any other file modified is a CRITICAL out-of-scope finding.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

```bash
uv run pytest tests/integration/test_i00075_fix_cycle_fixture.py -v 2>&1 | tail -50
```

If S03 has not yet authored that file, instead run the import-shape probe:

```bash
uv run python -c "import importlib.util; \
spec = importlib.util.spec_from_file_location('demo', 'ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py'); \
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
assert callable(m.seed), 'seed must be callable'"
```

Report results accurately in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Wrong row count, missing FixCycle rows, out-of-scope file modified, security issue | Must fix before merge |
| **HIGH** | Idempotency broken, insert-order missing flush, design-doc invariant violated | Must fix before merge |
| **MEDIUM (fixable)** | Style drift from F-00055, missing module docstring, ruff/lint violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Helper-function placement, naming preference | Optional |
| **LOW** | Nitpicks | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00075",
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
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
