# CR-00022_S14_CodeReview_report

**Step**: S14 (code-review-impl)
**Reviewing**: S13 — Phase E UI (frontend-impl)
**Agent**: code-review-impl

---

## Summary

S13 implements the OSS compliance UI: scan/run actions, findings table with per-row re-run, finding detail modal with accept form, and apply-all-safe preview modal. The implementation is broadly sound. One validation inconsistency and one accessibility gap found.

---

## Finding 1 — Backend/Frontend minlength mismatch (MEDIUM)

**File**: `dashboard/routers/oss_models.py:24-27`
**Severity**: MEDIUM

**Issue**: The accept form requires `minlength="5"` in the HTML textarea and the JS enforces `reason.length < 5` before submitting. However, the Pydantic model on the server accepts `min_length=1`:

```python
class AcceptRequestBody(BaseModel):
    reason: Annotated[
        str,
        Field(
            min_length=1,   # ← server allows 1 char
            max_length=500,
            ...
        ),
    ]
```

A user who bypasses the UI (e.g., via browser dev tools) can POST a reason with 2–4 characters and it will be accepted by the server. The UI and JS require 5.

**Recommendation**: Change server-side to `min_length=5` to match the declared UX contract:
```python
reason: Annotated[
    str,
    Field(
        min_length=5,   # match UI contract
        max_length=500,
        ...
    ),
]
```

---

## Finding 2 — Apply-all modal missing focus trap (LOW)

**File**: `dashboard/templates/fragments/oss_apply_all_safe_modal.html:31-189`
**Severity**: LOW

**Issue**: The finding detail modal (`oss_finding_modal.html`) has a `trapFocus()` function that cycles Tab/Shift+Tab between focusable elements inside the modal. The apply-all modal does not have an equivalent focus trap.

Per WCAG 2.1 Level A, dialogs should trap focus. The apply-all modal is a proper `role="dialog"` with `aria-modal="true"` but no programmatic focus containment.

**Recommendation**: Either apply the same `trapFocus()` pattern to the apply-all modal, or ensure that all interactive elements inside the modal are unreachable via Tab when the modal is open (e.g., by moving the modal outside the normal tab order and restoring focus to the trigger on close).

---

## Finding 3 — Re-run uses full rescan not per-check (INFORMATIONAL)

**File**: `dashboard/routers/oss.py:474-514`
**Severity**: INFORMATIONAL

**Issue**: The `/oss/recheck/{check_id}` endpoint ignores the `check_id` path parameter and runs a full re-scan of all findings. The docstring acknowledges this: `"Re-run a single check by re-running the full scan (v1) — Phase F2 adds --check filter."`

This is a Phase F2 gap, not a bug in S13. Flagged for awareness.

---

## Verified Passed Items

| Check | Detail |
|-------|--------|
| Per-row re-run icon present | `↻` button with `aria-label="Re-run this check"` on every row |
| Re-run endpoint correct | `POST /project/{id}/oss/recheck/{check_id}` |
| Re-run spinner feedback | JS replaces icon with animated SVG while fetch is in-flight; restores on complete or error |
| SSE row patching | `row-update` event calls `patchRowInPlace()` on existing row, `insertRow()` for new rows |
| Accept form — HTML minlength | `textarea minlength="5"` present |
| Accept form — JS validation | `reason.length < 5` blocks submission |
| Accept POST URL | `POST /oss/accept/{check_id}` with `{finding_hash, reason}` |
| finding_hash source | Read from `btn.dataset.findingHash` (from row `data-finding-hash` attribute) — not recomputed |
| Accept success | `window.location.reload()` — full page reload; modal closes, toast from server via `HX-Trigger` |
| Apply-all preview trigger | Button click fetches `POST /oss/apply-all-safe/preview` |
| Apply-all modal copy | "Writes to your working tree only. No branch is created." visible |
| Apply-all POST body | Sends `{check_ids: [...]}` with only checked recipe check_ids |
| Per-file checkboxes | Documented as informational; top-level checkbox controls inclusion |
| Finding modal a11y | `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, ESC closes, backdrop closes, focus trap present |
| `make css` | Tailwind rebuilt successfully; `styles.css` updated |
| `make lint` (dashboard) | `ruff check dashboard/` — all checks passed |
| `mypy` (OSS router) | No issues found |
| Server defensiveness — apply-all | `oss.py:603-611` iterates each `check_id` and 422s if `recipe.auto_apply_safe` is False |
| Server defensiveness — accept | No server-side minlength check (see Finding 1) |

---

## Pre-existing Issues (Not from S13)

- `orch/oss/fix_recipes/secrets.py`: 95 ruff E501/W505 line-length violations — pre-existing, not introduced by S13.

---

## Verdict

**S13 passes review with 2 findings.**

- **Finding 1 (MEDIUM)**: Backend `min_length=1` should be `min_length=5` to match the declared UI contract. Fix before merge.
- **Finding 2 (LOW)**: Apply-all modal needs a focus trap for accessibility compliance. Fix before merge or track as follow-up.

**No blocking issues.** The server-side `auto_apply_safe` guard on the apply-all endpoint is correctly implemented and cannot be bypassed from the UI. The re-run SSE loop correctly patches rows in place.
