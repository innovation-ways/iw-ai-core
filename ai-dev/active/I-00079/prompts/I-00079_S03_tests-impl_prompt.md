# I-00079_S03_tests-impl_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00079 --json`.
- `ai-dev/active/I-00079/I-00079_Issue_Design.md` — design document (read `## Test to Reproduce`, `## Acceptance Criteria`, `## TDD Approach` in full)
- `ai-dev/active/I-00079/reports/I-00079_S01_frontend-impl_report.md` — what S01 changed (the exact new `primary_href` values, any seed test it added)
- `tests/dashboard/test_empty_states.py` — **the file you extend.** It already renders all six empty-state pages: `/project/{test_project.id}/queue`, `/batches`, `/history`, `/research`, `/docs`, and `/system/all-active`, asserting the empty-state *markers* (`data-empty-state`, `<h3>`, `<p>`, `class="empty-state__cta-primary"`). It does NOT follow `primary_href` — that's the gap that let this bug ship.
- `tests/dashboard/conftest.py` — the `client` fixture and `test_project` fixture (registered only under `tests/dashboard/`)
- `dashboard/templates/macros/empty_state.html` — the macro emits `<a href="{{ primary_href }}" class="empty-state__cta-primary">{{ primary_label }}</a>` — `href` first, then `class`
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` map (the canonical correct targets, for the AC3 consistency test)
- `tests/CLAUDE.md`, `dashboard/CLAUDE.md`, `CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S03_tests-impl_report.md` — step report
- `tests/dashboard/test_empty_states.py` — extended with the reproduction + regression tests (S01 may have seeded a minimal version)

## Context

Pre-S01, every empty-state panel's primary CTA pointed at `/docs/<DocName>.md` — a path that matches no FastAPI route, so `GET` returns `{"detail":"Not Found"}` (HTTP 404). S01 changed all six to `/system/docs/<DocName>` (the dashboard's doc-viewer route). Your tests must FAIL against the pre-fix templates (GET on the old href → 404) and PASS against the current (fixed) code.

**Test-file location** — extend `tests/dashboard/test_empty_states.py`. It renders `base.html`-extending pages via the `client` fixture, which lives only in `tests/dashboard/conftest.py`; a test placed under `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found` (I-00067).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed — but the bug was NOT fixed. The *existing* `test_empty_states.py` is exactly this failure mode: it asserts the `empty-state__cta-primary` link *element exists* but never checks where it points. Your new tests must verify the **specific target** and that it **resolves**:

- BAD: `assert 'empty-state__cta-primary' in html` (the element always existed — the bug was the href value)
- BAD: `assert 'IW_AI_Core_CLI_Spec' in html` (the doc name appears in the help-popover link too; doesn't prove the *CTA* is right, or that it resolves)
- GOOD: extract the `empty-state__cta-primary` href specifically, assert `not href.startswith("/docs/")` and `".md" not in href.split("#")[0]` (the broken pattern is gone)
- GOOD: `assert client.get(href.split("#")[0]).status_code == 200` (the link actually resolves)
- GOOD: `assert href.startswith("/system/docs/IW_AI_Core_CLI_Spec")` for the queue page (the *specific* expected destination, not "some 200")

## Requirements — tests to write (cover every AC)

Add to `tests/dashboard/test_empty_states.py`. Keep the existing marker tests; add the following. A clean way to structure this: a small helper that extracts the CTA href(s) and a per-page test (or a parametrized test) over the six pages.

1. **`_primary_cta_hrefs(html)` helper** — return every empty-state primary CTA href, attribute-scoped, e.g.
   `re.findall(r'<a\s+href="([^"]+)"\s+class="empty-state__cta-primary"', html)`.
   (Confirm the macro's attribute order against `dashboard/templates/macros/empty_state.html` and adjust the regex if S01 or a prior change reordered them — but `href` then `class` is current.)

2. **`test_i00079_queue_empty_state_cta_resolves(client, test_project)`** — `GET /project/{test_project.id}/queue` → 200; for each CTA href returned by the helper (there are two empty-state blocks on this page — both must be checked): assert `not href.startswith("/docs/")`, assert `".md" not in href.split("#")[0]`, assert `client.get(href.split("#")[0]).status_code == 200`; and assert at least one href `startswith("/system/docs/IW_AI_Core_CLI_Spec")`. (AC1, AC2)

3. **`test_i00079_history_empty_state_cta_resolves(client, test_project)`** — `GET /project/{test_project.id}/history` → 200; same per-href checks; assert the CTA href `startswith("/system/docs/IW_AI_Core_Architecture")`. (AC1, AC2)

4. **`test_i00079_batches_empty_state_cta_resolves(client, test_project)`** — `GET /project/{test_project.id}/batches` → 200; same per-href checks; assert the CTA href `startswith("/system/docs/IW_AI_Core_Daemon_Design")` (anchor `#batches` may follow). (AC1, AC2)

