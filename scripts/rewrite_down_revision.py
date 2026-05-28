from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"^(down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*)(.+)$",
    re.MULTILINE,
)


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: python scripts/rewrite_down_revision.py <migration_path>\n")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        sys.stderr.write(f"Error: file not found: {path}\n")
        return 1

    content = path.read_text()

    def _replace(match: re.Match[str]) -> str:
        return f'{match.group(1)}"PENDING"'

    rewritten, count = PATTERN.subn(_replace, content, count=1)
    if count == 0:
        sys.stderr.write(f"Error: no down_revision line found in {path}\n")
        return 1

    path.write_text(rewritten)
    return 0


if __name__ == "__main__":
    sys.exit(main())
