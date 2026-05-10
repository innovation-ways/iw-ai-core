# CR-00043_S03_backend-impl_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S03
**Agent**: backend-impl

---

## Task

Make a Chromium browser available inside the E2E image (`Dockerfile.e2e`), so the resolver added in S01 finds one via `shutil.which("chromium")` and the PDF route returns a real `%PDF` in the browser-verification stack (`scripts/e2e_up.sh` → `docker-compose.e2e.yml`, which builds `Dockerfile.e2e`).

**Scope note**: the per-worktree compose `app` container (`ai-dev/iw-config/worktree-compose.template.yml`) is **out of scope** for this CR — it runs as a non-root user, so an in-container `apt-get` won't work, and it is *not* the stack browser verification runs against. A clean fix there is deferred (see the "Out of scope / follow-up" note in the design doc). **Do not touch `worktree-compose.template.yml`.**

## Project Context

Read `CLAUDE.md` (esp. the Docker rules) and `ai-dev/active/CR-00043/CR-00043_CR_Design.md` (authoritative). **You are editing one build file, not running any `docker compose` lifecycle command.** Do not run `docker compose up/down/build`, `docker kill/rm/restart`, etc. — `make` / `./ai-core.sh` targets only, and even those are not needed for this step.

## `Dockerfile.e2e`

Current relevant block:

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

Add the Debian `chromium` package (Debian bookworm ships `chromium` in `main`) **with `--no-install-recommends`** plus only the runtime libs Chromium actually needs to run headless. A typical minimal set: `fonts-liberation` (or `fonts-freefont-ttf`), `libnss3`, `libxss1`, `libasound2`, `libatk-bridge2.0-0`, `libatk1.0-0`, `libcups2`, `libdrm2`, `libgbm1`, `libgtk-3-0`, `libx11-xcb1`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxkbcommon0`, `libxrandr2`, `libpangocairo-1.0-0`. (Many of these are pulled by `chromium` itself even without recommends; only add what's missing — verify the package list installs cleanly.) Keep the `apt-get clean && rm -rf /var/lib/apt/lists/*` at the end of the **same `RUN`** layer. Do **not** remove the existing `libpango-1.0-0 libpangoft2-1.0-0` (WeasyPrint may still be a code dependency elsewhere). Do **not** install `chromium-l10n` or extra locales.

After install, `which chromium` inside the image must succeed (it lands at `/usr/bin/chromium`). The S01 resolver's `shutil.which("chromium")` will then pick it up; no env var needs to be set.

Optionally (nice-to-have, not required): also set `ENV IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` in the image so resolution is explicit and version-proof. (Use the **existing** env-var name — `IW_PLAYWRIGHT_CHROME_PATH`, not a new one.)

## Constraints

- No `docker compose`/`docker` lifecycle commands. Edit `Dockerfile.e2e` only.
- Don't bloat the image more than necessary — `--no-install-recommends`, clean apt lists in the same layer, no `chromium-l10n`/extra locales.
- Don't touch `dashboard/utils/markdown.py` (S01 owns it), `dashboard/routers/docs.py`, or `ai-dev/iw-config/worktree-compose.template.yml` (out of scope).
- The image must still start the dashboard exactly as before — the `CMD` / startup is unchanged in behavior (just with Chromium now installed).

## Output

Report: the exact package list you added to `Dockerfile.e2e`; whether you also set the optional `ENV IW_PLAYWRIGHT_CHROME_PATH`; confirmation that `which chromium` will succeed in the built image and that the `CMD` is unchanged; and any image-size impact you estimated.

**Do NOT** call `iw step-done` / `iw step-fail`.
