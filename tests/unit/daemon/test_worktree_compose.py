"""Unit tests for orch.daemon.worktree_compose."""

from __future__ import annotations

import stat
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.worktree_compose import (
    UpResult,
    WorktreeStackConfig,
    _compose_project_name,
    assert_gitignore_safe,
    discover_ports,
    down,
    has_iw_config,
    is_alive,
    load_config,
    render_compose,
    rewrite_env,
    run_seed,
    up,
)


class TestComposeProjectName:
    """Tests for the _compose_project_name naming helper."""

    def test_lowercase_and_underscore_replaced(self) -> None:
        """Verifies that uppercase letters and underscores are converted to lowercase dashes."""
        assert _compose_project_name("F-00062") == "iwcore-f-00062"
        assert _compose_project_name("F_00062") == "iwcore-f-00062"
        assert _compose_project_name("ABC_123_XYZ") == "iwcore-abc-123-xyz"

    def test_compose_project_name_is_lowercase_and_dash_separated(self) -> None:
        """AC6 — project name CR-00022 maps to iwcore-cr-00022."""
        assert _compose_project_name("CR-00022") == "iwcore-cr-00022"
        assert _compose_project_name("cr-00022") == "iwcore-cr-00022"


class TestHasIwConfig:
    """Tests for the has_iw_config predicate."""

    def test_returns_true_when_template_exists(self, tmp_path: Path) -> None:
        """Verifies that has_iw_config returns True when the compose template file is present."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)
        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")

        assert has_iw_config(worktree) is True

    def test_returns_false_when_template_missing(self, tmp_path: Path) -> None:
        """Verifies that has_iw_config returns False when the compose template file is absent."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / "ai-dev" / "iw-config").mkdir(parents=True)

        assert has_iw_config(worktree) is False


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_raises_when_template_missing(self, tmp_path: Path) -> None:
        """Verifies that load_config raises FileNotFoundError when the compose template."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / "ai-dev" / "iw-config").mkdir(parents=True)

        with pytest.raises(FileNotFoundError):
            load_config("F-00062", "iw-ai-core", worktree)

    def test_loads_all_paths(self, tmp_path: Path) -> None:
        """Verifies that load_config correctly populates all path and metadata fields."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_toml = iw_config / "worktree-env.toml"
        env_toml.write_text('[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"')

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        assert cfg.batch_item_id == "F-00062"
        assert cfg.project_id == "iw-ai-core"
        assert cfg.worktree_path == worktree
        assert cfg.template_path == template
        assert cfg.env_toml_path == env_toml
        expected_rendered = worktree / ".iw" / "docker-compose-F-00062.yml"
        assert cfg.rendered_compose_path == expected_rendered
        assert cfg.compose_project_name == "iwcore-f-00062"

    def test_seed_script_none_when_missing(self, tmp_path: Path) -> None:
        """Verifies that seed_script_path is None when no seed script exists."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        assert cfg.seed_script_path is None

    def test_seed_script_set_when_executable(self, tmp_path: Path) -> None:
        """Verifies that seed_script_path is populated when an executable seed script exists."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text("#!/bin/bash\nexit 0")
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        assert cfg.seed_script_path == seed_script


