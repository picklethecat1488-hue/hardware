"""Cat fountain geometry provider."""

from build123d import *  # type: ignore
import math
from model import (
    method_cache,
    TextArgs,
    ShapeType,
    BoundaryType,
    PinModel,
    LabelModel,
    FootprintModel,
    NetModel,
    Wiring,
    DiagramStyle,
)
from pathlib import Path
from provider import (
    Provider,
    Section,
    Mode as ProviderMode,
    discover_provider,
    Room,
    Simulate,
    URDFBoundary,
    URDFMetadata,
    URDFShape,
    URDFCollisionType,
    URDFBoundaryType,
    URDFJointType,
    URDFMotorType,
    LinkType,
    WiringDiagram,
)
from projects_config import CatFountainConfig
from . import layouts
from typing import cast, Callable, Sequence, Any, Optional


@discover_provider
class CatFountainProvider(Provider):
    """Provider for cat fountain geometry."""

    # Slot cutter constants (treating length as an infinite cutting plane)
    SLOT_WIDTH = 2.0
    SLOT_LENGTH = 100.0

    water_sim: Optional[Any] = None

    @property
    def default_config(self) -> CatFountainConfig:
        """Return the default configuration for the cat fountain project."""
        if not hasattr(self, "_cached_default_config"):
            self._cached_default_config = CatFountainConfig(
                measurements_path=str(Path(__file__).parent / "measurements.yaml")
            )
        return self._cached_default_config

    @property
    def settings(self) -> CatFountainConfig:
        """Return the typed configuration settings."""
        return cast(CatFountainConfig, super().settings)

    @property
    def part(self) -> dict[str, Callable[..., BuildPart]]:
        """Map part names to their build handler methods."""
        return {
            "bowl": self.build_bowl,
            "impeller": self.build_impeller,
            "bottom_cover": self.build_bottom_cover,
            "lid": self.build_lid,
            "led_cover": self.build_led_cover,
            "drive_hub": self.build_drive_hub,
            "pump_cover": self.build_pump_cover,
            "motor_clip": self.build_motor_clip,
        }

    @property
    def diagram(self) -> dict[str, Callable[[Room, Sequence[str], ProviderMode], None]]:
        """Map diagram names to their build handler methods."""
        return {
            name: (self.build_wiring_diagram if "wiring" in name else self.build_diagram)
            for name in self.targets.supporting(Section.DIAGRAM)
        }

    @property
    def view(self) -> dict[str, Callable[[Room, ProviderMode], None]]:
        """Map room names to view functions."""
        return {
            "product": self.build_product,
        }

    @method_cache
    def build_bowl(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the cat fountain bowl with integrated 2L reservoir, integrated tube, motor compartment, and screw mounts."""
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
                # Snap fit recess for pump cover at the top rim
                with Locations((0, 0, 8.5)):
                    Cylinder(
                        radius=snap_r, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
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
                # Static guide post (radius 2.5mm, height 12.0mm)
                Cylinder(radius=pin_r + 1.5, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=pin_r, height=12.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Motor mounting boss projecting down from the bowl floor (Z = floor_z)
            # This creates a solid 1.2mm barrier floor at the center of rotation
            with Locations((0, 0, floor_z)):
                # Outer boss body (increased radius to 21.0mm to provide full support under the impeller casing)
                boss_h = self.settings.motor_boss_height
                Cylinder(radius=21.0, height=boss_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

                # Local boss extension to house the speed sensor pocket (North side, Y = 21.0)
                with Locations((0, 21.0, 0)):
                    Box(8.0, 6.0, boss_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

                # 1. Recess for the drive hub
                # Formed as a U-shaped slot open to the South side (Y < 0) for horizontal slide-in assembly
                recess_r = self.settings.drive_hub_recess_radius
                recess_d = self.settings.drive_hub_recess_depth
                with Locations((0, 0, -1.2)):
                    Cylinder(
                        radius=recess_r,
                        height=recess_d,
                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                        mode=Mode.SUBTRACT,
                    )
                    # Subtract slot extension along Y < 0
                    with Locations((0, -recess_r, 0)):
                        Box(
                            recess_r * 2.0,
                            recess_r * 2.0,
                            recess_d,
                            align=(Align.CENTER, Align.CENTER, Align.MAX),
                            mode=Mode.SUBTRACT,
                        )
                # Restore the central column (radius 5.5mm, height 4.0mm from Z = -6.5 upwards)
                # This fits within the drive hub bottom recess and provides solid core support
                with Locations((0, 0, -6.5)):
                    Cylinder(radius=5.5, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.ADD)
                    # Subtract central hole for the motor shaft to pass through (radius 0.85mm)
                    Cylinder(radius=0.85, height=5.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

                # Speed sensor pocket (5.0mm wide, 2.2mm thick, 14.5mm deep from Z = -17.5 upwards)
                with Locations((0, 18.5, -17.5)):
                    Box(5.0, 2.2, 14.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

                # 2. Pocket for the BetaFPV 1102 motor body (starting at Z = -6.5 downwards by 12.0mm to break through bottom)
                with Locations((0, 0, -6.5)):
                    # Motor body pocket (radius 7.0mm for 13.8mm diameter, height 12.0mm)
                    Cylinder(radius=7.0, height=12.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                    # Motor front face alignment boss pocket (radius 2.75mm, height 1.6mm)
                    Cylinder(radius=2.75, height=1.6, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

                # 3. Horizontal slide-in slot for the motor retaining clip (Z = 23.5 to 25.5 mm, open to Y < 0)
                clip_slot_w = self.settings.motor_clip_width + 0.4
                clip_slot_h = self.settings.motor_clip_thickness + 0.2
                # Shifted slot center to Y = 5.0 and length to 41.0 to accommodate the clip's 5.0mm front projection
                with Locations((0, 5.0, -17.5)):
                    Box(clip_slot_w, 41.0, clip_slot_h, align=(Align.CENTER, Align.MAX, Align.MIN), mode=Mode.SUBTRACT)

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

            # Helper function to generate a 3D-printed two-sided slide-in card guide
            def add_pcb_clip(
                center_x: float,
                center_y: float,
                board_w: float,  # Width along Y (20.3)
                board_l: float,  # Length along X (25.4)
                standoff_h: float,
                label: str,
            ):
                with Locations((center_x, center_y, floor_z - t)):
                    # 1. Base plate connecting the two guide tracks (recessed to save material and provide airflow)
                    Box(board_l - 4.0, board_w - 2.0, standoff_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

                    # 2. Left and Right guide tracks (at X = +/- board_l/2)
                    track_w = board_w
                    track_l = 3.0
                    track_h = standoff_h + 3.2

                    with Locations((-board_l / 2.0 - 0.75, 0, 0), (board_l / 2.0 + 0.75, 0, 0)):
                        Box(track_l, track_w, track_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

                    # 3. Subtract the slot for the PCB inside the left/right tracks (1.9mm height)
                    with Locations((0, 0, -standoff_h)):
                        with Locations((-board_l / 2.0 - 0.15, 0, 0), (board_l / 2.0 + 0.15, 0, 0)):
                            Box(
                                2.0,
                                board_w + 0.3,
                                1.9,
                                align=(Align.CENTER, Align.CENTER, Align.MAX),
                                mode=Mode.SUBTRACT,
                            )

                # Add engraved label
                label_y_offset = -(board_w / 2.0 + 5.0)
                with BuildSketch() as label_sketch:
                    Text(label, font_size=4.5, align=(Align.CENTER, Align.CENTER))
                mirrored_sketch = label_sketch.sketch.mirror(Plane.YZ)
                ext_text = extrude(mirrored_sketch, amount=1.5, mode=Mode.PRIVATE)
                bowl.part -= Location((center_x, center_y + label_y_offset, floor_z - t)) * ext_text

            # Helper function to generate standoff posts and blind screw holes on the ceiling
            def add_pcb_mount(
                center_x: float,
                center_y: float,
                spacing_x: float,
                spacing_y: Optional[float],
                standoff_h: float,
                label: str,
            ):
                dxs = [-spacing_x / 2.0, spacing_x / 2.0]
                dys = [-spacing_y / 2.0, spacing_y / 2.0] if spacing_y else [0.0]

                locs = []
                for dx in dxs:
                    for dy in dys:
                        locs.append(Location((center_x + dx, center_y + dy, floor_z - t)))

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
                    "standoff",
                ),
                (
                    -50.0,
                    0.0,
                    self.settings.pico_spacing_x,
                    self.settings.pico_spacing_y,
                    self.settings.pico_standoff_height,
                    "PICO W",
                    "standoff",
                ),
                (
                    0.0,
                    -79.0,
                    self.settings.charger_spacing_x,
                    self.settings.charger_spacing_y,
                    self.settings.charger_standoff_height,
                    "CHARGER",
                    "standoff",
                ),
                (
                    50.0,
                    -15.0,
                    self.settings.current_monitor_spacing_x,
                    self.settings.current_monitor_spacing_y,
                    self.settings.current_monitor_standoff_height,
                    "CURRENT",
                    "standoff",
                ),
                (
                    50.0,
                    15.0,
                    self.settings.motor_driver_spacing_x,
                    self.settings.motor_driver_spacing_y,
                    self.settings.motor_driver_standoff_height,
                    "TMC6300",
                    "clip",
                ),
            ]
            for cx, cy, sx, sy, sh, lbl, mtype in pcb_mounts:
                if mtype == "clip":
                    # For the clip bracket, sx (spacing_x) is board length, sy (spacing_y) is board width
                    add_pcb_clip(cx, cy, sy, sx, sh, lbl)
                else:
                    add_pcb_mount(cx, cy, sx, sy, sh, lbl)

            # Charging port hole in the outer wall of the dry compartment (back side, y = -r)
            # Centered on the USB port, which is located on the underside of the PCB
            usb_z = floor_z - t - self.settings.charger_standoff_height - 3.2
            with Locations((0, -r + t / 2.0, usb_z)):
                with BuildPart(mode=Mode.PRIVATE) as port_cutout:
                    Box(
                        self.settings.charger_port_width,
                        10.0,
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

                        # Flat mounting standoff posts on the INSIDE of the bowl wall
                        # Build in a private block in local coordinates
                        with BuildPart(mode=Mode.PRIVATE) as standoffs_part:
                            # Bottom standoffs (dz = -tof_spacing_y / 2.0)
                            locs_bottom = []
                            for dy in [-tof_spacing_x / 2.0, tof_spacing_x / 2.0]:
                                dz = -tof_spacing_y / 2.0
                                locs_bottom.append(Location((-4.0, dy, dz), (0, 90, 0)))

                            add_standoffs(
                                locations=locs_bottom,
                                boss_radius=boss_r,
                                standoff_height=tof_standoff,
                                hole_radius=hole_r,
                                hole_depth=7.0,
                                boss_align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                hole_align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            )

                            # Top standoffs (dz = tof_spacing_y / 2.0) extended to merge with the wall
                            locs_top = []
                            for dy in [-tof_spacing_x / 2.0, tof_spacing_x / 2.0]:
                                dz = tof_spacing_y / 2.0
                                locs_top.append(Location((-4.0, dy, dz), (0, 90, 0)) * Location((0, 0, 5.0)))

                            add_standoffs(
                                locations=locs_top,
                                boss_radius=boss_r,
                                standoff_height=14.0,  # 4.0 original + 10.0 extension towards wall
                                hole_radius=hole_r,
                                hole_depth=7.0,
                                boss_align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                hole_align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                hole_z_offset=-5.0,  # Shift hole back to original centering
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

            with URDFMetadata(
                label=target,
                material=self.settings.material,
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
            ):
                URDFBoundary(
                    reservoir_shape,
                    link_type=LinkType.BASE,
                    type=BoundaryType.CAVITY,
                    height=(h - floor_z + self.settings.spout_length) * 0.001,
                    thickness=0.030,
                    has_tube=True,
                    tube_radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
                )
                with Locations((0.0, 28.0, floor_z)):
                    tube_geom = Cylinder(
                        radius=self.settings.tube_radius,
                        height=self.settings.tube_height,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.PRIVATE,
                    )
                URDFBoundary(
                    tube_geom,
                    link_type=LinkType.TUBE,
                    shape=ShapeType.TUBE,
                    type=BoundaryType.SOLID_CAVITY,
                    radius=0.018,  # Increased outer radius to overlap casing
                    thickness=0.010,  # Thick wall to prevent particle tunneling
                    height=self.settings.tube_height * 0.001,
                    slot_height=9.0 * 0.001,
                    slot_width=8.0 * 0.001,
                    spout_radius=(self.settings.spout_deflection_radius + 1.0) * 0.001,
                    spout_height=(self.settings.spout_deflection_thickness + 9.0) * 0.001,
                    xyz=(0.0, 28.0 * 0.001, floor_z * 0.001),
                    rpy=(0.0, 0.0, math.pi),
                )
                with Locations((0.0, 0.0, floor_z)):
                    casing_geom = Cylinder(
                        radius=28.0,
                        height=10.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.PRIVATE,
                    )
                URDFBoundary(
                    casing_geom,
                    link_type=LinkType.CASING,
                    shape=ShapeType.CASING,
                    type=BoundaryType.SOLID_CAVITY,
                    radius=0.028,
                    thickness=0.010,  # Inner chamber is 18mm, overlaps tube
                    height=10.0 * 0.001,
                    slot_height=9.0 * 0.001,  # Slot opening from Z = 0 to 9mm
                    slot_width=8.0 * 0.001,
                    tube_y=0.028,
                    cutoff_y=0.0,
                    ceiling_thickness=2.0 * 0.001,
                    xyz=(0.0, 0.0, floor_z * 0.001),
                    rpy=(0.0, 0.0, 0.0),
                )

        # Define joints
        RigidJoint("impeller_post", bowl.part, Location((0, 0, floor_z)))
        RigidJoint("motor_shaft", bowl.part, Location((0, 0, floor_z - 6.0)))
        RigidJoint("pump_cover_seat", bowl.part, Location((0, 0, floor_z + 8.5)))
        RigidJoint("motor_clip_seat", bowl.part, Location((0, 0, floor_z - 17.5)))
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

    @method_cache
    def build_impeller(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the lightweight centrifugal impeller (magnetic-drive)."""
        hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.0
        hub_h = 4.0
        impeller_r = hub_r + 4.0
        pin_r = self.settings.impeller_shaft_radius
        mr = self.settings.magnet_radius + self.settings.magnet_clearance
        mt = self.settings.magnet_thickness + self.settings.magnet_clearance
        ring_r = self.settings.magnet_ring_radius

        with BuildPart() as impeller:
            # Impeller Hub base (carrying the magnets)
            Cylinder(radius=hub_r, height=hub_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Central guide post sleeve (protrudes up to 8.0mm for stability on the post)
            Cylinder(radius=4.5, height=8.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract guide post central hole (radius 2.65mm for clearance on 2.5mm pin)
            Cylinder(
                radius=pin_r + 0.15, height=12.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
            )

            # Subtract recess for guide post flange (radius 4.2mm for clearance on 4.0mm flange, depth 2.2mm)
            Cylinder(radius=pin_r + 1.7, height=2.2, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Subtract 4 magnet pockets on the bottom face (Z = 0)
            for i in range(self.settings.magnet_count):
                angle = i * (360.0 / self.settings.magnet_count)
                with Locations(Rot(0, 0, angle)):
                    with Locations((ring_r, 0, 0)):
                        Cylinder(
                            radius=mr, height=mt, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Add radial blades on the top face of the hub base (Z = hub_h = 4.0)
            blade_h = 4.0
            blade_len = hub_r - 6.0
            num_blades = self.settings.impeller_blades
            for i in range(num_blades):
                angle = i * (360.0 / num_blades)
                with Locations(Location((0, 0, hub_h)) * Rot(0, 0, angle)):
                    with Locations((6.0, 0, 0)):
                        Box(blade_len, 1.2, blade_h, align=(Align.MIN, Align.CENTER, Align.MIN))

            with URDFMetadata(
                label=target,
                material=self.settings.material,
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
                URDFBoundary(
                    impeller,
                    link_type=LinkType.IMPELLER,
                    shape=ShapeType.IMPELLER,
                    type=BoundaryType.SOLID,
                    radius=impeller_r * 0.001,
                    height=cast(URDFShape, impeller.part).urdf_height,
                    thickness=pin_r * 0.001,
                    vane_twist=self.settings.vane_twist,
                    vane_thickness=1.2 * 0.001,
                    num_vanes=num_blades,
                    magnet_radius=self.settings.magnet_radius,
                    magnet_thickness=self.settings.magnet_thickness,
                    pump_well_wall=self.settings.pump_well_wall,
                    magnet_count=self.settings.magnet_count,
                    impeller_shaft_radius=self.settings.impeller_shaft_radius,
                )

        RevoluteJoint(label="pin", to_part=impeller.part, axis=Axis((0, 0, 0), (0, 0, 1)), angular_range=(0, 360))

        return impeller

    @method_cache
    def build_bottom_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the detachable bottom cover for the motor controller compartment."""
        r = self.settings.bowl_radius
        t = self.settings.bowl_thickness
        clearance = self.settings.bottom_cover_clearance
        cover_r = r - t - clearance

        with BuildPart() as cover:
            Cylinder(radius=cover_r, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add a 0.5mm snap-fit annular ring around the perimeter
            with BuildPart(mode=Mode.PRIVATE) as snap_ring_part:
                Cylinder(radius=cover_r + 0.5, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(
                    radius=cover_r - 2.0, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )
                fillet(snap_ring_part.edges().filter_by(GeomType.CIRCLE), radius=0.4)

            with Locations((0, 0, 1.2)):
                add(snap_ring_part.part)

            # Funnel-shaped top surface to drain water towards the central drain hole
            with Locations((0, 0, 1.5)):
                Cone(
                    bottom_radius=0.0,
                    top_radius=80.0,
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

            URDFMetadata(
                label=target,
                material=self.settings.material,
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    @method_cache
    def build_lid(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the top cover lid which acts as a drinking shelf and covers/stabilizes the vertical delivery tube."""
        r = self.settings.bowl_radius
        h = self.settings.bowl_height
        t = self.settings.bowl_thickness
        tube_y = 28.0

        lid_r = r - t + self.settings.lid_step_width - self.settings.lid_clearance
        lid_h = 8.0
        step_d = self.settings.lid_step_depth
        step_w = self.settings.lid_step_width
        clearance = self.settings.lid_clearance

        with BuildPart() as lid:
            lid_disk = Cylinder(radius=lid_r, height=lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add the snap-fit annular Torus ridge
            with Locations((0, 0, self.settings.snap_ridge_z)):
                Torus(
                    major_radius=lid_r + self.settings.snap_ridge_major_offset,
                    minor_radius=self.settings.snap_ridge_minor,
                )

            with BuildPart() as pocket_tool:
                Cylinder(radius=80.0, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                bottom_edge = pocket_tool.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[0]
                fillet(bottom_edge, radius=1.5)
            with Locations((0.0, 0.0, 3.0)):
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
                        radius=30.0,
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
                    Circle(radius=30.0, mode=Mode.SUBTRACT)

                # Inner ridge: ring from 30.0 to 30.0 + ridge_w at (0, 28.0) intersected with the cutout circle
                with BuildSketch(mode=Mode.PRIVATE) as inner_ridge:
                    with Locations((0, 28.0)):
                        Circle(radius=30.0 + ridge_w)
                        Circle(radius=30.0, mode=Mode.SUBTRACT)
                    with Locations((0, cutout_y)):
                        Circle(radius=cutout_r, mode=Mode.INTERSECT)
                add(inner_ridge)

            with Locations((0, 0, 3.0)):
                extrude(ridge_sketch.sketch, amount=ridge_h)

            with Locations((0.0, tube_y, 3.0)):
                with Locations(Rot(-self.settings.lid_platform_slope_angle, 0, 0)):
                    terrace_shelf = Cylinder(radius=30.0, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    with Locations((0, 0, 3.0)):
                        Cylinder(radius=30.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                        Cylinder(
                            radius=28.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
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

        with URDFMetadata(
            geometry=lid,
            label=target,
            material=self.settings.material,
            density=self.settings.density,
            boundary_friction=self.settings.boundary_friction,
            collision_type=URDFCollisionType.ANALYTICAL,
            parent="bowl",
            joint_type=URDFJointType.FIXED,
        ):
            URDFBoundary(
                pocket_tool.part,
                link_type=LinkType.LID,
                shape=ShapeType.CYLINDER,
                type=BoundaryType.CAVITY,
                radius=self.settings.lid_pocket_radius * 0.001,
                height=self.settings.lid_pocket_cavity_height * 0.001,
                thickness=0.030,
                xyz=(0.0, 0.0, self.settings.lid_pocket_z_offset * 0.001),
                rpy=(0.0, 0.0, 0.0),
                has_drain=True,
                drain_hole_y=cutout_y * 0.001,  # Parameterized coordinate
                drain_hole_radius=cutout_r * 0.001,  # Parameterized radius
                has_tube=True,
                tube_radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
            )

            dome_top_z = outer_dome.bounding_box().max.Z
            URDFBoundary(
                outer_dome,
                link_type=LinkType.LID,
                shape=ShapeType.CYLINDER,
                type=BoundaryType.CAVITY,
                radius=self.settings.spout_deflection_radius * 0.001,
                height=self.settings.spout_deflection_height * 0.001,
                thickness=self.settings.spout_deflection_thickness * 0.001,
                xyz=(0.0, tube_y * 0.001, dome_top_z * 0.001),
                rpy=(math.pi, 0.0, 0.0),
            )

            URDFBoundary(
                lid_disk,
                link_type=LinkType.LID,
                shape=ShapeType.CYLINDER,
                type=BoundaryType.CAVITY,
                height=0.0,
                thickness=2.0 * 0.001,
                xyz=(0.0, 0.0, -2.0 * 0.001),
                rpy=(math.pi, 0.0, 0.0),
                has_drain=True,
                drain_hole_y=-cutout_y * 0.001,  # Parameterized coordinate (flipped)
                drain_hole_radius=cutout_r * 0.001,  # Parameterized radius
                has_tube=True,
                tube_radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
            )

            URDFBoundary(
                terrace_shelf,
                link_type=LinkType.LID,
                shape=ShapeType.CYLINDER,
                type=BoundaryType.CAVITY,
                radius=(terrace_shelf.bounding_box().max.X - 2.0) * 0.001,
                height=0.0,
                thickness=3.0 * 0.001,
                xyz=(0.0, tube_y * 0.001, terrace_shelf.bounding_box().max.Z * 0.001),
                has_tube=True,
                tube_radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
            )

        RigidJoint("mount", lid.part, Location((0, 0, step_d)))

        return lid

    @method_cache
    def build_led_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build a translucent push-fit cover/diffuser for the RGB status LED."""
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
                material="petg",
                density=self.settings.petg_density,
                boundary_friction=self.settings.petg_boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    @method_cache
    def build_drive_hub(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the dry-side magnet drive hub mounted on the motor D-shaft."""
        hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.5
        hub_h = 4.5
        mr = self.settings.magnet_radius + self.settings.magnet_clearance
        mt = self.settings.magnet_thickness + self.settings.magnet_clearance
        ring_r = self.settings.magnet_ring_radius

        with BuildPart() as hub:
            Cylinder(radius=hub_r, height=hub_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract central clearance recess on the bottom face to clear the bowl's 5.5mm mounting column
            # (radius 5.8mm, depth 3.6mm starting from Z = 0, leaving 0.9mm ceiling and 2.4mm floor under magnets)
            Cylinder(radius=5.8, height=3.6, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Round shaft hole (radius 0.78mm for 1.5mm motor shaft)
            with BuildSketch() as hole_sketch:
                Circle(radius=0.78)
            ext_hole = extrude(hole_sketch.sketch, amount=hub_h + 2.0, mode=Mode.PRIVATE)
            hub.part -= Location((0, 0, -1.0)) * ext_hole

            # Magnet pockets on the top face (Z = hub_h)
            for i in range(self.settings.magnet_count):
                angle = i * (360.0 / self.settings.magnet_count)
                with Locations(Location((0, 0, hub_h)) * Rot(0, 0, angle)):
                    with Locations((ring_r, 0, 0)):
                        # Pockets cut downward into the cylinder
                        Cylinder(
                            radius=mr, height=mt, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT
                        )

            URDFMetadata(
                label=target,
                material=self.settings.material,
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

    @method_cache
    def build_pump_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the wet-side pump cover that snaps onto the volute casing."""
        # Dynamically calculate cover radius based on impeller settings
        hub_r = self.settings.impeller_radius + self.settings.magnet_radius + 1.0
        impeller_r = hub_r + 4.0
        chamber_r = impeller_r + self.settings.pump_casing_clearance
        snap_r = chamber_r + 1.0
        cover_r = snap_r - 0.15  # Fits with print clearance
        cover_h = 1.5
        inlet_r = self.settings.pump_inlet_radius

        with BuildPart() as cover:
            # Main disc body
            Cylinder(radius=cover_r, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Add downward-pointing intake snout (extends 4.0 mm downwards into the blade clearance gap)
            with Locations((0, 0, -4.0)):
                Cylinder(radius=inlet_r, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Subtract central axial water intake hole through both disc and snout
            with Locations((0, 0, -4.0)):
                Cylinder(
                    radius=inlet_r - 1.5,
                    height=cover_h + 4.0 + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            with URDFMetadata(
                label=target,
                material="petg",
                density=self.settings.petg_density,
                boundary_friction=self.settings.petg_boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            ):
                # Flat cover plate boundary (positioned at the mount joint Z_world = 49.5 mm)
                URDFBoundary(
                    cover,
                    link_type=LinkType.PUMP_COVER,
                    shape=ShapeType.CYLINDER,
                    type=BoundaryType.CAVITY,
                    radius=cover_r * 0.001,
                    height=0.0,
                    thickness=cover_h * 0.001,
                    xyz=(0.0, 0.0, 0.0),
                    rpy=(math.pi, 0.0, 0.0),
                    has_drain=True,
                    drain_hole_y=0.0,
                    drain_hole_radius=inlet_r * 0.001,  # Large hole to let water enter snout
                    has_tube=True,
                    tube_radius=(self.settings.tube_radius - self.settings.tube_thickness) * 0.001,
                )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))
        return cover

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drive_hub_part = self.build_drive_hub("drive_hub").part
        pump_cover_part = self.build_pump_cover("pump_cover").part
        motor_clip_part = self.build_motor_clip("motor_clip").part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drive_hub_part is not None
            and pump_cover_part is not None
            and motor_clip_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["impeller_post"].connect_to(impeller_part.joints["pin"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        bowl_part.joints["motor_shaft"].connect_to(drive_hub_part.joints["motor"])
        bowl_part.joints["pump_cover_seat"].connect_to(pump_cover_part.joints["mount"])
        bowl_part.joints["motor_clip_seat"].connect_to(motor_clip_part.joints["mount"])

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
        assert motor_clip_part.location is not None

        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        bottom_cover_part.location = Location((0, 0, -50)) * bottom_cover_part.location
        lid_part.location = Location((0, 0, 80)) * lid_part.location
        drive_hub_part.location = Location((0, 0, -25)) * drive_hub_part.location
        pump_cover_part.location = Location((0, 0, 110)) * pump_cover_part.location
        motor_clip_part.location = Location((0, -35, 0)) * motor_clip_part.location

        # 4. Add the exploded parts to the room
        room.add("bowl", bowl_part, color="grey", alpha=0.4)
        room.add("impeller", impeller_part, color="red")
        room.add("bottom_cover", bottom_cover_part, color="black")
        room.add("lid", lid_part, color="green")
        room.add("led_cover", led_cover, color="grey")
        room.add("drive_hub", drive_hub_part, color="red")
        room.add("pump_cover", pump_cover_part, color="grey", alpha=0.5)
        room.add("motor_clip", motor_clip_part, color="yellow")

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

        motor_clip_conn = Line(
            bowl_part.joints["motor_clip_seat"].location.position, motor_clip_part.joints["mount"].location.position
        )
        room.add("motor_clip_connector", motor_clip_conn)

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
            "motor_clip_label",
            "MOTOR CLIP",
            motor_clip_part.center() + Vector(-50, -10, 0),
            options=TextArgs(font_size=10),
        )

    def build_product(self, room: Room, mode: ProviderMode) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        bottom_cover_part = self.build_bottom_cover("bottom_cover", mode=mode).part
        lid_part = self.build_lid("lid", mode=mode).part
        drive_hub_part = self.build_drive_hub("drive_hub", mode=mode).part
        pump_cover_part = self.build_pump_cover("pump_cover", mode=mode).part
        motor_clip_part = self.build_motor_clip("motor_clip", mode=mode).part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drive_hub_part is not None
            and pump_cover_part is not None
            and motor_clip_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["impeller_post"].connect_to(impeller_part.joints["pin"])
        bowl_part.joints["motor_shaft"].connect_to(drive_hub_part.joints["motor"])
        bowl_part.joints["pump_cover_seat"].connect_to(pump_cover_part.joints["mount"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        bowl_part.joints["motor_clip_seat"].connect_to(motor_clip_part.joints["mount"])

        # Build and connect the LED cover using joints
        led_cover = self.build_led_cover("led_cover", mode=mode).part
        assert led_cover is not None
        bowl_part.joints["led_port"].connect_to(led_cover.joints["mount"])

        # 3. Add the positioned parts directly to the room
        if mode == ProviderMode.SIMULATE:
            room.add("bowl", bowl_part, color="grey", alpha=0.4)
            room.add("lid", lid_part, color="grey", alpha=0.4)
            room.add("impeller", impeller_part, color="grey")
            room.add("bottom_cover", bottom_cover_part, color="grey", alpha=0.4)
            room.add("led_cover", led_cover, color="grey", alpha=0.4)
            room.add("drive_hub", drive_hub_part, color="grey", alpha=0.4)
            room.add("pump_cover", pump_cover_part, color="grey", alpha=0.4)
            room.add("motor_clip", motor_clip_part, color="grey", alpha=0.4)
        else:
            room.add("bowl", bowl_part, color="grey", alpha=0.4)
            room.add("lid", lid_part, color="green", alpha=0.6)
            room.add("impeller", impeller_part, color="red")
            room.add("bottom_cover", bottom_cover_part, color="black", alpha=0.6)
            room.add("led_cover", led_cover, color="grey", alpha=0.4)
            room.add("drive_hub", drive_hub_part, color="red")
            room.add("pump_cover", pump_cover_part, color="grey", alpha=0.5)
            room.add("motor_clip", motor_clip_part, color="yellow")

        # 4. Build and add dummy PCBs for visualization and interference checking (non-printable)
        if mode != ProviderMode.SIMULATE:

            def make_motor() -> Part:
                with BuildPart() as motor:
                    # 1102 BLDC motor body (radius 6.9mm, height 9.3mm)
                    Cylinder(radius=6.9, height=9.3, align=(Align.CENTER, Align.CENTER, Align.MAX))
                    # 1.5mm shaft (radius 0.75mm, height 5.0mm)
                    Cylinder(radius=0.75, height=5.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                return cast(Part, motor.part)

            motor_part = make_motor()
            floor_z = self.settings.floor_z
            motor_part.location = Location((0, 0, floor_z - 6.5))
            room.add("motor", motor_part, color="grey", alpha=0.8)

            def make_pcb(w: float, l: float, h: float = 2.0) -> Part:
                with BuildPart() as pcb:
                    Box(w, l, h, align=(Align.CENTER, Align.CENTER, Align.CENTER))
                    fillet_r = min(1.5, min(w, l) / 2.0 - 0.1)
                    if fillet_r > 0.1:
                        fillet(pcb.edges().filter_by(Axis.Z), radius=fillet_r)
                return cast(Part, pcb.part)

            def make_sensor_pcb() -> Part:
                with BuildPart() as pcb:
                    Box(2.0, 25.0, 17.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))
                    fillet(pcb.edges().filter_by(Axis.X), radius=1.5)
                return cast(Part, pcb.part)

            floor_z = self.settings.floor_z
            t = self.settings.bowl_thickness

            # Load component footprints using Wiring class directly
            yaml_path = Path(__file__).parent / "wiring.yaml"
            wiring = Wiring(yaml_path, bowl_part)
            pcb_footprints = wiring.footprints
            for fp in pcb_footprints:
                if fp.name in ("motor", "led"):
                    continue
                w, l, thickness = fp.dimensions
                if fp.package == "tof_sensor":
                    joint_name = fp.name.replace("sensor_", "sensor_port_")
                    joint_loc = bowl_part.joints[joint_name].location
                    s_pcb = make_sensor_pcb()
                    s_pcb.location = joint_loc * Location((-18.3, 0, 0))
                    room.add(f"sensor_pcb_{fp.name.split('_')[-1]}", s_pcb, color="green", alpha=0.6)

                    # Model the emitter and receiver cones (25-degree Field of View)
                    def make_cone() -> Part:
                        h = 40.0
                        r1 = 0.5
                        r2 = r1 + h * math.tan(math.radians(12.5))
                        with BuildPart() as cone:
                            Cone(r1, r2, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                        return cast(Part, cone.part)

                    e_cone = make_cone()
                    e_cone.location = joint_loc * Location((-18.3, 0, 0)) * Location((2.0, -0.8, 0)) * Rot(0, 90, 0)
                    room.add(f"sensor_emitter_{fp.name.split('_')[-1]}", e_cone, color="red", alpha=0.3)

                    r_cone = make_cone()
                    r_cone.location = joint_loc * Location((-18.3, 0, 0)) * Location((2.0, 0.8, 0)) * Rot(0, 90, 0)
                    room.add(f"sensor_receiver_{fp.name.split('_')[-1]}", r_cone, color="blue", alpha=0.3)
                else:
                    pcb = make_pcb(w, l, thickness)
                    pcb.location = Location(fp.position, fp.rotation)
                    room.add(f"{fp.name}_pcb", pcb, color="green", alpha=0.6)

        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return the simulation hooks for the cat fountain."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        from .config import config_tune

        return {
            "tune": lambda target, sa: config_tune(self, target, sa),
        }

    def build_motor_clip(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the slide-in motor retaining clip (fork) to secure the motor in place."""
        clip_w = self.settings.motor_clip_width
        clip_l = self.settings.motor_clip_length
        clip_h = self.settings.motor_clip_thickness
        fork_w = self.settings.motor_clip_cutout_width

        with BuildPart() as clip:
            # Main flat slide plate extending South from the center (0, 0)
            # Extends from Y = -clip_l to Y = 5.0 (so U-cutout centered at Y=0 is 5mm from front)
            with Locations((0, -clip_l, 0)):
                Box(clip_w, clip_l + 5.0, clip_h, align=(Align.CENTER, Align.MIN, Align.MIN))

            # Subtract U-cutout centered at (0, 0) of diameter fork_w (radius fork_w / 2.0)
            Cylinder(
                radius=fork_w / 2.0,
                height=clip_h + 10.0,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT,
            )

            # Subtract the leading guide slot from Y = 0 to Y = 10.0 to break through the front (Y > 0)
            with Locations((0, 0, 0)):
                Box(fork_w, 20.0, clip_h + 10.0, align=(Align.CENTER, Align.MIN, Align.CENTER), mode=Mode.SUBTRACT)

            # Add a pull handle at the back (South end, Y = -clip_l)
            with Locations((0, -clip_l, 0)):
                Box(clip_w + 4.0, 3.0, clip_h + 3.0, align=(Align.CENTER, Align.MAX, Align.MIN))

            URDFMetadata(
                label=target,
                material="petg",
                density=self.settings.petg_density,
                boundary_friction=self.settings.petg_boundary_friction,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", clip.part, Location((0, 0, 0)))
        return clip

    def build_wiring_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build a 2D colored wiring diagram for the cat water fountain."""
        import math

        self.settings.diagram_options.style = DiagramStyle.COLOR
        self.settings.diagram_options.view_from = "top"

        r = self.settings.bowl_radius
        t = self.settings.bowl_thickness

        # Draw the bowl outline in grey
        with BuildSketch() as bowl_outline:
            Circle(radius=r)
            Circle(radius=r - t, mode=Mode.SUBTRACT)
        room.add("bowl_outline", bowl_outline.sketch, color="grey")

        # Draw the motor compartment outline in grey
        with BuildSketch() as motor_comp:
            Circle(radius=15.0)
            Circle(radius=14.0, mode=Mode.SUBTRACT)
        room.add("motor_compartment", motor_comp.sketch, color="grey")

        # Get bowl part to query joints and load/resolve Wiring
        bowl_part = self.build_bowl("bowl").part
        yaml_path = Path(__file__).parent / "wiring.yaml"
        wiring = Wiring(yaml_path, bowl_part)

        # Build the diagram using the diagram class
        diagram = WiringDiagram(wiring)
        diagram.build(room)
