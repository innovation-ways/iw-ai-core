"""Server-side rendering of Mermaid and D2 DSL to SVG.

Never raises — all functions return str | None with graceful fallback.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_MERMAID_BINARY_CACHE: str | None = None
_D2_BINARY_CACHE: str | None = None


def _mermaid_env() -> dict[str, str]:
    """Return a subprocess env with PUPPETEER_EXECUTABLE_PATH set when resolvable.

    mmdc needs a Chromium to render; without an explicit executable it tries to
    download one. Point it at the Playwright-managed Chromium so validation works
    in headless environments. Resolution: ``$IW_PLAYWRIGHT_CHROME_PATH`` → newest
    ``~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome``.
    """
    env = os.environ.copy()
    chrome = os.environ.get("IW_PLAYWRIGHT_CHROME_PATH", "")
    if not chrome or not Path(chrome).exists():
        cache = Path.home() / ".cache" / "ms-playwright"
        candidates: list[tuple[int, Path]] = []
        if cache.is_dir():
            for d in cache.iterdir():
                if d.is_dir() and d.name.startswith("chromium-"):
                    binp = d / "chrome-linux64" / "chrome"
                    try:
                        suffix = int(d.name.removeprefix("chromium-"))
                    except ValueError:
                        continue
                    if binp.is_file():
                        candidates.append((suffix, binp))
        chrome = str(max(candidates)[1]) if candidates else ""
    if chrome:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome
    return env


def _mermaid_command() -> list[str] | None:
    """Return the argv prefix that runs Mermaid, or None when unavailable.

    Prefers a standalone ``mmdc`` binary; falls back to ``npx
    @mermaid-js/mermaid-cli`` (how the dashboard renders), so validation works in
    environments that only have npx.
    """
    binary = _get_mermaid_binary()
    if binary:
        return [binary]
    if shutil.which("npx"):
        return ["npx", "@mermaid-js/mermaid-cli"]
    return None


def mermaid_available() -> bool:
    """Return True when Mermaid can be rendered (mmdc binary or npx present)."""
    return _mermaid_command() is not None


def d2_available() -> bool:
    """Return True when the d2 binary is resolvable (for validation gating)."""
    return _get_d2_binary() is not None


def _get_mermaid_binary() -> str | None:
    """Return the path to the mmdc binary, checking PATH then ~/.local/bin. Cached."""
    global _MERMAID_BINARY_CACHE
    if _MERMAID_BINARY_CACHE == "":
        return None
    if _MERMAID_BINARY_CACHE is not None:
        return _MERMAID_BINARY_CACHE

    path = shutil.which("mmdc")
    if path:
        _MERMAID_BINARY_CACHE = path
        return path

    local = Path("~/.local/bin/mmdc").expanduser()
    if local.exists():
        _MERMAID_BINARY_CACHE = str(local)
        return str(local)

    _MERMAID_BINARY_CACHE = ""
    return None


def _get_d2_binary() -> str | None:
    """Return the path to the d2 binary from PATH. Cached."""
    global _D2_BINARY_CACHE
    if _D2_BINARY_CACHE == "":
        return None
    if _D2_BINARY_CACHE is not None:
        return _D2_BINARY_CACHE

    env_path = os.environ.get("IW_D2_PATH", "")
    if env_path and Path(env_path).exists():
        _D2_BINARY_CACHE = env_path
        return env_path

    path = shutil.which("d2")
    if path:
        _D2_BINARY_CACHE = path
        return path

    local = Path("~/.local/bin/d2").expanduser()
    if local.is_file():
        _D2_BINARY_CACHE = str(local)
        return str(local)

    _D2_BINARY_CACHE = ""
    return None


def render_mermaid(dsl: str) -> str | None:
    """Render Mermaid DSL to an SVG string. Returns None on any failure.

    Uses a standalone ``mmdc`` binary or ``npx @mermaid-js/mermaid-cli`` via
    temp files (mirroring the dashboard render path), with the Playwright
    Chromium resolved into the subprocess env.
    """
    command = _mermaid_command()
    if command is None:
        logger.warning("Mermaid renderer not found (no mmdc binary, no npx)")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "diagram.mmd"
        out_path = Path(tmpdir) / "diagram.svg"
        cfg_path = Path(tmpdir) / "puppeteer.json"
        in_path.write_text(dsl, encoding="utf-8")
        cfg_path.write_text(
            '{"args":["--no-sandbox","--disable-setuid-sandbox"]}', encoding="utf-8"
        )
        try:
            result = subprocess.run(  # noqa: S603
                [
                    *command,
                    "-i",
                    str(in_path),
                    "-o",
                    str(out_path),
                    "-b",
                    "#ffffff",
                    "--puppeteerConfigFile",
                    str(cfg_path),
                ],
                capture_output=True,
                timeout=30,
                check=False,
                env=_mermaid_env(),
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("Failed to invoke Mermaid renderer: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — module contract: never raise
            logger.warning("Unexpected error invoking Mermaid renderer: %s", exc)
            return None

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            logger.warning("Mermaid render exited %d: %s", result.returncode, stderr[:300])
            return None
        if not out_path.exists() or out_path.stat().st_size < 100:
            return None
        return out_path.read_text(encoding="utf-8")


def render_d2(dsl: str) -> str | None:
    """Render D2 DSL to an SVG string. Returns None on any failure.

    Renders natively via the ``d2`` binary (ELK layout, no browser) to a temp
    SVG file. Note: ``d2`` v0.7 uses positional ``input output`` paths, not the
    ``--format`` flag.
    """
    binary = _get_d2_binary()
    if not binary:
        logger.warning("d2 binary not found — D2 server-side rendering unavailable")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "diagram.d2"
        out_path = Path(tmpdir) / "diagram.svg"
        in_path.write_text(dsl, encoding="utf-8")
        try:
            result = subprocess.run(  # noqa: S603
                [binary, "--layout", "elk", "--pad", "24", str(in_path), str(out_path)],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("Failed to invoke d2: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — module contract: never raise
            logger.warning("Unexpected error invoking d2: %s", exc)
            return None

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            logger.warning("d2 exited %d: %s", result.returncode, stderr[:300])
            return None
        if not out_path.exists() or out_path.stat().st_size < 100:
            return None
        return out_path.read_text(encoding="utf-8")


def render(dsl: str, dsl_type: str) -> str | None:
    """Render a DSL string to SVG, dispatching by dsl_type.

    Args:
        dsl: The diagram source string.
        dsl_type: Either ``"mermaid"`` or ``"d2"``.

    Returns:
        SVG string, or None when the rendering binary is unavailable or fails.
    """
    if dsl_type == "mermaid":
        return render_mermaid(dsl)
    if dsl_type == "d2":
        return render_d2(dsl)
    return None
