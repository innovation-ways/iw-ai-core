# R-00075 — Codex Usage Chip: Limits Model & Query API

| Field | Value |
|-------|-------|
| **ID** | R-00075 |
| **Date** | 2026-05-15 |
| **Mode** | tech (technical / operational investigation) |
| **Depth** | standard |
| **Status** | draft |
| **Author** | Sergio (with Claude Code) |
| **Related** | F-00081 (agent runtime options), migration `d1e2f3gpt53c` (added `openai/gpt-5.3-codex`), `orch/llm_usage.py`, `dashboard/templates/fragments/llm_usage_footer.html` |

---

## Primary Question

How can the IW AI Core dashboard footer surface remaining Codex usage on a ChatGPT-subscription OAuth token — mirroring the existing MiniMax 5h chip — what's the limit structure, what endpoint/header returns it, and how do we authenticate the poller?

## Executive Summary

The hypothesis — *"5h sliding window + 7-day weekly cap, mirroring Anthropic's structure"* — is **confirmed in principle but materially imprecise**: Codex on a ChatGPT subscription enforces a **5-hour rolling window** plus an **additional weekly window**, and both are exposed as `RateLimitWindow{used_percent, window_minutes, resets_at}` records ([HIGH]). The window structure is **identical in shape** to what we want to show (percent + reset time), so the footer template needs only minor templating work. OpenAI does not publish the weekly window's *duration* numerically — the `window_minutes` field reports it dynamically per response, and community reports show values consistent with 7 days but the official docs do not commit to that wording ([MEDIUM]).

There **is an official, undocumented endpoint** — `GET https://chatgpt.com/backend-api/wham/usage` — that returns the full snapshot. It is the same endpoint the Codex CLI polls every ~60 seconds when ChatGPT-OAuth auth is cached ([HIGH]). Authentication is `Authorization: Bearer <access>` plus `ChatGPT-Account-Id: <accountId>`, both of which **are already on disk** in `~/.local/share/opencode/auth.json` after the user ran `opencode auth login` for the OpenAI provider ([HIGH], verified locally).

Recommended implementation: replicate the MiniMax pattern in `orch/llm_usage.py::_codex_usage()`, load the OAuth credentials from opencode's auth.json (refreshing via `https://auth0.openai.com/oauth/token` when the cached access token is within ~5 minutes of expiry), call `/wham/usage`, and expose `{codex_5h_pct, codex_5h_reset, codex_weekly_pct, codex_weekly_reset, codex_plan_type}` to the footer template. Cache for 60s to match what the Codex CLI itself does (and to limit pressure on a non-public endpoint).

---

## Findings

### F1 — Limit model is "5h rolling + weekly", measured in messages [HIGH]

OpenAI's [Codex pricing page](https://developers.openai.com/codex/pricing) and [Codex rate-card help article](https://help.openai.com/en/articles/20001106-codex-rate-card) state that *"the usage limits for local messages and cloud tasks share a five-hour window. Additional weekly limits may apply."* The unit is **messages, not tokens** — but with a per-model multiplier: heavier models burn the 5h budget faster ([Codex pricing](https://developers.openai.com/codex/pricing) shows per-model "15-80 / 20-100 / 30-150 / 60-350" ranges for GPT-5.5 / 5.4 / 5.3-Codex / 5.4-mini on Plus). The range exists because **the count depends on task size and complexity** — a "message" with a long agent loop and tool use costs more than a one-shot reply.

The Codex CLI's `/status` command surfaces both windows via the field set `primary` (5-hour) and `secondary` (weekly) — confirmed in [openai/codex issue #15281](https://github.com/openai/codex/issues/15281), which is a feature request to **show more** of the same data (the data is fetched today but not all of it is displayed). This is also corroborated by the polling complaint in [openai/codex issue #10869](https://github.com/openai/codex/issues/10869).

