"""Unit tests for wrap_h2_sections_collapsible in dashboard/utils/markdown.py."""

from __future__ import annotations

from dashboard.utils.markdown import wrap_h2_sections_collapsible


class TestWrapH2SectionsCollapsible:
    """Tests for wrap_h2_sections_collapsible — wraps each H2 + content in <details>."""

    def test_purpose_h2_renders_open(self) -> None:
        """The first H2 in document order gets the open attribute."""
        html_in = "<h1>Title</h1><h2>Purpose</h2><p>p1</p>"
        out = wrap_h2_sections_collapsible(html_in)
        # Accept both <details open> and <details open=""> (BeautifulSoup output)
        assert (
            '<details open=""><summary>Purpose</summary>' in out
            or "<details open><summary>Purpose</summary>" in out
        ), f"Expected Purpose H2 wrapped with open attribute. Got:\n{out}"
        assert "<p>p1</p>" in out

    def test_subsequent_h2s_render_closed(self) -> None:
        """Non-first H2s are wrapped in <details> without the open attribute."""
        html_in = "<h2>A</h2><p>a</p><h2>B</h2><p>b</p>"
        out = wrap_h2_sections_collapsible(html_in)
        # First H2 must be open
        assert (
            '<details open=""><summary>A</summary>' in out
            or "<details open><summary>A</summary>" in out
        ), f"Expected first H2 (A) to be open. Got:\n{out}"
        # Second H2 must NOT be open
        assert (
            '<details open=""><summary>B</summary>' in out
            or "<details open><summary>B</summary>" in out
        ) is False, f"Second H2 (B) must not be open. Got:\n{out}"
        # Second H2 must be wrapped in a closed details
        assert (
            "<details><summary>B</summary>" in out
            or '<details open=""><summary>B</summary>' not in out
        )

    def test_pre_h1_content_left_at_top_level(self) -> None:
        """Content before the first H2 must remain outside any <details> block."""
        html_in = "<h1>Title</h1><p>intro</p><h2>Purpose</h2><p>body</p>"
        out = wrap_h2_sections_collapsible(html_in)
        # The intro paragraph must NOT be inside a <details>
        assert "<p>intro</p>" in out
        purpose_idx = out.find("<details")
        assert purpose_idx != -1, "Expected at least one <details> tag in output"
        assert out.find("<p>intro</p>") < purpose_idx, (
            "Intro paragraph must appear BEFORE the first <details> block"
        )

    def test_no_h2_returns_input_unchanged(self) -> None:
        """HTML with no H2 elements is returned verbatim (idempotent base case)."""
        html_in = "<h1>X</h1><p>only paragraph</p>"
        assert wrap_h2_sections_collapsible(html_in) == html_in

    def test_idempotent(self) -> None:
        """Running the helper twice must produce identical output."""
        html_in = "<h2>A</h2><p>a</p><h2>B</h2><p>b</p>"
        once = wrap_h2_sections_collapsible(html_in)
        twice = wrap_h2_sections_collapsible(once)
        assert once == twice, (
            "Helper must be idempotent — applying it twice produces identical output.\n"
            f"First pass:\n{once}\nSecond pass:\n{twice}"
        )

    def test_body_html_preserved(self) -> None:
        """Complex inline HTML inside an H2 section is preserved in the output."""
        html_in = "<h2>Components</h2><ul><li><strong>X</strong> (<code>x/</code>)</li></ul>"
        out = wrap_h2_sections_collapsible(html_in)
        assert "<ul><li><strong>X</strong> (<code>x/</code>)</li></ul>" in out

    def test_wrap_h2_only_purpose_open(self) -> None:
        """RED reproduction test — only Purpose (first H2) should be open."""
        html_in = "<h1>Title</h1>\n<h2>Purpose</h2>\n<p>p1</p>\n<h2>Components</h2>\n<p>p2</p>"
        out = wrap_h2_sections_collapsible(html_in)
        assert (
            '<details open=""><summary>Purpose</summary>' in out
            or "<details open><summary>Purpose</summary>" in out
        ), f"Expected Purpose H2 wrapped open. Got:\n{out}"
        assert (
            '<details open=""><summary>Components</summary>' in out
            or "<details open><summary>Components</summary>" in out
        ) is False, f"Components H2 must not be open. Got:\n{out}"
        assert "<p>p1</p>" in out
        assert "<p>p2</p>" in out
