# I-00066: OSS finding modal too narrow and footer buttons unclear

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-05
**Reported By**: sergio (visual review of OSS Compliance page)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

This incident touches no database state — there is no migration step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

On the OSS Compliance page (`/project/{id}/oss`) clicking the row-level
"…" (View details) button opens a finding modal that is too narrow and
whose footer buttons read as plain labels instead of buttons. The modal
caps at `max-width: 36rem` (~576px), which on a 1280–1920px viewport
appears around 30–50% of window width and feels cramped given the
amount of text content (What it checks / How it tests / Risk / Findings
/ How to fix / References). The footer buttons (Re-run check / Mark
accepted / Close) have minimal styling — the Close button reuses the
header `×` close style — so they are hard to identify as actionable.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Dashboard CSS is prebuilt via Tailwind CLI (`make css`). The
generated `dashboard/static/styles.css` is committed and must be
regenerated whenever `dashboard/static/tailwind.src.css` changes.

## Browser Evidence

Pre-fix screenshot captured on 2026-05-05 against the live dashboard at
`http://localhost:9900/project/iw-ai-core/oss`:

- `ai-dev/active/I-00066/evidences/pre/I-00066-bug-evidence.png`

The screenshot shows the OSS finding modal opened on `OSS-SEC-01`
(secrets / tree scan). The modal is roughly half the viewport width
with the OSS table visible behind it on both sides; the three footer
buttons (Re-run check / Mark accepted / Close) blend into the modal
chrome.

## Steps to Reproduce

1. Open the dashboard at `/project/iw-ai-core/oss`.
2. Wait for the OSS findings table to render.
3. Click the "…" (View details) button on any failing row (for
   example the row for `OSS-SEC-01`).

**Expected**:
- The finding modal occupies approximately 80% of the viewport width
  on a desktop window.
- The three visible footer buttons (Re-run check, Mark accepted,
  Close) are clearly identifiable as buttons — visible border,
  consistent height, hover affordance — without using flashy or
  brand-coloured backgrounds.

**Actual**:
- The modal caps at `max-width: 36rem` (~576px) and looks ~50% of
  the viewport width.
- Footer buttons render as flat label-like text. The footer Close
  button reuses the small `×`-close style and lacks border/padding
  consistent with the other footer buttons.

## Browser Verification Script

The post-fix QV-Browser step uses these commands inside the daemon's
isolated e2e stack (driven by `$IW_BROWSER_BASE_URL`); operators can
reproduce the same flow against the live dashboard at port 9900.

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/oss"
playwright-cli snapshot                       # capture refs of the "..." details buttons
playwright-cli click <details-button-ref>     # click the first View-details button
playwright-cli screenshot                     # auto-saved under .playwright-cli/
cp .playwright-cli/page-*.png \
   ai-dev/active/I-00066/evidences/post/I-00066_v1_modal_open.png
```

## Root Cause Analysis

Two CSS rules and one template line drive the symptom:

1. **`dashboard/static/tailwind.src.css:146`** — the `.oss-modal-inner`
   block sets `max-width: 36rem;`. Combined with the parent
   `.oss-modal` flex container's `padding: 1rem` this caps the inner
   card at ~576px regardless of the viewport size, so on a desktop
   viewport the modal looks ~50% of the window width.
2. **`dashboard/static/tailwind.src.css:224-241`** — the
   `.modal-apply, .modal-rerun, .modal-accept` selector applies a thin
   `border: 1px solid var(--border)` on a `var(--card)` background
   with the same `var(--foreground)` text colour as plain prose. There
   is no shadow, no contrast tint and no clear hover beyond a
   `var(--muted)` background swap. The result reads as a label, not a
   button.
3. **`dashboard/templates/fragments/oss_finding_modal.html:74`** — the
   footer Close button is `<button class="modal-close">Close</button>`.
   The `.modal-close` class (lines 208-222 of `tailwind.src.css`) is
   the styling for the header `×` close button: `1.25rem` font,
   `var(--muted-foreground)` colour, no border, no background. Reusing
   it for the footer Close button is what makes that button look like
   a label.

The compiled stylesheet `dashboard/static/styles.css` is generated
from `tailwind.src.css` by `make css`; both the source and the
generated file must be updated.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/static/tailwind.src.css` | `.oss-modal-inner` width cap and footer button styling are too restrictive / too subtle. |
| `dashboard/static/styles.css` | Compiled output must be regenerated (`make css`). |
| `dashboard/templates/fragments/oss_finding_modal.html` | Footer `Close` button reuses header `×`-close styling — must use a peer footer-button class. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Widen `.oss-modal-inner`, restyle footer buttons, give the footer Close button a peer style; rebuild compiled CSS via `make css` | — |
| S02 | CodeReview_Frontend | Review S01 | — |
| S03 | Tests | Reproduction + regression test on the rendered template fragment and compiled stylesheet | — |
| S04 | CodeReview_Tests | Review S03 | — |
| S05 | CodeReview_Final | Global cross-step review | — |
| S06 | self-assess | Process self-assessment (project has `self_assess=true`) | — |
| S07..S13 | QV gates | lint, format-check, type-check, arch-check, security-sast, unit-tests, integration-tests | — |
| S14 | qv-browser | Browser verification | — |

