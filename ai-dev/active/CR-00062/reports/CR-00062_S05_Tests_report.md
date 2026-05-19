# CR-00062 — S05 Tests Report

**Step**: S05 — Tests
**Agent**: tests-impl
**Completion**: complete

## What was done

Built the durable test surface that proves S01/S03/S04 wired Pi end-to-end. The
test layer enforces argv-shape correctness for every dispatch site touched by
S03, the new `pi_agents_synced` counter added by S04, the `_VALID_CLI_TOOLS`
allowlist added by S03 to `project_registry`, and the S01 catalogue rows
reachable through the resolver. The integration layer adds a stub `pi` binary
on PATH so the bash-layer dispatch (`step_executor.sh`, `step_executor_lib.sh`)
is exercised under realistic subprocess semantics.

### Files changed

| File | Change |
|------|--------|
| `tests/unit/test_pi_runtime_dispatch.py` | **REWRITTEN** — was 9 tests covering only the Pi arm of three sites; now 19 tests parametrising every dispatch site across `cli_tool ∈ {opencode, claude, pi}` plus negative tests for each S03-added explicit-raise site (5 sites total). Adds doc-service coverage by driving `complete_doc_job` with a mock session and asserting on `report["command_issued"]`. The project_registry tests that were temporarily co-located here in S03 have been moved into the dedicated `test_project_registry_allowlist.py` file. |
| `tests/unit/test_sync_agents_pi.py` | **EXPANDED** — was 3 tests; now 5 tests covering the dataclass invariant, copy-into-`.pi/agents/`, target-creation-on-missing, byte-level idempotency (re-run produces byte-identical files), and the total-count CLI arithmetic. |
| `tests/unit/test_project_registry_allowlist.py` | **NEW** — 7 tests covering valid cli_tool loads (opencode/claude/pi), invalid typo warn-and-skip, missing-key default to opencode, `.iw-orch.json` fallback through allowlist (negative + positive). |
| `tests/integration/test_pi_dispatch_end_to_end.py` | **NEW** — 6 tests: stub pi binary on PATH for auto-merge oneshot subprocess; full step_executor.sh end-to-end against a real DB step row + stub pi on PATH; fix-cycle launch-argv integration (pi takes `/bin/sh -c` arm, not `script -qec` PTY wrap); doc-job builder against a real `Project` row in the testcontainer DB (happy path + bad-cli_tool ValueError); catalogue resolver returning both new pi rows with exact `display_name` / `sort_order` / `enabled` / `is_default` values. |

### Test count summary

| File | Tests | Notes |
|------|-------|-------|
| `tests/unit/test_pi_runtime_dispatch.py` | 19 | 1 parametrise-3 case + 16 explicit |
| `tests/unit/test_sync_agents_pi.py` | 5 | dataclass + sync + idempotency + total |
| `tests/unit/test_project_registry_allowlist.py` | 7 | 3 valid + invalid + missing + 2 iw-orch fallback |
| `tests/integration/test_pi_dispatch_end_to_end.py` | 6 | bash subprocess + DB integration + resolver |
| **Total** | **37** | all green on first full-suite run |

## Argv-shape coverage matrix (per dispatch site)

| Site | opencode | claude | pi | unknown raises |
|------|----------|--------|----|----|
| `batch_manager._build_initial_command` | ✓ | ✓ | ✓ | ✓ |
| `fix_cycle._build_fix_inner_command` | ✓ | ✓ | ✓ | ✓ |
| `fix_cycle._build_fix_launch_argv` | ✓ (`script -qec`) | ✓ (`/bin/sh -c`) | ✓ (`/bin/sh -c`) | n/a (no explicit raise — non-opencode falls through) |
| `doc_job_poller._build_agent_command` | ✓ | ✓ | ✓ | ✓ |
| `doc_service.complete_doc_job` (inline) | ✓ (parametrise) | ✓ (parametrise) | ✓ (parametrise) | ✓ |
| `step_executor.sh` (bash dispatch) | — | — | ✓ (e2e stub) | — |
| `step_executor_lib.sh _run_agent_oneshot` | — | — | ✓ (e2e stub) | — |

## Test results

```
$ uv run pytest tests/unit/test_pi_runtime_dispatch.py \
                tests/unit/test_sync_agents_pi.py \
                tests/unit/test_project_registry_allowlist.py \
                tests/integration/test_pi_dispatch_end_to_end.py -v --no-cov
…
============================== 37 passed in 5.87s ==============================
```

Per the prompt's NON-NEGOTIABLE rule (and CR-00023's tests-impl convention),
no `make test-unit` or `make test-integration` was run — those are S12 / S13
QV gates.

## Preflight (NON-NEGOTIABLE)

- `make format` → ok (`776 files already formatted`)
- `make lint` → ok (`scripts/check_templates.py` + `ruff check` — `All checks passed!`)
- `make typecheck` → ok (`mypy orch/ dashboard/` — `Success: no issues found in 257 source files`)

## TDD evidence

Per the prompt:

> Pre-fix RED evidence for the `pi` dispatch branches and the
> `pi_agents_synced` field is owned by S03 and S04.

S03 reported the RED evidence for the dispatch branches in
`CR-00062_S03_Pipeline_report.md`:

