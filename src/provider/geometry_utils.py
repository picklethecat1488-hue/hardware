"""Shared geometric primitives and computational geometry algorithms."""

from typing import Sequence, Tuple


def point_in_polygon(x: float, y: float, polygon: Sequence[Tuple[float, float]]) -> bool:
    """Test whether a 2D point (x, y) is enclosed within a polygon boundary using ray casting.

    Args:
        x: X coordinate of the test point.
        y: Y coordinate of the test point.
        polygon: Ordered sequence of (x, y) vertices defining the closed polygon boundary.

    Returns:
        True if the point lies strictly within the interior of the polygon, False otherwise.
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside
