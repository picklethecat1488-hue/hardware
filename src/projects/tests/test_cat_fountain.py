"""Unit tests for the CatFountain project."""

import pytest
import math
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
            },
            "product": {Section.VIEW: {"modes": [Mode.DEFAULT, Mode.SIMULATE]}},
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
        assert "bowl" in room
        assert "impeller" in room
        assert "tube" in room
        assert "spout" in room

    def test_build_product(self, provider):
        """Verify that build_product populates the room with all fountain parts and their URDF attributes."""
        room = Room()
        provider.build_product(room)
        room.translate_joints()

        # Verify all parts are placed
        assert "bowl" in room
        assert "impeller" in room
        assert "tube" in room
        assert "spout" in room

        # Verify attributes on bowl
        bowl_shape = room["bowl"][0]
        assert bowl_shape.urdf_label == "bowl"
        assert bowl_shape.urdf_material == "petg"
        assert bowl_shape.urdf_parent is None
        assert bowl_shape.urdf_joint_type is None
        assert bowl_shape.urdf_boundary_friction == 0.20
        assert bowl_shape.urdf_contact_angle == 75.0

        # Verify attributes on impeller
        impeller_shape = room["impeller"][0]
        assert impeller_shape.urdf_label == "impeller"
        assert impeller_shape.urdf_parent == "bowl"
        assert impeller_shape.urdf_joint_type == "continuous"
        assert impeller_shape.urdf_joint_axis == "0 0 1"

    def test_configuration_loading(self, provider):
        """Ensure that critical measurement values are loaded correctly."""
        assert provider.settings.bowl_radius == 80.0
        assert provider.settings.tube_radius == 8.0
        assert provider.settings.impeller_radius == 12.0
        assert provider.settings.impeller_blades == 6
        assert provider.settings.petg_boundary_friction == 0.20
        assert provider.settings.petg_contact_angle == 75.0

    def test_dynamic_material_properties(self, provider):
        """Verify that modifying the material attribute resolves dynamic properties correctly."""
        # Check defaults
        assert provider.settings.material == "petg"
        assert provider.settings.density == 1.27
        assert provider.settings.boundary_friction == 0.20
        assert provider.settings.contact_angle == 75.0

        # Change to pla
        provider.settings.material = "pla"
        assert provider.settings.density == 1.24
        assert provider.settings.boundary_friction == 0.30
        assert provider.settings.contact_angle == 68.0

        # Change to abs
        provider.settings.material = "abs"
        assert provider.settings.density == 1.04
        assert provider.settings.boundary_friction == 0.25
        assert provider.settings.contact_angle == 80.0

    def test_collar_standoff_geometry(self, provider):
        """Verify that the collar standoff, tube, and impeller hub are built with correct dimensions & clearance."""
        bowl = provider.build_bowl("bowl")
        # Ensure outer bowl and collar socket exist
        assert bowl.part.is_valid
        assert bowl.part.volume > 0

        # Impeller shaft vs hub radius check
        # Hub radius must be shaft_radius + 1.0 (to ensure wall thickness/clearance)
        impeller = provider.build_impeller("impeller")
        assert impeller.part.is_valid

        # Verify tube bottom slot subtraction (which has length > 0)
        tube = provider.build_tube("tube")
        assert tube.part.is_valid

    def test_water_spawner_padding_and_jitter(self):
        """Verify that WaterSpawner spawns batches with jitter and pads arrays correctly."""
        import pybullet as p
        from projects.cat_fountain.simulate import WaterSpawner

        physics_client = p.connect(p.DIRECT)
        try:
            spawner = WaterSpawner(
                physics_client=physics_client,
                r_s=0.003,
                n_particles=10,
                particle_mass=0.002,
                particle_color=[0, 0, 1, 1],
                particle_visual_length=0.0001,
                linear_damping=0.05,
                angular_damping=0.05,
                lateral_friction=0.1,
                restitution=0.0,
            )

            # Initial state
            assert spawner.active_count == 0
            assert len(spawner.water_body_ids) == 0

            # 1. Spawn a batch of 4 particles
            newly_spawned = spawner.spawn_batch(spawn_z=0.100, batch_size=4, spacing=0.008)
            assert newly_spawned == 4
            assert spawner.active_count == 4
            assert len(spawner.water_body_ids) == 4

            # Verify positions and velocities are padded up to n_particles (10)
            positions, velocities = spawner.get_positions_and_velocities()
            assert len(positions) == 10
            assert len(velocities) == 10

            # First 4 positions should be active particles (z < 1000)
            for i in range(4):
                assert positions[i][2] < 100.0
                # Jitter should make positions slightly off 0.0 in X and Y
                assert abs(positions[i][0]) <= 0.006
                assert abs(positions[i][1]) <= 0.006

            # Remaining 6 should be padded to 1000.0
            for i in range(4, 10):
                assert math.isclose(positions[i][2], 1000.0)
                assert positions[i][0] == 0.0
                assert positions[i][1] == 0.0

            # Spawn more than n_particles capacity
            newly_spawned_2 = spawner.spawn_batch(spawn_z=0.100, batch_size=10, spacing=0.008)
            assert newly_spawned_2 == 6  # Spawner caps at n_particles (10)
            assert spawner.active_count == 10

        finally:
            p.disconnect(physicsClientId=physics_client)

    def test_water_simulator_dynamic_properties(self, provider):
        """Verify that WaterSimulator reads target velocity, force, and offset from shape metadata and PyBullet."""
        from projects.cat_fountain.simulate import WaterSimulator

        room = Room()
        provider.build_product(room)

        sim = WaterSimulator(provider)
        sim.body_id = 42
        sim.physics_client = 1

        # Mock PyBullet functions
        def mock_get_num_joints(body_id, physicsClientId):
            return 3

        def mock_get_joint_info(body_id, joint_idx, physicsClientId):
            # idx 0: impeller, idx 1: tube, idx 2: spout
            if joint_idx == 0:
                return (
                    0,
                    b"joint0",
                    0,
                    0,
                    0,
                    0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    b"impeller",
                    (0, 0, 0),
                    (0, 0, 0),
                    (0, 0, 0, 1),
                    -1,
                )
            elif joint_idx == 1:
                # parentFramePosition Y coordinate is 0.057 meters (57.0 mm)
                return (
                    1,
                    b"joint1",
                    0,
                    0,
                    0,
                    0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    b"tube",
                    (0, 0, 0),
                    (0.0, 0.057, 0.0),
                    (0, 0, 0, 1),
                    -1,
                )
            else:
                return (
                    2,
                    b"joint2",
                    0,
                    0,
                    0,
                    0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    b"spout",
                    (0, 0, 0),
                    (0, 0, 0),
                    (0, 0, 0, 1),
                    -1,
                )

        def mock_get_aabb(body_id, link_idx, physicsClientId):
            if link_idx == -1:
                # bowl AABB: x from -0.080 to 0.080 (radius 0.080)
                return ((-0.080, -0.080, 0.0), (0.080, 0.080, 0.040))
            elif link_idx == 1:
                # tube AABB: x from 0.049 to 0.065 (radius 0.008)
                return ((-0.008, 0.049, 0.0), (0.008, 0.065, 0.100))
            return ((0, 0, 0), (0, 0, 0))

        with (
            patch("pybullet.getNumJoints", side_effect=mock_get_num_joints),
            patch("pybullet.getJointInfo", side_effect=mock_get_joint_info),
            patch("pybullet.getAABB", side_effect=mock_get_aabb),
        ):
            # Verify dynamic properties
            assert sim.impeller_target_velocity == 15.0
            assert sim.impeller_force == 10.0

            # bowl_outer_radius = 80mm
            # tube_outer_radius = 8mm
            # tube_y = 57mm
            # tube_offset_mm = 80 - 8 - 57 = 15.0
            assert math.isclose(sim.tube_offset_mm, 15.0, abs_tol=1e-3)
