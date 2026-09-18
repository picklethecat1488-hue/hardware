"""Test Board rigid-flex PCB and enclosure geometry provider."""

from pathlib import Path
from typing import cast, Callable, Sequence, Any, Optional
from functools import cached_property
from build123d import (
    BuildPart,
    Box,
    Cylinder,
    fillet,
    Locations,
    Axis,
    Mode as BuildMode,
    add,
)
from model import Wiring
from model.pcb import (
    LayerType,
    MountingHoleModel,
    SilkscreenTextModel,
    TraceSegmentModel,
    ViaModel,
)
from provider import (
    Provider,
    discover_provider,
    Room,
    Mode,
    WiringDiagram,
    BuildSilkscreen,
    SilkscreenText,
    BuildStackup,
    StackupLayer,
    BuildDrillHoles,
    MountingHole,
    BuildCopperRegions,
    CopperRegion,
    BuildTestPoints,
    TestPoint,
    BuildTraces,
    Trace,
    BuildVias,
    Via,
)
from projects_config import TestBoardConfig


@discover_provider
class TestBoardProvider(Provider):
    """Provider for 6-layer rigid-flex test board and enclosure geometry."""

    __test__ = False

    @cached_property
    def default_config(self) -> TestBoardConfig:
        """Return the default configuration for the test board project."""
        measurements_file = str(Path(__file__).parent / "measurements.yaml")
        return TestBoardConfig(measurements_path=measurements_file)

    @property
    def settings(self) -> TestBoardConfig:
        """Return typed configuration settings."""
        return cast(TestBoardConfig, super().settings)

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

    def carrier_board(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the rigid 6-layer carrier board substrate with rounded corners and mounting holes."""
        w = self.settings.board_width
        length = self.settings.board_length
        thickness = self.settings.board_thickness
        r_corner = self.settings.corner_radius
        hole_dia = self.settings.mounting_hole_diameter
        inset = self.settings.mounting_hole_inset

        with BuildPart() as pcb:
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
            for cyl in dh.to_shapes(depth_mm=thickness * 2.0):
                add(cyl, mode=BuildMode.SUBTRACT)

        return pcb

    def flex_tail(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the flexible polyimide sensing tail extending from the carrier board edge."""
        w_tail = self.settings.flex_tail_width
        l_tail = self.settings.flex_tail_length
        t_tail = self.settings.flex_tail_thickness
        length_board = self.settings.board_length

        with BuildPart() as tail:
            # Place flex tail protruding along +Y from the top edge of the board
            y_center = (length_board / 2.0) + (l_tail / 2.0)
            with Locations((0.0, y_center, 0.0)):
                Box(w_tail, l_tail, t_tail)

        return tail

    def silkscreen(self) -> list[SilkscreenTextModel]:
        """Define silkscreen text markings located relative to board geometry using CAD primitives."""
        length_board = self.settings.board_length
        margin = self.settings.silkscreen_margin
        y_top = (length_board / 2.0) - margin
        y_bottom = -(length_board / 2.0) + margin

        with BuildSilkscreen() as silk:
            with Locations((0.0, y_top)):
                SilkscreenText("TEST BOARD CARRIER REV 1.0", layer="F.SilkS", font_size=1.2, thickness=0.18)
            with Locations((0.0, y_bottom)):
                SilkscreenText("LAYER 1-6 RIGID-FLEX", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((0.0, 0.0)):
                SilkscreenText(
                    "BOTTOM SHIELD / GROUND REF", layer="B.SilkS", font_size=1.0, thickness=0.15, mirror=True
                )

            # Global optical fiducials (crosshairs)
            with Locations((-24.0, 38.0), (24.0, -38.0), (-24.0, -38.0)):
                SilkscreenText("+", layer="F.SilkS", font_size=1.5, thickness=0.25)
            with Locations((-24.0, 38.0), (24.0, -38.0), (-24.0, -38.0)):
                SilkscreenText("+", layer="B.SilkS", font_size=1.5, thickness=0.25, mirror=True)

            # Alignment markers for ICs, connectors, and capacitors
            # U1 BGA pin-1 indicator
            with Locations((-7.0, 7.0)):
                SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            # U2 QFN pin-1 indicator
            with Locations((15.0, -12.5)):
                SilkscreenText("• Pin 1", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            # J1 M.2 connector edge alignment markers
            with Locations((-12.0, -38.0), (12.0, -38.0)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)
            # J2 FPC connector alignment markers
            with Locations((-10.0, 39.5), (10.0, 39.5)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)
            # Capacitor polarity and alignment marks
            with Locations((18.0, -22.0), (-12.0, -9.5)):
                SilkscreenText("╶╴", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-8.0, -6.0)):
                SilkscreenText("╶╴", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)

        return silk.texts

    def enclosure_bottom(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the protective lower enclosure shell with mounting standoffs."""
        w = self.settings.board_width + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        length = self.settings.board_length + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        wall = self.settings.enclosure_wall_thickness
        standoff_h = self.settings.standoff_height
        standoff_r = self.settings.standoff_radius
        h_shell = standoff_h + self.settings.board_thickness + 10.0

        with BuildPart() as shell:
            # Outer enclosure box
            Box(w, length, h_shell)
            # Cavity pocket
            w_cavity = w - (2.0 * wall)
            l_cavity = length - (2.0 * wall)
            with Locations((0.0, 0.0, wall)):
                Box(w_cavity, l_cavity, h_shell, mode=BuildMode.SUBTRACT)

            # Corner standoffs
            hole_x = (self.settings.board_width / 2.0) - self.settings.mounting_hole_inset
            hole_y = (self.settings.board_length / 2.0) - self.settings.mounting_hole_inset
            with Locations(
                (hole_x, hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (-hole_x, hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (-hole_x, -hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (hole_x, -hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
            ):
                Cylinder(radius=standoff_r, height=standoff_h)

            # Standoff screw mounting pilot holes
            standoff_hole_r = self.settings.standoff_hole_diameter / 2.0
            standoff_hole_depth = self.settings.standoff_hole_depth
            hole_z = -h_shell / 2.0 + wall + standoff_h - (standoff_hole_depth / 2.0)
            with Locations(
                (hole_x, hole_y, hole_z),
                (-hole_x, hole_y, hole_z),
                (-hole_x, -hole_y, hole_z),
                (hole_x, -hole_y, hole_z),
            ):
                Cylinder(radius=standoff_hole_r, height=standoff_hole_depth, mode=BuildMode.SUBTRACT)

        return shell

    def enclosure_lid(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the top snap enclosure lid with flex tail exit slot."""
        w = self.settings.board_width + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        length = self.settings.board_length + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        wall = self.settings.enclosure_wall_thickness
        slot_w = self.settings.flex_tail_width + 2.0
        slot_t = self.settings.flex_tail_thickness + 1.0

        with BuildPart() as lid:
            Box(w, length, wall)
            # Slot for flex ribbon passage
            slot_y = length / 2.0 - (wall + self.settings.enclosure_clearance)
            with Locations((0.0, slot_y, 0.0)):
                Box(slot_w, wall * 4.0, slot_t, mode=BuildMode.SUBTRACT)

        return lid

    def view_product(self, room: Room, mode: Mode) -> None:
        """Assemble complete rigid-flex PCB and protective housing for 3D inspection."""
        carrier = self.carrier_board("carrier_board", None, mode)
        tail = self.flex_tail("flex_tail", None, mode)
        enclosure = self.enclosure_bottom("enclosure_bottom", None, mode)

        room.add("carrier_board", carrier, color=(0.08, 0.40, 0.20), alpha=1.0)
        room.add("flex_tail", tail, color=(0.85, 0.65, 0.15), alpha=0.9)
        room.add("enclosure_bottom", enclosure, color=(0.15, 0.16, 0.20), alpha=0.4)

    def diagram_product(self, room: Room, targets: Sequence[str], mode: Mode) -> None:
        """Populate product mechanical diagram elements."""
        self.view_product(room, mode)

    def diagram_wiring(self, room: Room, targets: Sequence[str], mode: Mode) -> None:
        """Render electrical netlist and component layout in vector diagram."""
        if self.wiring_path.exists():
            wiring = Wiring(self.wiring_path)
            diagram = WiringDiagram(wiring)
            diagram.build(room)

    @property
    def part(self) -> dict[str, Callable[..., Any]]:
        """Map part names to CAD builder methods."""
        return {
            "carrier_board": self.carrier_board,
            "flex_tail": self.flex_tail,
            "enclosure_bottom": self.enclosure_bottom,
            "enclosure_lid": self.enclosure_lid,
        }

    @property
    def view(self) -> dict[str, Callable[[Room, Mode], None]]:
        """Map view targets to room population functions."""
        return {
            "product": self.view_product,
        }

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """Map diagram targets to render methods."""
        return {
            "product": self.diagram_product,
            "wiring": self.diagram_wiring,
        }

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
            CopperRegion(
                net="GND",
                layer="In4.Cu",
                outline=polygon,
                priority=1,
                clearance_mm=0.25,
            )
        return cr

    def test_points(self) -> BuildTestPoints:
        """Define exposed copper test points for I2C, PCIe, and MIPI using BuildTestPoints."""
        with BuildTestPoints(default_layer="F.Cu", default_diameter_mm=1.0) as tp:
            # I2C test points
            TestPoint("TP_SDA", net="I2C_SDA", at=(12.0, -4.0))
            TestPoint("TP_SCL", net="I2C_SCL", at=(12.0, -6.0))

            # PCIe Gen4 differential pair test points
            TestPoint("TP_TX0_P", net="PCIE_TX0_P", at=(-15.0, -22.0))
            TestPoint("TP_TX0_N", net="PCIE_TX0_N", at=(-13.0, -22.0))
            TestPoint("TP_RX0_P", net="PCIE_RX0_P", at=(-11.0, -22.0))
            TestPoint("TP_RX0_N", net="PCIE_RX0_N", at=(-9.0, -22.0))

            # MIPI display differential pair test points
            TestPoint("TP_D0_P", net="MIPI_DATA0_P", at=(10.0, 22.0))
            TestPoint("TP_D0_N", net="MIPI_DATA0_N", at=(12.0, 22.0))
            TestPoint("TP_CLK_P", net="MIPI_CLK_P", at=(14.0, 22.0))
            TestPoint("TP_CLK_N", net="MIPI_CLK_N", at=(16.0, 22.0))
        return tp

    @cached_property
    def _routed_network(self) -> tuple[list[TraceSegmentModel], list[ViaModel]]:
        """Compute complete routed traces and vias combining manual flex tail routes and auto-routed nets."""
        # 1. Manual flex tail routing using BuildTraces context manager
        with BuildTraces(default_layer="F.Cu", default_width_mm=0.15) as tr:
            Trace("CAP_TX0", start=(1.0, 38.0), end=(1.0, 55.0))
            Trace("CAP_RX0", start=(2.0, 38.0), end=(2.0, 55.0))
            Trace("CAP_TX1", start=(3.0, 38.0), end=(3.0, 65.0))
            Trace("CAP_RX1", start=(4.0, 38.0), end=(4.0, 65.0))
            Trace("CAP_TX2", start=(5.0, 38.0), end=(5.0, 75.0))
            Trace("CAP_RX2", start=(6.0, 38.0), end=(6.0, 75.0))
            Trace("CAP_RX3", start=(7.0, 38.0), end=(7.0, 85.0))
            Trace("CAP_SHIELD", start=(8.0, 38.0), end=(8.0, 85.0))

        flex_traces = list(tr.traces)
        manual_nets = {"CAP_TX0", "CAP_RX0", "CAP_TX1", "CAP_RX1", "CAP_TX2", "CAP_RX2", "CAP_RX3", "CAP_SHIELD"}

        # 2. Automated routing for remaining nets via PCBAutoRouter
        raw_cfg = self.pcb_manifest
        wiring = Wiring(str(self.wiring_path)) if self.wiring_path.exists() else None
        auto_traces: list[TraceSegmentModel] = []
        auto_vias: list[ViaModel] = []
        if raw_cfg and wiring:
            from provider.pcb.router import PCBAutoRouter

            router = PCBAutoRouter(raw_cfg, wiring)
            auto_traces, auto_vias = router.route_all_nets(exclude_nets=manual_nets)

        return flex_traces + auto_traces, auto_vias

    def traces(self) -> list[TraceSegmentModel]:
        """Return routed copper traces for the test board."""
        return self._routed_network[0]

    def vias(self) -> list[ViaModel]:
        """Return interlayer vias for the test board."""
        return self._routed_network[1]

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """Map Modes to configuration handler methods."""
        from projects.test_board.config import config_route

        def _handler(target: str, subassembly: Optional[str]) -> Any:
            if "route" in target:
                return config_route(self, target, subassembly)
            return None

        return {
            Mode.DEFAULT: _handler,
            "default": _handler,
            "route": _handler,
        }
