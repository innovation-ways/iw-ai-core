"""Template smoke tests for chat panel — asserts required id/role/aria-* attributes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _css_rule_body(css: str, selector: str) -> str | None:
    """Return the declaration block of the CSS rule for ``selector``.

    Matches the first occurrence of ``selector`` followed only by whitespace
    then ``{``; returns the text between that ``{`` and its ``}``, or None when
    no such rule exists. Scopes substring checks to the rule that actually
    declares the style.
    """
    pos = 0
    while True:
        idx = css.find(selector, pos)
        if idx == -1:
            return None
        brace = css.find("{", idx + len(selector))
        if brace != -1 and css[idx + len(selector) : brace].strip() == "":
            end = css.find("}", brace)
            if end != -1:
                return css[brace + 1 : end]
        pos = idx + len(selector)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


@pytest.fixture
def chat_panel_html():
    """Return the rendered chat_panel.html template for testing."""
    tmpl = _env().get_template("chat/panel.html")
    return tmpl.render()


@pytest.fixture
def chat_composer_html():
    """Return the rendered chat_assistant/composer.html template for testing."""
    return _env().get_template("chat/composer.html").render()


@pytest.fixture
def chat_assistant_composer_html():
    """Return the rendered chat_assistant/composer.html with assistant-mode context."""
    return _env().get_template("chat_assistant/composer.html").render()


class TestChatPanelTemplate:
    """Tests for the chat panel Jinja2 template structure."""

    def test_panel_has_correct_id(self, chat_panel_html):
        """Verifies that the chat panel has the expected DOM id."""
        assert 'id="chat-panel"' in chat_panel_html

    def test_panel_role_region(self, chat_panel_html):
        """Verifies that the chat panel has role='region'."""
        assert 'role="region"' in chat_panel_html
        assert 'aria-label="Code module chat"' in chat_panel_html

    def test_panel_ships_collapsed(self, chat_panel_html):
        """Verifies that the chat panel ships with data-collapsed=true."""
        # I-00057 changed the chat panel to ship collapsed (slim rail) by default
        # so module navigation is not blocked by a wide open panel on first load.
        assert 'data-collapsed="true"' in chat_panel_html
        assert 'data-collapsed="false"' not in chat_panel_html

    def test_resize_handle_present(self, chat_panel_html):
        """Verifies that a resize handle element is present in the panel."""
        assert 'id="chat-resize-handle"' in chat_panel_html
        assert 'aria-hidden="true"' in chat_panel_html
        assert "cursor-col-resize" in chat_panel_html

    def test_messages_log_role(self, chat_panel_html):
        """Verifies that the messages log has an accessible ARIA role."""
        assert 'role="log"' in chat_panel_html
        assert 'aria-live="polite"' in chat_panel_html
        assert 'aria-relevant="additions"' in chat_panel_html
        assert 'aria-label="Conversation"' in chat_panel_html

    def test_collapse_and_expand_affordances_present(self, chat_panel_html):
        """Verifies that both collapse and expand affordances are present."""
        # I-00057 superseded the I-00046 floating slide-out tab with a pair of
        # in-panel affordances: #chat-collapse-btn (in the expanded header) and
        # #chat-expand-rail (in the collapsed slim rail). Both must be labelled
        # so the toggle is accessible in either state.
        assert 'id="chat-collapse-btn"' in chat_panel_html
        assert 'id="chat-expand-rail"' in chat_panel_html
        assert 'aria-label="Collapse chat panel' in chat_panel_html
        assert 'aria-label="Expand chat panel' in chat_panel_html

    def test_scroll_to_bottom_button(self, chat_panel_html):
        """Verifies that a scroll-to-bottom button is present."""
        assert 'id="chat-scroll-to-bottom"' in chat_panel_html
        assert 'aria-label="Jump to latest"' in chat_panel_html

    def test_drawer_open_button(self, chat_panel_html):
        """Verifies that a drawer open button is present in the panel."""
        assert 'id="chat-drawer-open"' in chat_panel_html
        assert 'aria-label="Open chat panel"' in chat_panel_html

    def test_drawer_has_translate_class(self, chat_panel_html):
        """Verifies that the drawer element has a translate CSS class for animation."""
        assert "translate-x-full" in chat_panel_html

    # NOTE: the original mobile "drawer close" button (#chat-close-btn) was
    # removed in I-00057 — collapse/expand are now handled by #chat-collapse-btn
    # and #chat-expand-rail in both desktop and drawer modes, so the legacy test
    # for the close button no longer applies.


class TestChatComposerTemplate:
    """Tests for the chat composer Jinja2 template structure."""

    def test_composer_form_has_enctype(self, chat_composer_html):
        """Verifies that the composer form has the correct enctype attribute."""
        assert 'enctype="multipart/form-data"' in chat_composer_html
        assert 'id="chat-composer"' in chat_composer_html

    def test_context_chips_div(self, chat_composer_html):
        """Verifies that a context chips container div is present."""
        assert 'id="chat-context-chips"' in chat_composer_html

    def test_image_chips_div(self, chat_composer_html):
        """Verifies that an image chips container div is present."""
        assert 'id="chat-image-chips"' in chat_composer_html

    def test_textarea_input(self, chat_composer_html):
        """Verifies that a textarea input element is present in the composer."""
        assert 'id="chat-input"' in chat_composer_html
        assert "Ask about this module" in chat_composer_html

    def test_slash_menu(self, chat_composer_html):
        """Verifies that a slash command menu element is present."""
        assert 'id="chat-slash-menu"' in chat_composer_html
        assert 'role="listbox"' in chat_composer_html

    def test_image_picker_accepts_images(self, chat_composer_html):
        """Verifies that the image picker input accepts image file types."""
        assert 'id="chat-image-picker"' in chat_composer_html
        accept_val = re.search(r'accept="([^"]+)"', chat_composer_html)
        assert accept_val is not None
        accept_str = accept_val.group(1)
        for mime in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            assert mime in accept_str, f"Image picker must accept {mime}"

    def test_send_button(self, chat_composer_html):
        """Verifies that a send button is present in the composer."""
        assert 'id="chat-send"' in chat_composer_html
        assert "min-h-[44px]" in chat_composer_html
        assert "min-w-[44px]" in chat_composer_html

    def test_image_picker_is_sr_only(self, chat_composer_html):
        """Verifies that the image picker input is visually hidden (screen-reader only)."""
        assert 'type="file"' in chat_composer_html
        assert "sr-only" in chat_composer_html

    def test_clear_button_disabled_initially(self, chat_assistant_composer_html):
        """CR-00064 AC1 — clear button starts disabled (no history on a fresh tab)."""
        soup = BeautifulSoup(chat_assistant_composer_html, "html.parser")
        btn = soup.find(id="chat-assistant-clear")
        assert btn is not None, "#chat-assistant-clear button not found"
        assert btn.has_attr("disabled"), (
            "clear button must start disabled — a fresh tab has no history to clear"
        )

    def test_clear_button_has_aria_label(self, chat_assistant_composer_html):
        """Verifies that the clear button has an accessible aria-label."""
        soup = BeautifulSoup(chat_assistant_composer_html, "html.parser")
        btn = soup.find(id="chat-assistant-clear")
        assert btn is not None, "#chat-assistant-clear button not found"
        assert btn.get("aria-label") == "Clear chat history", (
            "clear button must carry aria-label='Clear chat history' for screen readers"
        )

    def test_clear_button_min_touch_size(self, chat_assistant_composer_html):
        """Verifies that the clear button meets the minimum 44px touch target size."""
        soup = BeautifulSoup(chat_assistant_composer_html, "html.parser")
        btn = soup.find(id="chat-assistant-clear")
        assert btn is not None, "#chat-assistant-clear button not found"
        classes = set(btn.get("class", []))
        assert {"min-h-[44px]", "min-w-[44px]"}.issubset(classes), (
            "clear button must carry min-h-[44px] and min-w-[44px] (44px touch target); "
            f"got classes: {sorted(classes)}"
        )


class TestChatCss:
    """Tests for chat-panel CSS variable definitions."""

    def test_css_defines_chat_width_var(self):
        """Verifies that the CSS file defines the --chat-panel-width variable."""
        css_path = Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat.css"
        content = css_path.read_text()
        assert ":root { --chat-width: 400px; }" in content
        assert ":focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }" in content
        assert ".tap { min-height: 44px; min-width: 44px; }" in content

    def test_clear_button_disabled_has_opacity(self):
        """CR-00064 — clear button must visually indicate disabled state via opacity."""
        root = Path(__file__).parent.parent.parent
        css_content = (root / "dashboard" / "static" / "chat_assistant" / "chat.css").read_text()
        rule = _css_rule_body(css_content, "#chat-assistant-clear:disabled")
        assert rule is not None, "chat.css must define a #chat-assistant-clear:disabled rule"
        # The opacity declaration must live INSIDE the :disabled rule, not just
        # anywhere in the stylesheet.
        assert rule.count("opacity") >= 1, (
            "the #chat-assistant-clear:disabled rule must set opacity to dim the button"
        )


class TestChatMessageTemplate:
    """Tests for chat/message.html (S05) — AC10, AC14."""

    @pytest.fixture
    def message_tmpl(self):
        """Return the rendered chat message template for testing."""
        return _env().get_template("chat/message.html")

    def test_message_includes_actions_only_for_assistant(self, message_tmpl):
        """AC10 — actions.html only included for assistant role, not user."""
        assistant_html = message_tmpl.render(
            role="assistant", id="msg-1", content="Hello", role_label="Assistant"
        )
        user_html = message_tmpl.render(role="user", id="msg-2", content="Hello", role_label="You")
        assert 'data-action="copy"' in assistant_html
        assert 'data-action="copy"' not in user_html

    def test_renders_assistant_role(self, message_tmpl):
        """Verifies that the message template renders the assistant role."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="Hello", role_label="Assistant"
        )
        assert 'data-role="assistant"' in html
        assert 'data-msg-id="msg-1"' in html

    def test_renders_user_role(self, message_tmpl):
        """Verifies that the message template renders the user role."""
        html = message_tmpl.render(role="user", id="msg-2", content="Hello", role_label="You")
        assert 'data-role="user"' in html

    def test_assistant_includes_actions_and_sources(self, message_tmpl):
        """Verifies that assistant messages include action buttons and a sources panel."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="Hello", role_label="Assistant"
        )
        assert 'data-action="copy"' in html
        assert 'data-action="regenerate"' in html
        assert 'data-action="thumbs-up"' in html
        assert 'data-action="thumbs-down"' in html

    def test_content_rendered_safe(self, message_tmpl):
        """Verifies that message content is rendered with HTML escaping."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="<strong>bold</strong>", role_label="Assistant"
        )
        assert "<strong>bold</strong>" in html

    def test_panel_has_log_role_and_aria_live_polite(self):
        """AC14 — message container has role=log and aria-live=polite."""
        panel_html = _env().get_template("chat/panel.html").render()
        assert 'role="log"' in panel_html
        assert 'aria-live="polite"' in panel_html
        assert 'aria-relevant="additions"' in panel_html

    def test_panel_aria_region_labelled(self):
        """AC1 — panel has role=region with non-empty aria-label."""
        panel_html = _env().get_template("chat/panel.html").render()
        assert 'role="region"' in panel_html
        assert 'aria-label="Code module chat"' in panel_html

    def test_composer_image_picker_restricts_mime(self):
        """AC13 — file input accept contains image/png, image/jpeg, image/gif, image/webp."""
        composer_html = _env().get_template("chat/composer.html").render()
        accept_match = re.search(r'accept="([^"]+)"', composer_html)
        assert accept_match is not None, "Image picker must have accept attribute"
        accept_str = accept_match.group(1)
        for mime in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            assert mime in accept_str, f"Image picker must restrict to {mime}"

    def test_code_block_partial_has_language_label_and_copy_button(self):
        """AC5 — code.html partial has language label and copy button with accessible name."""
        code_html = _env().get_template("chat/parts/code.html")
        html = code_html.render(language="python", raw_code="print('hello')")
        assert "python" in html.lower(), "Code block must have language label"
        assert 'aria-label="Copy code"' in html, "Copy button must have accessible name"
        assert "Copy code" in html


