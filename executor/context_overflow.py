# SPDX-License-Identifier: MIT
"""Context-overflow detection for IW AI Core step execution.

Detects context-window-overflow signatures in agent runtime output so that
the step executor can finalize the step as a clean failure rather than
leaving it in a degraded state (causes 1–3 reduce the likelihood; this makes
the residual case fail honestly — AC4).

Overflow signatures are error-string constants kept here, not in config.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ------------------------------------------------------------------
# Overflow signatures — error strings each runtime emits when the model's
# context window is exceeded.
#
# These must remain exact matches (case-sensitive) so that false positives
# are impossible.  Each entry: (label, pattern)  where pattern is a raw
# string that appears verbatim in the runtime's output.
#
# Source: R-00078 findings + runtime documentation.
# ------------------------------------------------------------------

_OVERFLOW_SIGNATURES: list[tuple[str, str]] = [
    # Anthropic API — "400 invalid_request_error: ... context window exceeds limit"
    # (CR-00076 / I-00105 triggering incident; also opencode / pi on Anthropic models)
    (
        "anthropic_context_window_exceeded",
        "context window exceeds limit",
    ),
    # openai / compatible APIs — "context_length_exceeded"
    (
        "openai_context_length_exceeded",
        "context_length_exceeded",
    ),
    # Azure OpenAI
    (
        "azure_context_limit",
        "context_limit_exceeded",
    ),
    # Generic / catch-all patterns from opencode compaction docs
    (
        "opencode_context_overflow",
        "ContextOverflowError",
    ),
    # LiteLLM / proxy layer — wraps multiple backends
    (
        "litellm_context_exceeded",
        "Context window exceeded",
    ),
]

# Pre-compile for speed (unit tests exercise every pattern).
_COMPILED: list[tuple[str, re.Pattern[str]]] = [
    (label, re.compile(re.escape(pattern))) for label, pattern in _OVERFLOW_SIGNATURES
]

# Default blocker message — written to DB when a step fails with overflow.
_DEFAULT_BLOCKER = (
    "Step failed: agent runtime overflowed the model's context window. "
    "The agent did not call step-done.  "
    "This is a clean, clearly-attributed failure (AC4 / I-00105 root-cause 4).  "
    "Check .tool-cache for spilled output from this step; "
    "consider splitting the step into smaller pieces."
)


@dataclass(frozen=True)
class OverflowDetectionResult:
    """Result of scanning a log for context-overflow signatures."""

    detected: bool
    """True when an overflow signature was found in the log."""

    signatures_found: tuple[str, ...]
    """Labels of any signatures matched (empty when detected==False)."""

    blocker_message: str | None
    """Human-readable blocker message; only set when detected==True."""


def detect_context_overflow(
    text: str,
    *,
    blocker_message: str = _DEFAULT_BLOCKER,
) -> OverflowDetectionResult:
    """Return OverflowDetectionResult after scanning ``text`` for overflow signatures.

    Parameters
    ----------
    text:
        Raw text to scan — typically the full content of the agent runtime's
        captured output/log file.
    blocker_message:
        Message written to DB when overflow is detected.
        The default names I-00105 AC4 and the spill-file location so the
        operator knows exactly what happened and where to look.

    Returns
    -------
    OverflowDetectionResult
        ``detected=True`` when at least one signature matched; ``signatures_found``
        lists which labels did.  ``blocker_message`` is the supplied message
        when detected, else None.

    Notes
    -----
    - Scan is case-sensitive — avoids false positives on partial-word matches.
    - ``text`` may be large (hundreds of KB); the scan stops at the first match
      for each pattern to keep runtime O(length_of_text × num_signatures) but
      fast in the common (no overflow) case.
    - When ``detected`` is True the step must NOT be marked as succeeded.
      The executor uses this result to decide between ``step-done`` and
      ``step-fail --reason "<blocker>"``.
    """
    if not text:
        return OverflowDetectionResult(
            detected=False,
            signatures_found=(),
            blocker_message=None,
        )

    found: list[str] = []
    for label, pattern in _COMPILED:
        if pattern.search(text):
            found.append(label)
            # Continue scanning — collect ALL matching labels for diagnostics.
            # (At most 2–3 will match in practice.)

    if found:
        return OverflowDetectionResult(
            detected=True,
            signatures_found=tuple(found),
            blocker_message=blocker_message,
        )

    return OverflowDetectionResult(
        detected=False,
        signatures_found=(),
        blocker_message=None,
    )


def overflow_signatures() -> list[str]:
    """Return the list of all known overflow-signature labels (for tests)."""
    return [label for label, _ in _COMPILED]
