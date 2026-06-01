"""Unit tests for the Viewer class."""

import pytest
from unittest.mock import MagicMock, patch
from view import Viewer


class TestViewer:
    """Viewer unit tests."""

    @pytest.fixture
    def mock_builder(self):
        """Mock Builder fixture."""
        builder = MagicMock()
        builder.config.tube.names = ["driver", "passenger"]
        builder.config.bound_box = "mock_box"
        return builder

    @pytest.fixture
    def mock_configurator(self):
        """Mock Configurator fixture."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Mock Logger fixture."""
        return MagicMock()

    @pytest.fixture
    def viewer(self, mock_builder, mock_configurator, mock_logger):
        """Viewer fixture."""
        return Viewer(mock_builder, mock_configurator, mock_logger)

    def test_get_summary_truncation(self, viewer):
        """Verify summary logic for short and long lists."""
        assert viewer.get_summary(["a", "b"]) == "a, b"
        long_list = [str(i) for i in range(20)]
        summary = viewer.get_summary(long_list)
        assert summary.startswith("0, 1, 2, 3, 4, 5, 6, 7")
        assert "(20 items)" in summary

    def test_room_methods_return_tuples(self, viewer, mock_builder):
        """Verify that room methods return dictionaries of (geometry, color, alpha)."""
        mock_builder.create_wire.return_value = "wire_geom"
        wires = viewer.show_wires_room()
        assert "driver_wire" in wires
        assert wires["driver_wire"] == ("wire_geom", "magenta", 1.0)

        mock_builder.build_part.return_value = "part_geom"
        parts = viewer.show_parts_room()
        assert "driver_left" in parts
        assert parts["driver_left"] == ("part_geom", "green", 1.0)

    @patch("view.show")
    def test_show_view_bounds_inclusion(self, mock_show, viewer):
        """Verify bounding box is included when requested."""
        viewer.show_wires_room = MagicMock(return_value={})
        viewer.show_view("wires", show_bounds=True)

        _, kwargs = mock_show.call_args
        assert "bounds" in kwargs["names"]
        assert "grey" in kwargs["colors"]

    @patch("view.show")
    def test_show_view_filtering(self, mock_show, viewer):
        """Verify name filtering updates the internal names list."""
        viewer.show_parts_room = MagicMock(return_value={"dummy": (MagicMock(), "red", 1.0)})
        viewer.show_view("parts", name="driver")
        assert viewer.names == ["driver"]

    def test_show_view_error_on_empty(self, viewer):
        """Verify ValueError is raised if no items are generated."""
        # Mock an empty room response
        viewer.show_wires_room = MagicMock(return_value={})
        with pytest.raises(ValueError, match="No scenes to show"):
            viewer.show_view("wires")
