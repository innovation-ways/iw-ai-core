# CR-00087_S01_BackendImpl_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
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

This step adds NO migration. Do not run alembic commands against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00087 --json` for current step list and prompt paths.
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document (read this first).
- `orch/daemon/project_registry.py` — file to modify.
- `tests/unit/daemon/test_project_registry_overlap_gate.py` — read this for the per-concern test-file pattern the new tests must follow.
- `tests/unit/daemon/test_project_registry_auto_amend_scope.py` — NEW file where the new parsing unit tests go.

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S01_BackendImpl_report.md` — Step report

## Context

You are implementing **Step 1** of CR-00087. This step adds a new optional `auto_amend_scope` block to the project's `.iw-orch.json` schema, parses it in `orch/daemon/project_registry.py`, and stores the result on `ProjectConfig` so that S03 can consume it from the daemon's fix-cycle path.

Read the design doc first (especially the **Desired Behavior** and **Acceptance Criteria** sections). Then read `CLAUDE.md` (root + `orch/CLAUDE.md`) for project-specific patterns and conventions.

## Requirements

### 1. Add two fields to `ProjectConfig` (orch/daemon/project_registry.py)

Add to the `@dataclass class ProjectConfig` block (somewhere after the existing `overlap_block_patterns` / `overlap_allow_patterns` fields so related per-project policy lives together):

```python
# Per-project auto-amend policy for scope violations. When auto_amend_allow_patterns
# is non-empty, the daemon will auto-run amend_allowed_paths() inside _complete_fix_cycle
# if every violated path matches one of the patterns and the count stays within
# auto_amend_max_paths (when set). Empty list means the feature is off (default).
# auto_amend_max_paths = None means no count cap.
auto_amend_allow_patterns: list[str] = field(default_factory=list)
auto_amend_max_paths: int | None = None
```

### 2. Add a parser helper `_parse_auto_amend_scope` (orch/daemon/project_registry.py)

Mirror the shape of the existing `_parse_overlap_gate` helper (look at it carefully — same defensive logging style, same fallback-to-defaults on malformed input). Signature:

```python
def _parse_auto_amend_scope(
    project_id: str, raw: object
) -> tuple[list[str], int | None]:
    """Parse the optional auto_amend_scope block from .iw-orch.json.

    Returns (auto_allow_patterns, max_paths).
    On any malformed input, returns ([], None) and logs a WARNING.
    """
```

Rules (mirror these exactly):
- `raw is None` → return `([], None)` silently (field is optional).
- `raw` not a dict → log WARNING and return `([], None)`.
- `raw["auto_allow_patterns"]` missing → return `([], None)`.
- `raw["auto_allow_patterns"]` not a list → log WARNING and return `([], None)`.
- For each entry in `auto_allow_patterns`: if it is not a `str`, log WARNING (mention the entry's value), drop it. The final list contains only valid `str` entries; if no entries survive validation, return `([], None)`.
- `raw["max_paths"]` missing → max_paths is `None`.
- `raw["max_paths"]` not an `int` (and not a `bool` — bool is an `int` subtype in Python; explicitly reject `bool` here so `True`/`False` don't get coerced to 1/0) → log WARNING and treat as `None`.
- `raw["max_paths"] < 0` → log WARNING and treat as `None` (negative cap makes no sense).

### 3. Call `_parse_auto_amend_scope` in `_build_project_config`

Inside `_build_project_config`, after the existing `_parse_overlap_gate` call (~line 194), add:

```python
auto_amend_allow_patterns, auto_amend_max_paths = _parse_auto_amend_scope(
    project_id, iw_config.get("auto_amend_scope")
)
```

Then wire them into the `ProjectConfig(...)` constructor call further down (alphabetical with the other new fields, or grouped with the overlap_* fields — match the existing style).

### 4. Unit tests (tests/unit/daemon/test_project_registry_auto_amend_scope.py — NEW FILE)

Following **TDD (Red-Green-Refactor)**. Write the tests FIRST and confirm RED before implementing.

The project uses per-concern test files under `tests/unit/daemon/` (see `test_project_registry_overlap_gate.py`, `test_project_registry_ai_assistant.py`). Create a NEW file `tests/unit/daemon/test_project_registry_auto_amend_scope.py` and match the existing fixture style from `test_project_registry_overlap_gate.py` exactly. Do NOT add tests to `tests/unit/test_project_registry.py` — that is a separate top-level unit test file with its own scope.

Add tests covering:

- `auto_amend_scope` absent from `.iw-orch.json` → `ProjectConfig.auto_amend_allow_patterns == []` and `auto_amend_max_paths is None` (no WARNING log).
- Valid block with both fields → both fields populated correctly.
- Valid block with `auto_allow_patterns` only → patterns populated, `max_paths is None`.
- Malformed: `auto_amend_scope` is a list (not a dict) → defaults + WARNING logged.
- Malformed: `auto_allow_patterns` contains a non-string entry mixed with strings → only string entries are kept, WARNING for the bad entry.
- Malformed: `auto_allow_patterns` is a string (not a list) → defaults + WARNING logged.
- Malformed: `max_paths` is a string `"10"` → patterns populated, `max_paths is None`, WARNING logged.
- Malformed: `max_paths` is a bool `True` → patterns populated, `max_paths is None`, WARNING logged (explicitly verify bool rejection).
- Malformed: `max_paths` is `-1` → patterns populated, `max_paths is None`, WARNING logged.

Use the **same test fixtures and project-registry-loading helpers** that `test_project_registry_overlap_gate.py` uses (a `tmp_path` + `_write_iw_orch_json(...)` style — read that file first). Do NOT create a new fixture style.

**RED capture**: pick the first test (e.g. `test_auto_amend_scope_absent_uses_defaults`), implement only the test, and run it via `uv run pytest tests/unit/daemon/test_project_registry_auto_amend_scope.py::<test_name> -v`. Confirm it fails with `AttributeError` (the dataclass field doesn't exist yet) or `AssertionError` (default doesn't match expected). Capture the test id and the first 2-3 lines of failure output. Record these in your `tdd_red_evidence` field.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries (`orch/CLAUDE.md` covers the daemon registry).
- Coding conventions and naming rules.
- Framework-specific patterns (SQLAlchemy 2.0, Click 8.1, etc.).
- Test organization and fixtures (`tests/CLAUDE.md`).
- Build and run commands.

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior.
   Run the new failing test targeted (not the full suite).
   Confirm the failure is for the expected reason (AssertionError / AttributeError from missing implementation).
2. **GREEN**: Write the minimal implementation to make tests pass.
3. **REFACTOR**: Improve code structure while keeping all tests green.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report. Skipping any of these wastes a fix-cycle slot
when the QV gate steps catch the same issue downstream.

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command.

## Test Verification (NON-NEGOTIABLE)

After implementation, run only the new test file(s) you touched:

```bash
uv run pytest tests/unit/daemon/test_project_registry_auto_amend_scope.py -v
```

Do NOT run the full unit suite or `make test-integration` — those are S10 / S11 QV gates with their own budgets.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/project_registry.py",
    "tests/unit/daemon/test_project_registry_auto_amend_scope.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/daemon/test_project_registry_auto_amend_scope.py::test_auto_amend_scope_absent_uses_defaults — AttributeError: 'ProjectConfig' object has no attribute 'auto_amend_allow_patterns'",
  "blockers": [],
  "notes": ""
}
```
