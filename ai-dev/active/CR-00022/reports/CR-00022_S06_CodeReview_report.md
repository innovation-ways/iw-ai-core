# CR-00022 S06 Code Review Report

## Verdict: `request_changes`

---

## Findings

### CRITICAL

#### 1. `skills/iw-oss-publish/scripts/checks/contributor.py:48` — Syntax error prevents AST parsing

**File:** `skills/iw-oss-publish/scripts/checks/contributor.py`
**Line:** 48
**Severity:** CRITICAL

The `else:` at line 48 is unreachable. The nested `if`/`else` structure at lines 20–47 fully handles all cases when `mode_cfg == "DCO"` — the outer `else` (line 48) would pair with `if mode_cfg == "DCO":` at line 20 but is never reached because the inner `if dco_cfg:` / `else:` block already exhausts the DCO branch. Python raises `SyntaxError: invalid syntax` when parsing this file.

**Impact:** The AST walker in the CI completeness test cannot parse `contributor.py`, so OSS-CA-01, OSS-CA-02, and OSS-CA-03 are invisible to the automated check.

**Recommended fix:** The unreachable `else` block (lines 48–63) was likely intended to handle `mode_cfg == "CLA"` (non-DCO mode). The structure should be flattened:

```python
if mode_cfg == "DCO":
    if dco_cfg:
        out.append(Finding(id="OSS-CA-01", status=Status.PASS, ...))
    else:
        out.append(Finding(id="OSS-CA-01", status=Status.FAIL, auto_fix_available=True, auto_apply_safe=True, ...))
else:
    # CLA mode branch
    out.append(Finding(id="OSS-CA-01", status=Status.PASS if cla_cfg else Status.HUMAN_REQUIRED, ...))
```

---

#### 2. `dashboard/services/oss_check_catalog.yaml:873` — Malformed URL (leading space)

**File:** `dashboard/services/oss_check_catalog.yaml`
**Line:** 873
**Check:** `OSS-HYG-01`
**Severity:** CRITICAL

Reference URL has a leading space:
```
https:// OWASP.org/community/www-project-api-security/asvs/latest/doc/4.0/0x10-app-security-best-practices/
```
Should be:
```
https://OWASP.org/community/www-project-api-security/asvs/latest/doc/4.0/0x10-app-security-best-practices/
```

The leading space makes the URL invalid — `curl` returns no output for it.

**Recommended fix:** Remove the leading space from the URL.

---

#### 3. `dashboard/services/oss_check_catalog.yaml` — Orphan catalog entries (OSS-CA-01, OSS-CA-02, OSS-CA-03)

**File:** `dashboard/services/oss_check_catalog.yaml`
**Lines:** 6–18 (OSS-CA-01), 19–27 (OSS-CA-02), 28–37 (OSS-CA-03)
**Severity:** CRITICAL (catalog completeness)

The YAML contains 3 entries that the AST walker cannot associate with any `Finding(id=...)` constructor in the check modules, because `contributor.py` has a syntax error and could not be parsed. Running the AST walk gives:

```
Missing from catalog: []
Extra (orphan) in catalog: ['OSS-CA-01', 'OSS-CA-02', 'OSS-CA-03']
```

These entries exist in the YAML but their IDs could not be extracted from Python source, so the CI completeness test (referenced in the YAML itself at line 3 as `tests/unit/test_oss_catalog_completeness.py`) would fail when run against this codebase.

**Recommended fix:** Fix the syntax error in `contributor.py` so the AST walker can extract the 3 IDs, then re-run the AST walk to confirm the orphan set becomes empty.

---

### HIGH

#### 4. `dashboard/services/oss_check_catalog.yaml:687` — 404 URL (OSS-GH-12)

**File:** `dashboard/services/oss_check_catalog.yaml`
**Line:** 687
**Check:** `OSS-GH-12`
**Severity:** HIGH

Reference URL:
```
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-the-default-branch-value
```
Returns `HTTP/2 404`. The GitHub docs path for this topic has changed or the URL was mistyped.

**Recommended fix:** Find the correct URL for the GitHub documentation about merge commit settings and update the reference.

---

### MEDIUM

#### 5. Brand voice — `OSS-CH-02` risk_if_failing

**File:** `dashboard/services/oss_check_catalog.yaml`
**Check:** `OSS-CH-02`
**Severity:** MEDIUM

The `risk_if_failing` field contains three sentences and two line breaks. While not egregious, the phrasing "Security vulnerabilities in the project go unreported..." is slightly more paragraph-like than the norm across the rest of the catalog. The field reads as one long paragraph rather than the 2–4 concise sentences used elsewhere.

**Recommended fix:** Tighten to 2–3 sentences; split across one or two short lines.

---

## Checklist Summary

| Item | Result |
|------|--------|
| 1. Catalog completeness | **FAIL** — 3 orphaned entries (OSS-CA-01/02/03) due to unparseable contributor.py |
| 2. Field completeness | **PASS** — no blank/TODO/TBD values in 10 random spot-checks |
| 3. Brand voice | **PASS** (minor note on OSS-CH-02) |
| 4. References quality | **FAIL** — 1 malformed URL, 1 404 URL |
| 5. Loader correctness | **PASS** — Pydantic v2, @cache+debug, Path(__file__).parent, clear errors, None on miss |
| 6. auto_apply_safe assignments | **PASS** — consistent with design table; defaults conservative at False |
| 7. Persistence wiring | **PASS** — `auto_apply_safe` correctly written at `persistence.py:59`, migration `c062b6bf5eb3` adds column |
| 8. No silent fallbacks | **PASS** — `get_copy()` returns `None` on miss; no domain-level fallback |

---

## Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `dashboard/services/oss_check_catalog.py` | 1–48 | ✅ |
| `dashboard/services/oss_check_catalog.yaml` | 1–1359 | ⚠️ URLs + orphans |
| `skills/iw-oss-publish/scripts/lib/types.py` | 1–57 | ✅ |
| `skills/iw-oss-publish/scripts/checks/contributor.py` | 1–110 | ❌ Syntax error |
| `skills/iw-oss-publish/scripts/checks/community.py` | 1–264 | ✅ |
| `skills/iw-oss-publish/scripts/checks/hygiene.py` | 1–254 | ✅ |
| `skills/iw-oss-publish/scripts/checks/license_check.py` | 1–207 | ✅ |
| `skills/iw-oss-publish/scripts/checks/github.py` | 1–288 | ✅ |
| `skills/iw-oss-publish/scripts/checks/secrets.py` | 1–175 | ✅ |
| `skills/iw-oss-publish/scripts/checks/dependencies.py` | 1–264 | ✅ |
| `orch/oss/persistence.py` | 1–111 | ✅ |
| `orch/db/models.py` | 1620–1639 | ✅ (auto_apply_safe at 1627) |

---

## Required Actions Before Approval

1. **Fix syntax error** in `contributor.py` — restructure the if/else so `mode_cfg == "CLA"` is a proper branch, not an unreachable `else`
2. **Remove orphan catalog entries** — after fixing contributor.py, re-run AST walk and confirm `missing=[]` and `extra=[]`
3. **Fix malformed URL** at line 873 — remove leading space before `OWASP.org`
4. **Fix 404 URL** at line 687 — find correct GitHub docs path for OSS-GH-12 merge-commit setting
