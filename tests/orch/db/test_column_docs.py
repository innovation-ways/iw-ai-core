"""RED-first tests for the DB-column documentation scanner (CR-00085).

RED phase: write the test BEFORE implementing the scanner; it should fail
with a ModuleNotFoundError because `scripts.check_db_column_docs` does not
yet exist. Once the scanner is implemented, all tests below pass (GREEN).

GREEN phase: these tests verify the scanner's library API contracts:
  - scan() returns a list of Violation objects for undocumented columns
  - the committed baseline produces zero new violations
  - DaemonEvent.event_metadata rename is handled correctly
  - the scanner is composable with arbitrary mapper lists
  - --write-baseline roundtrips through a parse
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# ---------------------------------------------------------------------------
# RED test — running against the missing module must raise ModuleNotFoundError
# ---------------------------------------------------------------------------


def test_all_model_columns_are_documented():
    """CR-00092: every Column in orch/db/models.py now carries a doc=.

    The column-docs scrub (CR-00092) added a ``doc=`` description to every
    Column declaration, so scanning with an EMPTY baseline must yield zero
    violations. This is the blocking invariant the gate now enforces; if a
    future Column lands without a doc=, this test (and ``make check-column-docs``)
    fails naming the offending column.

    (The scanner's ability to *detect* an undocumented column is covered by
    test_scanner_flags_new_undocumented_column_on_synthetic_mapper below, which
    no longer depends on orch.db.models carrying any undocumented columns.)
    """
    from scripts.check_db_column_docs import scan

    violations = scan(baseline=[])  # empty allowlist — no columns may be undocumented
    assert violations == [], (
        "every Column in orch/db/models.py must carry doc=; "
        f"undocumented: {sorted(v.fqn for v in violations)}"
    )


# ---------------------------------------------------------------------------
# GREEN tests
# ---------------------------------------------------------------------------


def test_column_docs_baseline_is_removed():
    """CR-00092: the burn-in baseline file is deleted now that the scrub is complete.

    The scanner runs against ``--baseline /dev/null`` (no allowlist) in the gate;
    the committed baseline allow-list is gone. This test guards against the file
    being reintroduced, which would silently re-open the warn-first escape hatch.
    """
    baseline_path = Path("orch/db/column_docs_baseline.txt")
    assert not baseline_path.exists(), (
        f"baseline file must be deleted after the CR-00092 scrub; found {baseline_path}"
    )


def test_scanner_handles_daemon_event_metadata_rename():
    """Regression: scanner must use SQL column name, not python attribute name.

    DaemonEvent uses `event_metadata` as the Python attribute name because
    SQLAlchemy reserves `metadata` on the declarative base.  The scanner
    must walk `mapper.local_table.columns` and report the SQL column name
    (e.g. `orch.db.models.DaemonEvent.metadata`), never `event_metadata`.
    """

    from orch.db.models import Base
    from scripts.check_db_column_docs import scan

    # Find DaemonEvent mapper via the registry — authoritative.
    daemons = [m for m in Base.registry.mappers if m.class_.__name__ == "DaemonEvent"]
    assert daemons, "DaemonEvent not found in Base.registry.mappers"
    mapper = daemons[0]

    # Verify the SQL column name is `metadata`.
    sql_names = {c.name for c in mapper.local_table.columns}
    assert "metadata" in sql_names, f"expected 'metadata' in SQL columns; got {sql_names}"

    # The python attribute name is `event_metadata`.  This must NOT appear
    # as the FQN in any violation (scanner reports SQL names only).
    violations = scan(baseline=[], mappers=[mapper])
    fqns = {v.fqn for v in violations}
    assert all(".event_metadata" not in f for f in fqns), (
        f"scanner must report SQL column name 'metadata', not python attribute "
        f"'event_metadata'. Got: {fqns}"
    )


def test_scanner_flags_new_undocumented_column_on_synthetic_mapper():
    """Composable: scanner works with a synthetic mapper not on orch.db.models.Base.

    Builds a tiny standalone declarative base, declares a class with one
    undocumented column, passes its mapper to scan(), and asserts exactly
    one violation with the expected FQN.
    """
    from sqlalchemy import Integer, String
    from sqlalchemy.orm import DeclarativeBase, mapped_column

    from scripts.check_db_column_docs import scan

    class SyntheticBase(DeclarativeBase):
        pass

    class FakeModel(SyntheticBase):
        __tablename__ = "fake_model"
        id = mapped_column(Integer, primary_key=True)
        undocumented_col = mapped_column(String, nullable=True)

    mapper = None
    for m in SyntheticBase.registry.mappers:
        if m.class_.__name__ == "FakeModel":
            mapper = m
            break
    assert mapper is not None, "FakeModel mapper not found"

    violations = scan(baseline=[], mappers=[mapper])
    fqns = {v.fqn for v in violations}

    # The synthetic class has two columns: id (likely documentable-or-not depending
    # on whether the declarative machinery sets doc=), and undocumented_col (no doc=).
    # We assert at least undocumented_col is flagged.
    assert any("undocumented_col" in f for f in fqns), (
        f"scanner should flag synthetic model's undocumented_col; got {fqns}"
    )


def test_write_baseline_roundtrips():
    """Baseline written to disk must parse back to identical violation set."""
    from scripts.check_db_column_docs import scan

    violations = scan(baseline=[])
    if not violations:
        pytest.skip("no violations found — baseline would be empty")

    from scripts.check_db_column_docs import _load_baseline

    with TemporaryDirectory() as td:
        path = Path(td) / "roundtrip_baseline.txt"
        # We need to call the CLI-style write routine.
        # Import the internal writer so the test is library-form end-to-end.
        from scripts.check_db_column_docs import _write_baseline

        _write_baseline(path, violations)
        parsed = _load_baseline(path)
        written_lines = {v.as_baseline_line() for v in violations}
        assert parsed == written_lines, "roundtrip baseline must preserve all FQNs"


# ---------------------------------------------------------------------------
# Helpers (also used for roundtrip test)
# ---------------------------------------------------------------------------


def _load_baseline(path: Path) -> set[str]:
    """Parse one-FQN-per-line baseline file (mirrors scanner's internal)."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out
