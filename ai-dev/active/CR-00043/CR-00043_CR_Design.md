# CR-00043: Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers

**Type**: Change Request
**Priority**: Medium
**Reason**: Tech debt / robustness — I-00074 swapped WeasyPrint for a headless-Chromium PDF renderer whose binary path defaults to the host's Playwright cache (with only a single env override), so the PDF route 503s and Mermaid rendering loses its preferred engine inside the E2E container; the I-00074 browser-verification step could never exercise the real PDF happy path.
**Created**: 2026-05-10
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt. This CR *edits* `Dockerfile.e2e`, but does not run any `docker compose` lifecycle commands.)

## ⛔ Migrations: agents generate, daemon applies

This CR does not add, modify, or remove any database migrations.

## Description

I-00074 replaced WeasyPrint with `dashboard/utils/markdown.py::render_pdf_chromium()`, which shells out to a Chromium binary resolved from `$IW_PLAYWRIGHT_CHROME_PATH` if that env var is set, else a hardcoded default `Path.home() / ".cache" / "ms-playwright" / "chromium-1217" / "chrome-linux64" / "chrome"`. Neither is satisfied inside the isolated E2E container (`Dockerfile.e2e` ships only WeasyPrint's `libpango*` deps and no browser, and no env var is set), nor the per-worktree compose `app` container (raw `python:3.12-slim`). So the PDF route returns a clean `503` in any container, and Mermaid rendering loses `PUPPETEER_EXECUTABLE_PATH` (it still works via the Kroki fallback or puppeteer's own download, but the preferred path is dead). This CR generalizes the resolution — keeping the existing `IW_PLAYWRIGHT_CHROME_PATH` env var as the explicit override but adding a version-agnostic glob over the ms-playwright cache and a `PATH` lookup — and provisions a Chromium in the E2E image (`Dockerfile.e2e`) so the PDF happy path is actually reachable and testable in the browser-verification stack. (Provisioning Chromium in the per-worktree compose `app` container is left as a follow-up — that container runs as a non-root user, so an in-container `apt-get` won't work, and the per-worktree compose stack is not what browser verification runs against; see Notes.)

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Key points relevant to this CR:
- Dashboard: FastAPI + Jinja2; `dashboard/utils/markdown.py` does Mermaid→SVG (`mmdc` / Kroki fallback) and HTML→PDF (`render_pdf_chromium`).
- `Dockerfile.e2e` builds the image used by `browser_verification` steps' isolated stack (`scripts/e2e_up.sh` / `docker-compose.e2e.yml`) — that is the stack S15 verifies. The separate per-worktree compose `app` stack (`ai-dev/iw-config/worktree-compose.template.yml`, `image: python:3.12-slim`, runs as a non-root user) is **out of scope** for this CR — see Notes.
- In **production** the dashboard runs directly on the host, so this is purely a containerized-environment robustness fix; no production behavior changes.
- Append plain CSS to `dashboard/static/styles.css` if `make css` fails (Tailwind toolchain issue, see I-00067) — not expected to be needed here.

## Current Behavior

`dashboard/utils/markdown.py` defines, at module scope:

```python
_PLAYWRIGHT_CHROME = (
    Path(os.environ.get("IW_PLAYWRIGHT_CHROME_PATH", ""))
    if os.environ.get("IW_PLAYWRIGHT_CHROME_PATH")
    else Path.home() / ".cache" / "ms-playwright" / "chromium-1217" / "chrome-linux64" / "chrome"
)
```

So there *is* already an `IW_PLAYWRIGHT_CHROME_PATH` env override (added by I-00074, but referenced nowhere else in the repo), and its **default** still bakes in the literal `chromium-1217` version and assumes the host's ms-playwright cache layout. There is no glob over the cache and no `PATH` lookup.

- `render_pdf_chromium()` checks `_PLAYWRIGHT_CHROME.exists()`; if not, logs a warning and returns `None`. The three PDF routes in `dashboard/routers/docs.py` then return `503 {"error":"PDF generation unavailable", ...}`.
- `_render_mermaid_mmdc()` sets `env["PUPPETEER_EXECUTABLE_PATH"] = str(_PLAYWRIGHT_CHROME)` only `if _PLAYWRIGHT_CHROME.exists()`; otherwise it leaves puppeteer to find/download its own browser, and there's a Kroki.io fallback.

Inside the E2E container no env var is set and `Path.home()` is `/app`, so `_PLAYWRIGHT_CHROME` resolves to `/app/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`, which does not exist. `Dockerfile.e2e` installs `curl ca-certificates git libpango-1.0-0 libpangoft2-1.0-0` and nothing browser-related. The per-worktree `app` container is `python:3.12-slim` with no browser either. Net effect: PDF export 503s in every container; the I-00074 S13 browser-verification step had to be relaxed (2026-05-10) to accept the 503 as the expected graceful-degradation outcome because there was no way to exercise the real path.

## Desired Behavior

1. The Chromium binary is resolved by a small helper `_resolve_chromium_binary() -> Path | None` that tries, in order:
   1. `$IW_PLAYWRIGHT_CHROME_PATH` env var (the **existing** name — not renamed, not duplicated), if set and the path exists;
   2. the newest `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome` matched by glob (so the hardcoded `chromium-1217` version no longer matters for resolution);
   3. `shutil.which()` for `chromium`, `chromium-browser`, `google-chrome`, `google-chrome-stable`;
   4. otherwise `None`.
   The module exposes the resolved value (recomputed once at import; the env var is read at import time). `render_pdf_chromium()` and `_render_mermaid_mmdc()` both consult it. When `None`, the existing graceful-degradation behavior is unchanged (503 / Kroki fallback). A set-but-nonexistent `IW_PLAYWRIGHT_CHROME_PATH` falls through to the glob/`which` chain (today it would just be returned as a dead path).
2. `Dockerfile.e2e` installs a Chromium browser (`chromium` from Debian, plus the headless deps it needs) so that inside the E2E stack `shutil.which("chromium")` succeeds and the PDF route returns a real `%PDF`.
3. The I-00074 S13-style browser verification can now assert the **HTTP 200 + `%PDF`** happy path in the E2E stack (the relaxed "503 also acceptable" branch stays as a safety net but is no longer the only reachable outcome).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/utils/markdown.py` | `_PLAYWRIGHT_CHROME` = `IW_PLAYWRIGHT_CHROME_PATH` env var or a hardcoded `chromium-1217` host path; used as-is by PDF + mmdc | `_resolve_chromium_binary()` helper (`IW_PLAYWRIGHT_CHROME_PATH` → newest `chromium-*` glob → `which`); both call-sites consult it; graceful `None` path unchanged |
| `Dockerfile.e2e` | Installs only WeasyPrint's `libpango*` | Also installs `chromium` + its headless runtime deps |
| PDF export routes (`dashboard/routers/docs.py`) | 503 in any container | Real PDF in containers that now ship Chromium; **no code change** — behavior follows the resolver |

### Breaking Changes

None. The PDF route's public contract is unchanged (still 200 + PDF on success, 503 on unavailability). The `IW_PLAYWRIGHT_CHROME_PATH` env var keeps its meaning and remains optional; no new env var is introduced.

### Data Migration

- Not required.
- N/A — no schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `_resolve_chromium_binary()` to `dashboard/utils/markdown.py` (env `IW_PLAYWRIGHT_CHROME_PATH` → newest `chromium-*` glob → `which`); route `render_pdf_chromium()` + `_render_mermaid_mmdc()` through it; keep graceful `None` behavior | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | Provision a Chromium browser in `Dockerfile.e2e` (`apt-get install --no-install-recommends chromium` + minimal headless runtime libs) | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | Unit tests for the resolver (env override / glob picks newest / `which` fallback / none → graceful) | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Cross-agent global review: resolver correctness, image changes sane, AC trace | — |
| S08 | qv-gate (lint) | `make lint` | — |
| S09 | qv-gate (format) | `make format-check` | — |
| S10 | qv-gate (typecheck) | `make type-check` | — |
| S11 | qv-gate (arch-check) | `make arch-check` | — |
| S12 | qv-gate (security-sast) | `make security-sast` | — |
| S13 | qv-gate (unit-tests) | `make test-unit` | — |
| S14 | qv-gate (integration-tests) | `make test-integration` | — |
| S15 | qv-browser | Verify the PDF route returns a real `%PDF` in the E2E stack; no regressions on the doc page | — |
| S16 | self-assess-impl | Self-assessment (project has `self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None (the PDF routes' behavior follows the resolver — no code edit there)
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00043_CR_Design.md` | Design | This document |
| `CR-00043_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00043_S01_backend-impl_prompt.md` | Prompt | S01: Chromium resolver in markdown.py |
| `prompts/CR-00043_S02_CodeReview_prompt.md` | Prompt | S02: review S01 |
| `prompts/CR-00043_S03_backend-impl_prompt.md` | Prompt | S03: Chromium in the E2E image (`Dockerfile.e2e`) |
| `prompts/CR-00043_S04_CodeReview_prompt.md` | Prompt | S04: review S03 |
| `prompts/CR-00043_S05_tests-impl_prompt.md` | Prompt | S05: resolver unit tests |
| `prompts/CR-00043_S06_CodeReview_prompt.md` | Prompt | S06: review S05 |
| `prompts/CR-00043_S07_CodeReview_Final_prompt.md` | Prompt | S07: global review |
| `prompts/CR-00043_S15_BrowserVerification_prompt.md` | Prompt | S15: browser verification |
| `prompts/CR-00043_S16_SelfAssess_prompt.md` | Prompt | S16: self-assessment |
| `dashboard/utils/markdown.py` | Code | `_resolve_chromium_binary()` + call-site updates |
| `Dockerfile.e2e` | Build | Install `chromium` + headless deps |
| `tests/dashboard/test_markdown_chromium.py` | Test | New unit tests for the resolver |
| `tests/dashboard/test_docs_pdf_chromium.py` | Test | Existing — update if it asserts the old hardcoded path |

Reports are created during execution in `ai-dev/work/CR-00043/reports/`.

## Acceptance Criteria

### AC1: Env var override wins

```
Given IW_PLAYWRIGHT_CHROME_PATH points at an existing executable
When the dashboard resolves the Chromium binary
Then it uses that path (in preference to the ms-playwright cache or PATH lookup)
And a set-but-nonexistent IW_PLAYWRIGHT_CHROME_PATH is ignored (falls through to the next method)
```

### AC2: ms-playwright cache glob resolves regardless of version

```
Given no env override is set, and ~/.cache/ms-playwright contains chromium-1208 and chromium-1217 dirs with chrome-linux64/chrome
When the dashboard resolves the Chromium binary
Then it picks the newest chromium-* directory's chrome binary (the hardcoded "chromium-1217" string is no longer load-bearing)
```

### AC3: PATH fallback

```
Given no env override and no ms-playwright cache, but `chromium` (or chromium-browser / google-chrome / google-chrome-stable) is on PATH
When the dashboard resolves the Chromium binary
Then it uses the one found via shutil.which()
```

### AC4: Graceful degradation preserved

```
Given no Chromium can be resolved by any method
When a PDF route is called
Then it returns the existing 503 {"error":"PDF generation unavailable", ...} (no traceback, no 500), and Mermaid rendering falls back to its existing behavior
```

### AC5: PDF works in the E2E stack

```
Given the E2E stack built from this CR's Dockerfile.e2e
When the /pdf route is requested for a document with Mermaid diagrams
Then it returns HTTP 200 and a body beginning with the %PDF magic bytes
```

## Rollback Plan

- **Database**: N/A — no schema or data changes.
- **Code**: Revert the CR's squash commit. `dashboard/utils/markdown.py` returns to the env-var-or-hardcoded-`chromium-1217` constant; `Dockerfile.e2e` loses the Chromium install (next E2E stack rebuild reverts to the old image). No coordinated rollout needed — purely additive resolution logic plus image content.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: I-00074 (introduced `render_pdf_chromium()` and `_PLAYWRIGHT_CHROME`)
- **Blocks**: None

## Impacted Paths

- `dashboard/utils/markdown.py`
- `Dockerfile.e2e`
- `tests/dashboard/test_markdown_chromium.py`
- `tests/dashboard/test_docs_pdf_chromium.py`

## TDD Approach

- **Unit tests** (`tests/dashboard/test_markdown_chromium.py`): `_resolve_chromium_binary()` with `monkeypatch` over `os.environ`, a `tmp_path` fake `ms-playwright` tree, and `shutil.which` — assert the priority order (env > glob-newest > which > None) and that a non-existent env path is ignored rather than returned. Pure functions, no DB; if the resolver can't be tested without importing a router, extract it so it can (see `tests/CLAUDE.md` gotcha about importing `dashboard.routers.*` in unit tests — keep the resolver in `dashboard/utils/markdown.py`, which has no DB in its import chain).
- **Integration / dashboard tests**: update `tests/dashboard/test_docs_pdf_chromium.py` only if it currently asserts the literal hardcoded `chromium-1217` path; otherwise leave it (it mocks `render_pdf_chromium`).
- **Browser verification (S15)**: in the E2E stack (which now ships Chromium), open a doc with Mermaid diagrams, hit Download PDF, assert HTTP 200 + `%PDF`; plus a no-regressions pass on the doc HTML view.
- **Updated tests**: none beyond the optional `test_docs_pdf_chromium.py` tweak.

## Notes

- **Out of scope / follow-up — per-worktree compose `app` container**: `ai-dev/iw-config/worktree-compose.template.yml` runs the `app` service as `image: python:3.12-slim` under `user: "{{ host_uid }}:{{ host_gid }}"` (non-root), so an in-container `apt-get install chromium` from the startup `bash -lc` block can't work, and switching the service to `build:` from `Dockerfile.e2e` is a non-trivial restructure of a delicate file (F-00080 / F-00062 history). Crucially, browser verification (S15) runs against the `Dockerfile.e2e` / `docker-compose.e2e.yml` stack (`scripts/e2e_up.sh`), **not** the per-worktree compose stack — so the per-worktree container isn't on the test path for this CR. A clean fix there (build the `app` service from `Dockerfile.e2e`, or download a standalone Chromium into `/tmp` and point `IW_PLAYWRIGHT_CHROME_PATH` at it) is deferred to a follow-up.
- **Out of scope / follow-up — `chromium-1217` literal elsewhere**: the literal string `chromium-1217` still appears in other places (e.g. this codebase's `.playwright/` config and any docs); de-hardcoding it everywhere is a separate cleanup. This CR only removes its load-bearing role inside `dashboard/utils/markdown.py`'s resolution.
- **Image size**: `apt-get install -y chromium` on Debian slim adds roughly ~150 MB to the E2E image. Acceptable for a verification-only image; the implementer should use `--no-install-recommends` plus the minimal runtime libs Chromium needs (fonts, nss, etc.) rather than pulling the full recommends set.
- **`--no-sandbox`**: `render_pdf_chromium()` already passes `--no-sandbox --disable-setuid-sandbox` (required when running as a non-root user inside a container without user-namespace support), so no extra Chromium flags are needed.
- **Env var name — `IW_PLAYWRIGHT_CHROME_PATH` is kept, not renamed**: I-00074 already added `IW_PLAYWRIGHT_CHROME_PATH` as an override (it's referenced nowhere else in the repo). This CR keeps that exact name as resolution step 1 rather than introducing a parallel `IW_CORE_*` variant — one env var, not two. It stays read directly via `os.environ.get(...)` in `markdown.py` (not added to `orch/config.py`, which `markdown.py` must not import).
- Production is unaffected — the dashboard runs on the host where the ms-playwright cache exists; this CR only changes containerized behavior and the resolution mechanism.
