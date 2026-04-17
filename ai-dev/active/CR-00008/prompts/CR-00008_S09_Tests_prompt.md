# CR-00008 S09 — Tests: SSE wire format, templates, a11y, security, browser smoke

**Work Item**: CR-00008
**Step**: S09
**Agent**: tests-impl

---

## Input Files (read first)

- `CLAUDE.md`, `tests/CLAUDE.md` — testing conventions, fixtures, `testcontainers` rules
- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` — AC1…AC15
- All prompts and reports from S01, S03, S05, S07
- All source files modified/created by those steps
- `tests/conftest.py` — existing fixtures

## Output Files

- **New**: `tests/dashboard/test_code_qa_sse_wire.py` (may already exist from S01 — extend it)
- **New**: `tests/dashboard/test_chat_templates.py`
- **New**: `tests/dashboard/test_chat_a11y.py`
- **New**: `tests/dashboard/test_chat_security.py`
- **New**: `tests/dashboard/browser/test_chat_smoke.py` (Playwright)
- **New report**: `ai-dev/active/CR-00008/reports/CR-00008_S09_Tests_report.md`

## Scope

This step **consolidates** and **extends** testing across S01/S03/S05/S07. Prior impl steps wrote scoped tests; S09 adds cross-cutting coverage and a single Playwright end-to-end smoke.

## Tasks

### Task 1 — SSE wire-format tests (extend)

Ensure `tests/dashboard/test_code_qa_sse_wire.py` covers:

1. `test_token_event_newline_in_payload` — token containing `\n\n` survives base64 round-trip without corrupting SSE framing.
2. `test_utf8_multibyte_token_roundtrip` — tokens containing emoji / CJK characters decode back to identical UTF-8.
3. `test_cumulative_citations_deduplicated_by_n` — emitting the same citation twice yields one `event: citation` frame; `n` values strictly increase.
4. `test_done_event_has_ok_true`.
5. `test_error_event_on_upstream_connection_refused` — generator exits after emitting exactly one error event.
6. `test_image_attachment_returns_501_with_detail`.
7. `test_response_headers_preserved` — `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`.

Mock `QAEngine.answer_stream` — no Ollama / network.

### Task 2 — Template render tests

`tests/dashboard/test_chat_templates.py`:

1. `test_panel_has_log_role_and_aria_live_polite` — `dashboard/templates/chat/panel.html` renders with `role="log"` on the message container and `aria-live="polite" aria-relevant="additions"`.
2. `test_panel_aria_region_labelled` — panel has `role="region"` with a non-empty `aria-label`.
3. `test_composer_image_picker_restricts_mime` — `accept` attribute on the file input contains `image/png,image/jpeg,image/gif,image/webp` (any order).
4. `test_message_includes_actions_only_for_assistant` — `data-role="user"` does NOT include `actions.html`; `data-role="assistant"` does.
5. `test_code_block_partial_has_language_label_and_copy_button` — `parts/code.html` renders a language label slot and a `<button>` with an accessible name containing "Copy".
6. `test_sources_panel_collapsed_by_default` — `<details>` without `open` attribute.
7. `test_mermaid_error_chip_has_retry_button` — `parts/mermaid.html` renders a Retry button with non-empty `aria-label`.

Render via Jinja directly (`jinja2.Environment` with the `dashboard/templates/` loader), NOT via the full FastAPI app — keeps tests fast.

### Task 3 — Accessibility assertions

`tests/dashboard/test_chat_a11y.py`:

1. `test_all_buttons_have_accessible_name` — parse each of `chat/panel.html`, `chat/composer.html`, `chat/message.html`, and `chat/parts/*.html`; assert every `<button>` has a non-empty text content OR `aria-label` OR `aria-labelledby`.
2. `test_no_div_onclick` — no `<div` or `<span` element in those templates has an `onclick=` attribute.
3. `test_buttons_have_hit_target_classes` — every `<button>` has one of `min-h-[44px]`, `h-11`, `tap` (via class attribute) OR the class is defined in `chat.css` with the equivalent. Parse the rendered HTML as BeautifulSoup and check the class attribute.
4. `test_images_have_alt` — any `<img>` in rendered templates has a non-empty `alt`.

Use `beautifulsoup4` (already in dev deps per `pyproject.toml`; if not, justify).

### Task 4 — Security tests

`tests/dashboard/test_chat_security.py` (Python-side only — DOM-level JS XSS is covered by the Playwright smoke in Task 5):

1. `test_no_cdn_references_in_base_html` — grep `dashboard/templates/base.html`; no `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `unpkg.com`.
2. `test_no_marked_references_remain` — no `marked` or `marked.min.js` in templates.
3. `test_vendored_license_files_exist` — for each subdirectory under `dashboard/static/vendor/`, assert a `LICENSE` or `LICENSE.md` file exists. Assert `LICENSES.md` index exists at the vendor root.
4. `test_vendored_licenses_index_entries` — parse `LICENSES.md`; for each vendored folder, ensure the index lists an SPDX ID (must be one of `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `MPL-2.0`, `EPL-2.0`, `CC-BY-*`). No `GPL*` accepted.
5. `test_stale_code_qa_fragment_deleted` — assert `dashboard/templates/fragments/code_qa_panel.html` no longer exists.
6. `test_code_qa_route_registered` — create the app via `dashboard.app.create_app()` and assert `POST /api/projects/{project_id}/code/qa` (and the 501 multipart variant path, if implemented distinctly) are registered. This absorbs the route-smoke gate that was previously a standalone QV check.

### Task 5 — Playwright browser smoke

`tests/dashboard/browser/test_chat_smoke.py` (mark with `pytest.mark.browser`):

Starts the dashboard in-process via Uvicorn + TestClient or a local fixture; drives Playwright against it. Covers the end-to-end golden path:

1. Navigate to `/project/iw-ai-core/code`.
2. Assert `<aside id="chat-panel">` visible.
3. Press `Control+\`; assert `[data-collapsed="true"]`. Press again; restores.
4. Type `/ex`; assert slash menu lists `/explain`.
5. Send a stubbed request (mock the SSE endpoint via a local test route that emits a fixed event sequence: 3 tokens, 1 citation, done).
6. Assert the rendered message contains at least one citation chip and a copy button on a code block if the stub contained one.
7. Assert no console errors on the page.

If the in-process server fixture is tricky, use an existing test harness pattern from the repo (check `tests/CLAUDE.md` for the established approach).

### Task 6 — Update any existing tests broken by the rewrite

Scan for tests that assert the old `{"token": "..."}` JSON format on `/api/projects/*/code/qa` or that target the old `#qa-panel` DOM id. Update them to the new format / selectors.

## Hard rules (from `CLAUDE.md`)

- **NEVER** connect tests to the live DB (port 5433) — use testcontainers only.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **NEVER** mock the database in integration tests (but DB is out of scope here).
- Replace psycopg2 URLs in any container setup: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run ruff check tests/
uv run pytest tests/dashboard/ -v
# browser tests marked with @pytest.mark.browser, run locally:
uv run pytest tests/dashboard/browser/ -m browser -v
```

All must be zero-failure.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "files_changed": [...],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "State whether browser smoke ran in CI or only locally."
}
```
