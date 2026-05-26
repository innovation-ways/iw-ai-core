from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class NarrationVerdict(StrEnum):
    NARRATION = "NARRATION"
    TOOL_CALL = "TOOL_CALL"
    NO_ASSISTANT = "NO_ASSISTANT"
    PARSE_ERROR = "PARSE_ERROR"


@dataclass(frozen=True)
class GuardArgs:
    item_id: str
    step_id: str
    max_reprompts: int
    pi_cmd: list[str]


def parse_args(argv: list[str]) -> GuardArgs:
    parser = argparse.ArgumentParser(description="Wrap pi and reprompt narration exits")
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--max-reprompts", type=int, default=5)
    parser.add_argument("pi_cmd", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)

    pi_cmd = list(ns.pi_cmd)
    if pi_cmd and pi_cmd[0] == "--":
        pi_cmd = pi_cmd[1:]
    if not pi_cmd:
        parser.error("missing pi command after --")
    return GuardArgs(
        item_id=ns.item_id,
        step_id=ns.step_id,
        max_reprompts=ns.max_reprompts,
        pi_cmd=pi_cmd,
    )


def _log(message: str) -> None:
    sys.stderr.write(f"[narration-guard] {message}\n")


def run_pi(pi_cmd: list[str], cwd: str | None = None) -> int:
    _log(f"running: {' '.join(pi_cmd)}")
    proc = subprocess.run(pi_cmd, cwd=cwd, check=False)  # noqa: S603
    return proc.returncode


def _uv_bin() -> str:
    return shutil.which("uv") or "uv"


def get_item_status(item_id: str, step_id: str) -> tuple[bool, str | None]:
    proc = subprocess.run(  # noqa: S603
        [_uv_bin(), "run", "iw", "-j", "item-status", item_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        _log(f"warning: item-status failed ({proc.returncode}): {proc.stderr.strip()}")
        return True, None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        _log("warning: failed to parse item-status JSON")
        return True, None

    project_id = payload.get("project_id")
    steps = payload.get("steps") or []
    for step in steps:
        if step.get("step_id") == step_id:
            return step.get("status") == "in_progress", project_id
    _log(f"warning: step {step_id} not found in item-status output")
    return True, project_id


def _cwd_to_session_slug(cwd: str) -> str:
    normalized = cwd.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return f"--{normalized.replace('/', '-')}--"


def find_latest_pi_session(cwd: str) -> Path | None:
    base = Path(Path.home() / ".pi" / "agent" / "sessions")
    override = (
        Path(os.environ["PI_CODING_AGENT_SESSION_DIR"])
        if "PI_CODING_AGENT_SESSION_DIR" in os.environ
        else None
    )
    if override is not None:
        base = override

    session_dir = base / _cwd_to_session_slug(cwd)
    if not session_dir.is_dir():
        return None
    candidates = [p for p in session_dir.iterdir() if p.is_file() and p.suffix == ".jsonl"]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _extract_last_assistant_blocks(session_path: Path) -> list[dict[str, Any]] | None:
    last_blocks: list[dict[str, Any]] | None = None
    with session_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            is_assistant = event.get("type") == "assistant" or event.get("role") == "assistant"
            if not is_assistant:
                continue
            content = event.get("content")
            if isinstance(content, list):
                last_blocks = [b for b in content if isinstance(b, dict)]
            else:
                last_blocks = []
    return last_blocks


def classify_last_assistant(session_path: Path) -> NarrationVerdict:
    try:
        blocks = _extract_last_assistant_blocks(session_path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return NarrationVerdict.PARSE_ERROR

    if blocks is None:
        return NarrationVerdict.NO_ASSISTANT

    for block in blocks:
        if block.get("type") == "toolCall":
            return NarrationVerdict.TOOL_CALL

    texty = {"text", "thinking"}
    if blocks and all(block.get("type") in texty for block in blocks):
        return NarrationVerdict.NARRATION
    return NarrationVerdict.NO_ASSISTANT


def _last_assistant_text(session_path: Path) -> str | None:
    try:
        blocks = _extract_last_assistant_blocks(session_path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not blocks:
        return None
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    if not parts:
        return None
    return "\n".join(parts).strip() or None


def build_reprompt_message(last_text: str | None, attempt: int, cap: int) -> str:
    base = (
        "Your previous message announced an action but did not execute it. "
        "Continue executing tools now until the step is genuinely complete; "
        "finish with `iw step-done --report …` or `iw step-fail --reason ...`."
    )
    header = f"Reprompt {attempt}/{cap}."
    if not last_text:
        return f"{header} {base}"
    quote = last_text.replace("\n", " ")[:300]
    return f'{header} You said: "{quote}". {base}'


def emit_narration_event(
    project_id: str | None,
    item_id: str,
    step_id: str,
    attempt: int,
    cap: int,
    last_text: str | None,
    verdict: NarrationVerdict = NarrationVerdict.PARSE_ERROR,
) -> None:
    if not project_id:
        _log("warning: skipping narration event (project_id unknown)")
        return

    metadata = {
        "step_id": step_id,
        "reprompt_attempt": attempt,
        "max_reprompts": cap,
        "last_assistant_text": (last_text[:500] if last_text else None),
        "verdict": verdict.name,
    }

    try:
        from orch.db.models import DaemonEvent  # noqa: PLC0415
        from orch.db.session import get_orch_session  # noqa: PLC0415

        with get_orch_session() as session:
            event = DaemonEvent(
                project_id=project_id,
                event_type="step_narration_exit",
                entity_type="work_item",
                entity_id=item_id,
                message="pi exited cleanly while step is still in_progress",
                event_metadata=metadata,
            )
            session.add(event)
            session.flush()
    except Exception as exc:  # pragma: no cover - defensive fallback
        _log(f"warning: failed to emit daemon event: {exc}")


def _to_continue_cmd(original: list[str], reprompt_message: str) -> list[str]:
    cmd = list(original)
    if cmd and cmd[0] == "pi":
        cmd = ["pi", "--continue", reprompt_message] + cmd[1:]
    else:
        cmd = ["--continue", reprompt_message] + cmd

    cleaned: list[str] = []
    i = 0
    while i < len(cmd):
        token = cmd[i]
        if token in {"-p", "--print"}:
            i += 2
            continue
        cleaned.append(token)
        i += 1
    return cleaned


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    cwd = str(Path.cwd())

    last_rc = run_pi(args.pi_cmd)
    if last_rc != 0:
        return last_rc
    is_running, project_id = get_item_status(args.item_id, args.step_id)
    if not is_running:
        return 0

    for attempt in range(1, args.max_reprompts + 1):
        session = find_latest_pi_session(cwd)
        verdict = NarrationVerdict.PARSE_ERROR
        last_text: str | None = None
        if session is None:
            _log("warning: no pi session JSONL found")
        else:
            verdict = classify_last_assistant(session)
            last_text = _last_assistant_text(session)

        emit_narration_event(
            project_id,
            args.item_id,
            args.step_id,
            attempt,
            args.max_reprompts,
            last_text,
            verdict,
        )

        reprompt = build_reprompt_message(last_text, attempt, args.max_reprompts)
        continue_cmd = _to_continue_cmd(args.pi_cmd, reprompt)
        last_rc = run_pi(continue_cmd)
        if last_rc != 0:
            return last_rc
        is_running, project_id = get_item_status(args.item_id, args.step_id)
        if not is_running:
            return 0

    return last_rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
