"""Template smoke tests for chat/message.html (F-00068 S02)."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


class TestChatMessageTemplateStructure:
    """Asserts message.html template structure for F-00068 S02."""

    @pytest.fixture
    def message_tmpl(self):
        return _env().get_template("chat/message.html")

    def test_message_uses_chat_message_body_class(self, message_tmpl):
        """AC3 — chat-message-body div is present in rendered output."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="Hello", role_label="Assistant"
        )
        assert 'class="chat-message-body"' in html

    def test_message_body_renders_content_safe(self, message_tmpl):
        """Content is rendered with | safe filter."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="<strong>bold</strong>", role_label="Assistant"
        )
        assert "<strong>bold</strong>" in html

    def test_assistant_includes_sources_panel(self, message_tmpl):
        """Assistant role includes sources_panel include."""
        html = message_tmpl.render(
            role="assistant", id="msg-1", content="Hello", role_label="Assistant"
        )
        assert 'class="chat-message-body"' in html

    def test_user_does_not_include_actions(self, message_tmpl):
        """User role does not include actions partial."""
        html = message_tmpl.render(role="user", id="msg-2", content="Hello", role_label="You")
        assert 'data-action="copy"' not in html


class TestChatCssProseAndCallouts:
    """CSS prose + callout styles for F-00068 S02."""

    def test_css_contains_chat_message_body_prose_styles(self):
        """Prose styles are defined for .chat-message-body."""
        css_path = Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat.css"
        content = css_path.read_text()
        assert ".chat-message-body {" in content
        assert ".chat-message-body h1" in content
        assert ".chat-message-body h2" in content
        assert ".chat-message-body h3" in content
        assert ".chat-message-body p" in content
        assert ".chat-message-body code" in content
        assert ".chat-message-body pre" in content
        assert ".chat-message-body blockquote" in content

    def test_css_contains_callout_styles(self):
        """Callout CSS for all 5 types is defined."""
        css_path = Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat.css"
        content = css_path.read_text()
        assert ".chat-message-body .callout {" in content
        assert ".chat-message-body .callout-note" in content
        assert ".chat-message-body .callout-tip" in content
        assert ".chat-message-body .callout-warning" in content
        assert ".chat-message-body .callout-danger" in content
        assert ".chat-message-body .callout-important" in content
        assert ".chat-message-body .callout-header" in content

    def test_css_callout_colors_match_f00067_canonical_spec(self):
        """Callout colors exactly match F-00067 canonical palette."""
        css_path = Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat.css"
        content = css_path.read_text()
        assert "#3B82F6" in content  # note border
        assert "#EFF6FF" in content  # note bg
        assert "#1D4ED8" in content  # note header
        assert "#10B981" in content  # tip border
        assert "#ECFDF5" in content  # tip bg
        assert "#065F46" in content  # tip header
        assert "#F59E0B" in content  # warning border
        assert "#FFFBEB" in content  # warning bg
        assert "#92400E" in content  # warning header
        assert "#EF4444" in content  # danger border
        assert "#FEF2F2" in content  # danger bg
        assert "#991B1B" in content  # danger header
        assert "#8B5CF6" in content  # important border
        assert "#F5F3FF" in content  # important bg
        assert "#4C1D95" in content  # important header


class TestRenderJsDomPurifyAllowlist:
    """DOMPurify allowlist verification for F-00068 S02 AC5."""

    def test_dom_purify_allows_class_attribute(self):
        """ALLOWED_ATTR includes 'class' so callout divs survive sanitization."""
        js_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "render.js"
        )
        content = js_path.read_text()
        assert "'class'" in content
        assert "ALLOWED_ATTR" in content
        allowed_attrs_start = content.index("ALLOWED_ATTR")
        allowed_attrs_line_end = content.index("]", allowed_attrs_start)
        allowed_attrs_block = content[allowed_attrs_start:allowed_attrs_line_end]
        assert "'class'" in allowed_attrs_block

    def test_dom_purify_allows_div_tag(self):
        """ALLOWED_TAGS includes 'div' so callout containers are not stripped."""
        js_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "render.js"
        )
        content = js_path.read_text()
        allowed_tags_start = content.index("ALLOWED_TAGS")
        allowed_tags_line_end = content.index("]", allowed_tags_start)
        allowed_tags_block = content[allowed_tags_start:allowed_tags_line_end]
        assert "'div'" in allowed_tags_block

    def test_iw_process_chat_callouts_function_exists(self):
        """iwProcessChatCallouts function is defined in render.js."""
        js_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "render.js"
        )
        content = js_path.read_text()
        assert "function iwProcessChatCallouts" in content
        assert "CALLOUT_TYPES" in content

    def test_iw_process_chat_callouts_called_in_on_done(self):
        """iwProcessChatCallouts is called in the onDone handler."""
        js_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "render.js"
        )
        content = js_path.read_text()
        assert "iwProcessChatCallouts(bodyEl)" in content

    def test_callout_types_defined(self):
        """All 5 callout types have icon and cls properties."""
        js_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "render.js"
        )
        content = js_path.read_text()
        assert "'note'" in content
        assert "'tip'" in content
        assert "'warning'" in content
        assert "'danger'" in content
        assert "'important'" in content
