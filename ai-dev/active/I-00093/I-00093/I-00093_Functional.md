# I-00093 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

Operators investigating an auto-merge resolver event open the event
detail dialog expecting to see what happened — the message the daemon
emitted, the model and latency for a health probe, the old-versus-new
config diff for a settings change, the LLM call summary for a
resolution. Today the dialog shows only four fields, none of which
answer those questions. Operators close the dialog without learning
anything they didn't already know from the table row, which makes the
whole "(view)" link feel decorative.

## What Changed (for the User)

- The detail dialog now shows the event's message text in full, not
  just the truncated preview from the table row.
- The full metadata payload is rendered as readable, pretty-printed
  JSON inside a collapsible block. Operators can see all the details
  the daemon recorded without leaving the page or reading raw DB rows.
- For events that already supported it (auto-resolved merges), the
  side-by-side diffs and the verdict form continue to render exactly
  as before, but now sit alongside the new metadata view.
- The dialog heading describes the event in human terms — its event
  type and timestamp — instead of an internal numeric ID.
- A "Copy as JSON" button next to the metadata block puts the whole
  payload on the clipboard so operators can paste it into chat,
  tickets, or scripts.

## How It Behaves

Clicking "(view)" on any row in the events table fetches the same
detail fragment as before, but the rendered dialog now lays out:

1. A humanized title at the top — "Auto-merge config updated —
   2026-05-17 23:13:55", for example.
2. A summary row of small facts (timestamp, type, entity, project).
3. The event's message text if it has one.
4. The full metadata payload as collapsible JSON. The block is
   collapsed by default for very large payloads (more than a few
   lines) and expanded otherwise.
5. Resolved-merge events keep their existing diff section and verdict
   form below.

Closing the dialog (Escape, clicking outside, or the ✕ button)
behaves exactly as today.

## Out of Scope

- A richer diff viewer replacing the current `difflib.HtmlDiff` output
  (would belong to a separate feature, not a bug fix).
- Filtering or searching within the metadata block.
- Linking entity_id values to their work-item detail page — covered by
  a sibling polish incident.
