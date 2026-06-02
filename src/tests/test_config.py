"""Contains Configurator unit tests."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from config import Configurator
from provider import Action, TargetList


class TestConfigurator:
    """Unit tests for the Configurator orchestration logic."""

    @pytest.fixture
    def mock_manager(self):
        """Return a mock ProviderManager."""
        manager = MagicMock()
        manager.config = MagicMock()
        manager.logger = MagicMock()
        return manager

    @pytest.fixture
    def configurator(self, mock_manager):
        """Return a configurator instance."""
        # Pass the mock logger to ensure .print calls are capturable
        return Configurator(mock_manager, logger=mock_manager.logger)

    def test_get_summary(self, configurator):
        """Verify target list truncation in log summary."""
        assert configurator._get_summary(["a", "b"]) == "a, b"
        long_list = [str(i) for i in range(10)]
        summary = configurator._get_summary(long_list)
        assert "..." in summary
        assert "(10 items)" in summary

    def test_resolve_targets(self, configurator):
        """Verify that _resolve_targets filters based on Action.CONFIG."""
        mock_targets = MagicMock()
        configurator.manager.router.targets.supporting.return_value = mock_targets

        # Test with names
        configurator._resolve_targets(names=["p1/t1"])
        configurator.manager.router.targets.supporting.assert_called_with(Action.CONFIG)
        mock_targets.for_targets.assert_called_with(["p1/t1"])

        # Test literal error
        mock_targets.for_targets.return_value = []
        with pytest.raises(ValueError, match="No matching configuration targets found"):
            configurator._resolve_targets(names=["missing"])

        # Test wildcard error (should raise instead of warning)
        mock_targets.for_targets.return_value = TargetList(configurator.manager.router, [])
        with pytest.raises(ValueError, match="No targets matched wildcard pattern"):
            configurator._resolve_targets(names=["tube/*"])

    def test_resolve_modes(self, configurator):
        """Verify mode discovery from manifests."""
        configurator.manager.router.manifest = {
            "t1": {Action.CONFIG: {"modes": ["m1", "m2"]}},
            "t2": {Action.CONFIG: {"modes": ["m2", "m3"]}},
        }

        # Discover all
        modes = configurator._resolve_modes(["t1", "t2"])
        assert modes == ["m1", "m2", "m3"]

        # Override
        modes_override = configurator._resolve_modes(["t1"], mode_override="custom")
        assert modes_override == ["custom"]

        # Wildcard override
        modes_wildcard = configurator._resolve_modes(["t1"], mode_override="m*")
        assert modes_wildcard == ["m1", "m2"]

        # Error
        with pytest.raises(ValueError, match="No configuration modes found"):
            configurator._resolve_modes(["t3_missing"], None)

    def test_configure_execution(self, configurator):
        """Verify that configure dispatches calls to the router."""
        mock_targets = MagicMock()
        mock_targets.__iter__.return_value = iter(["t1"])
        configurator.manager.router.targets.supporting.return_value = mock_targets
        configurator.manager.router.manifest = {"t1": {Action.CONFIG: {"modes": ["m1"]}}}

        # Mock for_modes to return a list of targets so it passes truthiness check
        mock_run_targets = MagicMock()
        mock_targets.for_modes.return_value = mock_run_targets

        configurator.configure()

        # Verify orchestration
        mock_targets.for_modes.assert_called_with(["m1"])
        configurator.manager.router.run.assert_called_with(mock_run_targets)
