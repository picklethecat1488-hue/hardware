"""Application build configuration."""

import os
import json
from functools import cached_property
from pathlib import Path
from typing import Any, cast

import numpy as np
from pydantic import Field
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict
from build123d import BuildPart, Box, Part, Location, Mode, add

from .text_args import TextArgs
from .diagram_options import DiagramOptions
from .tube_config import TubeConfig
from .utils import method_cache, parse_measurements


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    project_name: str = Field(default="exhaust_manifolds", description="The project name")
    ver: int = Field(default=4, gt=0, description="Build version")
    measurements_path: str = Field(
        default=str(Path(__file__).parent.parent / "measurements.yml"),
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
    tube: TubeConfig = Field(default_factory=TubeConfig, description="Tube and part configuration")
    diagram_options: DiagramOptions = Field(default_factory=DiagramOptions, description="Diagram export options")
    diagram_part_offset: int = Field(default=60, description="Distance between manifold assemblies in the diagram")
    diagram_part_dist: int = Field(default=120, description="Distance between exploded halves in the diagram")
    diagram_label_dist: int = Field(default=120, description="Distance of the labels from the parts in the diagram")

    color: tuple[float, float, float, float] = Field(
        default=(1.0, 0.0, 1.0, 1.0), description="The default object color"
    )

    _env_flattened_keys: list[str] = ["TUBE", "LOGO_TEXT_ARGS", "LOGO_TEXT_POSITIONS", "DIAGRAM_OPTIONS"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        alias_generator=str.upper,
        validate_by_name=True,
        validate_by_alias=True,
        env_nested_delimiter="__",
    )

    def model_post_init(self, __context: Any) -> None:
        """Sync global settings to sub-models after initialization."""
        if self.tube.measurements_path is None:
            self.tube.measurements_path = self.measurements_path

    def dump_env(self, path: str | Path):
        """Dump the configuration to a .env file with flattened nested keys."""
        env_prefix = cast(str, self.model_config.get("env_prefix", ""))
        dump = self.model_dump(by_alias=True, mode="json")
        env_dir = Path(path).parent.absolute()

        def write_recursive(f, data, prefix=""):
            for k, v in data.items():
                k_upper = k.upper()
                full_key = f"{prefix}{k_upper}"
                if k_upper in self._env_flattened_keys and isinstance(v, dict):
                    write_recursive(f, v, f"{full_key}__")
                else:
                    val = v
                    if isinstance(v, str):
                        path_candidate = v
                        suffix = ""
                        if ":" in v and not os.path.exists(v):
                            parts = v.rsplit(":", 1)
                            if os.path.isabs(parts[0]):
                                path_candidate, suffix = parts[0], ":" + parts[1]
                        if os.path.isabs(path_candidate) and os.path.exists(path_candidate):
                            try:
                                val = os.path.relpath(path_candidate, env_dir) + suffix
                            except (ValueError, TypeError):
                                pass
                    val_str = json.dumps(val, separators=(",", ":")) if isinstance(val, (dict, list)) else str(val)
                    f.write(f"{full_key}={val_str}\n")

        with open(path, "w") as f:
            write_recursive(f, dump, prefix=env_prefix)

    @cached_property
    def bound_box(self) -> Part:
        """Return the axis-aligned build bounding box."""
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
            vx_len = self.tube.measurements[2][0] - self.tube.measurements[1][0]
            vy_len = np.max(self.y_bounds) - np.mean([self.tube.measurements[2][1], self.tube.measurements[1][1]])
            vz_len = np.max(self.z_bounds) - np.mean([self.tube.measurements[2][2], self.tube.measurements[1][2]])
            v_center = (
                np.min([self.tube.measurements[2][0], self.tube.measurements[1][0]]) + vx_len / 2,
                np.min([self.tube.measurements[2][1], self.tube.measurements[1][1]]) + vy_len / 2,
                np.min([self.tube.measurements[2][2], self.tube.measurements[1][2]]) + vz_len / 2,
            )
            with BuildPart(mode=Mode.SUBTRACT):
                add(Box(vx_len, vy_len, vz_len).moved(Location(v_center)))
        return cast(Part, bounds.part)
