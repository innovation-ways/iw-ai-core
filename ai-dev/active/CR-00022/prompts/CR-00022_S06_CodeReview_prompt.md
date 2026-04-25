# CR-00022_S06_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S05 (Phase B — catalog)
**Review Step**: S06
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules. Read-only.

## Input Files

- Design + S05 report
- `dashboard/services/oss_check_catalog.py`
- `dashboard/services/oss_check_catalog.yaml`
- `skills/iw-oss-publish/scripts/lib/types.py`
- `skills/iw-oss-publish/scripts/checks/*.py`
- `orch/oss/persistence.py`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S06_CodeReview_report.md`

## Review Checklist

### 1. Catalog completeness

Run the AST walk yourself to confirm every check ID is in the YAML:

```python
import ast, pathlib, yaml
ids = set()
for p in pathlib.Path("skills/iw-oss-publish/scripts/checks").glob("*.py"):
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
            for kw in node.keywords:
                if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                    ids.add(kw.value.value)
catalog = yaml.safe_load(open("dashboard/services/oss_check_catalog.yaml"))
missing = ids - catalog.keys()
extra = catalog.keys() - ids
print("missing:", sorted(missing))
print("extra (orphan):", sorted(extra))
```

Both sets should be empty. Any missing entries are CRITICAL findings.

### 2. Field completeness

Every catalog entry has non-empty `what_it_checks`, `how_it_tests`, `risk_if_failing`, `how_to_fix`. Spot-check 5 entries randomly. Any blank or placeholder values (`TODO`, `FIXME`, `...`) are HIGH findings.

### 3. Brand voice

Spot-check 10 entries. Are they:
- Plain English, no abbreviations without expansion?
- 2-4 sentences per field, not paragraphs?
- "Risk" framed as concrete consequences, not policy?
- "How to fix" stated as actions, not lectures?
- No emoji, no headline-case where sentence-case would be natural?
- Consistent with `doc-system/` editorial voice?

Flag voice issues at MEDIUM severity unless egregious.

### 4. References quality

Spot-check 5 entries with `references`. Are URLs:
- Reachable (curl head check is fine)?
- Authoritative (OpenSSF, GitHub docs, RFC, opensource.guide) — not random blogs?
- Specific (link to the page that explains the rule, not a top-level domain)?

### 5. Loader correctness

- Pydantic v2 syntax (not v1 `validator`)?
- `@cache` invalidates correctly when `IW_CORE_DEBUG=true`? (Verify by reading the code path — production cache should NOT short-circuit the debug branch.)
- `CATALOG_PATH` resolves regardless of CWD (uses `Path(__file__).parent`)?
- `load_catalog()` raises a clear error on malformed YAML?
- `get_copy(check_id)` returns `None` on miss (callers handle), not a default empty record?

### 6. `auto_apply_safe` assignments

For each check module:
- Every `Finding(...)` constructor now passes `auto_apply_safe`?
- Values reasonable per the design's table (template renders → True; secret rotation → False; etc.)?
- Defaults are `False` (conservative) where the check is ambiguous?

Flag any True assignment that could realistically modify the user's tracked source files in a non-idempotent way as HIGH.

### 7. Persistence wiring

- `orch/oss/persistence.py` writes `auto_apply_safe` from Finding to `OssFinding.auto_apply_safe`?
- Migration column from S01 is referenced (no orphan column)?

### 8. No silent fallbacks

- Code must NOT substitute domain-level copy when per-check copy is missing — the catalog is meant to be authoritative. Missing entry → completeness test fails in CI, not a soft fallback in production.

## Output Report

Findings list with severity, file:line, recommended fix. Verdict (`approve` / `request_changes`). End with `iw step-done` / `iw step-fail`.
