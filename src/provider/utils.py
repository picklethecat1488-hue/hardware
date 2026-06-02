"""Utility functions for build providers."""

from typing import Any, TypeVar, Callable, overload
import yaml
from .types import Mode, Action, MODES, SUBASSEMBLIES, COLOR

T = TypeVar("T", bound=type)


@overload
def discover_provider(cls: T) -> T: ...


@overload
def discover_provider(*, enabled: bool = True) -> Callable[[T], T]: ...


def discover_provider(cls: T | None = None, *, enabled: bool = True) -> Any:
    """Mark a Provider subclass for automatic discovery by ProviderManager."""

    def decorator(target: T) -> T:
        setattr(target, "_discover_provider", enabled)
        return target

    if cls is None:
        return decorator
    return decorator(cls)


def load_manifest(path: str) -> dict[str, dict[Any, Any]]:
    """
    Load and parse a manifest from a YAML file.

    Example YAML format:
    ```yaml
    part_a:
      wire:
        modes: [default]
        subassemblies: [left]
      part:
        modes: [default, bare]
        subassemblies: [left]
      color: [0.8, 0.8, 0.8, 1.0]
    part_b:
      part:
        modes: [default]
        subassemblies: [right]
      color:
        right: [0.9, 0.9, 0.9, 1.0]
    ```
    """
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    manifest = {}
    for target, actions in data.items():
        target_cfg = {}
        for key, val in actions.items():
            # Handle Color metadata
            if key == "color":
                if isinstance(val, dict):
                    target_cfg[COLOR] = {str(k): tuple(v) for k, v in val.items()}
                else:
                    target_cfg[COLOR] = tuple(val)
                continue

            # Map string keys to Action Enums
            try:
                action_key = Action(key)
            except ValueError:
                target_cfg[key] = val
                continue

            action_cfg = {}
            if isinstance(val, dict):
                if MODES in val:
                    action_cfg[MODES] = [Mode(m) for m in val[MODES]]
                if SUBASSEMBLIES in val:
                    action_cfg[SUBASSEMBLIES] = [str(s) for s in val[SUBASSEMBLIES]]
            target_cfg[action_key] = action_cfg

        manifest[target] = target_cfg
    return manifest
