# F-00090 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies.

## ⛔ Migrations: agents generate, daemon applies

This work adds a database migration. Agents generate the revision; the daemon applies it.

## Why

The dashboard's loudest metric today is throughput — items merged per week. Throughput on its own is misleading: shipping fast but breaking things is a worse outcome than steady shipping with very few regressions. Operators have asked for a second dimension so the dashboard can be read at a glance. This work adds it: every bug filed gets linked back to the merge that introduced it, and the resulting weekly regression rate sits next to throughput.

## What Changed (for the User)

- Each Incident detail page gains a "Regression classification" form: pick the merge that introduced the bug, optionally paste a commit hash, and pick one of three labels (regression, pre-existing, unknown).
- If the system has a guess about which merge caused the regression, the form shows an "Accept suggestion" button so the operator can confirm with one click.
- A new "Quality KPIs" section appears on each project's home (and has a dedicated page of its own). It shows three numbers for the current week — merges, regressions, and the rate — plus a small trend chart for the last twelve weeks.
- On the Batches and History views, every merged item blamed for one or more regressions shows a small badge with the count.
- A new operator command asks the system to suggest the most likely introducing merge for any given incident, and can accept the top suggestion in one shot.
- A one-off operator script sweeps every existing incident and populates suggestions so the team can triage the backlog without doing each one by hand.

## How It Behaves

The operator opens an Incident, picks "regression", and either selects a merge from the searchable dropdown or accepts the system's top guess. The form posts back without reloading and the row updates inline.

The Quality KPIs section shows the current week's merges, regressions, and rate (regressions divided by merges). When a week has zero merges, the rate is shown as zero rather than an error. The trend chart plots whatever history exists — if the project is only four weeks old, four weeks are shown.

The regression badge on Batches and History rows updates automatically as new classifications come in. A merge with zero attributions shows no badge.

The suggestion engine looks at the files the incident's fix touched and walks the recent history of those files; it ranks merges by how often they appear. It can be wrong — the operator is always the source of truth — so the system never persists a classification without an explicit operator action, either a click in the form or the accept flag on the command.

## Out of Scope

- Automatic classification without operator confirmation.
- Cross-project regression analytics; the new metric is per-project only.
