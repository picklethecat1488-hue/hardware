"""Manages the lifecycle and configuration of multiple providers."""

import json
import os
import inspect
import pkgutil
import importlib
import sys
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
        bootstrap: bool = True,
    ):
        """Initialize the manager."""
        self.config = config

        if providers is not None and bootstrap:
            raise ValueError("Cannot bootstrap when providers are explicitly provided.")

        if providers is None and bootstrap:
            providers = self._discover_providers(executor)

        self._router = ProviderRouter(executor=executor, providers=providers)

        if bootstrap:
            self.load_configs()

    @property
    def router(self) -> ProviderRouter:
        """Return the managed router."""
        return self._router

    def _discover_providers(self, executor: Optional[ThreadPoolExecutor]) -> list[Provider]:
        """Automatically discover and instantiate Provider subclasses in the package."""
        # Scan both the library providers and the project providers
        import provider.provider as lib_base

        try:
            import projects as project_base

            search_targets = [lib_base, project_base]
        except ImportError:
            search_targets = [lib_base]

        for base_module in search_targets:
            if hasattr(base_module, "__file__") and base_module.__file__:
                package_path = os.path.dirname(base_module.__file__)
                for _, name, is_pkg in pkgutil.iter_modules([package_path]):
                    if not is_pkg:
                        module_name = f"{base_module.__package__}.{name}"
                        if module_name not in sys.modules:
                            importlib.import_module(module_name)

        discovered: list[Provider] = []

        def find_subclasses(cls):
            for subclass in cls.__subclasses__():
                if not inspect.isabstract(subclass) and getattr(subclass, "_discover_provider", False):
                    try:
                        discovered.append(subclass(executor=executor, config=self.config))
                    except (TypeError, AttributeError):
                        continue
                find_subclasses(subclass)

        find_subclasses(Provider)
        return discovered

    @validate_call(config={"arbitrary_types_allowed": True})
    def load_configs(self) -> None:
        """Route environment variables from AppConfig extra fields to provider settings."""
        config = self.config
        delimiter = cast(str, config.model_config.get("env_nested_delimiter", "__"))

        for provider in self.router.providers:
            name = provider.name.lower()
            provider_config = provider.default_config
            if provider_config is None:
                continue
            env_key = name.upper()

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
            # Sync the provider to use the shared global configuration
            provider.app_config = config

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
