"""Cat fountain geometry provider."""

# No longer using cached_property
from build123d import *  # type: ignore
import math
from model import method_cache, TextArgs, FluidConfig, ShapeType, BoundaryType, BoundaryConfig
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
    URDFCollisionShapeType,
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
            "tube": self.build_tube,
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
        """Build the cat fountain bowl with integrated 2L reservoir, motor compartment, raised sealing boss, and screw mounts."""
        r = self.settings.bowl_radius
        h = self.settings.bowl_height
        t = self.settings.bowl_thickness
        pin_r = self.settings.impeller_shaft_radius
        floor_z = 25.0
        tube_y = 0.0

        with BuildPart() as bowl:
            # Outer bowl body
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract inner water reservoir (enclosed storage tank area above floor_z)
            with Locations((0, 0, floor_z)):
                reservoir_shape = Cylinder(
                    radius=r - t, height=h - floor_z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Subtract dry motor controller compartment under the floor
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=r - t, height=floor_z - t, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Add bottom controller cover mounting tabs inside the dry compartment (at z = 4.0)
            tab_height = (floor_z - t) - 4.0
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, 4.0)):
                        # Mounting tab (extends up to ceiling at floor_z - t)
                        Cylinder(radius=5.0, height=tab_height, align=(Align.CENTER, Align.CENTER, Align.MIN))
                        # Screw hole for self-drilling M3 plastic screw (1.2mm radius)
                        Cylinder(
                            radius=1.2, height=10.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Add top cover lid mounting tabs at the top rim (at z = h - 10)
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t, 0, h - 10.0)):
                        # Tab projecting inward from inner wall
                        Box(10.0, 10.0, 10.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                        # Vertical screw hole (1.2mm radius, 8mm deep from top)
                        with Locations((0, 0, 10.0)):
                            Cylinder(
                                radius=1.2,
                                height=8.0,
                                align=(Align.CENTER, Align.CENTER, Align.MAX),
                                mode=Mode.SUBTRACT,
                            )

            # Sump / collar for the tube connection (off-center)
            # Volute outer radius at bottom of tube is tube_radius + 3.0
            volute_outer_r = self.settings.tube_radius + 3.0
            with Locations((0, tube_y, floor_z)):
                # Outer collar for tube socket (height 12.0mm to be flush with central boss)
                Cylinder(radius=volute_outer_r + t, height=12.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Cut the outer collar in half (keep only the outer/rim-facing half)
                col_r = volute_outer_r + t
                Box(
                    col_r * 2.0 + 2.0,
                    col_r,
                    12.0 + 2.0,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
                # Inner pocket to fit the tube (step pocket: volute below, snug socket above)
                # 1. Lower volute chamber (height 5.0mm, radius volute_outer_r)
                Cylinder(
                    radius=volute_outer_r,
                    height=5.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
                # 2. Upper tube socket (height 7.0mm, starts at z = 5.0, radius tube_radius + 0.2)
                with Locations((0, 0, 5.0)):
                    Cylinder(
                        radius=self.settings.tube_radius + 0.2,
                        height=7.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # Raised central boss for impeller shaft (placement that won't leak water)
            # The top of the boss is at floor_z + 2.0.
            with Locations((0, tube_y, floor_z)):
                # Boss body
                Cylinder(radius=pin_r + 3.5, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Seal cavity (O-ring groove) inside the floor to prevent leakage
                with Locations((0, 0, -2.0)):
                    Cylinder(
                        radius=pin_r + 1.2,
                        height=2.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # Motor mounting boss projecting down from the ceiling of the dry compartment (centered at (0, tube_y))
            # The ceiling is at z = floor_z - t. The boss goes down by 15.0 mm.
            with Locations((0, tube_y, floor_z - t)):
                # Outer boss body
                Cylinder(radius=15.0, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
                # Pocket for the motor body (depth 15.0 mm, rectangular width 13.0mm, depth 11.0mm)
                Box(13.0, 11.0, 15.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the DC motor bracket to the pocket ceiling (M2 screws, spacing 17 mm)
            # Starts at z = 21.0 (floor_z - t) and goes up 2.5 mm (completely blind, does not penetrate reservoir floor at z = 25.0)
            for x_offset in [-8.5, 8.5]:
                with Locations((x_offset, tube_y, floor_z - t)):
                    Cylinder(radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the Adafruit NeoDriver LED board to the dry compartment ceiling (M2 screws, 20.32mm spacing)
            # Centered at (0, 40.0), starts at z = 21.0 and goes up 2.5 mm (completely blind)
            for x_offset in [-10.16, 10.16]:
                for y_offset in [40.0 - 10.16, 40.0 + 10.16]:
                    with Locations((x_offset, y_offset, floor_z - t)):
                        Cylinder(
                            radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Shaft hole running through the motor pocket ceiling, reservoir floor, and standpipe boss
            # Starts at pocket ceiling (z = 21.0) and goes up 6.0 mm to the top of standpipe boss (z = 27.0)
            with Locations((0, tube_y, floor_z - t)):
                Cylinder(
                    radius=pin_r + 0.2,
                    height=6.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Charging port hole in the outer wall of the dry compartment (back side, y = -r)
            # Centered at z = floor_z - t - 3.0 (so the top is flush with the ceiling at z = floor_z - t)
            with Locations((0, -r + t / 2.0, floor_z - t - 3.0)):
                Box(12.0, 10.0, 6.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the Adafruit bq25185 Charger board to the dry compartment ceiling (M2 screws, spacing 13.97mm in X and 24.13mm in Y)
            # Centered at (0, -79.0), starts at z = floor_z - t and goes up 2.5 mm (completely blind)
            for x_offset in [-6.985, 6.985]:
                for y_offset in [-79.0 - 12.065, -79.0 + 12.065]:
                    with Locations((x_offset, y_offset, floor_z - t)):
                        Cylinder(
                            radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Blind screw holes for mounting the Raspberry Pi Pico W to the dry compartment ceiling (M2 screws, spacing 17.78mm in X and 48.26mm in Y)
            # Centered at (-50.0, 0.0), starts at z = floor_z - t and goes up 2.5 mm (completely blind)
            for x_offset in [-50.0 - 8.89, -50.0 + 8.89]:
                for y_offset in [-24.13, 24.13]:
                    with Locations((x_offset, y_offset, floor_z - t)):
                        Cylinder(
                            radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Blind screw holes for mounting the L9110S DC Motor Driver to the dry compartment ceiling (M2 screws, spacing 20.0mm in X)
            # Centered at (50.0, 15.0), starts at z = floor_z - t and goes up 2.5 mm (completely blind)
            for x_offset in [50.0 - 10.0, 50.0 + 10.0]:
                with Locations((x_offset, 15.0, floor_z - t)):
                    Cylinder(radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the Adafruit INA219 Current Sensor to the dry compartment ceiling (M2 screws, spacing 20.32mm in X)
            # Centered at (50.0, -15.0), starts at z = floor_z - t and goes up 2.5 mm (completely blind)
            for x_offset in [50.0 - 10.16, 50.0 + 10.16]:
                with Locations((x_offset, -15.0, floor_z - t)):
                    Cylinder(radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Blind screw holes for mounting the Adafruit MAX17048 LiPo Fuel Gauge to the dry compartment ceiling (M2 screws, spacing 20.32mm in X)
            # Centered at (50.0, -45.0), starts at z = floor_z - t and goes up 2.5 mm (completely blind)
            for x_offset in [50.0 - 10.16, 50.0 + 10.16]:
                with Locations((x_offset, -45.0, floor_z - t)):
                    Cylinder(radius=1.0, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Radial ventilation slits in the back wall around the charging port
            # The charging port is at angle 270 (back). We place slits at angles 252, 261, 279, and 288.
            for angle in [252, 261, 279, 288]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t / 2.0, 0, 10.0)):
                        Box(t + 4.0, 2.5, 12.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Cutout for an RGB LED on the front-right side (at angle 75, z = 8.0) to serve as a state of charge indicator
            with Locations(Rot(0, 0, 75.0)):
                with Locations((r - t / 2.0, 0, 8.0)):
                    Cylinder(
                        radius=2.5,
                        height=10.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                        rotation=(0, 90, 0),
                    )

            # Proximity sensor mounts / cutouts at East (0), North (90), West (180)
            for s_angle in [0.0, 90.0, 180.0]:
                with Locations(Rot(0, 0, s_angle)):
                    with Locations(Location((r - t / 2.0, 0, 12.0), (0, -30, 0))):
                        # Flat mounting bosses on the INSIDE (dry compartment side) of the bowl wall
                        # Centered at X = -3.0 so they extend from X = -4.0 (boss face) to X = -2.0 (inner wall face)
                        for y_offset in [-10.16, 10.16]:
                            with Locations((-3.0, y_offset, 0)):
                                Cylinder(
                                    radius=2.2,
                                    height=2.0,
                                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                    rotation=(0, 90, 0),
                                )

                        # Flat sensor cover boss on the OUTSIDE (extends from local X = -5.0 to X = 5.0)
                        # Centered at local X = 0.0, height 10.0
                        Box(10.0, 10.0, 10.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))

                        # Subtract the sensor pocket (through hole to dry compartment, width 8 along local Y)
                        Box(14.0, 8.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

                        # Blind mounting holes starting from the inside (X = -4.0) and going 5.0mm deep to X = 1.0
                        # These are completely blind and not visible on the exterior of the bowl (outer wall is at X = 2.0)
                        for y_offset in [-10.16, 10.16]:
                            with Locations((-1.5, y_offset, 0)):
                                Cylinder(
                                    radius=0.9,
                                    height=5.0,
                                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                                    mode=Mode.SUBTRACT,
                                    rotation=(0, 90, 0),
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

        # Define joints
        RigidJoint("shaft", bowl.part, Location((0, tube_y, floor_z + 2.0)))
        RigidJoint("tube_socket", bowl.part, Location((0, tube_y, floor_z + 5.0)))
        RigidJoint("lid_seat", bowl.part, Location((0, 0, h)))
        RigidJoint("cover_seat", bowl.part, Location((0, 0, 0)))
        RigidJoint(
            "sensor_port_east",
            bowl.part,
            Location((r - t / 2.0, 0, 12.0), (0, -30, 0)) * Location((5.2, 0, 0)),
        )
        RigidJoint(
            "sensor_port_north",
            bowl.part,
            Location(Rot(0, 0, 90.0)) * Location((r - t / 2.0, 0, 12.0), (0, -30, 0)) * Location((5.2, 0, 0)),
        )
        RigidJoint(
            "sensor_port_west",
            bowl.part,
            Location(Rot(0, 0, 180.0)) * Location((r - t / 2.0, 0, 12.0), (0, -30, 0)) * Location((5.2, 0, 0)),
        )
        RigidJoint(
            "led_port",
            bowl.part,
            Location(Rot(0, 0, 75.0)) * Location((r - t / 2.0, 0, 8.0), (0, 90, 0)) * Location((0, 0, 2.0)),
        )

        return bowl

    @method_cache
    def build_impeller(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the Archimedes screw impeller."""
        # Snug fit clearance of 0.1mm relative to the straight tube inner wall (16.0mm ID tube)
        r = self.settings.tube_radius - self.settings.tube_thickness - 0.1
        h = self.settings.impeller_height
        shaft_r = self.settings.impeller_shaft_radius
        num_blades = self.settings.impeller_blades
        # Core shaft diameter is 9.6mm, so radius is 4.8mm
        hub_r = 4.8

        with BuildPart() as impeller:
            # Main hub body
            Cylinder(radius=hub_r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Integrated input shaft extending downwards from the bottom of the hub
            # Length 6.0mm to go exactly through the bowl standpipe boss to the motor pocket ceiling
            Cylinder(radius=shaft_r, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MAX))

            # Subtract hole in the bottom of the shaft to connect to the motor D-shaft
            # Diameter 3.1mm (radius 1.55mm) for a tight press-fit on the 3mm N20 motor shaft.
            # Depth 9.5mm from the bottom (goes 3.5mm into the main hub body)
            with Locations((0, 0, -6.0)):
                Cylinder(radius=1.55, height=9.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
            blade_w = r - hub_r
            blade_t = self.settings.impeller_radius * 0.125
            total_twist = self.settings.vane_twist
            num_rotations = abs(total_twist) / 360.0
            z_start = 6.0
            helix_height = h - z_start
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
    def build_tube(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the water delivery tube."""
        r = self.settings.tube_radius
        t = self.settings.tube_thickness
        h = self.settings.tube_height

        with BuildPart() as tube:
            # 1. Main straight tube outer body (from z = 0 to h)
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # 2. Subtract straight inner cavity (from z = 0 to h + 2.0)
            Cylinder(
                radius=r - t,
                height=h + 2.0,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )

            # 3. Subtract the pickup side slot (narrow slot at the bottom)
            Box(
                (r - t) * 2.0,
                r + 2.0,
                self.settings.slot_height,
                align=(Align.CENTER, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

            with URDFMetadata(
                label=target,
                material=self.settings.material,
                density=self.settings.density,
                boundary_friction=self.settings.boundary_friction,
                collision_type=URDFCollisionType.ANALYTICAL,
            ):
                URDFBoundary(
                    tube,
                    link_type=LinkType.TUBE,
                    shape=ShapeType.TUBE,
                    type=BoundaryType.SOLID_CAVITY,
                    height=cast(URDFShape, tube.part).urdf_height,
                    thickness=t * 0.001,
                    slot_height=self.settings.slot_height * 0.001,
                )

        RigidJoint("base", tube.part, Location((0, 0, 0)))
        RigidJoint("top", tube.part, Location((0, 0, h)))

        return tube

    @method_cache
    def build_bottom_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the detachable bottom cover for the motor controller compartment."""
        r = self.settings.bowl_radius
        t = self.settings.bowl_thickness
        cover_r = r - t - 0.2  # 0.2mm clearance

        with BuildPart() as cover:
            # Main cover disk
            Cylinder(radius=cover_r, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Concave top surface to permit drainage towards the center hole
            # Cone from z = 2.0 to z = 4.0, radius 0 at bottom and cover_r at top
            with Locations((0, 0, 2.0)):
                Cone(
                    bottom_radius=0.0,
                    top_radius=cover_r,
                    height=2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Drainage hole in the center
            Cylinder(radius=8.0, height=6.0, mode=Mode.SUBTRACT)

            # Notch for charging port access (at y = -cover_r, matching bowl's charging port)
            with Locations((0, -cover_r, 0.0)):
                Box(16.0, 10.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Recesses for rubber feet on the bottom surface (z = 0)
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((cover_r - 10.0, 0, 0.0)):
                        Cylinder(
                            radius=6.0, height=2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )

            # Countersunk screw holes matching bowl's bottom tabs (at radius = r - t - 5.0)
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, 0.0)):
                        # Clearance hole (goes from z=0 to z=4)
                        Cylinder(
                            radius=1.6, height=4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                        )
                        # Countersink on bottom surface (goes from z=0 to z=2)
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

        # Define joint
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

        # Dimensions for the lid
        lid_r = r - t - 0.5  # 0.5mm clearance from inner bowl wall
        lid_h = 8.0

        with BuildPart() as lid:
            # Main lid disk
            lid_disk = Cylinder(radius=lid_r, height=lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add mounting ears matching the bowl's tabs at 45, 135, 225, 315 degrees
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((lid_r - 2.0, 0, 0)):
                        Box(8.0, 12.0, lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract screw holes centered at radius r - t = 96.0
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t, 0, -1.0)):
                        Cylinder(
                            radius=1.5,
                            height=lid_h + 2.0,
                            align=(Align.CENTER, Align.CENTER, Align.MIN),
                            mode=Mode.SUBTRACT,
                        )
                        # Counterbore for screw heads (radius 3.0mm, depth 2.5mm from top)
                        with Locations((0, 0, lid_h - 1.5)):
                            Cylinder(
                                radius=3.0,
                                height=3.0,
                                align=(Align.CENTER, Align.CENTER, Align.MIN),
                                mode=Mode.SUBTRACT,
                            )

            # --- CENTRAL 100ML POCKET (Radius 80.0, depth 5.0, floor at z = 3.0) ---
            with BuildPart() as pocket_tool:
                Cylinder(radius=80.0, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                bottom_edge = pocket_tool.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[0]
                fillet(bottom_edge, radius=1.5)
            with Locations((0.0, 0.0, 3.0)):
                add(pocket_tool, mode=Mode.SUBTRACT)

            # --- CIRCULAR TERRACE LEVEL WITH SPOUT OUTLET (Radius 30.0, floor at z = 6.0) ---
            with Locations((0, tube_y, 3.0)):
                # Base terrace shelf (height 3.0, from z = 3.0 to z = 6.0)
                terrace_shelf = Cylinder(radius=30.0, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Add the lip ring (from z = 6.0 to z = 7.0 globally, height 1.0, on top of the terrace)
                with Locations((0, 0, 3.0)):
                    Cylinder(radius=30.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    Cylinder(radius=28.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # --- DRAIN LIP (Radius 16.0 to 18.0, height 1.5 from z = 3.0 to z = 4.5) ---
            with Locations((0, 65.0, 3.0)):
                Cylinder(radius=18.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=16.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # --- integrated tube cover / convex grate & cap at (0, tube_y) ---
            with Locations((0, tube_y, 0)):
                # 1. Add the convex dome starting flush with the terrace top platform at z = 6.0
                with Locations((0, 0, 6.0)):
                    socket_r = self.settings.tube_radius + 0.2
                    dome_out_r = socket_r + 1.0
                    dome_in_r = self.settings.tube_radius - self.settings.tube_thickness + 0.2
                    outer_dome = Sphere(radius=dome_out_r)
                    # Hollow the inside of the dome
                    Sphere(radius=dome_in_r, mode=Mode.SUBTRACT)
                    # 2. Cut grate slots in the dome ONLY up to the inner dome peak
                    # This leaves the top portion of the dome as a solid cap.
                    for angle in [0, 45, 90, 135]:
                        with Locations(Rot(0, 0, angle)):
                            Box(
                                2.0,
                                dome_out_r * 2.0,
                                dome_in_r,
                                align=(Align.CENTER, Align.CENTER, Align.MIN),
                                mode=Mode.SUBTRACT,
                            )
                # 3. Tube socket pocket (clearance fit for tube)
                # Starts at z = -10.0 to cut away the spherical bulge of the dome extending below z = 0.0
                with Locations((0, 0, -10.0)):
                    Cylinder(
                        radius=socket_r,
                        height=16.0,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

            # --- DRAIN HOLE & BAYONET MOUNT ---
            with Locations((0, 65.0, 0)):
                # Cage wall extending down to -15.0 (pocket depth 15mm)
                with Locations((0, 0, -15.0)):
                    Cylinder(radius=18.0, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(
                    radius=15.0, height=lid_h + 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )
                # Undercut pocket
                with Locations((0, 0, -1.5)):
                    Cylinder(radius=17.0, height=1.3, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                # Lip pocket (height 2.5, goes to 2.3, cutting cleanly through pocket floor)
                with Locations((0, 0, -0.2)):
                    Cylinder(radius=15.6, height=2.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                    # Taller entry slots (height 3.0, cuts cleanly through pocket floor)
                    for x_offset in [-16.0, 16.0]:
                        with Locations((x_offset, 0, 0)):
                            Box(4.0, 12.0, 3.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

                # Hollow out filter compartment (hollowing from -15.0 to -1.5)
                with Locations((0, 0, -15.0)):
                    Cylinder(
                        radius=16.0, height=13.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                    )
                # Grate at the bottom (-15.0)
                with Locations((0, 0, -15.0)):
                    Box(32.0, 3.0, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    Box(3.0, 32.0, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Lateral slots (from -12.0 to -4.0, height 8.0)
                with Locations((0, 0, -12.0)):
                    Box(4.0, 40.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                    Box(40.0, 4.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Trim any lip geometry sticking out at the front and back of the lid
            with Locations((0, 105.5, 0)):
                Box(120.0, 20.0, 30.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
            with Locations((0, -105.5, 0)):
                Box(120.0, 20.0, 30.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

        # Construct analytical boundary configurations
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

        # Define joint at the base of the lid for positioning
        RigidJoint("mount", lid.part, Location((0, 0, 0)))
        # Define joint at the bottom of the recessed step for the removable drain cover
        RigidJoint("drain_socket", lid.part, Location((0, 65.0, -1.5)))

        return lid

    @method_cache
    def build_drain_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the removable circular drain cover with locking tabs for the filter compartment."""
        # Fits inside the 15.6mm step with clearance
        cover_r = 15.3
        cover_h = 2.5

        with BuildPart() as cover:
            # Main disk
            Cylinder(radius=cover_r, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Add offset locking tabs on both sides (at x = -14.9 and x = 14.9)
            for x_offset in [-14.9, 14.9]:
                with Locations((x_offset, 0, 0)):
                    Box(3.8, 10.0, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Trim the outer corners of the tabs to fit within the 17.0mm radius undercut pocket with clearance
            Cylinder(radius=16.9, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.INTERSECT)

            # Subtract central finger pull hole (radius 6.0mm)
            Cylinder(radius=6.0, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Add flush finger crossbar across the central hole
            Box(15.0, 2.5, cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Pattern of drainage holes: 6 holes of radius 1.2mm at radius 10.5mm
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

        # Define joint at bottom center
        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    @method_cache
    def build_sensor_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build a push-fit flexible TPU cover for the proximity sensor port."""
        with BuildPart() as cover:
            # Outer flange (10.0mm x 10.0mm square, 1.5mm thick)
            # Aligned MIN along X so it starts at X=0 and goes to X=1.5
            Box(1.5, 10.0, 10.0, align=(Align.MIN, Align.CENTER, Align.CENTER))
            # Fillet the four outer corners of the flange
            fillet(cover.edges().filter_by(Axis.X), radius=2.0)

            # Plug insert (7.6mm x 7.6mm square to fit the 8.0mm x 8.0mm pocket with clearance, 6.0mm long)
            # Aligned MAX along X so it starts at X=0 and goes to X=-6.0
            Box(6.0, 7.6, 7.6, align=(Align.MAX, Align.CENTER, Align.CENTER))

            URDFMetadata(
                label=target,
                material="tpu",
                density=1.20,
                boundary_friction=0.50,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        # Define mount joint at the interface plane
        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    @method_cache
    def build_led_cover(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build a translucent push-fit cover/diffuser for the RGB status LED."""
        with BuildPart() as cover:
            # Outer flange (7.0mm diameter, 1.0mm thick)
            # Aligned MIN along Z so it goes from Z = 0 to Z = 1.0
            Cylinder(radius=3.5, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Plug insert (4.6mm diameter to fit 5.0mm hole with clearance, 3.0mm long)
            # Aligned MAX along Z so it goes from Z = 0 to Z = -3.0
            Cylinder(radius=2.3, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MAX))

            URDFMetadata(
                label=target,
                material="petg",
                density=1.27,
                boundary_friction=0.20,
                collision_type=URDFCollisionType.CONVEX,
                parent="bowl",
                joint_type=URDFJointType.FIXED,
            )

        # Define mount joint at the interface plane (where flange meets plug insert)
        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        tube_part = self.build_tube("tube").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drain_cover_part = self.build_drain_cover("drain_cover").part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and tube_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drain_cover_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
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
        assert tube_part.location is not None
        assert bottom_cover_part.location is not None
        assert lid_part.location is not None
        assert drain_cover_part.location is not None

        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        tube_part.location = Location((0, 50, 25)) * tube_part.location
        bottom_cover_part.location = Location((0, 0, -40)) * bottom_cover_part.location
        lid_part.location = Location((0, 0, 70)) * lid_part.location
        drain_cover_part.location = Location((0, 0, 60)) * drain_cover_part.location

        # 4. Add the exploded parts to the room
        room.add("bowl", bowl_part, color="grey")
        room.add("impeller", impeller_part, color="red")
        room.add("tube", tube_part, color="blue")
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
        room.add_label("tube_label", "TUBE", tube_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=10))
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
        # Label the first sensor cover and LED cover
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
        tube_part = self.build_tube("tube", mode=mode).part
        bottom_cover_part = self.build_bottom_cover("bottom_cover", mode=mode).part
        lid_part = self.build_lid("lid", mode=mode).part
        drain_cover_part = self.build_drain_cover("drain_cover", mode=mode).part

        assert (
            bowl_part is not None
            and impeller_part is not None
            and tube_part is not None
            and bottom_cover_part is not None
            and lid_part is not None
            and drain_cover_part is not None
        )

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
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
            room.add("tube", tube_part, color="grey", alpha=0.4)
            room.add("lid", lid_part, color="grey")
            room.add("drain_cover", drain_cover_part, color="grey")
            room.add("impeller", impeller_part, color="grey")
            room.add("bottom_cover", bottom_cover_part, color="grey")
            room.add("sensor_cover_east", sensor_cover_east, color="grey", alpha=0.4)
            room.add("sensor_cover_north", sensor_cover_north, color="grey", alpha=0.4)
            room.add("sensor_cover_west", sensor_cover_west, color="grey", alpha=0.4)
            room.add("led_cover", led_cover, color="grey", alpha=0.4)
        else:
            room.add("bowl", bowl_part, color="grey")
            room.add("tube", tube_part, color="blue")
            room.add("lid", lid_part, color="green")
            room.add("drain_cover", drain_cover_part, color="light_grey")
            room.add("impeller", impeller_part, color="red")
            room.add("bottom_cover", bottom_cover_part, color="black")
            room.add("sensor_cover_east", sensor_cover_east, color="grey")
            room.add("sensor_cover_north", sensor_cover_north, color="grey")
            room.add("sensor_cover_west", sensor_cover_west, color="grey")
            room.add("led_cover", led_cover, color="grey")
        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return simulation hooks for the cat fountain."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)