`frontend-tsc` and `frontend-tests` gates are intentionally omitted —
the dashboard does not have a separate `frontend/` TypeScript stack;
JS lint runs as part of `make lint` (which runs `lint-js`), and
dashboard rendering tests run inside `make test-unit` and
`make test-integration`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration step in this incident.

### Code Changes

- **Files to modify**:
  - `dashboard/static/tailwind.src.css` — widen `.oss-modal-inner` to
    `max-width: 80vw` (preserve existing `width: 100%`,
    `max-height: 90vh`); restyle `.modal-apply`, `.modal-rerun`,
    `.modal-accept`, `.modal-preview` and add `.modal-footer-close`
    so that all five render with consistent padding, border, hover
    affordance and a subtle muted-tinted background (no flashy /
    brand colour).
  - `dashboard/static/styles.css` — regenerate via `make css`.
  - `dashboard/templates/fragments/oss_finding_modal.html` — change
    the footer Close button from `class="modal-close"` to
    `class="modal-footer-close modal-close"` so it inherits the new
    peer button styling while preserving the existing
    `.modal-close` JS click handler that closes the modal.
- **Nature of change**: Pure cosmetic CSS + one template class
  attribute change. No JS, no Python, no API.

## File Manifest

All files for this work item live under `ai-dev/active/I-00066/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00066_Issue_Design.md` | Design | This document |
| `I-00066_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions + scope.allowed_paths |
| `prompts/I-00066_S01_Frontend_prompt.md` | Prompt | S01 — fix CSS + template |
| `prompts/I-00066_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00066_S03_Tests_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00066_S04_CodeReview_Tests_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00066_S05_CodeReview_Final_prompt.md` | Prompt | S05 — global cross-step review |
| `prompts/I-00066_S06_SelfAssess_prompt.md` | Prompt | S06 — self-assess |
| `prompts/I-00066_S14_BrowserVerification_prompt.md` | Prompt | S14 — browser verification |

Reports are created during execution in
`ai-dev/active/I-00066/reports/`.

## Test to Reproduce

The reproduction test exercises the rendered modal fragment and the
compiled stylesheet (this is a frontend cosmetic bug, so the
reproduction lives in a dashboard-level test rather than a unit
test).

```python
# tests/dashboard/test_i00066_oss_modal_styling.py
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "dashboard/templates/fragments/oss_finding_modal.html"
SOURCE_CSS = REPO_ROOT / "dashboard/static/tailwind.src.css"
COMPILED_CSS = REPO_ROOT / "dashboard/static/styles.css"


def _block(css: str, selector: str) -> str:
    """Return the contents of the FIRST CSS block whose selector exactly matches."""
    pattern = re.compile(
        r"(?:^|\s|,)" + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.MULTILINE,
    )
    m = pattern.search(css)
    assert m, f"selector not found: {selector}"
    return m.group(1)


def test_i00066_modal_inner_widened_in_source_css():
    """`.oss-modal-inner` must use 80vw, not 36rem (semantic value check)."""
    body = _block(SOURCE_CSS.read_text(), ".oss-modal-inner")
    assert "max-width: 80vw" in body, body
    assert "36rem" not in body, body


def test_i00066_modal_inner_widened_in_compiled_css():
    """Compiled stylesheet must reflect the source change."""
    css = COMPILED_CSS.read_text()
    assert ".oss-modal-inner" in css
    # The compiled file is minified; just check the selector and the new value
    # appear together (no 36rem in the same rule).
    inner_match = re.search(
        r"\.oss-modal-inner\{([^}]*)\}", css
    )
    assert inner_match, "oss-modal-inner not found in compiled CSS"
    body = inner_match.group(1)
    assert "max-width:80vw" in body or "max-width: 80vw" in body, body
    assert "36rem" not in body, body


