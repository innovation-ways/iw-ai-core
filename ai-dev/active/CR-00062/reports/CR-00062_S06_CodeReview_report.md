# CR-00062 — S06 Code Review Report

**Step**: S06 — Per-agent code review of S01/S03/S04/S05
**Agent**: code-review-impl
**Completion**: complete

## Scope

Reviewed all implementation work produced by S01 (database-impl), S03
(pipeline-impl), S04 (backend-impl), and S05 (tests-impl), against the
review checklists in `prompts/CR-00062_S06_CodeReview_prompt.md`, the
design doc `CR-00062_CR_Design.md`, and the project conventions in
`CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`, and `tests/CLAUDE.md`.

No code was modified by this step — review only. Findings below will be
applied by S07 (`code-review-fix-impl`) for CRITICAL/HIGH severities;
MEDIUM/LOW are advisory.

## Files reviewed

| Step | File |
|------|------|
| S01 | `orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py` |
| S01 | `orch/db/models.py` (StepRun.cli_tool and Batch.cli_tool comments) |
| S03 | `executor/step_executor.sh` |
| S03 | `executor/step_executor_lib.sh` |
| S03 | `orch/daemon/batch_manager.py` |
| S03 | `orch/daemon/fix_cycle.py` |
| S03 | `orch/daemon/doc_job_poller.py` |
| S03 | `orch/doc_service.py` |
| S03 | `orch/daemon/project_registry.py` |
| S03 | `tests/unit/test_batch_manager.py` (existing-test updates) |
| S03 | `tests/unit/test_doc_job_poller.py` (existing-test updates) |
| S04 | `orch/skills/sync_agents.py` |
| S04 | `orch/cli/skills_commands.py` |
| S04 | `agents/pi/*.md` (30 files — full directory) |
| S05 | `tests/unit/test_pi_runtime_dispatch.py` |
| S05 | `tests/unit/test_sync_agents_pi.py` |
| S05 | `tests/unit/test_project_registry_allowlist.py` |
| S05 | `tests/integration/test_pi_dispatch_end_to_end.py` |

## Summary

The implementation is **clean and follows project conventions**. No
CRITICAL or HIGH findings. Every required dispatch site has a `pi` branch
with the documented argv shape, the catalogue migration mirrors the
`d1e2f3gpt53c` reference pattern (sequence realignment + ON-CONFLICT
idempotency + per-row DELETEs in downgrade), the allowlist in
`project_registry` warns-and-skips on unknown values, the
`agents/pi/` master tree matches `agents/claude/` filename-by-filename
(30/30), and the test surface covers each new code path with strict
positional assertions plus negative tests for every explicit-raise site
added by S03.

Three LOW-severity findings recorded for tidiness. None block downstream
steps.

### Findings index

| ID | Severity | Step | File | Summary |
|----|----------|------|------|---------|
| F1 | LOW | S01 | `ai-dev/active/CR-00062/CR-00062/` | Stray nested duplicate of the design package (CR-00062_CR_Design.md / Functional.md / prompts/ / workflow-manifest.json) sits one directory below itself. Likely an init-time artifact; does not affect runtime but should be deleted to avoid drift between the two copies. |
| F2 | LOW | S03 | `executor/step_executor.sh` | Script header (lines 13–20) still documents the `<cli_tool>` argument as "'opencode' or 'claude' (default: opencode)". The else-branch error message was updated to include `pi`, but the file-top header was not. |
| F3 | LOW | S01 | `ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md` | The S01 report does not embed an explicit JSON result-contract block with a `tdd_red_evidence: "n/a — data-only migration ..."` field. The narrative does explain the seed-migration's lack of a RED test, but for consistency with S03/S04/S05 (which all embed the JSON block) S01 should carry one too. Not a blocker for execution. |

## Detailed review per step

### S01 (database-impl) — migration + model comments

