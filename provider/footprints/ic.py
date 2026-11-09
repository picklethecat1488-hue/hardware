"""Declarative integrated circuit (IC) component footprints using build123d primitives."""

from build123d import Box, Locations

from model.wiring import PinSide
from provider.pcb.footprint import BuildFootprint, Pad, PadShape, PadType, footprint


@footprint("SOIC-8", dimensions=(5.0, 4.0, 1.75))
def fp_soic8() -> BuildFootprint:
    """SOIC-8 8-lead small-outline integrated circuit package."""
    with BuildFootprint("SOIC-8", dimensions=(5.0, 4.0, 1.75)) as fp:
        with Locations([(-2.6, 1.905), (-2.6, 0.635), (-2.6, -0.635), (-2.6, -1.905)]):
            Pad(
                name=["1", "2", "3", "4"],
                size=(1.5, 0.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(2.6, -1.905), (2.6, -0.635), (2.6, 0.635), (2.6, 1.905)]):
            Pad(
                name=["5", "6", "7", "8"],
                size=(1.5, 0.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        Box(5.0, 4.0, 1.75)
    return fp


@footprint("QFN-20", dimensions=(3.0, 3.0, 0.6))
def fp_qfn20() -> BuildFootprint:
    """QFN-20 20-lead quad flat no-lead package with exposed thermal pad."""
    with BuildFootprint("QFN-20", dimensions=(3.0, 3.0, 0.6)) as fp:
        with Locations([(-1.45, 0.8), (-1.45, 0.4), (-1.45, 0.0), (-1.45, -0.4), (-1.45, -0.8)]):
            Pad(
                name=["VDD", "VREGD", "VSS", "VREGA", "CR0"],
                size=(0.65, 0.22),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-0.8, -1.45), (-0.4, -1.45), (0.0, -1.45), (0.4, -1.45), (0.8, -1.45)]):
            Pad(
                name=["CR1", "CR2", "CR3", "CR4", "CR5"],
                size=(0.22, 0.65),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(1.45, -0.8), (1.45, -0.4), (1.45, 0.0), (1.45, 0.4), (1.45, 0.8)]):
            Pad(
                name=["CR6", "CR7", "CT8", "OUTA", "NC1"],
                size=(0.65, 0.22),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.8, 1.45), (0.4, 1.45), (0.0, 1.45), (-0.4, 1.45), (-0.8, 1.45)]):
            Pad(
                name=["NC2", "RDY", "SCL", "SDA", "MCLR"],
                size=(0.22, 0.65),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        with Locations([(0.0, 0.0)]):
            Pad(name="EP", size=(1.65, 1.65), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.BOTTOM)
        Box(3.0, 3.0, 0.6)
    return fp


@footprint("QFN-24", dimensions=(4.0, 4.0, 0.85))
def fp_qfn24() -> BuildFootprint:
    """QFN-24 24-lead quad flat no-lead capacitive sensor package."""
    with BuildFootprint("QFN-24", dimensions=(4.0, 4.0, 0.85)) as fp:
        with Locations([(-2.0, 1.5), (-2.0, -1.5), (-2.0, 0.5), (-2.0, -0.5)]):
            Pad(
                name=["VDD", "VSS", "SDA", "SCL"],
                size=(0.8, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-1.0, -2.0)]):
            Pad(name="INT", size=(0.28, 0.8), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.BOTTOM)
        with Locations(
            [
                (2.0, 1.5),
                (2.0, 1.0),
                (2.0, 0.5),
                (2.0, 0.0),
                (2.0, -0.5),
                (2.0, -1.0),
                (2.0, -1.5),
            ]
        ):
            Pad(
                name=["CS0", "CS1", "CS2", "CS3", "CS4", "CS5", "CS6"],
                size=(0.8, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.0, 2.0), (1.0, 2.0)]):
            Pad(
                name=["SHIELD", "VREG"],
                size=(0.28, 0.8),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        Box(4.0, 4.0, 0.85)
    return fp


@footprint("QFN-16-AMP", dimensions=(3.0, 3.0, 0.8))
def fp_qfn16_amp() -> BuildFootprint:
    """QFN-16 I2S class-D audio amplifier package."""
    with BuildFootprint("QFN-16-AMP", dimensions=(3.0, 3.0, 0.8)) as fp:
        with Locations([(-1.5, 0.75), (-1.5, 0.25), (-1.5, -0.25), (-1.5, -0.75)]):
            Pad(
                name=["DIN", "GAIN", "GND", "SD_MODE"],
                label=["DIN", "GAIN", "GND", "SD_MODE"],
                size=(0.7, 0.25),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-0.75, -1.5), (-0.25, -1.5)]):
            Pad(
                name=["BCLK", "LRCLK"],
                label=["BCLK", "LRCLK"],
                size=(0.25, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(1.5, 0.5), (1.5, -0.5)]):
            Pad(
                name=["OUTP", "OUTN"],
                label=["SPK+", "SPK-"],
                size=(0.7, 0.35),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.0, 1.5)]):
            Pad(
                name="VDD",
                label="VDD",
                size=(0.35, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        Box(3.0, 3.0, 0.8)
    return fp


@footprint("USB-C-16P", dimensions=(9.0, 7.5, 3.2))
def fp_usbc_16p() -> BuildFootprint:
    """USB Type-C 16-pin mid-mount receptacle with shield through-hole tabs."""
    with BuildFootprint("USB-C-16P", dimensions=(9.0, 7.5, 3.2)) as fp:
        # SMD signal and power pins
        with Locations([(-3.2, 2.5), (-2.4, 2.5)]):
            Pad(
                name=["GND", "VBUS"],
                label=["GND", "VBUS"],
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-0.8, 2.5)]):
            Pad(
                name="CC1", label="CC1", size=(0.35, 1.2), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.RIGHT
            )
        with Locations([(-0.25, 2.5)]):
            Pad(name="DP1", label="D+", size=(0.3, 1.2), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(0.25, 2.5)]):
            Pad(name="DN1", label="D-", size=(0.3, 1.2), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        with Locations([(0.8, 2.5)]):
            Pad(
                name="CC2", label="CC2", size=(0.35, 1.2), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.RIGHT
            )
        with Locations([(2.4, 2.5), (3.2, 2.5)]):
            Pad(
                name=["VBUS2", "GND2"],
                label=["VBUS", "GND"],
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )

        # Shield mechanical tabs 1 & 2
        with Locations([(-4.2, 0.0), (4.2, 0.0)]):
            Pad(
                name=["SHIELD1", "SHIELD2"],
                label=["SHIELD", "SHIELD"],
                size=(1.8, 2.2),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.LEFT,
                drill_dia_mm=1.0,
            )

        # SBU pins
        with Locations([(-1.6, 2.5)]):
            Pad(
                name="SBU1",
                label="SBU1",
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(1.6, 2.5)]):
            Pad(
                name="SBU2",
                label="SBU2",
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )

        # Shield mechanical tabs 3 & 4
        with Locations([(-4.2, 3.5)]):
            Pad(
                name="SHIELD3",
                label="SHIELD",
                size=(1.8, 2.2),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.LEFT,
                drill_dia_mm=1.0,
            )
        with Locations([(4.2, 3.5)]):
            Pad(
                name="SHIELD4",
                label="SHIELD",
                size=(1.8, 2.2),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.RIGHT,
                drill_dia_mm=1.0,
            )
        Box(9.0, 7.5, 3.2)
    return fp


