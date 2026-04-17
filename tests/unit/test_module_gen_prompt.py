"""Unit tests for the filler-preamble stripper used on Level 2 module answers."""

from __future__ import annotations

import pytest


def test_strip_list_intro_based_on_provided_code():
    from orch.rag.module_gen import _strip_filler_preamble

    text = (
        "Based on the provided code, the key entry points and public "
        "interfaces of the Orchestration Daemon are:\n- main.py\n- daemon.py"
    )
    assert _strip_filler_preamble(text) == "- main.py\n- daemon.py"


def test_strip_according_to_the_code():
    from orch.rag.module_gen import _strip_filler_preamble

    text = "According to the code, the key files are:\n* a.py\n* b.py"
    assert _strip_filler_preamble(text) == "* a.py\n* b.py"


def test_strip_looking_at_the_excerpts():
    from orch.rag.module_gen import _strip_filler_preamble

    text = "Looking at the excerpts, the primary responsibilities are:\nX and Y."
    assert _strip_filler_preamble(text) == "X and Y."


def test_strip_from_the_context():
    from orch.rag.module_gen import _strip_filler_preamble

    text = "From the context provided, the external dependencies are: httpx, sqlalchemy."
    assert _strip_filler_preamble(text) == "httpx, sqlalchemy."


def test_noop_on_prose_without_colon():
    from orch.rag.module_gen import _strip_filler_preamble

    # Prose that happens to begin with "Based on" but doesn't end with a colon
    # is NOT stripped — could contain real content.
    text = "Based on the code, the daemon polls PostgreSQL every 60 seconds."
    assert _strip_filler_preamble(text) == text


def test_noop_on_clean_answer():
    from orch.rag.module_gen import _strip_filler_preamble

    text = "The Orchestration Daemon polls PostgreSQL every 60 seconds."
    assert _strip_filler_preamble(text) == text


def test_noop_on_empty():
    from orch.rag.module_gen import _strip_filler_preamble

    assert _strip_filler_preamble("") == ""


def test_strip_double_preamble():
    from orch.rag.module_gen import _strip_filler_preamble

    text = (
        "Based on the provided code, the entry points are:\n"
        "According to the excerpts, the key files are:\n"
        "- main.py"
    )
    assert _strip_filler_preamble(text) == "- main.py"


@pytest.mark.parametrize(
    "opener",
    [
        "Based on the provided code,",
        "based on the context,",
        "According to the provided information,",
        "From the code snippets shown,",
        "Looking at these excerpts,",
        "Referring to the documentation above,",
    ],
)
def test_variety_of_openers(opener: str):
    from orch.rag.module_gen import _strip_filler_preamble

    text = f"{opener} the dependencies are:\n- a\n- b"
    assert _strip_filler_preamble(text) == "- a\n- b"
