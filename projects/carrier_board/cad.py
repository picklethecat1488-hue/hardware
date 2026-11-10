"""Mechanical enclosure CAD parts and 3D product view for Carrier Board."""

from typing import cast, Callable, Sequence, Any, Optional
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
from provider import (
    Room,
    Mode,
    WiringDiagram,
)


class CarrierBoardCAD:
    """CAD part builder implementations and mechanical assembly views for Carrier Board."""

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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
            wiring = self.wiring
            if wiring is not None:
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
        if self.wiring:
            wiring = self.wiring
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
        wiring = self.wiring
        if wiring is not None:
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
        wiring = self.wiring
        if wiring is not None:
            d1_comp = next((c for c in wiring.footprints if c.name == "D1"), None)
            if d1_comp:
                led_x, led_y = d1_comp.position[0], d1_comp.position[1]

        cover_geom = cover.part.locate(Location((led_x, led_y, z_lid + wall)))

        batt_cov_geom = batt_cov.part.locate(Location((0.0, 0.0, z_lid + wall + 0.5)))

        room.add("carrier_board", carrier_geom, color=self.CARRIER_BOARD_COLOR, alpha=1.0)
        room.add("flex_tail", tail_geom, color=self.FLEX_TAIL_COVERLAY_COLOR, alpha=0.9)
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
        wiring = getattr(self, "system_wiring", None) or self.wiring
        if wiring is not None:
            diagram = WiringDiagram(wiring)
            diagram.build(room)

    def view_battery_cover(self, room: Room, mode: Mode) -> None:
        """Render standalone snap-fit battery cover."""
        cover = self.battery_cover("battery_cover", None, mode)
        room.add("battery_cover", cover.part, color=(0.20, 0.22, 0.28), alpha=0.9)
