# I-00091 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no migrations.

## Why

The Auto-Merge Resolver settings panel quietly contradicts itself. When an
operator overrides only one knob — e.g. choosing dry-run mode but leaving
the runtime on global default — reloading re-displays both dropdowns as
"Use global default" even though the chosen setting is in fact saved and
active. Saving also gives no visible feedback, because the panel only
refreshes a small status badge elsewhere. Operators end up second-guessing
whether the platform "took" their change, which erodes trust in a feature
whose whole purpose is letting humans drive the auto-merge resolver safely.

## What Changed (for the User)

- Each dropdown (Phase and Runtime) now independently reflects what is
  actually saved. Overriding one without overriding the other is now a
  first-class state and shows up correctly on reload.
- The settings card now refreshes in place when the user clicks Save,
  including the dropdowns and the small "last changed" footer line. A
  brief "Saved" hint appears next to the button so the operator gets
  immediate visual confirmation.
- The status badge at the top of the page now accurately describes which
  axis is using a per-project override and which is using the global
  default, instead of collapsing the two into a single misleading label.
- Clearing both dropdowns back to "Use global default" and saving removes
  the per-project override entirely (it is no longer "stuck") and the
  footer changes back to "Using global default".

## How It Behaves

The settings card always renders from the truth in the database. The
panel computes two independent answers — "is phase overridden for this
project?" and "is the runtime overridden for this project?" — and uses
those two answers separately to decide which option appears as selected
in each dropdown. So the four observable states are:

- Neither axis overridden — both dropdowns show "Use global default";
  footer reads "Using global default".
- Phase only — Phase shows the chosen value (e.g. "1 — dry-run"); Runtime
  shows "Use global default"; footer reads "Last changed: … by dashboard".
- Runtime only — Runtime shows the chosen model; Phase shows "Use global
  default"; footer reads "Last changed: …".
- Both — both dropdowns show their chosen values; footer reads "Last
  changed: …".

On Save, the panel posts the form, then swaps the entire settings card and
the page-top status badge in a single response. The operator never sees a
full-page reload; they see the dropdowns settle to the just-saved values
plus a brief "Saved" affirmation that fades after a few seconds.

## Out of Scope

- Other auto-merge view bugs found in the same audit — filter chip not
  highlighting the active filter, event detail modal showing only four
  fields, wrong cursor on chip/link hover, missing column sort, status
  chip duplication, and entity-id linking — are filed as separate
  incidents and are not addressed here.
- No changes to the resolver's actual behaviour (what events it emits,
  what files it touches, when it fires). This is a UI/UX correctness fix
  only.
