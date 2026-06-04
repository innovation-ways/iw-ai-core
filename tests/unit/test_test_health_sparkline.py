"""Unit tests for the test-health SVG sparkline helper.

These test the rendering logic in isolation — no DB, no HTTP client.
"""

from __future__ import annotations

import pytest


class TestSparkline:
    """Test the server-side SVG sparkline builder."""

    def test_sparkline_ascending_values(self) -> None:
        """Ascending [1..5] → y-coords monotonically decrease (SVG y-axis is inverted)."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        svg = build_sparkline_svg(values)

        # Must contain a <path> element with an M command
        assert "<path" in svg
        assert "M " in svg, f"No path 'M' command found in: {svg}"

        # Extract y-coords from path M/L commands: "M x,y L x,y ..."
        import re

        coords = re.findall(r"[ML]\s+([\d.]+),([\d.]+)", svg)
        assert len(coords) >= 2, f"Not enough path coordinates in: {svg}"
        ys = [float(y) for _, y in coords]

        # SVG y-axis: smaller value → larger y pixel
        # Ascending [1..5] → y should monotonically decrease
        for i in range(1, len(ys)):
            assert ys[i] <= ys[i - 1], (
                f"Y-coords not monotonically decreasing at index {i}: {ys} "
                "(ascending input [1..5] should give descending y values)"
            )

    def test_sparkline_empty_returns_none(self) -> None:
        """Given an empty list, the helper returns None (template handles None → 'no data yet')."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        svg = build_sparkline_svg([])

        # Must return None for empty input
        assert svg is None, f"Empty list should return None, got: {svg!r}"

    def test_sparkline_single_value(self) -> None:
        """A single data point produces an SVG with one circle and no path (just M, no L)."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        svg = build_sparkline_svg([42.0])

        assert svg is not None
        assert "<svg" in svg
        # Single point: no <path d="M ... L ...>, only a circle
        assert "<circle" in svg
        assert "M " not in svg or "L " not in svg, (
            f"Single value should not have M...L path, got: {svg}"
        )

    def test_sparkline_descending_values(self) -> None:
        """Given descending values [5, 4, 3, 2, 1], y-coords monotonically increase."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        svg = build_sparkline_svg(values)

        assert svg is not None

        import re

        coords = re.findall(r"[ML]\s+([\d.]+),([\d.]+)", svg)
        assert len(coords) >= 2, f"Not enough path coordinates in: {svg}"
        ys = [float(y) for _, y in coords]

        for i in range(1, len(ys)):
            assert ys[i] >= ys[i - 1], (
                f"Y-coords not monotonically increasing at index {i}: {ys} "
                "(descending input [5..1] should give ascending y values)"
            )

    def test_sparkline_flat_values(self) -> None:
        """All identical values renders without divide-by-zero."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        svg = build_sparkline_svg([50.0, 50.0, 50.0])
        assert svg is not None
        assert "<path" in svg
        assert "M " in svg
        # Divide-by-zero guard: identical values must produce finite, equal
        # y-coordinates (a flat line), not NaN/inf from a zero range.
        import re

        coords = re.findall(r"[ML]\s+([\d.]+),([\d.]+)", svg)
        assert len(coords) == 3, f"expected 3 plotted points for 3 inputs, got: {coords}"
        ys = [float(y) for _, y in coords]
        assert len(set(ys)) == 1, f"identical inputs must render a flat line; ys={ys}"

    def test_sparkline_two_points(self) -> None:
        """Two points: M x0,y0 L x1,y1."""
        from dashboard.routers._test_health_helpers import build_sparkline_svg

        svg = build_sparkline_svg([10.0, 20.0])

        assert svg is not None
        assert "<path" in svg
        assert "M " in svg
        assert "L " in svg
        # Should have exactly two coord pairs
        import re

        coords = re.findall(r"[ML]\s+([\d.]+),([\d.]+)", svg)
        assert len(coords) == 2, f"Expected 2 coords for 2 points, got: {coords}"
