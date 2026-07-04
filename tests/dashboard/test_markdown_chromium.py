"""S05 — Unit tests for _resolve_chromium_binary() and render_pdf_chromium integration.

AC coverage:
  AC1 — Env var override wins (existing path returned; set-but-nonexistent falls through)
  AC2 — ms-playwright cache glob resolves regardless of version (newest wins)
  AC3 — PATH fallback via shutil.which order: chromium → chromium-browser → google-chrome
  AC4 — Graceful degradation preserved (render_pdf_chromium returns None when unresolved)

No DB, no real subprocess, no actual Chromium launched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from dashboard.utils import markdown as md_mod
from dashboard.utils.markdown import _resolve_chromium_binary, render_pdf_chromium

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_chrome(path: Path) -> None:
    """Create a fake chrome executable (empty file, executable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o755)


# ---------------------------------------------------------------------------
# AC1: Env var override wins
# ---------------------------------------------------------------------------


def test_env_override_wins(monkeypatch, tmp_path):
    """IW_PLAYWRIGHT_CHROME_PATH pointing at an existing executable is returned."""
    # Set up env var pointing at a fake chrome
    env_chrome = tmp_path / "my-chrome-bin"
    _fake_chrome(env_chrome)
    monkeypatch.setenv("IW_PLAYWRIGHT_CHROME_PATH", str(env_chrome))

    # Also create a ms-playwright cache and which result to prove env wins over them
    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)
    fake_cached = cache_root / "chromium-1217" / "chrome-linux64" / "chrome"
    _fake_chrome(fake_cached)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _resolve_chromium_binary()
    assert result == env_chrome


def test_env_override_nonexistent_is_ignored(monkeypatch, tmp_path):
    """IW_PLAYWRIGHT_CHROME_PATH set to a non-existent path falls through to the next method."""
    # Env var set but path doesn't exist
    monkeypatch.setenv("IW_PLAYWRIGHT_CHROME_PATH", str(tmp_path / "does-not-exist"))

    # Set up ms-playwright cache with a valid chrome so we can confirm it's picked
    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)
    fake_cached = cache_root / "chromium-1217" / "chrome-linux64" / "chrome"
    _fake_chrome(fake_cached)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _resolve_chromium_binary()
    # Should fall through to the ms-playwright cache, not return the bogus env path
    assert result == fake_cached


# ---------------------------------------------------------------------------
# AC2: ms-playwright cache glob resolves regardless of version
# ---------------------------------------------------------------------------


def test_ms_playwright_glob_picks_newest(monkeypatch, tmp_path):
    """When env var is absent, the newest chromium-* dir with a real chrome is returned."""
    monkeypatch.delenv("IW_PLAYWRIGHT_CHROME_PATH", raising=False)

    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)

    # Add three chromium dirs: 1208, 1212 (incomplete — no chrome-linux64), 1217
    for suffix in ("1208", "1212"):
        chrome_dir = cache_root / f"chromium-{suffix}" / "chrome-linux64"
        chrome_dir.mkdir(parents=True)
        # Leave chromium-1212 without a chrome binary (incomplete)

    # chromium-1217 has a real chrome
    chrome_1217 = cache_root / "chromium-1217" / "chrome-linux64" / "chrome"
    _fake_chrome(chrome_1217)

    # Also add chromium-1220 as the newest
    chrome_1220 = cache_root / "chromium-1220" / "chrome-linux64" / "chrome"
    _fake_chrome(chrome_1220)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Mock shutil.which to return None so it doesn't interfere
    with patch("dashboard.utils.markdown.shutil.which", return_value=None):
        result = _resolve_chromium_binary()

    # Should pick 1220 (newest), not 1217
    assert result == chrome_1220


