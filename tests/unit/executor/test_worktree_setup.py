"""Unit tests for executor/worktree_setup.sh.

Tests are driven via subprocess against a temporary git repository.
A shim `iw` script is injected into PATH to avoid needing a live DB.

Bugs covered:
- C1: env leak — daemon process env vars must NOT appear in worktree .env
- H2: dep install failure swallowed — uv sync || true must be || true-removed
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent.parent.parent.parent / "executor" / "worktree_setup.sh"


def _make_git_repo(path: Path) -> None:
    """Initialise a bare git repo with one commit so branches work."""
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
        cwd=str(path),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True,
        capture_output=True,
        cwd=str(path),
    )
    readme = path / "README.md"
    readme.write_text("# test\n")
    subprocess.run(["git", "add", "README.md"], check=True, capture_output=True, cwd=str(path))
    subprocess.run(
        ["git", "commit", "-m", "init"],
        check=True,
        capture_output=True,
        cwd=str(path),
    )


def _make_iw_shim(bin_dir: Path, item_id: str = "I-00001") -> None:
    """Write a tiny `iw` shim that returns a minimal item-status JSON."""
    iw = bin_dir / "iw"
    iw.write_text(f'#!/usr/bin/env bash\necho \'{{"id": "{item_id}", "title": "Test Item"}}\'\n')
    iw.chmod(0o755)


def _run_setup(
    project_root: Path,
    item_id: str,
    extra_env: dict[str, str] | None = None,
    iw_core_root: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run worktree_setup.sh with a shim iw in PATH."""
    bin_dir = project_root / "_bin"
    bin_dir.mkdir(exist_ok=True)
    _make_iw_shim(bin_dir, item_id)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(project_root),  # keep git author config local
    }
    if extra_env:
        env.update(extra_env)

    cmd = [str(SCRIPT), item_id, str(project_root)]
    if iw_core_root:
        cmd.append(iw_core_root)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# C1: env leak tests
# ---------------------------------------------------------------------------


