#!/usr/bin/env python3
"""Architecture consistency checker.

Validates cross-package layering is respected:
- orch/ must not import from dashboard/ or executor/
- dashboard/ can import from orch/ but not executor/
- executor/ can import from orch/ but not dashboard/

Exit codes:
  0 = all checks passed
  1 = check failed
  2 = unexpected error
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


PACKAGES = ["orch", "dashboard", "executor"]


def _collect_imports(package_dir: Path) -> dict[str, set[str]]:
    """Walk a package directory and collect all top-level imports per module.

    Returns a dict mapping "package.module" -> set of top-level package imports
    (e.g. {"dashboard", "orch"}).
    """
    imports: dict[str, set[str]] = {}

    for py_file in package_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            rel = package_dir.name
        else:
            rel = (
                str(py_file.relative_to(package_dir.parent))
                .replace("/", ".")
                .replace("\\", ".")
                .removesuffix(".py")
            )

        imports[rel] = set()

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            logger.debug("Failed to read %s", py_file)
            continue

        try:
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            logger.debug("Failed to parse %s", py_file)
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[rel].add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports[rel].add(node.module.split(".")[0])

    return imports


def _cross_package_violations(
    imports: dict[str, set[str]], pkg: str, allowed: set[str]
) -> list[str]:
    """Return list of violation messages for cross-package imports outside allowed layer."""
    violations = []
    pkg_prefix = pkg + "."
    for module, deps in imports.items():
        if not (module == pkg or module.startswith(pkg_prefix)):
            continue
        for dep in deps:
            if dep in PACKAGES and dep not in allowed:
                violations.append(
                    f"  {module} imports '{dep}' which violates layer policy "
                    f"(allowed: {sorted(allowed)})"
                )
    return violations


def main() -> int:
    """Run all cross-package layer checks and report violations.

    Returns:
        0 when all checks pass, 1 when any layer violation is found.
    """
    base = Path(__file__).parent.parent
    errors = []

    layer_policy: dict[str, set[str]] = {
        "orch": {"orch"},
        "dashboard": {"orch", "dashboard"},
        "executor": {"orch", "executor"},
    }

    for pkg in PACKAGES:
        pkg_dir = base / pkg
        if not pkg_dir.exists():
            continue

        imports = _collect_imports(pkg_dir)
        violations = _cross_package_violations(imports, pkg, layer_policy.get(pkg, set()))
        if violations:
            errors.append(f"[{pkg}] Cross-package layer violations:")
            errors.extend(violations)

    if errors:
        print("arch-check FAILED")  # noqa: T201
        print()  # noqa: T201
        for e in errors:
            print(e)  # noqa: T201
        return 1

    print("arch-check PASSED")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
