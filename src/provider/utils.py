"""Utility functions for build providers."""

import os
from typing import Any, TypeVar, Callable, overload, Union, cast
import yaml
from .types import Mode, Section, ColorType, MODES, SUBASSEMBLIES, COLOR, MATERIAL, EXPORT

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


def _merge_manifests(dst: dict, src: dict):
    """Recursively merge src dictionary into dst dictionary."""
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            _merge_manifests(dst[k], v)
        else:
            dst[k] = v


def load_manifest(path: str) -> dict[str, dict[Any, Any]]:
    """
    Load and parse a manifest from a YAML file, resolving any imports.

    Example YAML format:
    ```yaml
    imports:
      - print_materials.yaml
    material:
      pla:
        density: 1.24
    part_a:
      wire:
        modes: [default]
        subassemblies: [left]
      part:
        modes: [default, bare]
        subassemblies: [left]
      color: [0.8, 0.8, 0.8, 1.0]
      material: pla
    ```
    """
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    manifest = {}

    # 1. Handle imports recursively
    import_paths = []
    if "import" in data:
        val = data.pop("import")
        if isinstance(val, str):
            import_paths.append(val)
    if "imports" in data:
        val = data.pop("imports")
        if isinstance(val, list):
            import_paths.extend(val)
        elif isinstance(val, str):
            import_paths.append(val)

    base_dir = os.path.dirname(os.path.abspath(path))
    for imp_path in import_paths:
        abs_imp_path = os.path.normpath(os.path.join(base_dir, imp_path))
        if os.path.exists(abs_imp_path):
            imported_manifest = load_manifest(abs_imp_path)
            _merge_manifests(manifest, imported_manifest)

    # 2. Parse current manifest target/section config
    current_manifest = {}
    for target, actions in data.items():
        if target == MATERIAL:
            # Merging material definitions section
            current_manifest[MATERIAL] = actions
            continue

        target_cfg = {}
        if isinstance(actions, dict):
            for key, val in actions.items():
                # Handle Color metadata
                if key == "color":
                    if isinstance(val, dict):
                        target_cfg[COLOR] = {str(k): ColorType(v) for k, v in val.items()}
                    else:
                        target_cfg[COLOR] = ColorType(val)
                    continue

                # Handle Material metadata
                if key == MATERIAL:
                    target_cfg[MATERIAL] = val
                    continue

                # Handle Export metadata
                if key == EXPORT:
                    target_cfg[EXPORT] = val
                    continue

                # Map string keys to Section Enums
                try:
                    section_key = Section(key)
                except ValueError:
                    target_cfg[key] = val
                    continue

                section_cfg = {}
                if isinstance(val, dict):
                    if MODES in val:
                        section_cfg[MODES] = [str(m) if section_key == Section.CONFIG else Mode(m) for m in val[MODES]]
                    if SUBASSEMBLIES in val:
                        section_cfg[SUBASSEMBLIES] = [str(s) for s in val[SUBASSEMBLIES]]
                target_cfg[section_key] = section_cfg
        else:
            target_cfg = actions

        current_manifest[target] = target_cfg

    _merge_manifests(manifest, current_manifest)
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
