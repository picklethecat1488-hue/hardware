"""Declarative PCB layout, rigid-flex substrates, wiring, test steps, and routing for Carrier Board."""

from typing import cast, Callable, Sequence, Any, Optional, Dict, List, Tuple, Union
from functools import cached_property
from pathlib import Path
from build123d import (
    Align,
    BuildPart,
    BuildSketch,
    Polygon,
    Rectangle,
    RectangleRounded,
    Plane,
    Location,
    RigidJoint,
    extrude,
    offset,
    Box,
    Circle,
    Cone,
    Cylinder,
    fillet,
    Locations,
    Axis,
    Mode as BuildMode,
    add,
    Text,
)
from model import Wiring, DiagramOptions, DiagramStyle
from provider import Mode, Room
from model.pcb import (
    BoardType,
    LayerType,
    MountingHoleModel,
    SilkscreenTextModel,
    SilkscreenGraphicModel,
    TraceSegmentModel,
    ViaModel,
    PCBConfig,
    PCBDesignRulesModel,
    RuleSeverity,
    RuleSeveritiesModel,
    NetClassModel,
    FlexZoneModel,
    PCBObstacleModel,
    CapacitiveElectrodeModel,
    SchematicSheetModel,
    AssemblyTestStepModel,
    AssemblyTestModel,
    StackupModel,
    SymbolTableEntry,
)
from provider.pcb import (
    BuildPcb,
    BuildFlexPCB,
    FlexType,
    BuildStackup,
    StackupLayer,
    BuildDrillHoles,
    MountingHole,
    BuildCopperRegions,
    CopperRegion,
    BuildTestPoints,
    TestPoint,
    BuildSilkscreen,
    SilkscreenText,
    SilkscreenRect,
    SilkscreenLine,
    SilkscreenPolygon,
    BuildTraces,
    Trace,
    BuildVias,
    Via,
    BuildComponents,
    Component,
    BuildWiring,
    Net,
    BuildTestSteps,
    BuildAssemblyTestSteps,
    AssemblyTestMetadata,
    TestStep,
    RouteStyle,
    SchematicMetadata,
    SchematicSheet,
    PcbMetadata,
)


def get_flex_tail_traces() -> List[TraceSegmentModel]:
    """Return pre-routed copper trace segments on F.Cu for the flexible polyimide tail."""
    raw_traces = [
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [1.0, -22.75], "end_mm": [1.0, -24.2]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [1.0, -24.2], "end_mm": [-7.5, -24.2]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-7.5, -24.2], "end_mm": [-7.5, -19.5]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-7.5, -19.5], "end_mm": [-6.6, -18.6]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.6, -18.6], "end_mm": [-6.6, 7.0]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.6, 7.0], "end_mm": [-5.0, 7.0]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.6, 7.0], "end_mm": [-6.6, 18.0]},
        {"net": "CAP_TX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.6, 18.0], "end_mm": [-4.0, 18.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [2.0, -22.75], "end_mm": [2.0, -22.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [2.0, -22.0], "end_mm": [1.8, -21.8]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [1.8, -21.8], "end_mm": [-6.5, -21.8]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.5, -21.8], "end_mm": [-6.5, -19.5]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.5, -19.5], "end_mm": [-6.0, -19.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.0, -19.0], "end_mm": [-6.0, -3.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.0, -3.0], "end_mm": [-5.0, -3.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.0, -3.0], "end_mm": [-6.0, 2.0]},
        {"net": "CAP_TX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-6.0, 2.0], "end_mm": [-5.0, 2.0]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [3.0, -22.75], "end_mm": [3.0, -22.0]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [3.0, -22.0], "end_mm": [3.5, -21.5]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [3.5, -21.5], "end_mm": [3.5, -20.5]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [3.5, -20.5], "end_mm": [-5.4, -20.5]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-5.4, -20.5], "end_mm": [-5.4, -13.0]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-5.4, -13.0], "end_mm": [-5.0, -13.0]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-5.4, -13.0], "end_mm": [-5.4, -8.0]},
        {"net": "CAP_TX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-5.4, -8.0], "end_mm": [-5.0, -8.0]},
        {"net": "CAP_RX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [5.0, -22.75], "end_mm": [5.0, -22.0]},
        {"net": "CAP_RX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [5.0, -22.0], "end_mm": [5.4, -21.6]},
        {"net": "CAP_RX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [5.4, -21.6], "end_mm": [5.4, -13.0]},
        {"net": "CAP_RX0", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [5.4, -13.0], "end_mm": [5.0, -13.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -22.75], "end_mm": [6.0, -22.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -22.0], "end_mm": [6.45, -21.55]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.45, -21.55], "end_mm": [6.45, -19.5]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.45, -19.5], "end_mm": [6.0, -19.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -19.0], "end_mm": [6.0, -8.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -8.0], "end_mm": [5.0, -8.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -8.0], "end_mm": [6.0, -3.0]},
        {"net": "CAP_RX1", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.0, -3.0], "end_mm": [5.0, -3.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.0, -22.75], "end_mm": [7.0, -21.7]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.0, -21.7], "end_mm": [6.8, -21.5]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.8, -21.5], "end_mm": [6.8, -19.5]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.8, -19.5], "end_mm": [6.6, -19.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, -19.0], "end_mm": [6.6, 2.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, 2.0], "end_mm": [5.0, 2.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, 2.0], "end_mm": [6.6, 7.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, 7.0], "end_mm": [5.0, 7.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, 7.0], "end_mm": [6.6, 18.0]},
        {"net": "CAP_RX2", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [6.6, 18.0], "end_mm": [4.0, 18.0]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [4.0, -22.75], "end_mm": [4.0, -24.2]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [4.0, -24.2], "end_mm": [7.4, -24.2]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.4, -24.2], "end_mm": [7.4, -18.5]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.4, -18.5], "end_mm": [7.1, -18.1]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.1, -18.1], "end_mm": [7.1, 24.5]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [7.1, 24.5], "end_mm": [-7.1, 24.5]},
        {"net": "CAP_RX3", "layer": "F.Cu", "width_mm": 0.15, "start_mm": [-7.1, 24.5], "end_mm": [-7.1, -17.5]},
    ]
    return [TraceSegmentModel(**t) for t in raw_traces]


def get_flex_tail_vias() -> List[ViaModel]:
    """Return interlayer vias for the flexible sensing tail."""
    raw_vias = []
    return [ViaModel(**v) for v in raw_vias]


