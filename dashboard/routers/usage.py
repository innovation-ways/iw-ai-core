"""LLM usage footer endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from orch.llm_usage import get_llm_usage

router = APIRouter(prefix="/api/usage", tags=["usage"])

# Maps Codex usage status to the warning text shown in the footer chip.
# When status == "ok" no warning is shown (normal bars are rendered).
_CODEX_WARNING_MAP: dict[str, str] = {
    "expired": "token expired — re-authenticate",
    "unauthenticated": "not configured — run opencode auth login",
    "error": "usage unavailable",
}


def _bar_color(pct: int) -> str:
    """Return the Tailwind CSS class for a usage bar based on percentage.

    Args:
        pct: Usage percentage (0–100).

    Returns:
        Tailwind bg class — red at >=90%, amber at >=70%, primary otherwise.
    """
    if pct >= 90:
        return "bg-red-500"
    if pct >= 70:
        return "bg-amber-500"
    return "bg-primary"


def _bar_hex(pct: int) -> str:
    """Return a usage-bar color on a green->amber->red gradient by percentage.

    The hue scales continuously with usage so every percentage maps to a
    distinct color (low usage green, mid amber, high red) — an at-a-glance
    indicator, rather than one flat color shared by all low values.

    Args:
        pct: Usage percentage (0–100).

    Returns:
        An ``hsl(...)`` CSS color string.
    """
    pct = max(0, min(100, pct))
    hue = 120 - (pct * 1.2)  # 0% -> 120 (green), 50% -> 60 (amber), 100% -> 0 (red)
    return f"hsl({hue:.0f}, 75%, 48%)"


@router.get("/llm/embed", response_class=HTMLResponse)
def llm_usage_embed(request: Request, provider: str = "claude") -> Any:
    """Return a self-contained HTML bar view for one provider, for embedding.

    Designed to be loaded in an ``<iframe>`` by external dashboards (e.g. a
    gethomepage.dev iframe widget) so they render the same bar + reset-time
    visualization as the in-app footer. Transparent background, inline CSS,
    no external dependencies.

    Args:
        request: The current FastAPI request.
        provider: One of ``"claude"``, ``"codex"``, ``"minimax"``.

    Returns:
        Standalone HTML page rendering that provider's usage-window bars.
    """
    usage = get_llm_usage()
    windows: list[dict[str, Any]] = []
    warning: str | None = None

    if provider == "minimax":
        minimax = usage["minimax"]
        windows = [{"label": minimax.get("block_reset") or "5h", "pct": minimax["block_pct"]}]
    elif provider == "codex":
        codex = usage.get("codex") or {"block_pct": 0, "week_pct": 0, "status": "error"}
        status = codex.get("status") or "ok"
        if status != "ok":
            warning = _CODEX_WARNING_MAP.get(status, "usage unavailable")
        else:
            windows = [
                {"label": codex.get("block_reset") or "5h", "pct": codex["block_pct"]},
                {"label": codex.get("week_reset") or "7d", "pct": codex["week_pct"]},
            ]
    else:  # claude (default)
        claude = usage["claude"]
        windows = [
            {"label": claude.get("block_reset") or "5h", "pct": claude["block_pct"]},
            {"label": claude.get("week_reset") or "7d", "pct": claude["week_pct"]},
        ]

    for window in windows:
        window["color"] = _bar_hex(int(window["pct"]))

    response = request.app.state.templates.TemplateResponse(
        request,
        "fragments/llm_usage_embed.html",
        {"windows": windows, "warning": warning},
    )
    # Bars must always reflect live usage; never let a browser/iframe serve a
    # stale (e.g. differently-colored) cached copy.
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@router.get("/llm")
def llm_usage_json() -> Any:
    """Return raw LLM usage data as JSON for external consumers.

    Unlike ``/llm/fragment`` (which renders the dashboard footer as HTML), this
    returns the plain per-provider dict from ``get_llm_usage()`` so external
    tools — e.g. a gethomepage.dev Custom API widget — can map the numeric
    fields directly. Reuses the same 60s in-process cache as the fragment.

    Returns:
        JSON object with ``claude``, ``minimax``, and ``codex`` usage snapshots.
    """
    return JSONResponse(get_llm_usage())


@router.get("/llm/fragment", response_class=HTMLResponse)
def llm_usage_fragment(request: Request) -> Any:
    """Return the LLM usage footer fragment for the dashboard status bar.

    Args:
        request: The current FastAPI request.

    Returns:
        HTML fragment with Claude, MiniMax, and Codex usage bars.
    """
    usage = get_llm_usage()
    claude = usage["claude"]
    minimax = usage["minimax"]
    # Codex was added after the original Claude+MiniMax pair (R-00075); fall back
    # to a zeroed snapshot if a stale in-process cache predates the upgrade.
    codex = usage.get("codex") or {
        "block_pct": 0,
        "week_pct": 0,
        "block_reset": None,
        "week_reset": None,
        "plan_type": None,
        "status": "error",  # stale cache → surface a warning rather than silent 0%
    }
    codex_status = codex.get("status") or "ok"
    codex_warning = _CODEX_WARNING_MAP.get(codex_status)
    return request.app.state.templates.TemplateResponse(
        request,
        "fragments/llm_usage_footer.html",
        {
            "claude_5h_pct": claude["block_pct"],
            "claude_7d_pct": claude["week_pct"],
            "claude_reset": claude.get("block_reset"),
            "claude_7d_reset": claude.get("week_reset"),
            "minimax_5h_pct": minimax["block_pct"],
            "claude_5h_color": _bar_color(claude["block_pct"]),
            "claude_7d_color": _bar_color(claude["week_pct"]),
            "minimax_5h_color": _bar_color(minimax["block_pct"]),
            "minimax_reset": minimax.get("block_reset"),
            "minimax_5h_used": minimax.get("used"),
            "minimax_5h_total": minimax.get("total"),
            "codex_5h_pct": codex["block_pct"],
            "codex_7d_pct": codex["week_pct"],
            "codex_5h_reset": codex.get("block_reset"),
            "codex_7d_reset": codex.get("week_reset"),
            "codex_5h_color": _bar_color(codex["block_pct"]),
            "codex_7d_color": _bar_color(codex["week_pct"]),
            "codex_plan_type": codex.get("plan_type"),
            "codex_warning": codex_warning,
            "codex_status": codex_status,
        },
    )
