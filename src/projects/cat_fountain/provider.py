"""Cat fountain geometry provider."""

from functools import cached_property
from build123d import *  # type: ignore
import math
from model import method_cache, TextArgs, FluidConfig, FluidMotorConfig
from pathlib import Path
from provider import Provider, Section, Mode as ProviderMode, discover_provider, Room, Simulate
from provider.types import URDFShape, URDFCollisionType, URDFCollisionShapeType, URDFBoundaryType
from projects_config.cat_fountain_config import CatFountainConfig
from typing import cast, Callable, Sequence, Any


@discover_provider
class CatFountainProvider(Provider):
    """Provider for cat fountain geometry."""

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
            "spout": self.build_spout,
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
        """Build the cat fountain bowl."""
        r = self.settings.bowl_radius
        h = self.settings.bowl_height
        t = self.settings.bowl_thickness
        pin_r = self.settings.impeller_shaft_radius
        pin_h = self.settings.impeller_height + 5.0

        with BuildPart() as bowl:
            # Outer bowl body
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Subtract inner bowl cavity to hollow it
            with Locations((0, 0, t)):
                Cylinder(radius=r - t, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
            # Standoff/socket for the tube connection (off-center)
            tube_y = r - self.settings.tube_radius - 15.0
            with Locations((0, tube_y, t)):
                # Outer collar for tube socket
                Cylinder(
                    radius=self.settings.tube_radius + t, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MIN)
                )
                # Cut the outer collar in half (keep only the outer/rim-facing half)
                col_r = self.settings.tube_radius + t
                Box(
                    col_r * 2.0 + 2.0,
                    col_r,
                    15.0 + 2.0,
                    align=(Align.CENTER, Align.MAX, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
                # Inner pocket to fit the tube
                Cylinder(
                    radius=self.settings.tube_radius,
                    height=16.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            # Central impeller shaft pin inside the tube socket
            with Locations((0, tube_y, t)):
                Cylinder(radius=pin_r, height=pin_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

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
        bowl_part.urdf_boundary_height = (h - t) * 0.001
        bowl_part.urdf_boundary_thickness = t * 0.001
        bowl_part.urdf_boundary_xyz = f"0.0 0.0 {t * 0.001}"
        bowl_part.urdf_boundary_rpy = "0.0 0.0 0.0"

        # Dimensions in meters
        R = r * 0.001
        H = h * 0.001
        thickness = t * 0.001
        R_i = R - thickness
        H_w = H - thickness

        primitives = []

        # 1. Bottom plate box
        primitives.append(
            {
                "type": URDFCollisionShapeType.BOX,
                "size": [R_i * 2.0, R_i * 2.0, thickness],
                "xyz": [0.0, 0.0, thickness / 2.0],
                "rpy": [0.0, 0.0, 0.0],
            }
        )

        # 2. Side walls segments (12 boxes)
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

        # Define RigidJoint for the central shaft (concentric with tube_socket)
        RigidJoint("shaft", bowl.part, Location((0, tube_y, t + 1.0)))

        # Define RigidJoint for the tube socket
        RigidJoint("tube_socket", bowl.part, Location((0, tube_y, t + 5.0)))

        return bowl

    @method_cache
    def build_impeller(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the impeller."""
        # Size the impeller to fit concentric inside the tube inner cavity
        r = self.settings.tube_radius - self.settings.tube_thickness - 1.2
        h = self.settings.impeller_height
        shaft_r = self.settings.impeller_shaft_radius
        num_blades = self.settings.impeller_blades
        hub_r = shaft_r + 1.0

        with BuildPart() as impeller:
            # Hub
            Cylinder(radius=hub_r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Subtract shaft hole (with clearance)
            Cylinder(
                radius=shaft_r + 0.2, height=h + 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT
            )
            # Add blades
            blade_w = r - hub_r
            blade_t = 1.5
            for i in range(num_blades):
                angle = i * (360.0 / num_blades)
                with Locations(Rot(0, 0, angle)):
                    with Locations((hub_r + blade_w / 2.0, 0, 0)):
                        Box(blade_w, blade_t, h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Attach metadata for URDF/simulation export
        impeller_part = cast(URDFShape, impeller.part)
        impeller_part.urdf_label = "impeller"
        impeller_part.urdf_material = self.settings.material
        impeller_part.urdf_density = self.settings.density
        impeller_part.urdf_boundary_friction = self.settings.boundary_friction
        impeller_part.urdf_contact_angle = self.settings.contact_angle
        impeller_part.urdf_motor_type = "velocity"
        impeller_part.urdf_motor_target = 15.0
        impeller_part.urdf_motor_force = 10.0
        impeller_part.urdf_collision_type = URDFCollisionType.ANALYTICAL
        impeller_part.urdf_boundary_shape = "impeller"
        impeller_part.urdf_boundary_type = URDFBoundaryType.SOLID
        impeller_part.urdf_boundary_radius = r * 0.001
        impeller_part.urdf_boundary_height = h * 0.001
        impeller_part.urdf_boundary_thickness = shaft_r * 0.001
        impeller_part.urdf_boundary_xyz = "0.0 0.0 0.0"
        impeller_part.urdf_boundary_rpy = "0.0 0.0 0.0"

        # Define RevoluteJoint for the impeller motor connection
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
            # Outer tube
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Cut a slot at the bottom of the tube facing the -Y direction (bowl center)
            # to prevent obstructing the impeller and allow water intake.
            Box(
                r * 2.0 + 2.0,
                r,
                15.0,
                align=(Align.CENTER, Align.MAX, Align.MIN),
                mode=Mode.SUBTRACT,
            )
            # Hollow inner cylinder
            Cylinder(radius=r - t, height=h + 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # Attach metadata for URDF/simulation export
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

        # Define joints for relative positioning and URDF linkage
        RigidJoint("base", tube.part, Location((0, 0, 0)))
        RigidJoint("top", tube.part, Location((0, 0, h - 10.0)))

        return tube

    @method_cache
    def build_spout(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the spout nozzle at the top of the tube."""
        r = self.settings.tube_radius
        t = self.settings.tube_thickness
        spout_len = self.settings.spout_length

        with BuildPart() as spout:
            # Collar that fits onto the tube
            Cylinder(radius=r, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Spout extension pointing in -Y direction
            with Locations((0, -spout_len / 2.0, 15.0 - r)):
                Box(r * 2.0, spout_len, r * 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # Hollow it
                Box(
                    (r - t) * 2.0,
                    spout_len + 2.0,
                    (r - t) * 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            # Hollow the main collar
            Cylinder(radius=r - t, height=16.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # Attach metadata for URDF/simulation export
        spout_part = cast(URDFShape, spout.part)
        spout_part.urdf_label = "spout"
        spout_part.urdf_material = self.settings.material
        spout_part.urdf_density = self.settings.density
        spout_part.urdf_boundary_friction = self.settings.boundary_friction
        spout_part.urdf_contact_angle = self.settings.contact_angle
        spout_part.urdf_collision_type = "concave"

        # Define RigidJoint for connecting to the tube
        RigidJoint("base", spout.part, Location((0, 0, 0)))

        return spout

    @method_cache
    def build_fountain(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Assemble all parts of the cat fountain."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])

        t = self.settings.bowl_thickness
        tube_y = self.settings.bowl_radius - self.settings.tube_radius - 15.0
        tube_part = self.build_tube("tube", mode=mode).part
        tube_part.locate(Location((0, tube_y, t + 5.0)))

        spout_part = self.build_spout("spout", mode=mode).part
        spout_part.locate(Location((0, tube_y, t + 5.0 + self.settings.tube_height - 10.0)))

        with BuildPart() as f:
            f._obj = Part(children=[bowl_part, impeller_part, tube_part, spout_part])

        return f

    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an exploded assembly diagram for the cat fountain."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        tube_part = self.build_tube("tube").part
        spout_part = self.build_spout("spout").part

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
        tube_part.joints["top"].connect_to(spout_part.joints["base"])

        # 3. Explode the parts by translating their .location attributes
        impeller_part.location = Location((0, 0, 50)) * impeller_part.location
        tube_part.location = Location((0, 50, 25)) * tube_part.location
        spout_part.location = Location((0, 100, 60)) * spout_part.location

        # 4. Add the exploded parts to the room
        room.add("bowl", bowl_part, color="grey")
        room.add("impeller", impeller_part, color="red")
        room.add("tube", tube_part, color="blue")
        room.add("spout", spout_part, color="cyan")

        # 5. Add connector lines indicating assembly paths
        impeller_conn = Line(
            bowl_part.joints["shaft"].location.position, impeller_part.joints["motor"].location.position
        )
        room.add("impeller_connector", impeller_conn)

        # 6. Add labels for each part
        room.add_label("bowl_label", "BOWL", bowl_part.center() + Vector(-100, -20, 10), options=TextArgs(font_size=16))
        room.add_label(
            "impeller_label", "IMPELLER", impeller_part.center() + Vector(-50, -10, 10), options=TextArgs(font_size=16)
        )
        room.add_label("tube_label", "TUBE", tube_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=16))
        room.add_label("spout_label", "SPOUT", spout_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=16))

    def build_product(self, room: Room, mode: ProviderMode) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl", mode=mode).part
        impeller_part = self.build_impeller("impeller", mode=mode).part
        tube_part = self.build_tube("tube", mode=mode).part
        spout_part = self.build_spout("spout", mode=mode).part

        # 2. Position them in their standard assembled configuration using joints
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
        tube_part.joints["top"].connect_to(spout_part.joints["base"])

        # 3. Add the positioned parts directly to the room
        room.add("bowl", bowl_part, color="grey")
        room.add("impeller", impeller_part, color="red")
        if mode == ProviderMode.SIMULATE:
            room.add("tube", tube_part, color="blue", alpha=0.4)
        else:
            room.add("tube", tube_part, color="blue")
        room.add("spout", spout_part, color="cyan")
        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return simulation hooks for the cat fountain."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)
