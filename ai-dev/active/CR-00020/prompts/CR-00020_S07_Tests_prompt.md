# CR-00020_S07_Tests_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`. Testcontainers only (via existing pytest fixtures).

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — ACs are the test specification
- `ai-dev/active/CR-00020/reports/CR-00020_S01_Database_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S03_Backend_report.md`
- `ai-dev/active/CR-00020/reports/CR-00020_S05_API_report.md`
- `tests/CLAUDE.md` — critical test rules (testcontainer, no DB mocking, FTS DDL setup)
- `tests/conftest.py` — existing fixtures (`pg_engine`, `db_session`, `test_project`)
- `tests/unit/test_step_commands.py` — example of pure validation-helper test shape

## Output Files

- `tests/unit/test_evidences_ingest.py` — NEW, pure helper tests
- `tests/integration/test_evidences_cli.py` — NEW, `iw approve` / `iw step-done` testcontainer
- `tests/dashboard/test_evidences_db_source.py` — NEW, TestClient + testcontainer dashboard tests
- `ai-dev/active/CR-00020/reports/CR-00020_S07_Tests_report.md` — step report

## Context

Write the test suite that locks in every AC from the design doc. Tests must be:

- **No DB mocking** (integration + dashboard tiers use testcontainer)
- **Byte-identical assertions** — SHA256 or exact equality where content is checked
- **Deterministic** — no timing races, no dependency on external filesystem layout beyond `tmp_path`
- **Isolated** — each test builds its own work_items row and evidences; no global fixture pollution across tests

## Requirements

### 1. `tests/unit/test_evidences_ingest.py` — unit tier

Test `orch.evidences.ingest_phase_from_disk` directly. Use a real `Session` via the existing `pg_engine` + per-test transaction fixture (this is a unit test of a pure helper that needs a real DB for the upsert — it still qualifies as "unit" style under the existing convention, OR move to integration if the project draws the line there).

**If the project's convention is that unit tests never touch a DB at all**, split: test the non-DB parts (stat loop, oversize check ordering, file filtering) via a fake session recorder in `tests/unit/`, and put the upsert behavior in `tests/integration/`.

Required test cases:

- `test_ingests_regular_files_with_correct_metadata` — 2 files → 2 rows with right content_type, size_bytes, byte-identical content
- `test_missing_base_dir_returns_empty_result` — no exception, empty list
- `test_empty_base_dir_returns_empty_result` — dir exists, no files
- `test_skips_subdirectories` — `pre/subdir/img.png` not ingested
- `test_skips_non_regular_files` — symlinks-to-dirs, sockets, etc. (use `tmp_path` + `os.symlink`)
- `test_oversize_file_raises_before_any_insert` — 2 files (small + large). Assert zero rows inserted when the large one exceeds `max_bytes`.
- `test_idempotent_upsert_updates_content_keeps_id` — ingest twice; second pass has different content; assert row's `id` unchanged, `content` + `size_bytes` + `captured_at` updated.
- `test_step_id_null_for_pre_phase` — AC1 shape
- `test_step_id_populated_for_post_phase` — AC2 shape
- `test_mime_fallback_for_unknown_extension` — a file named `file.weirdext` gets `application/octet-stream`

### 2. `tests/integration/test_evidences_cli.py` — integration tier (testcontainer)

Uses the project's standard testcontainer session fixture (follow `tests/integration/test_cli_steps.py` for the pattern — Click's CliRunner or direct command invocation).

Required test cases (one per AC):

- **AC1 — `iw approve` ingests pre**:
  - Create a `WorkItem` in draft status + FS files at `<tmp>/ai-dev/active/<id>/evidences/pre/`
  - Invoke `iw approve <id>` with the CliRunner (point `-p` / working dir to tmp)
  - Assert: status flipped to approved, `work_item_evidences` has rows matching files, byte-identical content (`hashlib.sha256` check)

- **AC2 — `iw step-done` ingests post on browser_verification**:
  - Set up WorkItem + browser_verification step in_progress + FS files at post/
  - Invoke `iw step-done <id> --step <S> --report <path>`
  - Assert: step completed, rows inserted with `phase='post'`, `step_id=<S>`

