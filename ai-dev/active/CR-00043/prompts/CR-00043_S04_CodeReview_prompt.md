# CR-00043_S04_CodeReview_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S04
**Agent**: code-review-impl

---

## Task

Review the S03 change to `Dockerfile.e2e`.

## Source of truth

Read `ai-dev/active/CR-00043/CR-00043_CR_Design.md` first.

## Review checklist

- `Dockerfile.e2e`: `chromium` is installed with `--no-install-recommends`; only the minimal headless runtime libs were added (no `chromium-l10n`, no full recommends, no extra locales); `apt-get clean && rm -rf /var/lib/apt/lists/*` still terminates the **same `RUN`** layer; `libpango-1.0-0 libpangoft2-1.0-0` were NOT removed; the image's `CMD` / dashboard startup is unchanged in behavior.
- After the change, `which chromium` resolves to `/usr/bin/chromium` in the built image — so the S01 resolver's `shutil.which("chromium")` will find it without any env var. An optional `ENV IW_PLAYWRIGHT_CHROME_PATH=/usr/bin/chromium` is fine but not required; if present it must use the **existing** env-var name `IW_PLAYWRIGHT_CHROME_PATH` (not a new `IW_CORE_*` variant).
- **Out of scope respected**: S03 must NOT have touched `ai-dev/iw-config/worktree-compose.template.yml` (the per-worktree compose `app` container is deferred — see the design Notes), nor `dashboard/utils/markdown.py` / `dashboard/routers/docs.py`.
- No `docker compose`/`docker` lifecycle command was run or added to any script.
- Trivy/hadolint-style hygiene: minimal package install, single `RUN` layer, cleanup in the same layer (this repo runs `make security-sast` / image scans — don't introduce new high-severity Dockerfile findings).

## Output

Review report with severities and `mandatory_fix_count`. Deviation from the design doc is at least HIGH. An image that won't build is CRITICAL; touching the out-of-scope `worktree-compose.template.yml` is at least HIGH.

**Do NOT** call `iw step-done` / `iw step-fail`.
