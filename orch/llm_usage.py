"""LLM usage service — Claude Code, MiniMax, Codex, and Tavily consumption tracking.

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
    and the ChatGPT-Account-Id header. When the access token is expired,
    this service refreshes it with the stored refresh token, atomically updates
    opencode auth.json, and then fetches usage with the new access token.

    On any failure (file missing, non-OAuth, network error, 401, schema
    drift) the function returns zeroed dict and logs the exception
    once — never raises out.

Tavily:
  - Live call to https://api.tavily.com/usage using TAVILY_API_KEY. No
    X-Project-ID is sent because this deployment does not use Tavily projects.
    Preferred usage source is key.usage/key.limit, with account.plan_usage /
    account.plan_limit as fallback. Homepage displays against the free-tier
    1000 credits/month cap and clamps the bar to 0–100%.

Results are cached in-process for 60 seconds.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # seconds
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
    """Call GET /coding_plan/remains and return the active text-plan usage.

    The API returns one row per plan bucket. Accounts expose either
    model-specific rows (``MiniMax-M*``) carrying explicit request counts, or
    generic ``general``/``video`` buckets that report a remaining-percentage
    instead of counts. We prefer a ``MiniMax-M*`` row, fall back to
    ``general``, and derive usage from counts when available, otherwise from
    the ``*_remaining_percent`` fields. The weekly window is included when the
    plan exposes it.
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
    base = data.get("base_resp") or {}
    if base.get("status_code", 0) != 0:
        raise RuntimeError(base.get("status_msg", "MiniMax API error"))

    model_remains: list[dict[str, Any]] = data["model_remains"]
    row = next((r for r in model_remains if r["model_name"].startswith("MiniMax-M")), None)
    if row is None:
        row = next((r for r in model_remains if r["model_name"] == "general"), None)
    if row is None:
        raise LookupError("no usable MiniMax plan row (MiniMax-M* or general)")

    result: dict[str, Any] = {}

    # 5h interval: prefer explicit counts (usage_count is *remaining*), else the
    # remaining-percent the plan reports directly.
    total = row.get("current_interval_total_count") or 0
    if total > 0:
        remaining = row.get("current_interval_usage_count", 0)
        used = total - remaining
        result["block_pct"] = min(100, round(used / total * 100))
        result["used"] = used
        result["total"] = total
    else:
        rem_pct = row.get("current_interval_remaining_percent")
        if rem_pct is None:
            raise ValueError(
                f"MiniMax plan {row.get('model_name')!r} reports total quota is 0 "
                "and no remaining-percent fallback — cannot compute usage"
            )
        result["block_pct"] = max(0, min(100, 100 - int(rem_pct)))
    result["block_reset"] = _format_reset(row.get("remains_time") or 0)

    # Weekly window (when the plan exposes it).
    week_rem_pct = row.get("current_weekly_remaining_percent")
    if week_rem_pct is not None:
        result["week_pct"] = max(0, min(100, 100 - int(week_rem_pct)))
        weekly_end = row.get("weekly_end_time")
        # Match Claude/Codex weekly style ("Tue 09:00") via the wall-clock end
        # time; fall back to a remaining-duration if it's absent.
        result["week_reset"] = (
            _format_resets_at(weekly_end / 1000)
            if weekly_end
            else _format_reset(row.get("weekly_remains_time") or 0)
        )

    return result


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
# Tavily — via /usage API
# ---------------------------------------------------------------------------


_TAVILY_USAGE_URL = "https://api.tavily.com/usage"
_TAVILY_FREE_TIER_LIMIT = 1000
_TAVILY_STALE_CACHE_ENVVAR = "IW_CORE_TAVILY_USAGE_CACHE"


def _tavily_stale_cache_path() -> Path:
    """Return the on-disk last-good Tavily usage cache path."""
    override = os.environ.get(_TAVILY_STALE_CACHE_ENVVAR)
    if override:
        return Path(override)
    return Path.home() / ".cache/iw-ai-core/tavily-usage.json"


