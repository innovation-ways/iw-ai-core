"""I-00044 e2e fixtures — fix slug mismatch between e2e_seed and module_gen.

The module Level-2 docs created by e2e_seed.py use slugs like
``iw-ai-core-<path>`` (e.g. ``iw-ai-core-dashboard``), but
``module_gen._make_slug()`` produces ``iw-ai-core-module-<path>`` (e.g.
``iw-ai-core-module-dashboard``).  This causes the fast-path cache lookup in
``code.py:get_module`` to miss, triggering the slow Ollama path which fails in
the E2E stack (no Ollama available).  Fix the slugs to match module_gen's
expectation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


MODULE_DOCS = [
    {
        "path": "orch/daemon",
        "title": "Orchestration Daemon",
        "content": (
            "# Orchestration Daemon\n\n"
            "The orchestration daemon is the single-threaded polling loop that\n"
            "drives the platform.\n\n"
            "## Responsibilities\n"
            "- Poll work_items every 60s for approved batches\n"
            "- Provision one git worktree per active item\n"
            "- Launch opencode or claude-code with the step prompt\n"
        ),
    },
    {
        "path": "dashboard",
        "title": "FastAPI Dashboard",
        "content": (
            "# FastAPI Dashboard\n\n"
            "The dashboard is a FastAPI + Jinja2 + htmx application that\n"
            "provides real-time visibility into the orchestration platform.\n\n"
            "## Pages\n"
            "- Project home with active items and daemon health\n"
            "- Work item detail with per-step logs and evidence\n"
        ),
    },
]


def seed(db: Session) -> None:
    for module in MODULE_DOCS:
        doc_id = f"module-{module['path'].replace('/', '-')}"
        pk = f"iw-ai-core:{doc_id}"
        existing = db.get(ProjectDoc, pk)
        if existing is not None:
            existing.slug = f"iw-ai-core-module-{module['path'].replace('/', '-')}"
            continue
        db.add(
            ProjectDoc(
                id=pk,
                project_id="iw-ai-core",
                doc_id=doc_id,
                title=module["title"],
                slug=f"iw-ai-core-module-{module['path'].replace('/', '-')}",
                doc_type=DocType.module,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=module["content"],
                version=1,
            )
        )
