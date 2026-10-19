"""Jumper bridge drawing utility for crossing schematic wires."""

from typing import List, Tuple

import matplotlib.axes
import matplotlib.patches as patches

from provider.schematic.constants import JUMPER_BRIDGE_RADIUS_MM


def draw_vertical_wire_with_jumpers(
    ax: matplotlib.axes.Axes,
    x_v: float,
    y_start: float,
    y_end: float,
    col: str,
    h_wire_segments: List[Tuple[float, float, float, str, str]],
    net_name: str = "",
) -> None:
    """Render a vertical wire segment with semicircular jumper bridge loops over crossing horizontal wires.

    Args:
        ax: Matplotlib axes to render onto.
        x_v: X coordinate of vertical wire.
        y_start: Starting Y coordinate.
        y_end: Ending Y coordinate.
        col: Color string of wire.
        h_wire_segments: List of horizontal wire segments (x_start, x_end, y, net_name, col).
        net_name: Net name of current vertical wire.
    """
    r = JUMPER_BRIDGE_RADIUS_MM
    y_min = min(y_start, y_end)
    y_max = max(y_start, y_end)

    crossings: List[float] = []
    for h_start, h_end, h_y, h_net, _ in h_wire_segments:
        if h_net and net_name and h_net == net_name:
            continue
        hx_min = min(h_start, h_end)
        hx_max = max(h_start, h_end)
        if (hx_min + 0.5 < x_v < hx_max - 0.5) and (y_min + 0.5 < h_y < y_max - 0.5):
            crossings.append(h_y)

    s = 1.0 if y_end >= y_start else -1.0
    crossings.sort(reverse=(s < 0))

    y_curr = y_start
    for y_c in crossings:
        # Vertical segment up to jumper loop
        ax.plot([x_v, x_v], [y_curr, y_c - s * r], color=col, linewidth=1.2, zorder=2)
        # Semicircular jumper bridge loop bulging to the right
        arc = patches.Arc(
            (x_v, y_c),
            width=2 * r,
            height=2 * r,
            angle=0,
            theta1=270,
            theta2=90,
            color=col,
            linewidth=1.2,
            zorder=3,
        )
        ax.add_patch(arc)
        y_curr = y_c + s * r

    # Final vertical segment to endpoint
    ax.plot([x_v, x_v], [y_curr, y_end], color=col, linewidth=1.2, zorder=2)
