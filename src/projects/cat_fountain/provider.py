"""Cat fountain geometry provider."""

from build123d import *  # type: ignore
import math
from model import method_cache, TextArgs, ShapeType, BoundaryType
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
)
from projects_config import CatFountainConfig
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
            "drain_cover": self.build_drain_cover,
            "sensor_cover": self.build_sensor_cover,
            "sensor_cover_east": self.build_sensor_cover,
            "sensor_cover_north": self.build_sensor_cover,
            "sensor_cover_west": self.build_sensor_cover,
            "led_cover": self.build_led_cover,
        }

    @property
    def diagram(self) -> dict[str, Callable[[Room, Sequence[str], ProviderMode], None]]:
        """Map diagram names to their build handler methods."""
        return {name: self.build_diagram for name in self.targets.supporting(Section.DIAGRAM)}

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
        floor_z = 32.0
        tube_y = 0.0

        # PCB settings
        hole_r = self.settings.pcb_hole_radius
        boss_r = self.settings.pcb_boss_radius

        with BuildPart() as bowl:
            # Outer bowl body
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

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

            # Subtract dry motor controller compartment under the floor
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=r - t, height=floor_z - t, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Helper to add mounting tabs that automatically extend between z_start and z_end
            def add_mounting_tabs(
                angles: list[float],
                radial_position: float,
                z_start: float,
                z_end: float,
                shape_fn: Callable[[float], Any],
                hole_radius: float,
                hole_depth: float,
                hole_align_top: bool = True,
            ):
                height = abs(z_end - z_start)
                z_min = min(z_start, z_end)
                for angle in angles:
                    with Locations(Rot(0, 0, angle)):
                        with Locations((radial_position, 0, z_min)):
                            shape_fn(height)
                            if hole_align_top:
                                with Locations((0, 0, height)):
                                    Cylinder(
                                        radius=hole_radius,
                                        height=hole_depth,
                                        align=(Align.CENTER, Align.CENTER, Align.MAX),
                                        mode=Mode.SUBTRACT,
                                    )
                            else:
                                Cylinder(
                                    radius=hole_radius,
                                    height=hole_depth,
                                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                                    mode=Mode.SUBTRACT,
                                )

            # Add bottom controller cover mounting tabs (extending from cover thickness to dry compartment ceiling)
            cover_thickness = 4.0
            add_mounting_tabs(
                angles=[45, 135, 225, 315],
                radial_position=r - t - 5.0,
                z_start=cover_thickness,
                z_end=floor_z - t,
                shape_fn=lambda h: Cylinder(radius=5.0, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN)),
                hole_radius=1.2,
                hole_depth=10.0,
                hole_align_top=False,
            )

            # Add top cover lid mounting tabs (extending from 10mm below the lid step to the bottom of the lid step)
            add_mounting_tabs(
                angles=[45, 135, 225, 315],
                radial_position=r - t - 5.0,
                z_start=h - self.settings.lid_step_depth - 10.0,
                z_end=h - self.settings.lid_step_depth,
                shape_fn=lambda h: Box(10.0, 10.0, h, align=(Align.CENTER, Align.CENTER, Align.MIN)),
                hole_radius=1.2,
                hole_depth=8.0,
                hole_align_top=True,
            )

            # --- INTEGRATED TUBE ---
            # Tube runs from floor_z = 32.0 to floor_z + tube_height = 102.0
            with Locations((0, tube_y, floor_z)):
                Cylinder(
                    radius=self.settings.tube_radius,
                    height=self.settings.tube_height,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

            # Subtract the tube inner cavity
            with Locations((0, tube_y, floor_z + 2.0)):
                Cylinder(
                    radius=self.settings.tube_radius - self.settings.tube_thickness,
                    height=self.settings.tube_height + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Subtract the intake slot at the bottom (+Y side of the integrated tube wall)
            with Locations((0, tube_y, floor_z)):
                Box(
                    2.0 * (self.settings.tube_radius - self.settings.tube_thickness),
                    self.settings.tube_radius + 2.0,
                    self.settings.slot_height,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Raised central boss for impeller shaft (placement that won't leak water)
            with Locations((0, tube_y, floor_z)):
                # Boss body
                Cylinder(radius=pin_r + 3.5, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Subtract shaft hole going through the boss and floor (from Z=21.0 to Z=27.0, height 6.0)
                with Locations((0, 0, -t)):
                    Cylinder(
                        radius=pin_r + 0.1,
                        height=2.0 + t,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )
                # Seal cavity (O-ring groove) inside the floor to prevent leakage
                with Locations((0, 0, -2.0)):
                    Cylinder(
                        radius=pin_r + 1.2,
                        height=2.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # Motor mounting boss projecting down from the ceiling of the dry compartment (centered at (0, tube_y))
            with Locations((0, tube_y, floor_z - t)):
                # Outer boss body (20.0mm deep to fit N20 motor)
                Cylinder(radius=15.0, height=20.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
                # Pocket for the motor body
                Box(13.0, 11.0, 20.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the DC motor bracket to the pocket ceiling (M2 screws, spacing 17 mm)
            for x_offset in [-self.settings.motor_spacing_x / 2.0, self.settings.motor_spacing_x / 2.0]:
                with Locations((x_offset, tube_y, floor_z - t)):
                    Cylinder(
                        radius=hole_r, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
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
                dys = [-spacing_y / 2.0, spacing_y / 2.0] if spacing_y is not None else [0.0]

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

            # Mount all PCBs in the dry compartment using the helper
            pcb_mounts = [
                (
                    50.0,
                    -45.0,
                    self.settings.fuel_gauge_spacing_x,
                    self.settings.fuel_gauge_spacing_y,
                    self.settings.fuel_gauge_standoff_height,
                    "FUEL",
                ),
                (
                    -50.0,
                    0.0,
                    self.settings.pico_spacing_x,
                    self.settings.pico_spacing_y,
                    self.settings.pico_standoff_height,
                    "PICO W",
                ),
                (
                    0.0,
                    -79.0,
                    self.settings.charger_spacing_x,
                    self.settings.charger_spacing_y,
                    self.settings.charger_standoff_height,
                    "CHARGER",
                ),
                (
                    0.0,
                    40.0,
                    self.settings.neodriver_spacing_x,
                    self.settings.neodriver_spacing_y,
                    self.settings.neodriver_standoff_height,
                    "NEODRIVE",
                ),
                (
                    50.0,
                    -15.0,
                    self.settings.current_monitor_spacing_x,
                    self.settings.current_monitor_spacing_y,
                    self.settings.current_monitor_standoff_height,
                    "CURRENT",
                ),
                (
                    50.0,
                    15.0,
                    self.settings.motor_driver_spacing_x,
                    self.settings.motor_driver_spacing_y,
                    self.settings.motor_driver_standoff_height,
                    "MOTOR DRV",
                ),
            ]
            for cx, cy, sx, sy, sh, lbl in pcb_mounts:
                add_pcb_mount(cx, cy, sx, sy, sh, lbl)

            # Charging port hole in the outer wall of the dry compartment (back side, y = -r)
            with Locations((0, -r + t / 2.0, floor_z - t - 5.0)):
                Box(12.0, 10.0, 6.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

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
            boss_sy = self.settings.sensor_boss_y
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
                                8.0,
                                12.0,
                                align=(Align.MAX, Align.CENTER, Align.CENTER),
                                mode=Mode.SUBTRACT,
                            )

                        # Flat mounting standoff posts on the INSIDE (dry compartment side) of the bowl wall
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
                            # Shift location by 5.0 mm in Z (parent X direction) to center the extended cylinder
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
                    thickness=t * 0.001,
                )
                with Locations((0, tube_y, floor_z)):
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
                    height=self.settings.tube_height * 0.001,
                    thickness=self.settings.tube_thickness * 0.001,
                    slot_height=self.settings.slot_height * 0.001,
                )

        # Define joints
        RigidJoint("shaft", bowl.part, Location((0, tube_y, floor_z + 2.0)))
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
        """Build the vortex impeller (with helical Archimedes screw vanes)."""
        r = self.settings.tube_radius - self.settings.tube_thickness - 0.1
        h = self.settings.impeller_height
        shaft_r = self.settings.impeller_shaft_radius
        num_blades = self.settings.impeller_blades
        hub_r = 4.8

        with BuildPart() as impeller:
            Cylinder(radius=hub_r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            Cylinder(radius=shaft_r, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MAX))

            # D-shaped shaft hole to prevent motor shaft slippage (radius 1.55mm, flat at X = 1.05mm)
            with BuildSketch() as hole_sketch:
                Circle(radius=1.55)
                with Locations((1.05 + 5.0, 0)):
                    Rectangle(10.0, 10.0, mode=Mode.SUBTRACT)
            ext_hole = extrude(hole_sketch.sketch, amount=10.5, mode=Mode.PRIVATE)
            impeller.part -= Location((0, 0, -6.0)) * ext_hole  # type: ignore
            blade_w = r - hub_r
            blade_t = self.settings.impeller_radius * 0.125
            total_twist = self.settings.vane_twist
            num_rotations = abs(total_twist) / 360.0
            z_start = 6.0
            helix_height = h - z_start - 5.0
            if num_rotations > 0:
                pitch = helix_height / num_rotations
                for i in range(num_blades):
                    angle = i * (360.0 / num_blades)
                    path = cast(
                        Wire,
                        Location((0, 0, z_start))
                        * Rot(0, 0, angle)
                        * Helix(
                            pitch=pitch,
                            height=helix_height,
                            radius=hub_r,
                            lefthand=(total_twist < 0),
                        ),
                    )
                    with BuildSketch(path ^ 0) as profile:
                        Rectangle(blade_w, blade_t, align=(Align.MAX, Align.CENTER))
                    sweep(profile.sketch, path=path, is_frenet=False)
            else:
                for i in range(num_blades):
                    angle = i * (360.0 / num_blades)
                    with Locations(Rot(0, 0, angle)):
                        with Locations((hub_r + blade_w / 2.0, 0, z_start)):
                            Box(blade_w, blade_t, helix_height, align=(Align.CENTER, Align.CENTER, Align.MIN))

            with URDFMetadata(
                label=target,
                material=self.settings.material,
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
                motor_type=URDFMotorType.VELOCITY,
                motor_target=120.0,
                motor_force=10.0,
            ):
                URDFBoundary(
                    impeller,
                    link_type=LinkType.IMPELLER,
                    shape=ShapeType.IMPELLER,
                    type=BoundaryType.SOLID,
                    height=cast(URDFShape, impeller.part).urdf_height,
                    thickness=shaft_r * 0.001,
                    vane_twist=self.settings.vane_twist,
                    vane_thickness=blade_t * 0.001,
                    num_vanes=self.settings.impeller_blades,
                )

        RevoluteJoint(label="motor", to_part=impeller.part, axis=Axis((0, 0, 0), (0, 0, 1)), angular_range=(0, 360))

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

            # Funnel-shaped top surface to drain water towards the central drain hole
            with Locations((0, 0, 1.5)):
                Cone(
                    bottom_radius=0.0,
                    top_radius=80.0,
                    height=2.5,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            Cylinder(radius=self.settings.bottom_cover_drain_radius, height=6.0, mode=Mode.SUBTRACT)

            with Locations((0, -cover_r, 0.0)):
                Box(16.0, 10.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((cover_r - 10.0, 0, 0.0)):
                        Cylinder(
                            radius=6.0, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, 0.0)):
                        Cylinder(
                            radius=1.6, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )
                        Cylinder(
                            radius=3.2,
                            height=2.0,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )

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
        tube_y = 0.0

        lid_r = r - t + self.settings.lid_step_width - self.settings.lid_clearance
        lid_h = 8.0
        step_d = self.settings.lid_step_depth
        step_w = self.settings.lid_step_width
        clearance = self.settings.lid_clearance

        with BuildPart() as lid:
            lid_disk = Cylinder(radius=lid_r, height=lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            with Locations((0, 0, 0)):
                Cylinder(
                    radius=lid_r + 2.0, height=step_d, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )
                Cylinder(radius=r - t - clearance, height=step_d, align=(Align.CENTER, Align.CENTER, Align.MIN))

            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, 0)):
                        Box(10.0, 12.0, lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, -1.0)):
                        Cylinder(
                            radius=1.5,
                            height=lid_h + 2.0,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )
                        with Locations((0, 0, lid_h - 1.5)):
                            Cylinder(
                                radius=3.0,
                                height=3.0,
                                align=(Align.CENTER, Align.CENTER, Align.MIN),
                                mode=Mode.SUBTRACT,
                            )

            with BuildPart() as pocket_tool:
                Cylinder(radius=80.0, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                bottom_edge = pocket_tool.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[0]
                fillet(bottom_edge, radius=1.5)
            with Locations((0.0, 0.0, 3.0)):
                add(pocket_tool, mode=Mode.SUBTRACT)

            with Locations((0, tube_y, 3.0)):
                terrace_shelf = Cylinder(radius=30.0, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((0, 0, 3.0)):
                    Cylinder(radius=30.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    Cylinder(radius=28.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            with Locations((0, 65.0, 3.0)):
                Cylinder(radius=18.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=16.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            with Locations((0, tube_y, 0)):
                with Locations((0, 0, 6.0)):
                    socket_r = self.settings.tube_radius + self.settings.tube_lid_clearance
                    dome_out_r = socket_r + 1.5
                    dome_in_r = (
                        self.settings.tube_radius - self.settings.tube_thickness + self.settings.tube_lid_clearance
                    )
                    outer_dome = Sphere(radius=dome_out_r)
                    Sphere(radius=dome_in_r, mode=Mode.SUBTRACT)
                    for angle in [0, 45, 90, 135]:
                        with Locations(Rot(0, 0, angle)):
                            Box(
                                self.SLOT_WIDTH,
                                self.SLOT_LENGTH,
                                dome_in_r,
                                align=(Align.CENTER, Align.CENTER, Align.MIN),
                                mode=Mode.SUBTRACT,
                            )
                    # Retention boss extending down from inner sphere ceiling to limit impeller vertical travel (added after cuts)
                    with Locations((0, 0, dome_in_r)):
                        Cylinder(radius=3.0, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
                with Locations((0, 0, -10.0)):
                    Cylinder(
                        radius=socket_r,
                        height=16.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            with Locations((0, 65.0, 0)):
                with Locations((0, 0, -15.0)):
                    Cylinder(radius=18.0, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(
                    radius=self.settings.drain_hole_radius,
                    height=lid_h + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
                with Locations((0, 0, -1.5)):
                    Cylinder(radius=17.0, height=1.3, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                with Locations((0, 0, -0.2)):
                    Cylinder(radius=15.6, height=3.2, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                    for x_offset in [-15.5, 15.5]:
                        with Locations((x_offset, 0, 0)):
                            Box(5.0, 12.0, 10.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

                with Locations((0, 0, -15.0)):
                    Cylinder(
                        radius=16.0, height=13.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                    )
                with Locations((0, 0, -15.0)):
                    Box(32.0, 3.0, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    Box(3.0, 32.0, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((0, 0, -12.0)):
                    Box(4.0, 40.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                    Box(40.0, 4.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

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
                thickness=3.0 * 0.001,
                xyz=(0.0, 0.0, self.settings.lid_pocket_z_offset * 0.001),
                rpy=(0.0, 0.0, 0.0),
                has_drain=True,
                drain_hole_y=self.settings.drain_hole_y * 0.001,
                drain_hole_radius=self.settings.drain_hole_radius * 0.001,
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
                has_tube=False,
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
                drain_hole_y=-self.settings.drain_hole_y * 0.001,
                drain_hole_radius=self.settings.drain_hole_radius * 0.001,
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
        RigidJoint("drain_socket", lid.part, Location((0, 65.0, -1.5)))

        return lid

    @method_cache
    def build_drain_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the removable circular drain cover with locking tabs for the filter compartment."""
        cover_r = 15.3
        cover_h = 2.5

        with BuildPart() as cover:
            Cylinder(radius=cover_r, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Downward hollow boss to center/retain the cover (outer radius 5.5mm, inner radius 4.0mm, height 5.0mm)
            Cylinder(radius=5.5, height=5.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
            Cylinder(radius=4.0, height=5.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

            for x_offset in [-14.9, 14.9]:
                with Locations((x_offset, 0, 0)):
                    Box(3.8, 10.0, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))

            Cylinder(radius=16.9, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.INTERSECT)

            Cylinder(radius=4.0, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            Box(15.0, 2.5, cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            for i in range(6):
                angle = i * (360.0 / 6)
                with Locations(Rot(0, 0, angle)):
                    with Locations((10.5, 0, -1.0)):
                        Cylinder(
                            radius=1.2,
                            height=cover_h + 2.0,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )

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
    def build_sensor_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build a push-fit flexible TPU cover for the proximity sensor port."""
        with BuildPart() as cover:
            with Locations((0, 0, -2.0)):
                Box(1.5, 10.0, 14.0, align=(Align.MIN, Align.CENTER, Align.CENTER))
            fillet(cover.edges().filter_by(Axis.X), radius=2.0)

            with Locations((0, 0, -2.0)):
                Box(6.0, 7.6, 11.6, align=(Align.MAX, Align.CENTER, Align.CENTER))

            URDFMetadata(
                label=target,
                material="tpu",
                density=1.20,
                boundary_friction=0.50,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

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
                density=1.27,
                boundary_friction=0.20,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drain_cover_part = self.build_drain_cover("drain_cover").part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drain_cover_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        lid_part.joints["drain_socket"].connect_to(drain_cover_part.joints["mount"])

        # Build and connect the three sensor covers using joints
        sensor_cover_east = self.build_sensor_cover("sensor_cover_east").part
        sensor_cover_north = self.build_sensor_cover("sensor_cover_north").part
        sensor_cover_west = self.build_sensor_cover("sensor_cover_west").part
        assert sensor_cover_east is not None and sensor_cover_north is not None and sensor_cover_west is not None

        bowl_part.joints["sensor_port_east"].connect_to(sensor_cover_east.joints["mount"])
        bowl_part.joints["sensor_port_north"].connect_to(sensor_cover_north.joints["mount"])
        bowl_part.joints["sensor_port_west"].connect_to(sensor_cover_west.joints["mount"])

        # Build and connect the LED cover
        led_cover = self.build_led_cover("led_cover").part
        assert led_cover is not None
        bowl_part.joints["led_port"].connect_to(led_cover.joints["mount"])

        # Explode outwards by translating 30.0 mm along local X axis for sensor covers, and Z axis for LED cover
        assert sensor_cover_east.location is not None
        assert sensor_cover_north.location is not None
        assert sensor_cover_west.location is not None
        assert led_cover.location is not None

        sensor_cover_east.location = sensor_cover_east.location * Location((30.0, 0, 0))
        sensor_cover_north.location = sensor_cover_north.location * Location((30.0, 0, 0))
        sensor_cover_west.location = sensor_cover_west.location * Location((30.0, 0, 0))
        led_cover.location = led_cover.location * Location((0, 0, 30.0))

        # 3. Explode the parts by translating their .location attributes
        assert impeller_part.location is not None
        assert bottom_cover_part.location is not None
        assert lid_part.location is not None
        assert drain_cover_part.location is not None

        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        bottom_cover_part.location = Location((0, 0, -40)) * bottom_cover_part.location
        lid_part.location = Location((0, 0, 70)) * lid_part.location
        drain_cover_part.location = Location((0, 0, 60)) * drain_cover_part.location

        # 4. Add the exploded parts to the room
        room.add("bowl", bowl_part, color="grey")
        room.add("impeller", impeller_part, color="red")
        room.add("bottom_cover", bottom_cover_part, color="black")
        room.add("lid", lid_part, color="green")
        room.add("drain_cover", drain_cover_part, color="light_grey")
        room.add("sensor_cover_east", sensor_cover_east, color="grey")
        room.add("sensor_cover_north", sensor_cover_north, color="grey")
        room.add("sensor_cover_west", sensor_cover_west, color="grey")
        room.add("led_cover", led_cover, color="grey")

        # 5. Add connector lines indicating assembly paths
        impeller_conn = Line(
            bowl_part.joints["shaft"].location.position, impeller_part.joints["motor"].location.position
        )
        room.add("impeller_connector", impeller_conn)

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
            "drain_cover_label",
            "DRAIN COVER",
            drain_cover_part.center() + Vector(40, -10, 10),
            options=TextArgs(font_size=10),
        )
        room.add_label(
            "sensor_cover_label",
            "SENSOR COVER",
            sensor_cover_east.center() + Vector(30, 0, 10),
            options=TextArgs(font_size=10),
        )
        room.add_label(
            "led_cover_label",
            "LED COVER",
            led_cover.center() + Vector(30, 0, 10),
            options=TextArgs(font_size=10),
        )

    def build_product(self, room: Room, mode: ProviderMode) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        bottom_cover_part = self.build_bottom_cover("bottom_cover", mode=mode).part
        lid_part = self.build_lid("lid", mode=mode).part
        drain_cover_part = self.build_drain_cover("drain_cover", mode=mode).part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drain_cover_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        lid_part.joints["drain_socket"].connect_to(drain_cover_part.joints["mount"])

        # Build and connect the three sensor covers using joints
        sensor_cover_east = self.build_sensor_cover("sensor_cover_east", mode=mode).part
        sensor_cover_north = self.build_sensor_cover("sensor_cover_north", mode=mode).part
        sensor_cover_west = self.build_sensor_cover("sensor_cover_west", mode=mode).part
        assert sensor_cover_east is not None and sensor_cover_north is not None and sensor_cover_west is not None

        bowl_part.joints["sensor_port_east"].connect_to(sensor_cover_east.joints["mount"])
        bowl_part.joints["sensor_port_north"].connect_to(sensor_cover_north.joints["mount"])
        bowl_part.joints["sensor_port_west"].connect_to(sensor_cover_west.joints["mount"])

        # Build and connect the LED cover using joints
        led_cover = self.build_led_cover("led_cover", mode=mode).part
        assert led_cover is not None
        bowl_part.joints["led_port"].connect_to(led_cover.joints["mount"])

        # 3. Add the positioned parts directly to the room
        if mode == ProviderMode.SIMULATE:
            room.add("bowl", bowl_part, color="grey", alpha=0.4)
            room.add("lid", lid_part, color="grey", alpha=0.4)
            room.add("drain_cover", drain_cover_part, color="grey")
            room.add("impeller", impeller_part, color="grey")
            room.add("bottom_cover", bottom_cover_part, color="grey", alpha=0.4)
            room.add("sensor_cover_east", sensor_cover_east, color="grey", alpha=0.4)
            room.add("sensor_cover_north", sensor_cover_north, color="grey", alpha=0.4)
            room.add("sensor_cover_west", sensor_cover_west, color="grey", alpha=0.4)
            room.add("led_cover", led_cover, color="grey", alpha=0.4)
        else:
            room.add("bowl", bowl_part, color="grey")
            room.add("lid", lid_part, color="green", alpha=0.6)
            room.add("drain_cover", drain_cover_part, color="light_grey")
            room.add("impeller", impeller_part, color="red")
            room.add("bottom_cover", bottom_cover_part, color="black", alpha=0.6)
            room.add("sensor_cover_east", sensor_cover_east, color="grey", alpha=0.4)
            room.add("sensor_cover_north", sensor_cover_north, color="grey", alpha=0.4)
            room.add("sensor_cover_west", sensor_cover_west, color="grey", alpha=0.4)
            room.add("led_cover", led_cover, color="grey", alpha=0.4)

        # 4. Build and add dummy PCBs for visualization and interference checking (non-printable)
        if mode != ProviderMode.SIMULATE:

            def make_motor() -> Part:
                with BuildPart() as motor:
                    Box(12.0, 10.0, 24.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
                    with BuildSketch() as shaft_sketch:
                        Circle(radius=1.5)
                        with Locations((1.0 + 5.0, 0)):
                            Rectangle(10.0, 10.0, mode=Mode.SUBTRACT)
                    extrude(shaft_sketch.sketch, amount=10.0)
                return cast(Part, motor.part)

            motor_part = make_motor()
            floor_z = 32.0
            t = self.settings.bowl_thickness
            motor_part.location = Location((0, 0, floor_z - t))
            room.add("motor", motor_part, color="grey", alpha=0.8)

            def make_pcb(w: float, l: float, h: float = 2.0) -> Part:
                with BuildPart() as pcb:
                    Box(w, l, h, align=(Align.CENTER, Align.CENTER, Align.CENTER))
                    fillet(pcb.edges().filter_by(Axis.Z), radius=1.5)
                return cast(Part, pcb.part)

            floor_z = 32.0
            t = self.settings.bowl_thickness

            # Standard PCBs configuration: (name, center_x, center_y, spacing_x, spacing_y, standoff_height)
            pcb_configs = [
                (
                    "fuel_gauge",
                    50.0,
                    -45.0,
                    self.settings.fuel_gauge_spacing_x,
                    self.settings.fuel_gauge_spacing_y,
                    self.settings.fuel_gauge_standoff_height,
                ),
                (
                    "pico",
                    -50.0,
                    0.0,
                    self.settings.pico_spacing_x,
                    self.settings.pico_spacing_y,
                    self.settings.pico_standoff_height,
                ),
                (
                    "charger",
                    0.0,
                    -79.0,
                    self.settings.charger_spacing_x,
                    self.settings.charger_spacing_y,
                    self.settings.charger_standoff_height,
                ),
                (
                    "neodriver",
                    0.0,
                    40.0,
                    self.settings.neodriver_spacing_x,
                    self.settings.neodriver_spacing_y,
                    self.settings.neodriver_standoff_height,
                ),
                (
                    "current_monitor",
                    50.0,
                    -15.0,
                    self.settings.current_monitor_spacing_x,
                    self.settings.current_monitor_spacing_y,
                    self.settings.current_monitor_standoff_height,
                ),
                (
                    "motor_driver",
                    50.0,
                    15.0,
                    self.settings.motor_driver_spacing_x,
                    self.settings.motor_driver_spacing_y,
                    self.settings.motor_driver_standoff_height,
                ),
            ]

            for name, cx, cy, sx, sy, sh in pcb_configs:
                pcb = make_pcb(sx + 4.0, sy + 4.0)
                pcb.location = Location((cx, cy, floor_z - t - sh - 1.0))
                room.add(f"{name}_pcb", pcb, color="green", alpha=0.6)

            # Proximity Sensor PCBs: 2.0mm thick, 25.0mm local Y, 17.0mm local Z. Centered at local X = -16.3 relative to joint
            def make_sensor_pcb() -> Part:
                with BuildPart() as pcb:
                    Box(2.0, 25.0, 17.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))
                    fillet(pcb.edges().filter_by(Axis.X), radius=1.5)
                return cast(Part, pcb.part)

            for name, joint_name in [
                ("sensor_pcb_east", "sensor_port_east"),
                ("sensor_pcb_north", "sensor_port_north"),
                ("sensor_pcb_west", "sensor_port_west"),
            ]:
                s_pcb = make_sensor_pcb()
                joint_loc = bowl_part.joints[joint_name].location
                s_pcb.location = joint_loc * Location((-18.3, 0, 0))
                room.add(name, s_pcb, color="green", alpha=0.6)

        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return simulation hooks for the cat fountain."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)
