# CR-00091_S01_Backend_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Do not execute any docker container/volume/network management commands. Testcontainer fixtures in tests are exempt. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do not apply any migration to the live DB on port 5433. This step creates tooling scripts — it does not generate a migration file.

## Context

Read `CLAUDE.md` and `orch/CLAUDE.md` before starting.

This step implements the "generation side" of the PENDING sentinel: a helper script that rewrites a migration file's `down_revision` to the sentinel value, and a Makefile target that wraps `alembic revision --autogenerate` and calls the script immediately after.

**Design doc**: `ai-dev/active/CR-00091/CR-00091_CR_Design.md` — read AC1 and AC5 before writing code.

## TDD — Write Tests FIRST

Before implementing, write failing unit tests in `tests/unit/test_rewrite_down_revision.py`. Capture the RED run output (a real `AssertionError`, not an `ImportError`) in your step report under `tdd_red_evidence`. Then implement until GREEN.

Required test cases (all in `tests/unit/test_rewrite_down_revision.py`):

1. **test_rewrites_hex_down_revision** — given a migration file containing `down_revision = "76250ecb2593"`, calling the script rewrites it to `down_revision = "PENDING"`. The rest of the file (docstring, revision, upgrade/downgrade bodies) is unchanged.

2. **test_rewrites_none_down_revision** — given `down_revision = None` (first migration in chain), the script rewrites it to `down_revision = "PENDING"`.

3. **test_rewrites_typed_annotation_form** — given `down_revision: str | tuple[str, ...] | None = "abc123ef"` (with a type annotation before the `=`), the script rewrites only the value, preserving the annotation.

4. **test_idempotent_pending** — given a file already containing `down_revision = "PENDING"`, calling the script leaves it unchanged and exits 0 (AC5).

5. **test_no_down_revision_raises** — given a Python file with no `down_revision` line, the script exits with a non-zero code and prints an error to stderr.

6. **test_missing_file_raises** — given a path to a file that does not exist, the script exits with a non-zero code.

Use `tmp_path` (pytest built-in fixture) to create temporary migration files for all tests. Do NOT read from `orch/db/migrations/versions/` in unit tests.

## Deliverable 1: `scripts/rewrite_down_revision.py`

Create `scripts/rewrite_down_revision.py` as a standalone CLI script (no project imports — only stdlib).

**Behaviour**:
- Accepts exactly one positional argument: the path to a migration file.
- Reads the file contents.
- Uses a regex to find the `down_revision` line. The pattern must handle:
  - Plain form: `down_revision = "abc123"` or `down_revision = None`
  - Type-annotated form: `down_revision: str | tuple[str, ...] | None = "abc123"`
  - Existing sentinel: `down_revision = "PENDING"` (idempotent — rewrite to same value)
- Rewrites the value to `"PENDING"` (the string literal including quotes, not Python None).
- Writes the result back to the same file.
- Exits 0 on success.
- If no `down_revision` line is found, prints `"Error: no down_revision line found in <path>"` to stderr and exits 1.
- If the file does not exist, prints `"Error: file not found: <path>"` to stderr and exits 1.

**Regex guidance** — this pattern handles all forms:

```python
pattern = re.compile(
    r'^(down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*)(.+)$',
    re.MULTILINE,
)
```

Replace the matched group 2 with `'"PENDING"'`.

Make the script directly executable (`if __name__ == "__main__": sys.exit(main())`).

## Deliverable 2: `Makefile` — `migration-pending` target

Add the following target to `Makefile`, placed immediately after the existing `migration-check` target:

```makefile
migration-pending:
ifndef MSG
	$(error MSG is required. Usage: make migration-pending MSG="describe the change")
endif
	uv run alembic revision --autogenerate -m "$(MSG)"
	@ls -t orch/db/migrations/versions/*.py | grep -v __pycache__ | head -1 | \
		xargs uv run python scripts/rewrite_down_revision.py
	@echo "Migration generated with down_revision = PENDING (resolved at merge time by migration_rebase.py)"
```

The `ls -t` + `head -1` pattern reliably picks the just-generated file because Alembic writes it last. The `grep -v __pycache__` excludes compiled bytecode.

Do **not** modify any other Makefile targets in this step.

## Preflight before committing

Run `make lint` and `make format-check` on the changed files before finishing. Fix any issues found.

Run targeted tests only:
```bash
uv run pytest tests/unit/test_rewrite_down_revision.py -v
```

Report any failures; do not proceed if tests are red.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|blocked",
  "files_changed": [
    "scripts/rewrite_down_revision.py",
    "Makefile",
    "tests/unit/test_rewrite_down_revision.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok|skipped:no-typed-imports",
    "lint": "ok|fixed"
  },
  "tests_passed": true,
  "test_summary": "6/6 unit tests passed",
  "tdd_red_evidence": "<paste AssertionError snippet from RED run>",
  "blockers": [],
  "notes": ""
}
```
