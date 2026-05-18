# CR-00062_S03_Pipeline_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S03
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures in tests are the only exception. Read-only `docker ps / inspect / logs` is allowed. No `docker compose up/down/restart`, no container `kill/stop/rm`, no `volume rm / prune`, no `system / container / image prune`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are NOT touching migrations in this step. Do NOT run any `alembic upgrade / downgrade / stamp` command. S01 owns the migration; you consume its schema via testcontainers in your test runs.

## Input Files

- Runtime step state: `uv run iw item-status CR-00062 --json`
- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- S01 report (after it completes): `ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md`
- Eight dispatch sites listed in the design's *Current Behavior* section:
  - `executor/step_executor.sh:130`
  - `executor/step_executor_lib.sh:616` (`_run_agent_oneshot`)
  - `orch/daemon/batch_manager.py:1466`
  - `orch/daemon/fix_cycle.py:2206-2230` (`_build_fix_launch_argv`)
  - `orch/daemon/fix_cycle.py:2286` (fix inner command)
  - `orch/daemon/doc_job_poller.py:298` (`_build_agent_command`)
  - `orch/doc_service.py:573`
  - `orch/daemon/project_registry.py:155` (cli_tool resolution — needs allowlist)

## Output Files

- Edits to all eight files above
- `ai-dev/active/CR-00062/reports/CR-00062_S03_Pipeline_report.md`

## Context

You are implementing S03 of CR-00062 — wiring the `pi` branch into every dispatch site that today branches on `cli_tool ∈ {opencode, claude}`. Read the design doc's *Desired Behavior* + *Affected Components* table for the exact argv shapes and the *Acceptance Criteria* AC1 + AC4 for the assertions your work must satisfy.

## Requirements

### 1. Bash executor — step launch (`executor/step_executor.sh:130`)

Add a third arm to the `if/elif/else` block. The `pi` branch:

- Sets `TMPDIR="$WORKTREE_PATH/.tmp"` (same as the claude branch — no XDG isolation needed; Pi stores sessions under `~/.pi/agent/sessions/` and does not need per-item PATH isolation).
- Invokes `setsid timeout "$TIMEOUT" pi -p "$INSTRUCTION" --model "$MODEL" < /dev/null >> "$STEP_LOG" 2>&1 || EXIT_CODE=$?`
- The `--model` flag value should come from the `$MODEL` env var (already set higher up in the script from the resolved runtime option). If `$MODEL` is empty, fall back to a documented Pi default (`anthropic/claude-sonnet-4-6` per R-00072) and log a warning via `_lib_log`.

The existing `else` branch's error message currently reads `"Unknown CLI tool: $CLI_TOOL (expected 'opencode' or 'claude')"`. Update it to `"Unknown CLI tool: $CLI_TOOL (expected 'opencode', 'claude', or 'pi')"`.

### 2. Bash executor — auto-merge one-shot (`executor/step_executor_lib.sh:616`)

Add a `pi)` case to the `_run_agent_oneshot` case-statement matching the claude/opencode pattern:

```bash
pi)
    echo "$prompt" | pi -p --model "$model"
    ;;
```

(`pi -p` without an inline prompt argument reads from stdin per Pi's documented print-mode contract — verify with `pi --help | grep -A2 'print'`.)

The `*)` default case's error message currently reads `"ERROR: unknown agent: $agent"`; leave it as-is (it doesn't enumerate runtimes, so no update needed).

### 3. Daemon — initial step argv (`orch/daemon/batch_manager.py:1466`)

Add a third branch to the `if resolved_cli_tool == "opencode" ... else ...` block. The `pi` branch builds:

```
pi -p "$(cat {prompt_file})" --model {resolved_model}
```

Mirror the existing string-formatting style; pass `prompt_file` and `resolved_model` through the same way the opencode branch does.

### 4. Daemon — fix-launch argv wrapper (`orch/daemon/fix_cycle.py:2206-2230` `_build_fix_launch_argv`)