class TestEnvLeak:
    """C1: The worktree .env must only contain keys declared in the project .env."""

    def test_daemon_context_not_leaked(self, tmp_path: Path) -> None:
        """IW_CORE_DAEMON_CONTEXT set in daemon env must NOT appear in worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        # Project .env has only one key
        (project / ".env").write_text("APP_PORT=8080\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"IW_CORE_DAEMON_CONTEXT": "production"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "IW_CORE_DAEMON_CONTEXT" not in worktree_env
        assert "APP_PORT" in worktree_env

    def test_operator_apply_not_leaked(self, tmp_path: Path) -> None:
        """IW_CORE_OPERATOR_APPLY set in daemon env must NOT appear in worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("DB_HOST=localhost\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"IW_CORE_OPERATOR_APPLY": "true"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "IW_CORE_OPERATOR_APPLY" not in worktree_env

    def test_github_token_not_leaked(self, tmp_path: Path) -> None:
        """GITHUB_TOKEN set only in process env must NOT appear in worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("APP_NAME=myapp\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"GITHUB_TOKEN": "ghp_supersecret"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "GITHUB_TOKEN" not in worktree_env

    def test_aws_secret_not_leaked(self, tmp_path: Path) -> None:
        """AWS_SECRET_ACCESS_KEY set only in process env must NOT appear in worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("REGION=us-east-1\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"AWS_SECRET_ACCESS_KEY": "s3cr3t"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "AWS_SECRET_ACCESS_KEY" not in worktree_env

    def test_ssh_auth_sock_not_leaked(self, tmp_path: Path) -> None:
        """SSH_AUTH_SOCK set only in process env must NOT appear in worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("SERVICE=web\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"SSH_AUTH_SOCK": "/tmp/agent.123"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "SSH_AUTH_SOCK" not in worktree_env

    def test_project_env_keys_present(self, tmp_path: Path) -> None:
        """Keys declared in the project .env ARE written to the worktree .env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("APP_PORT=9000\nDB_NAME=mydb\n")

        result = _run_setup(project, "I-00001")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "APP_PORT" in worktree_env
        assert "DB_NAME" in worktree_env

    def test_var_reference_expanded(self, tmp_path: Path) -> None:
        """A ${VAR} reference in project .env is expanded using the daemon env."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        # Project .env references PROJECT_DIR which daemon provides
        (project / ".env").write_text("DATA_DIR=${PROJECT_DIR}/data\n")

        result = _run_setup(
            project,
            "I-00001",
            extra_env={"PROJECT_DIR": "/srv/myproject"},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "/srv/myproject/data" in worktree_env

    def test_unset_var_preserved_verbatim(self, tmp_path: Path) -> None:
        """A ${UNSET_VAR} reference in project .env is preserved verbatim."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        (project / ".env").write_text("THING=${TOTALLY_UNSET_VARIABLE_XYZ}\n")

        # TOTALLY_UNSET_VARIABLE_XYZ is not a real env var — no need to strip it.
        # Just run normally; the script must preserve the literal ${VAR} token.
        result = _run_setup(project, "I-00001")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "${TOTALLY_UNSET_VARIABLE_XYZ}" in worktree_env

    def test_comments_and_blank_lines_preserved(self, tmp_path: Path) -> None:
        """Comment lines and blank lines in project .env are preserved."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        env_content = "# This is a comment\n\nAPP_PORT=8080\n"
        (project / ".env").write_text(env_content)

        result = _run_setup(project, "I-00001")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        worktree_env = (project / ".worktrees" / "I-00001" / ".env").read_text()
        assert "# This is a comment" in worktree_env
        assert "APP_PORT=8080" in worktree_env


# ---------------------------------------------------------------------------
# H2: dep install failure swallowed
# ---------------------------------------------------------------------------


class TestDepInstallFailure:
    """H2: uv sync failure must abort the script (no || true)."""

    def test_uv_sync_failure_aborts_script(self, tmp_path: Path) -> None:
        """When uv sync fails (bad pyproject.toml), worktree_setup.sh must exit non-zero."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        # Write a deliberately broken pyproject.toml
        (project / "pyproject.toml").write_text(
            '[project]\nname = "broken"\n[tool.uv]\n# bad: dependency that cannot possibly exist\n'
        )
        # Stage it so it appears in the worktree after git worktree add
        subprocess.run(
            ["git", "add", "pyproject.toml"], check=True, capture_output=True, cwd=str(project)
        )
        subprocess.run(
            ["git", "commit", "-m", "add bad pyproject"],
            check=True,
            capture_output=True,
            cwd=str(project),
        )

        # Inject a fake uv that always fails
        bin_dir = project / "_bin"
        bin_dir.mkdir(exist_ok=True)
        _make_iw_shim(bin_dir)
        fake_uv = bin_dir / "uv"
        fake_uv.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "$1" == "sync" ]]; then\n'
            '    echo "uv sync FAILED: simulated error" >&2\n'
            "    exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        fake_uv.chmod(0o755)

        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        result = subprocess.run(
            [str(SCRIPT), "I-00001", str(project)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit when uv sync fails, got 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_npm_install_failure_aborts_script(self, tmp_path: Path) -> None:
        """When npm install fails, worktree_setup.sh must exit non-zero."""
        project = tmp_path / "proj"
        project.mkdir()
        _make_git_repo(project)

        # Create frontend dir (triggers npm install branch)
        frontend = project / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"name": "test"}\n')
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True, cwd=str(project))
        subprocess.run(
            ["git", "commit", "-m", "add frontend"],
            check=True,
            capture_output=True,
            cwd=str(project),
        )

        bin_dir = project / "_bin"
        bin_dir.mkdir(exist_ok=True)
        _make_iw_shim(bin_dir)
        fake_npm = bin_dir / "npm"
        fake_npm.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "$1" == "install" ]]; then\n'
            '    echo "npm install FAILED: simulated error" >&2\n'
            "    exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        fake_npm.chmod(0o755)

        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        result = subprocess.run(
            [str(SCRIPT), "I-00001", str(project)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit when npm install fails, got 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
