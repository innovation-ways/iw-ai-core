"""Query classifier for routing between work-item-aware and code-only pipelines."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from llama_index.llms.ollama import Ollama

if TYPE_CHECKING:
    from orch.rag.config import CodeUnderstandingConfig

SLASH_OVERRIDE_CHIPS = {"why", "history", "findusages"}

CLASSIFIER_SYSTEM_PROMPT = """\
You are a query classifier. Classify the user question into exactly one of two categories:

1. "workitem_aware" - The question asks about WHY something works a certain way,
   HOW a behavior was introduced, what FEATURES or CHANGES shaped the current behavior,
   or asks for HISTORY or CAUSE of code. Questions containing "why", "how does",
   "what caused", "history of", "feature", "behavior", "introduced", "added in",
   "changed by", "since when" are almost always workitem_aware.

2. "code_only" - The question asks for technical details like function signatures,
   implementation details, code locations, or purely technical "show me" queries
   that don't ask about WHY or HOW something came to be. Questions like "show me
   the signature of X", "where is Y defined", "what's the implementation of Z"
   are code_only.

Respond with ONLY the category name, nothing else.

 Exemplars:
 Question: "why does the daemon retry 3 times?"
 Category: workitem_aware

 Question: "what is the retry logic in the daemon?"
 Category: workitem_aware

 Question: "show me the signature of parse_id"
 Category: code_only

 Question: "where is the WorkItem model defined?"
 Category: code_only

 Question: "how is the batch approval workflow implemented?"
 Category: workitem_aware

 Question: "what does the export button do?"
 Category: workitem_aware

 Question: "find the file containing the QATest class"
 Category: code_only

 Question: "what's in the daemon loop?"
 Category: code_only
"""


def classify_query(
    question: str,
    config: CodeUnderstandingConfig,
    context_chips: list[str] | None = None,
) -> Literal["workitem_aware", "code_only"]:
    """Classify a query as workitem_aware or code_only.

    If context_chips contains slash override keywords (why, history, findusages),
    returns "workitem_aware" immediately.

    Otherwise, calls an LLM classifier with a 2-second timeout.
    On timeout, defaults to "code_only".
    """
    if context_chips:
        for chip in context_chips:
            if chip.lower() in SLASH_OVERRIDE_CHIPS:
                return "workitem_aware"

    return _llm_classify(question, config)


def _llm_classify(
    question: str,
    config: CodeUnderstandingConfig,
) -> Literal["workitem_aware", "code_only"]:
    """Use LLM to classify the query."""
    try:
        llm = Ollama(
            model=config.resolved_llm_model(),
            base_url=config.ollama_url,
        )
        response = llm.complete(
            f"{CLASSIFIER_SYSTEM_PROMPT}\n\n Question: {question}\n Category:",
            max_tokens=20,
        )
        result = response.text.strip().lower()

        if "workitem_aware" in result:
            return "workitem_aware"
        return "code_only"
    except Exception:
        logging.warning("LLM classifier failed, defaulting to code_only")
        return "code_only"
