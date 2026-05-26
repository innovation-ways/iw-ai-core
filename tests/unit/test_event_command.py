from __future__ import annotations

import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from click.testing import CliRunner

_SPEC = importlib.util.spec_from_file_location("event_commands", Path("orch/cli/event_commands.py"))
assert _SPEC
assert _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
daemon_event = _MODULE.daemon_event


class _FakeSession:
    def __init__(self) -> None:
        self.events: list[Any] = []

    def add(self, obj: Any) -> None:
        self.events.append(obj)

    def flush(self) -> None:
        for index, event in enumerate(self.events, start=1):
            if getattr(event, "id", None) is None:
                event.id = index


@contextmanager
def _get_session(fake_session: _FakeSession):
    yield fake_session


def test_daemon_event_inserts_row() -> None:
    fake_session = _FakeSession()
    runner = CliRunner()

    result = runner.invoke(
        daemon_event,
        [
            "--event-type",
            "step_narration_exit",
            "--entity-type",
            "work_item",
            "--entity-id",
            "F-00089",
            "--message",
            "Step S05 narrated without executing — reprompting (attempt 1)",
            "--metadata",
            '{"step_id":"S05","reprompt_attempt":1,"max_reprompts":5}',
        ],
        obj={
            "project_id": "iw-ai-core",
            "get_session": lambda: _get_session(fake_session),
            "json": False,
        },
    )

    assert result.exit_code == 0
    assert len(fake_session.events) == 1

    event = fake_session.events[0]
    assert event.project_id == "iw-ai-core"
    assert event.event_type == "step_narration_exit"
    assert event.entity_type == "work_item"
    assert event.entity_id == "F-00089"
    assert event.message == "Step S05 narrated without executing — reprompting (attempt 1)"
    assert event.event_metadata == {
        "step_id": "S05",
        "reprompt_attempt": 1,
        "max_reprompts": 5,
    }
    assert result.output.strip() == "1"


def test_daemon_event_json_output_returns_id() -> None:
    fake_session = _FakeSession()
    runner = CliRunner()

    result = runner.invoke(
        daemon_event,
        [
            "--event-type",
            "step_narration_exit",
        ],
        obj={
            "project_id": "iw-ai-core",
            "get_session": lambda: _get_session(fake_session),
            "json": True,
        },
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"id": 1}
