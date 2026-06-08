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
            part = provider.build_limiter_plate("limiter_plate", side, Mode.DEFAULT)
            assert isinstance(part, Part)
            assert part.volume > 0
            assert part.is_valid

    def test_build_diagram(self, provider):
        """Verify that build_diagram returns a valid CadQuery assembly."""
        assy = provider.build_diagram("limiter_plate", Mode.DEFAULT)
        assert isinstance(assy, cq.Assembly)

    def test_volumes_match(self, provider):
        """Verify that mirroring maintains volume consistency."""
        left_part = provider.build_limiter_plate("limiter_plate", "left", Mode.DEFAULT)
        right_part = provider.build_limiter_plate("limiter_plate", "right", Mode.DEFAULT)

        assert left_part.volume == pytest.approx(right_part.volume)

    def test_configuration_loading(self, provider):
        """Ensure that critical measurement values are loaded correctly as non-zero floats."""
        assert provider.settings.pocket_radius == 25.0
        assert provider.settings.wall_thickness == 3.0
        assert provider.settings.bolt_radius == 3.2

    def test_bolt_hole_spacing(self, provider):
        """Verify the distances between the asymmetric bolt holes match spec.

        Holes are defined in measurements.yaml relative to part centroid.
        Spec distances: 65mm, 85mm, 80mm.
        """
        holes = provider.settings.bolt_holes
        assert len(holes) == 3

        # Calculate Euclidean distances between the three pairs of Vectors
        dist_12 = (holes[0] - holes[1]).length
        dist_23 = (holes[1] - holes[2]).length
        dist_31 = (holes[2] - holes[0]).length

        distances = sorted([dist_12, dist_23, dist_31])

        assert distances[0] == pytest.approx(65.0, abs=0.1)
        assert distances[1] == pytest.approx(80.0, abs=0.1)
        assert distances[2] == pytest.approx(85.0, abs=0.1)