| Checklist item | Verdict |
|----------------|---------|
| Revision file matches `d1e2f3gpt53c` pattern (SERIAL realignment + ON CONFLICT idempotency) | ✅ — `6d78323d0954_add_pi_runtime_options.py` uses identical `setval(pg_get_serial_sequence(...), GREATEST(MAX(id), 1), true)` + `ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model DO UPDATE`. |
| Both rows enabled=true, is_default=false, sort_order 25/26 | ✅ — `(pi, minimax/MiniMax-M2.7)` is sort_order 25; `(pi, openai/gpt-5.3-codex)` is 26. |
| `display_name` strings match design | ✅ — `"Pi + MiniMax 2.7"` and `"Pi + GPT-5.3 Codex"` exactly. |
| `downgrade()` is symmetric and explicit (one DELETE per row, not a blanket WHERE) | ✅ — Two per-`(cli_tool='pi', model=…)` DELETEs. |
| Column-comment updates: StepRun.cli_tool and Batch.cli_tool both say new enumeration | ✅ — Migration writes `_NEW_CLI_TOOL_COMMENT = "LLM CLI tool used: 'opencode', 'claude', or 'pi'"` to both; the model file mirrors with `comment=` strings on both columns. |
| Batch.cli_tool `server_default='opencode'` unchanged | ✅ — `server_default=text("'opencode'")` preserved in both the migration's `existing_server_default=` and the model. |
| No CHECK constraint added | ✅ — Migration adds none; allowlist is code-only in `project_registry`. |
| `make migration-check` reported green | ✅ — S01 report: "3 passed in 8.49s" (round-trip + create_all parity + head-from-empty). |
| Migration chain is linear and head | ✅ — `down_revision = "21de61b41cec"`; no other revision claims `21de61b41cec` as parent; no revision claims `6d78323d0954` as parent. |
| Downgrade ordering | ✅ — Alters columns first, then DELETEs the rows. Documented intent: a partial downgrade where the FK RESTRICT prevents the DELETE still leaves the schema with the reverted comments rather than the wrong-comment state. Defensible and well-commented. |

**Observation**: the downgrade reverts the column comment first then deletes the rows, which means if the DELETE fails due to RESTRICT, the schema is left without the three-value comment but still has the two pi rows referenced by FKs. This is the documented intended state and operationally correct (the operator is expected to un-pin the references then re-run the downgrade). Not a finding.

### S03 (pipeline-impl) — eight dispatch sites + allowlist

| Site | Verdict |
|------|---------|
| `executor/step_executor.sh` step-launch arm | ✅ — New `elif [[ "$CLI_TOOL" == "pi" ]]` arm with `setsid timeout "$TIMEOUT" pi -p "$INSTRUCTION" --model "$MODEL"`; else-branch error mentions `'opencode', 'claude', or 'pi'`. The empty-MODEL fallback (`anthropic/claude-sonnet-4-6` with a `_lib_log` WARNING) is a thoughtful manual-operator ergonomics touch — not required, but matches the script's documented "for manual execution and testing" purpose. |
| `executor/step_executor_lib.sh _run_agent_oneshot` | ✅ — New `pi)` case `echo "$prompt" \| pi -p --model "$model"`. Stdin piping mirrors the claude case. |
| `orch/daemon/batch_manager.py _build_initial_command` (NEW helper) | ✅ — Three-arm `if cli_tool == "opencode" / "claude" / "pi"`, each with the exact form documented in the design. Trailing `raise ValueError(f"Unknown cli_tool: {cli_tool!r}")` matches the design's explicit-raise contract. Pi branch carries **no** `--dangerously-skip-permissions` per R-00072 §7. |
| `orch/daemon/fix_cycle.py _build_fix_inner_command` (NEW helper) | ✅ — Same three-arm shape as the batch_manager helper, with `raise ValueError` for unknown. Docstring explicitly names "drifting between them is exactly how I-00074 surfaced" — keeps the two helpers in lockstep. |
| `orch/daemon/fix_cycle.py _build_fix_launch_argv` | ✅ — Function body unchanged. Docstring expanded to call out that pi/claude both take the unwrapped `/bin/sh -c` arm and Pi's print mode is documented to work under non-TTY stdout (R-00072 §1). No PTY wrapper applied to pi — correct per design. |
| `orch/daemon/doc_job_poller.py _build_agent_command` | ✅ — Converted from `if/else` to `if/elif/elif/else`. Pi arm produces `pi -p "/{skill} doc-job {job.id}"` — no permission flag. Else-branch raises `ValueError("Unknown cli_tool: …")`. |
| `orch/doc_service.py complete_doc_job` | ✅ — Same three-arm + raise structure inline (no extracted helper, which the S05 report explicitly verifies via a parametrised mock-session test against `report["command_issued"]`). |
| `orch/daemon/project_registry.py _build_project_config` | ✅ — Module-level `_VALID_CLI_TOOLS = {"opencode", "claude", "pi"}` constant; allowlist check sits AFTER the `entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")` expression so both projects.toml and .iw-orch.json paths are validated; warn-and-skip returns `None`, matching the existing `repo_root`-missing / nonexistent-repo skip shape. |
| No PTY wrapper used for pi | ✅ — Confirmed by reading `_build_fix_launch_argv` body; the `script -qec ... /dev/null` arm is gated on `cli_tool == "opencode"` only. |
| No `--dangerously-skip-permissions` or `--permission-mode bypassPermissions` flag on the pi command | ✅ — Verified across all eight dispatch sites. Pi gates capabilities via extension permissions per R-00072 §7. |

