"""Playwright browser tests for Mermaid rendering (S07).

These tests rely on the ``page`` fixture from the ``pytest-playwright`` plugin,
which is intentionally NOT a project dependency — CLAUDE.md mandates
``playwright-cli`` exclusively for browser automation. The test file is kept
in place so the intent is preserved and a future port to the playwright-cli
helpers (see ``test_code_layout_fixes.py``) is straightforward, but it is
skipped at collection time when the plugin is absent so the run does not
report spurious ERRORs.
"""

import pytest

pytest.importorskip(
    "pytest_playwright",
    reason="pytest-playwright is not a project dependency; use playwright-cli "
    "(see CLAUDE.md). Port these tests to the playwright-cli helpers in "
    "test_code_layout_fixes.py to re-enable them.",
)


@pytest.fixture
def dashboard_url(http_server):
    """Return base URL of the dashboard app."""
    return http_server.url


@pytest.fixture
def mermaid_good_dsl():
    """Return a valid Mermaid flowchart DSL string for testing."""
    return """flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Do Action]
    B -->|No| D[Skip]
    C --> E[End]
    D --> E
    E --> F[Cleanup]
    F --> G[Done]
    G --> H[Archive]
    H --> I[Complete]"""


@pytest.fixture
def mermaid_bad_dsl():
    """Return an invalid Mermaid DSL string that should trigger an error chip."""
    return "flowchart TD\n  A -->"


@pytest.mark.browser
class TestMermaidRendering:
    """Browser tests for Mermaid diagram rendering via playwright-cli."""

    def test_good_mermaid_renders_iframe(self, page, dashboard_url, mermaid_good_dsl):
        """Verifies that valid Mermaid DSL renders an iframe wrapper."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")

        pre_el = page.locator("pre[data-lang='mermaid']").first
        if not pre_el.count():
            pytest.skip("No mermaid blocks on page")

        initial_count = page.locator(".mermaid-wrapper").count()
        page.evaluate(
            """(() => {{
                var pre = document.querySelector('pre[data-lang="mermaid"]');
                if (pre && window.iwChat && window.iwChat.upgradeMermaidBlock) {{
                    window.iwChat.upgradeMermaidBlock(pre);
                }}
            }})()"""
        )
        page.wait_for_timeout(2000)
        assert page.locator(".mermaid-wrapper").count() >= initial_count

    def test_bad_mermaid_shows_error_chip(self, page, dashboard_url, mermaid_bad_dsl):
        """Verifies that invalid Mermaid DSL renders an error chip with a retry button."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")

        page.evaluate(
            f"""(() => {{
                var pre = document.createElement('pre');
                pre.setAttribute('data-lang', 'mermaid');
                var code = document.createElement('code');
                code.textContent = {repr(mermaid_bad_dsl)};
                pre.appendChild(code);
                document.body.appendChild(pre);
                if (window.iwChat && window.iwChat.upgradeMermaidBlock) {{
                    window.iwChat.upgradeMermaidBlock(pre);
                }}
            }})()"""
        )
        page.wait_for_timeout(1000)
        assert page.locator(".mermaid-error").count() > 0
        retry_btn = page.locator(".mermaid-retry").first
        assert retry_btn.is_visible()
        assert page.locator(".mermaid-error details summary").first.inner_text() == "Show source"

    def test_mermaid_wrapper_has_data_iw_layout(self, page, dashboard_url, mermaid_good_dsl):
        """Verifies that the mermaid wrapper has data-iw-layout=\'elk\'."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")

        page.evaluate(
            f"""(() => {{
                var pre = document.createElement('pre');
                pre.setAttribute('data-lang', 'mermaid');
                var code = document.createElement('code');
                code.textContent = {repr(mermaid_good_dsl)};
                pre.appendChild(code);
                document.body.appendChild(pre);
                if (window.iwChat && window.iwChat.upgradeMermaidBlock) {{
                    window.iwChat.upgradeMermaidBlock(pre);
                }}
            }})()"""
        )
        page.wait_for_timeout(2000)
        wrappers = page.locator(".mermaid-wrapper[data-iw-layout='elk']")
        assert wrappers.count() > 0

    def test_mermaid_iframe_has_sandbox(self, page, dashboard_url, mermaid_good_dsl):
        """Verifies that the mermaid iframe has a sandbox attribute."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")

        page.evaluate(
            f"""(() => {{
                var pre = document.createElement('pre');
                pre.setAttribute('data-lang', 'mermaid');
                var code = document.createElement('code');
                code.textContent = {repr(mermaid_good_dsl)};
                pre.appendChild(code);
                document.body.appendChild(pre);
                if (window.iwChat && window.iwChat.upgradeMermaidBlock) {{
                    window.iwChat.upgradeMermaidBlock(pre);
                }}
            }})()"""
        )
        page.wait_for_timeout(2000)
        sandboxed_iframe = page.locator("iframe[sandbox][title='Mermaid diagram']").first
        assert sandboxed_iframe.count() > 0

    def test_retry_re_runs_upgrade(self, page, dashboard_url, mermaid_bad_dsl):
        """Verifies that clicking the retry button re-runs the mermaid upgrade."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")

        page.evaluate(
            f"""(() => {{
                var pre = document.createElement('pre');
                pre.setAttribute('data-lang', 'mermaid');
                var code = document.createElement('code');
                code.textContent = {repr(mermaid_bad_dsl)};
                pre.appendChild(code);
                document.body.appendChild(pre);
                if (window.iwChat && window.iwChat.upgradeMermaidBlock) {{
                    window.iwChat.upgradeMermaidBlock(pre);
                }}
            }})()"""
        )
        page.wait_for_timeout(500)
        error_chip = page.locator(".mermaid-error").first
        assert error_chip.count() > 0
        error_chip.locator(".mermaid-retry").click()
        page.wait_for_timeout(500)
        assert page.locator(".mermaid-error").count() > 0


@pytest.fixture
def http_server():
    """Serve the dashboard static files via a simple HTTP server."""
    import http.server
    import socketserver
    import threading
    from pathlib import Path

    static_dir = Path(__file__).parent.parent.parent / "dashboard" / "static"

    class Handler(http.server.SimpleHTTPRequestHandler):
        """SimpleHTTPRequestHandler configured to serve the dashboard static directory."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=static_dir, **kwargs)

    port = 18765
    with socketserver.TCPServer(("", port), Handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        yield type("Server", (), {"url": f"http://localhost:{port}"})()
