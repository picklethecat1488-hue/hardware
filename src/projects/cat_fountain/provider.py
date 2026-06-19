"""Cat fountain geometry provider."""

from functools import cached_property
from build123d import *  # type: ignore
from model import method_cache
from pathlib import Path
from provider import Provider, Section, Mode as ProviderMode, discover_provider, Room
from provider.types import URDFShape
from projects_config.cat_fountain_config import CatFountainConfig
from typing import cast, Callable, Sequence


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
        """A mapping of part names to their build handler methods."""
        return {
            "bowl": self.build_bowl,
            "impeller": self.build_impeller,
            "tube": self.build_tube,
            "spout": self.build_spout,
            "fountain": self.build_fountain,
        }

    @property
    def diagram(self) -> dict[str, Callable[[Room, Sequence[str], ProviderMode], None]]:
        """A mapping of diagram names to their build handler methods."""
        return {name: self.build_diagram for name in self.targets.supporting(Section.DIAGRAM)}

    @property
    def view(self) -> dict[str, Callable[[Room], None]]:
        """A mapping of room names to view functions."""
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
        tube_part.urdf_parent = "bowl"
        tube_part.urdf_joint_type = "fixed"

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
        spout_part.urdf_parent = "bowl"
        spout_part.urdf_joint_type = "fixed"

        return spout

    @method_cache
    def build_fountain(
        self, target: str, subassembly: str = "default", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Assemble all parts of the cat fountain."""
        with BuildPart() as f:
            # 1. Add bowl
            bowl = self.build_bowl("bowl", mode=mode)
            add(bowl.part)

            # 2. Add impeller
            t = self.settings.bowl_thickness
            impeller = self.build_impeller("impeller", mode=mode)
            bowl.part.joints["shaft"].connect_to(impeller.part.joints["motor"])
            add(impeller.part)

            # 3. Add tube
            tube_y = self.settings.bowl_radius - self.settings.tube_radius - 15.0
            tube = self.build_tube("tube", mode=mode)
            with Locations((0, tube_y, t + 5.0)):
                add(tube.part)

            # 4. Add spout
            spout = self.build_spout("spout", mode=mode)
            with Locations((0, tube_y, t + 5.0 + self.settings.tube_height - 10.0)):
                add(spout.part)

        return f

    @method_cache
    def build_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Build an assembly diagram for the cat fountain."""
        fountain = self.build_fountain("fountain", mode=mode)
        room.add("fountain", fountain)

    @method_cache
    def build_product(self, room: Room) -> None:
        """Place all parts of the cat fountain in the room for visualization/simulation."""
        t = self.settings.bowl_thickness
        tube_y = self.settings.bowl_radius - self.settings.tube_radius - 15.0

        # 1. Add bowl at (0, 0, 0)
        bowl = self.build_bowl("bowl")
        room.add("bowl", bowl, color="grey")

        # 2. Add impeller connected via joint to the bowl
        impeller = self.build_impeller("impeller")
        bowl.part.joints["shaft"].connect_to(impeller.part.joints["motor"])
        room.add("impeller", impeller, color="red")

        # 3. Add tube at (0, tube_y, t + 5.0)
        tube = self.build_tube("tube")
        moved_tube = Location((0, tube_y, t + 5.0)) * tube.part
        room.add("tube", moved_tube, color="blue")

        # 4. Add spout at the top of the tube
        spout = self.build_spout("spout")
        moved_spout = Location((0, tube_y, t + 5.0 + self.settings.tube_height - 10.0)) * spout.part
        room.add("spout", moved_spout, color="cyan")
