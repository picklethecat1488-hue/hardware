"""Unit tests for the ValveActuatorLimiter project."""

import pytest
from unittest.mock import patch
from build123d import Part, Vector
from projects_config.valve_actuator_limiter_config import ValveActuatorLimiterConfig
from projects.valve_actuator_limiter.provider import ValveActuatorLimiterProvider
from provider import Section, Mode, Room


class TestValveActuatorLimiterProvider:
    """Tests for ValveActuatorLimiterProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for ValveActuatorLimiterProvider with mocked manifest."""
        mock_manifest = {
            "limiter_plate": {
                Section.PART: {
                    "modes": [Mode.DEFAULT],
                    "subassemblies": ["90deg"],
                },
            },
            "product": {
                Section.DIAGRAM: {"modes": [Mode.DEFAULT]},
            },
        }
        with patch("provider.provider.load_manifest", return_value=mock_manifest):
            yield ValveActuatorLimiterProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "valve_actuator_limiter"
        assert isinstance(provider.default_config, ValveActuatorLimiterConfig)

    def test_action_registrations(self, provider):
        """Verify that part actions are correctly registered."""
        assert "plate" in provider.part
        assert "limiter_plate" in provider.part

    def test_build_part_geometry(self, provider):
        """Verify that build_limiter_plate produces valid geometry."""
        res = provider.build_limiter_plate("limiter_plate", Mode.DEFAULT)
        part = res.part
        assert isinstance(part, Part)
        assert part.volume > 0
        assert part.is_valid

    def test_build_diagram(self, provider):
        """Verify that build_diagram populates the room with geometry."""
        room = Room()
        provider.build_diagram(room, ["product"], Mode.DEFAULT)
        assert "limiter_plate" in room

    def test_configuration_loading(self, provider):
        """Ensure that critical measurement values are loaded correctly as non-zero floats."""
        assert provider.settings.pocket_radius == 25.0
        assert provider.settings.wall_thickness == 3.0
        assert provider.settings.bolt_radius == 3.2

    def test_hull_center_distances(self, provider):
        """Verify hull_center is positioned correctly relative to bolt holes."""
        center = provider.settings.hull_center
        holes = provider.settings.bolt_holes
        assert len(holes) == 3
        assert (center - holes[0]).length == pytest.approx(33.3, abs=1.0)
        assert (center - holes[1]).length == pytest.approx(33.3, abs=1.0)
        assert (center - holes[2]).length == pytest.approx(65.0, abs=1.0)
