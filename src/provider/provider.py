"""Base definitions for geometry and data providers."""

import os
import inspect
from abc import ABC, abstractmethod
from typing import Optional, Any, Callable, Iterable, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor
from build123d import Part, Sketch, Wire
import cadquery as cq
from pydantic import validate_call, BaseModel
from model.utils import method_cache
from .types import Mode, Action, MODES, SUBASSEMBLIES, COLOR
from .target_list import TargetList
from .orchestrator import Orchestrator, ProviderOrchestrator
from .utils import load_manifest

if TYPE_CHECKING:
    from model.app_config import AppConfig
    from shell import Logger


class Provider(ABC):
    """Base class for all build providers."""

    orchestrator_type: type[Orchestrator] = ProviderOrchestrator

    def __init__(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
        config: Optional["AppConfig"] = None,
        logger: Optional["Logger"] = None,
    ):
        """Initialize the provider."""
        if config is None:
            from model.app_config import AppConfig

            config = AppConfig()
        self.app_config = config
        self.logger = logger
        self.orchestrator = self.orchestrator_type(self, executor=executor)

    @property
    def name(self) -> str:
        """Return the name of the provider, defaulting to the class name in lowercase."""
        return self.__class__.__name__.lower().removesuffix("provider")

    @property
    @abstractmethod
    def default_config(self) -> BaseModel:
        """Return a default instance of the provider's configuration."""
        pass

    @property
    def settings(self) -> Any:
        """Return the provider-specific configuration sub-model from the global config."""
        return getattr(self.app_config, self.name.lower(), self.default_config)

    @property
    def manifest(self) -> dict[str, dict[str, Any]]:
        """A mapping of part names to their supported capabilities and colors.

        By default, attempts to load "manifest.yaml" relative to the provider module.
        """
        try:
            # Resolve path relative to the module defining the concrete provider class
            base_dir = os.path.dirname(os.path.abspath(inspect.getfile(self.__class__)))
            manifest_path = os.path.join(base_dir, "manifest.yaml")
            if os.path.exists(manifest_path):
                return load_manifest(manifest_path)
        except (TypeError, ValueError, OSError):
            pass

        return load_manifest("manifest.yaml")

    @property
    def part(self) -> dict[str, Callable[..., Any]]:
        """A mapping of part names to their build handler methods."""
        return {}

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """A mapping of diagram names to their build handler methods."""
        return {}

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """A mapping of Modes to configuration handler methods."""
        return {}

    @property
    def view(self) -> dict[str, Callable[[], list[tuple[Any, tuple[float, float, float, float]]]]]:
        """A mapping of room names to view functions."""
        return {}

    @property
    def targets(self) -> TargetList:
        """List of supported build targets derived from the manifest keys."""
        return TargetList(self, self.manifest.keys())

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_color(self, target: str, subassembly: Optional[str] = None) -> tuple[float, float, float, float]:
        """Resolve the color for a specific target and subassembly."""
        target_cfg = self.manifest.get(target, {})
        color = target_cfg.get(COLOR)

        if isinstance(color, dict):
            # If COLOR is a dict, resolve by subassembly key.
            if subassembly:
                color = color.get(subassembly)
            else:
                color = next(iter(color.values())) if color else None
        return color or self.app_config.color

    @validate_call(config={"arbitrary_types_allowed": True})
    def run(self, targets: TargetList) -> Any:
        """Perform the requested provider-specific build action based on TargetList."""
        action = targets.action
        if action is None:
            raise ValueError(f"No action specified for {targets}. You must call .supporting(action) before running.")

        if action == Action.DIAGRAM and targets.subassemblies:
            raise ValueError(
                f"Subassemblies cannot be specified for Action.DIAGRAM in '{self.name}'. "
                "Diagrams are global assembly views."
            )

        return self.orchestrator.execute(tuple(targets), action, tuple(targets.subassemblies), tuple(targets.modes))
