"""Declarative through-hole (TH) component footprints using build123d primitives."""

from typing import Dict
from build123d import Box, Cylinder, Locations

from model.wiring import PinSide
from provider.pcb.footprint import BuildFootprint, Pad, PadShape, PadType, footprint


@footprint("pin_header_1x2", dimensions=(5.08, 2.54, 8.5))
def fp_pin_header_1x2() -> BuildFootprint:
    """1x2 2.54mm pitch through-hole vertical pin header."""
    with BuildFootprint("pin_header_1x2", dimensions=(5.08, 2.54, 8.5)) as fp:
        with Locations([(-1.27, 0.0)]):
            Pad(
                name="1",
                size=(1.7, 1.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(1.27, 0.0)]):
            Pad(
                name="2",
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Box(5.08, 2.54, 8.5)
    return fp


@footprint("pin_header_1x3", dimensions=(7.62, 2.54, 8.5))
def fp_pin_header_1x3() -> BuildFootprint:
    """1x3 2.54mm pitch through-hole vertical pin header."""
    with BuildFootprint("pin_header_1x3", dimensions=(7.62, 2.54, 8.5)) as fp:
        with Locations([(-2.54, 0.0)]):
            Pad(
                name="1",
                size=(1.7, 1.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(0.0, 0.0)]):
            Pad(
                name="2",
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(2.54, 0.0)]):
            Pad(
                name="3",
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Box(7.62, 2.54, 8.5)
    return fp


@footprint("pin_header_1x4", dimensions=(10.16, 2.54, 8.5))
def fp_pin_header_1x4() -> BuildFootprint:
    """1x4 2.54mm pitch through-hole vertical pin header."""
    with BuildFootprint("pin_header_1x4", dimensions=(10.16, 2.54, 8.5)) as fp:
        with Locations([(-3.81, 0.0)]):
            Pad(
                name="1",
                size=(1.7, 1.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(-1.27, 0.0)]):
            Pad(
                name="2",
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(1.27, 0.0), (3.81, 0.0)]):
            Pad(
                name=["3", "4"],
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Box(10.16, 2.54, 8.5)
    return fp


@footprint("axial_resistor", dimensions=(8.5, 2.5, 2.5))
def fp_axial_resistor() -> BuildFootprint:
    """Through-hole axial leaded resistor."""
    with BuildFootprint("axial_resistor", dimensions=(8.5, 2.5, 2.5)) as fp:
        with Locations([(-3.81, 0.0)]):
            Pad(
                name="1",
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(3.81, 0.0)]):
            Pad(
                name="2",
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.RIGHT,
            )
        Box(8.5, 2.5, 2.5)
    return fp


@footprint("radial_capacitor", dimensions=(5.0, 5.0, 7.0))
def fp_radial_capacitor() -> BuildFootprint:
    """Through-hole radial leaded electrolytic capacitor."""
    with BuildFootprint("radial_capacitor", dimensions=(5.0, 5.0, 7.0)) as fp:
        with Locations([(-1.27, 0.0)]):
            Pad(
                name="1",
                label="+",
                size=(1.6, 1.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(1.27, 0.0)]):
            Pad(
                name="2",
                label="-",
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.RIGHT,
            )
        Cylinder(radius=2.5, height=7.0)
    return fp


@footprint("mounting_hole_plated", dimensions=(3.5, 3.5, 1.6))
def fp_mounting_hole_plated() -> BuildFootprint:
    """Plated mounting hole for M2 / M2.5 screw fasteners."""
    with BuildFootprint("mounting_hole_plated", dimensions=(3.5, 3.5, 1.6)) as fp:
        with Locations([(0.0, 0.0)]):
            Pad(
                name="1",
                size=(3.5, 3.5),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=2.20,
                side=PinSide.LEFT,
            )
        Cylinder(radius=1.75, height=1.6)
    return fp


