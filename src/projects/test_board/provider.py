"""Test Board rigid-flex PCB and enclosure geometry provider."""

from pathlib import Path
from typing import cast, Callable, Sequence, Any, Optional
from functools import cached_property
from build123d import (
    Align,
    BuildPart,
    BuildSketch,
    Polygon,
    RectangleRounded,
    Plane,
    Location,
    RigidJoint,
    extrude,
    Box,
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
from model.pcb import (
    BoardType,
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
    BuildPcb,
    BuildFlexPCB,
    FlexType,
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

            with BuildTraces() as bt:
                bt.add(self.traces())
            with BuildVias() as bv:
                bv.add(self.vias())

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
                with Locations((-8.0, -21.0)):
                    SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.5, thickness=0.08)
                with Locations((0.0, -6.25)):
                    SilkscreenText("CH0: LOW", layer="F.SilkS", font_size=0.7, thickness=0.10)
                with Locations((0.0, 5.25)):
                    SilkscreenText("CH1: MID", layer="F.SilkS", font_size=0.7, thickness=0.10)
                with Locations((0.0, 16.75)):
                    SilkscreenText("CH2: HIGH", layer="F.SilkS", font_size=0.7, thickness=0.10)
                with Locations((0.0, 24.75)):
                    SilkscreenText("CH3: PROX", layer="F.SilkS", font_size=0.7, thickness=0.10)

            routing_flex_file = self.wiring_path.parent / "routing_flex.yaml"
            if routing_flex_file.exists():
                from provider.pcb.router import PCBAutoRouter

                f_traces, f_vias = PCBAutoRouter.load_routing_yaml(routing_flex_file)
                with BuildTraces() as bt:
                    bt.add(f_traces)
                with BuildVias() as bv:
                    bv.add(f_vias)

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

            # Flex tail passage exit slot at front rim (aligned with J2 at [0.0, 38.0, 0.8] and flex tail)
            slot_w = self.settings.flex_tail_width + 2.0
            z_cut_bot = z_carrier - 1.0
            z_cut_top = (h_shell / 2.0) + 0.5
            slot_h = z_cut_top - z_cut_bot
            slot_z = (z_cut_top + z_cut_bot) / 2.0
            with Locations((0.0, length / 2.0, slot_z)):
                Box(slot_w, wall * 3.0, slot_h, mode=BuildMode.SUBTRACT)

            # M.2 connector cutout through rear exterior wall (aligned with J1 at [0.0, -36.0, 0.8])
            m2_w = self.settings.enclosure_m2_cutout_width
            m2_h = self.settings.enclosure_m2_cutout_height
            m2_z = -h_shell / 2.0 + wall + standoff_h + (m2_h / 2.0) - 0.5
            with BuildSketch(Plane.XZ.offset(-length / 2.0)) as s_m2:
                with Locations((0.0, m2_z)):
                    RectangleRounded(m2_w, m2_h, cutout_r)
            extrude(s_m2.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # Peripheral cutouts and bus identifiers through right exterior wall (BUG-074, BUG-090)
            periph_cutout_h = 5.0
            periph_z = z_carrier + (self.settings.board_thickness / 2.0) + (periph_cutout_h / 2.0) - 0.5
            periph_specs = [
                ("J6", 26.0, 10.5, "I2C"),
                ("J7", 16.0, 10.5, "I3C0"),
                ("J8", 6.0, 10.5, "I3C1"),
                ("J9", -6.0, 15.5, "SPI"),
                ("J10", -17.0, 15.5, "UART"),
            ]
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                comp_map = {c.name: c for c in wiring.footprints}
                for idx, (des, def_y, cut_l, label) in enumerate(periph_specs):
                    if des in comp_map:
                        periph_specs[idx] = (des, comp_map[des].position[1], cut_l, label)

            with BuildSketch(Plane.YZ.offset(w / 2.0)) as s_periph:
                for _, py, cut_l, _ in periph_specs:
                    with Locations((py, periph_z)):
                        RectangleRounded(cut_l, periph_cutout_h, cutout_r)
            extrude(s_periph.sketch, amount=wall * 3.0, both=True, mode=BuildMode.SUBTRACT)

            # Bus identifier labels on exterior right wall
            with BuildSketch(Plane.YZ.offset(w / 2.0)) as s_periph_labels:
                for _, py, _, label in periph_specs:
                    with Locations((py, periph_z + (periph_cutout_h / 2.0) + 1.2)):
                        Text(label, font_size=1.6)
            extrude(s_periph_labels.sketch, amount=-0.3, mode=BuildMode.SUBTRACT)

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

            # GPIO key engraved on enclosure lid exterior surface
            with BuildSketch(Plane.XY.offset(wall)) as s_key:
                with Locations((gpio_x - 4.5, gpio_y)):
                    Text("GPIO", font_size=2.5, rotation=90.0)
                with Locations((gpio_x - 3.5, gpio_y + (gpio_l / 2.0) - 2.0)):
                    Text("10", font_size=1.5, rotation=90.0)
                with Locations((gpio_x - 3.5, gpio_y - (gpio_l / 2.0) + 2.0)):
                    Text("1", font_size=1.5, rotation=90.0)
            extrude(s_key.sketch, amount=-0.4, mode=BuildMode.SUBTRACT)

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

            # Battery retention cradle on top exterior of enclosure lid (BUG-090)
            batt_w = self.settings.enclosure_battery_mount_width
            batt_l = self.settings.enclosure_battery_mount_length
            batt_rim_t = self.settings.enclosure_battery_mount_wall_thickness
            batt_rim_h = self.settings.enclosure_battery_mount_wall_height
            batt_x = self.settings.enclosure_battery_mount_x
            batt_y = self.settings.enclosure_battery_mount_y
            with BuildSketch(Plane.XY.offset(wall)) as s_batt:
                with Locations((batt_x, batt_y)):
                    RectangleRounded(batt_w + (2.0 * batt_rim_t), batt_l + (2.0 * batt_rim_t), 2.0)
                    RectangleRounded(batt_w, batt_l, 1.0, mode=BuildMode.SUBTRACT)
            extrude(s_batt.sketch, amount=batt_rim_h)

            # Battery connector pass-through cutout through lid (aligned with J13, BUG-090)
            j13_x, j13_y = -23.0, 16.0
            if self.wiring_path.exists():
                wiring = Wiring(str(self.wiring_path))
                j13_comp = next((c for c in wiring.footprints if c.name == "J13"), None)
                if j13_comp:
                    j13_x, j13_y = j13_comp.position[0], j13_comp.position[1]

            batt_cut_w = self.settings.enclosure_battery_cutout_width
            batt_cut_l = self.settings.enclosure_battery_cutout_length
            cutout_r = self.settings.enclosure_cutout_fillet_radius
            with BuildSketch(Plane.XY.offset(wall + 1.0)) as s_batt_cut:
                with Locations((j13_x, j13_y)):
                    RectangleRounded(batt_cut_w, batt_cut_l, cutout_r)
            extrude(s_batt_cut.sketch, amount=-(wall + 2.0), mode=BuildMode.SUBTRACT)

        RigidJoint("led_port", lid.part, Location((led_x, led_y, wall)))
        RigidJoint("battery_mount", lid.part, Location((batt_x, batt_y, wall)))
        RigidJoint("battery_port", lid.part, Location((j13_x, j13_y, wall)))

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

    def view_product(self, room: Room, mode: Mode) -> None:
        """Assemble complete rigid-flex PCB and protective housing for 3D inspection."""
        carrier = self.carrier_board("carrier_board", None, mode)
        tail = self.flex_tail("flex_tail", None, mode)
        enclosure = self.enclosure_bottom("enclosure_bottom", None, mode)
        lid = self.enclosure_lid("enclosure_lid", None, mode)
        cover = self.led_cover("led_cover", None, mode)

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

        room.add("carrier_board", carrier_geom, color=(0.08, 0.40, 0.20), alpha=1.0)
        room.add("flex_tail", tail_geom, color=(0.85, 0.65, 0.15), alpha=0.9)
        room.add("enclosure_bottom", enclosure.part, color=(0.15, 0.16, 0.20), alpha=0.4)
        room.add("enclosure_lid", lid_geom, color=(0.20, 0.22, 0.28), alpha=0.4)
        room.add("led_cover", cover_geom, color=(0.90, 0.95, 1.0), alpha=0.6)

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

            # PCIe Gen4 differential pair test points (spaced with 4mm pitch)
            TestPoint("TP5", net="PCIE_TX0_N", at=(-14.0, -22.0))
            TestPoint("TP6", net="PCIE_TX0_P", at=(-10.0, -22.0))
            TestPoint("TP7", net="PCIE_RX0_P", at=(-6.0, -22.0))
            TestPoint("TP8", net="PCIE_RX0_N", at=(-2.0, -22.0))

            # I2C test points (through-hole, accessible from both sides, routed on B.Cu)
            TestPoint("TP9", net="I2C_SDA", at=(14.0, -4.0), layer="B.Cu")
            TestPoint("TP10", net="I2C_SCL", at=(18.0, -4.0), layer="B.Cu")

            # MIPI display differential pair test points (spaced with 4mm pitch on left half of board)
            TestPoint("TP11", net="MIPI_DATA0_P", at=(-14.0, 22.0))
            TestPoint("TP12", net="MIPI_DATA0_N", at=(-10.0, 22.0))
            TestPoint("TP13", net="MIPI_CLK_P", at=(-6.0, 22.0))
            TestPoint("TP14", net="MIPI_CLK_N", at=(-2.0, 22.0))
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

    def silkscreen(self) -> list[SilkscreenTextModel]:
        """Return silkscreen markings for the test board carrier."""
        with BuildSilkscreen() as silk:
            # Top logo in empty space between connector J2 and carrier title (BUG-092)
            with Locations((0.0, 31.0)):
                SilkscreenText("ANTIGRAVITY", layer="F.SilkS", font_size=1.6, thickness=0.25)

            # Position silkscreen markings cleanly clear of connector J2 (Y=38) and connector J1 (Y=-36)
            with Locations((0.0, 26.0)):
                SilkscreenText("TEST BOARD CARRIER REV 2.0", layer="F.SilkS", font_size=1.2, thickness=0.18)
            with Locations((0.0, -28.0)):
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

            # Alignment markers for ICs and connectors
            # U1 BGA pin-1 indicator
            with Locations((-7.0, 7.0)):
                SilkscreenText("• Pin 1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            # U2 QFN pin-1 indicator
            with Locations((15.0, -6.5)):
                SilkscreenText("• Pin 1", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            # J1 M.2 connector edge alignment markers
            with Locations((-12.0, -38.0), (12.0, -38.0)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)
            # J2 FPC connector alignment markers
            with Locations((-10.0, 39.5), (10.0, 39.5)):
                SilkscreenText("|", layer="F.SilkS", font_size=1.0, thickness=0.15)

            # Component Reference Designators (BUG-066)
            # Active ICs and Primary Modules
            with Locations((0.0, 8.5)):
                SilkscreenText("U1", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((18.0, -11.5)):
                SilkscreenText("U2", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            with Locations((0.0, -32.5)):
                SilkscreenText("J1", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((0.0, 35.5)):
                SilkscreenText("J2", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((-17.5, 0.0)):
                SilkscreenText("J3", layer="F.SilkS", font_size=1.0, thickness=0.15)
            with Locations((-23.0, 19.5)):
                SilkscreenText("J13", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-24.0, 13.5)):
                SilkscreenText("+", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-22.0, 13.5)):
                SilkscreenText("-", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-18.0, -12.5)):
                SilkscreenText("Q1", layer="B.SilkS", font_size=0.8, thickness=0.12, mirror=True)
            with Locations((-19.0, 12.5)):
                SilkscreenText("U3", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-18.0, 24.5)):
                SilkscreenText("U4", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((-18.0, 38.0)):
                SilkscreenText("SPK1", layer="F.SilkS", font_size=0.8, thickness=0.12)
            with Locations((0.0, 17.0)):
                SilkscreenText("Y1", layer="F.SilkS", font_size=0.8, thickness=0.12)

            # Resistors
            with Locations((14.5, -6.0)):
                SilkscreenText("R1", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((10.0, -4.5)):
                SilkscreenText("R2", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-14.5, 4.5)):
                SilkscreenText("R3", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-14.5, -4.5)):
                SilkscreenText("R4", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-5.5, 8.0)):
                SilkscreenText("R5", layer="F.SilkS", font_size=0.7, thickness=0.10)
            with Locations((-11.5, -12.0)):
                SilkscreenText("R6", layer="F.SilkS", font_size=0.7, thickness=0.10)

            # Capacitors
            with Locations((13.0, -17.5)):
                SilkscreenText("C1", layer="F.SilkS", font_size=0.7, thickness=0.10)
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

        return silk.texts

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
