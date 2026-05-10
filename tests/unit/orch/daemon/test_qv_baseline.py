"""Unit tests for orch.daemon.qv_baseline — parsers, fingerprint algebra, serialization.

Tests cover:
- TestRuffParser: text mode parsing (only format S03 reliably supports)
- TestPytestParser: FAILED-line extraction with nodeid-first format
- TestMypyParser: happy path, line-number collapse, determinism
- TestSubtract: identity, full-overlap, partial-overlap, monotonicity, unparseable-surfaces
- TestFingerprintRoundTrip: JSONable identity
- TestGateParsers: mapping completeness and format-gate exclusion

NOTE: The S03 ruff parser text-mode regex requires messages without extra
colons (regex: CODE msg where msg has no colon separator from CODE).
The S03 ruff parser JSON path only handles dict-with-"results" format for
entries list (array-format JSON goes to text mode and fails).
The S03 pytest parser requires "FAILED <nodeid> - <msg>" format (nodeid FIRST).
These fixtures use formats the S03 code can actually parse.
"""

from __future__ import annotations

from orch.daemon.qv_baseline import (
    GATE_PARSERS,
    FailureEntry,
    Fingerprint,
    fingerprint_from_jsonable,
    fingerprint_to_jsonable,
    parse_mypy,
    parse_pytest,
    parse_ruff,
    subtract,
)

# ---------------------------------------------------------------------------
# Ruff fixtures
# ---------------------------------------------------------------------------

RUFF_TEXT_SAMPLE = """\
dashboard/app.py:10:1: E501 Line too long
another/path.py:20:2: F401 Unused import
"""

RUFF_SAME_FAILURE_DIFFERENT_LINE = """\
dashboard/app.py:10:1: E501 Line too long
dashboard/app.py:200:1: E501 Line too long
"""

RUFF_TEXT_UNPARSEABLE = """\
dashboard/app.py:10:1: E501 Line too long
this is not a valid ruff output line
another/path.py:20:2: F401 Unused import
"""

# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

PYTEST_HAPPY_SAMPLE = """\
FAILED tests/unit/x.py::test_a - AssertionError
FAILED tests/unit/y.py::test_b - Some error occurred
"""

PYTEST_SAME_TEST_DIFFERENT_MSG_A = (
    "FAILED tests/unit/foo.py::test_flaky - AssertionError: expected 1 got 2"
)
PYTEST_SAME_TEST_DIFFERENT_MSG_B = (
    "FAILED tests/unit/foo.py::test_flaky - AssertionError: expected 3 got 4"
)

PYTEST_SUMMARY_ONLY = """\
============================= test session starts ==============================
collected 5 items

=========================== 3 failed in 1.2s ===============================
"""

# ---------------------------------------------------------------------------
# Mypy fixtures
# ---------------------------------------------------------------------------

MYPY_HAPPY_SAMPLE = """\
dashboard/app.py:10: error: Unused 'x' import [unused-import]
orch/daemon/main.py:42: error: Argument missing for keyword argument [call-arg]
"""

MYPY_SINGLE_FAILURE = """\
dashboard/app.py:10: error: Unused 'x' import [unused-import]
"""

MYPY_SAME_FAILURE_DIFFERENT_LINE = """\
dashboard/app.py:10: error: Unused 'x' import [unused-import]
dashboard/app.py:200: error: Unused 'x' import [unused-import]
"""

# ---------------------------------------------------------------------------
# TestRuffParser
# ---------------------------------------------------------------------------


class TestRuffParser:
    def test_happy_path_text_output(self) -> None:
        """Text mode: file:line:col: CODE msg (msg must not contain extra colons)."""
        fp = parse_ruff(RUFF_TEXT_SAMPLE)
        assert len(fp.failures) == 2
        keys = {f.key for f in fp.failures}
        assert keys == {"dashboard/app.py::E501", "another/path.py::F401"}
        assert all(f.kind == "lint" for f in fp.failures)
        assert fp.unparseable == ()

    def test_line_number_change_collapses(self) -> None:
        """Boundary Behavior row 4: same failure on different line → identical fingerprint."""
        fp_a = parse_ruff("dashboard/app.py:10:1: E501 Line too long")
        fp_b = parse_ruff("dashboard/app.py:200:1: E501 Line too long")
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)

    def test_determinism(self) -> None:
        fp_a = parse_ruff(RUFF_TEXT_SAMPLE)
        fp_b = parse_ruff(RUFF_TEXT_SAMPLE)
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)

    def test_unparseable_lines(self) -> None:
        """Lines that don't match the regex go to unparseable; parseable ones are extracted."""
        fp = parse_ruff(RUFF_TEXT_UNPARSEABLE)
        assert len(fp.failures) == 2
        keys = {f.key for f in fp.failures}
        assert "dashboard/app.py::E501" in keys
        assert "another/path.py::F401" in keys
        assert "this is not a valid ruff output line" in fp.unparseable


