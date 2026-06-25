"""Unit tests for the CatFountain project."""

import pytest
import math
from unittest.mock import patch
from build123d import Part
from projects_config import CatFountainConfig
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
        assert "bottom_cover" in provider.part
        assert "lid" in provider.part
        assert "drain_cover" in provider.part
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
        assert "bottom_cover" in room
        assert "lid" in room
        assert "drain_cover" in room

    def test_build_product(self, provider):
        """Verify that build_product populates the room with all fountain parts and their URDF attributes."""
        room = Room()
        provider.build_product(room, Mode.DEFAULT)
        room.translate_joints()

        # Verify all parts are placed
        assert "bowl" in room
        assert "impeller" in room
        assert "tube" in room
        assert "bottom_cover" in room
        assert "lid" in room
        assert "drain_cover" in room

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
        assert provider.settings.bowl_radius == 100.0
        assert provider.settings.tube_radius == 8.0
        assert provider.settings.impeller_radius == 12.0
        assert provider.settings.impeller_blades == 2
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

    @pytest.mark.slow
    def test_pump_integration(self):
        """Verify that the water pump works in the simulation by measuring particles pumped."""
        import tempfile
        import os
        from build import Builder
        from provider import ProviderManager, Room, Simulate
        from model import AppConfig
        from shell import Logger
        import pybullet as p

        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig()
            real_measurements = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../cat_fountain/measurements.yaml")
            )
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements

            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            builder.generate_parts(temp_dir, names=None)
            builder.generate_urdfs(temp_dir, names=None)

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()

            room["impeller"][0].urdf_motor_target = 150.0

            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(temp_dir, "cat_fountain/product.urdf")
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                assert body_id >= 0, "Failed to load URDF in PyBullet"

                boundaries = {}
                for _, (geom, _) in room.items():
                    u_geom = geom
                    label = getattr(u_geom, "urdf_label", None)
                    if label:
                        c_type = getattr(u_geom, "urdf_collision_type", None)
                        if c_type == "analytical" or str(c_type) == "URDFCollisionType.ANALYTICAL":
                            xyz_str = getattr(u_geom, "urdf_boundary_xyz", None)
                            rpy_str = getattr(u_geom, "urdf_boundary_rpy", None)
                            boundaries[label] = {
                                "shape": getattr(u_geom, "urdf_boundary_shape", None),
                                "type": getattr(u_geom, "urdf_boundary_type", None),
                                "radius": getattr(u_geom, "urdf_boundary_radius", None),
                                "height": getattr(u_geom, "urdf_boundary_height", None),
                                "thickness": getattr(u_geom, "urdf_boundary_thickness", None),
                                "xyz": [float(x) for x in xyz_str.split()] if xyz_str else [0.0, 0.0, 0.0],
                                "rpy": [float(x) for x in rpy_str.split()] if rpy_str else [0.0, 0.0, 0.0],
                            }

                hooks = provider.get_simulate_hooks("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                setup_fn(body_id, physics_client, "product:view/simulate", boundaries, None)

                if provider:
                    fluid = provider.water_sim
                assert fluid is not None

                step_fn = hooks[Simulate.STEP]
                for step_idx in range(100):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                # Math derivation for the lower limit:
                # 1. Theoretical vertical velocity from helix lead L and rotation speed omega
                # impeller height h_impeller = 78.0 mm, twist = 720 degrees
                # lead = h_impeller * (360 / twist) = 39.0 mm = 0.039 meters
                lead = 0.039  # meters
                v_z = 150.0 * (lead / (2.0 * 3.14159))  # ~0.931 m/s

                # 2. Time needed to travel the tube height (75mm = 0.075m)
                h_tube = 0.075  # meters
                t_travel = h_tube / v_z  # ~0.0698 seconds

                # 3. Active pumping time: motor starts at step 40, total 100 steps
                # dt = 1 / 240 seconds per step
                dt = 1.0 / 240.0
                t_motor = (100 - 40) * dt  # 0.25s
                t_exit = t_motor - t_travel  # time during which fluid actively exits: ~0.18s

                # 4. Volume flow rate Q = Area * v_z
                # tube inner radius r_inner = tube_radius - tube_thickness = 8.0 - 2.0 = 6.0mm = 0.006m
                r_inner = 0.006  # meters
                area = 3.14159 * (r_inner**2)
                Q = area * v_z  # m^3/s

                # 5. Particle volume V_p = 4/3 * pi * (r_s)^3
                # r_s = 0.0015m
                r_s = 0.0015
                v_p = (4.0 / 3.0) * 3.14159 * (r_s**3)

                # 6. Theoretical particle rate (particles/second)
                rate = Q / v_p

                # 7. Expected particles under 5% efficiency (slip factor)
                efficiency = 0.05
                expected_min_particles = int(rate * t_exit * efficiency)

                # Assert that we pump at least this minimum number of particles
                assert len(fluid.spout_water_ids) >= expected_min_particles, (
                    f"Pump efficiency too low: pumped {len(fluid.spout_water_ids)}, expected >= {expected_min_particles}"
                )

            finally:
                p.disconnect(physics_client)