def _read_tavily_stale_usage() -> dict[str, Any] | None:
    """Return last known-good Tavily usage, if present and well-formed."""
    try:
        payload = json.loads(_tavily_stale_cache_path().read_text())
    except Exception:
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    if not {"block_pct", "used", "total"}.issubset(usage):
        return None
    try:
        return {
            "block_pct": int(usage["block_pct"]),
            "used": int(usage["used"]),
            "total": int(usage["total"]),
            "stale": True,
        }
    except (TypeError, ValueError):
        return None


def _write_tavily_stale_usage(usage: dict[str, Any]) -> None:
    """Persist last known-good Tavily usage for rate-limit fallback."""
    try:
        path = _tavily_stale_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"updated_at": datetime.now(UTC).isoformat(), "usage": usage}))
    except Exception as exc:
        logger.debug("Could not write Tavily stale usage cache: %s", exc)


def _coerce_usage_number(value: Any) -> float | None:
    """Return a numeric usage value, accepting API numbers or numeric strings."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _load_tavily_key() -> str | None:
    """Resolve Tavily API key from the process environment."""
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    return None


def _tavily_usage_remote(api_key: str) -> dict[str, Any]:
    """Call GET /usage and return Homepage-friendly free-tier usage.

    Response shapes observed/documented include both key-scoped and account-
    scoped counters. We prefer key.usage/key.limit, then fall back to
    account.plan_usage/account.plan_limit. The rendered Homepage card always
    displays against the configured free-tier maximum of 1000 credits/month.
    """
    resp = httpx.get(
        _TAVILY_USAGE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=10.0,
    )
    resp.raise_for_status()

    payload = resp.json()
    key = payload.get("key") if isinstance(payload.get("key"), dict) else {}
    account = payload.get("account") if isinstance(payload.get("account"), dict) else {}

    usage = _coerce_usage_number(key.get("usage"))
    source_limit = _coerce_usage_number(key.get("limit"))
    if usage is None:
        usage = _coerce_usage_number(account.get("plan_usage"))
        source_limit = _coerce_usage_number(account.get("plan_limit"))
    if usage is None:
        usage = 0.0

    total = _TAVILY_FREE_TIER_LIMIT
    # Keep source_limit read/parsing explicit for schema coverage while honoring
    # the Homepage/free-tier display requirement of 1000 credits.
    if source_limit == _TAVILY_FREE_TIER_LIMIT:
        total = int(source_limit)

    pct = min(100, max(0, round((usage / _TAVILY_FREE_TIER_LIMIT) * 100)))
    used = max(0, round(usage))
    result = {"block_pct": pct, "used": used, "total": total}
    _write_tavily_stale_usage(result)
    return result


def _tavily_usage() -> dict[str, Any]:
    """Return Tavily credits used/total and usage percent, never raises."""
    key = _load_tavily_key()
    if key is None:
        logger.warning("TAVILY_API_KEY not configured; Tavily usage bar will show 0%%")
        return {"block_pct": 0, "used": 0, "total": _TAVILY_FREE_TIER_LIMIT}

    try:
        return _tavily_usage_remote(key)
    except Exception:
        stale = _read_tavily_stale_usage()
        if stale is not None:
            logger.warning("Tavily usage fetch failed; using last known-good usage cache")
            return stale
        logger.exception("Tavily usage fetch failed and no stale cache is available")
        return {"block_pct": 0, "used": 0, "total": _TAVILY_FREE_TIER_LIMIT}


# ---------------------------------------------------------------------------
# Codex — via /backend-api/wham/usage with opencode OAuth
# ---------------------------------------------------------------------------


# Status discriminators for _codex_usage() return dict.
_CODEX_STATUS_OK = "ok"
_CODEX_STATUS_EXPIRED = "expired"
_CODEX_STATUS_UNAUTHENTICATED = "unauthenticated"
_CODEX_STATUS_ERROR = "error"


def _oauth_is_expired(entry: dict[str, Any]) -> bool:
    """Return True when the stored token expiry epoch-ms is at/before now.

    Returns False when `expires` is missing, None, zero, or not a number — let
    the remote call decide rather than treating unknown as expired.
    """
    raw = entry.get("expires")
    # 0 or 0.0 (epoch-0) is the OAuth-unset sentinel; treat it as "unknown" so the
    # remote call decides rather than hard-coding it as permanently expired.
    if raw is None or raw == 0 or not isinstance(raw, (int, float)):
        return False
    return bool(raw <= datetime.now(UTC).timestamp() * 1000)


def _codex_zero(status: str) -> dict[str, Any]:
    """Return the zeroed Codex usage dict tagged with `status`.

    Args:
        status: One of the _CODEX_STATUS_* constants.

    Returns:
        Dict with block_pct=0, week_pct=0, *_reset=None, plan_type=None,
        and the given status.
    """
    return {
        "block_pct": 0,
        "week_pct": 0,
        "block_reset": None,
        "week_reset": None,
        "plan_type": None,
        "status": status,
    }


_CODEX_ISSUER = "https://auth.openai.com"
_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
_CODEX_TOKEN_URL = f"{_CODEX_ISSUER}/oauth/token"
_CODEX_ZERO: dict[str, Any] = {
    "block_pct": 0,
    "week_pct": 0,
    "block_reset": None,
    "week_reset": None,
    "plan_type": None,
}


def _resolve_opencode_auth_file() -> Path:
    """Return opencode's global auth.json path."""
    return Path.home() / ".local/share/opencode/auth.json"


