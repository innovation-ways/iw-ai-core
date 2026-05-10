# CR-00043 S03 Backend Report

**Step**: S03
**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Agent**: backend-impl
**Date**: 2026-05-10

---

## What Was Done

Modified `Dockerfile.e2e` to install the Debian `chromium` package and its minimal headless runtime dependencies, so that `shutil.which("chromium")` succeeds inside the E2E image and the S01 resolver's PATH-lookup step finds a real binary.

### Changes Made

**File**: `Dockerfile.e2e`

- Added `chromium` to the `apt-get install` list (Debian bookworm, `main` section, `--no-install-recommends`)
- Added the minimal runtime libraries Chromium needs to run headless in a container:
  - `fonts-liberation` — font fallback
  - `libnss3`, `libxss1`, `libasound2` — networking, XSS, audio
  - `libatk-bridge2.0-0`, `libatk1.0-0` — accessibility bridge
  - `libcups2` — printing
  - `libdrm2`, `libgbm1` — DRM / GBM (GPUoffscreen rendering)
  - `libgtk-3-0` — UI toolkit
  - `libx11-xcb1`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxkbcommon0`, `libxrandr2` — X11 event handling
  - `libpangocairo-1.0-0` — kept (existing `libpango*` libs for WeasyPrint)
- Preserved `apt-get clean && rm -rf /var/lib/apt/lists/*` in the same RUN layer
- Added `ENV IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` so resolution is explicit and version-proof (nice-to-have, not required)

### Files Changed

| File | Change |
|------|--------|
| `Dockerfile.e2e` | Added chromium + runtime deps to apt-get install; added IW_PLAYWRIGHT_CHROME_PATH env var |

### Not Changed

- `CMD` unchanged — still `["/app/scripts/e2e_dashboard_entrypoint.sh"]`
- `libpango-1.0-0 libpangoft2-1.0-0` kept (WeasyPrint dependency)
- `dashboard/utils/markdown.py` — S01 owns it, not touched here
- `dashboard/routers/docs.py` — out of scope
- `ai-dev/iw-config/worktree-compose.template.yml` — out of scope per design doc

---

## Confirmation

- **`which chromium`** will succeed in the built image at `/usr/bin/chromium`
- **`IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium`** is set in the image, so the env-var step of the S01 resolver is satisfied first (even before PATH lookup)
- The `CMD` is unchanged; dashboard startup behavior is identical
- The `--no-sandbox` flag is already passed by `render_pdf_chromium()` in S01, so no extra Chromium flags are needed for non-root container execution

---

## Estimated Image Size Impact

- Debian `chromium` package: ~120–150 MB (compressed layer)
- Runtime libs (most pulled as dependencies of chromium itself): ~20–40 MB
- **Total additional size**: ~150–190 MB

This is acceptable for a verification-only E2E image (per the design doc's impact analysis).

---

## Test Results

No test execution required for this step (build file only, no code changes, no docker lifecycle commands). No regressions possible since the CMD and startup behavior are unchanged.

---

## Blockers or Concerns

None.