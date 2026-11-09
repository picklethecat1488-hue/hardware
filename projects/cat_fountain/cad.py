"""CAD part builder implementations for the Cat Fountain project."""

from typing import cast, Callable, Sequence, Any, Optional, Dict
import math
from pathlib import Path
from build123d import *  # type: ignore
from model import (
    TextArgs,
    ShapeType,
    BoundaryType,
    Wiring,
)
from provider import (
    Room,
    Simulate,
    URDFBoundary,
    URDFMetadata,
    URDFShape,
    URDFCollisionType,
    URDFBoundaryType,
    URDFJointType,
    URDFMotorType,
    IntakePort,
    DrainPort,
    TubePort,
    FlowSlot,
    SpoutDeflection,
    ImpellerVanes,
    MagneticCoupling,
    LinkType,
    Mode as ProviderMode,
)


def make_snap_ring(
    outer_radius: float,
    inner_radius: float,
    height: float,
    fillet_radius: float = 0.35,
    align_z: Align = Align.MIN,
) -> Part:
    """Build an annular snap-fit ring with filleted circular edges."""
    with BuildPart() as snap_ring:
        Cylinder(radius=outer_radius, height=height, align=(Align.CENTER, Align.CENTER, align_z))
        Cylinder(
            radius=inner_radius,
            height=height + 2.0,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
            mode=Mode.SUBTRACT,
        )
        if fillet_radius > 0.0:
            fillet(snap_ring.edges().filter_by(GeomType.CIRCLE), radius=fillet_radius)
    return cast(Part, snap_ring.part)


def make_filleted_pocket_tool(radius: float, height: float, fillet_radius: float = 1.5) -> Part:
    """Build a cylindrical pocket subtractive tool with a filleted bottom circular edge."""
    with BuildPart() as tool:
        Cylinder(radius=radius, height=height, align=(Align.CENTER, Align.CENTER, Align.MIN))
        bottom_edge = tool.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[0]
        if fillet_radius > 0.0:
            fillet(bottom_edge, radius=fillet_radius)
    return cast(Part, tool.part)