class TestAssertGitignoreSafe:
    """Tests for the assert_gitignore_safe pre-flight check."""

    def test_passes_when_env_and_iw_present(self, tmp_path: Path) -> None:  # noqa: assertion-scanner
        """Verifies that assert_gitignore_safe passes when both .env and .iw/ are listed."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".env\n.iw/\nother\n")
        assert_gitignore_safe(tmp_path)

    def test_raises_when_env_missing(self, tmp_path: Path) -> None:
        """Verifies that assert_gitignore_safe raises ValueError when .env is absent from
        .gitignore.
        """
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".iw/\nother\n")

        with pytest.raises(ValueError, match=".env must be in .gitignore"):
            assert_gitignore_safe(tmp_path)

    def test_raises_when_iw_dir_missing(self, tmp_path: Path) -> None:
        """Verifies that assert_gitignore_safe raises ValueError when .iw/ is absent from
        .gitignore.
        """
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".env\nother\n")

        with pytest.raises(ValueError, match=".iw/ must be in .gitignore"):
            assert_gitignore_safe(tmp_path)

    def test_raises_when_gitignore_missing(self, tmp_path: Path) -> None:
        """Verifies that assert_gitignore_safe raises ValueError when no .gitignore file exists."""
        with pytest.raises(ValueError, match=".gitignore not found"):
            assert_gitignore_safe(tmp_path)


class TestRenderCompose:
    """Tests for the render_compose template rendering function."""

    def test_substitutes_jinja_vars(self, tmp_path: Path) -> None:
        """Verifies that Jinja2 template variables are substituted with the correct values."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text(
            "project: {{ project_name }}\n"
            "batch: {{ batch_item_id }}\n"
            "path: {{ worktree_path }}\n"
            "compose_project: {{ compose_project_name }}"
        )

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        result = render_compose(cfg)

        content = result.read_text()
        assert "iw-ai-core" in content
        assert "F-00062" in content
        assert str(worktree) in content
        assert "iwcore-f-00062" in content

    def test_writes_to_iw_subdir(self, tmp_path: Path) -> None:
        """Verifies that render_compose writes the rendered file to the .iw subdirectory."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")

        cfg = load_config("F-99999", "iw-ai-core", worktree)
        result = render_compose(cfg)

        assert result.parent == worktree / ".iw"
        assert result.name == "docker-compose-F-99999.yml"
        assert result.is_file()

    def test_render_compose_uses_strict_undefined_so_missing_var_raises(
        self, tmp_path: Path
    ) -> None:
        """AC6 — StrictUndefined raises immediately on missing template variable."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("project: {{ project_name }}\nmissing: {{ does_not_exist }}")

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        import jinja2

        with pytest.raises(jinja2.UndefinedError):
            render_compose(cfg)


class TestDiscoverPorts:
    """Tests for the discover_ports port-mapping function."""

    def test_parses_docker_compose_port_output(self, tmp_path: Path) -> None:
        """Verifies that discover_ports correctly maps docker compose port output to env."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_dir = worktree / ".iw"
        iw_dir.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_toml = iw_config / "worktree-env.toml"
        env_toml.write_text(
            '[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"\n"app:9900" = "IW_CORE_DASHBOARD_PORT"'
        )

        compose_file = iw_dir / "docker-compose-F-00062.yml"
        compose_file.write_text("services:\n  db:\n    image: postgres")

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="0.0.0.0:34567\n",
                stderr="",
            )
            ports = discover_ports(cfg)

        assert "IW_CORE_DB_PORT" in ports
        assert ports["IW_CORE_DB_PORT"] == 34567

    def test_handles_ipv6_output(self, tmp_path: Path) -> None:
        """Verifies that discover_ports correctly parses IPv6-format port output."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_dir = worktree / ".iw"
        iw_dir.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_toml = iw_config / "worktree-env.toml"
        env_toml.write_text('[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"')

        compose_file = iw_dir / "docker-compose-F-00062.yml"
        compose_file.write_text("services:\n  db:\n    image: postgres")

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[::]:54321\n",
                stderr="",
            )
            ports = discover_ports(cfg)

        assert ports["IW_CORE_DB_PORT"] == 54321