class TestCodeBlockTemplate:
    """Tests for the code block template rendering."""

    @pytest.fixture
    def code_tmpl(self):
        """Return the rendered code block template for testing."""
        return _env().get_template("chat/parts/code.html")

    def test_emits_copy_button_with_aria_label(self, code_tmpl):
        """Verifies that the code block emits a copy button with an aria-label."""
        html = code_tmpl.render(language="python", raw_code="print('hello')")
        assert 'aria-label="Copy code"' in html

    def test_emits_language_label(self, code_tmpl):
        """Verifies that the code block emits a language label element."""
        html = code_tmpl.render(language="python", raw_code="print('hello')")
        assert "python" in html.lower()

    def test_has_data_copy_payload(self, code_tmpl):
        """Verifies that the copy button has a data-copy-payload attribute."""
        html = code_tmpl.render(language="python", raw_code="print('hello')")
        assert "data-copy-payload=" in html


class TestSourcesPanelTemplate:
    """Tests for the sources panel template rendering."""

    @pytest.fixture
    def sources_tmpl(self):
        """Return the rendered sources panel template for testing."""
        return _env().get_template("chat/parts/sources_panel.html")

    def test_zero_citations_renders_empty(self, sources_tmpl):
        """Verifies that zero citations render an empty sources panel."""
        html = sources_tmpl.render(citations=[])
        assert "<details" not in html

    def test_with_citations_renders_list(self, sources_tmpl):
        """Verifies that citations render as a list of source items."""
        html = sources_tmpl.render(
            citations=[
                {
                    "n": 1,
                    "label": "orch.db.models",
                    "url": "/project/1/code/orch.db.models",
                    "snippet": "first line...",
                }
            ]
        )
        assert "<details" in html
        assert "Sources (1)" in html

    def test_sources_panel_collapsed_by_default(self, sources_tmpl):
        """AC7 — <details> has no open attribute by default."""
        html = sources_tmpl.render(
            citations=[{"n": 1, "label": "x", "url": "/p/x", "snippet": "s"}]
        )
        assert "<details" in html
        assert "open" not in html


