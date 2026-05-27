"""Unit tests for KeepAlivePoller control flow."""

from __future__ import annotations

from unittest.mock import patch

from orch.daemon.keep_alive_poller import KeepAlivePoller
from orch.keep_alive_service import FireResult


def _ok(stdout: str = "OK", elapsed_ms: int = 3000) -> FireResult:
    return FireResult(returncode=0, stdout=stdout, stderr="", elapsed_ms=elapsed_ms)


def _fail(returncode: int = 1, stderr: str = "boom", elapsed_ms: int = 1200) -> FireResult:
    return FireResult(returncode=returncode, stdout="", stderr=stderr, elapsed_ms=elapsed_ms)


def test_fire_slot_logs_success_without_retry() -> None:
    poller = KeepAlivePoller()
    with (
        patch("orch.daemon.keep_alive_poller.fire_claude", return_value=_ok()) as mock_fire,
        patch.object(poller, "_log_run") as mock_log,
    ):
        poller._fire_slot(1, "05:00", "claude-sonnet-4-6")

    assert mock_fire.call_count == 1
    mock_log.assert_called_once_with(
        1,
        "05:00",
        status="success",
        stdout="OK",
        stderr="",
        elapsed_ms=3000,
        returncode=0,
    )


def test_fire_slot_retry_success_logs_retried_success() -> None:
    poller = KeepAlivePoller()
    with (
        patch(
            "orch.daemon.keep_alive_poller.fire_claude", side_effect=[_fail(), _ok()]
        ) as mock_fire,
        patch.object(poller, "_log_run") as mock_log,
    ):
        poller._fire_slot(1, "05:00", "claude-sonnet-4-6")

    assert mock_fire.call_count == 2
    mock_log.assert_called_once_with(
        1,
        "05:00",
        status="retried_success",
        stdout="OK",
        stderr="",
        elapsed_ms=3000,
        returncode=0,
    )


def test_fire_slot_double_failure_logs_retried_failed() -> None:
    poller = KeepAlivePoller()
    with (
        patch(
            "orch.daemon.keep_alive_poller.fire_claude",
            side_effect=[
                FireResult(returncode=1, stdout="", stderr="first", elapsed_ms=1000),
                FireResult(returncode=1, stdout="", stderr="second", elapsed_ms=1100),
            ],
        ) as mock_fire,
        patch.object(poller, "_log_run") as mock_log,
    ):
        poller._fire_slot(1, "05:00", "claude-sonnet-4-6")

    assert mock_fire.call_count == 2
    _, kwargs = mock_log.call_args
    assert kwargs["status"] == "retried_failed"
    assert kwargs["stdout"] == ""
    assert kwargs["returncode"] == 1
    assert kwargs["elapsed_ms"] == 1000
    assert kwargs["error"] == "rc=1 elapsed=1000ms; retry rc=1 elapsed=1100ms"


def test_fire_slot_treats_rc0_empty_stdout_as_failure_and_retries() -> None:
    poller = KeepAlivePoller()
    first = FireResult(returncode=0, stdout="", stderr="", elapsed_ms=3000)
    second = _ok(stdout="OK retry", elapsed_ms=3200)
    with (
        patch(
            "orch.daemon.keep_alive_poller.fire_claude", side_effect=[first, second]
        ) as mock_fire,
        patch.object(poller, "_log_run") as mock_log,
    ):
        poller._fire_slot(1, "05:00", "claude-sonnet-4-6")

    assert mock_fire.call_count == 2
    _, kwargs = mock_log.call_args
    assert kwargs["status"] == "retried_success"
    assert kwargs["stdout"] == "OK retry"
