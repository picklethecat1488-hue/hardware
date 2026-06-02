"""Routes build targets to multiple providers."""

from typing import Any, Optional
from .provider import Provider
from .target_list import TargetList
from .types import Action, Mode
from .orchestrator import Orchestrator, ProviderRouterOrchestrator
from concurrent.futures import ThreadPoolExecutor
from pydantic import validate_call


class ProviderRouter:
    """Aggregates multiple providers into a single build interface."""

    orchestrator_type: type[Orchestrator] = ProviderRouterOrchestrator

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None, providers: Optional[list[Provider]] = None):
        """Initialize the router."""
        self._provider_list: list[Provider] = providers or []
        self.orchestrator = self.orchestrator_type(self, executor=executor)

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
            for target_name, config in provider.manifest.items():
                combined[f"{provider.name}/{target_name}"] = config
        return combined

    @property
    def default_configs(self) -> dict[str, Any]:
        """Return the default configurations for all registered providers."""
        return {p.name: p.default_config for p in self.providers}

    @property
    def targets(self) -> TargetList:
        """Return a TargetList encompassing all registered providers."""
        return TargetList(self, self.manifest.keys())

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_color(self, target: str, subassembly: Optional[str] = None) -> tuple[float, float, float, float]:
        """Resolve the color for a specific target and subassembly."""
        if "/" in target:
            p_name, t_name = target.split("/", 1)
            for provider in self.providers:
                if provider.name == p_name:
                    return provider.get_color(t_name, subassembly)
        raise ValueError(f"Target '{target}' not found in any registered provider.")

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
