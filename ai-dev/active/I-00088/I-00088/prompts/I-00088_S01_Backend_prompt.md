# I-00088_S01_Backend_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Step**: S01
**Agent**: Backend (`backend-impl`)

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

This step adds NO migrations. If you find yourself reaching for `alembic`,
STOP and raise a blocker — the design is wrong.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00088 --json`
- `ai-dev/active/I-00088/I-00088_Issue_Design.md` — Design document (READ THIS FIRST)
- `orch/daemon/auto_merge_health.py` — file you will modify
- `orch/daemon/auto_merge.py` — **canonical reference pattern** (see lines 717-736, `invoke_llm_for_file`); also defines `AutoMergeConfig` and `EVENT_AUTO_MERGE_HEALTH_PROBE`
- `executor/step_executor.sh` — current (buggy) call target, for context only — DO NOT MODIFY
- `executor/step_executor_lib.sh` — **new call target**; specifically lines 608-628 (`_run_agent_oneshot`) and 635-652 (direct-dispatch block exposing `auto_merge_resolve <agent> <model>`). DO NOT MODIFY.
- `tests/unit/test_auto_merge_health.py` — existing tests for context; the Tests step (S03) will rewrite the relevant assertions, not you

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md` — Step report

## Context

The auto-merge health probe in `orch/daemon/auto_merge_health.py:46-66` invokes
`executor/step_executor.sh` with flag-style arguments (`--step-type`, `--agent`,
`--model`), but the executor reads positional arguments. Every probe fails at
the executor with `ERROR: Worktree not found or invalid: --agent` and records
`runtime_reachable=false`. The chip in the dashboard reads `● down`
permanently.

This step replaces the bogus `step_executor.sh` invocation with the **canonical
one-shot dispatch** that the real auto-merge resolver already uses: invoke
`bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>`. The lib
script's `_run_agent_oneshot` reads the prompt from stdin and shells out to
the configured runtime (`claude --print --model <m>` or
`opencode run -p <m>`), echoing the runtime's stdout back. See
`orch/daemon/auto_merge.py:717-736` for the canonical caller pattern — your
implementation MUST mirror it, with two narrow deviations documented in the
design doc's `## Notes` (the probe inherits `PATH` from the parent and uses
a placeholder `WORKTREE_PATH`).

## Requirements

### 1. Replace the subprocess call in `maybe_run_probe`

Inside `orch/daemon/auto_merge_health.py::maybe_run_probe`, replace the
existing `subprocess.run([..., "step_executor.sh", "--step-type", ...])`
invocation with a call that mirrors `orch/daemon/auto_merge.py:717-736`:

```python
result = subprocess.run(  # noqa: S603
    [  # noqa: S607
        "bash",
        str(_EXECUTOR_DIR / "step_executor_lib.sh"),
        "auto_merge_resolve",
        resolved.cli_tool,
        resolved.model,
    ],
    input=PROBE_PROMPT,
    text=True,
    capture_output=True,
    timeout=max(15, toml_config.health_probe_interval_seconds // 4),
    env={
        "WORKTREE_PATH": str(_EXECUTOR_DIR),   # placeholder; _run_agent_oneshot doesn't use it,
                                               # but the lib script's top-level guard requires it
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
    },
)
```

- Rename the module-level `_EXECUTOR_PATH` to `_EXECUTOR_DIR` for clarity and
  consistency with `auto_merge.py` (which uses `_EXECUTOR_DIR`). Keep its
  computed value (`Path(__file__).resolve().parent.parent.parent / "executor"`).
- The success check stays `result.returncode == 0 and "OK" in result.stdout`.

**Do NOT** shell out directly to `opencode` / `claude`. The fix's central
property is that the probe and the resolver share the same call path so they
can never drift; bypassing the lib script breaks that property. If you find
yourself reaching for `subprocess.run(["opencode", ...])` or
`subprocess.run(["claude", ...])`, STOP and re-read the design's `## Notes`
section.

### 2. Preserve the event metadata contract

The `daemon_events` row written by the probe MUST keep the same shape so
`orch/auto_merge_aggregator.py::get_health_summary` and the chip template
continue to work unchanged:

```python
event_metadata = {
    "runtime_reachable": bool,
    "cli_tool": str,           # resolved cli_tool
    "model": str,              # resolved model
    "probe_duration_ms": int,
    "error": str | None,       # None on success
}
```

