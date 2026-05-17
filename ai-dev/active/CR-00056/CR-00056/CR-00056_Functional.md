# CR-00056 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds one migration (two new optional columns on the step-run records).

## Why

Operators currently have no way to see, from the dashboard, what prompt was actually sent to an AI agent for a given step. Today the only options are SSHing into the worktree or — once the item is merged and the worktree is reaped — there is no option at all. This makes it hard to debug why an agent took a wrong turn, validate prompt-engineering changes, or share context with teammates. The goal is to make every prompt directly viewable from the item's detail page, even months after the item has shipped.

## What Changed (for the User)

- A new **Prompt** column appears in the steps table on every item-detail page, sitting between the existing Model and Status columns.
- Each step row shows a small **View** button when a prompt is available, or a dash when there is none (synthetic setup/merge rows, or historical items from before this change).
- Clicking View opens a centred dialog that displays the full prompt text, scrollable, in a monospaced font.
- A **Copy** button on the dialog copies the visible prompt to the clipboard.
- Pressing **Escape**, clicking outside the dialog, or clicking the close button dismisses it.
- For steps that needed fix-cycle retries, the dialog shows the initial prompt **and** each fix-cycle prompt stacked below it, clearly labelled (Initial Prompt, Fix Prompt cycle 1, etc.).

## How It Behaves

When a new work item runs, the orchestration daemon saves a snapshot of each prompt directly into the database the moment a step is launched. From then on, the prompt is permanently viewable from the dashboard, regardless of whether the worktree still exists. Items completed before this change keep working as usual; their step rows simply show a dash in the new column because no snapshot was ever captured. Loading the dialog is on-demand — the prompt text is only fetched when a user actually clicks View, so pages with many steps still load quickly. The dialog is keyboard- and screen-reader-friendly: focus is trapped inside while it is open, and returns to the View button when it closes.

## Out of Scope

- Adding the Prompt column to the batch detail or history pages.
- Backfilling prompts for historical items that completed before this change.
- Syntax highlighting or diffing of prompt text inside the dialog.
