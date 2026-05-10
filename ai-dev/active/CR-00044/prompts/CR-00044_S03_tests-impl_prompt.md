# CR-00044_S03_tests-impl_prompt

**Work Item**: CR-00044 — Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed: testcontainers via pytest fixtures, read-only `docker ps|inspect|logs`, `./ai-core.sh` / `make` targets. Dashboard tests use `TestClient` — they never touch docker. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches no migrations. Do not run `alembic upgrade|downgrade|stamp`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Runtime step state: `uv run iw item-status CR-00044 --json`.
- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` — design document (read `## TDD Approach` and `## Acceptance Criteria` in full).
- `ai-dev/active/CR-00044/reports/CR-00044_S01_backend-impl_report.md` — S01 report.
- Existing tests: `tests/dashboard/test_system_docs_route.py`, `tests/dashboard/test_help_router.py`, plus `tests/CLAUDE.md` and `tests/conftest.py` for fixture conventions.

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S03_tests-impl_report.md` — step report.

## Context

S01 implemented the favicon route, the `{doc_path:path}` docs viewer, the `_SLUG_TO_DOC` retargeting, and the H1 title. S01 should already have written RED tests; your job is to make the test coverage complete and correct for AC1–AC6. Use the existing dashboard test patterns (`TestClient`, no live DB, no docker).

## Requirements — tests to add / update

### `tests/dashboard/test_system_docs_route.py` (extend)

- `GET /system/docs/orch/rag/CLAUDE.md` → 200; body contains a heading that appears in `orch/rag/CLAUDE.md`. (AC1)
- `GET /system/docs/implementation/00_INDEX` → 200; body contains content from `docs/implementation/00_INDEX.md`. (AC1)
- `GET /system/docs/IW_AI_Core_Daemon_Design` → 200; body contains content from `docs/IW_AI_Core_Daemon_Design.md` (regression guard — the flat form still works). (AC2)
- Traversal / rejection cases, each → 404 with no file content in the body:
  - `GET /system/docs/../etc/passwd`
  - `GET /system/docs/..%2f..%2fREADME`
  - `GET /system/docs/docs/../../orch/config.py` (non-`.md`)
  - `GET /system/docs/orch/config.py` (real file, not `.md`, not allow-listed)
  - `GET /system/docs/some/unknown/doc` (allow-list miss)
  - `GET /system/docs/` and `GET /system/docs/%2fetc%2fpasswd` (empty / leading slash) — accept 404 or 405/redirect as appropriate to the route shape, but never a 200 leaking a file.
  (AC3)
- `<title>` (or the rendered title element) of `GET /system/docs/implementation/00_INDEX` reflects that file's first `# H1`, not the literal `"implementation/00 INDEX"`. (AC6)

### Favicon test (`tests/dashboard/test_favicon.py`, new — or add to an existing dashboard test module)

- `GET /favicon.ico` → 200; `content-type` starts with `image/svg+xml`; response body equals the bytes of `dashboard/static/favicon.svg`. (AC5)

### `tests/dashboard/test_help_router.py` (update)

- `GET /_help/code` → rendered fragment whose "Open full docs" link `href` is `/system/docs/orch/rag/CLAUDE.md` (optionally followed by `#fragment`).
- `GET /_help/item_detail`, `/_help/research`, `/_help/search` → `href` points at `/system/docs/IW_AI_Core_Dashboard_Design` (optionally `#fragment`).
- `GET /_help/projects` → `href` is `/system/docs/IW_AI_Core_Architecture`.
- For every help slug, the rendered fragment contains a `help-content__docs-link` whose `href` starts with `/system/docs/` — and **no** rendered fragment contains a hardcoded `/docs/IW_AI_Core` or `/orch/...` href (regression guard inherited from CR-00042; note `/system/docs/orch/rag/CLAUDE.md` legitimately contains the substring `orch/` — assert on the full prefix `/system/docs/`, not a naive `orch/` substring search).
- **Anchor-pinning (required).** For every entry in `_SLUG_TO_DOC` whose value contains a `#fragment` (after S01 ran — whatever fragments actually shipped), request the target `/system/docs/<doc-path>` and assert the rendered HTML contains `id="<fragment>"`. Iterate over `_SLUG_TO_DOC` programmatically so the test pins **every** shipped anchor, including pre-existing ones like `queue` → `#iw-approve`. (This is AC4's "every `#anchor` … matches a heading id in the rendered target document" clause — it must have a covering test, not be left implicit.)

## ⚠️ Semantic Correctness Warning (I-00003 lesson)

Tests MUST verify **specific values**, not just shape. Shape-only assertions
let a buggy implementation pass — and the I-00003 post-mortem traced a
production regression directly to this anti-pattern. Apply this rule to every
assertion in this step:

- ❌ **BAD (status-only)**: `assert resp.status_code == 200`
- ✅ **GOOD (status + content)**: `assert resp.status_code == 200 and "Code Understanding" in resp.text` (a heading that genuinely appears in `orch/rag/CLAUDE.md`)
- ❌ **BAD (presence-only)**: `assert "/system/docs/" in href`
- ✅ **GOOD (value-checked)**: `assert href == "/system/docs/orch/rag/CLAUDE.md"` (or `href.split("#", 1)[0] == "/system/docs/orch/rag/CLAUDE.md"` when an anchor is allowed)
- ❌ **BAD (just a 404)**: `assert resp.status_code == 404`
- ✅ **GOOD (404 + no leak)**: `assert resp.status_code == 404 and "root:" not in resp.text and "PATH" not in resp.text` — prove the attacked file's bytes did not reach the body

For the title-from-H1 test, assert the **exact** expected title string (the H1
text of `docs/implementation/00_INDEX.md`), and additionally assert the literal
path-derived string (`"implementation/00 INDEX"`) is **absent** — a test that
only checks "title is non-empty" passes against the buggy old behaviour.

If a test asserts only a status code or only that a key/substring is present
without checking its value, S04's review will flag it as HIGH and burn a
fix-cycle. Don't.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the files you wrote/modified:

```bash
uv run pytest tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py tests/dashboard/test_favicon.py -v
```

Do NOT run `make test-integration` or `make test-unit` — those are downstream QV gates. Do not report `tests_passed: true` unless these pass with zero failures.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, then `make typecheck`, then `make lint` — on your touched files. Record each in the `preflight` object.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "CR-00044",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_system_docs_route.py", "tests/dashboard/test_help_router.py", "tests/dashboard/test_favicon.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
