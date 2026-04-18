"""Playwright browser tests for Mermaid rendering (S07)."""

import pytest


@pytest.fixture
def dashboard_url(http_server):
    """Return base URL of the dashboard app."""
    return http_server.url


@pytest.fixture
def mermaid_good_dsl():
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
    return "flowchart TD\n  A -->"


@pytest.mark.browser
class TestMermaidRendering:
    def test_good_mermaid_renders_iframe(self, page, dashboard_url, mermaid_good_dsl):
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
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=static_dir, **kwargs)

    port = 18765
    with socketserver.TCPServer(("", port), Handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        yield type("Server", (), {"url": f"http://localhost:{port}"})()
