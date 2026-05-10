# CR-00043_S07_CodeReview_Final_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S07
**Agent**: code-review-final-impl

---

## Task

Final cross-agent review of all CR-00043 work (S01 markdown.py resolver, S03 image provisioning, S05 tests). Confirm the pieces fit and every acceptance criterion is met.

## Source of truth

`ai-dev/active/CR-00043/CR-00043_CR_Design.md` — read it first, then trace AC1–AC5 through the actual code.

## Cross-cutting checks

1. **End-to-end consistency**: the resolver in `markdown.py` looks for `shutil.which("chromium")`; `Dockerfile.e2e` installs `chromium` at `/usr/bin/chromium` → the two line up so the PDF route returns a real `%PDF` in the E2E stack that S15 verifies (AC5). (The per-worktree compose `app` container is deliberately out of scope — see the design Notes; S03 must not have touched `worktree-compose.template.yml`.)
2. **Graceful degradation intact** (AC4): with no env var, no ms-playwright cache, and no `chromium` on PATH, `render_pdf_chromium()` returns `None` (callers 503) and mmdc omits `PUPPETEER_EXECUTABLE_PATH` (Kroki fallback unaffected). `dashboard/routers/docs.py` is untouched.
3. **Priority order** (AC1–AC3): `IW_PLAYWRIGHT_CHROME_PATH` (existing env-var name, only if the path exists) > newest `chromium-*` glob > `which` chain > `None`; a set-but-missing env path is ignored; no new env var was introduced. Tests assert all of this.
4. **Scope**: only `dashboard/utils/markdown.py`, `Dockerfile.e2e`, `tests/dashboard/test_markdown_chromium.py` (new), and possibly `tests/dashboard/test_docs_pdf_chromium.py` were modified — nothing outside `workflow-manifest.json:scope.allowed_paths` (in particular, `worktree-compose.template.yml` was NOT modified).
5. **No DB-import contamination** of `markdown.py`; **no docker lifecycle commands** anywhere.
6. **Hygiene**: image install is `--no-install-recommends` + cleaned in the same layer; no new high-severity Dockerfile scan findings; lint/format/typecheck/arch-check all clean.
7. **Production unaffected**: nothing changes for the host-run dashboard.

## Output

Final review report: AC1–AC5 trace table, any residual findings with severities, `mandatory_fix_count`, and an overall PASS/FAIL recommendation.

**Do NOT** call `iw step-done` / `iw step-fail`.
