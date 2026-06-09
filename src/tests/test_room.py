"""Unit tests for the Room container."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest
import cadquery as cq
from model.app_config import AppConfig
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


def test_room_assembly_property():
    """Verify that the room can be converted to a cq.Assembly."""
    room = Room()
    with patch("cadquery.Shape.cast") as mock_cast:
        # Setup mock return for cast to avoid CadQuery internal validation
        mock_shape = MagicMock(spec=cq.Shape)
        mock_cast.return_value = mock_shape

        # Create a mock object that looks like build123d geometry (has .wrapped)
        mock_geom = MagicMock()
        mock_geom.wrapped = MagicMock()
        room.add("item1", mock_geom, color=ColorType.RED)

        assy = room.assembly
        assert isinstance(assy, cq.Assembly)
        assert "item1" in [c.name for c in assy.children]


def test_room_export_svg():
    """Verify that export_svg correctly maps options and calls export."""
    room = Room()

    # We mock the assembly property to avoid building a real assembly in this test
    with patch("provider.room.Room.assembly", new_callable=PropertyMock) as mock_assy_prop:
        mock_assy = MagicMock()
        mock_compound = MagicMock()
        mock_assy.toCompound.return_value = mock_compound
        mock_assy_prop.return_value = mock_assy

        # Define a mock options object with snake_case attributes
        class MockOptions:
            width = 800
            projection_dir = (0, 0, -1)
            stroke_width = 0.5
            show_hidden = True
            margin_left = None  # Should be ignored if None

        options = MockOptions()
        room.export_svg("test_output.svg", options)

        # Verify the explicit mapping from snake_case to camelCase
        expected_opts = {
            "width": 800,
            "projectionDir": (0, 0, -1),
            "strokeWidth": 0.5,
            "showHidden": True,
        }

        mock_compound.export.assert_called_once_with("test_output.svg", opt=expected_opts)
