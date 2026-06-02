"""Application build configuration."""

import os
import json
from pathlib import Path
from typing import Any, cast

from pydantic import Field
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict

from .text_args import TextArgs
from .diagram_options import DiagramOptions
from .utils import method_cache, load_measurements


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    project_name: str = Field(default="exhaust_manifolds", description="The project name")
    ver: int = Field(default=4, gt=0, description="Build version")
    measurements_path: str = Field(
        default=str(Path(__file__).parent.parent / "measurements.yml"),
        description="Path to the measurements YAML file.",
    )
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
        extra="allow",
    )

    def dump_env(self, path: str | Path):
        """Dump the configuration to a .env file with flattened nested keys."""
        env_prefix = cast(str, self.model_config.get("env_prefix", ""))
        dump = self.model_dump(by_alias=True, mode="json")
        env_dir = Path(path).parent.absolute()

        def write_recursive(f, data, prefix=""):
            for k, v in data.items():
                k_upper = k.upper()
                # If the key already contains the global prefix (likely from model_extra), don't double it.
                if prefix == env_prefix and k_upper.startswith(env_prefix):
                    full_key = k_upper
                else:
                    full_key = f"{prefix}{k_upper}"

                if k_upper in self._env_flattened_keys and isinstance(v, dict):
                    write_recursive(f, v, f"{full_key}__")
                else:
                    val = v
                    if isinstance(v, str):
                        if os.path.isabs(v) and os.path.exists(v):
                            try:
                                val = os.path.relpath(v, env_dir)
                            except (ValueError, TypeError):
                                pass
                    val_str = json.dumps(val, separators=(",", ":")) if isinstance(val, (dict, list)) else str(val)
                    f.write(f"{full_key}={val_str}\n")

        with open(path, "w") as f:
            write_recursive(f, dump, prefix=env_prefix)
