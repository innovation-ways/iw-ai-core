# F-00059_S02_Backend_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network mutation command.
See the banner in the S01 prompt for the full list. Testcontainers, read-only
introspection, and `./ai-core.sh` / `make` targets are allowed.

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — see *Scope* and *AC4*, *AC5*, and *Boundary Behavior*
- `ai-dev/active/F-00059/reports/F-00059_S01_Database_report.md` — confirms columns + FTS trigger exist
- `orch/cli/item_commands.py` — existing `register` command (the function around line 212 loads `design_doc_content` from disk)
- `scripts/backfill_functional_doc.py` — existing backfill script (writes a markdown file via opencode)

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S02_Backend_report.md` (new)
- `orch/cli/item_commands.py` (modified — `register` auto-detects and loads functional doc)
- `scripts/backfill_functional_doc.py` (modified — new `--load-db` flag)

## Context

S01 added the DB columns and FTS trigger. This step makes two existing code
paths populate the new `functional_doc_content`:

1. **`iw register`** — the command that enrolls a new work item in the DB.
   Today it reads `design_doc_path` from disk and stores the text in
   `design_doc_content`. Extend it to do the same for a sibling
   `<ID>_Functional.md` file.
2. **`scripts/backfill_functional_doc.py`** — today writes the markdown file
   only. Add a flag so a single invocation also UPDATEs the DB columns.

No skill, template, or UI changes in this step.

## Requirements

### 1. `iw register` auto-detects the functional doc

Read the existing `register` command in `orch/cli/item_commands.py` (the block
that resolves `design_doc_path`, reads its content, and passes both to the
`WorkItem` INSERT). Add parallel behaviour:

- After `design_doc_path` is resolved to an absolute path, compute
  `functional_doc_candidate = design_doc_path.parent / f"{work_item_id}_Functional.md"`.
- If that file exists and is readable, set `functional_doc_path` (stored as a
  path **relative to the repo root**, same convention as `design_doc_path`) and
  read its UTF-8 content into `functional_doc_content`.
- If the file does not exist, leave both fields `None` and proceed — this is
  AC4's "file absent" branch and must not raise.
- If the file exists but is empty or unreadable (permission error), log a
  warning via the CLI's existing warn path and still proceed (treat as
  absent for DB purposes).

Add a new Click option `--functional-doc PATH` on `register` that:

- Overrides the auto-detect path.
- If given AND the file does not exist, the command must fail with a clear
  error (non-zero exit) — this is AC4's "explicit override with missing file"
  branch.
- If given AND the file exists, both DB columns are populated from it and
  `functional_doc_path` in the DB is the argument's value, resolved relative
  to `Path.cwd()` as the existing `design_doc_path` handling does.

### 2. `scripts/backfill_functional_doc.py` gains `--load-db`

The existing script writes a markdown file via opencode. Add an optional flag
`--load-db` that, after the file has been successfully created by opencode,
updates the `work_items` row via SQLAlchemy:

```python
with SessionLocal() as session:
    item = session.get(WorkItem, (project_id, item_id))
    if item is None:
        # item missing from DB — exit 4 as documented in the script header
        ...
    item.functional_doc_path = relative_path_to_output
    item.functional_doc_content = output_path.read_text(encoding="utf-8")
    session.commit()
```

- `--load-db` is **opt-in**. Without it, the script behaves exactly as today
  (file only; no DB write).
- Resolve `project_id` via the existing `find_project_root(Path.cwd())` call.
- `relative_path_to_output` is relative to the repo root.
- If the work item is not in the DB, exit 4 WITHOUT writing to the DB and
  WITHOUT deleting the file opencode produced (the operator may want the
  file regardless).
- If opencode fails to produce the file, the script already exits with
  opencode's return code before reaching the DB path — `--load-db` must not
  change that.
- Update the script's module docstring exit-code table to include:
  `7  --load-db passed but file was produced yet DB update failed` (catch
  `SQLAlchemyError`, print the message, exit 7).

### 3. Do not regress the existing `register` or backfill behaviour

- `iw register` with no adjacent functional doc and no `--functional-doc`
  flag must still succeed exactly as today. `functional_doc_path` and
  `functional_doc_content` are `None`; the WorkItem row is inserted normally.
- The backfill script without `--load-db` must behave bit-for-bit identically
  to today.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`. Click 8.1+ for the CLI option.
SQLAlchemy 2.0 sync style. psycopg v3. Use the existing
`ctx.obj["get_session"]` pattern if available for the `register` command;
otherwise match whatever session access the existing code uses.

## TDD Requirement

1. **RED**: Create `tests/integration/test_item_register_functional_doc.py` with parameterised cases:
   - Sibling `<ID>_Functional.md` exists → both columns populated.
   - Sibling file absent → both columns `None`; INSERT succeeds.
   - `--functional-doc PATH` override with existing file → columns populated from that path.
   - `--functional-doc PATH` override with missing file → command fails, no row inserted.
   - Sibling file empty → warning logged, columns set to empty string OR `None` (pick one consistent with `design_doc_content` empty-file handling and document the choice in the report).

   Create `tests/unit/test_backfill_functional_doc.py` with:
   - `--load-db` path mocks opencode to produce a file, asserts DB UPDATE occurs and columns are set.
   - `--load-db` with missing item → exit 4, no DB write.
   - `--load-db` with SQLAlchemy exception → exit 7.
   - Default (no `--load-db`) → no DB calls at all (mock `SessionLocal` and assert never called).

2. **GREEN**: implement `register` changes and the `--load-db` flag.
3. **REFACTOR**: ensure the opencode subprocess branch is unchanged on the default path.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass (new backfill tests).
2. `make test-integration` — pass (new register tests).
3. `make lint` and `make type-check` — pass.

## Subagent Result Contract

Standard JSON with `step: "S02"`, `agent: "backend-impl"`, `work_item: "F-00059"`.
