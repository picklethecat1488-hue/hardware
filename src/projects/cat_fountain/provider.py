"""Cat fountain geometry provider."""

from functools import cached_property
from build123d import *  # type: ignore
import math
from model import method_cache, TextArgs, FluidConfig, FluidMotorConfig
from pathlib import Path
from provider import (
    Provider,
    Section,
    Mode as ProviderMode,
    discover_provider,
    Room,
    Simulate,
    URDFShape,
    URDFCollisionType,
    URDFCollisionShapeType,
    URDFBoundaryType,
)
from projects_config import CatFountainConfig
from typing import cast, Callable, Sequence, Any, Optional


@discover_provider
class CatFountainProvider(Provider):
    """Provider for cat fountain geometry."""

    water_sim: Optional[Any] = None

    @cached_property
    def default_config(self) -> CatFountainConfig:
        """Return the default configuration for the cat fountain project."""
        return CatFountainConfig(measurements_path=str(Path(__file__).parent / "measurements.yaml"))

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
            "fountain": self.build_fountain,
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
        tube_y = -(r - self.settings.tube_radius - 25.0)

        with BuildPart() as bowl:
            # Outer bowl body
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Subtract inner water reservoir (enclosed storage tank area above floor_z)
            with Locations((0, 0, floor_z)):
                Cylinder(
                    radius=r - t, height=h - floor_z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Subtract dry motor controller compartment under the floor
            with Locations((0, 0, 0)):
                Cylinder(
                    radius=r - t, height=floor_z - t, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
                )

            # Add bottom controller cover mounting tabs inside the dry compartment (at z = 4.0)
            for angle in [45, 135, 225, 315]:
                with Locations(Rot(0, 0, angle)):
                    with Locations((r - t - 5.0, 0, 4.0)):
                        # Mounting tab
                        Cylinder(radius=5.0, height=8.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
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
            with Locations((0, -r + t / 2.0, 12.5)):
                Box(12.0, 10.0, 6.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Charging port mounting holes on both sides (spacing 17mm: x = -8.5 and +8.5)
            for x_offset in [-8.5, 8.5]:
                with Locations((x_offset, -r + t / 2.0, 12.5)):
                    Cylinder(
                        radius=0.9,
                        height=10.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                        rotation=(90, 0, 0),
                    )

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

            # Cutouts for 3 proximity sensors along the North, East, and West directions of the motor room
            # North (0, r), East (r, 0), West (-r, 0)
            # Centered at z = 12.0. Window height increased to 8.0mm for a wider field of view.
            # North
            with Locations(Location((0, r - t / 2.0, 12), (30, 0, 0))):
                Box(8.0, 10.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
                # North sensor mounting holes (spacing 20.32mm (0.8") for Adafruit VL53L0X STEMMA QT: x = -10.16 and +10.16)
                for x_offset in [-10.16, 10.16]:
                    with Locations((x_offset, 0, 0)):
                        Cylinder(
                            radius=0.9,
                            height=10.0,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            mode=Mode.SUBTRACT,
                            rotation=(90, 0, 0),
                        )
            # East
            with Locations(Location((r - t / 2.0, 0, 12), (0, -30, 0))):
                Box(10.0, 8.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
                # East sensor mounting holes (spacing 20.32mm (0.8") for Adafruit VL53L0X STEMMA QT: y = -10.16 and +10.16)
                for y_offset in [-10.16, 10.16]:
                    with Locations((0, y_offset, 0)):
                        Cylinder(
                            radius=0.9,
                            height=10.0,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            mode=Mode.SUBTRACT,
                            rotation=(0, 90, 0),
                        )
            # West
            with Locations(Location((-r + t / 2.0, 0, 12), (0, 30, 0))):
                Box(10.0, 8.0, 8.0, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
                # West sensor mounting holes (spacing 20.32mm (0.8") for Adafruit VL53L0X STEMMA QT: y = -10.16 and +10.16)
                for y_offset in [-10.16, 10.16]:
                    with Locations((0, y_offset, 0)):
                        Cylinder(
                            radius=0.9,
                            height=10.0,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                            mode=Mode.SUBTRACT,
                            rotation=(0, 90, 0),
                        )

            # Drainage notch at the bottom rim of the outer wall
            with Locations((0, -r, 0.0)):
                Cylinder(radius=3.0, height=6.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # Attach metadata for URDF/simulation export
        bowl_part = cast(URDFShape, bowl.part)
        bowl_part.urdf_label = "bowl"
        bowl_part.urdf_material = self.settings.material
        bowl_part.urdf_density = self.settings.density
        bowl_part.urdf_boundary_friction = self.settings.boundary_friction
        bowl_part.urdf_contact_angle = self.settings.contact_angle
        bowl_part.urdf_parent = None
        bowl_part.urdf_joint_type = None
        bowl_part.urdf_collision_type = URDFCollisionType.ANALYTICAL
        bowl_part.urdf_boundary_shape = "cylinder"
        bowl_part.urdf_boundary_type = URDFBoundaryType.CAVITY
        bowl_part.urdf_boundary_radius = (r - t) * 0.001
        bowl_part.urdf_boundary_height = (h - floor_z) * 0.001
        bowl_part.urdf_boundary_thickness = t * 0.001
        bowl_part.urdf_boundary_xyz = f"0.0 0.0 {floor_z * 0.001}"
        bowl_part.urdf_boundary_rpy = "0.0 0.0 0.0"

        # Dimensions in meters
        R = r * 0.001
        H = h * 0.001
        thickness = t * 0.001
        R_i = R - thickness
        H_w = H - thickness

        primitives = []

        # 1. Base plate box (bottom of the dry compartment)
        primitives.append(
            {
                "type": URDFCollisionShapeType.BOX,
                "size": [R_i * 2.0, R_i * 2.0, thickness],
                "xyz": [0.0, 0.0, thickness / 2.0],
                "rpy": [0.0, 0.0, 0.0],
            }
        )

        # 2. Reservoir floor plate box (at z = floor_z)
        primitives.append(
            {
                "type": URDFCollisionShapeType.BOX,
                "size": [R_i * 2.0, R_i * 2.0, thickness],
                "xyz": [0.0, 0.0, floor_z * 0.001 - thickness / 2.0],
                "rpy": [0.0, 0.0, 0.0],
            }
        )

        # 3. Side walls segments (12 boxes)
        N_segments = 12
        R_mid = R_i + thickness / 2.0
        circ = 2.0 * math.pi * R_mid
        seg_width = circ / N_segments + 0.003  # Add 3mm overlap to prevent gaps

        for i in range(N_segments):
            theta = i * (2.0 * math.pi / N_segments)
            primitives.append(
                {
                    "type": URDFCollisionShapeType.BOX,
                    "size": [thickness, seg_width, H_w],
                    "xyz": [R_mid * math.cos(theta), R_mid * math.sin(theta), thickness + H_w / 2.0],
                    "rpy": [0.0, 0.0, theta],
                }
            )

        bowl_part.urdf_collision_primitives = primitives

        # Define joints
        RigidJoint("shaft", bowl.part, Location((0, tube_y, floor_z + 2.0)))
        RigidJoint("tube_socket", bowl.part, Location((0, tube_y, floor_z + 5.0)))
        RigidJoint("lid_seat", bowl.part, Location((0, 0, h)))
        RigidJoint("cover_seat", bowl.part, Location((0, 0, 0)))

        return bowl

    @method_cache
    def build_impeller(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the Archimedes screw impeller."""
        # Snug fit clearance of 0.2mm relative to the straight tube inner wall
        r = self.settings.tube_radius - self.settings.tube_thickness - 0.2
        h = self.settings.impeller_height
        shaft_r = self.settings.impeller_shaft_radius
        num_blades = self.settings.impeller_blades
        hub_r = shaft_r + 1.0

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
            blade_t = 1.5
            total_twist = self.settings.vane_twist  # Left-handed twist: CCW rotation lifts fluid UP
            N_layers = int(math.ceil(h))
            layer_h = h / N_layers
            for layer in range(N_layers):
                z_pos = layer * layer_h
                layer_angle = total_twist * (z_pos / h)
                for i in range(num_blades):
                    angle = i * (360.0 / num_blades) + layer_angle
                    with Locations(Rot(0, 0, angle)):
                        with Locations((hub_r + blade_w / 2.0, 0, z_pos)):
                            Box(blade_w, blade_t, layer_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        impeller_part = cast(URDFShape, impeller.part)
        impeller_part.urdf_label = "impeller"
        impeller_part.urdf_material = self.settings.material
        impeller_part.urdf_density = self.settings.density
        impeller_part.urdf_boundary_friction = self.settings.boundary_friction
        impeller_part.urdf_contact_angle = self.settings.contact_angle
        impeller_part.urdf_motor_type = "velocity"
        impeller_part.urdf_motor_target = 150.0
        impeller_part.urdf_motor_force = 10.0
        impeller_part.urdf_collision_type = URDFCollisionType.ANALYTICAL
        impeller_part.urdf_boundary_shape = "impeller"
        impeller_part.urdf_boundary_type = URDFBoundaryType.SOLID
        impeller_part.urdf_boundary_radius = r * 0.001
        impeller_part.urdf_boundary_height = h * 0.001
        impeller_part.urdf_boundary_thickness = shaft_r * 0.001
        impeller_part.urdf_boundary_xyz = "0.0 0.0 0.0"
        impeller_part.urdf_boundary_rpy = "0.0 0.0 0.0"

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

        tube_part = cast(URDFShape, tube.part)
        tube_part.urdf_label = "tube"
        tube_part.urdf_material = self.settings.material
        tube_part.urdf_density = self.settings.density
        tube_part.urdf_boundary_friction = self.settings.boundary_friction
        tube_part.urdf_contact_angle = self.settings.contact_angle
        tube_part.urdf_collision_type = URDFCollisionType.ANALYTICAL
        tube_part.urdf_boundary_shape = "tube"
        tube_part.urdf_boundary_type = URDFBoundaryType.SOLID_CAVITY
        tube_part.urdf_boundary_radius = r * 0.001
        tube_part.urdf_boundary_height = h * 0.001
        tube_part.urdf_boundary_thickness = t * 0.001
        tube_part.urdf_boundary_xyz = "0.0 0.0 0.0"
        tube_part.urdf_boundary_rpy = "0.0 0.0 0.0"

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
            Cylinder(radius=3.0, height=6.0, mode=Mode.SUBTRACT)

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

        # Attach metadata for URDF/simulation export
        cover_part = cast(URDFShape, cover.part)
        cover_part.urdf_label = "bottom_cover"
        cover_part.urdf_material = self.settings.material
        cover_part.urdf_density = self.settings.density
        cover_part.urdf_boundary_friction = self.settings.boundary_friction
        cover_part.urdf_contact_angle = self.settings.contact_angle
        cover_part.urdf_collision_type = URDFCollisionType.CONVEX
        cover_part.urdf_parent = "bowl"
        cover_part.urdf_joint_type = "fixed"

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
        tube_y = -(r - self.settings.tube_radius - 25.0)

        # Dimensions for the lid
        lid_r = r - t - 0.5  # 0.5mm clearance from inner bowl wall
        lid_h = 8.0

        with BuildPart() as lid:
            # Main lid disk
            Cylinder(radius=lid_r, height=lid_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

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
                Cylinder(radius=30.0, height=3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Add the lip ring (from z = 6.0 to z = 7.0 globally, height 1.0, on top of the terrace)
                with Locations((0, 0, 3.0)):
                    Cylinder(radius=30.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    Cylinder(radius=28.0, height=1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # --- DRAIN LIP (Radius 16.0 to 18.0, height 1.5 from z = 3.0 to z = 4.5) ---
            with Locations((0, 65.0, 3.0)):
                Cylinder(radius=18.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=16.0, height=1.5, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # --- integrated tube cover / spout cap at (0, tube_y) ---
            with Locations((0, tube_y, 0)):
                Cylinder(radius=13.0, height=20.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(radius=8.2, height=14.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                with Locations((0, 13.0, 6.0)):
                    Box(24.0, 10.0, 5.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

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

        # Attach metadata for URDF/simulation export
        lid_part = cast(URDFShape, lid.part)
        lid_part.urdf_label = "lid"
        lid_part.urdf_material = self.settings.material
        lid_part.urdf_density = self.settings.density
        lid_part.urdf_boundary_friction = self.settings.boundary_friction
        lid_part.urdf_contact_angle = self.settings.contact_angle
        lid_part.urdf_collision_type = URDFCollisionType.ANALYTICAL
        lid_part.urdf_parent = "bowl"
        lid_part.urdf_joint_type = "fixed"

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

            # Subtract central finger pull hole (radius 6.0mm)
            Cylinder(radius=6.0, height=cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

            # Add flush finger crossbar across the central hole
            Box(12.0, 2.5, cover_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

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

        # Attach metadata for URDF/simulation export
        cover_part = cast(URDFShape, cover.part)
        cover_part.urdf_label = "drain_cover"
        cover_part.urdf_material = self.settings.material
        cover_part.urdf_density = self.settings.density
        cover_part.urdf_boundary_friction = self.settings.boundary_friction
        cover_part.urdf_contact_angle = self.settings.contact_angle
        cover_part.urdf_collision_type = URDFCollisionType.CONVEX
        cover_part.urdf_parent = "bowl"
        cover_part.urdf_joint_type = "fixed"

        # Define joint at bottom center
        RigidJoint("mount", cover.part, Location((0, 0, 0)))

        return cover

    @method_cache
    def build_fountain(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Assemble all parts of the cat fountain."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])

        floor_z = 25.0
        tube_y = -(self.settings.bowl_radius - self.settings.tube_radius - 25.0)
        tube_part = self.build_tube("tube", mode=mode).part
        tube_part.locate(Location((0, tube_y, floor_z + 5.0)))

        bottom_cover_part = self.build_bottom_cover("bottom_cover", mode=mode).part
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])

        lid_part = self.build_lid("lid", mode=mode).part
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])

        drain_cover_part = self.build_drain_cover("drain_cover", mode=mode).part
        lid_part.joints["drain_socket"].connect_to(drain_cover_part.joints["mount"])

        with BuildPart() as f:
            f._obj = Part(
                children=[
                    bowl_part,
                    impeller_part,
                    tube_part,
                    bottom_cover_part,
                    lid_part,
                    drain_cover_part,
                ]
            )

        return f

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        tube_part = self.build_tube("tube").part
        bottom_cover_part = self.build_bottom_cover("bottom_cover").part
        lid_part = self.build_lid("lid").part
        drain_cover_part = self.build_drain_cover("drain_cover").part

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        lid_part.joints["drain_socket"].connect_to(drain_cover_part.joints["mount"])

        # 3. Explode the parts by translating their .location attributes
        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        tube_part.location = Location((0, 50, 25)) * tube_part.location
        bottom_cover_part.location = Location((0, 0, -40)) * bottom_cover_part.location
        lid_part.location = Location((0, 0, 40)) * lid_part.location
        drain_cover_part.location = Location((0, 0, 60)) * drain_cover_part.location

        # 4. Add the exploded parts to the room
        room.add("bowl", bowl_part, color="grey")
        room.add("impeller", impeller_part, color="red")
        room.add("tube", tube_part, color="blue")
        room.add("bottom_cover", bottom_cover_part, color="black")
        room.add("lid", lid_part, color="green")
        room.add("drain_cover", drain_cover_part, color="light_grey")

        # 5. Add connector lines indicating assembly paths
        impeller_conn = Line(
            bowl_part.joints["shaft"].location.position, impeller_part.joints["motor"].location.position
        )
        room.add("impeller_connector", impeller_conn)

        # 6. Add labels for each part
        room.add_label("bowl_label", "BOWL", bowl_part.center() + Vector(-120, -20, 10), options=TextArgs(font_size=16))
        room.add_label(
            "impeller_label", "IMPELLER", impeller_part.center() + Vector(-50, -10, 10), options=TextArgs(font_size=16)
        )
        room.add_label("tube_label", "TUBE", tube_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=16))
        room.add_label(
            "cover_label", "COVER", bottom_cover_part.center() + Vector(-80, 0, -10), options=TextArgs(font_size=16)
        )
        room.add_label("lid_label", "LID", lid_part.center() + Vector(-50, -10, 20), options=TextArgs(font_size=16))
        room.add_label(
            "drain_cover_label",
            "DRAIN COVER",
            drain_cover_part.center() + Vector(40, -10, 10),
            options=TextArgs(font_size=16),
        )

    def build_product(self, room: Room, mode: ProviderMode) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        tube_part = self.build_tube("tube", mode=mode).part
        bottom_cover_part = self.build_bottom_cover("bottom_cover", mode=mode).part
        lid_part = self.build_lid("lid", mode=mode).part
        drain_cover_part = self.build_drain_cover("drain_cover", mode=mode).part

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
        bowl_part.joints["cover_seat"].connect_to(bottom_cover_part.joints["mount"])
        bowl_part.joints["lid_seat"].connect_to(lid_part.joints["mount"])
        lid_part.joints["drain_socket"].connect_to(drain_cover_part.joints["mount"])

        # 3. Add the positioned parts directly to the room
        if mode == ProviderMode.SIMULATE:
            room.add("bowl", bowl_part, color="grey", alpha=0.4)
            room.add("tube", tube_part, color="blue", alpha=0.7)
            # Remove lid and drain cover from simulation to avoid confusion
        else:
            room.add("bowl", bowl_part, color="grey")
            room.add("tube", tube_part, color="blue")
            room.add("lid", lid_part, color="green")
            room.add("drain_cover", drain_cover_part, color="light_grey")
        room.add("impeller", impeller_part, color="red")
        room.add("bottom_cover", bottom_cover_part, color="black")
        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return simulation hooks for the cat fountain."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)
