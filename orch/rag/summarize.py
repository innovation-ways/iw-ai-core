"""Conversation compaction — rolling summary via LLM.

summarize_history(messages, llm) produces a compact prose summary that
preserves named entities (file paths, function names, work-item IDs),
user-stated facts, and decisions reached.
"""

from __future__ import annotations

import logging
from typing import Any

from llama_index.llms.ollama import Ollama

logger = logging.getLogger(__name__)

BaseLLM = Ollama

__all__ = ["BaseLLM", "summarize_history"]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SUMMARIZE_PROMPT = """\
Summarize the conversation below into a compact note that PRESERVES:
- Named entities (file paths, function names, work-item IDs like F-00055,
  module names, error messages quoted verbatim).
- Specific facts the user stated about themselves or their project (names,
  goals, preferences).
- Decisions reached or conclusions drawn.
- The user's current investigative thread (what they're trying to figure out).

DROP: pleasantries, rephrasing, the assistant's reasoning chain. Keep it
factual.

If a "Previous summary" is provided, EXTEND or REFINE it; don't restart.

Output 3-8 sentences.

{previous_section}

Conversation:
{conversation}

Summary:"""


def summarize_history(
    messages: list[object],
    llm: Any,
    previous_summary: str | None = None,
) -> str:
    """Produce a compact prose summary from a list of ChatMessage objects.

    Raises on LLM exception (caller handles as failed job).
    """
    # Build conversation text for the prompt
    conversation_lines = "\n".join(
        f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in messages
    )

    previous_section = f"Previous summary:\n{previous_summary}\n\n" if previous_summary else ""

    prompt = SUMMARIZE_PROMPT.format(
        previous_section=previous_section,
        conversation=conversation_lines,
    )

    try:
        response = llm.chat([{"role": "user", "content": prompt}])
        content = getattr(getattr(response, "message", None), "content", "") or ""
        return content.strip()
    except Exception:
        logger.exception("summarize_history LLM call failed")
        raise
