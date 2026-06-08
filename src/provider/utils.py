"""Utility functions for build providers."""

from typing import Any, TypeVar, Callable, overload, Union, cast
import yaml
from .types import Mode, Action, ColorType, MODES, SUBASSEMBLIES, COLOR

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
                    target_cfg[COLOR] = {str(k): ColorType(v) for k, v in val.items()}
                else:
                    target_cfg[COLOR] = ColorType(val)
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
                    action_cfg[MODES] = [str(m) if action_key == Action.CONFIG else Mode(m) for m in val[MODES]]
                if SUBASSEMBLIES in val:
                    action_cfg[SUBASSEMBLIES] = [str(s) for s in val[SUBASSEMBLIES]]
            target_cfg[action_key] = action_cfg

        manifest[target] = target_cfg
    return manifest


def get_rgba_color(
    color: Union[str, ColorType, tuple[float, float, float]],
    alpha: float,
    default_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[float, float, float, float]:
    """Convert a color name (or ColorType enum) to an RGBA tuple."""
    if isinstance(color, (tuple, list)):
        return (*color, alpha)  # type: ignore

    color_map = {
        ColorType.RED: (1.0, 0.0, 0.0),
        ColorType.GREEN: (0.0, 1.0, 0.0),
        ColorType.BLUE: (0.0, 0.0, 1.0),
        ColorType.ORANGE: (1.0, 0.65, 0.0),
        ColorType.CYAN: (0.0, 1.0, 1.0),
        ColorType.YELLOW: (1.0, 1.0, 0.0),
        ColorType.MAGENTA: (1.0, 0.0, 1.0),
        ColorType.GREY: (0.5, 0.5, 0.5),
    }
    name = str(color)
    rgb = color_map.get(cast(ColorType, name), default_rgb)
    return (*rgb, alpha)
