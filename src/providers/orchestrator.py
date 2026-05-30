"""Handles the validation and execution strategy for build actions."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, Optional
from concurrent.futures import ThreadPoolExecutor
from .types import Subassembly, Mode, Action, MODES, SUBASSEMBLIES
from model import method_cache
from pydantic import validate_call

if TYPE_CHECKING:
    from .provider import Provider


class Orchestrator(ABC):
    """Base class for orchestrators."""

    @abstractmethod
    def __init__(self, provider: Provider, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator with a provider reference."""
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

    _default_executor: Optional[ThreadPoolExecutor] = None

    def __init__(self, provider: Provider, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator with a provider reference."""
        self.provider = provider
        if executor is not None:
            self.executor = executor
        else:
            if ProviderOrchestrator._default_executor is None:
                ProviderOrchestrator._default_executor = ThreadPoolExecutor()
            self.executor = ProviderOrchestrator._default_executor

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
        return results

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

        if action == Action.CONFIG and results != [None] * len(targets):
            raise ValueError("Configuration actions should not return geometry or data values.")
