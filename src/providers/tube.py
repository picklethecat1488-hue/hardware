"""Provider for manifold tube geometry."""

from pathlib import Path
from typing import Any, Callable, Optional
from model import TubeConfig
from .provider import Provider
from .types import Action, Mode, Subassembly
from .utils import discover_provider


@discover_provider
class TubeProvider(Provider):
    """Provides tube geometry and configuration."""

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "tube"

    @property
    def default_config(self) -> TubeConfig:
        """Return the default tube configuration."""
        return TubeConfig(measurements_path=str(Path(__file__).parent / "tube_measurements.yaml"))

    @property
    def build(self) -> dict[Action, Callable[[str, Optional[Subassembly], Mode], Any]]:
        """A mapping of Actions to their handler methods."""
        return {
            Action.PART: self._build_part,
            Action.WIRE: self._build_wire,
            Action.SKETCH: self._build_sketch,
            Action.DIAGRAM: self._build_diagram,
        }

    @property
    def config(self) -> dict[Mode, Callable[[str, Optional[Subassembly]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        return {
            Mode.DEFAULT: self._config_default,
            Mode.MOUNT: self._config_mount,
            Mode.TEXT: self._config_text,
        }

    @property
    def view(self) -> dict[str, Callable[[], list[tuple[Any, tuple[float, float, float, float]]]]]:
        """A mapping of room names to view functions."""
        return {
            "part_positions": self._view_part_positions,
            "overlay": self._view_overlay,
        }

    def _build_part(self, target: str, subassembly: Optional[Subassembly], mode: Mode) -> Any:
        """Skeleton for building part geometry."""
        return "part_placeholder"

    def _build_wire(self, target: str, subassembly: Optional[Subassembly], mode: Mode) -> Any:
        """Skeleton for building wire geometry."""
        return "wire_placeholder"

    def _build_sketch(self, target: str, subassembly: Optional[Subassembly], mode: Mode) -> Any:
        """Skeleton for building sketch geometry."""
        return "sketch_placeholder"

    def _build_diagram(self, target: str, subassembly: Optional[Subassembly], mode: Mode) -> Any:
        """Skeleton for building assembly diagrams."""
        return "diagram_placeholder"

    def _config_default(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for default configuration logic."""
        pass

    def _config_mount(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for mount configuration logic."""
        pass

    def _config_text(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for text configuration logic."""
        pass

    def _view_part_positions(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Skeleton for part positions visualization."""
        return []

    def _view_overlay(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Skeleton for overlay visualization."""
        return []
