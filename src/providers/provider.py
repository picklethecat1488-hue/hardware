"""Base definitions for geometry and data providers."""

from abc import ABC, abstractmethod
from typing import Optional, Any, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from build123d import Part, Sketch, Wire
import cadquery as cq
from pydantic import validate_call, BaseModel
from model import AppConfig, method_cache
from .types import Subassembly, Mode, Action, MODES, SUBASSEMBLIES, COLOR
from .target_list import TargetList
from .orchestrator import Orchestrator, ProviderOrchestrator
from .utils import load_manifest


class Provider(ABC):
    """Base class for all build providers."""

    orchestrator_type: type[Orchestrator] = ProviderOrchestrator

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None, config: Optional[AppConfig] = None):
        """Initialize the provider."""
        self.config = config or AppConfig()
        self.orchestrator = self.orchestrator_type(self, executor=executor)

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the provider."""
        pass

    @property
    @abstractmethod
    def default_config(self) -> BaseModel:
        """Return a default instance of the provider's configuration."""
        pass

    @property
    def manifest(self) -> dict[str, dict[str, Any]]:
        """A mapping of part names to their supported capabilities and colors.

        By default, attempts to load f"{self.name}_manifest.yaml".
        """
        return load_manifest(f"{self.name}_manifest.yaml")

    @property
    @abstractmethod
    def registry(self) -> dict[Action, Callable[[str, list[Subassembly], list[Mode]], Any]]:
        """A mapping of Actions to their handler methods."""
        pass

    @property
    def targets(self) -> TargetList:
        """List of supported build targets derived from the manifest keys."""
        return TargetList(self, self.manifest.keys())

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_color(self, target: str, subassembly: Optional[Subassembly] = None) -> tuple[float, float, float, float]:
        """Resolve the color for a specific target and subassembly."""
        target_cfg = self.manifest.get(target, {})
        color = target_cfg.get(COLOR)

        if isinstance(color, dict):
            # If COLOR is a dict, resolve by subassembly key.
            if subassembly:
                color = color.get(subassembly)
            else:
                color = next(iter(color.values())) if color else None
        return color or self.config.color

    @validate_call(config={"arbitrary_types_allowed": True})
    def run(self, targets: TargetList) -> Any:
        """Perform the requested provider-specific build action based on TargetList."""
        action = targets.action
        if action is None:
            raise ValueError(f"No action specified for {targets}. You must call .supporting(action) before running.")
        return self.orchestrator.execute(tuple(targets), action, tuple(targets.subassemblies), tuple(targets.modes))
