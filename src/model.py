"""Data models and configuration for the exhaust manifolds project."""

from functools import wraps
import inspect
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, TypeVar, overload, Literal, cast, Tuple
from functools import cached_property
import numpy as np
import yaml
from build123d import *  # type: ignore
from pydantic import BaseModel, Field
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict


class TextArgs(BaseModel):
    """Text configuration arguments."""

    font_size: float = Field(default=10, description="Font size in points")
    font: str = Field(default="Sans", description="Font name")
    align: Tuple[Align, Align] = Field(
        default=(Align.CENTER, Align.CENTER), description="Horizontal and vertical alignment"
    )
    font_style: FontStyle = Field(default=FontStyle.BOLD, description="Font style (Regular, Bold, Italic)")
    height: float = Field(default=3, description="Extrusion height of the text")


class DiagramOptions(BaseModel):
    """Diagram export configuration."""

    show_axes: bool = Field(default=False, alias="showAxes", description="Show coordinate axes")
    stroke_width: float = Field(default=3, alias="strokeWidth", description="Width of lines")
    stroke_color: Tuple[int, int, int] = Field(default=(0, 0, 0), alias="strokeColor", description="RGB color of lines")
    projection_dir: Tuple[float, float, float] = Field(
        default=(1, 1, 1), alias="projectionDir", description="Camera projection direction"
    )
    width: int = Field(default=1024, description="Output image width")
    height: int = Field(default=1024, description="Output image height")


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    project_name: str = Field(default="exhaust_manifolds", description="The project name")

    ver: int = Field(default=4, description="Build version", gt=0)

    measurements_path: str = Field(
        str(Path(__file__).parent / "measurements.yml"),
        description="Path to the measurements YAML file, optionally followed by ':key' to select a sub-entry.",
    )

    x_bounds: list[float] = Field(
        default_factory=lambda: [145, 950],
        description="The project x boundaries",
        min_length=2,
        max_length=2,
    )

    y_bounds: list[float] = Field(
        default_factory=lambda: [-32, 390],
        description="The project y boundaries",
        min_length=2,
        max_length=2,
    )

    z_bounds: list[float] = Field(
        default_factory=lambda: [145, 530],
        description="The project z boundaries",
        min_length=2,
        max_length=2,
    )

    wall_thickness: float = Field(default=3.0, description="Wall thickness ~3mm", gt=0)

    clamp_diameters: list[float] = Field(
        default_factory=lambda: [63.5, 76.2, 63.5],
        description='Inlet and outlet diameters, 2.5", inner clamp diameter 3"',
        min_length=3,
    )

    clamp_lengths: list[float] = Field(
        default_factory=lambda: [50.4, 25.4, 50.4],
        description='Inlet and outlet clamp length 2", inner clamp length 1"',
        min_length=3,
    )

    clamp_positions: dict[str, list[tuple[float, float] | None]] = Field(
        default_factory=lambda: {
            "driver": [None, (0.5, 0), None],
            "passenger": [None, (0.5, 0), None],
        },
        description="The clamp positions, each one is a tuple of path offset and angle offset",
    )

    clamp_space: float = Field(default=15, description="Space between clamps on each side", ge=0)

    joint_radius: float = Field(default=1.5, description="The radius of the circular lap joint features", gt=0)

    joint_space: float = Field(default=0.3, description="The clearance added to the recess side of the lap joint", ge=0)

    names: list[Literal["driver", "passenger"]] = Field(
        default_factory=lambda: ["driver", "passenger"], description="The part names, driver and passenger"
    )

    _measurements: list[list[float]] | dict[int | str, list[float]] = []

    logo_text_args: TextArgs = Field(default_factory=TextArgs, description="The logo text arguments")

    logo_text_positions: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "driver": (0.4, 0),
            "passenger": (0.4, 0),
        },
        description="The logo text offset, pathwise and anglewise",
    )

    diagram_options: DiagramOptions = Field(default_factory=DiagramOptions, description="Diagram export options")

    diagram_part_offset: int = Field(default=60, description="Distance between manifold assemblies in the diagram")

    diagram_part_dist: int = Field(default=120, description="Distance between exploded halves in the diagram")

    diagram_label_dist: int = Field(default=120, description="Distance of the labels from the parts in the diagram")

    """ The list of model keys which flattening gets applied to by dump_env. """
    _env_flattened_keys: list[str] = ["LOGO_TEXT_ARGS", "DIAGRAM_OPTIONS"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        alias_generator=str.upper,
        validate_by_name=True,
        validate_by_alias=True,
        env_nested_delimiter="__",
    )

    def __init__(self, **kwargs):
        """Initialize the config and load measurements from YAML."""
        super().__init__(**kwargs)
        self._measurements = parse_measurements(self.measurements_path)

    def dump_env(self, path: str | Path):
        """Dump the configuration to a .env file with flattened nested keys."""
        dump = self.model_dump(by_alias=True, mode="json")
        with open(path, "w") as f:
            for key, value in dump.items():
                if key in self._env_flattened_keys and isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        # Flatten nested models into individual lines using the double underscore delimiter
                        if isinstance(sub_value, (dict, list)):
                            val_str = json.dumps(sub_value, separators=(",", ":"))
                        else:
                            val_str = str(sub_value)
                        f.write(f"{key}__{sub_key.upper()}={val_str}\n")
                elif isinstance(value, (dict, list)):
                    val_str = json.dumps(value, separators=(",", ":"))
                    f.write(f"{key}={val_str}\n")
                else:
                    f.write(f"{key}={value}\n")

    @cached_property
    def measurements(self) -> dict[int, np.ndarray]:
        """Return raw measurement points."""
        p = {}
        if isinstance(self._measurements, list):
            measurements = cast(list, self._measurements)
            for idx, item in enumerate(measurements):
                p[idx + 1] = np.array(item, dtype=float)
        elif isinstance(self._measurements, dict):
            measurements = cast(dict, self._measurements)
            for key, item in measurements.items():
                p[key] = np.array(item, dtype=float)

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
            cast(Part, bounds.part).move(Location(center))

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
        return cast(Part, bounds.part)


def parse_measurements(measurements_path: str) -> Any:
    """Parse the measurements YAML file and return the raw data."""
    if ":" in measurements_path:
        file_path_str, key = measurements_path.split(":", 1)
    else:
        file_path_str, key = measurements_path, None

    file_path = Path(file_path_str)
    if not file_path.exists():
        return {}

    with open(file_path, "r") as f:
        try:
            data = yaml.safe_load(f) or {}
            return data.get(key, {}) if key else data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML at {file_path}") from e


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