The reachability check stays the same: `result.returncode == 0 and "OK" in result.stdout`.

### 3. Preserve the timeout, skip-if-recent, and skip-if-phase-0 behaviour

- The `interval` guard at `auto_merge_health.py:38-41` (skip if a probe ran
  within `health_probe_interval_seconds`) must be kept.
- The phase-0 guard at `auto_merge_health.py:27-28` must be kept.
- The subprocess timeout cap (`max(15, toml_config.health_probe_interval_seconds // 4)`)
  must be kept — the probe is best-effort and must never block the daemon loop.
- The exception handling (`subprocess.TimeoutExpired` → `error="timeout"`,
  generic `Exception` → `error=f"{type(exc).__name__}: {exc}"`) must be kept.

### 4. Keep (and rename) `_EXECUTOR_PATH`

The module-level `_EXECUTOR_PATH = Path(__file__).resolve().parent.parent.parent / "executor"`
is still needed (it points at the `executor/` directory that contains
`step_executor_lib.sh`). Rename it to `_EXECUTOR_DIR` for consistency with
`orch/daemon/auto_merge.py`. Keep `PROBE_PROMPT` unchanged.

Add `import os` at the top of the module if it isn't already imported — the
env dict needs `os.environ.get("PATH", ...)`.

### 5. Do NOT change `executor/step_executor.sh` or `executor/step_executor_lib.sh`

This fix deliberately keeps both executor scripts untouched. The `auto_merge_resolve`
direct-dispatch already exists in `step_executor_lib.sh:635-652` (added in F-00084)
and is the same code path the real resolver uses. Scope-stick: only
`orch/daemon/auto_merge_health.py` changes.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md`. In particular:

- `orch/` uses SQLAlchemy 2.0 sync, psycopg v3, Click 8.1+. Match the existing
  style of the module you're editing.
- `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves
  `metadata`).
- Never connect tests to the live DB; the existing unit tests use a `MagicMock`
  for the `db` session.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Before you change `auto_merge_health.py`, add a single targeted
   unit test in `tests/unit/test_auto_merge_health.py` that asserts the
   command list passed to `subprocess.run` contains `"step_executor_lib.sh"`,
   `"auto_merge_resolve"`, the resolved `cli_tool`, AND the resolved `model`
   in that order. Run **only that test file**:
   ```bash
   uv run pytest tests/unit/test_auto_merge_health.py -v
   ```
   Confirm the new test FAILS for the right reason (`AssertionError` —
   today the argv is `["/bin/bash", ".../step_executor.sh", "--step-type",
   "auto_merge_resolve", "--agent", <cli_tool>, "--model", <model>]`,
   which contains `auto_merge_resolve` but in the wrong position and
   points at the wrong script).
   Capture the failure line(s) for `tdd_red_evidence`.
2. **GREEN**: Implement the fix. Re-run the same test file; the new test
   must pass. The remaining existing tests in that file may break — that
   is expected and is S03's job to fix. Document which existing tests now
   fail and why, but do not "patch" them yourself; leave them red for S03.
3. **REFACTOR**: Clean up imports (`_EXECUTOR_PATH` is now dead). Re-run
   the new test file.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run and fix any issues from:

1. `make format` — auto-fixes formatting drift. Re-stage if files change.
2. `make typecheck` — must report zero errors involving the files you touched.
3. `make lint` — must report zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — **DO NOT run the full
test suite**:

- Run only the file you touched:
  ```bash
  uv run pytest tests/unit/test_auto_merge_health.py -v
  ```
- The new RED→GREEN test you authored must pass. Other tests in that file
  may fail (they were written against the old subprocess shape and will be
  rewritten by S03). Note this clearly in `notes`.
- Run lint + typecheck on the touched file (`orch/daemon/auto_merge_health.py`).

## Migration Verification

N/A — no migrations.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00088",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/auto_merge_health.py",
    "tests/unit/test_auto_merge_health.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "1 new passed, N existing now failing (will be rewritten in S03)",
  "tdd_red_evidence": "tests/unit/test_auto_merge_health.py::<new test> — AssertionError: ... (RED snippet)",
  "blockers": [],
  "notes": "Existing mocked-subprocess tests now red because subprocess shape changed; S03 (Tests) rewrites them."
}
```
