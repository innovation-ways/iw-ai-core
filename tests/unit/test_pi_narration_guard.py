from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "pi_narration_guard", Path("executor/pi_narration_guard.py")
)
assert _SPEC
assert _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

NarrationVerdict = _MODULE.NarrationVerdict
build_reprompt_message = _MODULE.build_reprompt_message
classify_last_assistant = _MODULE.classify_last_assistant
find_latest_pi_session = _MODULE.find_latest_pi_session


def test_classify_narration_shape_text_only_returns_NARRATION(tmp_path: Path) -> None:  # noqa: N802
    session = tmp_path / "session.jsonl"
    session.write_text(
        (
            '{"type":"assistant","content":[{"type":"thinking","thinking":"hmm"},'
            '{"type":"text","text":"I will do it"}]}\n'
        ),
        encoding="utf-8",
    )

    assert classify_last_assistant(session) is NarrationVerdict.NARRATION


def test_classify_narration_shape_with_toolcall_returns_TOOL_CALL(tmp_path: Path) -> None:  # noqa: N802
    session = tmp_path / "session.jsonl"
    session.write_text(
        (
            '{"type":"assistant","content":[{"type":"thinking"},'
            '{"type":"toolCall","toolCall":{"toolName":"bash"}}]}\n'
        ),
        encoding="utf-8",
    )

    assert classify_last_assistant(session) is NarrationVerdict.TOOL_CALL


def test_classify_with_text_and_toolcall_returns_TOOL_CALL(tmp_path: Path) -> None:  # noqa: N802
    session = tmp_path / "session.jsonl"
    session.write_text(
        (
            '{"type":"assistant","content":[{"type":"thinking"},'
            '{"type":"text","text":"doing this"},'
            '{"type":"toolCall","toolCall":{"toolName":"bash"}}]}\n'
        ),
        encoding="utf-8",
    )

    assert classify_last_assistant(session) is NarrationVerdict.TOOL_CALL


def test_classify_empty_session_returns_NO_ASSISTANT(tmp_path: Path) -> None:  # noqa: N802
    session = tmp_path / "session.jsonl"
    session.write_text(
        '{"type":"session","id":"abc"}\n{"type":"model_change","model":"x"}\n',
        encoding="utf-8",
    )

    assert classify_last_assistant(session) is NarrationVerdict.NO_ASSISTANT


def test_classify_missing_file_returns_PARSE_ERROR(tmp_path: Path) -> None:  # noqa: N802
    assert classify_last_assistant(tmp_path / "missing.jsonl") is NarrationVerdict.PARSE_ERROR


def test_classify_malformed_jsonl_returns_PARSE_ERROR(tmp_path: Path) -> None:  # noqa: N802
    session = tmp_path / "session.jsonl"
    session.write_text('{"type":"assistant"}\n{not-json}\n', encoding="utf-8")

    assert classify_last_assistant(session) is NarrationVerdict.PARSE_ERROR


def test_find_latest_pi_session_picks_most_recent(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "sessions"
    slug = "--tmp-worktree--"
    session_dir = base / slug
    session_dir.mkdir(parents=True)

    older = session_dir / "older.jsonl"
    newer = session_dir / "newer.jsonl"
    older.write_text("{}\n", encoding="utf-8")
    newer.write_text("{}\n", encoding="utf-8")
    older_mtime = 1_700_000_000
    newer_mtime = older_mtime + 10
    older.touch()
    newer.touch()
    os.utime(older, (older_mtime, older_mtime))
    os.utime(newer, (newer_mtime, newer_mtime))

    monkeypatch.setenv("PI_CODING_AGENT_SESSION_DIR", str(base))
    assert find_latest_pi_session("/tmp/worktree") == newer


def test_find_latest_pi_session_returns_None_for_empty_dir(tmp_path: Path, monkeypatch) -> None:  # noqa: N802
    base = tmp_path / "sessions"
    (base / "--tmp-worktree--").mkdir(parents=True)
    monkeypatch.setenv("PI_CODING_AGENT_SESSION_DIR", str(base))

    assert find_latest_pi_session("/tmp/worktree") is None


def test_build_reprompt_message_includes_last_text_truncated() -> None:
    long_text = "x" * 400
    message = build_reprompt_message(long_text, attempt=2, cap=5)

    assert "Reprompt 2/5." in message
    assert f'You said: "{"x" * 300}".' in message
    assert "x" * 301 not in message


def test_build_reprompt_message_handles_None_last_text() -> None:  # noqa: N802
    message = build_reprompt_message(None, attempt=1, cap=5)

    assert "Reprompt 1/5." in message
    assert "You said:" not in message
