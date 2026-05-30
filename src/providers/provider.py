"""Base definitions for geometry and data providers."""

from abc import ABC, abstractmethod
from typing import Optional, Any, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from build123d import Part, Sketch, Wire
import cadquery as cq
from pydantic import validate_call, BaseModel
from model import method_cache
from .types import Subassembly, Mode, Action
from .target_list import TargetList


class Provider(ABC):
    """Base class for all build providers."""

    _default_executor: Optional[ThreadPoolExecutor] = None

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the provider."""
        if executor is not None:
            self.executor = executor
        else:
            if Provider._default_executor is None:
                Provider._default_executor = ThreadPoolExecutor()
            self.executor = Provider._default_executor

    @property
    @abstractmethod
    def default_config(self) -> BaseModel:
        """Return a default instance of the provider's configuration."""
        pass

    @property
    @abstractmethod
    def manifest(self) -> dict[str, dict[str, Any]]:
        """A mapping of part names to their supported capabilities (actions, modes, subassemblies)."""
        pass

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
    def build_wires(
        self,
        targets: TargetList,
    ) -> list[Wire]:
        """Build wires for the specified names."""
        return self._run(tuple(targets), Action.WIRE, tuple(targets.subassemblies), tuple(targets.modes))

    @validate_call(config={"arbitrary_types_allowed": True})
    def build_sketches(
        self,
        targets: TargetList,
    ) -> list[Sketch]:
        """Build sketches for the specified names."""
        return self._run(tuple(targets), Action.SKETCH, tuple(targets.subassemblies), tuple(targets.modes))

    @validate_call(config={"arbitrary_types_allowed": True})
    def build_parts(
        self,
        targets: TargetList,
    ) -> list[Part]:
        """Build parts for the specified names."""
        return self._run(tuple(targets), Action.PART, tuple(targets.subassemblies), tuple(targets.modes))

    @validate_call(config={"arbitrary_types_allowed": True})
    def configure_parts(
        self,
        targets: TargetList,
    ) -> list[Any]:
        """Run configuration for the specified names."""
        return self._run(tuple(targets), Action.CONFIG, tuple(targets.subassemblies), tuple(targets.modes))

    @validate_call(config={"arbitrary_types_allowed": True})
    def build_diagram(
        self,
        targets: TargetList,
    ) -> cq.Assembly:
        """Build an assembly diagram for the specified names."""
        results = self._run(tuple(targets), Action.DIAGRAM, (), tuple(targets.modes))
        return results[0]

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def _run(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...] = (),
        modes: tuple[Mode, ...] = (Mode.DEFAULT,),
    ) -> list[Any]:
        """Perform a requested provider-specific build action."""
        self._pre_handler(targets, action, subassemblies, modes)
        handler = self.registry.get(action)
        if not handler:
            raise ValueError(f"No handler registered for action '{action}' in {self.__class__.__name__}")

        def handler_task(i: int) -> Any:
            target = targets[i]
            sa = (
                subassemblies[i]
                if len(subassemblies) == len(targets)
                else (subassemblies[0] if subassemblies else None)
            )
            return handler(target, [sa] if sa else [], list(modes))

        results = list(self.executor.map(handler_task, range(len(targets))))
        self._post_handler(targets, results, action)
        return results

    def _pre_handler(
        self,
        targets: tuple[str, ...],
        action: Action,
        subassemblies: tuple[Subassembly, ...],
        modes: tuple[Mode, ...],
    ) -> None:
        """Validate input parameters before the handler execution."""
        # Validate that subassemblies list length matches names or is exactly 1
        if subassemblies and len(subassemblies) != len(targets) and len(subassemblies) != 1:
            raise ValueError(
                f"Length of subassemblies ({len(subassemblies)}) must match "
                f"length of targets ({len(targets)}) or be exactly 1."
            )

        # Cache references to avoid repeated property lookups in the loop
        valid_targets = self.targets
        manifest = self.manifest

        # Validate name, action, format, and subassembly for each name
        for i, name in enumerate(targets):
            if name not in valid_targets:
                raise ValueError(f"Unsupported part name: '{name}'. Supported: {valid_targets}")

            target_manifest = manifest.get(name, {})

            if action not in target_manifest.get("actions", []):
                raise ValueError(
                    f"Action '{action}' is not supported for part '{name}'. "
                    f"Supported actions: {target_manifest.get('actions', [])}"
                )

            for mode in modes:
                if mode not in target_manifest.get("modes", []):
                    raise ValueError(
                        f"Mode '{mode}' is not supported for part '{name}'. "
                        f"Supported modes: {target_manifest.get('modes', [])}"
                    )

            if subassemblies:
                # Determine which subassembly to check for this name
                sa = subassemblies[i] if len(subassemblies) == len(targets) else subassemblies[0]
                if sa not in target_manifest.get("subassemblies", []):
                    raise ValueError(
                        f"Subassembly '{sa}' is not supported for part '{name}'. "
                        f"Supported subassemblies: {target_manifest.get('subassemblies', [])}"
                    )

    def _post_handler(self, targets: tuple[str, ...], results: list[Any], action: Action) -> None:
        """Validate build results after the handler execution."""
        expected_len = 1 if action == Action.DIAGRAM else len(targets)
        if len(results) != expected_len:
            raise ValueError(
                f"Provider build failed validation for {action}: returned {len(results)} items, "
                f"but {expected_len} were expected."
            )
