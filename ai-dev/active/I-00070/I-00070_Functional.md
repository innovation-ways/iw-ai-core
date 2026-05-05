# I-00070 — Functional Design

## ⛔ Docker is off-limits

Standard policy. No container operations are required.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work introduces no migrations.

## Why

Team members open the orchestration dashboard from their own laptops via the LAN hostname (for example over plain HTTP). On those connections, every "copy to clipboard" button on the dashboard silently does nothing — clicks register but the text never reaches the clipboard, and the button gives no feedback. The bug was first reported on the new "Copy paste prompt" buttons inside the Self-Assessment finding cards, where it defeats the whole point of presenting a ready-to-paste command. The same silent failure affects the OSS install commands, OSS CLI snippets, and chat copy actions, so anyone who is not physically on the dashboard host cannot use any copy button.

## What Changed (for the User)

- Every copy button on the dashboard now works regardless of whether the dashboard is opened on the dashboard host itself or from a remote machine over plain HTTP.
- After clicking, the button briefly displays "Copied" so the user gets immediate confirmation.
- If the copy still fails for any reason (for example the user's browser blocks both clipboard paths), the button now shows "Copy failed" instead of pretending nothing happened. The text the user wanted to copy is still readable on screen so they can select it manually.
- Behaviour for users who already access the dashboard from the host machine is unchanged in every visible way.

## How It Behaves

When a user clicks any copy-to-clipboard button on the dashboard, the dashboard first tries the modern browser clipboard interface. If the browser refuses that interface — which happens whenever the dashboard is served over plain HTTP from a hostname other than the local one — the dashboard falls back to a long-standing alternative copy mechanism that does not require a secure connection. Either way, the user sees the same visible response: the button label briefly switches to "Copied", then reverts to its original label after about a second and a half. If both paths fail, the label briefly switches to "Copy failed" instead. The text being copied is always rendered visibly next to the button, so manual selection remains a fallback.

## Out of Scope

- Switching the dashboard to HTTPS. That is a separate operational decision and would also fix this class of bug, but it is not what this incident addresses.
- Adding new copy buttons or changing where existing buttons appear.
