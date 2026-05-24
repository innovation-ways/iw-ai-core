"""Batch planner — dependency analysis, execution plan, and diagram generation.

Ported from the iw-doc-plan reference implementation to work with
DB-backed data instead of file-based manifests. Generates:
- Execution plan markdown
- Draw.io XML diagram
- PNG diagram (via Pillow, best-effort)

All outputs are stored in the Batch model columns, not on disk.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC, datetime
from typing import Any

from orch.daemon.scope_overlap import globs_intersect  # noqa: E402
from orch.design_doc_parser import strip_excluded_sections

logger = logging.getLogger("iw-ai-core.batch_planner")

# ---------------------------------------------------------------------------
# Draw.io colors
# ---------------------------------------------------------------------------

GROUP_COLORS = [
    ("#D4E4F7", "#2E86AB"),  # Group 0: blue
    ("#E8D5B7", "#D4A574"),  # Group 1: amber
    ("#D5E8D4", "#6B8E6B"),  # Group 2: green
    ("#E8D5E8", "#8B6B8E"),  # Group 3: purple
    ("#F7E4D4", "#AB6B2E"),  # Group 4: orange
]

TYPE_COLORS = {
    "Feature": ("#D4E4F7", "#2E86AB"),
    "Issue": ("#C8E6C9", "#82b366"),
    "ChangeRequest": ("#E8D5E8", "#7B2D8E"),
}

_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ---------------------------------------------------------------------------
# Dependency analysis types
# ---------------------------------------------------------------------------


class ItemAnalysis:
    """Analysis result for a single work item in a batch."""

    __slots__ = (
        "item_id",
        "title",
        "item_type",
        "depends_on",
        "has_database_step",
        "affected_files",
        "overlap_with",
        "cross_batch_conflicts",
        "group",
    )

    def __init__(
        self,
        item_id: str,
        title: str,
        item_type: str,
        depends_on: list[str],
        has_database_step: bool,
        affected_files: list[str],
    ) -> None:
        self.item_id = item_id
        self.title = title
        self.item_type = item_type
        self.depends_on = depends_on
        self.has_database_step = has_database_step
        self.affected_files = affected_files
        self.overlap_with: list[str] = []
        self.cross_batch_conflicts: list[tuple[str, str, list[str]]] = []
        self.group = 0


# ---------------------------------------------------------------------------
# File-overlap extraction from design doc content
# ---------------------------------------------------------------------------

# Match any path-looking token that contains at least one directory separator
# and ends in a known source-code extension. Deliberately excludes `.md`,
# `.json`, and `.yaml` to avoid false positives from design docs quoting each
# other or from workflow manifests being referenced across items. The old
# regex only caught `src/` and `frontend/src/` prefixes — that missed every
# path rooted at `orch/`, `dashboard/`, `backend/`, `api/`, etc., which is
# why F-00004 / F-00005 were not flagged as overlapping on DesignerShell.tsx
# (their common file sits under `frontend/src/` and WOULD have matched the
# old regex, but `design_doc_content` was never populated at registration —
# see register() in orch/cli/item_commands.py).
_FILE_PATH_RE = re.compile(
    r"\b[\w][\w./-]*/[\w./-]+"
    r"\.(?:py|pyi|tsx|ts|jsx|js|mjs|cjs|vue|svelte|html|css|scss|sass|sql|sh|bash|go|rs|java|kt|rb|c|h|cpp|hpp|cs)"
    r"\b"
)

# Test-file path fragments: conflicts in test files are trivially resolvable,
# and design docs often list them next to the production files — counting
# them would cause duplicate overlap signals.
_TEST_PATH_MARKERS = ("/tests/", "/test/", "/__tests__/", "conftest", ".test.", ".spec.")


def _is_test_path(path: str) -> bool:
    if path.startswith(("tests/", "test/", "__tests__/")):
        return True
    return any(marker in path for marker in _TEST_PATH_MARKERS)


def extract_affected_files(design_doc: str | None) -> list[str]:
    """Extract affected file paths from a design document.

    Looks for source file paths in tables and code blocks.
    Excludes test files — conflicts there are trivially resolvable.
    Skips ``## Out of Scope`` and ``## Notes`` sections to avoid false-positive
    overlaps from prose mentions (I-00053).
    """
    if not design_doc:
        return []
    cleaned = strip_excluded_sections(design_doc)
    files: set[str] = set()
    for match in _FILE_PATH_RE.finditer(cleaned):
        path = match.group(0)
        if not _is_test_path(path):
            files.add(path)
    return sorted(files)


def has_database_step(steps: list[dict[str, Any]]) -> bool:
    """Check if workflow steps include a database implementation step."""
    for step in steps:
        label = (step.get("agent_label") or "").lower()
        if label in ("database", "database-impl"):
            step_type = step.get("step_type", "")
            if step_type == "implementation":
                return True
    return False


# ---------------------------------------------------------------------------
# Dependency analysis (core logic — works with pre-loaded DB data)
# ---------------------------------------------------------------------------


def analyze_dependencies(
    items_data: list[dict[str, Any]],
    active_items_data: list[dict[str, Any]] | None = None,
) -> dict[str, ItemAnalysis]:
    """Analyze dependencies between items.

    items_data is a list of dicts with keys:
        id, title, type, depends_on (list[str]),
        impacted_paths (list[str]|None) — if present, used in place of regex;
        design_doc_content (str|None) — fallback when impacted_paths absent;
        steps (list of step dicts)

    active_items_data is an optional list of items currently executing in other
    batches, used for cross-batch file overlap detection. Each dict needs:
        id, batch_id, impacted_paths (list[str]|None), design_doc_content (str|None)

    Returns a dict mapping item_id to its ItemAnalysis.
    """
    selected_ids = {d["id"] for d in items_data}
    analysis: dict[str, ItemAnalysis] = {}

    # Phase 1: Build initial analysis from DB data
    for d in items_data:
        # F-00076: prefer impacted_paths column; fall back to regex for items
        # registered before the backfill ran.
        impacted = d.get("impacted_paths")
        if impacted:
            affected = [p for p in impacted if not _is_test_path(p)]
        else:
            # Defensive fallback for items registered before F-00076 backfill ran.
            affected = extract_affected_files(d.get("design_doc_content"))
        db_step = has_database_step(d.get("steps", []))
        # Filter depends_on to only items within this batch
        deps = [dep for dep in (d.get("depends_on") or []) if dep in selected_ids]
        analysis[d["id"]] = ItemAnalysis(
            item_id=d["id"],
            title=d["title"],
            item_type=d["type"],
            depends_on=deps,
            has_database_step=db_step,
            affected_files=affected,
        )

    item_ids = list(analysis.keys())

    # Phase 2: Database step sequencing — items with DB steps run sequentially
    db_items = sorted([iid for iid in item_ids if analysis[iid].has_database_step])
    for i in range(1, len(db_items)):
        dep = db_items[i - 1]
        if dep not in analysis[db_items[i]].depends_on:
            analysis[db_items[i]].depends_on.append(dep)

    # Phase 3: File overlap detection (intra-batch)
    for i, id_a in enumerate(item_ids):
        for id_b in item_ids[i + 1 :]:
            files_a = list(analysis[id_a].affected_files)
            files_b = list(analysis[id_b].affected_files)
            overlap = globs_intersect(files_a, files_b)
            if overlap:
                analysis[id_a].overlap_with.append(id_b)
                analysis[id_b].overlap_with.append(id_a)
                if id_a not in analysis[id_b].depends_on:
                    analysis[id_b].depends_on.append(id_a)

    # Phase 3b: Cross-batch file overlap detection (warning only — no sequencing possible)
    if active_items_data:
        for active in active_items_data:
            # Prefer impacted_paths column; fall back to regex for items
            # registered before the F-00076 backfill ran.
            active_impacted = active.get("impacted_paths")
            if active_impacted:
                active_files = {p for p in active_impacted if not _is_test_path(p)}
            else:
                active_files = set(extract_affected_files(active.get("design_doc_content")))
            if not active_files:
                continue
            active_batch_id = active.get("batch_id", "?")
            active_item_id = active.get("id", "?")
            for iid in item_ids:
                overlap = globs_intersect(list(analysis[iid].affected_files), list(active_files))
                if overlap:
                    analysis[iid].cross_batch_conflicts.append(
                        (active_batch_id, active_item_id, sorted(overlap))
                    )

    # Phase 4: Break circular dependencies
    _break_cycles(analysis, item_ids)

    # Phase 5: Assign execution groups
    _assign_groups(analysis, item_ids)

    return analysis


def _break_cycles(analysis: dict[str, ItemAnalysis], item_ids: list[str]) -> None:
    """Detect and break circular dependencies via DFS."""
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for dep in list(analysis[node].depends_on):
            if dep not in analysis:
                continue
            if dep in in_stack:
                logger.warning("Circular dependency: %s → %s — removing edge", node, dep)
                analysis[node].depends_on.remove(dep)
                return True
            if dep not in visited and _dfs(dep):
                return True
        in_stack.discard(node)
        return False

    for iid in item_ids:
        if iid not in visited:
            _dfs(iid)


def _assign_groups(analysis: dict[str, ItemAnalysis], item_ids: list[str]) -> None:
    """Assign execution groups based on dependency chains."""
    changed = True
    max_iterations = len(item_ids) + 1
    iteration = 0
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        for iid in item_ids:
            deps = analysis[iid].depends_on
            if not deps:
                continue
            max_dep_group = max(analysis[d].group for d in deps if d in analysis)
            needed = max_dep_group + 1
            if analysis[iid].group < needed:
                analysis[iid].group = needed
                changed = True


# ---------------------------------------------------------------------------
# Execution plan markdown
# ---------------------------------------------------------------------------


def generate_execution_plan_md(
    batch_id: str,
    analysis: dict[str, ItemAnalysis],
    max_parallel: int,
) -> str:
    """Generate a markdown execution plan document."""
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    groups: dict[int, list[str]] = {}
    for iid, info in analysis.items():
        groups.setdefault(info.group, []).append(iid)

    lines = [
        f"# Batch Execution Plan: {batch_id}",
        "",
        f"**Created**: {now}",
        f"**Items**: {len(analysis)}",
        f"**Max Parallel**: {max_parallel}",
        f"**Execution Groups**: {len(groups)}",
        "",
        "---",
        "",
        "## Dependency Analysis",
        "",
        "| Item | Type | Title | Group | Depends On | DB Step | Overlap With |",
        "|------|------|-------|-------|------------|---------|--------------|",
    ]

    for iid in sorted(analysis.keys()):
        info = analysis[iid]
        deps = ", ".join(info.depends_on) or "\u2014"
        db = "Yes" if info.has_database_step else "No"
        overlap = ", ".join(info.overlap_with) or "None"
        title = info.title[:60]
        lines.append(
            f"| {iid} | {info.item_type} | {title} | {info.group} | {deps} | {db} | {overlap} |"
        )

    lines.extend(["", "---", "", "## Execution Order", ""])

    for group_num in sorted(groups.keys()):
        group_items = groups[group_num]
        mode = "parallel" if len(group_items) > 1 else "sequential"
        lines.append(f"### Group {group_num} ({mode})")
        lines.append("")
        for iid in sorted(group_items):
            info = analysis[iid]
            lines.append(f"- **{iid}**: {info.title}")
        lines.append("")

    # Intra-batch warnings
    warnings = []
    for iid, info in analysis.items():
        if info.overlap_with:
            warnings.append(
                f"- {iid} has file overlap with {', '.join(info.overlap_with)} "
                "\u2014 sequenced automatically"
            )
    db_items = [iid for iid in analysis if analysis[iid].has_database_step]
    if len(db_items) > 1:
        warnings.append(f"- DB migration items sequenced: {' \u2192 '.join(sorted(db_items))}")

    lines.append("## Warnings")
    lines.append("")
    if warnings:
        lines.extend(warnings)
    else:
        lines.append("- None \u2014 all items are independent.")
    lines.append("")

    # Cross-batch conflict warnings
    cross_batch: list[tuple[str, str, str, list[str]]] = []  # (new_id, batch_id, active_id, files)
    for iid, info in analysis.items():
        for batch_id, active_id, files in info.cross_batch_conflicts:
            cross_batch.append((iid, batch_id, active_id, files))

    lines.append("## \u26a0\ufe0f Cross-Batch Conflicts")
    lines.append("")
    if cross_batch:
        lines.append(
            "> These items share files with items currently executing in another batch. "
            "Merging both batches will require a rebase. "
            "Consider waiting for the active batch to finish before approving this one."
        )
        lines.append("")
        for new_id, batch_id, active_id, files in cross_batch:
            file_list = ", ".join(f"`{f}`" for f in files[:5])
            if len(files) > 5:
                file_list += f" (+{len(files) - 5} more)"
            lines.append(f"- **{new_id}** conflicts with **{active_id}** ({batch_id}): {file_list}")
    else:
        lines.append("- None \u2014 no file overlap with currently active batches.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Draw.io XML generation
# ---------------------------------------------------------------------------


def generate_drawio(
    batch_id: str,
    analysis: dict[str, ItemAnalysis],
    max_parallel: int,
) -> str:
    """Generate draw.io XML for the execution plan diagram."""
    groups: dict[int, list[str]] = {}
    for iid, info in analysis.items():
        groups.setdefault(info.group, []).append(iid)

    cells: list[str] = []
    cell_id = 10

    # Title
    cells.append(
        f'        <mxCell id="title" value="{batch_id}: Execution Plan '
        f'({len(analysis)} items, {len(groups)} group(s))" '
        f'style="text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;'
        f'fontSize=16;fontColor=#1B2A4A;fontStyle=1" vertex="1" parent="1">'
        f'\n          <mxGeometry x="100" y="20" width="600" height="30" as="geometry" />'
        f"\n        </mxCell>"
    )

    y_offset = 70
    node_positions: dict[str, tuple[int, int]] = {}

    for group_num in sorted(groups.keys()):
        group_items = sorted(groups[group_num])
        _fill, stroke = GROUP_COLORS[group_num % len(GROUP_COLORS)]

        container_w = max(160 * len(group_items) + 40, 200)
        container_h = 180
        mode = "parallel" if len(group_items) > 1 else "sequential"
        cells.append(
            f'        <mxCell id="g{group_num}-container" '
            f'value="Group {group_num} ({mode}, max {max_parallel})" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F5F7FA;strokeColor={stroke};'
            f'verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#1B2A4A;arcSize=10;dashed=1" '
            f'vertex="1" parent="1">'
            f'\n          <mxGeometry x="40" y="{y_offset}" width="{container_w}" '
            f'height="{container_h}" as="geometry" />'
            f"\n        </mxCell>"
        )

        x_offset = 60
        for iid in group_items:
            info = analysis[iid]
            type_fill, type_stroke = TYPE_COLORS.get(info.item_type, ("#F5F7FA", "#6B7280"))
            cell_id += 1
            title_esc = info.title[:40].replace("&", "&amp;").replace('"', "&quot;")
            node_x = x_offset
            node_y = y_offset + 35

            cells.append(
                f'        <mxCell id="node-{iid}" '
                f'value="{iid}&#xa;{title_esc}" '
                f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={type_fill};'
                f"strokeColor={type_stroke};fontSize=10;verticalAlign=middle;"
                f'align=center;spacingTop=4" vertex="1" parent="1">'
                f'\n          <mxGeometry x="{node_x}" y="{node_y}" '
                f'width="140" height="120" as="geometry" />'
                f"\n        </mxCell>"
            )
            node_positions[iid] = (node_x + 70, node_y + 120)
            x_offset += 160

        y_offset += container_h + 30

    # Dependency arrows
    for iid, info in analysis.items():
        for dep_id in info.depends_on:
            if dep_id in node_positions and iid in node_positions:
                cells.append(
                    f'        <mxCell id="edge-{dep_id}-{iid}" value="" '
                    f'style="endArrow=classic;html=1;strokeColor=#6B7280;strokeWidth=2;curved=1" '
                    f'edge="1" parent="1" source="node-{dep_id}" target="node-{iid}">'
                    f'\n          <mxGeometry relative="1" as="geometry" />'
                    f"\n        </mxCell>"
                )

    page_h = y_offset + 50
    now_iso = datetime.now(UTC).isoformat()

    return (
        f'<mxfile host="app.diagrams.net" modified="{now_iso}" '
        f'agent="iw-ai-core" etag="{batch_id.lower()}-plan" '
        f'version="24.0.0" type="device">\n'
        f'  <diagram name="{batch_id} Execution Plan" id="{batch_id.lower()}-plan">\n'
        f'    <mxGraphModel dx="1200" dy="{page_h}" grid="1" gridSize="10" '
        f'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
        f'pageScale="1" pageWidth="850" pageHeight="{page_h}" math="0" shadow="0">\n'
        f"      <root>\n"
        f'        <mxCell id="0" />\n'
        f'        <mxCell id="1" parent="0" />\n'
        f"{chr(10).join(cells)}\n"
        f"      </root>\n"
        f"    </mxGraphModel>\n"
        f"  </diagram>\n"
        f"</mxfile>\n"
    )


# ---------------------------------------------------------------------------
# PNG generation (Pillow, best-effort)
# ---------------------------------------------------------------------------

_FONT_SIZES = [15, 12, 11, 10]


def _load_fonts() -> tuple[Any, ...]:
    """Load DejaVu fonts, falling back to the PIL default."""
    fonts: list[Any] = []
    for size in _FONT_SIZES:
        try:
            from PIL import ImageFont  # noqa: PLC0415

            try:
                path = _DEJAVU_BOLD if size > 12 else _DEJAVU
                fonts.append(ImageFont.truetype(path, size))
            except OSError:
                fonts.append(ImageFont.load_default())
        except ImportError:
            fonts.append(None)
    return tuple(fonts)


def generate_png(
    batch_id: str,
    analysis: dict[str, ItemAnalysis],
    max_parallel: int,
) -> bytes | None:
    """Generate a PNG execution plan diagram as bytes.

    Returns the PNG bytes on success, None on failure (best-effort).
    """
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except ImportError:
        logger.warning("Pillow not available — skipping PNG export")
        return None

    try:
        canvas_w = 860
        margin_x = 40
        title_h = 60
        group_h = 190
        group_gap = 28
        node_w = 140
        node_h = 120
        node_stride = 160
        node_top_pad = 38

        groups: dict[int, list[str]] = {}
        for iid, info in analysis.items():
            groups.setdefault(info.group, []).append(iid)

        total_h = title_h + len(groups) * (group_h + group_gap) + margin_x

        img = Image.new("RGB", (canvas_w, total_h), "white")
        draw = ImageDraw.Draw(img)
        f_title, f_group, f_node_id, f_node_text = _load_fonts()

        # Title
        title = f"{batch_id} \u00b7 Execution Plan  ({len(analysis)} items, {len(groups)} group(s))"
        draw.text(
            (canvas_w // 2, title_h // 2),
            title,
            fill="#1B2A4A",
            font=f_title,
            anchor="mm",
        )

        node_centres: dict[str, tuple[int, int]] = {}
        y = title_h

        for group_num in sorted(groups.keys()):
            group_items = sorted(groups[group_num])
            _fill_hex, stroke_hex = GROUP_COLORS[group_num % len(GROUP_COLORS)]

            container_w = max(node_stride * len(group_items) + node_w // 2, 200)
            x0, y0 = margin_x, y
            x1, y1 = x0 + container_w, y0 + group_h

            draw.rounded_rectangle(
                [x0, y0, x1, y1],
                radius=10,
                fill="#F5F7FA",
                outline=stroke_hex,
                width=2,
            )
            mode = "parallel" if len(group_items) > 1 else "sequential"
            label = f"Group {group_num}  \u00b7  {mode}  \u00b7  max {max_parallel} parallel"
            draw.text((x0 + 12, y0 + 9), label, fill="#1B2A4A", font=f_group)

            nx = x0 + 20
            for iid in group_items:
                info = analysis[iid]
                type_fill, type_stroke = TYPE_COLORS.get(info.item_type, ("#F5F7FA", "#6B7280"))

                ny = y0 + node_top_pad
                draw.rounded_rectangle(
                    [nx, ny, nx + node_w, ny + node_h],
                    radius=7,
                    fill=type_fill,
                    outline=type_stroke,
                    width=2,
                )

                draw.text(
                    (nx + node_w // 2, ny + 18),
                    iid,
                    fill="#1B2A4A",
                    font=f_node_id,
                    anchor="mm",
                )
                draw.text(
                    (nx + node_w // 2, ny + 34),
                    info.item_type,
                    fill=type_stroke,
                    font=f_node_text,
                    anchor="mm",
                )

                title_text = info.title[:50]
                mid = len(title_text) // 2
                split = title_text.rfind(" ", 0, mid + 10)
                if split == -1 or split < mid - 10:
                    split = mid
                line1 = title_text[:split].strip()
                line2 = title_text[split:].strip()
                draw.text(
                    (nx + node_w // 2, ny + 52),
                    line1,
                    fill="#374151",
                    font=f_node_text,
                    anchor="mm",
                )
                if line2:
                    draw.text(
                        (nx + node_w // 2, ny + 65),
                        line2,
                        fill="#374151",
                        font=f_node_text,
                        anchor="mm",
                    )

                node_centres[iid] = (nx + node_w // 2, ny + node_h)
                nx += node_stride

            y += group_h + group_gap

        # Dependency arrows
        for iid, info in analysis.items():
            for dep_id in info.depends_on:
                if dep_id not in node_centres or iid not in node_centres:
                    continue
                ax, ay = node_centres[dep_id]
                bx, by = node_centres[iid]
                draw.line([ax, ay, bx, by], fill="#6B7280", width=2)
                angle = math.atan2(by - ay, bx - ax)
                aw = 8
                pts = [
                    (bx, by),
                    (
                        int(bx - aw * math.cos(angle - 0.4)),
                        int(by - aw * math.sin(angle - 0.4)),
                    ),
                    (
                        int(bx - aw * math.cos(angle + 0.4)),
                        int(by - aw * math.sin(angle + 0.4)),
                    ),
                ]
                draw.polygon(pts, fill="#6B7280")

        import io  # noqa: PLC0415

        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        logger.info("Generated execution plan PNG (%d bytes)", buf.tell())
        return buf.getvalue()

    except Exception:
        logger.warning("PNG generation failed", exc_info=True)
        return None