@footprint("BGA-196", dimensions=(12.0, 12.0, 1.4))
def fp_bga196() -> BuildFootprint:
    """BGA-196 14x14 ball grid array package with 0.8mm pitch."""
    rows = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P"]
    with BuildFootprint("BGA-196", dimensions=(12.0, 12.0, 1.4)) as fp:
        for r_idx, r in enumerate(rows):
            y = round(5.2 - r_idx * 0.8, 4)
            for c_idx in range(14):
                col = c_idx + 1
                x = round(-5.2 + c_idx * 0.8, 4)
                name = f"{r}{col}"
                side = PinSide.LEFT if x < 0 else PinSide.RIGHT
                with Locations([(x, y)]):
                    Pad(
                        name=name,
                        label=name,
                        size=(0.35, 0.35),
                        shape=PadShape.CIRCLE,
                        pad_type=PadType.SMD,
                        side=side,
                    )
        Box(12.0, 12.0, 1.4)
    return fp


@footprint("M.2-KEY-M", dimensions=(22.0, 6.0, 3.2))
def fp_m2_key_m() -> BuildFootprint:
    """M.2 Key-M edge connector footprint."""
    with BuildFootprint("M.2-KEY-M", dimensions=(22.0, 6.0, 3.2)) as fp:
        with Locations([(-10.0, 0.0), (-8.0, 0.0)]):
            Pad(
                name=["GND", "3V3"],
                size=(1.2, 1.2),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.RIGHT,
                drill_dia_mm=0.7,
            )
        with Locations([(-6.0, 0.0), (-4.0, 0.0), (-2.0, 0.0), (0.0, 0.0)]):
            Pad(
                name=["VLOAD_SW", "NC1", "NC2", "NC3"],
                size=(1.2, 1.2),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.LEFT,
                drill_dia_mm=0.7,
            )
        with Locations([(2.0, 0.0), (4.0, 0.0), (6.0, 0.0), (8.0, 0.0)]):
            Pad(
                name=["PETp0", "PETn0", "PERp0", "PERn0"],
                size=(1.2, 1.2),
                shape=PadShape.CIRCLE,
                pad_type=PadType.THRU_HOLE,
                side=PinSide.RIGHT,
                drill_dia_mm=0.7,
            )
        Box(22.0, 6.0, 3.2)
    return fp


