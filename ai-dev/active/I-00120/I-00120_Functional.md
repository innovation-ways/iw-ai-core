# I-00120 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This work leaves migrations unchanged.

## Why

The dashboard footer shows a Codex usage reading next to Claude and MiniMax. When the Codex sign-in credential stored by the local agent tool goes out of date or is no longer valid, the reading quietly drops to zero and looks exactly like genuinely having used nothing. The operator reported the Codex values were "stuck at 0%" and had no way to know the credential had lapsed. The goal is to replace that misleading zero with a clear, visible warning so the operator knows to re-authenticate.

## What Changed (for the User)

- When the Codex credential is expired or rejected, the Codex chip now shows a warning such as "token expired — re-authenticate" instead of a silent zero reading.
- When no Codex sign-in exists at all, the chip shows "not configured — run opencode auth login".
- When the usage service can't be reached for another reason, the chip shows "usage unavailable".
- When everything is healthy, the chip behaves exactly as before, showing the two usage bars with their percentages.

## How It Behaves

The footer refreshes about once a minute. On each refresh the system checks the Codex credential and the live usage reading. If the reading came back successfully, the two usage bars appear normally. If the credential is past its expiry or the usage service rejects it as expired, the bars are replaced by an amber warning telling the operator to re-authenticate. If there is no Codex sign-in on the machine, the warning instead says it is not configured. Any other failure to fetch the reading shows a generic "usage unavailable" warning. Because the reading is cached briefly, a freshly expired credential may take up to a minute to switch the chip into its warning state. The warning is informational only — nothing else on the dashboard changes, and the other providers' chips are unaffected.

## Out of Scope

- This work does not renew, refresh, or repair the Codex credential. Re-authentication is done by the operator. The change only makes the broken state visible.
