"""Handles the validation and execution strategy for build actions."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from .types import Subassembly, Mode, Action, MODES, SUBASSEMBLIES
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
        """Perform the requested build action."""
        # Diagram action does not use subassemblies during build execution
        handler_subs = () if action == Action.DIAGRAM else subassemblies
        self.pre_handler(targets, action, handler_subs, modes)

        if action == Action.DIAGRAM:
            handler = self.provider.build[Action.DIAGRAM]
            # Diagrams operate on all targets at once and ignore subassemblies.
            result = handler(list(targets), modes[0])
            results = [result]
            self.post_handler(targets, results, action)
            return results[0]

        # Flatten units of work into (target, subassembly, mode) triples
        work_subs = list(subassemblies) if subassemblies else [None]
        work = [(t, sa, m) for t in targets for sa in work_subs for m in modes]

        if action == Action.VIEW:

            def view_task(item: tuple[str, Optional[Subassembly], Mode]) -> Any:
                target, _, _ = item
                return self.provider.view[target]()

            raw_results = list(self.executor.map(view_task, work))
        elif action == Action.CONFIG:

            def config_task(item: tuple[str, Optional[Subassembly], Mode]) -> None:
                target, sa, m = item
                self.provider.config[m](target, sa)

            list(self.executor.map(config_task, work))
            self.post_handler(targets, None, action)
            return None
        else:
            handler = self.provider.build[action]

            def build_task(item: tuple[str, Optional[Subassembly], Mode]) -> Any:
                target, sa, m = item
                return handler(target, sa, m)

            raw_results = list(self.executor.map(build_task, work))

        # Group results back by target for VIEW and BUILD
        results = []
        group_size = len(work_subs) * len(modes)
        for i in range(len(targets)):
            group = raw_results[i * group_size : (i + 1) * group_size]
            results.append(group[0] if group_size == 1 else group)

        self.post_handler(targets, results, action)
        return list(zip(targets, results))

    def pre_handler(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...],
        modes: tuple[Mode, ...],
    ) -> None:
        """Validate input parameters before the handler execution."""
        if action != Action.VIEW and action != Action.CONFIG and action not in self.provider.build:
            raise ValueError(f"No handler registered for action '{action}' in {self.provider.__class__.__name__}")

        valid_targets = self.provider.targets
        manifest = self.provider.manifest

        for i, name in enumerate(targets):
            if name not in valid_targets:
                raise ValueError(f"Unsupported part name: '{name}'. Supported: {valid_targets}")

            if action == Action.VIEW and name not in self.provider.view:
                raise ValueError(f"No view function registered for room '{name}' in {self.provider.name}")

            if action == Action.CONFIG:
                for mode in modes:
                    if mode not in self.provider.config:
                        raise ValueError(f"No config handler registered for mode '{mode}' in {self.provider.name}")

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
                supported_subs = action_config.get(SUBASSEMBLIES, [])
                for sa in subassemblies:
                    if sa not in supported_subs:
                        raise ValueError(
                            f"Subassembly '{sa}' is not supported for part '{name}'. "
                            f"Supported subassemblies: {supported_subs}"
                        )

    def post_handler(self, targets: tuple[str, ...], results: Optional[list[Any]], action: Action) -> None:
        """Validate build results after the handler execution."""
        if action == Action.CONFIG:
            return

        expected_len = 1 if action == Action.DIAGRAM else len(targets)
        if results is None or len(results) != expected_len:
            raise ValueError(
                f"Orchestration failed: expected {expected_len} items, got {len(results) if results else 0}."
            )

        if any(r is None for r in results):
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
            # Extract the leaf target name (e.g., 'p/t' -> 't')
            p_targets = [targets[i].split("/", 1)[1] for i in indices]
            p_subs = [subassemblies[i] for i in indices] if len(subassemblies) == len(targets) else list(subassemblies)
            sub_list = TargetList(p, p_targets, subassemblies=p_subs, modes=list(modes), action=action)
            return p, indices, p.run(sub_list)

        # Execute all provider runs in parallel across the thread pool
        results = list(self.executor.map(provider_task, groups.items()))
        return self.merge(action, targets, results)
