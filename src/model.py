"""Data models and configuration for the exhaust manifolds project."""

from functools import wraps
import inspect
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, TypeVar, overload, Union, Literal, cast
from functools import cached_property
import numpy as np
import yaml
from build123d import *  # type: ignore
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    # Project name
    project_name: str = "exhaust_manifolds"

    # Build version
    ver: int = 4

    # The part x boundaries
    x_bounds: list[float] = [145, 950]

    # The part y boundaries
    y_bounds: list[float] = [-32, 390]

    # The part bounds
    z_bounds: list[float] = [145, 530]

    # Wall thickness ~3mm
    wall_thickness: float = 3.0

    # Inlet and outlet diameters, 2.5", inner clamp diameter 3"
    clamp_diameters: list[float] = [63.5, 76.2, 63.5]

    # Inlet and outlet clamp length 2", inner clamp length 1"
    clamp_lengths: list[float] = [50.4, 25.4, 50.4]

    # The clamp positions, each one is a tuple of path offset and angle offset
    clamp_positions: dict[str, list[tuple[float, float] | None]] = {
        "driver": [None, (0.5, 0), None],
        "passenger": [None, (0.5, 0), None],
    }

    # Space between clamps on each side
    clamp_space: float = 15

    # The radius of the circular lap joint features
    joint_radius: float = 1.5

    # The clearance added to the recess side of the lap joint
    joint_space: float = 0.3

    # The part names, driver and passenger
    names: list[Literal["driver", "passenger"]] = ["driver", "passenger"]

    # Private attribute to store raw measurements loaded from file
    _measurements: list[list[float]] = []

    # The logo text arguments
    logo_text_args: dict[str, Any] = {
        "fontsize": 10,
        "distance": 3,
        "fontPath": "Sans",
        "halign": "center",
        "valign": "center",
        "kind": "bold",
    }

    # The logo text offset, pathwise and anglewise
    logo_text_positions: dict[str, tuple[float, float]] = {
        "driver": (0.4, 0),
        "passenger": (0.4, 0),
    }

    # Diagram export options
    diagram_options: dict[str, Any] = {
        "showAxes": False,
        "strokeWidth": 3,
        "strokeColor": (0, 0, 0),
        "projectionDir": (1, 1, 1),
        "width": 1024,
        "height": 1024,
    }

    # Distance between manifold assemblies in the diagram
    diagram_part_offset: int = 60

    # Distance between exploded halves in the diagram
    diagram_part_dist: int = 120

    # Distance of the labels from the parts in the diagram
    diagram_label_dist: int = 120

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="APP_", alias_generator=str.upper, populate_by_name=True
    )

    def __init__(self, **kwargs):
        """Initialize the config and load measurements from YAML."""
        super().__init__(**kwargs)
        yml_path = Path(__file__).parent / "measurements.yml"
        if yml_path.exists():
            with open(yml_path, "r") as f:
                try:
                    self._measurements = yaml.safe_load(f)
                except yaml.YAMLError:
                    raise ValueError("missing or invalid measurements.yml")

    @cached_property
    def measurements(self) -> dict[int, np.ndarray]:
        """Return raw measurement points."""
        p = {}
        for idx, item in enumerate(self._measurements):
            p[idx + 1] = np.array(item)
        # Correct for expected Z offset- middle of outlet instead of top
        for idx in [3, 6, 9, 10]:
            p[idx][2] = p[idx][2] - min(self.clamp_diameters) / 2
        return p

    def _ndarray2vec(self, arr: np.ndarray) -> Vector:
        return Vector(X=arr[0], Y=arr[1], Z=arr[2])

    @cached_property
    def P(self) -> dict[str, Vector]:
        """Get position vectors for all endpoints."""
        ret_val = {
            "driver_inlet": self._ndarray2vec(self.measurements[6]),
            "driver_outlet": self._ndarray2vec(self.measurements[9]),
            "passenger_inlet": self._ndarray2vec(self.measurements[3]),
            "passenger_outlet": self._ndarray2vec(self.measurements[10]),
        }
        return ret_val

    @cached_property
    def V(self) -> dict[str, Vector]:
        """Get direction vectors for all endpoints."""

        def dir_vector(start, end):
            """Generate a 3D direction vector for the given points."""
            v = np.array(end) - np.array(start)
            return v / np.linalg.norm(v)

        raw_driver_inlet = dir_vector(self.measurements[7], self.measurements[8])
        raw_passenger_inlet = dir_vector(self.measurements[5], self.measurements[4])
        ret_val = {
            "driver_inlet": self._ndarray2vec(raw_driver_inlet),
            "driver_outlet": Vector(X=-1, Y=0, Z=0),
            "passenger_inlet": self._ndarray2vec(raw_passenger_inlet),
            "passenger_outlet": Vector(X=1, Y=0, Z=0),
        }
        return ret_val

    @cached_property
    def bound_box(self) -> Part:
        """Return the axis-aligned build bounding box."""
        # Create the overall bounds.
        x_len = np.max(self.x_bounds) - np.min(self.x_bounds)
        y_len = np.max(self.y_bounds) - np.min(self.y_bounds)
        z_len = np.max(self.z_bounds) - np.min(self.z_bounds)
        center = (
            np.min(self.x_bounds) + x_len / 2,
            np.min(self.y_bounds) + y_len / 2,
            np.min(self.z_bounds) + z_len / 2,
        )

        with BuildPart() as bounds:
            Box(x_len, y_len, z_len)
            bounds.part.move(Location(center))

            # Subtract the valve controller bottom plane from the overall bounds.
            vx_len = self.measurements[2][0] - self.measurements[1][0]
            vy_len = np.max(self.y_bounds) - np.mean([self.measurements[2][1], self.measurements[1][1]])
            vz_len = np.max(self.z_bounds) - np.mean([self.measurements[2][2], self.measurements[1][2]])
            v_center = (
                np.min([self.measurements[2][0], self.measurements[1][0]]) + vx_len / 2,
                np.min([self.measurements[2][1], self.measurements[1][1]]) + vy_len / 2,
                np.min([self.measurements[2][2], self.measurements[1][2]]) + vz_len / 2,
            )
            with BuildPart(mode=Mode.SUBTRACT):
                add(Box(vx_len, vy_len, vz_len).moved(Location(v_center)))
        return bounds.part


