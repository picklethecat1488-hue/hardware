"""Unit tests for the Room container."""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import math
from typing import cast, Any
import pybullet as p
import pytest
from build123d import Compound, Box, Vector, RigidJoint, RevoluteJoint, Axis, Location, LinearJoint, BallJoint
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


def test_room_urdf_pybullet_integration():
    """Verify that PyBullet can successfully load the exported URDF and parses all joint types correctly."""
    room = Room()

    # Create parent link
    parent = Box(10, 10, 10)
    p_shape = cast(URDFShape, parent)
    p_shape.urdf_label = "parent_link"
    room.add("parent_link", parent)

    temp_dir = tempfile.mkdtemp()
    proj_dir = os.path.join(temp_dir, "test_robot")
    os.makedirs(proj_dir, exist_ok=True)

    try:
        # Mock .obj files
        with open(os.path.join(proj_dir, "parent_link.obj"), "w") as f:
            f.write("# empty obj\n")

        # 1. Fixed (RigidJoint)
        child_fixed = Box(2, 2, 2)
        room.add("child_fixed", child_fixed)
        with open(os.path.join(proj_dir, "child_fixed.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_fixed = RigidJoint("j_p_fixed", parent, Location((15, 0, 0)))
        cj_fixed = RigidJoint("j_c_fixed", child_fixed, Location((0, 0, 0)))
        pj_fixed.connect_to(cj_fixed)

        # 2. Revolute
        child_rev = Box(2, 2, 2)
        room.add("child_rev", child_rev)
        with open(os.path.join(proj_dir, "child_rev.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_rev = RigidJoint("j_p_rev", parent, Location((30, 0, 0)))
        cj_rev = RevoluteJoint("j_c_rev", child_rev, Axis((0, 0, 0), (0, 1, 0)), angular_range=(0, 180))
        pj_rev.connect_to(cj_rev)

        # 3. Continuous (RevoluteJoint with >= 360 angular range)
        child_cont = Box(2, 2, 2)
        room.add("child_cont", child_cont)
        with open(os.path.join(proj_dir, "child_cont.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_cont = RigidJoint("j_p_cont", parent, Location((45, 0, 0)))
        cj_cont = RevoluteJoint("j_c_cont", child_cont, Axis((0, 0, 0), (0, 1, 0)), angular_range=(0, 360))
        pj_cont.connect_to(cj_cont)

        # 4. Prismatic (LinearJoint)
        child_prism = Box(2, 2, 2)
        room.add("child_prism", child_prism)
        with open(os.path.join(proj_dir, "child_prism.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_prism = RigidJoint("j_p_prism", parent, Location((60, 0, 0)))
        cj_prism = LinearJoint("j_c_prism", child_prism, Axis((0, 0, 0), (0, 0, 1)), linear_range=(0, 100))
        pj_prism.connect_to(cj_prism)

        # 5. Ball/Spherical (BallJoint)
        child_ball = Box(2, 2, 2)
        room.add("child_ball", child_ball)
        with open(os.path.join(proj_dir, "child_ball.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_ball = RigidJoint("j_p_ball", parent, Location((75, 0, 0)))
        cj_ball = BallJoint("j_c_ball", child_ball, Location((0, 0, 0)))
        pj_ball.connect_to(cj_ball)

        # 6. Planar (using RigidJoint + urdf_joint_type override)
        child_planar = Box(2, 2, 2)
        room.add("child_planar", child_planar)
        with open(os.path.join(proj_dir, "child_planar.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_planar = RigidJoint("j_p_planar", parent, Location((90, 0, 0)))
        cj_planar = RigidJoint("j_c_planar", child_planar, Location((0, 0, 0)))
        cast(Any, cj_planar).urdf_joint_type = "planar"
        cast(Any, cj_planar).urdf_joint_axis = "0 1 1"
        pj_planar.connect_to(cj_planar)

        # 7. Floating (using RigidJoint + urdf_joint_type override)
        child_float = Box(2, 2, 2)
        room.add("child_float", child_float)
        with open(os.path.join(proj_dir, "child_float.obj"), "w") as f:
            f.write("# empty obj\n")
        pj_float = RigidJoint("j_p_float", parent, Location((105, 0, 0)))
        cj_float = RigidJoint("j_c_float", child_float, Location((0, 0, 0)))
        cast(Any, cj_float).urdf_joint_type = "floating"
        pj_float.connect_to(cj_float)

        urdf_path = os.path.join(temp_dir, "test.urdf")
        room.export_urdf(urdf_path, "test_robot")

        # Load in PyBullet
        physics_client = p.connect(p.DIRECT)
        try:
            body_id = p.loadURDF(urdf_path)
            assert body_id >= 0, "PyBullet failed to load the URDF file"

            num_joints = p.getNumJoints(body_id)
            assert num_joints == 7, f"Expected 7 joints, found {num_joints}"

            # Verify each joint type
            joints_info = {}
            for i in range(num_joints):
                info = p.getJointInfo(body_id, i)
                name = info[1].decode("utf-8")
                j_type = info[2]
                lower = info[8]
                upper = info[9]
                axis = info[13]
                joints_info[name] = {"type": j_type, "lower": lower, "upper": upper, "axis": axis}

            # 1. Fixed
            fixed_info = joints_info["parent_link_to_child_fixed"]
            assert fixed_info["type"] == p.JOINT_FIXED

            # 2. Revolute
            rev_info = joints_info["parent_link_to_child_rev"]
            assert rev_info["type"] == p.JOINT_REVOLUTE
            assert math.isclose(rev_info["lower"], 0.0, abs_tol=1e-5)
            assert math.isclose(rev_info["upper"], math.radians(180), abs_tol=1e-5)
            assert rev_info["axis"] == (0.0, 1.0, 0.0)

            # 3. Continuous
            cont_info = joints_info["parent_link_to_child_cont"]
            assert cont_info["type"] == p.JOINT_REVOLUTE
            # Continuous joints do not have upper/lower limits in PyBullet
            assert cont_info["lower"] == 0.0
            assert cont_info["upper"] == -1.0
            assert cont_info["axis"] == (0.0, 1.0, 0.0)

            # 4. Prismatic
            prism_info = joints_info["parent_link_to_child_prism"]
            assert prism_info["type"] == p.JOINT_PRISMATIC
            assert math.isclose(prism_info["lower"], 0.0, abs_tol=1e-5)
            assert math.isclose(prism_info["upper"], 0.1, abs_tol=1e-5)  # 100mm = 0.1m
            assert prism_info["axis"] == (0.0, 0.0, 1.0)

            # 5. Ball/Spherical
            ball_info = joints_info["parent_link_to_child_ball"]
            assert ball_info["type"] == p.JOINT_SPHERICAL

            # 6. Planar
            planar_info = joints_info["parent_link_to_child_planar"]
            assert planar_info["type"] == p.JOINT_PLANAR

            # 7. Floating (loaded as fixed by PyBullet internally but parsed without error)
            float_info = joints_info["parent_link_to_child_float"]
            assert float_info["type"] == p.JOINT_FIXED

        finally:
            p.disconnect(physicsClientId=physics_client)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
