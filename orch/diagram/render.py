"""Server-side rendering of Mermaid and D2 DSL to SVG.

Never raises — all functions return str | None with graceful fallback.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_MERMAID_BINARY_CACHE: str | None = None
_D2_BINARY_CACHE: str | None = None


def _get_mermaid_binary() -> str | None:
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
    global _D2_BINARY_CACHE
    if _D2_BINARY_CACHE == "":
        return None
    if _D2_BINARY_CACHE is not None:
        return _D2_BINARY_CACHE

    path = shutil.which("d2")
    if path:
        _D2_BINARY_CACHE = path
        return path

    _D2_BINARY_CACHE = ""
    return None


def render_mermaid(dsl: str) -> str | None:
    """Render Mermaid DSL to SVG string. Returns None on any failure."""
    binary = _get_mermaid_binary()
    if not binary:
        logger.warning("mmdc binary not found — Mermaid server-side rendering unavailable")
        return None

    try:
        result = subprocess.run(  # noqa: S603
            [
                binary,
                "--input",
                "-",
                "--output",
                "-",
                "--outputFormat",
                "svg",
                "--puppeteerConfig",
                '{"args":["--no-sandbox","--disable-setuid-sandbox"]}',
            ],
            input=dsl.encode(),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("mmdc timed out after 10s")
        return None
    except OSError as exc:
        logger.warning("Failed to invoke mmdc: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error invoking mmdc: %s", exc)
        return None

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        logger.warning("mmdc exited with code %d: %s", result.returncode, stderr)
        return None

    return result.stdout.decode("utf-8", errors="replace")


def render_d2(dsl: str) -> str | None:
    """Render D2 DSL to SVG string. Returns None on any failure."""
    binary = _get_d2_binary()
    if not binary:
        logger.warning("d2 binary not found — D2 server-side rendering unavailable")
        return None

    try:
        result = subprocess.run(  # noqa: S603
            [binary, "-", "--format", "svg"],
            input=dsl.encode(),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("d2 timed out after 10s")
        return None
    except OSError as exc:
        logger.warning("Failed to invoke d2: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error invoking d2: %s", exc)
        return None

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        logger.warning("d2 exited with code %d: %s", result.returncode, stderr)
        return None

    return result.stdout.decode("utf-8", errors="replace")


def render(dsl: str, dsl_type: str) -> str | None:
    """Convenience dispatcher: dsl_type is 'mermaid' or 'd2'."""
    if dsl_type == "mermaid":
        return render_mermaid(dsl)
    if dsl_type == "d2":
        return render_d2(dsl)
    return None
