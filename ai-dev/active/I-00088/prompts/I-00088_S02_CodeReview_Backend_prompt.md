# I-00088_S02_CodeReview_Backend_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Same policy as the implementation step. You MUST NOT touch docker container,
volume, or network state. Read-only `docker ps` / `inspect` / `logs` is OK.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migrations. Read-only `alembic history / current / show`
is OK; everything else is off-limits in an agent context.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00088 --json`
- `ai-dev/active/I-00088/I-00088_Issue_Design.md` — Design document
- `ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md` — S01 report
- All files listed in S01's `files_changed` (expected: `orch/daemon/auto_merge_health.py`, `tests/unit/test_auto_merge_health.py`)

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_S02_CodeReview_report.md`

## Context

You are reviewing the backend fix that replaces the broken `step_executor.sh`
invocation in `orch/daemon/auto_merge_health.py::maybe_run_probe` with a
direct call to the configured runtime binary.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` in `I-00088_Issue_Design.md` — every criterion
  is a mandatory check.
- Read `## TDD Approach` — the named test files are
  `tests/unit/test_auto_merge_health.py` and
  `tests/integration/test_auto_merge_health_runtime.py`.
- S01 should touch `tests/unit/test_auto_merge_health.py` (one new RED→GREEN
  test) and leave the integration test for S03. Confirm this.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in S01's `files_changed`:

```bash
make lint
make format
```

Any NEW violation in the changed files (not present on `main` before this
step) is a **CRITICAL** finding with `"category": "conventions"`. Do NOT
auto-fix; only report.

## Review Checklist

### 1. Architecture Compliance

- Does the fix touch ONLY `orch/daemon/auto_merge_health.py` (plus one
  test addition in `tests/unit/test_auto_merge_health.py`)?
- Did the agent leave `executor/step_executor.sh` AND
  `executor/step_executor_lib.sh` untouched? If they modified either,
  raise a CRITICAL finding — the design explicitly excludes both.
- **Canonical pattern mirror**: does the new subprocess call mirror
  `orch/daemon/auto_merge.py:717-736`? Specifically:
  - `argv = ["bash", "<.../step_executor_lib.sh>", "auto_merge_resolve", resolved.cli_tool, resolved.model]`
  - `input=PROBE_PROMPT`, `text=True`, `capture_output=True`
  - `env={"WORKTREE_PATH": <some non-empty placeholder>, "PATH": os.environ.get("PATH", "<fallback>")}`
  If the agent shelled out directly to `opencode` / `claude` (i.e.,
  `argv[0] in {"opencode", "claude"}`) instead of going through the lib
  script, raise a **CRITICAL** finding — that breaks the probe-resolver
  parity property the design was explicitly redrafted to preserve.

### 2. Code Quality

- Are the `subprocess.run` argv elements all strings (no `Path` objects
  that might surprise on Windows / under `bash -c`)?
- Is the timeout cap (`max(15, interval // 4)`) preserved?
- Is exception handling preserved (`TimeoutExpired` → `error="timeout"`,
  generic `Exception` → `f"{type(exc).__name__}: {exc}"`)?
- Is `_EXECUTOR_PATH` renamed to `_EXECUTOR_DIR` (matching `auto_merge.py`'s
  naming) and still pointing at the `executor/` directory?
- Does the success check stay `returncode == 0 and "OK" in stdout`?

### 3. Event Metadata Contract (CRITICAL)

The aggregator (`orch/auto_merge_aggregator.py::get_health_summary`) and the
chip template (`dashboard/templates/fragments/auto_merge_status_chip.html`)
read these keys from `event_metadata`:

- `runtime_reachable: bool`
- `cli_tool: str`
- `model: str`
- `probe_duration_ms: int`
- `error: str | None`

If any key is missing, renamed, or has a different type, raise a CRITICAL
finding — the chip will silently misclassify health states.

### 4. Project Conventions

- Read `orch/CLAUDE.md`. The module uses `DaemonEvent(event_metadata=...)`
  (the Python attribute is `event_metadata`, not `metadata` — SQLAlchemy
  reserves `metadata` on declarative base subclasses).
- Imports must follow ruff's isort config (`from __future__ import annotations`
  at top, std-lib then third-party then local, etc.).

### 5. Security

- The subprocess argv MUST NOT be built from any user-controlled string.
  `cli_tool` and `model` come from `resolve_project_config`, which loads
  from `projects.toml` + per-project DB overrides; trace the path and
  confirm nothing originates from an HTTP request, header, or query param.
- If the implementation uses `shell=True` anywhere, raise a CRITICAL finding —
  the existing call shape passes argv as a list (`shell=False`) and that
  must be preserved.

### 5a. TDD RED Evidence

This is a Backend step, so TDD RED evidence is mandatory.

1. The S01 report's `tdd_red_evidence` field must record the test id and a
   1–3 line `AssertionError` snippet from running the new test against the
   pre-change code. Verify it is present and plausible.
2. Reason: would the new test (which asserts that argv contains
   `"step_executor_lib.sh"`, `"auto_merge_resolve"`, the resolved
   `cli_tool`, and the resolved `model` in that order) have failed against
   the pre-fix code? YES — pre-fix argv is
   `["/bin/bash", ".../step_executor.sh", "--step-type", "auto_merge_resolve", "--agent", <cli>, "--model", <model>]`,
   which points at `step_executor.sh` (not `step_executor_lib.sh`) and places
   `--agent` between `auto_merge_resolve` and `<cli_tool>`. If the agent's
   reasoning contradicts that, raise a HIGH finding.

### 6. Other Tests in the File

S01 deliberately leaves the *other* pre-existing tests in
`tests/unit/test_auto_merge_health.py` red because their `subprocess.run`
mock asserts on the now-incorrect shape. S01's report should call this out
under `notes`, and S03 is responsible for rewriting them. Confirm S01 did
not silently delete or "fix" those tests in a way that papers over the
intent. If S01 modified existing-test assertions beyond a minimal merge
to keep the file compiling, raise a MEDIUM_FIXABLE finding.

## Test Verification (NON-NEGOTIABLE)

Run **only**:

```bash
uv run pytest tests/unit/test_auto_merge_health.py -v
```

Record the results. Do NOT run `make test-unit` or `make test-integration` —
the QV gates own full-suite runs.

## Severity Levels

Standard scale (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).
`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00088",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<results from the targeted run>",
  "notes": ""
}
```
