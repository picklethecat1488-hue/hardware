"""Unit tests for the ValveActuatorLimiterProvider class."""

import pytest
from unittest.mock import patch
from build123d import Part
import cadquery as cq
from projects_config.valve_actuator_limiter_config import ValveActuatorLimiterConfig
from projects.valve_actuator_limiter import ValveActuatorLimiterProvider
from provider import Action, Mode


class TestValveActuatorLimiterProvider:
    """Tests for ValveActuatorLimiterProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for ValveActuatorLimiterProvider."""
        mock_manifest = {
            "limiter_plate": {
                Action.PART: {
                    "modes": [Mode.DEFAULT],
                    "subassemblies": ["left", "right"],
                },
                Action.DIAGRAM: {"modes": [Mode.DEFAULT]},
            }
        }
        with patch("provider.provider.load_manifest", return_value=mock_manifest):
            yield ValveActuatorLimiterProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "valve_actuator_limiter"
        assert isinstance(provider.default_config, ValveActuatorLimiterConfig)

    def test_action_registrations(self, provider):
        """Verify that part actions are correctly registered."""
        assert "limiter_plate" in provider.part
        assert "limiter_plate" in provider.diagram

    def test_build_part_geometry(self, provider):
        """Verify that build_part produces valid geometry for both subassemblies."""
        for side in ["left", "right"]:
            part = provider.build_part("limiter_plate", side, Mode.DEFAULT)
            assert isinstance(part, Part)
            assert part.volume > 0
            assert part.is_valid

    def test_build_diagram(self, provider):
        """Verify that build_diagram returns a valid CadQuery assembly."""
        assy = provider.build_diagram(["limiter_plate"], Mode.DEFAULT)
        assert isinstance(assy, cq.Assembly)

    def test_volumes_match(self, provider):
        """Verify that mirroring maintains volume consistency."""
        left_part = provider.build_part("limiter_plate", "left", Mode.DEFAULT)
        right_part = provider.build_part("limiter_plate", "right", Mode.DEFAULT)

        assert left_part.volume == pytest.approx(right_part.volume)
