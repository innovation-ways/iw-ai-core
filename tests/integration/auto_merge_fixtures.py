"""Shared fixtures for F-00084 auto_merge integration tests.

Provides:
- ConflictFixture: dataclass describing a synthetic conflict repo
- make_git_conflict_repo(): build a bare conflict fixture in tmp_path
- make_project_and_batch_item(): insert minimal DB rows
- FakeLLM / fake_llm fixture: replace invoke_llm_for_file at the Python boundary
- seed_default_runtime_option fixture: insert a default AgentRuntimeOption row
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from orch.daemon.auto_merge import LLMCallResult
from orch.db.models import (
    AgentRuntimeOption,
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# ConflictFixture dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConflictFixture:
    """Describes a synthetic git conflict repo built in tmp_path."""

    repo_path: Path
    branch_name: str
    expected_conflict_files: list[str]
    main_sha: str = ""


# ---------------------------------------------------------------------------
# Git repo builder helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: str | Path, **kwargs) -> subprocess.CompletedProcess:
    """Run a git command; raise on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        **kwargs,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def make_git_conflict_repo(
    tmp_path: Path,
    conflict_files: list[tuple[str, str, str]],
    branch_name: str = "agent/F-99999-test-feature",
    author_env: dict[str, str] | None = None,
) -> ConflictFixture:
    """Build a local git repo with conflicting files.

    conflict_files: list of (relative_path, main_version, branch_version).
    - The base version is written first (common ancestor).
    - main version is committed on main.
    - branch_version is committed on the branch.
    - These create a 3-way conflict that git rebase will detect.

    Returns a ConflictFixture with repo_path, branch_name, expected_conflict_files.
    """
    repo = tmp_path / "conflict_repo"
    repo.mkdir()

    env = {
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test Committer",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "HOME": str(tmp_path),
        **(author_env or {}),
    }

    _git(["init", "-b", "main"], cwd=repo, env=env)
    _git(["config", "user.email", "test@example.com"], cwd=repo, env=env)
    _git(["config", "user.name", "Test User"], cwd=repo, env=env)

    # Write base (common ancestor) version of each file
    for rel_path, _main_ver, _branch_ver in conflict_files:
        abs_path = repo / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(f"# base version of {rel_path}\nvalue = 0\n")
        _git(["add", rel_path], cwd=repo, env=env)

    _git(["commit", "-m", "Base commit: initial versions"], cwd=repo, env=env)
    _git(["rev-parse", "HEAD"], cwd=repo, env=env)  # establish base SHA

    # Create a feature branch from base
    _git(["checkout", "-b", branch_name], cwd=repo, env=env)

    # Write the branch version of each file
    for rel_path, _main_ver, branch_ver in conflict_files:
        abs_path = repo / rel_path
        abs_path.write_text(branch_ver)
        _git(["add", rel_path], cwd=repo, env=env)

    _git(["commit", "-m", f"Branch commit: feature changes on {branch_name}"], cwd=repo, env=env)

    # Go back to main and make a different change (creates the divergence)
    _git(["checkout", "main"], cwd=repo, env=env)

    for rel_path, main_ver, _branch_ver in conflict_files:
        abs_path = repo / rel_path
        abs_path.write_text(main_ver)
        _git(["add", rel_path], cwd=repo, env=env)

    _git(
        ["commit", "-m", "Main commit: parallel changes on main (simulates prior merge)"],
        cwd=repo,
        env=env,
    )
    main_sha = _git(["rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()

    return ConflictFixture(
        repo_path=repo,
        branch_name=branch_name,
        expected_conflict_files=[path for path, _, _ in conflict_files],
        main_sha=main_sha,
    )


# ---------------------------------------------------------------------------
# DB row builders
# ---------------------------------------------------------------------------


def make_db_project(db_session: Session, project_id: str = "test-proj") -> Project:
    """Insert a minimal Project row (idempotent via flush)."""
    existing = db_session.get(Project, project_id)
    if existing is not None:
        return existing
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def make_work_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    title: str = "Test Feature",
    description: str = "A test feature for auto-merge testing.",
    status: WorkItemStatus = WorkItemStatus.approved,
) -> WorkItem:
    """Insert a minimal WorkItem row."""
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content=description,
    )
    db_session.add(item)
    db_session.flush()
    return item


