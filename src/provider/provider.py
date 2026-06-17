"""Base definitions for geometry and data providers."""

from __future__ import annotations
import os
import inspect
from typing import Optional, Any, Callable, Iterable, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor
from build123d import Part, Sketch, Wire
from pydantic import validate_call, BaseModel
from model.utils import method_cache
from model.app_config import AppConfig
import re
from .types import Mode, Section, MODES, SUBASSEMBLIES, COLOR, MATERIAL, EXPORT
from .target_list import TargetList
from .orchestrator import Orchestrator
from .utils import load_manifest
from .room import Room

if TYPE_CHECKING:
    from model.app_config import AppConfig
    from shell import Logger


_default_executor: Optional[ThreadPoolExecutor] = None


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
        action: Section,
        subassemblies: tuple[str | None, ...] = (),
        modes: tuple[Mode | str, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform the requested build action."""
        # Diagram action does not use subassemblies during build execution
        handler_subs = () if action == Section.DIAGRAM else subassemblies
        self.pre_handler(targets, action, handler_subs, modes)

        if action == Section.DIAGRAM:
            # Diagrams operate on all targets at once. We pick the handler for the first target.
            handler = self.provider.diagram[targets[0]]
            # Diagrams operate on all targets at once and return content in a Room.
            room = Room(config=self.provider.app_config)
            handler(room, targets, modes[0])
            results = [room]
            self.post_handler(targets, results, action)
            return results[0]

        # Flatten units of work into (target, subassembly, mode) triples
        work_subs = list(subassemblies) if subassemblies else [None]
        work = [(t, sa, m) for t in targets for sa in work_subs for m in modes]

        if action == Section.VIEW:

            def view_task(item: tuple[str, Optional[str], Mode]) -> Room:
                target, _, m = item
                room = Room(config=self.provider.app_config)
                room.mode = m
                self.provider.view[target](room)
                return room

            raw_results = list(self.executor.map(view_task, work))
        elif action == Section.CONFIG:

            def config_task(item: tuple[str, Optional[str], Mode]) -> None:
                target, sa, m = item
                self.provider.config[m](target, sa)

            list(self.executor.map(config_task, work))
            self.post_handler(targets, None, action)
            return None
        elif action == Section.PART:

            def build_task(item: tuple[str, Optional[str], Mode]) -> Any:
                target, sa, m = item
                handler = self.provider.part[target]
                return handler(target, sa, m)

            raw_results = list(self.executor.map(build_task, work))
        else:
            raise ValueError(f"Unsupported action: {action}")

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
        action: Section,
        subassemblies: tuple[str | None, ...],
        modes: tuple[Mode | str, ...],
    ) -> None:
        """Validate input parameters before the handler execution."""
        # Ensure the action is recognized by the orchestrator
        if action not in [Section.VIEW, Section.CONFIG, Section.PART, Section.DIAGRAM]:
            raise ValueError(f"No handler registered for action '{action}' in {self.provider.__class__.__name__}")

        # Diagrams operate on all targets at once, so we validate the first target has a handler.
        if action == Section.DIAGRAM:
            if targets[0] not in self.provider.diagram:
                raise ValueError(f"No diagram handler registered for '{targets[0]}' in {self.provider.name}")

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

            if action == Section.VIEW and name not in self.provider.view:
                raise ValueError(f"No view function registered for room '{name}' in {self.provider.name}")

            if action == Section.PART and name not in self.provider.part:
                raise ValueError(f"No part handler registered for '{name}' in {self.provider.name}")

            if action == Section.CONFIG:
                for mode in modes:
                    if mode not in self.provider.config:
                        raise ValueError(f"No config handler registered for mode '{mode}' in {self.provider.name}")

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

    def post_handler(self, targets: tuple[str, ...], results: Optional[list[Any]], action: Section) -> None:
        """Validate build results after the handler execution."""
        if action == Section.CONFIG:
            return

        expected_len = 1 if action == Section.DIAGRAM else len(targets)
        if results is None or len(results) != expected_len:
            raise ValueError(
                f"Orchestration failed: expected {expected_len} items, got {len(results) if results else 0}."
            )

        if any(r is None for r in results):
            raise ValueError(f"Orchestration failed: one or more results for action '{action}' were None.")


class Provider:
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
            config = AppConfig()
        self.app_config = config
        self.logger = logger
        self.orchestrator = self.orchestrator_type(self, executor=executor)

    @property
    def name(self) -> str:
        """Infers the provider name from the class name (snake_case, minus 'Provider')."""
        cls_name = self.__class__.__name__
        if cls_name.endswith("Provider"):
            cls_name = cls_name.removesuffix("Provider")
        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls_name).lower()

    @property
    def default_config(self) -> BaseModel:
        """Return a default instance of the provider's configuration (an empty BaseModel)."""
        return BaseModel()

    @property
    def settings(self) -> Any:
        """Return the provider-specific configuration sub-model from the global config."""
        return getattr(self.app_config, self.name.lower(), self.default_config)

    @property
    def manifest(self) -> dict[str, dict[str, Any]]:
        """A mapping of part names to their supported capabilities and colors.

        By default, attempts to load "manifest.yaml" relative to the provider module.
        """
        base_dir = os.path.dirname(os.path.abspath(inspect.getfile(self.__class__)))
        manifest_path = os.path.join(base_dir, "manifest.yaml")
        if os.path.exists(manifest_path):
            return load_manifest(manifest_path)
        return {}

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
    def view(self) -> dict[str, Callable[[Room], None]]:
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

        if color is None:
            return self.app_config.color

        if isinstance(color, (tuple, list)):
            return tuple(color)  # type: ignore

        from .utils import get_rgba_color

        return get_rgba_color(color, 1.0, self.app_config.color[:3])

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_material(self, target: str, subassembly: Optional[str] = None) -> Optional[str]:
        """Resolve the material for a specific target and subassembly."""
        target_cfg = self.manifest.get(target, {})
        material = target_cfg.get(MATERIAL)

        if isinstance(material, dict):
            # If MATERIAL is a dict, resolve by subassembly key.
            if subassembly:
                material = material.get(subassembly)
            else:
                material = next(iter(material.values())) if material else None

        if material is None:
            return None

        return str(material)

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_export_types(self, target: str, subassembly: Optional[str] = None) -> list[str]:
        """Resolve the export formats for a specific target and subassembly."""
        target_cfg = self.manifest.get(target, {})
        export_val = target_cfg.get(EXPORT)

        if isinstance(export_val, dict):
            # If EXPORT is a dict, resolve by subassembly key.
            if subassembly:
                export_val = export_val.get(subassembly)
            else:
                export_val = next(iter(export_val.values())) if export_val else None

        if export_val is None:
            return ["stl"]

        if isinstance(export_val, list):
            return [str(e).lower() for e in export_val]
        return [str(export_val).lower()]

    @validate_call(config={"arbitrary_types_allowed": True})
    def run(self, targets: TargetList) -> Any:
        """Perform the requested provider-specific build action based on TargetList."""
        action = targets.action
        if action is None:
            raise ValueError(f"No action specified for {targets}. You must call .supporting(action) before running.")

        if action == Section.DIAGRAM and targets.subassemblies:
            raise ValueError(
                f"Subassemblies cannot be specified for Section.DIAGRAM in '{self.name}'. "
                "Diagrams are global assembly views."
            )

        return self.orchestrator.execute(tuple(targets), action, tuple(targets.subassemblies), tuple(targets.modes))
