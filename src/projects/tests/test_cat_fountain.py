"""Unit tests for the CatFountain project."""

import pytest
from unittest.mock import patch
from build123d import Part
from projects_config.cat_fountain_config import CatFountainConfig
from projects.cat_fountain.provider import CatFountainProvider
from provider import Section, Mode, Room


class TestCatFountainProvider:
    """Tests for CatFountainProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for CatFountainProvider with mocked manifest."""
        mock_manifest = {
            "fountain": {
                Section.PART: {
                    "modes": [Mode.DEFAULT, Mode.PRINT],
                },
                Section.DIAGRAM: {"modes": [Mode.DEFAULT]},
            }
        }
        with patch("provider.provider.load_manifest", return_value=mock_manifest):
            yield CatFountainProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "cat_fountain"
        assert isinstance(provider.default_config, CatFountainConfig)

    def test_action_registrations(self, provider):
        """Verify that part actions are correctly registered."""
        assert "bowl" in provider.part
        assert "impeller" in provider.part
        assert "tube" in provider.part
        assert "spout" in provider.part
        assert "fountain" in provider.part

    def test_build_part_geometry(self, provider):
        """Verify that build_fountain produces valid geometry."""
        res = provider.build_fountain("fountain", Mode.DEFAULT)
        part = res.part
        assert isinstance(part, Part)
        assert part.volume > 0
        assert part.is_valid

    def test_build_diagram(self, provider):
        """Verify that build_diagram populates the room with geometry."""
        room = Room()
        provider.build_diagram(room, ["fountain"], Mode.DEFAULT)
        assert "fountain" in room

    def test_configuration_loading(self, provider):
        """Ensure that critical measurement values are loaded correctly."""
        assert provider.settings.bowl_radius == 80.0
        assert provider.settings.tube_radius == 8.0
        assert provider.settings.impeller_radius == 12.0
        assert provider.settings.impeller_blades == 6