def _load_openai_oauth() -> dict[str, Any] | None:
    """Read ~/.local/share/opencode/auth.json and return the openai OAuth entry.

    Returns the dict ``{access, refresh, expires, accountId}`` from the
    ``openai`` section when ``type == "oauth"``; returns None for any
    other shape (raw API key, missing section, malformed file, missing
    file). Never raises.
    """
    try:
        data: dict[str, Any] = json.loads(_resolve_opencode_auth_file().read_text())
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


def _save_openai_oauth(entry: dict[str, Any]) -> None:
    """Atomically update opencode auth.json with a refreshed OpenAI OAuth entry."""
    path = _resolve_opencode_auth_file()
    data: dict[str, Any] = json.loads(path.read_text())
    data["openai"] = entry

    fd, tmp_name = tempfile.mkstemp(prefix="auth.", suffix=".json", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        tmp_path.chmod(path.stat().st_mode)
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _refresh_openai_oauth(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Refresh an expired opencode OpenAI OAuth entry and persist it.

    Mirrors opencode's Codex provider refresh flow. Returns the updated entry on
    success; returns None on missing refresh token or refresh failure. Secrets are
    never logged.
    """
    refresh_token = entry.get("refresh")
    if not isinstance(refresh_token, str) or not refresh_token:
        logger.warning("Codex OAuth token expired but no refresh token is available")
        return None

    try:
        resp = httpx.post(
            _CODEX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _CODEX_CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20.0,
        )
        resp.raise_for_status()
        tokens = resp.json()
        access = tokens.get("access_token")
        if not isinstance(access, str) or not access:
            raise RuntimeError("refresh response missing access_token")
        updated = dict(entry)
        updated["type"] = "oauth"
        updated["access"] = access
        token_refresh = tokens.get("refresh_token")
        if isinstance(token_refresh, str) and token_refresh:
            updated["refresh"] = token_refresh
        expires_in = tokens.get("expires_in")
        if not isinstance(expires_in, (int, float)):
            expires_in = 3600
        updated["expires"] = datetime.now(UTC).timestamp() * 1000 + (float(expires_in) * 1000)
        _save_openai_oauth(updated)
        return updated
    except Exception:
        logger.exception("Codex OAuth token refresh failed")
        return None


def _codex_window_pct(window: Any) -> int:
    """Extract used_percent from a RateLimitWindowSnapshot dict; 0 if missing/invalid.

    Args:
        window: A dict (or any value) from the Codex rate_limit response.

    Returns:
        Integer 0–100 representing used percentage.
    """
    if not isinstance(window, dict):
        return 0
    raw = window.get("used_percent")
    if not isinstance(raw, (int, float)):
        return 0
    return min(100, max(0, round(raw)))


def _codex_window_reset_ts(window: Any) -> int:
    """Extract reset_at (epoch seconds) from a window dict; 0 if missing/invalid.

    Args:
        window: A dict (or any value) from the Codex rate_limit response.

    Returns:
        Unix epoch seconds as integer, or 0 when absent or invalid.
    """
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

    Returns a dict that always includes ``status: _CODEX_STATUS_OK``.
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
        "status": _CODEX_STATUS_OK,
    }


def _codex_usage() -> dict[str, Any]:
    """Return Codex 5h + weekly usage; never raises.

    Returns a dict always containing a ``status`` key:
      - ``ok``:            usage fetched successfully from the endpoint
      - ``expired``:       stored ``expires`` epoch-ms is at/before now, OR endpoint
                           returns HTTP 401 (token_expired)
      - ``unauthenticated``: auth.json missing or no valid openai OAuth entry
      - ``error``:         any other transport/decode/schema failure

    When status ``!= "ok"``, block_pct/week_pct are 0 and *_reset are None.
    """
    entry = _load_openai_oauth()
    if entry is None:
        logger.warning(
            "Codex OAuth credentials not found in opencode auth.json; usage chips will show 0%%",
        )
        return _codex_zero(_CODEX_STATUS_UNAUTHENTICATED)

    if _oauth_is_expired(entry):
        logger.warning(
            "Codex OAuth token is expired (expires <= now); refreshing access token",
        )
        refreshed = _refresh_openai_oauth(entry)
        if refreshed is None:
            return _codex_zero(_CODEX_STATUS_EXPIRED)
        entry = refreshed

    try:
        return _codex_usage_remote(entry["access"], entry["accountId"])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning(
                "Codex token rejected (HTTP 401 token_expired); refreshing access token",
            )
            refreshed = _refresh_openai_oauth(entry)
            if refreshed is None:
                return _codex_zero(_CODEX_STATUS_EXPIRED)
            try:
                return _codex_usage_remote(refreshed["access"], refreshed["accountId"])
            except Exception:
                logger.exception("Codex usage fetch failed after OAuth refresh")
                return _codex_zero(_CODEX_STATUS_ERROR)
        logger.exception("Codex usage fetch failed")
        return _codex_zero(_CODEX_STATUS_ERROR)
    except Exception:
        logger.exception("Codex usage fetch failed")
        return _codex_zero(_CODEX_STATUS_ERROR)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_llm_usage() -> dict[str, Any]:
    """Return cached LLM usage data, refreshed every 300 seconds.

    The cache lock is intentionally held while refreshing. Homepage embeds poll
    multiple provider iframes at the same interval; without single-flight
    refresh, those concurrent requests all miss the cache together and hammer
    upstream APIs such as Tavily /usage, which responds with 429.
    """
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
            codex = _codex_zero(_CODEX_STATUS_ERROR)

        try:
            tavily = _tavily_usage()
        except Exception:
            logger.exception("Tavily usage fetch failed")
            tavily = {"block_pct": 0, "used": 0, "total": _TAVILY_FREE_TIER_LIMIT}

        result: dict[str, Any] = {
            "claude": claude,
            "minimax": minimax,
            "codex": codex,
            "tavily": tavily,
        }
        _cache["ts"] = now
        _cache["data"] = result
        return result


def prewarm() -> None:
    """Kick off cache population in a background daemon thread at startup."""
    import threading

    t = threading.Thread(target=get_llm_usage, daemon=True, name="llm-usage-prewarm")
    t.start()
