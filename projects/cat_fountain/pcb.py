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
from model.wiring import FootprintModel, NetModel, LabelModel, PinModel, PinListModel, PinSide, PinList, Pin
from provider.pcb import BuildComponents, Component, BuildWiring, Net, BuildPcb


def build_cat_fountain_wiring(parent_part: Optional[Any] = None) -> Wiring:
    """Construct in-memory Wiring container for Cat Fountain using BuildComponents and BuildWiring."""
    with BuildComponents(name="cat_fountain_components", parent_part=parent_part) as layout:
        battery = Component(
            name="battery",
            package="battery",
            dimensions=(25.0, 35.0, 6.0),
            position=(0.0, -40.0, 12.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="LiPo Battery", position=(0.0, -20.0, 0.0), align=("center", "max")),
            pins=[
                Pin(name="+", label="+", side=PinSide.RIGHT),
                Pin(name="-", label="-", side=PinSide.RIGHT),
            ],
        )
        charger = Component(
            name="charger",
            package="board",
            dimensions=(18.0, 29.0, 1.6),
            position=(0.0, -79.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="BQ25185", position=(0.0, -17.5, 0.0), align=("center", "max")),
            pins=[
                Pin(name="BAT+", label="BAT+", side=PinSide.RIGHT),
                Pin(name="BAT-", label="BAT-", side=PinSide.RIGHT),
                Pin(name="S1", label="S1", side=PinSide.RIGHT),
                Pin(name="SYS", label="SYS", side=PinSide.LEFT),
                Pin(name="GND", label="GND", side=PinSide.LEFT),
                Pin(name="S2", label="S2", side=PinSide.LEFT),
            ],
        )
        pico = Component(
            name="pico",
            package="board",
            dimensions=(17.0, 52.0, 1.6),
            position=(-50.0, 0.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            slots_per_side=20,
            label=LabelModel(text="PICO W", position=(0.0, 29.0, 0.0), align=("center", "min")),
            pins=[
                Pin(name="GP2", label="GP2", side=PinSide.RIGHT, slot=3),
                Pin(name="GP3", label="GP3", side=PinSide.RIGHT, slot=4),
                Pin(name="GP4", label="GP4", side=PinSide.RIGHT, slot=5),
                Pin(name="GP5", label="GP5", side=PinSide.RIGHT, slot=6),
                Pin(name="GP6", label="GP6", side=PinSide.RIGHT, slot=8),
                Pin(name="GP7", label="GP7", side=PinSide.RIGHT, slot=9),
                Pin(name="GP8", label="GP8", side=PinSide.RIGHT, slot=10),
                Pin(name="GP9", label="GP9", side=PinSide.RIGHT, slot=11),
                Pin(name="GP10", label="GP10", side=PinSide.RIGHT, slot=13),
                Pin(name="GP11", label="GP11", side=PinSide.RIGHT, slot=12),
                Pin(name="GP12", label="GP12", side=PinSide.RIGHT, slot=15),
                Pin(name="GP13", label="GP13", side=PinSide.RIGHT, slot=16),
                Pin(name="GP14", label="GP14", side=PinSide.RIGHT, slot=18),
                Pin(name="GP15", label="GP15", side=PinSide.RIGHT, slot=19),
                Pin(name="GP16", label="GP16", side=PinSide.LEFT, slot=1),
                Pin(name="GP17", label="GP17", side=PinSide.LEFT, slot=2),
                Pin(name="GP18", label="GP18", side=PinSide.LEFT, slot=3),
                Pin(name="GP19", label="GP19", side=PinSide.LEFT, slot=4),
                Pin(name="GP20", label="GP20", side=PinSide.LEFT, slot=5),
                Pin(name="GP21", label="GP21", side=PinSide.LEFT, slot=6),
                Pin(name="GP22", label="GP22", side=PinSide.LEFT, slot=7),
                Pin(name="GND_L", label="GND", side=PinSide.RIGHT, slot=2),
                Pin(name="VSYS", label="VSYS", side=PinSide.LEFT, slot=18),
                Pin(name="GND_R", label="GND", side=PinSide.LEFT, slot=17),
                Pin(name="3V3", label="3V3", side=PinSide.LEFT, slot=15),
                Pin(name="GP26", label="GP26", side=PinSide.LEFT, slot=11),
            ],
        )
        fuel_gauge = Component(
            name="fuel_gauge",
            package="board",
            dimensions=(24.0, 20.0, 1.6),
            position=(50.0, -45.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="MAX17048", position=(0.0, -13.0, 0.0), align=("center", "max")),
            pins=[
                Pin(name="BAT", label="BAT", side=PinSide.RIGHT),
                Pin(name="VIN", label="VIN", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="SDA", label="SDA", side=PinSide.RIGHT),
                Pin(name="SCL", label="SCL", side=PinSide.RIGHT),
                Pin(name="ALRT", label="ALRT", side=PinSide.LEFT),
            ],
        )
        current_monitor = Component(
            name="current_monitor",
            package="board",
            dimensions=(25.0, 21.5, 1.6),
            position=(50.0, -15.0, 23.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="INA219", position=(15.5, 0.0, 0.0), align=("min", "center")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="SDA", label="SDA", side=PinSide.RIGHT),
                Pin(name="SCL", label="SCL", side=PinSide.RIGHT),
                Pin(name="VIN+", label="VIN+", side=PinSide.LEFT),
                Pin(name="VIN-", label="VIN-", side=PinSide.LEFT),
            ],
        )
        motor_driver = Component(
            name="motor_driver",
            package="board",
            dimensions=(20.32, 15.24, 1.6),
            position=(50.0, 15.0, 23.0),
            rotation=(0.0, 0.0, 90.0),
            label=LabelModel(text="TMC6300", position=(15.0, 0.0, 0.0), align=("min", "center")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.RIGHT),
                Pin(name="VIO", label="VIO", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="UH", label="UH", side=PinSide.RIGHT),
                Pin(name="UL", label="UL", side=PinSide.RIGHT),
                Pin(name="VH", label="VH", side=PinSide.RIGHT),
                Pin(name="VL", label="VL", side=PinSide.RIGHT),
                Pin(name="WH", label="WH", side=PinSide.RIGHT),
                Pin(name="WL", label="WL", side=PinSide.RIGHT),
                Pin(name="DIAG", label="DIAG", side=PinSide.RIGHT),
                Pin(name="U", label="U", side=PinSide.LEFT),
                Pin(name="V", label="V", side=PinSide.LEFT),
                Pin(name="W", label="W", side=PinSide.LEFT),
            ],
        )
        motor = Component(
            name="motor",
            package="motor",
            dimensions=(13.8, 13.8, 9.3),
            position=(0.0, 0.0, 28.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="1102 BLDC", position=(-10.0, 0.0, 0.0), align=("max", "center")),
            pins=[
                Pin(name="U", label="U", side=PinSide.TOP),
                Pin(name="V", label="V", side=PinSide.TOP),
                Pin(name="W", label="W", side=PinSide.TOP),
            ],
        )
        sensor_east = Component(
            name="sensor_east",
            package="tof_sensor",
            dimensions=(17.0, 25.0, 2.0),
            joint_ref={"joint": "sensor_port_east", "offset": [-18.3, 0.0, 0.0]},
            label=LabelModel(text="VL53L0X (EAST)", position=(10.0, 0.0, 0.0), align=("min", "center")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="SDA", label="SDA", side=PinSide.RIGHT),
                Pin(name="SCL", label="SCL", side=PinSide.RIGHT),
                Pin(name="XSHUT", label="XSHUT", side=PinSide.LEFT),
                Pin(name="INT", label="INT", side=PinSide.LEFT),
            ],
        )
        sensor_north = Component(
            name="sensor_north",
            package="tof_sensor",
            dimensions=(25.0, 17.0, 2.0),
            joint_ref={"joint": "sensor_port_north", "offset": [-18.3, 0.0, 0.0]},
            label=LabelModel(text="VL53L0X (NORTH)", position=(0.0, 10.0, 0.0), align=("center", "min")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.TOP),
                Pin(name="GND", label="GND", side=PinSide.TOP),
                Pin(name="SDA", label="SDA", side=PinSide.TOP),
                Pin(name="SCL", label="SCL", side=PinSide.TOP),
                Pin(name="XSHUT", label="XSHUT", side=PinSide.BOTTOM),
                Pin(name="INT", label="INT", side=PinSide.BOTTOM),
            ],
        )
        sensor_west = Component(
            name="sensor_west",
            package="tof_sensor",
            dimensions=(17.0, 25.0, 2.0),
            joint_ref={"joint": "sensor_port_west", "offset": [-18.3, 0.0, 0.0]},
            label=LabelModel(text="VL53L0X (WEST)", position=(-10.0, 0.0, 0.0), align=("max", "center")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="SDA", label="SDA", side=PinSide.RIGHT),
                Pin(name="SCL", label="SCL", side=PinSide.RIGHT),
                Pin(name="XSHUT", label="XSHUT", side=PinSide.RIGHT),
                Pin(name="INT", label="INT", side=PinSide.RIGHT),
            ],
        )
        led = Component(
            name="led",
            package="led",
            dimensions=(10.0, 10.0, 1.0),
            joint_ref={"joint": "led_port", "offset": [0.0, 0.0, 0.0]},
            label=LabelModel(text="RGB LED", position=(0.0, 6.0, 0.0), align=("center", "min")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="DIN", label="DIN", side=PinSide.LEFT),
            ],
        )
        speed_sensor = Component(
            name="speed_sensor",
            package="TO-92",
            dimensions=(4.5, 2.2, 4.5),
            position=(0.0, 17.5, 12.0),
            rotation=(0.0, 0.0, 0.0),
            label=LabelModel(text="Hall", position=(10.0, 0.0, 0.0), align=("min", "center")),
            pins=[
                Pin(name="VCC", label="VCC", side=PinSide.LEFT),
                Pin(name="GND", label="GND", side=PinSide.LEFT),
                Pin(name="OUT", label="OUT", side=PinSide.RIGHT),
            ],
        )
        swd_adapter = Component(
            name="swd_adapter",
            package="board",
            dimensions=(19.1, 13.7, 1.6),
            position=(-50.0, -45.0, 23.0),
            rotation=(0.0, 0.0, 90.0),
            label=LabelModel(text="SWD", position=(12.0, 0.0, 0.0), align=("min", "center")),
            pins=[
                Pin(name="SWDIO", label="SWDIO", side=PinSide.RIGHT),
                Pin(name="GND", label="GND", side=PinSide.RIGHT),
                Pin(name="SWCLK", label="SWCLK", side=PinSide.RIGHT),
            ],
        )

    with BuildWiring(name="cat_fountain_nets") as net_ctx:
        Net(
            name="gnd",
            pins=[
                battery.pin("-"),
                charger.pin("GND"),
                charger.pin("BAT-"),
                fuel_gauge.pin("GND"),
                sensor_east.pin("GND"),
                current_monitor.pin("GND"),
                motor_driver.pin("GND"),
                led.pin("GND"),
                sensor_north.pin("GND"),
                sensor_west.pin("GND"),
                pico.pin("GND_R"),
                speed_sensor.pin("GND"),
            ],
            color="black",
        )
        Net(
            name="vcc_logic",
            pins=[
                pico.pin("3V3"),
                sensor_west.pin("VCC"),
                sensor_north.pin("VCC"),
                led.pin("VCC"),
                sensor_east.pin("VCC"),
                fuel_gauge.pin("VIN"),
                motor_driver.pin("VIO"),
                speed_sensor.pin("VCC"),
            ],
            color="red",
        )
        Net(name="vcc_bat", pins=[battery.pin("+"), charger.pin("BAT+"), fuel_gauge.pin("BAT")], color="red")
        Net(name="vcc_sys_pico", pins=[charger.pin("SYS"), pico.pin("VSYS")], color="red")
        Net(name="vcc_sys_cm", pins=[charger.pin("SYS"), current_monitor.pin("VIN+")], color="red")
        Net(name="cm_jumper", pins=[current_monitor.pin("VCC"), current_monitor.pin("VIN+")], color="red")
        Net(name="vcc_sys_md", pins=[current_monitor.pin("VIN-"), motor_driver.pin("VCC")], color="red")
        Net(
            name="sda",
            pins=[
                pico.pin("GP12"),
                sensor_west.pin("SDA"),
                sensor_north.pin("SDA"),
                current_monitor.pin("SDA"),
                sensor_east.pin("SDA"),
                fuel_gauge.pin("SDA"),
            ],
            color="yellow",
        )
        Net(
            name="scl",
            pins=[
                pico.pin("GP13"),
                sensor_west.pin("SCL"),
                sensor_north.pin("SCL"),
                current_monitor.pin("SCL"),
                sensor_east.pin("SCL"),
                fuel_gauge.pin("SCL"),
            ],
            color="blue",
            offset=(1.5, 1.5),
        )
        Net(name="motor_u", pins=[motor_driver.pin("U"), motor.pin("U")], color="purple")
        Net(name="motor_v", pins=[motor_driver.pin("V"), motor.pin("V")], color="green")
        Net(name="motor_w", pins=[motor_driver.pin("W"), motor.pin("W")], color="blue")
        Net(name="led_data", pins=[pico.pin("GP11"), led.pin("DIN")], color="purple")
        Net(name="ctrl_xshut_n", pins=[pico.pin("GP4"), sensor_north.pin("XSHUT")], color="orange")
        Net(name="ctrl_xshut_e", pins=[pico.pin("GP5"), sensor_east.pin("XSHUT")], color="orange")
        Net(name="ctrl_xshut_w", pins=[pico.pin("GP6"), sensor_west.pin("XSHUT")], color="orange")
        Net(name="ctrl_int_n", pins=[pico.pin("GP7"), sensor_north.pin("INT")], color="green")
        Net(name="ctrl_int_e", pins=[pico.pin("GP9"), sensor_east.pin("INT")], color="green")
        Net(name="ctrl_int_w", pins=[pico.pin("GP10"), sensor_west.pin("INT")], color="green")
        Net(name="ctrl_alrt", pins=[pico.pin("GP14"), fuel_gauge.pin("ALRT")], color="orange")
        Net(name="ctrl_uh", pins=[pico.pin("GP16"), motor_driver.pin("UH")], color="brown")
        Net(name="ctrl_ul", pins=[pico.pin("GP17"), motor_driver.pin("UL")], color="teal", offset=(1.0, 1.0))
        Net(name="ctrl_vh", pins=[pico.pin("GP18"), motor_driver.pin("VH")], color="magenta")
        Net(name="ctrl_vl", pins=[pico.pin("GP19"), motor_driver.pin("VL")], color="purple", offset=(1.0, 1.0))
        Net(name="ctrl_wh", pins=[pico.pin("GP20"), motor_driver.pin("WH")], color="yellow")
        Net(name="ctrl_wl", pins=[pico.pin("GP21"), motor_driver.pin("WL")], color="orange", offset=(1.0, 1.0))
        Net(name="ctrl_diag", pins=[pico.pin("GP22"), motor_driver.pin("DIAG")], color="blue")
        Net(name="speed_sense", pins=[pico.pin("GP26"), speed_sensor.pin("OUT")], color="green")

    wiring = Wiring.from_models(
        footprints=layout.components,
        nets=net_ctx.nets,
        parent_part=parent_part,
    )
    return wiring


def make_pcb(w: float, l: float, h: float = 2.0, name: str = "pcb") -> Part:
    """Build a dummy 3D solid for a rectangular PCB with corner fillets."""
    with BuildPcb(name=name) as pcb:
        Box(w, l, h, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        r = min(1.5, min(w, l) * 0.4)
        if r > 0.1:
            fillet(pcb.edges().filter_by(Axis.Z), radius=r)
    return cast(Part, pcb.part)


def make_sensor_pcb(name: str = "sensor_pcb") -> Part:
    """Build a dummy 3D solid for a ToF sensor PCB module."""
    with BuildPcb(name=name) as pcb:
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
