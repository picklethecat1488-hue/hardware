"""Manages the lifecycle and configuration of multiple providers."""

import json
from typing import Any, Optional, cast
from concurrent.futures import ThreadPoolExecutor
from pydantic import validate_call
from model import AppConfig
from .provider import Provider
from .provider_router import ProviderRouter


class ProviderManager:
    """Manages the lifecycle and configuration of multiple providers."""

    def __init__(
        self,
        config: AppConfig,
        providers: Optional[list[Provider]] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the manager."""
        self.config = config
        self._router = ProviderRouter(executor=executor, providers=providers)

    @property
    def router(self) -> ProviderRouter:
        """Return the managed router."""
        return self._router

    @validate_call(config={"arbitrary_types_allowed": True})
    def load_configs(self) -> None:
        """Route environment variables from AppConfig extra fields to provider settings."""
        config = self.config
        delimiter = cast(str, config.model_config.get("env_nested_delimiter", "__"))

        for provider in self.router.providers:
            # Sync the provider to use the shared global configuration
            provider.app_config = config

            name = provider.name.lower()
            env_key = name.upper()
            provider_config = provider.settings
            if provider_config is None:
                continue

            # ROUTING: Extract values loaded by BaseSettings into model_extra and apply to sub-model
            prefix_with_delim = f"{env_key}{delimiter}"
            if config.model_extra:
                for k, v in config.model_extra.items():
                    if k.startswith(prefix_with_delim):
                        attr_name = k[len(prefix_with_delim) :].lower()
                        if hasattr(provider_config, attr_name):
                            # Handle potential JSON strings for complex types (lists/dicts)
                            if isinstance(v, str) and v.strip().startswith(("{", "[")):
                                try:
                                    v = json.loads(v)
                                except json.JSONDecodeError as e:
                                    raise ValueError(f"Failed to parse JSON configuration for '{k}': {v}") from e
                            setattr(provider_config, attr_name, v)

            # Ensure the config instance is attached to AppConfig as an extra field
            setattr(config, name, provider_config)

    @validate_call(config={"arbitrary_types_allowed": True})
    def save_configs(self) -> None:
        """Prepare AppConfig with provider configurations for environment dumping."""
        config = self.config
        for provider in self.router.providers:
            # Sync the provider to use the shared global configuration
            provider.app_config = config

            provider_config = provider.settings
            if provider_config is None:
                continue

            name = provider.name.lower()

            # Attach the config instance to AppConfig as an extra field for dumping
            setattr(config, name, provider_config)

            # Add to flattened keys so dump_env expands the nested Pydantic model into KEY__SUBKEY format
            env_key = name.upper()
            if env_key not in config._env_flattened_keys:
                config._env_flattened_keys.append(env_key)
