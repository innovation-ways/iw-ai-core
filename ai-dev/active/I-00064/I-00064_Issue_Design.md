# I-00064: Job detail "View document" link 404s with double project_id prefix

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-05
**Reported By**: sergio (dashboard usage)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT add or modify any Alembic migration. The fix is a
pure Python change inside `orch/jobs/aggregator.py` plus a new test file.

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

In the per-project Jobs view, opening any `doc_generation` job (e.g.
`/project/iw-ai-core/jobs/doc_generation/DOC-00001`) and clicking the
"→ View document" link returns HTTP 404 with the JSON body
`{"detail":"Document 'iw-ai-core:code-index' not found"}`. The link should
navigate to the documentation detail page (`/project/iw-ai-core/docs/code-index`),
but the rendered href contains the composite primary key `iw-ai-core:code-index`,
which the docs route then re-prefixes — producing the unreachable id
`iw-ai-core:iw-ai-core:code-index`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

Relevant area: `orch/jobs/aggregator.py` (read-only unified job table feeding
the Jobs UI) and `dashboard/templates/pages/project/job_detail.html` (the
template that renders the job detail with the "View document" link).

## Browser Evidence

The bug was reproduced live against the running dashboard at
`http://localhost:9900` with `playwright-cli`. Evidence:

| File | Description |
|------|-------------|
| `evidences/pre/I-00064-01-job-detail-with-broken-link.png` | Job detail page for DOC-00001 showing the "View document" link |
| `evidences/pre/I-00064-01-job-detail-snapshot.yml` | Accessibility snapshot — line containing the link reads: `/url: /project/iw-ai-core/docs/iw-ai-core:code-index` (the composite is in the URL) |
| `evidences/pre/I-00064-02-404-after-click.png` | Browser landing page after clicking the link — JSON 404 body visible |
| `evidences/pre/I-00064-02-404-after-click.yml` | Snapshot capturing the rendered text `{"detail":"Document 'iw-ai-core:code-index' not found"}` |

## Steps to Reproduce

1. Open the dashboard: `http://localhost:9900/project/iw-ai-core/jobs`.
2. Filter by "Documentation" or scroll until a `doc_generation` row appears.
3. Click the row to open the job detail page (e.g.
   `/project/iw-ai-core/jobs/doc_generation/DOC-00001`).
4. Click the "→ View document" link in the lower-right of the Parameters card.

**Expected**: The browser navigates to
`/project/iw-ai-core/docs/code-index` (or whatever the inner doc identifier
is) and renders the documentation detail page with the doc title, content,
versions, and "Generate" button.

