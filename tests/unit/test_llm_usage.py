"""Unit tests for orch.llm_usage MiniMax path (F-00075).

Covers:
  - _load_minimax_key(): env var vs auth.json resolution
  - _format_reset(): millisecond-to-human-string formatting
  - _minimax_usage_remote(): httpx-mocked API calls
  - _minimax_usage(): orchestrator (key → remote with graceful failure)
  - get_llm_usage(): cache TTL behaviour
  - No-SQLite3 regression checks
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "minimax_remains.json"


def _fake_response(body: dict[str, Any]) -> MagicMock:
    """Build a fake httpx.Response whose .json() returns `body`."""
    resp = MagicMock()
    resp.json.return_value = body
    return resp


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text())


class TestLoadMinimaxKey:
    """Tests for _load_minimax_key()."""

    def test_env_var_wins_over_auth_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When IW_MINIMAX_API_KEY is set, it is returned without consulting auth.json."""
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "env-key-abc")
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"minimax": {"key": "auth-key-xyz"}}))

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result == "env-key-abc"

    def test_env_var_empty_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An empty-string env var (IW_MINIMAX_API_KEY='') counts as unset."""
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "")
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"minimax": {"key": "auth-key-from-file"}}))

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result == "auth-key-from-file"

    def test_auth_json_fallback(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """When env var is unset, _load_minimax_key() falls back to auth.json."""
        monkeypatch.delenv("IW_MINIMAX_API_KEY", raising=False)
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"minimax": {"key": "auth-fallback-key"}}))

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result == "auth-fallback-key"

    def test_auth_json_missing_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When neither IW_MINIMAX_API_KEY nor auth.json exists, returns None."""
        monkeypatch.delenv("IW_MINIMAX_API_KEY", raising=False)
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result is None

    def test_auth_json_malformed_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When auth.json exists but is not valid JSON, returns None without raising."""
        monkeypatch.delenv("IW_MINIMAX_API_KEY", raising=False)
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("not json at all")

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result is None

    def test_auth_json_no_minimax_section_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When auth.json parses but has no minimax.key, returns None without raising."""
        monkeypatch.delenv("IW_MINIMAX_API_KEY", raising=False)
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"openai": {"key": "some-key"}}))

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            result = llm_usage._load_minimax_key()
            assert result is None


