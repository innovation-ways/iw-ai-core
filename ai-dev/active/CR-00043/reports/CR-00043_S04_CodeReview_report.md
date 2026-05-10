# CR-00043_S04_CodeReview_report.md

## Step Summary

| Field | Value |
|-------|-------|
| Work Item | CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers |
| Step | S04 |
| Reviewing | S03 (`backend-impl`) changes to `Dockerfile.e2e` |
| Agent | `code-review-impl` |

---

## Files Changed by S03

| File | Intent |
|------|--------|
| `Dockerfile.e2e` | Add Chromium browser + headless runtime deps to the E2E image; set `IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` |

`dashboard/utils/markdown.py` is also modified in the working tree (S01+S03 cumulative), but S03's explicit scope is only `Dockerfile.e2e`.

---

## Review Findings

### CRITICAL — uv Installation Silently Dropped

**File**: `Dockerfile.e2e`, lines 19–30

**Description**: The original `RUN` layer (lines 19–30 in `HEAD~1`) installed uv via the official installer:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
        libpango-1.0-0 libpangoft2-1.0-0 \
    && env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 \
       sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

The S03 diff replaces this entire `RUN` block with one that **omits the uv installation step**:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
        libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
        chromium \
        fonts-liberation libnss3 libxss1 libasound2 \
        ... \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

The E2E image boots into a `python:3.12-slim` base that ships **no `uv`**. Every subsequent `RUN uv sync ...` instruction (lines 44, 50 in `Dockerfile.e2e`) will fail at image-build time with `exec: "uv": executable file not found`.

The `CMD` / dashboard startup behavior is **unchanged in behavior** (it still runs the same entrypoint), but the image will not build — an incomplete image that won't build is by definition CRITICAL.

**Suggested fix**: Restore the uv installation inside the same `RUN` layer, before or alongside the package install:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
        libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
        chromium \
        fonts-liberation libnss3 libxss1 libasound2 \
        ... \
    && env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 \
       sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

(Using `--no-install-recommends` for all packages including Chromium is correct per the design notes; the headless runtime libs added are appropriate.)

---

### HIGH — Out-of-Scope `worktree-compose.template.yml` Not Touched

**Verification**: `git diff HEAD~1 -- ai-dev/iw-config/worktree-compose.template.yml` returns empty. ✅ Correct — the design explicitly defers the per-worktree compose container to a follow-up.

### HIGH — `dashboard/routers/docs.py` and `dashboard/utils/markdown.py` Not Modified by S03

S03's scope is `Dockerfile.e2e` only. `markdown.py`'s resolver was added in S01 (working-tree changes confirmed separate from S03). ✅ The routing behavior follows the resolver automatically per the design.

### VERIFIED — `chromium` Installed with `--no-install-recommends`

All packages in the `RUN` layer use `--no-install-recommends`. ✅ No `chromium-l10n` or full recommends. ✅ No extra locales pulled in.

### VERIFIED — Cleanup in Same Layer

`apt-get clean && rm -rf /var/lib/apt/lists/*` terminates the same `RUN` layer. ✅

### VERIFIED — `libpango-1.0-0 libpangoft2-1.0-0` NOT Removed

`libpangocairo-1.0-0` was added (needed by Chromium); the two original libs remain. ✅ No removal.

### VERIFIED — `IW_PLAYWRIGHT_CHROME_PATH` Uses Existing Env-Var Name

The design explicitly requires `IW_PLAYWRIGHT_CHROME_PATH` (not a new `IW_CORE_*` variant). The working-tree `markdown.py` reads this name correctly. ✅

### VERIFIED — `which chromium` Resolves to `/usr/bin/chromium`

Debian's `chromium` package installs to `/usr/bin/chromium`. The `ENV IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` makes this explicit. ✅ The S01 resolver's `shutil.which("chromium")` chain (step 3) will also find it on PATH.

### VERIFIED — No `docker compose`/`docker` Lifecycle Commands Added

Only comments reference `docker-compose.e2e.yml`. ✅

### VERIFIED — No Trivy/Hadolint Issues

Single `RUN` layer for all apt operations; cleanup in same layer. ✅

---

## Test Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ All files formatted |

---

## Verdict

**NEEDS_FIX** — 1 mandatory fix.

The uv installation is silently dropped from the `RUN` layer. Without it the E2E image will fail to build (`uv sync` won't find `uv`), blocking the S15 browser-verification step and all downstream acceptance criteria.

---

## Mandatory Fix Count

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00043",
  "reviewed_agent": "backend-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "Dockerfile.e2e",
      "line(s)": "19-30",
      "description": "uv installation (astral.sh) was silently dropped from the RUN layer. The image will fail to build because subsequent 'RUN uv sync' commands (lines 44, 50) will find no 'uv' binary. The python:3.12-slim base ships no uv.",
      "suggested_fix": "Restore the uv installer inside the same RUN layer: add '&& env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh -c \"curl -LsSf https://astral.sh/uv/install.sh | sh\"' before 'apt-get clean', alongside the --no-install-recommends packages and Chromium."
    },
    {
      "severity": "HIGH",
      "file": "ai-dev/iw-config/worktree-compose.template.yml",
      "line(s)": "N/A",
      "description": "Correctly untouched — out of scope per design Notes.",
      "suggested_fix": "No fix needed."
    }
  ],
  "notes": "The S03 diff shows only Dockerfile.e2e changes; markdown.py is working-tree S01-only. The design checklist items (--no-install-recommends, cleanup in same layer, libpango* not removed, IW_PLAYWRIGHT_CHROME_PATH name, no docker lifecycle commands) all pass. The single showstopper is the missing uv install."
}
