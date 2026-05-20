"""Stub Pi RPC binary for F-00087 integration tests.

Behaviour:
- Reads JSONL commands from stdin.
- For each {"type": "prompt", "message": <text>}:
    - If message contains "trigger-approval":
        1. Emits agent_start
        2. Emits extension_ui_request with id="iw-chat-approvals.test-001"
        3. Waits for extension_ui_response on stdin
        4. Emits tool_execution_start / tool_execution_end based on the response value
        5. Emits agent_end
        6. Emits {"type":"response","ok":true}
    - Otherwise (normal prompt):
        1. Emits agent_start
        2. Emits message_update (text_delta) — the model's reply
        3. Emits agent_end
        4. Emits {"type":"response","ok":true}
- For {"type": "abort"}:
    1. Emits agent_end with abort marker
    2. Emits {"type":"response","ok":true}
- For {"type": "get_messages"}:
    1. Emits {"type":"response","ok":true,"messages":[]}
- For {"type": "set_model"}:
    1. Emits {"type":"response","ok":true}
- For {"type": "extension_ui_response", "id": ..., "value": ...}:
    The _approval_queue is populated; the waiting prompt handler reads it.

Usage (by the bash wrapper):
    exec python3 _pi_stub.py --mode rpc --session-dir <dir> [...]
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from typing import Any

_stdout_lock = threading.Lock()


def _emit(event: dict[str, Any]) -> None:
    """Write a JSONL event to stdout and flush atomically (thread-safe)."""
    line = json.dumps(event) + "\n"
    with _stdout_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


# Queue for extension_ui_response events arriving on stdin while a prompt
# handler is waiting for approval.
_approval_queue: queue.Queue[dict[str, Any]] = queue.Queue()

# Signal: set when a prompt handler is waiting for approval.
_waiting_for_approval = threading.Event()


def _handle_prompt(message: str) -> None:
    """Process a prompt command, emitting the appropriate event sequence."""
    _emit({"type": "agent_start"})

    if "trigger-approval" in message:
        # Emit an extension_ui_request and wait for the approval response.
        _emit(
            {
                "type": "extension_ui_request",
                "id": "iw-chat-approvals.test-001",
                "tool": "bash",
                "args": {"cmd": "rm temp.txt"},
                "question": "Allow bash to run 'rm temp.txt'?",
            }
        )
        _waiting_for_approval.set()
        # Block until the extension_ui_response arrives on stdin.
        try:
            resp = _approval_queue.get(timeout=30)
            approved = resp.get("value", False)
        except queue.Empty:
            approved = False
        _waiting_for_approval.clear()

        if approved:
            _emit({"type": "tool_execution_start", "tool": "bash", "args": {"cmd": "rm temp.txt"}})
            _emit({"type": "tool_execution_end", "tool": "bash", "result": "ok"})
        else:
            _emit({"type": "tool_execution_end", "tool": "bash", "result": "denied"})
    else:
        # Normal prompt: emit a streaming text response.
        _emit(
            {
                "type": "message_update",
                "assistantMessageEvent": {
                    "type": "text_delta",
                    "delta": f"Echo: {message}",
                },
            }
        )

    _emit({"type": "agent_end"})
    _emit({"type": "response", "ok": True})


def main() -> None:
    """Read commands from stdin and dispatch.

    Prompt handlers run in worker threads so they can block waiting for
    extension_ui_response while the main loop continues reading stdin.
    Without this, an "approval flow" prompt would deadlock: the prompt
    handler blocks waiting for the response, but the response can only
    be parsed after stdin is read again.

    Ignores CLI args (``--mode rpc --session-dir <dir>`` etc.).
    """
    # Use stdout in line-buffered mode (default for stdout when connected
    # to a pipe is block-buffered, which would delay events).
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            continue

        cmd_type = cmd.get("type", "")

        if cmd_type == "prompt":
            # Run the prompt handler in a daemon thread so the main loop
            # can keep reading stdin (notably for extension_ui_response).
            t = threading.Thread(
                target=_handle_prompt,
                args=(cmd.get("message", ""),),
                daemon=True,
            )
            t.start()

        elif cmd_type == "abort":
            _emit({"type": "agent_end", "aborted": True})
            _emit({"type": "response", "ok": True})

        elif cmd_type == "get_messages":
            _emit({"type": "response", "ok": True, "messages": []})

        elif cmd_type == "set_model":
            _emit({"type": "response", "ok": True})

        elif cmd_type == "extension_ui_response":
            # Route the response to the waiting prompt handler.
            _approval_queue.put(cmd)

        else:
            # Unknown command — respond ok to keep the protocol moving.
            _emit({"type": "response", "ok": True})


if __name__ == "__main__":
    main()