def make_batch(
    db_session: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.executing,
) -> Batch:
    """Insert a minimal Batch row."""
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def make_batch_item(
    db_session: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    worktree_path: str = "/tmp/worktrees/test",
    status: BatchItemStatus = BatchItemStatus.completed,
) -> BatchItem:
    """Insert a minimal BatchItem row."""
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=0,
        status=status,
        worktree_info={"path": worktree_path},
    )
    db_session.add(bi)
    db_session.flush()
    return bi


def make_default_runtime_option(
    db_session: Session,
    option_id: int = 9901,
    cli_tool: str = "claude",
    model: str = "claude-sonnet-4-6-automerge-test",
) -> AgentRuntimeOption:
    """Insert a non-default AgentRuntimeOption row for auto_merge tests.

    Uses is_default=False to avoid conflicting with the Alembic-seeded default
    row (uq_agent_runtime_options_one_default partial-unique constraint).
    Tests that need a specific runtime option reference it via runtime_option_id
    in the AutoMergeConfig, which _resolve_runtime_option honours directly.
    """
    option = AgentRuntimeOption(
        id=option_id,
        cli_tool=cli_tool,
        model=model,
        cli_label="Claude Code",
        model_label="Sonnet 4.6 AutoMerge Test",
        display_name="Claude Code + Sonnet 4.6 (auto-merge test)",
        is_default=False,
        enabled=True,
        sort_order=99,
    )
    db_session.add(option)
    db_session.flush()
    return option


# ---------------------------------------------------------------------------
# FakeLLM: replaces invoke_llm_for_file at the Python boundary
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMCall:
    """Record of a single FakeLLM invocation."""

    file_path: str
    cli_tool: str
    model: str


class FakeLLM:
    """Deterministic fake that replaces invoke_llm_for_file.

    Configure responses per file via response_for[filename] = <content>.
    Unconfigured files return a reasonable default resolved content.
    Set abstain_for to make specific files return ABSTAIN.
    Set error_for to make specific files return an error.
    """

    def __init__(self) -> None:
        self.calls: list[FakeLLMCall] = []
        self.response_for: dict[str, str] = {}
        self.abstain_for: set[str] = set()
        self.error_for: dict[str, str] = {}

    def invoke(
        self,
        *,
        worktree_path: str,
        file_path: str,
        main_sha: str,  # noqa: ARG002
        branch_name: str,  # noqa: ARG002
        item_id: str,  # noqa: ARG002
        item_title: str,  # noqa: ARG002
        item_description: str,  # noqa: ARG002
        cli_tool: str,
        model: str,
        config: object,  # noqa: ARG002
    ) -> LLMCallResult:
        self.calls.append(FakeLLMCall(file_path=file_path, cli_tool=cli_tool, model=model))

        import hashlib

        prompt_hash = hashlib.sha256(f"fake-prompt-{file_path}".encode()).hexdigest()

        if file_path in self.error_for:
            return LLMCallResult(
                file_path=file_path,
                abstained=False,
                proposed_content=None,
                error=self.error_for[file_path],
                model=model,
                cli_tool=cli_tool,
                input_tokens=None,
                output_tokens=None,
                prompt_hash=prompt_hash,
                output_hash=None,
            )

        if file_path in self.abstain_for:
            return LLMCallResult(
                file_path=file_path,
                abstained=True,
                proposed_content=None,
                error=None,
                model=model,
                cli_tool=cli_tool,
                input_tokens=None,
                output_tokens=None,
                prompt_hash=prompt_hash,
                output_hash=None,
            )

        content = self.response_for.get(
            file_path, f"# resolved content for {file_path}\nvalue = 42\n"
        )
        output_hash = hashlib.sha256(content.encode()).hexdigest()
        return LLMCallResult(
            file_path=file_path,
            abstained=False,
            proposed_content=content,
            error=None,
            model=model,
            cli_tool=cli_tool,
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=output_hash,
        )


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Replace invoke_llm_for_file with a deterministic fake.

    Returns the FakeLLM instance so tests can inspect call counts and args.
    """
    fake = FakeLLM()
    monkeypatch.setattr(
        "orch.daemon.auto_merge.invoke_llm_for_file",
        fake.invoke,
    )
    return fake


# ---------------------------------------------------------------------------
# Shared DB fixture for default runtime option
# ---------------------------------------------------------------------------


@pytest.fixture
def default_runtime_option(db_session: Session) -> AgentRuntimeOption:
    """Insert a default AgentRuntimeOption row for auto_merge tests."""
    return make_default_runtime_option(db_session)