**Note on the `test_batch_manager.py` / `test_doc_job_poller.py` updates** (called out by the S03 report as "two pre-existing tests were quietly relying on the lenient `else: claude form` fall-through"): the updates patch `resolve_runtime` to return a concrete `cli_tool` string instead of a MagicMock, which is the *correct* fix — the previous tests were exercising a fall-through behaviour that S03's explicit-raise contract intentionally removes. The fix-tests change is appropriate and not a regression.

### S04 (backend-impl) — agents/pi/ + sync engine + CLI

| Checklist item | Verdict |
|----------------|---------|
| `agents/pi/` directory exists and matches `agents/claude/` filename count | ✅ — Both directories contain 30 `.md` files; `diff <(ls agents/claude/) <(ls agents/pi/)` is empty. (The prompt referenced "31"; both master trees in the worktree are 30 — the S04 report correctly notes and explains the discrepancy.) |
| Stubbed agent files carry `TODO(CR-00062-followup):` markers | ✅ — Not applicable: S04 verified every body is runtime-agnostic and no file was stubbed (`grep -r "TODO(CR-00062-followup)" agents/pi/` returns nothing). Frontmatter translation removed Claude-specific fields (`model`, `maxTurns`, `disallowedTools`, `permissionMode`) and replaced them with a `<!-- pi-port: stripped … -->` comment placed immediately below the closing `---`. |
| `AgentSyncResult.pi_agents_synced` field added with default 0 | ✅ — `pi_agents_synced: int = 0` inserted between `claude_agents_synced` and `opencode_agents_synced`. |
| `sync_agents_and_commands()` includes a third `_sync_directory(... agents/pi, .pi/agents)` call between Claude and OpenCode | ✅ — Order matches the design. |
| `sync_agents_cmd` JSON output includes `"pi_agents"` key | ✅ — Added between `claude_agents` and `opencode_agents`. |
| `sync_agents_cmd` human output prints `Pi agents: N` line and total includes pi | ✅ — `click.echo(f"  Pi agents: {result.pi_agents_synced}")` + the `total = result.claude_agents_synced + result.pi_agents_synced + result.opencode_agents_synced + result.opencode_commands_synced` sum. |
| `projects.toml` unchanged | ✅ — `git diff main -- projects.toml` is empty. No project switched to pi. |

### S05 (tests-impl) — argv, sync, allowlist, e2e

