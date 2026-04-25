# CR-00022_S16_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S15 (CI workflow honor)
**Review Step**: S16
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S15 report
- `.github/workflows/compliance-scan.yml`
- `.claude/skills/iw-oss-publish/scripts/honor_accepted.py`
- `docs/IW_AI_Core_OSS_Accepted_Risk.md`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S16_CodeReview_report.md`

## Review Checklist

### 1. Hash consistency

- `honor_accepted.py:compute_finding_hash` produces byte-for-byte identical output to `dashboard/services/oss_accepted.py:compute_finding_hash`?
- Both use SHA-256, both truncate to 16 hex chars, both include null separators, both serialise evidence with sorted keys + compact separators?
- Any divergence is CRITICAL — the dashboard would write entries the CI cannot match.

Test: run both functions over the same `(check_id, summary, evidence)` tuple and compare.

### 2. Workflow correctness

- Honor step runs AFTER scan SARIF is produced and BEFORE upload?
- Recompute step exits non-zero only when unaccepted MUST findings remain?
- Both steps tolerate the absence of `.iw/oss-accepted.yaml`?
- `actions/checkout@<sha>` still pinned by SHA?
- Python heredoc syntax correct (no interpolation surprises)?

### 3. Edge cases

- Workflow handles empty `accepted: []` array?
- Handles malformed YAML (treat as empty, log a warning, continue)?
- Handles a SARIF file with zero results?
- Handles a SARIF file with results that don't have an `evidence` property?

### 4. Removed unconditional fail

- The previous `Fail if secrets detected` step (line 74-78 of original `compliance-scan.yml`) is either removed or subsumed by the new recompute step?
- No double-gating (don't fail twice for the same finding)?

### 5. Doc

- `IW_AI_Core_OSS_Accepted_Risk.md` covers: purpose, schema, finding_hash semantics, dashboard accept flow, CI honoring flow, lifecycle (rewording invalidates accept entry)?
- Linked from `docs/IW_AI_Core_Architecture.md` table-of-contents (verify)?

### 6. SECURITY implications

- Does the doc warn that secret findings (OSS-SEC-*) CAN be accepted via this mechanism, with explicit caution that rotating the secret is the only correct action and acceptance should be temporary?

## Output Report

Findings list with severity. End with verdict + step-done/fail.
