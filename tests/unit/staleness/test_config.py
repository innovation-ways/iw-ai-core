"""Unit tests for orch.staleness.config.

Tests config schema parsing and validation of services/alembic blocks.
No I/O, no database, no subprocess calls.
"""

from __future__ import annotations

import pytest

from orch.staleness.config import (
    AlembicConfig,
    ProjectStalenessConfig,
    ServiceConfig,
    ServiceDetect,
    parse_project_staleness,
)

# ---------------------------------------------------------------------------
# ServiceDetect parsing
# ---------------------------------------------------------------------------


class TestServiceDetectParsing:
    def test_port_detect(self) -> None:
        """detect.type=port requires a port field."""
        d = ServiceDetect.from_dict({"type": "port", "port": 9900})
        assert d.type == "port"
        assert d.port == 9900

    def test_pidfile_detect(self) -> None:
        """detect.type=pidfile requires a path field."""
        d = ServiceDetect.from_dict({"type": "pidfile", "path": ".daemon.pid"})
        assert d.type == "pidfile"
        assert d.path == ".daemon.pid"

    def test_docker_detect(self) -> None:
        """detect.type=docker requires a container field."""
        d = ServiceDetect.from_dict({"type": "docker", "container": "my-container"})
        assert d.type == "docker"
        assert d.container == "my-container"

    def test_pgrep_detect(self) -> None:
        """detect.type=pgrep requires a pattern field."""
        d = ServiceDetect.from_dict({"type": "pgrep", "pattern": "uvicorn"})
        assert d.type == "pgrep"
        assert d.pattern == "uvicorn"

    def test_unknown_detect_type_raises(self) -> None:
        """Unknown detect.type values raise ValueError."""
        with pytest.raises(ValueError, match="Unknown detect type"):
            ServiceDetect.from_dict({"type": "magic"})

    def test_port_detect_missing_port_raises(self) -> None:
        """detect.type=port without port field raises ValueError."""
        with pytest.raises(ValueError, match="port"):
            ServiceDetect.from_dict({"type": "port"})

    def test_pidfile_detect_missing_path_raises(self) -> None:
        """detect.type=pidfile without path field raises ValueError."""
        with pytest.raises(ValueError, match="path"):
            ServiceDetect.from_dict({"type": "pidfile"})

    def test_docker_detect_missing_container_raises(self) -> None:
        """detect.type=docker without container field raises ValueError."""
        with pytest.raises(ValueError, match="container"):
            ServiceDetect.from_dict({"type": "docker"})

    def test_pgrep_detect_missing_pattern_raises(self) -> None:
        """detect.type=pgrep without pattern field raises ValueError."""
        with pytest.raises(ValueError, match="pattern"):
            ServiceDetect.from_dict({"type": "pgrep"})


# ---------------------------------------------------------------------------
# ServiceConfig parsing
# ---------------------------------------------------------------------------


class TestServiceConfigParsing:
    def _minimal(self) -> dict:  # type: ignore[type-arg]
        return {
            "name": "daemon",
            "detect": {"type": "pidfile", "path": ".daemon.pid"},
            "watch_paths": ["orch/**"],
            "ignore_paths": [],
        }

    def test_minimal_service_config(self) -> None:
        """A minimal service config parses correctly with all defaults."""
        sc = ServiceConfig.from_dict(self._minimal())
        assert sc.name == "daemon"
        assert sc.detect.type == "pidfile"
        assert sc.watch_paths == ["orch/**"]
        assert sc.ignore_paths == []
        assert sc.restart_command is None
        assert sc.start_command is None
        assert sc.stop_command is None
        assert sc.hot_reload is False

    def test_service_config_with_commands(self) -> None:
        """Optional command fields are parsed when present."""
        raw = self._minimal()
        raw["restart_command"] = "./ai-core.sh daemon restart"
        raw["start_command"] = "./ai-core.sh daemon start"
        raw["stop_command"] = "./ai-core.sh daemon stop"
        sc = ServiceConfig.from_dict(raw)
        assert sc.restart_command == "./ai-core.sh daemon restart"
        assert sc.start_command == "./ai-core.sh daemon start"
        assert sc.stop_command == "./ai-core.sh daemon stop"

    def test_service_config_hot_reload_true(self) -> None:
        """hot_reload=true is parsed correctly."""
        raw = self._minimal()
        raw["hot_reload"] = True
        sc = ServiceConfig.from_dict(raw)
        assert sc.hot_reload is True

    def test_service_config_missing_name_raises(self) -> None:
        """Missing 'name' field raises ValueError."""
        raw = self._minimal()
        del raw["name"]
        with pytest.raises(ValueError, match="name"):
            ServiceConfig.from_dict(raw)

    def test_service_config_missing_detect_raises(self) -> None:
        """Missing 'detect' field raises ValueError."""
        raw = self._minimal()
        del raw["detect"]
        with pytest.raises(ValueError, match="detect"):
            ServiceConfig.from_dict(raw)

    def test_service_config_missing_watch_paths_raises(self) -> None:
        """Missing 'watch_paths' field raises ValueError."""
        raw = self._minimal()
        del raw["watch_paths"]
        with pytest.raises(ValueError, match="watch_paths"):
            ServiceConfig.from_dict(raw)

    def test_service_config_ignore_paths_defaults_to_empty(self) -> None:
        """ignore_paths defaults to empty list when not specified."""
        raw = self._minimal()
        del raw["ignore_paths"]
        sc = ServiceConfig.from_dict(raw)
        assert sc.ignore_paths == []


