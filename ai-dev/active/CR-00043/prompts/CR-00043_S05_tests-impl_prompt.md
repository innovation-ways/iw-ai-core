# CR-00043_S05_tests-impl_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S05
**Agent**: tests-impl

---

## Task

Write unit tests for the `_resolve_chromium_binary()` helper added in S01. Create `tests/dashboard/test_markdown_chromium.py`.

## Project Context

Read `tests/CLAUDE.md` and `ai-dev/active/CR-00043/CR-00043_CR_Design.md`. Key gotcha: `dashboard/utils/markdown.py` has a DB-free import chain — importing `_resolve_chromium_binary` directly is fine in a unit test. Do NOT import `dashboard.routers.*` / `dashboard.dependencies` (those load `SessionLocal` and the live-DB guard fires at collection time).

## Tests to write (`tests/dashboard/test_markdown_chromium.py`)

Use `monkeypatch` over `os.environ`, a `tmp_path`-rooted fake `ms-playwright` tree, and `monkeypatch.setattr` over `shutil.which` (and over `Path.home` where the resolver reads `~/.cache/...` — patch it to return `tmp_path`). Cover, at minimum:

1. **`test_env_override_wins`** — `IW_PLAYWRIGHT_CHROME_PATH` (the existing env-var name) set to an existing executable file; assert the resolver returns exactly that path, even when an `ms-playwright` cache and a `which("chromium")` result also exist.
2. **`test_env_override_nonexistent_is_ignored`** — `IW_PLAYWRIGHT_CHROME_PATH` set to a path that does not exist; assert the resolver falls through to the next method (does NOT return the bogus path).
3. **`test_ms_playwright_glob_picks_newest`** — no env override; `tmp_path/.cache/ms-playwright/` contains `chromium-1208/chrome-linux64/chrome` and `chromium-1217/chrome-linux64/chrome` (both real files); assert the resolver returns the `chromium-1217` one. (Add a `chromium-1212` with no `chrome-linux64/chrome` inside to confirm incomplete dirs are skipped.)
4. **`test_path_lookup_fallback`** — no env override, no `ms-playwright` cache; `shutil.which` returns a path for `"chromium"` (or one of the other names); assert the resolver returns it. Also assert it tries the names in order (`chromium` before `chromium-browser` before `google-chrome` before `google-chrome-stable`).
5. **`test_none_when_nothing_found`** — no env, no cache, `shutil.which` returns `None` for all names; assert the resolver returns `None`.
6. **`test_render_pdf_chromium_returns_none_when_unresolved`** — with the resolver patched/forced to `None` (or `_PLAYWRIGHT_CHROME` set to `None`), call `render_pdf_chromium("<h1>x</h1>")` and assert it returns `None` and does not raise (graceful degradation — AC4).

Keep tests fast, no DB, no real subprocess (don't actually launch Chromium). If `_resolve_chromium_binary` recomputes only at import time and you need to re-evaluate it per-test, either call the function directly (preferred — it should be callable with the env/filesystem patched) or `importlib.reload(dashboard.utils.markdown)` *carefully* after patching (note `tests/CLAUDE.md`'s warning is specifically about reloading `orch.config`, not `dashboard.utils.markdown`, but prefer calling the function directly).

## Also

- If `tests/dashboard/test_docs_pdf_chromium.py` currently asserts the literal hardcoded `chromium-1217` path string (or otherwise breaks because `_PLAYWRIGHT_CHROME` is now `Path | None`), update the affected assertion(s) to match the new resolver. Otherwise leave the file alone — it mocks `render_pdf_chromium` / monkeypatches the module attr and should keep passing.
- **Test verification — targeted only**: run `uv run pytest tests/dashboard/test_markdown_chromium.py tests/dashboard/test_docs_pdf_chromium.py -q` (the new/affected files only — do NOT run `make test-unit` or `make test-integration`; the full suites are owned by the downstream QV gates). Also run `make lint`, `make format-check`, `make type-check` on your changes before finishing.

## Output

Report the test names you added, the coverage of AC1–AC4, and the test-run result.

**Do NOT** call `iw step-done` / `iw step-fail`.
