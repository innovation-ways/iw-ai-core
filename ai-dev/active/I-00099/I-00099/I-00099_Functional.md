# I-00099 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
-->

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item leaves migrations unchanged.)

## Why

When several work items run in parallel across different batches, the platform keeps a safety check that prevents two agents from editing files that would collide. The check was too aggressive: it held a new item back whenever it touched a different file that simply happened to live in the same folder as a file already being edited. This produced repeated false alarms in large folders like the docs area and the daemon module, and forced an operator to manually edit each blocked item's scope to unstick it. The problem was hit twice in one week and was getting worse as more batches ran at once.

## What Changed (for the User)

- New work items are no longer blocked just because they share a folder with an in-flight item. They are only blocked when they really overlap — either both items list the same file, or one item's wildcard reach covers a file the other writes.
- The hold message that operators see on the dashboard now always names a file that genuinely intersects between the two items. It no longer points at a file that wasn't actually a conflict.
- Operators no longer have to hand-edit an item's declared file list to unblock it from a same-folder neighbour. The only legitimate reason to edit that list is when the declaration is genuinely wrong.

## How It Behaves

When the daemon prepares to launch an approved item, it compares the new item's declared file list against every item currently in flight in the same project. If any pair of declarations names the same exact file, or one declaration's wildcard covers a file the other names, the new item is held and a "scope overlap" event is recorded so the operator can see who is blocking whom. If no such intersection exists, the new item launches even when its files happen to sit next to files another item is editing.

If a future case really does need two items to be serialised because they live in the same module, the team can declare it explicitly by using a wildcard such as the whole folder. The platform respects that declaration without imposing an automatic "shared folder = conflict" rule that was producing more noise than safety.

## Out of Scope

- Rewriting the overall cross-batch conflict model. The change is intentionally minimal — only the structural "shared parent folder" rule is removed.
- Back-filling or rewording old hold events recorded before this change shipped; those stay as historical record.
