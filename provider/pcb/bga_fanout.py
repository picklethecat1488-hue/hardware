"""BGA footprint generation and fanout breakout router for fine-pitch modern architectures."""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from model.pcb import BgaFanoutModel


@dataclass
class BGAPad:
    """Represents a single ball pad in a BGA matrix."""

    name: str
    row: int
    col: int
    x_mm: float
    y_mm: float
    ring: int  # 0 = outermost perimeter ring, 1 = second ring, etc.
    quadrant: int  # 1 (+x, +y), 2 (-x, +y), 3 (-x, -y), 4 (+x, -y)


@dataclass
class BGAEscapeRoute:
    """Breakout trace and via for a single BGA pin."""

    pad: BGAPad
    via_x_mm: float
    via_y_mm: float
    escape_layer: str
    trace_path: List[Tuple[float, float]] = field(default_factory=list)


class BGAFanoutRouter:
    """Generates matrix pads and escape fanout routing for fine-pitch BGA packages."""

    def __init__(
        self,
        rows: int,
        cols: int,
        config: BgaFanoutModel,
        center_pos: Tuple[float, float] = (0.0, 0.0),
    ):
        """Initialize the router with matrix dimensions, fanout model, and board coordinates.

        Args:
            rows: Total number of ball rows.
            cols: Total number of ball columns.
            config: BgaFanoutModel configuration parameters.
            center_pos: (x, y) board coordinates of package center.
        """
        self.rows = rows
        self.cols = cols
        self.config = config
        self.cx, self.cy = center_pos

    @staticmethod
    def get_pin_label(row: int, col: int) -> str:
        """Convert 0-indexed (row, col) to standard BGA alphanumeric designation (e.g. A1, B3, H12).

        Letters I, O, Q, S, X, Z are conventionally skipped per JEDEC standards to avoid confusion.
        """
        jedec_letters = "ABCDEFGHJKLMNPRTUVWY"
        row_str = ""
        r = row
        while r >= len(jedec_letters):
            row_str += jedec_letters[r // len(jedec_letters) - 1]
            r %= len(jedec_letters)
        row_str += jedec_letters[r]
        return f"{row_str}{col + 1}"

    def generate_pads(self) -> List[BGAPad]:
        """Generate all BGA pads with accurate coordinates, ring indices, and quadrants."""
        pads = []
        p = self.config.pitch_mm
        total_w = (self.cols - 1) * p
        total_h = (self.rows - 1) * p

        start_x = self.cx - (total_w / 2.0)
        start_y = self.cy + (total_h / 2.0)

        for r in range(self.rows):
            for c in range(self.cols):
                px = start_x + (c * p)
                py = start_y - (r * p)

                # Ring index = distance to closest edge
                ring = min(r, self.rows - 1 - r, c, self.cols - 1 - c)

                # Quadrant determination relative to package center
                dx = px - self.cx
                dy = py - self.cy
                if dx >= 0 and dy >= 0:
                    quad = 1
                elif dx < 0 and dy >= 0:
                    quad = 2
                elif dx < 0 and dy < 0:
                    quad = 3
                else:
                    quad = 4

                pin_name = self.get_pin_label(r, c)
                pads.append(
                    BGAPad(
                        name=pin_name,
                        row=r,
                        col=c,
                        x_mm=px,
                        y_mm=py,
                        ring=ring,
                        quadrant=quad,
                    )
                )

        return pads

    def route_fanouts(self, pads: Optional[List[BGAPad]] = None) -> List[BGAEscapeRoute]:
        """Generate breakout routes and vias for all BGA pads.

        Outer rings (ring 0 and 1) use diagonal dogbone fanout to outer interstitial vias.
        Inner rings (ring 2+) use Via-In-Pad (VIPPO) or internal stripline layer breakouts.
        """
        if pads is None:
            pads = self.generate_pads()

        routes = []
        p = self.config.pitch_mm
        dogbone_offset = p * 0.50  # Diagonal interstitial offset

        for pad in pads:
            if pad.ring in (0, 1) or self.config.strategy == "dogbone":
                # Dogbone diagonal breakout pointing away from center (quadrant-aligned)
                sign_x = 1.0 if pad.quadrant in (1, 4) else -1.0
                sign_y = 1.0 if pad.quadrant in (1, 2) else -1.0

                vx = pad.x_mm + (sign_x * dogbone_offset)
                vy = pad.y_mm + (sign_y * dogbone_offset)
                layer = self.config.escape_layers[0] if self.config.escape_layers else "F.Cu"

                routes.append(
                    BGAEscapeRoute(
                        pad=pad,
                        via_x_mm=vx,
                        via_y_mm=vy,
                        escape_layer=layer,
                        trace_path=[(pad.x_mm, pad.y_mm), (vx, vy)],
                    )
                )
            else:
                # Via-in-Pad (VIPPO): Concentric plated-over via dropping directly down
                layer_idx = min(pad.ring - 1, len(self.config.escape_layers) - 1)
                layer = self.config.escape_layers[layer_idx]

                routes.append(
                    BGAEscapeRoute(
                        pad=pad,
                        via_x_mm=pad.x_mm,
                        via_y_mm=pad.y_mm,
                        escape_layer=layer,
                        trace_path=[(pad.x_mm, pad.y_mm)],
                    )
                )

        return routes
