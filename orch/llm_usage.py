"""LLM usage service — Claude Code and MiniMax consumption tracking.

Claude:
  - 5h block: reads ~/.claude/rate-limits-cache.json written by the statusline
    hook after every Claude Code API response. The file contains server-
    authoritative utilisation from the anthropic-ratelimit-unified-* headers.
    Falls back to ccusage blocks --active if the cache is absent or stale.
  - 7d (weekly): ccusage weekly → totalTokens / CLAUDE_WEEKLY_LIMIT

MiniMax:
  - Live call to https://api.minimax.io/v1/api/openplatform/coding_plan/remains
    (MiniMax-M* row only). Counts requests, not tokens.
    API key resolved from IW_MINIMAX_API_KEY env var first, then
    ~/.local/share/opencode/auth.json. On missing key or failure the bar
    reports block_pct=0 and the failure is logged.
    Optional IW_MINIMAX_GROUP_ID env var appends ?GroupId=<value> to the URL.

Plan limits are configurable via env vars:
  IW_CLAUDE_WEEKLY_LIMIT (default 2_730_000_000 tokens, used for 7d bar only)

Results are cached in-process for 60 seconds.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds
_RATE_LIMITS_FILE = Path.home() / ".claude/rate-limits-cache.json"

# Claude Max 5x weekly token limit (empirically derived; override via env var).
_CLAUDE_WEEKLY_LIMIT: int = int(os.environ.get("IW_CLAUDE_WEEKLY_LIMIT", "2730000000"))

_cache: dict[str, Any] = {}
_cache_lock = Lock()


# ---------------------------------------------------------------------------
# ccusage helper
# ---------------------------------------------------------------------------


def _run_ccusage(*args: str) -> Any:
    result = subprocess.run(  # noqa: S603
        ["npx", "ccusage", *args, "-j", "--offline"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    lines = [line for line in result.stdout.split("\n") if not line.startswith("[ccusage]")]
    return json.loads("\n".join(lines))


# ---------------------------------------------------------------------------
# Claude Code — server-authoritative rate limits + ccusage weekly
# ---------------------------------------------------------------------------


def _format_minutes(minutes: float) -> str | None:
    if minutes <= 0:
        return None
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _read_rate_limits_cache() -> dict[str, Any] | None:
    """Read ~/.claude/rate-limits-cache.json written by the statusline hook.

    Returns the five_hour dict {used_percentage, resets_at} if the data is
    from the current block (resets_at is in the future), else None.
    """
    try:
        data = json.loads(_RATE_LIMITS_FILE.read_text())
    except Exception as exc:
        logger.debug("rate-limits cache unreadable: %s", exc)
        return None
    five_hour = data.get("five_hour")
    if not five_hour:
        return None
    resets_at = five_hour.get("resets_at")
    if resets_at and resets_at > datetime.now(UTC).timestamp():
        return dict(five_hour)
    return None


def _claude_usage() -> dict[str, Any]:
    """Return block_pct, week_pct, block_reset for Claude Code.

    5h block: uses server-authoritative data from the statusline cache file
    (anthropic-ratelimit-unified-* headers written after each API response).
    Falls back to ccusage blocks --active if the cache is absent or stale.
    """
    now = datetime.now(UTC)

    # 5h block — prefer server-authoritative cache from statusline hook
    five_hour = _read_rate_limits_cache()
    if five_hour:
        block_pct = min(100, round(five_hour["used_percentage"]))
        resets_at = five_hour.get("resets_at", 0)
        remaining_s = resets_at - now.timestamp()
        reset_str = _format_minutes(remaining_s / 60)
    else:
        # Fallback: ccusage blocks --active (JSONL-based, may lag slightly)
        blocks_data = _run_ccusage("blocks", "--active")
        active = next(
            (b for b in blocks_data.get("blocks", []) if b.get("isActive")),
            None,
        )
        if active:
            limit = int(os.environ.get("IW_CLAUDE_5H_LIMIT", "110000000"))
            block_pct = min(100, round(active["totalTokens"] / limit * 100))
            reset_str = _format_minutes(active.get("projection", {}).get("remainingMinutes", 0))
        else:
            block_pct = 0
            reset_str = None

    # Weekly (ccusage — server headers don't expose a weekly window via statusline)
    weekly_data = _run_ccusage("weekly")
    weeks: list[Any] = weekly_data.get("weekly", [])
    days_since_sunday = (now.weekday() + 1) % 7
    current_sunday = (now - timedelta(days=days_since_sunday)).strftime("%Y-%m-%d")
    current_week = next((w for w in weeks if w.get("week") == current_sunday), None)
    week_tokens = current_week["totalTokens"] if current_week else 0
    week_pct = min(100, round(week_tokens / _CLAUDE_WEEKLY_LIMIT * 100))

    return {
        "block_pct": block_pct,
        "week_pct": week_pct,
        "block_reset": reset_str,
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
        claude = {"block_pct": 0, "week_pct": 0, "block_reset": None}

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