@footprint("FPC-30P-0.5MM", dimensions=(21.6, 4.5, 1.2))
def fp_fpc_30p_05mm() -> BuildFootprint:
    """FPC-30P 0.5mm pitch flexible flat cable connector."""
    with BuildFootprint("FPC-30P-0.5MM", dimensions=(21.6, 4.5, 1.2)) as fp:
        # Row 1 signals (y = 0.0)
        with Locations([(-8.0, 0.0), (-7.0, 0.0)]):
            Pad(name=["GND", "3V3"], size=(0.35, 1.2), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        with Locations([(-6.0, 0.0), (-5.0, 0.0), (-4.0, 0.0), (-3.0, 0.0)]):
            Pad(
                name=["D0_P", "D0_N", "CLK_P", "CLK_N"],
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations(
            [(1.0, 0.0), (2.0, 0.0), (3.0, 0.0), (4.0, 0.0), (5.0, 0.0), (6.0, 0.0), (7.0, 0.0), (8.0, 0.0)]
        ):
            Pad(
                name=["CAP_TX2", "CAP_TX1", "CAP_TX0", "CAP_RX3", "CAP_RX0", "CAP_RX1", "CAP_RX2", "CAP_SHIELD"],
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-9.5, 0.0)]):
            Pad(name="MP1", size=(1.2, 1.6), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        with Locations([(9.5, 0.0)]):
            Pad(name="MP2", size=(1.2, 1.6), shape=PadShape.RECT, pad_type=PadType.SMD, side=PinSide.RIGHT)
        with Locations([(-2.0, 0.0), (-1.0, 0.0), (0.0, 0.0)]):
            Pad(
                name=["NC1", "NC2", "NC3"],
                label=["NC1", "NC2", "NC3"],
                size=(0.35, 1.2),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )

        # Row 2 NC signals (y = 1.6)
        with Locations([(-6.0, 1.6), (-5.0, 1.6), (-4.0, 1.6), (-3.0, 1.6), (-2.0, 1.6), (-1.0, 1.6), (0.0, 1.6)]):
            Pad(
                name=["NC4", "NC5", "NC6", "NC7", "NC8", "NC9", "NC10"],
                label=["NC4", "NC5", "NC6", "NC7", "NC8", "NC9", "NC10"],
                size=(0.35, 0.6),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(1.0, 1.6), (2.0, 1.6), (3.0, 1.6), (4.0, 1.6), (5.0, 1.6), (6.0, 1.6)]):
            Pad(
                name=["NC11", "NC12", "NC13", "NC14", "NC15", "NC16"],
                label=["NC11", "NC12", "NC13", "NC14", "NC15", "NC16"],
                size=(0.35, 0.6),
                shape=PadShape.RECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        Box(21.6, 4.5, 1.2)
    return fp


@footprint("WSON-8", dimensions=(8.0, 6.0, 0.8))
def fp_wson8() -> BuildFootprint:
    """WSON-8 8x6mm SPI flash memory package with exposed thermal ground pad."""
    with BuildFootprint("WSON-8", dimensions=(8.0, 6.0, 0.8)) as fp:
        with Locations([(-3.9, 1.905), (-3.9, 0.635), (-3.9, -0.635), (-3.9, -1.905)]):
            Pad(
                name=["1", "2", "3", "4"],
                label=["CS#", "SO/IO1", "WP#/IO2", "GND"],
                size=(0.8, 0.5),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(3.9, -1.905), (3.9, -0.635), (3.9, 0.635), (3.9, 1.905)]):
            Pad(
                name=["5", "6", "7", "8"],
                label=["SI/IO0", "SCK", "HOLD#/IO3", "VCC"],
                size=(0.8, 0.5),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.0, 0.0)]):
            Pad(
                name="EP",
                label="PAD",
                size=(4.3, 3.4),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        Box(8.0, 6.0, 0.8)
    return fp


@footprint("TDFN-8", dimensions=(2.0, 2.0, 0.8))
def fp_tdfn8() -> BuildFootprint:
    """TDFN-8 2x2mm micro leadframe package with exposed thermal pad."""
    with BuildFootprint("TDFN-8", dimensions=(2.0, 2.0, 0.8)) as fp:
        with Locations([(-0.95, 0.75), (-0.95, 0.25), (-0.95, -0.25), (-0.95, -0.75)]):
            Pad(
                name=["1", "2", "3", "4"],
                size=(0.6, 0.3),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(0.95, -0.75), (0.95, -0.25), (0.95, 0.25), (0.95, 0.75)]):
            Pad(
                name=["5", "6", "7", "8"],
                size=(0.6, 0.3),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.0, 0.0)]):
            Pad(name="EP", size=(0.7, 1.3), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        Box(2.0, 2.0, 0.8)
    return fp


@footprint("TSSOP-16", dimensions=(5.0, 4.4, 1.1))
def fp_tssop16() -> BuildFootprint:
    """TSSOP-16 16-lead thin shrink small outline package."""
    with BuildFootprint("TSSOP-16", dimensions=(5.0, 4.4, 1.1)) as fp:
        with Locations(
            [
                (-2.8, 2.275),
                (-2.8, 1.625),
                (-2.8, 0.975),
                (-2.8, 0.325),
                (-2.8, -0.325),
                (-2.8, -0.975),
                (-2.8, -1.625),
                (-2.8, -2.275),
            ]
        ):
            Pad(
                name=["1", "2", "3", "4", "5", "6", "7", "8"],
                size=(1.0, 0.4),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations(
            [
                (2.8, -2.275),
                (2.8, -1.625),
                (2.8, -0.975),
                (2.8, -0.325),
                (2.8, 0.325),
                (2.8, 0.975),
                (2.8, 1.625),
                (2.8, 2.275),
            ]
        ):
            Pad(
                name=["9", "10", "11", "12", "13", "14", "15", "16"],
                size=(1.0, 0.4),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        Box(5.0, 4.4, 1.1)
    return fp


@footprint("VQFN-16", dimensions=(3.0, 3.0, 0.9))
def fp_vqfn16() -> BuildFootprint:
    """VQFN-16 16-lead quad flat no-lead package with center thermal pad."""
    with BuildFootprint("VQFN-16", dimensions=(3.0, 3.0, 0.9)) as fp:
        with Locations([(-1.45, 0.75), (-1.45, 0.25), (-1.45, -0.25), (-1.45, -0.75)]):
            Pad(
                name=["1", "2", "3", "4"],
                size=(0.6, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations([(-0.75, -1.45), (-0.25, -1.45), (0.25, -1.45), (0.75, -1.45)]):
            Pad(
                name=["5", "6", "7", "8"],
                size=(0.28, 0.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations([(1.45, -0.75), (1.45, -0.25), (1.45, 0.25), (1.45, 0.75)]):
            Pad(
                name=["9", "10", "11", "12"],
                size=(0.6, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations([(0.75, 1.45), (0.25, 1.45), (-0.25, 1.45), (-0.75, 1.45)]):
            Pad(
                name=["13", "14", "15", "16"],
                size=(0.28, 0.6),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        with Locations([(0.0, 0.0)]):
            Pad(name="EP", size=(1.6, 1.6), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        Box(3.0, 3.0, 0.9)
    return fp


@footprint("QFN-32", dimensions=(5.0, 5.0, 0.9))
def fp_qfn32() -> BuildFootprint:
    """QFN-32 32-lead quad flat no-lead package with center thermal pad."""
    with BuildFootprint("QFN-32", dimensions=(5.0, 5.0, 0.9)) as fp:
        with Locations(
            [
                (-2.45, 1.75),
                (-2.45, 1.25),
                (-2.45, 0.75),
                (-2.45, 0.25),
                (-2.45, -0.25),
                (-2.45, -0.75),
                (-2.45, -1.25),
                (-2.45, -1.75),
            ]
        ):
            Pad(
                name=["1", "2", "3", "4", "5", "6", "7", "8"],
                size=(0.7, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )
        with Locations(
            [
                (-1.75, -2.45),
                (-1.25, -2.45),
                (-0.75, -2.45),
                (-0.25, -2.45),
                (0.25, -2.45),
                (0.75, -2.45),
                (1.25, -2.45),
                (1.75, -2.45),
            ]
        ):
            Pad(
                name=["9", "10", "11", "12", "13", "14", "15", "16"],
                size=(0.28, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        with Locations(
            [
                (2.45, -1.75),
                (2.45, -1.25),
                (2.45, -0.75),
                (2.45, -0.25),
                (2.45, 0.25),
                (2.45, 0.75),
                (2.45, 1.25),
                (2.45, 1.75),
            ]
        ):
            Pad(
                name=["17", "18", "19", "20", "21", "22", "23", "24"],
                size=(0.7, 0.28),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )
        with Locations(
            [
                (1.75, 2.45),
                (1.25, 2.45),
                (0.75, 2.45),
                (0.25, 2.45),
                (-0.25, 2.45),
                (-0.75, 2.45),
                (-1.25, 2.45),
                (-1.75, 2.45),
            ]
        ):
            Pad(
                name=["25", "26", "27", "28", "29", "30", "31", "32"],
                size=(0.28, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )
        with Locations([(0.0, 0.0)]):
            Pad(name="EP", size=(3.2, 3.2), shape=PadShape.ROUNDRECT, pad_type=PadType.SMD, side=PinSide.LEFT)
        Box(5.0, 5.0, 0.9)
    return fp


VFBGA_184_ROW_COLS = {
    "A": (1, 10, 12, 14, 16, 17, 2, 4, 6, 8),
    "B": (1, 10, 11, 12, 14, 15, 16, 17, 2, 3, 4, 6, 7, 8),
    "C": (10, 12, 13, 14, 15, 3, 4, 5, 6, 8, 9),
    "D": (1, 11, 12, 14, 15, 16, 17, 2, 3, 4, 6, 7, 9),
    "E": (10, 11, 13, 14, 4, 5, 7, 8),
    "F": (1, 10, 12, 14, 15, 16, 17, 2, 3, 4, 6, 8),
    "G": (11, 13, 14, 16, 2, 4, 5, 7),
    "H": (1, 10, 12, 13, 15, 16, 17, 2, 3, 5, 6, 8, 9),
    "J": (1, 10, 11, 12, 13, 14, 15, 16, 17, 2, 3, 4, 5, 6, 7, 8),
    "K": (1, 10, 12, 13, 15, 16, 17, 2, 3, 5, 6, 8, 9),
    "L": (11, 13, 14, 16, 2, 4, 5, 7),
    "M": (1, 10, 12, 14, 15, 16, 17, 2, 3, 4, 6, 8),
    "N": (10, 11, 13, 14, 4, 5, 7, 8),
    "P": (1, 11, 12, 14, 15, 16, 17, 2, 3, 4, 6, 7, 9),
    "R": (10, 12, 13, 14, 15, 3, 4, 5, 6, 8, 9),
    "T": (1, 10, 11, 12, 14, 15, 16, 17, 2, 3, 4, 6, 7, 8),
}


@footprint("VFBGA-184", dimensions=(11.0, 11.0, 1.2))
def fp_vfbga184() -> BuildFootprint:
    """VFBGA-184 184-ball fine-pitch ball grid array package."""
    rows = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "R", "T"]
    with BuildFootprint("VFBGA-184", dimensions=(11.0, 11.0, 1.2)) as fp:
        for r_idx, r in enumerate(rows):
            y = round(3.75 - r_idx * 0.5, 4)
            for col in VFBGA_184_ROW_COLS[r]:
                x = round(-4.0 + (col - 1) * 0.5, 4)
                name = f"{r}{col}"
                side = PinSide.LEFT if x < 0 else PinSide.RIGHT
                with Locations([(x, y)]):
                    Pad(
                        name=name,
                        label=name,
                        size=(0.28, 0.28),
                        shape=PadShape.CIRCLE,
                        pad_type=PadType.SMD,
                        side=side,
                    )
        Box(11.0, 11.0, 1.2)
    return fp


@footprint("MOD-BLE-PCB-ANT", dimensions=(10.0, 15.0, 2.23))
def fp_mod_ble_pcb_ant() -> BuildFootprint:
    """Bluetooth Low Energy wireless transceiver module with integrated PCB antenna."""
    with BuildFootprint("MOD-BLE-PCB-ANT", dimensions=(10.0, 15.0, 2.23)) as fp:
        # Pins 1-5 (Left, upper)
        with Locations(
            [
                (-4.125, 4.0),
                (-4.125, 3.0),
                (-4.125, 2.0),
                (-4.125, 1.0),
                (-4.125, 0.0),
            ]
        ):
            Pad(
                name=["RED", "IO_2", "IO_3", "IO_4", "IO_5"],
                number=["1", "2", "3", "4", "5"],
                label=["RED", "IO_2", "IO_3", "IO_4", "IO_5"],
                size=(1.15, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )

        # Pin 6 (Top)
        with Locations([(-2.5, 6.25)]):
            Pad(
                name="GND",
                number="6",
                label="GND",
                size=(0.7, 1.15),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )

        # Pins 7-10 (Left, lower)
        with Locations(
            [
                (-4.125, -1.0),
                (-4.125, -2.0),
                (-4.125, -3.0),
                (-4.125, -4.0),
            ]
        ):
            Pad(
                name=["GREEN", "BLUE", "3V3", "VCC"],
                number=["7", "8", "9", "10"],
                label=["GREEN", "BLUE", "3V3", "VCC"],
                size=(1.15, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.LEFT,
            )

        # Pins 11, 12, 18, 15 (Top)
        with Locations([(-1.5, 6.25), (-0.5, 6.25), (0.5, 6.25), (1.5, 6.25)]):
            Pad(
                name=["SWDCLK", "GND_12", "SWITCH_2", "SWDIO"],
                number=["11", "12", "18", "15"],
                label=["SWDCLK", "GND", "SWITCH_2", "SWDIO"],
                size=(0.7, 1.15),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.TOP,
            )

        # Pins 19-23 (Bottom)
        with Locations([(-2.0, -4.0), (-1.0, -4.0), (0.0, -4.0), (1.0, -4.0), (2.0, -4.0)]):
            Pad(
                name=["RESET_N", "RTS", "CTS", "TXD", "RXD"],
                number=["19", "20", "21", "22", "23"],
                label=["RESET_N", "RTS", "CTS", "TXD", "RXD"],
                size=(0.7, 1.15),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )

        # Pins 24-30 (Right)
        with Locations(
            [
                (4.125, 4.0),
                (4.125, 3.0),
                (4.125, 2.0),
                (4.125, 1.0),
                (4.125, 0.0),
                (4.125, -1.0),
                (4.125, -2.0),
            ]
        ):
            Pad(
                name=["IO_24", "IO_25", "GND_26", "IO_27", "NFC1", "NFC2", "GND_30"],
                number=["24", "25", "26", "27", "28", "29", "30"],
                label=["IO_24", "IO_25", "GND", "IO_27", "NFC1", "NFC2", "GND"],
                size=(1.15, 0.7),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.RIGHT,
            )

        # Ground thermal pad
        with Locations([(0.0, 1.0)]):
            Pad(
                name="EGP",
                number="53",
                label="GND",
                size=(1.5, 1.5),
                shape=PadShape.ROUNDRECT,
                pad_type=PadType.SMD,
                side=PinSide.BOTTOM,
            )
        Box(10.0, 15.0, 2.23)
    return fp