# ---------------------------------------------------------------------------
# AlembicConfig parsing
# ---------------------------------------------------------------------------


class TestAlembicConfigParsing:
    def test_minimal_alembic_config(self) -> None:
        """A minimal alembic config with just 'config' path."""
        ac = AlembicConfig.from_dict({"config": "alembic.ini"})
        assert ac.config == "alembic.ini"
        assert ac.db_url_env is None

    def test_alembic_config_with_db_url_env(self) -> None:
        """alembic config with db_url_env is parsed."""
        ac = AlembicConfig.from_dict({"config": "alembic.ini", "db_url_env": "MY_DB_URL"})
        assert ac.config == "alembic.ini"
        assert ac.db_url_env == "MY_DB_URL"

    def test_alembic_config_missing_config_raises(self) -> None:
        """Missing 'config' field raises ValueError."""
        with pytest.raises(ValueError, match="config"):
            AlembicConfig.from_dict({})


# ---------------------------------------------------------------------------
# parse_project_staleness
# ---------------------------------------------------------------------------


class TestParseProjectStaleness:
    def test_empty_dict_returns_empty_config(self) -> None:
        """A project with no services/alembic block returns empty config (opt-out)."""
        result = parse_project_staleness({})
        assert isinstance(result, ProjectStalenessConfig)
        assert result.services == []
        assert result.alembic is None

    def test_only_other_keys_returns_empty_config(self) -> None:
        """Keys unrelated to staleness are ignored; returns empty config."""
        result = parse_project_staleness({"cli_tool": "opencode", "display_name": "Test"})
        assert result.services == []
        assert result.alembic is None

    def test_parses_services_list(self) -> None:
        """services key is parsed into a list of ServiceConfig."""
        raw = {
            "services": [
                {
                    "name": "daemon",
                    "detect": {"type": "pidfile", "path": ".daemon.pid"},
                    "watch_paths": ["orch/**"],
                    "ignore_paths": [],
                    "restart_command": "./ai-core.sh daemon restart",
                }
            ]
        }
        result = parse_project_staleness(raw)
        assert len(result.services) == 1
        assert result.services[0].name == "daemon"
        assert result.services[0].detect.type == "pidfile"

    def test_parses_alembic_block(self) -> None:
        """alembic key is parsed into AlembicConfig."""
        raw = {"alembic": {"config": "alembic.ini"}}
        result = parse_project_staleness(raw)
        assert result.alembic is not None
        assert result.alembic.config == "alembic.ini"

    def test_parses_multiple_services(self) -> None:
        """Multiple services in the list are all parsed."""
        raw = {
            "services": [
                {
                    "name": "daemon",
                    "detect": {"type": "pidfile", "path": ".daemon.pid"},
                    "watch_paths": ["orch/**"],
                    "ignore_paths": [],
                },
                {
                    "name": "dashboard",
                    "detect": {"type": "port", "port": 9900},
                    "watch_paths": ["dashboard/**"],
                    "ignore_paths": [],
                },
            ]
        }
        result = parse_project_staleness(raw)
        assert len(result.services) == 2
        assert result.services[0].name == "daemon"
        assert result.services[1].name == "dashboard"

    def test_invalid_service_raises_value_error(self) -> None:
        """Invalid service config propagates ValueError."""
        raw = {
            "services": [
                {"name": "bad", "detect": {"type": "port"}}  # missing port field
            ]
        }
        with pytest.raises(ValueError, match="requires a 'port' field"):
            parse_project_staleness(raw)

    def test_invalid_detect_type_raises_value_error(self) -> None:
        """Unknown detect type raises ValueError."""
        raw = {
            "services": [
                {
                    "name": "svc",
                    "detect": {"type": "unknown"},
                    "watch_paths": [],
                    "ignore_paths": [],
                }
            ]
        }
        with pytest.raises(ValueError, match="Unknown detect type"):
            parse_project_staleness(raw)

    def test_full_iw_ai_core_config(self) -> None:
        """The exact iw-ai-core seed config from projects.toml parses correctly."""
        raw = {
            "services": [
                {
                    "name": "daemon",
                    "watch_paths": ["orch/**", "executor/**"],
                    "ignore_paths": ["**/tests/**", "**/*.md"],
                    "restart_command": "./ai-core.sh daemon restart",
                    "detect": {"type": "pidfile", "path": ".daemon.pid"},
                },
                {
                    "name": "dashboard",
                    "watch_paths": ["dashboard/**", "orch/**"],
                    "ignore_paths": ["**/tests/**", "**/*.md"],
                    "restart_command": "bin/restart-dashboard.sh",
                    "detect": {"type": "pidfile", "path": ".dashboard.pid"},
                },
            ],
            "alembic": {"config": "alembic.ini"},
        }
        result = parse_project_staleness(raw)
        assert len(result.services) == 2
        assert result.services[0].name == "daemon"
        assert result.services[1].name == "dashboard"
        assert result.alembic is not None
        assert result.alembic.config == "alembic.ini"
        assert result.alembic.db_url_env is None