class TestRewriteEnv:
    """Tests for the rewrite_env .env file update function."""

    def test_applies_port_to_env_mapping(self, tmp_path: Path) -> None:
        """Verifies that rewrite_env writes discovered ports and env overrides into the."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_toml = iw_config / "worktree-env.toml"
        env_toml.write_text(
            '[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"\n'
            '[env_overrides]\nIW_CORE_DB_HOST = "localhost"'
        )

        env_file = worktree / ".env"
        env_file.write_text("IW_CORE_OTHER=value\n")

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        discovered_ports = {"IW_CORE_DB_PORT": 34567}
        rewrite_env(cfg, discovered_ports)

        content = env_file.read_text()
        assert "IW_CORE_DB_PORT=34567" in content
        assert "IW_CORE_DB_HOST=localhost" in content
        assert "IW_CORE_OTHER=value" in content

    def test_preserves_passthrough_keys(self, tmp_path: Path) -> None:
        """Verifies that env_passthrough keys are preserved in the .env file after rewrite."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_toml = iw_config / "worktree-env.toml"
        env_toml.write_text(
            '[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"\n'
            '[env_passthrough]\nkeep = ["IW_CORE_ORCH_DB_*", "ANTHROPIC_API_KEY"]'
        )

        env_file = worktree / ".env"
        env_file.write_text(
            "IW_CORE_ORCH_DB_HOST=orch.example.com\n"
            "ANTHROPIC_API_KEY=sk-ant-secret\n"
            "IW_CORE_OTHER=value\n"
        )

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        discovered_ports = {"IW_CORE_DB_PORT": 34567}
        rewrite_env(cfg, discovered_ports)

        content = env_file.read_text()
        assert "IW_CORE_ORCH_DB_HOST=orch.example.com" in content
        assert "ANTHROPIC_API_KEY=sk-ant-secret" in content


class TestRunSeed:
    """Tests for the run_seed seed script execution function."""

    def test_zero_exit_succeeds(self, tmp_path: Path) -> None:
        """Verifies that run_seed returns (True, None) when the seed script exits with code 0."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text("#!/bin/bash\nexit 0")
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok, stderr = run_seed(cfg)

        assert ok is True
        assert stderr is None

    def test_nonzero_exit_returns_failure_with_stderr_tail(self, tmp_path: Path) -> None:
        """Verifies that run_seed returns (False, stderr) when the seed script exits non-zero."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text("#!/bin/bash\nexit 1")
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="FATAL: source DB unreachable",
            )
            ok, stderr = run_seed(cfg)

        assert ok is False
        assert stderr == "FATAL: source DB unreachable"

    def test_no_seed_script_is_noop(self, tmp_path: Path) -> None:
        """Verifies that run_seed returns (True, None) immediately when no seed script exists."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        ok, stderr = run_seed(cfg)

        assert ok is True
        assert stderr is None

    def test_run_seed_loads_worktree_env_into_subprocess_environment(self, tmp_path: Path) -> None:
        """AC6 — seed script inherits the worktree's .env as subprocess environment."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text("#!/bin/bash\necho $IW_CORE_DB_HOST")
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        env_file = worktree / ".env"
        env_file.write_text("IW_CORE_DB_HOST=per-worktree-db\nIW_CORE_OTHER=value\n")

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="per-worktree-db\n", stderr="")
            run_seed(cfg)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert "IW_CORE_DB_HOST" in call_kwargs["env"]
        assert call_kwargs["env"]["IW_CORE_DB_HOST"] == "per-worktree-db"

    def test_multi_assignment_export_does_not_trigger_false_positive(self, tmp_path: Path) -> None:
        """Regression: ``export A=1 B=2 C=3`` lines must not flag B/C as unset.

        F-00079 added ``export HOME=/app PATH=... UV_PROJECT_ENVIRONMENT=/tmp/.venv``
        to worktree-seed.sh. The pre-flight regex previously only matched the
        first assignment per line, causing UV_PROJECT_ENVIRONMENT to be reported
        as an unbound external reference even though it is set inline.
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text(
            "#!/bin/bash\n"
            "set -euo pipefail\n"
            'export HOME=/app PATH="/tmp/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/.venv\n'
            'echo "venv at ${UV_PROJECT_ENVIRONMENT}"\n'
        )
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok, err = run_seed(cfg)

        assert ok is True, f"pre-flight rejected multi-assignment line: {err}"
        assert err is None

    def test_genuinely_unset_var_still_caught_by_preflight(self, tmp_path: Path) -> None:
        """Pre-flight must still catch real undefined references.

        Guards against the regex fix over-matching to the point of disabling
        the missing-var check entirely.
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text(
            '#!/bin/bash\nset -euo pipefail\necho "${SOME_REQUIRED_BUT_UNSET_VAR}"\n'
        )
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok, err = run_seed(cfg)
            mock_run.assert_not_called()

        assert ok is False
        assert err is not None
        assert "SOME_REQUIRED_BUT_UNSET_VAR" in err


