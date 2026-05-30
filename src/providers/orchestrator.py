"""Handles the validation and execution strategy for build actions."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from .types import Subassembly, Mode, Action, MODES, SUBASSEMBLIES
from model import method_cache
from pydantic import validate_call
from .target_list import TargetList

if TYPE_CHECKING:
    from .provider import Provider
    from .provider_router import ProviderRouter


_default_executor: Optional[ThreadPoolExecutor] = None


class Orchestrator(ABC):
    """Base class for orchestrators."""

    @abstractmethod
    def __init__(self, context: Any, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator."""
        pass

    @abstractmethod
    def execute(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),  # noqa: B006
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform a build action."""
        pass


class ProviderOrchestrator(Orchestrator):
    """Handles the validation and execution strategy for build actions."""

    def __init__(self, provider: Provider, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator with a provider reference."""
        self.provider = provider
        if executor is not None:
            self.executor = executor
        else:
            global _default_executor
            if _default_executor is None:
                _default_executor = ThreadPoolExecutor()
            self.executor = _default_executor

    @validate_call(config={"arbitrary_types_allowed": True})
    def execute(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform a build action, routing through the cache if appropriate."""
        # Diagram action does not use subassemblies during build execution
        exec_subs = () if action == Action.DIAGRAM else subassemblies

        if action == Action.CONFIG:
            return self._execute_uncached(targets, action, exec_subs, modes)

        return self._execute_cached(targets, action, exec_subs, modes)

    @method_cache()
    def _execute_cached(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform a cached build action."""
        return self._execute_uncached(targets, action, subassemblies, modes)

    def _execute_uncached(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform the actual build action without caching."""
        self.pre_handler(targets, action, subassemblies, modes)
        handler = self.provider.registry.get(action)
        if not handler:
            raise ValueError(f"No handler registered for action '{action}' in {self.provider.__class__.__name__}")

        def handler_task(i: int) -> Any:
            target: str = targets[i]
            sa = (
                subassemblies[i]
                if len(subassemblies) == len(targets)
                else (subassemblies[0] if subassemblies else None)
            )
            return handler(target, [sa] if sa else [], list(modes))

        results = list(self.executor.map(handler_task, range(len(targets))))
        self.post_handler(targets, results, action)

        if action == Action.DIAGRAM:
            return results[0]
        elif action == Action.CONFIG:
            return None
        return list(zip(targets, results))

    def pre_handler(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...],
        modes: tuple[Mode, ...],
    ) -> None:
        """Validate input parameters before the handler execution."""
        if subassemblies and len(subassemblies) != len(targets) and len(subassemblies) != 1:
            raise ValueError(
                f"Length of subassemblies ({len(subassemblies)}) must match "
                f"length of targets ({len(targets)}) or be exactly 1."
            )

        valid_targets = self.provider.targets
        manifest = self.provider.manifest

        for i, name in enumerate(targets):
            if name not in valid_targets:
                raise ValueError(f"Unsupported part name: '{name}'. Supported: {valid_targets}")

            actions_config = manifest.get(name, {})
            if action not in actions_config:
                raise ValueError(
                    f"Action '{action}' is not supported for part '{name}'. Supported: {list(actions_config.keys())}"
                )

            action_config = actions_config[action]
            supported_modes = action_config.get(MODES, [])
            for mode in modes:
                if mode not in supported_modes:
                    raise ValueError(
                        f"Mode '{mode}' is not supported for action '{action}' on part '{name}'. "
                        f"Supported modes: {supported_modes}"
                    )

            if subassemblies:
                sa = subassemblies[i] if len(subassemblies) == len(targets) else subassemblies[0]
                supported_subs = action_config.get(SUBASSEMBLIES, [])
                if sa not in supported_subs:
                    raise ValueError(
                        f"Subassembly '{sa}' is not supported for part '{name}'. "
                        f"Supported subassemblies: {supported_subs}"
                    )

    def post_handler(self, targets: tuple[str, ...], results: list[Any], action: Action) -> None:
        """Validate build results after the handler execution."""
        expected_len = 1 if action == Action.DIAGRAM else len(targets)
        if len(results) != expected_len:
            raise ValueError(f"Orchestration failed: expected {expected_len} items, got {len(results)}.")

        if action == Action.CONFIG:
            if results != [None] * len(targets):
                raise ValueError("Configuration actions should not return geometry or data values.")
        elif any(r is None for r in results):
            raise ValueError(f"Orchestration failed: one or more results for action '{action}' were None.")


class ProviderRouterOrchestrator(Orchestrator):
    """Handles routing and merging for multiple providers."""

    def __init__(self, controller: ProviderRouter, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator with a controller reference."""
        self.controller = controller
        if executor is not None:
            self.executor = executor
        else:
            global _default_executor
            if _default_executor is None:
                _default_executor = ThreadPoolExecutor()
            self.executor = _default_executor

    def collect(self, targets: tuple[str, ...]) -> Dict[Provider, list[int]]:
        """Map target names to providers and group indices by provider."""
        lookup: Dict[str, Provider] = {}
        for p in self.controller.providers:
            for t in p.manifest:
                lookup[t] = p

        groups: Dict[Provider, list[int]] = {}
        for i, target in enumerate(targets):
            provider = lookup.get(target)
            if not provider:
                raise ValueError(f"No provider found for target '{target}'")
            groups.setdefault(provider, []).append(i)
        return groups

    def merge(self, action: Action, targets: tuple[str, ...], results: list[Any]) -> Any:
        """Merge results from multiple providers based on the action."""
        if action == Action.CONFIG:
            return None

        indexed_results = [None] * len(targets)
        diagram_results = []

        for provider, indices, res in results:
            if action == Action.DIAGRAM:
                diagram_results.append((provider.name, res))
            else:
                # res is now list[tuple[str, Any]]
                for local_idx, global_idx in enumerate(indices):
                    # Store only the result object in indexed_results for merging
                    indexed_results[global_idx] = res[local_idx][1]

        if action == Action.DIAGRAM:
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
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Route targets to their respective providers and merge results."""
        groups = self.collect(targets)

        def provider_task(item: tuple[Provider, list[int]]) -> tuple[Provider, list[int], Any]:
            p, indices = item
            p_targets = [targets[i] for i in indices]
            p_subs = [subassemblies[i] for i in indices] if len(subassemblies) == len(targets) else list(subassemblies)
            sub_list = TargetList(p, p_targets, subassemblies=p_subs, modes=list(modes), action=action)
            return p, indices, p.run(sub_list)

        # Execute all provider runs in parallel across the thread pool
        results = list(self.executor.map(provider_task, groups.items()))
        return self.merge(action, targets, results)
