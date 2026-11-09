"""Declarative surface mount device (SMD) component footprints using build123d primitives."""

from typing import Dict
from build123d import Box, Locations

from model.wiring import PinSide
from provider.pcb.footprint import BuildFootprint, Pad, PadShape, PadType, footprint


@footprint("SW_PUSH_SMD", dimensions=(3.0, 2.5, 1.5))
def fp_sw_push_smd() -> BuildFootprint:
    """SMD tactile momentary push button switch."""
    with BuildFootprint("SW_PUSH_SMD", dimensions=(3.0, 2.5, 1.5)) as fp:
        with Locations([(-1.4, 0.0), (1.4, 0.0)]):
            Pad(
                name=["1", "2"],
                size=(0.8, 1.2),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=[PinSide.LEFT, PinSide.RIGHT],
            )
        Box(3.0, 2.5, 1.5)
    return fp


@footprint("0402", dimensions=(1.0, 0.5, 0.35))
def fp_0402() -> BuildFootprint:
    """EIA 0402 / metric 1005 passive chip resistor or capacitor."""
    with BuildFootprint("0402", dimensions=(1.0, 0.5, 0.35)) as fp:
        with Locations([(-0.5, 0.0)]):
            Pad(name="1", size=(0.6, 0.5), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(0.5, 0.0)]):
            Pad(name="2", size=(0.6, 0.5), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        Box(1.0, 0.5, 0.35)
    return fp


@footprint("0603", dimensions=(1.6, 0.8, 0.45))
def fp_0603() -> BuildFootprint:
    """EIA 0603 / metric 1608 passive chip resistor or capacitor."""
    with BuildFootprint("0603", dimensions=(1.6, 0.8, 0.45)) as fp:
        with Locations([(-0.8, 0.0)]):
            Pad(name="1", size=(0.8, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(0.8, 0.0)]):
            Pad(name="2", size=(0.8, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        Box(1.6, 0.8, 0.45)
    return fp


@footprint("0805", dimensions=(2.0, 1.25, 0.6))
def fp_0805() -> BuildFootprint:
    """EIA 0805 / metric 2012 passive chip resistor or capacitor."""
    with BuildFootprint("0805", dimensions=(2.0, 1.25, 0.6)) as fp:
        with Locations([(-1.0, 0.0)]):
            Pad(name="1", size=(1.0, 1.25), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(1.0, 0.0)]):
            Pad(name="2", size=(1.0, 1.25), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        Box(2.0, 1.25, 0.6)
    return fp


@footprint("1206", dimensions=(3.2, 1.6, 0.8))
def fp_1206() -> BuildFootprint:
    """EIA 1206 / metric 3216 passive chip resistor or capacitor."""
    with BuildFootprint("1206", dimensions=(3.2, 1.6, 0.8)) as fp:
        with Locations([(-1.5, 0.0)]):
            Pad(name="1", size=(1.1, 1.6), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(1.5, 0.0)]):
            Pad(name="2", size=(1.1, 1.6), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        Box(3.2, 1.6, 0.8)
    return fp


@footprint("SOT-23", dimensions=(2.9, 1.3, 1.0))
def fp_sot23() -> BuildFootprint:
    """SOT-23 3-lead transistor or voltage regulator."""
    with BuildFootprint("SOT-23", dimensions=(2.9, 1.3, 1.0)) as fp:
        with Locations([(-0.95, -1.0)]):
            Pad(name="1", size=(0.6, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(0.95, -1.0)]):
            Pad(name="2", size=(0.6, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        with Locations([(0.0, 1.0)]):
            Pad(name="3", size=(0.6, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.TOP)
        Box(2.9, 1.3, 1.0)
    return fp


@footprint("SOT-23-5", dimensions=(2.9, 1.6, 1.1))
def fp_sot23_5() -> BuildFootprint:
    """SOT-23-5 5-lead IC package (LDO regulators, logic)."""
    with BuildFootprint("SOT-23-5", dimensions=(2.9, 1.6, 1.1)) as fp:
        with Locations([(-0.95, -1.3), (0.0, -1.3), (0.95, -1.3)]):
            Pad(
                name=["1", "2", "3"],
                label=["VIN", "GND", "EN"],
                size=(0.55, 0.85),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(0.95, 1.3), (-0.95, 1.3)]):
            Pad(
                name=["4", "5"],
                label=["BYP", "VOUT"],
                size=(0.55, 0.85),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        Box(2.9, 1.6, 1.1)
    return fp


@footprint("SOT-23-6", dimensions=(2.9, 1.6, 1.1))
def fp_sot23_6() -> BuildFootprint:
    """SOT-23-6 6-lead IC package."""
    with BuildFootprint("SOT-23-6", dimensions=(2.9, 1.6, 1.1)) as fp:
        with Locations([(-0.95, -1.3), (0.0, -1.3), (0.95, -1.3)]):
            Pad(
                name=["1", "2", "3"],
                size=(0.55, 0.85),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(0.95, 1.3), (0.0, 1.3), (-0.95, 1.3)]):
            Pad(
                name=["4", "5", "6"],
                size=(0.55, 0.85),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        Box(2.9, 1.6, 1.1)
    return fp


@footprint("SOD-123", dimensions=(2.7, 1.6, 1.2))
def fp_sod123() -> BuildFootprint:
    """SOD-123 surface mount diode."""
    with BuildFootprint("SOD-123", dimensions=(2.7, 1.6, 1.2)) as fp:
        with Locations([(-1.4, 0.0)]):
            Pad(
                name="1",
                label="K",
                size=(0.9, 1.0),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(1.4, 0.0)]):
            Pad(
                name="2",
                label="A",
                size=(0.9, 1.0),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        Box(2.7, 1.6, 1.2)
    return fp


@footprint("XTAL-3225-4P", dimensions=(3.2, 2.5, 0.8))
def fp_xtal_3225_4p() -> BuildFootprint:
    """4-pad 3.2x2.5mm miniature crystal oscillator."""
    with BuildFootprint("XTAL-3225-4P", dimensions=(3.2, 2.5, 0.8)) as fp:
        with Locations([(-1.1, -0.8), (1.1, -0.8), (1.1, 0.8), (-1.1, 0.8)]):
            Pad(
                name=["1", "2", "3", "4"],
                label=["OSC_IN", "GND", "OSC_OUT", "GND"],
                size=(1.2, 0.9),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=[PinSide.LEFT, PinSide.RIGHT, PinSide.RIGHT, PinSide.LEFT],
            )
        Box(3.2, 2.5, 0.8)
    return fp


@footprint("LED_RGB_4P", dimensions=(2.1, 2.1, 1.0))
def fp_led_rgb_4p() -> BuildFootprint:
    """4-lead RGB surface mount LED."""
    with BuildFootprint("LED_RGB_4P", dimensions=(2.1, 2.1, 1.0)) as fp:
        with Locations([(-0.8, -0.8), (0.8, -0.8), (0.8, 0.8), (-0.8, 0.8)]):
            Pad(
                name=["1", "2", "3", "4"],
                label=["A", "R", "G", "B"],
                size=(0.7, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=[PinSide.LEFT, PinSide.RIGHT, PinSide.RIGHT, PinSide.LEFT],
            )
        Box(2.1, 2.1, 1.0)
    return fp


@footprint("FPC-15P-0.5MM", dimensions=(10.5, 4.0, 1.2))
def fp_fpc_15p_05mm() -> BuildFootprint:
    """15-position 0.5mm pitch bottom-contact FPC connector."""
    with BuildFootprint("FPC-15P-0.5MM", dimensions=(10.5, 4.0, 1.2)) as fp:
        signal_locs = [(-3.5 + i * 0.5, -1.2) for i in range(15)]
        with Locations(signal_locs):
            Pad(
                name=[str(i + 1) for i in range(15)],
                size=(0.3, 1.2),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(-4.8, 0.5)]):
            Pad(name="MP1", size=(1.4, 2.0), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(4.8, 0.5)]):
            Pad(name="MP2", size=(1.4, 2.0), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        Box(10.5, 4.0, 1.2)
    return fp


SMD_FOOTPRINTS: Dict[str, BuildFootprint] = {
    "SW_PUSH_SMD": fp_sw_push_smd(),
    "0402": fp_0402(),
    "0603": fp_0603(),
    "0805": fp_0805(),
    "1206": fp_1206(),
    "SOT-23": fp_sot23(),
    "SOT-23-5": fp_sot23_5(),
    "SOT-23-6": fp_sot23_6(),
    "SOD-123": fp_sod123(),
    "XTAL-3225-4P": fp_xtal_3225_4p(),
    "LED_RGB_4P": fp_led_rgb_4p(),
    "FPC-15P-0.5MM": fp_fpc_15p_05mm(),
}
