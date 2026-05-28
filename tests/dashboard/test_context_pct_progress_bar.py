import re
from pathlib import Path


def test_bar_markup_present() -> None:
    composer = Path("dashboard/templates/chat_assistant/composer.html").read_text(encoding="utf-8")
    assert composer.count('id="chat-assistant-context-pct"') == 1
    assert 'role="status"' in composer
    assert 'aria-label="Context window usage"' in composer
    assert "chat-assistant-context-pct__bar" in composer
    assert "chat-assistant-context-pct__fill" in composer


def test_chat_js_uses_progress_bar_shape() -> None:
    js = Path("dashboard/static/chat_assistant/chat.js").read_text(encoding="utf-8")
    assert "chat-assistant-context-pct__fill" in js
    assert "chat-assistant-context-pct__label" in js
    assert "function _formatTokenCount" in js

    m = re.search(r"function _applyContextPct\(payload\) \{([\s\S]*?)\n  \}\n", js)
    assert m is not None
    apply_body = m.group(1)
    assert "label.textContent = rounded + '%'" in apply_body
    assert "\nel.textContent = rounded + '%'" not in apply_body
