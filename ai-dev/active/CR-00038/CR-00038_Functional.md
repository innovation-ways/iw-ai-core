# CR-00038 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. Schema is unchanged.

## Why

The documentation library page has two UX problems that reduce trust in the platform. First, the filter controls span three stacked rows of pill buttons, making the page feel cluttered and wasting valuable screen space above the doc cards. Second, clicking Generate or Regenerate on a doc shows a spinner that never stops — even after the job finishes — because the UI has no mechanism to detect when the background job completes. Users must manually refresh the page to see the updated document, which makes the generation feature feel broken.

## What Changed (for the User)

- The three-row filter area (Type pills, Status pills, search box) is replaced by a single compact row with two dropdown selects (Type and Status) and a search box, all on one line. All filters combine — switching the type while a status is selected keeps both active.
- A new running-jobs strip appears between the filter row and the doc cards whenever a generation job is in progress. Each active job gets one row showing the doc name, a live elapsed timer, and a Cancel button.
- Clicking Generate or Regenerate immediately disables the button (it goes grey with a small spinner and "Queued…" text) so the user knows the request was accepted.
- When a job finishes — successfully or with an error — its row disappears from the strip and the corresponding doc card refreshes automatically. A successful finish updates the card's status badge; a failure shows the "Last run failed" warning badge.
- Multiple jobs running at the same time each get their own row in the strip.

## How It Behaves

A user navigating to the docs page sees the compact filter row at the top. Selecting "Architecture" from the Type dropdown immediately filters the grid; selecting "Published" from the Status dropdown further narrows it; typing in the search box refines again — all three work together.

The user clicks Regenerate on a doc card. The button turns grey instantly. A new row appears in the running-jobs strip with the doc title and a ticking elapsed timer. The daemon picks up the job, runs the doc-generator skill, and marks the job complete. The running-jobs strip detects the completion via a background connection and removes that row. The doc card automatically refreshes, showing the new version date and an updated status badge. If the job fails, the strip row briefly turns red before disappearing and the card shows the "Last run failed" badge.

If the user leaves and returns to the docs page while a job is still running, the running-jobs strip reloads and reconnects — the in-progress row reappears.

## Out of Scope

- The doc detail page (individual doc view) is not changed; its existing job-status panel is unaffected.
- No changes to how jobs are created, scheduled, or executed by the daemon.
