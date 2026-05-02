"""LLM usage service — Claude Code and MiniMax consumption tracking.

Claude:
  Both bars (5h and 7d) are read from ~/.claude/rate-limits-cache.json,
  written by the statusline hook after every Claude Code API response.
  The file contains server-authoritative utilisation from the
  anthropic-ratelimit-unified-{5h,7d}-* response headers — there is no
  public REST endpoint for this data, only headers.

  When the cache is missing or stale (no Claude Code call has hit the
  server since the last reset), both bars report 0% and the next request
  the user makes through Claude Code will repopulate the file.

MiniMax:
  - Live call to https://api.minimax.io/v1/api/openplatform/coding_plan/remains
    (MiniMax-M* row only). Counts requests, not tokens.
    API key resolved from IW_MINIMAX_API_KEY env var first, then
    ~/.local/share/opencode/auth.json. On missing key or failure the bar
    reports block_pct=0 and the failure is logged.
    Optional IW_MINIMAX_GROUP_ID env var appends ?GroupId=<value> to the URL.

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
_RATE_LIMITS_FILE = Path.home() / ".claude/rate-limits-cache.json"

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


def _read_rate_limits_cache(window: str) -> dict[str, Any] | None:
    """Read ~/.claude/rate-limits-cache.json for `window`.

    `window` is "five_hour" or "seven_day" — the keys the Claude Code
    statusline hook persists from the anthropic-ratelimit-unified-{5h,7d}-*
    response headers.

    Returns the window dict {used_percentage, resets_at} if its resets_at
    is in the future (i.e. the data hasn't expired), else None.
    """
    try:
        data = json.loads(_RATE_LIMITS_FILE.read_text())
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
        block_reset = _format_resets_at(five_hour.get("resets_at", 0))
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

    result: dict[str, Any] = {"claude": claude, "minimax": minimax}
    with _cache_lock:
        _cache["ts"] = now
        _cache["data"] = result
    return result


def prewarm() -> None:
    """Kick off cache population in a background daemon thread at startup."""
    import threading

    t = threading.Thread(target=get_llm_usage, daemon=True, name="llm-usage-prewarm")
    t.start()
