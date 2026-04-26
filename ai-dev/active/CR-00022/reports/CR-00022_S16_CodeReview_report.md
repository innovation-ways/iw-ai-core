# CR-00022 S16 Code Review Report

## Step Reviewed: S15 (CI workflow honor)

## 1. Hash Consistency ✅

Tested `compute_finding_hash` in both:
- `dashboard/services/oss_accepted.py:35` (dashboard version)
- `.claude/skills/iw-oss-publish/scripts/honor_accepted.py:13` (CI version)

Both use SHA-256, null byte separators (`\x00`), JSON dumps with `sort_keys=True, separators=(",", ":")`, and truncate to 16 hex chars. **Byte-for-byte identical** across 4 test cases covering all three code paths (evidence dict, evidence null, empty dict).

## 2. Workflow Correctness ✅

- **Honor step** (lines 60-70) runs AFTER gitleaks/pinact scans produce SARIF, BEFORE upload — correct order.
- **Recompute gate** (lines 72-105) exits non-zero only when unaccepted MUST findings remain.
- **Absence of `.iw/oss-accepted.yaml`**: `honor_accepted.py` uses `args.accepted.exists()` guard; `recompute_gate` uses `accepted_path.exists()` guard — both tolerate missing file.
- **`actions/checkout@<sha>`**: Pinned to `34e114876b0b11c390a56381ad16ebd13914f8d5` ✅
- **Python heredoc** (line 76): `python3 - <<'PY'` — single quotes around delimiter prevents interpolation ✅

## 3. Edge Cases ✅

| Case | Behavior |
|------|----------|
| `accepted: []` empty array | `accepted.get("accepted", [])` → empty set, no downgrade, no-op |
| Malformed YAML | `yaml.safe_load` raises; `recompute_gate` catches via `or {}` fallback; `honor_accepted` has no try/except — would propagate. **Observation**: honor_accepted.py has no error handling for malformed YAML. Low risk (CI fail is acceptable for misconfiguration). |
| SARIF with zero results | `for result in run.get("results", [])` → empty iteration, no downgrade, no-op |
| SARIF result without `evidence` property | `result.get("properties", {}).get("evidence")` → `None`; hash uses `evidence is not None` branch → consistent with dashboard |

## 4. Removed Unconditional Fail ✅

The old `Fail if secrets detected` step (original lines 74-78) is **absent** from the current workflow. Secrets (GITLEAKS-*) findings now go through the same honor/recompute flow as OSS-CH findings — no double-gating.

## 5. Documentation ⚠️

`IW_AI_Core_OSS_Accepted_Risk.md` covers purpose, schema, hash semantics, dashboard flow, CI flow, and lifecycle. **Issue**: Not linked from `IW_AI_Core_Architecture.md` table of contents. The arch doc has no mention of the oss-accepted mechanism anywhere (verified via grep — zero matches for "oss-accepted" in the 1785-line arch doc).

## 6. Security ⚠️

The doc explicitly warns about secrets acceptance in a dedicated "Secrets Acceptance" section (lines 104-111). It states that for secrets in git history, acceptance records the risk but does not remove the secret, and a history rewrite may be required. **Good.**

However, the doc does **not** explicitly warn: "rotating the secret is the only correct action and acceptance should be temporary." The checklist item 6 requires this explicit caution.

---

## Findings Summary

| # | Severity | Area | Description |
|---|----------|------|-------------|
| 1 | MEDIUM | Doc | `IW_AI_Core_OSS_Accepted_Risk.md` not linked from `IW_AI_Core_Architecture.md` |
| 2 | LOW | Doc | "Secrets Acceptance" section does not include the explicit caution that rotating the secret is the only correct action and acceptance should be temporary |

---

## Verdict: PASS with notes

The implementation is correct. The two findings are documentation-only — the CI behavior is sound and the hash consistency is verified. Recommend fixing both doc issues before closing CR-00022.

**Step complete.**