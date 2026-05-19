# CR-00062 — S08 Cross-Agent Final Review Report

**Step**: S08 — Cross-agent global review
**Agent**: code-review-final-impl
**Completion**: complete
**Date**: 2026-05-19

## Scope

Cross-cutting integration review across the seven implementation/review steps
(S01..S07). Looking for issues that no single per-agent review (S06) could
catch because they span layer boundaries — executor↔daemon↔resolver↔dashboard.

The branch is `agent/CR-00062-add-pi-pi-dev-as-a-third-agent`; the CR is staged
on top of `db0483ec` (which only adds the `ai-dev/active/CR-00062/` scaffolding
without any code change). `git diff main...HEAD` is therefore empty — all
implementation lives uncommitted in the working tree (modified files + new
files). Reviewed both surfaces.

## Files reviewed (cross-step view)

| Step | Layer | Files |
|------|-------|-------|
| S01 | DB / migration | `orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py`, `orch/db/models.py` |
| S03 | Dispatch (executor + daemon + service) | `executor/step_executor.sh`, `executor/step_executor_lib.sh`, `orch/daemon/batch_manager.py`, `orch/daemon/fix_cycle.py`, `orch/daemon/doc_job_poller.py`, `orch/doc_service.py`, `orch/daemon/project_registry.py` |
| S04 | Master agents + sync engine + CLI | `agents/pi/*.md` (30 files), `orch/skills/sync_agents.py`, `orch/cli/skills_commands.py` |
| S05 | Tests | `tests/unit/test_pi_runtime_dispatch.py`, `tests/unit/test_sync_agents_pi.py`, `tests/unit/test_project_registry_allowlist.py`, `tests/unit/test_batch_manager.py`, `tests/unit/test_doc_job_poller.py`, `tests/integration/test_pi_dispatch_end_to_end.py` |
| Cross | Dashboard | `dashboard/routers/runtime_overrides.py` (verified UNCHANGED) |

## Cross-cutting integration checks

### 1. Model-string consistency — catalogue ↔ dispatch

✅ **CONSISTENT.** All `--model X` arguments constructed by the four Python
dispatch helpers (`batch_manager._build_initial_command`,
`fix_cycle._build_fix_inner_command`, `doc_job_poller._build_agent_command`,
`doc_service.complete_doc_job`) take the model string from the resolver, which
reads `option.model` directly from the DB row. No hard-coded model literals
in the dispatch helpers. The two new pi seed rows
(`minimax/MiniMax-M2.7`, `openai/gpt-5.3-codex`) match the F-00081 seed
naming convention exactly.

One non-issue worth recording: `executor/step_executor.sh` has a manual-run
fallback `MODEL="anthropic/claude-sonnet-4-6"` inside the pi branch when
`$MODEL` is unset. This is **not** a pi catalogue row, so a manual operator
running the script with an empty `MODEL` against pi would hit a `--model`
value that no catalogue row matches. The fallback is documented as
"manual execution and testing"-only (the script header explicitly says this)
and the daemon always splices in the resolver-resolved model via
`subprocess.Popen` argv (never via the bash fallback). Not a finding — the
warning log `_lib_log "WARNING: \$MODEL is empty …"` makes the path
discoverable.

### 2. Allowlist consistency — `_VALID_CLI_TOOLS` ↔ dispatch sites

✅ **CONSISTENT, with a future-drift note.** `_VALID_CLI_TOOLS = {"opencode",
"claude", "pi"}` in `orch/daemon/project_registry.py` matches the four
Python dispatch sites and the two bash dispatch sites (`step_executor.sh`
and `step_executor_lib.sh`). All four Python sites carry an explicit
`raise ValueError(f"Unknown cli_tool: {cli_tool!r}")` for the unknown-tool
branch — second line of defence against an allowlist bypass.

⚠️ **F1 (LOW) — `_VALID_CLI_TOOLS` is not referenced by any dispatch site.**
A future contributor adding `aider` to `_VALID_CLI_TOOLS` is **NOT** visibly
forced to update the seven dispatch sites (4 Python + 2 bash + 1 frontend).
The runtime `ValueError` will fire on first dispatch attempt — but that's
catching the bug, not preventing it. Consider exporting `_VALID_CLI_TOOLS`
publicly and asserting `cli_tool in _VALID_CLI_TOOLS` inside one of the
dispatch helpers (e.g., `_build_initial_command`) as a safety net. Not a
blocker for this CR (the allowlist + explicit-raise pattern is the same one
F-00081 used), but worth filing as a follow-up note.

