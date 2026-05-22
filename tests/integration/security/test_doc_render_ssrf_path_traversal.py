"""SSRF and path-traversal tests for the doc-render / doc-system pipeline.

Tests the entry points that accept user-supplied paths or URLs:
  - DocService._is_ssrf_blocked()  — internal URL blocklist
  - DocService.validate_links()     — link validation (no real HTTP calls; mocked)
  - doc_sections.split_by_sections() — pure string; path-traversal chars are data

No test makes a real HTTP request or accesses the filesystem.
All network calls use unittest.mock to assert the mock was never invoked
with an internal URL.

Genuine vulnerability handling (CR-00075 §AC5):
  If a test surfaces a real SSRF or path-traversal (the doc system reads a
  file or fetches an internal URL), write it as the failing reproduction,
  mark xfail(strict=False), file a high-priority Incident, and flag it as a
  SECURITY BLOCKER. Do NOT fix production code in this CR.
"""

from __future__ import annotations

from unittest import mock

import pytest

from orch.doc_sections import extract_sections, split_by_sections
from orch.doc_service import DocService

# ---------------------------------------------------------------------------
# SSRF — _is_ssrf_blocked()
# ---------------------------------------------------------------------------


class TestIsSsrfBlocked:
    """Assert _is_ssrf_blocked() correctly classifies internal vs public hosts."""

    @pytest.mark.parametrize("host", ["localhost"])
    def test_blocks_localhost(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, "localhost should be blocked but was allowed"

    @pytest.mark.parametrize("host", ["::1"])
    def test_blocks_ipv6_loopback(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, "IPv6 loopback should be blocked"

    @pytest.mark.parametrize("host", ["127.0.0.1", "127.1.2.3", "127.255.255.255"])
    def test_blocks_127_netblock(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f"127.x.x.x address {host} should be blocked"

    @pytest.mark.parametrize("host", ["10.0.0.0", "10.1.2.3", "10.255.255.255"])
    def test_blocks_10_netblock(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f"10.x.x.x address {host} should be blocked"

    @pytest.mark.parametrize(
        "host",
        ["172.16.0.0", "172.16.100.200", "172.20.0.0", "172.31.255.255"],
    )
    def test_blocks_172_16_31_netblock(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f"172.16-31.x.x address {host} should be blocked"

    @pytest.mark.parametrize("host", ["192.168.0.0", "192.168.1.1", "192.168.255.255"])
    def test_blocks_192_168_netblock(self, host: str) -> None:
        url = f"http://{host}:8080/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f"192.168.x.x address {host} should be blocked"

    @pytest.mark.parametrize("host", ["host.local", "mydevice.local"])
    def test_blocks_local_mdns(self, host: str) -> None:
        url = f"http://{host}/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f".local hostname {host} should be blocked"

    @pytest.mark.parametrize("host", ["host.internal", "svc.internal"])
    def test_blocks_internal_dns(self, host: str) -> None:
        url = f"http://{host}/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is True, f".internal hostname {host} should be blocked"

    @pytest.mark.parametrize("host", ["github.com", "pypi.org", "example.com"])
    def test_allows_public_hosts(self, host: str) -> None:
        url = f"https://{host}/path"
        result = DocService._is_ssrf_blocked(None, url)  # type: ignore[arg-type]
        assert result is False, f"Public host {host} should be allowed but was blocked"

    def test_blocks_url_without_scheme(self) -> None:
        assert DocService._is_ssrf_blocked(None, "file:///etc/passwd") is True
        assert DocService._is_ssrf_blocked(None, "ftp://example.com") is True

    def test_blocks_non_url_strings(self) -> None:
        assert DocService._is_ssrf_blocked(None, "just some text") is True
        assert DocService._is_ssrf_blocked(None, "") is True
        assert DocService._is_ssrf_blocked(None, "/absolute/path") is True


# ---------------------------------------------------------------------------
# SSRF — validate_links() — mocked; asserts no internal URL is fetched
# ---------------------------------------------------------------------------

MOCK_EXTERNAL_URL = "https://public-allowed.example.com/ok"


def _make_mock_svc() -> tuple[DocService, mock.MagicMock]:
    """Return a DocService with a mocked _session."""
    svc = DocService.__new__(DocService)
    mock_session = mock.MagicMock()
    svc._session = mock_session
    return svc, mock_session


class TestValidateLinksSsrf:
    """validate_links() must never fetch an internal URL (mocked httpx)."""

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_reports_localhost_as_blocked_ssrf(
        self, mock_head: mock.MagicMock
    ) -> None:
        mock_head.return_value.status_code = 200
        content = "[link](http://localhost:5433/)\n[l](https://127.0.0.1/)"
        mock_doc = type("MockDoc", (), {"content": content, "broken_links": None})()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        for call in mock_head.call_args_list:
            url: str = call[0][0] if call[0] else ""
            assert "localhost" not in url.lower(), f"httpx.head was called with internal URL: {url}"
            assert not url.startswith("http://127."), f"httpx fetched internal URL: {url}"

        broken_urls = [b["url"] for b in result]
        assert "http://localhost:5433/" in broken_urls
        statuses = [b["status"] for b in result if b["url"] == "http://localhost:5433/"]
        assert statuses[0] == "blocked_ssrf"
        mock_session.flush.assert_called_once()

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_reports_127_netblock_as_blocked_ssrf(
        self, mock_head: mock.MagicMock
    ) -> None:
        mock_head.return_value.status_code = 200
        mock_doc = type(
            "MockDoc",
            (),
            {"content": "[l](https://127.0.0.1/admin)", "broken_links": None},
        )()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        for call in mock_head.call_args_list:
            url = call[0][0] if call[0] else ""
            assert not url.startswith("https://127."), f"httpx fetched internal URL: {url}"

        broken_urls = [b["url"] for b in result]
        assert "https://127.0.0.1/admin" in broken_urls
        statuses = [b["status"] for b in result if b["url"] == "https://127.0.0.1/admin"]
        assert statuses[0] == "blocked_ssrf"
        mock_session.flush.assert_called()

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_reports_10_netblock_as_blocked_ssrf(
        self, mock_head: mock.MagicMock
    ) -> None:
        mock_head.return_value.status_code = 200
        mock_doc = type(
            "MockDoc",
            (),
            {"content": "[l](http://10.0.0.1:8080/api)", "broken_links": None},
        )()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        broken_urls = [b["url"] for b in result]
        assert "http://10.0.0.1:8080/api" in broken_urls
        statuses = [b["status"] for b in result if b["url"] == "http://10.0.0.1:8080/api"]
        assert statuses[0] == "blocked_ssrf"

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_reports_localhost_dashboard_port_as_blocked_ssrf(
        self, mock_head: mock.MagicMock
    ) -> None:
        mock_head.return_value.status_code = 200
        mock_doc = type(
            "MockDoc",
            (),
            {"content": "[l](http://localhost:9900/admin)", "broken_links": None},
        )()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        for call in mock_head.call_args_list:
            url = call[0][0] if call[0] else ""
            assert "localhost" not in url.lower(), f"httpx should not fetch localhost URL: {url}"

        broken_urls = [b["url"] for b in result]
        assert "http://localhost:9900/admin" in broken_urls
        mock_session.flush.assert_called()

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_allows_public_url(self, mock_head: mock.MagicMock) -> None:
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        mock_doc = type(
            "MockDoc", (), {"content": f"[l]({MOCK_EXTERNAL_URL})", "broken_links": None}
        )()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        mock_head.assert_called_once_with(MOCK_EXTERNAL_URL, timeout=5, follow_redirects=True)
        assert result == []
        mock_session.flush.assert_called()


# ---------------------------------------------------------------------------
# Path traversal — doc_sections pure-string functions
# ---------------------------------------------------------------------------


class TestSplitBySectionsPathTraversal:
    """split_by_sections() must not access the filesystem — path chars are data."""

    @pytest.mark.parametrize(
        "content",
        [
            "../../../etc/passwd",
            "../../../../etc/passwd",
            "../../../etc/hostname",
            "../../../proc/self/environ",
            "../../.ssh/id_rsa",
            "/etc/passwd",
            "./../../../../../etc/passwd",
        ],
    )
    def test_split_by_sections_treats_traversal_as_data(self, content: str) -> None:
        """A path-traversal string with no H2 headings is returned verbatim under
        the single "Document" key — it is never opened, resolved, or read as a
        filesystem path. The exact-equality assertion proves the input survived
        as inert data."""
        result = split_by_sections(content)
        assert result == {"Document": content}

    def test_split_by_sections_with_real_headings_returns_section_dict(self) -> None:
        result = split_by_sections("## Purpose\nContent\n## Architecture\nMore content\n")
        assert result.get("Purpose") == "## Purpose\nContent"
        assert result.get("Architecture") == "## Architecture\nMore content"
        assert "Purpose" in result
        assert "Architecture" in result

    def test_split_by_sections_empty_returns_document(self) -> None:
        result = split_by_sections("")
        assert result == {"Document": ""}

    def test_split_by_sections_no_headings_returns_document_key(self) -> None:
        content = "Just some prose content without any H2 headings."
        result = split_by_sections(content)
        assert result == {"Document": content}


class TestExtractSectionsPathTraversal:
    """extract_sections() must not access the filesystem — path chars are data."""

    @pytest.mark.parametrize(
        "content",
        [
            "../../../etc/passwd",
            "../../../../etc/passwd",
            "../../../etc/hostname",
            "../../../proc/self/environ",
            "../../.ssh/id_rsa",
            "/etc/passwd",
            "./../../../../../etc/passwd",
        ],
    )
    def test_extract_sections_path_traversal_returns_list(self, content: str) -> None:
        result = extract_sections(content)
        assert isinstance(result, list), "extract_sections must return a list"
        assert result == ["Document"], f"Expected ['Document'] for traversal input, got {result}"

    def test_extract_sections_real_headings(self) -> None:
        content = "## Purpose\nContent\n## Architecture\nMore\n## Key Capabilities\nMore\n"
        result = extract_sections(content)
        assert result == ["Purpose", "Architecture", "Key Capabilities"]


# ---------------------------------------------------------------------------
# file:// URL surface
# ---------------------------------------------------------------------------


class TestFileUrlSurface:
    """Assert the doc system does not have a file:// surface that reads arbitrary paths."""

    def test_file_url_blocked_by_ssrf_guard(self) -> None:
        result = DocService._is_ssrf_blocked(None, "file:///etc/passwd")
        assert result is True, "file:// URLs must be blocked by _is_ssrf_blocked"

    @mock.patch("orch.doc_service.httpx.head")
    def test_validate_links_file_url_marked_blocked_ssrf(self, mock_head: mock.MagicMock) -> None:
        mock_head.return_value.status_code = 200
        content_val = "[f](file:///etc/passwd)"
        mock_doc = type("MockDoc", (), {"content": content_val, "broken_links": None})()

        svc, mock_session = _make_mock_svc()
        result = DocService.validate_links(svc, mock_doc, repo_root="/fake/repo", max_links=20)

        for call in mock_head.call_args_list:
            url = call[0][0] if call[0] else ""
            assert not url.startswith("file://"), f"httpx should not process file:// URL: {url}"

        broken_urls = [b["url"] for b in result]
        assert "file:///etc/passwd" in broken_urls
        assert "file://" not in str(mock_head.call_args_list)
        mock_session.flush.assert_called()