# Generic type for callables used by the method_cache decorator
T = TypeVar("T", bound=Callable[..., Any])


@overload
def method_cache(func: Callable[..., Any]) -> Callable[..., Any]: ...


@overload
def method_cache(*, maxsize: int = 128) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def method_cache(func: Callable[..., Any] | None = None, *, maxsize: int = 128) -> Any:
    """Create per-instance cache to avoid memory leaks and Pydantic @validate_call conflicts."""

    def decorator(f: T) -> T:
        """Implement the decorator behavior for method_cache."""

        @wraps(f)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Create a unique string identifier for this specific method
            cache_attr = f"_cache_{f.__name__}"
            if not hasattr(self, cache_attr):
                setattr(self, cache_attr, OrderedDict())
            cache = getattr(self, cache_attr)

            # Create a cache key from the arguments
            key = (args, tuple(sorted(kwargs.items())))
            if key in cache:
                cache.move_to_end(key)
                return cache[key]

            # Compute new value
            result = f(self, *args, **kwargs)
            cache[key] = result
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return result

        # Masking __wrapped__ prevents Pydantic 2.x from following the wrapper back
        # to underlying compiled 'cyfunction' types, which causes validation errors.
        try:
            setattr(wrapper, "__signature__", inspect.signature(f))
        except (ValueError, TypeError):
            pass

        if hasattr(wrapper, "__wrapped__"):
            delattr(wrapper, "__wrapped__")

        return cast(T, wrapper)

    if func is None:
        return decorator
    return decorator(func)
