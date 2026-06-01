"""Provider for manifold tube geometry."""

from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING
from model.app_config import AppConfig
from projects_config import TubeConfig
from provider import Provider, Action, Mode, Subassembly, discover_provider
from .tube_builder import TubeBuilder
from .tube_configurator import TubeConfigurator
from .tube_viewer import TubeViewer


@discover_provider
class TubeProvider(Provider):
    """Provides tube geometry and configuration."""

    def __init__(self, *args, **kwargs):
        """Initialize the provider and its builder."""
        super().__init__(*args, **kwargs)
        # The orchestrator handles the thread pool lifecycle, so we extract it here.
        executor = getattr(self.orchestrator, "executor", None)
        self.builder = TubeBuilder(config=self.app_config, tube_config=self.settings, executor=executor)
        self.configurator = TubeConfigurator(
            builder=self.builder,
            config=self.app_config,
            tube_config=self.settings,
            executor=executor,
            logger=self.logger,
        )
        self.viewer = TubeViewer(
            builder=self.builder,
            config=self.app_config,
            tube_config=self.settings,
            executor=executor,
        )

    @property
    def default_config(self) -> TubeConfig:
        """Return the default tube configuration."""
        return TubeConfig(measurements_path=str(Path(__file__).parent / "tube_measurements.yaml"))

    @property
    def build(self) -> dict[Action, Callable[..., Any]]:
        """A mapping of Actions to their handler methods."""
        return {
            Action.PART: self.builder.build_part,
            Action.WIRE: self.builder.build_wire,
            Action.SKETCH: self.builder.build_sketch,
            Action.DIAGRAM: self.builder.build_diagram,
        }

    @property
    def config(self) -> dict[Mode, Callable[[str, Optional[Subassembly]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        return {
            Mode.DEFAULT: self.configurator.config_default,
            Mode.MOUNT: self.configurator.config_mount,
            Mode.TEXT: self.configurator.config_text,
        }

    @property
    def view(self) -> dict[str, Callable[[], list[tuple[Any, tuple[float, float, float, float]]]]]:
        """A mapping of room names to view functions."""
        return {
            "part_positions": self.viewer.view_part_positions,
            "overlay": self.viewer.view_overlay,
            "tube_profile": self.viewer.view_tube_profile,
        }
