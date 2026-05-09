# CR-00039 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged — no database schema is modified.

## Why

The Step Pipeline section on the item detail page is supposed to give operators a quick
visual summary of how a work item progressed through its steps. In practice the coloured
squares are only 6 pixels wide, making it impossible to tell one step from another. A
separate row of timing labels below the squares is misaligned with the squares themselves,
causing all duration strings to run together into a single unreadable string. Additionally,
when a fix cycle is triggered and a step runs two or three times, all of those runs collapse
into a single square — so there is no way to see that retries happened just from the pipeline
view. The operator must scroll down to the table and count the "Runs" column, which defeats
the purpose of the visual overview.

## What Changed (for the User)

- Each step in the pipeline strip now shows its step label (S01, S02, S03, etc.) as
  readable text inside a pill-shaped block.
- The duration for each step appears on a second line inside the same pill — no separate
  misaligned row below the strip.
- When a fix cycle is triggered and a step runs again, an additional amber pill labelled
  with a recycle arrow and the step ID (for example ↺S03) appears immediately after the
  original step pill. A step that ran three times shows three pills in a row.
- The connector between a regular step and its fix-cycle reruns uses a dashed style so
  the retry relationship is immediately recognisable.

## How It Behaves

When an operator opens an item that completed cleanly, the pipeline strip shows one green
pill per step in order: S00, S01, S02, and so on through MERGE. Each pill displays the
step ID and its duration (for example "7m44s") on a second line.

When an item had fix cycles, the affected steps appear expanded. For example, if S03 was
retried twice the strip shows: … S02 (green) → S03 (green or red, first run) → ↺S03
(amber, second run) → ↺S03 (amber, third run) → S04 (green) … The amber colour and the
↺ prefix make fix-cycle reruns immediately distinguishable from original runs. Hovering
over any pill shows a tooltip with the full step name, status, and duration.

Steps that are pending, skipped, in progress, or failed retain their existing colours
(grey, muted, blue/pulsing, red) in the new pill format.

## Out of Scope

- Per-run durations for individual fix-cycle reruns (the current data model exposes only
  the aggregate duration per step; per-run breakdown remains available in the step table
  below and the Fix Cycles tab).
- Proportional pill widths based on duration — all pills are the same fixed width.
