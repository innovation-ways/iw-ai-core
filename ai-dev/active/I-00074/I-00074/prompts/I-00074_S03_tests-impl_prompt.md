# I-00074_S03_tests-impl_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ No manual RED-check revert

Do NOT `git stash`, `git checkout HEAD~1 -- ...`, or otherwise revert source files to
verify the pre-fix failure. The design document describes the failure; trust it.

## Input Files

- `ai-dev/active/I-00074/I-00074_Issue_Design.md` — root cause, acceptance criteria, TDD approach
- `dashboard/utils/markdown.py` — `render_pdf_chromium()` and `_PLAYWRIGHT_CHROME`
- `dashboard/routers/docs.py` — the three PDF routes
- `tests/dashboard/conftest.py` — `client` fixture (read to understand fixture signatures)
- `tests/CLAUDE.md` — test conventions for this project

## Output Files

- `tests/dashboard/test_docs_pdf_chromium.py` — all tests for this incident
- `ai-dev/work/I-00074/reports/I-00074_S03_tests_report.md` — report

## Test File Location

**All tests MUST go in `tests/dashboard/test_docs_pdf_chromium.py`** — they exercise FastAPI
routes via the `client` fixture, which is only registered in `tests/dashboard/conftest.py`.
A test placed in `tests/unit/` or `tests/integration/` will fail with `fixture 'client' not found`.

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Applied here:
- BAD: `assert response.status_code == 200` only (shape check — WeasyPrint would also give 200)
- GOOD: Assert `subprocess.run` was called with `--print-to-pdf` (semantic — proves Chromium path taken)
- GOOD: Assert WeasyPrint was NOT imported (semantic — proves old path is gone)

---

## Required Tests

### Group 1: Unit tests for `render_pdf_chromium()`

These do not need the `client` fixture. They can use `monkeypatch`.

**T1: Function exists and is callable (reproduction test)**

```python
def test_i00074_render_pdf_chromium_exists():
    """Fails before fix (function didn't exist); passes after."""
    from dashboard.utils.markdown import render_pdf_chromium
    assert callable(render_pdf_chromium)
```

**T2: Chromium binary missing → returns None**

```python
def test_i00074_render_pdf_chromium_binary_missing(monkeypatch, tmp_path):
    """When Chromium binary does not exist, returns None (not an exception)."""
    from dashboard.utils import markdown as md_mod
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", tmp_path / "nonexistent_chrome")

    from dashboard.utils.markdown import render_pdf_chromium
    result = render_pdf_chromium("<html><body>test</body></html>")
    assert result is None  # clean None — not an exception
```

**T3: Chromium subprocess fails → returns None**

```python
def test_i00074_render_pdf_chromium_subprocess_fails(monkeypatch, tmp_path):
    """When Chromium exits with non-zero code, returns None."""
    import subprocess
    from unittest.mock import MagicMock, patch
    from dashboard.utils import markdown as md_mod

    # Make binary appear to exist
    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"error: something went wrong"

    with patch("dashboard.utils.markdown.subprocess.run", return_value=mock_result):
        result = md_mod.render_pdf_chromium("<html><body>test</body></html>")

    assert result is None
```

**T4: Chromium succeeds → returns bytes**

```python
def test_i00074_render_pdf_chromium_success(monkeypatch, tmp_path):
    """When Chromium succeeds and writes output PDF, returns the PDF bytes."""
    import subprocess
    from unittest.mock import MagicMock, patch
    from dashboard.utils import markdown as md_mod

    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    fake_pdf_content = b"%PDF-1.4 fake-content"

    def fake_run(cmd, **kwargs):
        # Find --print-to-pdf=<path> and write fake PDF there
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                out_path = arg.split("=", 1)[1]
                Path(out_path).write_bytes(fake_pdf_content)
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = md_mod.render_pdf_chromium("<html><body>test</body></html>")

    assert result == fake_pdf_content  # semantic: specific expected bytes
```

**T4b: Chromium subprocess times out → returns None (no exception propagation)**

```python
def test_i00074_render_pdf_chromium_subprocess_timeout(monkeypatch, tmp_path):
    """When Chromium hangs and subprocess.run raises TimeoutExpired, returns None.

    Without the try/except wrapper around subprocess.run, a Chromium hang would
    propagate as an unhandled exception and the calling route would return 500
    instead of the intended 503.
    """
    import subprocess
    from unittest.mock import patch
    from dashboard.utils import markdown as md_mod

    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 30))

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = md_mod.render_pdf_chromium("<html><body>test</body></html>")

    assert result is None  # semantic: timeout coerced to None, not raised
```

