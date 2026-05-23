# I-00105_S07_Backend_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S07
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Do NOT run any command that changes Docker container/volume/network state.
Testcontainers via pytest fixtures are the only exception; read-only docker
introspection and `./ai-core.sh` / `make` targets are allowed. The executor
launches and supervises agent runtimes — **do not** add code that kills,
restarts, or removes any container. STOP and raise a blocker if your task seems
to need a prohibited command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migration** and no schema change. If your work appears to
need one, STOP and raise a blocker.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design document (read §Root Cause Analysis causes 2, 3 & 4, and AC2 & AC4).
- `docs/research/R-00078-agent-tool-output-context-capping.md` — **MUST read** — findings "The correct pattern is cap + spill to file, not in-place truncation", "Production harness caps", and "Proactive compaction". The Primary Recommendation specifies the approach.
- `executor/step_executor.sh` — the step launcher (`CLI_TOOL` opencode/claude/pi, around lines 38 / 130+).
- `executor/CLAUDE.md` — executor conventions.
- `orch/config.py` — config loader (`.env`-backed).

## Output Files

- `executor/step_executor.sh` (modified) and/or new helper script(s) under `executor/` — the cap/spill and overflow-detection helpers MUST live under `executor/` (or another path inside `scope.allowed_paths`), not elsewhere in `orch/`, so they stay within scope
- `orch/config.py` (modified — new config vars)
- `tests/...` — cap-helper and overflow-detection tests
- `docs/IW_AI_Core_Daemon_Design.md` (modified — document the cap, if appropriate)
- `ai-dev/work/I-00105/reports/I-00105_S07_Backend_report.md` — step report.

## Context

You are implementing three executor-side fixes: the **tool-output cap with disk
spill** (AC2, root-cause cause 2), **compaction-threshold calibration** (root
cause 3), and **context-overflow detection → clean step-fail** (AC4, root cause
4). Per R-00078, the per-call cap that some runtimes apply does not bound
*cumulative* context; the executor must add a cap of its own, and it must spill
(not silently truncate). Causes 1–3 only reduce the *likelihood* of overflow —
AC4 ensures an overflow that still happens fails the step cleanly rather than
limping on in a degraded state.

## Requirements

### 1. Per-tool-output cap with disk spill (AC2)

Cap each tool result the executor mediates at a **configurable byte budget**
(R-00078 Primary Recommendation: a ~25 KB starting point, in the order of
magnitude of Claude Code's 30 KB Bash cap). When a result exceeds the cap:

- **Write the full, unmodified result to a file** under the step work directory
  (e.g. `ai-dev/work/<ITEM>/.tool-cache/<step>-<n>.txt`).
- Return to the agent a **head + tail preview** PLUS the **file path** and the
  total size, so the agent can `grep`/read the rest on demand.
- This is **recoverability** — per R-00078 and the Codex #14206 finding, an
  in-place head/tail snippet with an inline `…truncated…` marker and *no spill
  file* is forbidden ("preserves neither exactness nor recoverability").
- Under-cap results pass through completely unchanged.

Scope the interception to what the executor can mediate (it already shells out
for the runtime). For a runtime's own built-in file tools that the executor
cannot intercept, set that runtime's native cap env var as low as it allows
(e.g. export `BASH_MAX_OUTPUT_LENGTH` for the `claude` runtime) and document
the limitation in the report. Do not over-claim coverage you cannot deliver.

### 2. Compaction-threshold calibration (root cause 3)

Calibrate proactive compaction to fire at **~75% of the effective budget**
(`window − max_output − safety_buffer`), not at the nominal window. Where the
runtime exposes a compaction-threshold setting, set it via env var / config at
launch in `step_executor.sh`. Where it does not, document what is and is not
controllable. Reuse the effective-budget reasoning from S03 — do not duplicate
a second, divergent formula.

### 3. Context-overflow detection → clean step-fail (AC4)

When the runtime overflows the model's context window it returns
`400 invalid_request_error: ... context window exceeds limit` (or a
runtime-specific equivalent), then auto-compacts and *continues* in a degraded
state — it never calls `step-done` and leaves junk artifacts behind. The
executor must catch this:

- **Detect** the overflow signature in the runtime's captured output/log —
  match a small, documented set of signatures (e.g. `context window exceeds
  limit`, `context_length_exceeded`, an `invalid_request_error` paired with a
  context-length message). Check R-00078 and the runtime docs for the exact
  strings each runtime (`opencode` / `claude` / `pi`) emits.
- When the signature is seen **and the step did not complete cleanly** (no
  `step-done`), **finalize the step as a clean failure** with a blocker/reason
  that names the context overflow as the cause. Use the step-failure path
  `step_executor.sh` already has — inspect the script to find how a step is
  failed when its agent exits without `step-done` (e.g. `iw step-fail` for the
  running item/step). The result must be a clearly-attributed `step-fail`, not a
  silent stall or a generic timeout.
- Do **not** override a step that *did* reach a clean `step-done` — only a
  non-completed, overflowed step is failed.
- At minimum, detect-and-fail after the runtime exits; aborting the degraded
  run as soon as the signature appears is preferred where the executor can do
  it cleanly.
- Put the signature-matching logic in a unit-testable helper (prefer a small
  Python helper over inline `grep` — see Requirement 5). Overflow signatures
  are error-string constants — keep them in the helper, not in `orch/config.py`.

This is root cause 4: causes 1–3 make overflow rarer; this makes the
unavoidable residual case fail honestly.

### 4. Configuration

Put the cap byte budget, the safety buffer, and the compaction-threshold
fraction in `orch/config.py` as documented config vars with sensible defaults
(follow the existing `IW_CORE_*` naming and the "never hardcode" rule in
`CLAUDE.md`). Defaults must be safe out of the box.

### 5. Tests

If you extract a cap/spill helper (recommended — a shell function or a small
script is hard to unit-test; a Python helper is testable), cover it: oversized
input → spill file created with the **full** content + a preview returned with
the path; under-cap input → returned unchanged. Assert specific values (file
exists, file content equals the original, preview contains head and tail).

Cover the **context-overflow-detection helper** too: runtime output carrying an
overflow signature → detected, returning a clear blocker message; clean output
→ not detected. Assert the specific blocker text / boolean value, not shape.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `executor/CLAUDE.md`. Never hardcode
ports/paths/credentials — use config. Bash in `executor/` must be robust
(`set -euo pipefail` style as the existing scripts use).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete, run in order and fix anything reported:
1. `make format`  2. `make typecheck`  3. `make lint` (lint includes a bash/JS check)

Also run `make test-assertions` if you added tests.

## Test Verification (NON-NEGOTIABLE)

Run only your own new/affected tests — NOT the full suite:
```bash
uv run pytest tests/<your cap-helper test files> -v
```
Do not report `tests_passed: true` unless they pass.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "backend-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/... — <RED line>  (or 'n/a — <reason>')",
  "blockers": [],
  "notes": "Cap default chosen; spill file location; which runtimes' compaction thresholds are controllable vs not; new IW_CORE_* config vars; overflow-detection signatures + step-fail mechanism used."
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S07`
On success: write the report, then
`uv run iw step-done I-00105 --step S07 --report ai-dev/work/I-00105/reports/I-00105_S07_Backend_report.md`
On failure: `uv run iw step-fail I-00105 --step S07 --reason "<brief reason>"`
You MUST call `step-done` (with `--report`) or `step-fail` before exiting.