**Actual**: The browser navigates to
`/project/iw-ai-core/docs/iw-ai-core:code-index` and the response is HTTP
404 with body `{"detail":"Document 'iw-ai-core:code-index' not found"}`.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "http://localhost:9900/project/iw-ai-core/jobs/doc_generation/DOC-00001"
playwright-cli snapshot         # locate the "→ View document" link ref (e.g. e110)
playwright-cli click <ref>      # use the ref id from the snapshot
playwright-cli screenshot       # captures the 404 JSON page
```

The snapshot at the click step will already show the bug because the link's
`/url:` field contains the composite `iw-ai-core:code-index`. Clicking
makes the round-trip, producing the 404 body.

## Root Cause Analysis

Three pieces of code combine to produce the bug:

1. **`orch/db/models.py:1281-1289`** — `ProjectDoc.id` is a composite
   primary key formatted as `"{project_id}:{doc_id}"` (the inner,
   user-defined identifier lives in the separate `ProjectDoc.doc_id`
   column).

2. **`orch/db/models.py:1388-1390` and `:1428`** —
   `DocGenerationJob.doc_id` is a foreign key to `project_docs.id`, so
   it stores the **composite** value (e.g. `iw-ai-core:code-index`),
   not the inner identifier.

3. **`orch/jobs/aggregator.py:397-423` (`_build_doc_generation_raw`)** —
   the helper copies `job.doc_id` straight into the row's `raw["doc_id"]`,
   propagating the composite to the UI. The detail-page entry point
   `_get_doc_generation` (lines 606-631) goes through the same helper.

4. **`dashboard/templates/pages/project/job_detail.html:124-130`** —
   builds the link as
   `/project/{{ current_project.id }}/docs/{{ raw.get('doc_id') }}`,
   producing `/project/iw-ai-core/docs/iw-ai-core:code-index`.

5. **`dashboard/routers/docs.py:65-76`** — the `/docs/{doc_id}` route
   handler delegates to `DocService.get_doc(project_id, doc_id)`.

6. **`orch/doc_service.py:222-224`** — `get_doc` constructs the lookup
   id as `f"{project_id}:{doc_id}"`. With `project_id="iw-ai-core"` and
   `doc_id="iw-ai-core:code-index"` it looks up
   `"iw-ai-core:iw-ai-core:code-index"` → no row → 404.

The doc-route's contract is "give me the inner identifier". Every other
caller that links to a doc page already follows that contract — see
`dashboard/templates/fragments/docs_card.html:64,125`,
`dashboard/templates/fragments/docs_global_results.html:34`,
`dashboard/templates/docs_detail.html:50`. Only the jobs aggregator's
output violates it.

The neighbouring `code_mapping` job type (`_fetch_code_mapping`,
aggregator line 266) also stores the composite in `raw["doc_id"]`, but
the template only uses it as a presence check (gating the visibility of
a "View code map" link whose URL is `/project/{id}/code` — no doc id in
the URL), so that path is not user-broken today. We will not change
`code_mapping` rows in this fix to avoid scope creep, but we will add a
short comment in the aggregator pointing to the convention.

The `research` job type already follows the correct convention
(`_fetch_research` aggregator line 495 sets `raw["doc_id"] = doc.doc_id`,
the inner id).

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/jobs/aggregator.py` | `_build_doc_generation_raw` returns the composite FK as `raw["doc_id"]` — the source of truth for the broken link |
| `dashboard/templates/pages/project/job_detail.html:126` | Renders the URL using `raw["doc_id"]`; consumes the bad value |
| Documentation detail route (`dashboard/routers/docs.py:65`) | Receives the double-prefixed id and 404s — behaviour is correct given the input; nothing to change here |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Fix `_build_doc_generation_raw` in `orch/jobs/aggregator.py` so `raw["doc_id"]` exposes the inner `ProjectDoc.doc_id`. Update `_fetch_doc_generation` to pass the already-loaded `doc_id_map` and `_get_doc_generation` to look up the doc once. Falls back to `None` when the FK is set but the doc has been deleted (orphan), which keeps the template's `{% if raw.get('doc_id') %}` guard correctly hiding the link. | — |
| S02 | code-review-impl | Review S01: correctness of mapping, no extra DB queries (reuse the `doc_titles`/`doc_id_map` lookup already loaded for titles), template contract, orphan handling, no other consumers of `raw["doc_id"]` broken. | — |
| S03 | tests-impl | Write `tests/integration/test_i00064_doc_generation_view_document_url.py`. Includes (a) a reproduction unit-style test against `JobsAggregator._get_doc_generation` asserting `raw["doc_id"]` does NOT contain `:` and equals the source `ProjectDoc.doc_id`; (b) an end-to-end FastAPI TestClient regression test that follows the URL `/project/{pid}/docs/{raw.doc_id}` and asserts HTTP 200; (c) an orphan case asserting `raw["doc_id"]` is `None` when the FK target is missing. | — |
| S04 | code-review-impl | Review S03: tests assert specific values (semantic, not shape); reproduction is falsifiable (passes after the fix, would fail before); FastAPI TestClient set up correctly with the project + doc + job rows; no testcontainer leakage. | — |
| S05 | code-review-final-impl | Global review across S01 and S03 — fix is integrated, the regression test really exercises the broken code path, no other call sites of `raw["doc_id"]` regressed (search). Run full test suite. | — |
| S06 | self-assess-impl | Self-assessment via `iw-item-analyze` skill (project has `self_assess=true`). | — |
| S07..S13 | qv-gate | lint, format-check, typecheck, arch-check, security-sast, test-unit, test-integration | — |
| S14 | qv-browser | Browser verification: visit `DOC-00001` job → click "View document" → expect 200 doc page; visit catalog and Jobs list as no-regression check. | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This incident does not touch the schema.

