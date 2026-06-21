"""Cat fountain geometry provider."""

from functools import cached_property
from build123d import *  # type: ignore
import math
from model import method_cache, TextArgs
from pathlib import Path
import pybullet as p
from provider import Provider, Section, Mode as ProviderMode, discover_provider, Room, Simulate
from provider.types import URDFShape
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
    def petg_density(self) -> float:
        """Return the density of PETG material dynamically from manifest configuration."""
        materials_cfg = self.manifest.get("material", {})
        return float(materials_cfg.get("petg", {}).get("density", 1.27))

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
    def view(self) -> dict[str, Callable[[Room], None]]:
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
            # Central impeller shaft pin
            with Locations((0, 0, t)):
                Cylinder(radius=pin_r, height=pin_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # Standoff/socket for the tube connection (off-center)
            tube_y = r - self.settings.tube_radius - 15.0
            with Locations((0, tube_y, t)):
                # Outer collar for tube socket
                Cylinder(
                    radius=self.settings.tube_radius + t, height=15.0, align=(Align.CENTER, Align.CENTER, Align.MIN)
                )
                # Inner pocket to fit the tube
                Cylinder(
                    radius=self.settings.tube_radius,
                    height=16.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

        # Attach metadata for URDF/simulation export
        bowl_part = cast(URDFShape, bowl.part)
        bowl_part.urdf_label = "bowl"
        bowl_part.urdf_material = "petg"
        bowl_part.urdf_density = self.petg_density
        bowl_part.urdf_parent = None
        bowl_part.urdf_joint_type = None

        # Define RigidJoint for the central shaft
        RigidJoint("shaft", bowl.part, Location((0, 0, t + 1.0)))

        # Define RigidJoint for the tube socket
        tube_y = self.settings.bowl_radius - self.settings.tube_radius - 15.0
        RigidJoint("tube_socket", bowl.part, Location((0, tube_y, t + 5.0)))

        return bowl

    @method_cache
    def build_impeller(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the impeller."""
        r = self.settings.impeller_radius
        h = self.settings.impeller_height
        shaft_r = self.settings.impeller_shaft_radius
        num_blades = self.settings.impeller_blades
        hub_r = r * 0.4

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
        impeller_part.urdf_material = "petg"
        impeller_part.urdf_density = self.petg_density

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
            # Hollow inner cylinder
            Cylinder(radius=r - t, height=h + 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # Attach metadata for URDF/simulation export
        tube_part = cast(URDFShape, tube.part)
        tube_part.urdf_label = "tube"
        tube_part.urdf_material = "petg"
        tube_part.urdf_density = self.petg_density

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
        spout_part.urdf_material = "petg"
        spout_part.urdf_density = self.petg_density

        # Define RigidJoint for connecting to the tube
        RigidJoint("base", spout.part, Location((0, 0, 0)))

        return spout

    @method_cache
    def build_fountain(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Assemble all parts of the cat fountain."""
        bowl = self.build_bowl("bowl", mode=mode)
        impeller = self.build_impeller("impeller", mode=mode)
        bowl.part.joints["shaft"].connect_to(impeller.part.joints["motor"])

        t = self.settings.bowl_thickness
        tube_y = self.settings.bowl_radius - self.settings.tube_radius - 15.0
        tube = self.build_tube("tube", mode=mode)
        tube.part.locate(Location((0, tube_y, t + 5.0)))

        spout = self.build_spout("spout", mode=mode)
        spout.part.locate(Location((0, tube_y, t + 5.0 + self.settings.tube_height - 10.0)))

        with BuildPart() as f:
            f._obj = Part(children=[bowl.part, impeller.part, tube.part, spout.part])

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

        tube_conn = Line(bowl_part.joints["tube_socket"].location.position, tube_part.joints["base"].location.position)
        room.add("tube_connector", tube_conn)

        spout_conn = Line(tube_part.joints["top"].location.position, spout_part.joints["base"].location.position)
        room.add("spout_connector", spout_conn)

        # 6. Add labels for each part
        room.add_label("bowl_label", "BOWL", bowl_part.center() + Vector(-100, -20, 10), options=TextArgs(font_size=16))
        room.add_label(
            "impeller_label", "IMPELLER", impeller_part.center() + Vector(-50, -10, 10), options=TextArgs(font_size=16)
        )
        room.add_label("tube_label", "TUBE", tube_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=16))
        room.add_label("spout_label", "SPOUT", spout_part.center() + Vector(40, 10, 10), options=TextArgs(font_size=16))

    def build_product(self, room: Room) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        bowl_part = self.build_bowl("bowl").part
        impeller_part = self.build_impeller("impeller").part
        tube_part = self.build_tube("tube").part
        spout_part = self.build_spout("spout").part

        # 2. Add bowl at (0, 0, 0)
        room.add("bowl", bowl_part, color="grey")

        # 3. Add impeller connected via joint to the bowl
        bowl_part.joints["shaft"].connect_to(impeller_part.joints["motor"])
        room.add("impeller", impeller_part, color="red")

        # 4. Add tube connected to the bowl via joint
        bowl_part.joints["tube_socket"].connect_to(tube_part.joints["base"])
        room.add("tube", tube_part, color="blue")

        # 5. Add spout connected to the tube via joint
        tube_part.joints["top"].connect_to(spout_part.joints["base"])
        room.add("spout", spout_part, color="cyan")
        self.room = room

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Map simulation hook names to handler methods for the cat fountain."""
        return {
            Simulate.SETUP: self.setup_simulation,
            Simulate.STEP: self.step_simulation,
        }

    def get_impeller_idx(self, body_id: int, physics_client: int) -> int | None:
        """Get the motor index of the impeller."""
        num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
        for i in range(num_joints):
            info = p.getJointInfo(body_id, i, physicsClientId=physics_client)
            joint_name = info[1].decode("utf-8")
            if "impeller" in joint_name or "motor" in joint_name:
                return i
        return None

    def setup_simulation(self, body_id: int, physics_client: int, sim_name: str) -> None:
        """Configure velocity motor control and pour 0.5L of water."""
        motor_idx = self.get_impeller_idx(body_id, physics_client)
        if motor_idx is not None:
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=motor_idx,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=15.0,
                force=10.0,
                physicsClientId=physics_client,
            )

        # Apply top rear camera view using the room helper
        if hasattr(self, "room") and self.room:
            self.room.reset_camera(physics_client, view_from="top rear")

        r_s = 0.003
        self.vol_s = (4 / 3) * math.pi * (r_s**3)
        target_vol = 0.0001
        N = int(round(target_vol / self.vol_s))

        positions = []
        step = 2.2 * r_s
        z_val = 0.004 + r_s
        while len(positions) < N and z_val < 0.120:
            x_val = -0.076 + r_s
            while x_val < 0.076 - r_s:
                y_val = -0.076 + r_s
                while y_val < 0.076 - r_s:
                    if len(positions) >= N:
                        break
                    if x_val * x_val + y_val * y_val > (0.076 - r_s) ** 2:
                        y_val += step
                        continue
                    if x_val * x_val + y_val * y_val < (0.015 + r_s) ** 2:
                        y_val += step
                        continue
                    tube_y = 0.057
                    if x_val * x_val + (y_val - tube_y) ** 2 < (0.010 + r_s) ** 2:
                        y_val += step
                        continue
                    positions.append((x_val, y_val, z_val))
                    y_val += step
                x_val += step
            z_val += step

        sphere_col = p.createCollisionShape(p.GEOM_SPHERE, radius=r_s, physicsClientId=physics_client)
        sphere_vis = p.createVisualShape(
            p.GEOM_SPHERE, radius=r_s, rgbaColor=[0.0, 0.5, 1.0, 0.8], physicsClientId=physics_client
        )

        self.water_body_ids = []
        self.spout_water_ids = set()
        self.fallen_out_water_ids = set()

        for pos in positions:
            bid = p.createMultiBody(
                baseMass=0.001,
                baseCollisionShapeIndex=sphere_col,
                baseVisualShapeIndex=sphere_vis,
                basePosition=pos,
                physicsClientId=physics_client,
            )
            p.changeDynamics(
                bid,
                -1,
                linearDamping=0.05,
                angularDamping=0.05,
                lateralFriction=0.1,
                restitution=0.0,
                physicsClientId=physics_client,
            )
            self.water_body_ids.append(bid)

    def step_simulation(self, body_id: int, physics_client: int, step_index: int, sim_name: str) -> str | None:
        """Step simulation, check termination."""
        for w_id in self.water_body_ids:
            pos, _ = p.getBasePositionAndOrientation(w_id, physicsClientId=physics_client)
            x, y, z = pos

            if z >= 0.095 and y < 0.030:
                self.spout_water_ids.add(w_id)

            if z < 0.0 or (x**2 + y**2 > 0.090**2):
                self.fallen_out_water_ids.add(w_id)

        spout_vol = len(self.spout_water_ids) * self.vol_s * 1000
        fallen_vol = len(self.fallen_out_water_ids) * self.vol_s * 1000

        # Terminate early if 0.1L falls out of bowl or spout
        if spout_vol >= 0.1:
            return "0.1L of water spout volume reached"
        if fallen_vol >= 0.1:
            return "0.1L of water fell out of bowl"

        return None
