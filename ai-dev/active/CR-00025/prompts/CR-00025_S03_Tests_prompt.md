# CR-00025 S03 — Tests: ingest helper + lifecycle integration + post-archive regression

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same constraints as S01 — see prompt for full text. Testcontainers spun up
by pytest fixtures are allowed; no manual `docker compose` commands.

## Input Files

- `uv run iw item-status CR-00025 --json`
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md` — read AC1–AC5 carefully
- `ai-dev/active/CR-00025/reports/CR-00025_S01_Backend_report.md`
- `ai-dev/active/CR-00025/reports/CR-00025_S02_CodeReview_Backend_report.md`
- `orch/evidences.py` (created in S01)
- `orch/cli/item_commands.py` (modified in S01)
- `orch/cli/step_commands.py` (modified in S01)
- `orch/archive/archiver.py` — for the regression test
- `dashboard/routers/items.py:_list_evidences` — for the regression test
- `tests/conftest.py` — for fixtures (`db_session`, project + work_item factories, `cli_runner`)
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL, no DB mocking
- `tests/integration/test_work_item_evidence.py` — existing model-level tests (DO NOT modify; add to a new file)

## Output Files

- `tests/unit/test_evidences_ingest.py` — new
- `tests/integration/test_evidences_lifecycle.py` — new
- `ai-dev/active/CR-00025/reports/CR-00025_S03_Tests_report.md`

## Context

You are writing tests for the new ingestion pipeline. The most important
test in this step is the **post-archive regression test** — the one that
the original CR-00020 S15 qv-browser step was supposed to perform but
missed, allowing the table to ship empty in production.

## Requirements

### 1. Unit tests — `tests/unit/test_evidences_ingest.py`

Use the existing testcontainer fixture (`db_session` or equivalent). Do
**not** mock the database — `tests/CLAUDE.md` forbids mocking integration
DB calls, and ON CONFLICT can't be tested without a real Postgres.

Cases:

- **Happy path**: write 2 PNG + 1 YAML to a temp dir under
  `<tmp>/ai-dev/active/X-99999/evidences/pre/`, call
  `ingest_phase_from_disk(...)`, assert returned count == 3, assert
  3 rows exist with correct `content_type` (`image/png`, `application/yaml`),
  assert `size_bytes` matches `Path.stat().st_size`, assert SHA256 of
  `row.content` matches SHA256 of file bytes.
- **Empty dir**: dir exists but contains no files — return 0, no rows.
- **Missing dir**: dir does not exist — return 0, no rows, no exception.
- **Non-file entries**: dir contains a subdir and a symlink to a file —
  both ignored, return 0, no rows.
- **Oversize hard-fail**: file size = `max_bytes + 1`. Assert
  `EvidenceTooLargeError` is raised. Assert the session is **not**
  committed (no rows inserted; if you assert by querying after a rollback,
  use `session.rollback()` explicitly between the raise and the query).
  Assert the exception's `filename`, `size`, and `max_bytes` attributes.
- **Idempotent upsert (AC3)**: ingest a file with content A, then
  overwrite the file with content B (different bytes, different size),
  ingest again. Assert exactly 1 row exists for that filename, assert
  `row.content == B`, `row.size_bytes == len(B)`. Verify `step_id` is
  also updated when you pass a new `step_id` on the second call.
- **Unknown extension**: file `weird.xyz` — `content_type` defaults to
  `application/octet-stream`.
- **YAML extension MIME**: file `evidence.yaml` and `evidence.yml` —
  `content_type` is `application/yaml` (verify the `mimetypes.add_type`
  registration in `orch/evidences.py` works).
- **`max_bytes` parameter overrides config**: passing `max_bytes=100`
  overrides `IW_CORE_EVIDENCE_MAX_BYTES`.

### 2. Integration tests — `tests/integration/test_evidences_lifecycle.py`

Use Click's `CliRunner` against the real `iw` command group, real
testcontainer DB. Use the existing `cli_runner` / `cli_invoke` fixture
if it exists; otherwise build a minimal one matching the pattern in
other integration tests under `tests/integration/`.

Cases:

- **AC1 — `iw approve` ingests pre evidences**: register a work item,
  set up `ai-dev/active/X-99999/evidences/pre/{a.png,b.yaml}` in a
  tmp_path-anchored repo root, run `iw approve X-99999`. Assert exit
  code 0, assert work item status == `approved`, assert 2 rows in
  `work_item_evidences` with phase `pre`, step_id NULL,
  byte-identical content.
- **AC2 positive — `iw step-done` for browser_verification ingests
  post**: register work item with a single browser_verification step,
  start it, drop a screenshot in `evidences/post/`, run `iw step-done
  X-99999 --step S01`. Assert step.status == `completed`, assert 1 row
  with phase `post`, step_id `S01`.
- **AC2 negative — `iw step-done` for non-browser steps does NOT
  ingest**: same setup but step_type is `implementation`. Drop files in
  `evidences/post/` (not normally there, but the test forces it). Run
  `iw step-done`. Assert 0 rows in `work_item_evidences`.
- **AC4 — oversize rolls back the status flip**: set
  `IW_CORE_EVIDENCE_MAX_BYTES=100` via `monkeypatch.setenv`, place a
  201-byte file in `evidences/pre/`, run `iw approve`. Assert non-zero
  exit code, assert work item status remains `draft`, assert 0 rows in
  `work_item_evidences`.
- **AC5 — post-archive visibility (THE regression test)**:
  1. Register a work item, drop pre and post files in active dir,
     `iw approve`, mark a browser_verification step done so post is
     ingested too.
  2. Mark the work item completed (status=`completed`) so the
     archiver will accept it.
  3. Call `archive_work_item(db, project_id, item_id, archive_dir,
     cleanup=True)` from `orch.archive`. Assert
     `ai-dev/active/X-99999/` no longer exists.
  4. Call `_list_evidences(item, project, db, worktree_path=None)` from
     `dashboard.routers.items`. Assert the returned list contains all
     pre and post `EvidenceFile` objects.
  5. Call `item_evidence_file(...)` (or test the underlying DB query
     it uses) to fetch each filename and assert byte-identical content.

   This test is the regression guard. If it ever starts failing, the
   ingestion pipeline has regressed and the bug from CR-00020 has
   reopened. Add a clear comment in the test docstring saying so.

### 3. Conventions

- `tests/CLAUDE.md` — read before writing. Critical rules:
  - Use the testcontainer fixture; never connect to live DB on 5433.
  - No `importlib.reload(orch.config)` — use `monkeypatch.delenv` /
    `monkeypatch.setenv` instead.
  - Replace psycopg2 URLs with `postgresql+psycopg://` (the fixture
    likely already does this).
  - Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
    `Base.metadata.create_all()` if your test creates a fresh DB.
- File naming: `tests/unit/test_evidences_ingest.py`,
  `tests/integration/test_evidences_lifecycle.py`. Match snake_case
  test function names with descriptive prefixes (`test_ingest_*`,
  `test_lifecycle_*`).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fix.
2. `make typecheck` — zero errors in your new files.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — your new unit tests must pass.
2. `make test-integration` — your new integration tests must pass.
3. Do **NOT** report `tests_passed: true` unless every test passes.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "CR-00025",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_evidences_ingest.py",
    "tests/integration/test_evidences_lifecycle.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
