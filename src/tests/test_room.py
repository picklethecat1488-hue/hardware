"""Unit tests for the Room container."""

from unittest.mock import MagicMock, patch
import math
from typing import cast
import pytest
from build123d import Compound, Box, Vector, RigidJoint, RevoluteJoint, Axis, Location
from model import AppConfig, TextArgs, DiagramOptions
from provider.room import Room
from provider.types import ColorType, URDFShape


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
            view_from = "front"

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


def test_room_parse_options_view_from():
    """Verify that view_from is correctly parsed from DiagramOptions."""
    room = Room()
    options = DiagramOptions(view_from="top rear")
    opts = room._parse_options(options)
    assert opts["view_from"] == "top rear"


def test_room_get_projection_vectors_named_views():
    """Verify that named view expressions map to correct direction vectors."""
    room = Room()
    room.add("box", Box(1, 1, 1))  # Centered at (0,0,0)

    # Test simple 'top' view
    look_from, look_at, _ = room._get_projection_vectors({"view_from": "top"})
    assert look_at == Vector(0, 0, 0)
    assert (look_from - look_at).normalized() == Vector(0, 0, 1)

    # Test composite 'top rear' view: top (0,0,1) + rear (0,1,0) -> (0,1,1)
    look_from, look_at, _ = room._get_projection_vectors({"view_from": "top rear"})
    expected_dir = Vector(0, 1, 1).normalized()
    assert (look_from - look_at).normalized() == expected_dir


def test_room_get_projection_vectors_dynamic_distance():
    """Verify that the camera distance is calculated based on the bounding box diagonal."""
    room = Room()
    room.add("box", Box(100, 100, 100))
    bb = room.compound.bounding_box()
    expected_distance = bb.diagonal * 2

    look_from, look_at, _ = room._get_projection_vectors({"view_from": "top"})
    assert (look_from - look_at).length == pytest.approx(expected_distance)


def test_room_get_projection_vectors_overrides():
    """Verify that projection_origin and projection_dir override automatic calculations."""
    room = Room()
    room.add("box", Box(1, 1, 1))
    opts = {"projection_origin": (10, 10, 10), "projection_dir": (1, 1, 1)}
    look_from, look_at, _ = room._get_projection_vectors(opts)
    assert look_from == Vector(10, 10, 10)
    assert look_at == Vector(1, 1, 1)


def test_room_translate_joints():
    """Verify that translate_joints correctly maps build123d joints to URDF attributes on shapes."""
    room = Room()

    parent = Box(10, 10, 10)
    parent_shape = cast(URDFShape, parent)
    parent_shape.urdf_label = "parent_link"
    room.add("parent_link", parent)

    child = Box(5, 5, 5)
    child_shape = cast(URDFShape, child)
    child_shape.urdf_label = "child_link"
    room.add("child_link", child)

    pj = RigidJoint("joint_p", parent, Location((0, 0, 5)))
    cj = RevoluteJoint("joint_c", child, Axis((0, 0, 0), (0, 1, 0)), angular_range=(0, 180))
    pj.connect_to(cj)

    assert getattr(child, "urdf_parent", None) is None

    room.translate_joints()

    assert child_shape.urdf_parent == "parent_link"
    assert child_shape.urdf_joint_type == "revolute"
    assert child_shape.urdf_joint_axis == "0 1 0"
    assert child_shape.urdf_joint_lower is not None
    assert math.isclose(child_shape.urdf_joint_lower, 0.0)
    assert child_shape.urdf_joint_upper is not None
    assert math.isclose(child_shape.urdf_joint_upper, math.radians(180))


def test_room_disconnect_joints():
    """Verify that disconnect_joints clears all URDF joint connection properties on shapes."""
    room = Room()

    child = Box(5, 5, 5)
    child_shape = cast(URDFShape, child)
    child_shape.urdf_parent = "parent_link"
    child_shape.urdf_joint_type = "revolute"
    child_shape.urdf_joint_axis = "0 1 0"
    child_shape.urdf_joint_lower = 0.0
    child_shape.urdf_joint_upper = 3.14
    room.add("child", child)

    assert child_shape.urdf_parent == "parent_link"

    room.disconnect_joints()

    assert child_shape.urdf_parent is None
    assert child_shape.urdf_joint_type is None
    assert child_shape.urdf_joint_axis is None
    assert child_shape.urdf_joint_lower is None
    assert child_shape.urdf_joint_upper is None
