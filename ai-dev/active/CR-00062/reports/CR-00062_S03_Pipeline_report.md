# CR-00062 — S03 Pipeline Report

## What was done

Wired `cli_tool = "pi"` into every runtime-specific dispatch site listed in
the design doc's *Current Behavior* section, plus a code-only allowlist in
`project_registry.py` that rejects typos like `"pii"` or `"piE"` before they
reach the dispatcher. Two small builders were extracted alongside the
existing `_build_fix_launch_argv` helper so the per-runtime argv shape is
unit-testable (and so a future drift between the initial-step launcher and
the fix-cycle launcher — the exact mode of failure I-00074 — can be caught
by a unit test instead of in production):

- `orch.daemon.batch_manager._build_initial_command(cli_tool, prompt_file, resolved_model, agent_args)`
- `orch.daemon.fix_cycle._build_fix_inner_command(cli_tool, prompt_path, resolved_model)`

Both builders end the cli_tool chain with an explicit
`raise ValueError(f"Unknown cli_tool: {cli_tool!r}")` so a typo doesn't
silently land in the claude branch. `doc_job_poller._build_agent_command`
and `doc_service.complete_doc_job` were converted from two-arm `if/else`
to three-arm `if/elif/elif/else` with the same explicit raise.

## Pi-branch argv shapes

| Site | Argv |
|------|------|
| `step_executor.sh` (manual step launch) | `setsid timeout "$TIMEOUT" pi -p "$INSTRUCTION" --model "$MODEL"` |
| `step_executor_lib.sh _run_agent_oneshot` (F-00084 auto-merge dry-run) | `echo "$prompt" \| pi -p --model "$model"` (prompt on stdin) |
| `batch_manager._build_initial_command` (initial step launch) | `pi -p "$(cat {prompt_file})" --model {resolved_model}` |
| `fix_cycle._build_fix_inner_command` (fix-cycle inner cmd) | `pi -p "$(cat {prompt_path})" --model {resolved_model}` |
| `fix_cycle._build_fix_launch_argv` (PTY wrapper resolver) | falls through to `["/bin/sh", "-c", inner_command]` — Pi works under non-TTY stdout (R-00072 §1), no `script -qec` wrapper |
| `doc_job_poller._build_agent_command` (doc-job launcher) | `pi -p "/{skill} doc-job {job.id}"` |
| `doc_service.complete_doc_job` (command_issued snapshot) | `pi -p "/doc-job {job.id}"` |

No `--dangerously-skip-permissions` or `--permission-mode bypassPermissions`
flag is passed in any Pi branch — Pi gates capabilities via extension
permissions rather than a CLI switch (R-00072 §7).

## Allowlist (project_registry.py)

Added module-level `_VALID_CLI_TOOLS = {"opencode", "claude", "pi"}`. After
`cli_tool` is resolved (projects.toml entry → .iw-orch.json → default
"opencode"), the loader checks `cli_tool in _VALID_CLI_TOOLS`; on miss it
logs `Project %r has invalid cli_tool %r (expected one of %s) — skipping`
and returns `None` (same shape as the existing `repo_root`-missing and
nonexistent-repo skip paths at lines 141 / 145). No DB CHECK constraint is
added — adding a 4th runtime later stays a one-line code change.

## Files changed

| File | Change |
|------|--------|
| `executor/step_executor.sh` | + `pi` arm; `else` error message lists three runtimes |
| `executor/step_executor_lib.sh` | + `pi)` case in `_run_agent_oneshot` (prompt on stdin) |
| `orch/daemon/batch_manager.py` | Extracted `_build_initial_command`; `_launch_step` now calls it |
| `orch/daemon/fix_cycle.py` | Extracted `_build_fix_inner_command`; `_launch_fix_agent` now calls it; comment on `_build_fix_launch_argv` documents that pi/claude take the unwrapped `/bin/sh -c` arm |
| `orch/daemon/doc_job_poller.py` | Three-arm `if/elif/elif/else` with explicit ValueError on unknown cli_tool |
| `orch/doc_service.py` | Same three-arm pattern in `complete_doc_job` |
| `orch/daemon/project_registry.py` | + `_VALID_CLI_TOOLS` module-level constant + allowlist check inside `_build_project_config` |
| `tests/unit/test_pi_runtime_dispatch.py` | **NEW** — 13 unit tests covering the new branches + allowlist |
| `tests/unit/test_batch_manager.py` | Two pre-existing tests updated to patch `resolve_runtime` with concrete `cli_tool` strings (they previously relied on the MagicMock-fall-through-to-claude behaviour that the explicit-raise broke) |
| `tests/unit/test_doc_job_poller.py` | Two pre-existing `complete_doc_job` tests updated to seed a concrete `cli_tool` so the new ValueError path doesn't fire |

The `_build_fix_launch_argv` function itself is unchanged — only its
docstring grew a paragraph explaining that the unwrapped `/bin/sh -c` arm
intentionally covers pi (matching what the design doc S03 §4 calls out).

## TDD evidence

RED was captured against the new helper before the pi branch was added:

