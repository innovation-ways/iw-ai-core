# CR-00085 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work introduces no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database migration. The new check reads existing model declarations.

## Why

The platform's database schema reference is hand-maintained narrative writing — it describes every table and column in human-readable terms. Nothing forces an engineer to update it when a new column is added, so the reference drifts away from reality. Today no automated check notices when a column lacks a written description, and the drift accumulates silently over months. The sister InnoForge project already runs an equivalent check and uses it to keep its own schema reference accurate; this work brings the same discipline to the IW AI Core platform. The tracker has carried this item as a "to do" since the testing-strategy plan was filed.

## What Changed (for the User)

For day-to-day users (operators, dashboard viewers, support staff) nothing visible changes. The change is behind the scenes — a new automated check that runs alongside the existing quality checks.

For engineers adding columns to the platform's models, two things change. First, a new automated check surfaces any column on its violation list if the engineer did not attach a human-readable description. During an initial burn-in period the check runs in advisory mode — it prints warnings but does not block the build — so the change is non-disruptive. Second, the project's internal testing playbook now records the rule and explains how to address a warning correctly (by writing a real description on the column, not by silencing the check).

## How It Behaves

The new check inspects every column on every database model the platform declares, asking one question of each: does it carry a written description? If the column already has a description, or if it appears on a frozen baseline list of today's known undocumented columns, it is considered acceptable. Any other column is flagged.

The frozen baseline freezes today's debt — it is not an "accepted forever" list, it is the cleanup backlog. The correct way to remove a column from the baseline is to write a real description on the column declaration, never to silence the check by adding another entry.

When an engineer adds a brand-new column without a description, the check flags it as a new violation. During burn-in this is advisory only; once burn-in ends in a follow-up change, the check becomes blocking and the engineer is required to add a description (or have a strong reason not to) before the change can merge.

## Out of Scope

- Writing real descriptions for the existing undocumented columns. That is a separate cleanup effort scheduled as a follow-up item.
- Editing the schema reference document. The check exists to keep that document honest over time; cleaning up its current state is not part of this work.
- Flipping the check from advisory to blocking. That is the follow-up item's responsibility, after the cleanup backlog has shrunk to a meaningful size.
