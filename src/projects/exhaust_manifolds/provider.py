"""Provider for manifold tube geometry."""

from pathlib import Path
from functools import cached_property
from typing import Any, Callable, Optional, TYPE_CHECKING
from model.app_config import AppConfig
from projects_config import ExhaustManifoldsConfig
from provider import Provider, Section, Mode, discover_provider, Room
from .builder import ExhaustManifoldsBuilder
from .configurator import ExhaustManifoldsConfigurator
from .viewer import ExhaustManifoldsViewer


@discover_provider
class ExhaustManifoldsProvider(Provider):
    """Provides exhaust manifold geometry and configuration."""

    @property
    def default_config(self) -> ExhaustManifoldsConfig:
        """Return the default exhaust manifolds configuration."""
        if not hasattr(self, "_cached_default_config"):
            self._cached_default_config = ExhaustManifoldsConfig(
                measurements_path=str(Path(__file__).parent / "measurements.yaml")
            )
        return self._cached_default_config

    @cached_property
    def builder(self) -> ExhaustManifoldsBuilder:
        """Return the exhaust manifolds builder."""
        return ExhaustManifoldsBuilder(
            config=self.app_config, exhaust_manifolds_config=self.settings, executor=self.orchestrator.executor
        )

    @cached_property
    def configurator(self) -> ExhaustManifoldsConfigurator:
        """Return the exhaust manifolds configurator."""
        return ExhaustManifoldsConfigurator(
            builder=self.builder,
            config=self.app_config,
            exhaust_manifolds_config=self.settings,
            executor=self.orchestrator.executor,
            logger=self.logger,
        )

    @cached_property
    def viewer(self) -> ExhaustManifoldsViewer:
        """Return the exhaust manifolds viewer."""
        return ExhaustManifoldsViewer(
            builder=self.builder,
            configurator=self.configurator,
            config=self.app_config,
            exhaust_manifolds_config=self.settings,
            executor=self.orchestrator.executor,
        )

    @property
    def part(self) -> dict[str, Callable[..., Any]]:
        """A mapping of part names to their build handler methods."""
        return {name: self.builder.build_part for name in self.targets.supporting(Section.PART)}

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """A mapping of diagram names to their build handler methods."""
        return {name: self.builder.build_diagram for name in self.targets.supporting(Section.DIAGRAM)}

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        return {
            "mount": self.configurator.config_mount,
            "text": self.configurator.config_text,
        }

    @property
    def view(self) -> dict[str, Callable[[Room, Mode], None]]:
        """A mapping of room names to view functions."""
        return {
            "part_positions": self.viewer.view_part_positions,
            "overlay": self.viewer.view_overlay,
            "wire": self.viewer.view_wire,
            "sketch": self.viewer.view_sketch,
        }
