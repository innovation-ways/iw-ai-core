# I-00121 — Functional Design

## ⛔ Docker is off-limits

Standard policy. This work does not touch Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves the database structure unchanged.

## Why

When viewing test results on the dashboard, almost every test category showed "Report unavailable" with no pass-or-fail breakdown. Only a few categories produced a viewable report. This was discovered while fixing a related results-view bug. The goal is to make every test category produce a viewable report and a pass/fail summary, so the team regains full visibility into test outcomes across the whole suite rather than just a handful of categories.

## What Changed (for the User)

- After running any test category from the dashboard, that run now produces its own detailed report and pass/fail summary — not just the few categories that worked before.
- The results view stops pointing at reports that were never actually produced. When a run genuinely has no report, the system records that honestly instead of advertising a broken link.
- Selecting different runs in the results dropdown now consistently shows each run's own outcome.

## How It Behaves

When a test run finishes, the platform now reliably collects the detailed results that the report viewer needs, regardless of how that category's tests are launched. It then builds the report and reads the pass/fail totals from it.

If, for any reason, a run still produces no results to build a report from (for example a category that does not run automated tests, or a run that failed before producing output), the run is recorded as having no report rather than being linked to an empty location. In that case the results view shows a clear "report unavailable" state and, where totals could not be read, a short note that detailed statistics are not available — while still identifying which run is selected.

Categories that already worked continue to work exactly as before; nothing about their behaviour changes.

## Out of Scope

- This work does not change which tests run, how often they run, or whether they pass — only whether their reports and summaries are captured and shown.
- It does not retroactively rebuild reports for historical runs that completed before the change; the improvement applies to runs going forward.
