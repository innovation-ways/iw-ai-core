"""LLM usage service — Claude Code and MiniMax consumption tracking.

Computes usage percentages against plan limits:
  - Claude 5h block: JSONL token scan for the current billing period / CLAUDE_5H_LIMIT
  - Claude 7d (weekly): ccusage weekly total / CLAUDE_WEEKLY_LIMIT
  - MiniMax 5h: live call to https://api.minimax.io/v1/api/openplatform/coding_plan/remains,
    reading the MiniMax-M* row only. Counts requests, not tokens.

    API key is resolved from IW_MINIMAX_API_KEY env var first, then from
    ~/.local/share/opencode/auth.json. On missing key or any failure the bar
    reports block_pct=0 and block_reset=None and the failure is logged.

    Optional IW_MINIMAX_GROUP_ID env var appends ?GroupId=<value> to the URL.
    Most accounts do not need this.

Claude billing blocks are 5h long but start at an account-specific offset from
UTC midnight (not a fixed grid). The offset is set via IW_CLAUDE_BLOCK_ANCHOR_MIN
(minutes past each 5h UTC boundary; back-calculate from the claude.ai reset timer).

Plan limits are empirically derived from Claude Max 5x and configurable via env vars.

Results are cached in-process for 60 seconds (ccusage cold-start ≈ 5s).
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

_CLAUDE_JSONL_DIR = Path.home() / ".claude/projects"
_CACHE_TTL = 60  # seconds

# Claude Max 5x plan limits (empirically derived; override via env vars).
_CLAUDE_5H_LIMIT: int = int(os.environ.get("IW_CLAUDE_5H_LIMIT", "110000000"))
_CLAUDE_WEEKLY_LIMIT: int = int(os.environ.get("IW_CLAUDE_WEEKLY_LIMIT", "2730000000"))

# Minutes offset from the 5h UTC boundary where YOUR account's billing block starts.
# Find it: open claude.ai, note the reset timer, compute: (reset_hour*60+reset_min) mod 300.
# Example: reset at 20:25 UTC → (20*60+25) mod 300 = 1225 mod 300 = 25.
_CLAUDE_BLOCK_ANCHOR_MIN: int = int(os.environ.get("IW_CLAUDE_BLOCK_ANCHOR_MIN", "25"))

_cache: dict[str, Any] = {}
_cache_lock = Lock()


# ---------------------------------------------------------------------------
# Claude Code — JSONL scan for 5h block, ccusage for weekly
# ---------------------------------------------------------------------------


def _run_ccusage(subcommand: str) -> Any:
    result = subprocess.run(  # noqa: S603
        ["npx", "ccusage", subcommand, "-j", "--offline"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    lines = [line for line in result.stdout.split("\n") if not line.startswith("[ccusage]")]
    return json.loads("\n".join(lines))


def _block_start() -> datetime:
    """Return the start of the current Claude billing block."""
    now = datetime.now(UTC)
    now_min = now.hour * 60 + now.minute
    mins_since_anchor = (now_min - _CLAUDE_BLOCK_ANCHOR_MIN) % 300
    return now.replace(second=0, microsecond=0) - timedelta(minutes=mins_since_anchor)


def _sum_jsonl_tokens(since: datetime) -> int:
    """Sum tokens from all JSONL session files since the given UTC datetime."""
    since_prefix = since.strftime("%Y-%m-%dT%H:%M")
    since_mtime = since.timestamp() - 60  # 60s buffer
    total = 0
    for f in _CLAUDE_JSONL_DIR.rglob("*.jsonl"):
        try:
            if f.stat().st_mtime < since_mtime:
                continue
            with f.open() as fh:
                for line in fh:
                    msg = json.loads(line)
                    ts = msg.get("timestamp", "")
                    if not ts or ts[:16] < since_prefix:
                        continue
                    usage = msg.get("message", {}).get("usage", {})
                    if usage:
                        total += (
                            usage.get("input_tokens", 0)
                            + usage.get("output_tokens", 0)
                            + usage.get("cache_creation_input_tokens", 0)
                            + usage.get("cache_read_input_tokens", 0)
                        )
        except Exception:  # noqa: S110
            pass
    return total


def _claude_usage() -> dict[str, Any]:
    """Return block_pct, week_pct, block_reset for Claude Code."""
    now = datetime.now(UTC)
    start = _block_start()
    end = start + timedelta(hours=5)

    # 5h block — scan JSONL for the real billing period
    current_block_tokens = _sum_jsonl_tokens(start)
    block_pct = min(100, round(current_block_tokens / _CLAUDE_5H_LIMIT * 100))

    reset_str: str | None = None
    remaining = end - now
    if remaining.total_seconds() > 0:
        h = int(remaining.total_seconds() // 3600)
        m = int((remaining.total_seconds() % 3600) // 60)
        reset_str = f"{h}h {m}m" if h else f"{m}m"

    # Weekly (ccusage uses Sunday-based weeks)
    weekly_data = _run_ccusage("weekly")
    weeks: list[Any] = weekly_data.get("weekly", [])
    days_since_sunday = (now.weekday() + 1) % 7
    current_sunday = (now - timedelta(days=days_since_sunday)).strftime("%Y-%m-%d")
    current_week = next((w for w in weeks if w.get("week") == current_sunday), None)
    current_week_tokens = current_week["totalTokens"] if current_week else 0
    week_pct = min(100, round(current_week_tokens / _CLAUDE_WEEKLY_LIMIT * 100))

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
    """Format milliseconds-to-reset as a short human string.

    - remains_ms <= 0 → None
    - remains_ms < 3_600_000 (1 hour) → "{m}m"
    - otherwise → "{h}h {m}m"
    """
    if remains_ms <= 0:
        return None
    if remains_ms < 3_600_000:
        return f"{remains_ms // 60_000}m"
    hours = remains_ms // 3_600_000
    minutes = (remains_ms % 3_600_000) // 60_000
    return f"{hours}h {minutes}m"


def _minimax_usage_remote(api_key: str) -> dict[str, Any]:
    """Call GET /coding_plan/remains and return usage dict for the MiniMax-M* row.

    Raises on: non-2xx HTTP, base_resp.status_code != 0, missing MiniMax-M* row,
    total == 0, JSON parse error. The caller is responsible for catching.
    """
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
