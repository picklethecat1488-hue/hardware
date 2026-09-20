"""Capacitive sensing electrode and flexible PCB ground hatch geometry generator."""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any
from model.pcb import CapacitiveElectrodeModel, FlexZoneModel


@dataclass
class HatchLine:
    """Represents a single cross-hatch line segment for capacitive ground pours."""

    start: Tuple[float, float]
    end: Tuple[float, float]
    width_mm: float


@dataclass
class CapacitiveGeometry:
    """Full geometric representation of a capacitive sensor layout."""

    name: str
    tx_fingers: List[List[Tuple[float, float]]] = field(default_factory=list)
    rx_fingers: List[List[Tuple[float, float]]] = field(default_factory=list)
    guard_ring: List[Tuple[float, float]] = field(default_factory=list)
    hatch_lines: List[HatchLine] = field(default_factory=list)


class CapacitiveSensingGenerator:
    """Synthesizes capacitive electrode patterns, driven shield guard tracks, and hatched ground planes."""

    def __init__(self, config: CapacitiveElectrodeModel, center: Tuple[float, float] = (0.0, 0.0)):
        """Initialize generator with electrode model and placement coordinates."""
        self.config = config
        self.cx, self.cy = center

    def generate(self) -> CapacitiveGeometry:
        """Generate all copper geometric primitives for the capacitive sensor."""
        geom = CapacitiveGeometry(name=self.config.name)
        w, l = self.config.area_mm

        # 1. Generate Interdigital Comb Electrodes
        if self.config.shape == "interdigital":
            geom.tx_fingers, geom.rx_fingers = self._generate_interdigital_combs(w, l)
        else:
            # Solid touch pad rectangular bounds
            half_w = w / 2.0
            half_l = l / 2.0
            pad_poly = [
                (self.cx - half_w, self.cy - half_l),
                (self.cx + half_w, self.cy - half_l),
                (self.cx + half_w, self.cy + half_l),
                (self.cx - half_w, self.cy + half_l),
            ]
            geom.tx_fingers = [pad_poly]

        # 2. Generate Driven Shield Guard Ring if requested
        if self.config.drive_shield:
            geom.guard_ring = self._generate_guard_ring(w, l, offset_mm=0.8)

        # 3. Generate 45-degree Cross-Hatched Ground Fill
        if self.config.hatch_ground_pour:
            geom.hatch_lines = self._generate_hatched_ground(w, l)

        return geom

    def _generate_interdigital_combs(
        self, width_mm: float, length_mm: float
    ) -> Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]:
        """Generate interleaved TX and RX comb fingers for mutual capacitance measurement."""
        tx_combs = []
        rx_combs = []

        half_w = width_mm / 2.0
        half_l = length_mm / 2.0
        busbar_width = 0.50
        finger_w = (self.config.pitch_mm - self.config.gap_mm) / 2.0
        gap = self.config.gap_mm

        # TX busbar on West (-X), RX busbar on East (+X)
        tx_busbar = [
            (self.cx - half_w, self.cy - half_l),
            (self.cx - half_w + busbar_width, self.cy - half_l),
            (self.cx - half_w + busbar_width, self.cy + half_l),
            (self.cx - half_w, self.cy + half_l),
        ]
        rx_busbar = [
            (self.cx + half_w - busbar_width, self.cy - half_l),
            (self.cx + half_w, self.cy - half_l),
            (self.cx + half_w, self.cy + half_l),
            (self.cx + half_w - busbar_width, self.cy + half_l),
        ]
        tx_combs.append(tx_busbar)
        rx_combs.append(rx_busbar)

        # Interleaved fingers extending across Y axis
        finger_length = width_mm - (2.0 * busbar_width) - gap
        num_fingers = int(length_mm / self.config.pitch_mm)

        for i in range(num_fingers):
            y_pos = self.cy - half_l + (i * self.config.pitch_mm) + (self.config.pitch_mm / 2.0)
            if i % 2 == 0:
                # TX finger extending West to East
                fx_start = self.cx - half_w + busbar_width
                fx_end = fx_start + finger_length
                finger = [
                    (fx_start, y_pos - finger_w / 2.0),
                    (fx_end, y_pos - finger_w / 2.0),
                    (fx_end, y_pos + finger_w / 2.0),
                    (fx_start, y_pos + finger_w / 2.0),
                ]
                tx_combs.append(finger)
            else:
                # RX finger extending East to West
                fx_start = self.cx + half_w - busbar_width
                fx_end = fx_start - finger_length
                finger = [
                    (fx_start, y_pos - finger_w / 2.0),
                    (fx_end, y_pos - finger_w / 2.0),
                    (fx_end, y_pos + finger_w / 2.0),
                    (fx_start, y_pos + finger_w / 2.0),
                ]
                rx_combs.append(finger)

        return tx_combs, rx_combs

    def _generate_guard_ring(
        self, width_mm: float, length_mm: float, offset_mm: float = 0.8
    ) -> List[Tuple[float, float]]:
        """Generate active guard ring surrounding sensing electrode envelope."""
        half_w = (width_mm / 2.0) + offset_mm
        half_l = (length_mm / 2.0) + offset_mm
        return [
            (self.cx - half_w, self.cy - half_l),
            (self.cx + half_w, self.cy - half_l),
            (self.cx + half_w, self.cy + half_l),
            (self.cx - half_w, self.cy + half_l),
            (self.cx - half_w, self.cy - half_l),
        ]

    def _generate_hatched_ground(self, width_mm: float, length_mm: float) -> List[HatchLine]:
        """Generate 45-degree angled cross-hatching grid lines to prevent parasitic capacitance."""
        lines = []
        pitch = self.config.hatch_pitch_mm
        line_w = self.config.hatch_line_width_mm

        half_w = width_mm / 2.0
        half_l = length_mm / 2.0

        # Generate diagonal lines in local coordinates centered at (cx, cy)
        diag_span = half_w + half_l
        num_lines = int(math.ceil(diag_span / pitch))

        for i in range(-num_lines, num_lines + 1):
            offset = i * pitch

            # 1. +45 degree line: v - u = offset -> v = u + offset
            pts_pos: List[Tuple[float, float]] = []
            v_at_umin = -half_w + offset
            if -half_l <= v_at_umin <= half_l:
                pts_pos.append((-half_w, v_at_umin))
            v_at_umax = half_w + offset
            if -half_l <= v_at_umax <= half_l:
                pts_pos.append((half_w, v_at_umax))
            u_at_vmin = -half_l - offset
            if -half_w <= u_at_vmin <= half_w and not any(
                math.hypot(u_at_vmin - p[0], -half_l - p[1]) < 1e-4 for p in pts_pos
            ):
                pts_pos.append((u_at_vmin, -half_l))
            u_at_vmax = half_l - offset
            if -half_w <= u_at_vmax <= half_w and not any(
                math.hypot(u_at_vmax - p[0], half_l - p[1]) < 1e-4 for p in pts_pos
            ):
                pts_pos.append((u_at_vmax, half_l))

            if len(pts_pos) == 2:
                lines.append(
                    HatchLine(
                        start=(round(self.cx + pts_pos[0][0], 4), round(self.cy + pts_pos[0][1], 4)),
                        end=(round(self.cx + pts_pos[1][0], 4), round(self.cy + pts_pos[1][1], 4)),
                        width_mm=line_w,
                    )
                )

            # 2. -45 degree line: v + u = offset -> v = -u + offset
            pts_neg: List[Tuple[float, float]] = []
            v_at_umin_neg = half_w + offset
            if -half_l <= v_at_umin_neg <= half_l:
                pts_neg.append((-half_w, v_at_umin_neg))
            v_at_umax_neg = -half_w + offset
            if -half_l <= v_at_umax_neg <= half_l:
                pts_neg.append((half_w, v_at_umax_neg))
            u_at_vmin_neg = offset + half_l
            if -half_w <= u_at_vmin_neg <= half_w and not any(
                math.hypot(u_at_vmin_neg - p[0], -half_l - p[1]) < 1e-4 for p in pts_neg
            ):
                pts_neg.append((u_at_vmin_neg, -half_l))
            u_at_vmax_neg = offset - half_l
            if -half_w <= u_at_vmax_neg <= half_w and not any(
                math.hypot(u_at_vmax_neg - p[0], half_l - p[1]) < 1e-4 for p in pts_neg
            ):
                pts_neg.append((u_at_vmax_neg, half_l))

            if len(pts_neg) == 2:
                lines.append(
                    HatchLine(
                        start=(round(self.cx + pts_neg[0][0], 4), round(self.cy + pts_neg[0][1], 4)),
                        end=(round(self.cx + pts_neg[1][0], 4), round(self.cy + pts_neg[1][1], 4)),
                        width_mm=line_w,
                    )
                )

        return lines