5. **`test_i00079_all_active_empty_state_cta_resolves(client)`** — `GET /system/all-active` → 200; same per-href checks; assert the CTA href `startswith("/system/docs/IW_AI_Core_Daemon_Design")`. (AC1, AC2)

6. **`test_i00079_docs_library_empty_state_cta_resolves(client, test_project)`** — `GET /project/{test_project.id}/docs` → 200 (with no docs the empty state renders); same per-href checks; assert the CTA href `startswith("/system/docs/implementation/00_INDEX")`. This one exercises CR-00044's subdirectory doc serving — if `client.get("/system/docs/implementation/00_INDEX").status_code` is not 200, that's a real finding (report it as a blocker — do NOT weaken the assertion). (AC1, AC2)

7. **`test_i00079_research_library_empty_state_cta_resolves(client, test_project)`** — `GET /project/{test_project.id}/research` → 200; same per-href checks; assert the CTA href `startswith("/system/docs/implementation/00_INDEX")`. (AC1, AC2)

8. **`test_i00079_no_legacy_docs_md_links_in_templates()`** — pure file scan, no fixture. Walk `dashboard/templates/**/*.html`, read each with `encoding="utf-8"`, and assert no file contains the substring `primary_href="/docs/` and no file contains a regex match for `"/docs/[A-Za-z0-9_./-]*\.md` (a `/docs/...md` link target). This is the structural guard against the whole class of bug recurring. (AC2, Regression Prevention)

9. **`test_i00079_empty_state_cta_agrees_with_help_doc_map(client, test_project)`** — for the pages that have both an empty-state CTA and a help slug (`queue`, `history`, `batches`, `all_active`), import `_SLUG_TO_DOC` from `dashboard.routers.help` and assert the empty-state CTA's path component (href before any `#`) is one of: exactly `_SLUG_TO_DOC[slug]`'s path component, OR a deliberate documented divergence — specifically `queue` must match exactly (`/system/docs/IW_AI_Core_CLI_Spec`), while `history` is intentionally `/system/docs/IW_AI_Core_Architecture` (the design records this — see the design doc's *Code Changes* note and AC3). The point is: both surfaces point at a real, related `/system/docs/...` doc; neither carries a `.md` suffix or a bare `/docs/` prefix. If you'd rather not encode the `history` exception, at minimum assert for every one of those four pages that the CTA path `startswith("/system/docs/")` and the corresponding `_SLUG_TO_DOC[slug]` also `startswith("/system/docs/")` — that still catches drift. (AC3)

If S01 used slightly different target strings than the design's, follow what S01 actually shipped — but every *semantic* invariant above (resolves to 200; no `/docs/*.md`; specific expected doc per page; no legacy links anywhere in templates) is mandatory. Do not weaken a check to "make it pass" — if a check genuinely can't pass against the current code, that's a real finding: report it as a blocker rather than deleting the assertion.

## Project Conventions

Read `tests/CLAUDE.md`: no live DB (port 5433) in tests; the `client` / `test_project` fixtures come from `tests/dashboard/conftest.py`; testcontainers only for DB-backed tests (not needed here). Match the style of the existing tests in `tests/dashboard/test_empty_states.py`. Use `encoding="utf-8"` when reading template files.

## TDD Requirement

These tests are the RED→GREEN proof for I-00079. They must fail against the pre-S01 templates (the CTA href was `/docs/<name>.md`, so `client.get(...)` returns 404, and the no-legacy-links scan finds the `/docs/*.md` strings) and pass now. You do **not** need to revert source files to "prove RED" — that was done at design time. Just write tests whose assertions clearly target the pre-fix conditions described above.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in the test file you wrote:

1. `make format`
2. `make typecheck` (likely a no-op for a test file; note pre-existing errors)
3. `make lint`

Record results in `preflight`.

## Test Verification (NON-NEGOTIABLE)

Run **only** the test file you touched — do NOT run `make test-integration` or `make test-unit` (those are downstream QV gates S09/S10; running them here burns the step budget — see I-00073/S03 post-mortem):

```bash
uv run pytest tests/dashboard/test_empty_states.py -v
```

All assertions must pass with zero failures. Do not report `tests_passed: true` otherwise.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_empty_states.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
