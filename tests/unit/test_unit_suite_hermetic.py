"""Hermetic-unit-suite guard — I-00125.

FAILS before S01 (16 static offenders: 13 direct-import test files +
3 conftest wiring files); PASSES after S01 relocation.

Each file under tests/unit/ is scanned in SOURCE TEXT (no import) for either vector:
  Vector A — a file that BOTH (1) mentions the testcontainers module AND
              (2) contains an actual PostgresContainer() constructor call.
              A bare class-name mention in a @patch target string or docstring
              is NOT sufficient.
  Vector B — import statement reaching tests.integration.conftest fixtures

A file is an offender if it matches EITHER vector.
Excludes the guard file itself (by resolved path) so its own pattern tokens do NOT
self-flag.
"""

from __future__ import annotations

import pathlib
import re

import pytest


def test_i00125_unit_suite_is_hermetic():
    """Assert no file under tests/unit/ reaches a testcontainer via either vector."""
    # Vector B: import statement (anchored, MULTILINE) that pulls in the real
    # testcontainer fixtures from the integration conftest.
    # Separated into prefix+name so the guard's own source does not self-flag.
    _from_tic = "from tests"
    _import_tic = "import tests"
    _conftest_import = re.compile(
        rf"^\s*({re.escape(_from_tic)}\.integration\.conftest\s+import"
        rf"|{re.escape(_import_tic)}\.integration\.conftest)",
        re.MULTILINE,
    )

    # Vector A: a file must BOTH touch the module name AND contain a constructor
    # call.  This two-condition gate eliminates @patch-target false positives
    # (test_migration_pipeline.py, test_migrations_cli.py) and prose false
    # positives (test_agent_subprocess_env.py, etc.).
    # Tokens split so the guard's own source does not self-flag.
    _tk_tc = "testcontainers"
    _tk_pg = "PostgresContainer"
    _module_tk = re.compile(rf"\b{re.escape(_tk_tc)}\b")
    _call_pat = re.compile(rf"\b{re.escape(_tk_pg)}\s*\(")

    this_file = pathlib.Path(__file__).resolve()
    offenders: list[str] = []

    for path in pathlib.Path("tests/unit").rglob("*.py"):
        if path.resolve() == this_file:
            continue
        text = path.read_text(encoding="utf-8")

        # Vector B — integration-conftest fixture import
        if _conftest_import.search(text):
            offenders.append(str(path))
            continue

        # Vector A — both conditions must be TRUE for the file to be an offender
        if _module_tk.search(text) and _call_pat.search(text):
            offenders.append(str(path))

    # SEMANTIC: assert the specific set is EMPTY, list any offenders by path.
    assert offenders == [], (
        "tests/unit must not reach a testcontainer (direct import or via "
        "tests.integration.conftest); move these to tests/integration/: " + ", ".join(offenders)
    )
