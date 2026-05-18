"""CR-00057 e2e fixture — seed Project.config["ai_assistant"] for iw-ai-core.

The e2e DB starts empty, so scripts/e2e_seed.py::_seed_project creates the
iw-ai-core Project row with only the code_understanding sub-config. The
chat allowlist contract (CR-00057) lives under config["ai_assistant"];
without this fixture the browser_verification chat router falls open and
V1/V2 see the full provider list instead of the curated 5.

The values mirror `[projects.iw-ai-core.ai_assistant]` in projects.toml at
the time of CR-00057. If the toml block drifts, update both this fixture
and the V1/V2 assertions in
ai-dev/active/CR-00057/prompts/CR-00057_S15_BrowserVerification_prompt.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"

AI_ASSISTANT_CONFIG = {
    "models": [
        "anthropic/claude-opus-4-7",
        "anthropic/claude-sonnet-4-6",
        "minimax/MiniMax-M2.7",
        "openai/gpt-5.3-codex",
        "ollama/gemma4:26b",
    ],
    "default_model": "anthropic/claude-opus-4-7",
}


def seed(db: Session) -> None:
    project = db.get(Project, PROJECT_ID)
    if project is None:
        # Defensive: the central seed (_seed_project) runs first and should
        # always create the row. If somehow missing, do nothing — the chat
        # router will fall open and S15 will report the gap loudly.
        return
    current = dict(project.config or {})
    current["ai_assistant"] = AI_ASSISTANT_CONFIG
    project.config = current
