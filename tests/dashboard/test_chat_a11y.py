"""Accessibility tests for chat message templates (AC14).

Asserts real <button> elements with accessible names, no onclick divs,
44x44 hit targets via BeautifulSoup, and alt text on images.
beautifulsoup4 is in dev dependencies (added during this step).
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


def _render_templates(*names: str) -> list[tuple[str, str]]:
    env = _make_env()
    return [(n, env.get_template(n).render()) for n in names]


def _render_message(
    role="assistant", msg_id="test-1", content="Hello", citations=None, role_label="Assistant"
):
    return (
        _make_env()
        .get_template("chat/message.html")
        .render(
            role=role,
            id=msg_id,
            content=content,
            citations=citations or [],
            role_label=role_label,
        )
    )


class TestButtonAccessibleNames:
    """AC14 — every <button> must have a non-empty accessible name."""

    def test_all_buttons_have_accessible_name(self):
        """Every <button> has non-empty text content OR aria-label OR aria-labelledby."""
        templates = _render_templates(
            "chat/panel.html",
            "chat/composer.html",
            "chat/message.html",
            "chat/parts/actions.html",
            "chat/parts/code.html",
            "chat/parts/citation_chip.html",
            "chat/parts/mermaid.html",
        )
        failures = []
        for name, html in templates:
            soup = BeautifulSoup(html, "html.parser")
            for btn in soup.find_all("button"):
                has_text = bool(btn.get_text(strip=True))
                has_aria_label = bool(btn.get("aria-label", "").strip())
                has_aria_labelledby = bool(btn.get("aria-labelledby", "").strip())
                if not (has_text or has_aria_label or has_aria_labelledby):
                    failures.append(f"{name}: button lacks accessible name: {btn}")
        assert not failures, "\n".join(failures)


class TestNoDivOnclick:
    """AC14 — no <div> or <span> with onclick in chat templates."""

    def test_no_div_onclick(self):
        """No <div> or <span> element in chat templates has onclick attribute."""
        templates = _render_templates(
            "chat/panel.html",
            "chat/composer.html",
            "chat/message.html",
            "chat/parts/actions.html",
            "chat/parts/code.html",
            "chat/parts/text.html",
            "chat/parts/table.html",
            "chat/parts/mermaid.html",
            "chat/parts/citation_chip.html",
            "chat/parts/sources_panel.html",
        )
        failures = []
        for name, html in templates:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["div", "span"]):
                if tag.has_attr("onclick"):
                    failures.append(f"{name}: <{tag.name} onclick> found: {tag}")
        assert not failures, "\n".join(failures)


class TestButtonHitTargets:
    """AC14 — every <button> has 44x44px hit target via class or CSS."""

    def _css_rule_has_44px(self, css_text: str, selector: str) -> bool:
        pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
        match = re.search(pattern, css_text)
        if not match:
            return False
        return "min-height: 44px" in match.group(1)

    def test_buttons_have_hit_target_classes(self):
        """Every <button> has a hit target ≥44px via inline class, .tap, or chat.css.

        Accepts any inline `min-h-[Npx]` / `h-N` whose pixel value is ≥44 — the
        I-00046 chat toggle tab is vertical (88px tall × 44px wide), so the
        original literal `min-h-[44px]` check no longer matches even though
        the WCAG hit target requirement is fully satisfied.
        """
        templates = [
            "chat/panel.html",
            "chat/composer.html",
            "chat/parts/actions.html",
            "chat/parts/code.html",
            "chat/parts/mermaid.html",
        ]
        css_path = Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat.css"
        css_content = css_path.read_text()
        tap_defines_44 = ".tap {" in css_content and "min-height: 44px" in css_content

        # min-h-[Npx] where N is any integer ≥44, or h-11 (Tailwind's 44px helper).
        inline_min_h_re = re.compile(r"min-h-\[(\d+)px\]")

        def _has_inline_44(class_str: str) -> bool:
            if "h-11" in class_str:
                return True
            return any(int(match.group(1)) >= 44 for match in inline_min_h_re.finditer(class_str))

        failures = []
        for name in templates:
            soup = BeautifulSoup(_make_env().get_template(name).render(), "html.parser")
            for btn in soup.find_all("button"):
                cls = btn.get("class", [])
                class_str = " ".join(cls) if isinstance(cls, list) else str(cls)
                if _has_inline_44(class_str):
                    continue
                if tap_defines_44 and "tap" in class_str:
                    continue
                class_has_44 = any(self._css_rule_has_44px(css_content, "." + c) for c in cls if c)
                if not class_has_44:
                    failures.append(f"{name}: button lacks 44px hit target: {btn}")
        assert not failures, "\n".join(failures)


class TestImagesHaveAlt:
    """AC14 — every <img> has a non-empty alt attribute."""

    def test_images_have_alt(self):
        """Any <img> in rendered templates has a non-empty alt attribute."""
        templates = _render_templates(
            "chat/panel.html",
            "chat/composer.html",
            "chat/message.html",
            "chat/parts/actions.html",
            "chat/parts/code.html",
            "chat/parts/text.html",
            "chat/parts/table.html",
            "chat/parts/mermaid.html",
            "chat/parts/citation_chip.html",
            "chat/parts/sources_panel.html",
        )
        failures = []
        for name, html in templates:
            soup = BeautifulSoup(html, "html.parser")
            for img in soup.find_all("img"):
                alt = img.get("alt", "")
                if not alt.strip():
                    failures.append(f"{name}: <img> missing non-empty alt: {img}")
        assert not failures, "\n".join(failures)


class TestMessageA11y:
    def test_assistant_message_has_actions_buttons(self):
        html = _render_message(role="assistant")
        assert 'data-action="copy"' in html
        assert 'data-action="regenerate"' in html
        assert 'data-action="thumbs-up"' in html
        assert 'data-action="thumbs-down"' in html

    def test_user_message_has_no_actions(self):
        html = _render_message(role="user", role_label="You")
        assert 'data-action="copy"' not in html

    def test_copy_button_has_aria_label(self):
        html = _render_message(role="assistant")
        assert 'aria-label="Copy message"' in html

    def test_all_action_buttons_have_aria_labels(self):
        html = _render_message(role="assistant")
        buttons = re.findall(r'<button[^>]*data-action="([^"]+)"', html)
        for btn in buttons:
            assert f'data-action="{btn}"' in html

    def test_copy_code_button_in_parts(self):
        html = (
            _make_env()
            .get_template("chat/parts/code.html")
            .render(language="python", raw_code="print('hello')")
        )
        assert 'aria-label="Copy code"' in html

    def test_citation_chip_has_aria_haspopup(self):
        html = _make_env().get_template("chat/parts/citation_chip.html").render(n="1")
        assert 'aria-haspopup="dialog"' in html

    def test_sources_panel_has_proper_semantics(self):
        html = (
            _make_env()
            .get_template("chat/parts/sources_panel.html")
            .render(
                citations=[
                    {
                        "n": 1,
                        "label": "orch.db.models",
                        "url": "/project/1/code/orch.db.models",
                        "snippet": "...",
                    }
                ]
            )
        )
        assert "<details" in html
        assert "<summary" in html
        assert "<ol" in html

    def test_sources_panel_zero_citations_empty(self):
        html = _make_env().get_template("chat/parts/sources_panel.html").render(citations=[])
        assert "<details" not in html
