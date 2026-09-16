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
        x_min, x_max = self.cx - half_w, self.cx + half_w
        y_min, y_max = self.cy - half_l, self.cy + half_l

        # Generate diagonal lines at +45 deg (y = x + offset) and -45 deg (y = -x + offset)
        diag_span = width_mm + length_mm
        num_lines = int(diag_span / pitch)

        for i in range(-num_lines, num_lines + 1):
            offset = i * pitch

            # 1. +45 degree line: y - x = offset
            pts_pos = []
            y_at_xmin = x_min + offset
            if y_min <= y_at_xmin <= y_max:
                pts_pos.append((x_min, y_at_xmin))
            y_at_xmax = x_max + offset
            if y_min <= y_at_xmax <= y_max:
                pts_pos.append((x_max, y_at_xmax))
            x_at_ymin = y_min - offset
            if x_min <= x_at_ymin <= x_max and (x_at_ymin, y_min) not in pts_pos:
                pts_pos.append((x_at_ymin, y_min))
            x_at_ymax = y_max - offset
            if x_min <= x_at_ymax <= x_max and (x_at_ymax, y_max) not in pts_pos:
                pts_pos.append((x_at_ymax, y_max))

            if len(pts_pos) == 2:
                lines.append(HatchLine(start=pts_pos[0], end=pts_pos[1], width_mm=line_w))

            # 2. -45 degree line: y + x = offset
            pts_neg = []
            y_at_xmin_neg = -x_min + offset
            if y_min <= y_at_xmin_neg <= y_max:
                pts_neg.append((x_min, y_at_xmin_neg))
            y_at_xmax_neg = -x_max + offset
            if y_min <= y_at_xmax_neg <= y_max:
                pts_neg.append((x_max, y_at_xmax_neg))
            x_at_ymin_neg = -y_min + offset
            if x_min <= x_at_ymin_neg <= x_max and (x_at_ymin_neg, y_min) not in pts_neg:
                pts_neg.append((x_at_ymin_neg, y_min))
            x_at_ymax_neg = -y_max + offset
            if x_min <= x_at_ymax_neg <= x_max and (x_at_ymax_neg, y_max) not in pts_neg:
                pts_neg.append((x_at_ymax_neg, y_max))

            if len(pts_neg) == 2:
                lines.append(HatchLine(start=pts_neg[0], end=pts_neg[1], width_mm=line_w))

        return lines
