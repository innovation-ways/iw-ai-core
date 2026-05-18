# I-00097 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

Two small things on the Auto-Merge Resolver view feel half-finished.
The Token cost rollup always shows "$0.000000" on a project that
hasn't run any LLM calls yet — six decimal places of zero looks like a
display bug. And the entity_id column lists work-item IDs like
"CR-00057" as plain text, even though every other table in the
dashboard turns those into links straight to the item's detail page.
Operators end up copy-pasting the ID into the URL bar to navigate,
which they shouldn't have to do.

## What Changed (for the User)

- When the total token cost is exactly zero, it renders as "$0"
  rather than "$0.000000". When the total has real cents it still
  shows enough precision to read the number — including the very
  small sub-cent fractions auto-merge produces.
- Work-item IDs in the entity_id column (anything matching the
  IW pattern such as CR-00057, F-00084, I-00075) are now clickable
  links straight to that item's detail page.
- Other values in entity_id — project IDs, dashes, or anything that
  doesn't match the work-item pattern — stay as plain text. Only
  recognisable work-item IDs become links.

## How It Behaves

The rollup card formats a zero cost the same way a human would write
it. Small non-zero costs keep their fractional digits exactly as
today. Large costs would render in normal currency precision.

In the events table, an event referencing a work item ("Step S13
launched for CR-00057") shows the CR-00057 as a hyperlink coloured
the same as other links in the dashboard. Clicking it navigates to
that item's detail page. Events without a work item — a health
probe, a config update — keep showing the dash placeholder.

## Out of Scope

- Adding richer cost formatting (e.g. currency localisation, separator
  commas). Pure trim-trailing-zeros behaviour for now.
- Linking other identifier shapes (project_id, batch_id, runtime
  option ids). Only `F/I/CR-NNNNN` work-item IDs get the treatment.
