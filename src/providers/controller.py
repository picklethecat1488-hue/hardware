"""Routes build targets to multiple providers."""

from typing import Any, Optional, Union
from .provider import Provider
from .target_list import TargetList
from .types import Action, Mode, Subassembly
from .orchestrator import ControllerOrchestrator


class Controller:
    """Aggregates multiple providers into a single build interface."""

    orchestrator_type: type[ControllerOrchestrator] = ControllerOrchestrator

    def __init__(self, providers: Optional[list[Provider]] = None):
        """Initialize the controller."""
        self._provider_list: list[Provider] = providers or []
        self.orchestrator = self.orchestrator_type(self)

    @property
    def providers(self) -> list[Provider]:
        """Return the list of registered providers."""
        return self._provider_list

    @property
    def provider_names(self) -> list[str]:
        """Return the names of all registered providers."""
        return [p.name for p in self.providers]

    @property
    def manifest(self) -> dict[str, dict[str, Any]]:
        """Aggregate manifest from all registered providers."""
        combined = {}
        for provider in self.providers:
            p_manifest = provider.manifest
            overlap = set(combined.keys()) & set(p_manifest.keys())
            if overlap:
                raise ValueError(
                    f"Name collision detected in Controller: targets {overlap} are defined in multiple "
                    f"providers. Provider '{provider.name}' conflicts with previously registered providers."
                )
            combined.update(p_manifest)
        return combined

    @property
    def targets(self) -> TargetList:
        """Return a TargetList encompassing all registered providers."""
        return TargetList(self, self.manifest.keys())

    def run(self, targets: TargetList) -> Any:
        """Route targets to their respective providers and merge results."""
        action = targets.action
        if action is None:
            raise ValueError(f"No action specified for {targets}.")

        return self.orchestrator.execute(
            tuple(targets),
            action,
            tuple(targets.subassemblies),
            tuple(targets.modes),
        )