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

    pcb_only_items = assembler.get_display_items(prefix="test_pcb", include_components=False)
    pcb_only_names = [name for _, name, _, _ in pcb_only_items]
    assert "test_pcb_components" not in pcb_only_names
    assert "test_pcb_substrate" in pcb_only_names
    assert "test_pcb_pads" in pcb_only_names
    assert "test_pcb_traces_top" in pcb_only_names
    assert "test_pcb_traces_bottom" in pcb_only_names
    assert "test_pcb_vias" in pcb_only_names


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


def test_pcb_cad_assembler_silkscreen_and_colors():
    """Verify silkscreen text and graphics synthesis and canonical layer colors."""
    from model.pcb import LayerType, SilkscreenGraphicModel, SilkscreenTextModel, StackupLayerModel

    cfg = PCBConfig(
        name="silk_board",
        dimensions_mm=(40.0, 40.0, 1.6),
        stackup=StackupModel(
            layers=[
                StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035, material="copper"),
                StackupLayerModel(name="Core", layer_type=LayerType.DIELECTRIC, thickness_mm=1.53, material="FR4"),
                StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035, material="copper"),
            ],
            finish="ENIG",
            soldermask_color="blue",
            silkscreen_color="white",
        ),
        silkscreen_texts=[
            SilkscreenTextModel(text="CANONICAL", layer="F.SilkS", position=(0.0, 5.0), font_size=1.0),
            SilkscreenTextModel(text="REV 1.0", layer="B.SilkS", position=(0.0, -5.0), font_size=0.8),
        ],
        silkscreen_graphics=[
            SilkscreenGraphicModel(shape="rect", layer="F.SilkS", position=(0.0, 0.0), dimensions=(10.0, 10.0)),
            SilkscreenGraphicModel(
                shape="line", layer="F.SilkS", position=(0.0, 0.0), points=[(-5.0, 0.0), (5.0, 0.0)]
            ),
            SilkscreenGraphicModel(shape="polygon", layer="B.SilkS", points=[(0.0, 0.0), (2.0, 0.0), (1.0, 2.0)]),
        ],
    )

    assembler = PCB3DAssembler(cfg)
    assert assembler.substrate_color == assembler.SOLDERMASK_COLORS["blue"]
    assert assembler.silkscreen_color == assembler.DEFAULT_SILKSCREEN_COLOR

    silk_top = assembler.build_silkscreen("F.SilkS")
    assert silk_top is not None
    assert isinstance(silk_top, Compound)
    # 1 text + 4 rect border boxes + 1 line = 6 shapes
    assert len(silk_top.children) == 6

    silk_bot = assembler.build_silkscreen("B.SilkS")
    assert silk_bot is not None
    assert isinstance(silk_bot, Compound)
    # 1 text + 1 polygon = 2 shapes
    assert len(silk_bot.children) == 2

    display_items = assembler.get_display_items(prefix="silk_board")
    item_dict = {name: (geom, color, alpha) for geom, name, color, alpha in display_items}
    assert "silk_board_silkscreen_top" in item_dict
    assert "silk_board_silkscreen_bottom" in item_dict
    assert item_dict["silk_board_silkscreen_top"][1] == assembler.DEFAULT_SILKSCREEN_COLOR
    assert item_dict["silk_board_substrate"][1] == (0.10, 0.35, 0.65)