### Code Changes

- **Files to modify**: `orch/jobs/aggregator.py` only
- **Nature of change**: Substitute the composite FK value in `raw["doc_id"]`
  with the inner `ProjectDoc.doc_id` field. Reuse the doc lookup already
  performed for titles to avoid extra DB queries.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00064_Issue_Design.md` | Design | This document |
| `I-00064_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00064_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00064_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00064_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00064_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00064_S05_CodeReview_Final_prompt.md` | Prompt | S05 global cross-step review |
| `prompts/I-00064_S06_SelfAssess_prompt.md` | Prompt | S06 self-assessment |
| `prompts/I-00064_S14_BrowserVerification_prompt.md` | Prompt | S14 browser verification |
| `evidences/pre/I-00064-01-job-detail-with-broken-link.png` | Evidence | Pre-fix screenshot of the job detail with the broken link |
| `evidences/pre/I-00064-01-job-detail-snapshot.yml` | Evidence | Accessibility snapshot showing the composite id in the URL |
| `evidences/pre/I-00064-02-404-after-click.png` | Evidence | Pre-fix screenshot of the 404 JSON page after clicking |
| `evidences/pre/I-00064-02-404-after-click.yml` | Evidence | Snapshot of the 404 JSON body |

Reports are created during execution under `ai-dev/active/I-00064/reports/`.

## Test to Reproduce

```python
# tests/integration/test_i00064_doc_generation_view_document_url.py
"""I-00064 reproduction: doc_generation job's raw['doc_id'] must be the
inner ProjectDoc.doc_id (not the composite FK), so the job detail page's
"View document" link works."""

def test_i00064_reproduces_bug(db_session) -> None:
    """FAILS before fix, PASSES after.

    Pre-fix: raw['doc_id'] == 'iw-ai-core:code-index' (composite FK).
    Post-fix: raw['doc_id'] == 'code-index' (inner identifier).
    """
    # Arrange — minimal project + doc + doc_generation_job
    project = _make_project(db_session, project_id="iw-ai-core")
    doc = _make_doc(db_session, project_id="iw-ai-core", doc_id="code-index")
    job = _make_doc_generation_job(
        db_session, project_id=project.id, doc_id=doc.id, public_id="DOC-00001"
    )
    db_session.flush()

    # Act
    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(project_id="iw-ai-core", job_type="doc_generation",
                             job_id="DOC-00001")

    # Assert — semantic correctness, not shape
    assert row is not None
    assert row.raw["doc_id"] == "code-index"          # inner id, not composite
    assert ":" not in (row.raw["doc_id"] or "")       # never contains the prefix
```

A second, end-to-end test then walks the URL the template builds, using
the FastAPI TestClient, to prove the link works:

```python
def test_i00064_view_document_link_resolves(client, db_session) -> None:
    project = _make_project(db_session, project_id="iw-ai-core")
    doc = _make_doc(db_session, project_id="iw-ai-core", doc_id="code-index")
    _make_doc_generation_job(db_session, project_id=project.id,
                             doc_id=doc.id, public_id="DOC-00001")
    db_session.commit()

    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(project_id="iw-ai-core", job_type="doc_generation",
                             job_id="DOC-00001")
    url = f"/project/iw-ai-core/docs/{row.raw['doc_id']}"

    response = client.get(url, follow_redirects=False)
    assert response.status_code == 200, (
        f"Expected 200 from {url!r}, got {response.status_code}: {response.text[:200]}"
    )