class CatFountainCAD:
    """CAD part builder implementations and geometric operations for Cat Fountain."""

    def _build_bowl_impl(self, target: str) -> BuildPart:
        """Build cached implementation of bowl CAD geometry."""
        r = self.settings.bowl_radius
        h = self.settings.bowl_height
        t = self.settings.bowl_thickness
        pin_r = self.settings.impeller_shaft_radius
        floor_z = self.settings.floor_z
        tube_y = 0.0

        # PCB settings
        hole_r = self.settings.pcb_hole_radius
        boss_r = self.settings.pcb_boss_radius

        with BuildPart() as bowl:
            # Outer bowl body
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Create the global outer cylinder for trimming standoffs (oversized to prevent coincident face mesh artifacts)
            outer_cylinder = Cylinder(
                radius=r + 1.0, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.PRIVATE
            )

            # Subtract inner water reservoir (enclosed storage tank area above floor_z)
            # Make a step at the top rim of the bowl inner wall for the lid seat
            with Locations((0, 0, floor_z)):
                reservoir_shape = Cylinder(
                    radius=r - t,
                    height=h - floor_z - self.settings.lid_step_depth,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            # Step recess at the top rim
            with Locations((0, 0, h - self.settings.lid_step_depth)):
                Cylinder(
                    radius=r - t + self.settings.lid_step_width,
                    height=self.settings.lid_step_depth + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            # Annular groove for lid snap fit (scaling with lid radius)
            groove_major = r - t + self.settings.lid_step_width - self.settings.lid_clearance
            with Locations((0, 0, h - 2.5)):
                Torus(major_radius=groove_major, minor_radius=0.6, mode=Mode.SUBTRACT)

            # Subtract dry motor controller compartment under the floor
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=r - t, height=floor_z - t, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Subtract a matching snap-fit groove on the inner wall of the dry compartment
            # Located to align with the bottom cover's snap ring (Z = 1.1 on cover of height 4.0)
            with Locations((0, 0, 1.1)):
                Cylinder(
                    radius=r - t + 0.6,
                    height=1.2,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # --- INTEGRATED TUBE & CENTRIFUGAL VOLUTE CASING ---
            tube_x = 0.0
            tube_y = 28.0
            tube_r = self.settings.tube_radius
            tube_t = self.settings.tube_thickness
            tube_in_r = tube_r - tube_t

            # Dynamically calculate casing dimensions based on impeller settings
            hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.0
            impeller_r = hub_r + 4.0
            chamber_r = impeller_r + self.settings.pump_casing_clearance
            casing_r = chamber_r + self.settings.pump_well_wall
            snap_r = chamber_r + 1.0

            # 1. Casing & Tube outer solid geometries
            with Locations((0, 0, floor_z)):
                # Volute casing outer cylinder
                Cylinder(radius=casing_r, height=10.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((tube_x, tube_y, floor_z)):
                # Integrated vertical tube outer cylinder
                Cylinder(radius=tube_r, height=self.settings.tube_height, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Solid connector block for the tangential flow nozzle (running along Y)
            with Locations((0, 14.0, floor_z)):
                Box(tube_r * 2.0, 28.0, 10.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # 2. Subtract inner cavities
            with Locations((0, 0, floor_z)):
                # Volute impeller chamber
                Cylinder(
                    radius=chamber_r, height=10.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )
                # Snap fit recess for pump cover at the top rim (BUG-LEAPING-LOCUST-56)
                mount_depth = self.settings.pump_cover_mount_depth or 1.5
                with Locations((0, 0, 10.0 - mount_depth)):
                    Cylinder(
                        radius=snap_r,
                        height=mount_depth,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )
                # Internal annular snap-fit groove in casing recess wall (BUG-SPECKLED-ROACH-49, BUG-LEAPING-LOCUST-56)
                with Locations((0, 0, 10.0 - self.settings.pump_cover_snap_z_offset)):
                    Torus(
                        major_radius=snap_r,
                        minor_radius=self.settings.pump_cover_snap_groove_minor,
                        mode=Mode.SUBTRACT,
                    )
            with Locations((tube_x, tube_y, floor_z + 2.0)):
                # Tube inner cavity (starting 2mm above floor to create a bottom pocket)
                Cylinder(
                    radius=tube_in_r,
                    height=self.settings.tube_height + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            # Rectangular flow channel between casing and tube (Z = floor_z + 1.0 to floor_z + 9.0)
            with Locations((0, 14.0, floor_z + 1.0)):
                Box(8.0, 28.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Central solid boss and guide post for the isolated impeller
            with Locations((0, 0, floor_z)):
                # Static guide post (radius pin_r, height 12.0mm on shoulder pin_r + 1.0mm)
                Cylinder(radius=pin_r + 1.0, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=pin_r, height=12.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Groove-style cylindrical mounting socket for dedicated motor hub assembly (BUG-VIBRANT-WOODBORER-940)
            # Replaces slide-in tracks with an annular snap-groove socket (matching the lid and bottom cover style)
            # so the motor, drive hub, Hall sensor, and bracket install and remove axially as a single unit.
            ceiling_z = floor_z - self.settings.pump_well_wall
            recess_r = self.settings.drive_hub_recess_radius
            recess_depth = t - self.settings.pump_well_wall + 0.1
            if recess_depth > 0:
                with Locations((0, 0, ceiling_z)):
                    Cylinder(
                        radius=recess_r,
                        height=recess_depth,
                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                        mode=Mode.SUBTRACT,
                    )

            standoff_h = self.settings.drive_hub_standoff_height
            hub_h = self.settings.magnet_thickness + self.settings.magnet_clearance + 0.8
            motor_h = 9.3
            clip_h = self.settings.motor_hub_thickness
            collar_gap = 0.5
            mount_seat_z = ceiling_z - standoff_h - hub_h - collar_gap - motor_h - clip_h

            socket_in_r = self.settings.motor_hub_socket_radius
            socket_wall = self.settings.motor_hub_socket_wall
            socket_out_r = socket_in_r + socket_wall
            socket_h = (floor_z - t) - mount_seat_z + 0.5
            groove_offset = self.settings.motor_hub_snap_groove_radius_offset
            groove_h = self.settings.motor_hub_snap_groove_height

            with Locations((0, 0, floor_z - t)):
                # Outer solid cylinder of mounting socket
                Cylinder(radius=socket_out_r, height=socket_h, align=(Align.CENTER, Align.CENTER, Align.MAX))
                # Inner bore receiving the motor hub collar
                Cylinder(
                    radius=socket_in_r,
                    height=socket_h + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MAX),
                    mode=Mode.SUBTRACT,
                )

            # Internal annular snap-fit groove in socket inner wall (aligns with motor hub snap ring)
            with Locations((0, 0, mount_seat_z + clip_h + 2.0)):
                Cylinder(
                    radius=socket_in_r + groove_offset,
                    height=groove_h,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT,
                )

            # Keyway slot at North (+Y) in socket wall allowing Hall sensor platform and cabling to pass through (BUG-LUSTROUS-COCOON-669)
            # Fits hall sensor mount to prevent rotation during spinning without cutting into the bowl floor above ceiling_z.
            # Cut from Y = 0 (well inside hollow bore radius 18mm) outwards past the socket wall to eliminate thin sliver walls at the curved corners
            keyway_w = self.settings.hall_sensor_clearance_width or (self.settings.hall_sensor_spacing_x + 6.0)
            with Locations((0, 0, floor_z - t)):
                Box(
                    keyway_w,
                    socket_out_r + 5.0,
                    socket_h + 1.0,
                    align=(Align.CENTER, Align.MIN, Align.MAX),
                    mode=Mode.SUBTRACT,
                )

            # Helper to create cylindrical standoff posts with blind holes
            def add_standoffs(
                locations: list[Location],
                boss_radius: float,
                standoff_height: float,
                hole_radius: float,
                hole_depth: float,
                boss_align: tuple[Align, Align, Align] = (Align.CENTER, Align.CENTER, Align.MAX),
                hole_align: tuple[Align, Align, Align] = (Align.CENTER, Align.CENTER, Align.MIN),
                hole_z_offset: float = 0.0,
            ):
                for loc in locations:
                    with Locations(loc):
                        Cylinder(radius=boss_radius, height=standoff_height, align=boss_align)
                        with Locations((0, 0, hole_z_offset)):
                            Cylinder(
                                radius=hole_radius,
                                height=hole_depth,
                                align=hole_align,
                                mode=Mode.SUBTRACT,
                            )

            # Helper function to generate a 3D-printed snap-fit socket for hole-less PCBs (BUG-STINGING-LACEWING-799)
            def add_pcb_clip(
                center_x: float,
                center_y: float,
                board_span: float,  # Board width along X
                board_slide: float,  # Board length along Y
                standoff_h: float,
                label: str,
            ):
                wall_t = 2.0
                pcb_t = 1.6
                clearance = 0.2
                snap_depth = 0.35
                snap_h = 1.8
                lip_t = self.settings.pcb_clip_detent_lip
                chamfer_h = 0.3
                total_h = standoff_h + snap_h + lip_t + chamfer_h

                cutout_margin = self.settings.pcb_snap_socket_cutout_margin

                outer_x = board_span + 2.0 * wall_t
                outer_y = board_slide + 2.0 * wall_t
                inner_x = board_span + clearance
                inner_y = board_slide + clearance
                cutout_x = board_span - cutout_margin
                cutout_y = board_slide - cutout_margin

                with Locations((center_x, center_y, floor_z - t)):
                    # 1. Solid outer socket frame extending from ceiling
                    Box(outer_x, outer_y, total_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

                    # 2. Central cutout surrounding the boards with small margin (0.1mm - 0.5mm) per BUG-FIERCE-LONGHORN-849
                    Box(
                        cutout_x,
                        cutout_y,
                        total_h + 0.1,
                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                        mode=Mode.SUBTRACT,
                    )

                    # 3. PCB seating pocket (from -standoff_h down through PCB thickness)
                    # Creates internal snap-fit groove with positive retaining lip below and ceiling shelf above
                    with Locations((0, 0, -standoff_h)):
                        Box(
                            inner_x + snap_depth * 2.0,
                            inner_y + snap_depth * 2.0,
                            snap_h,
                            align=(Align.CENTER, Align.CENTER, Align.MAX),
                            mode=Mode.SUBTRACT,
                        )

                    # 4. Lead-in entry chamfer at bottom opening for smooth snap-in insertion
                    with Locations((0, 0, -total_h)):
                        Box(
                            cutout_x + 0.6,
                            cutout_y + 0.6,
                            chamfer_h,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )

                    # 5. Tool removal openings on each wall beneath the PCB (BUG-FIERCE-LONGHORN-849)
                    # Allows inserting a tool (e.g. Allen wrench) under the board from any of the 4 sides to pop it out
                    tool_hole_w = self.settings.pcb_snap_socket_tool_hole_width
                    tool_hole_h = self.settings.pcb_snap_socket_tool_hole_height
                    with Locations((0, 0, -tool_hole_h / 2.0)):
                        Box(
                            outer_x + 2.0,
                            tool_hole_w,
                            tool_hole_h,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            mode=Mode.SUBTRACT,
                        )
                        Box(
                            tool_hole_w,
                            outer_y + 2.0,
                            tool_hole_h,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            mode=Mode.SUBTRACT,
                        )

                # Add engraved label (move to opposite side of board to avoid proximity to CURRENT)
                label_y_offset = board_slide / 2.0 + 5.0
                if center_y + label_y_offset > r - t - 10.0:
                    label_y_offset = -label_y_offset
                with BuildSketch() as label_sketch:
                    Text(label, font_size=4.5, align=(Align.CENTER, Align.CENTER))
                mirrored_sketch = label_sketch.sketch.mirror(Plane.YZ)
                ext_text = extrude(mirrored_sketch, amount=1.5, mode=Mode.PRIVATE)
                bowl.part -= Location((center_x, center_y + label_y_offset, floor_z - t)) * ext_text

            # Helper function to generate standoff posts or press-fit clip mounts on the ceiling
            def add_pcb_mount(
                center_x: float,
                center_y: float,
                spacing_x: float,
                spacing_y: Optional[float],
                standoff_h: float,
                label: str,
                mount_type: str = "press_fit",
                post_indices: Optional[set[int]] = None,
            ):
                dxs = [-spacing_x / 2.0, spacing_x / 2.0]
                dys = [-spacing_y / 2.0, spacing_y / 2.0] if spacing_y else [0.0]

                locs = []
                for dx in dxs:
                    for dy in dys:
                        locs.append(Location((center_x + dx, center_y + dy, floor_z - t)))

                if mount_type == "standoff":
                    # Screw mount: standoffs with blind screw holes (used for CHARGER)
                    add_standoffs(
                        locations=locs,
                        boss_radius=boss_r,
                        standoff_height=standoff_h,
                        hole_radius=hole_r,
                        hole_depth=standoff_h + 2.5,
                        boss_align=(Align.CENTER, Align.CENTER, Align.MAX),
                        hole_align=(Align.CENTER, Align.CENTER, Align.MIN),
                        hole_z_offset=-standoff_h,
                    )
                else:
                    # Clip-in mount: press-fit onto bossed posts with flared heads (carrier_board enclosure style)
                    post_r = self.settings.pcb_mounting_post_diameter / 2.0
                    flare_r = self.settings.pcb_mounting_post_flare_diameter / 2.0
                    tip_r = self.settings.pcb_mounting_post_tip_diameter / 2.0
                    flare_h = self.settings.pcb_mounting_post_flare_height
                    shaft_h = self.settings.pcb_mounting_post_height - flare_h

                    for idx, loc in enumerate(locs):
                        with Locations(loc):
                            # Cylindrical standoff boss
                            Cylinder(radius=boss_r, height=standoff_h, align=(Align.CENTER, Align.CENTER, Align.MAX))
                            # Determine whether this mount point gets a post
                            has_post = (post_indices is None) or (idx in post_indices)
                            if has_post:
                                with Locations((0, 0, -standoff_h)):
                                    Cylinder(
                                        radius=post_r,
                                        height=shaft_h,
                                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                                    )
                                with Locations((0, 0, -standoff_h - shaft_h)):
                                    Cone(
                                        bottom_radius=tip_r,
                                        top_radius=flare_r,
                                        height=flare_h,
                                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                                    )

                label_y_offset = (spacing_y / 2.0 + 5.0) if spacing_y is not None else 8.0
                if center_y + label_y_offset > r - t - 10.0:
                    label_y_offset = -label_y_offset
                with BuildSketch() as label_sketch:
                    Text(label, font_size=4.5, align=(Align.CENTER, Align.CENTER))
                # Mirror the sketch horizontally so it reads correctly from below (looking up)
                mirrored_sketch = label_sketch.sketch.mirror(Plane.YZ)
                ext_text = extrude(mirrored_sketch, amount=1.5, mode=Mode.PRIVATE)
                bowl.part -= Location((center_x, center_y + label_y_offset, floor_z - t)) * ext_text  # type: ignore

            # Mount all PCBs in the dry compartment (standard boards use standoffs, TMC6300 uses slide-in guide)
            pcb_mounts = [
                (
                    50.0,
                    -45.0,
                    self.settings.fuel_gauge_spacing_x,
                    self.settings.fuel_gauge_spacing_y,
                    self.settings.fuel_gauge_standoff_height,
                    "FUEL",
                    "press_fit",
                    {1, 3},
                ),
                (
                    -50.0,
                    0.0,
                    self.settings.pico_spacing_x,
                    self.settings.pico_spacing_y,
                    self.settings.pico_standoff_height,
                    "PICO W",
                    "press_fit",
                    None,
                ),
                (
                    0.0,
                    -79.0,
                    self.settings.charger_spacing_x,
                    self.settings.charger_spacing_y,
                    self.settings.charger_standoff_height,
                    "CHARGER",
                    "standoff",
                    None,
                ),
                (
                    50.0,
                    -15.0,
                    self.settings.current_monitor_spacing_x,
                    self.settings.current_monitor_spacing_y,
                    self.settings.current_monitor_standoff_height,
                    "CURRENT",
                    "press_fit",
                    {1, 3},
                ),
                (
                    50.0,
                    15.0,
                    self.settings.motor_driver_spacing_y,
                    self.settings.motor_driver_spacing_x,
                    self.settings.motor_driver_standoff_height,
                    "TMC6300",
                    "clip",
                    None,
                ),
                (
                    -50.0,
                    -45.0,
                    self.settings.swd_board_width,
                    self.settings.swd_board_length,
                    self.settings.swd_board_standoff_height,
                    "SWD",
                    "clip",
                    None,
                ),
            ]
            for cx, cy, sx, sy, sh, lbl, mtype, p_indices in pcb_mounts:
                if mtype == "clip":
                    # sx is board span across rails (along X), sy is board slide length (along Y)
                    add_pcb_clip(cx, cy, sx, sy, sh, lbl)
                else:
                    add_pcb_mount(cx, cy, sx, sy, sh, lbl, mount_type=mtype, post_indices=p_indices)

            # Charging port hole in the outer wall of the dry compartment (back side, y = -r)
            # Centered on the USB port, which is located on the underside of the PCB
            usb_z = floor_z - t - self.settings.charger_standoff_height - 3.2
            port_depth = self.settings.charger_port_depth
            with Locations((0, -r + t / 2.0, usb_z)):
                with BuildPart(mode=Mode.PRIVATE) as port_cutout:
                    Box(
                        self.settings.charger_port_width,
                        port_depth,
                        self.settings.charger_port_height,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    )
                    fillet(port_cutout.edges().filter_by(Axis.Y), radius=2.0)
                add(port_cutout, mode=Mode.SUBTRACT)

            # Radial ventilation slits in the back wall around the charging port
            for angle in [252, 261, 279, 288]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t / 2.0, 0, 10.0)):
                        Box(t + 4.0, 2.5, 12.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Cutout for a square RGB LED on the front-right side (at angle 75, z = 8.0)
            with Locations(Rot(0, 0, 75.0)):
                with Locations((r - t / 2.0, 0, 8.0)):
                    Box(
                        10.0,
                        self.settings.led_hole_width,
                        self.settings.led_hole_width,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                    )

            # Proximity sensor mounts / cutouts at East (0), North (90), West (180)
            boss_sx = self.settings.sensor_boss_x
            boss_sy = 28.0  # Increased from 14.0 to cover the 21.0mm sensor spacing and standoffs
            boss_sz = self.settings.sensor_boss_z
            tof_spacing_x = self.settings.proximity_sensor_spacing_x
            tof_spacing_y = self.settings.proximity_sensor_spacing_y
            tof_standoff = self.settings.proximity_sensor_standoff_height
            ext_h = self.settings.proximity_sensor_inner_wall_extension

            for s_angle in [0.0, 90.0, 180.0]:
                with Locations(Rot(0, 0, s_angle)):
                    with Locations(Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0))):
                        # Outer flat sensor cover boss with rounded corners (extended vertically downwards)
                        with Locations(Location((11.0, 0, -2.0))):
                            with BuildPart(mode=Mode.PRIVATE) as boss_part:
                                Box(boss_sx, boss_sy, boss_sz, align=(Align.MAX, Align.CENTER, Align.CENTER))
                                fillet(boss_part.edges(), radius=2.0)
                            add(boss_part)

                        # Subtract the sensor pocket (extended vertically downwards)
                        with Locations(Location((11.0, 0, -2.0))):
                            Box(
                                boss_sx + 7.0,
                                self.settings.proximity_sensor_pocket_width,
                                self.settings.proximity_sensor_pocket_height,
                                align=(Align.MAX, Align.CENTER, Align.CENTER),
                                mode=Mode.SUBTRACT,
                            )

                        # Sensor shield on the inner bowl wall: extruded hollow rectangle (BUG-SPECKLED-ROVEBEETLE-352)
                        side_wall_t = 2.0
                        pocket_w = self.settings.proximity_sensor_pocket_width
                        pocket_h = self.settings.proximity_sensor_pocket_height
                        with Locations(Location((-4.0, 0, -2.0))):
                            with BuildPart(mode=Mode.PRIVATE) as shield_part:
                                Box(
                                    4.0,
                                    pocket_w + side_wall_t * 2.0,
                                    pocket_h + side_wall_t * 2.0,
                                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                )
                                Box(
                                    4.0 + 0.1,
                                    pocket_w,
                                    pocket_h,
                                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                    mode=Mode.SUBTRACT,
                                )
                            add(shield_part)

                        # Press-fit mounting standoffs on the INSIDE of the bowl wall (Finding 5)
                        post_r = self.settings.pcb_mounting_post_diameter / 2.0
                        flare_r = self.settings.pcb_mounting_post_flare_diameter / 2.0
                        tip_r = self.settings.pcb_mounting_post_tip_diameter / 2.0
                        flare_h = self.settings.pcb_mounting_post_flare_height
                        shaft_h = self.settings.pcb_mounting_post_height - flare_h

                        with BuildPart(mode=Mode.PRIVATE) as standoffs_part:
                            # Bottom standoff boss bodies
                            for dy in [-tof_spacing_x / 2.0, tof_spacing_x / 2.0]:
                                dz = -tof_spacing_y / 2.0
                                with Locations(Location((-4.0, dy, dz), (0, 90, 0))):
                                    Cylinder(
                                        radius=boss_r,
                                        height=tof_standoff,
                                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                    )

                            # Top standoff boss bodies extended into the inclined wall
                            for dy in [-tof_spacing_x / 2.0, tof_spacing_x / 2.0]:
                                dz = tof_spacing_y / 2.0
                                with Locations(Location((-4.0, dy, dz), (0, 90, 0)) * Location((0, 0, 5.0))):
                                    Cylinder(
                                        radius=boss_r, height=14.0, align=(Align.CENTER, Align.CENTER, Align.CENTER)
                                    )

                            # Press-fit flared retaining posts projecting inward from the standoff face at X = -6.0
                            for dy in [-tof_spacing_x / 2.0, tof_spacing_x / 2.0]:
                                for dz in [-tof_spacing_y / 2.0, tof_spacing_y / 2.0]:
                                    with Locations(Location((-6.0, dy, dz), (0, -90, 0))):
                                        Cylinder(
                                            radius=post_r,
                                            height=shaft_h,
                                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                                        )
                                        with Locations((0, 0, shaft_h)):
                                            Cone(
                                                bottom_radius=flare_r,
                                                top_radius=tip_r,
                                                height=flare_h,
                                                align=(Align.CENTER, Align.CENTER, Align.MIN),
                                            )

                        # Transform local standoffs to global coordinates using active locations
                        from build123d import LocationList

                        combined_loc = Location()
                        ctx = LocationList._get_context()
                        if ctx is not None:
                            for loc_list in ctx.locations:
                                combined_loc = combined_loc * loc_list

                        if standoffs_part.part is not None:
                            global_standoffs = combined_loc * standoffs_part.part

                            # Trim any protrusions extending past the outer cylinder
                            trimmed_standoffs = global_standoffs.intersect(outer_cylinder)

                            # Add trimmed standoffs directly to the bowl part (bypassing locations list)
                            if bowl.part is not None:
                                merged_shape = bowl.part + trimmed_standoffs
                                # Ensure final returned shape is a Part object, wrapping the internal Solid
                                bowl.part = Part(children=merged_shape.solids(), label=target)

            # Ensure dry compartment clearance for bottom cover (Z <= 4.0)
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=r - t + 0.5,
                    height=4.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            with URDFMetadata(
                label=target,
                material=self.get_material(target) or "utr8100",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
            ):
                with URDFBoundary.from_shape(
                    reservoir_shape,
                    link_type=LinkType.BASE,
                    shape=ShapeType.CYLINDER,
                    type=BoundaryType.CAVITY,
                    thickness=t * 0.001,
                    height=(h - floor_z + self.settings.spout_length) * 0.001,
                ):
                    TubePort(location=Location((0.0, tube_y, 0.0)), radius=tube_in_r * 0.001)

                tube_geom = Cylinder(
                    radius=self.settings.tube_radius,
                    height=self.settings.tube_height,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.PRIVATE,
                ).locate(Location((0.0, tube_y, floor_z)))
                with URDFBoundary.from_shape(
                    tube_geom,
                    link_type=LinkType.TUBE,
                    shape=ShapeType.TUBE,
                    type=BoundaryType.SOLID_CAVITY,
                    thickness=self.settings.tube_thickness * 0.001,
                ):
                    IntakePort(location=Location((0.0, 0.0, 0.0), (0, 180, 0)), radius=tube_in_r * 0.001)
                    DrainPort(
                        location=Location((0.0, 0.0, self.settings.tube_height), (0, 0, 0)),
                        radius=tube_in_r * 0.001,
                    )
                    FlowSlot(height=9.0 * 0.001, width=8.0 * 0.001)
                    SpoutDeflection(
                        radius=(self.settings.spout_deflection_radius + 1.0) * 0.001,
                        height=(self.settings.spout_deflection_thickness + 9.0) * 0.001,
                    )

                casing_thick = (casing_r - chamber_r) * 0.001
                casing_geom = Cylinder(
                    radius=casing_r,
                    height=10.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.PRIVATE,
                ).locate(Location((0.0, 0.0, floor_z)))
                with URDFBoundary.from_shape(
                    casing_geom,
                    link_type=LinkType.CASING,
                    shape=ShapeType.CASING,
                    type=BoundaryType.SOLID_CAVITY,
                    thickness=casing_thick,
                    is_submerged=True,
                ):
                    IntakePort(
                        location=Location((0.0, -casing_r, (self.settings.pump_inlet_height / 2.0 - 1.5)), (90, 0, 0)),
                        radius=min(self.settings.pump_inlet_width, self.settings.pump_inlet_height) * 0.5 * 0.001,
                    )
                    DrainPort(location=Location((0.0, tube_y, 0.0), (-90, 0, 0)), radius=tube_in_r * 0.001)
                    TubePort(location=Location((0.0, tube_y, 0.0), (0, 0, 0)))
                    FlowSlot(height=9.0 * 0.001, width=8.0 * 0.001)

        # Define joints
        ceiling_z = floor_z - self.settings.pump_well_wall
        standoff_h = self.settings.drive_hub_standoff_height
        hub_h = self.settings.magnet_thickness + self.settings.magnet_clearance + 0.8
        clip_h = self.settings.motor_hub_thickness
        motor_h = 9.3
        collar_gap = 0.5
        mount_seat_z = ceiling_z - standoff_h - hub_h - collar_gap - motor_h - clip_h
        motor_shaft_z = mount_seat_z + clip_h + motor_h + collar_gap

        RigidJoint("impeller_post", bowl.part, Location((0, 0, floor_z + 2.0)))
        RigidJoint("motor_shaft", bowl.part, Location((0, 0, motor_shaft_z)))
        RigidJoint("pump_cover_seat", bowl.part, Location((0, 0, floor_z + 10.0)))
        RigidJoint("motor_hub_seat", bowl.part, Location((0, 0, mount_seat_z)))
        RigidJoint("lid_seat", bowl.part, Location((0, 0, h)))
        RigidJoint("cover_seat", bowl.part, Location((0, 0, 0)))
        RigidJoint(
            "sensor_port_east",
            bowl.part,
            Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0)) * Location((11.2, 0, 0)),
        )
        RigidJoint(
            "sensor_port_north",
            bowl.part,
            Location(Rot(0, 0, 90.0)) * Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0)) * Location((11.2, 0, 0)),
        )
        RigidJoint(
            "sensor_port_west",
            bowl.part,
            Location(Rot(0, 0, 180.0)) * Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0)) * Location((11.2, 0, 0)),
        )
        RigidJoint(
            "led_port",
            bowl.part,
            Location(Rot(0, 0, 75.0))
            * Location((r - t / 2.0, 0, 8.0), (0, 90, 0))
            * Location((0, 0, self.settings.led_flange_thickness + 1.0)),
        )

        return bowl

    def _build_impeller_impl(self, target: str) -> BuildPart:
        """Build cached implementation of impeller CAD geometry."""
        hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.0
        hub_h = self.settings.impeller_base_height
        impeller_r = hub_r + 4.0
        pin_r = self.settings.impeller_shaft_radius
        pin_clearance = self.settings.impeller_shaft_clearance
        sleeve_r = self.settings.impeller_sleeve_radius
        mr = self.settings.magnet_radius + self.settings.magnet_clearance
        mt = self.settings.magnet_thickness + self.settings.magnet_clearance
        ring_r = self.settings.magnet_ring_radius
        min_wall = 1.5
        lobe_r = mr + min_wall
        center_r = 4.0
        num_blades = self.settings.impeller_blades
        blade_h = 4.0
        blade_overlap = self.settings.impeller_blade_overlap
        blade_start_r = sleeve_r - blade_overlap
        blade_len = (ring_r + lobe_r) - blade_start_r

        with BuildPart() as impeller:
            # 1. 3-lobed convex hull base carrying the magnets (minimizes inertia and startup torque)
            with BuildSketch() as sketch:
                for i in range(self.settings.magnet_count):
                    angle = i * (360.0 / self.settings.magnet_count)
                    rad = math.radians(angle)
                    with BuildSketch() as arm:
                        Circle(radius=center_r)
                        with Locations((ring_r * math.cos(rad), ring_r * math.sin(rad))):
                            Circle(radius=lobe_r)
                        make_hull()
                    add(arm.sketch)
            extrude(amount=hub_h)

            # 2. Central guide post sleeve (protrudes up for axial stability on the slim pin)
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=sleeve_r,
                    height=self.settings.impeller_sleeve_height,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

            # 3. Add 3 radial blades on the top face of the hub base (Z = hub_h)
            # Situated directly atop the 3 lobes of the convex hull base, extending into the central sleeve to prevent micro-gaps
            for i in range(num_blades):
                angle = i * (360.0 / num_blades)
                with Locations(Location((0, 0, hub_h)) * Rot(0, 0, angle)):
                    with Locations((blade_start_r, 0, 0)):
                        Box(blade_len, 1.2, blade_h, align=(Align.MIN, Align.CENTER, Align.MIN))

            # 4. Subtract magnet pockets on the bottom face of each lobe
            for i in range(self.settings.magnet_count):
                angle = i * (360.0 / self.settings.magnet_count)
                with Locations(Rot(0, 0, angle)):
                    with Locations((ring_r, 0, 0)):
                        Cylinder(
                            radius=mr, height=mt, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # 5. Subtract guide post central hole (with generous clearance for free rotation after resin coating)
            # Rests directly on top of the bowl's 2.0mm post flange shoulder, elevating the base 2.0mm off the floor.
            # Subtracted after blades to guarantee bore is completely unobstructed.
            Cylinder(
                radius=pin_r + pin_clearance,
                height=14.0,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )

            with URDFMetadata(
                label=target,
                material=self.get_material(target) or "petg",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
                motor_type=URDFMotorType.VELOCITY,
                motor_target=self.settings.motor_target,
                motor_force=self.settings.motor_power / self.settings.motor_target,
                magnet_radius=self.settings.magnet_radius,
                magnet_thickness=self.settings.magnet_thickness,
                pump_well_wall=self.settings.pump_well_wall,
                magnet_count=self.settings.magnet_count,
                impeller_shaft_radius=self.settings.impeller_shaft_radius,
            ):
                with URDFBoundary.from_shape(
                    impeller.part,
                    link_type=LinkType.IMPELLER,
                    shape=ShapeType.IMPELLER,
                    type=BoundaryType.SOLID,
                    radius=impeller_r * 0.001,
                    thickness=pin_r * 0.001,
                ):
                    ImpellerVanes(count=num_blades, twist=self.settings.vane_twist, thickness=1.2 * 0.001)
                    MagneticCoupling(
                        radius=self.settings.magnet_radius,
                        thickness=self.settings.magnet_thickness,
                        count=self.settings.magnet_count,
                        well_wall=self.settings.pump_well_wall,
                        shaft_radius=self.settings.impeller_shaft_radius,
                    )

        RevoluteJoint(label="pin", to_part=impeller.part, axis=Axis((0, 0, 0), (0, 0, 1)), angular_range=(0, 360))

        return impeller

    def _build_bottom_cover_impl(self, target: str) -> BuildPart:
        """Build cached implementation of bottom cover CAD geometry."""
        r = self.settings.bowl_radius
        t = self.settings.bowl_thickness
        clearance = self.settings.bottom_cover_clearance
        cover_r = r - t - clearance

        with BuildPart() as cover:
            Cylinder(radius=cover_r, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add a 0.5mm snap-fit annular Torus ridge around the perimeter (BUG-CLICKING-LARVA-354)
            snap_minor = self.settings.bottom_cover_snap_ridge_minor
            snap_z = self.settings.bottom_cover_snap_ridge_z
            if snap_minor > 0.0:
                with Locations((0, 0, snap_z)):
                    Torus(
                        major_radius=cover_r,
                        minor_radius=snap_minor,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.ADD,
                    )

            # Funnel-shaped top surface to drain water towards the central drain hole
            with Locations((0, 0, 1.5)):
                Cone(
                    bottom_radius=0.0,
                    top_radius=self.settings.lid_pocket_radius,
                    height=2.5,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Central drain hole drilled through the entire cover
            Cylinder(
                radius=self.settings.bottom_cover_drain_radius,
                height=10.0,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT,
            )

            # Peripheral wire/access opening notch on the edge
            opening_w = self.settings.bottom_cover_opening_width
            with Locations((0, -cover_r, 0.0)):
                Box(opening_w, 20.0, 10.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Symmetrically spaced depressions for adhesive rubber feet on the bottom face (Z = 0)
            feet_r = self.settings.rubber_feet_radius
            feet_d = self.settings.rubber_feet_depth
            pitch_r = self.settings.rubber_feet_pitch_radius
            feet_count = self.settings.rubber_feet_count
            if feet_count > 0 and feet_r > 0.0 and feet_d > 0.0:
                for i in range(feet_count):
                    angle_deg = (i * 360.0 / feet_count) + 45.0
                    rad = math.radians(angle_deg)
                    fx = pitch_r * math.cos(rad)
                    fy = pitch_r * math.sin(rad)
                    with Locations((fx, fy, 0.0)):
                        Cylinder(
                            radius=feet_r,
                            height=feet_d,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )

            URDFMetadata(
                label=target,
                material=self.get_material(target) or "utr8100",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def _build_lid_impl(self, target: str) -> BuildPart:
        """Build cached implementation of lid CAD geometry."""
        r = self.settings.bowl_radius
        h = self.settings.bowl_height
        t = self.settings.bowl_thickness
        tube_y = 28.0

        lid_r = r - t + self.settings.lid_step_width - self.settings.lid_clearance
        lid_h = 8.0
        step_d = self.settings.lid_step_depth
        step_w = self.settings.lid_step_width
        clearance = self.settings.lid_clearance
        socket_r = self.settings.tube_radius + self.settings.tube_lid_clearance
        platform_r = self.settings.spout_deflection_radius

        with BuildPart() as lid:
            lid_disk = Cylinder(radius=lid_r, height=lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add the snap-fit annular Torus ridge
            with Locations((0, 0, self.settings.snap_ridge_z)):
                Torus(
                    major_radius=lid_r + self.settings.snap_ridge_major_offset,
                    minor_radius=self.settings.snap_ridge_minor,
                )

            pocket_tool = make_filleted_pocket_tool(
                radius=self.settings.lid_pocket_radius,
                height=6.0,
                fillet_radius=1.5,
            )
            with Locations((0.0, 0.0, self.settings.lid_pocket_z_offset)):
                add(pocket_tool, mode=Mode.SUBTRACT)

            # Subtract the large circular cutout, but preserve the circular platform at Y = 28.0
            cutout_r = self.settings.lid_cutout_radius
            cutout_y = self.settings.lid_cutout_y

            with BuildPart(mode=Mode.PRIVATE) as cutout_tool:
                # Large cutout cylinder
                Cylinder(radius=cutout_r, height=lid_h + 10.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))
                # Add back the platform cylinder to preserve it
                with Locations((0, 28.0 - cutout_y, 0)):  # Relative to cutout center Y
                    Cylinder(
                        radius=platform_r,
                        height=lid_h + 20.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                    )
            with Locations((0, cutout_y, 0)):
                add(cutout_tool, mode=Mode.SUBTRACT)

            # Create a small protective ridge around the opening (on the pocket floor, from Z = 3.0)
            ridge_w = self.settings.lid_cutout_ridge_width
            ridge_h = self.settings.lid_cutout_ridge_height
            with BuildSketch() as ridge_sketch:
                # Outer ridge: ring from cutout_r to cutout_r + ridge_w at (0, cutout_y)
                with Locations((0, cutout_y)):
                    Circle(radius=cutout_r + ridge_w)
                    Circle(radius=cutout_r, mode=Mode.SUBTRACT)
                # Subtract the platform area
                with Locations((0, 28.0)):
                    Circle(radius=platform_r, mode=Mode.SUBTRACT)

                # Inner ridge: ring from platform_r to platform_r + ridge_w at (0, 28.0) intersected with the cutout circle
                with BuildSketch(mode=Mode.PRIVATE) as inner_ridge:
                    with Locations((0, 28.0)):
                        Circle(radius=platform_r + ridge_w)
                        Circle(radius=platform_r, mode=Mode.SUBTRACT)
                    with Locations((0, cutout_y)):
                        Circle(radius=cutout_r, mode=Mode.INTERSECT)
                add(inner_ridge)

            with Locations((0, 0, 3.0)):
                extrude(ridge_sketch.sketch, amount=ridge_h)

            with Locations((0.0, tube_y, 3.0)):
                with Locations(Rot(-self.settings.lid_platform_slope_angle, 0, 0)):
                    Cylinder(radius=platform_r, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    with Locations((0, 0, 3.0)):
                        Cylinder(radius=platform_r, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                        Cylinder(
                            radius=platform_r - 2.0,
                            height=1.0,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )
                    Cylinder(
                        radius=socket_r,
                        height=10.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                    )

            with Locations((0.0, tube_y, 0)):
                socket_r = self.settings.tube_radius + self.settings.tube_lid_clearance
                dome_out_r = socket_r + 1.5
                dome_in_r = self.settings.tube_radius - self.settings.tube_thickness + self.settings.tube_lid_clearance
                dome_slot_len = (dome_out_r + 1.0) * 2.0

                with BuildPart(mode=Mode.PRIVATE) as dome_tool:
                    with Locations((0, 0, 6.0)):
                        outer_dome = Sphere(radius=dome_out_r)
                        Sphere(radius=dome_in_r, mode=Mode.SUBTRACT)
                        for angle in [0, 45, 90, 135]:
                            with Locations(Rot(0, 0, angle)):
                                Box(
                                    self.SLOT_WIDTH,
                                    dome_slot_len,
                                    dome_in_r,
                                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                                    mode=Mode.SUBTRACT,
                                )
                        # Retention boss extending down from inner sphere ceiling to limit impeller vertical travel (added after cuts)
                        with Locations((0, 0, dome_in_r)):
                            Cylinder(
                                radius=3.0,
                                height=self.settings.retention_boss_height,
                                align=(Align.CENTER, Align.CENTER, Align.MAX),
                            )

                add(dome_tool.part)

                with Locations((0, 0, -10.0)):
                    Cylinder(
                        radius=socket_r,
                        height=16.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

        # Define joints and fluid ports
        intake_z = self.settings.lid_intake_z
        RigidJoint("intake_port", lid.part, Location((0.0, tube_y, intake_z), (0, 0, 0)))
        RigidJoint("drain_port", lid.part, Location((0.0, cutout_y, 0.0), (0, 0, 0)))
        RigidJoint("tube_port", lid.part, Location((0.0, tube_y, intake_z), (0, 0, 0)))
        RigidJoint("mount", lid.part, Location((0, 0, step_d)))

        # Define CAD feature geometry primitives for analytical boundaries
        pocket_geom = Cylinder(
            radius=self.settings.lid_pocket_radius,
            height=self.settings.lid_pocket_cavity_height,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.PRIVATE,
        ).locate(Location((0, 0, self.settings.lid_pocket_z_offset)))
        dome_geom = Sphere(radius=dome_out_r, mode=Mode.PRIVATE).locate(Location((0, tube_y, 6.0)))

        with URDFMetadata(
            geometry=lid,
            label=target,
            material=self.get_material(target) or "utr8100",
            density=self.settings.density,
            boundary_friction=self.settings.boundary_friction,
            collision_type=URDFCollisionType.ANALYTICAL,
            parent="bowl",
            joint_type=URDFJointType.FIXED,
        ):
            with URDFBoundary.from_shape(
                pocket_geom,
                link_type=LinkType.LID,
                shape=ShapeType.CYLINDER,
                type=BoundaryType.CAVITY,
                thickness=self.settings.lid_pocket_thickness * 0.001,
                shelf_depth=self.settings.lid_pocket_thickness * 0.001,
            ):
                IntakePort(location=Location((0.0, tube_y, intake_z), (0, 0, 0)), radius=platform_r * 0.001)
                DrainPort(location=Location((0.0, cutout_y, 0.0), (0, 0, 0)), radius=cutout_r * 0.001)
                TubePort(
                    location=Location((0.0, tube_y, intake_z), (0, 0, 0)),
                    radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
                )

            with URDFBoundary.from_shape(
                dome_geom,
                link_type=LinkType.LID,
                shape=ShapeType.CANOPY,
                type=BoundaryType.SOLID,
                thickness=(dome_out_r - dome_in_r) * 0.001,
            ):
                pass

        return lid

    def _build_led_cover_impl(self, target: str) -> BuildPart:
        """Build cached implementation of LED cover CAD geometry."""
        flange_w = self.settings.led_flange_width
        flange_t = self.settings.led_flange_thickness
        plug_w = self.settings.led_plug_width
        plug_l = self.settings.led_plug_length

        with BuildPart() as cover:
            Box(flange_w, flange_w, flange_t, align=(Align.CENTER, Align.CENTER, Align.MIN))
            fillet(cover.edges().filter_by(Axis.Z), radius=1.0)

            Box(plug_w, plug_w, plug_l, align=(Align.CENTER, Align.CENTER, Align.MAX))

            URDFMetadata(
                label=target,
                material=self.get_material(target) or "utr8100",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def _build_drive_hub_impl(self, target: str) -> BuildPart:
        """Build cached implementation of drive hub CAD geometry."""
        hub_h = self.settings.magnet_thickness + self.settings.magnet_clearance + 0.8
        standoff_h = self.settings.drive_hub_standoff_height
        mr = self.settings.magnet_radius + self.settings.magnet_clearance
        mt = self.settings.magnet_thickness + self.settings.magnet_clearance
        ring_r = self.settings.magnet_ring_radius
        thrust_r = self.settings.drive_hub_thrust_collar_radius
        shaft_r = self.settings.drive_hub_shaft_radius

        min_wall = self.settings.drive_hub_min_wall
        lobe_r = mr + min_wall
        center_r = 4.5
        groove_w = self.settings.drive_hub_strut_groove_width
        groove_d = self.settings.drive_hub_strut_groove_depth
        groove_l = self.settings.drive_hub_strut_groove_length

        with BuildPart() as hub:
            # 1. 3-lobed convex hull body with minimum 1.5mm wall thickness around magnets, grooves, and center hole (BUG-THORACIC-HARVESTMAN-529)
            with BuildSketch() as sketch:
                for i in range(self.settings.magnet_count):
                    angle = i * (360.0 / self.settings.magnet_count)
                    rad = math.radians(angle)
                    with BuildSketch() as arm:
                        Circle(radius=center_r)
                        with Locations((ring_r * math.cos(rad), ring_r * math.sin(rad))):
                            Circle(radius=lobe_r)
                        make_hull()
                    add(arm.sketch)
            extrude(sketch.sketch, amount=hub_h)

            # Central PTFE/POM thrust collar directly around 1.5mm motor shaft collar at R <= 1.5mm
            # Dropping contact radius from R = 15.6mm down to R <= 1.5mm reduces friction torque by over 90%
            if standoff_h > 0.0 and thrust_r > 0.0:
                with Locations((0, 0, hub_h)):
                    Cylinder(radius=thrust_r, height=standoff_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Motor shaft through-hole extending through the full hub and thrust collar
            total_h = hub_h + standoff_h
            with Locations((0, 0, -1.0)):
                Cylinder(
                    radius=shaft_r,
                    height=total_h + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Magnet pockets on the top face (Z = hub_h)
            for i in range(self.settings.magnet_count):
                angle = i * (360.0 / self.settings.magnet_count)
                with Locations(Location((0, 0, hub_h)) * Rot(0, 0, angle)):
                    with Locations((ring_r, 0, 0)):
                        # Pockets cut downward into the cylinder
                        Cylinder(
                            radius=mr, height=mt, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT
                        )

            # Triangular motor strut grooves on the bottom face (Z = 0) to prevent torque slippage (BUG-THORACIC-HARVESTMAN-529)
            for i in range(self.settings.magnet_count):
                angle = i * (360.0 / self.settings.magnet_count)
                with Locations(Location((0, 0, 0)) * Rot(0, 0, angle)):
                    with Locations((groove_l / 2.0, 0, 0)):
                        Box(
                            groove_l,
                            groove_w,
                            groove_d,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )

            URDFMetadata(
                label=target,
                material=self.get_material(target) or "petg",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                motor_type=URDFMotorType.VELOCITY,
                motor_target=self.settings.motor_target,
                motor_force=self.settings.motor_power / self.settings.motor_target,
                parent="bowl",
                joint_type=URDFJointType.CONTINUOUS,
            )

        RevoluteJoint(label="motor", to_part=hub.part, axis=Axis((0, 0, 0), (0, 0, 1)))
        return hub

    def _build_pump_cover_impl(self, target: str) -> BuildPart:
        """Build cached implementation of pump cover CAD geometry."""
        tube_x = 0.0
        tube_y = 28.0
        tube_r = self.settings.tube_radius
        tube_clearance = self.settings.pump_cover_tube_clearance
        hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.0
        impeller_r = hub_r + 4.0
        chamber_r = impeller_r + self.settings.pump_casing_clearance
        pump_well_wall = self.settings.pump_well_wall
        casing_r = chamber_r + pump_well_wall
        snap_r = chamber_r + 1.0
        snap_clearance = self.settings.pump_cover_snap_clearance
        internal_clearance = self.settings.pump_cover_internal_clearance
        cover_r = snap_r - snap_clearance  # Fits into casing snap recess with epoxy resin clearance
        cover_h = self.settings.pump_cover_height
        sleeve_h = self.settings.pump_cover_sleeve_height
        inlet_w = self.settings.pump_inlet_width
        inlet_h = self.settings.pump_inlet_height
        clip_opening_w = self.settings.pump_cover_clip_opening_width
        lip_thickness = self.settings.pump_cover_lip_thickness
        lip_in_r = cover_r - lip_thickness

        with BuildPart() as cover:
            # 1. Main casing cap over impeller volute (Z = 0 at casing top rim)
            with Locations((0, 0, 0)):
                Cylinder(radius=casing_r, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                mount_depth = self.settings.pump_cover_mount_depth or 1.5
                # Downward lip entering casing snap recess (Z = -mount_depth to 0) with tapered entry chamfer (BUG-LEAPING-LOCUST-56)
                with Locations((0, 0, -mount_depth)):
                    Cone(
                        bottom_radius=cover_r - 0.3,
                        top_radius=cover_r,
                        height=mount_depth,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                    )
                # Annular snap-fit ridge on downward lip to lock tightly into casing recess (BUG-SPECKLED-ROACH-49, BUG-GOLDEN-FIREFLY-566)
                with Locations((0, 0, -self.settings.pump_cover_snap_z_offset)):
                    ridge_r = snap_r + self.settings.pump_cover_snap_ridge_offset
                    ridge_minor = self.settings.pump_cover_snap_ridge_minor
                    Cylinder(
                        radius=ridge_r,
                        height=ridge_minor * 2.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    )
                    Torus(
                        major_radius=ridge_r,
                        minor_radius=ridge_minor,
                    )

            # 2. Tube sleeve sliding down the vertical delivery tube
            with Locations((tube_x, tube_y, 0)):
                Cylinder(radius=tube_r + 2.5, height=sleeve_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # 3. Connecting bridge between casing cap and tube sleeve
            with Locations((0, tube_y / 2.0, 0)):
                Box(tube_r * 2.0 + 5.0, tube_y, cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # 4. Subtract vertical tube bore through sleeve with bottom entry lead-in cone
            with Locations((tube_x, tube_y, -2.0)):
                Cylinder(
                    radius=tube_r + tube_clearance,
                    height=sleeve_h + 4.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
                with Locations((0, 0, 0)):
                    Cone(
                        bottom_radius=tube_r + tube_clearance + 0.6,
                        top_radius=tube_r + tube_clearance,
                        height=1.5,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # 5. Subtract North-facing C-clip snap opening through sleeve for easy tube installation
            if clip_opening_w > 0.0:
                with Locations((tube_x, tube_y, -2.0)):
                    Box(
                        clip_opening_w,
                        20.0,
                        sleeve_h + 4.0,
                        align=(Align.CENTER, Align.MIN, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # 6. Subtract internal impeller / guide post clearance cavity inside casing cap
            with Locations((0, 0, -mount_depth)):
                Cylinder(
                    radius=lip_in_r,
                    height=cover_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # 7. Side water intake window on South face (opposite the tube: Y < 0)
            with Locations((0, -casing_r + 2.0, 0.0)):
                Box(
                    inlet_w,
                    10.0,
                    inlet_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            with URDFMetadata(
                label=target,
                material=self.get_material(target) or "utr8100",
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            ):
                volute_geom = Cylinder(
                    radius=casing_r,
                    height=cover_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.PRIVATE,
                )
                with URDFBoundary.from_shape(
                    volute_geom,
                    link_type=LinkType.PUMP_COVER,
                    shape=ShapeType.CYLINDER,
                    type=BoundaryType.CAVITY,
                    thickness=pump_well_wall * 0.001,
                    is_submerged=True,
                ):
                    IntakePort(
                        location=Location((0.0, -casing_r, (inlet_h / 2.0)), (90, 0, 0)),
                        radius=min(inlet_w, inlet_h) * 0.5 * 0.001,
                    )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))
        return cover

    def _build_motor_hub_impl(self, target: str) -> BuildPart:
        """Build cached implementation of motor hub CAD geometry."""
        clip_h = self.settings.motor_hub_thickness
        r_bcd = self.settings.motor_mount_bolt_circle_radius
        hole_r = self.settings.motor_mount_hole_radius
        shaft_r = self.settings.motor_shaft_clearance_radius
        recess_d = self.settings.motor_base_recess_depth
        lobe_r = self.settings.motor_base_lobe_radius

        collar_r = self.settings.motor_hub_socket_radius - self.settings.motor_hub_collar_clearance
        collar_h = 5.0
        groove_offset = self.settings.motor_hub_snap_groove_radius_offset

        angles_deg = [90.0, 210.0, 330.0]
        mount_pts = [(r_bcd * math.cos(math.radians(a)), r_bcd * math.sin(math.radians(a))) for a in angles_deg]

        hall_front_y = self.settings.speed_sensor_pocket_y
        hall_sp_x = self.settings.hall_sensor_spacing_x
        hall_sh = self.settings.hall_sensor_standoff_height
        hall_dx = hall_sp_x / 2.0
        rect_w = hall_sp_x + 6.0
        rect_len = hall_front_y + 5.0

        with BuildPart() as hub_bracket:
            # 1. Base plate: circle unioned with rectangle to mount the hall sensor (BUG-LUSTROUS-COCOON-669)
            Cylinder(radius=collar_r, height=clip_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((0, rect_len / 2.0, 0)):
                Box(rect_w, rect_len, clip_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # 2. Circular cylindrical snap-fit collar with annular ridge
            with Locations((0, 0, clip_h)):
                Cylinder(radius=collar_r, height=collar_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(
                    radius=13.5,
                    height=collar_h + 1.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Annular snap ridge matching the internal groove in the bowl mounting socket
            snap_ring_part = make_snap_ring(
                outer_radius=collar_r + groove_offset - 0.1,
                inner_radius=collar_r - 1.0,
                height=1.0,
                fillet_radius=0.35,
                align_z=Align.CENTER,
            )
            with Locations((0, 0, clip_h + 2.0)):
                add(snap_ring_part)

            # Hall sensor clearance opening through North (+Y) collar wall (BUG-CRIMSON-MAYFLY-874)
            # Extends across the full width of the Hall sensor tongue so the sensor module passes through unobstructed.
            # Only cuts North (+Y) wall starting from Y = 10.0 outwards; South (-Y) collar wall remains continuous and solid.
            hall_opening_w = self.settings.hall_sensor_clearance_width or rect_w
            with Locations((0, 10.0, clip_h)):
                Box(
                    hall_opening_w,
                    collar_r - 10.0 + 5.0,
                    collar_h + 2.0,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # 3. Dedicated Hall sensor PCB module mount on the rectangular tongue (FORIOT A3144 module)
            post_r = self.settings.pcb_mounting_post_diameter / 2.0
            flare_r = self.settings.pcb_mounting_post_flare_diameter / 2.0
            tip_r = self.settings.pcb_mounting_post_tip_diameter / 2.0
            flare_h = self.settings.pcb_mounting_post_flare_height
            shaft_h = self.settings.pcb_mounting_post_height - flare_h
            boss_r = 2.8

            for hx in [-hall_dx, hall_dx]:
                with Locations((hx, hall_front_y, clip_h)):
                    # Cylindrical boss pad
                    Cylinder(radius=boss_r, height=hall_sh, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    # Press-fit flared retaining post
                    with Locations((0, 0, hall_sh)):
                        Cylinder(radius=post_r, height=shaft_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    with Locations((0, 0, hall_sh + shaft_h)):
                        Cone(
                            bottom_radius=flare_r,
                            top_radius=tip_r,
                            height=flare_h,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                        )

            # Sensor element locator pocket aligning with drive hub magnet pitch circle (R = 9.0mm)
            ring_r = self.settings.magnet_ring_radius
            with Locations((0, ring_r, clip_h)):
                Box(4.5, 2.5, hall_sh + 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Debossed label "HALL" on sensor platform
            with BuildSketch() as hall_label_sketch:
                Text("HALL", font_size=3.5, align=(Align.CENTER, Align.CENTER))
            ext_label = extrude(hall_label_sketch.sketch, amount=0.5, mode=Mode.PRIVATE)
            hub_bracket.part -= Location((0, hall_front_y - 4.5, clip_h)) * ext_label

            # 4. Central shaft and bearing collar clearance through-hole
            Cylinder(
                radius=shaft_r,
                height=clip_h + 10.0,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT,
            )

            # 5. Exactly 3x M1.4 mounting screw through-holes on Phi 6.6mm BCD on the bottom
            with Locations(*mount_pts):
                Cylinder(
                    radius=hole_r,
                    height=clip_h + 10.0,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT,
                )

            # 6. Triangular anti-rotation recess for motor base (on top surface Z = clip_h)
            with Locations((0, 0, clip_h)):
                with BuildSketch(mode=Mode.PRIVATE) as base_sketch:
                    with Locations(*mount_pts):
                        Circle(radius=lobe_r)
                    make_hull()
                extrude(base_sketch.sketch, amount=-recess_d, mode=Mode.SUBTRACT)

            URDFMetadata(
                label=target,
                material=self.get_material(target) or "petg",
                density=self.settings.petg_density,
                boundary_friction=self.settings.petg_boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", hub_bracket.part, Location((0, 0, 0)))
        RigidJoint("motor_shaft", hub_bracket.part, Location((0, 0, clip_h + 9.3 + 0.5)))
        RigidJoint("hall_mount", hub_bracket.part, Location((0, hall_front_y, clip_h + hall_sh)))
        return hub_bracket

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drive_hub_part = self.build_drive_hub("drive_hub").part
        pump_cover_part = self.build_pump_cover("pump_cover").part
        motor_hub_part = self.build_motor_hub("motor_hub").part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drive_hub_part is not None
            and pump_cover_part is not None
            and motor_hub_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["impeller_post"].connect_to(impeller_part.joints["pin"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        bowl_part.joints["motor_shaft"].connect_to(drive_hub_part.joints["motor"])
        bowl_part.joints["pump_cover_seat"].connect_to(pump_cover_part.joints["mount"])
        bowl_part.joints["motor_hub_seat"].connect_to(motor_hub_part.joints["mount"])

        # Build and connect the LED cover
        led_cover = self.build_led_cover("led_cover").part
        assert led_cover is not None
        bowl_part.joints["led_port"].connect_to(led_cover.joints["mount"])

        # Explode outwards by translating Z axis for LED cover
        assert led_cover.location is not None
        led_cover.location = led_cover.location * Location((0, 0, 30.0))

        # 3. Explode the parts by translating their .location attributes
        assert impeller_part.location is not None
        assert bottom_cover_part.location is not None
        assert lid_part.location is not None
        assert drive_hub_part.location is not None
        assert pump_cover_part.location is not None
        assert motor_hub_part.location is not None

        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        bottom_cover_part.location = Location((0, 0, -50)) * bottom_cover_part.location
        lid_part.location = Location((0, 0, 80)) * lid_part.location
        drive_hub_part.location = Location((0, 0, -25)) * drive_hub_part.location
        pump_cover_part.location = Location((0, 0, 110)) * pump_cover_part.location
        motor_hub_part.location = Location((0, -35, 0)) * motor_hub_part.location

        # 4. Add the exploded parts to the room using manifest colors
        for name, part in [
            ("bowl", bowl_part),
            ("impeller", impeller_part),
            ("bottom_cover", bottom_cover_part),
            ("lid", lid_part),
            ("led_cover", led_cover),
            ("drive_hub", drive_hub_part),
            ("pump_cover", pump_cover_part),
            ("motor_hub", motor_hub_part),
        ]:
            rgba = self.get_color(name)
            room.add(name, part, color=rgba[:3], alpha=rgba[3])

        # 5. Add connector lines indicating assembly paths
        impeller_conn = Line(
            bowl_part.joints["impeller_post"].location.position, impeller_part.joints["pin"].location.position
        )
        room.add("impeller_connector", impeller_conn)

        pump_cover_conn = Line(
            bowl_part.joints["pump_cover_seat"].location.position, pump_cover_part.joints["mount"].location.position
        )
        room.add("pump_cover_connector", pump_cover_conn)

        drive_hub_conn = Line(
            bowl_part.joints["motor_shaft"].location.position, drive_hub_part.joints["motor"].location.position
        )
        room.add("drive_hub_connector", drive_hub_conn)

        motor_hub_conn = Line(
            bowl_part.joints["motor_hub_seat"].location.position, motor_hub_part.joints["mount"].location.position
        )
        room.add("motor_hub_connector", motor_hub_conn)

        # 6. Add labels for each part
        room.add_label("bowl_label", "BOWL", bowl_part.center() + Vector(-120, -20, 10), options=TextArgs(font_size=10))
        room.add_label(
            "impeller_label", "IMPELLER", impeller_part.center() + Vector(-50, -10, 10), options=TextArgs(font_size=10)
        )
        room.add_label(
            "cover_label", "COVER", bottom_cover_part.center() + Vector(-80, 0, -10), options=TextArgs(font_size=10)
        )
        room.add_label("lid_label", "LID", lid_part.center() + Vector(-50, -10, 20), options=TextArgs(font_size=10))
        room.add_label(
            "led_cover_label",
            "LED COVER",
            led_cover.center() + Vector(30, 0, 10),
            options=TextArgs(font_size=10),
        )
        room.add_label(
            "drive_hub_label",
            "DRIVE HUB",
            drive_hub_part.center() + Vector(-50, 0, -10),
            options=TextArgs(font_size=10),
        )
        room.add_label(
            "pump_cover_label",
            "PUMP COVER",
            pump_cover_part.center() + Vector(-50, -10, 10),
            options=TextArgs(font_size=10),
        )
        room.add_label(
            "motor_hub_label",
            "MOTOR HUB",
            motor_hub_part.center() + Vector(-50, -10, 0),
            options=TextArgs(font_size=10),
        )

    def build_product(self, room: Room, mode: ProviderMode) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drive_hub_part = self.build_drive_hub("drive_hub").part
        pump_cover_part = self.build_pump_cover("pump_cover").part
        motor_hub_part = self.build_motor_hub("motor_hub").part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drive_hub_part is not None
            and pump_cover_part is not None
            and motor_hub_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["impeller_post"].connect_to(impeller_part.joints["pin"])
        bowl_part.joints["motor_shaft"].connect_to(drive_hub_part.joints["motor"])
        bowl_part.joints["pump_cover_seat"].connect_to(pump_cover_part.joints["mount"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        bowl_part.joints["motor_hub_seat"].connect_to(motor_hub_part.joints["mount"])

        # Build and connect the LED cover using joints
        led_cover = self.build_led_cover("led_cover").part
        assert led_cover is not None
        bowl_part.joints["led_port"].connect_to(led_cover.joints["mount"])

        # 3. Add the positioned parts directly to the room using manifest colors
        for name, part in [
            ("bowl", bowl_part),
            ("lid", lid_part),
            ("impeller", impeller_part),
            ("bottom_cover", bottom_cover_part),
            ("led_cover", led_cover),
            ("drive_hub", drive_hub_part),
            ("pump_cover", pump_cover_part),
            ("motor_hub", motor_hub_part),
        ]:
            rgba = self.get_color(name)
            room.add(name, part, color=rgba[:3], alpha=rgba[3])

        # 4. Build and add dummy PCBs / footprints for visual inspection and fitment checks (non-printable)
        if mode != ProviderMode.SIMULATE:
            from .pcb import make_pcb, make_sensor_pcb, make_motor

            wiring = self.wiring
            pcb_footprints = wiring.footprints

            for fp in pcb_footprints:
                if fp.name == "led":
                    continue
                w, l, thickness = fp.dimensions
                if fp.package == "tof_sensor":
                    joint_name = fp.name.replace("sensor_", "sensor_port_")
                    joint_loc = bowl_part.joints[joint_name].location
                    s_pcb = make_sensor_pcb()
                    s_pcb.location = joint_loc * Location((-18.3, 0, 0))
                    room.add(f"sensor_pcb_{fp.name[7:]}", s_pcb, color="green", alpha=0.6)
                elif fp.package == "motor":
                    m_part = make_motor(w, thickness)
                    m_part.location = Location(fp.position, fp.rotation)
                    room.add(f"{fp.name}_pcb", m_part, color="grey", alpha=0.85)
                else:
                    pcb = make_pcb(w, l, thickness)
                    pcb.location = Location(fp.position, fp.rotation)
                    color = "blue" if fp.package == "battery" else "green"
                    alpha = 0.8 if fp.package == "battery" else 0.6
                    room.add(f"{fp.name}_pcb", pcb, color=color, alpha=alpha)

        self.room = room

    def compute_flow_metrics(self) -> dict[str, Any]:
        """Compute continuous flow and drainage metrics delegating to simulation hooks."""
        from .simulate_hooks import compute_flow_metrics

        return compute_flow_metrics(self)
