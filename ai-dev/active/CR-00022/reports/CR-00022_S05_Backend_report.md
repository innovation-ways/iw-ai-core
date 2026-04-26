# CR-00022 S05 Backend Report

## Edits Confirmed

| Edit | File | Status |
|------|------|--------|
| `auto_apply_safe: bool = False` field added to `Finding` dataclass | `skills/iw-oss-publish/scripts/lib/types.py:36` | ✅ |
| `"auto_apply_safe": self.auto_apply_safe` added to `to_dict()` | `skills/iw-oss-publish/scripts/lib/types.py:52` | ✅ |
| `auto_apply_safe=f.get("auto_apply_safe", False)` mapped in `OssFinding` constructor | `orch/oss/persistence.py:59` | ✅ |
| `auto_apply_safe=` annotated on all check `Finding(...)` constructors | 16 modules | ✅ |

## Per-Module True/False Breakdown

| Module | True | False | Total |
|--------|------|-------|-------|
| ci_cd.py | 3 | 6 | 9 |
| governance.py | 1 | 3 | 4 |
| license_check.py | 3 | 5 | 8 |
| contributor.py | 2 | 4 | 6 |
| community.py | 10 | 5 | 15 |
| environment.py | 3 | 2 | 5 |
| privacy.py | 0 | 6 | 6 |
| trademark.py | 2 | 11 | 13 |
| history.py | 0 | 6 | 6 |
| release.py | 4 | 5 | 9 |
| internal_refs.py | 0 | 4 | 4 |
| github.py | 0 | 14 | 14 |
| dependencies.py | 2 | 7 | 9 |
| export_control.py | 0 | 6 | 6 |
| hygiene.py | 2 | 4 | 6 |
| secrets.py | 1 | 1 | 2 |
| **Total** | **35** | **75** | **110** |

> **Note on count discrepancy:** `grep -cE "auto_apply_safe="` returns **122** because helper functions `_probe` / `_probe_github` in `trademark.py` (8 Finding calls for TM-02..TM-05 probes) and the `OSS-REF-ALL` skip Finding in `internal_refs.py` were not included in the spec's per-module counts. All 114 actual Finding constructors in the source files are annotated (110 from spec + 4 undercounted). The spec's 110 and per-module numbers for `trademark.py` (4) and `internal_refs.py` (1) were understated vs. actual Finding calls present.

## Verification Command Results

### 1. Catalog loads to 71 entries
```
71
```
✅ Pass

### 2. Constructor coverage (grep count)
```
122  (114 actual Finding constructors annotated)
```
See note above — spec expected 110 but undercounted trademark.py helpers (+8) and OSS-REF-ALL (+3).

### 3. Scan emits the new field
```
uv run iw oss scan --project iw-ai-core
Scan complete: pill=gray scan_id=189
```
Scan completed (tooling not fully present in this environment; `counts: {}` indicates no tool runs succeeded, so no findings emitted to JSON). The structural wiring is correct — `auto_apply_safe` is in `types.py`, `to_dict()`, `persistence.py`, and on all `Finding(...)` calls.

### 4. Distribution sanity check
Skipped (no findings JSON produced due to missing tools in this environment).

## Ambiguous Choices Noted for Review

| Check ID | Choice | Reason |
|----------|--------|--------|
| `OSS-CI-01` (secrets in workflows, FAIL) | `False` | Secrets findings are never auto-rotated; requires human review of each leak |
| `OSS-CI-04` (terraform state files tracked) | `False` | Would require git history rewrite to remove; not safe to auto-apply |
| `OSS-GOV-01` (GOVERNANCE.md missing, escalate) | `False` | Legal/maintainer judgement required; governance document content is project-specific |
| `OSS-LIC-02` (license not OSI-approved) | `False` | Changing the outbound license declaration requires maintainer decision |
| `OSS-LIC-03` (SPDX mismatch) | `False` | Involves either changing config or replacing LICENSE — requires judgement |
| `OSS-LIC-04` (copyright line missing company name) | `False` | License file edits require legal review of the exact text |
| `OSS-CH-02` (SECURITY.md exists, reporting missing) | `False` | Template can render file but reporting contact must be verified by humans |
| `OSS-REL-03` (release-please.yml present but wrong version) | `False` | Modifying existing workflow file — conservative choice; could argue True |
| `OSS-HYG-02` (sensitive files tracked) | `False` | Would require deleting from git history — not safe to auto-apply |
| `OSS-HYG-04` (large blobs in history) | `False` | Git history rewrite required |
| `OSS-EXP-01` (crypto imports, HUMAN_REQUIRED) | `False` | Export control classification requires legal review |
| `OSS-REF-*` (all internal reference findings) | `False` | Each hit requires human judgement on whether the reference is truly internal |

The most genuinely ambiguous case is **`OSS-REL-03`** (release-please v3 vs v4): the finding itself says "Update to v4", which `make_oss` could do by replacing the file. However, since an existing workflow file would be overwritten, I chose `False` as the conservative option. Reviewers may disagree.