- **AC3 — upsert idempotency**:
  - Ingest once, modify file content, ingest again
  - Assert: same UUID, updated content, `captured_at` advanced

- **AC4 — size limit**:
  - Create 2 files (one oversize). Invoke `iw approve`.
  - Assert: CLI exit code 1, stderr names the oversize file, zero rows in table, item still `draft`.

- **AC6 — no cascade on FK**:
  - Ingest evidences
  - Execute `DELETE FROM work_items WHERE project_id=... AND id=...` (raw SQL if ORM relationship cascade interferes)
  - Assert: `work_item_evidences` rows still exist, queryable by (project_id, item_id)

- **AC8 — missing/empty evidences dir**:
  - Item with NO `evidences/pre/` dir → `iw approve` succeeds, zero rows
  - Item with empty `evidences/pre/` dir → same

### 3. `tests/dashboard/test_evidences_db_source.py` — dashboard tier (TestClient + testcontainer)

Follow the existing dashboard test pattern (TestClient + `override_get_db` dependency).

Required test cases:

- **AC5 — dashboard serves from DB after FS deletion**:
  - Seed: ingest rows for item X (both phases). Do NOT create any FS directory for X.
  - `GET /project/{pid}/item/X/tab/evidences` → 200, HTML contains each filename
  - `GET /project/{pid}/item/X/evidence/pre/<filename>` → 200, bytes match DB row content, Content-Type matches DB row

- **AC7 — FS fallback for in-progress post**:
  - Seed: item Y in_progress with a BatchItem whose `worktree_info['path']` points to a `tmp_path` worktree. Write `evidences/post/V1.png` to that worktree path. No DB rows for Y.
  - `GET /project/{pid}/item/Y/tab/evidences` → 200, HTML lists V1.png under post
  - `GET /project/{pid}/item/Y/evidence/post/V1.png` → 200, bytes from FS

- **Pre-phase has no FS fallback**:
  - Seed: item Z with `evidences/pre/only_on_fs.png` on FS but no DB rows
  - `GET …/tab/evidences` → 200 but pre section is empty
  - `GET …/evidence/pre/only_on_fs.png` → 404

- **Path traversal still blocked on FS fallback**:
  - `GET /project/{pid}/item/Y/evidence/post/../../../etc/passwd` → 403

- **Content-Type fidelity**:
  - Ingest a `.yml` snapshot. Dashboard image route returns `Content-Type: text/yaml` (whatever the DB stored, not what mimetypes would re-guess).

### 4. Fixture helpers

Consider adding to `tests/fixtures/evidences.py`:

- `make_evidence_bytes(size: int) -> bytes` — deterministic content (e.g., `b'x' * size`) for SHA256 verifiability
- `seed_evidence_row(session, ...)` — helper to bypass the CLI for dashboard tests

## Project Conventions

- Test files: `test_<feature>.py`
- Test classes: `TestXxx:` grouping related cases
- Parametrize where it shortens (e.g., phase enum values)
- Use `tmp_path` for all filesystem scaffolding — never hard-code paths
- Integration + dashboard tiers: use the existing `pg_engine` fixture; remember `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all` (but the fixture already handles this)
- **NEVER** connect to port 5433 from tests
- **NEVER** mock the database in integration or dashboard tests

## TDD Requirement

Write tests that would FAIL on pre-CR-00020 code:

- AC5 test would hit the old FS scan and return empty — good, it fails pre-fix and passes post-fix
- AC6 test would fail if FK had cascade — good, catches a schema regression

## Test Verification (NON-NEGOTIABLE)

1. All new tests pass: `make test-unit` + `make test-integration` + `uv run pytest tests/dashboard/test_evidences_db_source.py -v`
2. No existing tests regress: full `make check` is clean for tests (quality gates are S10-S14's job)
3. Report accurate counts in the JSON contract

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_evidences_ingest.py",
    "tests/integration/test_evidences_cli.py",
    "tests/dashboard/test_evidences_db_source.py"
  ],
  "tests_passed": true,
  "test_summary": "unit N added, integration M added, dashboard K added — all pass",
  "blockers": [],
  "notes": ""
}
```
