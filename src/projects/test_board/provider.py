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
)
from model import Wiring
from provider import (
    Provider,
    discover_provider,
    Room,
    Mode,
    WiringDiagram,
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

            # Four corner mounting holes
            hole_x = (w / 2.0) - inset
            hole_y = (length / 2.0) - inset
            with Locations(
                (hole_x, hole_y),
                (-hole_x, hole_y),
                (-hole_x, -hole_y),
                (hole_x, -hole_y),
            ):
                Cylinder(radius=hole_dia / 2.0, height=thickness * 2.0, mode=BuildMode.SUBTRACT)

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
