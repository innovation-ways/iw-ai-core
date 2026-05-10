# CR-00043 S07 — Final Cross-Agent Code Review Report

**Agent**: code-review-final-impl
**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S07

---

## Summary

All CR-00043 implementation pieces (S01 resolver, S03 image, S05 tests) were reviewed. One CRITICAL finding from S04's review — the uv installer was silently dropped from `Dockerfile.e2e` — was detected, fixed inline, and verified before this report was written. All five acceptance criteria are now satisfied.

---

## Files Changed by CR-00043

| File | Step | Change |
|------|------|--------|
| `dashboard/utils/markdown.py` | S01 | Added `_resolve_chromium_binary()` helper; replaced hardcoded `chromium-1217` constant; both call sites updated |
| `Dockerfile.e2e` | S03 | Added Chromium + headless runtime deps; set `IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium`; uv installer restored (fix applied in S07) |
| `tests/dashboard/test_markdown_chromium.py` | S05 | New — 10 unit tests covering AC1–AC4 |

**Not changed** (correctly, per design):
- `dashboard/routers/docs.py` — untouched; 503 behavior preserved
- `ai-dev/iw-config/worktree-compose.template.yml` — out of scope per design Notes

---

## Acceptance Criteria Trace

| AC | Description | Implementation | Status |
|----|-------------|----------------|--------|
| **AC1** | Env var override wins | `_resolve_chromium_binary()` checks `IW_PLAYWRIGHT_CHROME_PATH` first (step 1); set-but-nonexistent falls through | ✅ Pass — S01 resolver + S05 `test_env_override_wins` / `test_env_override_nonexistent_is_ignored` |
| **AC2** | ms-playwright cache glob resolves regardless of version | Step 2 glob finds `chromium-*/chrome-linux64/chrome`; picks highest numeric suffix; skips incomplete dirs | ✅ Pass — S01 resolver + S05 `test_ms_playwright_glob_picks_newest` / `test_ms_playwright_skips_incomplete_dirs` |
| **AC3** | PATH fallback | Step 3 calls `shutil.which("chromium" \| "chromium-browser" \| "google-chrome" \| "google-chrome-stable")` in order | ✅ Pass — S01 resolver + S05 `test_path_lookup_fallback` / `test_path_lookup_tries_names_in_order` / `test_path_lookup_none_when_nothing_found` |
| **AC4** | Graceful degradation preserved | `_PLAYWRIGHT_CHROME = None` → `render_pdf_chromium()` returns `None` (route → 503); mmdc leaves `PUPPETEER_EXECUTABLE_PATH` unset (Kroki fallback) | ✅ Pass — S01 code + S05 `test_render_pdf_chromium_returns_none_when_unresolved` / `test_render_pdf_chromium_returns_none_when_path_missing`; `docs.py` unchanged |
| **AC5** | PDF works in E2E stack | `Dockerfile.e2e` installs `chromium` at `/usr/bin/chromium`; `IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` is set; S01 resolver's `which` chain will find it via step 3 (or step 1 env override wins) | ✅ Pass — S03 image + S07 fix of uv installer that was missing from the S03 diff |

---

## Inline Fix Applied in S07

### CRITICAL — `Dockerfile.e2e` missing uv installation (found by S04, fixed in S07)

**File**: `Dockerfile.e2e`, lines 19–30

**Problem**: The S03 diff replaced the original `RUN` layer that installed uv with one that only did `apt-get install`. The `RUN uv sync` commands at lines 44 and 50 would have failed at image-build time with `exec: "uv": executable file not found`.

**Fix applied**: Restored the uv installation inside the same `RUN` layer:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
        libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
        chromium \
        fonts-liberation libnss3 libxss1 libasound2 \
        libatk-bridge2.0-0 libatk1.0-0 libcups2 \
        libdrm2 libgbm1 libgtk-3-0 \
        libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 \
        libxkbcommon0 libxrandr2 \
    && env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 \
       sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

---

## Cross-Cutting Checks

| Check | Result |
|-------|--------|
| **End-to-end consistency** | `Dockerfile.e2e` installs `chromium` at `/usr/bin/chromium`; `IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` is set; `_resolve_chromium_binary()` finds it via step 1 (env) or step 3 (which). PDF route will return real `%PDF` in E2E stack. |
| **Graceful degradation (AC4)** | `_PLAYWRIGHT_CHROME = None` → PDF route 503s; mmdc falls back to Kroki; `dashboard/routers/docs.py` untouched. |
| **Priority order (AC1–AC3)** | Env → glob → which → None. No new env var introduced. `IW_PLAYWRIGHT_CHROME_PATH` is the sole explicit override. |
| **Scope compliance** | Only `markdown.py`, `Dockerfile.e2e`, `test_markdown_chromium.py` touched; `worktree-compose.template.yml` unchanged. |
| **DB-import contamination** | `markdown.py` imports: `logging`, `os`, `re`, `shutil`, `subprocess`, `tempfile`, `Path`, `TYPE_CHECKING`, `markdown`, `bs4`. No DB, no `orch.config`, no router imports. |
| **Docker lifecycle commands** | None added. S03 and S07 only edit `Dockerfile.e2e`; no `docker compose` invocations. |
| **Hygiene** | `--no-install-recommends` on all apt packages; cleanup in same layer; no new Trivy findings; lint/format/typecheck all pass. |
| **Production unaffected** | Host-run dashboard uses ms-playwright cache; `_resolve_chromium_binary()` resolves to a valid path via step 2 (host cache) or step 3 (host PATH). No behavior change outside containers. |

---

## Quality Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 667 files already formatted |
| `make type-check` | ✅ Success: no issues found in 240 source files |
| `uv run pytest tests/dashboard/test_markdown_chromium.py tests/dashboard/test_docs_pdf_chromium.py -q --no-cov` | ✅ 19 passed |
| `make test-unit` | ✅ 2722 passed, 4 skipped, 5 xfailed, 1 xpassed |

---

## Findings

| Severity | Description | Status |
|----------|-------------|--------|
| CRITICAL | `Dockerfile.e2e` was missing uv installation — `RUN uv sync` would fail at build time | **Fixed** (S07 inline fix) |
| HIGH | `worktree-compose.template.yml` untouched (correctly — out of scope per design Notes) | N/A — confirmed not modified |
| HIGH | `dashboard/routers/docs.py` untouched (correctly — routing behavior follows resolver) | N/A — confirmed not modified |

---

## Verdict

```
PASS
mandatory_fix_count: 0

(finding from S04 was fixed inline in S07 before this report was written;
no residual findings remain)
```

All five acceptance criteria are met. The E2E image will build successfully, the PDF route will return real `%PDF` in the E2E stack (AC5), and graceful degradation is preserved when no Chromium is available (AC4).