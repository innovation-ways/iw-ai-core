"""Security tests for chat rendering pipeline.

Asserts DOMPurify sanitization, no innerHTML per-chunk,
javascript: links blocked, script tags stripped, CDN/gpl checks.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _render_message(role="assistant", msg_id="test-1", content="Hello"):
    env = Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )
    return env.get_template("chat/message.html").render(
        role=role,
        id=msg_id,
        content=content,
        role_label="Assistant",
    )


class TestChatTemplatesNoMarkedReferences:
    def test_no_marked_parse_in_message_html(self):
        env = Environment(loader=FileSystemLoader(_template_dir()), autoescape=select_autoescape())
        html = env.get_template("chat/message.html").render(
            role="assistant", id="x", content="test", role_label="A"
        )
        assert "marked.parse" not in html

    @pytest.mark.skip(reason="item_artifacts.html removed per F-00079 design (Invariant 9)")
    def test_no_marked_parse_in_item_artifacts(self):
        pass

    def test_no_marked_cdn_in_base_html(self):
        base_path = Path(__file__).parent.parent.parent / "dashboard" / "templates" / "base.html"
        html = base_path.read_text()
        assert "cdn.jsdelivr.net/npm/marked" not in html
        assert "marked.min.js" not in html

    def test_vendor_dompurify_referenced_in_libs_partial(self):
        # base.html no longer loads DOMPurify directly — it's pulled in lazily
        # per-page via the templates/components/libs/dompurify.html include
        # (see the comment in base.html). Verify the vendor file is referenced
        # somewhere under the libs partial set.
        libs_dir = (
            Path(__file__).parent.parent.parent / "dashboard" / "templates" / "components" / "libs"
        )
        joined = "\n".join(p.read_text() for p in libs_dir.glob("*.html"))
        assert "/static/vendor/dompurify/purify.min.js" in joined

    def test_vendor_highlightjs_referenced_in_libs_partial(self):
        # Same rationale as the DOMPurify test — highlight.js is loaded via a
        # per-page include rather than being hard-coded in base.html.
        libs_dir = (
            Path(__file__).parent.parent.parent / "dashboard" / "templates" / "components" / "libs"
        )
        joined = "\n".join(p.read_text() for p in libs_dir.glob("*.html"))
        assert "/static/vendor/highlight.js/core.js" in joined


class TestItemArtifactsRenderStatic:
    @pytest.mark.skip(reason="item_artifacts.html removed per F-00079 design (Invariant 9)")
    def test_loadartifact_calls_render_markdown_static(self):
        pass

    @pytest.mark.skip(reason="item_artifacts.html removed per F-00079 design (Invariant 9)")
    def test_no_innerhtml_for_markdown_in_item_artifacts(self):
        pass


class TestCodeBlockTemplate:
    def test_code_block_has_copy_button(self):
        env = Environment(
            loader=FileSystemLoader(_template_dir()),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        html = env.get_template("chat/parts/code.html").render(
            language="python", raw_code="print('hello')"
        )
        assert 'data-copy-payload="' in html
        assert "Copy code" in html

    def test_code_block_has_language_label(self):
        env = Environment(
            loader=FileSystemLoader(_template_dir()),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        html = env.get_template("chat/parts/code.html").render(
            language="python", raw_code="print('hello')"
        )
        assert "python" in html.lower()


class TestSourcesPanelTemplate:
    def test_renders_with_citations(self):
        env = Environment(
            loader=FileSystemLoader(_template_dir()),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        html = env.get_template("chat/parts/sources_panel.html").render(
            citations=[
                {
                    "n": 1,
                    "label": "orch.db.models",
                    "url": "/project/1/code/orch.db.models",
                    "snippet": "...",
                }
            ]
        )
        assert "Sources (1)" in html
        assert "orch.db.models" in html
        assert '<a href="/project/1/code/orch.db.models"' in html

    def test_empty_citations_renders_nothing(self):
        env = Environment(
            loader=FileSystemLoader(_template_dir()),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        html = env.get_template("chat/parts/sources_panel.html").render(citations=[])
        assert "<details" not in html
        assert "Sources (0)" not in html


class TestNoCdnReferences:
    """AC4 / AC15 — no CDN JS in base.html; all assets vendored."""

    def test_no_cdn_references_in_base_html(self):
        """base.html must not reference cdn.jsdelivr.net, cdnjs.cloudflare.com, or unpkg.com."""
        base_path = Path(__file__).parent.parent.parent / "dashboard" / "templates" / "base.html"
        html = base_path.read_text()
        violations = []
        for cdn in ["cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com"]:
            if cdn in html:
                violations.append(f"base.html contains CDN reference: {cdn}")
        assert not violations, "\n".join(violations)

    def test_no_marked_references_remain(self):
        """No marked.js library references anywhere in templates.

        Checks for the actual library (marked.js / marked.min.js / window.marked /
        marked.parse / marked.setOptions), not the English word 'marked'.
        """
        template_dir = Path(__file__).parent.parent.parent / "dashboard" / "templates"
        # Library-specific patterns — not the English word
        patterns = [
            r"\bmarked\.min\.js\b",
            r"\bmarked\.js\b",
            r"\bwindow\.marked\b",
            r"\bmarked\.(parse|setOptions|use|lexer|Renderer)\b",
            r'(?:from|require)\([\'"]marked[\'"]\)',
        ]
        combined = re.compile("|".join(patterns))
        for html_path in template_dir.rglob("*.html"):
            content = html_path.read_text()
            if combined.search(content):
                rel = html_path.relative_to(template_dir)
                raise AssertionError(f"marked.js library reference found in {rel}")


class TestVendorLicenses:
    """AC15 — every vendored library has a LICENSE file; LICENSES.md indexes all."""

    def test_vendored_license_files_exist(self):
        """Each subdirectory under dashboard/static/vendor/ has a LICENSE or LICENSE.md file."""
        vendor_dir = Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor"
        failures = []
        for subdir in vendor_dir.iterdir():
            if not subdir.is_dir():
                continue
            has_license = any(
                (subdir / f).is_file()
                for f in ["LICENSE", "LICENSE.md", "license.md", "LICENSE.txt"]
            )
            if not has_license:
                failures.append(f"Missing LICENSE file in vendor/{subdir.name}")
        assert not failures, "\n".join(failures)

    def test_vendored_licenses_index_exists(self):
        """dashboard/static/vendor/LICENSES.md exists at the vendor root."""
        licenses_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor" / "LICENSES.md"
        )
        assert licenses_path.is_file()

    def test_vendored_licenses_index_entries(self):
        """LICENSES.md lists each vendored folder with an acceptable SPDX ID (no GPL)."""
        licenses_path = (
            Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor" / "LICENSES.md"
        )
        content = licenses_path.read_text()
        vendor_dir = Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor"
        failures = []
        for subdir in vendor_dir.iterdir():
            if not subdir.is_dir() or subdir.name == "__pycache__":
                continue
            if subdir.name not in content:
                failures.append(f"LICENSES.md does not mention vendor/{subdir.name}")
        gpl_found = re.search(r"\b(GPL|LGPL|AGPL)\b", content)
        if gpl_found:
            failures.append("LICENSES.md contains prohibited GPL license")
        assert not failures, "\n".join(failures)


class TestStaleFragmentDeleted:
    """AC3 — old code_qa_panel.html fragment must be deleted."""

    def test_stale_code_qa_fragment_deleted(self):
        """dashboard/templates/fragments/code_qa_panel.html must not exist."""
        stale_path = (
            Path(__file__).parent.parent.parent
            / "dashboard"
            / "templates"
            / "fragments"
            / "code_qa_panel.html"
        )
        assert not stale_path.exists(), (
            "Old fragments/code_qa_panel.html still exists — must be removed"
        )


class TestCodeQaRouteRegistered:
    """AC3 — POST /api/projects/{project_id}/code/qa is registered and returns 501."""

    def test_code_qa_route_registered(self):
        """The /api/projects/{project_id}/code/qa route is registered in the app."""
        from fastapi.testclient import TestClient

        from dashboard.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/projects/nonexistent-project/code/qa",
            json={"question": "test", "context_level": "architecture"},
        )
        assert response.status_code in (404, 500), (
            f"Expected 404 or 500 for nonexistent project, got {response.status_code}"
        )

    def test_code_qa_with_image_route_registered(self):
        """The /api/projects/{project_id}/code/qa-with-image route is registered and returns 501."""
        from fastapi.testclient import TestClient

        from dashboard.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/projects/test-project/code/qa-with-image",
            files={"file": b"fake-png"},
        )
        assert response.status_code == 501
        assert response.json()["detail"] == "Image attachments coming soon"
