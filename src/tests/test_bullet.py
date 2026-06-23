"""Unit tests for PyBullet simulation engine lifecycle manager (bullet.py)."""

from unittest.mock import MagicMock, patch
import pybullet as p
import pytest
from provider.bullet import Bullet, BulletStateTracker, _is_real_physics_client


def test_is_real_physics_client_invalid():
    """Verify that _is_real_physics_client returns False for invalid client IDs."""
    assert not _is_real_physics_client(None)
    assert not _is_real_physics_client("string_id")
    assert not _is_real_physics_client(-1)
    assert not _is_real_physics_client(999)  # Non-existent client ID


def test_is_real_physics_client_valid():
    """Verify that _is_real_physics_client returns True for a valid connected client."""
    client_id = p.connect(p.DIRECT)
    try:
        assert _is_real_physics_client(client_id)
    finally:
        p.disconnect(physicsClientId=client_id)


def test_bullet_state_tracker_basic():
    """Verify BulletStateTracker updates positions and transforms for base and joints."""
    client_id = p.connect(p.DIRECT)
    try:
        # Create a simple multi-body: box base (bowl) and one joint
        bowl_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.1, 0.1, 0.01], physicsClientId=client_id)
        tube_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.008, height=0.120, physicsClientId=client_id)
        body_id = p.createMultiBody(
            baseMass=1.0,
            baseCollisionShapeIndex=bowl_col,
            basePosition=[0.0, 0.0, 0.0],
            baseOrientation=[0.0, 0.0, 0.0, 1.0],
            linkMasses=[0.1],
            linkCollisionShapeIndices=[tube_col],
            linkVisualShapeIndices=[-1],
            linkPositions=[[0.0, 0.0, 0.1]],
            linkOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkInertialFramePositions=[[0.0, 0.0, 0.0]],
            linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkParentIndices=[0],
            linkJointTypes=[p.JOINT_FIXED],
            linkJointAxis=[[0.0, 0.0, 1.0]],
            physicsClientId=client_id,
        )

        label_to_link_idx = {"base_link": -1, "tube_link": 0}
        tracker = BulletStateTracker(body_id, client_id, label_to_link_idx)
        assert tracker.body_id == body_id
        assert tracker.physics_client == client_id

        # Update and verify transforms
        tracker.update_state()
        assert "base_link" in tracker.transforms
        assert "tube_link" in tracker.transforms

        # Base transform (pos, orn)
        base_pos, base_orn = tracker.transforms["base_link"]
        assert len(base_pos) == 3
        assert len(base_orn) == 4

        # Link transform
        link_pos, link_orn = tracker.transforms["tube_link"]
        assert len(link_pos) == 3
        assert len(link_orn) == 4

    finally:
        p.disconnect(physicsClientId=client_id)


def test_bullet_state_tracker_discover_particles():
    """Verify that BulletStateTracker correctly discovers dynamic particles."""
    client_id = p.connect(p.DIRECT)
    try:
        # Base body
        bowl_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.1, 0.1, 0.01], physicsClientId=client_id)
        body_id = p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=bowl_col,
            physicsClientId=client_id,
        )

        tracker = BulletStateTracker(body_id, client_id, {})
        tracker.update_state()
        assert len(tracker.particle_body_ids) == 0

        # Create a dynamic particle body with mass > 0.0
        part_col = p.createCollisionShape(p.GEOM_SPHERE, radius=0.003, physicsClientId=client_id)
        part_vis = p.createVisualShape(
            p.GEOM_SPHERE, radius=0.003, rgbaColor=[0.1, 0.2, 0.3, 0.4], physicsClientId=client_id
        )
        part_id = p.createMultiBody(
            baseMass=0.001,
            baseCollisionShapeIndex=part_col,
            baseVisualShapeIndex=part_vis,
            basePosition=[0.05, 0.05, 0.1],
            physicsClientId=client_id,
        )

        tracker.update_state()
        assert len(tracker.particle_body_ids) == 1
        assert tracker.particle_body_ids[0] == part_id
        assert tracker.particle_radii[0] == pytest.approx(0.003)
        assert tracker.particle_colors[0] == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert tracker.particle_positions[0] == pytest.approx([0.05, 0.05, 0.1])

    finally:
        p.disconnect(physicsClientId=client_id)


