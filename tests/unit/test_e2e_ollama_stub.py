"""Unit tests for scripts/e2e_ollama_stub.py — parser + reply builder.

The end-to-end contract with llama_index lives in
``tests/integration/test_e2e_ollama_stub.py`` (runs the stub as a
subprocess and exercises the pinned Ollama clients). These unit tests
cover the deterministic Python surface the stub exposes so regressions
to citation parsing / ranking are caught without a network-bound test.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_stub():
    """Import scripts/e2e_ollama_stub.py as a module without side effects."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "e2e_ollama_stub.py"
    spec = importlib.util.spec_from_file_location("e2e_ollama_stub_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _system_prompt_with_three_candidates() -> str:
    """Mirror the exact shape emitted by orch.rag.qa._build_workitem_system_prompt."""
    lines = [
        "## Work Item Context",
        "",
        "The following work items may be related to the user's question.",
        "",
        (
            "### Candidate 1: F-00060-ORIGINAL — "
            "New project button — original implementation (feature)"
        ),
        "The New project button enables users to create a new project workspace",
        "from the dashboard home.",
        "",
        (
            "### Candidate 2: CR-00060-RECOLOR — "
            "Recolor the New project button to blue (change_request)"
        ),
        "Changed the button background colour from grey to blue for visual emphasis.",
        "",
        (
            "### Candidate 3: CR-00060-RESHAPE — "
            "Reshape the button from circle to square (change_request)"
        ),
        "Changed the button from a circle shape to a square shape.",
        "",
    ]
    return "\n".join(lines)


class TestCandidateExtraction:
    def test_extracts_each_candidate_with_id_title_type(self) -> None:
        stub = _load_stub()
        messages = [{"role": "system", "content": _system_prompt_with_three_candidates()}]
        cands = stub._extract_workitem_candidates(messages)
        assert [c["id"] for c in cands] == [
            "F-00060-ORIGINAL",
            "CR-00060-RECOLOR",
            "CR-00060-RESHAPE",
        ]
        assert cands[0]["type"] == "feature"
        assert cands[1]["type"] == "change_request"
        assert "blue for visual emphasis" in cands[1]["content"]

    def test_code_only_prompt_yields_no_candidates(self) -> None:
        stub = _load_stub()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a codebase expert assistant. Answer questions "
                    "about the codebase accurately and concisely."
                ),
            },
        ]
        assert stub._extract_workitem_candidates(messages) == []

    def test_accepts_plain_five_digit_ids_too(self) -> None:
        """Not every seeded item uses the -SUFFIX convention — plain IDs must also parse."""
        stub = _load_stub()
        messages = [
            {
                "role": "system",
                "content": (
                    "## Work Item Context\n\n"
                    "### Candidate 1: CR-00011 — New project button feature (change_request)\n"
                    "Adds a button on the dashboard home.\n"
                ),
            },
        ]
        cands = stub._extract_workitem_candidates(messages)
        assert len(cands) == 1
        assert cands[0]["id"] == "CR-00011"


class TestCandidateRanking:
    def test_question_keyword_lands_recolor_first(self) -> None:
        """F-00060 V3: 'why is the button blue?' must rank the recolor item first,
        not the reshape item, so the allowlist filter emits only the relevant ID."""
        stub = _load_stub()
        messages = [{"role": "system", "content": _system_prompt_with_three_candidates()}]
        cands = stub._extract_workitem_candidates(messages)
        ranked = stub._rank_candidates(cands, "Why is the New project button blue?")
        assert ranked[0]["id"] == "CR-00060-RECOLOR"

    def test_question_about_creation_ranks_original_first(self) -> None:
        """F-00060 V2: 'when was the button created?' must rank the original
        feature item first, not a change request."""
        stub = _load_stub()
        messages = [{"role": "system", "content": _system_prompt_with_three_candidates()}]
        cands = stub._extract_workitem_candidates(messages)
        ranked = stub._rank_candidates(
            cands,
            "When was the New project button created? What does it do?",
        )
        assert ranked[0]["id"] == "F-00060-ORIGINAL"

    def test_ranking_is_stable_on_ties(self) -> None:
        """When no keyword matches, the original parse order must be preserved
        so the stub reply is fully deterministic."""
        stub = _load_stub()
        messages = [{"role": "system", "content": _system_prompt_with_three_candidates()}]
        cands = stub._extract_workitem_candidates(messages)
        ranked = stub._rank_candidates(cands, "xyz")  # no overlap → scores all 0
        assert [c["id"] for c in ranked] == [c["id"] for c in cands]


class TestReplyBuilder:
    def test_workitem_reply_cites_top_candidate_with_bracket_marker(self) -> None:
        """The first non-whitespace characters of the reply must be ``[1]`` so
        citation_allowlist.extract_citations (which looks for ``[N]``) finds
        the citation. The cited ID must be one of the allowed candidate IDs."""
        stub = _load_stub()
        messages = [{"role": "system", "content": _system_prompt_with_three_candidates()}]
        cands = stub._extract_workitem_candidates(messages)
        reply = stub._build_reply(
            None,
            "Why is the New project button blue?",
            candidates=cands,
        )
        assert reply.lstrip().startswith("[1]")
        # The cited ID must come from the candidates (allowlist guarantee).
        cited_ids = [c["id"] for c in cands if c["id"] in reply]
        assert "CR-00060-RECOLOR" in cited_ids
        # And the reply must not invent an un-allowed ID that looks similar.
        assert "CR-99999" not in reply

    def test_code_only_reply_does_not_include_citations(self) -> None:
        """F-00060 V5: code-only questions get the plain echo reply — no
        [N] markers, no citation panel, no work-item context injection."""
        stub = _load_stub()
        reply = stub._build_reply(
            None,
            "Show me the signature of classify_query",
            candidates=[],
        )
        assert "[1]" not in reply
        assert "deterministic stub response" in reply

    def test_module_ref_fallback_preserved(self) -> None:
        """Pre-F-00060 verifications (code/module views) depend on the
        ``module_ref`` echo path — it must not regress."""
        stub = _load_stub()
        reply = stub._build_reply("orch/rag", "hello", candidates=[])
        assert "`orch/rag`" in reply
