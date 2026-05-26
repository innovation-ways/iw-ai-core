from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path


def _session_slug(cwd: str) -> str:
    normalized = cwd.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return f"--{normalized.replace('/', '-')}--"


def _write_session() -> None:
    base = Path(os.environ["PI_CODING_AGENT_SESSION_DIR"])
    session_dir = base / _session_slug(str(Path.cwd()))
    session_dir.mkdir(parents=True, exist_ok=True)

    counter_file = Path(os.environ["STUB_PI_COUNTER_FILE"])
    count = int(counter_file.read_text(encoding="utf-8")) if counter_file.exists() else 0
    session = session_dir / f"{count:03d}-stub.jsonl"

    kind = os.environ.get("STUB_PI_SESSION_KIND", "narration")
    if kind == "toolcall":
        content = [
            {"type": "thinking", "thinking": "working"},
            {
                "type": "toolCall",
                "toolCall": {
                    "toolName": "bash",
                    "arguments": {"command": "uv run iw step-done ..."},
                },
            },
        ]
    else:
        content = [
            {"type": "thinking", "thinking": "working"},
            {
                "type": "text",
                "text": "I'll now run tests and then call iw step-done with report.",
            },
        ]

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": "assistant",
        "content": content,
    }
    session.write_text(json.dumps(event) + "\n", encoding="utf-8")


def main() -> int:
    counter_file = Path(os.environ["STUB_PI_COUNTER_FILE"])
    count = int(counter_file.read_text(encoding="utf-8")) if counter_file.exists() else 0
    counter_file.write_text(str(count + 1), encoding="utf-8")

    marker_dir = Path(os.environ["STUB_PI_MARKER_DIR"])
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / f"invocation-{count + 1}.txt").write_text("called\n", encoding="utf-8")

    if os.environ.get("STUB_PI_WRITE_SESSION", "1") == "1":
        _write_session()

    return int(os.environ.get("STUB_PI_EXIT_CODE", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