**No change to logic; verify by reading the function.** The function returns `["script", "-qec", inner_command, "/dev/null"]` only when `cli_tool == "opencode"` (PTY wrapper for opencode's TTY requirement) and `["/bin/sh", "-c", inner_command]` for everything else. `pi` does NOT need a PTY wrapper — its print mode works under non-TTY stdout (this is documented in R-00072 §1). So `pi` correctly falls through to the `/bin/sh -c` arm by default.

**Action**: add a comment line right above the `if cli_tool == "opencode":` line explaining that pi (and claude) use the unwrapped `/bin/sh -c` form, so a reader doesn't think pi support is missing.

### 5. Daemon — fix-cycle inner command (`orch/daemon/fix_cycle.py:2286`)

Add a `pi` branch to the inner-command builder mirroring the opencode/claude shapes. Format:

```
pi -p "$(cat {prompt_file})" --model {resolved_model}
```

### 6. Daemon — doc-job command (`orch/daemon/doc_job_poller.py:298`)

Replace the current `if/else` two-arm structure with a three-arm if/elif/else, ending the chain with an explicit `else: raise ValueError(f"Unknown cli_tool: {cli_tool!r}")` so a typo doesn't silently produce a bare-command launch. The `pi` arm:

```python
cmd = f'pi -p "/{skill} doc-job {job.id}"'
```

(No `--dangerously-skip-permissions` or `--permission-mode bypassPermissions` flag — Pi's permission model is extension-based, not a CLI flag. See R-00072 §7.)

### 7. Service — doc service (`orch/doc_service.py:573`)

Same shape as step 6 above — extend the if/elif/else to three arms with an explicit `else: raise ValueError(...)`. The `pi` arm builds a `pi -p ...` command matching the existing claude/opencode structure for `doc_service`'s context (use the surrounding code's prompt-string format verbatim — do not improvise).

### 8. Project registry allowlist (`orch/daemon/project_registry.py:155`)

After the line `cli_tool: str = entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")`, add an allowlist check:

```python
_VALID_CLI_TOOLS = {"opencode", "claude", "pi"}
if cli_tool not in _VALID_CLI_TOOLS:
    logger.warning(
        "Project %r has invalid cli_tool %r (expected one of %s) — skipping",
        project_id,
        cli_tool,
        sorted(_VALID_CLI_TOOLS),
    )
    return None
```

Place `_VALID_CLI_TOOLS` as a module-level constant near the top of the file (after imports) so it's reusable by future code. The `return None` causes the loader to skip the project, matching the existing skip patterns at lines 141 and 145 (`logger.warning(...) — skipping`; `return None`).

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md` (daemon module map, Technology Stack), `executor/CLAUDE.md` (no docker / no alembic in executor scripts).

## TDD Requirement

**`tdd_red_evidence` (Pipeline step)** — write a targeted unit test before each implementation that asserts the new branch's argv. Capture the failing run:

Example for batch_manager:

```bash
uv run pytest tests/unit/test_pi_runtime_dispatch.py::test_batch_manager_pi_argv -v
```

Expected RED output: `AssertionError: assert "pi -p" in cmd` (because today the dispatch falls through to claude, producing `claude -p`). Capture the failure line into `tdd_red_evidence`. Then implement the branch and re-run for GREEN.

If you cannot land RED before GREEN for a particular site (e.g., for the bash scripts where unit-testing is harder), note `"n/a — bash dispatch site verified by S05 integration test against stub `pi` binary"` for that site, but at least ONE site in this step MUST have captured RED→GREEN evidence (the batch_manager site is the easiest).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

Record in `preflight` per the standard contract.

## Test Verification (NON-NEGOTIABLE)

Run targeted unit tests for files you touched:

```bash
uv run pytest tests/unit/test_pi_runtime_dispatch.py -v
```

Do NOT run the full unit or integration suite. Those are S12/S13 QV gates.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "pipeline-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "executor/step_executor.sh",
    "executor/step_executor_lib.sh",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "orch/daemon/doc_job_poller.py",
    "orch/doc_service.py",
    "orch/daemon/project_registry.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "<test id> — <failing assertion line>",
  "blockers": [],
  "notes": "any divergence from documented argv shapes; any Pi-CLI-help findings (e.g., if `pi -p` requires a prompt arg vs stdin)"
}
```