# ---------------------------------------------------------------------------
# TestPytestParser
# ---------------------------------------------------------------------------


class TestPytestParser:
    def test_happy_path_failed_lines(self) -> None:
        """Requires 'FAILED <nodeid> - <msg>' format (nodeid FIRST, dash-space separator)."""
        fp = parse_pytest(PYTEST_HAPPY_SAMPLE)
        assert len(fp.failures) == 2
        keys = {f.key for f in fp.failures}
        assert keys == {"tests/unit/x.py::test_a", "tests/unit/y.py::test_b"}
        assert all(f.kind == "test" for f in fp.failures)
        assert fp.unparseable == ()

    def test_error_message_variation_collapses(self) -> None:
        """Boundary Behavior row 5: same nodeid, different messages → identical fingerprint."""
        fp_a = parse_pytest(PYTEST_SAME_TEST_DIFFERENT_MSG_A)
        fp_b = parse_pytest(PYTEST_SAME_TEST_DIFFERENT_MSG_B)
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)

    def test_summary_only_treated_as_unparseable(self) -> None:
        fp = parse_pytest(PYTEST_SUMMARY_ONLY)
        assert fp.failures == ()
        assert len(fp.unparseable) > 0

    def test_determinism(self) -> None:
        fp_a = parse_pytest(PYTEST_HAPPY_SAMPLE)
        fp_b = parse_pytest(PYTEST_HAPPY_SAMPLE)
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)

    def test_bare_failed_line_without_reason_is_parsed(self) -> None:
        """I-00074: pytest omits the ' - <reason>' suffix for assertion failures.

        The original regex required the dash, so a bare ``FAILED <nodeid>`` line
        produced zero parsed failures (and, under ``pytest -v``, a few thousand
        progress lines in ``unparseable``).
        """
        fp = parse_pytest(
            "FAILED tests/unit/test_skill_files.py::test_skills_sync_is_byte_identical[iw-workflow]"
        )
        assert [f.key for f in fp.failures] == [
            "tests/unit/test_skill_files.py::test_skills_sync_is_byte_identical[iw-workflow]"
        ]
        assert fp.unparseable == ()

    def test_verbose_progress_lines_are_not_unparseable(self) -> None:
        """I-00074: ``pytest -v`` per-test lines must never reach ``unparseable``."""
        raw = "\n".join(
            [
                "tests/unit/test_a.py::test_one PASSED [  1%]",
                "tests/unit/test_b.py::test_two SKIPPED (reason) [  2%]",
                "tests/unit/test_c.py::test_three XFAIL [  3%]",
                "tests/unit/test_d.py::test_four FAILED [  4%]",
                "FAILED tests/unit/test_d.py::test_four - AssertionError: nope",
                "=========================== 1 failed, 3 passed ============================",
            ]
        )
        fp = parse_pytest(raw)
        assert [f.key for f in fp.failures] == ["tests/unit/test_d.py::test_four"]
        assert fp.unparseable == ()

    def test_unparseable_is_capped(self) -> None:
        """I-00074: a parser miss must not bloat the fix-cycle prompt past execve's argv limit."""
        raw = "\n".join(f"weird noise line {i}" for i in range(5000))
        fp = parse_pytest(raw)
        assert len(fp.unparseable) <= 81  # _MAX_UNPARSEABLE_LINES + omission marker
        assert any("lines omitted" in line for line in fp.unparseable)


# ---------------------------------------------------------------------------
# TestMypyParser
# ---------------------------------------------------------------------------