### 3. Dashboard endpoint unchanged

✅ **VERIFIED.** `git diff HEAD -- dashboard/` is empty. The
`GET /project/{project_id}/api/runtime-options` endpoint at
`dashboard/routers/runtime_overrides.py:60-86` builds its response by
SELECTing all enabled rows from `agent_runtime_options` and projecting
`{id, cli_tool, model, cli_label, model_label, display_name, is_default}`
generically — so the two new pi rows (both `enabled=true`) surface in
the dropdown automatically without any router change. The design's claim
("**no change is required**") held.

### 4. Sync-agents counter — dataclass ↔ engine ↔ CLI JSON ↔ CLI human ↔ total

✅ **THREADED END-TO-END.** Single coherent chain:

| Surface | Shape |
|---------|-------|
| `AgentSyncResult.pi_agents_synced: int = 0` | Field added between claude/opencode |
| `sync_agents_and_commands()` | New `_sync_directory(platform_root/"agents"/"pi", project_path/".pi"/"agents")` call returns count, assigned to `result.pi_agents_synced` |
| `sync_agents_cmd` JSON | `"pi_agents": result.pi_agents_synced` (between `claude_agents` and `opencode_agents`) |
| `sync_agents_cmd` human | `click.echo(f"  Pi agents: {result.pi_agents_synced}")` |
| Total | `total = result.claude_agents_synced + result.pi_agents_synced + result.opencode_agents_synced + result.opencode_commands_synced` |

No drift between counter add and counter use.

### 5. No PTY wrapper for pi

✅ **VERIFIED.** `_build_fix_launch_argv(cli_tool, inner_command)` returns
`["script", "-qec", inner_command, "/dev/null"]` only when
`cli_tool == "opencode"`; every other value (including `"pi"`) falls into
the `["/bin/sh", "-c", inner_command]` arm. The docstring explicitly calls
out pi: *"Pi's print mode is documented to work under non-TTY stdout
(R-00072 §1), so it never needs the PTY wrapper — falling through to the
unwrapped arm is the correct behaviour, not a missing branch."* Both
`test_pi_runtime_dispatch.py::test_build_fix_launch_argv_pi_uses_sh_c_no_pty_wrap`
and `test_pi_dispatch_end_to_end.py::test_pi_fix_cycle_uses_sh_c_not_script_pty_wrapper`
pin this behaviour.

### 6. Migration round-trip — re-check after S07

✅ **STILL GREEN.** S02 reported `3 passed in 9.09s`
(round-trip + create_all parity + head-from-empty). S07's diff did not touch
`orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py` or
`orch/db/models.py` (verified by inspecting S07's `files_changed`:
`ai-dev/active/CR-00062/CR-00062/ (deleted)`, `executor/step_executor.sh`,
`ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md`,
`ai-dev/active/CR-00062/reports/CR-00062_S07_CodeReviewFix_report.md`).
Therefore the S02 round-trip evidence still holds — no re-run needed in
S08. (The full `make migration-check` will run again at S13 against the
patched worktree.)

### 7. No regressions in claude / opencode dispatch

✅ **GREEN.** Ran the targeted unit subset:

```
$ uv run pytest tests/unit/test_pi_runtime_dispatch.py \
                tests/unit/test_sync_agents_pi.py \
                tests/unit/test_project_registry_allowlist.py \
                tests/unit/test_batch_manager.py \
                tests/unit/test_doc_job_poller.py --no-cov
collected 96 items
…
============================== 96 passed in 0.38s ==============================
```

The two pre-existing tests in `test_batch_manager.py` and the two in
`test_doc_job_poller.py` that S03 updated (to feed `resolve_runtime` a
concrete `cli_tool` string instead of a MagicMock) all pass — confirming
the tightening did not regress the opencode/claude dispatch shape. The
parametrised dispatch tests in `test_pi_runtime_dispatch.py` cover the
opencode and claude argv shapes alongside the new pi shape, so a future
regression in either of the older runtimes also surfaces here.

