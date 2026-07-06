"""Unit tests for orch.mcp.server.resolve_transport transport/host/port resolution."""

from __future__ import annotations

import pytest

from orch.mcp.server import resolve_transport

# Bind-all address used by the LAN HTTP deployment; isolated here so the
# bandit S104 suppression lives in one place, not scattered across asserts.
_ALL_INTERFACES = "0.0.0.0"  # noqa: S104


class TestResolveTransport:
    """Covers precedence (args > env > defaults) and validation."""

    def test_defaults_to_stdio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no args and no env, transport resolves to stdio."""
        monkeypatch.delenv("IW_CORE_MCP_TRANSPORT", raising=False)
        transport, _host, _port = resolve_transport(None, None, None)
        assert transport == "stdio"

    def test_env_selects_http_with_default_bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IW_CORE_MCP_TRANSPORT=http resolves to http on the default 127.0.0.1:9901."""
        monkeypatch.setenv("IW_CORE_MCP_TRANSPORT", "http")
        monkeypatch.delenv("IW_CORE_MCP_HTTP_HOST", raising=False)
        monkeypatch.delenv("IW_CORE_MCP_HTTP_PORT", raising=False)
        transport, host, port = resolve_transport(None, None, None)
        assert (transport, host, port) == ("http", "127.0.0.1", 9901)

    def test_explicit_args_win_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit transport/host/port override the environment values."""
        monkeypatch.setenv("IW_CORE_MCP_TRANSPORT", "stdio")
        monkeypatch.setenv("IW_CORE_MCP_HTTP_HOST", "127.0.0.1")
        monkeypatch.setenv("IW_CORE_MCP_HTTP_PORT", "1111")
        transport, host, port = resolve_transport("http", _ALL_INTERFACES, 9901)
        assert (transport, host, port) == ("http", _ALL_INTERFACES, 9901)

    def test_env_host_and_port_used_for_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP host and port are read from env when args are None."""
        monkeypatch.setenv("IW_CORE_MCP_TRANSPORT", "http")
        monkeypatch.setenv("IW_CORE_MCP_HTTP_HOST", _ALL_INTERFACES)
        monkeypatch.setenv("IW_CORE_MCP_HTTP_PORT", "9910")
        transport, host, port = resolve_transport(None, None, None)
        assert (transport, host, port) == ("http", _ALL_INTERFACES, 9910)

    def test_unknown_transport_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unrecognised transport value raises ValueError."""
        monkeypatch.delenv("IW_CORE_MCP_TRANSPORT", raising=False)
        with pytest.raises(ValueError, match="Unknown MCP transport"):
            resolve_transport("carrier-pigeon", None, None)

    def test_invalid_env_port_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-integer IW_CORE_MCP_HTTP_PORT raises ValueError."""
        monkeypatch.setenv("IW_CORE_MCP_TRANSPORT", "http")
        monkeypatch.setenv("IW_CORE_MCP_HTTP_PORT", "not-a-port")
        with pytest.raises(ValueError, match="must be an integer"):
            resolve_transport(None, None, None)
