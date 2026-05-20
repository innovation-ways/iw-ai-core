# CR-00066_S03_Backend_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- `orch/db/models.py` — `StepRun` (new columns), `AgentRuntimeOption`
- `orch/daemon/step_monitor.py` — existing poll loop + session file resolution (CR-00065)
- `orch/daemon/session_reader.py` — JSONL reader (CR-00065); reuse for token extraction

## Task

Extend `step_monitor.py` to extract token counts from the pi session JSONL and update `context_tokens_peak` and `context_tokens_last` on each poll cycle.

---

### Changes to `orch/daemon/step_monitor.py`

Add a helper `_extract_latest_tokens(session_file: str) -> int | None` that:
1. Opens the session `.jsonl` file.
2. Iterates lines in reverse order (from the end) looking for the most recent `type == "message"` entry where `message.role == "assistant"` and `message.usage` is present.
3. Returns `message.usage.get("totalTokens")` as an `int`, or `None` if not found.
4. Handles: file not found, empty file, malformed JSON lines — all return `None` silently.

In the main poll loop, for each `running` pi `StepRun` where `session_file is not None`:
```python
latest_tokens = _extract_latest_tokens(run.session_file)
if latest_tokens is not None:
    run.context_tokens_last = latest_tokens
    if run.context_tokens_peak is None or latest_tokens > run.context_tokens_peak:
        run.context_tokens_peak = latest_tokens
    # commit is handled by the existing poll cycle DB flush
```

**Important**:
- `context_tokens_peak` NEVER decreases — it is the all-time high-water mark.
- `context_tokens_last` can decrease after a compaction event (this is correct behaviour).
- Wrap in try/except — no filesystem error should crash the poll loop.
- Only run for `cli_tool == "pi"` runs with a non-NULL `session_file`.

---

### TDD (RED → GREEN → REFACTOR)

Write tests in `tests/unit/test_step_monitor_token_poll.py`:

```python
def test_extract_latest_tokens_from_valid_jsonl():
    """Returns totalTokens from the most recent assistant message with usage."""

def test_extract_latest_tokens_ignores_non_assistant_entries():
    """Skips user/toolResult entries; finds the last assistant entry."""

def test_extract_latest_tokens_returns_none_for_missing_usage():
    """Returns None if no assistant message has a usage field."""

def test_extract_latest_tokens_returns_none_for_empty_file():
    """Returns None for an empty file without raising."""

def test_extract_latest_tokens_returns_none_for_missing_file():
    """Returns None for a non-existent path without raising."""

def test_peak_never_decreases():
    """When context_tokens_last drops (post-compaction), context_tokens_peak stays at high-water mark."""
```

Run RED, then implement, then GREEN.

### Quality gates

```bash
make format
make lint
make typecheck
make test-unit
```

## Output Files

- `orch/daemon/step_monitor.py` — updated with token extraction
- `tests/unit/test_step_monitor_token_poll.py` — new unit tests

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S03 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S03_Backend_report.md
```

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00066",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/step_monitor.py",
    "tests/unit/test_step_monitor_token_poll.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "6 new unit tests pass",
  "blockers": [],
  "notes": ""
}
```
