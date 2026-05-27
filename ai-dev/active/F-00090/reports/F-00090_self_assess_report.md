### Item Analysis: F-00090

Bottom line: Add a platform-level guard that detects non-actionable fix cycles (PID-dead reviewer crashes / out-of-scope stale-head failures) and auto-escalates instead of looping retries.

Steps analyzed: 17   Steps with retries: 7   Total fix-cycles: 16   DB signal: yes

[1] Fix-cycle thrash on non-actionable failures
    Severity: HIGH   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00090_S06_fix2.log:3 — "Process exited without reporting completion (PID dead)"
      - ai-dev/logs/F-00090_S06_fix3.log:5 — "crash of the review agent itself"
      - ai-dev/logs/F-00090_S15_fix7.log:10 — "test hardcodes _HEAD_REVISION ... current head is d43ea9e75e8f"
    Recommendation: Add daemon/executor detection for repeated identical non-actionable diagnostics and auto-escalate/mark blocked after N cycles.
    Target: orch/daemon/step_monitor.py
    Pros: Cuts wasted cycles and queue time; clearer operator signal.
    Cons: Needs careful pattern matching to avoid false positives.
    If we don't: Similar items will burn multiple fix cycles without new information.
    Effort: M   (~2 files)

[2] Browser verification prompt had wrong compose service name
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00090_S16_run1.log:9 — "docker compose ... exec app"
      - ai-dev/logs/F-00090_S16_run1.log:10 — "service \"app\" is not running"
      - ai-dev/logs/F-00090_S16_fix1.log:8 — "running service is e2e-dashboard, not app"
    Recommendation: Update browser verification prompt template to parameterize compose service name (or reference canonical env command).
    Target: templates/design/Feature_Design_Template.md
    Pros: Prevents environment false-fails in browser steps.
    Cons: Small template churn.
    If we don't: Future items may repeat the same S16 startup failure.
    Effort: S   (~1 file)

[3] Migration-head pinning made integration gate brittle
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00090_S15_fix2.log:6 — "hardcode an older expected head (2be8dc12874f)"
      - ai-dev/logs/F-00090_S15_fix2.log:15 — "expected head 2be8dc12874f vs actual d43ea9e75e8f"
    Recommendation: Replace hardcoded head revision assertion with dynamic `alembic heads`/helper resolution in the integration test.
    Target: tests/integration/daemon/test_phase2_apply_no_self_deadlock.py
    Pros: Stops migration-related false failures after legitimate new revisions.
    Cons: Minor test refactor.
    If we don't: Integration gate will keep breaking on new migrations.
    Effort: S   (~1 file)

[4] TDD RED evidence contract drift in behavior-step reporting
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00090/reports/F-00090_S05_Backend_report.md:27 — "## TDD RED evidence"
      - ai-dev/active/F-00090/reports/F-00090_S05_Backend_report.md:30 — "test_backfill_persists_no_classifications"
    Recommendation: Enforce step-specific TDD field policy in implementation prompt templates (S01/S05 must emit `n/a — ...`; S02/S03/S04 must include real RED run evidence).
    Target: templates/design/Feature_Design_Template.md
    Pros: Consistent auditability across steps.
    Cons: Slightly stricter prompt output contract.
    If we don't: Self-assessment and QA interpretation of RED discipline remains inconsistent.
    Effort: S   (~1 file)
