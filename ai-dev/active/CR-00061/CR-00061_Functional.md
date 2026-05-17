# CR-00061 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Quarantine and flake-detection runs reuse the existing test-container fixtures; no new container management.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

Test flakiness is inevitable in a suite that shares state via session-scoped fixtures and runs subprocess-backed integration tests. Today the team has no process for it: a flaky test either gets retried until it passes, gets silently ignored, or gets hidden behind an ad-hoc marker that nobody tracks. Real bugs guarded by the flaky test stop being caught, and the team has no list of what is currently un-tested. This change makes the workflow explicit: an intermittently-failing test is quarantined out of the merge gate so it no longer blocks work; an incident is filed so the cause is tracked in the same backlog as every other open issue; an on-demand command tests whether the failure has recovered; and a separate nightly command runs the suite three times and reports any test that disagreed with itself.

## What Changed (for the User)

A new test marker is registered. The merge gate automatically skips any test that carries it, so a flaky test no longer blocks merges while under investigation. A new on-demand command runs only the quarantined tests so the team can see when a flake has recovered. A second on-demand command runs the full suite three times and reports any test that disagreed across runs. The testing strategy document, the test guidelines, and the agent-facing testing skill are updated to make the quarantine workflow non-discretionary: quarantining a test requires filing an incident, the incident's identifier goes in the marker reason, and a quarantined test that has passed consistently for three runs or a week can be un-quarantined. Existing test commands, the existing order-dependent quarantines, and the dashboards are unchanged. The testing enhancement plan and changelog record the change.

## How It Behaves

A developer who finds a test intermittently failing in a way they cannot immediately fix files an incident describing the suspected cause, adds the new quarantine marker to the test with the incident identifier in the marker's reason, and merges. From that point the test no longer blocks the merge gate. The on-demand quarantine command, run later, executes only the quarantined tests with a single retry on failure; if the test passes consistently across the next few invocations or week, the marker can be removed and the incident closed as not-reproducible. The nightly flake-detection command runs the full suite three times, captures the results, and reports any test whose outcome differed across runs — that report is the input to the file-an-incident-and-quarantine workflow. The pre-existing order-dependent quarantines continue to work unchanged: they are excluded from the merge gate by the same mechanism, and the testing guidelines explain the relationship between the two marker flavours.

## Out of Scope

Wiring the nightly flake-detection into a scheduled cron, migrating existing order-dependent quarantines to the new marker, and adding any per-test flake-rate dashboard are deferred. Closing or root-causing any flake the detector surfaces during this change's review is also deferred to follow-up incidents — the workflow lands cleanly first.
