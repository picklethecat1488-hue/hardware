"""Declarative PCB layout, rigid-flex substrates, wiring, test steps, and routing for Carrier Board."""

import threading
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
from model import Wiring, DiagramOptions, DiagramStyle, LabelModel
from provider import Mode, Room
from functools import cached_property
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
    SchematicLayoutModel,
    SchematicSheetModel,
    PinSideDef,
    AssemblyTestStepModel,
    AssemblyTestModel,
    StackupModel,
    SymbolTableEntry,
    SheetSize,
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
    Pin,
    PinList,
    PinListModel,
    PinModel,
    PinSide,
    BuildWiring,
    Net,
    BuildAssemblyTests,
    TestStep,
    RouteStyle,
    BuildSchematic,
    SchematicConfig,
    SchematicSheet,
    BuildDesignRules,
    BuildNetClasses,
    BuildFlexZones,
    BuildObstacles,
    BuildCapacitiveSensors,
    PcbMetadata,
)


def build_carrier_board_schematic_config() -> SchematicConfig:
    """Instantiate the 21 schematic sheets for Carrier Board."""
    cfg = SchematicConfig(sheet_size=SheetSize.A4)
    with cfg:
        SchematicSheet(
            title="USB-C Power & Battery Interface",
            description="USB-C connector, CC pull-down termination, Li-Ion battery connector, and MAX17048 fuel gauge",
        )
        SchematicSheet(
            title="3.3V Power Regulation & Distribution",
            description="Low-dropout linear voltage regulator with C8 bulk filtering, and system decoupling",
            layout={"cols_per_row": 4, "grid_positions": {"U3": [0, 0], "C8": [0, 1]}},
        )
        SchematicSheet(
            title="Peripheral Power Regulation & Gating",
            description="Dedicated 3.3V peripheral buck regulator (TLV62568) and power gating enable control",
        )
        SchematicSheet(
            title="Microcontroller Core, Clock & Reset",
            description="Primary microcontroller core, 24MHz crystal oscillator, power bypass, reset and boot circuitry",
            layout={"col_gap": 65.0},
        )
        SchematicSheet(
            title="External Serial NAND Storage Subsystem",
            description="Winbond W25N01GV 1Gb SLC serial NAND flash on FlexSPI Port A",
        )
        SchematicSheet(
            title="Telemetry & Debug Communications",
            description="FTDI FT232RNQ high-speed USB-to-UART serial bridge and ARM 10-pin SWD debug micro-header",
        )
        SchematicSheet(
            title="User Interface & Status Indication",
            description="TI LP5009 9-channel I2C constant-current LED driver and high-brightness RGB status indicator",
        )
        SchematicSheet(
            title="Capacitive Sensing & Control (Azoteq IQS7222A)",
            description="Azoteq IQS7222A ProxFusion controller, 5-button slider, action button, and proximity sensing flex tail, and I2C bus",
            layout={"col_gap": 65.0},
        )
        SchematicSheet(
            title="Audio Subsystem",
            description="MAX98357A I2S/PDM digital audio amplifier and piezo speaker",
            layout={"cols_per_row": 3, "grid_positions": {"U1": [0, 0], "U4": [0, 1], "U5": [0, 2]}},
        )
        SchematicSheet(
            title="High-Speed BTLE UART & Wireless Interface",
            description="BTLE transceiver module (U11) with 1Mb/s high-speed UART link, flow control, cap-touch pairing trigger, and integrated PCB antenna",
            layout={
                "cols_per_row": 3,
                "col_gap": 50.0,
                "grid_positions": {"U1": [0, 0], "U11": [0, 1], "J16": [0, 2]},
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
        )
        SchematicSheet(
            title="I2C Peripheral Expansion Interface (J6)",
            description="Primary I2C peripheral expansion connector (JST-PH-6P)",
        )
        SchematicSheet(
            title="I3C Primary Controller Expansion Interface (J7)",
            description="High-speed I3C0 primary peripheral expansion connector (JST-PH-6P)",
        )
        SchematicSheet(
            title="I3C Secondary Controller Expansion Interface (J8)",
            description="High-speed I3C1 secondary peripheral expansion connector (JST-PH-6P)",
        )
        SchematicSheet(
            title="SPI Master Expansion Interface (J9)",
            description="High-speed SPI peripheral expansion connector (JST-PH-7P)",
        )
        SchematicSheet(
            title="UART & Control Expansion Interface (J10)",
            description="FTDI auxiliary UART and modem control expansion connector (JST-PH-7P)",
        )
        SchematicSheet(
            title="General Purpose I/O Expansion Header",
            description="10-pin multipurpose microcontroller GPIO expansion header",
        )
        SchematicSheet(
            title="Status and Overrides - MCU Reset & Bootloader",
            description="Manual reset pushbutton and FTDI hardware programming jumpers",
            layout={
                "cols_per_row": 3,
                "top_row_y": 152.0,
                "grid_positions": {"SW1": [0, 0], "JP1": [0, 1], "JP2": [0, 2]},
            },
        )
        SchematicSheet(
            title="Status and Overrides - Power Isolation & Boot Mode",
            description="Boot configuration and USB charger isolation jumpers",
            layout={"cols_per_row": 2, "top_row_y": 152.0, "grid_positions": {"JP3": [0, 0], "JP4": [0, 1]}},
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
        )
    return cfg


def build_carrier_board_design_rules() -> PCBDesignRulesModel:
    """Return fabrication and spacing design rules for Carrier Board."""
    return PCBDesignRulesModel(
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


def build_carrier_board_net_classes() -> List[NetClassModel]:
    """Return high-speed, RF, and interface net class rules for Carrier Board."""
    return [
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


def build_carrier_board_flex_zones() -> List[FlexZoneModel]:
    """Return rigid-flex transition zones for Carrier Board."""
    return [
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


def build_carrier_board_obstacles() -> List[PCBObstacleModel]:
    """Return 3D component clearance obstacles and RF keepouts for Carrier Board."""
    return [
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


def build_carrier_board_capacitive_sensors() -> List[CapacitiveElectrodeModel]:
    """Return capacitive sensing electrodes for Carrier Board."""
    return []


def build_carrier_board_assembly_test() -> AssemblyTestModel:
    """Return flying probe assembly test instructions for Carrier Board."""
    return AssemblyTestModel(
        test_fixture="flying_probe",
        pass_criteria="all_steps_within_tolerance",
        subassembly="carrier_board",
        instructions=[
            AssemblyTestStepModel(
                step_id="TEST_CONTINUITY_GND",
                description="Verify solid low-impedance ground plane continuity across all copper layers",
                test_type="continuity",
                net_name="GND",
                net_or_points=["GND", "IN1_GND", "IN3_PWR"],
                pad_a_mm=(-18.0, -22.0),
                pad_b_mm=(-25.0, -4.2),
                nominal=0.05,
                expected_nominal=0.05,
                tolerance_pct=20.0,
                unit="ohm",
                stimulus="100mA 4-wire Kelvin DC",
                measured=0.048,
            ),
            AssemblyTestStepModel(
                step_id="TEST_UART_BLE_SPEED",
                description="Measure BTLE high-speed 1Mb/s UART signal integrity on BLE_TX / BLE_RX",
                test_type="voltage",
                net_name="BLE_UART",
                net_or_points=["BLE_TX", "BLE_RX"],
                pad_a_mm=(-6.0, -22.0),
                pad_b_mm=(-10.0, -22.0),
                nominal=3.3,
                expected_nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="1Mb/s PRBS UART serial transceiver test",
                measured=3.3,
            ),
            AssemblyTestStepModel(
                step_id="TEST_RAIL_3V3",
                description="Verify regulated system 3.3V power distribution rail",
                test_type="voltage",
                net_name="3V3",
                pad_a_mm=(-10.0, -26.0),
                pad_b_mm=(-18.0, -22.0),
                nominal=3.3,
                expected_nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="DC power rail regulation probe",
                measured=3.31,
            ),
            AssemblyTestStepModel(
                step_id="TEST_RAIL_VBAT",
                description="Verify battery input sensing rail continuity to charger",
                test_type="voltage",
                net_name="VBAT",
                pad_a_mm=(-18.0, -26.0),
                pad_b_mm=(-18.0, -22.0),
                nominal=3.7,
                expected_nominal=3.7,
                tolerance_pct=5.0,
                unit="V",
                stimulus="Battery charge domain sensor",
                measured=3.72,
            ),
            AssemblyTestStepModel(
                step_id="TEST_IMP_USB_DIFF",
                description="Measure USB 2.0 / USB-C differential impedance on DP/DM",
                test_type="diff_pair",
                net_name="USB_DP_DM",
                pad_a_mm=(-25.0, 0.5),
                pad_b_mm=(-25.0, -0.5),
                nominal=90.0,
                expected_nominal=90.0,
                tolerance_pct=10.0,
                unit="ohm",
                stimulus="200ps TDR step differential pulse",
                measured=89.8,
            ),
            AssemblyTestStepModel(
                step_id="TEST_UART_BLE_FLOW_CTRL",
                description="Verify BTLE hardware flow control handshake on BLE_RTS / BLE_CTS",
                test_type="voltage",
                net_name="BLE_FLOW_CTRL",
                pad_a_mm=(-14.0, -22.0),
                pad_b_mm=(-2.0, -22.0),
                nominal=3.3,
                expected_nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="Hardware RTS/CTS assert handshake probe",
                measured=3.3,
            ),
            AssemblyTestStepModel(
                step_id="TEST_I2C_PULLUPS",
                description="Measure I2C SDA/SCL pull-up resistance to 3.3V rail",
                test_type="resistance",
                net_name="I2C_BUS",
                pad_a_mm=(14.0, -4.0),
                pad_b_mm=(18.0, -4.0),
                nominal=4700.0,
                expected_nominal=4700.0,
                tolerance_pct=5.0,
                unit="ohm",
                stimulus="1.0V DC precision Ohmmeter",
                measured=4705.0,
            ),
        ],
    )


class CarrierBoardPCBListing:
    """PCB substrate builders, layer stackups, drill holes, and physical copper geometries."""

    @cached_property
    def _wiring_lock(self) -> threading.Lock:
        return threading.Lock()

    @cached_property
    def _sheets_lock(self) -> threading.Lock:
        return threading.Lock()

    @property
    def sheets(self) -> SchematicConfig:
        """Return thread-safe cached SchematicConfig containing all 21 carrier board drawing sheets."""
        if hasattr(self, "_cached_sheets_config") and self._cached_sheets_config is not None:
            return self._cached_sheets_config
        with self._sheets_lock:
            if hasattr(self, "_cached_sheets_config") and self._cached_sheets_config is not None:
                return self._cached_sheets_config
            self._cached_sheets_config = build_carrier_board_schematic_config()
            return self._cached_sheets_config

    @cached_property
    def tests(self) -> AssemblyTestModel:
        """Return cached assembly test model and instructions."""
        return build_carrier_board_assembly_test()

    @cached_property
    def flex_tail_tests(self) -> AssemblyTestModel:
        """Return cached assembly test model and instructions for flex tail."""
        from .flex_tail import build_flex_tail_assembly_test

        return build_flex_tail_assembly_test()

    @cached_property
    def net_classes(self) -> List[NetClassModel]:
        """Return cached high-speed and differential net classes."""
        return build_carrier_board_net_classes()

    @cached_property
    def design_rules(self) -> PCBDesignRulesModel:
        """Return cached PCB fabrication and layout design rules."""
        return build_carrier_board_design_rules()

    @cached_property
    def flex_zones(self) -> List[FlexZoneModel]:
        """Return cached flex zones."""
        return build_carrier_board_flex_zones()

    @cached_property
    def obstacles(self) -> List[PCBObstacleModel]:
        """Return cached 3D clearance keepouts and obstacles."""
        return build_carrier_board_obstacles()

    @cached_property
    def capacitive_sensors(self) -> List[CapacitiveElectrodeModel]:
        """Return cached capacitive sensing electrode definitions."""
        return build_carrier_board_capacitive_sensors()

    @property
    def wiring(self) -> Wiring:
        """Return thread-safe in-memory wiring model."""
        if hasattr(self, "_cached_wiring_model") and self._cached_wiring_model is not None:
            return self._cached_wiring_model
        with self._wiring_lock:
            if hasattr(self, "_cached_wiring_model") and self._cached_wiring_model is not None:
                return self._cached_wiring_model
            self._cached_wiring_model = build_carrier_board_wiring(schematic_config=self.sheets)
            return self._cached_wiring_model

    @property
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

    @property
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
        with BuildPcb(
            name="CarrierBoard",
            shape_ref="carrier_board",
            board_type=BoardType.RIGID,
            revision=pcb_rev,
        ) as pcb:
            with BuildDesignRules() as bdr:
                bdr.add(self.design_rules)
            with BuildNetClasses() as bnc:
                bnc.add(self.net_classes)
            with BuildFlexZones() as bfz:
                bfz.add(self.flex_zones)
            with BuildObstacles() as bo:
                bo.add(self.obstacles)
            with BuildCapacitiveSensors() as bcs:
                bcs.add(self.capacitive_sensors)
            with BuildStackup() as bst:
                bst.add(self.stackup)
            with BuildWiring() as bw:
                bw.add(self.wiring)
            with BuildSchematic() as bs:
                bs.add(self.sheets)
            with BuildAssemblyTests() as bat:
                bat.add(self.tests)

            # Main board outline block
            b = Box(w, length, thickness)
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
            tp = self.test_points
            for cyl in tp.to_shapes(depth_mm=thickness):
                add(cyl, mode=BuildMode.SUBTRACT)

            cr = self.copper_regions
            for r in cr.regions:
                if r not in pcb.copper_regions:
                    pcb.copper_regions.append(r)

            with BuildSilkscreen() as silk:
                silk.add(self.silkscreen)
                silk.add(self.silkscreen_graphics)

            with BuildTraces() as bt:
                bt.add(self.traces)
            with BuildVias() as bv:
                bv.add(self.vias)

        return pcb

    def view_carrier_board(self, room: Room, mode: Mode) -> None:
        """Assemble rigid carrier PCB with component obstacles and test points for inspection and simulation."""
        carrier = self.carrier_board("carrier_board", None, mode)
        room.add("carrier_board", carrier.part, color=self.CARRIER_BOARD_COLOR, alpha=1.0)

    @property
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

    @property
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
        """Compute complete routed traces and vias directly from carrier_board_routing.py."""
        from projects.carrier_board.carrier_board_routing import (
            get_carrier_board_traces,
            get_carrier_board_vias,
        )

        return get_carrier_board_traces(), get_carrier_board_vias()

    @property
    def traces(self) -> list[TraceSegmentModel]:
        """Return routed copper traces for the test board."""
        return self._routed_network[0]

    @property
    def vias(self) -> list[ViaModel]:
        """Return interlayer vias for the test board."""
        return self._routed_network[1]

    @property
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

    @property
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


def build_carrier_board_wiring(
    parent_part: Optional[Any] = None,
    schematic_config: Optional[SchematicConfig] = None,
) -> Wiring:
    """Construct complete in-memory Wiring model for Carrier Board using BuildComponents and BuildWiring."""
    if schematic_config is None:
        schematic_config = build_carrier_board_schematic_config()

    with schematic_config:
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
                pins=[
                    Pin("J8", "VSS"),
                ],
                schematic_sheets={
                    "Peripheral Power Regulation & Gating": PinSideDef(right=["L5"]),
                    "Microcontroller Core, Clock & Reset": PinSideDef(
                        left=["J8", "H8", "F3", "C14"], right=["F2", "F1"]
                    ),
                    "External Serial NAND Storage Subsystem": PinSideDef(
                        right=["B17", "D14", "E14", "F15", "F17", "F16"]
                    ),
                    "Telemetry & Debug Communications": PinSideDef(right=["B6", "A6", "F10", "E10", "A17", "A16"]),
                    "User Interface & Status Indication": PinSideDef(right=["A10", "B10"]),
                    "Capacitive Sensing & Control (Azoteq IQS7222A)": PinSideDef(right=["C5", "C6", "C4"]),
                    "Audio Subsystem": PinSideDef(right=["G2", "H1", "J1", "L4"]),
                    "High-Speed BTLE UART & Wireless Interface": PinSideDef(left=["T2", "T1", "T3", "T4"]),
                    "I2C Peripheral Expansion Interface (J6)": PinSideDef(right=["B2", "A1", "B1"]),
                    "I3C Primary Controller Expansion Interface (J7)": PinSideDef(right=["B8", "A8", "C8"]),
                    "I3C Secondary Controller Expansion Interface (J8)": PinSideDef(right=["E4", "F6", "F4"]),
                    "SPI Master Expansion Interface (J9)": PinSideDef(right=["R9", "R8", "T7", "T6", "T8"]),
                    "General Purpose I/O Expansion Header": PinSideDef(left=["M8", "N8"], right=["N10", "T10"]),
                },
            )
            u2 = Component(
                name="U2",
                package="QFN-20",
                position=(18.0, -9.0, -0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="IQS7222C101QNR",
                supplier_pn="1790-IQS7222C101QNRCT-ND",
                layer="B.Cu",
                sheet="Capacitive Sensing & Control (Azoteq IQS7222A)",
                pin_sides=PinSideDef(
                    left=["SCL", "SDA", "RDY", "VDD", "MCLR", "VSS", "EP"],
                    right=["CR0", "CR1", "CR2", "CR3", "CR4", "CR5", "CR6", "CR7", "CT8", "OUTA"],
                ),
            )
            u11 = Component(
                name="U11",
                package="MOD-BLE-PCB-ANT",
                position=(0.0, -36.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="NINA-B312-02B",
                supplier_pn="1972-NINA-B312-02B-ND",
                sheet="High-Speed BTLE UART & Wireless Interface",
                pin_sides=PinSideDef(
                    left=["RXD", "RTS", "TXD", "CTS", "RESET_N"],
                    right=["GND", "3V3", "NFC1", "NFC2"],
                ),
            )
            j15 = Component(
                name="J15",
                package="pin_header_2x5_1.27mm",
                position=(-14.5, -41.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="DNP",
                supplier_pn="N/A",
                dnp=True,
                sheet="BTLE Programming & Reset Interface (J15, SW2)",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5"]),
            )
            sw2 = Component(
                name="SW2",
                package="SW_PUSH_SMD",
                position=(-14.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
                sheet="BTLE Programming & Reset Interface (J15, SW2)",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )
            j2 = Component(
                name="J2",
                package="FPC-30P-0.5MM",
                position=(0.0, 38.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FH12-30S-0.5SH(55)",
                supplier_pn="HFJ130CT-ND",
                shape_ref="carrier_board",
                sheet="Capacitive Sensing & Control (Azoteq IQS7222A)",
                pin_sides=PinSideDef(
                    left=[
                        "CAP_RX0",
                        "CAP_RX1",
                        "CAP_RX2",
                        "CAP_RX3",
                        "CAP_TX0",
                        "CAP_TX1",
                        "CAP_TX2",
                        "CAP_SHIELD",
                    ]
                ),
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
                sheet="USB-C Power & Battery Interface",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
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
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
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
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )
            c3 = Component(
                "C",
                package="0603",
                position=(-13.0, -8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1004-1-ND",
                value="10uF",
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )
            mcu_caps = [c1, c2, c3]

            # Autoincrementing Resistors R1..R6
            with Locations([(12.0, -6.0, -0.8), (12.0, -4.5, -0.8)]):
                r_pullups = Component(
                    "R",
                    package="0402",
                    mpn="RC0402FR-074K7L",
                    supplier_pn="311-4.7KLRCT-ND",
                    layer="B.Cu",
                    value="4.7k",
                    sheet="Capacitive Sensing & Control (Azoteq IQS7222A)",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            r1, r2 = r_pullups[0], r_pullups[1]

            with Locations([(-17.0, -4.5, 0.8), (-17.0, 4.5, 0.8)]):
                r_cc = Component(
                    "R",
                    package="0402",
                    mpn="RC0402FR-075K1L",
                    supplier_pn="311-5.1KLRCT-ND",
                    value="5.1k",
                    sheet="USB-C Power & Battery Interface",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            r3, r4 = r_cc[0], r_cc[1]

            with Locations([(-8.0, 8.0, 0.8), (-9.0, -12.0, 0.8)]):
                r_boot = Component(
                    "R",
                    package="0402",
                    mpn="RC0402FR-0710KL",
                    supplier_pn="311-10.0KLRCT-ND",
                    value="10k",
                    sheet="Microcontroller Core, Clock & Reset",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            r5, r6 = r_boot[0], r_boot[1]

            # Autoincrementing Capacitors C4..C14
            with Locations([(8.0, 8.0, 0.8), (-6.0, -9.0, 0.8)]):
                c_bulk = Component(
                    "C",
                    package="0402",
                    mpn="CC0402KRX7R9BB104",
                    supplier_pn="311-1438-1-ND",
                    value="0.1uF",
                    sheet="Microcontroller Core, Clock & Reset",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            c4, c5 = c_bulk[0], c_bulk[1]

            c6 = Component(
                "C",
                package="0603",
                position=(-24.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )
            c7 = Component(
                "C",
                package="0603",
                position=(-14.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A475KP8NNNC",
                supplier_pn="1276-1188-1-ND",
                value="4.7uF",
                sheet="USB-C Power & Battery Interface",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )

            c8 = Component(
                "C",
                package="0603",
                position=(-23.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A105KP8NNNC",
                supplier_pn="1276-1002-1-ND",
                value="1uF",
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )

            with Locations([(-12.0, 2.5, 0.8), (-12.0, 0.0, 0.8)]):
                c_xtal = Component(
                    "C",
                    package="0402",
                    mpn="CC0402JRNPO9BN120",
                    supplier_pn="311-1032-1-ND",
                    value="12pF",
                    sheet="Microcontroller Core, Clock & Reset",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            c9, c10 = c_xtal[0], c_xtal[1]

            c11 = Component(
                "C",
                package="0402",
                position=(-10.5, 8.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CC0402KRX7R9BB104",
                supplier_pn="311-1438-1-ND",
                value="0.1uF",
                sheet="Microcontroller Core, Clock & Reset",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
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
                sheet="Capacitive Sensing & Control (Azoteq IQS7222A)",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )
            c13 = Component(
                "C",
                package="0603",
                position=(-20.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CL10A106KP8NNNC",
                supplier_pn="1276-1004-1-ND",
                value="10uF",
                sheet="USB-C Power & Battery Interface",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
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
                sheet="Capacitive Sensing & Control (Azoteq IQS7222A)",
                pin_sides=PinSideDef(left=["1"], right=["2"]),
            )

            j3 = Component(
                name="J3",
                package="USB-C-16P",
                position=(-25.0, 0.0, 0.8),
                rotation=(0.0, 0.0, 270.0),
                mpn="TYPE-C-16P-3MD",
                supplier_pn="6652-TYPE-C-16P-3MDTR-ND",
                sheet="USB-C Power & Battery Interface",
                pin_sides=PinSideDef(
                    left=["VBUS", "VBUS2", "SHIELD1", "SHIELD2"],
                    right=["GND", "GND2", "CC1", "CC2"],
                ),
            )
            u3 = Component(
                name="U3",
                package="SOT-23-5",
                position=(-19.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="AP2112K-3.3TRG1",
                supplier_pn="AP2112K-3.3-ND",
                sheet="3.3V Power Regulation & Distribution",
                pin_sides=PinSideDef(left=["1", "2", "3"], right=["4", "5"]),
            )
            u4 = Component(
                name="U4",
                package="QFN-16-AMP",
                position=(-18.0, 21.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX98357AETE+",
                supplier_pn="MAX98357A-ND",
                sheet="Audio Subsystem",
                pin_sides=PinSideDef(
                    left=["BCLK", "DIN", "LRCLK", "SD_MODE", "VDD", "GND", "GAIN"],
                    right=["OUTP", "OUTN"],
                ),
            )
            u5 = Component(
                name="U5",
                package="piezo_speaker_12mm",
                position=(-18.0, 31.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CPT-1207-5LTH-T",
                supplier_pn="2223-CPT-1207-5LTH-T-ND",
                sheet="Audio Subsystem",
                pin_sides=PinSideDef(left=["1", "2"]),
            )
            y1 = Component(
                name="Y1",
                package="XTAL-3225-4P",
                position=(-9.0, 1.25, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="ECS-240-8-30B-CKM",
                supplier_pn="XC1842CT-ND",
                sheet="Microcontroller Core, Clock & Reset",
                pin_sides=PinSideDef(left=["1", "3"], right=["2", "4"]),
            )
            j5 = Component(
                name="J5",
                package="pin_header_2x5_1.27mm",
                position=(-18.0, -15.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="FTSH-105-01-L-DV-K",
                supplier_pn="SAMTEC-FTSH105-ND",
                sheet="Telemetry & Debug Communications",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5"]),
            )
            j6 = Component(
                name="J6",
                package="JST-PH-6P",
                position=(24.5, 32.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
                sheet="I2C Peripheral Expansion Interface (J6)",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5", "6"]),
            )
            j7 = Component(
                name="J7",
                package="JST-PH-6P",
                position=(24.5, 17.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
                sheet="I3C Primary Controller Expansion Interface (J7)",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5", "6"]),
            )
            j8 = Component(
                name="J8",
                package="JST-PH-6P",
                position=(24.5, 2.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B6B-PH-K-S",
                supplier_pn="455-1708-ND",
                sheet="I3C Secondary Controller Expansion Interface (J8)",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5", "6"]),
            )
            j9 = Component(
                name="J9",
                package="JST-PH-7P",
                position=(24.5, -14.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    Pin("1", "SPI0_CS_N", signal_name="SPI0_CS_N"),
                    Pin("2", "SPI0_MISO", signal_name="SPI0_MISO"),
                    Pin("3", "SPI0_MOSI", signal_name="SPI0_MOSI"),
                    Pin("4", "SPI0_SCK", signal_name="SPI0_SCK"),
                    Pin("5", "EXP_INT_SPI", signal_name="EXP_INT_SPI"),
                    Pin("6", "PERIPH_3V3", signal_name="PERIPH_3V3"),
                    Pin("7", "GND", signal_name="GND"),
                ],
                sheet="SPI Master Expansion Interface (J9)",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5", "6", "7"]),
            )
            j10 = Component(
                name="J10",
                package="JST-PH-7P",
                position=(24.5, -31.0, 0.8),
                rotation=(0.0, 0.0, -90.0),
                mpn="B7B-PH-K-S",
                supplier_pn="455-1709-ND",
                pins=[
                    Pin("1", "GND", signal_name="GND"),
                    Pin("2", "PERIPH_3V3", signal_name="PERIPH_3V3"),
                    Pin("3", "DTR_N", signal_name="DTR_N"),
                    Pin("4", "CBUS2", signal_name="CBUS2"),
                    Pin("5", "CBUS4", signal_name="CBUS4"),
                    Pin("6", "DCD_N", signal_name="DCD_N"),
                    Pin("7", "DSR_N", signal_name="DSR_N"),
                ],
                sheet="UART & Control Expansion Interface (J10)",
                pin_sides=PinSideDef(left=["3", "4", "5", "6", "7"], right=["1", "2"]),
            )
            j14 = Component(
                name="J14",
                package="pin_header_1x10",
                position=(19.0, -28.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="TSW-110-07-L-S",
                supplier_pn="SAM1034-10-ND",
                pins=[
                    Pin("1", "GPIO0", signal_name="GPIO0"),
                    Pin("2", "GPIO1", signal_name="GPIO1"),
                    Pin("3", "GPIO2", signal_name="GPIO2"),
                    Pin("4", "GPIO3", signal_name="GPIO3"),
                    Pin("5", "3V3", signal_name="3V3"),
                    Pin("6", "GND", signal_name="GND"),
                    Pin("7", "CBUS7", signal_name="CBUS7"),
                    Pin("8", "CBUS5", signal_name="CBUS5"),
                    Pin("9", "CBUS6", signal_name="CBUS6"),
                    Pin("10", "CBUS3", signal_name="CBUS3"),
                ],
                sheet="General Purpose I/O Expansion Header",
                pin_sides=PinSideDef(left=["1", "2", "3", "4", "5", "6"], right=["7", "8", "9", "10"]),
            )
            u8 = Component(
                name="U8",
                package="WSON-8",
                position=(15.0, 4.0, 0.8),
                rotation=(0.0, 0.0, 90.0),
                mpn="W25N01GVZEIG",
                supplier_pn="W25N01GVZEIG-ND",
                sheet="External Serial NAND Storage Subsystem",
                pin_sides=PinSideDef(left=["1", "6", "5", "2", "3", "7"], right=["8", "4"]),
            )
            u6 = Component(
                name="U6",
                package="TSSOP-16",
                position=(14.0, 14.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="LP5009PWR",
                supplier_pn="296-LP5009PWR-ND",
                sheet="User Interface & Status Indication",
                pin_sides=PinSideDef(left=["1", "2", "5", "3", "4", "15"], right=["6", "7", "8", "16"]),
            )
            d1 = Component(
                name="D1",
                package="LED_RGB_4P",
                position=(17.0, 10.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="CLV1A-FKB-CK1VW1DE1BB7C3C3",
                supplier_pn="CLV1A-FKB-CK1VW1DE1BB7C3C3CT-ND",
                sheet="User Interface & Status Indication",
                pin_sides=PinSideDef(left=["1", "2", "3", "4"]),
            )
            u7 = Component(
                name="U7",
                package="TDFN-8",
                position=(-16.0, 16.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="MAX17048G+T10",
                supplier_pn="MAX17048G+T10-ND",
                sheet="USB-C Power & Battery Interface",
                pin_sides=PinSideDef(left=["1", "2", "3", "4"], right=["5", "7", "8"]),
            )
            u9 = Component(
                name="U9",
                package="QFN-32",
                position=(-20.0, -32.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="FT232RNQ-REEL",
                supplier_pn="768-FT232RNQ-REEL-ND",
                schematic_sheets={
                    "Telemetry & Debug Communications": PinSideDef(
                        left=["1", "5", "3", "11"],
                        right=["4", "15", "16", "18", "19", "20", "21", "22", "23", "25", "26", "29", "7"],
                    ),
                    "UART & Control Expansion Interface (J10)": PinSideDef(
                        right=["2", "13", "12", "10", "9"],
                    ),
                },
            )
            u10 = Component(
                name="U10",
                package="SOT-23-5",
                position=(18.0, 24.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="TLV62568DBVR",
                supplier_pn="296-TLV62568DBVR-ND",
                sheet="Peripheral Power Regulation & Gating",
                pin_sides=PinSideDef(left=["3", "1", "2"], right=["5"]),
            )
            sw1 = Component(
                name="SW1",
                package="SW_PUSH_SMD",
                position=(0.0, -11.0, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="PTS645SL43SMTR92LFS",
                supplier_pn="CKN9012CT-ND",
                show_designator=False,
                sheet="Status and Overrides - MCU Reset & Bootloader",
                pin_sides=PinSideDef(left=["1", "2"]),
            )

        with BuildComponents(
            name="status_and_overrides", subassembly="status_and_overrides", parent_part=parent_part
        ) as status_comps:
            with Locations(
                [
                    (10.5, -15.5, 0.8),
                    (10.5, -18.0, 0.8),
                ]
            ):
                jumpers_mcu = Component(
                    "JP",
                    package="pin_header_1x2",
                    mpn="TSW-102-07-L-S",
                    supplier_pn="SAM1026-02-ND",
                    show_designator=False,
                    sheet="Status and Overrides - MCU Reset & Bootloader",
                    pin_sides=PinSideDef(left=["1", "2"]),
                )
            jp1, jp2 = jumpers_mcu[0], jumpers_mcu[1]

            with Locations(
                [
                    (10.5, -21.0, 0.8),
                    (10.5, -23.6, 0.8),
                ]
            ):
                jumpers_boot = Component(
                    "JP",
                    package="pin_header_1x2",
                    mpn="TSW-102-07-L-S",
                    supplier_pn="SAM1026-02-ND",
                    show_designator=False,
                    sheet="Status and Overrides - Power Isolation & Boot Mode",
                    pin_sides=PinSideDef(left=["1", "2"]),
                )
            jp3, jp4 = jumpers_boot[0], jumpers_boot[1]

            with Locations(
                [
                    (4.0, -24.0, 0.8),
                    (4.0, -22.0, 0.8),
                    (4.0, -20.0, 0.8),
                ]
            ):
                leds_pwr = Component(
                    "D2",
                    package="0603",
                    mpn="LTST-C190GKT",
                    supplier_pn="160-1447-1-ND",
                    show_designator=False,
                    sheet="Status and Overrides - Primary Power LEDs",
                    pin_sides=PinSideDef(left=["1", "2"]),
                )
            d2, d3, d4 = leds_pwr[0], leds_pwr[1], leds_pwr[2]

            with Locations(
                [
                    (4.0, -18.0, 0.8),
                    (4.0, -16.0, 0.8),
                    (4.0, -14.0, 0.8),
                ]
            ):
                leds_periph = Component(
                    "D5",
                    package="0603",
                    mpn="LTST-C190GKT",
                    supplier_pn="160-1447-1-ND",
                    show_designator=False,
                    sheet="Status and Overrides - Peripheral & MCU LEDs",
                    pin_sides=PinSideDef(left=["1", "2"]),
                )
            d5, d6, d7 = leds_periph[0], leds_periph[1], leds_periph[2]

            with Locations(
                [
                    (6.5, -24.0, 0.8),
                    (6.5, -22.0, 0.8),
                    (6.5, -20.0, 0.8),
                ]
            ):
                r_leds_pwr = Component(
                    "R",
                    package="0402",
                    mpn="RC0402FR-071KL",
                    supplier_pn="311-1.00KLRCT-ND",
                    value="1k",
                    show_designator=False,
                    sheet="Status and Overrides - Primary Power LEDs",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            r7, r8, r9 = r_leds_pwr[0], r_leds_pwr[1], r_leds_pwr[2]

            with Locations(
                [
                    (6.5, -18.0, 0.8),
                    (6.5, -16.0, 0.8),
                    (6.5, -14.0, 0.8),
                ]
            ):
                r_leds_periph = Component(
                    "R",
                    package="0402",
                    mpn="RC0402FR-071KL",
                    supplier_pn="311-1.00KLRCT-ND",
                    value="1k",
                    show_designator=False,
                    sheet="Status and Overrides - Peripheral & MCU LEDs",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            r10, r11, r12 = r_leds_periph[0], r_leds_periph[1], r_leds_periph[2]

            with Locations(
                [
                    Location((7.0, -35.2, 0.8), (0.0, 0.0, 90.0)),
                    Location((7.0, -37.3, 0.8), (0.0, 0.0, 270.0)),
                ]
            ):
                c_rf = Component(
                    "C18",
                    package="0402",
                    mpn="GRM1555C1H301JA01D",
                    supplier_pn="490-GRM1555C1H301JA01D-ND",
                    value="300pF",
                    sheet="High-Speed BTLE UART & Wireless Interface",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
            c18, c19 = c_rf[0], c_rf[1]

        with BuildComponents(name="rf_interfaces", subassembly="rf_interfaces", parent_part=parent_part) as rf_comps:
            j16 = Component(
                name="J16",
                package="pin_header_1x2",
                position=(13.5, -36.5, 0.8),
                rotation=(0.0, 0.0, 0.0),
                mpn="22-28-4023",
                supplier_pn="WM6402-ND",
                sheet="High-Speed BTLE UART & Wireless Interface",
                pin_sides=PinSideDef(left=["1", "2"]),
            )

    with BuildWiring(name="power_nets") as pwr_nets:
        net_gnd = Net(
            name="GND",
            pins=[
                mcu.pin("VSS"),
                u2.named_pin.VSS,
                c1.pin("2"),
                c2.pin("2"),
                c3.pin("2"),
                u11.pin("GND"),
                j2.pin("GND"),
                j2.pin("MP1"),
                j2.pin("MP2"),
                c18.pin("2"),
                c19.pin("2"),
                j15.pin("3"),
                j15.pin("5"),
                j3.pin("GND"),
                j3.pin("GND2"),
                j3.pin("SHIELD1"),
                j3.pin("SHIELD2"),
                j3.pin("SHIELD3"),
                j3.pin("SHIELD4"),
                r3.pin("2"),
                r4.pin("2"),
                u3.pin("2"),
                c6.pin("2"),
                c7.pin("2"),
                y1.pin("2"),
                y1.pin("4"),
                c9.pin("2"),
                c10.pin("2"),
                c11.pin("2"),
                r6.pin("2"),
                c4.pin("2"),
                c5.pin("2"),
                c12.pin("2"),
                c14.pin("2"),
                u2.pin("EP"),
                j13.pin("2"),
                c13.pin("2"),
                u8.pin("4"),
                u8.pin("EP"),
                u7.pin("1"),
                u7.pin("4"),
                u7.pin("6"),
                u7.pin("EP"),
                u6.pin("3"),
                u6.pin("4"),
                u6.pin("9"),
                u6.pin("10"),
                u6.pin("11"),
                u6.pin("12"),
                u6.pin("13"),
                u6.pin("14"),
                u6.pin("15"),
                u9.pin("7"),
                u9.pin("18"),
                u9.pin("21"),
                u9.pin("25"),
                u9.pin("26"),
                u9.pin("29"),
                u9.pin("EP"),
                j5.pin("3"),
                j5.pin("5"),
                j5.pin("7"),
                j5.pin("8"),
                j5.pin("9"),
                u10.pin("2"),
                u4.pin("GND"),
                u4.pin("GAIN"),
                c8.pin("2"),
                j6.pin("5"),
                j6.pin("6"),
                j7.pin("5"),
                j7.pin("6"),
                j8.pin("5"),
                j8.pin("6"),
                j9.pin("7"),
                j10.pin("1"),
                j14.pin("6"),
                sw1.pin("2"),
                r7.pin("2"),
                r8.pin("2"),
                r9.pin("2"),
                r10.pin("2"),
                r11.pin("2"),
                r12.pin("2"),
                sw2.pin("2"),
            ],
            color="#475569",
        )
        net_3v3 = Net(
            name="3V3",
            pins=[
                mcu.pin("H8"),
                u2.pin("VDD"),
                u2.pin("MCLR"),
                u11.pin("3V3"),
                u11.pin("VCC"),
                j2.pin("3V3"),
                r1.pin("1"),
                r2.pin("1"),
                c1.pin("1"),
                c2.pin("1"),
                c3.pin("1"),
                u3.pin("5"),
                c7.pin("1"),
                u4.pin("VDD"),
                c8.pin("1"),
                r5.pin("1"),
                c4.pin("1"),
                c5.pin("1"),
                u8.pin("8"),
                u7.pin("3"),
                u6.pin("5"),
                u6.pin("16"),
                d1.pin("4"),
                u9.pin("4"),
                u9.pin("19"),
                j5.pin("1"),
                u10.pin("1"),
                j14.pin("5"),
                jp3.pin("1"),
                d4.pin("1"),
                d7.pin("1"),
                j15.pin("1"),
            ],
            color="#dc2626",
        )
        net_vbus = Net(
            name="VBUS",
            pins=[j3.pin("VBUS"), j3.pin("VBUS2"), u9.pin("20"), jp4.pin("1"), d3.pin("1")],
            color="#b91c1c",
            priority=24,
        )
        net_vbat = Net(
            name="VBAT",
            pins=[j13.pin("1"), c13.pin("1"), u3.pin("4"), u7.pin("2"), d2.pin("1")],
            color="#f59e0b",
            priority=24,
        )
        net_periph_3v3 = Net(
            name="PERIPH_3V3",
            pins=[
                u10.pin("5"),
                j6.pin("1"),
                j7.pin("1"),
                j8.pin("1"),
                j9.pin("6"),
                j10.pin("2"),
                d6.pin("1"),
            ],
            color="#dc2626",
            priority=25,
        )

    with BuildWiring(name="signal_nets") as sig_nets:
        Net(
            name="VBUS_CHG",
            pins=[u3.pin("1"), u3.pin("3"), c6.pin("1"), jp4.pin("2")],
            color="#b91c1c",
            priority=24,
        )
        Net(name="CC1", pins=[j3.pin("CC1"), r3.pin("1")], color="#0284c7", priority=53)
        Net(name="CC2", pins=[j3.pin("CC2"), r4.pin("1")], color="#0284c7", priority=54)
        Net(
            name="AUDIO_EN",
            pins=[mcu.pin("L4"), u4.pin("SD_MODE"), d5.pin("1")],
            color="#ea580c",
            priority=16,
        )
        Net(name="PERIPH_EN", pins=[mcu.pin("L5"), u10.pin("3")], color="#ea580c", priority=24)
        Net(name="EXP_INT_I2C", pins=[mcu.pin("B2"), j6.pin("2")], color="#84cc16", priority=19)
        Net(name="EXP_INT_I3C", pins=[mcu.pin("B8"), j7.pin("2")], color="#84cc16", priority=20)
        Net(name="EXP_INT_I3C1", pins=[mcu.pin("E4"), j8.pin("2")], color="#84cc16", priority=21)
        Net(name="EXP_INT_SPI", pins=[mcu.pin("T8"), j9.pin("5")], color="#84cc16", priority=22)
        Net(name="CAP_INT", pins=[mcu.pin("C4"), u2.pin("RDY")], color="#84cc16", priority=18)
        Net(name="I2C_SCL", pins=[mcu.pin("C5"), u2.pin("SCL"), r2.pin("2")], color="#22c55e", priority=19)
        Net(name="I2C_SDA", pins=[mcu.pin("C6"), u2.pin("SDA"), r1.pin("2")], color="#16a34a", priority=20)
        Net(name="OSC_IN", pins=[mcu.pin("F2"), y1.pin("1"), c9.pin("1")], color="#059669", priority=1)
        Net(name="OSC_OUT", pins=[mcu.pin("F1"), y1.pin("3"), c10.pin("1")], color="#10b981", priority=2)
        Net(
            name="NRST",
            pins=[mcu.pin("F3"), r5.pin("2"), c11.pin("1"), jp1.pin("2"), sw1.pin("1")],
            color="#eab308",
            priority=21,
        )
        Net(name="FTDI_NRST", pins=[u9.pin("23"), jp1.pin("1")], color="#eab308", priority=21)
        Net(name="BOOT0", pins=[mcu.pin("C14"), r6.pin("1"), jp2.pin("2"), jp3.pin("2")], color="#ca8a04")
        Net(name="FTDI_BOOT0", pins=[u9.pin("22"), jp2.pin("1")], color="#ca8a04")
        Net(name="LED_VBAT_K", pins=[d2.pin("2"), r7.pin("1")], color="#f59e0b")
        Net(name="LED_VBUS_K", pins=[d3.pin("2"), r8.pin("1")], color="#b91c1c")
        Net(name="LED_3V3_K", pins=[d4.pin("2"), r9.pin("1")], color="#dc2626")
        Net(name="LED_AUD_K", pins=[d5.pin("2"), r10.pin("1")], color="#ea580c")
        Net(name="LED_PERIPH_K", pins=[d6.pin("2"), r11.pin("1")], color="#dc2626")
        Net(name="LED_MCU_K", pins=[d7.pin("2"), r12.pin("1")], color="#ea580c")
        Net(name="BLE_RX", pins=[mcu.pin("T2"), u11.pin("RXD")], color="#2563eb", priority=9)
        Net(name="BLE_RTS", pins=[mcu.pin("T1"), u11.pin("RTS")], color="#3b82f6", priority=10)
        Net(name="BLE_TX", pins=[mcu.pin("T3"), u11.pin("TXD")], color="#059669", priority=11)
        Net(name="BLE_CTS", pins=[mcu.pin("T4"), u11.pin("CTS")], color="#10b981", priority=12)
        Net(name="BLE_RESET_N", pins=[u11.pin("RESET_N"), sw2.pin("1")], color="#f97316", priority=13)
        Net(name="BLE_SWDCLK", pins=[u11.pin("SWDCLK"), j15.pin("4")], color="#4169e1", priority=13)
        Net(name="BLE_SWDIO", pins=[u11.pin("SWDIO"), j15.pin("2")], color="#1e90ff", priority=14)
        Net(name="NFC1", pins=[u11.pin("NFC1"), c18.pin("1"), j16.pin("1")], color="#8b5cf6", priority=15)
        Net(name="NFC2", pins=[u11.pin("NFC2"), c19.pin("1"), j16.pin("2")], color="#a855f7", priority=16)
        Net(
            name="CAP_SHIELD",
            pins=[u2.pin("CR7"), j2.pin("CAP_SHIELD"), j4.pin("CAP_SHIELD")],
            color="#64748b",
            priority=25,
        )
        Net(name="CAP_TX2", pins=[u2.pin("CR6"), j2.pin("CAP_TX2"), j4.pin("CAP_TX2")], color="#0ea5e9", priority=26)
        Net(name="CAP_TX1", pins=[u2.pin("CR5"), j2.pin("CAP_TX1"), j4.pin("CAP_TX1")], color="#0284c7", priority=27)
        Net(name="CAP_TX0", pins=[u2.pin("CR4"), j2.pin("CAP_TX0"), j4.pin("CAP_TX0")], color="#06b6d4", priority=28)
        Net(name="CAP_RX3", pins=[u2.pin("CR3"), j2.pin("CAP_RX3"), j4.pin("CAP_RX3")], color="#67e8f9", priority=29)
        Net(name="CAP_RX2", pins=[u2.pin("CR2"), j2.pin("CAP_RX2"), j4.pin("CAP_RX2")], color="#38bdf8", priority=30)
        Net(name="CAP_RX1", pins=[u2.pin("CR1"), j2.pin("CAP_RX1"), j4.pin("CAP_RX1")], color="#0369a1", priority=31)
        Net(name="CAP_RX0", pins=[u2.pin("CR0"), j2.pin("CAP_RX0"), j4.pin("CAP_RX0")], color="#0891b2", priority=32)
        Net(name="CAP_CT8", pins=[u2.pin("CT8"), j2.pin("NC3")], color="#0284c7", priority=33)
        Net(name="PDM_CLK", pins=[mcu.pin("G2"), u4.pin("BCLK")], color="#a855f7", priority=13)
        Net(name="PDM_DAT", pins=[mcu.pin("H1"), u4.pin("DIN")], color="#9333ea", priority=14)
        Net(name="PDM_LRCLK", pins=[mcu.pin("J1"), u4.pin("LRCLK")], color="#c084fc", priority=15)
        Net(name="SPK_P", pins=[u4.pin("OUTP"), u5.pin("1")], color="#e11d48")
        Net(name="SPK_N", pins=[u4.pin("OUTN"), u5.pin("2")], color="#be123c")
        Net(name="VREGD", pins=[u2.pin("VREGD"), c12.pin("1")], color="#0891b2")
        Net(name="VREGA", pins=[u2.pin("VREGA"), c14.pin("1")], color="#06b6d4")
        Net(name="I2C0_SCL", pins=[u7.pin("7"), u6.pin("1"), mcu.pin("A10")], color="#22c55e", priority=15)
        Net(name="I2C0_SDA", pins=[u7.pin("8"), u6.pin("2"), mcu.pin("B10")], color="#16a34a", priority=16)
        Net(name="FUEL_ALRT", pins=[u7.pin("5"), mcu.pin("G5")], color="#eab308", priority=24)
        Net(name="LED_R", pins=[u6.pin("6"), d1.pin("1")], color="#ef4444")
        Net(name="LED_G", pins=[u6.pin("7"), d1.pin("2")], color="#22c55e")
        Net(name="LED_B", pins=[u6.pin("8"), d1.pin("3")], color="#3b82f6")
        Net(name="FLEX0_A_CS0_N", pins=[u8.pin("1"), mcu.pin("B17")], color="#6366f1", priority=9)
        Net(name="FLEX0_A_IO2", pins=[u8.pin("3"), mcu.pin("F17")], color="#a5b4fc", priority=10)
        Net(name="FLEX0_A_IO3", pins=[u8.pin("7"), mcu.pin("F16")], color="#c7d2fe", priority=11)
        Net(name="FLEX0_A_IO1", pins=[u8.pin("2"), mcu.pin("F15")], color="#818cf8", priority=12)
        Net(name="FLEX0_A_IO0", pins=[u8.pin("5"), mcu.pin("E14")], color="#4f46e5", priority=13)
        Net(name="FLEX0_A_SCK", pins=[u8.pin("6"), mcu.pin("D14")], color="#4338ca", priority=14)
        Net(name="SWD_CLK", pins=[j5.pin("4"), mcu.pin("A16")], color="#0d9488", priority=9)
        Net(name="SWD_DIO", pins=[j5.pin("2"), mcu.pin("A17")], color="#14b8a6", priority=10)
        Net(name="I2C2_SCL", pins=[j6.pin("4"), mcu.pin("B1")], color="#059669", priority=7)
        Net(name="I2C2_SDA", pins=[j6.pin("3"), mcu.pin("A1")], color="#10b981", priority=8)
        Net(name="I3C1_SCL", pins=[j8.pin("4"), mcu.pin("F4")], color="#0369a1", priority=22)
        Net(name="I3C1_SDA", pins=[j8.pin("3"), mcu.pin("F6")], color="#0284c7", priority=23)
        Net(name="I3C0_SCL", pins=[j7.pin("4"), mcu.pin("A8")], color="#0891b2", priority=17)
        Net(name="I3C0_SDA", pins=[j7.pin("3"), mcu.pin("C8")], color="#06b6d4", priority=18)
        Net(name="SPI0_CS_N", pins=[j9.pin("1"), mcu.pin("R9")], color="#92400e", priority=27)
        Net(name="SPI0_MISO", pins=[j9.pin("2"), mcu.pin("R8")], color="#b45309", priority=28)
        Net(name="SPI0_MOSI", pins=[j9.pin("3"), mcu.pin("T7")], color="#d97706", priority=29)
        Net(name="SPI0_SCK", pins=[j9.pin("4"), mcu.pin("T6")], color="#f59e0b", priority=30)
        Net(name="UART0_CTS", pins=[u9.pin("3"), mcu.pin("F10")], color="#a78bfa", priority=25)
        Net(name="UART0_RTS", pins=[u9.pin("11"), mcu.pin("E10")], color="#6d28d9", priority=26)
        Net(name="UART0_TXD", pins=[u9.pin("5"), mcu.pin("A6")], color="#7c3aed", priority=3)
        Net(name="UART0_RXD", pins=[u9.pin("1"), mcu.pin("B6")], color="#8b5cf6", priority=4)
        Net(name="USB_DP", pins=[u9.pin("15"), j3.pin("DP1")], color="#ec4899", priority=21)
        Net(name="USB_DM", pins=[u9.pin("16"), j3.pin("DN1")], color="#db2777", priority=22)
        Net(name="FTDI_3V3", pins=[u9.pin("17"), u9.pin("24")], color="#f43f5e", priority=25)
        Net(name="DTR_N", pins=[u9.pin("2"), j10.pin("3")], color="#64748b")
        Net(name="DSR_N", pins=[u9.pin("9"), j10.pin("7")], color="#64748b")
        Net(name="DCD_N", pins=[u9.pin("10"), j10.pin("6")], color="#64748b")
        Net(name="CBUS4", pins=[u9.pin("12"), j10.pin("5")], color="#64748b")
        Net(name="CBUS2", pins=[u9.pin("13"), j10.pin("4")], color="#64748b")
        Net(name="CBUS3", pins=[u9.pin("14"), j14.pin("10")], color="#64748b")
        Net(name="CBUS5", pins=[u9.pin("30"), j14.pin("8")], color="#64748b")
        Net(name="CBUS6", pins=[u9.pin("31"), j14.pin("9")], color="#64748b")
        Net(name="CBUS7", pins=[u9.pin("32"), j14.pin("7")], color="#64748b")
        Net(name="OSCI", pins=[u9.pin("27"), u9.pin("28")], color="#64748b")
        Net(name="GPIO0", pins=[j14.pin("1"), mcu.pin("M8")], color="#10b981", priority=33)
        Net(name="GPIO1", pins=[j14.pin("2"), mcu.pin("N8")], color="#10b981", priority=34)
        Net(name="GPIO2", pins=[j14.pin("3"), mcu.pin("N10")], color="#10b981", priority=35)
        Net(name="GPIO3", pins=[j14.pin("4"), mcu.pin("T10")], color="#10b981", priority=38)
    with BuildAssemblyTests(subassembly="carrier_board") as cb_steps:
        TestStep(
            step_id="TEST_CONTINUITY_GND",
            description="Verify solid low-impedance ground plane continuity across all copper layers",
            test_type="continuity",
            net_name=net_gnd.name,
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
            net_name=net_3v3.name,
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
            net_name=net_vbat.name,
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

    with BuildAssemblyTests(subassembly="flex_tail") as flex_steps:
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
            label=LabelModel(text="BTLE Wireless Host", position=[-16.0, 0.0, 0.0], align=["max", "center"]),
            pins=[
                Pin("BLE_RX", label="RX (1Mb/s)", side=PinSide.RIGHT),
                Pin("BLE_TX", label="TX (1Mb/s)", side=PinSide.RIGHT),
                Pin("BLE_RTS", label="RTS", side=PinSide.RIGHT),
                Pin("BLE_CTS", label="CTS", side=PinSide.RIGHT),
                Pin("3V3", label="3V3", side=PinSide.RIGHT),
                Pin("GND", label="GND", side=PinSide.RIGHT),
            ],
        )
        usb_c = Component(
            name="usb_c",
            package="board",
            position=[0.0, -80.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[30.0, 18.0, 1.6],
            color="darkorange",
            label=LabelModel(text="USB-C Source (5V)", position=[0.0, -14.0, 0.0], align=["center", "max"]),
            pins=[
                Pin("VBUS", label="VBUS (5V)", side=PinSide.TOP),
                Pin("CC", label="CC1/CC2", side=PinSide.TOP),
                Pin("USB_D", label="D+/D-", side=PinSide.TOP),
                Pin("GND", label="GND", side=PinSide.TOP),
            ],
        )
        carrier_pcb = Component(
            name="carrier_pcb",
            package="board",
            position=[0.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[60.0, 90.0, 1.6],
            color="forestgreen",
            label=LabelModel(text="Test Board Carrier PCB", position=[0.0, 0.0, 0.0], align=["center", "center"]),
            pins=[
                Pin("BLE_RX", side=PinSide.LEFT),
                Pin("BLE_TX", side=PinSide.LEFT),
                Pin("BLE_RTS", side=PinSide.LEFT),
                Pin("BLE_CTS", side=PinSide.LEFT),
                Pin("BLE_3V3", label="3V3", side=PinSide.LEFT),
                Pin("BLE_GND", label="GND", side=PinSide.LEFT),
                Pin("USB_VBUS", label="VBUS", side=PinSide.BOTTOM),
                Pin("USB_CC", label="CC", side=PinSide.BOTTOM),
                Pin("USB_DATA", label="USB_D", side=PinSide.BOTTOM),
                Pin("USB_GND", label="GND", side=PinSide.BOTTOM),
                Pin("FPC_TX0", label="CAP_TX0", side=PinSide.TOP),
                Pin("FPC_RX0", label="CAP_RX0", side=PinSide.TOP),
                Pin("FPC_TX1", label="CAP_TX1", side=PinSide.TOP),
                Pin("FPC_RX1", label="CAP_RX1", side=PinSide.TOP),
                Pin("FPC_TX2", label="CAP_TX2", side=PinSide.TOP),
                Pin("FPC_RX2", label="CAP_RX2", side=PinSide.TOP),
                Pin("FPC_RX3", label="CAP_RX3", side=PinSide.TOP),
                Pin("FPC_SHIELD", label="SHIELD", side=PinSide.TOP),
                Pin("FPC_GND", label="GND", side=PinSide.TOP),
            ],
        )
        flex_tail = Component(
            name="flex_tail",
            package="board",
            position=[0.0, 85.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            dimensions=[24.0, 54.0, 0.2],
            color="goldenrod",
            label=LabelModel(text="Capacitive Flex Tail Sensor", position=[0.0, 32.0, 0.0], align=["center", "min"]),
            pins=[
                Pin("TX0", label="CH0_TX", side=PinSide.BOTTOM),
                Pin("RX0", label="CH0_RX", side=PinSide.BOTTOM),
                Pin("TX1", label="CH1_TX", side=PinSide.BOTTOM),
                Pin("RX1", label="CH1_RX", side=PinSide.BOTTOM),
                Pin("TX2", label="CH2_TX", side=PinSide.BOTTOM),
                Pin("RX2", label="CH2_RX", side=PinSide.BOTTOM),
                Pin("RX3", label="CH3_PROX", side=PinSide.BOTTOM),
                Pin("SHIELD", label="SHIELD", side=PinSide.BOTTOM),
                Pin("GND", label="GND", side=PinSide.BOTTOM),
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


__all__ = [
    "CarrierBoardPCBListing",
    "build_carrier_board_schematic_config",
    "build_carrier_board_design_rules",
    "build_carrier_board_net_classes",
    "build_carrier_board_flex_zones",
    "build_carrier_board_obstacles",
    "build_carrier_board_capacitive_sensors",
    "build_carrier_board_assembly_test",
    "build_carrier_board_wiring",
    "build_carrier_board_system_wiring",
    "build_carrier_board_pcb_config",
]