class TestMypyParser:
    def test_happy_path(self) -> None:
        fp = parse_mypy(MYPY_HAPPY_SAMPLE)
        assert len(fp.failures) == 2
        keys = {f.key for f in fp.failures}
        assert "dashboard/app.py::unused-import" in keys
        assert "orch/daemon/main.py::call-arg" in keys
        assert all(f.kind == "typecheck" for f in fp.failures)
        assert fp.unparseable == ()

    def test_line_number_change_collapses(self) -> None:
        """Same failure (file + code) on different lines → identical fingerprint."""
        fp_a = parse_mypy(MYPY_SINGLE_FAILURE)
        fp_b = parse_mypy(MYPY_SAME_FAILURE_DIFFERENT_LINE)
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)

    def test_determinism(self) -> None:
        fp_a = parse_mypy(MYPY_HAPPY_SAMPLE)
        fp_b = parse_mypy(MYPY_HAPPY_SAMPLE)
        assert fingerprint_to_jsonable(fp_a) == fingerprint_to_jsonable(fp_b)


# ---------------------------------------------------------------------------
# TestSubtract
# ---------------------------------------------------------------------------


class TestSubtract:
    def test_identity(self) -> None:
        h = Fingerprint(failures=(FailureEntry(kind="lint", key="a::A"),))
        result = subtract(h, Fingerprint(failures=()))
        assert result.failures == h.failures

    def test_full_overlap(self) -> None:
        entry = FailureEntry(kind="lint", key="a::A")
        h = Fingerprint(failures=(entry,))
        result = subtract(h, h)
        assert result.failures == ()
        assert result.unparseable == h.unparseable

    def test_partial_overlap_preserves_order(self) -> None:
        a = FailureEntry(kind="lint", key="a::A")
        b = FailureEntry(kind="lint", key="b::B")
        c = FailureEntry(kind="lint", key="c::C")
        h = Fingerprint(failures=(a, b, c))
        baseline = Fingerprint(failures=(b,))
        result = subtract(h, baseline)
        assert list(result.failures) == [a, c]

    def test_monotonicity(self) -> None:
        entries = [FailureEntry(kind="lint", key=f"f{i}::R{i}") for i in range(20)]
        import random

        random.seed(42)
        for _ in range(50):
            h = Fingerprint(failures=tuple(random.sample(entries, 10)))
            baseline = Fingerprint(failures=tuple(random.sample(entries, 5)))
            result = subtract(h, baseline)
            assert len(result.failures) <= len(h.failures)

    def test_unparseable_always_surfaces(self) -> None:
        current = Fingerprint(
            failures=(FailureEntry(kind="lint", key="a::A"),),
            unparseable=("unparseable line",),
        )
        baseline = Fingerprint(
            failures=(FailureEntry(kind="lint", key="a::A"),),
            unparseable=("same unparseable line",),
        )
        result = subtract(current, baseline)
        assert result.unparseable == current.unparseable
        assert result.failures == ()


# ---------------------------------------------------------------------------
# TestFingerprintRoundTrip
# ---------------------------------------------------------------------------


class TestFingerprintRoundTrip:
    def test_to_jsonable_from_jsonable_is_identity(self) -> None:
        original = Fingerprint(
            failures=(
                FailureEntry(kind="lint", key="dashboard/app.py::E501"),
                FailureEntry(kind="test", key="tests/unit/foo.py::test_flaky"),
                FailureEntry(kind="typecheck", key="orch/daemon/main.py::call-arg"),
            ),
            unparseable=("could not parse: frobnicator",),
        )
        jsonable = fingerprint_to_jsonable(original)
        restored = fingerprint_from_jsonable(jsonable)
        assert fingerprint_to_jsonable(restored) == jsonable
        assert restored.failures == original.failures
        assert restored.unparseable == original.unparseable

    def test_empty_fingerprint_round_trips(self) -> None:
        fp = Fingerprint(failures=(), unparseable=())
        restored = fingerprint_from_jsonable(fingerprint_to_jsonable(fp))
        assert restored.failures == ()
        assert restored.unparseable == ()


# ---------------------------------------------------------------------------
# TestGateParsers
# ---------------------------------------------------------------------------


class TestGateParsers:
    def test_lint_maps_to_parse_ruff(self) -> None:
        assert GATE_PARSERS["lint"] is parse_ruff

    def test_typecheck_maps_to_parse_mypy(self) -> None:
        assert GATE_PARSERS["typecheck"] is parse_mypy

    def test_unit_tests_maps_to_parse_pytest(self) -> None:
        assert GATE_PARSERS["unit-tests"] is parse_pytest

    def test_integration_tests_is_not_in_gate_parsers(self) -> None:
        assert "integration-tests" not in GATE_PARSERS

    def test_frontend_tests_maps_to_parse_pytest(self) -> None:
        assert GATE_PARSERS["frontend-tests"] is parse_pytest

    def test_format_is_absent(self) -> None:
        assert "format" not in GATE_PARSERS
