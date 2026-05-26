# I-00114_S03_Backend_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step**: S03
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document.
- `ai-dev/active/I-00114/reports/I-00114_S02_Backend_report.md` — confirms the guard wrapper's entry-point shape (your wire-up must match exactly).
- `orch/daemon/batch_manager.py:2113-2144` — `_build_initial_command`. Lines 2135-2144 are the pi branch you must modify.
- `orch/daemon/batch_manager.py:2122-2123` — the explicit "Keep in sync with `_build_fix_inner_command`" comment that pairs the two builders.
- `orch/daemon/fix_cycle.py` — locate `_build_fix_inner_command`, find the pi branch, mirror the same change.
- `orch/CLAUDE.md` and `orch/daemon/CLAUDE.md` (if present) — daemon conventions.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S03_Backend_report.md` — Step report.

## Context

You are implementing **S03: wire the narration guard into the daemon's pi launch path.** S01 added the `iw daemon-event` CLI, S02 built `executor/pi_narration_guard.py`. Your job is the surgical change that makes the daemon use the guard for every pi launch.

This is a small, isolated diff. The hard part is correctness of the shell quoting and keeping the two builders (`_build_initial_command`, `_build_fix_inner_command`) in lock-step — there is a comment in the source that explicitly calls out their pairing, and prior drift between them caused I-00074. Do not let that recur.

## Requirements

### 1. Modify `_build_initial_command` (pi branch) in `orch/daemon/batch_manager.py`

The current pi branch returns:

```python
return (
    f'pi -p "$(cat {prompt_file})" --model {resolved_model} '
    f"{_pi_worktree_isolation_args(worktree_path)}"
)
```

Change it to invoke the guard wrapper. The guard's positional `--` separator means the original pi argv must appear after it, untouched:

```python
return (
    f"python {GUARD_SCRIPT} "
    f"--item-id {shlex.quote(item_id)} --step-id {shlex.quote(step_id)} "
    f"--max-reprompts 5 -- "
    f'pi -p "$(cat {prompt_file})" --model {resolved_model} '
    f"{_pi_worktree_isolation_args(worktree_path)}"
)
```

(Sketch — read S02's report for the actual flag names and resolve `GUARD_SCRIPT` to an absolute or worktree-relative path; do not hardcode `/home/sergiog/...`.)

- The `item_id` and `step_id` must be added to `_build_initial_command`'s signature if they aren't there already; check upstream callers and thread the values through. Search for every caller and update the call sites.
- opencode and claude branches: **untouched**. AC4.

### 2. Mirror the change in `_build_fix_inner_command` in `orch/daemon/fix_cycle.py`

Same modification — wrap the pi invocation with the guard. Use the same `GUARD_SCRIPT` resolution, same `--max-reprompts 5`. The `# Keep in sync with `_build_initial_command`` comment at `batch_manager.py:2122-2123` exists precisely because these two builders must agree shape-for-shape; if you change one without the other, fix-cycle re-launches skip the guard and the bug recurs in fix cycles only.

### 3. GUARD_SCRIPT path resolution

The path must be:

- **Worktree-relative**, i.e. the literal string `executor/pi_narration_guard.py`. The daemon launches the wrapper command with `cwd=worktree_path` (see `subprocess.Popen(..., cwd=worktree_path, ...)` in `batch_manager.py`), so the worktree-relative path resolves correctly inside every worktree without baking in a host-specific absolute path. NEVER hardcode `/home/sergiog/...` or any other absolute prefix.
- **A single constant defined once and reused** by both `_build_initial_command` and `_build_fix_inner_command`. Put the constant near the existing `_PI_WORKTREE_PIN_TEXT` constant in `batch_manager.py` and import it from `fix_cycle.py`, OR (cleaner) extract a tiny helper `_pi_command_with_guard(item_id, step_id, prompt_file, resolved_model, worktree_path)` in a shared module that both callers use. Pick whichever matches existing helper structure best — there is precedent for both. Document your choice in the step report.

### 4. Do NOT modify `_build_qv_direct_command`

QV-gate steps don't use pi; they use the qv-wrap.sh shell wrapper. Leave that path alone.

### 5. No regression in opencode / claude

Specifically assert by reading the code that the `if cli_tool == "opencode"` and `if cli_tool == "claude"` branches of both builders are byte-for-byte unchanged. AC4.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: in `tests/unit/test_daemon_command_builders.py` (or the closest existing file — search for tests covering `_build_initial_command`; create the file if none exists), write `test_pi_branch_invokes_narration_guard`: assert the returned command starts with `python ` (or whatever guard invocation is used) and includes `pi_narration_guard` and `-- pi -p`. Run it — must fail (today's output is bare `pi -p ...`).
2. **GREEN**: apply the change to both builders.
3. **REFACTOR**: extract shared helper if duplication justifies it.

Also add `test_opencode_branch_unchanged` and `test_claude_branch_unchanged` — both must pass before AND after your change (regression pin for AC4).

Record RED line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass on modified files.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_daemon_command_builders.py -v
```

(or whichever file holds your tests). Do NOT run `make test-unit` here.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Backend",
  "work_item": "I-00114",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "tests/unit/test_daemon_command_builders.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_daemon_command_builders.py::test_pi_branch_invokes_narration_guard — AssertionError: assert 'pi_narration_guard' in 'pi -p \"$(cat ...)\" --model ...'",
  "blockers": [],
  "notes": "Document the GUARD_SCRIPT location decision (constant vs helper) and confirm opencode/claude branches are byte-identical."
}
```
