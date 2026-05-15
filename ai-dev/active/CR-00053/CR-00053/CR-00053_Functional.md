# CR-00053 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This change adds one new migration that introduces a small audit table.)

## Why

Today, when something asks the platform for a fresh work-item ID, it gets a brand-new number every single time — even when the caller is just retrying after a network blip or a transient error. The first allocation is silently wasted. That has been a low-cost annoyance so far, but it gets more visible the moment the platform exposes a chat panel that can retry on the user's behalf without the user noticing. This change makes ID allocation safe to retry without leaking numbers.

## What Changed (for the User)

- A new option on the next-ID command lets a caller hand in an idempotency tag. If the same tag is presented again later, the system returns the same ID it returned the first time, instead of allocating a fresh one.
- Old usage is completely unchanged. Anything that doesn't pass the tag keeps getting fresh sequential IDs exactly like today.
- The audit table preserves an honest record of every keyed allocation, so support can answer "did this run ask for an ID twice?" with a single look.

## How It Behaves

- With no tag, the platform behaves exactly as it does today: each call increments the counter and returns the next number.
- With a tag the platform has never seen before, the platform allocates a fresh number and remembers the tag-to-number pairing.
- With a tag the platform has already seen, the platform returns the previously-allocated number and does not move the counter.
- A given tag is scoped per ID kind. Asking for a research ID with tag "abc" and asking for a feature ID with tag "abc" are independent — both get their own fresh allocation, both get remembered separately.
- If two callers try to claim the same tag at the same time, exactly one wins the allocation and the other receives the winner's number. There is no scenario where both get distinct numbers behind the same tag.

## Out of Scope

- The two related platform commands that already behave idempotently on their IDs are not changed in this work — only the next-ID allocator gets the new option.
- The upcoming dashboard chat panel uses this option but is delivered as a separate piece of work.