@footprint("piezo_speaker_12mm", dimensions=(12.0, 12.0, 6.5), shape="circle", radius_mm=6.0)
def fp_piezo_speaker_12mm() -> BuildFootprint:
    """12mm diameter circular through-hole piezo audio transducer."""
    with BuildFootprint("piezo_speaker_12mm", dimensions=(12.0, 12.0, 6.5), shape="circle", radius_mm=6.0) as fp:
        with Locations([(-2.5, 0.0)]):
            Pad(
                name="1",
                size=(1.8, 1.8),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(2.5, 0.0)]):
            Pad(
                name="2",
                size=(1.8, 1.8),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Cylinder(radius=6.0, height=6.5)
    return fp


@footprint("pin_header_1x6", dimensions=(15.24, 2.54, 8.5))
def fp_pin_header_1x6() -> BuildFootprint:
    """1x6 2.54mm pitch through-hole vertical pin header."""
    with BuildFootprint("pin_header_1x6", dimensions=(15.24, 2.54, 8.5)) as fp:
        with Locations([(-6.35, 0.0)]):
            Pad(
                name="1",
                size=(1.7, 1.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(-3.81, 0.0), (-1.27, 0.0)]):
            Pad(
                name=["2", "3"],
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        with Locations([(1.27, 0.0), (3.81, 0.0), (6.35, 0.0)]):
            Pad(
                name=["4", "5", "6"],
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Box(15.24, 2.54, 8.5)
    return fp


@footprint("pin_header_1x10", dimensions=(25.4, 2.54, 8.5))
def fp_pin_header_1x10() -> BuildFootprint:
    """1x10 2.54mm pitch through-hole vertical pin header."""
    with BuildFootprint("pin_header_1x10", dimensions=(25.4, 2.54, 8.5)) as fp:
        with Locations([(-11.43, 0.0)]):
            Pad(
                name="1",
                size=(1.7, 1.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        left_locs = [(-8.89 + i * 2.54, 0.0) for i in range(4)]
        with Locations(left_locs):
            Pad(
                name=[str(i + 2) for i in range(4)],
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.LEFT,
            )
        right_locs = [(1.27 + i * 2.54, 0.0) for i in range(5)]
        with Locations(right_locs):
            Pad(
                name=[str(i + 6) for i in range(5)],
                size=(1.7, 1.7),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=1.00,
                side=PinSide.RIGHT,
            )
        Box(25.4, 2.54, 8.5)
    return fp


@footprint("pin_header_2x5_1.27mm", dimensions=(6.35, 3.81, 5.0))
def fp_pin_header_2x5_127mm() -> BuildFootprint:
    """2x5 1.27mm pitch miniature dual-row SWD debugging header."""
    with BuildFootprint("pin_header_2x5_1.27mm", dimensions=(6.35, 3.81, 5.0)) as fp:
        with Locations([(-2.54, -0.635)]):
            Pad(
                name="1",
                size=(1.0, 1.0),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.65,
                side=PinSide.LEFT,
            )
        # Pins 2, 3, 4, 5
        left_locs = [(-2.54, 0.635), (-1.27, -0.635), (-1.27, 0.635), (0.0, -0.635)]
        with Locations(left_locs):
            Pad(
                name=["2", "3", "4", "5"],
                size=(1.0, 1.0),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.65,
                side=PinSide.LEFT,
            )
        # Pins 6, 7, 8, 9, 10
        right_locs = [(0.0, 0.635), (1.27, -0.635), (1.27, 0.635), (2.54, -0.635), (2.54, 0.635)]
        with Locations(right_locs):
            Pad(
                name=["6", "7", "8", "9", "10"],
                size=(1.0, 1.0),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.65,
                side=PinSide.RIGHT,
            )
        Box(6.35, 3.81, 5.0)
    return fp


@footprint("JST-PH-2P", dimensions=(6.0, 5.0, 6.5))
def fp_jst_ph_2p() -> BuildFootprint:
    """JST PH 2-pin 2.0mm pitch wire-to-board battery connector."""
    with BuildFootprint("JST-PH-2P", dimensions=(6.0, 5.0, 6.5)) as fp:
        with Locations([(-1.0, 0.0)]):
            Pad(
                name="1",
                size=(1.6, 1.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(1.0, 0.0)]):
            Pad(
                name="2",
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.RIGHT,
            )
        Box(6.0, 5.0, 6.5)
    return fp


@footprint("JST-PH-6P", dimensions=(14.0, 5.0, 6.5))
def fp_jst_ph_6p() -> BuildFootprint:
    """JST PH 6-pin 2.0mm pitch wire-to-board connector."""
    with BuildFootprint("JST-PH-6P", dimensions=(14.0, 5.0, 6.5)) as fp:
        with Locations([(-5.0, 0.0)]):
            Pad(
                name="1",
                size=(1.6, 1.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(-3.0, 0.0), (-1.0, 0.0)]):
            Pad(
                name=["2", "3"],
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(1.0, 0.0), (3.0, 0.0), (5.0, 0.0)]):
            Pad(
                name=["4", "5", "6"],
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.RIGHT,
            )
        Box(14.0, 5.0, 6.5)
    return fp


@footprint("JST-PH-7P", dimensions=(16.0, 5.0, 6.5))
def fp_jst_ph_7p() -> BuildFootprint:
    """JST PH 7-pin 2.0mm pitch wire-to-board connector."""
    with BuildFootprint("JST-PH-7P", dimensions=(16.0, 5.0, 6.5)) as fp:
        with Locations([(-6.0, 0.0)]):
            Pad(
                name="1",
                size=(1.6, 1.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(-4.0, 0.0), (-2.0, 0.0), (0.0, 0.0)]):
            Pad(
                name=["2", "3", "4"],
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.LEFT,
            )
        with Locations([(2.0, 0.0), (4.0, 0.0), (6.0, 0.0)]):
            Pad(
                name=["5", "6", "7"],
                size=(1.6, 1.6),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                drill_dia_mm=0.80,
                side=PinSide.RIGHT,
            )
        Box(16.0, 5.0, 6.5)
    return fp


THRU_HOLE_FOOTPRINTS: Dict[str, BuildFootprint] = {
    "pin_header_1x2": fp_pin_header_1x2(),
    "pin_header_1x3": fp_pin_header_1x3(),
    "pin_header_1x4": fp_pin_header_1x4(),
    "axial_resistor": fp_axial_resistor(),
    "radial_capacitor": fp_radial_capacitor(),
    "mounting_hole_plated": fp_mounting_hole_plated(),
    "piezo_speaker_12mm": fp_piezo_speaker_12mm(),
    "pin_header_1x6": fp_pin_header_1x6(),
    "pin_header_1x10": fp_pin_header_1x10(),
    "pin_header_2x5_1.27mm": fp_pin_header_2x5_127mm(),
    "JST-PH-2P": fp_jst_ph_2p(),
    "JST-PH-6P": fp_jst_ph_6p(),
    "JST-PH-7P": fp_jst_ph_7p(),
}
