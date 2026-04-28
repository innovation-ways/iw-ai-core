"""Check availability of diagram rendering binaries."""

from __future__ import annotations

import shutil
from pathlib import Path


def check_diagram_tools() -> dict[str, bool]:
    """Check availability of diagram rendering binaries.

    Returns {"mermaid": bool, "d2": bool}.
    """
    mermaid_bin = shutil.which("mmdc")
    if not mermaid_bin:
        local = Path("~/.local/bin/mmdc").expanduser()
        if local.exists():
            mermaid_bin = str(local)

    d2_bin = shutil.which("d2")

    return {"mermaid": mermaid_bin is not None, "d2": d2_bin is not None}
