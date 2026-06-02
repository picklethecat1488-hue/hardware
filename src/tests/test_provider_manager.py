"""Integration tests for the ProviderManager and project discovery."""

import pytest
from model import AppConfig
from provider import ProviderManager, Action, MODES


class TestProviderManagerIntegration:
    """Ensures all projects are correctly discovered and registered."""

    @pytest.fixture
    def manager(self):
        """Return a bootstrapped ProviderManager instance."""
        config = AppConfig()
        # bootstrap=True triggers auto-discovery and config syncing
        return ProviderManager(config, bootstrap=True)

    def test_provider_bootstrap_integrity(self, manager):
        """Verify that all providers are bootstrapped with correct settings."""
        assert len(manager.router.providers) > 0, "No providers were discovered."

        for provider in manager.router.providers:
            # 1. Ensure settings are linked to the global AppConfig
            assert hasattr(manager.config, provider.name), f"{provider.name} config missing from AppConfig"
            settings = getattr(manager.config, provider.name)
            assert provider.settings == settings

            # 2. Ensure settings is the correct specialized type
            assert isinstance(provider.settings, provider.default_config.__class__)

            # 3. Ensure measurements_path was resolved during bootstrap if it exists in the model
            if hasattr(provider.settings, "measurements_path"):
                assert provider.settings.measurements_path is not None
                assert "measurements.yaml" in provider.settings.measurements_path

    def test_callback_registration_alignment(self, manager):
        """Ensure providers implement all handlers promised by their manifests."""
        for provider in manager.router.providers:
            manifest = provider.manifest

            for target_name, target_cfg in manifest.items():
                # Verify Action.PART registration
                if Action.PART in target_cfg:
                    assert target_name in provider.part, (
                        f"Provider '{provider.name}' manifest claims Action.PART support for "
                        f"'{target_name}', but it is missing from provider.part registry."
                    )

                # Verify Action.DIAGRAM registration
                if Action.DIAGRAM in target_cfg:
                    assert target_name in provider.diagram, (
                        f"Provider '{provider.name}' manifest claims Action.DIAGRAM support for "
                        f"'{target_name}', but it is missing from provider.diagram registry."
                    )

                # Verify Action.VIEW registration
                if Action.VIEW in target_cfg:
                    assert target_name in provider.view, (
                        f"Provider '{provider.name}' manifest claims Action.VIEW support for "
                        f"'{target_name}', but it is missing from provider.view registry."
                    )

                # Verify Action.CONFIG registration (mapped by Mode)
                if Action.CONFIG in target_cfg:
                    supported_modes = target_cfg[Action.CONFIG].get(MODES, [])
                    for mode in supported_modes:
                        # Normalize Mode enum/string to string for registry lookup
                        mode_key = mode.value if hasattr(mode, "value") else str(mode)
                        assert mode_key in provider.config, (
                            f"Provider '{provider.name}' manifest claims Action.CONFIG support for "
                            f"mode '{mode_key}', but no handler is registered in provider.config."
                        )