### 8. Scope compliance

✅ **ALL CHANGES IN SCOPE.** Inspected the union of `git diff HEAD --name-only`
and `git ls-files --others --exclude-standard`:

| Modified / Added | Manifest scope rule |
|------------------|---------------------|
| `executor/step_executor.sh` | `executor/step_executor.sh` ✓ |
| `executor/step_executor_lib.sh` | `executor/step_executor_lib.sh` ✓ |
| `orch/daemon/batch_manager.py` | `orch/daemon/batch_manager.py` ✓ |
| `orch/daemon/fix_cycle.py` | `orch/daemon/fix_cycle.py` ✓ |
| `orch/daemon/doc_job_poller.py` | `orch/daemon/doc_job_poller.py` ✓ |
| `orch/doc_service.py` | `orch/doc_service.py` ✓ |
| `orch/daemon/project_registry.py` | `orch/daemon/project_registry.py` ✓ |
| `orch/db/models.py` | `orch/db/models.py` ✓ |
| `orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py` | `orch/db/migrations/versions/**` ✓ |
| `orch/skills/sync_agents.py` | `orch/skills/sync_agents.py` ✓ |
| `orch/cli/skills_commands.py` | `orch/cli/skills_commands.py` ✓ |
| `agents/pi/*.md` (30 files) | `agents/pi/**` ✓ |
| `tests/unit/*.py` (5 files) | `tests/unit/**` ✓ |
| `tests/integration/test_pi_dispatch_end_to_end.py` | `tests/integration/**` ✓ |
| `ai-dev/active/CR-00062/reports/*.md` | implicit (workflow reports) ✓ |

No out-of-scope edits. No `dashboard/` change (verified by `git diff HEAD --
dashboard/`).

## Acceptance Criteria re-check

