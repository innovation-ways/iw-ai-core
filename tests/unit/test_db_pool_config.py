"""Tests for DB pool configuration (B1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class TestPoolConfig:
    """Tests for PoolConfig scenarios."""

    def test_default_pool_size_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that default pool size from env."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "testdb")
        monkeypatch.setenv("IW_CORE_DB_USER", "user")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "pass")
        monkeypatch.setenv("IW_CORE_DASHBOARD_HOST", "127.0.0.1")
        monkeypatch.setenv("IW_CORE_DASHBOARD_PORT", "9900")
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "60")
        monkeypatch.setenv("IW_CORE_STALL_THRESHOLD", "600")
        monkeypatch.setenv("IW_CORE_PID_FILE", "/tmp/test.pid")
        monkeypatch.setenv("IW_CORE_ARCHIVE_DIR", "/tmp/archive")
        monkeypatch.setenv("IW_CORE_ARCHIVE_TTL", "600")
        monkeypatch.setenv("IW_CORE_LOG_LEVEL", "INFO")
        monkeypatch.setenv("IW_CORE_LOG_FILE", "/tmp/d.log")
        monkeypatch.delenv("IW_CORE_DB_POOL_SIZE", raising=False)
        monkeypatch.delenv("IW_CORE_DB_MAX_OVERFLOW", raising=False)

        from orch.config import load_config

        config = load_config()
        assert config.db_pool_size == 20
        assert config.db_max_overflow == 20

    def test_explicit_pool_size_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that explicit pool size from env."""
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "testdb")
        monkeypatch.setenv("IW_CORE_DB_USER", "user")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "pass")
        monkeypatch.setenv("IW_CORE_DASHBOARD_HOST", "127.0.0.1")
        monkeypatch.setenv("IW_CORE_DASHBOARD_PORT", "9900")
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "60")
        monkeypatch.setenv("IW_CORE_STALL_THRESHOLD", "600")
        monkeypatch.setenv("IW_CORE_PID_FILE", "/tmp/test.pid")
        monkeypatch.setenv("IW_CORE_ARCHIVE_DIR", "/tmp/archive")
        monkeypatch.setenv("IW_CORE_ARCHIVE_TTL", "600")
        monkeypatch.setenv("IW_CORE_LOG_LEVEL", "INFO")
        monkeypatch.setenv("IW_CORE_LOG_FILE", "/tmp/d.log")
        monkeypatch.setenv("IW_CORE_DB_POOL_SIZE", "10")
        monkeypatch.setenv("IW_CORE_DB_MAX_OVERFLOW", "5")

        from orch.config import load_config

        config = load_config()
        assert config.db_pool_size == 10
        assert config.db_max_overflow == 5


class TestSessionEnginePoolConfig:
    """Tests for SessionEnginePoolConfig scenarios."""

    def test_engine_created_with_explicit_pool_kwargs(self) -> None:
        """Verifies that engine created with explicit pool kwargs."""
        from orch.db.session import engine

        assert engine.pool.size() == 20
        assert engine.pool._max_overflow == 20

    def test_engine_pool_recycle_set(self) -> None:
        """Verifies that engine pool recycle set."""
        from orch.db.session import engine

        assert engine.pool._recycle == 1800

    def test_engine_pool_timeout_set(self) -> None:
        """Verifies that engine pool timeout set."""
        from orch.db.session import engine

        assert engine.pool._timeout == 10