```

A third test covers the orphan case (job whose doc has been deleted —
`ondelete=SET NULL` makes `job.doc_id` `None`, plus the case where
`job.doc_id` is set but the doc lookup misses):

```python
def test_i00064_orphan_doc_id_is_none(db_session) -> None:
    project = _make_project(db_session, project_id="iw-ai-core")
    job = _make_doc_generation_job(
        db_session, project_id=project.id, doc_id=None, public_id="DOC-00099"
    )
    db_session.commit()

    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(project_id="iw-ai-core", job_type="doc_generation",
                             job_id="DOC-00099")

    assert row is not None
    assert row.raw["doc_id"] is None  # template hides the link via {% if %}
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a doc_generation job whose doc_id FK points at an existing ProjectDoc
When a user opens the job detail page and clicks "→ View document"
Then the browser navigates to /project/{project_id}/docs/{inner_doc_id}
 And the documentation detail page renders with HTTP 200
```

### AC2: Regression test exists

```
Given the fix is applied
When `make test-integration` runs
Then tests/integration/test_i00064_doc_generation_view_document_url.py
 passes (3 tests: reproduction, end-to-end URL resolution, orphan)
```

### AC3: Orphan handling unchanged

```
Given a doc_generation job whose doc has been deleted (FK SET NULL)
 Or a job whose doc_id resolves to a missing ProjectDoc row
When the job detail page is rendered
Then the "View document" link is hidden (raw["doc_id"] is None)
 And no 500 error or stack trace is raised
```

## Regression Prevention

- **Inline contract comment**: add a short comment in
  `_build_doc_generation_raw` and `_fetch_code_mapping` (next to the
  `doc_id` assignment) stating that `raw["doc_id"]` MUST hold the inner
  `ProjectDoc.doc_id` because the template uses it directly in URLs that
  the docs route re-prefixes with the project_id.
- **Regression test** (above) asserts the contract for the
  `doc_generation` row.
- **Cross-job-type sanity**: also verify in S03 that
  `_fetch_research` already follows the convention (its existing test, if
  any, should not regress).

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/jobs/aggregator.py`
- `tests/integration/test_i00064_doc_generation_view_document_url.py`
- `ai-dev/active/I-00064/**`
- `ai-dev/archive/I-00064/**`

## TDD Approach

- **Reproducing test**: `test_i00064_reproduces_bug` — asserts
  `row.raw["doc_id"] == "code-index"` and `":" not in row.raw["doc_id"]`.
  Will FAIL on `main` (composite returned) and PASS after the fix.
- **Unit-level coverage**: build a `DocGenerationJob` against the
  testcontainer, call `JobsAggregator.get_job(...)`, assert on the raw
  dict.
- **Integration / dashboard test**: use FastAPI TestClient — issue a GET
  on `/project/{pid}/docs/{raw.doc_id}` and assert HTTP 200 plus that
  the rendered HTML contains the doc title.

## Notes

- Choice of fix shape (per S01 prompt): in-place replacement of
  `raw["doc_id"]` with the inner identifier — confirmed with the user
  before drafting. The alternative (introducing a new `doc_url_id` field
  and changing the template) was rejected as additive and not warranted
  here, because the only consumer of `raw["doc_id"]` for `doc_generation`
  is the URL link.
- The aggregator already loads `ProjectDoc` rows for titles in
  `_fetch_doc_generation` (lines 362-366) and again in
  `_get_doc_generation` (line 617-619). The fix should reuse those
  lookups; do NOT add a new query path.
- The neighbouring tests at
  `tests/integration/test_i00059_doc_generation_get_job.py:92` assert
  `row.raw.get("doc_id") is None` for orphans — that assertion still
  holds after the fix.