**T5: subprocess.run called with --print-to-pdf flag (proves Chromium path)**

```python
def test_i00074_render_pdf_chromium_uses_print_to_pdf_flag(monkeypatch, tmp_path):
    """Chromium must be invoked with --print-to-pdf (not --output or stdout)."""
    from unittest.mock import MagicMock, patch, call
    from dashboard.utils import markdown as md_mod

    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    captured_calls = []

    def fake_run(cmd, **kwargs):
        captured_calls.append(cmd)
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                Path(arg.split("=", 1)[1]).write_bytes(b"%PDF fake")
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        md_mod.render_pdf_chromium("<html><body>x</body></html>")

    assert len(captured_calls) == 1
    cmd = captured_calls[0]
    # Semantic: verify specific required flags
    flags = " ".join(cmd)
    assert "--print-to-pdf=" in flags, "Chromium must use --print-to-pdf flag"
    assert "--headless" in flags, "Chromium must run headless"
    assert "--no-sandbox" in flags, "Chromium must run with --no-sandbox for WSL/Linux"
```

### Group 2: Route-level tests (use `client` fixture)

These verify the three PDF routes no longer call WeasyPrint.

For these tests you need a minimal project + doc in the DB. Study `tests/dashboard/conftest.py`
to find the appropriate fixtures (`client`, any project/doc fixtures that exist). If no doc
fixture exists, create one inline using the `db` session fixture.

**T6: `docs_pdf_view` route uses Chromium, not WeasyPrint**

```python
def test_i00074_docs_pdf_view_does_not_call_weasyprint(client, ...):
    """The inline PDF view endpoint must not call WeasyPrint.HTML (I-00074)."""
    from unittest.mock import patch, MagicMock

    fake_pdf = b"%PDF-1.4 fake-inline"

    with patch("dashboard.utils.markdown.render_pdf_chromium", return_value=fake_pdf) as mock_render:
        # Create or look up a real project+doc, then:
        response = client.get(f"/project/{project_id}/docs/{doc_id}/pdf/view")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf  # semantic: exact bytes returned by Chromium mock
    mock_render.assert_called_once()  # semantic: render_pdf_chromium was called
```

**T7: `docs_pdf_view` returns 503 when Chromium unavailable (not 501 WeasyPrint error)**

```python
def test_i00074_docs_pdf_view_503_when_chromium_unavailable(client, ...):
    """When Chromium returns None, response is 503, not 500 or 501."""
    from unittest.mock import patch

    with patch("dashboard.utils.markdown.render_pdf_chromium", return_value=None):
        response = client.get(f"/project/{project_id}/docs/{doc_id}/pdf/view")

    assert response.status_code == 503  # semantic: 503 not 501 (WeasyPrint's code)
```

**T8: `docs_pdf` download route uses Chromium, not WeasyPrint**

```python
def test_i00074_docs_pdf_download_does_not_call_weasyprint(client, ...):
    """The PDF download route must not call WeasyPrint.HTML (I-00074)."""
    from unittest.mock import patch

    fake_pdf = b"%PDF-1.4 fake-download"

    with patch("dashboard.utils.markdown.render_pdf_chromium", return_value=fake_pdf) as mock_render:
        response = client.get(f"/project/{project_id}/docs/{doc_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers.get("content-disposition", "")
    mock_render.assert_called_once()  # semantic: Chromium path taken
```

**T9: `_make_render_pdf_fn()` returns `render_pdf_chromium`**

```python
def test_i00074_make_render_pdf_fn_returns_chromium():
    """Export bundle factory must return render_pdf_chromium, not a WeasyPrint wrapper."""
    from dashboard.routers.docs import _make_render_pdf_fn
    from dashboard.utils.markdown import render_pdf_chromium

    fn = _make_render_pdf_fn()
    assert fn is render_pdf_chromium  # semantic: exact same function object
```

## Test Verification

After writing all tests, run ONLY the new test file:

```bash
uv run pytest tests/dashboard/test_docs_pdf_chromium.py -v
```

All tests must pass. Do NOT run `make test-unit` or `make test-integration` — those are
owned by the downstream qv-gate steps (S11, S12).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_docs_pdf_chromium.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "10 tests in test_docs_pdf_chromium.py — all pass",
  "blockers": [],
  "notes": "Reproduction test passes (render_pdf_chromium exists). Semantic assertions verify Chromium path taken, WeasyPrint not called."
}
```
