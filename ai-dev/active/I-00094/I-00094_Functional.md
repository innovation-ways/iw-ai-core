# I-00094 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

Every clickable element in the Auto-Merge Resolver view that uses an
htmx-only action — the filter buttons, the per-row view action, the
7d/30d window switchers, and the Prev/Next pagination — looks
unclickable. The mouse cursor stays as a text insertion bar instead of
the standard hand pointer when hovering. Keyboard users can't tab to
them at all, and screen readers don't announce them as actions. The
buttons work when clicked, but everything about how they present
themselves says "this is not a button". Operators routinely report
"clicking on a filter doesn't do anything" when they're actually
hovering over what they think is a label.

## What Changed (for the User)

- Hovering any filter chip, the per-row view action, the 7d/30d
  toggles, or the Prev/Next pagination now shows the hand-pointer
  cursor.
- Tab navigation reaches each of these elements; pressing Enter or
  Space activates them.
- Screen readers announce each as a button, including its label and
  pressed state where applicable (e.g. "resolved filter, pressed").
- All click behaviour is unchanged: same filter, same modal, same
  pagination.

## How It Behaves

Visually the controls remain pill-shaped chips and small text links —
identical to today. The only differences are interaction affordances:
hover cursor, keyboard focus ring (the dashboard's default focus style
takes over automatically), and assistive-technology announcement.
Existing operators won't notice any layout change; new operators get
the standard cues that say "you can click this".

## Out of Scope

- Visual redesign of the filter row, view link, or rollup toggles.
- Adding shortcut keys (no `accesskey` bindings introduced here).