```
FAILED tests/unit/test_pi_runtime_dispatch.py::test_build_initial_command_pi_uses_pi_print_mode
FAILED tests/unit/test_pi_runtime_dispatch.py::test_build_fix_inner_command_pi_shape

tests/unit/test_pi_runtime_dispatch.py:66: AssertionError
>       assert "pi -p" in cmd
E       assert 'pi -p' in 'claude -p "$(cat /wt/.tmp/X_S01.prompt)" --model minimax/MiniMax-M2.7 --dangerously-skip-permissions'
```

S04 reported the RED for `pi_agents_synced` in `CR-00062_S04_Backend_report.md`:

```
>       assert result.pi_agents_synced == 2
E       AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced'. Did you mean: 'claude_agents_synced'?
```

For S05's own `tdd_red_evidence` slot in the result contract: **n/a —
pre-fix RED captured by S03/S04 prompts; this step adds the durable test
surface**. No S03/S04 regressions were discovered while writing the S05
tests — every assertion fires GREEN against the implemented production code,
and the negative tests (unknown cli_tool → `ValueError`) fire against the
explicit raises S03 added.

## Notes

- **Stub-PATH platform compatibility.** Two integration tests
  (`test_pi_auto_merge_oneshot_pipes_stdin`, `test_pi_step_launch_invokes_stub`)
  shell into bash subprocesses and rely on a stub `pi` binary being resolvable
  via PATH. A module-level probe (`_can_run_bash_subprocess_with_custom_path`)
  detects platforms where this mechanism cannot work and skips both tests
  with a documented reason — never a silent skip. On this dev environment the
  probe returned True; both tests passed.

- **`iw` CLI on PATH skip clause.** `test_pi_step_launch_invokes_stub` invokes
  `step_executor.sh` which shells out to `iw item-status` to discover the
  step's launchable state. If the venv-installed `iw` is missing
  (`.venv/bin/iw`), the test is `@pytest.mark.skipif`-ed with a reason
  pointing the operator to `uv sync`. Not a silent skip.

- **DB-visibility fix for `step_executor.sh` e2e.** While developing the
  step-launch e2e test, I discovered that the iw CLI's `get_orch_db_url()`
  prefers `IW_CORE_ORCH_DB_*` env vars over `IW_CORE_DB_*`. The integration
  conftest only monkeypatches the latter — so without the `_ORCH_` overrides
  the subprocess would silently resolve to the production orch DB on
  port 5433 and never see the test's rows. The pattern is borrowed
  from `tests/integration/cli/test_step_commands_drift.py` (which also
  documents `IW_CORE_DAEMON_CONTEXT=true` for live-db-guard bypass).
  Documented inline in the test for future readers.

- **`project_registry` allowlist tests promoted out of `test_pi_runtime_dispatch.py`.**
  S03 colocated three allowlist tests inside the dispatch test file (they
  were the simplest way to exercise the new `_VALID_CLI_TOOLS` constant
  during S03's RED-GREEN cycle). S05 promotes them to a dedicated module
  and expands the coverage to 7 functions per the prompt requirement — and
  removes the originals from `test_pi_runtime_dispatch.py` so the dispatch
  file stays focused.

- **doc_service.complete_doc_job inline branch.** There is no separate
  `_build_command` helper in `doc_service.py` (the cli_tool branch lives
  inline inside `complete_doc_job`). I exercised it via a `MagicMock`-driven
  unit test that drives the function with a fake session whose
  `session.get(DocGenerationJob, id)` and `session.get(Project, id)` calls
  return prepared mock objects. The test asserts on `job.report["command_issued"]`
  (the audit-trail field that captures the runtime-specific shape) and is
  parametrised across all three valid cli_tools plus a negative arm for the
  unknown-cli_tool ValueError.

- **Mutation-test discipline.** Per the prompt's "I003 lesson" warning, I
  used strict positional assertions (`cmd.startswith("pi -p ")`,
  `argv == ["/bin/sh", "-c", inner]`) rather than substring containment
  (`"pi" in cmd`) so a misbuilt `["pi-broken", "-p", ...]` or
  `["mpi", "-p", ...]` would still fail. The catalogue-resolver test
  pins every field the design doc names (cli_tool, model, display_name,
  enabled, is_default, sort_order) — not just "a pi row exists".

## Result contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "tests/unit/test_pi_runtime_dispatch.py",
    "tests/unit/test_sync_agents_pi.py",
    "tests/unit/test_project_registry_allowlist.py",
    "tests/integration/test_pi_dispatch_end_to_end.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "37 passed, 0 failed (19 + 5 + 7 + 6 across the 4 new/expanded files)",
  "tdd_red_evidence": "n/a — pre-fix RED captured by S03/S04 prompts; this step adds the durable test surface. Verified the S03 dispatch RED (test_build_initial_command_pi_uses_pi_print_mode, AssertionError on 'pi -p' in claude-form command) and the S04 sync RED (AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced') by reading the prior step reports — both are captured verbatim in S03's and S04's reports.",
  "blockers": [],
  "notes": "Two integration tests carry @pytest.mark.skipif with documented reasons (bash subprocess availability; iw CLI on PATH). Promoted project_registry tests out of test_pi_runtime_dispatch.py into a dedicated module per prompt requirement; expanded sync_agents test count from 3 to 5 to cover idempotency + total-count arithmetic; rewrote test_pi_runtime_dispatch.py to parametrise every dispatch site across all three cli_tools plus a negative test for every S03 explicit-raise site. No S03/S04 regressions were uncovered while building this test surface."
}
```