def test_i00066_footer_close_uses_peer_button_class():
    """The footer Close button must carry the new peer-button class so it
    renders like Re-run check / Mark accepted, not like the header × close."""
    html = TEMPLATE.read_text()
    # The header × close button is OK to keep `.modal-close` only.
    # The FOOTER close button (the one with text 'Close') must also have
    # the new `.modal-footer-close` class.
    footer_close = re.search(
        r'<button[^>]*class="[^"]*modal-footer-close[^"]*"[^>]*>\s*Close\s*</button>',
        html,
    )
    assert footer_close, html


def test_i00066_footer_button_class_styled_in_source_css():
    """The new `.modal-footer-close` class must have border + padding so
    it renders as a button, not a plain × close icon."""
    body = _block(SOURCE_CSS.read_text(), ".modal-footer-close")
    # Semantic checks: must have a real border, real padding, and font-weight
    # consistent with the other footer buttons.
    assert "border:" in body, body
    assert "padding:" in body, body
```

## Acceptance Criteria

### AC1: Modal width is approximately 80% of viewport on desktop

```
Given the dashboard is open at /project/{id}/oss on a viewport at least 1024px wide
When the user clicks any "..." (View details) button on an OSS findings row
Then the resulting modal renders with width approximately 80vw (capped by max-width: 80vw)
And the modal still respects max-height: 90vh
```

### AC2: Footer buttons are clearly identifiable as buttons

```
Given the OSS finding modal is open
When the user looks at the footer
Then the three visible footer buttons (Re-run check, Mark accepted, Close)
  render with a visible border, consistent padding, consistent height,
  and a hover state — without using a flashy or brand-coloured background
And the footer Close button looks like a peer of Re-run check / Mark accepted,
  not like the small × icon used in the modal header
```

### AC3: Reproduction and regression tests exist

```
Given the fix is applied
When the test suite runs
Then the dashboard test in tests/dashboard/test_i00066_oss_modal_styling.py
  passes — verifying:
    - .oss-modal-inner has max-width: 80vw in both tailwind.src.css and the
      compiled styles.css, and 36rem no longer appears in that rule;
    - the footer Close button in oss_finding_modal.html carries the new
      .modal-footer-close class;
    - the .modal-footer-close rule defines real border + padding.
```

## Regression Prevention

- The new tests assert SEMANTIC values (`max-width: 80vw`, presence of
  `border:` + `padding:` in the new class, presence of the new class
  on the footer Close button). Future width regressions or
  re-introduction of the old `36rem` cap will fail
  `test_i00066_modal_inner_widened_in_source_css`.
- The compiled-CSS assertion (`test_i00066_modal_inner_widened_in_compiled_css`)
  also catches the case where someone edits `tailwind.src.css` but
  forgets to run `make css` — a recurring class of bug for this
  dashboard.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/static/tailwind.src.css`
- `dashboard/static/styles.css`
- `dashboard/templates/fragments/oss_finding_modal.html`
- `tests/dashboard/test_i00066_oss_modal_styling.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_i00066_oss_modal_styling.py`
  — fails on `main` because (a) `tailwind.src.css` still has
  `max-width: 36rem`, (b) the footer Close button has only the
  `.modal-close` class, (c) `.modal-footer-close` does not exist.
- **Unit tests**: Not applicable — no Python logic changed.
- **Integration tests**: Existing dashboard integration tests
  continue to pass (the OSS page route, the modal fragment renderer,
  the htmx swap behaviour). No new integration test is added because
  no Python code path changed.

## Notes

- Width target: `max-width: 80vw` (no breakpoint media query). The
  modal already had `width: 100%` and `padding: 1rem` on the outer
  flex container, so the effective rendered width on a 1920px screen
  is ~1536px and on a 768px tablet is ~614px — both feel right and
  preserve readability of the long sections (Findings table,
  Preview).
- The `.modal-close` rule (lines 208-222) is intentionally LEFT
  UNCHANGED so the header `×` close button keeps its existing look.
- New `.modal-footer-close` class is additive — it does NOT replace
  `.modal-close` on the footer button. The footer button keeps both
  classes so existing JS click handlers
  (`oss_finding_modal.html:335-345`) still match `modal-close` and
  close the modal.
- No flashy / brand colours: reuse `var(--card)`, `var(--border)`,
  `var(--foreground)`, `var(--muted)`, and `var(--muted-foreground)`
  CSS custom properties already declared in `theme.css`. Add no new
  colour tokens.