def test_regression_bug_jumping_aphid_570_silkscreen_text_unmirrored_orientation():
    """Verify BUG-JUMPING-APHID-570 & BUG-MOTTLED-BUMBLEBEE-555: 3D silkscreen labels and designators are unmirrored."""
    from model.pcb import LayerType, SilkscreenTextModel, StackupLayerModel

    cfg = PCBConfig(
        name="glyph_orientation_board",
        dimensions_mm=(30.0, 30.0, 1.6),
        stackup=StackupModel(
            layers=[
                StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035, material="copper"),
                StackupLayerModel(name="Core", layer_type=LayerType.DIELECTRIC, thickness_mm=1.53, material="FR4"),
                StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035, material="copper"),
            ],
            finish="ENIG",
            soldermask_color="green",
            silkscreen_color="white",
        ),
        silkscreen_texts=[
            SilkscreenTextModel(text="L", layer="F.SilkS", position=(0.0, 0.0), font_size=10.0),
            SilkscreenTextModel(text="L", layer="B.SilkS", position=(0.0, 0.0), font_size=10.0),
        ],
    )
    footprints = [
        FootprintModel(
            name="P",
            package="0402",
            position=(10.0, 10.0, 0.8),
            rotation=(0.0, 0.0, 0.0),
            dimensions=(1.0, 0.5, 0.35),
            layer="F.Cu",
        ),
        FootprintModel(
            name="P",
            package="0402",
            position=(-10.0, -10.0, -0.8),
            rotation=(0.0, 0.0, 0.0),
            dimensions=(1.0, 0.5, 0.35),
            layer="B.Cu",
        ),
    ]
    assembler = PCB3DAssembler(cfg, wiring=Wiring.from_models(footprints=footprints, nets=[]))

    # Glyph "L" has its vertical stem on the left and horizontal foot at the bottom.
    # In right-handed Scope 3D CAD Top view (+Z camera, X_screen = +X_world, Y_screen = +Y_world):
    # - F.SilkS requires center.X < 0 (stem left) and center.Y < 0 (foot bottom, det = +1 unmirrored!).
    silk_top = assembler.build_silkscreen("F.SilkS")
    assert silk_top is not None
    assert len(silk_top.children) == 2  # explicit "L" label + auto-generated "P" reference designator
    top_center = silk_top.children[0].center()
    top_bb = silk_top.bounding_box()
    assert top_center.X < -0.5, f"F.SilkS glyph 'L' mirrored horizontally: center.X={top_center.X}"
    assert top_center.Y < -0.5, f"F.SilkS glyph 'L' reflected/upside-down: center.Y={top_center.Y}"
    assert top_bb.min.Z >= 0.800

    # Auto-generated top designator "P" (vertical stem on left, bowl at top => center.X < 10.0, center.Y > 8.5)
    top_des_center = silk_top.children[1].center()
    assert top_des_center.X < 10.0 and top_des_center.Y > 8.5, (
        f"F.SilkS auto-designator 'P' mirrored: center=({top_des_center.X}, {top_des_center.Y})"
    )

    # In right-handed Scope 3D CAD Bottom view (-Z camera, up = +Y_world => X_screen_bottom = -X_world, Y_screen_bottom = +Y_world):
    # - B.SilkS requires center.X > 0 (so -X_world < 0 = stem left) and center.Y < 0 (foot bottom).
    silk_bot = assembler.build_silkscreen("B.SilkS")
    assert silk_bot is not None
    assert len(silk_bot.children) == 2
    bot_center = silk_bot.children[0].center()
    bot_bb = silk_bot.bounding_box()
    assert bot_center.X > 0.5, f"B.SilkS glyph 'L' mirrored horizontally in bottom view: center.X={bot_center.X}"
    assert bot_center.Y < -0.5, f"B.SilkS glyph 'L' reflected/upside-down in bottom view: center.Y={bot_center.Y}"
    assert bot_bb.max.Z <= -0.800

    # Auto-generated bottom designator "P" at (-10.0, -11.5): stem on bottom-screen left (-X_world < 10 => X_world > -10.0), bowl at top (Y > -11.5)
    bot_des_center = silk_bot.children[1].center()
    assert bot_des_center.X > -10.0 and bot_des_center.Y > -11.5, (
        f"B.SilkS auto-designator 'P' mirrored in bottom view: center=({bot_des_center.X}, {bot_des_center.Y})"
    )


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


def test_regression_bug_spotted_spider_413_copper_traces_and_silkscreen_overlay():
    """Verify BUG-SPOTTED-SPIDER-413: 3D CAD traces render as physical copper wires cleanly overlaid by silkscreen."""
    from model.pcb import SilkscreenTextModel

    cfg = PCBConfig(
        name="copper_overlay_board",
        dimensions_mm=(30.0, 30.0, 1.6),
        traces=[
            TraceSegmentModel(start_mm=(-8.0, 0.0), end_mm=(8.0, 0.0), width_mm=0.2, layer="F.Cu", net="VDD"),
            TraceSegmentModel(start_mm=(-8.0, 2.0), end_mm=(8.0, 2.0), width_mm=0.2, layer="B.Cu", net="GND"),
        ],
        silkscreen_texts=[
            SilkscreenTextModel(text="U1", layer="F.SilkS", position=(0.0, 0.0), font_size=1.2),
            SilkscreenTextModel(text="J1", layer="B.SilkS", position=(0.0, 2.0), font_size=1.2),
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
    assembler = PCB3DAssembler(cfg, wiring=Wiring.from_models(footprints=footprints, nets=[]))

    # 1. In 3D CAD mode (kicad_2d_theme=False), both F.Cu and B.Cu traces must be warm physical copper (R > G > B)
    cad_items = {name: (geom, color) for geom, name, color, _ in assembler.get_display_items(prefix="brd")}
    top_geom, top_col = cad_items["brd_traces_top"]
    bot_geom, bot_col = cad_items["brd_traces_bottom"]
    for trace_col in (top_col, bot_col):
        r, g, b = trace_col
        assert r > 0.75 and 0.40 <= g <= 0.62 and 0.15 <= b <= 0.35 and r > g > b, (
            f"Expected physical warm copper RGB for 3D CAD traces, got {trace_col}"
        )

    # 2. KiCad 2D theme must still preserve red/blue layer distinction when requested
    kicad_items = {name: color for _, name, color, _ in assembler.get_display_items(prefix="brd", kicad_2d_theme=True)}
    assert kicad_items["brd_traces_top"] == assembler.KICAD_TOP_TRACE_COLOR
    assert kicad_items["brd_traces_bottom"] == assembler.KICAD_BOTTOM_TRACE_COLOR

    # 3. Top silkscreen Z-min must sit strictly proud above both top copper traces and top pads
    pads_geom, _ = cad_items["brd_pads"]
    silk_top_geom, _ = cad_items["brd_silkscreen_top"]
    silk_bot_geom, _ = cad_items["brd_silkscreen_bottom"]
    assert silk_top_geom.bounding_box().min.Z > top_geom.bounding_box().max.Z + 0.015
    assert silk_top_geom.bounding_box().min.Z > pads_geom.bounding_box().max.Z + 0.005
    assert silk_bot_geom.bounding_box().max.Z < bot_geom.bounding_box().min.Z - 0.015
