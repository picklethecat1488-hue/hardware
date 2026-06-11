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

    def test_configure_execution(self, configurator):
        """Verify that configure dispatches calls to the router."""
        mock_targets = MagicMock()
        mock_targets.__iter__.return_value = iter(["t1"])
        mock_targets.modes = ["m1"]
        configurator.target_parser.resolve = MagicMock(return_value=mock_targets)
        configurator.manager.router.manifest = {"t1": {Action.CONFIG: {"modes": ["m1"]}}}
        mock_targets.for_modes.return_value = mock_targets

        configurator.configure(names=["t1"])

        # Verify orchestration
        configurator.manager.router.run.assert_called_with(mock_targets)
