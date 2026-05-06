# I-00071_S01_Backend_prompt

**Work Item**: I-00071 -- Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker
**Step**: S01
**Agent**: Backend

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
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live
orchestration DB. This item adds NO migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00071 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00071/I-00071_Issue_Design.md` -- Design document (read fully before coding)
- `orch/design_doc_parser.py` -- file to modify (Bug 1)
- `orch/daemon/scope_overlap.py` -- file to modify (Bug 2)
- `orch/batch_planner.py` -- file to modify (Bug 2 parity — keep `_is_test_path` in sync with `scope_overlap.is_test_path`)
- `tests/unit/test_design_doc_parser.py` -- existing parser tests for context
- `tests/unit/daemon/test_scope_overlap.py` -- existing scope-overlap tests for context

## Output Files

- `ai-dev/active/I-00071/reports/I-00071_S01_Backend_report.md` -- Step report

## Context

You are fixing two latent bugs in the F-00076 cross-batch scope-overlap gate:

1. **Backtick-wrapped paths** persist into `WorkItem.impacted_paths` because the bullet-list parser does not strip surrounding markdown code-span fences.
2. **Relative test paths** like `tests/foo.py` are not classified as test paths, because `_TEST_PATH_MARKERS` requires a leading slash (`/tests/`).

Read `ai-dev/active/I-00071/I-00071_Issue_Design.md` fully — Steps to Reproduce, Root Cause Analysis, and Acceptance Criteria — before touching any code.

Then read `CLAUDE.md` and `orch/CLAUDE.md` for project-specific patterns.

## Requirements

### 1. Strip surrounding markdown code-span backticks in `parse_impacted_paths`

In `orch/design_doc_parser.py`, modify `parse_impacted_paths` so that globs extracted from BOTH bullet lines AND fenced code blocks have any surrounding markdown code-span backticks removed before validation and storage.

A markdown code span is a string wrapped in single backticks: `` `foo/bar.py` ``. Some users write double backticks (`` `` `foo` `` ``) when the content itself contains a backtick — handle the common single-backtick case at minimum, and the double-backtick case if it falls out naturally from a clean implementation.

**Concrete behaviour**:

```python
content = """## Impacted Paths

- `dashboard/CLAUDE.md`
- `dashboard/static/clipboard.js`
"""
result = parse_impacted_paths(content)
assert result.paths == ["dashboard/CLAUDE.md", "dashboard/static/clipboard.js"]
```

Implementation hints (you may diverge if you have a cleaner design):

- Add a small helper, e.g. `_strip_code_span(s: str) -> str`, that returns `s` with surrounding `` ` `` removed when it both starts and ends with `` ` `` (and the inner content has no whitespace).
- Apply it in both the bullet-line branch (around line 84-90) and the fenced-code-block branch (around line 73-78), AFTER `strip()` and BEFORE `_validate_glob`.
- A bare path with no backticks must be unchanged: `parse_impacted_paths("- foo.py")` → `["foo.py"]`.
- A path that contains `` ` `` mid-string (not wrapping) should be left alone (and rejected by `_validate_glob` if it now violates a rule, which is acceptable).

### 2. Broaden `is_test_path` to recognise relative test paths

In `orch/daemon/scope_overlap.py`, change `is_test_path` so it returns `True` for paths whose **first path segment** is `tests`, `test`, or `__tests__` — in addition to the existing markers.

**Concrete behaviour**:

```python
assert is_test_path("tests/dashboard/test_x.py") is True
assert is_test_path("test/foo.py") is True
assert is_test_path("__tests__/bar.py") is True
# Existing cases continue to work
assert is_test_path("src/tests/foo.py") is True
assert is_test_path("conftest.py") is True
assert is_test_path("foo.test.ts") is True
# Non-test paths must remain non-test
assert is_test_path("testscript.sh") is False
assert is_test_path("test_data.json") is False
assert is_test_path("src/test_utils.py") is False
```

Implementation hint (you may diverge):

- The current substring approach with `_TEST_PATH_MARKERS` works fine if you also include the prefix forms `"tests/"`, `"test/"`, `"__tests__/"` — but ONLY when matched at the **start** of the string. A simple way: keep the substring tuple as-is, and add a separate check `glob.startswith(("tests/", "test/", "__tests__/"))`.
- Do NOT loosen the predicate so far that `test_data.json` becomes a "test path" — those are existing test cases that must continue returning False.
- **MANDATORY parity update**: `orch/batch_planner.py:_is_test_path` (line ~112) carries the IDENTICAL `_TEST_PATH_MARKERS` constant and has the SAME bug. You MUST update it in lock-step so the two functions stay in sync — the docstring of `scope_overlap.is_test_path` already says "Mirror orch/batch_planner.py:_is_test_path semantics". The two modules' constants and predicates must continue to behave identically after your fix. (Optional: if you prefer, factor the predicate into a single shared helper — but only if the diff stays small. Otherwise, duplicate the fix.)

### 3. Keep changes minimal — no refactors, no new abstractions

This is an incident fix. Do not:
- Rename `_TEST_PATH_MARKERS` or restructure `globs_intersect`.
- Refactor `parse_impacted_paths` into a different shape than it has today.
- Add unrelated normalization (e.g. trimming Unicode dashes).
- Add comments explaining what the code does — only add a brief comment if the WHY is non-obvious (e.g. "strip markdown code-span before validate — I-00071").

Match the existing code style; the modules are pure-function and have no external dependencies beyond stdlib.

### 4. Do NOT write reproduction tests in this step

Tests are S03's responsibility. Your job here is to write the fix code only.

You MAY add or update tiny inline assertions in your local exploration, but do NOT modify `tests/unit/test_design_doc_parser.py` or `tests/unit/daemon/test_scope_overlap.py` — those are owned by S03.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:

- Architecture patterns and layer boundaries (these files are pure helpers — no DB, no I/O)
- Coding conventions (ruff format / lint, mypy, sync SQLAlchemy elsewhere — not relevant here)
- The note that `DaemonEvent.metadata` is named `event_metadata` in Python (not relevant here, just be aware)

Follow all rules defined there exactly. When in doubt, match existing code in the modules you are editing.

## TDD Requirement

Per the iw-ai-core workflow, **S03 (Tests)** owns the RED phase tests. For S01:

1. Read the reproduction test bodies in `I-00071_Issue_Design.md` (Test to Reproduce section).
2. **Sanity-check your fix** by running those exact assertions in a quick local repl or scratch script — but do NOT commit those assertions. The committed reproduction test will be authored by S03 to its own coverage standard.
3. **GREEN goal**: when S03 runs `pytest tests/unit/test_design_doc_parser.py tests/unit/daemon/test_scope_overlap.py -v`, every test in those files passes — including the new I-00071 ones.

If you find a third bug along the way, raise it as a `notes` entry in your report — do NOT widen the fix scope.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report.

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the `preflight` object recording
the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — all tests must pass with zero failures.
2. Run `make lint` and `make type-check` — zero errors in the files you touched.
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures.
4. If tests fail, fix them before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00071",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/design_doc_parser.py",
    "orch/daemon/scope_overlap.py",
    "orch/batch_planner.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

The `files_changed` list above is the expected baseline. If you discover the parity update can be skipped (e.g. the existing logic was already correct), document why in `notes`.