def test_bullet_reset_camera():
    """Verify Bullet.reset_camera handles camera calculations and calls pybullet."""

    # Mock room and compound with bounding box
    class MockPt:
        def __init__(self, x, y, z):
            self.X, self.Y, self.Z = x, y, z

    class MockBoundingBox:
        def __init__(self):
            self.min = MockPt(-50, -60, -10)
            self.max = MockPt(50, 40, 90)

        def center(self):
            return MockPt(0, -10, 40)

    class MockCompound:
        def bounding_box(self):
            return MockBoundingBox()

    class MockRoom:
        def __init__(self):
            self.compound = MockCompound()

    room = MockRoom()
    # Instantiate Bullet
    bullet = Bullet(
        room=room,
        provider_hooks={},
        proj_name="test_proj",
        sim_target="target",
        steps=10,
        manager=MagicMock(),
        logger=MagicMock(),
        spawn_viewer=False,
    )

    with patch("pybullet.resetDebugVisualizerCamera") as mock_reset:
        bullet.reset_camera(physics_client=1, view_from="iso")
        mock_reset.assert_called_once()
        _, kwargs = mock_reset.call_args
        # cameraDistance should be max_dim * 2.0 = 100 * 2.0 * 0.001 = 0.2, but clamped at min 0.3
        assert kwargs["cameraDistance"] == pytest.approx(0.3)
        assert kwargs["cameraYaw"] == pytest.approx(45.0)
        assert kwargs["cameraPitch"] == pytest.approx(-30.0)
        assert kwargs["cameraTargetPosition"] == pytest.approx([0.0, -0.01, 0.04])

        # Test view_from split-mix
        mock_reset.reset_mock()
        bullet.reset_camera(physics_client=1, view_from="top,front")
        assert mock_reset.call_args[1]["cameraYaw"] == pytest.approx(0.0)
        assert mock_reset.call_args[1]["cameraPitch"] == pytest.approx(-44.5)


def test_bullet_init_simulation_objects():
    """Verify Bullet._init_simulation_objects configures joints and properties correctly."""
    client_id = p.connect(p.DIRECT)
    try:

        class MockGeom:
            def __init__(self, label, parent=None, motor_type=None, target=None, force=None):
                self.urdf_label = label
                self.urdf_parent = parent
                self.urdf_motor_type = motor_type
                self.urdf_motor_target = target
                self.urdf_motor_force = force

        # Mock room elements
        room_dict = {
            "bowl": (MockGeom("bowl"), None),
            "impeller": (MockGeom("impeller", parent="bowl", motor_type="velocity", target=5.0, force=10.0), None),
        }

        class MockRoom(dict):
            def __init__(self, items):
                super().__init__(items)

        room = MockRoom(room_dict)
        bullet = Bullet(
            room=room,
            provider_hooks={},
            proj_name="test_proj",
            sim_target="target",
            steps=10,
            manager=MagicMock(),
            logger=MagicMock(),
            spawn_viewer=False,
        )

        bowl_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.1, 0.1, 0.01], physicsClientId=client_id)
        vane_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.005, height=0.015, physicsClientId=client_id)
        body_id = p.createMultiBody(
            baseMass=1.0,
            baseCollisionShapeIndex=bowl_col,
            linkMasses=[0.1],
            linkCollisionShapeIndices=[vane_col],
            linkVisualShapeIndices=[-1],
            linkPositions=[[0.0, 0.0, 0.0]],
            linkOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkInertialFramePositions=[[0.0, 0.0, 0.0]],
            linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkParentIndices=[0],
            linkJointTypes=[p.JOINT_REVOLUTE],
            linkJointAxis=[[0.0, 0.0, 1.0]],
            physicsClientId=client_id,
        )

        with (
            patch("pybullet.getJointInfo") as mock_get_joint_info,
            patch("pybullet.setJointMotorControl2") as mock_set_motor,
            patch("rerun.log"),
        ):
            mock_get_joint_info.return_value = (0, b"bowl_to_impeller")

            label_to_link_idx = bullet._init_simulation_objects(client_id, body_id, "/tmp", None)

            assert label_to_link_idx["bowl"] == -1
            assert label_to_link_idx["impeller"] == 0

            mock_set_motor.assert_called_with(
                bodyUniqueId=body_id,
                jointIndex=0,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=5.0,
                force=10.0,
                physicsClientId=client_id,
            )

    finally:
        p.disconnect(physicsClientId=client_id)