class TestUp:
    """Tests for the up() compose stack lifecycle function."""

    def test_refuses_when_env_not_gitignored(self, tmp_path: Path) -> None:
        """Verifies that up() returns a failure result when .env is not listed in .gitignore."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        (worktree / ".env").write_text("IW_CORE_OTHER=value")

        gitignore = worktree / ".gitignore"
        gitignore.write_text(".iw/\n")

        cfg = load_config("F-00062", "iw-ai-core", worktree)
        result = up(cfg)

        assert result.success is False
        assert "refusing to launch" in result.error_message

    def test_up_emits_daemon_event_with_phase_and_success(self, tmp_path: Path) -> None:
        """AC6 — up() emits DaemonEvent with phase='up' and success=True on success."""
        worktree = tmp_path / "worktree"
        worktree.mkdir(parents=True)
        git_dir = worktree / ".git"
        git_dir.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_file = worktree / ".env"
        env_file.write_text("")
        gitignore = worktree / ".gitignore"
        gitignore.write_text(".env\n.iw/\n")

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with (
            patch("subprocess.run") as mock_run,
            patch("orch.daemon.worktree_compose._emit_daemon_event") as mock_emit,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = up(cfg)

        assert result.success is True
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args[0]
        assert call_args[0] == "worktree_compose"
        metadata = call_args[1]
        assert metadata["phase"] == "up"
        assert metadata["success"] is True
        assert metadata["batch_item_id"] == "F-00062"

    def test_up_emits_daemon_event_with_project_id(self, tmp_path: Path) -> None:
        """H10 — up() passes cfg.project_id to _emit_daemon_event so events appear
        in per-project event feeds rather than being dropped into the global NULL bucket.
        """
        worktree = tmp_path / "worktree"
        worktree.mkdir(parents=True)
        git_dir = worktree / ".git"
        git_dir.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_file = worktree / ".env"
        env_file.write_text("")
        gitignore = worktree / ".gitignore"
        gitignore.write_text(".env\n.iw/\n")

        cfg = load_config("F-00062", "proj-A", worktree)

        with (
            patch("subprocess.run") as mock_run,
            patch("orch.daemon.worktree_compose._emit_daemon_event") as mock_emit,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = up(cfg)

        assert result.success is True
        mock_emit.assert_called_once()
        # project_id is passed as a keyword argument
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs.get("project_id") == "proj-A"

    def test_legacy_fallback_when_iw_config_missing(self, tmp_path: Path) -> None:
        """Verifies that has_iw_config returns False for a worktree without the compose template."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / "ai-dev" / "iw-config").mkdir(parents=True)

        assert has_iw_config(worktree) is False


