"""Application build configuration."""

import os
import json
from pathlib import Path
from typing import Any, cast

from pydantic import Field
from pydantic_changedetect import ChangeDetectionMixin
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils import method_cache


class AppConfig(ChangeDetectionMixin, BaseSettings):
    """Application build configuration."""

    color: tuple[float, float, float, float] = Field(
        default=(1.0, 0.0, 1.0, 1.0), description="The default object color"
    )

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

                if isinstance(v, dict):
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