class CarrierBoardPCB:
    """PCB substrate builders, layer stackups, drill holes, and physical copper geometries."""

    def stackup(self) -> BuildStackup:
        """Define 6-layer rigid-flex physical stackup using BuildStackup context manager."""
        with BuildStackup(finish="ENIG", soldermask_color="matte_black", silkscreen_color="white") as s:
            StackupLayer(name="F.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL)
            StackupLayer(
                name="Prepreg1", thickness_mm=0.100, material="fr4_prepreg_2116", layer_type=LayerType.DIELECTRIC
            )
            StackupLayer(name="In1.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.GROUND)
            StackupLayer(name="Core1", thickness_mm=0.450, material="fr4_core", layer_type=LayerType.DIELECTRIC)
            StackupLayer(name="In2.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL)
            StackupLayer(
                name="FlexDielectric", thickness_mm=0.200, material="polyimide_flex", layer_type=LayerType.DIELECTRIC
            )
            StackupLayer(name="In3.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.POWER)
            StackupLayer(name="Core2", thickness_mm=0.450, material="fr4_core", layer_type=LayerType.DIELECTRIC)
            StackupLayer(name="In4.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL)
            StackupLayer(
                name="Prepreg2", thickness_mm=0.100, material="fr4_prepreg_2116", layer_type=LayerType.DIELECTRIC
            )
            StackupLayer(name="B.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL)
        return s

    def mounting_holes(self) -> list[MountingHoleModel]:
        """Define CAD-located PCB drill and mounting holes using BuildDrillHoles context manager."""
        w = self.settings.board_width
        length = self.settings.board_length
        inset = self.settings.mounting_hole_inset
        hole_dia = self.settings.mounting_hole_diameter
        hole_x = (w / 2.0) - inset
        hole_y = (length / 2.0) - inset

        with BuildDrillHoles(default_plated=True, default_net="GND") as dh:
            with Locations(
                (hole_x, hole_y),
                (-hole_x, hole_y),
                (-hole_x, -hole_y),
                (hole_x, -hole_y),
            ):
                MountingHole(name="MH", drill_diameter_mm=hole_dia, pad_diameter_mm=hole_dia + 1.3)
        return dh.holes

    def carrier_board(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPcb:
        """Build the rigid 6-layer carrier board substrate with rounded corners and mounting holes."""
        w = self.settings.board_width
        length = self.settings.board_length
        thickness = self.settings.board_thickness
        r_corner = self.settings.corner_radius
        hole_dia = self.settings.mounting_hole_diameter
        inset = self.settings.mounting_hole_inset

        pcb_rev = "2.0"
        rules = PCBDesignRulesModel(
            min_clearance_mm=0.03,
            min_fine_pitch_clearance_mm=0.03,
            fine_pitch_pad_threshold_mm=0.35,
            min_track_width_mm=0.1,
            default_track_width_mm=0.12,
            min_copper_edge_clearance_mm=0.15,
            min_hole_to_hole_mm=0.03,
            min_hole_clearance_mm=0.03,
            min_via_diameter_mm=0.35,
            default_via_diameter_mm=0.36,
            default_via_drill_mm=0.16,
            via_penalty=2.0,
            pad_to_mask_clearance_mm=0.0,
            rule_severities=RuleSeveritiesModel(
                hole_to_hole=RuleSeverity.IGNORE,
                hole_near_hole=RuleSeverity.IGNORE,
                lib_footprint_issues=RuleSeverity.IGNORE,
                text_height=RuleSeverity.IGNORE,
                silk_overlap=RuleSeverity.IGNORE,
                silk_over_copper=RuleSeverity.IGNORE,
                track_dangling=RuleSeverity.IGNORE,
                silk_edge_clearance=RuleSeverity.IGNORE,
            ),
        )

        net_classes = [
            NetClassModel(
                name="BTLE_HIGH_SPEED_UART",
                trace_width_mm=0.12,
                clearance_mm=0.12,
                via_dia_mm=0.36,
                via_drill_mm=0.16,
                interface_type="uart",
                description="High-speed 1Mb/s UART interface between U1 MCU and U11 BTLE module",
                single_nets=["BLE_RX", "BLE_RTS", "BLE_TX", "BLE_CTS"],
            ),
            NetClassModel(
                name="RF_2GHZ",
                trace_width_mm=0.13,
                clearance_mm=0.2,
                via_dia_mm=0.36,
                via_drill_mm=0.16,
                interface_type="rf",
                coplanar_waveguide=True,
                ground_gap_mm=0.22,
                keepout_clearance_mm=1.5,
                single_nets=["RF_ANT_FEED"],
            ),
            NetClassModel(
                name="I2C_BUS",
                trace_width_mm=0.12,
                clearance_mm=0.12,
                via_dia_mm=0.36,
                via_drill_mm=0.16,
                interface_type="digital",
                single_nets=["I2C_SDA", "I2C_SCL"],
            ),
            NetClassModel(
                name="PWR_3V3",
                trace_width_mm=0.12,
                clearance_mm=0.2,
                via_dia_mm=0.36,
                via_drill_mm=0.16,
                interface_type="power",
                single_nets=["3V3"],
            ),
        ]

        flex_zones = [
            FlexZoneModel(
                name="flex_tail_ribbon",
                start_x_mm=30.0,
                length_mm=54.0,
                substrate_thickness_mm=0.05,
                coverlay_thickness_mm=0.025,
                coverlay_color="black",
                min_bend_radius_mm=3.0,
                shape_ref="flex_tail",
            )
        ]

        obstacles = [
            PCBObstacleModel(
                name="U1",
                shape="box",
                dimensions_mm=(12.0, 12.0, 2.0),
                position_mm=(0.0, 0.0, 1.8),
                description="MCU BGA at center",
            ),
            PCBObstacleModel(
                name="U11",
                shape="box",
                dimensions_mm=(10.0, 15.0, 2.23),
                position_mm=(0.0, -36.0, 1.915),
                description="BTLE transceiver module with integrated PCB antenna",
            ),
            PCBObstacleModel(
                name="J15",
                shape="box",
                dimensions_mm=(6.35, 3.81, 5.0),
                position_mm=(-14.5, -41.0, 3.3),
                description="SWD recovery header",
            ),
            PCBObstacleModel(
                name="ble_antenna_keepout",
                shape="box",
                dimensions_mm=(16.0, 5.0, 1.6),
                position_mm=(0.0, -42.0, 0.8),
                description="RF ground plane keepout for integrated PCB antenna",
            ),
            PCBObstacleModel(
                name="J2",
                shape="box",
                dimensions_mm=(25.0, 5.0, 2.0),
                position_mm=(0.0, 38.0, 1.8),
                description="Hirose FPC-30P connector",
            ),
            PCBObstacleModel(
                name="J3",
                shape="box",
                dimensions_mm=(9.0, 9.0, 4.0),
                position_mm=(-25.0, 0.0, 2.8),
                description="USB Type-C receptacle",
            ),
            PCBObstacleModel(
                name="J5",
                shape="box",
                dimensions_mm=(6.0, 12.0, 6.0),
                position_mm=(-21.0, -7.0, 3.8),
                description="SWD 10-pin micro-header",
            ),
            PCBObstacleModel(
                name="J13",
                shape="box",
                dimensions_mm=(6.0, 8.0, 7.0),
                position_mm=(-23.0, 16.0, 4.3),
                description="Battery 2-pin JST-PH connector",
            ),
            PCBObstacleModel(
                name="J9",
                shape="box",
                dimensions_mm=(6.0, 17.0, 7.0),
                position_mm=(24.5, -14.0, 4.3),
                description="Expansion header on right edge",
            ),
            PCBObstacleModel(
                name="J10",
                shape="box",
                dimensions_mm=(6.0, 17.0, 7.0),
                position_mm=(24.5, -31.0, 4.3),
                description="Expansion header on right edge",
            ),
        ]

        omitted_designators = [fp.name for fp in self.wiring.footprints if getattr(fp, "omit_silkscreen", False)]

        with BuildPcb(
            name="CarrierBoard",
            shape_ref="carrier_board",
            board_type=BoardType.RIGID,
            revision=pcb_rev,
            sheet_size="A4",
            omitted_silkscreen_designators=omitted_designators,
            design_rules=rules,
            net_classes=net_classes,
            flex_zones=flex_zones,
            obstacles=obstacles,
            stackup=self.stackup(),
        ) as pcb:
            with SchematicMetadata(sheet_size="A4") as sched:
                SchematicSheet(
                    title="USB-C Power & Battery Interface",
                    description="USB-C connector, CC pull-down termination, Li-Ion battery connector, and MAX17048 fuel gauge",
                    components=["J3", "R3", "R4", "J13", "C13", "U7", "C7", "C16"],
                    pin_breakouts={
                        "J3": ["VBUS", "VBUS2", "GND", "GND2", "CC1", "CC2", "SHIELD1", "SHIELD2"],
                        "J13": ["1", "2"],
                        "C13": ["1", "2"],
                        "U7": ["1", "2", "3", "4", "5", "7", "8"],
                        "R3": ["1", "2"],
                        "R4": ["1", "2"],
                        "C7": ["1", "2"],
                        "C16": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="3.3V Power Regulation & Distribution",
                    description="Low-dropout linear voltage regulator with C8 bulk filtering, and system decoupling",
                    layout={"cols_per_row": 4, "grid_positions": {"U3": [0, 0], "C8": [0, 1]}},
                    components=["U3", "C6", "C1", "C2", "C3", "C8"],
                    pin_breakouts={
                        "U3": ["1", "2", "3", "4", "5"],
                        "C8": ["1", "2"],
                        "C1": ["1", "2"],
                        "C2": ["1", "2"],
                        "C3": ["1", "2"],
                        "C6": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="Peripheral Power Regulation & Gating",
                    description="Dedicated 3.3V peripheral buck regulator (TLV62568) and power gating enable control",
                    components=["U1", "U10", "D8", "C15"],
                    pin_sides={
                        "U1": {"L5": "right"},
                        "U10": {"3": "left", "1": "left", "2": "left", "5": "right"},
                        "D8": {"1": "left", "2": "right"},
                    },
                    pin_breakouts={"U1": ["L5"], "U10": ["3", "1", "2", "5"], "D8": ["1", "2"], "C15": ["1", "2"]},
                )
                SchematicSheet(
                    title="Microcontroller Core, Clock & Reset",
                    description="Primary microcontroller core, 24MHz crystal oscillator, power bypass, reset and boot circuitry",
                    layout={"col_gap": 65.0},
                    components=["U1", "Y1", "C9", "C10", "R5", "C11", "R6", "C4", "C5"],
                    pin_sides={
                        "U1": {"J8": "left", "H8": "left", "F2": "right", "F1": "right", "F3": "left", "C14": "left"},
                        "Y1": {"1": "left", "3": "left", "2": "right", "4": "right"},
                    },
                    pin_breakouts={
                        "U1": ["J8", "H8", "F2", "F1", "F3", "C14"],
                        "Y1": ["1", "2", "3", "4"],
                        "C9": ["1", "2"],
                        "C10": ["1", "2"],
                        "R5": ["1", "2"],
                        "C11": ["1", "2"],
                        "R6": ["1", "2"],
                        "C4": ["1", "2"],
                        "C5": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="External Serial NAND Storage Subsystem",
                    description="Winbond W25N01GV 1Gb SLC serial NAND flash on FlexSPI Port A",
                    components=["U1", "U8", "C17"],
                    pin_sides={
                        "U1": {
                            "B17": "right",
                            "D14": "right",
                            "E14": "right",
                            "F15": "right",
                            "F17": "right",
                            "F16": "right",
                        },
                        "U8": {
                            "1": "left",
                            "6": "left",
                            "5": "left",
                            "2": "left",
                            "3": "left",
                            "7": "left",
                            "8": "right",
                            "4": "right",
                        },
                    },
                    pin_breakouts={
                        "U1": ["B17", "D14", "E14", "F15", "F17", "F16"],
                        "U8": ["1", "6", "5", "2", "3", "7", "8", "4"],
                        "C17": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="Telemetry & Debug Communications",
                    description="FTDI FT232RNQ high-speed USB-to-UART serial bridge and ARM 10-pin SWD debug micro-header",
                    components=["U1", "U9", "J5"],
                    pin_sides={
                        "U1": {
                            "B6": "right",
                            "A6": "right",
                            "F10": "right",
                            "E10": "right",
                            "A17": "right",
                            "A16": "right",
                        },
                        "U9": {
                            "1": "left",
                            "5": "left",
                            "3": "left",
                            "11": "left",
                            "4": "right",
                            "15": "right",
                            "16": "right",
                            "18": "right",
                            "19": "right",
                            "20": "right",
                            "21": "right",
                            "22": "right",
                            "23": "right",
                            "25": "right",
                            "26": "right",
                            "29": "right",
                            "7": "right",
                        },
                        "J5": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left"},
                    },
                    pin_breakouts={
                        "U1": ["B6", "A6", "F10", "E10", "A17", "A16"],
                        "U9": [
                            "1",
                            "5",
                            "3",
                            "11",
                            "4",
                            "15",
                            "16",
                            "18",
                            "19",
                            "20",
                            "21",
                            "22",
                            "23",
                            "25",
                            "26",
                            "29",
                            "7",
                        ],
                        "J5": ["1", "2", "3", "4", "5"],
                    },
                )
                SchematicSheet(
                    title="User Interface & Status Indication",
                    description="TI LP5009 9-channel I2C constant-current LED driver and high-brightness RGB status indicator",
                    components=["U1", "U6", "D1"],
                    pin_sides={
                        "U1": {"A10": "right", "B10": "right"},
                        "U6": {
                            "1": "left",
                            "2": "left",
                            "5": "left",
                            "3": "left",
                            "4": "left",
                            "15": "left",
                            "6": "right",
                            "7": "right",
                            "8": "right",
                            "16": "right",
                        },
                        "D1": {"1": "left", "2": "left", "3": "left", "4": "left"},
                    },
                    pin_breakouts={
                        "U1": ["A10", "B10"],
                        "U6": ["1", "2", "5", "3", "4", "15", "6", "7", "8", "16"],
                        "D1": ["1", "2", "3", "4"],
                    },
                )
                SchematicSheet(
                    title="Capacitive Sensing & Control (Azoteq IQS7222A)",
                    description="Azoteq IQS7222A ProxFusion controller, 5-button slider, action button, and proximity sensing flex tail, and I2C bus",
                    layout={"col_gap": 65.0},
                    components=["U1", "U2", "J2", "R1", "R2", "C12", "C14"],
                    pin_sides={
                        "U1": {"C5": "right", "C6": "right", "C4": "right"},
                        "U2": {
                            "SCL": "left",
                            "SDA": "left",
                            "RDY": "left",
                            "VDD": "left",
                            "MCLR": "left",
                            "VSS": "left",
                            "EP": "left",
                            "CR0": "right",
                            "CR1": "right",
                            "CR2": "right",
                            "CR3": "right",
                            "CR4": "right",
                            "CR5": "right",
                            "CR6": "right",
                            "CR7": "right",
                            "CT8": "right",
                            "OUTA": "right",
                        },
                        "J2": {
                            "CAP_RX0": "left",
                            "CAP_RX1": "left",
                            "CAP_RX2": "left",
                            "CAP_RX3": "left",
                            "CAP_TX0": "left",
                            "CAP_TX1": "left",
                            "CAP_TX2": "left",
                            "CAP_SHIELD": "left",
                        },
                    },
                    pin_breakouts={
                        "U1": ["C5", "C6", "C4"],
                        "U2": [
                            "SCL",
                            "SDA",
                            "RDY",
                            "VDD",
                            "MCLR",
                            "VSS",
                            "EP",
                            "CR0",
                            "CR1",
                            "CR2",
                            "CR3",
                            "CR4",
                            "CR5",
                            "CR6",
                            "CR7",
                            "CT8",
                        ],
                        "J2": [
                            "CAP_RX0",
                            "CAP_RX1",
                            "CAP_RX2",
                            "CAP_RX3",
                            "CAP_TX0",
                            "CAP_TX1",
                            "CAP_TX2",
                            "CAP_SHIELD",
                        ],
                        "R1": ["1", "2"],
                        "R2": ["1", "2"],
                        "C12": ["1", "2"],
                        "C14": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="Audio Subsystem",
                    description="MAX98357A I2S/PDM digital audio amplifier and piezo speaker",
                    layout={"cols_per_row": 3, "grid_positions": {"U1": [0, 0], "U4": [0, 1], "U5": [0, 2]}},
                    components=["U4", "U5", "U1"],
                    pin_sides={
                        "U1": {"G2": "right", "H1": "right", "J1": "right", "L4": "right"},
                        "U4": {
                            "BCLK": "left",
                            "DIN": "left",
                            "LRCLK": "left",
                            "SD_MODE": "left",
                            "VDD": "left",
                            "GND": "left",
                            "GAIN": "left",
                            "OUTP": "right",
                            "OUTN": "right",
                        },
                        "U5": {"1": "left", "2": "left"},
                    },
                    pin_breakouts={
                        "U1": ["G2", "H1", "J1", "L4"],
                        "U4": ["BCLK", "DIN", "LRCLK", "SD_MODE", "VDD", "GND", "GAIN", "OUTP", "OUTN"],
                        "U5": ["1", "2"],
                    },
                )
                SchematicSheet(
                    title="High-Speed BTLE UART & Wireless Interface",
                    description="BTLE transceiver module (U11) with 1Mb/s high-speed UART link, flow control, cap-touch pairing trigger, and integrated PCB antenna",
                    layout={
                        "cols_per_row": 3,
                        "col_gap": 50.0,
                        "grid_positions": {"U1": [0, 0], "U11": [0, 1], "J16": [0, 2]},
                    },
                    components=["U11", "U1", "C18", "C19", "J16"],
                    pin_sides={
                        "U1": {"T2": "left", "T1": "left", "T3": "left", "T4": "left"},
                        "U11": {
                            "RXD": "left",
                            "RTS": "left",
                            "TXD": "left",
                            "CTS": "left",
                            "RESET_N": "left",
                            "GND": "right",
                            "3V3": "right",
                            "NFC1": "right",
                            "NFC2": "right",
                        },
                        "C18": {"1": "left", "2": "right"},
                        "C19": {"1": "left", "2": "right"},
                        "J16": {"1": "left", "2": "left"},
                    },
                    pin_breakouts={
                        "U11": ["RXD", "RTS", "TXD", "CTS", "RESET_N", "GND", "3V3", "NFC1", "NFC2"],
                        "C18": ["1", "2"],
                        "C19": ["1", "2"],
                        "J16": ["1", "2"],
                        "U1": ["T2", "T1", "T3", "T4"],
                    },
                )
                SchematicSheet(
                    title="BTLE Programming & Reset Interface (J15, SW2)",
                    description="BLE SWD debug/recovery header (J15, DNP) and manual reset push button switch (SW2) for the NINA-B312 BLE module",
                    layout={
                        "cols_per_row": 2,
                        "col_gap": 50.0,
                        "top_row_y": 110.0,
                        "grid_positions": {"J15": [0, 0], "SW2": [0, 1]},
                    },
                    components=["J15", "SW2"],
                    pin_sides={
                        "J15": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left"},
                        "SW2": {"1": "left", "2": "right"},
                    },
                    pin_breakouts={"J15": ["1", "2", "3", "4", "5"], "SW2": ["1", "2"]},
                )
                SchematicSheet(
                    title="I2C Peripheral Expansion Interface (J6)",
                    description="Primary I2C peripheral expansion connector (JST-PH-6P)",
                    components=["U1", "J6"],
                    pin_sides={
                        "U1": {"A1": "right", "B1": "right", "B2": "right"},
                        "J6": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                    },
                    pin_breakouts={"U1": ["B2", "A1", "B1"], "J6": ["1", "2", "3", "4", "5", "6"]},
                )
                SchematicSheet(
                    title="I3C Primary Controller Expansion Interface (J7)",
                    description="High-speed I3C0 primary peripheral expansion connector (JST-PH-6P)",
                    components=["U1", "J7"],
                    pin_sides={
                        "U1": {"B8": "right", "A8": "right", "C8": "right"},
                        "J7": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                    },
                    pin_breakouts={"U1": ["B8", "A8", "C8"], "J7": ["1", "2", "3", "4", "5", "6"]},
                )
                SchematicSheet(
                    title="I3C Secondary Controller Expansion Interface (J8)",
                    description="High-speed I3C1 secondary peripheral expansion connector (JST-PH-6P)",
                    components=["U1", "J8"],
                    pin_sides={
                        "U1": {"E4": "right", "F6": "right", "F4": "right"},
                        "J8": {"1": "left", "2": "left", "3": "left", "4": "left", "5": "left", "6": "left"},
                    },
                    pin_breakouts={"U1": ["E4", "F6", "F4"], "J8": ["1", "2", "3", "4", "5", "6"]},
                )
                SchematicSheet(
                    title="SPI Master Expansion Interface (J9)",
                    description="High-speed SPI peripheral expansion connector (JST-PH-7P)",
                    components=["U1", "J9"],
                    pin_sides={
                        "U1": {"R9": "right", "R8": "right", "T7": "right", "T6": "right", "T8": "right"},
                        "J9": {
                            "1": "left",
                            "2": "left",
                            "3": "left",
                            "4": "left",
                            "5": "left",
                            "6": "left",
                            "7": "left",
                        },
                    },
                    pin_breakouts={"U1": ["R9", "R8", "T7", "T6", "T8"], "J9": ["1", "2", "3", "4", "5", "6", "7"]},
                )
                SchematicSheet(
                    title="UART & Control Expansion Interface (J10)",
                    description="FTDI auxiliary UART and modem control expansion connector (JST-PH-7P)",
                    components=["U9", "J10"],
                    pin_sides={
                        "U9": {"2": "right", "13": "right", "12": "right", "10": "right", "9": "right"},
                        "J10": {
                            "1": "right",
                            "2": "right",
                            "3": "left",
                            "4": "left",
                            "5": "left",
                            "6": "left",
                            "7": "left",
                        },
                    },
                    pin_breakouts={"U9": ["2", "13", "12", "10", "9"], "J10": ["2", "1", "3", "4", "5", "6", "7"]},
                )
                SchematicSheet(
                    title="General Purpose I/O Expansion Header",
                    description="10-pin multipurpose microcontroller GPIO expansion header",
                    components=["U1", "J14"],
                    pin_sides={
                        "U1": {"M8": "left", "N8": "left", "N10": "right", "T10": "right"},
                        "J14": {
                            "1": "left",
                            "2": "left",
                            "3": "left",
                            "4": "left",
                            "5": "left",
                            "6": "left",
                            "7": "right",
                            "8": "right",
                            "9": "right",
                            "10": "right",
                        },
                    },
                    pin_breakouts={
                        "U1": ["M8", "N8", "N10", "T10"],
                        "J14": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                    },
                )
                SchematicSheet(
                    title="Status and Overrides - MCU Reset & Bootloader",
                    description="Manual reset pushbutton and FTDI hardware programming jumpers",
                    layout={
                        "cols_per_row": 3,
                        "top_row_y": 152.0,
                        "grid_positions": {"SW1": [0, 0], "JP1": [0, 1], "JP2": [0, 2]},
                    },
                    components=["SW1", "JP1", "JP2"],
                    pin_sides={
                        "SW1": {"1": "left", "2": "left"},
                        "JP1": {"1": "left", "2": "left"},
                        "JP2": {"1": "left", "2": "left"},
                    },
                )
                SchematicSheet(
                    title="Status and Overrides - Power Isolation & Boot Mode",
                    description="Boot configuration and USB charger isolation jumpers",
                    layout={"cols_per_row": 2, "top_row_y": 152.0, "grid_positions": {"JP3": [0, 0], "JP4": [0, 1]}},
                    components=["JP3", "JP4"],
                    pin_sides={"JP3": {"1": "left", "2": "left"}, "JP4": {"1": "left", "2": "left"}},
                )
                SchematicSheet(
                    title="Status and Overrides - Primary Power LEDs",
                    description="Visual rail power indicators and current limiters for VBAT, VBUS, and 3V3",
                    layout={
                        "cols_per_row": 3,
                        "top_row_y": 168.0,
                        "row_step_y": 54.0,
                        "grid_positions": {
                            "D2": [0, 0],
                            "D3": [0, 1],
                            "D4": [0, 2],
                            "R7": [1, 0],
                            "R8": [1, 1],
                            "R9": [1, 2],
                        },
                    },
                    components=["D2", "D3", "D4", "R7", "R8", "R9"],
                    pin_sides={
                        "D2": {"1": "left", "2": "left"},
                        "D3": {"1": "left", "2": "left"},
                        "D4": {"1": "left", "2": "left"},
                    },
                )
                SchematicSheet(
                    title="Status and Overrides - Peripheral & MCU LEDs",
                    description="Subsystem activity indicators and current limiters for Audio, Peripherals, and MCU",
                    layout={
                        "cols_per_row": 3,
                        "top_row_y": 168.0,
                        "row_step_y": 54.0,
                        "grid_positions": {
                            "D5": [0, 0],
                            "D6": [0, 1],
                            "D7": [0, 2],
                            "R10": [1, 0],
                            "R11": [1, 1],
                            "R12": [1, 2],
                        },
                    },
                    components=["D5", "D6", "D7", "R10", "R11", "R12"],
                    pin_sides={
                        "D5": {"1": "left", "2": "left"},
                        "D6": {"1": "left", "2": "left"},
                        "D7": {"1": "left", "2": "left"},
                    },
                )

            # Main board outline block
            b = Box(w, length, thickness)
            # Fillet corner vertical edges
            vertical_edges = b.edges().filter_by(Axis.Z)
            if vertical_edges:
                fillet(vertical_edges, radius=r_corner)

            # Four corner mounting holes from BuildDrillHoles
            hole_x = (w / 2.0) - inset
            hole_y = (length / 2.0) - inset
            with BuildDrillHoles(default_plated=True, default_net="GND") as dh:
                with Locations(
                    (hole_x, hole_y),
                    (-hole_x, hole_y),
                    (-hole_x, -hole_y),
                    (hole_x, -hole_y),
                ):
                    MountingHole(name="MH", drill_diameter_mm=hole_dia, pad_diameter_mm=hole_dia + 1.3)
            for cyl in dh.to_shapes(depth_mm=thickness):
                add(cyl, mode=BuildMode.SUBTRACT)

            # Test point drilled through-holes
            tp = self.test_points()
            for cyl in tp.to_shapes(depth_mm=thickness):
                add(cyl, mode=BuildMode.SUBTRACT)

            cr = self.copper_regions()
            for r in cr.regions:
                if r not in pcb.copper_regions:
                    pcb.copper_regions.append(r)

            with BuildSilkscreen() as silk:
                silk.add(self.silkscreen())
                silk.add(self.silkscreen_graphics())

            with BuildTraces() as bt:
                bt.add(self.traces())
            with BuildVias() as bv:
                bv.add(self.vias())

            with AssemblyTestMetadata(
                test_fixture="flying_probe", pass_criteria="all_steps_within_tolerance", subassembly="carrier_board"
            ) as tests:
                TestStep(
                    step_id="TEST_CONTINUITY_GND",
                    description="Verify solid low-impedance ground plane continuity across all copper layers",
                    test_type="continuity",
                    net_name="GND",
                    pad_a_mm=(-18.0, -22.0),
                    pad_b_mm=(-25.0, -4.2),
                    nominal=0.05,
                    tolerance_pct=20.0,
                    unit="ohm",
                    stimulus="100mA 4-wire Kelvin DC",
                    measured=0.048,
                )
                TestStep(
                    step_id="TEST_UART_BLE_SPEED",
                    description="Measure BTLE high-speed 1Mb/s UART signal integrity on BLE_TX / BLE_RX",
                    test_type="voltage",
                    net_name="BLE_UART",
                    pad_a_mm=(-6.0, -22.0),
                    pad_b_mm=(-10.0, -22.0),
                    nominal=3.3,
                    tolerance_pct=3.0,
                    unit="V",
                    stimulus="1Mb/s PRBS UART serial transceiver test",
                    measured=3.3,
                )
                TestStep(
                    step_id="TEST_RAIL_3V3",
                    description="Verify regulated system 3.3V power distribution rail",
                    test_type="voltage",
                    net_name="3V3",
                    pad_a_mm=(-10.0, -26.0),
                    pad_b_mm=(-18.0, -22.0),
                    nominal=3.3,
                    tolerance_pct=3.0,
                    unit="V",
                    stimulus="DC power rail regulation probe",
                    measured=3.31,
                )
                TestStep(
                    step_id="TEST_RAIL_VBAT",
                    description="Verify battery input sensing rail continuity to charger",
                    test_type="voltage",
                    net_name="VBAT",
                    pad_a_mm=(-18.0, -26.0),
                    pad_b_mm=(-18.0, -22.0),
                    nominal=3.7,
                    tolerance_pct=5.0,
                    unit="V",
                    stimulus="Battery charge domain sensor",
                    measured=3.72,
                )
                TestStep(
                    step_id="TEST_IMP_USB_DIFF",
                    description="Measure USB 2.0 / USB-C differential impedance on DP/DM",
                    test_type="diff_pair",
                    net_name="USB_DP_DM",
                    pad_a_mm=(-25.0, 0.5),
                    pad_b_mm=(-25.0, -0.5),
                    nominal=90.0,
                    tolerance_pct=10.0,
                    unit="ohm",
                    stimulus="200ps TDR step differential pulse",
                    measured=89.8,
                )
                TestStep(
                    step_id="TEST_UART_BLE_FLOW_CTRL",
                    description="Verify BTLE hardware flow control handshake on BLE_RTS / BLE_CTS",
                    test_type="voltage",
                    net_name="BLE_FLOW_CTRL",
                    pad_a_mm=(-14.0, -22.0),
                    pad_b_mm=(-2.0, -22.0),
                    nominal=3.3,
                    tolerance_pct=3.0,
                    unit="V",
                    stimulus="Hardware RTS/CTS assert handshake probe",
                    measured=3.3,
                )
                TestStep(
                    step_id="TEST_I2C_PULLUPS",
                    description="Measure I2C SDA/SCL pull-up resistance to 3.3V rail",
                    test_type="resistance",
                    net_name="I2C_BUS",
                    pad_a_mm=(14.0, -4.0),
                    pad_b_mm=(18.0, -4.0),
                    nominal=4700.0,
                    tolerance_pct=5.0,
                    unit="ohm",
                    stimulus="1.0V DC precision Ohmmeter",
                    measured=4705.0,
                )

        return pcb

    def flex_tail(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildFlexPCB:
        """Build the flexible polyimide sensing tail extending from the carrier board edge."""
        w_tail = self.settings.flex_tail_width
        l_tail = self.settings.flex_tail_length
        t_tail = self.settings.flex_tail_thickness

        pts = [
            (-w_tail / 2.0, -l_tail / 2.0),
            (w_tail / 2.0, -l_tail / 2.0),
            (w_tail / 2.0, -l_tail / 2.0 + 7.0),
            (7.5, -l_tail / 2.0 + 9.0),
            (7.5, l_tail / 2.0 - 1.5),
            (5.0, l_tail / 2.0),
            (-5.0, l_tail / 2.0),
            (-7.5, l_tail / 2.0 - 1.5),
            (-7.5, -l_tail / 2.0 + 9.0),
            (-w_tail / 2.0, -l_tail / 2.0 + 7.0),
        ]

        cap_sensors = [
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_1",
                channel_id=0,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -13.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX0",
                rx_pin="CAP_RX0",
                threshold_raw=2200,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_2",
                channel_id=1,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -8.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX0",
                rx_pin="CAP_RX1",
                threshold_raw=2200,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_3",
                channel_id=2,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, -3.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX1",
                rx_pin="CAP_RX1",
                threshold_raw=2500,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_4",
                channel_id=3,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, 2.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX1",
                rx_pin="CAP_RX2",
                threshold_raw=2500,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="SLIDER_SEGMENT_5",
                channel_id=4,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(10.0, 4.5),
                pitch_mm=1.2,
                gap_mm=0.3,
                center_mm=(0.0, 7.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX2",
                rx_pin="CAP_RX2",
                threshold_raw=2800,
                shape_ref="flex_tail",
            ),
            CapacitiveElectrodeModel(
                name="ACTION_BUTTON",
                channel_id=5,
                electrode_type="mutual",
                shape="interdigital",
                area_mm=(8.0, 6.0),
                center_mm=(0.0, 18.0),
                drive_shield=False,
                hatch_ground_pour=True,
                hatch_line_width_mm=0.15,
                hatch_pitch_mm=0.5,
                tx_pin="CAP_TX2",
                rx_pin="CAP_RX2",
                threshold_raw=2000,
                shape_ref="flex_tail",
                pitch_mm=1.2,
                gap_mm=0.3,
            ),
            CapacitiveElectrodeModel(
                name="PROXIMITY_SENSOR",
                channel_id=6,
                electrode_type="self",
                shape="loop",
                area_mm=(14.2, 42.0),
                center_mm=(0.0, 3.5),
                drive_shield=False,
                hatch_ground_pour=False,
                rx_pin="CAP_RX3",
                threshold_raw=1500,
                shape_ref="flex_tail",
            ),
        ]

        tail_obstacles = [
            PCBObstacleModel(
                name="flex_vacuum_plate",
                shape="box",
                dimensions_mm=(30.0, 60.0, 4.0),
                position_mm=(0.0, 0.0, -2.0),
                description="Flex tail vacuum fixture support plate",
            ),
            PCBObstacleModel(
                name="J4",
                shape="box",
                dimensions_mm=(18.0, 5.0, 2.4),
                position_mm=(0.0, -22.75, 1.2),
                description="FPC-30P interface connector on flex tail",
            ),
        ]

        with BuildFlexPCB(
            name="flex_tail",
            flex_type=FlexType.CAPACITIVE,
            capacitive_sensors=cap_sensors,
            obstacles=tail_obstacles,
            outline_polygon=pts,
            coverlay_color="black",
        ) as tail:
            # Manifold hull enclosing connector and sensing channels with minimal wasted space
            with BuildSketch() as s:
                Polygon(*pts)
                r_corner = self.settings.flex_tail_corner_radius
                fillet(s.vertices(), radius=r_corner)
            extrude(s.sketch, amount=t_tail)

            with BuildSilkscreen() as silk:
                with Locations((0.0, -22.75)):
                    SilkscreenText(
                        "FLEX TAIL SENSOR REV 1.0", layer="B.SilkS", font_size=0.6, thickness=0.09, mirror=True
                    )
                with Locations((-7.5, -21.0)):
                    SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.5, thickness=0.08)

                # BUG-275: Fabrication notes and panelization specifications on Dwgs.User
                with Locations((0.0, -24.5)):
                    SilkscreenText(
                        "FAB: 2-LAYER POLYIMIDE FPC (0.20mm) | SMT ONLY: 0 DRILL HOLES / 0 VIAS",
                        layer="Dwgs.User",
                        font_size=0.5,
                        thickness=0.08,
                    )
                with Locations((0.0, -25.5)):
                    SilkscreenText(
                        "PANEL: 1*2 PANEL IN 64x64mm ACCEPTED WITH X-OUT BOARD ACCEPTED",
                        layer="Dwgs.User",
                        font_size=0.5,
                        thickness=0.08,
                    )

                # Inner Touch Sensing Region Outline (enclosing slider and action button without intersecting traces)
                SilkscreenLine((-6.85, -15.5), (-6.85, 21.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((6.85, -15.5), (6.85, 21.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((-6.85, 21.8), (6.85, 21.8), layer="F.SilkS", thickness=0.15)

                # 5-Button Slider Region Labels (BUG-147, BUG-155)
                with Locations((0.0, 11.5)):
                    SilkscreenText("SLIDER", layer="F.SilkS", font_size=0.8, thickness=0.12)
                for idx, dy in enumerate([-10.0, -5.0, 0.0, 5.0, 10.0], start=1):
                    with Locations((0.0, -3.0 + dy)):
                        SilkscreenText(f"S{idx}", layer="F.SilkS", font_size=0.55, thickness=0.08)

                # Action Button Region Label (centered) (BUG-147, BUG-157, BUG-158)
                with Locations((0.0, 18.0)):
                    SilkscreenText("ACTION", layer="F.SilkS", font_size=0.6, thickness=0.09)

                # Perimeter Proximity Sensor Loop Outline & Annotation (BUG-158, open at bottom)
                SilkscreenLine((-7.35, -16.5), (-7.35, 24.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((7.35, -16.5), (7.35, 24.8), layer="F.SilkS", thickness=0.15)
                SilkscreenLine((-7.35, 24.8), (7.35, 24.8), layer="F.SilkS", thickness=0.15)
                with Locations((0.0, 23.2)):
                    SilkscreenText("PROX LOOP", layer="F.SilkS", font_size=0.6, thickness=0.09)

            # Manual traces and sensor routing on flexible polyimide substrate
            with BuildTraces() as bt:
                bt.add(get_flex_tail_traces())

            with AssemblyTestMetadata(
                test_fixture="flying_probe", pass_criteria="all_steps_within_tolerance", subassembly="flex_tail"
            ) as tests:
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN0",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 0",
                    test_type="capacitance",
                    net_name="CAP_CHAN0",
                    pad_a_mm=(0.0, -6.25),
                    pad_b_mm=(-3.0, -6.25),
                    nominal=12.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=12.6,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN1",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 1",
                    test_type="capacitance",
                    net_name="CAP_CHAN1",
                    pad_a_mm=(0.0, 5.25),
                    pad_b_mm=(-3.0, 5.25),
                    nominal=14.0,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=14.1,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN2",
                    description="Measure baseline mutual capacitance on liquid level electrode Channel 2",
                    test_type="capacitance",
                    net_name="CAP_CHAN2",
                    pad_a_mm=(0.0, 16.75),
                    pad_b_mm=(-3.0, 16.75),
                    nominal=15.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave",
                    measured=15.4,
                )
                TestStep(
                    step_id="TEST_CAP_SENSE_CHAN3",
                    description="Measure baseline self capacitance on liquid proximity electrode Channel 3",
                    test_type="capacitance",
                    net_name="CAP_CHAN3",
                    pad_a_mm=(0.0, 24.75),
                    pad_b_mm=(0.0, -22.75),
                    nominal=8.0,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="250kHz 1.8V square wave self-cap",
                    measured=8.1,
                )
                TestStep(
                    step_id="TEST_CONTINUITY_TAIL_GND",
                    description="Verify ground plane guard ring continuity along flex tail contour",
                    test_type="continuity",
                    net_name="FLEX_GND",
                    pad_a_mm=(-7.0, -20.0),
                    pad_b_mm=(7.0, -20.0),
                    nominal=0.08,
                    tolerance_pct=20.0,
                    unit="ohm",
                    stimulus="100mA 4-wire Kelvin DC",
                    measured=0.078,
                )
                TestStep(
                    step_id="TEST_CAP_MUTUAL_TOUCH_CHAN0",
                    description="Simulate human finger touch proximity on liquid level Channel 0 mutual capacitance electrode",
                    test_type="mutual_cap",
                    net_name="CAP_CHAN0",
                    pad_a_mm=(0.0, -6.25),
                    pad_b_mm=(-3.0, -6.25),
                    nominal=15.8,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                    measured=15.9,
                )
                TestStep(
                    step_id="TEST_CAP_MUTUAL_TOUCH_CHAN1",
                    description="Simulate human finger touch proximity on liquid level Channel 1 mutual capacitance electrode",
                    test_type="mutual_cap",
                    net_name="CAP_CHAN1",
                    pad_a_mm=(0.0, 5.25),
                    pad_b_mm=(-3.0, 5.25),
                    nominal=17.5,
                    tolerance_pct=15.0,
                    unit="pF",
                    stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                    measured=17.6,
                )

        return tail

    def view_carrier_board(self, room: Room, mode: Mode) -> None:
        """Assemble rigid carrier PCB with component obstacles and test points for inspection and simulation."""
        carrier = self.carrier_board("carrier_board", None, mode)
        room.add("carrier_board", carrier.part, color=self.CARRIER_BOARD_COLOR, alpha=1.0)

    def view_flex_tail(self, room: Room, mode: Mode) -> None:
        """Assemble flex tail PCB with sensor pads and test points for inspection and simulation."""
        tail = self.flex_tail("flex_tail", None, mode)
        room.add("flex_tail", tail.part, color=self.FLEX_TAIL_COVERLAY_COLOR, alpha=0.9)

    def copper_regions(self) -> BuildCopperRegions:
        """Define inner layer ground planes on In1.Cu and In4.Cu using BuildCopperRegions."""
        w = self.settings.board_width
        length = self.settings.board_length
        # 1.0mm pullback from board edge
        w_half = (w / 2.0) - 1.0
        l_half = (length / 2.0) - 1.0
        polygon = [
            (-w_half, -l_half),
            (w_half, -l_half),
            (w_half, l_half),
            (-w_half, l_half),
        ]

        with BuildCopperRegions() as cr:
            CopperRegion(
                net="GND",
                layer="In1.Cu",
                outline=polygon,
                priority=1,
                clearance_mm=0.25,
            )
            # BUG-OPEN-003: Inner copper balance plane on In2.Cu to prevent warpage and delamination
            CopperRegion(
                net="GND",
                layer="In2.Cu",
                outline=polygon,
                priority=1,
                clearance_mm=0.25,
            )
            CopperRegion(
                net="3V3",
                layer="In3.Cu",
                outline=polygon,
                priority=1,
                clearance_mm=0.25,
            )
            CopperRegion(
                net="GND",
                layer="In4.Cu",
                outline=polygon,
                priority=1,
                clearance_mm=0.25,
            )
        return cr

    def test_points(self) -> BuildTestPoints:
        """Define drilled through-hole test points for GND, I2C, PCIe, and MIPI using BuildTestPoints."""
        with BuildTestPoints(default_layer="F.Cu", default_diameter_mm=1.40, default_drill_diameter_mm=0.80) as tp:
            # GND through-hole probe test point
            TestPoint("TP1", net="GND", at=(-18.0, -22.0))

            # Power test points (BUG-087)
            TestPoint("TP2", net="VBAT", at=(-18.0, -26.0))
            TestPoint("TP3", net="VBUS", at=(-14.0, -26.0))
            TestPoint("TP4", net="3V3", at=(-10.0, -26.0))

            # High-speed BTLE UART test points (spaced with 4mm pitch)
            TestPoint("TP5", net="BLE_RTS", at=(-14.0, -22.0))
            TestPoint("TP6", net="BLE_RX", at=(-10.0, -22.0))
            TestPoint("TP7", net="BLE_TX", at=(-6.0, -22.0))
            TestPoint("TP8", net="BLE_CTS", at=(-2.0, -22.0))

            # I2C test points (through-hole, accessible from both sides, routed on B.Cu)
            TestPoint("TP9", net="I2C_SDA", at=(14.0, -4.0), layer="B.Cu")
            TestPoint("TP10", net="I2C_SCL", at=(18.0, -4.0), layer="B.Cu")

            # Reserved test points (spaced with 4mm pitch on left half of board) (BUG-146)
            TestPoint("TP11", net="RESERVED", at=(-14.0, 22.0))
            TestPoint("TP12", net="RESERVED", at=(-10.0, 22.0))
            TestPoint("TP13", net="RESERVED", at=(-6.0, 22.0))
            TestPoint("TP14", net="RESERVED", at=(-2.0, 22.0))
        return tp

    @cached_property
    def _routed_network(self) -> tuple[list[TraceSegmentModel], list[ViaModel]]:
        """Compute complete routed traces and vias directly from settings routing_path."""
        from provider.pcb.router import PCBAutoRouter

        routing_file = self.settings.routing_path
        if routing_file and Path(routing_file).exists():
            return PCBAutoRouter.load_routing_yaml(routing_file)

        return [], []

    def traces(self) -> list[TraceSegmentModel]:
        """Return routed copper traces for the test board."""
        return self._routed_network[0]

    def vias(self) -> list[ViaModel]:
        """Return interlayer vias for the test board."""
        return self._routed_network[1]

    def silkscreen_graphics(self) -> list[SilkscreenGraphicModel]:
        """Return silkscreen graphic primitives (frames, lines, polygons) for the test board carrier."""
        with BuildSilkscreen() as silk:
            # Top Antigravity brand logo emblem in empty space between J2 and carrier title (BUG-092)
            # Unique graphic emblem within a square frame (not text)
            SilkscreenRect(position=(0.0, 31.0), dimensions=(7.0, 7.0), thickness=0.20, layer="F.SilkS")
            SilkscreenPolygon(
                polygon_points=[
                    (0.0, 33.2),
                    (1.6, 30.5),
                    (0.5, 30.5),
                    (0.5, 28.8),
                    (-0.5, 28.8),
                    (-0.5, 30.5),
                    (-1.6, 30.5),
                ],
                thickness=0.18,
                layer="F.SilkS",
                fill=True,
            )
            SilkscreenLine(start_mm=(-2.4, 32.2), end_mm=(-1.4, 30.8), thickness=0.18, layer="F.SilkS")
            SilkscreenLine(start_mm=(-2.4, 29.8), end_mm=(-1.4, 31.2), thickness=0.18, layer="F.SilkS")
            SilkscreenLine(start_mm=(2.4, 32.2), end_mm=(1.4, 30.8), thickness=0.18, layer="F.SilkS")
            SilkscreenLine(start_mm=(2.4, 29.8), end_mm=(1.4, 31.2), thickness=0.18, layer="F.SilkS")
        return silk.graphics

    def silkscreen(self) -> list[SilkscreenTextModel]:
        """Return silkscreen markings for the test board carrier."""
        with BuildSilkscreen() as silk:
            # Position silkscreen markings cleanly clear of connector J2 (Y=38) and connector J1 (Y=-36)
            with Locations((0.0, 26.0)):
                SilkscreenText("TEST BOARD CARRIER REV 2.0", layer="F.SilkS", font_size=1.2, thickness=0.18)
            with Locations((0.0, 0.0)):
                SilkscreenText(
                    "BOTTOM SHIELD / GROUND REF", layer="B.SilkS", font_size=1.0, thickness=0.15, mirror=True
                )

            # BUG-272, BUG-OPEN-003: Fabrication notes and controlled impedance specification table on Dwgs.User
            with Locations((0.0, 42.0)):
                SilkscreenText(
                    "FAB NOTES: 6-LAYER TG150 ENIG | SOLDERMASK: MATTE BLACK | SILK: WHITE",
                    layer="Dwgs.User",
                    font_size=0.7,
                    thickness=0.1,
                )
            with Locations((0.0, 40.5)):
                SilkscreenText(
                    "IMPEDANCE: 50 OHM SE (L1 W=0.12mm REF L2) | 90 OHM DIFF (L1 W=0.12 S=0.12 REF L2)",
                    layer="Dwgs.User",
                    font_size=0.55,
                    thickness=0.08,
                )
            with Locations((0.0, -43.5)):
                SilkscreenText(
                    "VIA PROCESS: RESIN FILL & CAP (VIPPO / IPC-4761 TYPE VII) FOR BGA & SMD PADS",
                    layer="Dwgs.User",
                    font_size=0.55,
                    thickness=0.08,
                )

            # BUG-183, BUG-209, BUG-219, BUG-231: Silkscreen labels for Status and Overrides
            with Locations((10.5, -13.5)):
                SilkscreenText("OVERRIDES", layer="F.SilkS", font_size=0.75, thickness=0.11)
            with Locations((4.5, -12.5)):
                SilkscreenText("STATUS", layer="F.SilkS", font_size=0.75, thickness=0.11)
            # Reset button label close to U1 central (0, 0) and SW1 (0, -11) (BUG-219)
            with Locations((0.0, -9.2)):
                SilkscreenText("RESET", layer="F.SilkS", font_size=0.6, thickness=0.09)
            # Jumper labels placed to the right of each horizontal jumper at X=14.0 (BUG-219)
            with Locations((14.0, -15.5)):
                SilkscreenText("NRST", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((14.0, -18.0)):
                SilkscreenText("BOOT0", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((14.0, -21.0)):
                SilkscreenText("ISP", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((14.0, -23.6)):
                SilkscreenText("VBUS", layer="F.SilkS", font_size=0.55, thickness=0.08)
            # Status LED labels
            with Locations((1.6, -14.0)):
                SilkscreenText("MCU", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((1.6, -16.0)):
                SilkscreenText("PERIPH", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((1.6, -18.0)):
                SilkscreenText("AUD", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((1.6, -20.0)):
                SilkscreenText("3V3", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((1.6, -22.0)):
                SilkscreenText("VBUS", layer="F.SilkS", font_size=0.55, thickness=0.08)
            with Locations((1.6, -24.8)):
                SilkscreenText("VBAT", layer="F.SilkS", font_size=0.55, thickness=0.08)

            # Global optical fiducials (crosshairs)
            with Locations((-24.0, 38.0), (21.0, -42.0), (-24.0, -38.0)):
                SilkscreenText("+", layer="F.SilkS", font_size=1.5, thickness=0.25)
            with Locations((-24.0, 38.0), (21.0, -42.0), (-24.0, -38.0)):
                SilkscreenText("+", layer="B.SilkS", font_size=1.5, thickness=0.25, mirror=True)

            # Alignment markers for ICs and connectors
            # U1 BGA pin-1 indicator
            with Locations((-7.0, 7.0)):
                SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            # U2 QFN pin-1 indicator
            with Locations((15.0, -6.5)):
                SilkscreenText("• Pin 1", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            # U11 BTLE module alignment markers and antenna keepout outline (BUG-214)
            with Locations((-5.0, -41.0), (5.0, -41.0)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((0.0, -41.5)):
                SilkscreenText("BLE ANT", layer="F.SilkS", font_size=0.7, thickness=0.10)
            # J2 FPC connector alignment markers
            with Locations((-10.0, 39.5), (10.0, 39.5)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)

            # Battery polarity markings
            with Locations((-24.0, 13.5)):
                SilkscreenText("+", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-22.0, 13.5)):
                SilkscreenText("-", layer="F.SilkS", font_size=0.8, thickness=0.12)

            # Component Reference Designators (BUG-066)
            # Active ICs and Primary Modules
            with Locations((0.0, 8.5)):
                SilkscreenText("U1", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((18.0, -11.5)):
                SilkscreenText("U2", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            with Locations((0.0, -27.2)):
                SilkscreenText("U11", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((-14.5, -39.0)):
                SilkscreenText("J15", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-14.5, -43.0)):
                SilkscreenText("BLE SWD", layer="F.SilkS", font_size=0.6, thickness=0.09)
            with Locations((0.0, 35.5)):
                SilkscreenText("J2", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((-17.5, 0.0)):
                SilkscreenText("J3", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((-23.0, 19.5)):
                SilkscreenText("J13", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-19.0, 12.5)):
                SilkscreenText("U3", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-18.0, 24.5)):
                SilkscreenText("U4", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-18.0, 38.0)):
                SilkscreenText("SPK1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-9.0, 3.5)):
                SilkscreenText("Y1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((14.0, 18.0)):
                SilkscreenText("U6", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-16.0, 19.0)):
                SilkscreenText("U7", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((15.0, 7.5)):
                SilkscreenText("U8", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-20.0, -37.5)):
                SilkscreenText("U9", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((18.0, 26.5)):
                SilkscreenText("U10", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((19.5, 10.0)):
                SilkscreenText("D1", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-18.0, -18.5)):
                SilkscreenText("J5", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((20.5, 32.0)):
                SilkscreenText("J6", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((20.5, 17.0)):
                SilkscreenText("J7", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((20.5, 2.0)):
                SilkscreenText("J8", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((20.5, -14.0)):
                SilkscreenText("J9", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((20.5, -31.0)):
                SilkscreenText("J10", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((19.0, -14.5)):
                SilkscreenText("J14", layer="F.SilkS", font_size=0.8, thickness=0.12)

            # Resistors
            with Locations((14.5, -6.0)):
                SilkscreenText("R1", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((10.0, -4.5)):
                SilkscreenText("R2", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-14.5, -4.5)):
                SilkscreenText("R3", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-14.5, 4.5)):
                SilkscreenText("R4", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-5.5, 8.0)):
                SilkscreenText("R5", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-11.5, -12.0)):
                SilkscreenText("R6", layer="F.SilkS", font_size=0.7, thickness=0.10)

            # Capacitors
            with Locations((14.5, -15.0)):
                SilkscreenText("C1", layer="F.SilkS", font_size=0.6, thickness=0.09)
            with Locations((-8.0, -6.5)):
                SilkscreenText("C2", layer="B.SilkS", font_size=0.7, thickness=0.10, mirror=True)
            with Locations((-13.0, -5.5)):
                SilkscreenText("C3", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((8.0, 10.5)):
                SilkscreenText("C4", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-6.0, -11.5)):
                SilkscreenText("C5", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-24.0, 12.5)):
                SilkscreenText("C6", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-14.0, 12.5)):
                SilkscreenText("C7", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-23.0, 23.5)):
                SilkscreenText("C8", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-5.0, 16.5)):
                SilkscreenText("C9", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((5.0, 16.5)):
                SilkscreenText("C10", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-10.5, 10.5)):
                SilkscreenText("C11", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((14.0, -6.5)):
                SilkscreenText("C12", layer="B.SilkS", font_size=0.7, thickness=0.10, mirror=True)
            with Locations((-20.0, 15.5)):
                SilkscreenText("C13", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((14.0, -12.0)):
                SilkscreenText("C14", layer="B.SilkS", font_size=0.7, thickness=0.10, mirror=True)
        return silk.texts


def build_carrier_board_wiring(parent_part: Optional[Any] = None) -> Wiring:
    """Construct complete in-memory Wiring model for Carrier Board using BuildComponents and BuildWiring."""
    all_components = []
    symbol_table = {}

    with BuildPcb(name="carrier_board", board_type=BoardType.RIGID) as pcb_ctx:
        with BuildComponents(
            name="carrier_board", subassembly="carrier_board", parent_part=parent_part
        ) as carrier_comps:
            mcu = Component(
                name="U1",
                package="VFBGA-184",
                position=(0.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MCXN947VDFT",
                supplier_pn="568-MCXN947VDFT-ND",
                pins=[{"name": "J8", "pin_name": "VSS", "label": "VSS"}],
            )
            u2 = Component(
                name="U2",
                package="QFN-20",
                position=(18.0, -9.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="IQS7222C101QNR",
                supplier_pn="1790-IQS7222C101QNRCT-ND",
                layer="B.Cu",
            )
            u11 = Component(
                name="U11",
                package="MOD-BLE-PCB-ANT",
                position=(0.0, -36.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="NINA-B312-02B",
                supplier_pn="1972-NINA-B312-02B-ND",
            )
            j15 = Component(
                name="J15",
                package="pin_header_2x5_1.27mm",
                position=(-14.5, -41.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="DNP",
                supplier_pn="N/A",
                dnp=True,
            )
            sw2 = Component(
                name="SW2",
                package="SW_PUSH_SMD",
                position=(-14.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
            )
            j2 = Component(
                name="J2",
                package="FPC-30P-0.5MM",
                position=(0.0, 38.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FH12-30S-0.5SH(55)",
                supplier_pn="HFJ130CT-ND",
                shape_ref="carrier_board",
            )
            j4 = Component(
                name="J4",
                package="FPC-30P-0.5MM",
                position=(0.0, -22.75, 0.0),
                rotation=(0.0, 0.0, 0.0),
                mpn="N/A - FPC Mating Tab (Male plug for J2)",
                supplier_pn="N/A",
                value="Male Plug for J2",
                dnp=True,
                shape_ref="flex_tail",
            )
            j13 = Component(
                name="J13",
                package="JST-PH-2P",
                position=(-23.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="S2B-PH-K-S",
                supplier_pn="455-1165-ND",
            )
            # Autoincrementing Capacitors C1, C2, C3
            c1 = Component(
                "C",
                package="0402",
                position=(13.5, -14.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            c2 = Component(
                "C",
                package="0402",
                position=(-8.0, -4.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                layer="B.Cu",
                value="0.1uF",
            )
            c3 = Component(
                "C",
                package="0603",
                position=(-13.0, -8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1004-1-ND",
                value="10uF",
            )
            mcu_caps = [c1, c2, c3]

            # Autoincrementing Resistors R1..R6
            r1 = Component(
                "R",
                package="0402",
                position=(12.0, -6.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-074K7L",
                supplier_pn="311-4.7KLRCT-ND",
                layer="B.Cu",
                value="4.7k",
            )
            r2 = Component(
                "R",
                package="0402",
                position=(12.0, -4.5, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-074K7L",
                supplier_pn="311-4.7KLRCT-ND",
                layer="B.Cu",
                value="4.7k",
            )
            r3 = Component(
                "R",
                package="0402",
                position=(-17.0, -4.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-075K1L",
                supplier_pn="311-5.1KLRCT-ND",
                value="5.1k",
            )
            r4 = Component(
                "R",
                package="0402",
                position=(-17.0, 4.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-075K1L",
                supplier_pn="311-5.1KLRCT-ND",
                value="5.1k",
            )
            r5 = Component(
                "R",
                package="0402",
                position=(-8.0, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-0710KL",
                supplier_pn="311-10.0KLRCT-ND",
                value="10k",
            )
            r6 = Component(
                "R",
                package="0402",
                position=(-9.0, -12.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-0710KL",
                supplier_pn="311-10.0KLRCT-ND",
                value="10k",
            )

            # Autoincrementing Capacitors C4..C17
            c4 = Component(
                "C",
                package="0402",
                position=(8.0, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            c5 = Component(
                "C",
                package="0402",
                position=(-6.0, -9.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            c6 = Component(
                "C",
                package="0603",
                position=(-24.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
            )
            c7 = Component(
                "C",
                package="0603",
                position=(-14.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
            )
            c8 = Component(
                "C",
                package="0603",
                position=(-23.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A105KP8NNNC",
                supplier_pn="1276-1002-1-ND",
                value="1uF",
            )
            c9 = Component(
                "C",
                package="0402",
                position=(-12.0, 2.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402JRNPO9BN120",
                supplier_pn="311-1032-1-ND",
                value="12pF",
            )
            c10 = Component(
                "C",
                package="0402",
                position=(-12.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402JRNPO9BN120",
                supplier_pn="311-1032-1-ND",
                value="12pF",
            )
            c11 = Component(
                "C",
                package="0402",
                position=(-10.5, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
            )
            c12 = Component(
                "C",
                package="0402",
                position=(14.0, -8.0, -0.8),
                rotation=(0.0, 0.0, 180.0),
                mpn="CC0402KRX5R6BB225",
                supplier_pn="311-1440-1-ND",
                layer="B.Cu",
                value="2.2uF",
            )
            c13 = Component(
                "C",
                package="0603",
                position=(-20.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1004-1-ND",
                value="10uF",
            )
            c14 = Component(
                "C",
                package="0402",
                position=(14.0, -10.0, -0.8),
                rotation=(0.0, 0.0, 180.0),
                mpn="CC0402KRX5R6BB225",
                supplier_pn="311-1440-1-ND",
                layer="B.Cu",
                value="2.2uF",
            )
            c15 = Component(
                "C",
                package="0603",
                position=(13.0, 29.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="GRM188R61A106KE69D",
                supplier_pn="490-10uF-0603-ND",
                layer="B.Cu",
                value="10uF",
            )
            c16 = Component(
                "C",
                package="0603",
                position=(16.0, 29.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="GRM188R61A106KE69D",
                supplier_pn="490-10uF-0603-ND",
                layer="B.Cu",
                value="10uF",
            )
            c17 = Component(
                "C",
                package="0402",
                position=(13.0, 32.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                layer="B.Cu",
                value="0.1uF",
            )

            Component(
                name="J3",
                package="USB-C-16P",
                position=(-25.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="TYPE-C-16P-3MD",
                supplier_pn="6652-TYPE-C-16P-3MDTR-ND",
            )
            Component(
                name="U3",
                package="SOT-23-5",
                position=(-19.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="AP2112K-3.3TRG1",
                supplier_pn="AP2112K-3.3-ND",
            )
            Component(
                name="U4",
                package="QFN-16-AMP",
                position=(-18.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX98357AETE+",
                supplier_pn="MAX98357A-ND",
            )
            Component(
                name="U5",
                package="piezo_speaker_12mm",
                position=(-18.0, 31.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CPT-1207-5LTH-T",
                supplier_pn="2223-CPT-1207-5LTH-T-ND",
            )
            Component(
                name="Y1",
                package="XTAL-3225-4P",
                position=(-9.0, 1.25, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="ECS-240-8-30B-CKM",
                supplier_pn="XC1842CT-ND",
            )
            Component(
                name="D8",
                package="SOD-123",
                position=(16.0, 32.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="SMF05CT1G",
                supplier_pn="ONSEMI-SMF05C-ND",
                layer="B.Cu",
                value="TVS_3V3",
            )
            Component(
                name="J5",
                package="pin_header_2x5_1.27mm",
                position=(-18.0, -15.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="FTSH-105-01-L-DV-K",
                supplier_pn="SAMTEC-FTSH105-ND",
            )
            Component(
                name="J6",
                package="JST-PH-6P",
                position=(24.5, 32.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J7",
                package="JST-PH-6P",
                position=(24.5, 17.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J8",
                package="JST-PH-6P",
                position=(24.5, 2.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
            )
            Component(
                name="J9",
                package="JST-PH-7P",
                position=(24.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {
                        "number": "1",
                        "name": "1",
                        "pin_name": "SPI0_CS_N",
                        "label": "SPI0_CS_N",
                        "signal_name": "SPI0_CS_N",
                    },
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "SPI0_MISO",
                        "label": "SPI0_MISO",
                        "signal_name": "SPI0_MISO",
                    },
                    {
                        "number": "3",
                        "name": "3",
                        "pin_name": "SPI0_MOSI",
                        "label": "SPI0_MOSI",
                        "signal_name": "SPI0_MOSI",
                    },
                    {
                        "number": "4",
                        "name": "4",
                        "pin_name": "SPI0_SCK",
                        "label": "SPI0_SCK",
                        "signal_name": "SPI0_SCK",
                    },
                    {
                        "number": "5",
                        "name": "5",
                        "pin_name": "EXP_INT_SPI",
                        "label": "EXP_INT_SPI",
                        "signal_name": "EXP_INT_SPI",
                    },
                    {
                        "number": "6",
                        "name": "6",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "7", "name": "7", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                ],
            )
            Component(
                name="J10",
                package="JST-PH-7P",
                position=(24.5, -31.0, 0.8),
                rotation=(0.0, 0.0, -90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {
                        "number": "2",
                        "name": "2",
                        "pin_name": "PERIPH_3V3",
                        "label": "PERIPH_3V3",
                        "signal_name": "PERIPH_3V3",
                    },
                    {"number": "3", "name": "3", "pin_name": "DTR_N", "label": "DTR_N", "signal_name": "DTR_N"},
                    {"number": "4", "name": "4", "pin_name": "CBUS2", "label": "CBUS2", "signal_name": "CBUS2"},
                    {"number": "5", "name": "5", "pin_name": "CBUS4", "label": "CBUS4", "signal_name": "CBUS4"},
                    {"number": "6", "name": "6", "pin_name": "DCD_N", "label": "DCD_N", "signal_name": "DCD_N"},
                    {"number": "7", "name": "7", "pin_name": "DSR_N", "label": "DSR_N", "signal_name": "DSR_N"},
                ],
            )
            Component(
                name="J14",
                package="pin_header_1x10",
                position=(19.0, -28.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="TSW-110-07-L-S",
                supplier_pn="SAM1034-10-ND",
                pins=[
                    {"number": "1", "name": "1", "pin_name": "GPIO0", "label": "GPIO0", "signal_name": "GPIO0"},
                    {"number": "2", "name": "2", "pin_name": "GPIO1", "label": "GPIO1", "signal_name": "GPIO1"},
                    {"number": "3", "name": "3", "pin_name": "GPIO2", "label": "GPIO2", "signal_name": "GPIO2"},
                    {"number": "4", "name": "4", "pin_name": "GPIO3", "label": "GPIO3", "signal_name": "GPIO3"},
                    {"number": "5", "name": "5", "pin_name": "3V3", "label": "3V3", "signal_name": "3V3"},
                    {"number": "6", "name": "6", "pin_name": "GND", "label": "GND", "signal_name": "GND"},
                    {"number": "7", "name": "7", "pin_name": "CBUS7", "label": "CBUS7", "signal_name": "CBUS7"},
                    {"number": "8", "name": "8", "pin_name": "CBUS5", "label": "CBUS5", "signal_name": "CBUS5"},
                    {"number": "9", "name": "9", "pin_name": "CBUS6", "label": "CBUS6", "signal_name": "CBUS6"},
                    {"number": "10", "name": "10", "pin_name": "CBUS3", "label": "CBUS3", "signal_name": "CBUS3"},
                ],
            )
            Component(
                name="U8",
                package="WSON-8",
                position=(15.0, 4.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="W25N01GVZEIG",
                supplier_pn="W25N01GVZEIG-ND",
            )
            Component(
                name="U6",
                package="TSSOP-16",
                position=(14.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LP5009PWR",
                supplier_pn="296-LP5009PWR-ND",
            )
            Component(
                name="D1",
                package="LED_RGB_4P",
                position=(17.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CLV1A-FKB-CK1VW1DE1BB7C3C3",
                supplier_pn="CLV1A-FKB-CK1VW1DE1BB7C3C3CT-ND",
            )
            Component(
                name="U7",
                package="TDFN-8",
                position=(-16.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX17048G+T10",
                supplier_pn="MAX17048G+T10-ND",
            )
            Component(
                name="U9",
                package="QFN-32",
                position=(-20.0, -32.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FT232RNQ-REEL",
                supplier_pn="768-FT232RNQ-REEL-ND",
            )
            Component(
                name="U10",
                package="SOT-23-5",
                position=(18.0, 24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TLV62568DBVR",
                supplier_pn="296-TLV62568DBVR-ND",
            )
            Component(
                name="SW1",
                package="SW_PUSH_SMD",
                position=(0.0, -11.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
                omit_silkscreen=True,
            )

        with BuildComponents(
            name="status_and_overrides", subassembly="status_and_overrides", parent_part=parent_part
        ) as status_comps:
            Component(
                name="JP1",
                package="pin_header_1x2",
                position=(10.5, -15.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
                omit_silkscreen=True,
            )
            Component(
                name="JP2",
                package="pin_header_1x2",
                position=(10.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
                omit_silkscreen=True,
            )
            Component(
                name="JP3",
                package="pin_header_1x2",
                position=(10.5, -21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
                omit_silkscreen=True,
            )
            Component(
                name="JP4",
                package="pin_header_1x2",
                position=(10.5, -23.6, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TSW-102-07-L-S",
                supplier_pn="SAM1026-02-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D2",
                package="0603",
                position=(4.0, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D3",
                package="0603",
                position=(4.0, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D4",
                package="0603",
                position=(4.0, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D5",
                package="0603",
                position=(4.0, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D6",
                package="0603",
                position=(4.0, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                name="D7",
                package="0603",
                position=(4.0, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LTST-C190GKT",
                supplier_pn="160-1447-1-ND",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -22.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -20.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -18.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "R",
                package="0402",
                position=(6.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="RC0402FR-071KL",
                supplier_pn="311-1.00KLRCT-ND",
                value="1k",
                omit_silkscreen=True,
            )
            Component(
                "C",
                package="0402",
                position=(7.0, -35.2, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )
            Component(
                "C",
                package="0402",
                position=(7.0, -37.3, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="GRM1555C1H301JA01D",
                supplier_pn="490-GRM1555C1H301JA01D-ND",
                value="300pF",
            )

        with BuildComponents(name="rf_interfaces", subassembly="rf_interfaces", parent_part=parent_part) as rf_comps:
            Component(
                name="J16",
                package="pin_header_1x2",
                position=(13.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="22-28-4023",
                supplier_pn="WM6402-ND",
            )

        with BuildWiring(name="power_nets") as pwr_nets:
            Net(
                name="GND",
                pins=[
                    mcu.pin("VSS"),
                    u2.named_pin.VSS,
                    mcu_caps[0].pin(2),
                    mcu_caps[1].pin(2),
                    mcu_caps[2].pin(2),
                    ["U11", "GND"],
                    ["J2", "GND"],
                    ["J2", "MP1"],
                    ["J2", "MP2"],
                    ["C15", "2"],
                    ["C16", "2"],
                    ["C17", "2"],
                    ["D8", "2"],
                    ["C18", "2"],
                    ["C19", "2"],
                    ["J15", "3"],
                    ["J15", "5"],
                    ["J3", "GND"],
                    ["J3", "GND2"],
                    ["J3", "SHIELD1"],
                    ["J3", "SHIELD2"],
                    ["J3", "SHIELD3"],
                    ["J3", "SHIELD4"],
                    ["R3", "2"],
                    ["R4", "2"],
                    ["U3", "2"],
                    ["C6", "2"],
                    ["C7", "2"],
                    ["Y1", "2"],
                    ["Y1", "4"],
                    ["C9", "2"],
                    ["C10", "2"],
                    ["C11", "2"],
                    ["R6", "2"],
                    ["C4", "2"],
                    ["C5", "2"],
                    ["C12", "2"],
                    ["C14", "2"],
                    ["U2", "EP"],
                    ["J13", "2"],
                    ["C13", "2"],
                    ["U8", "4"],
                    ["U8", "EP"],
                    ["U7", "1"],
                    ["U7", "4"],
                    ["U7", "6"],
                    ["U7", "EP"],
                    ["U6", "3"],
                    ["U6", "4"],
                    ["U6", "9"],
                    ["U6", "10"],
                    ["U6", "11"],
                    ["U6", "12"],
                    ["U6", "13"],
                    ["U6", "14"],
                    ["U6", "15"],
                    ["U9", "7"],
                    ["U9", "18"],
                    ["U9", "21"],
                    ["U9", "25"],
                    ["U9", "26"],
                    ["U9", "29"],
                    ["U9", "EP"],
                    ["J5", "3"],
                    ["J5", "5"],
                    ["J5", "7"],
                    ["J5", "8"],
                    ["J5", "9"],
                    ["U10", "2", "GND"],
                    ["U4", "GND", "GND"],
                    ["U4", "GAIN", "GAIN"],
                    ["C8", "2"],
                    ["J6", "5"],
                    ["J6", "6"],
                    ["J7", "5"],
                    ["J7", "6"],
                    ["J8", "5"],
                    ["J8", "6"],
                    ["J9", "7", "GND"],
                    ["J10", "1", "GND"],
                    ["J14", "6", "GND"],
                    ["SW1", "2"],
                    ["R7", "2"],
                    ["R8", "2"],
                    ["R9", "2"],
                    ["R10", "2"],
                    ["R11", "2"],
                    ["R12", "2"],
                    ["SW2", "2"],
                ],
                color="#475569",
            )
            Net(
                name="3V3",
                pins=[
                    ["U1", "H8"],
                    ["U2", "VDD"],
                    ["U2", "MCLR"],
                    ["U11", "3V3"],
                    ["U11", "VCC"],
                    ["J2", "3V3"],
                    ["R1", "1"],
                    ["R2", "1"],
                    ["C1", "1"],
                    ["C2", "1"],
                    ["C3", "1"],
                    ["C15", "1"],
                    ["C16", "1"],
                    ["C17", "1"],
                    ["D8", "1"],
                    ["U3", "5"],
                    ["C7", "1"],
                    ["U4", "VDD", "VDD"],
                    ["C8", "1"],
                    ["R5", "1"],
                    ["C4", "1"],
                    ["C5", "1"],
                    ["U8", "8"],
                    ["U7", "3"],
                    ["U6", "5"],
                    ["U6", "16"],
                    ["D1", "4"],
                    ["U9", "4"],
                    ["U9", "19"],
                    ["J5", "1"],
                    ["U10", "1", "VIN"],
                    ["J14", "5", "3V3"],
                    ["JP3", "1"],
                    ["D4", "1"],
                    ["D7", "1"],
                    ["J15", "1"],
                ],
                color="#dc2626",
            )
            Net(
                name="VBUS",
                pins=[["J3", "VBUS"], ["J3", "VBUS2"], ["U9", "20"], ["JP4", "1"], ["D3", "1"]],
                color="#b91c1c",
                priority=24,
            )
            Net(
                name="VBAT",
                pins=[["J13", "1"], ["C13", "1"], ["U3", "4"], ["U7", "2"], ["D2", "1"]],
                color="#f59e0b",
                priority=24,
            )
            Net(
                name="PERIPH_3V3",
                pins=[
                    ["U10", "5", "VOUT"],
                    ["J6", "1"],
                    ["J7", "1"],
                    ["J8", "1"],
                    ["J9", "6", "PERIPH_3V3"],
                    ["J10", "2", "PERIPH_3V3"],
                    ["D6", "1"],
                ],
                color="#dc2626",
                priority=25,
            )

        with BuildWiring(name="signal_nets") as sig_nets:
            Net(
                name="VBUS_CHG",
                pins=[["U3", "1"], ["U3", "3"], ["C6", "1"], ["JP4", "2"]],
                color="#b91c1c",
                priority=24,
            )
            Net(name="CC1", pins=[["J3", "CC1"], ["R3", "1"]], color="#0284c7", priority=53)
            Net(name="CC2", pins=[["J3", "CC2"], ["R4", "1"]], color="#0284c7", priority=54)
            Net(
                name="AUDIO_EN",
                pins=[["U1", "L4"], ["U4", "SD_MODE", "SD_MODE"], ["D5", "1"]],
                color="#ea580c",
                priority=16,
            )
            Net(name="PERIPH_EN", pins=[["U1", "L5"], ["U10", "3", "EN"]], color="#ea580c", priority=24)
            Net(name="EXP_INT_I2C", pins=[["U1", "B2"], ["J6", "2"]], color="#84cc16", priority=19)
            Net(name="EXP_INT_I3C", pins=[["U1", "B8"], ["J7", "2"]], color="#84cc16", priority=20)
            Net(name="EXP_INT_I3C1", pins=[["U1", "E4"], ["J8", "2"]], color="#84cc16", priority=21)
            Net(name="EXP_INT_SPI", pins=[["U1", "T8"], ["J9", "5", "EXP_INT_SPI"]], color="#84cc16", priority=22)
            Net(name="CAP_INT", pins=[["U1", "C4"], ["U2", "RDY"]], color="#84cc16", priority=18)
            Net(name="I2C_SCL", pins=[["U1", "C5"], ["U2", "SCL"], ["R2", "2"]], color="#22c55e", priority=19)
            Net(name="I2C_SDA", pins=[["U1", "C6"], ["U2", "SDA"], ["R1", "2"]], color="#16a34a", priority=20)
            Net(name="OSC_IN", pins=[["U1", "F2"], ["Y1", "1"], ["C9", "1"]], color="#059669", priority=1)
            Net(name="OSC_OUT", pins=[["U1", "F1"], ["Y1", "3"], ["C10", "1"]], color="#10b981", priority=2)
            Net(
                name="NRST",
                pins=[["U1", "F3"], ["R5", "2"], ["C11", "1"], ["JP1", "2"], ["SW1", "1"]],
                color="#eab308",
                priority=21,
            )
            Net(name="FTDI_NRST", pins=[["U9", "23"], ["JP1", "1"]], color="#eab308", priority=21)
            Net(name="BOOT0", pins=[["U1", "C14"], ["R6", "1"], ["JP2", "2"], ["JP3", "2"]], color="#ca8a04")
            Net(name="FTDI_BOOT0", pins=[["U9", "22"], ["JP2", "1"]], color="#ca8a04")
            Net(name="LED_VBAT_K", pins=[["D2", "2"], ["R7", "1"]], color="#f59e0b")
            Net(name="LED_VBUS_K", pins=[["D3", "2"], ["R8", "1"]], color="#b91c1c")
            Net(name="LED_3V3_K", pins=[["D4", "2"], ["R9", "1"]], color="#dc2626")
            Net(name="LED_AUD_K", pins=[["D5", "2"], ["R10", "1"]], color="#ea580c")
            Net(name="LED_PERIPH_K", pins=[["D6", "2"], ["R11", "1"]], color="#dc2626")
            Net(name="LED_MCU_K", pins=[["D7", "2"], ["R12", "1"]], color="#ea580c")
            Net(name="BLE_RX", pins=[["U1", "T2"], ["U11", "RXD"]], color="#2563eb", priority=9)
            Net(name="BLE_RTS", pins=[["U1", "T1"], ["U11", "RTS"]], color="#3b82f6", priority=10)
            Net(name="BLE_TX", pins=[["U1", "T3"], ["U11", "TXD"]], color="#059669", priority=11)
            Net(name="BLE_CTS", pins=[["U1", "T4"], ["U11", "CTS"]], color="#10b981", priority=12)
            Net(name="BLE_RESET_N", pins=[["U11", "RESET_N"], ["SW2", "1"]], color="#f97316", priority=13)
            Net(name="BLE_SWDCLK", pins=[["U11", "SWDCLK"], ["J15", "4"]], color="#4169e1", priority=13)
            Net(name="BLE_SWDIO", pins=[["U11", "SWDIO"], ["J15", "2"]], color="#1e90ff", priority=14)
            Net(name="NFC1", pins=[["U11", "NFC1"], ["C18", "1"], ["J16", "1"]], color="#8b5cf6", priority=15)
            Net(name="NFC2", pins=[["U11", "NFC2"], ["C19", "1"], ["J16", "2"]], color="#a855f7", priority=16)
            Net(
                name="CAP_SHIELD",
                pins=[["U2", "CR7"], ["J2", "CAP_SHIELD"], ["J4", "CAP_SHIELD"]],
                color="#64748b",
                priority=25,
            )
            Net(
                name="CAP_TX2", pins=[["U2", "CR6"], ["J2", "CAP_TX2"], ["J4", "CAP_TX2"]], color="#0ea5e9", priority=26
            )
            Net(
                name="CAP_TX1", pins=[["U2", "CR5"], ["J2", "CAP_TX1"], ["J4", "CAP_TX1"]], color="#0284c7", priority=27
            )
            Net(
                name="CAP_TX0", pins=[["U2", "CR4"], ["J2", "CAP_TX0"], ["J4", "CAP_TX0"]], color="#06b6d4", priority=28
            )
            Net(
                name="CAP_RX3", pins=[["U2", "CR3"], ["J2", "CAP_RX3"], ["J4", "CAP_RX3"]], color="#67e8f9", priority=29
            )
            Net(
                name="CAP_RX2", pins=[["U2", "CR2"], ["J2", "CAP_RX2"], ["J4", "CAP_RX2"]], color="#38bdf8", priority=30
            )
            Net(
                name="CAP_RX1", pins=[["U2", "CR1"], ["J2", "CAP_RX1"], ["J4", "CAP_RX1"]], color="#0369a1", priority=31
            )
            Net(
                name="CAP_RX0", pins=[["U2", "CR0"], ["J2", "CAP_RX0"], ["J4", "CAP_RX0"]], color="#0891b2", priority=32
            )
            Net(name="CAP_CT8", pins=[["U2", "CT8"], ["J2", "NC3"]], color="#0284c7", priority=33)
            Net(name="PDM_CLK", pins=[["U1", "G2"], ["U4", "BCLK"]], color="#a855f7", priority=13)
            Net(name="PDM_DAT", pins=[["U1", "H1"], ["U4", "DIN"]], color="#9333ea", priority=14)
            Net(name="PDM_LRCLK", pins=[["U1", "J1"], ["U4", "LRCLK"]], color="#c084fc", priority=15)
            Net(name="SPK_P", pins=[["U4", "OUTP"], ["U5", "1"]], color="#e11d48")
            Net(name="SPK_N", pins=[["U4", "OUTN"], ["U5", "2"]], color="#be123c")
            Net(name="VREGD", pins=[["U2", "VREGD"], ["C12", "1"]], color="#0891b2")
            Net(name="VREGA", pins=[["U2", "VREGA"], ["C14", "1"]], color="#06b6d4")
            Net(name="I2C0_SCL", pins=[["U7", "7"], ["U6", "1"], ["U1", "A10"]], color="#22c55e", priority=15)
            Net(name="I2C0_SDA", pins=[["U7", "8"], ["U6", "2"], ["U1", "B10"]], color="#16a34a", priority=16)
            Net(name="FUEL_ALRT", pins=[["U7", "5"], ["U1", "G5"]], color="#eab308", priority=24)
            Net(name="LED_R", pins=[["U6", "6"], ["D1", "1"]], color="#ef4444")
            Net(name="LED_G", pins=[["U6", "7"], ["D1", "2"]], color="#22c55e")
            Net(name="LED_B", pins=[["U6", "8"], ["D1", "3"]], color="#3b82f6")
            Net(name="FLEX0_A_CS0_N", pins=[["U8", "1"], ["U1", "B17"]], color="#6366f1", priority=9)
            Net(name="FLEX0_A_IO2", pins=[["U8", "3"], ["U1", "F17"]], color="#a5b4fc", priority=10)
            Net(name="FLEX0_A_IO3", pins=[["U8", "7"], ["U1", "F16"]], color="#c7d2fe", priority=11)
            Net(name="FLEX0_A_IO1", pins=[["U8", "2"], ["U1", "F15"]], color="#818cf8", priority=12)
            Net(name="FLEX0_A_IO0", pins=[["U8", "5"], ["U1", "E14"]], color="#4f46e5", priority=13)
            Net(name="FLEX0_A_SCK", pins=[["U8", "6"], ["U1", "D14"]], color="#4338ca", priority=14)
            Net(name="SWD_CLK", pins=[["J5", "4"], ["U1", "A16"]], color="#0d9488", priority=9)
            Net(name="SWD_DIO", pins=[["J5", "2"], ["U1", "A17"]], color="#14b8a6", priority=10)
            Net(name="I2C2_SCL", pins=[["J6", "4"], ["U1", "B1"]], color="#059669", priority=7)
            Net(name="I2C2_SDA", pins=[["J6", "3"], ["U1", "A1"]], color="#10b981", priority=8)
            Net(name="I3C1_SCL", pins=[["J8", "4"], ["U1", "F4"]], color="#0369a1", priority=22)
            Net(name="I3C1_SDA", pins=[["J8", "3"], ["U1", "F6"]], color="#0284c7", priority=23)
            Net(name="I3C0_SCL", pins=[["J7", "4"], ["U1", "A8"]], color="#0891b2", priority=17)
            Net(name="I3C0_SDA", pins=[["J7", "3"], ["U1", "C8"]], color="#06b6d4", priority=18)
            Net(name="SPI0_CS_N", pins=[["J9", "1", "SPI0_CS_N"], ["U1", "R9"]], color="#92400e", priority=27)
            Net(name="SPI0_MISO", pins=[["J9", "2", "SPI0_MISO"], ["U1", "R8"]], color="#b45309", priority=28)
            Net(name="SPI0_MOSI", pins=[["J9", "3", "SPI0_MOSI"], ["U1", "T7"]], color="#d97706", priority=29)
            Net(name="SPI0_SCK", pins=[["J9", "4", "SPI0_SCK"], ["U1", "T6"]], color="#f59e0b", priority=30)
            Net(name="UART0_CTS", pins=[["U9", "3"], ["U1", "F10"]], color="#a78bfa", priority=25)
            Net(name="UART0_RTS", pins=[["U9", "11"], ["U1", "E10"]], color="#6d28d9", priority=26)
            Net(name="UART0_TXD", pins=[["U9", "5"], ["U1", "A6"]], color="#7c3aed", priority=3)
            Net(name="UART0_RXD", pins=[["U9", "1"], ["U1", "B6"]], color="#8b5cf6", priority=4)
            Net(name="USB_DP", pins=[["U9", "15"], ["J3", "DP1"]], color="#ec4899", priority=21)
            Net(name="USB_DM", pins=[["U9", "16"], ["J3", "DN1"]], color="#db2777", priority=22)
            Net(name="FTDI_3V3", pins=[["U9", "17"], ["U9", "24"]], color="#f43f5e", priority=25)
            Net(name="DTR_N", pins=[["U9", "2"], ["J10", "3", "DTR_N"]], color="#64748b")
            Net(name="DSR_N", pins=[["U9", "9"], ["J10", "7", "DSR_N"]], color="#64748b")
            Net(name="DCD_N", pins=[["U9", "10"], ["J10", "6", "DCD_N"]], color="#64748b")
            Net(name="CBUS4", pins=[["U9", "12"], ["J10", "5", "CBUS4"]], color="#64748b")
            Net(name="CBUS2", pins=[["U9", "13"], ["J10", "4", "CBUS2"]], color="#64748b")
            Net(name="CBUS3", pins=[["U9", "14"], ["J14", "10", "CBUS3"]], color="#64748b")
            Net(name="CBUS5", pins=[["U9", "30"], ["J14", "8", "CBUS5"]], color="#64748b")
            Net(name="CBUS6", pins=[["U9", "31"], ["J14", "9", "CBUS6"]], color="#64748b")
            Net(name="CBUS7", pins=[["U9", "32"], ["J14", "7", "CBUS7"]], color="#64748b")
            Net(name="OSCI", pins=[["U9", "27"], ["U9", "28"]], color="#64748b")
            Net(name="GPIO0", pins=[["J14", "1", "GPIO0"], ["U1", "M8"]], color="#10b981", priority=33)
            Net(name="GPIO1", pins=[["J14", "2", "GPIO1"], ["U1", "N8"]], color="#10b981", priority=34)
            Net(name="GPIO2", pins=[["J14", "3", "GPIO2"], ["U1", "N10"]], color="#10b981", priority=35)
            Net(name="GPIO3", pins=[["J14", "4", "GPIO3"], ["U1", "T10"]], color="#10b981", priority=38)
        with BuildTestSteps(subassembly="carrier_board") as cb_steps:
            TestStep(
                step_id="TEST_CONTINUITY_GND",
                description="Verify solid low-impedance ground plane continuity across all copper layers",
                test_type="continuity",
                net_name="GND",
                pad_a_mm=(-18.0, -22.0),
                pad_b_mm=(-25.0, -4.2),
                nominal=0.05,
                tolerance_pct=20.0,
                unit="ohm",
                stimulus="100mA 4-wire Kelvin DC",
                measured=0.048,
            )
            TestStep(
                step_id="TEST_UART_BLE_SPEED",
                description="Measure BTLE high-speed 1Mb/s UART signal integrity on BLE_TX / BLE_RX",
                test_type="voltage",
                net_name="BLE_UART",
                pad_a_mm=(-6.0, -22.0),
                pad_b_mm=(-10.0, -22.0),
                nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="1Mb/s PRBS UART serial transceiver test",
                measured=3.3,
            )
            TestStep(
                step_id="TEST_RAIL_3V3",
                description="Verify regulated system 3.3V power distribution rail",
                test_type="voltage",
                net_name="3V3",
                pad_a_mm=(-10.0, -26.0),
                pad_b_mm=(-18.0, -22.0),
                nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="DC power rail regulation probe",
                measured=3.31,
            )
            TestStep(
                step_id="TEST_RAIL_VBAT",
                description="Verify battery input sensing rail continuity to charger",
                test_type="voltage",
                net_name="VBAT",
                pad_a_mm=(-18.0, -26.0),
                pad_b_mm=(-18.0, -22.0),
                nominal=3.7,
                tolerance_pct=5.0,
                unit="V",
                stimulus="Battery charge domain sensor",
                measured=3.72,
            )
            TestStep(
                step_id="TEST_IMP_USB_DIFF",
                description="Measure USB 2.0 / USB-C differential impedance on DP/DM",
                test_type="diff_pair",
                net_name="USB_DP_DM",
                pad_a_mm=(-25.0, 0.5),
                pad_b_mm=(-25.0, -0.5),
                nominal=90.0,
                tolerance_pct=10.0,
                unit="ohm",
                stimulus="200ps TDR step differential pulse",
                measured=89.8,
            )
            TestStep(
                step_id="TEST_UART_BLE_FLOW_CTRL",
                description="Verify BTLE hardware flow control handshake on BLE_RTS / BLE_CTS",
                test_type="voltage",
                net_name="BLE_FLOW_CTRL",
                pad_a_mm=(-14.0, -22.0),
                pad_b_mm=(-2.0, -22.0),
                nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="Hardware RTS/CTS assert handshake probe",
                measured=3.3,
            )
            TestStep(
                step_id="TEST_I2C_PULLUPS",
                description="Measure I2C SDA/SCL pull-up resistance to 3.3V rail",
                test_type="resistance",
                net_name="I2C_BUS",
                pad_a_mm=(14.0, -4.0),
                pad_b_mm=(18.0, -4.0),
                nominal=4700.0,
                tolerance_pct=5.0,
                unit="ohm",
                stimulus="1.0V DC precision Ohmmeter",
                measured=4705.0,
            )

        with BuildTestSteps(subassembly="flex_tail") as flex_steps:
            TestStep(
                step_id="TEST_CAP_SENSE_CHAN0",
                description="Measure baseline mutual capacitance on liquid level electrode Channel 0",
                test_type="capacitance",
                net_name="CAP_CHAN0",
                pad_a_mm=(0.0, -6.25),
                pad_b_mm=(-3.0, -6.25),
                nominal=12.5,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="250kHz 1.8V square wave",
                measured=12.6,
            )
            TestStep(
                step_id="TEST_CAP_SENSE_CHAN1",
                description="Measure baseline mutual capacitance on liquid level electrode Channel 1",
                test_type="capacitance",
                net_name="CAP_CHAN1",
                pad_a_mm=(0.0, 5.25),
                pad_b_mm=(-3.0, 5.25),
                nominal=14.0,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="250kHz 1.8V square wave",
                measured=14.1,
            )
            TestStep(
                step_id="TEST_CAP_SENSE_CHAN2",
                description="Measure baseline mutual capacitance on liquid level electrode Channel 2",
                test_type="capacitance",
                net_name="CAP_CHAN2",
                pad_a_mm=(0.0, 16.75),
                pad_b_mm=(-3.0, 16.75),
                nominal=15.5,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="250kHz 1.8V square wave",
                measured=15.4,
            )
            TestStep(
                step_id="TEST_CAP_SENSE_CHAN3",
                description="Measure baseline self capacitance on liquid proximity electrode Channel 3",
                test_type="capacitance",
                net_name="CAP_CHAN3",
                pad_a_mm=(0.0, 24.75),
                pad_b_mm=(0.0, -22.75),
                nominal=8.0,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="250kHz 1.8V square wave self-cap",
                measured=8.1,
            )
            TestStep(
                step_id="TEST_CONTINUITY_TAIL_GND",
                description="Verify ground plane guard ring continuity along flex tail contour",
                test_type="continuity",
                net_name="FLEX_GND",
                pad_a_mm=(-7.0, -20.0),
                pad_b_mm=(7.0, -20.0),
                nominal=0.08,
                tolerance_pct=20.0,
                unit="ohm",
                stimulus="100mA 4-wire Kelvin DC",
                measured=0.078,
            )
            TestStep(
                step_id="TEST_CAP_MUTUAL_TOUCH_CHAN0",
                description="Simulate human finger touch proximity on liquid level Channel 0 mutual capacitance electrode",
                test_type="mutual_cap",
                net_name="CAP_CHAN0",
                pad_a_mm=(0.0, -6.25),
                pad_b_mm=(-3.0, -6.25),
                nominal=15.8,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                measured=15.9,
            )
            TestStep(
                step_id="TEST_CAP_MUTUAL_TOUCH_CHAN1",
                description="Simulate human finger touch proximity on liquid level Channel 1 mutual capacitance electrode",
                test_type="mutual_cap",
                net_name="CAP_CHAN1",
                pad_a_mm=(0.0, 5.25),
                pad_b_mm=(-3.0, 5.25),
                nominal=17.5,
                tolerance_pct=15.0,
                unit="pF",
                stimulus="Simulated finger proximity 250kHz 1.8V dielectric perturb",
                measured=17.6,
            )

    all_components = carrier_comps.components + status_comps.components + rf_comps.components
    symbol_table.update(carrier_comps.symbol_table_entries)
    symbol_table.update(status_comps.symbol_table_entries)
    symbol_table.update(rf_comps.symbol_table_entries)

    merged_nets = list(pwr_nets.nets)
    existing_net_names = {n.name for n in merged_nets}
    for sn in sig_nets.nets:
        if sn.name in existing_net_names:
            target = next(n for n in merged_nets if n.name == sn.name)
            for p in sn.pins:
                if p not in target.pins:
                    target.pins.append(p)
        else:
            merged_nets.append(sn)
            existing_net_names.add(sn.name)

    wiring = Wiring.from_models(
        footprints=all_components,
        nets=merged_nets,
        parent_part=parent_part,
        symbol_table=symbol_table,
    )
    return wiring


def build_carrier_board_system_wiring() -> Wiring:
    """Construct top-down architecture system wiring for block diagram rendering."""
    with BuildComponents(name="system_interconnect") as sys_comps:
        btle_host = Component(
            name="btle_host",
            package="board",
            position=[-80.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[22.0, 50.0, 1.6],
            color="cornflowerblue",
            label={"text": "BTLE Wireless Host", "position": [-16.0, 0.0, 0.0], "align": ["max", "center"]},
            pins=[
                {"name": "BLE_RX", "label": "RX (1Mb/s)", "side": "right"},
                {"name": "BLE_TX", "label": "TX (1Mb/s)", "side": "right"},
                {"name": "BLE_RTS", "label": "RTS", "side": "right"},
                {"name": "BLE_CTS", "label": "CTS", "side": "right"},
                {"name": "3V3", "label": "3V3", "side": "right"},
                {"name": "GND", "label": "GND", "side": "right"},
            ],
        )
        usb_c = Component(
            name="usb_c",
            package="board",
            position=[0.0, -80.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[30.0, 18.0, 1.6],
            color="darkorange",
            label={"text": "USB-C Source (5V)", "position": [0.0, -14.0, 0.0], "align": ["center", "max"]},
            pins=[
                {"name": "VBUS", "label": "VBUS (5V)", "side": "top"},
                {"name": "CC", "label": "CC1/CC2", "side": "top"},
                {"name": "USB_D", "label": "D+/D-", "side": "top"},
                {"name": "GND", "label": "GND", "side": "top"},
            ],
        )
        carrier_pcb = Component(
            name="carrier_pcb",
            package="board",
            position=[0.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[60.0, 90.0, 1.6],
            color="forestgreen",
            label={"text": "Test Board Carrier PCB", "position": [0.0, 0.0, 0.0], "align": ["center", "center"]},
            pins=[
                {"name": "BLE_RX", "label": "BLE_RX", "side": "left"},
                {"name": "BLE_TX", "label": "BLE_TX", "side": "left"},
                {"name": "BLE_RTS", "label": "BLE_RTS", "side": "left"},
                {"name": "BLE_CTS", "label": "BLE_CTS", "side": "left"},
                {"name": "BLE_3V3", "label": "3V3", "side": "left"},
                {"name": "BLE_GND", "label": "GND", "side": "left"},
                {"name": "USB_VBUS", "label": "VBUS", "side": "bottom"},
                {"name": "USB_CC", "label": "CC", "side": "bottom"},
                {"name": "USB_DATA", "label": "USB_D", "side": "bottom"},
                {"name": "USB_GND", "label": "GND", "side": "bottom"},
                {"name": "FPC_TX0", "label": "CAP_TX0", "side": "top"},
                {"name": "FPC_RX0", "label": "CAP_RX0", "side": "top"},
                {"name": "FPC_TX1", "label": "CAP_TX1", "side": "top"},
                {"name": "FPC_RX1", "label": "CAP_RX1", "side": "top"},
                {"name": "FPC_TX2", "label": "CAP_TX2", "side": "top"},
                {"name": "FPC_RX2", "label": "CAP_RX2", "side": "top"},
                {"name": "FPC_RX3", "label": "CAP_RX3", "side": "top"},
                {"name": "FPC_SHIELD", "label": "SHIELD", "side": "top"},
                {"name": "FPC_GND", "label": "GND", "side": "top"},
            ],
        )
        flex_tail = Component(
            name="flex_tail",
            package="board",
            position=[0.0, 85.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[24.0, 54.0, 0.2],
            color="goldenrod",
            label={"text": "Capacitive Flex Tail Sensor", "position": [0.0, 32.0, 0.0], "align": ["center", "min"]},
            pins=[
                {"name": "TX0", "label": "CH0_TX", "side": "bottom"},
                {"name": "RX0", "label": "CH0_RX", "side": "bottom"},
                {"name": "TX1", "label": "CH1_TX", "side": "bottom"},
                {"name": "RX1", "label": "CH1_RX", "side": "bottom"},
                {"name": "TX2", "label": "CH2_TX", "side": "bottom"},
                {"name": "RX2", "label": "CH2_RX", "side": "bottom"},
                {"name": "RX3", "label": "CH3_PROX", "side": "bottom"},
                {"name": "SHIELD", "label": "SHIELD", "side": "bottom"},
                {"name": "GND", "label": "GND", "side": "bottom"},
            ],
        )

    with BuildWiring(name="system_nets") as sys_wiring:
        Net("ble_tx", pins=[btle_host.pin("BLE_TX"), carrier_pcb.pin("BLE_RX")], color="blue")
        Net("ble_rx", pins=[btle_host.pin("BLE_RX"), carrier_pcb.pin("BLE_TX")], color="blue")
        Net("ble_rts", pins=[btle_host.pin("BLE_RTS"), carrier_pcb.pin("BLE_CTS")], color="purple")
        Net("ble_cts", pins=[btle_host.pin("BLE_CTS"), carrier_pcb.pin("BLE_RTS")], color="purple")
        Net("pwr_3v3", pins=[btle_host.pin("3V3"), carrier_pcb.pin("BLE_3V3")], color="red")
        Net("gnd_ble", pins=[btle_host.pin("GND"), carrier_pcb.pin("BLE_GND")], color="black")
        Net("vbus_5v", pins=[usb_c.pin("VBUS"), carrier_pcb.pin("USB_VBUS")], color="red")
        Net("usb_cc", pins=[usb_c.pin("CC"), carrier_pcb.pin("USB_CC")], color="orange")
        Net("usb_data", pins=[usb_c.pin("USB_D"), carrier_pcb.pin("USB_DATA")], color="cyan")
        Net("gnd_usb", pins=[usb_c.pin("GND"), carrier_pcb.pin("USB_GND")], color="black")
        Net("cap_tx0", pins=[carrier_pcb.pin("FPC_TX0"), flex_tail.pin("TX0")], color="magenta")
        Net("cap_rx0", pins=[carrier_pcb.pin("FPC_RX0"), flex_tail.pin("RX0")], color="green")
        Net("cap_tx1", pins=[carrier_pcb.pin("FPC_TX1"), flex_tail.pin("TX1")], color="magenta")
        Net("cap_rx1", pins=[carrier_pcb.pin("FPC_RX1"), flex_tail.pin("RX1")], color="green")
        Net("cap_tx2", pins=[carrier_pcb.pin("FPC_TX2"), flex_tail.pin("TX2")], color="magenta")
        Net("cap_rx2", pins=[carrier_pcb.pin("FPC_RX2"), flex_tail.pin("RX2")], color="green")
        Net("cap_rx3", pins=[carrier_pcb.pin("FPC_RX3"), flex_tail.pin("RX3")], color="green")
        Net("cap_shield", pins=[carrier_pcb.pin("FPC_SHIELD"), flex_tail.pin("SHIELD")], color="yellow")
        Net("gnd_flex", pins=[carrier_pcb.pin("FPC_GND"), flex_tail.pin("GND")], color="black")

    return Wiring.from_models(
        footprints=sys_comps.components,
        nets=sys_wiring.nets,
        symbol_table=sys_comps.symbol_table_entries,
    )


def build_carrier_board_pcb_config(provider: Optional[Any] = None) -> PCBConfig:
    """Build strongly-typed PCBConfig for Carrier Board and Flex Tail."""
    if provider is not None and hasattr(provider, "pcb_config") and provider.pcb_config is not None:
        return provider.pcb_config
    from .provider import CarrierBoardProvider

    p = CarrierBoardProvider()
    cfg = p.pcb_config
    if cfg is not None:
        return cfg
    raise ValueError("Failed to construct PCBConfig from CarrierBoardProvider.")