class TestClaudeRateLimitsCache:
    """Tests for the rate-limits cache reader and Claude usage builder."""

    @staticmethod
    def _write_cache(tmp_path: Path, payload: dict[str, Any]) -> Path:
        cache_dir = tmp_path / ".claude"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = cache_dir / "rate-limits-cache.json"
        cache.write_text(json.dumps(payload))
        return cache

    def test_read_seven_day_returns_dict_when_in_future(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """seven_day with resets_at in the future → returns the bucket."""
        from datetime import UTC, datetime

        future = int(datetime.now(UTC).timestamp()) + 3600
        self._write_cache(
            tmp_path,
            {"seven_day": {"used_percentage": 56.0, "resets_at": future}},
        )

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            result = llm_usage_mod._read_rate_limits_cache("seven_day")
            assert result is not None
            assert result["used_percentage"] == 56.0
            assert result["resets_at"] == future

    def test_read_returns_none_when_resets_at_in_past(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Stale entry (resets_at in the past) → None, no fallback."""
        from datetime import UTC, datetime

        past = int(datetime.now(UTC).timestamp()) - 3600
        self._write_cache(
            tmp_path,
            {"five_hour": {"used_percentage": 10, "resets_at": past}},
        )

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            assert llm_usage_mod._read_rate_limits_cache("five_hour") is None

    def test_read_returns_none_when_missing_window(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Cache exists but lacks the requested window → None."""
        from datetime import UTC, datetime

        future = int(datetime.now(UTC).timestamp()) + 3600
        self._write_cache(
            tmp_path,
            {"five_hour": {"used_percentage": 70, "resets_at": future}},
        )

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            assert llm_usage_mod._read_rate_limits_cache("seven_day") is None

    def test_read_returns_none_when_file_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No cache file at all → None, no exception."""
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            assert llm_usage_mod._read_rate_limits_cache("seven_day") is None

    def test_claude_usage_uses_seven_day_from_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_claude_usage() uses seven_day.used_percentage, not any local token count."""
        from datetime import UTC, datetime

        future = int(datetime.now(UTC).timestamp()) + 3600
        self._write_cache(
            tmp_path,
            {
                "five_hour": {"used_percentage": 70, "resets_at": future},
                "seven_day": {"used_percentage": 56.00000000000001, "resets_at": future},
            },
        )

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            result = llm_usage_mod._claude_usage()
            assert result["block_pct"] == 70
            assert result["week_pct"] == 56
            assert result["block_reset"] is not None
            assert result["week_reset"] is not None

            # 5h: must be remaining-time format ("Xh Ym" or "Xm"), NEVER wall-clock "HH:MM"
            assert re.fullmatch(r"\d+h \d+m|\d+m", result["block_reset"]), result["block_reset"]
            assert ":" not in result["block_reset"]

            # 7d: still wall-clock — must contain a colon
            assert ":" in result["week_reset"]

    def test_claude_usage_zero_when_cache_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No cache file → both bars 0%, both resets None (no fallback)."""
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)

            result = llm_usage_mod._claude_usage()
            assert result == {
                "block_pct": 0,
                "week_pct": 0,
                "block_reset": None,
                "week_reset": None,
            }


class TestFormatResetsAt:
    """Tests for _format_resets_at() — wall-clock reset rendering."""

    def test_past_returns_none(self) -> None:
        from datetime import UTC, datetime

        from orch import llm_usage

        past = datetime.now(UTC).timestamp() - 60
        assert llm_usage._format_resets_at(past) is None

    def test_zero_returns_none(self) -> None:
        from orch import llm_usage

        assert llm_usage._format_resets_at(0) is None

    def test_within_24h_returns_hour_minute(self) -> None:
        """Resets <24h away → 'HH:MM' (no day prefix)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        ts = datetime.now(UTC).timestamp() + 2 * 3600
        result = llm_usage._format_resets_at(ts)
        assert result is not None
        assert ":" in result
        assert " " not in result

    def test_beyond_24h_returns_day_and_time(self) -> None:
        """Resets >24h away → 'Day HH:MM' (e.g. 'Tue 09:00')."""
        from datetime import UTC, datetime

        from orch import llm_usage

        ts = datetime.now(UTC).timestamp() + 3 * 24 * 3600
        result = llm_usage._format_resets_at(ts)
        assert result is not None
        parts = result.split(" ")
        assert len(parts) == 2
        assert len(parts[0]) == 3  # %a → "Mon", "Tue", ...
        assert ":" in parts[1]


class TestFormatRemainingFromTs:
    """Tests for _format_remaining_from_ts() — remaining-time rendering (MiniMax-style)."""

    def test_zero_returns_none(self) -> None:
        """_format_remaining_from_ts(0) → None."""
        from orch import llm_usage

        assert llm_usage._format_remaining_from_ts(0) is None

    def test_past_returns_none(self) -> None:
        """Timestamp in the past → None."""
        from datetime import UTC, datetime

        from orch import llm_usage

        past = datetime.now(UTC).timestamp() - 60
        assert llm_usage._format_remaining_from_ts(past) is None

    def test_under_one_minute_returns_zero_m(self) -> None:
        """30 seconds → '0m'."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + 30)
        assert result == "0m"

    def test_under_one_hour_returns_minutes_only(self) -> None:
        """25 minutes 5 seconds → '25m' (5s cushion past any boundary)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + (25 * 60 + 5))
        assert result == "25m"

    def test_under_one_hour_at_boundary(self) -> None:
        """59 minutes 50 seconds → '59m' (well below 3600s so no flake risk)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + (59 * 60 + 50))
        assert result == "59m"

    def test_just_over_one_hour(self) -> None:
        """3600 + 5 seconds → '1h 0m' (5s cushion above the hour boundary)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + (3600 + 5))
        assert result == "1h 0m"

    def test_multiple_hours(self) -> None:
        """4h 32m 5s → '4h 32m' (5s cushion past the 32-minute boundary)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + (4 * 3600 + 32 * 60 + 5))
        assert result == "4h 32m"

    def test_multiple_hours_with_seconds(self) -> None:
        """2h 43m 49s → '2h 43m' (seconds dropped; not on a boundary)."""
        from datetime import UTC, datetime

        from orch import llm_usage

        now = datetime.now(UTC).timestamp()
        result = llm_usage._format_remaining_from_ts(now + (2 * 3600 + 43 * 60 + 49))
        assert result == "2h 43m"


class TestNoCcusageRegressions:
    """ccusage path was removed — symbols must be absent from the module."""

    def test_no_run_ccusage(self) -> None:
        import orch.llm_usage as m

        assert not hasattr(m, "_run_ccusage")

    def test_no_claude_weekly_limit_constant(self) -> None:
        import orch.llm_usage as m

        assert not hasattr(m, "_CLAUDE_WEEKLY_LIMIT")

    def test_no_subprocess_import(self) -> None:
        import orch.llm_usage as m

        assert not hasattr(m, "subprocess")


class TestFormatReset:
    """Tests for _format_reset()."""

    def test_zero_returns_none(self) -> None:
        """remains_ms == 0 → None."""
        from orch import llm_usage

        assert llm_usage._format_reset(0) is None

    def test_negative_returns_none(self) -> None:
        """remains_ms < 0 → None."""
        from orch import llm_usage

        assert llm_usage._format_reset(-1) is None

    def test_under_one_hour_minutes_only(self) -> None:
        """remains_ms < 3_600_000 → '{m}m'."""
        from orch import llm_usage

        assert llm_usage._format_reset(1_500_000) == "25m"

    def test_under_one_hour_at_boundary(self) -> None:
        """3_599_999 ms → '59m' (just under the 1-hour threshold)."""
        from orch import llm_usage

        assert llm_usage._format_reset(3_599_999) == "59m"

    def test_exactly_one_hour(self) -> None:
        """remains_ms == 3_600_000 → '1h 0m'."""
        from orch import llm_usage

        assert llm_usage._format_reset(3_600_000) == "1h 0m"

    def test_multiple_hours(self) -> None:
        """remains_ms == 9_812_749 → '2h 43m'."""
        from orch import llm_usage

        assert llm_usage._format_reset(9_812_749) == "2h 43m"

    def test_one_hour_zero_minutes(self) -> None:
        """remains_ms == 3_600_000 → '1h 0m'."""
        from orch import llm_usage

        assert llm_usage._format_reset(3_600_000) == "1h 0m"


# ---------------------------------------------------------------------------
# _minimax_usage_remote() — mocked httpx
# ---------------------------------------------------------------------------


class TestMinimaxUsageRemote:
    """Tests for _minimax_usage_remote() with mocked httpx.get."""

    def test_happy_path_real_fixture(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Loading the real fixture yields block_pct=6, used=266, total=4500."""
        from orch import llm_usage

        fixture = _load_fixture()

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            resp = MagicMock()
            resp.json.return_value = fixture
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        result = llm_usage._minimax_usage_remote("test-key")

        # From fixture: MiniMax-M* has usage_count=4232 remaining → used=268
        assert result["block_pct"] == 6, f"expected 6, got {result['block_pct']}"
        assert result["used"] == 268, f"expected 268, got {result['used']}"
        assert result["total"] == 4500
        assert result["block_reset"] is not None

    def test_mid_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """total=4500, usage_count=3000 remaining → 1500 used → block_pct=33."""
        from orch import llm_usage

        body = _fake_response(
            {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 3000,
                        "remains_time": 1_500_000,
                    }
                ],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        result = llm_usage._minimax_usage_remote("test-key")
        assert result["block_pct"] == 33
        assert result["used"] == 1500
        assert result["total"] == 4500

    def test_fully_consumed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """usage_count=0 remaining → all 4500 used → block_pct=100."""
        from orch import llm_usage

        body = _fake_response(
            {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 0,
                        "remains_time": 0,
                    }
                ],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        result = llm_usage._minimax_usage_remote("test-key")
        assert result["block_pct"] == 100
        assert result["used"] == 4500

    def test_missing_m_row_raises_lookup_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Response with no MiniMax-M* row raises LookupError."""
        from orch import llm_usage

        body = _fake_response(
            {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "some-other-model",
                        "current_interval_total_count": 100,
                        "current_interval_usage_count": 0,
                        "remains_time": 0,
                    }
                ],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        with pytest.raises(LookupError, match="MiniMax-M"):
            llm_usage._minimax_usage_remote("test-key")

    def test_total_zero_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MiniMax-M* row with total=0 raises ValueError."""
        from orch import llm_usage

        body = _fake_response(
            {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 0,
                        "current_interval_usage_count": 0,
                        "remains_time": 0,
                    }
                ],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        with pytest.raises(ValueError, match="total quota is 0"):
            llm_usage._minimax_usage_remote("test-key")

    def test_status_code_nonzero_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """base_resp.status_code != 0 raises RuntimeError with the status_msg."""
        from orch import llm_usage

        body = _fake_response(
            {
                "base_resp": {"status_code": 1004, "status_msg": "auth error"},
                "model_remains": [],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        with pytest.raises(RuntimeError, match="auth error"):
            llm_usage._minimax_usage_remote("test-key")

    def test_http_status_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """httpx.HTTPStatusError from resp.raise_for_status() propagates to caller."""
        import httpx

        from orch import llm_usage

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.HTTPStatusError("server error", request=MagicMock(), response=MagicMock())

        monkeypatch.setattr("httpx.get", fake_get)
        with pytest.raises(httpx.HTTPStatusError):
            llm_usage._minimax_usage_remote("test-key")

    def test_bearer_header_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """httpx.get is called with Authorization: Bearer <key> and Accept: application/json."""
        from orch import llm_usage

        captured_kwargs: list[dict[str, Any]] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_kwargs.append(kwargs)
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        llm_usage._minimax_usage_remote("my-secret-key")

        assert len(captured_kwargs) == 1
        headers = captured_kwargs[0]["headers"]
        assert headers["Authorization"] == "Bearer my-secret-key"
        assert headers["Accept"] == "application/json"

    def test_groupid_appended_to_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When IW_MINIMAX_GROUP_ID is set, URL contains ?GroupId=<value>."""
        from orch import llm_usage

        captured_urls: list[str] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_urls.append(url)
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_GROUP_ID", "abc123")
        llm_usage._minimax_usage_remote("test-key")
        assert "GroupId=abc123" in captured_urls[0]

    def test_no_groupid_no_query_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When IW_MINIMAX_GROUP_ID is unset, URL has no query string."""
        from orch import llm_usage

        captured_urls: list[str] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_urls.append(url)
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.delenv("IW_MINIMAX_GROUP_ID", raising=False)
        monkeypatch.setattr("httpx.get", fake_get)
        llm_usage._minimax_usage_remote("test-key")
        assert "?" not in captured_urls[0]

    def test_timeout_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """httpx.get is called with timeout <= 10 seconds."""
        from orch import llm_usage

        captured_timeouts: list[float] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_timeouts.append(kwargs.get("timeout"))
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        llm_usage._minimax_usage_remote("test-key")
        assert captured_timeouts[0] is not None
        assert captured_timeouts[0] <= 10.0


# ---------------------------------------------------------------------------
# _minimax_usage() — orchestrator with graceful failure
# ---------------------------------------------------------------------------


class TestMinimaxUsage:
    """Tests for _minimax_usage() orchestrator."""

    def test_no_key_returns_zero_and_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When _load_minimax_key() returns None, result is {0, None} and a warning is logged."""
        from orch import llm_usage

        # Mock the key loader to return None (simulating missing key scenario)
        monkeypatch.setattr("orch.llm_usage._load_minimax_key", lambda: None)

        with caplog.at_level(logging.WARNING):
            result = llm_usage._minimax_usage()

        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax API key not configured" in caplog.text

    def test_remote_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Key present + httpx returns real fixture → result matches _minimax_usage_remote."""

        fixture = _load_fixture()

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            resp = MagicMock()
            resp.json.return_value = fixture
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        result = llm_usage_mod._minimax_usage()
        assert result["block_pct"] == 6
        assert result["used"] == 268
        assert result["total"] == 4500
        assert result["block_reset"] is not None

    def test_handles_status_code_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """status_code != 0 → {0, None}, logged once."""

        body = _fake_response(
            {
                "base_resp": {"status_code": 1004, "status_msg": "auth error"},
                "model_remains": [],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        with caplog.at_level(logging.ERROR):
            result = llm_usage_mod._minimax_usage()
        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax usage fetch failed" in caplog.text

    def test_handles_http_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """httpx.HTTPStatusError → {0, None}, logged once."""
        import httpx

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.HTTPStatusError("server error", request=MagicMock(), response=MagicMock())

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        with caplog.at_level(logging.ERROR):
            result = llm_usage_mod._minimax_usage()
        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax usage fetch failed" in caplog.text

    def test_handles_connect_timeout(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """httpx.ConnectTimeout → {0, None}, logged."""
        import httpx

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.ConnectTimeout("connection refused")

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        with caplog.at_level(logging.ERROR):
            result = llm_usage_mod._minimax_usage()
        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax usage fetch failed" in caplog.text

    def test_handles_malformed_json(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Response body that fails JSON parsing → {0, None}, logged."""

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            resp = MagicMock()
            resp.json.side_effect = json.JSONDecodeError("invalid", "", 0)
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        with caplog.at_level(logging.ERROR):
            result = llm_usage_mod._minimax_usage()
        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax usage fetch failed" in caplog.text

    def test_handles_missing_m_row(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No MiniMax-M* row → {0, None} (no local fallback), logged."""

        body = _fake_response(
            {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "some-other-model",
                        "current_interval_total_count": 100,
                        "current_interval_usage_count": 0,
                        "remains_time": 0,
                    }
                ],
            }
        )

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        with caplog.at_level(logging.ERROR):
            result = llm_usage_mod._minimax_usage()
        assert result == {"block_pct": 0, "block_reset": None}
        assert "MiniMax usage fetch failed" in caplog.text


# ---------------------------------------------------------------------------
# Cache TTL tests
# ---------------------------------------------------------------------------


class TestCacheTTL:
    """Tests for get_llm_usage() in-process cache TTL behaviour."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the module-level cache before and after each test."""
        from orch import llm_usage

        llm_usage._cache.clear()
        yield
        llm_usage._cache.clear()

    def test_within_ttl_single_call(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Call get_llm_usage() twice within TTL; second call hits cache (no httpx call)."""

        get_calls: list[Any] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            get_calls.append(url)
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")
        # Codex (R-00075) also flows through get_llm_usage; redirect its auth.json
        # read to an empty tmp_path so it short-circuits to the zero-fill path and
        # this test stays focused on MiniMax cache-hit semantics regardless of the
        # developer's on-disk opencode credentials.
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        # Clear cache to ensure first call goes through and populates cache
        llm_usage_mod._cache.clear()

        # First call — populates cache
        llm_usage_mod.get_llm_usage()
        # Second call — should hit cache
        llm_usage_mod.get_llm_usage()

        # Only one httpx call was made (cache hit on second)
        assert len(get_calls) == 1, f"expected 1 httpx call, got {len(get_calls)}"

    def test_second_call_hits_cache_when_data_seeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When cache has both ts and data, subsequent calls return cached data without HTTP."""
        get_calls: list[Any] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            get_calls.append(url)
            resp = MagicMock()
            resp.json.return_value = {
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "model_remains": [
                    {
                        "model_name": "MiniMax-M2.7",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 4500,
                        "remains_time": 9_812_749,
                    }
                ],
            }
            return resp

        monkeypatch.setattr("httpx.get", fake_get)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "test-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        # Pre-populate cache with fresh ts and valid data
        from datetime import UTC, datetime

        llm_usage_mod._cache["ts"] = datetime.now(UTC)
        llm_usage_mod._cache["data"] = {
            "claude": {},
            "minimax": {"block_pct": 0, "block_reset": None},
        }

        # Call twice — both should return cached data without HTTP
        result1 = llm_usage_mod.get_llm_usage()
        result2 = llm_usage_mod.get_llm_usage()

        assert len(get_calls) == 0, f"expected 0 httpx calls, got {len(get_calls)}"
        assert result1["minimax"]["block_pct"] == 0
        assert result2["minimax"]["block_pct"] == 0


# ---------------------------------------------------------------------------
# get_llm_usage() shape tests
# ---------------------------------------------------------------------------


class TestGetLlmUsageShape:
    """Ensure get_llm_usage() always returns a structurally sound dict."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        from orch import llm_usage

        llm_usage._cache.clear()
        yield
        llm_usage._cache.clear()

    def test_minimax_always_has_block_pct_and_block_reset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even on catastrophic failure, minimax dict has block_pct and block_reset."""
        import httpx

        def fake_remote(key: str) -> Any:  # noqa: ARG001
            raise httpx.ConnectTimeout("connection refused")

        monkeypatch.setattr("orch.llm_usage._minimax_usage_remote", fake_remote)
        monkeypatch.setenv("IW_MINIMAX_API_KEY", "some-key")

        import importlib

        import orch.llm_usage as llm_usage_mod

        importlib.reload(llm_usage_mod)

        result = llm_usage_mod.get_llm_usage()
        minimax = result["minimax"]
        assert "block_pct" in minimax
        assert "block_reset" in minimax
        assert minimax["block_pct"] == 0
        assert minimax["block_reset"] is None


# ---------------------------------------------------------------------------
# No-SQLite3 regressions (F-00075 replaced local SQLite with live API)
# ---------------------------------------------------------------------------


class TestNoSqliteRegressions:
    """SQLite symbols must be absent from orch/llm_usage.py after F-00075."""

    def test_no_sqlite3_import(self) -> None:
        """orch/llm_usage.py must not import sqlite3."""
        import orch.llm_usage as m

        assert not hasattr(m, "sqlite3")

    def test_no_opencode_db_constant(self) -> None:
        """orch/llm_usage.py must not have _OPENCODE_DB constant."""
        import orch.llm_usage as m

        assert not hasattr(m, "_OPENCODE_DB")

    def test_no_five_h_ms_constant(self) -> None:
        """orch/llm_usage.py must not have _FIVE_H_MS constant."""
        import orch.llm_usage as m

        assert not hasattr(m, "_FIVE_H_MS")

    def test_no_minimax_5h_limit_constant(self) -> None:
        """orch/llm_usage.py must not have _MINIMAX_5H_LIMIT constant."""
        import orch.llm_usage as m

        assert not hasattr(m, "_MINIMAX_5H_LIMIT")


# ---------------------------------------------------------------------------
# Codex — via /backend-api/wham/usage with opencode OAuth (R-00075)
# ---------------------------------------------------------------------------


def _write_opencode_auth_oauth(tmp_path: Path, *, access: str, account_id: str) -> Path:
    """Write a realistic opencode auth.json with an openai OAuth entry."""
    auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text(
        json.dumps(
            {
                "minimax": {"type": "api", "key": "mm-key"},
                "openai": {
                    "type": "oauth",
                    "access": access,
                    "refresh": "refresh-tok",
                    "expires": 1_779_689_299_438,
                    "accountId": account_id,
                },
            }
        )
    )
    return auth_file


def _codex_usage_payload(
    *,
    primary_pct: int = 47,
    secondary_pct: int = 12,
    primary_reset_at: int | None = None,
    secondary_reset_at: int | None = None,
    plan_type: str = "plus",
) -> dict[str, Any]:
    """Build a realistic /wham/usage response body."""
    from datetime import UTC, datetime

    now = int(datetime.now(UTC).timestamp())
    return {
        "plan_type": plan_type,
        "rate_limit": {
            "allowed": True,
            "limit_reached": False,
            "primary_window": {
                "used_percent": primary_pct,
                "limit_window_seconds": 18000,
                "reset_after_seconds": 7200,
                "reset_at": primary_reset_at or (now + 2 * 3600),
            },
            "secondary_window": {
                "used_percent": secondary_pct,
                "limit_window_seconds": 604800,
                "reset_after_seconds": 432000,
                "reset_at": secondary_reset_at or (now + 5 * 24 * 3600),
            },
        },
    }


class TestLoadOpenaiOauth:
    """Tests for _load_openai_oauth() — opencode auth.json reader."""

    def test_oauth_entry_returned(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A well-formed openai.oauth entry is returned as a dict."""
        _write_opencode_auth_oauth(
            tmp_path,
            access="eyJabc.def.ghi",
            account_id="11111111-2222-3333-4444-555555555555",
        )
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            entry = llm_usage._load_openai_oauth()
            assert entry is not None
            assert entry["type"] == "oauth"
            assert entry["access"] == "eyJabc.def.ghi"
            assert entry["accountId"] == "11111111-2222-3333-4444-555555555555"

    def test_missing_file_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No auth.json at all → None, no exception."""
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None

    def test_malformed_json_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Garbage in auth.json → None, no exception."""
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("not json")
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None

    def test_no_openai_section_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """auth.json present but lacks an `openai` key → None."""
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"minimax": {"type": "api", "key": "k"}}))
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None

    def test_raw_api_key_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """openai entry with type=api (raw API key) → None — Codex chip suppressed."""
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(json.dumps({"openai": {"type": "api", "key": "sk-..."}}))
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None

    def test_oauth_missing_access_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """OAuth entry without an `access` string field → None."""
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(
            json.dumps({"openai": {"type": "oauth", "accountId": "x", "refresh": "y"}})
        )
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None

    def test_oauth_missing_account_id_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """OAuth entry without an `accountId` string field → None."""
        auth_file = tmp_path / ".local" / "share" / "opencode" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text(
            json.dumps({"openai": {"type": "oauth", "access": "tok", "refresh": "r"}})
        )
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            from orch import llm_usage

            assert llm_usage._load_openai_oauth() is None


class TestCodexWindowExtractors:
    """Tests for the defensive primary/secondary-window extractors."""

    def test_pct_from_none(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_pct(None) == 0

    def test_pct_from_empty_dict(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_pct({}) == 0

    def test_pct_string_value_safely_zero(self) -> None:
        """Schema drift: string in used_percent → 0, never raises."""
        from orch import llm_usage

        assert llm_usage._codex_window_pct({"used_percent": "47"}) == 0

    def test_pct_integer_value(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_pct({"used_percent": 47}) == 47

    def test_pct_float_rounds(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_pct({"used_percent": 47.7}) == 48

    def test_pct_clamps_above_100(self) -> None:
        """Defensive: a >100 value (impossible in spec) clamps to 100."""
        from orch import llm_usage

        assert llm_usage._codex_window_pct({"used_percent": 150}) == 100

    def test_pct_clamps_below_zero(self) -> None:
        """Defensive: a negative value clamps to 0."""
        from orch import llm_usage

        assert llm_usage._codex_window_pct({"used_percent": -5}) == 0

    def test_reset_ts_from_none(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_reset_ts(None) == 0

    def test_reset_ts_explicit_null(self) -> None:
        """The Rust double-Option appears as JSON null — should be 0."""
        from orch import llm_usage

        assert llm_usage._codex_window_reset_ts({"reset_at": None}) == 0

    def test_reset_ts_zero(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_reset_ts({"reset_at": 0}) == 0

    def test_reset_ts_integer(self) -> None:
        from orch import llm_usage

        assert llm_usage._codex_window_reset_ts({"reset_at": 1779689299}) == 1779689299


class TestCodexUsageRemote:
    """Tests for _codex_usage_remote() with mocked httpx.get."""

    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Realistic payload yields {block_pct, week_pct, *reset, plan_type}."""
        body = _fake_response(_codex_usage_payload(primary_pct=47, secondary_pct=12))

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return body

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        result = llm_usage._codex_usage_remote("access-tok", "acct-uuid")
        assert result["block_pct"] == 47
        assert result["week_pct"] == 12
        assert result["plan_type"] == "plus"
        assert result["block_reset"] is not None
        assert result["week_reset"] is not None
        # 5h shows remaining ("Xh Ym"); weekly shows wall-clock (contains ":")
        assert re.fullmatch(r"\d+h \d+m|\d+m", result["block_reset"])
        assert ":" in result["week_reset"]

    def test_sends_oauth_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Authorization Bearer + ChatGPT-Account-Id headers are present."""
        captured: list[dict[str, Any]] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.append(kwargs)
            return _fake_response(_codex_usage_payload())

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        llm_usage._codex_usage_remote("my-access", "my-account")
        assert len(captured) == 1
        headers = captured[0]["headers"]
        assert headers["Authorization"] == "Bearer my-access"
        assert headers["ChatGPT-Account-Id"] == "my-account"
        assert headers["Accept"] == "application/json"
        # User-Agent identifies our poller for OpenAI traffic auditing
        assert "iw-ai-core" in headers["User-Agent"]

    def test_calls_wham_usage_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The exact backend-api URL is requested."""
        captured: list[str] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.append(url)
            return _fake_response(_codex_usage_payload())

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        llm_usage._codex_usage_remote("t", "a")
        assert captured == ["https://chatgpt.com/backend-api/wham/usage"]

    def test_timeout_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """httpx.get is called with a bounded timeout (≤10s)."""
        captured: list[float] = []

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.append(kwargs.get("timeout"))
            return _fake_response(_codex_usage_payload())

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        llm_usage._codex_usage_remote("t", "a")
        assert captured[0] is not None
        assert captured[0] <= 10.0

    def test_missing_rate_limit_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Payload without rate_limit → 0% both bars, no reset labels, plan_type preserved."""

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return _fake_response({"plan_type": "plus"})

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        result = llm_usage._codex_usage_remote("t", "a")
        assert result["block_pct"] == 0
        assert result["week_pct"] == 0
        assert result["block_reset"] is None
        assert result["week_reset"] is None
        assert result["plan_type"] == "plus"

    def test_rate_limit_explicit_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """rate_limit: null (Rust double-Option's outer None) → safe 0%."""

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return _fake_response({"plan_type": "free", "rate_limit": None})

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        result = llm_usage._codex_usage_remote("t", "a")
        assert result["block_pct"] == 0
        assert result["week_pct"] == 0

    def test_secondary_window_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only primary_window populated → 5h bar live, weekly bar 0%."""
        payload = _codex_usage_payload(primary_pct=80, secondary_pct=0)
        payload["rate_limit"]["secondary_window"] = None

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return _fake_response(payload)

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        result = llm_usage._codex_usage_remote("t", "a")
        assert result["block_pct"] == 80
        assert result["week_pct"] == 0
        assert result["week_reset"] is None

    def test_fully_consumed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """used_percent=100 → block_pct=100; the chip will color red downstream."""

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return _fake_response(_codex_usage_payload(primary_pct=100))

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        result = llm_usage._codex_usage_remote("t", "a")
        assert result["block_pct"] == 100

    def test_http_status_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bad bearer (401) is raised so the orchestrator can log it."""
        import httpx

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())

        monkeypatch.setattr("httpx.get", fake_get)
        from orch import llm_usage

        with pytest.raises(httpx.HTTPStatusError):
            llm_usage._codex_usage_remote("t", "a")


class TestCodexUsage:
    """Tests for _codex_usage() orchestrator with graceful failure."""

    def test_no_oauth_returns_zero_and_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When _load_openai_oauth() returns None, result is fully zeroed."""
        monkeypatch.setattr("orch.llm_usage._load_openai_oauth", lambda: None)
        from orch import llm_usage

        with caplog.at_level(logging.WARNING):
            result = llm_usage._codex_usage()
        assert result == {
            "block_pct": 0,
            "week_pct": 0,
            "block_reset": None,
            "week_reset": None,
            "plan_type": None,
        }
        assert "Codex OAuth credentials not found" in caplog.text

    def test_remote_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """OAuth present + valid response → result mirrors _codex_usage_remote."""
        _write_opencode_auth_oauth(tmp_path, access="tok-abc", account_id="acct-1")

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            return _fake_response(_codex_usage_payload(primary_pct=66, secondary_pct=33))

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            m.setattr("httpx.get", fake_get)
            from orch import llm_usage

            result = llm_usage._codex_usage()
            assert result["block_pct"] == 66
            assert result["week_pct"] == 33
            assert result["plan_type"] == "plus"

    def test_handles_http_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """401 / 404 from /wham/usage → zeroed dict, logged once."""
        import httpx

        _write_opencode_auth_oauth(tmp_path, access="tok-abc", account_id="acct-1")

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            m.setattr("httpx.get", fake_get)
            from orch import llm_usage

            with caplog.at_level(logging.ERROR):
                result = llm_usage._codex_usage()
            assert result["block_pct"] == 0
            assert result["week_pct"] == 0
            assert "Codex usage fetch failed" in caplog.text

    def test_handles_connect_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Network timeout → zeroed dict, logged."""
        import httpx

        _write_opencode_auth_oauth(tmp_path, access="t", account_id="a")

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.ConnectTimeout("connection refused")

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            m.setattr("httpx.get", fake_get)
            from orch import llm_usage

            with caplog.at_level(logging.ERROR):
                result = llm_usage._codex_usage()
            assert result["block_pct"] == 0
            assert "Codex usage fetch failed" in caplog.text

    def test_no_token_leaks_in_logs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Critical: no access/refresh/accountId material may appear in log output."""
        import httpx

        # S105 false positives: these are fixture sentinels used to assert that
        # NO token material reaches log output — the test would be meaningless
        # if it didn't contain a distinctive string to grep the log for.
        secret_access = "eyJSECRETACCESSTOKENVALUE.payload.signature"  # noqa: S105
        secret_account = "11111111-2222-3333-4444-555555555555"  # noqa: S105
        _write_opencode_auth_oauth(tmp_path, access=secret_access, account_id=secret_account)

        def fake_get(url: str, **kwargs: Any) -> MagicMock:  # noqa: ARG001
            raise httpx.HTTPStatusError("auth failed", request=MagicMock(), response=MagicMock())

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            m.setattr("httpx.get", fake_get)
            from orch import llm_usage

            with caplog.at_level(logging.DEBUG):
                llm_usage._codex_usage()
            log_text = caplog.text
            assert secret_access not in log_text
            assert secret_account not in log_text
            assert "eyJSECRET" not in log_text


class TestGetLlmUsageCodexIntegration:
    """get_llm_usage() always includes a structurally-sound codex key."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        from orch import llm_usage

        llm_usage._cache.clear()
        yield
        llm_usage._cache.clear()

    def test_codex_key_present_with_all_subkeys(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """get_llm_usage()["codex"] has the full template-required key set."""
        # No oauth → graceful zero, but the key set must still match.
        monkeypatch.setattr("orch.llm_usage._load_openai_oauth", lambda: None)
        monkeypatch.setattr("orch.llm_usage._load_minimax_key", lambda: None)
        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)
            result = llm_usage_mod.get_llm_usage()

        assert "codex" in result
        codex = result["codex"]
        for key in ("block_pct", "week_pct", "block_reset", "week_reset", "plan_type"):
            assert key in codex, f"codex missing key {key!r}"
        # All zero / None on the no-auth path
        assert codex["block_pct"] == 0
        assert codex["week_pct"] == 0
        assert codex["block_reset"] is None
        assert codex["week_reset"] is None

    def test_codex_failure_does_not_break_other_providers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A Codex network failure must not stop Claude/MiniMax data from coming back."""

        # _codex_usage already catches everything internally — confirm the outer
        # try/except in get_llm_usage doesn't swallow other providers' data either.
        def boom() -> dict[str, Any]:
            raise RuntimeError("codex blew up after returning")

        monkeypatch.setattr("orch.llm_usage._codex_usage", boom)
        monkeypatch.setattr("orch.llm_usage._load_minimax_key", lambda: None)

        with monkeypatch.context() as m:
            m.setattr("pathlib.Path.home", lambda: tmp_path)
            import importlib

            import orch.llm_usage as llm_usage_mod

            importlib.reload(llm_usage_mod)
            # Re-apply patches after reload (importlib.reload reloads the module's
            # globals so monkeypatches done before the reload are wiped).
            monkeypatch.setattr("orch.llm_usage._codex_usage", boom)
            monkeypatch.setattr("orch.llm_usage._load_minimax_key", lambda: None)

            result = llm_usage_mod.get_llm_usage()

        assert "claude" in result
        assert "minimax" in result
        assert "codex" in result
        # Codex zeroed by the outer fallback
        assert result["codex"]["block_pct"] == 0
        assert result["codex"]["week_pct"] == 0
