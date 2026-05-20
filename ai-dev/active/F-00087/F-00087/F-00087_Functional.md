# F-00087 — Functional Design

## Why

The multi-tab AI Assistant ships with one selectable runtime: OpenCode. The user wanted Pi as a second option so they can compare runtimes side by side and pick the one that fits the task. Pi's smaller per-turn context budget and different model line-up make it useful for cheap-and-fast tabs, while OpenCode remains the default for tabs that need its broader plugin and approval surface. This Feature wires Pi in as a peer runtime in the same chat panel; the choice is per tab, not project-wide.

## What Changed (for the User)

- The "Runtime" dropdown in the create-tab modal now offers two options: OpenCode (default) and Pi.
- Picking Pi populates the model dropdown with Pi-specific models drawn from the platform's runtime catalogue.
- A Pi tab behaves like an OpenCode tab: same composer, same streaming output, same abort button, same per-tab model selector, same approval modal when a risky tool call is gated.
- Approval prompts on Pi tabs use the same policy as OpenCode tabs — the project's existing approval rules apply to both runtimes without any duplicate configuration.
- Pi tabs persist across page reloads. The Pi-side conversation history is preserved and resumed when the tab is reopened.
- The platform manages a small pool of Pi backends. When the user has more Pi tabs than the pool allows, the least-recently-used tab quietly releases its backend; clicking it later spins a fresh backend that resumes the conversation. No data loss.
- If a Pi tab sits idle for fifteen minutes, the platform releases its backend; reactivating respawns transparently.

## How It Behaves

In the create-tab modal, choosing Pi swaps the model list to Pi's catalogue; choosing OpenCode swaps it back. The model dropdown above the composer in an active tab is locked to that tab's runtime — switching runtime means closing the tab and creating a new one.

When a Pi tab sends its first prompt, the platform starts a Pi backend in the background; subsequent prompts reuse it. Mixing one OpenCode tab and several Pi tabs is routine. Aborting a prompt in one tab never disturbs another, and sending prompts in two tabs at the same time runs both conversations in parallel.

If a tool call on a Pi tab matches an "ask" policy, the same approval modal the user knows from OpenCode appears, showing the tool and its arguments. Approve releases the call; deny stops it.

If the Pi binary is missing from the user's environment, creating a Pi tab returns a clear error and no tab is created. Existing tabs are unaffected. If a Pi backend dies mid-stream, the tab shows an error event; the next prompt restarts the backend automatically.

## Out of Scope

- Sandboxing of Pi tool execution; Pi runs with the user's permissions like the existing OpenCode flow.
- Automatic conversion of existing OpenCode tabs into Pi tabs; users create new Pi tabs explicitly.
- Branching or forking of Pi session trees; Pi sessions render as linear conversations like OpenCode sessions.
