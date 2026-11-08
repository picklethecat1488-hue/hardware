"""Unit tests for declarative build123d PCB context managers, continuous auto-numbering, and symbol table."""

import pytest
from build123d import Locations
from model.pcb import BoardType, RouteStyle, SymbolTableEntry
from provider.pcb import (
    BuildPcb,
    BuildComponents,
    Component,
    BuildWiring,
    Net,
    DiffPair,
    Bus,
    BuildTestSteps,
    TestStep,
    BuildTraces,
    Route,
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


def test_build_test_steps_under_pcb() -> None:
    """Verify BuildTestSteps registers AssemblyTestStepModel under BuildPcb."""
    with BuildPcb(name="test_board", board_type=BoardType.RIGID) as pcb:
        with BuildTestSteps(subassembly="power_rail") as ts:
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
