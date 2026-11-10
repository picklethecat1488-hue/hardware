"""Unit tests for declarative build123d PCB context managers, continuous auto-numbering, and symbol table."""

import pytest
from build123d import Locations, BuildLine, Polyline, Line, offset, Side, CenterArc
from model.pcb import BoardType, RouteStyle, SymbolTableEntry, TraceSegmentModel
from provider.pcb import (
    BuildPcb,
    BuildComponents,
    Component,
    BuildWiring,
    Net,
    DiffPair,
    Bus,
    BuildAssemblyTests,
    TestStep,
    BuildTraces,
    Trace,
    make_trace,
    Route,
    BuildDesignRules,
    BuildNetClasses,
    BuildFlexZones,
    BuildObstacles,
    BuildCapacitiveSensors,
    BuildSchematic,
    SchematicConfig,
    SchematicSheet,
    PinSideDef,
    PinSide,
)


def test_build_components_continuous_autonumbering_across_blocks() -> None:
    """Verify continuous auto-incrementing reference designators starting at highest_existing + 1."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildComponents(name="block_1") as b1:
            c1 = Component("R", package="0402", position=(0.0, 0.0, 0.0))
            c2 = Component("R", package="0402", position=(5.0, 0.0, 0.0))
            c3 = Component("C", package="0603", position=(10.0, 0.0, 0.0))

        assert [comp.name for comp in b1.components] == ["R1", "R2", "C1"]

        # Second block should start at R3 and C2
        with BuildComponents(name="block_2") as b2:
            c4 = Component("R", package="0402", position=(15.0, 0.0, 0.0))
            c5 = Component("C", package="0603", position=(20.0, 0.0, 0.0))
            c6 = Component("C", package="0603", position=(25.0, 0.0, 0.0))

        assert [comp.name for comp in b2.components] == ["R3", "C2", "C3"]

        # Third block should start at R4 and C4
        with BuildComponents(name="block_3") as b3:
            c7 = Component("R", package="0402", position=(30.0, 0.0, 0.0))
            c8 = Component("C", package="0603", position=(35.0, 0.0, 0.0))

        assert [comp.name for comp in b3.components] == ["R4", "C4"]

    assert len(pcb.footprints) == 8
    assert [f.name for f in pcb.footprints] == ["R1", "R2", "C1", "R3", "C2", "C3", "R4", "C4"]


def test_build_components_explicit_naming_and_location_list() -> None:
    """Verify explicit designators without auto-numbering and multi-location placement."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildComponents(name="fixed_components") as block:
            mcu = Component(name="MCU_MAIN", package="VFBGA-184", position=(0.0, 0.0, 0.0), auto_number=False)
            assert mcu.name == "MCU_MAIN"

            with Locations((-10.0, 0.0), (10.0, 0.0)):
                leds = Component("D", package="0603")

        assert [comp.name for comp in block.components] == ["MCU_MAIN", "D1", "D2"]


