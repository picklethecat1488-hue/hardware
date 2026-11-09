"""Cat fountain geometry provider."""

from build123d import *  # type: ignore
import math
from model import (
    method_cache,
    TextArgs,
    ShapeType,
    BoundaryType,
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
    IntakePort,
    DrainPort,
    TubePort,
    FlowSlot,
    SpoutDeflection,
    ImpellerVanes,
    MagneticCoupling,
    LinkType,
    WiringDiagram,
)
from projects_config import CatFountainConfig
from . import layouts
from typing import cast, Callable, Sequence, Any, Optional

from .cad import CatFountainCAD, make_snap_ring, make_filleted_pocket_tool
from .pcb import (
    build_cat_fountain_wiring,
    build_cat_fountain_wiring_diagram,
    build_rp2040_key,
    build_tmc6300_key,
)


@discover_provider
class CatFountainProvider(CatFountainCAD, Provider):
    """Geometry, PCB, and wiring provider for the Cat Fountain project."""

    # Slot cutter constants (treating length as an infinite cutting plane)
    SLOT_WIDTH = 2.0
    SLOT_LENGTH = 100.0

    # RP2040 GPIO Key constants for wiring diagram
    RP2040_KEY_BOX_WIDTH = 64.0
    RP2040_KEY_BOX_HEIGHT = 50.0
    RP2040_KEY_CENTER = (-95.0, -88.0)
    RP2040_KEY_CORNER_RADIUS = 2.5
    RP2040_KEY_SWATCH_LENGTH = 4.0
    RP2040_KEY_DOT_RADIUS = 0.5
    RP2040_KEY_ROW_PITCH = 3.6
    RP2040_KEY_LEFT_GPIOS = (
        "GP4",
        "GP5",
        "GP6",
        "GP7",
        "GP9",
        "GP10",
        "GP11",
        "GP12",
        "GP13",
        "GP14",
    )
    RP2040_KEY_RIGHT_GPIOS = (
        "GP26",
        "GP22",
        "GP21",
        "GP20",
        "GP19",
        "GP18",
        "GP17",
        "GP16",
    )

    # TMC6300 Pin Key constants for wiring diagram
    TMC6300_KEY_BOX_WIDTH = 54.0
    TMC6300_KEY_BOX_HEIGHT = 48.0
    TMC6300_KEY_CENTER = (95.0, 88.0)
    TMC6300_KEY_CORNER_RADIUS = 2.5
    TMC6300_KEY_SWATCH_LENGTH = 4.0
    TMC6300_KEY_DOT_RADIUS = 0.5
    TMC6300_KEY_ROW_PITCH = 3.6
    TMC6300_KEY_ENTRIES = (
        ("UH", "UH: High-side Phase U"),
        ("UL", "UL: Low-side Phase U"),
        ("VH", "VH: High-side Phase V"),
        ("VL", "VL: Low-side Phase V"),
        ("WH", "WH: High-side Phase W"),
        ("WL", "WL: Low-side Phase W"),
        ("U", "U: Phase U Output"),
        ("V", "V: Phase V Output"),
        ("W", "W: Phase W Output"),
    )

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
            "motor_hub": self.build_motor_hub,
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
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the cat fountain bowl with integrated 2L reservoir, integrated tube, motor compartment, and screw mounts."""
        return self._build_bowl_impl(target.split("/")[-1])

    @method_cache
    def build_impeller(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the lightweight centrifugal impeller (magnetic-drive)."""
        return self._build_impeller_impl(target.split("/")[-1])

    @method_cache
    def build_bottom_cover(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the detachable bottom cover for the motor controller compartment."""
        return self._build_bottom_cover_impl(target.split("/")[-1])

    @method_cache
    def build_lid(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the top cover lid which acts as a drinking shelf and covers/stabilizes the vertical delivery tube."""
        return self._build_lid_impl(target.split("/")[-1])

    @method_cache
    def build_led_cover(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build a translucent push-fit cover/diffuser for the RGB status LED."""
        return self._build_led_cover_impl(target.split("/")[-1])

    @method_cache
    def build_drive_hub(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the dry-side magnet drive hub mounted on the motor D-shaft."""
        return self._build_drive_hub_impl(target.split("/")[-1])

    @method_cache
    def build_pump_cover(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the revised wet-side pump cover that slides down the tube and mounts directly over the tube and casing."""
        return self._build_pump_cover_impl(target.split("/")[-1])

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

    @method_cache
    def build_motor_hub(
        self, target: str, subassembly: Optional[str] = None, mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the dedicated motor drive hub assembly bracket mounting the motor and Hall sensor (BUG-LUSTROUS-COCOON-669)."""
        return self._build_motor_hub_impl(target.split("/")[-1])

    @property
    def wiring(self) -> Wiring:
        """Construct in-memory Wiring container for Cat Fountain using BuildComponents and BuildWiring."""
        bowl_part = self.build_bowl("bowl").part
        return build_cat_fountain_wiring(parent_part=bowl_part)

    def build_wiring_diagram(self, room: Room, targets: Sequence[str], mode: ProviderMode) -> None:
        """Render the 2D colored wiring diagram for the cat water fountain."""
        build_cat_fountain_wiring_diagram(self, room, targets, mode)

    def _build_rp2040_key(self, room: Room, wiring: Wiring) -> None:
        """Add a dedicated RP2040 GPIO pinout key in the bottom-left corner of the wiring diagram."""
        build_rp2040_key(self, room, wiring)

    def _build_tmc6300_key(self, room: Room, wiring: Wiring) -> None:
        """Add a dedicated TMC6300 pinout key in the top-right corner of the wiring diagram."""
        build_tmc6300_key(self, room, wiring)
