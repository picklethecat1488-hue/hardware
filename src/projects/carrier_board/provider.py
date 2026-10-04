"""Test Board rigid-flex PCB and enclosure geometry provider."""

from pathlib import Path
from typing import cast, Callable, Sequence, Any, Optional
from functools import cached_property
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
    FontStyle,
)
from model import Wiring, DiagramOptions, DiagramStyle
from model.pcb import (
    BoardType,
    LayerType,
    MountingHoleModel,
    SilkscreenTextModel,
    SilkscreenGraphicModel,
    TraceSegmentModel,
    ViaModel,
)
from provider import (
    Provider,
    discover_provider,
    Room,
    Mode,
    Simulate,
    WiringDiagram,
    BuildSilkscreen,
    SilkscreenText,
    SilkscreenRect,
    SilkscreenLine,
    SilkscreenPolygon,
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
    BuildPcb,
    BuildFlexPCB,
    FlexType,
)
from projects_config import CarrierBoardConfig


@discover_provider
class CarrierBoardProvider(Provider):
    """Provider for 6-layer rigid-flex carrier board and enclosure geometry."""

    __test__ = False

    @cached_property
    def default_config(self) -> CarrierBoardConfig:
        """Return the default configuration for the carrier board project."""
        measurements_file = str(Path(__file__).parent / "measurements.yaml")
        return CarrierBoardConfig(measurements_path=measurements_file)

    @property
    def settings(self) -> CarrierBoardConfig:
        """Return typed configuration settings."""
        return cast(CarrierBoardConfig, super().settings)

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

        pcb_rev = self.pcb_manifest.get("revision", "2.0") if self.pcb_manifest else "2.0"
        with BuildPcb(
            name="carrier_board", board_type=BoardType.RIGID, revision=pcb_rev, stackup=self.stackup()
        ) as pcb:
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

        if hasattr(pcb, "part") and pcb.part is not None:
            pcb.part.label = "carrier_board"
            pcb.part.urdf_label = "carrier_board"
        pcb.label = "carrier_board"
        pcb.urdf_label = "carrier_board"
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

        with BuildFlexPCB(
            name="flex_tail",
            flex_type=FlexType.CAPACITIVE,
            capacitive_sensors=self.pcb_config.capacitive_sensors if self.pcb_config else None,
            outline_polygon=pts,
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

            routing_flex_file = self.wiring_path.parent / "routing_flex.yaml"
            if routing_flex_file.exists():
                from provider.pcb.router import PCBAutoRouter

                f_traces, f_vias = PCBAutoRouter.load_routing_yaml(routing_flex_file)
                with BuildTraces() as bt:
                    bt.add(f_traces)
                with BuildVias() as bv:
                    bv.add(f_vias)

        if hasattr(tail, "part") and tail.part is not None:
            tail.part.label = "flex_tail"
            tail.part.urdf_label = "flex_tail"
        tail.label = "flex_tail"
        tail.urdf_label = "flex_tail"
        return tail

    def enclosure_bottom(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the protective lower enclosure shell with mounting standoffs, fillets, and cutouts."""
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
        r_outer = self.settings.enclosure_corner_radius
        r_inner = self.settings.corner_radius
        w_cavity = w - (2.0 * wall)
        l_cavity = length - (2.0 * wall)

        with BuildPart() as shell:
            # Outer enclosure profile with rounded corners
            with BuildSketch(Plane.XY.offset(-h_shell / 2.0)) as s_outer:
                RectangleRounded(w, length, r_outer)
            extrude(s_outer.sketch, amount=h_shell)

            # Cavity pocket with matching corner fillets
            with BuildSketch(Plane.XY.offset(-h_shell / 2.0 + wall)) as s_inner:
                RectangleRounded(w_cavity, l_cavity, r_inner)
            extrude(s_inner.sketch, amount=h_shell + 1.0, mode=BuildMode.SUBTRACT)

            # Corner standoffs with clip-on mounting posts for carrier PCB (BUG-085)
            hole_x = (self.settings.board_width / 2.0) - self.settings.mounting_hole_inset
            hole_y = (self.settings.board_length / 2.0) - self.settings.mounting_hole_inset
            standoff_top_z = -h_shell / 2.0 + wall + standoff_h
            with Locations(
                (hole_x, hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (-hole_x, hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (-hole_x, -hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
                (hole_x, -hole_y, -h_shell / 2.0 + wall + standoff_h / 2.0),
            ):
                Cylinder(radius=standoff_r, height=standoff_h)

            post_r = self.settings.mounting_post_diameter / 2.0
            flare_r = self.settings.mounting_post_flare_diameter / 2.0
            tip_r = self.settings.mounting_post_tip_diameter / 2.0
            flare_h = self.settings.mounting_post_flare_height
            shaft_h = self.settings.mounting_post_height - flare_h

            # Cylindrical post shafts through PCB mounting holes
            with Locations(
                (hole_x, hole_y, standoff_top_z + shaft_h / 2.0),
                (-hole_x, hole_y, standoff_top_z + shaft_h / 2.0),
                (-hole_x, -hole_y, standoff_top_z + shaft_h / 2.0),
                (hole_x, -hole_y, standoff_top_z + shaft_h / 2.0),
            ):
                Cylinder(radius=post_r, height=shaft_h)

            # Flared retaining heads on top of mounting posts for secure clip-on fit
            with Locations(
                (hole_x, hole_y, standoff_top_z + shaft_h + flare_h / 2.0),
                (-hole_x, hole_y, standoff_top_z + shaft_h + flare_h / 2.0),
                (-hole_x, -hole_y, standoff_top_z + shaft_h + flare_h / 2.0),
                (hole_x, -hole_y, standoff_top_z + shaft_h + flare_h / 2.0),
            ):
                Cone(bottom_radius=flare_r, top_radius=tip_r, height=flare_h)

            # Foot recess indentations on bottom exterior face (BUG-060)
            foot_r = self.settings.enclosure_foot_diameter / 2.0
            foot_depth = self.settings.enclosure_foot_depth
            foot_inset = self.settings.enclosure_foot_inset
            foot_x = (w / 2.0) - foot_inset
            foot_y = (length / 2.0) - foot_inset
            foot_z = -h_shell / 2.0 + (foot_depth / 2.0)
            with Locations(
                (foot_x, foot_y, foot_z),
                (-foot_x, foot_y, foot_z),
                (-foot_x, -foot_y, foot_z),
                (foot_x, -foot_y, foot_z),
            ):
                Cylinder(radius=foot_r, height=foot_depth, mode=BuildMode.SUBTRACT)

            z_carrier = -h_shell / 2.0 + wall + standoff_h + (self.settings.board_thickness / 2.0)

            cutout_r = self.settings.enclosure_cutout_fillet_radius

            # USB-C connector cutout through left exterior wall (aligned with J3 at [-25.0, 0.0, 0.8])
            usb_w = self.settings.enclosure_usb_cutout_width
            usb_h = self.settings.enclosure_usb_cutout_height
            usb_z = -h_shell / 2.0 + wall + standoff_h + (usb_h / 2.0) - 0.5
            with BuildSketch(Plane.YZ.offset(-w / 2.0)) as s_usb:
                with Locations((0.0, usb_z)):
                    RectangleRounded(usb_w, usb_h, cutout_r)
            extrude(s_usb.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # SWD connector cutout through left exterior wall (aligned with J5) (BUG-075, BUG-090)
            swd_y = -15.0
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                if "J5" in comp_map:
                    swd_y = comp_map["J5"].position[1]
            swd_w = self.settings.enclosure_swd_cutout_width
            swd_h = self.settings.enclosure_swd_cutout_height
            swd_z = z_carrier + (self.settings.board_thickness / 2.0) + (swd_h / 2.0) - 0.5
            with BuildSketch(Plane.YZ.offset(-w / 2.0)) as s_swd:
                with Locations((swd_y, swd_z)):
                    RectangleRounded(swd_w, swd_h, cutout_r)
            extrude(s_swd.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # Ventilation slots through left exterior wall between charger (U3) and amplifier (U4) (BUG-077)
            vent_y_center = 15.5
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                if "U3" in comp_map and "U4" in comp_map:
                    vent_y_center = (comp_map["U3"].position[1] + comp_map["U4"].position[1]) / 2.0

            vent_w = self.settings.enclosure_vent_slot_width
            vent_h = self.settings.enclosure_vent_slot_height
            vent_spacing = self.settings.enclosure_vent_slot_spacing
            vent_count = self.settings.enclosure_vent_count
            vent_z = z_carrier + (self.settings.board_thickness / 2.0) + (vent_h / 2.0) - 0.5
            vent_y_offsets = [(-((vent_count - 1) / 2.0) + idx) * vent_spacing for idx in range(vent_count)]
            with BuildSketch(Plane.YZ.offset(-w / 2.0)) as s_vents:
                for dy in vent_y_offsets:
                    with Locations((vent_y_center + dy, vent_z)):
                        RectangleRounded(vent_w, vent_h, min(cutout_r, (vent_w / 2.0) - 0.1))
            extrude(s_vents.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # Flex tail support shelf extending from front exterior wall underneath flex tail (BUG-140, BUG-148)
            shelf_l = self.settings.enclosure_flex_support_length
            shelf_w = self.settings.enclosure_flex_support_width
            shelf_t = wall
            tail_dz = 0.8
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                if "J2" in comp_map and "J4" in comp_map:
                    tail_dz = comp_map["J2"].position[2] - comp_map["J4"].position[2]
            shelf_top_z = z_carrier + tail_dz - 0.05
            shelf_y_start = (length / 2.0) - wall
            shelf_total_l = shelf_l + wall
            shelf_y_center = shelf_y_start + (shelf_total_l / 2.0)
            with BuildSketch(Plane.XY.offset(shelf_top_z - shelf_t)) as s_shelf:
                with Locations((0.0, shelf_y_center)):
                    RectangleRounded(shelf_w, shelf_total_l, cutout_r * 2.0)
            extrude(s_shelf.sketch, amount=shelf_t)

            # Flex tail passage exit slot at front rim (aligned with J2 at [0.0, 38.0, 0.8] and flex tail)
            slot_w = self.settings.flex_tail_width + 2.0
            z_cut_bot = shelf_top_z
            z_cut_top = (h_shell / 2.0) + 0.5
            slot_h = z_cut_top - z_cut_bot
            slot_z = (z_cut_top + z_cut_bot) / 2.0
            with Locations((0.0, length / 2.0, slot_z)):
                Box(slot_w, wall * 3.0, slot_h, mode=BuildMode.SUBTRACT)

            # Flex ribbon support label (BUG-150)
            with BuildSketch(Plane.XY.offset(shelf_top_z)) as s_flex_lbl:
                with Locations((0.0, (length / 2.0) + (shelf_l / 2.0))):
                    Text("FLEX TAIL", font_size=1.5)
            extrude(s_flex_lbl.sketch, amount=-0.3, mode=BuildMode.SUBTRACT)

            # USB connector graphical label (USB trident icon) (BUG-150, BUG-159)
            plane_left = Plane(origin=(-w / 2.0, 0.0, 0.0), x_dir=(0, -1, 0), z_dir=(-1, 0, 0))
            usb_icon_z = (usb_z + (usb_h / 2.0) + (h_shell / 2.0)) / 2.0 + 0.05
            with BuildSketch(plane_left) as s_usb_icon:
                with Locations((0.0, usb_icon_z)):
                    Rectangle(0.35, 1.4)
                    with Locations((0.0, -0.8)):
                        Circle(0.3)
                    with Locations((0.0, 0.7)):
                        Polygon((-0.55, 0.0), (0.55, 0.0), (0.0, 0.65))
                    with Locations((-0.32, -0.15)):
                        Rectangle(0.4, 0.25)
                    with Locations((-0.52, 0.15)):
                        Rectangle(0.25, 0.45)
                    with Locations((-0.52, 0.45)):
                        Circle(0.25)
                    with Locations((0.32, 0.05)):
                        Rectangle(0.4, 0.25)
                    with Locations((0.52, 0.25)):
                        Rectangle(0.25, 0.4)
                    with Locations((0.52, 0.52)):
                        Rectangle(0.42, 0.42)
            extrude(s_usb_icon.sketch, amount=-0.4, mode=BuildMode.SUBTRACT)

            # SWD cutout label (BUG-150, BUG-159)
            with BuildSketch(plane_left) as s_swd_lbl:
                with Locations((-swd_y, swd_z + (swd_h / 2.0) + 1.8)):
                    Text("SWD", font_size=1.6)
            extrude(s_swd_lbl.sketch, amount=-0.4, mode=BuildMode.SUBTRACT)

            # Peripheral cutouts and bus identifiers through right exterior wall (BUG-074, BUG-090, BUG-110, BUG-113, BUG-143)
            # All cutouts have the exact same width, height, and equal spacing apart from each other
            periph_cutout_h = self.settings.enclosure_periph_cutout_height
            periph_cutout_l = self.settings.enclosure_periph_cutout_length
            periph_z = z_carrier + (self.settings.board_thickness / 2.0) + (periph_cutout_h / 2.0) - 0.5
            bus_labels = {"J6": "I2C", "J7": "I3C0", "J8": "I3C1", "J9": "SPI", "J10": "UART"}
            periph_specs = []
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                for des in ("J6", "J7", "J8", "J9", "J10"):
                    if des in comp_map:
                        c = comp_map[des]
                        periph_specs.append((des, c.position[1], periph_cutout_l, bus_labels.get(des, des)))

            with BuildSketch(Plane.YZ.offset(w / 2.0)) as s_periph:
                for _, py, cut_l, _ in periph_specs:
                    with Locations((py, periph_z)):
                        RectangleRounded(cut_l, periph_cutout_h, cutout_r)
            extrude(s_periph.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # Expansion carrier mounting collar with snap-fit retention ridge (BUG-132)
            mount_protrusion = self.settings.enclosure_expansion_mount_protrusion
            mount_wall = self.settings.enclosure_expansion_mount_wall_thickness
            mount_clr = self.settings.enclosure_expansion_mount_clearance
            mount_ridge = self.settings.enclosure_expansion_mount_snap_ridge

            if periph_specs:
                min_py = min(py - cut_l / 2.0 for _, py, cut_l, _ in periph_specs)
                max_py = max(py + cut_l / 2.0 for _, py, cut_l, _ in periph_specs)
                mount_mid_y = (min_py + max_py) / 2.0
                inner_l = (max_py - min_py) + 2.0 * mount_clr
                outer_l = inner_l + 2.0 * mount_wall
                inner_h = periph_cutout_h + 2.0 * mount_clr
                outer_h = inner_h + 2.0 * mount_wall

                with BuildSketch(Plane.YZ.offset(w / 2.0)) as s_mount:
                    with Locations((mount_mid_y, periph_z)):
                        RectangleRounded(outer_l, outer_h, cutout_r + mount_wall)
                        RectangleRounded(inner_l, inner_h, cutout_r, mode=BuildMode.SUBTRACT)
                extrude(s_mount.sketch, amount=mount_protrusion)

                # Outer snap-fit retention ridge (bead) on top and bottom faces of collar
                ridge_h = mount_ridge
                ridge_w = 1.0
                ridge_x = (w / 2.0) + mount_protrusion - (ridge_w / 2.0) - 0.2
                with Locations((ridge_x, mount_mid_y, periph_z + (outer_h / 2.0) + (ridge_h / 2.0))):
                    Box(ridge_w, outer_l - 2.0 * cutout_r, ridge_h)
                with Locations((ridge_x, mount_mid_y, periph_z - (outer_h / 2.0) - (ridge_h / 2.0))):
                    Box(ridge_w, outer_l - 2.0 * cutout_r, ridge_h)

            # Matching snap-fit retaining grooves on inner cavity walls (BUG-076)
            groove_depth = self.settings.enclosure_snap_groove_depth
            groove_len = self.settings.enclosure_snap_groove_length
            groove_h = self.settings.enclosure_snap_groove_height
            snap_z_bottom = (h_shell / 2.0) - (self.settings.enclosure_lip_height / 2.0)
            snap_y_positions = (-28.0, 28.0)
            for sy in snap_y_positions:
                with Locations(((w_cavity / 2.0) + (groove_depth / 2.0), sy, snap_z_bottom)):
                    Box(groove_depth * 2.0, groove_len, groove_h, mode=BuildMode.SUBTRACT)
                with Locations(((-w_cavity / 2.0) - (groove_depth / 2.0), sy, snap_z_bottom)):
                    Box(groove_depth * 2.0, groove_len, groove_h, mode=BuildMode.SUBTRACT)

        # Joint endpoints for expansion carrier mounting and peripheral connectors (BUG-132)
        if periph_specs:
            mount_x_tip = (w / 2.0) + mount_protrusion
            RigidJoint("expansion_carrier_mount", shell.part, Location((mount_x_tip, mount_mid_y, periph_z)))
            RigidJoint("expansion_mount", shell.part, Location((mount_x_tip, mount_mid_y, periph_z)))
            RigidJoint("connector_endpoint", shell.part, Location((mount_x_tip, mount_mid_y, periph_z)))
            for des, py, _, _ in periph_specs:
                RigidJoint(f"{des.lower()}_mount", shell.part, Location((mount_x_tip, py, periph_z)))
                RigidJoint(f"{des}_mount", shell.part, Location((mount_x_tip, py, periph_z)))

        return shell

    def enclosure_lid(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build the top snap enclosure lid with flex tail exit slot and locating rim."""
        w = self.settings.board_width + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        length = self.settings.board_length + 2.0 * (
            self.settings.enclosure_clearance + self.settings.enclosure_wall_thickness
        )
        wall = self.settings.enclosure_wall_thickness
        w_cavity = w - (2.0 * wall)
        l_cavity = length - (2.0 * wall)
        r_outer = self.settings.enclosure_corner_radius
        r_inner = self.settings.corner_radius
        lip_h = self.settings.enclosure_lip_height
        slot_w = self.settings.flex_tail_width + 2.0

        with BuildPart() as lid:
            with BuildSketch() as s_lid:
                RectangleRounded(w, length, r_outer)
            extrude(s_lid.sketch, amount=wall)

            # Locating rim extending into lower enclosure cavity
            with BuildSketch(Plane.XY) as s_lip:
                RectangleRounded(w_cavity - 0.5, l_cavity - 0.5, r_inner - 0.2)
                RectangleRounded(w_cavity - 3.5, l_cavity - 3.5, max(0.5, r_inner - 1.5), mode=BuildMode.SUBTRACT)
            extrude(s_lip.sketch, amount=-lip_h)

            # Snap-fit ridges on locating rim (BUG-076)
            snap_depth = self.settings.enclosure_snap_ridge_depth
            snap_len = self.settings.enclosure_snap_ridge_length
            snap_h = self.settings.enclosure_snap_ridge_height
            lip_x = (w_cavity - 0.5) / 2.0
            snap_y_positions = (-28.0, 28.0)
            for sy in snap_y_positions:
                with Locations((lip_x + (snap_depth / 2.0), sy, -lip_h / 2.0)):
                    Box(snap_depth, snap_len, snap_h)
                with Locations((-lip_x - (snap_depth / 2.0), sy, -lip_h / 2.0)):
                    Box(snap_depth, snap_len, snap_h)

            # Flex ribbon passage slot at front edge
            with Locations((0.0, length / 2.0, 0.0)):
                Box(slot_w, wall * 3.0, wall * 4.0, mode=BuildMode.SUBTRACT)

            # GPIO breakout cutout through enclosure top (aligned with J14, BUG-073)
            gpio_x, gpio_y = 24.5, -28.0
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                j14_comp = next((c for c in wiring.footprints if c.name == "J14"), None)
                if j14_comp:
                    gpio_x, gpio_y = j14_comp.position[0], j14_comp.position[1]

            gpio_w = self.settings.enclosure_gpio_cutout_width
            gpio_l = self.settings.enclosure_gpio_cutout_length
            with Locations((gpio_x, gpio_y, 0.0)):
                Box(gpio_w, gpio_l, wall * 4.0, mode=BuildMode.SUBTRACT)

            # GPIO key engraved on enclosure lid exterior surface (BUG-073, BUG-177, BUG-189, BUG-208)
            pitch = self.settings.enclosure_gpio_pin_pitch
            lbl_margin = self.settings.enclosure_gpio_label_margin
            hdr_margin = self.settings.enclosure_gpio_header_label_margin
            font_sz = self.settings.enclosure_gpio_label_font_size
            hdr_sz = self.settings.enclosure_gpio_header_font_size
            depth = self.settings.enclosure_gpio_label_depth

            pin_1_y = gpio_y - (4.5 * pitch)
            pin_3v3_y = gpio_y - (0.5 * pitch)
            pin_gnd_y = gpio_y + (0.5 * pitch)
            pin_10_y = gpio_y + (4.5 * pitch)
            label_x = gpio_x - (gpio_w / 2.0) - lbl_margin
            hdr_y = gpio_y + (gpio_l / 2.0) + hdr_margin
            with BuildSketch(Plane.XY.offset(wall)) as s_key:
                with Locations((gpio_x, hdr_y)):
                    Text("GPIO", font_size=hdr_sz, rotation=0.0)
                with Locations((label_x, pin_gnd_y)):
                    Text("GND", font_size=font_sz, rotation=0.0)
                with Locations((label_x, pin_3v3_y)):
                    Text("3V3", font_size=font_sz, rotation=0.0)
                with Locations((label_x + 0.6, pin_1_y)):
                    Text("1", font_size=font_sz, rotation=0.0)
                with Locations((label_x + 0.3, pin_10_y)):
                    Text("10", font_size=font_sz, rotation=0.0)
            extrude(s_key.sketch, amount=-depth, mode=BuildMode.SUBTRACT)

            # Peripheral bus identifier labels engraved on enclosure lid exterior right margin (BUG-160, BUG-177)
            bus_labels = {"J6": "I2C", "J7": "I3C0", "J8": "I3C1", "J9": "SPI", "J10": "UART"}
            periph_lid_specs = []
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                for des in ("J6", "J7", "J8", "J9", "J10"):
                    if des in comp_map:
                        c = comp_map[des]
                        periph_lid_specs.append((c.position[1], bus_labels.get(des, des)))

            if periph_lid_specs:
                with BuildSketch(Plane.XY.offset(wall)) as s_periph_lbl:
                    for py, label in periph_lid_specs:
                        with Locations(((w / 2.0) - 4.5, py)):
                            Text(label, font_size=1.6)
                extrude(s_periph_lbl.sketch, amount=-0.4, mode=BuildMode.SUBTRACT)

            # LED cutout through enclosure top (aligned with D1, BUG-078)
            led_x, led_y = 17.0, 10.0
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                d1_comp = next((c for c in wiring.footprints if c.name == "D1"), None)
                if d1_comp:
                    led_x, led_y = d1_comp.position[0], d1_comp.position[1]

            led_hole_w = self.settings.led_hole_width
            with Locations((led_x, led_y, 0.0)):
                Box(led_hole_w, led_hole_w, wall * 4.0, mode=BuildMode.SUBTRACT)

            # Battery retention cradle on top exterior of enclosure lid, extended over J13 cutout (BUG-090, BUG-145)
            batt_w = self.settings.enclosure_battery_mount_width
            batt_l = self.settings.enclosure_battery_mount_length
            batt_rim_t = self.settings.enclosure_battery_mount_wall_thickness
            batt_rim_h = self.settings.enclosure_battery_mount_wall_height
            batt_x = self.settings.enclosure_battery_mount_x
            batt_y = self.settings.enclosure_battery_mount_y
            j13_x, j13_y = -23.0, 16.0
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                j13_comp = next((c for c in wiring.footprints if c.name == "J13"), None)
                if j13_comp:
                    j13_x, j13_y = j13_comp.position[0], j13_comp.position[1]

            batt_cut_w = self.settings.enclosure_battery_cutout_width
            batt_cut_l = self.settings.enclosure_battery_cutout_length
            cutout_r = self.settings.enclosure_cutout_fillet_radius

            # Unified single rounded rectangle bounding envelope enclosing battery pouch and J13 connector (BUG-145)
            min_x = min(batt_x - (batt_w / 2.0), j13_x - (batt_cut_w / 2.0) - batt_rim_t)
            max_x = max(batt_x + (batt_w / 2.0), j13_x + (batt_cut_w / 2.0) + batt_rim_t)
            min_y = min(batt_y - (batt_l / 2.0), j13_y - (batt_cut_l / 2.0) - batt_rim_t)
            max_y = max(batt_y + (batt_l / 2.0), j13_y + (batt_cut_l / 2.0) + batt_rim_t)

            cradle_w = max_x - min_x
            cradle_l = max_y - min_y
            cradle_cx = (min_x + max_x) / 2.0
            cradle_cy = (min_y + max_y) / 2.0

            with BuildSketch() as s_c_in:
                with Locations((cradle_cx, cradle_cy)):
                    RectangleRounded(cradle_w, cradle_l, cutout_r)

            with BuildSketch() as s_c_out:
                offset(s_c_in.sketch, amount=batt_rim_t)

            with BuildSketch(Plane.XY.offset(wall)) as s_batt:
                add(s_c_out.sketch)
                add(s_c_in.sketch, mode=BuildMode.SUBTRACT)
            extrude(s_batt.sketch, amount=batt_rim_h)

            # Battery connector pass-through cutout through lid (now fully enclosed inside cradle) (BUG-090, BUG-145)
            with BuildSketch(Plane.XY.offset(wall + 1.0)) as s_batt_cut:
                with Locations((j13_x, j13_y)):
                    RectangleRounded(batt_cut_w, batt_cut_l, cutout_r)
            extrude(s_batt_cut.sketch, amount=-(wall + 2.0), mode=BuildMode.SUBTRACT)

            # Battery label (BUG-150, BUG-208, BUG-254)
            batt_cov_clr = self.settings.enclosure_battery_cover_clearance
            batt_cov_t = self.settings.enclosure_battery_cover_wall_thickness
            batt_lbl_margin = self.settings.enclosure_battery_label_margin
            batt_lbl_y = min_y - batt_rim_t - batt_cov_clr - batt_cov_t - batt_lbl_margin
            batt_lbl_fs = self.settings.enclosure_battery_label_font_size
            batt_lbl_off = self.settings.enclosure_battery_label_stroke_offset
            ble_x = self.settings.ble_logo_x
            ble_w = self.settings.ble_logo_width
            max_avail_x = ble_x - (ble_w / 2.0) - 2.5
            batt_lbl_x = (min_x + max_avail_x) / 2.0
            with BuildSketch(Plane.XY.offset(wall)) as s_batt_lbl:
                with Locations((batt_lbl_x, batt_lbl_y)):
                    t_lbl = Text("BATTERY", font_size=batt_lbl_fs, font_style=FontStyle.BOLD)
                    if batt_lbl_off > 0.0:
                        offset(t_lbl, amount=batt_lbl_off)
            extrude(s_batt_lbl.sketch, amount=-0.4, mode=BuildMode.SUBTRACT)

            # Bluetooth logo and text engraved on enclosure lid exterior surface (BUG-214)
            ble_x = self.settings.ble_logo_x
            ble_y = self.settings.ble_logo_y
            ble_depth = self.settings.ble_logo_depth
            with BuildSketch(Plane.XY.offset(wall)) as s_bt_logo:
                with Locations((ble_x, ble_y)):
                    # Bluetooth runic emblem (bindrune Hagall + Bjarkan)
                    Rectangle(0.7, 7.0)
                    Polygon((0, 0), (1.8, 1.8), (1.3, 2.3), (-0.5, 0.5))
                    Polygon((1.8, 1.8), (0, 3.5), (-0.5, 3.0), (1.3, 1.3))
                    Polygon((0, -3.5), (1.8, -1.8), (1.3, -1.3), (-0.5, -3.0))
                    Polygon((1.8, -1.8), (0, 0), (-0.5, -0.5), (1.3, -2.3))
                    Polygon((0, 0), (-1.8, 1.8), (-1.3, 2.3), (0.5, 0.5))
                    Polygon((0, 0), (-1.8, -1.8), (-1.3, -2.3), (0.5, -0.5))
            extrude(s_bt_logo.sketch, amount=-ble_depth, mode=BuildMode.SUBTRACT)

        RigidJoint("led_port", lid.part, Location((led_x, led_y, wall)))
        RigidJoint("battery_mount", lid.part, Location((batt_x, batt_y, wall)))
        RigidJoint("battery_port", lid.part, Location((j13_x, j13_y, wall)))
        RigidJoint("bluetooth_logo", lid.part, Location((ble_x, ble_y, wall)))

        return lid

    def led_cover(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build a translucent push-fit cover/diffuser for the RGB status LED."""
        flange_w = self.settings.led_flange_width
        flange_t = self.settings.led_flange_thickness
        plug_w = self.settings.led_plug_width
        plug_l = self.settings.led_plug_length

        with BuildPart() as cover:
            Box(flange_w, flange_w, flange_t, align=(Align.CENTER, Align.CENTER, Align.MIN))
            fillet(cover.edges().filter_by(Axis.Z), radius=1.0)

            Box(plug_w, plug_w, plug_l, align=(Align.CENTER, Align.CENTER, Align.MAX))

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def battery_cover(self, target: str, subassembly: Optional[str], mode: Mode) -> BuildPart:
        """Build snap-fit battery cover placed over the enclosure lid battery cradle (BUG-139, BUG-145)."""
        batt_w = self.settings.enclosure_battery_mount_width
        batt_l = self.settings.enclosure_battery_mount_length
        cradle_t = self.settings.enclosure_battery_mount_wall_thickness
        cradle_h = self.settings.enclosure_battery_mount_wall_height
        batt_x = self.settings.enclosure_battery_mount_x
        batt_y = self.settings.enclosure_battery_mount_y
        j13_x, j13_y = -23.0, 16.0
        if self.wiring_path.exists():
            wiring = Wiring(str(self.wiring_path))
            j13_comp = next((c for c in wiring.footprints if c.name == "J13"), None)
            if j13_comp:
                j13_x, j13_y = j13_comp.position[0], j13_comp.position[1]
        batt_cut_w = self.settings.enclosure_battery_cutout_width
        batt_cut_l = self.settings.enclosure_battery_cutout_length
        cutout_r = self.settings.enclosure_cutout_fillet_radius

        clr = self.settings.enclosure_battery_cover_clearance
        extra_h = self.settings.enclosure_battery_cover_vertical_clearance
        cover_t = self.settings.enclosure_battery_cover_wall_thickness

        inner_h = cradle_h + extra_h
        total_h = inner_h + cover_t

        min_x = min(batt_x - (batt_w / 2.0), j13_x - (batt_cut_w / 2.0) - cradle_t)
        max_x = max(batt_x + (batt_w / 2.0), j13_x + (batt_cut_w / 2.0) + cradle_t)
        min_y = min(batt_y - (batt_l / 2.0), j13_y - (batt_cut_l / 2.0) - cradle_t)
        max_y = max(batt_y + (batt_l / 2.0), j13_y + (batt_cut_l / 2.0) + cradle_t)

        cradle_w = max_x - min_x
        cradle_l = max_y - min_y
        cradle_cx = (min_x + max_x) / 2.0
        cradle_cy = (min_y + max_y) / 2.0

        with BuildSketch() as s_c_in:
            with Locations((cradle_cx, cradle_cy)):
                RectangleRounded(cradle_w, cradle_l, cutout_r)

        with BuildSketch() as s_c_out:
            offset(s_c_in.sketch, amount=cradle_t)

        with BuildPart() as cover:
            with BuildSketch() as s_outer:
                add(offset(s_c_out.sketch, amount=clr + cover_t))
            extrude(s_outer.sketch, amount=total_h)

            with BuildSketch(Plane.XY.offset(-0.01)) as s_inner:
                add(offset(s_c_out.sketch, amount=clr))
            extrude(s_inner.sketch, amount=inner_h + 0.01, mode=BuildMode.SUBTRACT)

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def view_product(self, room: Room, mode: Mode) -> None:
        """Assemble complete rigid-flex PCB and protective housing for 3D inspection."""
        carrier = self.carrier_board("carrier_board", None, mode)
        tail = self.flex_tail("flex_tail", None, mode)
        enclosure = self.enclosure_bottom("enclosure_bottom", None, mode)
        lid = self.enclosure_lid("enclosure_lid", None, mode)
        cover = self.led_cover("led_cover", None, mode)
        batt_cov = self.battery_cover("battery_cover", None, mode)

        wall = self.settings.enclosure_wall_thickness
        standoff_h = self.settings.standoff_height
        h_shell = standoff_h + self.settings.board_thickness + 10.0
        z_carrier = -h_shell / 2.0 + wall + standoff_h + (self.settings.board_thickness / 2.0)

        carrier_geom = carrier.part.locate(Location((0.0, 0.0, z_carrier)))

        tail_geom: Any = tail
        if self.wiring_path.exists():
            wiring = Wiring(self.wiring_path)
            j2_comp = next(
                (c for c in wiring.footprints if c.name == "J2" or getattr(c, "shape_ref", None) == "carrier_board"),
                None,
            )
            j_flex_comp = next(
                (c for c in wiring.footprints if c.name == "J4" or getattr(c, "shape_ref", None) == "flex_tail"),
                None,
            )
            if j2_comp and j_flex_comp:
                dx = j2_comp.position[0] - j_flex_comp.position[0]
                dy = j2_comp.position[1] - j_flex_comp.position[1]
                dz = j2_comp.position[2] - j_flex_comp.position[2]
                tail_geom = tail.part.locate(Location((dx, dy, z_carrier + dz)))

        z_lid = h_shell / 2.0
        lid_geom = lid.part.locate(Location((0.0, 0.0, z_lid)))

        led_x, led_y = 17.0, 10.0
        if self.wiring_path.exists():
            wiring = Wiring(self.wiring_path)
            d1_comp = next((c for c in wiring.footprints if c.name == "D1"), None)
            if d1_comp:
                led_x, led_y = d1_comp.position[0], d1_comp.position[1]

        cover_geom = cover.part.locate(Location((led_x, led_y, z_lid + wall)))

        batt_cov_geom = batt_cov.part.locate(Location((0.0, 0.0, z_lid + wall + 0.5)))

        room.add("carrier_board", carrier_geom, color=(0.08, 0.40, 0.20), alpha=1.0)
        room.add("flex_tail", tail_geom, color=(0.85, 0.65, 0.15), alpha=0.9)
        room.add("enclosure_bottom", enclosure.part, color=(0.15, 0.16, 0.20), alpha=0.4)
        room.add("enclosure_lid", lid_geom, color=(0.20, 0.22, 0.28), alpha=0.4)
        room.add("led_cover", cover_geom, color=(0.90, 0.95, 1.0), alpha=0.6)
        room.add("battery_cover", batt_cov_geom, color=(0.20, 0.22, 0.28), alpha=0.9)

    def diagram_product(self, room: Room, targets: Sequence[str], mode: Mode) -> None:
        """Populate product mechanical diagram elements."""
        room.diagram_options = DiagramOptions(
            line_weight=1,
            view_from="iso",
            style=DiagramStyle.HIDDEN,
        )
        self.view_product(room, mode)

    def diagram_wiring(self, room: Room, targets: Sequence[str], mode: Mode) -> None:
        """Render top-down system architecture wiring diagram with clean interconnects."""
        room.diagram_options = DiagramOptions(
            line_weight=1,
            view_from="top",
            style=DiagramStyle.COLOR,
            width=1000,
        )
        system_wiring_path = self.wiring_path.parent / "system_wiring.yaml"
        wiring_file = system_wiring_path if system_wiring_path.exists() else self.wiring_path
        if wiring_file.exists():
            wiring = Wiring(wiring_file)
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
            "led_cover": self.led_cover,
            "battery_cover": self.battery_cover,
        }

    def view_carrier_board(self, room: Room, mode: Mode) -> None:
        """Assemble rigid carrier PCB with component obstacles and test points for inspection and simulation."""
        carrier = self.carrier_board("carrier_board", None, mode)
        room.add("carrier_board", carrier.part, color=(0.08, 0.40, 0.20), alpha=1.0)

    def view_flex_tail(self, room: Room, mode: Mode) -> None:
        """Assemble flex tail PCB with sensor pads and test points for inspection and simulation."""
        tail = self.flex_tail("flex_tail", None, mode)
        room.add("flex_tail", tail.part, color=(0.85, 0.65, 0.15), alpha=0.9)

    def view_battery_cover(self, room: Room, mode: Mode) -> None:
        """Render standalone snap-fit battery cover."""
        cover = self.battery_cover("battery_cover", None, mode)
        room.add("battery_cover", cover.part, color=(0.20, 0.22, 0.28), alpha=0.9)

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return flying probe simulation and electrical verification hooks."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)

    @property
    def view(self) -> dict[str, Callable[[Room, Mode], None]]:
        """Map view targets to room population functions."""
        return {
            "product": self.view_product,
            "carrier_board": self.view_carrier_board,
            "flex_tail": self.view_flex_tail,
            "battery_cover": self.view_battery_cover,
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
        """Compute complete routed traces and vias, using persisted routing if available or routing dynamically."""
        from provider.pcb.router import PCBAutoRouter

        # 1. Check for configured or persisted routing file
        routing_file = getattr(self.settings, "routing_path", None)
        if routing_file and Path(routing_file).exists():
            return PCBAutoRouter.load_routing_yaml(routing_file)

        default_routing = self.wiring_path.parent / "routing.yaml"
        if default_routing.exists():
            return PCBAutoRouter.load_routing_yaml(default_routing)

        # 2. Automated routing across all nets via PCBAutoRouter
        base_cfg = self.get_pcb_config_without_routes()
        wiring = Wiring(str(self.wiring_path)) if self.wiring_path.exists() else None
        if base_cfg and wiring:
            router = PCBAutoRouter(base_cfg, wiring)
            return router.route_all_nets()

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

            # BUG-272: Fabrication notes and controlled impedance specification table on Dwgs.User
            with Locations((0.0, 42.0)):
                SilkscreenText(
                    "FAB NOTES: 6-LAYER TG170 ENIG | SOLDERMASK: MATTE BLACK | SILK: WHITE",
                    layer="Dwgs.User",
                    font_size=0.7,
                    thickness=0.1,
                )
            with Locations((0.0, 40.5)):
                SilkscreenText(
                    "IMPEDANCE: 50 OHM SE (L1 W=0.18mm REF L2) | 90 OHM DIFF (L1 W=0.16 S=0.18 REF L2) | 85 OHM DIFF (L1 W=0.18 S=0.15 REF L2)",
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

    @property
    def btle_status_signaling(self) -> dict[str, dict[str, str]]:
        """Return BTLE connection status signaling configuration for RGB LED (D1) and piezo buzzer (U5).

        Status Modes:
            - pairing: LED D1 pulses blue, buzzer U5 emits rising chirp (1kHz -> 2kHz).
              Triggered by capacitive touch input gesture on flex tail or proximity sensor.
            - connected: LED D1 solid cyan, buzzer U5 emits single confirmation tone (2.5kHz).
            - disconnected: LED D1 breathing white, buzzer U5 emits descending tone (2kHz -> 1kHz).
        """
        return {
            "pairing": {
                "led_color": "blue_pulse",
                "buzzer_tone": "chirp_rising_1khz_2khz",
                "trigger": "capacitive_touch_gesture_or_proximity",
            },
            "connected": {
                "led_color": "solid_cyan",
                "buzzer_tone": "confirmation_beep_2.5khz",
                "trigger": "ble_peer_connected",
            },
            "disconnected": {
                "led_color": "breathing_white",
                "buzzer_tone": "descending_tone_2khz_1khz",
                "trigger": "ble_peer_disconnected",
            },
        }

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """Map Modes to configuration handler methods."""
        from projects.carrier_board.config import config_route

        def _handler(target: str, subassembly: Optional[str]) -> Any:
            if "route" in target:
                return config_route(self, target, subassembly)
            return None

        return {
            Mode.DEFAULT: _handler,
            "default": _handler,
            "route": _handler,
        }
