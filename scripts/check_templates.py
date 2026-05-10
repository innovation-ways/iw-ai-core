#!/usr/bin/env python3
"""Static lint for Jinja2 templates — catch crashes that would otherwise only
surface at browser_verification time.

Currently checks one thing:

  Jinja2's ``format`` filter is ``%``-style (``"%dm%02ds"|format(m, s)`` →
  ``"%dm%02ds" % (m, s)``). Using ``str.format``-style ``{}`` / ``{0}``
  placeholders with it (``"{}m{}s"|format(m, s)``) raises
  ``TypeError: not all arguments converted during string formatting`` the
  moment the branch is actually taken — which can be never in dev/test if the
  data shape that exercises it (e.g. a workflow step with a non-NULL duration)
  doesn't exist in the seed data. I-00075 hit exactly this: CR-00039 shipped
  ``step_pipeline.html`` with ``"{}m{}s"|format(...)`` and it 500'd only once a
  fixture seeded a step with real timestamps.

Mirrors the spirit of ``make lint-js`` (F-00055 post-mortem): fail fast in
``make lint`` instead of in a 5-cycle browser-verification loop.

Exit code 0 = clean, 1 = violations found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "dashboard" / "templates"

# A quoted string literal that contains a str.format-style placeholder
# (`{}`, `{0}`, `{name}`, `{0:02d}`, ...) and is piped to the `format` filter.
# Matches e.g.  "{}m{}s"|format(dur_m, dur_s)   or   '{0}/{1}' | format(a, b)
_BAD_FORMAT_RE = re.compile(
    r"""(?P<quote>['"])              # opening quote
        (?P<body>(?:(?!(?P=quote)).)*  # string body (no unescaped closing quote)
            \{[^{}%]*\}              # ... containing a {..} placeholder
            (?:(?!(?P=quote)).)*)
        (?P=quote)
        \s*\|\s*format\b             # ... piped to the `format` filter
    """,
    re.VERBOSE,
)


def _iter_template_files() -> list[Path]:
    if not TEMPLATE_DIR.is_dir():
        return []
    return sorted(TEMPLATE_DIR.rglob("*.html"))


def check_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for m in _BAD_FORMAT_RE.finditer(line):
            findings.append((lineno, m.group(0).strip()))
    return findings


def main() -> int:
    violations: list[str] = []
    for path in _iter_template_files():
        for lineno, snippet in check_file(path):
            rel = path.relative_to(REPO_ROOT)
            violations.append(f"{rel}:{lineno}: {snippet}")

    if violations:
        sys.stderr.write(
            "ERROR: Jinja2 `format` filter is %-style — use %d/%s placeholders, "
            "not str.format-style {}.\n"
            '  e.g.  "%dm%02ds"|format(m, s)        (correct)\n'
            '        "{}m{}s"|format(m, s)          (raises TypeError at render time)\n'
            "Or build the string with ~ concatenation: (m ~ 'm' ~ s ~ 's').\n"
            "See I-00075 for why this only blows up under real data.\n\n"
        )
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
