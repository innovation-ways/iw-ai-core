"""LLM usage service — Claude Code, MiniMax, and Codex consumption tracking.

Claude:
  Both bars (5h and 7d) are read from ~/.claude/rate-limits-cache.json,
  written by the statusline hook after every Claude Code API response.
  The file contains server-authoritative utilisation from the
  anthropic-ratelimit-unified-{5h,7d}-* response headers — there is no
  public REST endpoint for this data, only headers.

  When the cache is missing or stale (no Claude Code call has hit the
  server since the last reset), both bars report 0% and the next request
  the user makes through Claude Code will repopulate the file.

  The 5h label shows time remaining until reset (e.g. "4h 32m", "25m");
  the 7d label shows a wall-clock reset time (e.g. "15:00" or "Tue 09:00").

MiniMax:
  - Live call to https://api.minimax.io/v1/api/openplatform/coding_plan/remains
    (MiniMax-M* row only). Counts requests, not tokens.
    API key resolved from IW_MINIMAX_API_KEY env var first, then
    ~/.local/share/opencode/auth.json. On missing key or failure the bar
    reports block_pct=0 and the failure is logged.
    Optional IW_MINIMAX_GROUP_ID env var appends ?GroupId=<value> to the URL.

Codex (ChatGPT-subscription OAuth via opencode):
  - Live call to https://chatgpt.com/backend-api/wham/usage — the same
    undocumented endpoint the official Codex CLI polls every ~60s
    (openai/codex issues #10869, #15281). Returns a 5-hour rolling
    window (primary) and a weekly window (secondary), both as
    {used_percent, limit_window_seconds, reset_after_seconds, reset_at}
    per the codex-backend-openapi-models RateLimitWindowSnapshot
    contract. Counts messages, not tokens; per-model multipliers apply.

    Auth source is ~/.local/share/opencode/auth.json — the JSON object
    under "openai" with type="oauth", supplying the bearer access token
    and the ChatGPT-Account-Id header. We DO NOT refresh tokens here;
    opencode refreshes on its own next invocation and our next 60s
    cache miss picks up the fresh token. While the access token is
    expired (≤1h gap if the user pauses opencode use), the chip shows
    0% with no reset label.

    On any failure (file missing, non-OAuth, network error, 401, schema
    drift) the function returns zeroed dict and logs the exception
    once — never raises out.

Results are cached in-process for 60 seconds.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds
_RATELIMITS_CACHE_DIR_ENVVAR = "CLAUDE_CACHE_DIR"


def _resolve_rate_limits_file() -> Path:
    """Return the path to the rate-limits cache file.

    Respects ``CLAUDE_CACHE_DIR`` env var when set (E2E/test scenarios
    that need a non-default location). Falls back to
    ``~/.claude/rate-limits-cache.json`` when unset.
    """
    override = os.environ.get(_RATELIMITS_CACHE_DIR_ENVVAR)
    if override:
        return Path(override) / ".claude/rate-limits-cache.json"
    return Path.home() / ".claude/rate-limits-cache.json"


_cache: dict[str, Any] = {}
_cache_lock = Lock()


# ---------------------------------------------------------------------------
# Claude Code — server-authoritative rate limits from statusline cache
# ---------------------------------------------------------------------------


def _format_resets_at(resets_at: float) -> str | None:
    """Render a Unix timestamp as a wall-clock reset label in local time.

    Same shape as claude.ai's "Resets on Tuesday 09:00":
      - <24h away → "HH:MM"      (e.g. "21:30")
      - else      → "Day HH:MM"  (e.g. "Tue 09:00")
    Returns None for past or zero timestamps.
    """
    if resets_at <= 0:
        return None
    now_ts = datetime.now(UTC).timestamp()
    if resets_at <= now_ts:
        return None
    local = datetime.fromtimestamp(resets_at, tz=UTC).astimezone()
    if resets_at - now_ts < 24 * 3600:
        return local.strftime("%H:%M")
    return local.strftime("%a %H:%M")


def _format_remaining_from_ts(resets_at: float) -> str | None:
    """Render a Unix timestamp as a remaining-time label (MiniMax-style).

    - >=1h ahead → 'Hh Mm'   (e.g. '4h 32m', '1h 0m')
    - <1h ahead  → 'Mm'      (e.g. '25m', '0m' for under one minute)
    - past or zero → None
    """
    if resets_at <= 0:
        return None
    delta = resets_at - datetime.now(UTC).timestamp()
    if delta < 0:
        return None
    remaining_s = int(delta)
    if remaining_s >= 3600:
        hours = remaining_s // 3600
        minutes = (remaining_s % 3600) // 60
        return f"{hours}h {minutes}m"
    return f"{remaining_s // 60}m"


def _read_rate_limits_cache(window: str) -> dict[str, Any] | None:
    """Read ~/.claude/rate-limits-cache.json for `window`.

    `window` is "five_hour" or "seven_day" — the keys the Claude Code
    statusline hook persists from the anthropic-ratelimit-unified-{5h,7d}-*
    response headers.

    Returns the window dict {used_percentage, resets_at} if its resets_at
    is in the future (i.e. the data hasn't expired), else None.
    """
    try:
        data = json.loads(_resolve_rate_limits_file().read_text())
    except Exception as exc:
        logger.debug("rate-limits cache unreadable: %s", exc)
        return None
    bucket = data.get(window)
    if not bucket:
        return None
    resets_at = bucket.get("resets_at")
    if resets_at and resets_at > datetime.now(UTC).timestamp():
        return dict(bucket)
    return None


def _claude_usage() -> dict[str, Any]:
    """Return block_pct/week_pct/block_reset/week_reset from the rate-limits cache.

    Both bars are server-authoritative, sourced from the
    anthropic-ratelimit-unified-{5h,7d}-* headers via
    ~/.claude/rate-limits-cache.json. If the cache is missing or stale
    for either window, that window reports 0% with no reset label.
    """
    five_hour = _read_rate_limits_cache("five_hour")
    if five_hour:
        block_pct = min(100, round(five_hour["used_percentage"]))
        block_reset = _format_remaining_from_ts(five_hour.get("resets_at", 0))
    else:
        block_pct = 0
        block_reset = None

    seven_day = _read_rate_limits_cache("seven_day")
    if seven_day:
        week_pct = min(100, round(seven_day["used_percentage"]))
        week_reset = _format_resets_at(seven_day.get("resets_at", 0))
    else:
        week_pct = 0
        week_reset = None

    return {
        "block_pct": block_pct,
        "week_pct": week_pct,
        "block_reset": block_reset,
        "week_reset": week_reset,
    }


# ---------------------------------------------------------------------------
# MiniMax — via /coding_plan/remains API
# ---------------------------------------------------------------------------


def _load_minimax_key() -> str | None:
    """Resolve MiniMax API key: IW_MINIMAX_API_KEY env var first, then auth.json fallback."""
    key = os.environ.get("IW_MINIMAX_API_KEY")
    if key:
        return key

    try:
        path = Path.home() / ".local/share/opencode/auth.json"
        data: dict[str, Any] = json.loads(path.read_text())
        minimax_entry: dict[str, Any] = data.get("minimax", {})
        auth_key: str | None = minimax_entry.get("key")
        return auth_key
    except Exception:  # noqa: S110
        return None


def _format_reset(remains_ms: int) -> str | None:
    """Format milliseconds-to-reset as a short human string."""
    if remains_ms <= 0:
        return None
    if remains_ms < 3_600_000:
        return f"{remains_ms // 60_000}m"
    hours = remains_ms // 3_600_000
    minutes = (remains_ms % 3_600_000) // 60_000
    return f"{hours}h {minutes}m"


def _minimax_usage_remote(api_key: str) -> dict[str, Any]:
    """Call GET /coding_plan/remains and return usage dict for the MiniMax-M* row."""
    url = "https://api.minimax.io/v1/api/openplatform/coding_plan/remains"
    group_id = os.environ.get("IW_MINIMAX_GROUP_ID")
    if group_id:
        url = f"{url}?GroupId={group_id}"

    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=10.0,
    )
    resp.raise_for_status()

    data = resp.json()
    if data["base_resp"]["status_code"] != 0:
        raise RuntimeError(data["base_resp"]["status_msg"])

    model_remains: list[dict[str, Any]] = data["model_remains"]
    row = next((r for r in model_remains if r["model_name"].startswith("MiniMax-M")), None)
    if row is None:
        raise LookupError("MiniMax-M* row not present")

    total = row["current_interval_total_count"]
    if total == 0:
        raise ValueError("MiniMax-M* total quota is 0")

    # usage_count is remaining, not used (confirmed with MiniMax API team)
    remaining = row["current_interval_usage_count"]
    used = total - remaining
    pct = min(100, round(used / total * 100))
    reset = _format_reset(row["remains_time"])

    return {
        "block_pct": pct,
        "block_reset": reset,
        "used": used,
        "total": total,
    }


def _minimax_usage() -> dict[str, Any]:
    """Return MiniMax block_pct and block_reset, never raises."""
    key = _load_minimax_key()
    if key is None:
        logger.warning("MiniMax API key not configured; usage bar will show 0%")
        return {"block_pct": 0, "block_reset": None}

    try:
        return _minimax_usage_remote(key)
    except Exception:
        logger.exception("MiniMax usage fetch failed")
        return {"block_pct": 0, "block_reset": None}


# ---------------------------------------------------------------------------
# Codex — via /backend-api/wham/usage with opencode OAuth
# ---------------------------------------------------------------------------


_CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
_CODEX_ZERO: dict[str, Any] = {
    "block_pct": 0,
    "week_pct": 0,
    "block_reset": None,
    "week_reset": None,
    "plan_type": None,
}


def _load_openai_oauth() -> dict[str, Any] | None:
    """Read ~/.local/share/opencode/auth.json and return the openai OAuth entry.

    Returns the dict ``{access, refresh, expires, accountId}`` from the
    ``openai`` section when ``type == "oauth"``; returns None for any
    other shape (raw API key, missing section, malformed file, missing
    file). Never raises.
    """
    try:
        path = Path.home() / ".local/share/opencode/auth.json"
        data: dict[str, Any] = json.loads(path.read_text())
    except Exception:  # noqa: S110, BLE001
        return None
    entry = data.get("openai")
    if not isinstance(entry, dict) or entry.get("type") != "oauth":
        return None
    access = entry.get("access")
    account_id = entry.get("accountId")
    if not isinstance(access, str) or not isinstance(account_id, str):
        return None
    return entry


def _codex_window_pct(window: Any) -> int:
    """Extract used_percent from a RateLimitWindowSnapshot dict; 0 if missing/invalid."""
    if not isinstance(window, dict):
        return 0
    raw = window.get("used_percent")
    if not isinstance(raw, (int, float)):
        return 0
    return min(100, max(0, round(raw)))


def _codex_window_reset_ts(window: Any) -> int:
    """Extract reset_at (epoch seconds) from a window dict; 0 if missing/invalid."""
    if not isinstance(window, dict):
        return 0
    raw = window.get("reset_at")
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    return 0


def _codex_usage_remote(access: str, account_id: str) -> dict[str, Any]:
    """Call GET /backend-api/wham/usage and return the 5h + weekly usage dict.

    Response shape per codex-backend-openapi-models RateLimitStatusPayload:
        {
          "plan_type": "plus"|"pro"|...,
          "rate_limit": {
            "primary_window":   {used_percent, limit_window_seconds, reset_after_seconds, reset_at},
            "secondary_window": {used_percent, limit_window_seconds, reset_after_seconds, reset_at}
          },
          ...
        }
    The double-Option in the Rust contract surfaces here as missing keys or
    explicit ``null`` values; both are handled defensively.
    """
    resp = httpx.get(
        _CODEX_USAGE_URL,
        headers={
            "Authorization": f"Bearer {access}",
            "ChatGPT-Account-Id": account_id,
            "Accept": "application/json",
            "User-Agent": "iw-ai-core/0.1 codex-usage-poller",
        },
        timeout=10.0,
    )
    resp.raise_for_status()

    payload = resp.json()
    rate_limit = payload.get("rate_limit") or {}
    primary = rate_limit.get("primary_window") or {}
    secondary = rate_limit.get("secondary_window") or {}

    return {
        "block_pct": _codex_window_pct(primary),
        "week_pct": _codex_window_pct(secondary),
        "block_reset": _format_remaining_from_ts(_codex_window_reset_ts(primary)),
        "week_reset": _format_resets_at(_codex_window_reset_ts(secondary)),
        "plan_type": payload.get("plan_type"),
    }


def _codex_usage() -> dict[str, Any]:
    """Return Codex 5h + weekly usage; never raises.

    Returns zeroed dict (``block_pct=0, week_pct=0, *_reset=None``) when:
      - opencode auth.json is missing or has no OAuth entry for openai
      - access token is rejected (401), endpoint moved (404),
        upstream is unreachable, or the JSON body fails to parse.
    Failures are logged at WARNING (auth absent — expected when the user
    has not run ``opencode auth login`` for openai) or ERROR (any other
    transport / decode failure).
    """
    entry = _load_openai_oauth()
    if entry is None:
        logger.warning(
            "Codex OAuth credentials not found in opencode auth.json; usage chips will show 0%%",
        )
        return dict(_CODEX_ZERO)

    try:
        return _codex_usage_remote(entry["access"], entry["accountId"])
    except Exception:
        logger.exception("Codex usage fetch failed")
        return dict(_CODEX_ZERO)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_llm_usage() -> dict[str, Any]:
    """Return cached LLM usage data, refreshed every 60 seconds."""
    now = datetime.now(UTC)
    with _cache_lock:
        if _cache.get("ts") and (now - _cache["ts"]).total_seconds() < _CACHE_TTL:
            return _cache["data"]  # type: ignore[no-any-return]

    try:
        claude = _claude_usage()
    except Exception:
        logger.exception("Claude usage fetch failed")
        claude = {"block_pct": 0, "week_pct": 0, "block_reset": None, "week_reset": None}

    try:
        minimax = _minimax_usage()
    except Exception:
        logger.exception("MiniMax usage fetch failed")
        minimax = {"block_pct": 0, "block_reset": None}

    try:
        codex = _codex_usage()
    except Exception:
        logger.exception("Codex usage fetch failed")
        codex = dict(_CODEX_ZERO)

    result: dict[str, Any] = {"claude": claude, "minimax": minimax, "codex": codex}
    with _cache_lock:
        _cache["ts"] = now
        _cache["data"] = result
    return result


def prewarm() -> None:
    """Kick off cache population in a background daemon thread at startup."""
    import threading

    t = threading.Thread(target=get_llm_usage, daemon=True, name="llm-usage-prewarm")
    t.start()
