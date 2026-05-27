# F-00090_S02_Backend_prompt

**Work Item**: F-00090 -- Regression-rate tracking — correlate filed Incidents back to the merge that introduced the regression
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network state-changing command. Testcontainers spun up by pytest fixtures are exempt. Read-only `docker ps` / `inspect` / `logs` are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` (or downgrade/stamp) against the live orchestration DB. This step does NOT add new migrations — only the service + CLI. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` — design (read first; AC2, AC3, AC4 are your targets).
- `ai-dev/active/F-00090/reports/F-00090_S01_Database_report.md` — S01 report, for the new schema layout.
- `orch/cli/main.py` and `orch/cli/__init__.py` — for how command groups are registered.
- `orch/cli/item_commands.py` — read for command/option style conventions.
- `orch/db/models.py` — `WorkItem` model (post-S01 with new fields).
- `orch/db/session.py` — `SessionLocal`, `get_session()` patterns.

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S02_Backend_report.md` — step report.
- New: `orch/regression_link_service.py`
- New: `orch/cli/regression_commands.py` (subcommand group), wired into `orch/cli/main.py` / `__init__.py`.
- New: `tests/integration/test_regression_link_service.py`

## Context

You are implementing the service + CLI layer for **F-00090**. The service is the single write path for regression classification; the CLI command exposes the heuristic to operators.

Read the design document first. Read `CLAUDE.md` and `orch/CLAUDE.md` for project conventions.

## Requirements

### 1. `orch/regression_link_service.py` — pure service module

Expose:

- `@dataclass class Candidate: commit_sha: str; work_item_id: str | None; score: int`
- `def classify(session, *, project_id: str, item_id: str, introduced_by_work_item_id: str | None, introduced_by_commit_sha: str | None, classification: RegressionClassification, classified_by: str) -> WorkItem` — validates the inputs (cross-project FK rejected; `introduced_by_work_item_id` must reference a row whose `status == 'done'`), updates the `WorkItem`, sets `classified_at = datetime.now(timezone.utc)`. Returns the refreshed row. Raises `ValueError` on invalid inputs.
- `def suggest_introducer(session, *, project_id: str, item_id: str, repo_path: Path | None = None) -> list[Candidate]` — see "File-discovery contract" below for the exact mechanism. Ranks candidates by frequency descending. Empty list when nothing found.

Implementation notes:

- Use `subprocess.run(["git", ...], cwd=repo_path or Path.cwd(), capture_output=True, text=True, check=False)`. Never `shell=True`.
- The heuristic is best-effort; swallow `subprocess.CalledProcessError` and `FileNotFoundError` and return `[]`.
- Resolve `commit_sha → work_item_id` by scanning recent merge commits' messages for `F-NNNNN` / `I-NNNNN` / `CR-NNNNN` patterns (this is how the daemon's squash merges are stamped). When the pattern is absent, leave `work_item_id = None`.
- All public functions take a `session: Session` argument; do NOT open sessions inside the service.

**File-discovery contract (NON-NEGOTIABLE)** — the heuristic only operates on Incidents whose fix has been merged. Concretely:

1. Load the `WorkItem` row for `item_id`. If `status != 'done'` or there is no merge SHA recorded (check `merge_commit_sha` / equivalent field on `WorkItem`, or derive from the most-recent step run record if no field exists — match the existing column on `WorkItem` and document the choice in the report), return `[]` and log at INFO level: `"suggest_introducer: I-NNNNN not merged yet; no file list available"`.
2. Given the merge SHA, derive the fix's file list with `git show --name-only --pretty=format: <merge_sha>` (filtering out empty lines). If the command fails or returns no files, return `[]`.
3. For each file in the fix list, run `git log -n 50 --pretty=format:%H -- <file>` to enumerate the most-recent 50 commits that touched it, ignoring the Incident's own merge SHA. Aggregate counts across files; the score for a candidate is the number of files-it-touched in the fix's file list.
4. For each candidate SHA, resolve to a `work_item_id` per the rule above (scan the commit message for `F-NNNNN` / `I-NNNNN` / `CR-NNNNN`). Drop candidates whose resolved `work_item_id` belongs to a different project (cross-project FK is rejected at write time anyway, so suggesting them is noise).
5. Return the top 10 candidates sorted by `(score DESC, recency DESC)`.

Add a docstring on `suggest_introducer` summarising this contract — the reader should not need to read the prompt to understand the boundary conditions.

### 2. `iw regression-classify` CLI command

Create `orch/cli/regression_commands.py` defining a Click group `regression` with a single subcommand `classify`:

```
uv run iw regression-classify --incident I-NNNNN [--accept N] [--project PROJECT_ID]
```

Behaviour:

- Without `--accept`: invoke `suggest_introducer()`, print the ranked candidates as a small table (`rank | sha | work_item_id | score`), exit 0. When the list is empty, print `No suggestions` and exit 0.
- With `--accept N`: take the Nth candidate (1-indexed), call `classify(... classification=RegressionClassification.regression, classified_by="heuristic:auto")`, print `Classified I-NNNNN as regression introduced by <wi or sha>`, exit 0.
- Invalid `--accept` (out of range) → print error, exit 2.
- Unknown incident or unknown project → exit 2.

Wire the group via `orch/cli/main.py` (or `__init__.py`, matching the existing style). Re-read `orch/cli/item_commands.py` for the exact pattern.

### 3. Integration tests — `tests/integration/test_regression_link_service.py`

Cover AC2..AC4 + relevant Boundary Behavior rows:

- `test_classify_persists_link` — happy path for AC2.
- `test_classify_rejects_cross_project_fk` — Boundary row.
- `test_classify_rejects_non_merged_target` — Boundary row.
- `test_classify_overwrites_on_reclassify` — Boundary row.
- `test_suggest_returns_empty_when_no_files` — Boundary row (AC3 corner; Incident has merge but no files changed).
- `test_suggest_returns_empty_when_incident_unmerged` — File-discovery contract step 1: Incident with `status != 'done'` returns `[]` immediately, no `git` invocation attempted.
- `test_suggest_ranks_by_frequency` — AC3 happy path. Use a tmp git repo fixture (testcontainer Postgres + a real `git init` tmp dir; write a few commits touching specific files, then a "fix" merge commit that touches the same files; assert ranking by score then recency).
- `test_suggest_drops_cross_project_candidates` — File-discovery contract step 4: candidate resolving to a different `project_id` is filtered out.
- `test_cli_prints_suggestions` — AC4 happy path via Click's `CliRunner`.
- `test_cli_accept_persists_with_heuristic_auto` — AC4 acceptance path.

Use the existing testcontainer fixtures from `tests/conftest.py` — see `tests/CLAUDE.md` for the rules. NEVER connect tests to the live DB on port 5433.

### 4. RED-first discipline (NON-NEGOTIABLE)

Write the failing tests FIRST. Run a targeted pytest invocation against each new test file and capture an `AssertionError` (not `ImportError` / `SyntaxError` / fixture error) before writing the service. Record one representative failure in `tdd_red_evidence`.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Key constraints:

- Sync SQLAlchemy 2.0 — no async.
- psycopg v3 driver — testcontainers must replace `postgresql+psycopg2://` with `postgresql+psycopg://`.
- FTS_FUNCTION_SQL + FTS_TRIGGER_SQL must run after `Base.metadata.create_all()` in tests (see `tests/conftest.py`).
- Click 8.1+ style — match existing command groups.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting completion:

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the new test file (targeted):

```bash
uv run pytest tests/integration/test_regression_link_service.py -v
```

Do **NOT** run `make test-integration` or `make test-unit` — those are the QV gate steps.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/regression_link_service.py",
    "orch/cli/regression_commands.py",
    "orch/cli/main.py",
    "tests/integration/test_regression_link_service.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/integration/test_regression_link_service.py: N passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_regression_link_service.py::test_classify_persists_link — AssertionError: WorkItem.regression_classification is None (RED before service implementation)",
  "blockers": [],
  "notes": ""
}
```
