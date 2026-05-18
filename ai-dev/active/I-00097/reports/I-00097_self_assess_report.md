### Item Analysis: I-00097

Bottom line: S12's E2E fixture seeds a DaemonEvent with `entity_id="CR-00057"` but not the corresponding WorkItem row, causing the verified link to 404 — an ENV_DATA_MISSING that is invisible until browser verification runs.

Steps analyzed: 13   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes

[1] E2E fixture missing WorkItem row for V2 link-target entity_id
    Severity: MED   Class: environment   Frequency: one-off
    Evidence:
      - ai-dev/active/I-00097/reports/I-00097_S12_BrowserVerification_Report.md:19 — "Failed to load resource: the server responded with a status of 404 (Not Found) @ http://localhost:9948/project/iw-ai-core/item/CR-00057:0 — this is the V2 navigation to `/item/CR-00057` which is a legitimate 404 since CR-00057 is not a DB row (only the DaemonEvent was seeded)"
    Recommendation: Ensure the E2E fixture for browser-verification steps seeds both the DaemonEvent row AND the corresponding WorkItem row so the link target exists. For CR-type entity_ids, use the project_factory to create the WorkItem first.
    Target: ai-dev/active/I-00097/e2e_fixtures/001_daemon_events.py
    Pros: Browser verification would confirm the full link-navigation round-trip works, not just that the link structure is correct.
    Cons: Slightly more complex fixture; adding a WorkItem row to what was a DaemonEvent-only seed.
    If we don't: Every future browser-verification step that links to a work-item entity_id will 404 in the E2E environment, making it look like a code defect when it's a fixture gap.
    Effort: S (~5 lines in fixture file)