| Checklist item | Verdict |
|----------------|---------|
| All four test files exist and target the right module surfaces | ✅ — `tests/unit/test_pi_runtime_dispatch.py` (19 tests), `tests/unit/test_sync_agents_pi.py` (5 tests), `tests/unit/test_project_registry_allowlist.py` (7 tests), `tests/integration/test_pi_dispatch_end_to_end.py` (6 tests). |
| Strict positional assertions (mutation-test discipline) | ✅ — `cmd.startswith("pi -p ")` and `argv == ["/bin/sh", "-c", inner]` throughout; no weak `"pi" in cmd` substring matches that would pass for `"mpi"` or `"pi-broken"`. |
| Test counts hit the prompt minimums | ✅ — argv dispatch ≥12 assertions: well over (19 tests, ~80 asserts). sync_agents: 5 tests / >15 asserts (≥6 assertion floor satisfied). project_registry allowlist: 7 tests / >15 asserts (≥6 floor). end-to-end integration: 6 tests with ≥10 strict-positional asserts total. |
| Stub `pi` binary fixture is correct | ✅ — `tmp_path/bin/pi` written with `0o755`, monkeypatch prepends `tmp_path/bin` to PATH, stub echoes `STUB_PI_MARKER_<pid>` so each invocation produces a unique marker (defends against stale-log false positives). |
| Catalogue lookup integration test runs against the testcontainer DB | ✅ — `test_pi_catalogue_resolves_minimax_and_codex` uses the real `db_session` fixture; `resolve_runtime(db_session, …)` reads from the migrated testcontainer DB (no mocking of the DB session). |
| No `importlib.reload(orch.config)` | ✅ — `grep -n "importlib.reload" tests/{unit,integration}/test_pi*.py` and related files returns nothing. |
| No DB mocking in integration tests | ✅ — `db_session` is the real testcontainer session; the MagicMock usage in `test_pi_dispatch_end_to_end.py` is confined to `job`/`step`/`item`/`project_*` objects (NOT the session), which is acceptable per the conventions. |
| FTS DDL hook present in fixtures | ✅ — Tests use the shared `tests/integration/conftest.py` fixtures (`db_session`, etc.), which set up FTS DDL after `create_all()`. The new tests do not invoke `create_all()` themselves, so no per-test FTS DDL hook is needed. |
| No silent `pytest.skip(...)` | ✅ — Two `@pytest.mark.skipif` decorators present (`_BASH_OK` probe; `_IW_BINARY.is_file()`), both carry inline `reason="..."` explaining the platform/setup constraint. |
| Negative-case coverage | ✅ — Each S03-added explicit-raise site has a `pytest.raises(ValueError, match="Unknown cli_tool")` test. The allowlist file has both projects.toml-typo and .iw-orch.json-typo negative cases. The doc-job poller test has a real-DB-row "aider" config test that asserts the second line of defence fires even when the in-memory allowlist is bypassed. |

### Cross-cutting checks

| Item | Verdict |
|------|---------|
| No scope creep | ✅ — `git status` shows only files under `scope.allowed_paths` from the workflow manifest. (`agents/pi/**`, `executor/**`, the listed `orch/*.py`, `orch/db/migrations/versions/**`, `tests/unit/**`, `tests/integration/**`, `ai-dev/active/CR-00062/**`.) |
| No regression in opencode or claude dispatch | ✅ — Existing tests in `tests/unit/test_batch_manager.py` and `tests/unit/test_doc_job_poller.py` were updated only to supply concrete `cli_tool` strings to the mocked `resolve_runtime` so the new explicit-raise on unknown does not fire — this is a tightening, not a regression. The opencode/claude argv shapes themselves are pinned by the new parametrised tests in `test_pi_runtime_dispatch.py`. |
| All four implementation steps' preflight gates ran clean | ✅ — Each report's "Preflight" section records `make format → ok`, `make typecheck → ok`, `make lint → ok`. S01 additionally records `make migration-check → ok`. |
| TDD red evidence captured | S01: explained as "data-only migration; n/a" (narrative only — see F3). S03: `test_build_initial_command_pi_uses_pi_print_mode — AssertionError: assert 'pi -p' in 'claude -p …'` captured verbatim. S04: `AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced'` captured verbatim. S05: explicit "n/a — pre-fix RED captured by S03/S04" in the result contract. All four are acceptable. |

## Result contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S06_CodeReview_report.md"
  ],
  "preflight": {
    "format": "n/a — review only",
    "typecheck": "n/a — review only",
    "lint": "n/a — review only"
  },
  "tests_passed": true,
  "test_summary": "review-only",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"id": "F1", "severity": "LOW", "step": "S01", "file": "ai-dev/active/CR-00062/CR-00062/", "summary": "Stray nested duplicate of the design package — delete to avoid drift."},
    {"id": "F2", "severity": "LOW", "step": "S03", "file": "executor/step_executor.sh", "summary": "Script header (Usage) does not list 'pi' as a valid <cli_tool> value; only the else-branch error message was updated."},
    {"id": "F3", "severity": "LOW", "step": "S01", "file": "ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md", "summary": "Report lacks the JSON result-contract block with tdd_red_evidence='n/a — data-only migration'; only S03/S04/S05 reports embed one."}
  ],
  "blockers": [],
  "notes": "No CRITICAL or HIGH findings. All eight dispatch sites correctly wire the pi branch with the documented argv shape; the migration follows the d1e2f3gpt53c pattern; the agents/pi/ master tree mirrors agents/claude/ filename-by-filename; the test surface uses strict positional assertions plus negative tests for every explicit-raise site. The three LOW findings are tidiness items for S07 to optionally address; none block downstream steps."
}
```
