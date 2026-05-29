# I-00120 S04 — Code Review Report

**Step**: S04
**Agent**: CodeReview
**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step Reviewed**: S03 (frontend-impl)
**Verdict**: **PASS**

---

## What Was Reviewed

S03 implemented the frontend half of the fix:
- `dashboard/routers/usage.py` — added `_CODEX_WARNING_MAP` and reads `codex.get("status")` from the backend dict, producing `codex_warning` for the template.
- `dashboard/templates/fragments/llm_usage_footer.html` — `{% if codex_warning %}` branch replaces the two Codex bars with a single amber warning span.

S01 (backend) added the status discriminator (`status: ok/expired/unauthenticated/error`) to `orch/llm_usage.py`. Both S01 and S03 changes are committed in the worktree.

---

## Pre-Review Quality Gates

| Gate | Result |
|------|--------|
| `make lint` (incl. `scripts/check_templates.py` for Jinja2) | ✅ All checks passed |
| `make format` | ✅ 973 files already formatted |

No new violations introduced by S03.

---

## Checklist Findings

### 1. Status → message mapping ✅

`_CODEX_WARNING_MAP` in `dashboard/routers/usage.py`:

| status | Warning text | Matches design? |
|--------|-------------|-----------------|
| `expired` | `token expired — re-authenticate` | ✅ exact match |
| `unauthenticated` | `not configured — run opencode auth login` | ✅ exact match |
| `error` | `usage unavailable` | ✅ exact match |
| `ok` | *(no entry — `None`)* | ✅ no warning |

### 2. Conditional render ✅

```jinja2
{% if codex_warning %}
  <span class="hidden sm:flex items-center gap-1 text-amber-600" title="Codex {{ codex_warning }}">⚠ {{ codex_warning }}</span>
{% else %}
  ...two bars...
{% endif %}
```
- Warning branch replaces bars completely when `codex_warning` is set.
- Normal bars render when status == `ok` (including the fallback path).
- Both branches are well-formed HTML; no broken tags.

### 3. CSS class pre-compiled ✅

`text-amber-600` was verified present in `dashboard/static/styles.css` (`grep -c` → 1). No `make css` run needed; no new Tailwind class introduced.

### 4. Thin router ✅

`llm_usage_fragment()` does only:
- Read `codex.get("status") or "ok"`
- `_CODEX_WARNING_MAP.get(codex_status)` → `codex_warning`
- Pass both to template context

Claude/MiniMax context is unchanged. The stale-cache fallback dict correctly carries `"status": "error"` so a pre-upgrade in-process cache surfaces the "usage unavailable" warning instead of silent 0%.

### 5. `format` filter style ✅

No Jinja2 `|format(...)` usage in `llm_usage_footer.html`. No `%`-style or `str.format`-style Jinja2 filters present.

### 6. No collateral changes ✅

Claude and MiniMax fragment sections are untouched. Fragment does not `extend base.html`.

---

## Test Verification

Rendered `GET /api/usage/llm/fragment` via `TestClient` with `get_llm_usage` patched, testing all 5 branches:

| Case | Amber class? | ⚠ glyph? | Correct message? | Bars absent? | Result |
|------|-------------|---------|-------------------|---------------|--------|
| `ok` | ❌ | ❌ | — | ✅ (bars shown) | **PASS** |
| `expired` | ✅ | ✅ | `token expired — re-authenticate` | ✅ | **PASS** |
| `unauthenticated` | ✅ | ✅ | `not configured — run opencode auth login` | ✅ | **PASS** |
| `error` | ✅ | ✅ | `usage unavailable` | ✅ | **PASS** |
| fallback (no codex key) | ✅ | ✅ | `usage unavailable` (from `"status": "error"` in fallback dict) | ✅ | **PASS** |

All 5 branches render correctly. The fallback path correctly surfaces the warning when an in-process cache predates the upgrade (no `codex` key).

---

## Mandatory Fix Count

**0** — no issues found.

---

## Notes

- The `IW_CORE_OPERATOR_APPLY=true` env var was needed to bypass `verify_instance_identity()` at `create_app()` time during the targeted render test. This is a known dashboard app behaviour, not a code issue.
- The 60-second in-process cache in `get_llm_usage()` means the warning can lag up to 60 seconds behind an actual token expiry — acceptable as noted in the design doc.
- No test file exists yet for this feature (`tests/dashboard/test_usage_fragment.py` will be added in S05).