```
$ uv run pytest tests/unit/test_pi_runtime_dispatch.py::test_build_initial_command_pi_uses_pi_print_mode \
                tests/unit/test_pi_runtime_dispatch.py::test_build_fix_inner_command_pi_shape \
                -v --no-cov
FAILED tests/unit/test_pi_runtime_dispatch.py::test_build_fix_inner_command_pi_shape
FAILED tests/unit/test_pi_runtime_dispatch.py::test_build_initial_command_pi_uses_pi_print_mode

tests/unit/test_pi_runtime_dispatch.py:66: AssertionError
>       assert "pi -p" in cmd
E       assert 'pi -p' in 'claude -p "$(cat /wt/.tmp/X_S01.prompt)" --model minimax/MiniMax-M2.7 --dangerously-skip-permissions'
```

The implementation site at that point was a transitional shape with the
helper returning the claude argv for any non-opencode cli_tool (matching
the previous inline logic at `batch_manager.py:1466`). Adding the `pi`
branch + the explicit `ValueError` flipped both tests GREEN on the next
run; the captured RED line above is the canonical evidence.

Bash dispatch sites are exercised only indirectly here — S05 will spin a
stub `pi` binary on PATH for end-to-end verification. That's documented in
the design's TDD section and the prompt's RED-evidence note.

## Preflight (NON-NEGOTIABLE)

- `make format` → ok (`773 files already formatted`)
- `make typecheck` → ok (`Success: no issues found in 257 source files`)
- `make lint` → ok (`scripts/check_templates.py` + `ruff check` — `All checks passed!`)

## Test verification (NON-NEGOTIABLE)

```
$ uv run pytest tests/unit/test_pi_runtime_dispatch.py -v --no-cov
13 passed in 0.17s
```

Sanity run of every test file my refactor touched:

```
$ uv run pytest tests/unit/test_fix_cycle.py tests/unit/test_batch_manager.py \
                tests/unit/test_doc_job_poller.py tests/unit/test_project_registry.py \
                tests/unit/test_pi_runtime_dispatch.py --no-cov
162 passed in 0.46s
```

No full unit/integration suite was run — those are S12 / S13 QV gates per
the prompt.

## Observations

- The `_build_initial_command` / `_build_fix_inner_command` extraction was
  the minimum refactor needed to write a meaningful RED→GREEN test against
  the dispatch logic. The previous inline branches at `batch_manager.py:1466`
  and `fix_cycle.py:2286` could only be tested by patching `subprocess.Popen`
  and reading the constructed command string back out of `call_args` — a
  much weaker assertion. The extraction keeps the existing call sites a
  one-liner and adds explicit, named contracts the design references
  (`_build_initial_command`, `_build_fix_inner_command` are both named in
  the design's *Affected Components* table).
- Two pre-existing tests were quietly relying on the lenient
  `else: <claude form>` fall-through (their MagicMocks returned a MagicMock
  for `cli_tool`, which compared non-equal to every concrete string and
  hit the else arm). Adding the explicit `raise ValueError` exposed the
  brittleness; updating those four tests (two in `test_batch_manager.py`,
  two in `test_doc_job_poller.py`) to mock `resolve_runtime` properly is
  the right fix — it was a latent test bug that masked a real production
  risk (a typo in `projects.toml`'s `cli_tool` would have silently launched
  claude, not failed loudly).
- `step_executor.sh`'s `$MODEL` is not set by the script itself. The header
  documents this script as "for manual execution and testing"; in normal
  daemon operation the daemon launches agents directly via
  `subprocess.Popen` with the resolved model spliced into the argv (via
  `_build_initial_command`). The pi branch uses `${MODEL:-}` with a
  documented fallback to `anthropic/claude-sonnet-4-6` and logs a warning
  via `_lib_log` when it has to use that fallback, so a manual operator
  who forgets to export `MODEL=...` gets a clear, recoverable message
  rather than `set -u`'s `unbound variable`.
- `pi -p` without an inline prompt argument is documented to read the
  prompt from stdin (verified by reading R-00072 §1 and §2 — the print-mode
  contract mirrors `claude --print`). The `_run_agent_oneshot` case is
  `echo "$prompt" | pi -p --model "$model"`, matching the existing
  claude/opencode shapes byte-for-byte.

## Result contract

```json
{
  "step": "S03",
  "agent": "pipeline-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "executor/step_executor.sh",
    "executor/step_executor_lib.sh",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "orch/daemon/doc_job_poller.py",
    "orch/doc_service.py",
    "orch/daemon/project_registry.py",
    "tests/unit/test_pi_runtime_dispatch.py",
    "tests/unit/test_batch_manager.py",
    "tests/unit/test_doc_job_poller.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "13 passed (test_pi_runtime_dispatch.py); 162 passed across all touched test files",
  "tdd_red_evidence": "tests/unit/test_pi_runtime_dispatch.py::test_build_initial_command_pi_uses_pi_print_mode — AssertionError: assert 'pi -p' in 'claude -p \"$(cat /wt/.tmp/X_S01.prompt)\" --model minimax/MiniMax-M2.7 --dangerously-skip-permissions'",
  "blockers": [],
  "notes": "Extracted two small dispatch helpers (_build_initial_command, _build_fix_inner_command) so the per-runtime argv shape is unit-testable end-to-end. Bash dispatch sites (step_executor.sh, step_executor_lib.sh) carry n/a RED evidence — verified by inspection here, exercised by S05 against a stub pi binary on PATH. Updated 4 pre-existing tests that were silently relying on the lenient else: claude fallthrough; they now patch resolve_runtime with concrete cli_tool strings."
}
```
