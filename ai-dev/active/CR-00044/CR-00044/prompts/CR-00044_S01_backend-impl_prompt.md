# CR-00044_S01_backend-impl_prompt

**Work Item**: CR-00044 — Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`, `docker system prune`, …). The orchestration DB, daemon, and dashboard containers are outside your scope — touching them causes multi-hour outages (see the 2026-04-22 incident in `docs/IW_AI_Core_DB_Setup.md`). Allowed: testcontainers spun up by pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does not touch alembic migrations. Do not run `alembic upgrade|downgrade|stamp` against any DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Runtime step state: `uv run iw item-status CR-00044 --json` (authoritative; `workflow-manifest.json` is a design-time snapshot).
- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` — design document (read it first, in full).
- `CLAUDE.md` and `dashboard/CLAUDE.md` — project conventions and hard rules.

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S01_backend-impl_report.md` — step report.

## Context

You are implementing the entire code change for CR-00044. There is no separate frontend step — the help fragments already render `href="{{ docs_link }}"` (shipped in CR-00042), so your changes are all in routers, `app.py`, the docs-view template wiring, `dashboard/CLAUDE.md`, plus the RED tests you write under TDD. Read the design document's **Desired Behavior**, **Acceptance Criteria**, and **Notes** sections carefully before writing anything.

## Requirements

### 1. `GET /favicon.ico` route (`dashboard/app.py`)

Register `GET /favicon.ico` directly on the app object, next to the existing `GET /health` route. It returns the bytes of `dashboard/static/favicon.svg` with media type `image/svg+xml` (use `fastapi.responses.FileResponse` with the resolved absolute path, or read the file and return a `Response`). If the file is somehow missing, returning a `204 No Content` is acceptable, but the SVG path exists today so the happy path is a 200 with the SVG. Satisfies **AC5**.

### 2. Subdirectory-capable docs viewer (`dashboard/routers/system.py`)

Replace `GET /docs/{doc_slug}` (currently `_DOCS_SLUG_RE = ^[A-Za-z0-9_]+$`, allow-list = stems of `docs/*.md`, reads `docs/{slug}.md`, title = `slug.replace("_"," ")`) with `GET /docs/{doc_path:path}`:

- **Allow-list / URL map**, computed once at module load — a `dict[str, str]` (`_DOC_URL_MAP`) mapping a *URL key* → a repo-relative POSIX path:
  - for every file under `docs/**/*.md` (recursive — `Path.rglob("*.md")`): URL key = the path **relative to `docs/`, with the `.md` suffix dropped** (`p.relative_to(_DOCS_DIR).with_suffix("").as_posix()`), value = the repo-relative path (`p.relative_to(_REPO_ROOT).as_posix()`). So `docs/IW_AI_Core_Daemon_Design.md` → key `IW_AI_Core_Daemon_Design` (this preserves every CR-00042 flat-form URL), `docs/implementation/00_INDEX.md` → key `implementation/00_INDEX`.
  - **plus** a small, explicit curated list of `**/CLAUDE.md` paths worth surfacing — at minimum `orch/rag/CLAUDE.md` (the `code` help link needs it). You MAY add other top-level `CLAUDE.md` files (`orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`) if you judge them useful — but do NOT bulk-add every `CLAUDE.md` in the tree; keep the list intentional and short. For each, URL key = value = its repo-relative POSIX path **including** the `.md` (e.g. key `orch/rag/CLAUDE.md` → value `orch/rag/CLAUDE.md`).
  - Also compute the set of allowed *base directories* — the repo's `docs/` dir, plus each curated `CLAUDE.md`'s parent dir — for the resolved-path defence-in-depth check below.
- **Validation** (in this order; any failure → `HTTPException(404, "Document not found")`):
  1. Reject if `doc_path` is empty, starts with `/`, or any of its `PurePosixPath(doc_path).parts` equals `..` or `.`.
  2. `mapped = _DOC_URL_MAP.get(doc_path)` — if `None`, 404. This dict-membership check is the real gate.
  3. Resolve the candidate filesystem path (`(_REPO_ROOT / mapped).resolve()`) and require it `is_relative_to` one of the allowed base directories (`Path.is_relative_to` is available on the project's Python). Defence-in-depth against symlink / `..` escapes.
  4. Require `candidate.suffix == ".md"` and `candidate.is_file()`.
- **Render**: read the file, `markdown(content, extensions=["toc", "tables", "fenced_code"])`, return `pages/system/docs_view.html` with the rendered HTML wrapped in `markupsafe.Markup` (as today).
- **Title**: derive `doc_title` from the document's first level-1 ATX heading (`# Heading` — the first line matching `^#\s+(.+)$` after stripping). Fall back to the file's basename without extension if there is no H1. Pass it under the same context key the template already uses (`doc_title`); if you must rename it, update `dashboard/templates/pages/system/docs_view.html` accordingly and list that file in `files_changed`. Satisfies **AC1, AC2, AC3, AC6**.
- Keep the existing `logger` usage and module structure; this is a focused edit, not a rewrite of `system.py`.