def test_symbol_table_generation_and_metadata() -> None:
    """Verify symbol table tracks declaring block, subassembly, source file, line, and connected nets."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildComponents(name="sensor_block", subassembly="sensing_tail") as blk:
            r1 = Component("R", package="0402", position=(1.0, 2.0, 0.8), value="10k", mpn="TEST-MPN")

        with BuildWiring(name="analog_wiring"):
            Net(name="SENSE_SIG", pins=[["R1", "1"]])
            Net(name="GND", pins=[["R1", "2"]])

    wiring = pcb.wiring
    assert wiring is not None
    sym_table = wiring.symbol_table
    assert "R1" in sym_table

    entry = sym_table["R1"]
    assert isinstance(entry, SymbolTableEntry)
    assert entry.designator == "R1"
    assert entry.block == "sensor_block"
    assert entry.subassembly == "sensing_tail"
    assert entry.package == "0402"
    assert entry.value == "10k"
    assert entry.mpn == "TEST-MPN"
    assert entry.position_mm == (1.0, 2.0, 0.8)
    assert set(entry.connected_nets) == {"SENSE_SIG", "GND"}
    assert entry.source_file is not None
    assert entry.source_line is not None


def test_build_wiring_incremental_net_merging() -> None:
    """Verify multiple BuildWiring blocks merge into unified nets without duplicate pins."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildComponents(name="comps"):
            u1 = Component("U", package="QFN-20", position=(0.0, 0.0, 0.0))
            c1 = Component("C", package="0402", position=(5.0, 0.0, 0.0))
            r1 = Component("R", package="0402", position=(10.0, 0.0, 0.0))

        # First wiring block attaches U1 and C1 to 3V3
        with BuildWiring(name="power_block"):
            Net("3V3", pins=[["U1", "1"], ["C1", "1"]], color="#FF0000")
            Net("GND", pins=[["U1", "2"], ["C1", "2"]], color="#000000")

        # Second wiring block connects R1 to 3V3 and U1 to 3V3 again (deduplication test)
        with BuildWiring(name="pullup_block"):
            Net("3V3", pins=[["R1", "1"], ["U1", "1"]])
            Net("SDA", pins=[["U1", "3"], ["R1", "2"]])

    wiring = pcb.wiring
    assert wiring is not None
    nets_by_name = {n.name: n for n in wiring.nets}

    assert "3V3" in nets_by_name
    assert "GND" in nets_by_name
    assert "SDA" in nets_by_name

    net_3v3 = nets_by_name["3V3"]
    # Verify U1 pin 1 appears only once despite being specified in both blocks
    pin_tuples = [(p[0], str(p[1])) for p in net_3v3.pins]
    assert pin_tuples == [("U1", "1"), ("C1", "1"), ("R1", "1")]
    assert net_3v3.color == "#FF0000"


