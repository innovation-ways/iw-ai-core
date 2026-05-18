# I-00097 S02 — Code Review Report

## What was reviewed

S01 (frontend-impl) implemented two small Jinja2 template polish changes for
the `/project/{id}/auto-merge` page:

1. **Smart $0 formatting** in `auto_merge_rollup.html` — zero-cost renders as
   `$0` instead of `$0.000000`.
2. **entity_id linkification** in `auto_merge_event_row.html` — work-item IDs
   (matching `^(F|I|CR)-\d{5}$`) render as links to
   `/project/{project_id}/item/{entity_id}`.

## Pre-review quality gates

| Gate | Result |
|------|--------|
| `make lint` | PASS — all checks passed |
| `make format` | PASS — 750 files already formatted |
| `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` | PASS — 25/25 passed |

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/auto_merge_rollup.html:22` | Smart $0 formatting (inline conditional + `.rstrip('0').rstrip('.')`) |
| `dashboard/templates/fragments/auto_merge_event_row.html:5–14` | Conditional linkification via `work_item_id` filter |
| `dashboard/app.py:349–360` | New `_is_work_item_id` Jinja2 filter registered |

## Review checklist

### 1. Zero-cost formatting ✅

```jinja
{% set _cost = token_cost_rollup.total_cost_usd %}{% if _cost == 0 %}$0{% else %}${{ ("%.6f"|format(_cost)).rstrip('0').rstrip('.') }}{% endif %}
```

- `total_cost_usd == 0` renders `$0` — correct.
- Non-zero values strip trailing zeros via `.rstrip('0').rstrip('.')` — e.g.
  `$0.000123` instead of `$0.000123000000`. Full precision preserved for
  non-zero values.

### 2. Linkification regex ✅

Pattern in `app.py:351`:
```python
_work_item_re = _re.compile(r"^(F|I|CR)-\d{5}$")
```

- Anchored with `^` and `$` — won't match `iw-ai-core`, `CR-005` (too short),
  `CR-000571` (6 digits), or partial strings.
- Defined once in a single helper (`_is_work_item_id` in `app.py`) and called
  as a filter in the template — no duplication.

### 3. URL pattern ✅

Template uses:
```jinja
<a href="/project/{{ request.path_params.project_id }}/item/{{ _eid }}" ...
```

Verified against `dashboard/routers/items.py:45` and `:1124`:
- Router: `router = APIRouter(prefix="/project/{project_id}")`
- Route: `@router.get("/item/{item_id}", ...)` → full path
  `/project/{project_id}/item/{item_id}` — matches the template href exactly.

### 4. Null handling ✅

```jinja
{% if _eid and (_eid | work_item_id) %}
  <a>link</a>
{% elif _eid %}
  {{ _eid }}
{% else %}
  —
{% endif %}
```

- `entity_id is None` → `—` ✅
- `entity_id` set but doesn't match pattern → plain text ✅
- `entity_id` matches pattern → link ✅

### 5. Tailwind CSS classes ✅

- `text-primary` — used elsewhere in the codebase (queue, history, etc.) ✅
- `hover:underline` — used elsewhere in the codebase ✅

### 6. No `| safe` added ✅

entity_id is rendered as `{{ _eid }}` (auto-escaped) inside the `<a>` tag.
No `| safe` filter is present anywhere in the changed templates.

### 7. Jinja2 `format`-filter `%`-style ✅

`"%.6f"|format(_cost)` — uses `%`-style formatting, enforced by
`scripts/check_templates.py` in `make lint`.

### 8. No tampering with other columns ✅

- Verdict column (lines 16–31) — unchanged.
- Message column (line 15) — unchanged.
- Actions column (lines 33–35) — unchanged.
- Filter row — not present in this fragment.

## Test verification

All 25 tests in `tests/dashboard/test_auto_merge_routes.py` pass, including any
new tests added for these acceptance criteria.

## Findings

No mandatory fixes required. The implementation is correct and complete.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00097",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "25/25 passed in tests/dashboard/test_auto_merge_routes.py",
  "notes": "S01 correctly implements both polish fixes: (1) $0 renders as $0 for exact-zero cost, non-zero costs strip trailing zeros; (2) entity_id is linkified only when it matches ^(F|I|CR)-\\d{5}$ and links to the correct /project/{id}/item/{eid} route. No violations of CLAUDE.md conventions or design document requirements."
}
```