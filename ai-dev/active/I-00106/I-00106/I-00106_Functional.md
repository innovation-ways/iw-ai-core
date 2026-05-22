# I-00106 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged — it is a display-only fix with no database change.

## Why

When someone opens a work item on the dashboard, the steps table has a Logs column. Clicking it opens the Agent Session Log — a window that shows everything the agent did during that step. Today that window lists events oldest-first: the very first thing the agent did sits at the top, and the most recent activity is hidden at the bottom. For long-running or still-running steps the reader has to scroll all the way down to find out what is happening now, and the window keeps adding fresh content below the fold every few seconds. The goal is to make the latest activity immediately visible without scrolling.

## What Changed (for the User)

- The Agent Session Log window now shows the newest activity at the top and the oldest at the bottom.
- A reader opening the window sees what the agent is doing right now first, instead of what it did at the start.
- For a still-running step, every automatic refresh keeps the latest activity in view at the top rather than pushing it further down.
- A light divider line now separates one agent turn from the next, so it is clear where each turn begins and ends.

## How It Behaves

The agent's work is shown as a series of turns. A turn is one cycle of the agent reasoning, using its tools, and then giving a reply. The window now lists the most recent turn first and the oldest turn last.

Inside each turn nothing is shuffled: the reasoning, the tool calls, the tool results, and the final reply still appear in the natural order they happened. Only the order of the turns relative to each other is flipped. So a reader scanning from the top sees the newest turn in full, then the turn before it, and so on back to the beginning of the step.

If the step is still running and its latest turn has not finished yet, that unfinished turn appears at the very top. A context-compaction marker — a note that the agent's memory was summarised — still appears as its own separator between turns. For step runs whose log is a single plain text dump rather than structured turns, the individual lines of that dump are also flipped so the newest line is on top.

If a step has no readable log yet, the window still shows its usual "no log content" message. Steps that are still running still refresh on their own every few seconds, now keeping the newest turn at the top after each refresh.

## Out of Scope

- The separate Logs tab on the item page is not changed — it already shows its newest lines first.
- The window does not try to remember a reader's scroll position across automatic refreshes; with the newest content at the top, the top is the natural place to land.
