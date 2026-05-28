from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from orch.db.models import AgentRuntimeOption, ChatTab, Project


PROJECT_A = "iw-ai-core"
PROJECT_B = "innoforge"


def _ensure_project_b(db: Session) -> None:
    if db.get(Project, PROJECT_B) is None:
        db.add(
            Project(
                id=PROJECT_B,
                display_name="Innoforge (E2E)",
                repo_root="/app",
                config={"code_understanding": {"provider": "local", "index_tier": "fast"}},
                enabled=True,
            )
        )


def _ensure_runtime_options(db: Session) -> None:
    known = db.scalar(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.cli_tool == "opencode",
            AgentRuntimeOption.model == "anthropic/claude-sonnet-4-7",
        )
    )
    if known is None:
        db.add(
            AgentRuntimeOption(
                cli_tool="opencode",
                model="anthropic/claude-sonnet-4-7",
                cli_label="OpenCode",
                model_label="Claude Sonnet 4.7",
                display_name="OpenCode · Claude Sonnet 4.7",
                enabled=True,
                sort_order=10,
                context_window_tokens=200000,
                max_output_tokens=64000,
            )
        )
    else:
        known.context_window_tokens = 200000
        known.max_output_tokens = 64000
        known.enabled = True

    unknown = db.scalar(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.cli_tool == "opencode",
            AgentRuntimeOption.model == "openai/gpt-4.1-mini",
        )
    )
    if unknown is None:
        db.add(
            AgentRuntimeOption(
                cli_tool="opencode",
                model="openai/gpt-4.1-mini",
                cli_label="OpenCode",
                model_label="GPT-4.1 mini",
                display_name="OpenCode · GPT-4.1 mini",
                enabled=True,
                sort_order=20,
                context_window_tokens=None,
                max_output_tokens=None,
            )
        )
    else:
        unknown.context_window_tokens = None
        unknown.max_output_tokens = None
        unknown.enabled = True


def _ensure_tab(db: Session, project_id: str, title: str, model: str) -> None:
    existing = db.scalar(
        select(ChatTab).where(
            ChatTab.project_id == project_id,
            ChatTab.title == title,
            ChatTab.status == "active",
        )
    )
    if existing is None:
        db.add(
            ChatTab(
                project_id=project_id,
                title=title,
                runtime="opencode",
                model=model,
                status="active",
            )
        )


def seed(db: Session) -> None:
    _ensure_project_b(db)
    db.flush()
    _ensure_runtime_options(db)
    db.flush()

    _ensure_tab(db, PROJECT_A, "A-Known-Context", "anthropic/claude-sonnet-4-7")
    _ensure_tab(db, PROJECT_A, "A-Unknown-Context", "openai/gpt-4.1-mini")
    _ensure_tab(db, PROJECT_B, "B-Only-Tab", "anthropic/claude-sonnet-4-7")
