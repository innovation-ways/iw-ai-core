"""FTS-trigger invariant test — all tsvector columns must be populated by their triggers.

This module extends tests/integration/test_work_items_functional_doc_fts.py
(which covers the functional_doc FTS trigger in isolation and with round-trip
migration) by asserting the broader invariant: every tsvector column in the
schema is non-null and non-empty after a row is inserted and then updated.

The three tsvector columns are:
  1. work_items.design_doc_search   — trigger: trg_work_items_fts
  2. work_items.functional_doc_search — trigger: work_items_functional_doc_search_trg
  3. project_docs.content_search   — trigger: trg_project_docs_fts

The db_session fixture inherits all three FTS function+trigger pairs because
the template DB is built via alembic upgrade head (see _migrate_template in
tests/integration/conftest.py).  No manual FTS DDL is needed here.

If a new tsvector column is added to the schema, add it to TSVECTOR_COLUMNS
(below) and a corresponding case will be automatically parametrised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from orch.db.models import (
    Project,
    ProjectDoc,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy import TextClause
    from sqlalchemy.orm import Session


# --------------------------------------------------------------------------
# Enumerate every (table, tsvector_column, searchable_text_column) tuple.
# Update this constant when a new tsvector column is added to the schema.
# --------------------------------------------------------------------------
TSVECTOR_COLUMNS: list[tuple[str, str, list[str]]] = [
    (
        "work_items",
        "design_doc_search",
        ["title", "design_doc_content"],
    ),
    (
        "work_items",
        "functional_doc_search",
        ["title", "functional_doc_content"],
    ),
    (
        "project_docs",
        "content_search",
        ["title", "content"],
    ),
]


def _dynamic_sql(template: str, **identifiers: str) -> TextClause:
    """Build a ``text()`` clause whose SQL interpolates table/column identifiers.

    SQL identifiers (table and column names) cannot be passed as bound
    parameters, so the FTS tests interpolate them into the query directly.
    Every identifier originates from the module-level ``TSVECTOR_COLUMNS``
    constant — trusted literals, never user input — so ruff's S608
    SQL-injection warning is a false positive here. Value parameters
    (``:pid``, ``:val`` …) are still bound, never interpolated.
    """
    return text(template.format(**identifiers))  # noqa: S608


@pytest.mark.parametrize(("table", "tsvector_col", "searchable_cols"), TSVECTOR_COLUMNS)
def test_fts_trigger_populates_tsvector_on_insert(
    db_session: Session,
    test_project: Project,
    table: str,
    tsvector_col: str,
    searchable_cols: list[str],
) -> None:
    """Insert a row — assert the tsvector column is non-null after INSERT."""
    if table == "work_items":
        _insert_work_item(db_session, test_project.id, searchable_cols)
    elif table == "project_docs":
        _insert_project_doc(db_session, test_project.id, searchable_cols)
    else:
        pytest.fail(f"Unexpected table: {table}")

    db_session.commit()

    if table == "work_items":
        result = db_session.execute(
            _dynamic_sql(
                "SELECT {col} FROM {tbl} WHERE project_id = :pid LIMIT 1",
                col=tsvector_col,
                tbl=table,
            ),
            {"pid": test_project.id},
        )
    else:
        # project_docs: PK is composite "{project_id}:{doc_id}"
        result = db_session.execute(
            _dynamic_sql(
                "SELECT {col} FROM {tbl} WHERE id LIKE :pid_prefix LIMIT 1",
                col=tsvector_col,
                tbl=table,
            ),
            {"pid_prefix": f"{test_project.id}:%"},
        )

    row = result.fetchone()
    assert row is not None, f"No row found in {table} for project {test_project.id}"
    tsvector_value = row[0]
    assert tsvector_value is not None, (
        f"{table}.{tsvector_col} is NULL after INSERT — FTS trigger may be missing or broken"
    )
    assert str(tsvector_value).strip() != "", (
        f"{table}.{tsvector_col} is empty after INSERT — FTS trigger returned empty tsvector"
    )


@pytest.mark.parametrize(("table", "tsvector_col", "searchable_cols"), TSVECTOR_COLUMNS)
def test_fts_trigger_regenerates_tsvector_on_update(
    db_session: Session,
    test_project: Project,
    table: str,
    tsvector_col: str,
    searchable_cols: list[str],
) -> None:
    """Update a searchable text field — assert the tsvector column is non-null
    and reflects the updated value."""
    if table == "work_items":
        item_id = _insert_work_item(db_session, test_project.id, searchable_cols)
        where_clause = "project_id = :pid AND id = :id"
        where_params = {"pid": test_project.id, "id": item_id}
    elif table == "project_docs":
        doc_id = _insert_project_doc(db_session, test_project.id, searchable_cols)
        full_pk = f"{test_project.id}:{doc_id}"
        where_clause = "id = :id"
        where_params = {"id": full_pk}
    else:
        pytest.fail(f"Unexpected table: {table}")

    db_session.commit()

    if table == "work_items":
        # Prefer the non-title field for update if present
        update_col = searchable_cols[-1] if len(searchable_cols) > 1 else searchable_cols[0]
    else:
        # project_docs: always update 'content' (the trigger watches it)
        update_col = "content"

    update_value = "Updated Search Term xyz789"

    db_session.execute(
        _dynamic_sql(
            "UPDATE {tbl} SET {ucol} = :val WHERE {where}",
            tbl=table,
            ucol=update_col,
            where=where_clause,
        ),
        {"val": update_value, **where_params},
    )
    db_session.commit()

    result = db_session.execute(
        _dynamic_sql(
            "SELECT {col}::text FROM {tbl} WHERE {where}",
            col=tsvector_col,
            tbl=table,
            where=where_clause,
        ),
        where_params,
    )
    row = result.fetchone()
    assert row is not None, f"Row disappeared after UPDATE in {table}"
    tsvector_text = row[0]
    assert tsvector_text is not None, (
        f"{table}.{tsvector_col} is NULL after UPDATE — FTS trigger failed to fire on UPDATE"
    )
    assert "xyz789" in tsvector_text, (
        f"{table}.{tsvector_col} does not contain new lexeme 'xyz789' after UPDATE — "
        f"trigger may not have regenerated the tsvector. Got: {tsvector_text!r}"
    )

    # The regenerated tsvector must be FTS-queryable for the new lexeme — that is
    # the behaviour the column exists for. The exact row count (== 1) is a
    # mutation-killing assertion: it fails if the trigger left a stale tsvector.
    matched = db_session.execute(
        _dynamic_sql(
            "SELECT count(*) FROM {tbl} WHERE {col} @@ to_tsquery('english', :term) AND {where}",
            col=tsvector_col,
            tbl=table,
            where=where_clause,
        ),
        {"term": "xyz789", **where_params},
    ).scalar()
    assert matched == 1, (
        f"{table}.{tsvector_col} did not match an FTS query for the updated lexeme "
        f"'xyz789' (matched {matched} row(s), expected 1) — the trigger did not "
        f"regenerate the tsvector on UPDATE"
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _insert_work_item(
    session: Session,
    project_id: str,
    searchable_cols: list[str],
) -> str:
    """Insert a minimal WorkItem and return its id.

    title is always set; functional_doc_content or design_doc_content
    is set when the column appears in searchable_cols.
    """
    kwargs: dict = {
        "project_id": project_id,
        "id": f"WI-FTS-{project_id[:4]}-{len(searchable_cols)}",
        "type": WorkItemType.Feature,
        "title": "FTS Test Item",
        "status": WorkItemStatus.draft,
        "phase": WorkItemPhase.active,
    }
    if "design_doc_content" in searchable_cols:
        kwargs["design_doc_content"] = "Initial design content"
    if "functional_doc_content" in searchable_cols:
        kwargs["functional_doc_content"] = "Initial functional content"

    item = WorkItem(**kwargs)
    session.add(item)
    session.flush()
    return item.id


def _insert_project_doc(
    session: Session,
    project_id: str,
    searchable_cols: list[str],
) -> str:
    """Insert a minimal ProjectDoc and return its doc_id (NOT the composite PK).

    Callers that need the full PK must construct it as f"{project_id}:{doc_id}".
    """
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory

    doc_id = f"fts-doc-{project_id[:4]}"
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",  # composite PK
        project_id=project_id,
        doc_id=doc_id,
        title="FTS Test Document",
        slug="fts-test-doc",
        doc_type=DocType.module,
        tier=DocTier.fully_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
    )
    if "content" in searchable_cols:
        doc.content = "Initial content for FTS testing"
    session.add(doc)
    session.flush()
    return doc_id