class TestMermaidTemplate:
    """AC9 — error chip has Retry button with non-empty aria-label."""

    @pytest.fixture
    def mermaid_tmpl(self):
        """Return the rendered mermaid error template for testing."""
        return _env().get_template("chat/parts/mermaid.html")

    def test_mermaid_error_chip_has_retry_button(self, mermaid_tmpl):
        """Verifies that the mermaid error chip has a retry button."""
        html = mermaid_tmpl.render()
        assert 'class="mermaid-retry' in html
        retry_btn_match = re.search(
            r'<button[^>]*class="mermaid-retry[^>]*aria-label="([^"]+)"', html
        )
        assert retry_btn_match is not None, "Retry button must have non-empty aria-label"
        assert retry_btn_match.group(1), "aria-label must not be empty"

    def test_retry_button_min_44px(self, mermaid_tmpl):
        """Verifies that the retry button meets the minimum 44px touch target size."""
        html = mermaid_tmpl.render()
        assert 'class="mermaid-retry' in html
        assert "min-h-[44px]" in html
        assert "min-w-[44px]" in html

    def test_error_label_present(self, mermaid_tmpl):
        """Verifies that an error label element is present in the mermaid error chip."""
        assert "⚠ Diagram error" in mermaid_tmpl.render()

    def test_details_source_revealer(self, mermaid_tmpl):
        """Verifies that a details element acts as a source code revealer."""
        html = mermaid_tmpl.render()
        assert "<details" in html
        assert "<summary" in html
        assert "Show source" in html

    def test_code_in_details(self, mermaid_tmpl):
        """Verifies that the mermaid source code is inside the details element."""
        html = mermaid_tmpl.render(dsl="flowchart TD\n  A --> B")
        assert "<code>" in html
