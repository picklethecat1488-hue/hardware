"""Declarative component layout, wiring netlists, and pinout keys for the Cat Fountain project."""

from typing import Any, Optional, Sequence, Dict, List, cast
from pathlib import Path
from build123d import (
    Align,
    Axis,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    Circle,
    Cylinder,
    Line,
    Location,
    Locations,
    Mode,
    Part,
    Rectangle,
    Vector,
    fillet,
)
from model import Wiring, TextArgs, DiagramStyle
from provider import Room, WiringDiagram, Mode as ProviderMode
from model.wiring import FootprintModel, NetModel, LabelModel, PinModel
from provider.pcb import BuildComponents, Component, BuildWiring, Net


def build_cat_fountain_wiring(parent_part: Optional[Any] = None) -> Wiring:
    """Construct in-memory Wiring container for Cat Fountain using BuildComponents and BuildWiring."""
    with BuildComponents(name="cat_fountain_components", parent_part=parent_part) as layout:
        Component(
            name="battery",
            package="battery",
            dimensions=(25.0, 35.0, 6.0),
            position=(0.0, -40.0, 12.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "LiPo Battery", "position": [0.0, -20.0, 0.0], "align": ["center", "max"]},
            pins=[{"name": "+", "label": "+", "side": "right"}, {"name": "-", "label": "-", "side": "right"}],
        )
        Component(
            name="charger",
            package="board",
            dimensions=(18.0, 29.0, 1.6),
            position=(0.0, -79.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "BQ25185", "position": [0.0, -17.5, 0.0], "align": ["center", "max"]},
            pins=[
                {"name": "BAT+", "label": "BAT+", "side": "right"},
                {"name": "BAT-", "label": "BAT-", "side": "right"},
                {"name": "S1", "label": "S1", "side": "right"},
                {"name": "SYS", "label": "SYS", "side": "left"},
                {"name": "GND", "label": "GND", "side": "left"},
                {"name": "S2", "label": "S2", "side": "left"},
            ],
        )
        Component(
            name="pico",
            package="board",
            dimensions=(17.0, 52.0, 1.6),
            position=(-50.0, 0.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            slots_per_side=20,
            label={"text": "PICO W", "position": [0.0, 29.0, 0.0], "align": ["center", "min"]},
            pins=[
                {"name": "GP2", "label": "GP2", "side": "right", "slot": 3},
                {"name": "GP3", "label": "GP3", "side": "right", "slot": 4},
                {"name": "GP4", "label": "GP4", "side": "right", "slot": 5},
                {"name": "GP5", "label": "GP5", "side": "right", "slot": 6},
                {"name": "GP6", "label": "GP6", "side": "right", "slot": 8},
                {"name": "GP7", "label": "GP7", "side": "right", "slot": 9},
                {"name": "GP8", "label": "GP8", "side": "right", "slot": 10},
                {"name": "GP9", "label": "GP9", "side": "right", "slot": 11},
                {"name": "GP10", "label": "GP10", "side": "right", "slot": 13},
                {"name": "GP11", "label": "GP11", "side": "right", "slot": 12},
                {"name": "GP12", "label": "GP12", "side": "right", "slot": 15},
                {"name": "GP13", "label": "GP13", "side": "right", "slot": 16},
                {"name": "GP14", "label": "GP14", "side": "right", "slot": 18},
                {"name": "GP15", "label": "GP15", "side": "right", "slot": 19},
                {"name": "GP16", "label": "GP16", "side": "left", "slot": 1},
                {"name": "GP17", "label": "GP17", "side": "left", "slot": 2},
                {"name": "GP18", "label": "GP18", "side": "left", "slot": 3},
                {"name": "GP19", "label": "GP19", "side": "left", "slot": 4},
                {"name": "GP20", "label": "GP20", "side": "left", "slot": 5},
                {"name": "GP21", "label": "GP21", "side": "left", "slot": 6},
                {"name": "GP22", "label": "GP22", "side": "left", "slot": 7},
                {"name": "GND_L", "label": "GND", "side": "right", "slot": 2},
                {"name": "VSYS", "label": "VSYS", "side": "left", "slot": 18},
                {"name": "GND_R", "label": "GND", "side": "left", "slot": 17},
                {"name": "3V3", "label": "3V3", "side": "left", "slot": 15},
                {"name": "GP26", "label": "GP26", "side": "left", "slot": 11},
            ],
        )
        Component(
            name="fuel_gauge",
            package="board",
            dimensions=(24.0, 20.0, 1.6),
            position=(50.0, -45.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "MAX17048", "position": [0.0, -13.0, 0.0], "align": ["center", "max"]},
            pins=[
                {"name": "BAT", "label": "BAT", "side": "right"},
                {"name": "VIN", "label": "VIN", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "SDA", "label": "SDA", "side": "right"},
                {"name": "SCL", "label": "SCL", "side": "right"},
                {"name": "ALRT", "label": "ALRT", "side": "left"},
            ],
        )
        Component(
            name="current_monitor",
            package="board",
            dimensions=(25.0, 21.5, 1.6),
            position=(50.0, -15.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "INA219", "position": [15.5, 0.0, 0.0], "align": ["min", "center"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "SDA", "label": "SDA", "side": "right"},
                {"name": "SCL", "label": "SCL", "side": "right"},
                {"name": "VIN+", "label": "VIN+", "side": "left"},
                {"name": "VIN-", "label": "VIN-", "side": "left"},
            ],
        )
        Component(
            name="motor_driver",
            package="board",
            dimensions=(20.32, 15.24, 1.6),
            position=(50.0, 15.0, 23.0),
            rotation=(0.0, 0.0, 90.0),
            label={"text": "TMC6300", "position": [15.0, 0.0, 0.0], "align": ["min", "center"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "right"},
                {"name": "VIO", "label": "VIO", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "UH", "label": "UH", "side": "right"},
                {"name": "UL", "label": "UL", "side": "right"},
                {"name": "VH", "label": "VH", "side": "right"},
                {"name": "VL", "label": "VL", "side": "right"},
                {"name": "WH", "label": "WH", "side": "right"},
                {"name": "WL", "label": "WL", "side": "right"},
                {"name": "DIAG", "label": "DIAG", "side": "right"},
                {"name": "U", "label": "U", "side": "left"},
                {"name": "V", "label": "V", "side": "left"},
                {"name": "W", "label": "W", "side": "left"},
            ],
        )
        Component(
            name="motor",
            package="motor",
            dimensions=(13.8, 13.8, 9.3),
            position=(0.0, 0.0, 28.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "1102 BLDC", "position": [-10.0, 0.0, 0.0], "align": ["max", "center"]},
            pins=[
                {"name": "U", "label": "U", "side": "top"},
                {"name": "V", "label": "V", "side": "top"},
                {"name": "W", "label": "W", "side": "top"},
            ],
        )
        Component(
            name="sensor_east",
            package="tof_sensor",
            dimensions=(17.0, 25.0, 2.0),
            joint_ref={"joint": "sensor_port_east", "offset": [-18.3, 0.0, 0.0]},
            label={"text": "VL53L0X (EAST)", "position": [10.0, 0.0, 0.0], "align": ["min", "center"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "SDA", "label": "SDA", "side": "right"},
                {"name": "SCL", "label": "SCL", "side": "right"},
                {"name": "XSHUT", "label": "XSHUT", "side": "left"},
                {"name": "INT", "label": "INT", "side": "left"},
            ],
        )
        Component(
            name="sensor_north",
            package="tof_sensor",
            dimensions=(25.0, 17.0, 2.0),
            joint_ref={"joint": "sensor_port_north", "offset": [-18.3, 0.0, 0.0]},
            label={"text": "VL53L0X (NORTH)", "position": [0.0, 10.0, 0.0], "align": ["center", "min"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "top"},
                {"name": "GND", "label": "GND", "side": "top"},
                {"name": "SDA", "label": "SDA", "side": "top"},
                {"name": "SCL", "label": "SCL", "side": "top"},
                {"name": "XSHUT", "label": "XSHUT", "side": "bottom"},
                {"name": "INT", "label": "INT", "side": "bottom"},
            ],
        )
        Component(
            name="sensor_west",
            package="tof_sensor",
            dimensions=(17.0, 25.0, 2.0),
            joint_ref={"joint": "sensor_port_west", "offset": [-18.3, 0.0, 0.0]},
            label={"text": "VL53L0X (WEST)", "position": [-10.0, 0.0, 0.0], "align": ["max", "center"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "SDA", "label": "SDA", "side": "right"},
                {"name": "SCL", "label": "SCL", "side": "right"},
                {"name": "XSHUT", "label": "XSHUT", "side": "right"},
                {"name": "INT", "label": "INT", "side": "right"},
            ],
        )
        Component(
            name="led",
            package="led",
            dimensions=(10.0, 10.0, 1.0),
            joint_ref={"joint": "led_port", "offset": [0.0, 0.0, 0.0]},
            label={"text": "RGB LED", "position": [0.0, 6.0, 0.0], "align": ["center", "min"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "DIN", "label": "DIN", "side": "left"},
            ],
        )
        Component(
            name="speed_sensor",
            package="TO-92",
            dimensions=(4.5, 2.2, 4.5),
            position=(0.0, 17.5, 12.0),
            rotation=(0.0, 0.0, 0.0),
            label={"text": "Hall", "position": [10.0, 0.0, 0.0], "align": ["min", "center"]},
            pins=[
                {"name": "VCC", "label": "VCC", "side": "left"},
                {"name": "GND", "label": "GND", "side": "left"},
                {"name": "OUT", "label": "OUT", "side": "right"},
            ],
        )
        Component(
            name="swd_adapter",
            package="board",
            dimensions=(19.1, 13.7, 1.6),
            position=(-50.0, -45.0, 23.0),
            rotation=(0.0, 0.0, 90.0),
            label={"text": "SWD", "position": [12.0, 0.0, 0.0], "align": ["min", "center"]},
            pins=[
                {"name": "SWDIO", "label": "SWDIO", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
                {"name": "SWCLK", "label": "SWCLK", "side": "right"},
            ],
        )

    with BuildWiring(name="cat_fountain_nets") as net_ctx:
        Net(
            name="gnd",
            pins=[
                ["battery", "-"],
                ["charger", "GND"],
                ["charger", "BAT-"],
                ["fuel_gauge", "GND"],
                ["sensor_east", "GND"],
                ["current_monitor", "GND"],
                ["motor_driver", "GND"],
                ["led", "GND"],
                ["sensor_north", "GND"],
                ["sensor_west", "GND"],
                ["pico", "GND_R"],
                ["speed_sensor", "GND"],
            ],
            color="black",
        )
        Net(
            name="vcc_logic",
            pins=[
                ["pico", "3V3"],
                ["sensor_west", "VCC"],
                ["sensor_north", "VCC"],
                ["led", "VCC"],
                ["sensor_east", "VCC"],
                ["fuel_gauge", "VIN"],
                ["motor_driver", "VIO"],
                ["speed_sensor", "VCC"],
            ],
            color="red",
        )
        Net(name="vcc_bat", pins=[["battery", "+"], ["charger", "BAT+"], ["fuel_gauge", "BAT"]], color="red")
        Net(name="vcc_sys_pico", pins=[["charger", "SYS"], ["pico", "VSYS"]], color="red")
        Net(name="vcc_sys_cm", pins=[["charger", "SYS"], ["current_monitor", "VIN+"]], color="red")
        Net(name="cm_jumper", pins=[["current_monitor", "VCC"], ["current_monitor", "VIN+"]], color="red")
        Net(name="vcc_sys_md", pins=[["current_monitor", "VIN-"], ["motor_driver", "VCC"]], color="red")
        Net(
            name="sda",
            pins=[
                ["pico", "GP12"],
                ["sensor_west", "SDA"],
                ["sensor_north", "SDA"],
                ["current_monitor", "SDA"],
                ["sensor_east", "SDA"],
                ["fuel_gauge", "SDA"],
            ],
            color="yellow",
        )
        Net(
            name="scl",
            pins=[
                ["pico", "GP13"],
                ["sensor_west", "SCL"],
                ["sensor_north", "SCL"],
                ["current_monitor", "SCL"],
                ["sensor_east", "SCL"],
                ["fuel_gauge", "SCL"],
            ],
            color="blue",
            offset=(1.5, 1.5),
        )
        Net(name="motor_u", pins=[["motor_driver", "U"], ["motor", "U"]], color="purple")
        Net(name="motor_v", pins=[["motor_driver", "V"], ["motor", "V"]], color="green")
        Net(name="motor_w", pins=[["motor_driver", "W"], ["motor", "W"]], color="blue")
        Net(name="led_data", pins=[["pico", "GP11"], ["led", "DIN"]], color="purple")
        Net(name="ctrl_xshut_n", pins=[["pico", "GP4"], ["sensor_north", "XSHUT"]], color="orange")
        Net(name="ctrl_xshut_e", pins=[["pico", "GP5"], ["sensor_east", "XSHUT"]], color="orange")
        Net(name="ctrl_xshut_w", pins=[["pico", "GP6"], ["sensor_west", "XSHUT"]], color="orange")
        Net(name="ctrl_int_n", pins=[["pico", "GP7"], ["sensor_north", "INT"]], color="green")
        Net(name="ctrl_int_e", pins=[["pico", "GP9"], ["sensor_east", "INT"]], color="green")
        Net(name="ctrl_int_w", pins=[["pico", "GP10"], ["sensor_west", "INT"]], color="green")
        Net(name="ctrl_alrt", pins=[["pico", "GP14"], ["fuel_gauge", "ALRT"]], color="orange")
        Net(name="ctrl_uh", pins=[["pico", "GP16"], ["motor_driver", "UH"]], color="brown")
        Net(name="ctrl_ul", pins=[["pico", "GP17"], ["motor_driver", "UL"]], color="teal", offset=(1.0, 1.0))
        Net(name="ctrl_vh", pins=[["pico", "GP18"], ["motor_driver", "VH"]], color="magenta")
        Net(name="ctrl_vl", pins=[["pico", "GP19"], ["motor_driver", "VL"]], color="purple", offset=(1.0, 1.0))
        Net(name="ctrl_wh", pins=[["pico", "GP20"], ["motor_driver", "WH"]], color="yellow")
        Net(name="ctrl_wl", pins=[["pico", "GP21"], ["motor_driver", "WL"]], color="orange", offset=(1.0, 1.0))
        Net(name="ctrl_diag", pins=[["pico", "GP22"], ["motor_driver", "DIAG"]], color="blue")
        Net(name="speed_sense", pins=[["pico", "GP26"], ["speed_sensor", "OUT"]], color="green")

    wiring = Wiring.from_models(
        footprints=layout.components,
        nets=net_ctx.nets,
        parent_part=parent_part,
        symbol_table=layout.symbol_table_entries,
    )
    return wiring


def make_pcb(w: float, l: float, h: float = 2.0) -> Part:
    """Build a dummy 3D solid for a rectangular PCB with corner fillets."""
    with BuildPart() as pcb:
        Box(w, l, h, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        r = min(1.5, min(w, l) * 0.4)
        if r > 0.1:
            fillet(pcb.edges().filter_by(Axis.Z), radius=r)
    return cast(Part, pcb.part)


def make_sensor_pcb() -> Part:
    """Build a dummy 3D solid for a ToF sensor PCB module."""
    with BuildPart() as pcb:
        Box(2.0, 25.0, 17.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        fillet(pcb.edges().filter_by(Axis.X), radius=1.5)
    return cast(Part, pcb.part)


def make_motor(dia: float = 13.8, h: float = 9.3) -> Part:
    """Build a dummy 3D solid for a 1102 BLDC motor."""
    with BuildPart() as motor:
        Cylinder(radius=dia / 2.0, height=h, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        with Locations((0, 0, h / 2.0)):
            Cylinder(radius=0.75, height=7.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return cast(Part, motor.part)


def build_rp2040_key(provider: Any, room: Room, wiring: Wiring) -> None:
    """Add a dedicated RP2040 GPIO pinout key in the bottom-left corner of the wiring diagram."""
    pico_nets: Dict[str, Tuple[str, str]] = {}
    for net in wiring.nets:
        color = getattr(net, "color", "grey")
        net_name = net.name
        for comp, pin in net.pins:
            if comp == "pico":
                pico_nets[pin] = (net_name, color)

    signal_labels = {
        "sda": "I2C_SDA",
        "scl": "I2C_SCL",
    }

    box_cx, box_cy = provider.RP2040_KEY_CENTER
    box_w = provider.RP2040_KEY_BOX_WIDTH
    box_h = provider.RP2040_KEY_BOX_HEIGHT

    with BuildSketch() as key_border:
        Rectangle(box_w, box_h)
        fillet(key_border.vertices(), radius=provider.RP2040_KEY_CORNER_RADIUS)
    room.add(
        "rp2040_key_border",
        key_border.sketch.moved(Location((box_cx, box_cy))),
        color="grey",
        line_weight=1.5,
    )

    room.add_label(
        "rp2040_key_title",
        "RP2040 GPIO KEY",
        Vector(box_cx, box_cy + box_h / 2.0 - 4.0, 0.0),
        options=TextArgs(font_size=2.0, align=(Align.CENTER, Align.CENTER), font="Serif"),
    )

    with BuildLine() as div:
        Line(
            (box_cx - box_w / 2.0 + 3.0, box_cy + box_h / 2.0 - 7.0),
            (box_cx + box_w / 2.0 - 3.0, box_cy + box_h / 2.0 - 7.0),
        )
    room.add("rp2040_key_divider", div.line, color="grey", line_weight=1.0)

    start_y = box_cy + box_h / 2.0 - 11.0
    col1_x = box_cx - box_w / 2.0 + 3.5
    col2_x = box_cx + 2.0

    for idx, gpio in enumerate(provider.RP2040_KEY_LEFT_GPIOS):
        if gpio not in pico_nets:
            continue
        net_name, color = pico_nets[gpio]
        display_name = signal_labels.get(net_name, net_name.upper())
        y = start_y - idx * provider.RP2040_KEY_ROW_PITCH
        with BuildLine() as sw:
            Line((col1_x, y), (col1_x + provider.RP2040_KEY_SWATCH_LENGTH, y))
        room.add(f"rp2040_key_swatch_{gpio.lower()}", sw.line, color=color, line_weight=2.0)
        with BuildSketch() as dot:
            Circle(radius=provider.RP2040_KEY_DOT_RADIUS)
        room.add(f"rp2040_key_dot_{gpio.lower()}", dot.sketch.moved(Location((col1_x, y))), color=color)
        room.add_label(
            f"rp2040_key_lbl_{gpio.lower()}",
            f"{gpio}: {display_name}",
            Vector(col1_x + provider.RP2040_KEY_SWATCH_LENGTH + 1.0, y, 0.0),
            options=TextArgs(font_size=1.4, align=(Align.MIN, Align.CENTER), font="Serif"),
        )

    for idx, gpio in enumerate(provider.RP2040_KEY_RIGHT_GPIOS):
        if gpio not in pico_nets:
            continue
        net_name, color = pico_nets[gpio]
        display_name = signal_labels.get(net_name, net_name.upper())
        y = start_y - idx * provider.RP2040_KEY_ROW_PITCH
        with BuildLine() as sw:
            Line((col2_x, y), (col2_x + provider.RP2040_KEY_SWATCH_LENGTH, y))
        room.add(f"rp2040_key_swatch_{gpio.lower()}", sw.line, color=color, line_weight=2.0)
        with BuildSketch() as dot:
            Circle(radius=provider.RP2040_KEY_DOT_RADIUS)
        room.add(f"rp2040_key_dot_{gpio.lower()}", dot.sketch.moved(Location((col2_x, y))), color=color)
        room.add_label(
            f"rp2040_key_lbl_{gpio.lower()}",
            f"{gpio}: {display_name}",
            Vector(col2_x + provider.RP2040_KEY_SWATCH_LENGTH + 1.0, y, 0.0),
            options=TextArgs(font_size=1.4, align=(Align.MIN, Align.CENTER), font="Serif"),
        )


def build_tmc6300_key(provider: Any, room: Room, wiring: Wiring) -> None:
    """Add a dedicated TMC6300 pinout key in the top-right corner of the wiring diagram."""
    driver_nets: Dict[str, Tuple[str, str]] = {}
    for net in wiring.nets:
        color = getattr(net, "color", "grey")
        net_name = net.name
        for comp, pin in net.pins:
            if comp == "motor_driver":
                driver_nets[pin] = (net_name, color)

    box_cx, box_cy = provider.TMC6300_KEY_CENTER
    box_w = provider.TMC6300_KEY_BOX_WIDTH
    box_h = provider.TMC6300_KEY_BOX_HEIGHT

    with BuildSketch() as key_border:
        Rectangle(box_w, box_h)
        fillet(key_border.vertices(), radius=provider.TMC6300_KEY_CORNER_RADIUS)
    room.add(
        "tmc6300_key_border",
        key_border.sketch.moved(Location((box_cx, box_cy))),
        color="grey",
        line_weight=1.5,
    )

    room.add_label(
        "tmc6300_key_title",
        "TMC6300 PIN KEY",
        Vector(box_cx, box_cy + box_h / 2.0 - 4.0, 0.0),
        options=TextArgs(font_size=2.0, align=(Align.CENTER, Align.CENTER), font="Serif"),
    )

    with BuildLine() as div:
        Line(
            (box_cx - box_w / 2.0 + 3.0, box_cy + box_h / 2.0 - 7.0),
            (box_cx + box_w / 2.0 - 3.0, box_cy + box_h / 2.0 - 7.0),
        )
    room.add("tmc6300_key_divider", div.line, color="grey", line_weight=1.0)

    start_y = box_cy + box_h / 2.0 - 11.0
    col_x = box_cx - box_w / 2.0 + 3.5

    for idx, (pin, label_text) in enumerate(provider.TMC6300_KEY_ENTRIES):
        _, color = driver_nets.get(pin, ("", "grey"))
        y = start_y - idx * provider.TMC6300_KEY_ROW_PITCH
        with BuildLine() as sw:
            Line((col_x, y), (col_x + provider.TMC6300_KEY_SWATCH_LENGTH, y))
        room.add(f"tmc6300_key_swatch_{pin.lower()}", sw.line, color=color, line_weight=2.0)
        with BuildSketch() as dot:
            Circle(radius=provider.TMC6300_KEY_DOT_RADIUS)
        room.add(f"tmc6300_key_dot_{pin.lower()}", dot.sketch.moved(Location((col_x, y))), color=color)
        room.add_label(
            f"tmc6300_key_lbl_{pin.lower()}",
            label_text,
            Vector(col_x + provider.TMC6300_KEY_SWATCH_LENGTH + 1.0, y, 0.0),
            options=TextArgs(font_size=1.4, align=(Align.MIN, Align.CENTER), font="Serif"),
        )


def build_cat_fountain_wiring_diagram(provider: Any, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
    """Render the 2D colored wiring diagram for the cat water fountain."""
    provider.settings.diagram_options.style = DiagramStyle.COLOR
    provider.settings.diagram_options.view_from = "top"

    r = provider.settings.bowl_radius
    t = provider.settings.bowl_thickness

    # Draw the bowl outline in grey
    with BuildSketch() as bowl_outline:
        Circle(radius=r)
        Circle(radius=r - t, mode=Mode.SUBTRACT)
    room.add("bowl_outline", bowl_outline.sketch, color="grey")

    # Draw the motor compartment outline in grey
    with BuildSketch() as motor_comp:
        Circle(radius=15.0)
        Circle(radius=14.0, mode=Mode.SUBTRACT)
    room.add("motor_compartment", motor_comp.sketch, color="grey")

    bowl_part = provider.build_bowl("bowl").part
    wiring = provider.wiring
    if wiring is None:
        wiring = build_cat_fountain_wiring(parent_part=bowl_part)

    diagram = WiringDiagram(wiring)
    diagram.build(room)
    build_rp2040_key(provider, room, wiring)
    build_tmc6300_key(provider, room, wiring)
