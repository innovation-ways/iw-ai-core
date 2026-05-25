# I-00114_S02_Backend_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step**: S02
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document (read in full).
- `ai-dev/active/I-00114/reports/I-00114_S01_Backend_report.md` — confirms the `iw daemon-event` CLI surface you must call.
- `executor/CLAUDE.md` — executor conventions (no docker, no alembic, log to stderr).
- `executor/step_executor.sh` lines 281-292 — the existing step-done fallback path (different launch path, but you'll mirror its post-exit logic).
- `executor/step_executor.sh` lines 250-275 — the context-overflow post-exit guard (closest prior art for "do something to the pi log after it exits"). Read it; your guard has the same shape but a different decision.
- `orch/daemon/batch_manager.py:2090-2144` — `_pi_worktree_isolation_args` and `_build_initial_command` pi branch. You must understand the exact pi command shape because the guard will invoke pi internally.
- `pi --help` — the `--continue` / `--session` flags you will use for reprompts.
- Live evidence (read-only) for shape verification: any session JSONL under `/home/sergiog/.pi/agent/sessions/--*-iw-ai-core-.worktrees-F-00089--/` to see real `[thinking, text]` and `[thinking, toolCall]` patterns.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S02_Backend_report.md` — Step report.

## Context

You are implementing **S02: the pi narration-exit guard wrapper** — the heart of this Incident. The guard is a Python script (`executor/pi_narration_guard.py`) that wraps `pi` invocation and converts the "agent narrated then quit" failure mode into a transparent in-place reprompt.

Python (not bash) because the JSONL parsing, JSON metadata building, and `iw -j item-status` parsing are noticeably cleaner. Match the style of `executor/scope_gate.py` and `executor/context_overflow.py` (existing Python helpers in `executor/`).

The guard must be invokable from a shell command line because the daemon launches everything via `subprocess.Popen(shell=True)`. The simplest entry shape:

```bash
python executor/pi_narration_guard.py \
    --item-id I-00114 --step-id S03 \
    --max-reprompts 5 \
    -- pi -p "$(cat .tmp/I-00114_S03.prompt)" --model openai-codex/gpt-5.3-codex --no-context-files --append-system-prompt CLAUDE.md ...
```

(The `--` separates guard args from the pi command. Subsequent reprompts swap `-p "$(cat ...prompt)"` for `--continue "<reprompt msg>"`.)

## Requirements

### 1. Create `executor/pi_narration_guard.py`

The guard is a single script with one entry-point. Decompose internally into testable functions:

```python
def parse_args(argv: list[str]) -> GuardArgs: ...
def run_pi(pi_cmd: list[str], cwd: str | None = None) -> int: ...
def is_step_still_running(item_id: str, step_id: str) -> bool: ...
def find_latest_pi_session(cwd: str) -> Path | None: ...
def classify_last_assistant(session_path: Path) -> NarrationVerdict: ...
def build_reprompt_message(last_text: str | None, attempt: int, cap: int) -> str: ...
def emit_narration_event(item_id: str, step_id: str, attempt: int, cap: int, last_text: str | None) -> None: ...
def main(argv: list[str]) -> int: ...
```

The decomposition is required — S04 tests will exercise these helpers directly.

### 2. Detection — hybrid (DB signal as gate, JSONL telemetry only)

The guard runs the pi command. After pi exits:

- If `pi_exit_code != 0`: return `pi_exit_code` immediately. No reprompt. (Real failure — let the daemon's existing path handle it.)
- If `pi_exit_code == 0`: query DB via `uv run iw -j item-status <item_id>`. Find the step row matching `step_id`.
  - If the step's `status != "in_progress"` (i.e., `iw step-done` or `iw step-fail` was called — status is `completed` or `failed`): return 0 immediately. The agent closed the step properly. **No reprompt, no event.**
  - If the step's `status == "in_progress"`: this is a narration-exit. Proceed to reprompt logic.

JSONL inspection is for telemetry only (capturing the agent's last text into the event metadata). The reprompt loop is driven entirely by the DB signal — if the JSONL parse fails or the session file is missing, log a warning, record `last_assistant_text=null`, and continue with the reprompt cycle. **Never block on JSONL parse failure.**

### 3. JSONL classifier

`classify_last_assistant(session_path)` reads the most recent assistant message from the pi session JSONL and returns:

- `NarrationVerdict.NARRATION` — last assistant message contains only `[thinking?, text]` blocks (no `toolCall`).
- `NarrationVerdict.TOOL_CALL` — last assistant message contains a `toolCall` block.
- `NarrationVerdict.NO_ASSISTANT` — no assistant message found at all.
- `NarrationVerdict.PARSE_ERROR` — JSONL malformed / missing file.

The classifier is informational only. The DB signal (above) is what gates the reprompt decision. The verdict is captured in `daemon_events.metadata` for diagnosis.

### 4. Session discovery

`find_latest_pi_session(cwd)` resolves the pi session dir by transforming `cwd` the way pi itself does. From the evidence file path:

```
/home/sergiog/.pi/agent/sessions/--home-sergiog-dev-iw-doc-plan-main-iw-ai-core-.worktrees-F-00089--/
```

the transform is: replace `/` with `-` (with `--` prefix/suffix). Confirm this empirically against an existing session before hardcoding — use `pi --help` and the actual `/home/sergiog/.pi/agent/sessions/` directory contents to verify the exact rule. The most recent JSONL in that dir is the current session.

### 5. Reprompt loop (cap = 5)

For attempt `n` in `1..max_reprompts`:

1. Inspect JSONL → harvest last assistant text and verdict (telemetry).
2. Emit `step_narration_exit` event via `iw daemon-event` with metadata `{"step_id": <S>, "reprompt_attempt": n, "max_reprompts": 5, "last_assistant_text": <truncated to e.g. 500 chars or null>, "verdict": <enum name>}`.
3. Build the reprompt message — short, direct, references the agent's narrated intent. Example: `"Your previous message announced an action but did not execute it. Continue executing tools now until the step is genuinely complete; finish with `iw step-done --report …` or `iw step-fail --reason ...`."` If `last_assistant_text` is available, prepend a one-line quote so the agent has context (truncate to 300 chars).
4. Launch pi with `pi --continue "<reprompt message>" --model … <other args from original>`. The model and isolation args must be carried over from the original command (preserve everything after `-p` was replaced with `--continue`).
5. After the new pi exits: if `exit_code != 0`, return it. If `exit_code == 0` and step status is no longer `in_progress`, return 0 (success — agent closed the step on reprompt). Otherwise loop.

After the loop body executes `max_reprompts` times without the step closing, return the last pi exit code (typically 0). The daemon's existing `_handle_crashed` path fires once on the dead PID. This satisfies AC2.

### 6. Logging

Use stderr (`print(..., file=sys.stderr)`) for all guard log lines so they merge with the daemon-captured log file. Prefix lines with `[narration-guard]` for searchability. Match `executor/CLAUDE.md`'s "log to stderr" convention.

### 7. NEVER

- NEVER write directly to the DB. Always go through `iw daemon-event`.
- NEVER run docker / alembic from this script.
- NEVER use anything other than `subprocess.run` / `subprocess.Popen` from the stdlib (no new dependencies).
- NEVER swallow non-zero pi exit codes silently.

## TDD Requirement

Red-Green-Refactor. Because S04 will be the comprehensive test step, your S02 RED should be one small unit test inside `tests/unit/test_pi_narration_guard.py` covering the JSONL classifier (the easiest pure function to test):

1. **RED**: write `test_classify_narration_shape_text_only_returns_NARRATION` with a hand-written JSONL fixture. Run it — must fail with `ImportError` (module doesn't exist yet).
2. **GREEN**: implement the classifier (+ enough of the module to import).
3. **REFACTOR**: extract any duplication.

S04 will own the wider test suite — your RED is just enough to anchor the structure.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass on `executor/pi_narration_guard.py` and `tests/unit/test_pi_narration_guard.py`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_pi_narration_guard.py -v
```

Do NOT run `make test-unit` or `make test-integration` here.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "I-00114",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "executor/pi_narration_guard.py",
    "tests/unit/test_pi_narration_guard.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_pi_narration_guard.py::test_classify_narration_shape_text_only_returns_NARRATION — ImportError: cannot import name 'classify_last_assistant'",
  "blockers": [],
  "notes": "Document the exact session-dir transform rule you verified, and any pi-flag forwarding edge cases."
}
```
