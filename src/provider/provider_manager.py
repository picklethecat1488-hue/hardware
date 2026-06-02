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
from shell import Logger
from .provider import Provider
from .provider_router import ProviderRouter


class ProviderManager:
    """Manages the lifecycle and configuration of multiple providers."""

    def __init__(
        self,
        config: AppConfig,
        providers: Optional[list[Provider]] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        logger: Optional[Logger] = None,
        bootstrap: bool = True,
    ):
        """Initialize the manager."""
        self.config = config
        self.logger = logger

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
        import provider

        # Resolve the source root (src/) relative to the provider package
        provider_file = os.path.abspath(provider.__file__)
        src_dir = os.path.dirname(os.path.dirname(provider_file))

        # Scan 'projects' directory for Provider subclasses
        pkg_name = "projects"
        pkg_path = os.path.join(src_dir, pkg_name)
        if os.path.isdir(pkg_path):
            # walk_packages recursively traverses the directory tree, ensuring that
            # providers in sub-directories (like projects/tube/) are correctly imported.
            prefix = f"{pkg_name}."
            for _, name, _ in pkgutil.walk_packages([pkg_path], prefix):
                if name not in sys.modules:
                    importlib.import_module(name)

        discovered: list[Provider] = []

        def find_subclasses(cls):
            for subclass in cls.__subclasses__():
                if not inspect.isabstract(subclass) and getattr(subclass, "_discover_provider", False):
                    try:
                        discovered.append(subclass(executor=executor, config=self.config, logger=self.logger))
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
        env_prefix = cast(str, config.model_config.get("env_prefix", ""))

        for provider in self.router.providers:
            name = provider.name.lower()
            provider_config = provider.default_config
            if provider_config is None:
                continue

            # The search prefix should include the global app prefix and the provider name
            # e.g., 'APP_TUBE__'
            prefix_with_delim = f"{env_prefix}{name}{delimiter}".upper()

            provider_updates = {}
            if config.model_extra:
                consumed_keys = []
                for k, v in config.model_extra.items():
                    if k.upper().startswith(prefix_with_delim):
                        consumed_keys.append(k)
                        # Reconstruct the nested path within the provider settings
                        # e.g. 'LOGO_TEXT_POSITIONS__DRIVER' -> ['logo_text_positions', 'driver']
                        path = k[len(prefix_with_delim) :].lower().split(delimiter)

                        curr = provider_updates
                        for part in path[:-1]:
                            curr = curr.setdefault(part, {})

                        # Values in model_extra are typically strings from the environment.
                        # Handle potential JSON strings for complex types (lists/dicts).
                        val = v
                        if isinstance(val, str) and val.strip().startswith(("{", "[")):
                            try:
                                val = json.loads(val)
                            except json.JSONDecodeError as e:
                                raise ValueError(f"Failed to parse JSON configuration for '{k}': {v}") from e
                        curr[path[-1]] = val

                # Remove keys that have been successfully routed to the provider model
                # to prevent double-prefixing and duplicates in dump_env.
                for k in consumed_keys:
                    del config.model_extra[k]

            if provider_updates:
                # Leverage Pydantic to validate and coerce the reconstructed nested dictionary.
                merged = provider_config.model_dump() | provider_updates
                coerced_model = provider_config.__class__.model_validate(merged)
                for attr_name in provider_updates.keys():
                    if hasattr(provider_config, attr_name):
                        setattr(provider_config, attr_name, getattr(coerced_model, attr_name))

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
