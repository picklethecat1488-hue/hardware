"""Unit tests for the Configurator class."""

from unittest.mock import MagicMock
import pytest
from config import Configurator
from provider import Section, Mode, MODES, TargetList


class TestConfiguratorLogic:
    """Unit tests for Configurator internal logic."""

    @pytest.fixture
    def configurator(self):
        """Return a configurator instance with a mocked manager."""
        manager = MagicMock()
        return Configurator(manager)

    def test_resolve_modes(self, configurator):
        """Verify configuration mode resolution logic."""
        # Case 1: Mode.DEFAULT is not in base_modes (explicitly overridden by user)
        assert configurator.resolve_modes(MagicMock(spec=TargetList), [Mode.PRINT]) == [Mode.PRINT]

        # Case 2: Mode.DEFAULT is in base_modes, resolve all supported modes from manifest
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.return_value = iter(["t1", "t2"])
        configurator.manager.router.manifest = {
            "t1": {Section.CONFIG: {MODES: ["m1", "m2"]}},
            "t2": {Section.CONFIG: {MODES: ["m2", "m3"]}},
        }
        res = configurator.resolve_modes(mock_targets, [Mode.DEFAULT])
        assert res == ["m1", "m2", "m3"]