def test_diff_pair_and_bus_helpers() -> None:
    """Verify DiffPair and Bus helpers construct formatted nets correctly."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildComponents(name="comps"):
            u1 = Component("U", package="QFN-20", position=(0.0, 0.0, 0.0))
            j1 = Component("J", package="USB-C-16P", position=(20.0, 0.0, 0.0))

        with BuildWiring(name="interfaces"):
            DiffPair("USB", p_pins=[["U1", "DP"], ["J1", "DP"]], n_pins=[["U1", "DM"], ["J1", "DM"]])
            Bus("DATA", width=4, pin_map={0: [["U1", "D0"]], 1: [["U1", "D1"]], 2: [["U1", "D2"]], 3: [["U1", "D3"]]})

    wiring = pcb.wiring
    assert wiring is not None
    net_names = {n.name for n in wiring.nets}
    assert "USB_P" in net_names
    assert "USB_N" in net_names
    for i in range(4):
        assert f"DATA{i}" in net_names


def test_route_style_strenum_and_route_primitives() -> None:
    """Verify RouteStyle is a StrEnum and Route generates properly styled segments."""
    assert issubclass(RouteStyle, str)
    assert RouteStyle.STRAIGHT == "straight"
    assert RouteStyle.CHAMFER_45 == "45_deg"
    assert RouteStyle.CURVED == "curved"
    assert RouteStyle.MANHATTAN == "manhattan"

    # Manhattan route
    with BuildTraces(layer="F.Cu", default_width_mm=0.25) as bt:
        Route(
            start_mm=(0.0, 0.0),
            end_mm=(10.0, 10.0),
            style=RouteStyle.MANHATTAN,
            net="TEST_NET",
        )
    assert len(bt.traces) == 3
    assert bt.traces[0].start_mm == (0.0, 0.0)
    assert bt.traces[0].end_mm == (5.0, 0.0)
    assert bt.traces[1].start_mm == (5.0, 0.0)
    assert bt.traces[1].end_mm == (5.0, 10.0)
    assert bt.traces[2].start_mm == (5.0, 10.0)
    assert bt.traces[2].end_mm == (10.0, 10.0)

    # Chamfer 45 route
    with BuildTraces(layer="F.Cu", default_width_mm=0.25) as bt2:
        Route(
            start_mm=(0.0, 0.0),
            end_mm=(10.0, 4.0),
            style=RouteStyle.CHAMFER_45,
            net="TEST_NET",
        )
    assert len(bt2.traces) == 2


def test_build_assembly_tests_under_pcb() -> None:
    """Verify BuildAssemblyTests registers AssemblyTestStepModel and AssemblyTestModel under BuildPcb."""
    from model.pcb import AssemblyTestModel, AssemblyTestStepModel

    # Direct TestStep registration
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildAssemblyTests(subassembly="power_rail") as ts:
            TestStep(
                step_id="TEST_3V3_RAIL",
                description="Verify regulated 3.3V rail",
                test_type="voltage",
                net_name="3V3",
                nominal=3.3,
                tolerance_pct=3.0,
                unit="V",
                stimulus="DC regulation probe",
            )

    cfg = pcb.to_pcb_config()
    assert len(cfg.test_steps) == 1
    step = cfg.test_steps[0]
    assert step.step_id == "TEST_3V3_RAIL"
    assert step.subassembly == "power_rail"
    assert step.nominal == 3.3
    assert step.tolerance_pct == 3.0
    assert step.unit == "V"

    # bat.add(AssemblyTestModel) registration
    test_model = AssemblyTestModel(
        test_fixture="flying_probe",
        pass_criteria="all_steps_within_tolerance",
        subassembly="carrier_board",
        instructions=[
            AssemblyTestStepModel(
                step_id="TEST_CONTINUITY_GND",
                description="Ground plane continuity",
                test_type="continuity",
                nominal=0.05,
                unit="ohm",
            )
        ],
    )
    with BuildPcb(name="test_board_2", board_type=BoardType.RIGID) as pcb2:
        with BuildAssemblyTests() as bat:
            bat.add(test_model)

    assert pcb2.assembly_test == test_model
    assert len(pcb2.test_steps) == 1
    assert pcb2.test_steps[0].step_id == "TEST_CONTINUITY_GND"


def test_build_design_rules_and_net_classes_under_pcb() -> None:
    """Verify BuildDesignRules and BuildNetClasses sub-context managers attach metadata to BuildPcb."""
    from model.pcb import PCBDesignRulesModel, NetClassModel

    rules = PCBDesignRulesModel(
        min_clearance_mm=0.05,
        default_track_width_mm=0.15,
    )
    net_classes = [
        NetClassModel(
            name="RF_50OHM",
            trace_width_mm=0.20,
            clearance_mm=0.25,
        ),
        NetClassModel(
            name="HIGH_SPEED_DIFF",
            trace_width_mm=0.12,
            clearance_mm=0.12,
        ),
    ]

    with BuildPcb(name="rules_board", board_type=BoardType.RIGID) as pcb:
        with BuildDesignRules() as bdr:
            bdr.add(rules)
        with BuildNetClasses() as bnc:
            bnc.add(net_classes)

    assert pcb.design_rules == rules
    assert len(pcb.net_classes) == 2
    assert pcb.net_classes[0].name == "RF_50OHM"
    assert pcb.net_classes[1].name == "HIGH_SPEED_DIFF"


def test_build_flex_zones_obstacles_and_capacitive_sensors() -> None:
    """Verify BuildFlexZones, BuildObstacles, and BuildCapacitiveSensors sub-context managers."""
    from model.pcb import FlexZoneModel, PCBObstacleModel, CapacitiveElectrodeModel

    fz = FlexZoneModel(
        name="tail_flex",
        start_x_mm=10.0,
        length_mm=30.0,
        substrate_thickness_mm=0.05,
        coverlay_thickness_mm=0.025,
        coverlay_color="black",
        min_bend_radius_mm=3.0,
        shape_ref="flex_tail",
    )
    obs = PCBObstacleModel(
        name="U1_CHIP",
        shape="box",
        dimensions_mm=(10.0, 10.0, 1.5),
        position_mm=(0.0, 0.0, 0.8),
    )
    cap = CapacitiveElectrodeModel(
        name="ELECTRODE_0",
        electrode_type="mutual",
        area_mm=(5.0, 10.0),
    )

    with BuildPcb(name="flex_board", board_type=BoardType.RIGID) as pcb:
        with BuildFlexZones() as bfz:
            bfz.add(fz)
        with BuildObstacles() as bo:
            bo.add(obs)
        with BuildCapacitiveSensors() as bcs:
            bcs.add([cap])

    assert len(pcb.flex_zones) == 1
    assert pcb.flex_zones[0].name == "tail_flex"
    assert len(pcb.obstacles) == 1
    assert pcb.obstacles[0].name == "U1_CHIP"
    assert len(pcb.capacitive_sensors) == 1
    assert pcb.capacitive_sensors[0].name == "ELECTRODE_0"


def test_pin_side_def_model_validation_and_mappings() -> None:
    """Verify PinSideDef normalization, side mapping, breakout extraction, and constructors."""
    ps = PinSideDef(
        left=["1", "2"],
        right=["3", "4"],
        top=["5"],
        bottom=["6"],
    )
    side_map = ps.to_side_map()
    assert side_map["1"] == PinSide.LEFT
    assert side_map["2"] == PinSide.LEFT
    assert side_map["3"] == PinSide.RIGHT
    assert side_map["5"] == PinSide.TOP
    assert side_map["6"] == PinSide.BOTTOM
    assert ps.to_breakout_list() == ["1", "2", "3", "4", "5", "6"]

    # Test from_side_map
    reconstructed = PinSideDef.from_side_map(
        {"A": PinSide.LEFT, "B": PinSide.RIGHT, "C": PinSide.TOP, "D": PinSide.BOTTOM}
    )
    assert reconstructed.left == ["A"]
    assert reconstructed.right == ["B"]
    assert reconstructed.top == ["C"]
    assert reconstructed.bottom == ["D"]


def test_build_schematic_and_component_sheet_binding() -> None:
    """Verify Component registers computed designators into referenced SchematicSheets."""
    with BuildSchematic() as sched:
        s1 = SchematicSheet(title="Power Management", description="Power regulator and bulk bypass")
        s2 = SchematicSheet(title="Microcontroller Core", description="Primary MCU and clock")

    with BuildPcb(name="carrier_board", board_type=BoardType.RIGID) as pcb:
        with sched.config:
            with BuildComponents(name="main_components") as comps:
                u1 = Component(
                    "U",
                    package="QFN-20",
                    position=(0.0, 0.0, 0.0),
                    schematic_sheets={
                        "Power Management": PinSideDef(left=["1", "2"], right=["3"]),
                        "Microcontroller Core": PinSideDef(left=["4", "5"], right=["6"]),
                    },
                )
                r1 = Component(
                    "R",
                    package="0402",
                    position=(5.0, 0.0, 0.0),
                    sheet="Power Management",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )
                c1 = Component(
                    "C",
                    package="0402",
                    position=(10.0, 0.0, 0.0),
                    sheet="Microcontroller Core",
                    pin_sides=PinSideDef(left=["1"], right=["2"]),
                )

        with BuildSchematic() as bs:
            bs.add(sched.config)

    # Verify U1, R1 registered to Power Management sheet
    sheet1 = pcb.schematic_sheets[0]
    assert "U1" in sheet1.components
    assert "R1" in sheet1.components
    assert sheet1.pin_sides["U1"]["1"] == PinSide.LEFT
    assert sheet1.pin_sides["U1"]["3"] == PinSide.RIGHT
    assert sheet1.pin_sides["R1"]["1"] == PinSide.LEFT
    assert sheet1.pin_sides["R1"]["2"] == PinSide.RIGHT

    # Verify U1, C1 registered to Microcontroller Core sheet
    sheet2 = pcb.schematic_sheets[1]
    assert "U1" in sheet2.components
    assert "C1" in sheet2.components
    assert sheet2.pin_sides["U1"]["4"] == PinSide.LEFT
    assert sheet2.pin_sides["U1"]["6"] == PinSide.RIGHT
    assert sheet2.pin_sides["C1"]["1"] == PinSide.LEFT
    assert sheet2.pin_sides["C1"]["2"] == PinSide.RIGHT


def test_make_trace_declarative_routing_and_offset() -> None:
    """Verify make_trace converts BuildLine polylines, branches, offsets, and curves into TraceSegmentModels."""
    with BuildTraces(default_layer="F.Cu", default_width_mm=0.15) as bt:
        # 1. Polyline and branches
        with BuildLine():
            Polyline((0.0, 0.0), (10.0, 0.0), (10.0, 5.0))
            Line((10.0, 0.0), (10.0, -5.0))
            segs_trunk = make_trace("NET_A")

        assert len(segs_trunk) == 3
        assert all(s.net == "NET_A" for s in segs_trunk)
        assert all(s.layer == "F.Cu" for s in segs_trunk)
        assert all(s.width_mm == 0.15 for s in segs_trunk)

        # 2. Offset inside BuildLine using build123d offset(..., closed=False)
        with BuildLine():
            Polyline((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
            offset(amount=0.20, side=Side.LEFT, closed=False)
            segs_offset = make_trace("NET_B")

        assert len(segs_offset) >= 2
        assert all(s.net == "NET_B" for s in segs_offset)

        # 3. Direct offset_mm parameter on make_trace
        with BuildLine():
            Polyline((0.0, 0.0), (5.0, 0.0), (5.0, 5.0))
            segs_param = make_trace("NET_C", offset_mm=0.15, side=Side.RIGHT)

        assert len(segs_param) >= 2
        assert all(s.net == "NET_C" for s in segs_param)

        # 4. Trace class within BuildLine inherits context line
        with BuildLine():
            Polyline((0.0, 0.0), (2.0, 2.0))
            tr = Trace("NET_D", layer="B.Cu", width_mm=0.25)

        assert len(tr.segments) == 1
        assert tr.segments[0].net == "NET_D"
        assert tr.segments[0].layer == "B.Cu"
        assert tr.segments[0].width_mm == 0.25

        # 5. Curved arc discretization
        with BuildLine():
            CenterArc(center=(0.0, 0.0), radius=5.0, start_angle=0.0, arc_size=90.0)
            segs_arc = make_trace("NET_E")

        assert len(segs_arc) >= 4
        assert all(s.net == "NET_E" for s in segs_arc)

    # Verify all segments registered into parent BuildTraces context
    total_expected = len(segs_trunk) + len(segs_offset) + len(segs_param) + len(tr.segments) + len(segs_arc)
    assert len(bt.traces) == total_expected


def test_flex_tail_declarative_routing_equivalence() -> None:
    """Verify get_flex_tail_traces generates all 54 trace segments across 7 nets matching specifications."""
    from projects.carrier_board.flex_tail import get_flex_tail_traces

    traces = get_flex_tail_traces()
    assert len(traces) == 54, f"Expected 54 trace segments, got {len(traces)}"

    # Verify all 7 nets are present with expected counts
    net_counts = {}
    for t in traces:
        assert isinstance(t, TraceSegmentModel)
        assert t.layer == "F.Cu"
        assert t.width_mm == 0.15
        assert t.start_mm != t.end_mm
        net_counts[t.net] = net_counts.get(t.net, 0) + 1

    expected_net_counts = {
        "CAP_TX2": 8,
        "CAP_TX1": 9,
        "CAP_TX0": 8,
        "CAP_RX0": 4,
        "CAP_RX1": 8,
        "CAP_RX2": 10,
        "CAP_RX3": 7,
    }
    assert net_counts == expected_net_counts
