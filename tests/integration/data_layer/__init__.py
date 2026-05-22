"""Data-layer test package — migrations, FTS, and DB-identity invariants.

This package consolidates the three data-layer test surfaces that were either
missing or only partially covered in Phase 3 CR-00076:

- ``test_fts_trigger_invariant.py`` — parametrized FTS trigger coverage for every
  tsvector column in the schema (work_items.design_doc_search,
  work_items.functional_doc_search, project_docs.content_search). Asserts that
  INSERT populates the vector and UPDATE of the searchable field re-generates it.
- ``test_migration_revision_skew.py`` — reproduces the I-00075/I-00076 failure
  class: a DB whose alembic_version points at a revision the on-disk migration
  files do not contain. Alembic surfaces this as a resolution error whose message
  contains ``Can't locate revision identified by``.
- ``test_db_identity_invariants.py`` — formally asserts the DB-identity invariants
  from CR-00014: match / mismatch / bootstrap / missing-row modes, using
  monkeypatch to control IW_CORE_EXPECTED_INSTANCE_ID.

Extends — does not replace — the existing migration round-trip
(``tests/integration/test_migrations_round_trip.py``) or FTS tests
(``tests/integration/test_work_items_functional_doc_fts.py``).

Run all three with::

    make data-layer-check   # migration-check (round-trip) → data_layer/

.. rubric:: Extending this package

When a new tsvector column is added
    Add one entry to ``TSVECTOR_COLUMNS`` in
    ``test_fts_trigger_invariant.py``.

When a new identity edge case surfaces
    Add a case to ``test_db_identity_invariants.py``.

When Alembic's skew error message changes
    Update the ``match=`` argument in the skew regression test.
"""

from __future__ import annotations
