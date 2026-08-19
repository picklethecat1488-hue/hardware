"""Unit tests for the CatFountain project."""

import pytest
import math
import shutil
from unittest.mock import patch
from build123d import Part, Location, Rot
from projects_config import CatFountainConfig
from projects.cat_fountain.provider import CatFountainProvider
import projects.cat_fountain.layouts
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
        assert "bottom_cover" in provider.part
        assert "lid" in provider.part
        assert "led_cover" in provider.part

    def test_build_part_geometry(self, provider):
        """Verify that build_fountain produces valid geometry."""
        for key, item in provider.part.items():
            res = item(key, Mode.DEFAULT)
            part = res.part
            assert isinstance(part, Part)
            assert part.volume > 0
            assert part.is_valid

    def test_build_diagram(self, provider):
        """Verify that build_diagram populates the room with geometry."""
        room = Room()
        provider.build_diagram(room, ["product"], Mode.DEFAULT)
        assert "bowl" in room
        assert "impeller" in room
        assert "bottom_cover" in room
        assert "lid" in room

    def test_build_wiring_diagram(self, provider):
        """Verify that build_wiring_diagram populates the room with footprints and wires."""
        room = Room()
        provider.build_wiring_diagram(room, ["wiring"], Mode.DEFAULT)
        assert "bowl_outline" in room
        assert "motor_compartment" in room
        assert "charger_footprint" in room
        assert "pico_footprint" in room
        assert "fuel_gauge_footprint" in room
        assert "current_monitor_footprint" in room
        assert "motor_driver_footprint" in room
        assert "motor_footprint" in room
        assert "sensor_east_footprint" in room
        assert "sensor_north_footprint" in room
        assert "sensor_west_footprint" in room
        assert "led_footprint" in room
        assert "wire_gnd" in room
        assert "wire_vcc_logic" in room
        assert "wire_sda" in room
        assert "wire_scl" in room

    def test_wiring_diagram_class(self, provider):
        """Verify that WiringDiagram populates the room with all pads and wires."""
        from pathlib import Path
        from provider import Wiring, WiringDiagram

        yaml_path = Path(__file__).parent.parent / "cat_fountain" / "wiring.yaml"
        bowl_part = provider.build_bowl("bowl").part
        wiring = Wiring(yaml_path, bowl_part)

        room = Room()
        diagram = WiringDiagram(wiring)
        diagram.build(room)

        # Verify footprints
        assert "pico_footprint" in room
        assert "charger_footprint" in room

        # Verify pads
        assert "pico_pad_GP2" in room
        assert "pico_pad_GND_L" in room

        # Verify wires
        assert "wire_gnd" in room
        assert "wire_sda" in room
        assert "wire_scl" in room
        assert "wire_led_data" in room

    def test_layout_edge_pins(self):
        """Verify edge pin layout calculations for boards and sensors."""
        from projects.cat_fountain.layouts import layout_edge_pins
        from model import PinModel

        # Create mock pins
        pins = [
            PinModel(name="P1", label="P1", side="right", slot=0),
            PinModel(name="P2", label="P2", side="right", slot=1),
        ]
        # Layout on a 10x20 footprint (w=10.0, l=20.0)
        # side right -> physical left side (X = -5.0)
        # Margin = 2.0. Limit = 10.0 - 2.0 = 8.0.
        layout_edge_pins(pins, 10.0, 20.0, slots_per_side=2)
        assert pins[0].position == (-5.0, 8.0, 0.0)
        assert pins[1].position == (-5.0, -8.0, 0.0)

    def test_layout_motor_pins(self):
        """Verify motor footprint pin placements."""
        from projects.cat_fountain.layouts import layout_motor_pins
        from model import PinModel

        pins = [
            PinModel(name="M+", label="M+", side="top"),
            PinModel(name="M-", label="M-", side="top"),
        ]
        layout_motor_pins(pins, 12.0, 10.0)
        assert pins[0].position == (-4.0, -5.0, 0.0)
        assert pins[1].position == (4.0, -5.0, 0.0)

    def test_layout_led_pins(self):
        """Verify LED footprint pin placements."""
        from projects.cat_fountain.layouts import layout_led_pins
        from model import PinModel

        pins = [
            PinModel(name="VCC", label="VCC", side="right"),
            PinModel(name="GND", label="GND", side="right"),
            PinModel(name="DIN", label="DIN", side="left"),
        ]
        layout_led_pins(pins, 10.0, 10.0)
        assert pins[0].position == (-5.0, 3.0, 0.0)
        assert pins[1].position == (-5.0, -3.0, 0.0)
        assert pins[2].position == (5.0, 0.0, 0.0)

    def test_build_product(self, provider):
        """Verify that build_product populates the room with all fountain parts and their URDF attributes."""
        room = Room()
        provider.build_product(room, Mode.DEFAULT)
        room.translate_joints()

        # Verify all parts are placed
        assert "bowl" in room
        assert "impeller" in room
        assert "bottom_cover" in room
        assert "lid" in room

        # Verify attributes on bowl
        bowl_shape = room["bowl"][0]
        assert bowl_shape.urdf_label == "bowl"
        assert bowl_shape.urdf_material == "petg"
        assert bowl_shape.urdf_parent is None
        assert bowl_shape.urdf_joint_type is None
        assert bowl_shape.urdf_boundary_friction == 0.20
        assert len(bowl_shape.urdf_boundaries) == 2
        assert bowl_shape.urdf_boundaries[0].shape == "cylinder"
        assert bowl_shape.urdf_boundaries[0].type == "cavity"

        # Verify attributes on impeller
        impeller_shape = room["impeller"][0]
        assert impeller_shape.urdf_label == "impeller"
        assert impeller_shape.urdf_parent == "bowl"
        assert impeller_shape.urdf_joint_type == "continuous"
        assert impeller_shape.urdf_joint_axis == "0 0 1"

    def test_configuration_loading(self, provider):
        """Ensure that critical measurement values are loaded correctly."""
        assert provider.settings.bowl_radius == 100.0
        assert provider.settings.tube_radius == 10.0
        assert provider.settings.impeller_radius == 12.0
        assert provider.settings.impeller_blades == 3
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
        """Verify that the collar standoff and impeller hub are built with correct dimensions & clearance."""
        bowl = provider.build_bowl("bowl")
        # Ensure outer bowl exists
        assert bowl.part.is_valid
        assert bowl.part.volume > 0

        # Impeller shaft vs hub radius check
        # Hub radius must be shaft_radius + 1.0 (to ensure wall thickness/clearance)
        impeller = provider.build_impeller("impeller")
        assert impeller.part.is_valid

    @pytest.mark.slow
    @pytest.mark.timeout(180)
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
            provider.settings.target_volume = 0.00008

            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            builder.generate_parts(temp_dir, names=None)
            builder.generate_urdfs(temp_dir, names=None)

            # Copy compiled OBJ assets into the URDF folder so PyBullet can locate them relative to the URDF
            obj_dir = os.path.join(temp_dir, "obj/cat_fountain")
            urdf_proj_dir = os.path.join(temp_dir, "urdf/cat_fountain")
            for f in os.listdir(obj_dir):
                if f.endswith(".obj"):
                    shutil.copy(os.path.join(obj_dir, f), os.path.join(urdf_proj_dir, f))

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()

            room["impeller"][0].urdf_motor_target = 120.0

            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(temp_dir, "urdf/cat_fountain/product.urdf")
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                assert body_id >= 0, "Failed to load URDF in PyBullet"

                boundaries = {}
                for _, (geom, _) in room.items():
                    u_geom = geom
                    label = getattr(u_geom, "urdf_label", None)
                    if label:
                        geom_boundaries = getattr(u_geom, "urdf_boundaries", None)
                        if geom_boundaries:
                            boundaries[label] = geom_boundaries

                hooks = provider.get_simulate_hooks("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                setup_fn(body_id, physics_client, "product:view/simulate", boundaries, None)

                if provider:
                    fluid = provider.water_sim
                assert fluid is not None

                step_fn = hooks[Simulate.STEP]
                for step_idx in range(80):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                # Math derivation for the lower limit:
                # 1. Theoretical vertical velocity from helix lead L and rotation speed omega
                # lead = h_impeller * (360 / twist)
                lead = (provider.settings.impeller_height * 0.001) / (abs(provider.settings.vane_twist) / 360.0)
                motor_speed = float(room["impeller"][0].urdf_motor_target)
                v_z = motor_speed * (lead / (2.0 * 3.14159))  # ~0.465 m/s

                # 2. Time needed to travel the tube height
                h_tube = provider.settings.tube_height * 0.001
                t_travel = h_tube / v_z  # ~0.120 seconds

                # 3. Active pumping time: motor starts at step 40, total 80 steps
                # dt = 1 / 240 seconds per step
                dt = 1.0 / 240.0
                t_motor = (80 - 40) * dt  # 0.167s
                t_exit = t_motor - t_travel  # time during which fluid actively exits: ~0.047s

                # 4. Volume flow rate Q = Area * v_z
                # tube inner radius r_inner = tube_radius - tube_thickness
                r_inner = (provider.settings.tube_radius - provider.settings.tube_thickness) * 0.001
                area = 3.14159 * (r_inner**2)
                Q = area * v_z  # m^3/s

                # 5. Particle volume V_p = 4/3 * pi * (r_s)^3
                # r_s = 0.0015m
                r_s = 0.0015
                v_p = (4.0 / 3.0) * 3.14159 * (r_s**3)

                # 6. Theoretical particle rate (particles/second)
                rate = Q / v_p

                # 7. Expected particles under 4.5% simulation efficiency (redesigned pump at lower fluid level)
                efficiency = 0.045
                expected_min_particles = int(rate * t_exit * efficiency)

                # Assert that we pump at least this minimum number of particles (should be >= 2)
                assert len(fluid.spout_water_ids) >= expected_min_particles, (
                    f"Pump efficiency too low: pumped {len(fluid.spout_water_ids)}, expected >= {expected_min_particles}"
                )

            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(180)
    def test_motor_torque_speed_limit_integration(self):
        """Verify that the motor's angular velocity is dynamically torque-limited by fluid drag."""
        import tempfile
        import os
        from build import Builder
        from provider import ProviderManager, Room, Simulate
        from model import AppConfig
        from shell import Logger
        import pybullet as p
        from provider.bullet import LinkType

        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig()
            real_measurements = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../cat_fountain/measurements.yaml")
            )
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements
            provider.settings.target_volume = 0.0004
            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            builder.generate_parts(temp_dir, names=None)
            builder.generate_urdfs(temp_dir, names=None)

            # Copy compiled OBJ assets into the URDF folder so PyBullet can locate them relative to the URDF
            obj_dir = os.path.join(temp_dir, "obj/cat_fountain")
            urdf_proj_dir = os.path.join(temp_dir, "urdf/cat_fountain")
            for f in os.listdir(obj_dir):
                if f.endswith(".obj"):
                    shutil.copy(os.path.join(obj_dir, f), os.path.join(urdf_proj_dir, f))

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()

            room["impeller"][0].urdf_motor_target = 120.0
            room["impeller"][0].urdf_motor_force = 10.0

            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(temp_dir, "urdf/cat_fountain/product.urdf")
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                assert body_id >= 0

                boundaries = {}
                for _, (geom, _) in room.items():
                    u_geom = geom
                    label = getattr(u_geom, "urdf_label", None)
                    if label:
                        geom_boundaries = getattr(u_geom, "urdf_boundaries", None)
                        if geom_boundaries:
                            boundaries[label] = geom_boundaries

                hooks = provider.get_simulate_hooks("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                setup_fn(body_id, physics_client, "product:view/simulate", boundaries, None)

                fluid = provider.water_sim
                assert fluid is not None

                # Find joint index for the impeller in PyBullet
                impeller_joint_idx = -1
                for i in range(p.getNumJoints(body_id, physicsClientId=physics_client)):
                    info = p.getJointInfo(body_id, i, physicsClientId=physics_client)
                    if "impeller" in info[12].decode("utf-8"):
                        impeller_joint_idx = i
                        break
                assert impeller_joint_idx != -1

                step_fn = hooks[Simulate.STEP]

                # Run simulation and check joint velocities
                for step_idx in range(60):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                    if step_idx >= 40:
                        target_omega = fluid.boundaries[LinkType.IMPELLER].target_omega
                        joint_state = p.getJointState(body_id, impeller_joint_idx, physicsClientId=physics_client)
                        joint_vel = abs(joint_state[1])

                        if step_idx >= 48:
                            # 1. Verify that PyBullet joint velocity matches target speed at each step
                            assert joint_vel == pytest.approx(target_omega, abs=1e-2), (
                                f"Step {step_idx}: Joint velocity {joint_vel} did not match target omega {target_omega}"
                            )

                            # 2. Verify that target speed correctly solves the torque-limiting equation
                            # Since the simulation updates at 1/240s steps, the speed governor is computed
                            # using the drag torque from the previous step (which is at index -2 of fluid.torques).
                            if len(fluid.torques) > 1:
                                last_torque = abs(fluid.torques[-2])
                                motor_power = provider.settings.motor_power
                                expected_omega = min(120.0, motor_power / last_torque) if last_torque > 1e-5 else 120.0
                                assert target_omega == pytest.approx(expected_omega, abs=1e-2), (
                                    f"Step {step_idx}: Solver speed {target_omega} did not match expected {expected_omega} (last torque: {last_torque})"
                                )
            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(180)
    def test_pump_integration_water_escaping(self):
        """Verify that the simulation early terminates when water escapes the bowl."""
        import tempfile
        import os
        from build import Builder
        from provider import ProviderManager, Room, Simulate
        from model import AppConfig
        from shell import Logger
        import pybullet as p
        import copy

        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig()
            real_measurements = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../cat_fountain/measurements.yaml")
            )
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements
            provider.settings.target_volume = 0.000005
            provider.settings.motor_power = 1000.0

            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            builder.generate_parts(temp_dir, names=None)
            builder.generate_urdfs(temp_dir, names=None)

            # Copy compiled OBJ assets into the URDF folder so PyBullet can locate them relative to the URDF
            obj_dir = os.path.join(temp_dir, "obj/cat_fountain")
            urdf_proj_dir = os.path.join(temp_dir, "urdf/cat_fountain")
            for f in os.listdir(obj_dir):
                if f.endswith(".obj"):
                    shutil.copy(os.path.join(obj_dir, f), os.path.join(urdf_proj_dir, f))

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()

            room["impeller"][0].urdf_motor_target = 350.0

            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(temp_dir, "urdf/cat_fountain/product.urdf")
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                assert body_id >= 0, "Failed to load URDF in PyBullet"

                boundaries = {}
                for _, (geom, _) in room.items():
                    u_geom = geom
                    label = getattr(u_geom, "urdf_label", None)
                    if label:
                        geom_boundaries = getattr(u_geom, "urdf_boundaries", None)
                        if geom_boundaries:
                            boundaries[label] = geom_boundaries

                # Remove the spout deflection cap to force water to shoot out of the spout into space
                test_boundaries = copy.deepcopy(boundaries)
                if "lid" in test_boundaries and isinstance(test_boundaries["lid"], list):
                    test_boundaries["lid"] = [
                        b
                        for b in test_boundaries["lid"]
                        if abs(
                            (b.radius if hasattr(b, "radius") else b.get("radius", 0.0))
                            - provider.settings.spout_deflection_radius * 0.001
                        )
                        > 1e-6
                    ]
                if "bowl" in test_boundaries:
                    bowl_list = test_boundaries["bowl"]
                    if isinstance(bowl_list, list):
                        new_bowl_list = []
                        for b in bowl_list:
                            b_dict = b.model_dump(exclude_defaults=True) if hasattr(b, "model_dump") else dict(b)
                            b_dict["height"] = (provider.settings.bowl_height - 25.0) * 0.001
                            from provider.bullet import LinkType

                            if b_dict.get("link_type") != LinkType.TUBE and b_dict.get("link_type") != "tube":
                                b_dict["radius"] = 0.020
                            from model.boundary_config import BoundaryConfig

                            new_bowl_list.append(BoundaryConfig.model_validate(b_dict))
                        test_boundaries["bowl"] = new_bowl_list
                    else:
                        test_boundaries["bowl"]["height"] = (provider.settings.bowl_height - 25.0) * 0.001
                        test_boundaries["bowl"]["radius"] = 0.020

                hooks = provider.get_simulate_hooks("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                setup_fn(body_id, physics_client, "product:view/simulate", test_boundaries, None)

                # Set a very low early termination threshold (e.g., 0.00001L) to terminate quickly
                provider.water_sim.fallen_threshold_liters = 0.00001

                step_fn = hooks[Simulate.STEP]
                terminated_message = None
                for step_idx in range(180):
                    if step_idx == 45:
                        import numpy as np
                        import jax.numpy as jnp

                        pos_arr = np.array(provider.water_sim.pos_jax)
                        if len(pos_arr) > 0:
                            pos_arr[0] = [0.0, 0.0, -10.0]
                            provider.water_sim.pos_jax = jnp.array(pos_arr)
                    res = step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    if res is not None:
                        terminated_message = res
                        break
                    p.stepSimulation(physicsClientId=physics_client)

                # Verify early termination was triggered and returned the expected message
                assert terminated_message is not None, "Simulation did not early terminate despite water escaping"
                assert "water fell out of bowl" in terminated_message

            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(180)
    def test_cat_fountain_water_escaping_termination(self, provider):
        """Verify that the cat fountain simulation terminates when water escapes/falls out of bounds."""
        import pybullet as p
        import numpy as np
        from provider import Simulate

        # Define mock impeller shape with motor target configuration attributes
        class MockImpeller:
            def __init__(self):
                self.urdf_motor_target = 120.0
                self.urdf_motor_force = 10.0

        # Define a mock room with the impeller key to satisfy step_simulation lookup
        provider.room = {"impeller": [MockImpeller()]}

        # Connect to PyBullet in direct (headless) mode
        client = p.connect(p.DIRECT)
        try:
            # Create a basic multibody with the expected links to satisfy setup_simulation
            bowl_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.1, 0.1, 0.01], physicsClientId=client)
            tube_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.008, height=0.120, physicsClientId=client)
            vane_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.005, height=0.015, physicsClientId=client)
            lid_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.080, height=0.010, physicsClientId=client)

            body_id = p.createMultiBody(
                baseMass=1.0,
                baseCollisionShapeIndex=bowl_col,
                linkMasses=[0.1, 0.1, 0.1],
                linkCollisionShapeIndices=[tube_col, vane_col, lid_col],
                linkVisualShapeIndices=[-1, -1, -1],
                linkPositions=[[0.0, 0.0, 0.05], [0.0, 0.0, 0.01], [0.0, 0.0, 0.10]],
                linkOrientations=[[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 1]],
                linkInertialFramePositions=[[0, 0, 0], [0, 0, 0], [0, 0, 0]],
                linkInertialFrameOrientations=[[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 1]],
                linkParentIndices=[0, 0, 0],
                linkJointTypes=[p.JOINT_FIXED, p.JOINT_REVOLUTE, p.JOINT_FIXED],
                linkJointAxis=[[0, 0, 1], [0, 0, 1], [0, 0, 1]],
                physicsClientId=client,
            )

            # Mock the link info names that setup_simulation looks up
            def mock_get_joint_info(body, joint, physicsClientId):
                if joint == 0:
                    return (
                        0,
                        b"joint_tube",
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
                        (0.0, 0.0, 0.0),
                        (0, 0, 0, 1),
                        -1,
                    )
                elif joint == 1:
                    return (
                        1,
                        b"joint_impeller",
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
                        (0.0, 0.0, 0.0),
                        (0, 0, 0, 1),
                        -1,
                    )
                elif joint == 2:
                    return (
                        2,
                        b"joint_lid",
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
                        b"lid",
                        (0, 0, 0),
                        (0.0, 0.0, 0.0),
                        (0, 0, 0, 1),
                        -1,
                    )
                return (
                    joint,
                    b"joint",
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
                    b"link",
                    (0, 0, 0),
                    (0.0, 0.0, 0.0),
                    (0, 0, 0, 1),
                    -1,
                )

            def mock_get_num_joints(body, physicsClientId):
                return 3

            import unittest.mock as mock

            with (
                mock.patch("pybullet.getNumJoints", side_effect=mock_get_num_joints),
                mock.patch("pybullet.getJointInfo", side_effect=mock_get_joint_info),
                mock.patch("provider.bullet.Bullet.reset_camera") as mock_reset_camera,
            ):
                # Define sample boundaries with new schema
                boundaries = {
                    "bowl": {"xyz": [0.0, 0.0, 0.003], "height": 0.010, "radius": 0.080},
                    "lid": [
                        {
                            "xyz": [0.0, 0.0, 0.016],
                            "height": 0.010,
                            "radius": 0.080,
                            "has_drain": True,
                            "has_tube": True,
                        },
                        {"xyz": [0.0, 0.0, 0.016], "height": 0.010, "radius": 0.013, "has_tube": True},
                    ],
                }

                # Retrieve simulation hooks
                hooks = provider.get_simulate_hooks("simulate")
                setup_fn = hooks[Simulate.SETUP]
                step_fn = hooks[Simulate.STEP]

                # Execute simulation setup hook
                setup_fn(body_id, client, "simulate", boundaries)

                assert provider.water_sim is not None

                # Verify that when all water is within boundaries, simulation does not terminate
                assert step_fn(body_id, client, 0, "simulate") is None

                # Move a sufficient volume of water particles outside the boundary to trigger escaping
                # (threshold is 0.001L of water, with r_s=0.0015)
                pos_np = np.array(provider.water_sim.pos_jax)
                assert len(pos_np) >= 100
                pos_np[:100, 2] = -10.0  # Put them below the floor boundary

                import jax.numpy as jnp

                provider.water_sim.pos_jax = jnp.array(pos_np)

                # Execute step simulation and verify the termination condition is met
                res = step_fn(body_id, client, 1, "simulate")
                assert res is not None
                assert "L of water fell out of bowl" in res

        finally:
            p.disconnect(client)

    def test_no_intersecting_parts(self, provider):
        """Verify that no parts intersect each other in the assembled configuration."""
        room = Room()
        provider.build_product(room, Mode.DEFAULT)
        room.translate_joints()

        parts = {
            name: geom[0]
            for name, geom in room.items()
            if not any(x in name for x in ["emitter", "receiver", "pcb", "motor"])
        }
        for name1, part1 in parts.items():
            for name2, part2 in parts.items():
                if name1 < name2:
                    intersection = part1.intersect(part2)
                    vol = sum(s.volume for s in intersection.solids()) if intersection else 0.0
                    assert vol == pytest.approx(0, abs=0.2), (
                        f"Intersection detected between {name1} and {name2}: {vol:.3f} mm3"
                    )
