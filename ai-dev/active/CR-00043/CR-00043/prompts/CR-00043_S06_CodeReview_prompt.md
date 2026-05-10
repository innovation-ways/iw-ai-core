# CR-00043_S06_CodeReview_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S06
**Agent**: code-review-impl

---

## Task

Review the S05 tests (`tests/dashboard/test_markdown_chromium.py`, plus any change to `tests/dashboard/test_docs_pdf_chromium.py`).

## Source of truth

Read `ai-dev/active/CR-00043/CR-00043_CR_Design.md`.

## Review checklist

- Tests cover the full resolution priority and edge cases: env-override-wins, env-path-nonexistent-ignored, ms-playwright-glob-picks-newest (and skips incomplete dirs), PATH-lookup-fallback (and the name order), none-when-nothing-found, and `render_pdf_chromium()` returns `None` gracefully when unresolved (AC1–AC4).
- Isolation: every test patches `os.environ` / `Path.home` / `shutil.which` (and a `tmp_path` fake cache) — no test reads the real host's `~/.cache/ms-playwright` or `/usr/bin/chromium`, and none launches a real Chromium subprocess.
- No `dashboard.routers.*` / `dashboard.dependencies` import at module level (would trip the live-DB guard at collection time — see `tests/CLAUDE.md`).
- No `importlib.reload(orch.config)`; if `dashboard.utils.markdown` is reloaded it's done deliberately and cleaned up — but calling `_resolve_chromium_binary()` directly is preferred.
- Assertions are semantic (assert the returned path / `None`), not just "doesn't crash".
- The targeted run passes — `uv run pytest tests/dashboard/test_markdown_chromium.py tests/dashboard/test_docs_pdf_chromium.py -q` — and `make lint`, `make format-check`, `make type-check` are clean. (Full-suite execution is the downstream QV gates' job; the review need not run `make test-unit`/`make test-integration`.)

## Output

Review report with severities and `mandatory_fix_count`. Missing coverage of a stated AC is at least HIGH; a test that touches the real host filesystem/binaries or imports a DB-bound module is CRITICAL.

**Do NOT** call `iw step-done` / `iw step-fail`.