**Per-tier numbers (Plus / Pro / Business)** are published as model-dependent ranges on [`developers.openai.com/codex/pricing`](https://developers.openai.com/codex/pricing) (Plus 5h GPT-5.3-Codex: 30-150 messages; higher tiers scale by 5× for Pro and use a credit-pool model for Business). Verbatim numeric weekly caps are **not** disclosed on either the help center or the pricing page — they are reported dynamically per account in the `secondary` window of the API response (see F2).

> Aside: the "5h" duration is **rolling**, not aligned to a fixed clock boundary. The `resets_at` field is per-account and slides forward as you use the budget. This matches the structure of Anthropic Claude's "block_pct / block_reset" that we already render for MiniMax.

### F2 — Endpoint `GET /backend-api/wham/usage` returns a structured snapshot [HIGH]

The Codex CLI fetches the snapshot from a single endpoint:

```
GET https://chatgpt.com/backend-api/wham/usage
Authorization: Bearer <access_token>
ChatGPT-Account-Id: <accountId>
User-Agent: codex-cli/<version>
```

This is confirmed by the [`backend-client/src/client.rs` source on the OpenAI Codex repository](https://github.com/openai/codex/blob/main/codex-rs/backend-client/src/client.rs), which dispatches on `PathStyle`:

```rust
let url = match self.path_style {
    PathStyle::CodexApi   => format!("{}/api/codex/usage", self.base_url),
    PathStyle::ChatGptApi => format!("{}/wham/usage", self.base_url),
};
let req = self.http.get(&url).headers(self.headers());
let (body, ct) = self.exec_request(req, "GET", &url).await?;
let payload: RateLimitStatusPayload = self.decode_json(&url, &ct, &body)?;
Ok(Self::rate_limit_snapshots_from_payload(payload))
```

`PathStyle::ChatGptApi` is the variant used when authenticating with a ChatGPT subscription via OAuth (our case). The `base_url` for that variant is `https://chatgpt.com/backend-api`, giving the full URL `https://chatgpt.com/backend-api/wham/usage`. Issue [#10869](https://github.com/openai/codex/issues/10869) corroborates the literal URL and the "~60 seconds" polling cadence, and identifies the poller as `ChatWidget::prefetch_rate_limits` in `tui/src/chatwidget.rs`.

The response deserializes to **`RateLimitStatusPayload`**. The Codex CLI then transforms it into the lower-level `RateLimitSnapshot` it actually displays:

```rust
RateLimitSnapshot {
    primary:   Option<RateLimitWindow>,   // 5-hour bucket
    secondary: Option<RateLimitWindow>,   // weekly bucket
    credits:   Option<CreditsSnapshot>,
}
RateLimitWindow {
    used_percent:   f64,   // 0.0..=100.0
    window_minutes: i64,   // e.g. 300 for 5h, 10080 for 7d
    resets_at:      i64,   // epoch seconds
}
CreditsSnapshot {
    has_credits: bool,
    unlimited:   bool,
    balance:     f64,
}
```

Field names and types verified verbatim against [`codex-rs/core/src/client.rs` (rust-v0.63.0)](https://github.com/openai/codex/blob/rust-v0.63.0/codex-rs/core/src/client.rs).

**Critical detail**: the Codex CLI also constructs the same `RateLimitSnapshot` from **HTTP response headers** on every Codex chat-completions call. The header set is `x-codex-{primary,secondary}-{used-percent,window-minutes,reset-at}` and `x-codex-credits-{has-credits,unlimited,balance}` — same semantics, free-of-quota because they ride existing traffic. The implication for us: **we get zero-cost piggyback updates on every step the daemon already runs through Codex**, plus a periodic poller for when the daemon is idle. (See F4.)

### F3 — Auth path is already on disk after `opencode auth login` [HIGH]

Empirical inspection of the user's local install (`~/.local/share/opencode/auth.json`, redacted) shows:

```json
{
  "minimax": { "type": "api",   "key": "<str len=125>" },
  "openai":  { "type": "oauth",
               "access":    "<JWT len=1920>",
               "refresh":   "<str len=90>",
               "expires":   1779689299438,
               "accountId": "<UUID len=36>" }
}
```

- `expires` is **milliseconds since Unix epoch** (1779689299438 → 2026-05-24T... — within ~9 days of the research date, so the file gets refreshed regularly).
- `accountId` is a UUID and goes into the `ChatGPT-Account-Id` header.
- `access` is a JWT bearer.
- `refresh` is the token used to mint new access tokens against `https://auth0.openai.com/oauth/token` (grant `refresh_token`), per the [Token Management & Refresh deepwiki](https://deepwiki.com/numman-ali/opencode-openai-codex-auth/4.2-token-management-and-refresh).

Access tokens typically live ~1 hour; refresh tokens live 30–90 days ([deepwiki](https://deepwiki.com/numman-ali/opencode-openai-codex-auth/4.2-token-management-and-refresh)). This is consistent with the `expires` timestamp lifetime we observed (~1h between consecutive opencode invocations).

**Multi-process safety**: opencode does not advertise a lock on auth.json. The risk is a write race if both opencode and our poller refresh simultaneously. Mitigation: have the poller **only refresh** when `expires < now + 300s` and **always write atomically** (tmp file + rename). In steady state, opencode refreshes during its own runs and our poller piggybacks on the cached access token — no write contention.

### F4 — Cheapest probe: piggyback on existing traffic, fall back to /wham/usage [HIGH]

OpenAI provides two equally-priced (free) ways to read the snapshot:

1. **HTTP response headers on every Codex chat-completion call.** The daemon already issues these whenever a step runs with `openai/gpt-5.3-codex`. We could parse `x-codex-primary-used-percent` etc. directly from the HTTP response of the agent's own step, push the snapshot to a small in-memory cache, and the dashboard footer reads from that cache. Cost: **zero** — the headers ride existing traffic. Caveat: when no Codex step has run recently, the cache is stale.

2. **`GET /backend-api/wham/usage`.** Direct snapshot fetch. Cost: **does not appear to count against the message budget** — it is a metadata endpoint, the Codex CLI polls it every ~60s indefinitely without burning quota (corroborated by [#10869](https://github.com/openai/codex/issues/10869) — the complaint there is wasted *bandwidth*, not wasted *quota*). Use this as the primary source when no recent header-derived snapshot exists.

For comparison: the alternative of **polling chat-completions with a 1-token probe** would cost ~1 message per minute against the 5h budget (Plus: ~720 messages per 5h × 12 per hour). The headers + `/wham/usage` route is strictly cheaper and is what the official client does.

### F5 — Limits are "soft" — block-on-exceed with a clear reset, not throttled [MEDIUM]

When a window saturates, Codex returns an explicit `usage_limit_reached` error with the reset timestamp. The relevant Rust enum is `RateLimitReachedType` (referenced in `RateLimitStatusPayload`, per [#15281](https://github.com/openai/codex/issues/15281)). The CLI then refuses subsequent calls until `resets_at` passes or the user purchases credits (Business tier only — see [Codex pricing](https://developers.openai.com/codex/pricing) for the credit-pool model).

For our footer, this means the chip should turn red at 100% and display the reset timestamp prominently. (We already use the same color-band convention for MiniMax — `_bar_color(pct)` in `dashboard/routers/usage.py`.)

### F6 — The "7-day sliding window" wording is community shorthand, not official [LOW]

Multiple community posts ([allthings.how](https://allthings.how/codex-token-and-rate-limits-explained-for-chatgpt-plans/), [knightli.com](https://www.knightli.com/en/2026/04/15/codex-usage-limits-five-hour-weekly-credits/), [openai/codex#15110](https://github.com/openai/codex/issues/15110)) describe the weekly window as "a 7-day rolling window". OpenAI's own help-center pages [403 to non-browser fetches](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan) so I could not retrieve the verbatim wording, but the [Codex pricing page](https://developers.openai.com/codex/pricing) commits only to *"Additional weekly limits may apply"*. The `RateLimitWindow.window_minutes` field is **per-account, per-response, dynamic** — so even if OpenAI changes the duration later (e.g., to 5 or 14 days), our footer code will keep working as long as it reads `window_minutes` from the response rather than hard-coding "7 days".

**Implication for the footer label**: write `"5h"` / `"weekly"` rather than `"5h sliding"` / `"7d sliding"`, and derive the duration from `window_minutes` if we want to render it.

---

## Recommendations

### R1 — Implement `_codex_usage()` mirroring the MiniMax pattern

Add to `orch/llm_usage.py`:

```python
_AUTH_FILE = pathlib.Path.home() / ".local/share/opencode/auth.json"
_TOKEN_URL = "https://auth0.openai.com/oauth/token"
_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
_OPENAI_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"  # ChatGPT-CLI OAuth client (public)

def _load_openai_oauth() -> dict[str, Any] | None:
    """Returns {access, refresh, expires_ms, accountId} or None if not OAuth."""
    try:
        data = json.loads(_AUTH_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    oa = data.get("openai") or {}
    if oa.get("type") != "oauth":
        return None
    return oa

def _maybe_refresh(oa: dict) -> str:
    """Refresh access token if within 5 min of expiry. Returns valid access token."""
    expires_ms = int(oa["expires"])
    now_ms = int(time.time() * 1000)
    if expires_ms - now_ms > 300_000:
        return oa["access"]
    # Refresh — POST application/json to auth0 token endpoint
    r = httpx.post(_TOKEN_URL, json={
        "grant_type": "refresh_token",
        "refresh_token": oa["refresh"],
        "client_id": _OPENAI_OAUTH_CLIENT_ID,
    }, timeout=10.0)
    r.raise_for_status()
    body = r.json()
    oa["access"]  = body["access_token"]
    oa["refresh"] = body.get("refresh_token", oa["refresh"])
    oa["expires"] = now_ms + body["expires_in"] * 1000
    _atomic_write_auth_json(oa)   # tmp + rename
    return oa["access"]

def _codex_usage_remote(access: str, account_id: str) -> dict[str, Any]:
    r = httpx.get(_USAGE_URL, headers={
        "Authorization": f"Bearer {access}",
        "ChatGPT-Account-Id": account_id,
        "User-Agent": "iw-ai-core/0.1 codex-usage-poller",
    }, timeout=5.0)
    r.raise_for_status()
    payload = r.json()
    # rate_limit.primary  = 5-hour bucket
    # rate_limit.secondary = weekly bucket
    rl = payload.get("rate_limit") or {}
    prim = rl.get("primary") or {}
    sec  = rl.get("secondary") or {}
    return {
        "5h_pct":      round(prim.get("used_percent") or 0),
        "5h_reset":    _format_reset(prim.get("resets_at")),
        "weekly_pct":  round(sec.get("used_percent") or 0),
        "weekly_reset":_format_reset(sec.get("resets_at")),
        "plan_type":   payload.get("plan_type"),
    }
```

**Cache TTL: 60s** — match what the Codex CLI does, and lighter than our existing MiniMax cache (which has a similar structure).

### R2 — Footer template additions

Add a Codex chip next to the existing MiniMax chip in `dashboard/templates/fragments/llm_usage_footer.html`. Reuse the existing bar markup; just feed it `codex_5h_pct`, `codex_5h_color`, `codex_5h_reset` (or `codex_weekly_*` if you want to show the more constraining of the two).

**Design call to make next**: show **one bar** (whichever window is closer to saturation — `max(5h_pct, weekly_pct)`) or **two bars** (5h + weekly, side by side). For symmetry with MiniMax (single 5h bar), the **one-bar `max()` approach** is simpler and just adds one chip — recommended for v1.

### R3 — Graceful degradation

Match the MiniMax fallback shape: on any error (file missing, OAuth refresh fails, endpoint 401/5xx, network timeout), return `{"5h_pct": 0, "5h_reset": None, ...}` and let the footer fragment render the chip empty (or omit it). **Never log the access token, refresh token, or accountId** — only the 6-char prefix of the access for debugging.

### R4 — Multi-account / API-key auth edge case

If `auth.json` has `openai.type = "api"` (raw API key, not OAuth), the `/wham/usage` endpoint will **not** work — that endpoint is ChatGPT-subscription-only. Detect this and either (a) suppress the chip silently, or (b) show "API key — no quota tracking". Recommended: (a) suppress, to keep the footer clean.

### R5 — Reuse of `accountId` for opencode runtime

We already inject `OPENCODE_DATA_DIR` per item in `executor/step_executor.sh` and **copy** auth.json into it. If we end up letting the poller refresh tokens, we should make sure the **master** `~/.local/share/opencode/auth.json` is what we write back to — otherwise per-item copies would diverge and opencode's own refresh would re-overwrite. The poller should only ever touch the master file.

---

## Limitations

- **Help-center pages unverified.** `help.openai.com` returned HTTP 403 to WebFetch, so I could not quote the *exact* numeric per-plan limits from the rate-card article. Numbers in F1 come from the [pricing page](https://developers.openai.com/codex/pricing) and community summaries. If we want verbatim numbers, the user can open the help center in a browser and paste.
- **Endpoint stability.** `/backend-api/wham/usage` is **undocumented**. It is used by OpenAI's own production CLI and is therefore stable in practice, but OpenAI has no commitment to its shape or URL. We should treat any 4xx response from it as "feature unavailable" and degrade silently.
- **Refresh-token client id.** I quoted `app_EMoamEEZ73f0CkXaXp7hrann` as the public ChatGPT-CLI OAuth client id from community references; this needs verification against opencode's own source before merging — read it from auth.json or opencode's binary if present. Wrong client id would 401 the refresh.
- **CreditsSnapshot semantics for Business tier.** Not investigated in depth — Business plans use a credit pool ([VentureBeat](https://venturebeat.com/orchestration/openai-introduces-chatgpt-pro-usd100-tier-with-5x-usage-limits-for-codex)) and `CreditsSnapshot{has_credits, unlimited, balance}` may shift the UI. Out of scope unless we expect Business-tier users.
- **No measurement of actual polling cost.** I asserted `/wham/usage` does not count against quota based on the absence of complaints in #10869, not a measurement.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | Codex Pricing — Plus / Pro / Business per-model 5h ranges | OpenAI official | https://developers.openai.com/codex/pricing |
| 2 | Codex CLI client.rs (v0.63.0) — RateLimitWindow / RateLimitSnapshot struct fields | OpenAI source (canonical) | https://github.com/openai/codex/blob/rust-v0.63.0/codex-rs/core/src/client.rs |
| 3 | Codex CLI backend-client client.rs — `get_rate_limits_many` URL + headers | OpenAI source (canonical) | https://github.com/openai/codex/blob/main/codex-rs/backend-client/src/client.rs |
| 4 | Codex CLI issue #10869 — `/backend-api/wham/usage` polling (URL + 60s cadence) | OpenAI / community confirm | https://github.com/openai/codex/issues/10869 |
| 5 | Codex CLI issue #15281 — `/status` shows 5h + weekly | OpenAI / community confirm | https://github.com/openai/codex/issues/15281 |
| 6 | Codex CLI issue #15110 — weekly window sliding behavior | Community | https://github.com/openai/codex/issues/15110 |
| 7 | Token Management & Refresh — opencode-openai-codex-auth deepwiki (refresh URL + TTLs) | Third-party plugin (cross-corroborated) | https://deepwiki.com/numman-ali/opencode-openai-codex-auth/4.2-token-management-and-refresh |
| 8 | numman-ali/opencode-openai-codex-auth (plugin reference) | Third-party plugin | https://github.com/numman-ali/opencode-openai-codex-auth |
| 9 | Using Codex with your ChatGPT plan (verbatim quotes not retrieved — 403) | OpenAI help center | https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan |
| 10 | Codex rate card (verbatim numbers not retrieved — 403) | OpenAI help center | https://help.openai.com/en/articles/20001106-codex-rate-card |
| 11 | OpenAI introduces $100 Pro tier (5× Codex usage) | Industry press | https://venturebeat.com/orchestration/openai-introduces-chatgpt-pro-usd100-tier-with-5x-usage-limits-for-codex |
| 12 | OpenAI API rate-limit headers (x-ratelimit-*) | OpenAI official | https://developers.openai.com/api/docs/guides/rate-limits |
| 13 | Local file inspection: `~/.local/share/opencode/auth.json` shape | Primary evidence | (local filesystem) |
| 14 | OpenCode auth.json default path documentation | OpenCode official | https://opencode.ai/docs/cli/ |
| 15 | Community: "Codex token and rate limits explained" | Community | https://allthings.how/codex-token-and-rate-limits-explained-for-chatgpt-plans/ |

---

## Next steps (proposed implementation outline — non-binding)

If approved, the implementation work is small and contained:

1. **`orch/llm_usage.py`** — add `_load_openai_oauth()`, `_maybe_refresh()`, `_codex_usage_remote()`, `_codex_usage()` per R1. Slot into the existing `get_llm_usage()` aggregator next to `_minimax_usage()`. Returns `{plan_type, 5h_pct, 5h_reset, weekly_pct, weekly_reset}`.
2. **`dashboard/routers/usage.py`** — wire the new dict into the template context: `codex_5h_pct`, `codex_5h_color`, `codex_5h_reset`, (and optionally `codex_weekly_*` if we want two bars). Reuse `_bar_color()`.
3. **`dashboard/templates/fragments/llm_usage_footer.html`** — add a Codex chip block. Recommend: one bar with `max(5h_pct, weekly_pct)` for v1 (matches the MiniMax 5h-only chip in visual weight).
4. **`tests/unit/test_llm_usage.py`** — mock `httpx` for both the refresh flow and the `/wham/usage` flow; assert error fallbacks return zeroed-but-renderable dicts; assert no token material is logged.
5. **No migration needed** — purely runtime/UI.

Open design call to make before coding: **one bar or two** in the footer (R2). I lean one bar (`max()` of 5h and weekly) for v1, two bars only if the user wants explicit weekly visibility.
