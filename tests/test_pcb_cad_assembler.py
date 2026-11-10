"""Unit tests for PCB3DAssembler and native PCB CAD viewing."""

import time
import pytest
from build123d import Box, Compound, Solid

from model.pcb import PCBConfig, StackupModel, TraceSegmentModel, ViaModel
from model.wiring import FootprintModel, Wiring
from provider.pcb.board import BuildPcb
from provider.pcb.cad_assembler import PCB3DAssembler
from provider.room import Room


def test_pcb_cad_assembler_empty_config():
    """Verify PCB3DAssembler handles empty config gracefully without errors."""
    cfg = PCBConfig(name="test_board", dimensions_mm=(50.0, 50.0, 1.6))
    assembler = PCB3DAssembler(cfg)

    # Substrate should be built from dimensions
    sub = assembler.build_substrate()
    assert sub is not None
    assert isinstance(sub, (Solid, Compound))

    # Empty layers should return None
    assert assembler.build_traces("F.Cu") is None
    assert assembler.build_traces("B.Cu") is None
    assert assembler.build_vias() is None

    comps, pads = assembler.build_components_and_pads()
    assert comps is None
    assert pads is None

    items = assembler.get_display_items(prefix="test_board")
    assert len(items) == 1
    assert items[0][1] == "test_board_substrate"

    room = Room()
    assembler.populate_room(room, prefix="test_board")
    assert "test_board_substrate" in room

    assy = assembler.to_cad_assembly()
    assert isinstance(assy, Compound)


def test_pcb_cad_assembler_full_layers():
    """Verify PCB3DAssembler synthesizes all 6 distinct layers when data is present."""
    cfg = PCBConfig(
        name="multi_layer_pcb",
        dimensions_mm=(60.0, 40.0, 1.6),
        traces=[
            TraceSegmentModel(
                start_mm=(-10.0, 0.0),
                end_mm=(10.0, 0.0),
                width_mm=0.20,
                layer="F.Cu",
                net="SIG_TOP",
            ),
            TraceSegmentModel(
                start_mm=(0.0, -10.0),
                end_mm=(0.0, 10.0),
                width_mm=0.20,
                layer="B.Cu",
                net="SIG_BOT",
            ),
        ],
        vias=[
            ViaModel(
                position_mm=(5.0, 5.0),
                drill_diameter_mm=0.2,
                pad_diameter_mm=0.45,
                net="GND",
            )
        ],
    )

    footprints = [
        FootprintModel(
            name="R1",
            package="0402",
            position=(0.0, 0.0, 0.8),
            rotation=(0.0, 0.0, 0.0),
            dimensions=(1.0, 0.5, 0.35),
            layer="F.Cu",
        )
    ]
    wiring = Wiring.from_models(footprints=footprints, nets=[])

    assembler = PCB3DAssembler(cfg, wiring=wiring)
    display_items = assembler.get_display_items(prefix="test_pcb")

    layer_names = {name for _, name, _, _ in display_items}
    assert "test_pcb_substrate" in layer_names
    assert "test_pcb_components" in layer_names
    assert "test_pcb_pads" in layer_names
    assert "test_pcb_traces_top" in layer_names
    assert "test_pcb_traces_bottom" in layer_names
    assert "test_pcb_vias" in layer_names

    room = Room()
    assembler.populate_room(room, prefix="test_pcb")
    for name in (
        "test_pcb_substrate",
        "test_pcb_components",
        "test_pcb_pads",
        "test_pcb_traces_top",
        "test_pcb_traces_bottom",
        "test_pcb_vias",
    ):
        assert name in room


def test_build_pcb_populate_room_and_to_cad_assembly():
    """Verify BuildPcb context manager exposes populate_room and to_cad_assembly methods."""
    with BuildPcb(name="demo_board") as pcb:
        Box(40, 30, 1.6)

    room = Room()
    pcb.populate_room(room, prefix="demo_board")
    assert "demo_board_substrate" in room

    assembly = pcb.to_cad_assembly()
    assert isinstance(assembly, Compound)
    assert len(assembly.children) >= 1


@pytest.mark.slow
def test_carrier_board_pcb_3d_assembler_performance():
    """Verify real carrier board 3D CAD assembly synthesizes in under 5.0 seconds."""
    from projects.carrier_board.provider import CarrierBoardProvider

    provider = CarrierBoardProvider()
    cfg = provider.pcb_config
    wiring = provider.wiring

    t0 = time.time()
    assembler = PCB3DAssembler(cfg, wiring=wiring, pcb_name="carrier_board")
    room = Room()
    assembler.populate_room(room, prefix="carrier_board")
    elapsed = time.time() - t0

    # Ensure all layers are present
    assert "carrier_board_substrate" in room
    assert "carrier_board_components" in room
    assert "carrier_board_pads" in room
    assert "carrier_board_traces_top" in room
    assert "carrier_board_traces_bottom" in room
    assert "carrier_board_vias" in room

    # Fast CAD synthesis invariant
    assert elapsed < 5.0, f"PCB 3D synthesis took {elapsed:.2f}s, expected < 5.0s"
