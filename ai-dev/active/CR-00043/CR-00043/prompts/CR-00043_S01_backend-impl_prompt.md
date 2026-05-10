# CR-00043_S01_backend-impl_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S01
**Agent**: backend-impl

---

## Task

Generalize the Chromium-binary resolution in `dashboard/utils/markdown.py` into a small resolver, and route the two consumers through it. **Keep the existing `IW_PLAYWRIGHT_CHROME_PATH` env-var name — do not introduce a new one.** **No behavior change when no browser is found** — the existing graceful degradation (PDF route 503, Mermaid Kroki/puppeteer fallback) must be preserved exactly.

## Project Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md` first. Also read `ai-dev/active/CR-00043/CR-00043_CR_Design.md` — it is the authoritative spec; if anything in this prompt conflicts with the design doc, the design doc wins.

## Current state

In `dashboard/utils/markdown.py` (module scope) — note there is **already** an `IW_PLAYWRIGHT_CHROME_PATH` env override; it is referenced nowhere else in the repo, and you are keeping that exact name:

```python
# Path to the Playwright-managed Chromium binary used by mmdc
_PLAYWRIGHT_CHROME = (
    Path(os.environ.get("IW_PLAYWRIGHT_CHROME_PATH", ""))
    if os.environ.get("IW_PLAYWRIGHT_CHROME_PATH")
    else Path.home() / ".cache" / "ms-playwright" / "chromium-1217" / "chrome-linux64" / "chrome"
)
```

- `render_pdf_chromium()` does `if not _PLAYWRIGHT_CHROME.exists(): ... return None`, else runs it with `--headless --disable-gpu --no-sandbox --disable-setuid-sandbox --print-to-pdf=...`.
- `_render_mermaid_mmdc()` does `if _PLAYWRIGHT_CHROME.exists(): env["PUPPETEER_EXECUTABLE_PATH"] = str(_PLAYWRIGHT_CHROME)`.
- `os` is already imported. The current code does **not** distinguish a set-but-nonexistent `IW_PLAYWRIGHT_CHROME_PATH` from an unset one (it just returns whatever path it built and lets `.exists()` fail later); the resolver below should instead *fall through* to the glob / `which` chain in that case.

## What to implement

1. Add a module-level helper:

   ```python
   def _resolve_chromium_binary() -> Path | None:
       """Locate a Chromium/Chrome executable for headless PDF + mmdc rendering.

       Resolution order:
         1. $IW_PLAYWRIGHT_CHROME_PATH, if set and the path exists. (This is
            the existing override env var — keep the name; do NOT add a new one.)
         2. The newest ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome
            (so the bundled-browser version number is not load-bearing here).
         3. shutil.which("chromium" | "chromium-browser" | "google-chrome" |
            "google-chrome-stable").
         4. None — callers must degrade gracefully (PDF route -> 503, mmdc ->
            puppeteer/Kroki fallback), exactly as today.
       """
   ```
   - "Newest" = of the matched `chromium-*` dirs, pick the one with the highest numeric suffix; a lexical sort of the matched paths is acceptable as long as Playwright build numbers stay the same width (`chromium-1208` < `chromium-1217`) — if you want to be extra safe, sort by `int(name.removeprefix("chromium-"))` with a fallback for any non-numeric suffix. Only return a candidate whose `chrome` file actually `exists()`; an incomplete `chromium-*` dir (no `chrome-linux64/chrome` inside) is skipped.
   - Read the env var with `os.environ.get(...)` (no new dependency, no `orch.config` import — `dashboard/utils/markdown.py` must stay free of any DB-import chain; see `tests/CLAUDE.md`). A set-but-nonexistent `IW_PLAYWRIGHT_CHROME_PATH` must NOT be returned — fall through to steps 2–4.
   - Use `shutil.which` (add the `import shutil` if not present — note `subprocess`, `os`, `Path` are already imported).

2. Replace the `_PLAYWRIGHT_CHROME` constant with the resolved value, computed once at import:

   ```python
   _PLAYWRIGHT_CHROME: Path | None = _resolve_chromium_binary()
   ```
   Keep the name `_PLAYWRIGHT_CHROME` (other code/tests may reference it) but it is now `Path | None`.

3. Update `render_pdf_chromium()`:
   - The guard becomes `if _PLAYWRIGHT_CHROME is None or not _PLAYWRIGHT_CHROME.exists():` (the `exists()` re-check is cheap belt-and-suspenders) → log a warning naming what was searched and return `None`.
   - Everything downstream uses `str(_PLAYWRIGHT_CHROME)` as before.

4. Update `_render_mermaid_mmdc()`:
   - `if _PLAYWRIGHT_CHROME is not None and _PLAYWRIGHT_CHROME.exists(): env["PUPPETEER_EXECUTABLE_PATH"] = str(_PLAYWRIGHT_CHROME)` — otherwise leave `env` alone (puppeteer finds/downloads its own; Kroki fallback still applies). No other change to mmdc logic.

5. Update the module comment near the constant to describe the new resolution (mention `IW_PLAYWRIGHT_CHROME_PATH`, the glob over the ms-playwright cache, and the `PATH` lookup).

## Constraints

- **Do not** change `dashboard/routers/docs.py` — its 503 behavior is correct and must stay.
- **Do not** add a `.env` key or touch `orch/config.py`. The env var is read directly in `markdown.py`.
- **Do not** rename the env var or add a second one — `IW_PLAYWRIGHT_CHROME_PATH` is the single override name (it already exists in this file today).
- **Do not** import anything that pulls in the DB engine (`orch.db.session`, `dashboard.dependencies`, `dashboard.routers.*`). Keep `markdown.py`'s import chain DB-free so it stays unit-testable.
- Keep `render_pdf_chromium()`'s subprocess flags exactly as they are (`--no-sandbox` etc. are required for non-root containers).
- Run `make lint`, `make format-check`, `make type-check` on your changes before finishing.

## Output

Report which functions you changed, the resolution order you implemented, and confirm `dashboard/routers/docs.py` was not touched. List the lint/format/type-check results.

**Do NOT** call `iw step-done` / `iw step-fail` — the orchestrator handles step completion.
