"""Unit tests for orch.config.

Tests run with the env vars injected directly via monkeypatch.
Do NOT reload the module — load_dotenv() runs once at import;
after that, _require() reads os.environ dynamically.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All required env vars and their valid test values
_VALID_ENV: dict[str, str] = {
    "IW_CORE_DB_HOST": "testhost",
    "IW_CORE_DB_PORT": "5999",
    "IW_CORE_DB_NAME": "testdb",
    "IW_CORE_DB_USER": "testuser",
    "IW_CORE_DB_PASSWORD": "testpass",  # noqa: S105
    "IW_CORE_DASHBOARD_HOST": "127.0.0.1",
    "IW_CORE_DASHBOARD_PORT": "9901",
    "IW_CORE_POLL_INTERVAL": "30",
    "IW_CORE_STALL_THRESHOLD": "300",
    "IW_CORE_PID_FILE": "/tmp/test-daemon.pid",  # noqa: S108
    "IW_CORE_ARCHIVE_DIR": "/tmp/test-archive",  # noqa: S108
    "IW_CORE_ARCHIVE_TTL": "90",
    "IW_CORE_LOG_LEVEL": "DEBUG",
    "IW_CORE_LOG_FILE": "/tmp/test-daemon.log",  # noqa: S108
}


def _set_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required env vars to valid test values."""
    for key, value in _VALID_ENV.items():
        monkeypatch.setenv(key, value)


# ---------------------------------------------------------------------------
# Tests: missing env vars raise clear errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing_var", list(_VALID_ENV.keys()))
def test_missing_env_var_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, missing_var: str
) -> None:
    """Each missing required env var must raise RuntimeError with the var name.

    NOTE: Do NOT reload the module here. load_dotenv() runs at import time
    and would re-add the deleted var from the .env file on reload.
    _require() reads os.environ dynamically, so monkeypatch.delenv is sufficient.
    """
    import orch.config as cfg

    _set_all(monkeypatch)
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(RuntimeError, match=missing_var):
        cfg.load_config()


def test_missing_db_host_raises_on_get_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db_url() fails fast when IW_CORE_DB_HOST is missing."""
    import orch.config as cfg

    _set_all(monkeypatch)
    monkeypatch.delenv("IW_CORE_DB_HOST", raising=False)

    with pytest.raises(RuntimeError, match="IW_CORE_DB_HOST"):
        cfg.get_db_url()


# ---------------------------------------------------------------------------
# Tests: DB URL is built correctly from components
# ---------------------------------------------------------------------------


def test_db_url_built_from_components(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB URL must be assembled from individual env vars, not hardcoded."""
    import orch.config as cfg

    _set_all(monkeypatch)

    url = cfg.get_db_url()
    assert url == "postgresql+psycopg://testuser:testpass@testhost:5999/testdb"


def test_db_url_uses_psycopg_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    """The DB URL must use the psycopg (v3) driver prefix."""
    import orch.config as cfg

    _set_all(monkeypatch)

    url = cfg.get_db_url()
    assert url.startswith("postgresql+psycopg://")


def test_load_config_db_url_matches_components(monkeypatch: pytest.MonkeyPatch) -> None:
    """DaemonConfig.db_url must equal what get_db_url() returns."""
    import orch.config as cfg

    _set_all(monkeypatch)

    config = cfg.load_config()
    assert config.db_url == cfg.get_db_url()


# ---------------------------------------------------------------------------
# Tests: all config fields loaded correctly
# ---------------------------------------------------------------------------


def test_load_config_all_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """All DaemonConfig fields must be loaded from env vars."""
    import orch.config as cfg

    _set_all(monkeypatch)

    config = cfg.load_config()

    assert config.db_host == "testhost"
    assert config.db_port == 5999
    assert config.db_name == "testdb"
    assert config.db_user == "testuser"
    assert config.db_password == "testpass"  # noqa: S105
    assert config.dashboard_host == "127.0.0.1"
    assert config.dashboard_port == 9901
    assert config.poll_interval == 30
    assert config.stall_threshold == 300
    assert config.pid_file == "/tmp/test-daemon.pid"  # noqa: S108
    assert config.archive_dir == "/tmp/test-archive"  # noqa: S108
    assert config.archive_ttl == 90
    assert config.log_level == "DEBUG"
    assert config.log_file == "/tmp/test-daemon.log"  # noqa: S108


def test_daemon_config_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    """DaemonConfig is a frozen dataclass — must reject attribute assignment."""
    import orch.config as cfg

    _set_all(monkeypatch)

    config = cfg.load_config()
    with pytest.raises((AttributeError, TypeError)):
        config.db_host = "hacked"  # type: ignore[misc]


def test_port_values_are_integers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Numeric config values must be converted to int, not left as strings."""
    import orch.config as cfg

    _set_all(monkeypatch)

    config = cfg.load_config()
    assert isinstance(config.db_port, int)
    assert isinstance(config.dashboard_port, int)
    assert isinstance(config.poll_interval, int)
    assert isinstance(config.stall_threshold, int)
    assert isinstance(config.archive_ttl, int)
