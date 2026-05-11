# I-00077: Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-10
**Reported By**: sergio (observed on http://iw-dev-01:9900 — job DOC-00055)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migrations** — the `_default` row already exists in `doc_type_guides` (inserted by `20260414_add_doc_type_guides.py`); the fix only changes how it is consumed.

## Description

Triggering a documentation regeneration for a doc whose `doc_type` has no explicit editorial guide row (e.g. `doc_type=diagram`) produces a job whose `guide_snapshot` and `section_guides_snapshot` are both `None`. The launched agent treats the null editorial context as a fatal blocker and closes the job with `--error` instead of generating the document. The failure is then **invisible on the Docs catalogue page** (`/project/<id>/docs`) — the running-jobs strip only shows `running` jobs, so a failed job vanishes after a ~1.2 s red flash, and that page has no `docJobFailed` listener at all. Users only discover the failure on the `/jobs` view.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant areas: `orch/doc_service.py` (`orch/doc_sections.py`, `orch/doc_diff.py` are siblings), the daemon's `orch/daemon/doc_job_poller.py`, the Docs dashboard routes/templates (`dashboard/routers/docs.py`, `dashboard/templates/docs_library.html`, `dashboard/templates/docs_detail.html`, `dashboard/templates/fragments/docs_running_jobs.html`), and the doc-generation skills under `skills/iw-doc-generator/` and `skills/iw-doc-system/`.

## Steps to Reproduce

1. On the Docs page of a project, trigger regeneration of a doc whose `doc_type` has no row in `doc_type_guides` and no per-doc instance guide — e.g. `iw-ai-core:diagram-architecture` (`doc_type=diagram`).
2. Observe the running-jobs strip at the top of `/project/<id>/docs`.
3. Wait for the job to finish (it fails within ~25 s).
4. Look for any failure indication on the Docs page.

**Expected**:
- The agent generates the diagram using the static `references/diagram-guidelines.md` even though the job's editorial snapshot is empty (a `_default` global editorial guide exists and should have been snapshotted as `guide_snapshot`).
- If a doc job *does* fail, the Docs catalogue page surfaces it persistently — a visible failed-job entry and/or a toast carrying the error — not only the `/jobs` view.

**Actual**:
- `DocService.create_doc_job()` snapshots `guide_snapshot=None` (and `section_guides_snapshot=None` since the doc has no section guides). `iw doc-job-status --json` reports both as `null`.
- The agent (observed: `MiniMax-M2.7` via opencode, job DOC-00055) reads `references/diagram-guidelines.md`, then runs `iw doc-job-done … --error 'job context has no section_guides_snapshot — cannot generate content without editorial guidance'` and exits. Same pattern previously hit DOC-00050 (`module-dashboard`).
- On `/project/iw-ai-core/docs` the failed job briefly flashes red in the running-jobs strip, then disappears (`runningJobsReload`). No toast, no banner, no persistent row. The failure is only visible on `/jobs`.

## Root Cause Analysis

Three independent contributing causes:

1. **`DocService._effective_guide()` never falls back to the `_default` `DocTypeGuide` row** — `orch/doc_service.py` (`_effective_guide`, ~L912):
   ```python
   def _effective_guide(self, project_id: str, doc_id: str, doc_type: str) -> str | None:
       instance = self.get_instance_guide(project_id, doc_id)
       if instance is not None:
           return instance
       return self.get_type_guide(doc_type)
   ```
   `get_type_guide("diagram")` returns `None` because only `_default` and `marketing` rows exist in `doc_type_guides`. The `_default` row was inserted in migration `20260414_add_doc_type_guides.py` precisely to be the global baseline, but `_effective_guide` never consults it. Result: `create_doc_job()` (~L483) snapshots `guide_snapshot=None`.

2. **The `iw-doc-generator` / `iw-doc-system` skills do not state that a null editorial snapshot is acceptable** — `skills/iw-doc-generator/SKILL.md` ("Job lifecycle" section, step 1) and `skills/iw-doc-system/SKILL.md` (same) only instruct the agent to abort when `iw doc-job-status` *exits non-zero*. They say nothing about `section_guides_snapshot` / `guide_snapshot` being `null`. A less-careful model interprets a null snapshot as a fatal blocker and closes the job with `--error` rather than generating from the static `references/…-guidelines.md`. The skill should explicitly say: null `section_guides_snapshot` / `guide_snapshot` is normal — proceed using the skill's `references/…-guidelines.md`; only abort on a non-zero `doc-job-status` exit.

3. **The Docs catalogue page does not surface job failures** — `dashboard/templates/docs_library.html` (the `/project/<id>/docs` page) wires `#docs-running-jobs` with `hx-trigger="load, runningJobsReload from:body"` and has **no `docJobFailed` listener** (only `dashboard/templates/docs_detail.html` — the single-doc page — listens for `docJobFailed` and renders a red banner). `dashboard/routers/docs.py::docs_running_jobs` queries only `DocGenerationJob.status == JobStatus.running` and `fragments/docs_running_jobs.html`'s per-job SSE handler, on a `failed` event, dispatches `docJobFailed` (no listener on the catalogue page → no-op) then `cleanup('border-red-400 …')` which paints the row red for ~1.2 s before dispatching `runningJobsReload`, which re-fetches the strip — now empty. Net effect on the catalogue page: a transient red flash and nothing persistent.

## Affected Components

| Component | File(s) | Impact |
|-----------|---------|--------|
| Doc editorial-guide resolution | `orch/doc_service.py` | `_effective_guide` returns `None` for any `doc_type` lacking an explicit guide row → `guide_snapshot=None` in the job context |
| Doc-generation skills | `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md` | Ambiguous "job lifecycle" guidance → agents abort instead of generating |
| Docs catalogue running-jobs strip | `dashboard/routers/docs.py` (`docs_running_jobs`), `dashboard/templates/fragments/docs_running_jobs.html` | Failed jobs excluded from the strip; failure UI is a 1.2 s flash |
| Docs catalogue page | `dashboard/templates/docs_library.html` | No `docJobFailed` listener → no persistent failure indication |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Fix #1: `_effective_guide` falls back to `get_type_guide("_default")` when neither an instance guide nor a `doc_type`-keyed guide exists. Fix #2: update `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md` "Job lifecycle" sections to state that null `section_guides_snapshot`/`guide_snapshot` is normal — proceed using the skill's static `references/…-guidelines.md`; only abort on a non-zero `doc-job-status` exit. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | Fix #3: `docs_running_jobs` also returns jobs that `failed` recently (within ~10 min); `fragments/docs_running_jobs.html` renders failed jobs as a dismissible red row showing the error; `docs_library.html` gains a `docJobFailed` listener that shows a persistent toast/banner. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | Reproduction test (integration: `create_doc_job` snapshots the `_default` guide for a `diagram` doc; unit: `_effective_guide` returns `_default` content) + regression tests (`docs_running_jobs` includes a recently-failed job; failed-row markup present; `docJobFailed` listener wired) | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Global cross-agent review | — |
| S08..S12 | qv-gate | lint · format-check · type-check · test-unit · test-integration | — |
| S13 | qv-browser | Browser verification — seed a failed `DocGenerationJob`; confirm the Docs catalogue page surfaces it persistently; no regressions | — |
| S14 | self-assess-impl | Self-assessment via `iw-item-analyze` | — |

Agent slugs: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — `doc_type_guides._default` already exists from `20260414_add_doc_type_guides.py`.

### Code Changes

- **Files to modify**:
  - `orch/doc_service.py` — `_effective_guide` `_default` fallback
  - `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md` — "Job lifecycle" wording
  - `dashboard/routers/docs.py` — `docs_running_jobs` query + the dict it passes to the fragment
  - `dashboard/templates/fragments/docs_running_jobs.html` — render failed jobs as a dismissible red row
  - `dashboard/templates/docs_library.html` — `docJobFailed` listener → persistent toast/banner
- **Nature of change**: small, surgical — a fallback lookup, two skill-doc clarifications, one query widening, and one template/JS addition. No refactors.

## File Manifest

All files for this work item live under `ai-dev/active/I-00077/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00077_Issue_Design.md` | Design | This document |
| `I-00077_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00077_S01_backend-impl_prompt.md` | Prompt | S01 — `_effective_guide` fallback + skill clarifications |
| `prompts/I-00077_S02_CodeReview_prompt.md` | Prompt | S02 — review of S01 |
| `prompts/I-00077_S03_frontend-impl_prompt.md` | Prompt | S03 — Docs catalogue page surfaces job failures |
| `prompts/I-00077_S04_CodeReview_prompt.md` | Prompt | S04 — review of S03 |
| `prompts/I-00077_S05_tests-impl_prompt.md` | Prompt | S05 — reproduction + regression tests |
| `prompts/I-00077_S06_CodeReview_prompt.md` | Prompt | S06 — review of S05 |
| `prompts/I-00077_S07_CodeReview_Final_prompt.md` | Prompt | S07 — global review |
| `prompts/I-00077_S13_BrowserVerification_prompt.md` | Prompt | S13 — browser verification |
| `prompts/I-00077_S14_SelfAssess_prompt.md` | Prompt | S14 — self-assessment |

Reports are created during execution in `ai-dev/active/I-00077/reports/`.

## Test to Reproduce

Write these failing tests before fixing. Test-file placement: `_effective_guide` / `create_doc_job` tests require a DB (or a `MagicMock` session) and go under `tests/integration/` (testcontainer) or `tests/unit/` (mock). The `docs_running_jobs` test drives a FastAPI route and **must** live under `tests/dashboard/` (the `client` fixture is only registered in `tests/dashboard/conftest.py`).

**Reproduction test #1 — `_effective_guide` falls back to `_default` (unit, `tests/unit/test_doc_type_guide_service.py`):**

```python
def test_effective_guide_falls_back_to_default_when_no_specific_guide() -> None:
    """FAILS before fix: _effective_guide returns None when neither an instance
    guide nor a doc_type-keyed guide exists, even though a '_default' row exists."""
    from unittest.mock import MagicMock
    from orch.db.models import DocInstanceGuide, DocTypeGuide
    from orch.doc_service import DocService

    default_guide = MagicMock(spec=DocTypeGuide)
    default_guide.guide_md = "# Global Editorial Guidelines\n..."

    def fake_get(model, key):
        if model is DocInstanceGuide:
            return None                       # no per-doc instance guide
        if model is DocTypeGuide and key == "diagram":
            return None                       # no diagram-specific guide
        if model is DocTypeGuide and key == "_default":
            return default_guide
        return None

    session = MagicMock()
    session.get.side_effect = fake_get
    svc = DocService(session)

    result = svc._effective_guide("iw-ai-core", "diagram-architecture", "diagram")
    assert result == "# Global Editorial Guidelines\n..."   # was None before the fix
```

**Reproduction test #2 — `create_doc_job` snapshots the `_default` guide (integration, extend `tests/integration/test_doc_type_guides.py`):**

```python
def test_create_doc_job_snapshots_default_guide_for_diagram_doc(db_session) -> None:
    """FAILS before fix: guide_snapshot is None for a diagram doc with no
    diagram-specific or instance guide, despite a _default row existing."""
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.save_type_guide("_default", "# Global Editorial Guidelines\nbaseline")
    # ... create a ProjectDoc with doc_type=diagram (no instance guide) ...
    job = svc.create_doc_job("iw-ai-core", "diagram-architecture")
    assert job.guide_snapshot == "# Global Editorial Guidelines\nbaseline"   # was None
```

**Regression test #3 — failed doc job appears in the running-jobs strip (dashboard, extend `tests/dashboard/test_docs_running_jobs.py`):**

```python
def test_running_jobs_strip_includes_recently_failed_job(client, db_session) -> None:
    """FAILS before fix: docs_running_jobs filters to status==running only, so a
    failed DocGenerationJob never appears on the Docs catalogue page."""
    # ... seed a ProjectDoc + a DocGenerationJob(status=failed, error='boom',
    #     completed_at=now()) for that doc ...
    resp = client.get(f"/project/{project_id}/api/docs/running-jobs")
    assert resp.status_code == 200
    html = resp.text
    assert 'class="' in html and "boom" in html       # error surfaced
    # the failed row carries a dismiss control (semantic — assert the attribute,
    # not a bare substring) e.g. hx-delete to the job's dismiss endpoint
```

## Acceptance Criteria

### AC1: Missing editorial guide no longer aborts a doc job

```
Given a doc whose doc_type has no row in doc_type_guides and no per-doc instance guide,
  and a "_default" row exists in doc_type_guides
When a DocGenerationJob is created for that doc (DocService.create_doc_job)
Then job.guide_snapshot equals the "_default" guide's markdown (it is NOT None)
```

### AC2: Skill guidance no longer treats a null editorial snapshot as fatal

```
Given the iw-doc-generator and iw-doc-system SKILL.md "Job lifecycle" sections
When an agent reads the job context and finds section_guides_snapshot / guide_snapshot is null
Then the skill text explicitly instructs it to proceed using the static references/…-guidelines.md,
  and to abort with --error only when "iw doc-job-status" exits non-zero
```

### AC3: A failed doc job is visible on the Docs catalogue page

```
Given a DocGenerationJob that finished in status "failed" within the last ~10 minutes
When a user opens /project/<id>/docs (the catalogue page)
Then the running-jobs strip shows a persistent failed-job entry carrying the job's error,
  with a control to dismiss it,
  and a docJobFailed event on that page surfaces a toast/banner with the error
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing tests (#1, #2, #3 above) pass
```

## Regression Prevention

- `_effective_guide` gains an explicit `_default` fallback and a unit test pinning the three-level resolution order (instance → doc_type → `_default`). Any future caller of `_effective_guide` automatically benefits.
- The `iw-doc-generator` / `iw-doc-system` skills make the "null editorial snapshot is normal" rule explicit, removing the ambiguity that lets a model bail.
- `tests/dashboard/test_docs_running_jobs.py` gains coverage that the catalogue strip surfaces `failed` jobs, so a future regression that re-narrows the query to `running`-only is caught.
- The browser-verification step (S13) exercises the failed-job surfacing end-to-end against the isolated stack.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

```
orch/doc_service.py
skills/iw-doc-generator/SKILL.md
skills/iw-doc-system/SKILL.md
dashboard/routers/docs.py
dashboard/templates/docs_library.html
dashboard/templates/fragments/docs_running_jobs.html
tests/unit/test_doc_type_guide_service.py
tests/integration/test_doc_type_guides.py
tests/dashboard/test_docs_running_jobs.py
tests/integration/test_i00077_doc_job_editorial_fallback.py
```

## TDD Approach

- **Reproducing test**: `_effective_guide` returns the `_default` guide when no instance/`doc_type` guide exists (unit, `tests/unit/test_doc_type_guide_service.py`); `create_doc_job` snapshots that guide (integration, `tests/integration/test_doc_type_guides.py`); a `failed` `DocGenerationJob` appears in `GET .../api/docs/running-jobs` (dashboard, `tests/dashboard/test_docs_running_jobs.py`).
- **Unit tests**: resolution order instance → `doc_type` → `_default` (all three branches); `_default`-missing case still returns `None`.
- **Integration tests**: `create_doc_job` for a `diagram` doc snapshots a non-`None` `guide_snapshot`; (optionally) a `module` doc with an explicit instance guide still snapshots that instance guide unchanged (no regression).
- **Dashboard tests**: `docs_running_jobs` returns both `running` and recently-`failed` jobs; the rendered fragment marks failed rows distinctly and carries a dismiss control; the catalogue template includes a `docJobFailed` handler (assert on the rendered `docs_library.html` HTML / inline script — attribute-scoped, not bare substring).

**Assertion scoping for CSS class names** — when a regression test asserts a CSS class is present in rendered HTML, use the attribute-scoped form (`assert 'class="docs-rjob-failed"' in html` or a `class\s*=\s*"[^"]*…"` regex), not the bare-substring form, because the same token may appear inside an inline `<script>`'s JSON, a `data-*` attribute, or a comment even when the production element is absent (I-00067).

## Notes

- **Skill propagation (manual post-merge follow-up, NOT a workflow step):** edits to `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md` must also be propagated to the IW-AI-DEV and InnoForge repositories and re-synced (`iw sync-skills`) per project convention. This happens outside the worktree and is the operator's responsibility after merge.
- **Scope of fix #3:** "recently-failed jobs in the strip" is scoped to jobs whose `status == failed` and `completed_at` is within ~10 minutes, rendered as a dismissible red row (a `DELETE`/dismiss endpoint may already exist via `docs_job_cancel` for `running` jobs; if a separate "dismiss a finished failed row" endpoint is needed, keep it minimal — a client-side dismiss that just removes the row is acceptable). Do **not** redesign the running-jobs strip beyond what AC3 requires.
- Evidence for this incident: job `a56a296d-76be-41c4-a591-709ea12726ad` / DOC-00055 (doc `iw-ai-core:diagram-architecture`); agent log `ai-dev/logs/doc_job_a56a296d-76be-41c4-a591-709ea12726ad.log`. Prior occurrence: DOC-00050 (`module-dashboard`).
