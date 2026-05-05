# I-00066_S02_CodeReview_Frontend_prompt

**Work Item**: I-00066 -- OSS finding modal too narrow and footer buttons unclear
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident touches no database state — there is no migration step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00066 --json`.
- `ai-dev/active/I-00066/I-00066_Issue_Design.md` -- Design document
- `ai-dev/active/I-00066/reports/I-00066_S01_Frontend_report.md` -- S01 implementation report
- All files listed in S01's `files_changed` (expected:
  `dashboard/static/tailwind.src.css`,
  `dashboard/static/styles.css`,
  `dashboard/templates/fragments/oss_finding_modal.html`).

## Output Files

- `ai-dev/active/I-00066/reports/I-00066_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by the
Frontend agent for **I-00066**. The fix is purely cosmetic: widen
`.oss-modal-inner`, restyle the footer buttons (`.modal-apply`,
`.modal-rerun`, `.modal-accept`, `.modal-preview`), add a new
`.modal-footer-close` peer-button class, apply it to the footer
Close button in the template, and regenerate the compiled
stylesheet.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`:

```bash
make lint
make format
```

Classify NEW violations in the changed files as **CRITICAL** with
`category: "conventions"`.

## Review Checklist

### 1. Architecture Compliance

- The change is restricted to `dashboard/static/` (CSS) and
  `dashboard/templates/fragments/` (one HTML class). No Python, no
  router, no model. No new build steps. No new dependencies.
- The compiled `styles.css` was regenerated from `tailwind.src.css`
  via `make css` (per `dashboard/CLAUDE.md`). Verify by checking
  that the `max-width: 80vw` value appears in BOTH files.

### 2. Code Quality

- `.oss-modal-inner` uses `max-width: 80vw`; the literal `36rem` is
  GONE from that rule.
- All other properties of `.oss-modal-inner` are preserved
  (`width: 100%`, `max-height: 90vh`, `display: flex`, etc.).
- Footer button rule (`.modal-apply, .modal-rerun, .modal-accept`,
  now also including `.modal-preview`) renders with stronger
  affordance — visible border, padding, hover. NO flashy /
  brand-coloured background (no `var(--primary)` /
  `var(--accent)` resting state).
- A new `.modal-footer-close` rule exists and includes both
  `border:` and `padding:` declarations (semantic check).
- The original `.modal-close` rule (used by the header `×` close
  button on `oss_finding_modal.html:11`) is UNCHANGED.

### 3. Template change

- `oss_finding_modal.html` line 74 now has
  `class="modal-footer-close modal-close"` (both classes — the
  `modal-close` class is required for the existing JS click
  handler at lines 335-345 to still match and close the modal).
- The header `×` close button on line 11 still has
  `class="modal-close"` (UNCHANGED).
- No other template lines were modified.

### 4. Project Conventions

- Tailwind classes used in templates are not constructed dynamically
  (would break JIT purging).
- CSS uses existing custom properties (`var(--card)`,
  `var(--border)`, etc.) — no new colour tokens added.
- File paths and naming match repo style.

### 5. Security

- No hardcoded secrets, URLs, or credentials.
- No injection vectors introduced (the change does not touch any
  user-rendered content or HTML escaping).

### 6. Testing

- The reproduction test at
  `tests/dashboard/test_i00066_oss_modal_styling.py` (produced by
  S03) PASSES against this fix. If S03 has already run, run the
  test:

  ```bash
  uv run pytest tests/dashboard/test_i00066_oss_modal_styling.py -x
  ```

  If the test file doesn't yet exist (S03 has not run), perform the
  same checks manually using grep:

  ```bash
  grep -n "max-width: 80vw" dashboard/static/tailwind.src.css
  grep -n "max-width:80vw\|max-width: 80vw" dashboard/static/styles.css
  grep -n "36rem" dashboard/static/tailwind.src.css   # must NOT match in .oss-modal-inner
  grep -n "modal-footer-close" dashboard/static/tailwind.src.css \
        dashboard/templates/fragments/oss_finding_modal.html
  ```

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and report the result. If the targeted
reproduction test exists, run it as well.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, modal is broken, regression test fails |
| **HIGH** | Significant style violation (e.g., flashy/brand colour added), missing class, missing compiled-CSS regeneration |
| **MEDIUM (fixable)** | Minor convention violation, formatting drift |
| **MEDIUM (suggestion)** | Improvement suggestion |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00066",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM (fixable)
findings. `mandatory_fix_count` = CRITICAL + HIGH + MEDIUM (fixable).
