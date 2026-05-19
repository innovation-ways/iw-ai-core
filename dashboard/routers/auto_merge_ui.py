from __future__ import annotations

import difflib
import subprocess
from pathlib import Path as FsPath
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import TemplateNotFound
from markupsafe import Markup
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from dashboard.dependencies import get_db
from orch import auto_merge_aggregator as agg
from orch.daemon.auto_merge import EVENT_AUTO_MERGE_CONFIG_UPDATED, AutoMergeConfig
from orch.db.models import (
    AgentRuntimeOption,
    AutoMergeProjectConfig,
    DaemonEvent,
    MergeAutoVerdict,
    Project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/project/{project_id}")

EXECUTOR_TOML = FsPath(__file__).resolve().parents[2] / "executor" / "auto_merge.toml"
MAX_VERDICT_NOTES_BYTES = 8192
REPO_ROOT = FsPath(__file__).resolve().parents[2]
ALLOWED_VERDICTS = {"pending", "correct", "wrong", "partial"}
SORT_VALUES = ("created_at", "event_type", "entity_id", "verdict")
DIR_VALUES = ("asc", "desc")


class VerdictBody(BaseModel):
    verdict: str
    notes: str = ""


class ConfigBody(BaseModel):
    phase: int | None = None
    runtime_option_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_global_sentinels(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("phase", "runtime_option_id"):
                val = data.get(key)
                if isinstance(val, str) and val.strip().lower() in {"", "global", "null", "none"}:
                    data[key] = None
        return data


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _operator(request: Request) -> str:
    return request.headers.get("X-Operator") or "dashboard"


def _accepts_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()


def _render_fragment(request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
    templates = request.app.state.templates
    try:
        return cast("HTMLResponse", templates.TemplateResponse(request, template_name, context))
    except TemplateNotFound:
        return HTMLResponse(f"<!-- placeholder: {template_name} -->")


def _load_status(db: Session, project_id: str) -> agg.StatusSnapshot:
    toml_config = AutoMergeConfig.load(str(EXECUTOR_TOML))[0]
    return agg.get_status_snapshot(db, project_id, toml_config)


@router.get("/auto-merge", response_class=HTMLResponse)
def auto_merge_page(
    project_id: str, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    project = _get_project_or_404(db, project_id)
    status = _load_status(db, project_id)
    request.state.auto_merge_phase_for_chip = status.config.phase
    request.state.auto_merge_status = status
    request.state.auto_merge_status_for_chip = status
    request.state.suppress_topbar_auto_merge_chip = True
    rows = db.scalars(
        select(AgentRuntimeOption)
        .where(AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.cli_tool, AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
    ).all()
    runtime_options: dict[str, list[AgentRuntimeOption]] = {}
    for row in rows:
        runtime_options.setdefault(row.cli_tool, []).append(row)
    return _render_fragment(
        request,
        "pages/project/auto_merge.html",
        {
            "request": request,
            "current_project": project,
            "status": status,
            "runtime_options": runtime_options,
        },
    )


@router.get("/auto-merge/status", response_class=HTMLResponse)
def auto_merge_status(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    compact: bool = Query(default=False),
) -> HTMLResponse:
    _get_project_or_404(db, project_id)
    status = _load_status(db, project_id)
    if compact and status.config.phase < 1:
        return HTMLResponse("")
    return _render_fragment(
        request,
        "fragments/auto_merge_status_chip.html",
        {
            "request": request,
            "status": status,
            "project_id": project_id,
            "compact": compact,
        },
    )


@router.get("/auto-merge/events", response_class=HTMLResponse)
def auto_merge_events(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=0, ge=0),
    type: str | None = Query(default=None),  # noqa: A002
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="created_at"),
    dir: str = Query(default="desc"),  # noqa: A002
    all: bool = Query(default=False, alias="all"),  # noqa: A002 — shadowing builtin
) -> HTMLResponse:
    _get_project_or_404(db, project_id)
    if sort not in SORT_VALUES:
        raise HTTPException(
            status_code=400, detail=f"sort must be one of {SORT_VALUES}; got {sort!r}"
        )
    if dir not in DIR_VALUES:
        raise HTTPException(status_code=400, detail=f"dir must be one of {DIR_VALUES}; got {dir!r}")

    try:
        rows, total = agg.list_recent_events(
            db,
            project_id,
            page=page,
            page_size=page_size,
            event_type_filter=type,
            include_non_auto_merge=all,
            sort=sort,
            direction=dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    has_more = (page + 1) * page_size < total
    return _render_fragment(
        request,
        "fragments/auto_merge_events_table.html",
        {
            "request": request,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
            "sort": sort,
            "direction": dir,
            "show_all": all,
        },
    )


@router.get("/auto-merge/events/{event_id}", response_class=HTMLResponse)
def auto_merge_event_detail(
    project_id: str,
    request: Request,
    event_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    event = agg.get_event_detail(db, project_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    humanized_title = f"{event.event_type} — {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    # Fetch the raw DaemonEvent to access entity_type (not carried on EventRow)
    raw_event = db.get(DaemonEvent, event_id)
    if raw_event is None or raw_event.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    diffs: list[dict[str, Any]] = []
    if event.event_type == "merge_auto_resolved":
        try:
            llm_calls = (event.metadata or {}).get("llm_calls", [])
            if not isinstance(llm_calls, list):
                llm_calls = []
            for call in llm_calls:
                if not isinstance(call, dict):
                    continue
                file_path = str(call.get("file_path") or "")
                proposed = str(call.get("proposed_content") or "")
                current_text: str | None = None
                git_show_status: Literal["ok", "missing", "timeout"] = "missing"
                if file_path:
                    try:
                        current = subprocess.run(  # noqa: S603,S607
                            ["git", "show", f"main:{file_path}"],  # noqa: S607
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                            cwd=str(REPO_ROOT),
                        )
                        if current.returncode == 0:
                            current_text = current.stdout
                            git_show_status = "ok"
                    except subprocess.TimeoutExpired:
                        current_text = None
                        git_show_status = "timeout"

                if proposed:
                    todesc = "Currently on main"
                    if git_show_status == "timeout":
                        todesc = "(could not read file from main: timeout)"
                    elif git_show_status == "missing":
                        todesc = "(file no longer exists on main)"
                    raw_diff_html = difflib.HtmlDiff(wrapcolumn=80).make_table(
                        proposed.splitlines(),
                        (current_text or "").splitlines(),
                        fromdesc="Proposed by LLM",
                        todesc=todesc,
                    )
                    # difflib.HtmlDiff escapes line content via HTML entities,
                    # so the produced table is safe to mark as Markup.
                    diff_html: Markup | None = Markup(raw_diff_html)  # noqa: S704
                else:
                    diff_html = None
                diffs.append(
                    {
                        "file_path": file_path,
                        "diff_html": diff_html,
                        "current_available": current_text is not None,
                        "git_show_status": git_show_status,
                    }
                )
        except Exception:  # noqa: BLE001
            diffs = []

    return _render_fragment(
        request,
        "fragments/auto_merge_event_detail.html",
        {
            "request": request,
            "event": event,
            "diffs": diffs,
            "verdict": event.verdict,
            "humanized_title": humanized_title,
            "raw_event": raw_event,
        },
    )


@router.post("/auto-merge/events/{event_id}/verdict")
def auto_merge_set_verdict(
    project_id: str,
    event_id: int,
    body: VerdictBody,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    if body.verdict not in ALLOWED_VERDICTS:
        raise HTTPException(
            status_code=400, detail="verdict must be one of pending|correct|wrong|partial"
        )
    if len(body.notes.encode("utf-8")) > MAX_VERDICT_NOTES_BYTES:
        raise HTTPException(status_code=413, detail="notes exceeds max size")

    event = db.get(DaemonEvent, event_id)
    if event is None or event.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if event.event_type != "merge_auto_resolved":
        raise HTTPException(
            status_code=400,
            detail="verdicts only apply to merge_auto_resolved events",
        )

    operator = _operator(request)
    stmt = insert(MergeAutoVerdict).values(
        project_id=project_id,
        daemon_event_id=event_id,
        verdict=body.verdict,
        verdict_notes=body.notes,
        verdicted_by=operator,
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[MergeAutoVerdict.project_id, MergeAutoVerdict.daemon_event_id],
            set_={
                "verdict": body.verdict,
                "verdict_notes": body.notes,
                "verdicted_by": operator,
            },
        )
    )
    db.commit()

    if _accepts_json(request):
        return JSONResponse({"ok": True, "verdict": body.verdict})

    row = agg.get_event_detail(db, project_id, event_id)
    return _render_fragment(
        request,
        "fragments/auto_merge_event_row.html",
        {
            "request": request,
            "row": row,
        },
    )


@router.post("/auto-merge/config")
def auto_merge_set_config(
    project_id: str,
    body: ConfigBody,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    if body.phase not in (None, 0, 1):
        raise HTTPException(status_code=400, detail="phases 2 and 3 are reserved for future CRs")

    if body.runtime_option_id is not None:
        runtime = db.get(AgentRuntimeOption, body.runtime_option_id)
        if runtime is None or not runtime.enabled:
            return JSONResponse(
                status_code=400,
                content={
                    "error": (
                        f"runtime_option {body.runtime_option_id} is disabled — pick an enabled row"
                    )
                },
            )

    old = db.get(AutoMergeProjectConfig, project_id)
    old_payload = {
        "phase": old.phase if old else None,
        "runtime_option_id": old.runtime_option_id if old else None,
    }
    operator = _operator(request)

    if body.phase is None and body.runtime_option_id is None:
        if old is not None:
            db.delete(old)
    else:
        stmt = insert(AutoMergeProjectConfig).values(
            project_id=project_id,
            phase=body.phase,
            runtime_option_id=body.runtime_option_id,
            updated_by=operator,
        )
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=[AutoMergeProjectConfig.project_id],
                set_={
                    "phase": body.phase,
                    "runtime_option_id": body.runtime_option_id,
                    "updated_by": operator,
                },
            )
        )

    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=EVENT_AUTO_MERGE_CONFIG_UPDATED,
            entity_id=project_id,
            entity_type="project",
            message="auto-merge config updated from dashboard",
            event_metadata={
                "old": old_payload,
                "new": {"phase": body.phase, "runtime_option_id": body.runtime_option_id},
                "updated_by": operator,
                "source": "dashboard",
            },
        )
    )
    db.commit()

    if _accepts_json(request):
        return JSONResponse(
            {
                "ok": True,
                "project_id": project_id,
                "phase": body.phase,
                "runtime_option_id": body.runtime_option_id,
            }
        )

    status = _load_status(db, project_id)
    runtime_rows = db.scalars(
        select(AgentRuntimeOption)
        .where(AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.cli_tool, AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
    ).all()
    runtime_options: dict[str, list[AgentRuntimeOption]] = {}
    for row in runtime_rows:
        runtime_options.setdefault(row.cli_tool, []).append(row)
    project = _get_project_or_404(db, project_id)
    settings_html = _render_fragment(
        request,
        "fragments/auto_merge_settings.html",
        {
            "request": request,
            "current_project": project,
            "status": status,
            "runtime_options": runtime_options,
            "just_saved": True,
        },
    ).body.decode()  # type: ignore[union-attr]
    chip_html = _render_fragment(
        request,
        "fragments/auto_merge_status_chip.html",
        {
            "request": request,
            "status": status,
            "project_id": project_id,
            "oob": True,
        },
    ).body.decode()  # type: ignore[union-attr]
    return HTMLResponse(settings_html + chip_html)


@router.get("/auto-merge/rollup", response_class=HTMLResponse)
def auto_merge_rollup(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    window: Literal["7d", "30d"] = Query(default="7d"),
) -> HTMLResponse:
    verdict = agg.get_verdict_rollup(db, project_id, window)
    token_cost = agg.get_token_cost_rollup(db, project_id, window)
    try:
        refuse_list = agg.get_refuse_list_breakdown(db, project_id, window)
    except Exception:  # noqa: BLE001
        refuse_list = []
    return _render_fragment(
        request,
        "fragments/auto_merge_rollup.html",
        {
            "request": request,
            "window": window,
            "verdict_rollup": verdict,
            "token_cost_rollup": token_cost,
            "refuse_list_breakdown": refuse_list,
        },
    )
