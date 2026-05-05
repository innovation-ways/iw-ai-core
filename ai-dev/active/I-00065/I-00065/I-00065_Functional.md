# I-00065 — Functional Design

## Why

The AI chat panel inside the project Code view has two small but visible defects that confuse first-time users and make the panel look unfinished. The "+ New" button leaks into the collapsed rail (where there is no chat to "start anew" because nothing is shown), and clicking "+ New" stacks duplicate "Ask about this module" greetings instead of producing a single fresh empty state. Both behaviours were noticed during routine inspection and reported by the product owner as polish issues that should be cleaned up before more eyes land on the page.

## What Changed (for the User)

- When the chat panel is collapsed to its narrow rail, only the rail icon and the rotated "Chat" label are visible. The "+ New" button no longer appears inside the rail.
- When the chat panel is expanded, clicking "+ New" still clears any prior chat history and shows the "Ask about this module" greeting — but exactly once, no matter how many times the button is clicked.
- All other chat behaviours are unchanged: composer, send, slash commands, message replay on expand, keyboard shortcuts, and image attachments all continue to work as before.

## How It Behaves

In the collapsed state, the chat panel acts purely as an entry point: a thin rail with an icon and a "Chat" label, and nothing else. Clicking the rail (or pressing Cmd+\) expands the panel into its full layout — header with title and "+ New" button, message list, and composer.

In the expanded state, the user can chat normally. When they want to start over, they click "+ New". The panel forgets the cached conversation, removes every chat bubble, and shows a single "Ask about this module" greeting with a one-line tip and a hint about slash commands. If they immediately click "+ New" again — perhaps absent-mindedly — nothing visibly changes: the panel is already in the empty state and there is still exactly one greeting on screen.

If the user collapses the panel after starting a new chat, the behaviour is the same as it has always been: the rail re-appears with no extra controls, and re-expanding the panel restores the empty state until the user types a new message.

## Out of Scope

- The wording, layout, or styling of the "Ask about this module" greeting itself is unchanged.
- The chat panel's keyboard shortcuts, composer behaviour, conversation replay, and image-attachment flows are not touched.
- This work does not introduce a confirmation dialog before clearing chat history — the "+ New" action remains immediate, matching today's behaviour.
