"""Unit tests for the Room container."""

from unittest.mock import MagicMock, patch
import pytest
from build123d import Compound, Box, Vector
from model import AppConfig, TextArgs
from provider.room import Room
from provider.types import ColorType


def test_room_add_success():
    """Verify items can be added to the room."""
    room = Room()
    room.add("item1", "geom1", color=ColorType.RED, alpha=0.5)
    assert "item1" in room
    assert room["item1"] == ("geom1", (1.0, 0.0, 0.0, 0.5))


def test_room_add_duplicate_name_raises_error():
    """Verify that adding a duplicate name raises a ValueError."""
    room = Room()
    room.add("duplicate", "geom1")
    with pytest.raises(ValueError, match="An item with the name 'duplicate' already exists"):
        room.add("duplicate", "geom2")


def test_room_add_default_values():
    """Verify default values are applied when adding items."""
    room = Room()
    room.add("default_item", "geom")
    assert room["default_item"] == ("geom", (0.5, 0.5, 0.5, 1.0))


def test_room_add_with_config():
    """Verify that default color is read from AppConfig when color is None."""
    mock_config = MagicMock(spec=AppConfig)
    mock_config.color = (0.1, 0.2, 0.3, 0.4)

    room = Room(config=mock_config)
    room.add("item", "geom")
    assert room["item"] == ("geom", (0.1, 0.2, 0.3, 0.4))


def test_room_add_with_rgb_tuple():
    """Verify that an RGB 3-tuple can be used as a color."""
    room = Room()
    rgb = (0.5, 0.5, 0.5)
    room.add("item", "geom", color=rgb)
    assert room["item"] == ("geom", (0.5, 0.5, 0.5, 1.0))


def test_room_compound_property():
    """Verify that the room can be converted to a single build123d Compound."""
    room = Room()
    box = Box(1, 1, 1)
    room.add("item1", box, color=ColorType.RED)

    assy = room.compound
    assert isinstance(assy, Compound)
    # build123d Compound children are identified by labels
    assert any(child.label == "item1" for child in assy.children)


def test_room_export_diagram():
    """Verify that export_diagram correctly maps options and calls ExportSVG for SVG paths."""
    room = Room()

    with patch("provider.room.ExportSVG") as mock_exporter_cls:
        mock_instance = mock_exporter_cls.return_value

        # Define a mock options object with snake_case attributes
        class MockOptions:
            width = 1000
            show_axes = False
            stroke_width = 0.5
            margin = 10

        options = MockOptions()

        # Add geometry to trigger scale calculation
        from build123d import Box

        room.add("item1", Box(100, 100, 100))

        room.export_diagram("test_output.svg", options)  # type: ignore

        # Verify that width is converted to scale and unsupported fields are removed
        expected_opts = {
            "scale": 10.0,  # 1000 / 100
            "line_weight": 0.5,
            "margin": 10,
        }

        mock_exporter_cls.assert_called_once_with(**expected_opts)
        mock_instance.write.assert_called_once_with("test_output.svg")

        # Verify add_shape was called with a Compound containing our item.
        # We check the captured argument directly to avoid calling room.compound
        # again, which would deparent the children from the recorded call.
        mock_instance.add_shape.assert_called_once()
        passed_compound = mock_instance.add_shape.call_args[0][0]
        assert isinstance(passed_compound, Compound)
        # One child for the manifold lines
        assert len(passed_compound.children) == 1


def test_room_add_label():
    """Verify annotations can be added to the room."""
    room = Room()
    loc = (10, 20, 30)
    room.add_label("label1", "Hello", loc, options=TextArgs(font_size=12))
    assert len(room._labels) == 1
    name, text, pos, opts = room._labels[0]
    assert text == "Hello"
    assert pos == Vector(10, 20, 30)
    assert opts.font_size == 12
