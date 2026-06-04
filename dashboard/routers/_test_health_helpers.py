"""Shared helpers for the test-health htmx fragment (CR-00086 S05).

Used by both dashboard/routers/tests.py and dashboard/routers/quality.py.
Factor here so S06 code review can assert zero duplication between the two routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from orch.db.models import Project, TestHealthSnapshot
from orch.test_health_service import trend as _trend

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

METRICS: list[tuple[str, str, str]] = [
    ("mutation_score", "Mutation Score", "%.1f%%"),
    ("coverage_pct", "Coverage", "%.1f%%"),
    ("flaky_test_count", "Flaky Tests", "%d"),
    ("assertion_baseline_size", "Assertion Baseline", "%d"),
]
"""(metric_key, human_label, value_format) for each test-health card."""


@dataclass(frozen=True)
class MetricCard:
    """A fully-populated metric card ready for the fragment template."""

    metric: str
    label: str
    value_format: str
    latest_value: float | None
    delta: float | None
    sparkline_data: list[tuple[str, float]]  # list of (ts_iso, value)
    svg: str | None  # rendered SVG string or None (empty-state placeholder in template)
    has_data: bool


def build_test_health_cards(
    project: Project,
    latest_snapshots: dict[str, TestHealthSnapshot],
    db: Session,
) -> list[MetricCard]:
    """Build a list of MetricCard for all four test-health metrics.

    Returns four cards in order.  Cards with no data set has_data=False and
    include a "no data yet" placeholder via the template.
    """
    # Collect trend data for each metric (up to 30 points)
    trend_data: dict[str, list[TestHealthSnapshot]] = {}
    for metric_key, _, _ in METRICS:
        trend_data[metric_key] = _trend(db, project.id, metric_key, limit=30)

    # Determine previous snapshots for delta computation
    # Group by (project_id, metric) and find the second-latest timestamp
    from sqlalchemy import select

    prev_ts: dict[str, float | None] = {}
    for metric_key in [k for k, _, _ in METRICS if k in latest_snapshots]:
        latest_ts = latest_snapshots[metric_key].ts
        latest_val = latest_snapshots[metric_key].value
        # Find the second-most-recent snapshot for this metric
        prev_row = db.execute(
            select(TestHealthSnapshot.value)
            .where(
                TestHealthSnapshot.project_id == project.id,
                TestHealthSnapshot.metric == metric_key,
                TestHealthSnapshot.ts < latest_ts,
            )
            .order_by(TestHealthSnapshot.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        if prev_row is not None:
            prev_ts[metric_key] = float(latest_val) - float(prev_row)
        else:
            prev_ts[metric_key] = None

    cards: list[MetricCard] = []
    for metric_key, label, fmt in METRICS:
        latest = latest_snapshots.get(metric_key)
        current_value: float | None = float(latest.value) if latest is not None else None
        delta = prev_ts.get(metric_key)
        # has_data: this metric has trend data (captured at least once)
        has_data = len(trend_data.get(metric_key, [])) > 0

        # Build sparkline data: sorted oldest→newest for the SVG
        rows = sorted(trend_data.get(metric_key, []), key=lambda r: r.ts)
        sparkline_data: list[tuple[str, float]] = [
            (row.ts.isoformat().replace("+00:00", "Z"), row.value) for row in rows
        ]

        # Build sparkline: convert (ts_iso, value) to plain float list
        values = [v for _, v in sparkline_data]
        svg = build_sparkline_svg(values)

        cards.append(
            MetricCard(
                metric=metric_key,
                label=label,
                value_format=fmt,
                latest_value=current_value,
                delta=delta,
                sparkline_data=sparkline_data,
                svg=svg,
                has_data=has_data,
            )
        )

    return cards


# ---------------------------------------------------------------------------
# SVG sparkline builder
# ---------------------------------------------------------------------------

SVG_WIDTH = 80
SVG_HEIGHT = 28


def build_sparkline_svg(values: list[float]) -> str | None:
    """Build an inline SVG sparkline from a list of values.

    Returns an SVG string (HTML-escaped so it can be safely rendered in a
    Jinja2 template with autoescape enabled) or None when values is empty
    (caller handles the None → "no data yet" placeholder).
    """
    if not values:
        return None

    n = len(values)
    if n == 1:
        # Single point — just a circle, no path
        cx, cy = SVG_WIDTH / 2, SVG_HEIGHT / 2
        vb = f"0 0 {SVG_WIDTH} {SVG_HEIGHT}"
        return (
            f'<svg width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="{vb}" '
            f'class="inline-block" aria-hidden="true">'
            f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="currentColor" opacity="0.6"/>'
            f"</svg>"
        )

    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v
    if range_v == 0:
        range_v = 1.0  # all values identical — render at mid-height

    pad_x = 4
    pad_y = 3
    chart_w = SVG_WIDTH - 2 * pad_x
    chart_h = SVG_HEIGHT - 2 * pad_y

    points: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        x = pad_x + (i / (n - 1)) * chart_w
        y = pad_y + (1 - (v - min_v) / range_v) * chart_h
        points.append((round(x, 1), round(y, 1)))

    # Build path: M x0,y0 L x1,y1 L ...
    # All coordinates to 1 decimal place
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    # Endpoint dots
    last_x, last_y = points[-1]
    dots = f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2" fill="currentColor" opacity="0.8"/>'

    # First-point dot (subtle)
    first_x, first_y = points[0]
    dots += (
        f'<circle cx="{first_x:.1f}" cy="{first_y:.1f}" r="1.5" fill="currentColor" opacity="0.4"/>'
    )

    return (
        f'<svg width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        f'class="inline-block" aria-hidden="true">'
        f'<path d="{d}" fill="none" stroke="currentColor" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.7"/>'
        f"{dots}"
        f"</svg>"
    )