### 3. Retarget the generic help mappings (`dashboard/routers/help.py`)

In `_SLUG_TO_DOC`:

- `code` → `/system/docs/orch/rag/CLAUDE.md`
- `item_detail` → `/system/docs/IW_AI_Core_Dashboard_Design` (add a `#anchor` only if a stable heading id for the item-detail / item tabs section exists in the rendered output)
- `research` → `/system/docs/IW_AI_Core_Dashboard_Design` (same anchor caveat — the Research view section)
- `search` → `/system/docs/IW_AI_Core_Dashboard_Design` (same caveat — the FTS search section)
- `projects` → **unchanged** (`/system/docs/IW_AI_Core_Architecture` — genuinely the right doc)
- You MAY add `#anchor` fragments to other existing entries (e.g. `batches`, `worktrees`, `status`, `config`) where the target document has a stable `toc`-generated heading id. **Verify every anchor** by rendering the target doc through the markdown call (or hitting `/system/docs/<doc>` on a locally running dashboard) and confirming the `id="..."` exists. If you cannot confirm a stable id, ship the entry without a fragment. Do NOT invent anchors.
- Leave the unmapped-slug fallback as `/system/docs/IW_AI_Core_Architecture`.
- Do NOT externalise `_SLUG_TO_DOC` to a config file — that is explicitly out of scope.

Satisfies **AC4**.

### 4. Update `dashboard/CLAUDE.md`

In the routers table / docs-view note, update the description of the docs viewer route from the `{doc_slug}` form to the `{doc_path:path}` form, and mention it serves `docs/**/*.md` plus a curated set of `CLAUDE.md` files. One or two lines — keep it terse and consistent with the surrounding style.

## TDD Requirement

Follow Red-Green-Refactor. Write the failing tests **first** (they belong to S03's deliverable list, but you should drive your implementation with them — coordinate by writing the new assertions in `tests/dashboard/test_system_docs_route.py` and `tests/dashboard/test_help_router.py` and a favicon test, watch them fail, then implement). Do not skip the RED phase. If S03 later expands the test set, that's fine.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`: routers are thin; FastAPI + Jinja2; never invoke docker or alembic from dashboard code/tests; use the existing markdown utility patterns where applicable (`dashboard/utils/markdown.py` exists, but the docs-view route deliberately uses the plain `markdown` lib with the `toc` extension for heading anchors — keep that). Match existing code style in `system.py` / `help.py` / `app.py`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report on your touched files:

1. `make format` — auto-fixes drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Record each in the `preflight` object of your result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the tests that exercise your changes — NOT the full suite:

```bash
uv run pytest tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py -v
uv run pytest tests/dashboard/ -k favicon -v   # if you placed the favicon test there
```

Do NOT run `make test-integration` / `make test-unit` — those are downstream QV gates. Do not report `tests_passed: true` unless your targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00044",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/app.py", "dashboard/routers/system.py", "dashboard/routers/help.py", "dashboard/CLAUDE.md", "tests/dashboard/test_system_docs_route.py", "tests/dashboard/test_help_router.py", "..."],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "List which #anchors you added to _SLUG_TO_DOC and how you verified each; list the curated CLAUDE.md paths you allow-listed."
}
```
