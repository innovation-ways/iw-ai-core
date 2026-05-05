# I-00068 — Functional Design

## Why

Operators noticed that on the project dashboard's Recent Activity card, clicking a batch identifier on a "Batch X archived successfully" row took them to a 404 page. The same batch identifier on the row immediately above ("Batch X archiving started") worked correctly. The asymmetric behaviour — same identifier, two different and inconsistent destinations — undermines trust in the activity feed and silently strands users on an error page during an otherwise successful flow.

## What Changed (for the User)

- Clicking a batch identifier from any row in the Recent Activity card now opens the batch detail page, no matter which event row it came from.
- The "Batch archived successfully" row, which previously led to a 404 error, now navigates to the same batch detail page as every other batch row.
- All other event rows behave exactly as before. Work-item rows still go to the work-item page; document-job rows still go to the document-job page.

## How It Behaves

When an event row in the Recent Activity card includes a batch identifier (a value starting with `BATCH-`), the dashboard always renders the link to point at the batch detail page. This is true whether the event source already records the row as a batch event explicitly, or whether the source omits that classification — in the second case, the dashboard recognises the identifier shape and chooses the correct destination on its own.

Behind the scenes, the platform now also records new archive events with the correct event classification ("batch") so the dashboard does not have to fall back to identifier-shape recognition for new rows. Older rows already in the database continue to work because the dashboard's recognition rule applies to them as well.

For non-batch identifiers (work items, change requests, document jobs), the existing routing is unchanged.

## Out of Scope

- Backfilling or rewriting historical activity rows that were stored before this fix. The dashboard handles them transparently; no migration is performed.
- Auditing every code path in the platform that writes activity rows. This change targets the specific archive code that produced the broken rows and adds a defensive rule on the dashboard side. A wider audit can be done in a future change request if needed.
