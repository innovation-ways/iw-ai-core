"""Citation allowlist filter for stripping hallucinated work-item IDs from LLM output."""

from __future__ import annotations

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

WORK_ITEM_ID_PATTERN = re.compile(r"\b(F|CR|I)-\d{5}\b")


def filter_citations(
    text: str,
    allowed_ids: set[str],
) -> tuple[str, list[str]]:
    """Filter work-item IDs from text, keeping only those in allowed_ids.

    Args:
        text: The LLM output text to filter.
        allowed_ids: Set of permitted work-item IDs.

    Returns:
        Tuple of (filtered_text, list_of_stripped_ids).
    """
    stripped_ids: list[str] = []

    def replace_match(match: re.Match[str]) -> str:
        wi_id = match.group(0)
        if wi_id not in allowed_ids:
            stripped_ids.append(wi_id)
            logger.warning(
                "Citation allowlist stripped hallucinated ID: %s | Context: %s",
                wi_id,
                text[max(0, match.start() - 40) : match.end() + 40],
            )
            return ""
        return wi_id

    filtered_text = WORK_ITEM_ID_PATTERN.sub(replace_match, text)
    return filtered_text, stripped_ids


def extract_citations(text: str) -> list[str]:
    """Extract all work-item ID citations from text.

    Returns list of IDs in order of appearance (deduplicated).
    """
    seen: set[str] = set()
    ids: list[str] = []

    for match in WORK_ITEM_ID_PATTERN.finditer(text):
        wi_id = match.group(0)
        if wi_id not in seen:
            seen.add(wi_id)
            ids.append(wi_id)

    return ids


def validate_citation(
    wi_id: str,
    allowed_ids: set[str],
) -> Literal["valid", "stripped"]:
    """Validate a single work-item ID citation.

    Returns "valid" if in allowed_ids, "stripped" otherwise.
    """
    return "valid" if wi_id in allowed_ids else "stripped"
