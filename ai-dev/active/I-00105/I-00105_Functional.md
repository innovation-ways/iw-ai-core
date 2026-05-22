# I-00105 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds one migration (a new optional field recording a runtime's maximum output size); the daemon applies it.

## Why

A development step run by an automated agent failed partway through because the agent's runtime ran out of working memory (its context window). The runtime quietly tried to recover and kept going in a degraded state instead of stopping cleanly, so the step left half-finished, partly corrupted work behind and needed manual rescue. This was first seen on a runtime with a comparatively small context window. The goal is to stop steps from silently overflowing, and to make the dashboard tell the truth about how full a step's working memory really is.

## What Changed (for the User)

- The dashboard's per-step context gauge now reflects the runtime's **usable** budget. Previously it showed a comfortable-looking figure (around two thirds full) at the very moment a step was actually out of room. After this change the gauge accounts for the space a model must reserve for its own output, so a near-full step now reads as near-full.
- Large outputs from a step's tools (file reads, command output, test runs) no longer pile up unbounded in the agent's working memory. When a single output is very large, the full content is saved to a file and the agent is handed a short preview plus the file location, so it can still go back and read the rest when it needs to.
- Steps compact their working memory earlier — before they hit the hard ceiling rather than after — which keeps them from tipping over mid-task.
- If a step genuinely runs out of room despite these safeguards, it now stops cleanly with a clear reason instead of limping on and leaving corrupted work behind — a failed step is now recognisable as failed and can be retried.

## How It Behaves

When a step runs, the system measures how full the runtime's working memory is against the budget the runtime can actually use, not its headline capacity. As the step works, any oversized tool result is set aside to a file and replaced in working memory by a brief preview and a pointer to that file; the agent can re-open the file at any time. As the step approaches its usable budget, it compacts older history proactively. If a step still overflows its budget despite these measures, the system now recognises that failure and ends the step cleanly with a clear blocker, instead of letting it continue in a broken state. A runtime that does not publish an output-size figure is treated conservatively — the gauge simply behaves as it does today rather than failing. Nothing changes about which model or runtime a step uses.

## Out of Scope

- Sending steps to a larger or different model — explicitly excluded.
- Breaking large steps into smaller ones — handled separately as its own change request.
