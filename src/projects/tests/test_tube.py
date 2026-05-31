"""Unit tests for the TubeProvider class."""

import pytest
from unittest.mock import patch
from model import AppConfig
from projects_config import TubeConfig
from projects import TubeProvider
from providers import Action, Mode, Subassembly, TargetList, ProviderManager


class TestTubeProvider:
    """Tests for TubeProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for TubeProvider.

        Note: We patch load_manifest to avoid file IO and ensure the manifest
        is aligned with our testing expectations for the skeleton.
        """
        mock_manifest = {
            "driver": {
                Action.CONFIG: {"modes": [Mode.DEFAULT, Mode.MOUNT, Mode.TEXT, Mode.BARE]},
                Action.PART: {
                    "modes": [Mode.DEFAULT, Mode.BARE],
                    "subassemblies": [Subassembly.LEFT, Subassembly.RIGHT],
                },
                Action.WIRE: {"modes": [Mode.DEFAULT]},
                Action.DIAGRAM: {"modes": [Mode.DEFAULT]},
            },
            "part_positions": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
            "overlay": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
        }
        with patch("providers.provider.load_manifest", return_value=mock_manifest):
            yield TubeProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "tube"
        assert isinstance(provider.default_config, TubeConfig)

    def test_settings_resolution(self, provider):
        """Verify settings property correctly retrieves TubeConfig from app_config."""
        assert isinstance(provider.settings, TubeConfig)
        # Ensure it reflects the defaults from TubeConfig
        assert provider.settings.wall_thickness == provider.default_config.wall_thickness

    def test_measurements_path_override(self, provider):
        """Verify that ProviderManager syncs the provider's specific measurements path."""
        config = AppConfig()
        # Before manager: uses AppConfig default
        assert "measurements.yml" in config.tube.measurements_path  # type: ignore

        mgr = ProviderManager(config, providers=[provider], bootstrap=False)
        mgr.load_configs()
        # After manager: uses TubeProvider's specific path
        assert "tube_measurements.yaml" in config.tube.measurements_path  # type: ignore

    def test_action_registrations(self, provider):
        """Verify that build, config, and view actions are correctly registered."""
        # Build actions
        assert Action.PART in provider.build
        assert Action.WIRE in provider.build
        assert Action.SKETCH in provider.build
        assert Action.DIAGRAM in provider.build

        # Config modes
        assert Mode.DEFAULT in provider.config
        assert Mode.MOUNT in provider.config
        assert Mode.TEXT in provider.config

        # View rooms
        assert "part_positions" in provider.view
        assert "overlay" in provider.view

    def test_run_part_placeholder(self, provider):
        """Verify executing a PART action returns the skeleton placeholder."""
        targets = provider.targets.supporting(Action.PART)
        results = provider.run(targets)
        # Provider returns namespaced results: [(name, result)]
        assert results == [("driver", "part_placeholder")]

    def test_run_wire_placeholder(self, provider):
        """Verify executing a WIRE action returns the skeleton placeholder."""
        targets = provider.targets.supporting(Action.WIRE)
        results = provider.run(targets)
        assert results == [("driver", "wire_placeholder")]

    def test_run_diagram_placeholder(self, provider):
        """Verify executing a DIAGRAM action returns a single placeholder object."""
        targets = provider.targets.supporting(Action.DIAGRAM)
        result = provider.run(targets)
        assert result == "diagram_placeholder"

    def test_run_view_placeholder(self, provider):
        """Verify executing a VIEW action returns the skeleton room data."""
        targets = TargetList(provider, ["part_positions"], action=Action.VIEW)
        results = provider.run(targets)
        assert results == [("part_positions", [])]

    def test_run_config_execution(self, provider):
        """Verify executing a CONFIG action returns None."""
        targets = provider.targets.supporting(Action.CONFIG).for_modes([Mode.DEFAULT])
        result = provider.run(targets)
        assert result is None

    def test_unsupported_config_mode_error(self, provider):
        """Verify that requesting an unregistered config mode raises a ValueError."""
        # Mode.BARE is in manifest but not in TubeProvider.config registry skeleton
        targets = TargetList(provider, ["driver"], action=Action.CONFIG, modes=[Mode.BARE])
        with pytest.raises(ValueError, match="No config handler registered for mode 'bare' in tube"):
            provider.run(targets)
