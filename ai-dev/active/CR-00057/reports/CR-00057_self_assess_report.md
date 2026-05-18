### Item Analysis: CR-00057

Bottom line: tighten workflow-level handoff contracts (agent names, report naming, and browser env bootstrap) so retries are spent on product behavior rather than orchestration friction.

Steps analyzed: 16   Steps with retries: 4   Total fix-cycles: 13   DB signal: yes

[1] Self-assess agent mapping fallback hides intended specialist behavior
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00057_S16_run1.log:1 — "agent \"self-assess-impl\" not found. Falling back to default agent"
      - ai-dev/logs/CR-00057_S16_run1.log:3 — "> build · gpt-5.3-codex"
    Recommendation: Add startup validation that every workflow `opencode_agent` resolves to an installed agent before step launch; fail fast with a clear remediation hint.
    Target: orch/daemon/batch_manager.py
    Pros: Prevents silent behavior drift on mandatory governance steps; reduces false confidence in step ownership.
    Cons: Adds one preflight validation branch to launch flow.
    If we don't: Mandatory self-assess steps can run under fallback agents with inconsistent quality and incomplete contracts.
    Effort: S   (~20-40 lines, 1-2 files)

[2] Browser verification environment bootstrap gap (registry sync path not runnable)
    Severity: HIGH   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00057_S15_run1.log:33 — "docker compose -p \"$COMPOSE_PROJECT_NAME\" exec app ... sync_projects_from_toml ..."
      - ai-dev/logs/CR-00057_S15_run1.log:34 — "service \"app\" is not running"
      - ai-dev/active/CR-00057/reports/CR-00057_S15_QvBrowser_report.md:7 — "Attempted remediation path ... but `app` service was not running."
    Recommendation: Update the browser verification prompt/template to include the supported E2E reseed command for this stack layout (no hardcoded `app` service assumption).
    Target: templates/design/steps/browser_verification.md
    Pros: Removes a deterministic env failure path; makes V1-V5 checks reproducible.
    Cons: Requires keeping template aligned with compose naming conventions.
    If we don't: QV browser runs continue burning fix-cycles on stack wiring instead of validating acceptance criteria.
    Effort: S   (~15-30 lines, 1 file)

[3] Report naming and path convention drift causes avoidable read failures
    Severity: MED   Class: convention   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00057_S03_run1.log:51 — "Read ... CR-00057_S02_API_report.md failed"
      - ai-dev/logs/CR-00057_S03_run1.log:52 — "Error: File not found"
      - ai-dev/logs/CR-00057_S03_run1.log:55 — "Did you mean ... CR-00057_S02_Api_report.md"
    Recommendation: Standardize step report filename casing in step templates and enforce with a lightweight validator during `step-done`.
    Target: orch/cli/step_commands.py
    Pros: Reduces cross-step friction; improves deterministic handoffs.
    Cons: Slightly stricter filename contract for contributors.
    If we don't: Agents keep spending time recovering from avoidable path/casing mismatches.
    Effort: S   (~20-50 lines, 1-2 files)

[4] Retry-heavy QV sequence indicates orchestration instability around late gates
    Severity: HIGH   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/CR-00057_S16_run1.log:38 — "CR-00057_S10_run10.log"
      - ai-dev/logs/CR-00057_S16_run1.log:74 — "CR-00057_S13_run10.log"
      - ai-dev/logs/CR-00057_S16_run1.log:86 — "CR-00057_S14_fix1.log" (also through `S14_fix7.log` and `S14_run22.log` in the same listing)
    Recommendation: Emit per-step retry budget telemetry and auto-summarize top recurring retry causes at each gate transition (S10-S15).
    Target: orch/daemon/fix_cycle.py
    Pros: Makes retry causes visible early; improves targeted fixes in prompts/platform.
    Cons: Additional telemetry plumbing and small report payload growth.
    If we don't: Late-stage gates continue to consume significant execution time with low diagnostic visibility.
    Effort: M   (~80-160 lines, 2-4 files)

Coverage notes: Read S01/S02/S03/S05/S15/S16 logs in full (all <1 MB). Sampled S14 fix-cycle behavior from index evidence in S16 run inventory plus S14_fix1 excerpt due log volume. Primary evidence is raw logs; step reports used only as secondary corroboration.