def test_ms_playwright_skips_incomplete_dirs(monkeypatch, tmp_path):
    """A chromium-* dir without chrome-linux64/chrome inside is skipped silently."""
    monkeypatch.delenv("IW_PLAYWRIGHT_CHROME_PATH", raising=False)

    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)

    # Only chromium-1212 exists but has no chrome binary
    incomplete = cache_root / "chromium-1212"
    incomplete.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch("dashboard.utils.markdown.shutil.which", return_value=None):
        result = _resolve_chromium_binary()

    # Should fall through to which (returns None in this test)
    assert result is None


# ---------------------------------------------------------------------------
# AC3: PATH fallback via shutil.which
# ---------------------------------------------------------------------------


def test_path_lookup_fallback(monkeypatch, tmp_path):
    """When no env var and no ms-playwright cache, shutil.which result is returned."""
    monkeypatch.delenv("IW_PLAYWRIGHT_CHROME_PATH", raising=False)

    # No ms-playwright cache
    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)
    # (empty — no chromium-* dirs)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    fake_which_path = tmp_path / "bin" / "chromium"
    _fake_chrome(fake_which_path)

    with patch("dashboard.utils.markdown.shutil.which", return_value=str(fake_which_path)):
        result = _resolve_chromium_binary()

    assert result == fake_which_path


def test_path_lookup_tries_names_in_order(monkeypatch, tmp_path):
    """shutil.which is called in order: chromium → chromium-browser → google-chrome."""
    monkeypatch.delenv("IW_PLAYWRIGHT_CHROME_PATH", raising=False)

    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # chromium and chromium-browser return None; google-chrome returns a path
    google_chrome_path = tmp_path / "opt" / "google-chrome" / "chrome"
    _fake_chrome(google_chrome_path)

    calls: list[str] = []

    def fake_which(name: str) -> str | None:
        """Return a path for known executables and None for unknown commands."""
        calls.append(name)
        if name == "google-chrome":
            return str(google_chrome_path)
        return None

    with patch("dashboard.utils.markdown.shutil.which", side_effect=fake_which):
        result = _resolve_chromium_binary()

    assert result == google_chrome_path
    assert calls == ["chromium", "chromium-browser", "google-chrome"]
    # google-chrome-stable should NOT be tried since google-chrome already matched


def test_path_lookup_none_when_nothing_found(monkeypatch, tmp_path):
    """When env, cache, and which all fail, None is returned."""
    monkeypatch.delenv("IW_PLAYWRIGHT_CHROME_PATH", raising=False)

    cache_root = tmp_path / ".cache" / "ms-playwright"
    cache_root.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch("dashboard.utils.markdown.shutil.which", return_value=None):
        result = _resolve_chromium_binary()

    assert result is None


# ---------------------------------------------------------------------------
# AC4: Graceful degradation preserved
# ---------------------------------------------------------------------------


def _fake_failing_worker(cmd, *args, **kwargs):
    """Simulate the PDF worker exiting non-zero — as it would with no usable Chromium.

    Keeps this test environment-independent: on hosts where Playwright ships its
    own browser, the worker would otherwise render successfully regardless of
    ``_PLAYWRIGHT_CHROME``. Per this file's contract, no real subprocess runs.

    Args:
        cmd: The worker argv (ignored beyond echoing back).

    Returns:
        A CompletedProcess with returncode 1 so render_pdf_chromium degrades.
    """
    return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"no chromium")


def test_render_pdf_chromium_returns_none_when_unresolved(monkeypatch):
    """When Chromium is unresolved and the worker fails, render returns None (no raise)."""
    # _PLAYWRIGHT_CHROME None → no explicit binary passed; worker then fails.
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", None)
    monkeypatch.setattr(md_mod.subprocess, "run", _fake_failing_worker)

    result = render_pdf_chromium("<h1>x</h1>")

    # Must return None, not raise
    assert result is None


def test_render_pdf_chromium_returns_none_when_path_missing(monkeypatch, tmp_path):
    """When the Chromium path is missing and the worker fails, returns None (not an exception)."""
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", tmp_path / "this-does-not-exist")
    monkeypatch.setattr(md_mod.subprocess, "run", _fake_failing_worker)

    result = render_pdf_chromium("<h1>x</h1>")

    assert result is None
