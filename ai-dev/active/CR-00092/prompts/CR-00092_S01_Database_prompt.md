# CR-00092_S01_Database_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub (wave 1: heavyweights)
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

If your task seems to require a prohibited command, STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. `doc=` on a SQLAlchemy `Column` is ORM-side metadata only — it does not appear in generated DDL. Do NOT run `alembic revision`, `alembic upgrade`, or `make migration-check`. Do NOT add or modify any file under `orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00092 --json` over the manifest snapshot.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — Design document (read FIRST, especially the Description / Desired Behavior / Notes / Acceptance Criteria sections).
- `orch/db/column_docs_baseline.txt` — the 450-entry cleanup backlog frozen by CR-00085. Wave 1 covers the four heavyweight classes listed below.
- `docs/IW_AI_Core_Database_Schema.md` — primary source for column descriptions. Read the per-table sections for the four target classes BEFORE writing any `doc=` text.
- `orch/db/models.py` — the file you will edit.

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S01_Database_report.md` — Step report.
- Edits in `orch/db/models.py` (in-place; the only file you may modify in this step).

## Context

You are implementing **wave 1 of 4** of the CR-00085 follow-up: scrubbing the 450-entry column-docs baseline by adding a one-line `doc="..."` argument to every undocumented `Column(...)` declaration in `orch/db/models.py`. Wave 1 owns the four heaviest-baseline classes:

| Class | Entries in baseline |
|-------|---------------------|
| `WorkItem` (line 524) | 33 |
| `StepRun` (line 859) | 28 |
| `ProjectDoc` (line 1686) | 21 |
| `BatchItem` (line 1247) | 21 |
| **Total** | **103** |

Waves 2–4 (S02–S04) handle the remaining 36 classes. S04 also removes the baseline file and flips the gate from warn-first to blocking — DO NOT do those in this step.

## Requirements

### 1. Read the design and the schema doc first

Read `ai-dev/active/CR-00092/CR-00092_CR_Design.md` end-to-end. Pay special attention to the **Notes → Description sourcing rule** — that rule governs every `doc=` string you write. In summary:

1. **Schema doc first.** Open `docs/IW_AI_Core_Database_Schema.md` and find the per-table section for each of the four wave-1 classes (`work_items`, `step_runs`, `project_docs`, `batch_items`). Where a column already has a description (in the DDL comment, the trigger code, or the prose around it), use that description verbatim — trimmed to one line.
2. **Inferred otherwise.** When the schema doc is silent on a column, write a one-line description inferred from (a) the SQL column name, (b) the SQLAlchemy type / nullable / default / FK target, (c) how the python attribute is used in `orch/` and `dashboard/` (grep is your friend). Keep it under ~100 characters.
3. **NEVER edit the schema doc.** It is out of scope for this CR.

### 2. Scrub all 103 columns in `orch/db/models.py`

For each of the four classes above, walk every `Column(...)` declaration in the class body and add a `doc="..."` keyword argument. Examples of the shape of edit:

Before:
```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
```
After:
```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, doc="Surrogate primary key.")
```

Before:
```python
status: Mapped[WorkItemStatus] = mapped_column(SAEnum(WorkItemStatus), nullable=False)
```
After:
```python
status: Mapped[WorkItemStatus] = mapped_column(
    SAEnum(WorkItemStatus),
    nullable=False,
    doc="Current lifecycle status — see WorkItemStatus enum for the full state machine.",
)
```

**Rules for the `doc=` text**:
- One line, in plain English. No multi-line strings, no backslash continuations.
- Describe WHAT the column holds, not implementation mechanics. "Surrogate primary key" is good; "BIGSERIAL via Postgres sequence" is not.
- Reference enums by class name when the column's type is a SAEnum (`see WorkItemStatus enum`).
- For FK columns, name the referenced table: `doc="FK → projects.id; the project this work item belongs to."`.
- For timestamp columns, say what event the timestamp marks: `doc="When the row was first inserted (server default = now())."`.
- For JSONB columns, name the shape if it's documented in the schema doc; otherwise describe the role: `doc="Free-form configuration overrides applied at item launch."`.
- For `DaemonEvent.event_metadata` specifically (the python attribute aliased away from SQLAlchemy's reserved `metadata`): the `doc=` lives on the `Column(...)` declaration regardless of the python attribute name. The scanner reports the SQL column name (`metadata`), not the python attribute name.

**Rules for the edit shape**:
- DO NOT reformat unrelated code. The diff should be minimal — only the `doc=` argument addition per `Column(...)`.
- When the existing declaration fits on one line and adding `doc=` would push past 100 characters, split into a multi-line `mapped_column(...)` call. Match the surrounding indentation style.
- DO NOT add `# why` or any other comments above column declarations — the `doc=` argument is self-documenting.
- DO NOT add `doc=` to columns OUTSIDE the four wave-1 classes. Waves 2–4 own the remaining 36 classes; touching them here causes merge serialization headaches.

### 3. Verify your wave is fully scrubbed

After editing, run the scanner against the live baseline and confirm the wave-1 class entries are gone:

```bash
uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt 2>&1 | grep -E "(WorkItem|StepRun|ProjectDoc|BatchItem)\." | wc -l
# Expected: 0 (no new violations for these four classes after S01)
```

Also confirm the baseline file still contains the wave-2/3/4 entries (they belong to other classes and are scrubbed in later steps — do NOT regenerate the baseline in this step):

```bash
wc -l orch/db/column_docs_baseline.txt
# Expected: 470 lines minus your 103 wave-1 entries = 367 lines (give or take the header comment block)
```

Do NOT run `--write-baseline` in this step. S04 owns the final baseline regeneration + deletion.

### 4. Targeted test verification (NON-NEGOTIABLE)

Run the existing scanner library-form tests to confirm you have not broken them:

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

All tests must pass. Do NOT run `make test-unit` or `make test-integration` — those are S11/S12 QV gates with their own budgets.

## Project Conventions

Read the project's `CLAUDE.md` for:
- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- The `DaemonEvent.event_metadata` rename rule (you do not need to act on it in this wave — wave 4 handles `DaemonEvent` — but be aware of it now).

Match existing code style in `orch/db/models.py`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order and fix anything they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors in `orch/db/models.py`.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object.

## TDD Requirement

This step adds NO new behavioural tests — it is a content-only edit on existing `Column(...)` declarations. Use:

```
"tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests (scanner tests in tests/orch/db/test_column_docs.py already cover the gate, unchanged)"
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/orch/db/test_column_docs.py)",
  "tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests",
  "wave_scrub_count": 103,
  "remaining_baseline_count": "<integer — `wc -l orch/db/column_docs_baseline.txt` minus header lines>",
  "blockers": [],
  "notes": "Wave 1 of 4 (WorkItem + StepRun + ProjectDoc + BatchItem). 103 columns documented. Baseline file unchanged in this step — waves 2/3 still scrubbing their classes; S04 regenerates and deletes the baseline."
}
```

The custom `wave_scrub_count` and `remaining_baseline_count` keys give S05 (CodeReview) and S06 (CodeReview_Final) an explicit numeric anchor for cross-step consistency checks.
