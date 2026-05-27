# CR-00083 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by the new perf tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds no migrations.

## Why

Today nothing in the platform measures how long anything takes. The daemon's polling loop, the Q&A flow that lets users ask questions of their own code, and the main dashboard pages can all silently get slower release after release — the only way anyone notices is when it becomes painful enough for a human to complain. That window can stretch into weeks. This work adds a small, dedicated layer of performance checks that run every night, compare against a saved reference measurement, and shout if anything has slowed down meaningfully.

## What Changed (for the User)

- Operators get an early-warning signal: a nightly run alerts the team when the polling loop, a code-search query, or one of the main dashboard pages takes noticeably longer than the saved reference.
- Reviewers gain a new check during code review: if a change in the platform is going to slow the system down, the nightly run will flag it within a day, before users feel it.
- End users see no change in the dashboard itself. There are no new pages, no new buttons, no new behaviour in the UI, and no impact on existing flows.

## How It Behaves

A new set of measurements runs every night on a fresh, seeded copy of the platform. Three things are measured: one full pass of the background daemon's polling cycle, one end-to-end question against the code-understanding feature, and the response time of five high-traffic dashboard pages. Each measurement is compared against a saved reference. If anything is slower than the reference by more than a generous threshold, the nightly run fails and an entry is added to the testing tracker so a human can investigate.

The thresholds are deliberately generous to start — the goal is to catch real regressions, not to chase noise from runner variability. As confidence in the measurements grows, the team can tighten the thresholds. Updating the saved reference is only ever done by an operator and requires a change request, so no one can quietly silence an alert by re-baselining a slowdown.

The measurements do not run on every change submitted for review — that surface is too noisy at the per-change scale. They run nightly only, where the signal is reliable. An operator can also trigger them on demand from the project's automation panel.

## Out of Scope

- Heavy load or stress testing — the goal here is regression alerting, not capacity planning.
- Performance budgets for end-user browser rendering (page-load metrics, Web Vitals).
- Per-pull-request performance gating — deferred until the nightly measurements have built enough history to be trustworthy at that granularity.
