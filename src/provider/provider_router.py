"""Routes build targets to multiple providers."""

from __future__ import annotations
from typing import Any, Optional, Dict
from .provider import Provider
from .target_list import TargetList
from .types import Section, Mode
from .orchestrator import Orchestrator
from concurrent.futures import ThreadPoolExecutor
from pydantic import validate_call


_router_default_executor: Optional[ThreadPoolExecutor] = None


class ProviderRouterOrchestrator(Orchestrator):
    """Handles routing and merging for multiple providers."""

    def __init__(self, controller: ProviderRouter, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator with a controller reference."""
        self.controller = controller
        if executor is not None:
            self.executor = executor
        else:
            global _router_default_executor
            if _router_default_executor is None:
                _router_default_executor = ThreadPoolExecutor()
            self.executor = _router_default_executor

    def collect(self, targets: tuple[str, ...]) -> Dict[Provider, list[int]]:
        """Map target names to providers and group indices by provider."""
        p_map = {p.name: p for p in self.controller.providers}

        groups: Dict[Provider, list[int]] = {}
        for i, target in enumerate(targets):
            if "/" not in target:
                raise ValueError(f"Target '{target}' must use 'provider/target' syntax.")
            p_name, _ = target.split("/", 1)
            provider = p_map.get(p_name)
            if not provider:
                raise ValueError(f"No provider found for target '{target}'")
            groups.setdefault(provider, []).append(i)
        return groups

    def merge(self, action: Section, targets: tuple[str, ...], results: list[Any]) -> Any:
        """Merge results from multiple providers based on the action."""
        if action == Section.CONFIG:
            return None

        indexed_results = [None] * len(targets)
        diagram_results = []

        for provider, indices, res in results:
            if action == Section.DIAGRAM:
                diagram_results.append((provider.name, res))
            else:
                for local_idx, global_idx in enumerate(indices):
                    # Store only the result object in indexed_results for merging
                    indexed_results[global_idx] = res[local_idx][1]

        if action == Section.DIAGRAM:
            if any(r is None for _, r in diagram_results):
                raise ValueError("Orchestration failed: one or more diagram results were None.")
            return diagram_results

        if any(r is None for r in indexed_results):
            missing = [targets[i] for i, r in enumerate(indexed_results) if r is None]
            raise ValueError(
                f"Orchestration failed in ProviderRouter: results for targets {missing} were not collected."
            )

        return list(zip(targets, indexed_results))

    @validate_call(config={"arbitrary_types_allowed": True})
    def execute(
        self,
        targets: tuple[str, ...],
        action: Section,
        subassemblies: tuple[str | None, ...] = (),
        modes: tuple[Mode | str, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Route targets to their respective providers and merge results."""
        groups = self.collect(targets)

        def provider_task(item: tuple[Provider, list[int]]) -> tuple[Provider, list[int], Any]:
            p, indices = item
            # Extract the leaf target name (e.g., 'p/t' -> 't')
            p_targets = [targets[i].split("/", 1)[1] for i in indices]
            p_subs = [subassemblies[i] for i in indices] if len(subassemblies) == len(targets) else list(subassemblies)
            sub_list = TargetList(p, p_targets, subassemblies=p_subs, modes=list(modes), action=action)
            return p, indices, p.run(sub_list)

        # Execute all provider runs in parallel across the thread pool
        results = list(self.executor.map(provider_task, groups.items()))
        return self.merge(action, targets, results)


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

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_material(self, target: str, subassembly: Optional[str] = None) -> Optional[str]:
        """Resolve the material for a specific target and subassembly."""
        if "/" in target:
            p_name, t_name = target.split("/", 1)
            for provider in self.providers:
                if provider.name == p_name:
                    return provider.get_material(t_name, subassembly)
        raise ValueError(f"Target '{target}' not found in any registered provider.")

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_export_types(self, target: str, subassembly: Optional[str] = None) -> list[str]:
        """Resolve the export formats for a specific target and subassembly."""
        if "/" in target:
            p_name, t_name = target.split("/", 1)
            for provider in self.providers:
                if provider.name == p_name:
                    return provider.get_export_types(t_name, subassembly)
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
