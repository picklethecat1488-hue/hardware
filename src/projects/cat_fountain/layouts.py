"""Footprint pin layout registration and algorithms for the CatFountain project."""

from typing import List, Optional
from model.wiring import register_layout


@register_layout("board")
@register_layout("tof_sensor")
def layout_edge_pins(pins: List, w: float, l: float, slots_per_side: Optional[int] = None):
    """Layout pins along the outer edges of a footprint (DIP board layout)."""
    by_side = {"left": [], "right": [], "top": [], "bottom": []}
    for p in pins:
        if p.side == "right":
            by_side["left"].append(p)
        elif p.side == "left":
            by_side["right"].append(p)
        elif p.side == "bottom":
            by_side["top"].append(p)
        elif p.side == "top":
            by_side["bottom"].append(p)

    for edge, group in by_side.items():
        if not group:
            continue

        margin = 2.0
        if edge in ("left", "right"):
            px = -w / 2.0 if edge == "left" else w / 2.0
            if len(group) == 1:
                if group[0].position == (0.0, 0.0, 0.0):
                    group[0].position = (px, 0.0, 0.0)
            else:
                limit = l / 2.0 - margin
                has_slots = any(p.slot is not None for p in group)
                if has_slots:
                    slots_n = slots_per_side if slots_per_side is not None else len(group)
                    pitch = (2 * limit) / (slots_n - 1) if slots_n > 1 else 0.0
                else:
                    pitch = (2 * limit) / (len(group) - 1)

                for idx, p in enumerate(group):
                    s = p.slot if p.slot is not None else idx
                    py = limit - s * pitch if edge == "left" else -limit + s * pitch
                    if p.position == (0.0, 0.0, 0.0):
                        p.position = (px, py, 0.0)

        elif edge in ("top", "bottom"):
            py = l / 2.0 if edge == "top" else -l / 2.0
            if len(group) == 1:
                if group[0].position == (0.0, 0.0, 0.0):
                    group[0].position = (0.0, py, 0.0)
            else:
                limit = w / 2.0 - margin
                has_slots = any(p.slot is not None for p in group)
                if has_slots:
                    slots_n = slots_per_side if slots_per_side is not None else len(group)
                    pitch = (2 * limit) / (slots_n - 1) if slots_n > 1 else 0.0
                else:
                    pitch = (2 * limit) / (len(group) - 1)

                for idx, p in enumerate(group):
                    s = p.slot if p.slot is not None else idx
                    px = -limit + s * pitch
                    if p.position == (0.0, 0.0, 0.0):
                        p.position = (px, py, 0.0)


@register_layout("motor")
def layout_motor_pins(pins: List, w: float, l: float, slots_per_side: Optional[int] = None):
    """Layout pins for motor footprints."""
    for p in pins:
        if p.name == "M+":
            p.position = (-4.0, -5.0, 0.0)
        elif p.name == "M-":
            p.position = (4.0, -5.0, 0.0)


@register_layout("led", surface_mount=True)
def layout_led_pins(pins: List, w: float, l: float, slots_per_side: Optional[int] = None):
    """Layout pins for LED footprints."""
    for p in pins:
        if p.name == "VCC":
            p.position = (-5.0, 3.0, 0.0)
        elif p.name == "GND":
            p.position = (-5.0, -3.0, 0.0)
        elif p.name == "DIN":
            p.position = (5.0, 0.0, 0.0)