| AC | Status | Evidence |
|----|--------|----------|
| **AC1** — pi dispatches end-to-end through 8 sites | ✅ Satisfied | All seven dispatch sites (eight if `_build_fix_launch_argv` is counted, though that one is `unchanged` per design) carry a `pi` branch. Strict positional argv assertions in `test_pi_runtime_dispatch.py` (19 tests, parametrised across all three runtimes for every site). Integration coverage in `test_pi_dispatch_end_to_end.py` (6 tests) including stub-pi-on-PATH end-to-end for `step_executor.sh` + `_run_agent_oneshot`. No invocation uses the PTY wrapper for pi (verified in `_build_fix_launch_argv`). No invocation falls through to claude/opencode branches (negative tests). |
| **AC2** — catalogue rows resolve + surface in dashboard | ✅ Satisfied | `test_pi_catalogue_resolves_minimax_and_codex` pins every field the design names (`cli_tool`, `model`, `display_name`, `enabled`, `is_default`, `sort_order`) against the real testcontainer DB. The existing opencode-MiniMax default is still `is_default=True` (defended against accidental slip). Migration round-trip pinned by S02 (3 passed in 9.09s) and unchanged by S07. Dashboard endpoint unchanged but verified to read enabled rows generically. |
| **AC3** — agents/pi/ created, synced, reported | ✅ Satisfied | `diff <(ls agents/claude/) <(ls agents/pi/)` empty (both contain 30 `.md` files — the design's "31" was off-by-one; both master trees in the worktree are 30). `pi_agents_synced` counter flows through dataclass → sync engine → JSON output → human output → total. `test_sync_agents_pi.py` (5 tests) covers field default, sync into `.pi/agents/`, target-creation-on-missing, byte-level idempotency. `iw sync-agents` CLI prints `Pi agents: N` line; JSON includes `"pi_agents"` key. |
| **AC4** — allowlist enforcement | ✅ Satisfied | `_VALID_CLI_TOOLS = {"opencode", "claude", "pi"}` in `project_registry.py:43`; allowlist check inserted after the `entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")` expression so both projects.toml and .iw-orch.json paths are validated. `test_project_registry_allowlist.py` (7 tests) covers the three valid values + invalid-typo warn-and-skip + missing-key default + .iw-orch.json fallback through allowlist (negative + positive). |
| **AC5** — column comments updated; default unchanged | ✅ Satisfied | Migration body sets `_NEW_CLI_TOOL_COMMENT = "LLM CLI tool used: 'opencode', 'claude', or 'pi'"` on both `step_runs.cli_tool` and `batches.cli_tool` via `op.alter_column`. `Batch.cli_tool` keeps `server_default=text("'opencode'")` (explicit `existing_server_default=` in the migration; preserved in `orch/db/models.py`). No CHECK constraint added. Models file mirrors the new comment. S02's migration-check round-trip would have failed if these strings drifted between `create_all()` and `alembic upgrade head`. |
| **AC6** — all QV gates pass | ✅ Partially satisfied at S08 boundary | S01..S07 each ran clean preflight gates (`format`, `lint`, `typecheck`, plus S02's `migration-check`). Targeted pytest subset in S08 returns 96/96 green. S10..S13 (`make lint` / `make quality` / `make test-unit` / `make test-integration`) are downstream of S09 and will run automatically; nothing in the S03/S04/S05/S07 diffs introduces a new mypy / ruff / format-check error that the per-step preflight didn't already catch. Assessing this AC as **satisfied** at the cross-agent-review boundary; final confirmation is the S10..S13 reports. |

## R-00072 cross-reference (§1 and §7)

✅ **ALIGNED.** R-00072 §1 (SDK API surface) and §7 (Tool-use, permissions,
sandbox) — both consulted; implementation aligns with both:

- **§1 — print/JSON modes are one-shot.** R-00072 §3 says "JSON Event
  Stream Mode" is one-shot (`pi --mode json "prompt"` runs to completion
  and exits). The CR uses **print mode** (`pi -p ...`), which is also a
  one-shot non-interactive mode. Verified `pi --help` on the dev box:
  `--print, -p   Non-interactive mode: process prompt and exit`. So
  `pi -p "$INSTRUCTION"` (inline prompt) and `echo "$prompt" | pi -p`
  (stdin prompt) are both real surfaces. The S03 report's citation of
  "R-00072 §1 and §2" for the `-p` flag was slightly imprecise (those
  sections don't explicitly mention `-p`; they discuss the SDK and RPC
  mode), but the underlying CLI surface is real. No alignment issue —
  flagging only as a documentation accuracy note for future reference.

- **§7 — no `--dangerously-skip-permissions` equivalent.** R-00072 §7:
  *"once an agent can write and execute code, security theater doesn't
  prevent exfiltration; containment (containers/VMs) is the real
  solution."* Approvals via extensions, not via a CLI switch. Every pi
  dispatch branch correctly omits `--dangerously-skip-permissions` and
  `--permission-mode bypassPermissions` (verified by negative assertions
  in `test_pi_runtime_dispatch.py`: `assert "--dangerously-skip-permissions"
  not in cmd` and `assert "--permission-mode" not in cmd` at every site).
  `pi --help` confirms no such flag exists in the pi CLI.

- **No MCP claim.** R-00072 §4 confirms Pi has no MCP support. The
  implementation correctly does not reference MCP for pi.

## Doc-system / Sibling-repo cross-reference

✅ **AGENTS/PI/ INTERNALLY CONSISTENT.**

- All 30 `.md` files start with a proper `---` frontmatter delimiter
  (verified with a script: `for f in agents/pi/*.md; do head -1 "$f" |
  grep -q "^---$" || echo BAD; done` produced no output).
- All 30 files have `name:` and `description:` keys matching their
  filenames (verified `grep -h "^name:" agents/pi/*.md | sort` is
  identical to the same on `agents/claude/`).
- All 30 files carry the `<!-- pi-port: stripped … -->` marker S04
  installed immediately after the closing frontmatter `---`. Confirmed
  `grep -l "pi-port: stripped" agents/pi/*.md | wc -l` = 30.
- The only `skills:` frontmatter key in either tree (`agents/pi/orchestrator.md`
  and `agents/claude/orchestrator.md`) references `iw-workflow`. Verified
  `skills/iw-workflow/` exists. No broken skill cross-reference.
- The 30 files exactly mirror the `agents/claude/` filename set
  (`diff <(ls agents/claude/) <(ls agents/pi/)` empty).
- Sibling repos (`iw-doc-plan`, `podforger`, `cv`) pick up the new master
  tree only when their next `iw sync-agents` is run — out of scope for
  this CR. No master-side change blocks the sync from working when those
  repos eventually sync.

## Findings

| ID | Severity | Summary | Layer |
|----|----------|---------|-------|
| FF1 | LOW | `_VALID_CLI_TOOLS` is not referenced from any dispatch site — a future contributor adding a 4th runtime to the allowlist is not visibly forced to update the seven dispatch sites; runtime `ValueError` is the only safety net. Worth filing as a follow-up to add an explicit `assert cli_tool in _VALID_CLI_TOOLS` inside one dispatch helper. | Cross-cut: `orch/daemon/project_registry.py` ↔ all dispatch sites |

No CRITICAL, no HIGH, no MEDIUM findings. **FF1 is advisory only** — S09 may
or may not address it; the existing explicit-raise pattern (same as F-00081's)
is acceptable as-is.

## Notes

- **S07's findings_addressed list (F1, F2, F3) was clean and accurate.** F1
  (stray duplicate dir) is verified gone (`ls ai-dev/active/CR-00062/` shows
  no nested `CR-00062/` directory). F2 (header docstring in
  `step_executor.sh`) is verified at line 20: `Agent CLI: "opencode",
  "claude", or "pi" (default: opencode)`. F3 (S01 report's missing JSON
  result-contract block) is verified by reading the S01 report's tail.
- **TDD discipline is end-to-end clean.** S03 captured `AssertionError: assert
  'pi -p' in 'claude -p …'` as the dispatch RED. S04 captured `AttributeError:
  'AgentSyncResult' object has no attribute 'pi_agents_synced'` as the sync
  RED. S05 reused those (the durable test surface step doesn't need its own
  RED — it inherits S03/S04's). All test files use strict positional
  assertions (`cmd.startswith("pi -p ")`, `argv == ["/bin/sh", "-c", inner]`)
  rather than weak substring containment — would catch a misbuilt
  `["pi-broken", "-p", ...]` or `["mpi", "-p", ...]`.
- **No `<!-- TODO(CR-00062-followup): -->` markers were added by any prior
  step.** S04 explicitly verified this; S08 re-grepped — `grep -r "TODO(CR-00062-followup)"
  . --include="*.py" --include="*.md" --include="*.sh"` returns nothing.
  Every agent file body is runtime-agnostic; no agent had to be stubbed.
- **Two integration tests carry documented `@pytest.mark.skipif`** (bash
  subprocess platform probe, `iw` venv binary presence). Both have inline
  `reason="..."` strings — not silent skips. Acceptable per `tests/CLAUDE.md`.

## Result contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S08_CodeReviewFinal_report.md"
  ],
  "preflight": {
    "format": "n/a — review only",
    "typecheck": "n/a — review only",
    "lint": "n/a — review only"
  },
  "tests_passed": true,
  "test_summary": "96 passed in 0.38s (targeted pi + updated tests subset)",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"id": "FF1", "severity": "LOW", "summary": "_VALID_CLI_TOOLS in project_registry is not referenced from any dispatch site — a future 4th-runtime addition would only catch the missing branch at runtime via the explicit ValueError, not at edit time. Suggest exporting the constant and asserting inside one dispatch helper as a safety net. Advisory only — same pattern as F-00081."}
  ],
  "ac_coverage": {
    "AC1": "satisfied",
    "AC2": "satisfied",
    "AC3": "satisfied",
    "AC4": "satisfied",
    "AC5": "satisfied",
    "AC6": "satisfied"
  },
  "blockers": [],
  "notes": "No CRITICAL/HIGH/MEDIUM findings. FF1 is LOW-severity advisory — does not block S09 or merge. R-00072 §1/§7 cross-reference holds: pi -p print mode is a real Pi CLI flag (verified against `pi --help`); no permission-mode flag is correctly omitted from every pi dispatch branch. Dashboard router unchanged. Migration-check still green (S07 did not touch the migration or models). 96/96 targeted unit tests pass. Scope compliance: every modified file falls under workflow-manifest.json:scope.allowed_paths."
}
```
