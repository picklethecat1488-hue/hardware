"""Provider for manifold tube geometry."""

from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING
from model.app_config import AppConfig
from projects_config import TubeConfig
from provider import Provider, Action, Mode, discover_provider
from .builder import TubeBuilder
from .configurator import TubeConfigurator
from .viewer import TubeViewer


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
        return TubeConfig(measurements_path=str(Path(__file__).parent / "measurements.yaml"))

    @property
    def part(self) -> dict[str, Callable[..., Any]]:
        """A mapping of part names to their build handler methods."""
        return {name: self.builder.build_part for name in self.targets.supporting(Action.PART)}

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """A mapping of diagram names to their build handler methods."""
        return {name: self.builder.build_diagram for name in self.targets.supporting(Action.DIAGRAM)}

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        return {
            "mount": self.configurator.config_mount,
            "text": self.configurator.config_text,
        }

    @property
    def view(self) -> dict[str, Callable[[], list[tuple[Any, tuple[float, float, float, float]]]]]:
        """A mapping of room names to view functions."""
        return {
            "part_positions": self.viewer.view_part_positions,
            "overlay": self.viewer.view_overlay,
            "wire": self.viewer.view_wire,
            "sketch": self.viewer.view_sketch,
        }