class TestDown:
    """Tests for the down() compose stack teardown function."""

    def test_down_idempotent_succeeds_when_no_stack_running(self) -> None:
        """AC6 — down() is idempotent; succeeds even when nothing is running."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = down("F-99999", None)
        assert result is True

    def test_down_with_compose_path_uses_minus_f_flag(self) -> None:
        """AC6 — when compose_path is provided, -f flag is passed to docker compose."""
        compose_path = Path("/tmp/worktree/.iw/docker-compose-F-00062.yml")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            down("F-00062", compose_path)

        compose_calls = [
            call
            for call in mock_run.call_args_list
            if "compose" in str(call) and "down" in str(call)
        ]
        assert len(compose_calls) == 1, f"Expected 1 compose down call, got {len(compose_calls)}"
        call_args = compose_calls[0][0][0]
        assert "-f" in call_args
        f_idx = call_args.index("-f")
        assert call_args[f_idx + 1] == str(compose_path)

    def test_down_without_compose_path_relies_on_project_name_only(self) -> None:
        """Verifies that down() uses only the project name when compose_path is None (AC6)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            down("F-00062", None)

        compose_calls = [
            call
            for call in mock_run.call_args_list
            if "compose" in str(call) and "down" in str(call)
        ]
        assert len(compose_calls) == 1, f"Expected 1 compose down call, got {len(compose_calls)}"
        call_args = compose_calls[0][0][0]
        assert "-f" not in call_args
        assert "iwcore-f-00062" in call_args


class TestIsAlive:
    """Tests for the is_alive container status check."""

    def test_returns_true_when_containers_running(self) -> None:
        """Verifies that is_alive returns True when docker ps reports container IDs."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="abc123def456\n",
                stderr="",
            )
            assert is_alive("F-00062") is True

    def test_returns_false_when_no_containers(self) -> None:
        """Verifies that is_alive returns False when docker ps reports empty output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            assert is_alive("F-00062") is False

    def test_returns_false_on_error(self) -> None:
        """Verifies that is_alive returns False when docker raises an OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("docker not available")
            assert is_alive("F-00062") is False


class TestWorktreeStackConfig:
    """Tests for WorktreeStackConfig dataclass immutability."""

    def test_dataclass_frozen(self) -> None:
        """Verifies that WorktreeStackConfig raises FrozenInstanceError when mutated."""
        cfg = WorktreeStackConfig(
            batch_item_id="F-00062",
            project_id="iw-ai-core",
            worktree_path=Path("/tmp/wt"),
            template_path=Path("/tmp/wt/ai-dev/iw-config/template.yml"),
            env_toml_path=Path("/tmp/wt/ai-dev/iw-config/env.toml"),
            seed_script_path=None,
            rendered_compose_path=Path("/tmp/wt/.iw/docker-compose-F-00062.yml"),
            compose_project_name="iwcore-f-00062",
        )
        with pytest.raises(FrozenInstanceError):
            cfg.batch_item_id = "F-99999"


class TestNoSecretsInLogs:
    """Tests that secrets from .env never appear in log output."""

    def test_no_secrets_in_logs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """AC9 — secrets from .env never appear in any log output."""
        import logging

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        iw_config = worktree / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)

        template = iw_config / "worktree-compose.template.yml"
        template.write_text("services:\n  db:\n    image: postgres")
        env_file = worktree / ".env"
        env_file.write_text("SECRET_VALUE=hunter2\nIW_CORE_DB_HOST=per-worktree-db\n")
        gitignore = worktree / ".gitignore"
        gitignore.write_text(".env\n.iw/\n")
        seed_script = iw_config / "worktree-seed.sh"
        seed_script.write_text("#!/bin/bash\nexit 0")
        seed_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        cfg = load_config("F-00062", "iw-ai-core", worktree)

        with caplog.at_level(logging.DEBUG, logger="orch.daemon.worktree_compose"):
            render_compose(cfg)
            run_seed(cfg)

        log_text = caplog.text
        assert "hunter2" not in log_text, "SECRET_VALUE must never appear in logs"
        assert "per-worktree-db" not in log_text or "IW_CORE_DB_HOST" in log_text


class TestUpResult:
    """Tests for UpResult dataclass immutability."""

    def test_dataclass_frozen(self) -> None:
        """Verifies that UpResult raises FrozenInstanceError when mutated."""
        result = UpResult(
            success=True,
            rendered_compose_path=Path("/tmp/compose.yml"),
            discovered_ports={"IW_CORE_DB_PORT": 34567},
            discovered_db_credentials={},
            error_message=None,
            seed_stderr_tail=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.success = False
