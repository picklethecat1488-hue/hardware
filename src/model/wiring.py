"""Data models and container class for component wiring, footprints, and net connections."""

import math
import yaml
from enum import StrEnum
from pathlib import Path
from typing import Tuple, List, Optional, Callable, Any
from functools import cached_property
from pydantic import BaseModel, Field, validate_call
from build123d import Vector, Location

# Footprint Layout Registry
PIN_LAYOUT_REGISTRY = {}


@validate_call
def register_layout(package_name: str, namespace: Optional[str] = None, surface_mount: bool = False):
    """Register a footprint pin layout function as a decorator.

    Raises ValueError if a layout for the key is already registered.
    """

    def decorator(func):
        inferred_namespace = namespace
        if not inferred_namespace:
            module_parts = func.__module__.split(".")
            if len(module_parts) > 1 and module_parts[0] == "projects":
                inferred_namespace = module_parts[1]

        key = f"{inferred_namespace}:{package_name}" if inferred_namespace else package_name
        if key in PIN_LAYOUT_REGISTRY:
            raise ValueError(f"Layout for '{key}' is already registered by '{PIN_LAYOUT_REGISTRY[key].__name__}'")
        func.surface_mount = surface_mount
        PIN_LAYOUT_REGISTRY[key] = func
        return func

    return decorator


class PinSide(StrEnum):
    """Placement side for a pin label."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class PinModel(BaseModel):
    """Data model representing a connection pin on a footprint."""

    name: str = Field(description="Name of the pin (e.g. GND, GP2)")
    position: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D offset relative to component center (x, y, z)"
    )
    label: str = Field(description="Display label text for the pin")
    side: PinSide = Field(description="Placement side for the pin label (left, right, top, bottom)")
    slot: Optional[int] = Field(default=None, description="Optional slot index for DIP spacing")


class LabelModel(BaseModel):
    """Data model representing textual label arguments and alignment."""

    text: str = Field(description="The display text for the label")
    position: Tuple[float, float, float] = Field(description="3D position offset relative to component center")
    align: Tuple[str, str] = Field(description="Horizontal and vertical text alignment (e.g. ['center', 'max'])")


class FootprintModel(BaseModel):
    """Data model representing a physical/electrical footprint package."""

    name: str = Field(description="Unique identifier for the component (e.g. charger, pico)")
    package: str = Field(description="Component shape/package type (e.g. board, ic, motor, led, tof_sensor)")
    namespace: Optional[str] = Field(default=None, description="Optional namespace prefix for the package")
    position: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D absolute center position (x, y, z)"
    )
    rotation: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D absolute rotation (pitch, roll, yaw)"
    )
    dimensions: Tuple[float, float, float] = Field(
        description="Component physical package dimensions (width, length, thickness)"
    )
    mounting_holes: Optional[Tuple[float, float]] = Field(
        default=None, description="Optional x/y spacing for mounting holes"
    )
    slots_per_side: Optional[int] = Field(default=None, description="Optional total number of DIP slots per side")
    label: LabelModel = Field(description="Label settings for the footprint")
    pins: List[PinModel] = Field(default_factory=list, description="List of pins on the footprint")


class NetModel(BaseModel):
    """Data model representing a wiring connection network."""

    name: str = Field(description="Name of the signal net (e.g. gnd, vcc_logic)")
    color: str = Field(description="Display color for the net wire path (e.g. black, red)")
    pins: List[Tuple[str, str]] = Field(description="List of connected pins as (component_name, pin_name) pairs")
    offset: Tuple[float, float] = Field(default=(0.0, 0.0), description="2D offset for drawing parallel wire paths")
    path: List[Tuple[float, float, float]] = Field(
        default_factory=list, description="Explicit 3D intermediate routing points for the net wire path"
    )


class Wiring:
    """Class encapsulating wiring layout, component footprints, and net connections."""

    @validate_call
    def __init__(self, yaml_path: Path, parent_part: Optional[Any] = None):
        """Initialize the Wiring configuration container and load components/nets."""
        self.yaml_path = yaml_path
        self.parent_part = parent_part
        with open(yaml_path, "r") as f:
            self.config = yaml.safe_load(f)

    @cached_property
    def footprints(self) -> List[FootprintModel]:
        """Load and compute all component footprints with resolved positions and pin layouts."""
        components = []
        for c in self.config.get("components", []):
            position = c.get("position", [0.0, 0.0, 0.0])
            rotation = c.get("rotation", [0.0, 0.0, 0.0])

            # Resolve joint reference dynamically if specified
            if c.get("joint_ref") is not None and self.parent_part is not None:
                joint_name = c["joint_ref"]["joint"]
                offset = c["joint_ref"].get("offset", [0.0, 0.0, 0.0])
                joint_loc = self.parent_part.joints[joint_name].location
                loc = joint_loc * Location(tuple(offset))
                position = [loc.position.X, loc.position.Y, loc.position.Z]

            pins = [PinModel(**p) for p in c.get("pins", [])]
            w, l, thickness = c["dimensions"]

            # Parse package and namespace from the YAML value
            pkg_str = c["package"]
            if ":" in pkg_str:
                ns, pkg = pkg_str.split(":", 1)
                layout_func = PIN_LAYOUT_REGISTRY.get(f"{ns}:{pkg}")
            else:
                pkg = pkg_str
                project_name = self.yaml_path.parent.name
                ns = project_name
                layout_func = PIN_LAYOUT_REGISTRY.get(f"{ns}:{pkg}")
                if layout_func is None:
                    # Fallback to global package name if namespaced key is not found
                    layout_func = PIN_LAYOUT_REGISTRY.get(pkg)
                    if layout_func is not None:
                        ns = None

            if layout_func is not None:
                layout_func(pins, w, l, c.get("slots_per_side"))

            label = LabelModel(**c["label"])

            components.append(
                FootprintModel(
                    name=c["name"],
                    package=pkg,
                    namespace=ns,
                    position=tuple(position),
                    rotation=tuple(rotation),
                    dimensions=tuple(c["dimensions"]),
                    mounting_holes=tuple(c["mounting_holes"]) if c.get("mounting_holes") is not None else None,
                    slots_per_side=c.get("slots_per_side"),
                    label=label,
                    pins=pins,
                )
            )
        return components

    @cached_property
    def nets(self) -> List[NetModel]:
        """Load and return structured network connections."""
        nets = []
        for n in self.config.get("nets", []):
            nets.append(
                NetModel(
                    name=n["name"],
                    color=n["color"],
                    pins=[(p[0], p[1]) for p in n["pins"]],
                    offset=tuple(n.get("offset", (0.0, 0.0))),
                    path=[tuple(p) for p in n.get("path", [])],
                )
            )
        return nets

    @validate_call
    def is_surface_mount(self, component_name: str) -> bool:
        """Check if a component footprint's package is registered as surface mount."""
        for fp in self.footprints:
            if fp.name == component_name:
                key = f"{fp.namespace}:{fp.package}" if fp.namespace else fp.package
                func = PIN_LAYOUT_REGISTRY.get(key)
                if func is None:
                    func = PIN_LAYOUT_REGISTRY.get(fp.package)
                if func is not None:
                    return getattr(func, "surface_mount", False)
        return False
