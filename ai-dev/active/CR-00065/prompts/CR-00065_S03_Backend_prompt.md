# CR-00065_S03_Backend_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT apply migrations. The S01 migration file has been generated; the daemon applies it.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `orch/db/models.py` — StepRun model (session_file column added in S01)
- `orch/daemon/step_monitor.py` — existing PID-alive polling logic
- `orch/daemon/batch_manager.py` — step launch, StepRun creation (~line 1500)

## Task

Implement two backend pieces: (1) resolve and persist the pi session file path in `step_monitor`, and (2) a new `session_reader` module that reads and renders session content for any runtime.

---

### Part 1: `orch/daemon/step_monitor.py` — resolve pi session file

**Context**: `step_monitor` runs every poll cycle. It queries active `StepRun` rows and checks PID liveness. For `pi` runs, it now also resolves the session file path and stores it if not yet set.

**Pi session slug derivation**: Pi derives the session directory slug from the working directory by replacing each `/` with `-`, then wrapping with leading and trailing `-`:
```
/home/user/.../CR-00065  →  --home-user-...-CR-00065--
```
The full session directory is: `~/.pi/agent/sessions/{slug}/`

**Changes to `step_monitor.py`**:

1. Add a helper `_resolve_pi_session_file(run: StepRun) -> str | None` that:
   - Returns `None` if `run.cli_tool != "pi"` or `run.worktree_path is None`
   - Constructs the slug from `run.worktree_path`: `worktree_path.replace("/", "-")` (the result already starts with `-` on Linux absolute paths, so no extra wrapping needed — verify against actual paths in `~/.pi/agent/sessions/`)
   - Locates `~/.pi/agent/sessions/{slug}/`
   - Scans for `.jsonl` files in that directory with an mtime >= `run.started_at` (or created after the step started)
   - Returns the path of the most recently modified `.jsonl` file found, or `None` if none yet exist

2. In the main poll loop, after confirming a `pi` run is alive (or on the poll that first sees it as `running`), if `run.session_file is None`:
   - Call `_resolve_pi_session_file(run)`
   - If a path is found, set `run.session_file = path` and commit

**Important**: Do not crash the poll loop on any file system error — wrap the resolution in a try/except and log a warning.

---

### Part 2: `orch/daemon/session_reader.py` — new module

Create `orch/daemon/session_reader.py` with a single public function:

```python
def read_session_content(run: StepRun, max_chars: int = 50_000) -> list[dict]:
    """Return a list of rendered segment dicts for the given StepRun.

    Each segment has keys:
      - type: "assistant" | "tool_call" | "tool_result" | "thinking" | "error" | "compaction" | "user"
      - text: str — human-readable content
      - collapsible: bool — True for thinking blocks and long tool results

    For pi runs: parse session_file JSONL.
    For claude/opencode runs: read log_file (or log_content from DB).
    Returns [] if no content is available.
    """
```

**Pi JSONL parsing rules**:
- Each line is a JSON object with a `type` field.
- `type == "message"`: check `message.role`:
  - `"assistant"`: iterate `message.content` items:
    - `type == "text"` → segment type `"assistant"`, text = content text (trim to max 2000 chars)
    - `type == "thinking"` → segment type `"thinking"`, text = first 200 chars of thinking + "…", `collapsible: True`
    - `type == "toolCall"` → segment type `"tool_call"`, text = `"{name}: {json.dumps(arguments)[:200]}"`, `collapsible: False`
  - `"toolResult"`: first `content` item's `text` → segment type `"tool_result"`, text = first 500 chars, `collapsible: True`
  - `"user"`: skip (these are the original prompt injections)
- `type == "compaction"` → segment type `"compaction"`, text = `"— context compacted —"`
- `type == "message"` with `stopReason == "error"` → segment type `"error"`, text = `message.errorMessage`
- Skip any lines that fail JSON parsing (log a debug warning)

**Claude/OpenCode log rendering**:
- If `run.log_content` is set: use it directly, wrap in a single segment `{"type": "log", "text": log_content, "collapsible": False}`
- Else if `run.log_file` is set and file exists: read last `max_chars` characters, same wrapping
- Else: return `[{"type": "error", "text": "No log content available", "collapsible": False}]`

---

### TDD (RED → GREEN → REFACTOR)

**RED**: Write tests first in `tests/unit/test_session_reader.py`:

```python
def test_pi_jsonl_parses_assistant_message():
    """Given a JSONL with one assistant text entry, read_session_content returns one 'assistant' segment."""

def test_pi_jsonl_thinking_is_collapsible():
    """Given a thinking block, segment has collapsible=True and text is truncated."""

def test_pi_jsonl_tool_call_segment():
    """Given a toolCall entry, segment type is 'tool_call' with name:args summary."""

def test_pi_jsonl_compaction_marker():
    """Given a compaction entry, segment type is 'compaction'."""

def test_pi_jsonl_error_entry():
    """Given a message with stopReason=error and errorMessage, segment type is 'error'."""

def test_claude_run_uses_log_content():
    """Given cli_tool='claude' and log_content set, returns single 'log' segment."""

def test_empty_run_returns_empty_list():
    """Given no session_file, no log_file, no log_content, returns []."""
```

Run to confirm they fail (RED), then implement `session_reader.py` to make them pass (GREEN).

### Quality gates

```bash
make format
make lint
make typecheck
make test-unit
```

All must pass.

## Output Files

- `orch/daemon/step_monitor.py` — updated with pi session file resolution
- `orch/daemon/session_reader.py` — new module
- `tests/unit/test_session_reader.py` — new unit tests

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S03 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S03_Backend_report.md
```

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00065",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/step_monitor.py",
    "orch/daemon/session_reader.py",
    "tests/unit/test_session_reader.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "7 new unit tests pass",
  "blockers": [],
  "notes": ""
}
```
