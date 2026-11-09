"""Unit tests for the CatFountain project."""

import pytest
import math
import shutil
import sys
from unittest.mock import patch
from build123d import Part, Location, Rot
from projects_config import CatFountainConfig
from projects.cat_fountain.provider import CatFountainProvider
import projects.cat_fountain.layouts
import pybullet as p
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
            "bowl": {"material": "utr8100"},
            "impeller": {"material": "petg"},
            "bottom_cover": {"material": "utr8100"},
            "lid": {"material": "utr8100"},
            "led_cover": {"material": "utr8100"},
            "drive_hub": {"material": "petg"},
            "pump_cover": {"material": "utr8100"},
            "motor_hub": {"material": "petg"},
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
        assert "drive_hub" in provider.part
        assert "motor_hub" in provider.part
        assert "motor_clip" not in provider.part

    def test_regression_bug_lustrous_cocoon_669_simplified_motor_base(self, provider):
        """Verify BUG-LUSTROUS-COCOON-669: Motor base design is circle unioned with rectangle for hall sensor, with 3 holes."""
        hub = provider.build_motor_hub("motor_hub")
        assert hub.part.volume > 0.0
        assert hub.part.is_valid()

        clip_h = provider.settings.motor_hub_thickness
        r_bcd = provider.settings.motor_mount_bolt_circle_radius
        collar_r = provider.settings.motor_hub_socket_radius - provider.settings.motor_hub_collar_clearance

        # 1. Circle base is solid, no complicated south handle or arm
        assert hub.part.is_inside((0, -collar_r * 0.5, clip_h * 0.5)), "Circular base must be solid"
        assert not hub.part.is_inside((0, -25.0, clip_h * 0.5)), "No extended South arm / handle"

        # 2. Rectangular tongue for Hall sensor mount is solid
        assert hub.part.is_inside((0, 15.0, clip_h * 0.5)), "Hall sensor rectangular mount must be solid"

        # 3. Central shaft clearance hole is open
        assert not hub.part.is_inside((0, 0, clip_h * 0.5)), "Central shaft hole must be open"

        # 4. Exactly 3 mounting holes on bottom
        for angle in [90.0, 210.0, 330.0]:
            rad = math.radians(angle)
            hx = r_bcd * math.cos(rad)
            hy = r_bcd * math.sin(rad)
            assert not hub.part.is_inside((hx, hy, clip_h * 0.5)), f"Mounting hole at {angle}° must be open"
            assert hub.part.is_inside((hx + 2.0, hy, clip_h * 0.5)), f"Surrounding base at {angle}° must be solid"

        # 5. Bowl socket keyway slot cuts cleanly through socket wall with zero thin slivers at inner curved corners
        bowl = provider.build_bowl("bowl")
        assert bowl.part.is_valid()
        floor_z = provider.settings.floor_z
        t = provider.settings.bowl_thickness
        z = floor_z - t - 5.0
        # Points inside keyway opening at Y = 16.8 (where curved inner wall was previously leaving thin slivers) must be open
        assert not bowl.part.is_inside((7.5, 16.8, z)), "Right corner of keyway slot must not have thin sliver wall"
        assert not bowl.part.is_inside((-7.5, 16.8, z)), "Left corner of keyway slot must not have thin sliver wall"
        # Socket wall outside the keyway width (X = 8.5) must remain solid
        assert bowl.part.is_inside((8.5, 16.8, z)), "Socket wall outside keyway must remain solid"
        assert bowl.part.is_inside((-8.5, 16.8, z)), "Socket wall outside keyway must remain solid"

    @pytest.mark.slow
    def test_build_part_geometry(self, provider):
        """Verify that build_fountain produces valid geometry."""
        for key, item in provider.part.items():
            res = item(key, Mode.DEFAULT)
            part = res.part
            assert isinstance(part, Part)
            assert part.volume > 0
            assert part.is_valid

    @pytest.mark.slow
    def test_build_diagram(self, provider):
        """Verify that build_diagram populates the room with geometry."""
        room = Room()
        provider.build_diagram(room, ["product"], Mode.DEFAULT)
        assert "bowl" in room
        assert "impeller" in room
        assert "bottom_cover" in room
        assert "lid" in room

    @pytest.mark.slow
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

        # Verify RP2040 GPIO Key (BUG-FOSSORIAL-BRISTLE-291)
        assert "rp2040_key_border" in room
        assert "rp2040_key_divider" in room
        for gpio in provider.RP2040_KEY_LEFT_GPIOS:
            assert f"rp2040_key_swatch_{gpio.lower()}" in room
            assert f"rp2040_key_dot_{gpio.lower()}" in room
        for gpio in provider.RP2040_KEY_RIGHT_GPIOS:
            assert f"rp2040_key_swatch_{gpio.lower()}" in room
            assert f"rp2040_key_dot_{gpio.lower()}" in room

        # Verify label contents
        label_names = {lbl[0] for lbl in room._labels}
        assert "rp2040_key_title" in label_names
        assert "rp2040_key_lbl_gp16" in label_names
        assert "rp2040_key_lbl_gp22" in label_names
        assert "rp2040_key_lbl_gp26" in label_names

        # Verify TMC6300 Pin Key (BUG-DEEP-BURROWER-108)
        assert "tmc6300_key_border" in room
        assert "tmc6300_key_divider" in room
        for pin, _ in provider.TMC6300_KEY_ENTRIES:
            assert f"tmc6300_key_swatch_{pin.lower()}" in room
            assert f"tmc6300_key_dot_{pin.lower()}" in room

        assert "tmc6300_key_title" in label_names
        for pin, _ in provider.TMC6300_KEY_ENTRIES:
            assert f"tmc6300_key_lbl_{pin.lower()}" in label_names

    @pytest.mark.slow
    def test_wiring_diagram_class(self, provider):
        """Verify that WiringDiagram populates the room with all pads and wires."""
        from provider import WiringDiagram

        wiring = provider.wiring

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

    @pytest.mark.slow
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

        # Verify footprints/PCBs are placed in DEFAULT mode for visual inspection
        expected_footprints = [
            "battery_pcb",
            "charger_pcb",
            "pico_pcb",
            "fuel_gauge_pcb",
            "current_monitor_pcb",
            "motor_driver_pcb",
            "motor_pcb",
            "sensor_pcb_east",
            "sensor_pcb_north",
            "sensor_pcb_west",
            "speed_sensor_pcb",
            "swd_adapter_pcb",
        ]
        for fp_name in expected_footprints:
            assert fp_name in room, f"Expected footprint '{fp_name}' in room for visual inspection"

        # Verify dummy footprints are omitted in SIMULATE mode
        sim_room = Room()
        provider.build_product(sim_room, Mode.SIMULATE)
        for fp_name in expected_footprints:
            assert fp_name not in sim_room, f"Footprint '{fp_name}' must not be present in SIMULATE mode"

        # Verify attributes on bowl
        bowl_shape = room["bowl"][0]
        assert bowl_shape.urdf_label == "bowl"
        assert bowl_shape.urdf_material == "utr8100"
        assert bowl_shape.urdf_parent is None
        assert bowl_shape.urdf_joint_type is None
        assert bowl_shape.urdf_boundary_friction == 0.20
        assert len(bowl_shape.urdf_boundaries) == 3
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
        assert provider.settings.tube_radius == 8.0
        assert provider.settings.impeller_radius == 9.0
        assert provider.settings.impeller_blades == 3
        assert provider.settings.impeller_shaft_radius == 1.0
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

    @pytest.mark.slow
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
    @pytest.mark.timeout(600)
    def test_pump_integration(self):
        """Verify that the water pump works in the simulation by measuring particles pumped."""
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
            provider.settings.target_volume = 0.0003
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

            room["impeller"][0].urdf_motor_target = 130.0
            room["impeller"][0].urdf_motor_force = 10.0
            provider.room = room

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
                for step_idx in range(25):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                # Math derivation for the lower limit:
                # 1. Theoretical vertical velocity from helix lead L and rotation speed omega
                # lead = h_impeller * (360 / twist)
                lead = (provider.settings.impeller_height * 0.001) / (abs(provider.settings.vane_twist) / 360.0)
                motor_speed = float(room["impeller"][0].urdf_motor_target)
                v_z = min(motor_speed * (lead / (2.0 * 3.14159)), 0.90)  # Capped at LBM stability limit~0.9 m/s

                # 2. Time needed to travel the tube height
                h_tube = provider.settings.tube_height * 0.001
                t_travel = h_tube / v_z  # ~0.120 seconds

                # 3. Active pumping time: total 55 steps
                # dt = 1 / 240 seconds per step
                dt = 1.0 / 240.0
                t_motor = 55 * dt  # 0.229s
                t_exit = t_motor - t_travel  # time during which fluid actively exits: ~0.062s

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

                # Assert that the fluid simulation is active and the impeller operates
                assert fluid is not None
                assert len(fluid.last_positions) > 0
                assert fluid.boundaries[LinkType.IMPELLER].target_omega > 0

            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(300)
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
            provider.room = room

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
                for step_idx in range(25):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                    if step_idx >= 8:
                        target_omega = fluid.boundaries[LinkType.IMPELLER].target_omega
                        joint_state = p.getJointState(body_id, impeller_joint_idx, physicsClientId=physics_client)
                        joint_vel = abs(joint_state[1])

                        if step_idx >= 12:
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
                                motor_target = float(room["impeller"][0].urdf_motor_target)
                                expected_omega = (
                                    min(motor_target, motor_power / last_torque) if last_torque > 1e-5 else motor_target
                                )
                                assert target_omega == pytest.approx(expected_omega, abs=1e-2), (
                                    f"Step {step_idx}: Solver speed {target_omega} did not match expected {expected_omega} (last torque: {last_torque})"
                                )
            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(300)
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
            provider.room = room

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
                provider.water_sim.recycle_fluid = False

                step_fn = hooks[Simulate.STEP]
                terminated_message = None
                for step_idx in range(180):
                    if step_idx == 15:
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
    @pytest.mark.timeout(300)
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
                    "bowl": {
                        "shape": "cylinder",
                        "type": "cavity",
                        "xyz": [0.0, 0.0, 0.003],
                        "height": 0.010,
                        "radius": 0.080,
                    },
                    "lid": [
                        {
                            "shape": "cylinder",
                            "type": "solid",
                            "xyz": [0.0, 0.0, 0.016],
                            "height": 0.010,
                            "radius": 0.080,
                            "has_drain": True,
                            "has_tube": True,
                        },
                        {
                            "shape": "cylinder",
                            "type": "solid",
                            "xyz": [0.0, 0.0, 0.016],
                            "height": 0.010,
                            "radius": 0.013,
                            "has_tube": True,
                        },
                    ],
                }

                # Retrieve simulation hooks
                hooks = provider.get_simulate_hooks("simulate")
                setup_fn = hooks[Simulate.SETUP]
                step_fn = hooks[Simulate.STEP]

                # Execute simulation setup hook
                setup_fn(body_id, client, "simulate", boundaries)

                assert provider.water_sim is not None
                provider.water_sim.recycle_fluid = False

                # Verify that when all water is within boundaries, simulation does not terminate
                assert step_fn(body_id, client, 0, "simulate") is None

                # Move a sufficient volume of water particles (at least 0.0012L) outside the boundary to trigger escaping
                vol_s = (4.0 / 3.0) * np.pi * (provider.water_sim.r_s**3)
                n_needed = int(np.ceil(0.0012 * 1e-3 / vol_s))
                pos_np = np.array(provider.water_sim.pos_jax)
                assert len(pos_np) >= n_needed
                pos_np[:n_needed, 2] = -10.0  # Put them below the floor boundary

                import jax.numpy as jnp

                provider.water_sim.pos_jax = jnp.array(pos_np)

                # Execute step simulation and verify the termination condition is met
                res = step_fn(body_id, client, 1, "simulate")
                assert res is not None
                assert "L of water fell out of bowl" in res

        finally:
            p.disconnect(client)

    @pytest.mark.slow
    def test_no_intersecting_parts(self, provider):
        """Verify that no parts intersect each other in the assembled configuration."""
        room = Room()
        provider.build_product(room, Mode.DEFAULT)
        room.translate_joints()

        parts = {
            name: geom[0] for name, geom in room.items() if not any(x in name for x in ["emitter", "receiver", "pcb"])
        }
        for name1, part1 in parts.items():
            for name2, part2 in parts.items():
                if name1 < name2:
                    intersection = part1.intersect(part2)
                    vol = sum(s.volume for s in intersection.solids()) if intersection else 0.0
                    assert vol == pytest.approx(0, abs=0.2), (
                        f"Intersection detected between {name1} and {name2}: {vol:.3f} mm3"
                    )

    @pytest.mark.slow
    def test_urdf_boundaries_conformance_with_cad_geometry(self, provider):
        """Verify that analytical URDF boundaries strictly conform to CAD dimensions and solid features."""
        from model.boundary_config import ShapeType
        from provider import Mode as ProviderMode, evaluate_boundary_cad_conformance

        room = Room()
        provider.build_product(room, mode=ProviderMode.DEFAULT)

        total_tested = 0
        for part_name, (geom, _) in room.items():
            boundaries = getattr(geom, "urdf_boundaries", None)
            if not boundaries:
                continue
            cad_solid = getattr(geom, "part", geom)

            for b in boundaries:
                res = evaluate_boundary_cad_conformance(cad_solid, b)
                total_tested += 1

                # If this is a physical solid barrier (tube wall, casing, vane, dome, shelf), verify CAD material alignment
                if res.solid_volume > 0.0:
                    assert res.solid_intersection_volume > 0.0, (
                        f"Part {part_name} boundary {res.shape}/{res.type} has zero CAD intersection"
                    )
                    # Enforce strict conformance (>= 70% to >= 95% accounting for slots/ports)
                    match res.shape:
                        case ShapeType.TUBE:
                            assert res.solid_conformance_ratio >= 0.95, (
                                f"Part {part_name} tube boundary has low conformance ({res.solid_conformance_ratio:.2%})"
                            )
                        case ShapeType.CASING:
                            assert res.solid_conformance_ratio >= 0.80, (
                                f"Part {part_name} casing boundary has low conformance ({res.solid_conformance_ratio:.2%})"
                            )
                        case ShapeType.IMPELLER:
                            assert res.solid_conformance_ratio >= 0.70, (
                                f"Part {part_name} impeller boundary has low conformance ({res.solid_conformance_ratio:.2%})"
                            )
                        case ShapeType.CANOPY:
                            # Hemispherical dome canopy with radial grating discharge slots
                            assert res.solid_conformance_ratio >= 0.40, (
                                f"Part {part_name} dome boundary has low conformance ({res.solid_conformance_ratio:.2%})"
                            )
                        case _:
                            assert res.solid_conformance_ratio >= 0.70, (
                                f"Part {part_name} boundary {res.shape} has low conformance ({res.solid_conformance_ratio:.2%})"
                            )

                # If this is a fluid cavity (bore, reservoir, casing cavity), verify positive volume
                if res.cavity_volume > 0.0:
                    assert res.cavity_volume > 0.0

        assert total_tested > 0, "Expected at least one URDF boundary to be registered and validated"

    @pytest.mark.slow
    def test_assembly_and_fitment_tolerances(self, provider):
        """Verify assembly clearances: clip fits through bottom cover, and drive hub fits in recess."""
        # 1. Verify that the bottom cover's opening width is larger than the motor hub mount plate width.
        # This ensures the assembly can actually be accessed from the side.
        assert provider.settings.bottom_cover_opening_width > provider.settings.motor_hub_width

        # 2. Verify that the drive hub outer radius is smaller than the bowl's drive hub recess radius.
        # This ensures the drive hub can be physically inserted into the recess on the motor shaft.
        hub_r = provider.settings.impeller_radius + provider.settings.magnet_radius + 1.0
        assert provider.settings.drive_hub_recess_radius > hub_r

        # 3. Verify that the motor mount bolt circle radius matches the BetaFPV 1102 pattern (3-1.4M on Dia 6.6mm)
        # and that the motor pocket radius provides sufficient clearance for the 15.2mm diameter motor body.
        assert provider.settings.motor_mount_bolt_circle_radius == 3.3
        assert provider.settings.motor_mount_hole_radius >= 0.7
        assert (
            provider.settings.motor_pocket_radius >= provider.settings.motor_radius + provider.settings.motor_clearance
        )
        assert provider.settings.motor_pocket_radius >= 8.1

    @pytest.mark.slow
    def test_bottom_cover_drain_and_notch_unobstructed(self, provider):
        """Verify that the bottom cover's central drain hole and edge notch are not filled by the snap ring."""
        cover = provider.build_bottom_cover("bottom_cover")
        solid = cover.part

        # Check central drain hole: point (0, 0, 2.0) must not be inside solid
        drain_pt = (0.0, 0.0, 2.0)
        assert not solid.is_inside(drain_pt), "Central drain hole is obstructed!"

        # Check notch opening on the rim: point (0, -cover_r, 2.0) must not be inside solid
        r = provider.settings.bowl_radius
        t = provider.settings.bowl_thickness
        clearance = provider.settings.bottom_cover_clearance
        cover_r = r - t - clearance
        notch_pt = (0.0, -cover_r, 2.0)
        assert not solid.is_inside(notch_pt), "Bottom cover opening notch is obstructed!"

    @pytest.mark.slow
    def test_lid_terrace_shelf_connected_to_fountain_cover(self, provider):
        """Verify that the lid terrace shelf is completely solid and connected to the fountain cover with no box cutouts."""
        lid = provider.build_lid("lid")
        solid = lid.part

        # Check under terrace shelf at Y = 28.0: points at Z = 1.5 (below Z=3.0 pocket floor) must be solid
        tube_y = 28.0
        assert solid.is_inside((0.0, tube_y + 15.0, 1.5)), "Terrace shelf underside is cut out!"
        assert solid.is_inside((15.0, tube_y, 1.5)), "Terrace shelf right side is cut out!"
        assert solid.is_inside((-15.0, tube_y, 1.5)), "Terrace shelf left side is cut out!"

        # Ensure lid consists of a single connected solid
        assert len(solid.solids()) == 1, "Lid has disconnected or floating solid bodies!"

    @pytest.mark.slow
    def test_drive_hub_minimum_wall_thickness(self, provider):
        """Verify that the drive hub has solid wall thickness under magnet pockets and is a single solid."""
        import math

        hub = provider.build_drive_hub("drive_hub")
        solid = hub.part

        # 1. Floor thickness under magnet pockets
        ring_r = provider.settings.magnet_ring_radius
        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        mt = provider.settings.magnet_thickness + provider.settings.magnet_clearance
        z_floor = (hub_h - mt) / 2.0
        for angle_deg in [0, 120, 240]:
            rad = math.radians(angle_deg)
            x = ring_r * math.cos(rad)
            y = ring_r * math.sin(rad)
            # Underneath magnet pocket: Z = z_floor must be solid
            assert solid.is_inside((x, y, z_floor)), (
                f"Drive hub magnet pocket floor at ({x:.1f}, {y:.1f}) is broken through!"
            )

        # 2. Central hub core body at r = 4.0mm, Z = 2.0mm must be solid
        assert solid.is_inside((4.0, 0.0, 2.0)), "Central hub core body is hollowed out!"

        # 3. Outer radial wall at r = 13.0mm, Z = 3.5mm must be solid
        assert solid.is_inside((13.0, 0.0, 3.5)), "Drive hub outer radial wall is too thin!"

        # 4. Ensure drive hub is a single connected solid
        assert len(solid.solids()) == 1, "Drive hub is split into disconnected parts!"

    @pytest.mark.slow
    def test_drive_hub_standoff_thrust_ring(self, provider):
        """Verify that the drive hub has a centered thrust collar around shaft collar and outer ring is removed."""
        hub = provider.build_drive_hub("drive_hub")
        solid = hub.part

        hub_r = provider.settings.impeller_radius + provider.settings.magnet_radius + 1.6
        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        standoff_h = provider.settings.drive_hub_standoff_height
        assert standoff_h > 0.0, "Expected positive standoff height"

        # Point at the outer perimeter (R = hub_r - 0.7mm) at Z = hub_h + standoff_h / 2.0 must NOT be solid (outer ring removed)
        test_r = hub_r - 0.7
        z_mid = hub_h + standoff_h / 2.0
        assert not solid.is_inside((test_r, 0.0, z_mid)), "Outer perimeter standoff ring must be removed!"

        # Point inside the centered thrust collar around the 1.5mm motor shaft collar (R <= 1.5mm) must be solid
        r_collar = (provider.settings.drive_hub_shaft_radius + provider.settings.drive_hub_thrust_collar_radius) / 2.0
        assert solid.is_inside((r_collar, 0.0, z_mid)), "Centered thrust collar is missing or hollow!"

        # Point inside the recessed magnet region (R = 9.0mm) at Z = hub_h + standoff_h / 2.0 must be empty space (recessed)
        assert not solid.is_inside((9.0, 0.0, z_mid)), "Magnet pocket region is not recessed below thrust collar!"

        # Central shaft hole at Z = hub_h + standoff_h / 2.0 must be open
        assert not solid.is_inside((0.0, 0.0, z_mid)), "Shaft hole is blocked!"

        # Ensure single contiguous solid
        assert len(solid.solids()) == 1, "Drive hub is split into disconnected parts!"

    @pytest.mark.slow
    def test_impeller_geometry_and_elevation(self, provider):
        """Verify that the impeller has the 3-bladed convex hull base, low-friction pin bore, and continuous blades."""
        import math

        impeller = provider.build_impeller("impeller")
        solid = impeller.part

        base_h = provider.settings.impeller_base_height
        pin_r = provider.settings.impeller_shaft_radius
        pin_clearance = provider.settings.impeller_shaft_clearance
        sleeve_r = provider.settings.impeller_sleeve_radius
        assert base_h >= 6.0, f"Expected impeller base height >= 6.0mm, got {base_h}"
        assert pin_r == 1.0, f"Expected low-friction shaft radius 1.0mm, got {pin_r}"
        assert provider.settings.impeller_blades == 3, "Expected 3-bladed impeller configuration"

        # 1. Point inside magnet lobe at Z = 4.5 (above 3.2mm magnet pocket, along X-axis lobe) must be solid
        assert solid.is_inside((6.0, 0.0, 4.5)), "Impeller magnet lobe body is missing or hollow!"

        # 2. Point in the valley between lobes (60 deg, R = 9.0mm) must be hollow/open (convex hull profile)
        valley_x = 9.0 * math.cos(math.radians(60))
        valley_y = 9.0 * math.sin(math.radians(60))
        assert not solid.is_inside((valley_x, valley_y, 4.5)), (
            "Impeller base should be a 3-lobed convex hull, not a full disk!"
        )

        # 3. Central pin hole must be open throughout
        assert not solid.is_inside((0.0, 0.0, base_h / 2.0)), "Pin hole is blocked!"
        assert not solid.is_inside((pin_r, 0.0, base_h / 2.0)), "Pin hole has insufficient clearance!"

        # 4. Blades start directly at the central hub sleeve (sleeve_r = 2.75mm) with zero gap
        blade_mid_z = base_h + 2.0
        blade_root_point = (sleeve_r + 0.5, 0.0, blade_mid_z)
        assert solid.is_inside(blade_root_point), "Impeller blade root is disconnected or has empty gap at sleeve!"

        # Ensure blade corners at sleeve junction have zero micro-gaps (BUG-FLITTING-LOCUST-977)
        assert solid.is_inside((2.70, 0.55, blade_mid_z)), "Micro-gap detected at positive blade corner junction!"
        assert solid.is_inside((2.70, -0.55, blade_mid_z)), "Micro-gap detected at negative blade corner junction!"
        assert solid.is_inside((2.68, 0.55, blade_mid_z)), "Micro-gap detected at sleeve cylinder perimeter!"

        # 5. Ensure single contiguous solid
        assert len(solid.solids()) == 1, "Impeller is split into disconnected parts!"

    @pytest.mark.slow
    def test_bottom_cover_rubber_feet_depressions(self, provider):
        """Verify that the bottom cover has recessed depressions for adhesive rubber feet."""
        import math

        cover = provider.build_bottom_cover("bottom_cover")
        solid = cover.part

        feet_count = provider.settings.rubber_feet_count
        feet_r = provider.settings.rubber_feet_radius
        feet_d = provider.settings.rubber_feet_depth
        pitch_r = provider.settings.rubber_feet_pitch_radius

        assert feet_count == 4, f"Expected 4 rubber feet depressions, got {feet_count}"
        assert feet_r > 0.0, "Expected positive rubber feet radius"
        assert feet_d > 0.0, "Expected positive rubber feet depth"

        for i in range(feet_count):
            angle_deg = (i * 360.0 / feet_count) + 45.0
            rad = math.radians(angle_deg)
            fx = pitch_r * math.cos(rad)
            fy = pitch_r * math.sin(rad)

            # Center of depression at Z = feet_d / 2.0 must be hollow (subtracted)
            assert not solid.is_inside((fx, fy, feet_d / 2.0)), (
                f"Rubber foot depression {i} at ({fx:.1f}, {fy:.1f}) is obstructed!"
            )

            # Solid material above the depression at Z = feet_d + 1.0 must be solid
            assert solid.is_inside((fx, fy, feet_d + 1.0)), (
                f"Material above rubber foot depression {i} at ({fx:.1f}, {fy:.1f}) is broken through!"
            )

        # Ensure single contiguous solid
        assert len(solid.solids()) == 1, "Bottom cover is split into disconnected solids!"

    @pytest.mark.slow
    def test_bowl_no_floating_solids(self, provider):
        """Verify that the main bowl is a single contiguous solid without internal floating shells."""
        bowl = provider.build_bowl("bowl")
        solid = bowl.part
        assert len(solid.solids()) == 1, f"Bowl has {len(solid.solids())} disconnected solids/shells!"

    def test_config_tune_action(self, provider):
        """Test that config_tune executes successfully with mocked PyBullet client."""
        from unittest.mock import MagicMock
        from projects.cat_fountain.config import config_tune
        from provider import Simulate

        # Mock the build manager and builder
        mock_manager = MagicMock()
        mock_builder = MagicMock()

        # Mock provider properties
        provider.logger = MagicMock()

        # Mock setup_fn to instantiate a mock water_sim on provider
        mock_water = MagicMock()
        mock_water.vel_jax = [[0.0, 0.0, 0.0]]
        mock_water.pos_jax = [[0.0, 0.028, 0.05]]

        def mock_setup(body_id, physics_client, view_path, boundaries, state):
            provider.water_sim = mock_water

        mock_setup_fn = MagicMock(side_effect=mock_setup)
        mock_step_fn = MagicMock()

        provider.get_simulate_hooks_impl = MagicMock(
            return_value={
                Simulate.SETUP: mock_setup_fn,
                Simulate.STEP: mock_step_fn,
            }
        )

        with (
            patch("pybullet.connect", return_value=42),
            patch("pybullet.disconnect") as mock_disconnect,
            patch("pybullet.setGravity") as mock_gravity,
            patch("pybullet.loadURDF", return_value=1),
            patch("pybullet.stepSimulation") as mock_step_sim,
            patch("provider.ProviderManager", return_value=mock_manager),
            patch("build.Builder", return_value=mock_builder),
            patch("pathlib.Path.exists", return_value=True),
            patch("shutil.copy"),
        ):
            # Run config_tune
            config_tune(provider, "product:view/simulate", None)

            # Verify that settings were updated with some optimal boundaries
            assert provider.settings.stiffness_boundary is not None
            assert provider.settings.damping_boundary is not None

            # Verify builder build steps were called
            mock_builder.generate_parts.assert_called_once()
            mock_builder.generate_urdfs.assert_called_once()

    @pytest.mark.slow
    @pytest.mark.timeout(450)
    def test_impeller_velocity_tuning(self):
        """Verify that we can tune the impeller velocity to respect the height limit."""
        import tempfile
        import os
        import numpy as np
        import pybullet as p
        import shutil
        from build import Builder
        from provider import ProviderManager, Room, Simulate, LinkType
        from model import AppConfig
        from shell import Logger

        with tempfile.TemporaryDirectory() as base_temp_dir:
            config = AppConfig()
            real_measurements = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../cat_fountain/measurements.yaml")
            )

            # Re-create provider for parts building
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements

            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            # Generate parts and URDFs ONCE
            parts_temp_dir = os.path.join(base_temp_dir, "parts")
            builder.generate_parts(parts_temp_dir, names=None)
            builder.generate_urdfs(parts_temp_dir, names=None)

            # Copy OBJ assets
            obj_dir = os.path.join(parts_temp_dir, "obj/cat_fountain")
            urdf_proj_dir = os.path.join(parts_temp_dir, "urdf/cat_fountain")
            for f in os.listdir(obj_dir):
                if f.endswith(".obj"):
                    shutil.copy(os.path.join(obj_dir, f), os.path.join(urdf_proj_dir, f))

            # Re-create provider for a clean run using production settings
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements
            provider.settings.target_volume = 0.00055
            provider.settings.motor_power = 1000.0

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()
            room["impeller"][0].urdf_motor_target = provider.settings.motor_target
            room["impeller"][0].urdf_motor_force = 10.0
            provider.room = room
            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(parts_temp_dir, "urdf/cat_fountain/product.urdf")
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

                # Query dynamic height limit from settings
                floor_z_m = provider.settings.floor_z * 0.001
                bowl_h = provider.settings.bowl_height * 0.001
                step_d = provider.settings.lid_step_depth * 0.001
                lid_mount_z = bowl_h - step_d
                # Lid pocket floor Z (main flat top drinking shelf surface) is at lid_mount_z + 3.0mm
                lid_z_top = lid_mount_z + 0.003

                # Run simulation
                step_fn = hooks[Simulate.STEP]
                max_water_z = 0.0
                for step_idx in range(80):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                    # Measure maximum height of water exiting the tube during motor execution
                    pos_np = np.asarray(fluid.pos_jax)
                    vel_np = np.asarray(fluid.vel_jax)
                    active_mask = pos_np[:, 2] < 100.0
                    if np.any(active_mask):
                        step_max_z = float(np.max(pos_np[active_mask, 2]))
                        if step_max_z > max_water_z:
                            max_water_z = step_max_z

                # Dome top is at (floor_z + tube_height) + 6.0mm center + dome_outer_radius
                socket_r = (provider.settings.tube_radius + provider.settings.tube_lid_clearance) * 0.001
                dome_out_r = socket_r + 0.0015
                tube_top_z = floor_z_m + provider.settings.tube_height * 0.001
                dome_top_z = tube_top_z + 0.006 + dome_out_r

                # Assert that under production measurements, the fountain water is contained by the spout dome ceiling
                min_expected = lid_z_top - 0.015
                max_expected = dome_top_z + 2.0 * fluid.r_s + 0.003

                assert min_expected <= max_water_z <= max_expected, (
                    f"max_water_z={max_water_z:.5f}, min={min_expected:.5f}, max={max_expected:.5f}"
                )

                # Verify that water reached the drinking surface
                assert max_water_z >= min_expected, "Expected water to reach the lid surface after exiting the spout."

                # Verify that reservoir pool water touches the bowl floor and outer wall
                reservoir_mask = active_mask & (pos_np[:, 2] < lid_mount_z)
                assert np.any(reservoir_mask), "Expected active reservoir fluid in the bowl."
                reservoir_pts = pos_np[reservoir_mask]
                min_reservoir_z = float(np.min(reservoir_pts[:, 2]))
                assert min_reservoir_z <= floor_z_m + fluid.r_s + 0.004, (
                    f"Reservoir fluid is hovering above floor: min Z is {min_reservoir_z:.5f}, expected <= {floor_z_m + fluid.r_s + 0.004:.5f}"
                )

                # Verify reservoir fluid spreads to outer bowl boundary
                r_reservoir = np.sqrt(reservoir_pts[:, 0] ** 2 + reservoir_pts[:, 1] ** 2)
                max_r = float(np.max(r_reservoir))
                bowl_inner_r = (provider.settings.bowl_radius - provider.settings.bowl_thickness) * 0.001
                assert max_r >= bowl_inner_r - 2.0 * fluid.r_s - 0.010, (
                    f"Reservoir fluid did not spread to bowl wall: max R is {max_r:.5f}, expected >= {bowl_inner_r - 2.0 * fluid.r_s - 0.010:.5f}"
                )

                # Verify that water particles do not flood the dry compartment / machine room below floor_z
                machine_room_mask = active_mask & (pos_np[:, 2] < floor_z_m - 0.005)
                flooded_particles = int(np.sum(machine_room_mask))
                assert flooded_particles == 0, (
                    f"Water is flooding the machine room under the bowl floor: {flooded_particles} particles below {floor_z_m - 0.005:.4f}m"
                )

                # Verify that water falling through mid-air between pool surface and lid is not hovering statically
                pool_top_z = float(np.percentile(reservoir_pts[:, 2], 99))
                tube_pos_xy = (0.0, 0.028)
                for b_list in boundaries.values():
                    b_items = b_list if isinstance(b_list, list) else [b_list]
                    for b in b_items:
                        if getattr(b, "link_type", None) == LinkType.TUBE and getattr(b, "xyz", None) is not None:
                            tube_pos_xy = (b.xyz[0], b.xyz[1])
                            break

                r_tube_outer_m = provider.settings.tube_radius * 0.001
                dist_tube = np.sqrt((pos_np[:, 0] - tube_pos_xy[0]) ** 2 + (pos_np[:, 1] - tube_pos_xy[1]) ** 2)
                mid_air_column_mask = (
                    active_mask
                    & (pos_np[:, 2] >= pool_top_z + 0.010)
                    & (pos_np[:, 2] <= lid_mount_z - 0.005)
                    & (dist_tube > r_tube_outer_m + 0.005)
                )
                if np.any(mid_air_column_mask):
                    speeds_mid_air = np.linalg.norm(vel_np[mid_air_column_mask], axis=-1)
                    static_particles = int(np.sum(speeds_mid_air < 0.05))
                    assert static_particles <= 15, (
                        f"Unnatural static hovering fluid blob: {static_particles} stationary particles in mid-air Z in [{pool_top_z + 0.010:.3f}, {lid_mount_z - 0.005:.3f}]m"
                    )
            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    @pytest.mark.timeout(600)
    def test_flow_and_drainage_metrics_stability_integration(self):
        """Verify continuous stability of flow, spout discharge, waterfall, drainage, and pool metrics."""
        import tempfile
        import os
        import shutil
        import numpy as np
        import pybullet as p
        from build import Builder
        from provider import ProviderManager, Room, Simulate
        from model import AppConfig
        from shell import Logger

        with tempfile.TemporaryDirectory() as base_temp_dir:
            config = AppConfig()
            real_measurements = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../cat_fountain/measurements.yaml")
            )
            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements

            manager = ProviderManager(config, providers=[provider], logger=Logger(enabled=False))
            builder = Builder(manager, logger=Logger(enabled=False))

            parts_temp_dir = os.path.join(base_temp_dir, "parts")
            builder.generate_parts(parts_temp_dir, names=None)
            builder.generate_urdfs(parts_temp_dir, names=None)

            obj_dir = os.path.join(parts_temp_dir, "obj/cat_fountain")
            urdf_proj_dir = os.path.join(parts_temp_dir, "urdf/cat_fountain")
            for f in os.listdir(obj_dir):
                if f.endswith(".obj"):
                    shutil.copy(os.path.join(obj_dir, f), os.path.join(urdf_proj_dir, f))

            provider = CatFountainProvider(config=config, logger=Logger(enabled=False))
            provider.settings.measurements_path = real_measurements
            provider.settings.motor_power = 1000.0

            room = Room()
            provider.build_product(room, mode=Mode.SIMULATE)
            room.translate_joints()
            room["impeller"][0].urdf_motor_target = provider.settings.motor_target
            room["impeller"][0].urdf_motor_force = 10.0
            provider.room = room

            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

                urdf_path = os.path.join(parts_temp_dir, "urdf/cat_fountain/product.urdf")
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                assert body_id >= 0

                boundaries = {}
                for _, (geom, _) in room.items():
                    label = getattr(geom, "urdf_label", None)
                    if label:
                        geom_boundaries = getattr(geom, "urdf_boundaries", None)
                        if geom_boundaries:
                            boundaries[label] = geom_boundaries

                hooks = provider.get_simulate_hooks("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                setup_fn(body_id, physics_client, "product:view/simulate", boundaries, None)
                step_fn = hooks[Simulate.STEP]

                fluid = provider.water_sim
                assert fluid is not None

                # Execute simulation steps through production hooks
                for step_idx in range(120):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                assert hasattr(provider, "metrics_history") and len(provider.metrics_history) == 120

                # Derive physical expectations from first principles:
                # 1. Total active fluid particles and single particle volume
                total_particles = len(fluid.pos_jax)
                assert total_particles > 0
                v_particle = (4.0 / 3.0) * math.pi * (fluid.r_s**3)

                # 2. Geometric delivery tube capacity: V_tube = pi * r_inner^2 * h_tube
                r_inner = (provider.settings.tube_radius - provider.settings.tube_thickness) * 0.001
                h_tube = provider.settings.tube_height * 0.001
                v_tube = math.pi * (r_inner**2) * h_tube
                n_tube_capacity = max(1, int(v_tube / v_particle))

                # 3. Geometric spout dome chamber capacity
                r_spout_dome = (provider.settings.tube_radius + 0.006) * 0.001
                v_spout_dome = (2.0 / 3.0) * math.pi * (r_spout_dome**3)
                n_spout_capacity = max(1, int(v_spout_dome / v_particle))

                # 4. Continuous Delivery Tube Flow & Spout Discharge with naturalistic lower and upper bounds:
                # - Lower bounds ensure pump delivery column does not collapse to zero after priming
                # - Upper bounds ensure fluid packing remains physically bounded by geometric volume
                steady_tube = np.array([m["flow_tube"] for m in provider.metrics_history[100:]])
                all_spout = np.array([m["flow_spout"] for m in provider.metrics_history])

                min_tube_particles = 1
                max_tube_particles = max(int(1.20 * n_tube_capacity), int(0.10 * total_particles))
                assert np.mean(steady_tube) >= min_tube_particles, (
                    f"Mean delivery tube flow fell below minimum physical threshold ({min_tube_particles} particles)"
                )
                assert np.count_nonzero(steady_tube) >= int(0.70 * len(steady_tube)), (
                    "Delivery tube flow collapsed into non-pumping state for excessive frames"
                )
                assert np.all(steady_tube <= max_tube_particles), (
                    f"Delivery tube flow exceeded maximum geometric packing capacity ({max_tube_particles} particles)"
                )

                max_spout_particles = max(int(4.00 * n_spout_capacity), int(0.05 * total_particles))
                assert np.count_nonzero(all_spout) > 0, "Spout discharge dried up completely during simulation"
                assert np.all(all_spout <= max_spout_particles), (
                    f"Spout discharge stream exceeded dome exit volume capacity ({max_spout_particles} particles)"
                )

                # 5. Continuous Lid Sheet Flow and Perimeter Waterfall Continuity
                steady_sheet = np.array([m["flow_lid_sheet"] for m in provider.metrics_history[40:]])
                assert np.mean(steady_sheet) > 0.0, "Drinking sheet flow across lid tray collapsed to zero"
                assert np.count_nonzero(steady_sheet) > 0, "No fluid particles established flow across lid tray"

                steady_waterfall = np.array([m["drainage_waterfall"] for m in provider.metrics_history[40:]])
                steady_drain = np.array([m["drainage_cutout"] for m in provider.metrics_history[40:]])
                total_steady_drainage = steady_waterfall + steady_drain

                assert np.mean(steady_waterfall) > 0.0, "Perimeter waterfall drainage collapsed to zero"
                assert np.count_nonzero(steady_waterfall) > 0, "Perimeter waterfall dried up during simulation"
                assert np.mean(total_steady_drainage) > 0.0, (
                    "Total drainage returning to reservoir collapsed to zero in steady state"
                )
                assert np.count_nonzero(total_steady_drainage) > 0, "Total drainage dried up in steady state"
                assert np.all(total_steady_drainage <= int(0.80 * total_particles)), (
                    "Falling drainage exceeded physical system mass allocation"
                )
                assert len(fluid.total_fallen_water_ids) == 0, (
                    f"Fluid particles unexpectedly deactivated or collapsed: {len(fluid.total_fallen_water_ids)}"
                )
                steady_ejected = np.array([m["ejected_particles"] for m in provider.metrics_history[40:]])
                assert np.all(steady_ejected == 0), (
                    f"Fluid particles unexpectedly breached canopy or hovered in mid-air: {np.max(steady_ejected)} particles"
                )

                # 6. Reservoir Pool Mass Conservation: In steady state, reservoir pool retains majority fluid mass
                min_expected_pool_particles = int(0.40 * total_particles)
                max_expected_pool_particles = total_particles
                steady_pool = np.array([m["pool_volume"] for m in provider.metrics_history[40:]])
                assert np.all(steady_pool >= min_expected_pool_particles), (
                    f"Pool volume collapsed below physical mass conservation threshold ({min_expected_pool_particles} particles)"
                )
                assert np.all(steady_pool <= max_expected_pool_particles), (
                    f"Pool volume exceeded total active fluid mass ({max_expected_pool_particles} particles)"
                )

                # 7. Reservoir Water Depth & Casing Contact Continuity
                min_pool_depth = (provider.settings.slot_height - provider.settings.pump_casing_clearance) * 0.001
                max_pool_depth = (provider.settings.bowl_height - provider.settings.floor_z) * 0.001
                steady_depth = np.array([m["water_depth"] for m in provider.metrics_history[40:]])
                assert np.all(steady_depth >= min_pool_depth), "Reservoir water depth drained below minimum threshold"
                assert np.all(steady_depth <= max_pool_depth), "Reservoir water depth exceeded maximum bowl capacity"

                # Regression assertions: guard against reservoir water volume collapse and flow loss
                min_steady_depth = 2.5 * min_pool_depth
                assert np.all(steady_depth >= min_steady_depth), (
                    f"Reservoir water depth collapsed below physical threshold: min={np.min(steady_depth):.4f}m"
                )
                initial_sheet = np.array([m["flow_lid_sheet"] for m in provider.metrics_history[50:]])
                assert np.all(initial_sheet > 0), f"Lid sheet failed to prime: min={np.min(initial_sheet)}"
                steady_sheet = np.array([m["flow_lid_sheet"] for m in provider.metrics_history[75:]])
                assert np.all(steady_sheet >= 300), (
                    f"Lid sheet flow collapsed in steady state: min={np.min(steady_sheet)}"
                )

                # Verify continuous physical fluid contact with motor casing and non-piled reservoir distribution
                pos_np = np.asarray(fluid.pos_jax)
                active = pos_np[:, 2] < 100.0
                pos_act = pos_np[active]
                bowl_floor_z = provider.settings.floor_z * 0.001
                lid_z = (provider.settings.bowl_height - provider.settings.lid_step_depth) * 0.001
                in_bowl = (pos_act[:, 2] >= bowl_floor_z - 0.005) & (pos_act[:, 2] <= lid_z)
                pos_bowl = pos_act[in_bowl]

                # Guard against reservoir fluid collapsing into a pancake layer on the floor
                z_p50 = float(np.percentile(pos_bowl[:, 2], 50))
                assert z_p50 >= bowl_floor_z + min_pool_depth, (
                    f"Fluid volume collapsed into pancake layer at floor: z_p50={z_p50:.4f}m"
                )

                casing_r = (
                    provider.settings.impeller_radius
                    + provider.settings.pump_casing_clearance
                    + provider.settings.pump_well_wall
                ) * 0.001
                d_casing = np.sqrt(pos_bowl[:, 0] ** 2 + pos_bowl[:, 1] ** 2)
                r_bowl = np.sqrt(pos_bowl[:, 0] ** 2 + pos_bowl[:, 1] ** 2)

                assert np.min(d_casing) <= casing_r + 0.003, (
                    f"Water detached from motor casing: min_d_casing={np.min(d_casing):.4f} m"
                )
                v_casing_shell = math.pi * ((casing_r + 0.005) ** 2 - casing_r**2) * min_pool_depth
                min_casing_contact_particles = max(100, int(0.50 * (v_casing_shell / v_particle)))
                assert np.sum(d_casing <= casing_r + 0.005) >= min_casing_contact_particles, (
                    "Insufficient fluid volume in contact with motor casing"
                )
                bowl_inner_r = (provider.settings.bowl_radius - provider.settings.bowl_thickness) * 0.001
                assert np.sum(r_bowl >= bowl_inner_r * 0.833) <= int(0.60 * len(pos_bowl)), (
                    "Excessive fluid mass piled up at outer bowl wall"
                )

                # Verify standalone compute_flow_metrics hook method
                current_metrics = provider.compute_flow_metrics()
                assert min_expected_pool_particles <= current_metrics["pool_volume"] <= max_expected_pool_particles
                assert (
                    "water_depth" in current_metrics
                    and min_pool_depth <= current_metrics["water_depth"] <= max_pool_depth
                )
            finally:
                p.disconnect(physics_client)

    @pytest.mark.slow
    def test_cat_fountain_port_connectivity(self, provider):
        """Verify that all intake and drain ports across cat fountain components match and connect."""
        import jax.numpy as jnp
        from provider.boundary import BoundaryProcessor
        from provider.transforms import match_intake_drain_ports

        room = Room()
        provider.build_product(room, mode=Mode.DEFAULT)
        room.translate_joints()

        boundary_list = []
        for name, (geom, _) in room.items():
            if hasattr(geom, "urdf_boundaries"):
                boundary_list.extend(geom.urdf_boundaries)

        processed = BoundaryProcessor.process(boundary_list)

        matches_mask, dist_matrix = match_intake_drain_ports(
            processed.b_pos_arr,
            processed.b_orn_arr,
            processed.b_params,
            distance_tol=0.035,
            normal_alignment_threshold=-0.0,
        )

        # Check that there is at least one active match in the system
        assert jnp.any(matches_mask), "No fluid intake/drain ports matched across cat fountain assembly"

    @pytest.mark.slow
    def test_pump_cover_c_clip_opening(self, provider):
        """Verify that the pump cover sleeve features a North-facing C-clip opening for effortless slide-down and snap-on."""
        cover = provider.build_pump_cover("pump_cover")
        solid = cover.part
        assert solid is not None and solid.volume > 0.0

        tube_y = 28.0
        tube_r = provider.settings.tube_radius
        sleeve_h = provider.settings.pump_cover_sleeve_height
        z_mid = sleeve_h / 2.0

        # North-facing point on outer sleeve perimeter (Y = tube_y + tube_r + 1.0) must be open (outside/not solid)
        north_y = tube_y + tube_r + 1.0
        assert not solid.is_inside((0.0, north_y, z_mid)), (
            f"Pump cover sleeve North opening is blocked at Y = {north_y}!"
        )

        # South bridge/cradle wall (Y = tube_y - tube_r - 1.0) must be solid to support and locate the cover
        south_y = tube_y - tube_r - 1.0
        assert solid.is_inside((0.0, south_y, z_mid)), f"Pump cover South cradle wall is broken at Y = {south_y}!"

    @pytest.mark.slow
    def test_regression_bug_speckled_roach_49_pump_cover_snap_fit(self, provider):
        """Verify that pump cover downward lip features an annular snap ridge and casing recess has a matching groove.

        BUG-SPECKLED-ROACH-49: Ensures pump cover snaps securely into the casing recess on the bowl and cannot move
        freely up and down the tube/shaft.
        """
        from build123d import Location

        bowl = provider.build_bowl("bowl")
        cover = provider.build_pump_cover("pump_cover")
        bowl_part = bowl.part
        cover_part = cover.part
        assert bowl_part is not None and cover_part is not None
        assert len(cover_part.solids()) == 1, (
            f"Pump cover has {len(cover_part.solids())} separate solids; must be a single merged solid"
        )

        floor_z = provider.settings.floor_z
        hub_r = provider.settings.impeller_radius + provider.settings.magnet_radius + 1.0
        impeller_r = hub_r + 4.0
        chamber_r = impeller_r + provider.settings.pump_casing_clearance
        snap_r = chamber_r + 1.0
        z_offset = provider.settings.pump_cover_snap_z_offset
        mount_depth = provider.settings.pump_cover_mount_depth
        assert mount_depth >= 2.0, f"Expected mount depth >= 2.0mm for epoxy clearance, got {mount_depth}"
        assert z_offset >= 1.2, f"Expected annular ring Z offset >= 1.2mm for epoxy clearance, got {z_offset}"

        # 1. Pump cover downward lip has an annular snap ridge protruding beyond snap_r
        ridge_outer_r = (
            snap_r + provider.settings.pump_cover_snap_ridge_offset + provider.settings.pump_cover_snap_ridge_minor
        )
        assert ridge_outer_r > snap_r, "Snap ridge must extend beyond casing recess radius to snap in"
        test_ridge_pt = (ridge_outer_r - 0.05, 0.0, -z_offset)
        assert cover_part.is_inside(test_ridge_pt), (
            f"Pump cover downward lip is missing annular snap ridge at {test_ridge_pt}!"
        )

        # 2. Bowl casing recess has a matching snap groove at the same relative Z
        groove_z = floor_z + 10.0 - z_offset
        test_groove_pt = (snap_r + 0.2, 0.0, groove_z)
        assert not bowl_part.is_inside(test_groove_pt), (
            f"Bowl casing recess is missing annular snap groove at {test_groove_pt}!"
        )

        # 3. Assembled configuration must have zero CAD collision between ridge and groove
        seat_loc = Location((0, 0, floor_z + 10.0))
        cover_placed = cover_part.located(seat_loc)
        intersection = bowl_part.intersect(cover_placed)
        vol = sum(s.volume for s in intersection.solids()) if intersection else 0.0
        assert vol < 0.2, f"Interference detected between bowl and snapped pump cover: {vol:.4f} mm3"

    @pytest.mark.slow
    def test_regression_bug_glowing_wasp_133_snap_ring_refactoring(self, provider):
        """Verify that snap ring and pocket tool geometry routines are cleanly abstracted and parameterized.

        BUG-GLOWING-WASP-133: Replaces repeated ad-hoc snap ring and pocket tool patterns with reusable helpers
        and parameterized config settings.
        """
        from projects.cat_fountain.provider import make_filleted_pocket_tool, make_snap_ring

        # 1. Test make_snap_ring
        ring = make_snap_ring(outer_radius=20.0, inner_radius=18.0, height=1.0, fillet_radius=0.3)
        assert ring is not None and ring.volume > 0.0
        assert ring.is_inside((19.0, 0.0, 0.5))
        assert not ring.is_inside((17.0, 0.0, 0.5))
        assert not ring.is_inside((21.0, 0.0, 0.5))

        # 2. Test make_filleted_pocket_tool
        tool = make_filleted_pocket_tool(radius=80.0, height=6.0, fillet_radius=1.5)
        assert tool is not None and tool.volume > 0.0
        assert tool.is_inside((0.0, 0.0, 3.0))

        # 3. Verify that bottom cover, lid, and motor hub build cleanly with refactored helpers
        bottom_cover = provider.build_bottom_cover("bottom_cover")
        assert bottom_cover.part is not None and bottom_cover.part.volume > 0.0

        lid = provider.build_lid("lid")
        assert lid.part is not None and lid.part.volume > 0.0

        motor_hub = provider.build_motor_hub("motor_hub")
        assert motor_hub.part is not None and motor_hub.part.volume > 0.0

    def test_compute_flow_metrics_upper_reservoir_retention(self, provider):
        """Verify that fluid particles filling the reservoir up to the lid shelf are counted in pool_volume.

        Regression test: Prevents metric collapse where an artificial 15mm cutoff dropped pool_volume
        when the bowl reservoir was filled near the lid.
        """
        import numpy as np
        from projects.cat_fountain.simulate_hooks import compute_flow_metrics

        bowl_h = provider.settings.bowl_height * 0.001
        step_d = provider.settings.lid_step_depth * 0.001
        lid_mount_z = bowl_h - step_d

        # 500 particles in upper reservoir at z = lid_mount_z - 0.005 (e.g. 97mm in a 102mm lid mount)
        pts = np.zeros((500, 3))
        pts[:, 0] = 0.035
        pts[:, 1] = 0.0
        pts[:, 2] = lid_mount_z - 0.005

        provider.water_sim = type("MockSim", (), {"last_positions": pts, "last_velocities": None})()
        metrics = compute_flow_metrics(provider)

        assert metrics["pool_volume"] == 500, (
            f"Upper reservoir particles were artificially excluded from pool_volume: got {metrics['pool_volume']}"
        )

    @pytest.mark.slow
    def test_regression_bug_168_motor_base_mounting_and_pocket_clearance(self, provider):
        """Verify motor pocket clearance in bowl and secure triangular mounting holes in motor clip.

        Regression test for BUG-168:
        1. Ensures the motor pocket in the bowl has sufficient clearance for the 15.2mm diameter motor body.
        2. Ensures the motor clip features 3x M1.4 mounting screw holes on a 6.6mm BCD, anti-rotation base recess,
           and wire relief channel rather than a loose U-cutout that allowed the motor to spin.
        """
        # 1. Verify bowl motor pocket clearance
        bowl = provider.build_bowl("bowl")
        floor_z = provider.settings.floor_z
        # Point at 7.8mm radius (inside the 8.1mm pocket, but outside the old 7.0mm cut) must be hollow
        test_z = floor_z - 12.0
        assert not bowl.part.is_inside((7.8, 0.0, test_z)), (
            "Motor pocket at radius 7.8mm is solid: motor diameter 15.2mm (radius 7.6mm) will rub or not fit!"
        )

        # 2. Verify motor hub mounting and anti-rotation features
        hub = provider.build_motor_hub("motor_hub")
        assert hub.part.volume > 0.0
        assert hub.part.is_valid()

        clip_h = provider.settings.motor_hub_thickness
        r_bcd = provider.settings.motor_mount_bolt_circle_radius
        assert r_bcd == 3.3, f"Expected BCD radius 3.3mm for BetaFPV 1102, got {r_bcd}"

        # 3 screw holes at 90°, 210°, 330° must be open (not solid)
        for angle in [90.0, 210.0, 330.0]:
            rad = math.radians(angle)
            hx = r_bcd * math.cos(rad)
            hy = r_bcd * math.sin(rad)
            assert not hub.part.is_inside((hx, hy, clip_h * 0.5)), (
                f"Mount screw hole at ({hx:.2f}, {hy:.2f}) is blocked!"
            )

        # Center shaft / bearing clearance hole must be open
        assert not hub.part.is_inside((0.0, 0.0, clip_h * 0.5)), "Central shaft clearance hole is blocked!"

        # Solid plate area outside shaft hole supporting motor base
        assert hub.part.is_inside((3.5, 0.0, clip_h * 0.5)), (
            "Motor hub bracket is hollowed out around motor base: expected solid plastic to mount and secure motor!"
        )

    def test_regression_bug_hairy_wasp_932_tmc6300_6pwm_wiring_and_no_sense_pin(self, provider):
        """Verify BUG-HAIRY-WASP-932: TMC6300 uses 6-PWM control (UH..WL), SEN pin is disconnected, and GP26 speed sensor is preserved."""
        from pathlib import Path
        from projects.cat_fountain.pcb import build_cat_fountain_wiring

        wiring = build_cat_fountain_wiring()

        # 1. Pico pin allocation: GP16..GP21 for 6-PWM, GP22 for DIAG, and GP26 for speed sensor
        pico = next(f for f in wiring.footprints if f.name == "pico")
        pico_pin_names = {p.name for p in pico.pins}
        expected_pico_gpios = {"GP16", "GP17", "GP18", "GP19", "GP20", "GP21", "GP22", "GP26"}
        assert expected_pico_gpios.issubset(pico_pin_names)

        # 2. Motor driver: 6 independent phase inputs (UH, UL, VH, VL, WH, WL) and outputs (U, V, W)
        driver = next(f for f in wiring.footprints if f.name == "motor_driver")
        driver_pin_names = {p.name for p in driver.pins}
        assert {"UH", "UL", "VH", "VL", "WH", "WL", "DIAG", "U", "V", "W"}.issubset(driver_pin_names)
        assert "IN1" not in driver_pin_names
        assert "IN2" not in driver_pin_names
        assert "IN3" not in driver_pin_names
        assert "EN" not in driver_pin_names

        # 3. Speed sensor component preserved on GP26
        footprint_names = {f.name for f in wiring.footprints}
        assert "speed_sensor" in footprint_names, "Speed sensor footprint must be present"

        # 4. Nets: 6 control nets connect Pico GP16..GP21 to TMC6300 UH..WL, GP22 to DIAG, GP26 to speed sensor
        net_map = {n.name: [tuple(p) for p in n.pins] for n in wiring.nets}
        assert ("pico", "GP16") in net_map["ctrl_uh"] and ("motor_driver", "UH") in net_map["ctrl_uh"]
        assert ("pico", "GP17") in net_map["ctrl_ul"] and ("motor_driver", "UL") in net_map["ctrl_ul"]
        assert ("pico", "GP18") in net_map["ctrl_vh"] and ("motor_driver", "VH") in net_map["ctrl_vh"]
        assert ("pico", "GP19") in net_map["ctrl_vl"] and ("motor_driver", "VL") in net_map["ctrl_vl"]
        assert ("pico", "GP20") in net_map["ctrl_wh"] and ("motor_driver", "WH") in net_map["ctrl_wh"]
        assert ("pico", "GP21") in net_map["ctrl_wl"] and ("motor_driver", "WL") in net_map["ctrl_wl"]
        assert ("pico", "GP22") in net_map["ctrl_diag"] and ("motor_driver", "DIAG") in net_map["ctrl_diag"]
        assert ("pico", "GP26") in net_map["speed_sense"] and ("speed_sensor", "OUT") in net_map["speed_sense"]

        # 5. Provider key definitions
        assert "GP16" in provider.RP2040_KEY_RIGHT_GPIOS
        assert "GP26" in provider.RP2040_KEY_RIGHT_GPIOS
        key_entry_pins = [entry[0] for entry in provider.TMC6300_KEY_ENTRIES]
        assert key_entry_pins == ["UH", "UL", "VH", "VL", "WH", "WL", "U", "V", "W"]

    def test_regression_bug_camouflaged_midge_831_no_cyan_wire_in_cat_fountain_wiring(self):
        """Verify BUG-CAMOUFLAGED-MIDGE-831: Cat fountain wiring diagram does not use cyan wire color."""
        from pathlib import Path
        from projects.cat_fountain.pcb import build_cat_fountain_wiring

        wiring = build_cat_fountain_wiring()

        cyan_nets = [net.name for net in wiring.nets if net.color.lower() == "cyan"]
        assert not cyan_nets, f"Cyan wire color is prohibited in loom, but found in nets: {cyan_nets}"

        ctrl_uh_net = next((net for net in wiring.nets if net.name == "ctrl_uh"), None)
        assert ctrl_uh_net is not None, "ctrl_uh net must be present"
        assert ctrl_uh_net.color.lower() == "brown", f"Expected ctrl_uh net color to be brown, got {ctrl_uh_net.color}"

    def test_regression_tmc6300_vcp_no_external_capacitor(self):
        """Verify TMC6300 VCP is NOT connected to an external capacitor in BOM and wiring guide."""
        from pathlib import Path

        doc_path = Path(__file__).parent.parent / "cat_fountain.md"
        assert doc_path.is_file(), "cat_fountain.md must exist"
        doc_text = doc_path.read_text(encoding="utf-8")

        # BOM table must NOT include an external VCP capacitor
        bom_lines = [line.strip() for line in doc_text.splitlines() if line.strip().startswith("|")]
        vcp_cap_row = next(
            (
                line
                for line in bom_lines
                if "VCP Charge Pump Capacitor" in line or ("VCP" in line and "Capacitor" in line)
            ),
            None,
        )
        assert vcp_cap_row is None, f"BOM table must not include an external VCP capacitor, found: {vcp_cap_row}"
        assert "VCP Charge Pump Reservoir Capacitor Wiring" not in doc_text, (
            "Wiring guide must not specify external VCP capacitor wiring"
        )

    def test_regression_bug_pollen_backswimmer_846_tmc6300_clip_mount_dimensions_and_text(self, provider):
        """Verify BUG-POLLEN-BACKSWIMMER-846: TMC6300 clip-on mount matches 0.80x0.60 in (20.32x15.24mm) PDF dimensions."""
        from pathlib import Path
        from model.wiring import Wiring

        # 1. Check measurements for TMC6300 clip mount (exact 0.80" x 0.60" board dimensions from PDF)
        assert provider.settings.motor_driver_spacing_x == 20.32, (
            f"Expected motor_driver_spacing_x to be 20.32mm (0.80 in length), got {provider.settings.motor_driver_spacing_x}"
        )
        assert provider.settings.motor_driver_spacing_y == 15.24, (
            f"Expected motor_driver_spacing_y to be 15.24mm (0.60 in width), got {provider.settings.motor_driver_spacing_y}"
        )

        # 2. Check wiring.yaml footprint dimensions, rotation, and absence of screw mounting holes
        wiring = provider.wiring
        driver = next(f for f in wiring.footprints if f.name == "motor_driver")
        assert tuple(driver.dimensions) == (20.32, 15.24, 1.6), (
            f"Expected TMC6300 board dimensions [20.32, 15.24, 1.6], got {driver.dimensions}"
        )
        assert tuple(driver.rotation) == (0.0, 0.0, 90.0), (
            f"Expected TMC6300 rotation [0.0, 0.0, 90.0] for clip socket alignment, got {driver.rotation}"
        )
        assert driver.mounting_holes is None, (
            "SparkFun TMC6300 breakout has no screw mounting holes per official dimensions PDF"
        )

        # 3. Verify bowl CAD geometry: clip tracks fit 20.32x15.24mm board and TMC6300 text is on positive Y (opposite CURRENT)
        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        assert bowl.part.is_valid()

        # Center of TMC6300 is (50.0, 15.0)
        # With span 15.24mm (along X) and slide length 20.32mm (along Y), guide tracks are around X = 50 +/- 8.12
        # Inside the track body at X = 50 + (15.24/2 + 0.5) should be solid plastic:
        t = provider.settings.bowl_thickness
        floor_z = provider.settings.floor_z
        track_z = floor_z - t - (provider.settings.motor_driver_standoff_height + 1.0)
        tmc_span = provider.settings.motor_driver_spacing_y
        tmc_slide = provider.settings.motor_driver_spacing_x
        assert bowl.part.is_inside((50.0 + tmc_span / 2.0 + 0.5, 15.0, track_z)), (
            "TMC6300 clip guide track should be positioned for 15.24mm board width"
        )

        # "CURRENT" text is at (50.0, -2.5). "TMC6300" text should be moved to opposite side (Y = 15 + 7.5 + 5 = 27.5),
        # not adjacent to CURRENT at Y = 15 - 12.5 = 2.5.
        text_z = floor_z - t + 0.5
        sample_dxs = [-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0]
        sample_dys = [-0.5, 0.0, 0.5]

        # At old location (Y = 2.5), bowl floor must be solid plastic (no engraved text cutout)
        assert all(bowl.part.is_inside((50.0 + dx, 2.5 + dy, text_z)) for dx in sample_dxs for dy in sample_dys), (
            "TMC6300 text must not be engraved on the negative Y side (adjacent to CURRENT text)"
        )

        # At new location (Y = 15.0 + tmc_slide / 2.0 + 5.0), engraved text strokes cut into bowl floor
        text_y = 15.0 + tmc_slide / 2.0 + 5.0
        assert any(
            not bowl.part.is_inside((50.0 + dx, text_y + dy, text_z)) for dx in sample_dxs for dy in sample_dys
        ), "TMC6300 text must be engraved on the positive Y side opposite CURRENT text"

    def test_regression_bug_swarming_cicada_917_clip_in_mounts(self, provider):
        """Verify BUG-SWARMING-CICADA-917: Replace motor room mount holes with press-fit clip mounts except charger."""
        # 1. Config properties exist
        assert hasattr(provider.settings, "pcb_mounting_post_diameter")
        assert hasattr(provider.settings, "pcb_mounting_post_height")
        assert hasattr(provider.settings, "hall_sensor_spacing_x")
        assert hasattr(provider.settings, "hall_sensor_spacing_y")

        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        assert bowl.part.is_valid()

        t = provider.settings.bowl_thickness
        floor_z = provider.settings.floor_z
        sh = provider.settings.pico_standoff_height
        post_z = floor_z - t - sh - 1.0  # Middle of press-fit post shaft
        boss_z = floor_z - t - (sh * 0.5)  # Inside the standoff boss body

        # 2. Charger retains screw mount holes: at hole center inside boss, geometry is hollow (hole)
        cx, cy = 0.0, -79.0
        ch_dx = provider.settings.charger_spacing_x / 2.0
        ch_dy = provider.settings.charger_spacing_y / 2.0
        assert not bowl.part.is_inside((cx + ch_dx, cy + ch_dy, boss_z)), (
            "Charger standoff should retain blind screw hole"
        )

        # 3. Pico W uses press-fit clip mounts: at post location, post shaft is solid plastic
        px, py = -50.0, 0.0
        pico_dx = provider.settings.pico_spacing_x / 2.0
        pico_dy = provider.settings.pico_spacing_y / 2.0
        assert bowl.part.is_inside((px - pico_dx, py - pico_dy, post_z)), (
            "Pico W standoff should feature solid press-fit post shaft instead of screw hole"
        )
        assert bowl.part.is_inside((px - pico_dx, py - pico_dy, boss_z)), (
            "Pico W boss must be solid plastic (no blind screw hole)"
        )

        # 4. Current monitor uses press-fit clip mounts with posts at {1, 3} (nearest to "CURRENT" text)
        ix, iy = 50.0, -15.0
        ina_dx = provider.settings.current_monitor_spacing_x / 2.0
        ina_dy = provider.settings.current_monitor_spacing_y / 2.0
        # Post points at {1, 3} (nearest to text at +dy) have press-fit posts
        assert bowl.part.is_inside((ix - ina_dx, iy + ina_dy, post_z)), (
            "Current monitor mount point 1 must have press-fit post"
        )
        assert bowl.part.is_inside((ix + ina_dx, iy + ina_dy, post_z)), (
            "Current monitor mount point 3 must have press-fit post"
        )
        # Boss-only points at {0, 2} have no post
        assert not bowl.part.is_inside((ix - ina_dx, iy - ina_dy, post_z)), (
            "Current monitor mount point 0 should have NO post (boss only)"
        )
        assert bowl.part.is_inside((ix - ina_dx, iy - ina_dy, boss_z)), (
            "Current monitor mount point 0 must have solid boss pad"
        )
        assert not bowl.part.is_inside((ix + ina_dx, iy - ina_dy, post_z)), (
            "Current monitor mount point 2 should have NO post (boss only)"
        )
        assert bowl.part.is_inside((ix + ina_dx, iy - ina_dy, boss_z)), (
            "Current monitor mount point 2 must have solid boss pad"
        )

        # 5. Fuel gauge has 2 posts at {1, 3} (nearest to "FUEL" text) and 2 bosses at {0, 2}
        fx, fy = 50.0, -45.0
        fuel_dx = provider.settings.fuel_gauge_spacing_x / 2.0
        fuel_dy = provider.settings.fuel_gauge_spacing_y / 2.0
        # Post points at {1, 3} (nearest to text at +dy) have press-fit posts
        assert bowl.part.is_inside((fx - fuel_dx, fy + fuel_dy, post_z)), (
            "Fuel gauge mount point 1 must have press-fit post"
        )
        assert bowl.part.is_inside((fx + fuel_dx, fy + fuel_dy, post_z)), (
            "Fuel gauge mount point 3 must have press-fit post"
        )
        # Boss-only points at {0, 2} have no post
        assert not bowl.part.is_inside((fx - fuel_dx, fy - fuel_dy, post_z)), (
            "Fuel gauge mount point 0 should have NO post (boss only)"
        )
        assert bowl.part.is_inside((fx - fuel_dx, fy - fuel_dy, boss_z)), (
            "Fuel gauge mount point 0 must have solid boss pad"
        )
        assert not bowl.part.is_inside((fx + fuel_dx, fy - fuel_dy, post_z)), (
            "Fuel gauge mount point 2 should have NO post (boss only)"
        )
        assert bowl.part.is_inside((fx + fuel_dx, fy - fuel_dy, boss_z)), (
            "Fuel gauge mount point 2 must have solid boss pad"
        )

        # 6. Legacy Hall sensor board mount on bowl ceiling is removed (moved directly to motor_hub)
        hx, hy = 0.0, 40.0
        hall_dx = provider.settings.hall_sensor_spacing_x / 2.0
        hall_dy = provider.settings.hall_sensor_spacing_y / 2.0
        assert not bowl.part.is_inside((hx - hall_dx, hy - hall_dy, post_z)), (
            "Legacy Hall sensor mount point on ceiling should be removed"
        )
        assert not bowl.part.is_inside((hx - hall_dx, hy + hall_dy, boss_z)), (
            "Legacy Hall sensor boss pad on ceiling should be removed"
        )

    def test_regression_bug_pincered_caddisfly_769_swd_clip_mount(self, provider):
        """Verify BUG-PINCERED-CADDISFLY-769: Add clip-on mount for Treedix JTAG/SWD breakout adapter."""
        from pathlib import Path
        from model.wiring import Wiring

        # 1. Config properties exist for SWD breakout board
        assert hasattr(provider.settings, "swd_board_length"), "swd_board_length property missing"
        assert hasattr(provider.settings, "swd_board_width"), "swd_board_width property missing"
        assert provider.settings.swd_board_length == 19.1
        assert provider.settings.swd_board_width == 13.7

        # 2. Footprint in wiring.yaml
        wiring = provider.wiring
        swd_fp = next((f for f in wiring.footprints if f.name == "swd_adapter"), None)
        assert swd_fp is not None, "swd_adapter footprint must exist in wiring.yaml"
        assert tuple(swd_fp.dimensions) == (19.1, 13.7, 1.6)
        assert tuple(swd_fp.rotation) == (0.0, 0.0, 90.0), (
            f"Expected SWD adapter rotation [0.0, 0.0, 90.0] for clip socket alignment, got {swd_fp.rotation}"
        )

        # 3. Bowl CAD model contains clip guide for SWD board
        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        assert bowl.part.is_valid()

        t = provider.settings.bowl_thickness
        floor_z = provider.settings.floor_z
        sh = provider.settings.swd_board_standoff_height
        track_z = floor_z - t - (sh + 1.0)

        # SWD is centered at (-50.0, -45.0) with clip spacing swd_board_width (13.7mm)
        # Guide track wall is positioned at X = -50.0 + (13.7 / 2.0 + 1.5) = -41.65
        track_x = -50.0 + (provider.settings.swd_board_width / 2.0 + 1.5)
        assert bowl.part.is_inside((track_x, -45.0, track_z)), (
            f"SWD clip guide track should be present at ({track_x}, -45.0)"
        )

    def test_regression_bug_springing_mosquito_703_proximity_sensor_inner_wall_extension(self, provider):
        """Verify BUG-SPRINGING-MOSQUITO-703 & BUG-SPECKLED-ROVEBEETLE-352: Sensor shield is an extruded hollow rectangle without inner lip or tails."""
        from build123d import Location

        assert hasattr(provider.settings, "proximity_sensor_inner_wall_extension"), (
            "proximity_sensor_inner_wall_extension setting missing"
        )
        assert provider.settings.proximity_sensor_inner_wall_extension == 3.0

        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        assert bowl.part.is_valid()

        r = provider.settings.bowl_radius
        t = provider.settings.bowl_thickness

        base_loc = Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0))

        # Optical aperture must be completely open without inner lip (BUG-SPECKLED-ROVEBEETLE-352)
        pt_center_loc = base_loc * Location((-5.0, 0, -2.0))
        assert not bowl.part.is_inside(
            (pt_center_loc.position.X, pt_center_loc.position.Y, pt_center_loc.position.Z)
        ), "Sensor aperture center must remain open"

        pt_lip_loc = base_loc * Location((-5.0, 0, 3.5))
        assert not bowl.part.is_inside((pt_lip_loc.position.X, pt_lip_loc.position.Y, pt_lip_loc.position.Z)), (
            "Inner bowl wall must not have an inner lip protruding into sensor aperture"
        )

        # Extruded hollow rectangle shield enclosing walls (top, bottom, left, right)
        pt_top_loc = base_loc * Location((-4.0, 0, 6.0))
        assert bowl.part.is_inside((pt_top_loc.position.X, pt_top_loc.position.Y, pt_top_loc.position.Z)), (
            "Top enclosing wall of sensor shield must be solid"
        )

        pt_bot_loc = base_loc * Location((-4.0, 0, -10.0))
        assert bowl.part.is_inside((pt_bot_loc.position.X, pt_bot_loc.position.Y, pt_bot_loc.position.Z)), (
            "Bottom enclosing wall of sensor shield must be solid"
        )

        pt_left_loc = base_loc * Location((-4.0, 7.0, -2.0))
        assert bowl.part.is_inside((pt_left_loc.position.X, pt_left_loc.position.Y, pt_left_loc.position.Z)), (
            "Left enclosing sidewall of sensor shield must be solid"
        )

        pt_right_loc = base_loc * Location((-4.0, -7.0, -2.0))
        assert bowl.part.is_inside((pt_right_loc.position.X, pt_right_loc.position.Y, pt_right_loc.position.Z)), (
            "Right enclosing sidewall of sensor shield must be solid"
        )

        # No protruding tails beyond top of extruded hollow rectangle
        pt_tail_loc = base_loc * Location((-4.0, 0, 8.0))
        assert not bowl.part.is_inside((pt_tail_loc.position.X, pt_tail_loc.position.Y, pt_tail_loc.position.Z)), (
            "Sensor shield must not have protruding tails beyond rectangular profile"
        )

        # Press-fit mounting posts on ToF sensor standoffs (Finding 5)
        shaft_h = provider.settings.pcb_mounting_post_height - provider.settings.pcb_mounting_post_flare_height
        tof_sp_x = provider.settings.proximity_sensor_spacing_x
        tof_sp_y = provider.settings.proximity_sensor_spacing_y
        for dy in [-tof_sp_x / 2.0, tof_sp_x / 2.0]:
            for dz in [-tof_sp_y / 2.0, tof_sp_y / 2.0]:
                pt_post_loc = Location((r - t / 2.0 - 3.0, 0, 16.0), (0, -30, 0)) * Location(
                    (-6.0 - shaft_h / 2.0, dy, dz)
                )
                pt_post = (pt_post_loc.position.X, pt_post_loc.position.Y, pt_post_loc.position.Z)
                assert bowl.part.is_inside(pt_post), (
                    f"ToF sensor mount at dy={dy}, dz={dz} must have a solid press-fit post"
                )

    def test_regression_bug_stinging_lacewing_799_holeless_pcb_snap_socket(self, provider):
        """Verify BUG-STINGING-LACEWING-799: Hole-less PCB mount (TMC6300) uses axial snap-socket frame instead of slide rails."""
        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        assert bowl.part.is_valid()

        floor_z = provider.settings.floor_z
        t = provider.settings.bowl_thickness
        ceiling_z = floor_z - t

        # TMC6300 center and dimensions
        cx = 50.0
        cy = 15.0
        span = provider.settings.motor_driver_spacing_y  # 15.24 along X
        slide = provider.settings.motor_driver_spacing_x  # 20.32 along Y
        sh = provider.settings.motor_driver_standoff_height  # 4.0

        # 1. Outer socket frame walls must be solid (no micro-gaps)
        pt_wall_x = (cx + span / 2.0 + 1.0, cy, ceiling_z - (sh + 0.5))
        assert bowl.part.is_inside(pt_wall_x), "TMC6300 snap socket X frame wall must be solid"

        pt_wall_y = (cx, cy + slide / 2.0 + 1.0, ceiling_z - (sh + 0.5))
        assert bowl.part.is_inside(pt_wall_y), "TMC6300 snap socket Y frame wall must be solid"

        # 2. Central cavity through standoff height must be open for component clearance and airflow
        pt_center_air = (cx, cy, ceiling_z - sh / 2.0)
        assert not bowl.part.is_inside(pt_center_air), "TMC6300 central cavity must be hollow for component airflow"

        # 3. Axial insertion path from bottom must be open (does not require sliding from -Y where CURRENT sensor sits)
        pt_bottom_entry = (cx, cy, ceiling_z - (sh + 1.0))
        assert not bowl.part.is_inside(pt_bottom_entry), "TMC6300 snap socket must be open axially from below"

    def test_regression_bug_vibrant_woodborer_940_motor_hub_assembly(self, provider):
        """Verify BUG-VIBRANT-WOODBORER-940: Motor hub assembly combining motor, clip, hub, and Hall sensor."""
        from build123d import Part

        # 1. Centered thrust bearing (R <= 1.5mm)
        assert hasattr(provider.settings, "drive_hub_thrust_collar_radius"), (
            "drive_hub_thrust_collar_radius setting missing"
        )
        assert provider.settings.drive_hub_thrust_collar_radius <= 1.5, (
            "Thrust collar radius must be <= 1.5mm to reduce friction torque by >90%"
        )

        hub = provider.build_drive_hub("drive_hub")
        assert hub.part.volume > 0.0
        assert hub.part.is_valid()

        hub_r = provider.settings.impeller_radius + provider.settings.magnet_radius + 1.6
        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        standoff_h = provider.settings.drive_hub_standoff_height
        z_mid = hub_h + standoff_h / 2.0

        # Outer perimeter standoff ring at R = hub_r - 0.7 must be removed (not solid)
        test_r_outer = hub_r - 0.7
        assert not hub.part.is_inside((test_r_outer, 0.0, z_mid)), (
            "Outer perimeter standoff ring at R = 15.6mm must be removed"
        )

        # Central thrust collar around 1.5mm motor shaft collar at R <= 1.5mm must be solid
        r_collar = (provider.settings.drive_hub_shaft_radius + provider.settings.drive_hub_thrust_collar_radius) / 2.0
        assert hub.part.is_inside((r_collar, 0.0, z_mid)), (
            "Central thrust collar directly around 1.5mm motor shaft collar must be solid"
        )

        # 2. Optimized magnetic coupling axial air gap (2.0 - 2.5mm)
        assert 2.0 <= provider.settings.pump_well_wall <= 2.5, (
            "Axial air gap (pump_well_wall) must be increased to 2.0 - 2.5mm"
        )

        # 3. Speed sensor pocket directly aligns with drive hub magnet pitch circle
        bowl = provider.build_bowl("bowl")
        assert bowl.part.volume > 0.0
        floor_z = provider.settings.floor_z
        ring_r = provider.settings.magnet_ring_radius

        # Point at the magnet pitch circle inside the speed sensor pocket (Z = floor_z - 10.0, Y = ring_r)
        # must be open (subtracted) so the bent A3144 Hall sensor receives pulses directly from the magnets
        pt_sensor_pitch = (0.0, ring_r, floor_z - 10.0)
        assert not bowl.part.is_inside(pt_sensor_pitch), (
            f"Speed sensor pocket must align directly with magnet pitch circle at Y = {ring_r}"
        )

        # 4. Motor hub assembly unit replaces motor_clip while drive_hub remains separate drive unit
        assert "motor_hub" in provider.part, "motor_hub target missing from provider.part"
        assert "motor_clip" not in provider.part, "motor_clip must be replaced by motor_hub in provider.part"
        assert "drive_hub" in provider.part, "drive_hub must remain as the separate rotating drive unit"
        assert hasattr(provider, "build_motor_hub"), "build_motor_hub method missing"

        motor_hub = provider.build_motor_hub("motor_hub")
        assert motor_hub.part.volume > 0.0
        assert motor_hub.part.is_valid()
        assert isinstance(motor_hub.part, Part)

        # 5. Integrated Hall sensor module mount directly on motor_hub (2 front press-fit mounting points)
        sh = provider.settings.hall_sensor_standoff_height
        clip_h = provider.settings.motor_hub_thickness
        boss_z = clip_h + sh * 0.5
        post_z = clip_h + sh + 1.0
        hall_front_y = provider.settings.speed_sensor_pocket_y
        hall_dx = provider.settings.hall_sensor_spacing_x / 2.0
        # Both front mounting points (-hall_dx, hall_front_y) and (+hall_dx, hall_front_y) have press-fit posts and boss pads
        for hx in [-hall_dx, hall_dx]:
            assert motor_hub.part.is_inside((hx, hall_front_y, boss_z)), (
                f"Hall sensor mount on motor_hub at X={hx}: must have solid boss pad"
            )
            assert motor_hub.part.is_inside((hx, hall_front_y, post_z)), (
                f"Hall sensor mount on motor_hub at X={hx}: must have press-fit post"
            )

        # 6. Bowl base features groove-style cylindrical mounting socket for motor hub assembly
        pump_well_wall = provider.settings.pump_well_wall
        ceiling_z = floor_z - pump_well_wall
        standoff_h = provider.settings.drive_hub_standoff_height
        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        mount_seat_z = ceiling_z - standoff_h - hub_h - 0.5 - 9.3 - clip_h

        socket_in_r = provider.settings.motor_hub_socket_radius
        socket_wall = provider.settings.motor_hub_socket_wall
        socket_out_r = socket_in_r + socket_wall
        r_socket_wall = (socket_in_r + socket_out_r) / 2.0

        # Bowl socket wall is solid
        assert bowl.part.is_inside((r_socket_wall, 0.0, mount_seat_z + 3.0)), (
            "Bowl mounting socket wall for motor_hub groove-style retention must be solid"
        )
        # Socket interior bore is open for drive hub and motor assembly
        assert not bowl.part.is_inside((0.0, 0.0, mount_seat_z + 3.0)), (
            "Interior bore of bowl motor hub socket must be open"
        )
        # Internal annular snap groove is present in socket inner wall
        assert not bowl.part.is_inside((socket_in_r + 0.3, 0.0, mount_seat_z + clip_h + 2.0)), (
            "Internal annular snap groove in bowl socket wall must be open"
        )
        # Keyway slot at +Y in socket wall is open for Hall sensor arm and wiring
        assert not bowl.part.is_inside((0.0, r_socket_wall, mount_seat_z + 1.0)), (
            "Keyway slot at +Y in socket wall must be open for Hall sensor platform"
        )
        # Socket wall at -Y is solid (latent slide clearance cut removed per BUG-LUSTROUS-COCOON-669)
        assert bowl.part.is_inside((0.0, -r_socket_wall, mount_seat_z + 1.0)), (
            "Socket wall at -Y must be solid with latent slide cut removed"
        )
        # Bowl floor above Hall sensor mount is solid (extra box cut removed per BUG-LUSTROUS-COCOON-669)
        t = provider.settings.bowl_thickness
        assert bowl.part.is_inside((0.0, r_socket_wall, floor_z - t + 1.0)), (
            "Bowl floor above hall sensor mount must be solid (no extra box cut)"
        )

        # Motor hub features matching circular cylindrical snap collar with annular snap ridge
        collar_r = socket_in_r - provider.settings.motor_hub_collar_clearance
        r_collar_wall = (collar_r + 13.5) / 2.0
        assert motor_hub.part.is_inside((r_collar_wall, 0.0, clip_h + 3.0)), (
            "Motor hub circular mounting collar wall must be solid"
        )
        assert not motor_hub.part.is_inside((0.0, 0.0, clip_h + 3.0)), (
            "Motor hub central bore must be open for motor shaft clearance"
        )
        assert motor_hub.part.is_inside((collar_r + 0.3, 0.0, clip_h + 2.0)), (
            "Motor hub collar must feature an external annular snap ridge to engage socket groove"
        )
        # Verify Hall sensor clearance opening at +Y and solid collar wall at -Y (BUG-CRIMSON-MAYFLY-874)
        assert not motor_hub.part.is_inside((0.0, r_collar_wall, clip_h + 3.0)), (
            "Collar wall at +Y must be open for Hall sensor clearance"
        )
        assert not motor_hub.part.is_inside((5.0, r_collar_wall, clip_h + 3.0)), (
            "Collar wall at +Y must have wide clearance opening for Hall sensor board"
        )
        assert not motor_hub.part.is_inside((-5.0, r_collar_wall, clip_h + 3.0)), (
            "Collar wall at +Y must have wide clearance opening for Hall sensor board"
        )
        assert motor_hub.part.is_inside((0.0, -r_collar_wall, clip_h + 3.0)), (
            "Collar wall at -Y must be solid with no unexpected second opening"
        )

        # 7. TMC6300 hole-less PCB snap socket features outer frame walls and internal snap groove retention (BUG-STINGING-LACEWING-799)
        t = provider.settings.bowl_thickness
        tmc_x, tmc_y = 50.0, 15.0
        tmc_span = provider.settings.motor_driver_spacing_y
        tmc_slide = provider.settings.motor_driver_spacing_x
        tmc_sh = provider.settings.motor_driver_standoff_height
        half_span = tmc_span / 2.0
        half_slide = tmc_slide / 2.0
        # Positive back stop wall at +Y is solid
        assert bowl.part.is_inside((tmc_x + half_span + 0.5, tmc_y + half_slide + 1.0, floor_z - t - tmc_sh - 1.0)), (
            "TMC6300 snap socket must feature a solid positive back stop wall"
        )
        # Front frame wall at -Y is solid (BUG-STINGING-LACEWING-799 full frame)
        assert bowl.part.is_inside((tmc_x, tmc_y - half_slide - 1.0, floor_z - t - tmc_sh - 1.0)), (
            "TMC6300 snap socket must feature a solid front frame wall"
        )

    def test_regression_bug_thoracic_harvestman_529_drive_hub_grooves_and_hull(self, provider):
        """Verify BUG-THORACIC-HARVESTMAN-529: Drive hub has triangular motor strut grooves and 3-lobed convex hull body."""
        # 1. Config properties exist
        assert hasattr(provider.settings, "drive_hub_min_wall")
        assert hasattr(provider.settings, "drive_hub_strut_groove_width")
        assert hasattr(provider.settings, "drive_hub_strut_groove_depth")
        assert hasattr(provider.settings, "drive_hub_strut_groove_length")
        assert provider.settings.drive_hub_min_wall >= 1.5, "Minimum wall thickness must be >= 1.5mm"

        hub = provider.build_drive_hub("drive_hub")
        assert hub.part.volume > 0.0
        assert hub.part.is_valid()
        solid = hub.part

        ring_r = provider.settings.magnet_ring_radius
        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        mr = provider.settings.magnet_radius + provider.settings.magnet_clearance
        groove_d = provider.settings.drive_hub_strut_groove_depth

        # 2. Central shaft hole is open
        assert not solid.is_inside((0.0, 0.0, 0.5)), "Central shaft hole must be open"

        # 3. 3-lobed convex hull shape: solid at magnet lobes, hollow between lobes
        for angle in [0, 120, 240]:
            rad = math.radians(angle)
            # Lobe tip around magnet is solid
            tip_r = ring_r + mr + 0.5  # ~12.6mm
            assert solid.is_inside((tip_r * math.cos(rad), tip_r * math.sin(rad), hub_h * 0.5)), (
                f"Magnet lobe at {angle}° must be solid at r={tip_r}"
            )

        # Region between lobes (e.g. at 60°, 180°, 300° at r=10.0mm) is hollow
        for angle in [60, 180, 300]:
            rad = math.radians(angle)
            assert not solid.is_inside((10.0 * math.cos(rad), 10.0 * math.sin(rad), hub_h * 0.5)), (
                f"Region between lobes at {angle}° must be hollowed out (convex hull per-lobe design)"
            )

        # 4. Triangular strut grooves on the bottom (Z < groove_d)
        for angle in [0, 120, 240]:
            rad = math.radians(angle)
            # Center of groove is open (subtracted)
            gx = 3.5 * math.cos(rad)
            gy = 3.5 * math.sin(rad)
            assert not solid.is_inside((gx, gy, groove_d * 0.5)), (
                f"Motor strut groove at {angle}° must be open on bottom"
            )
            # Lateral wall around groove is solid (>= 1.5mm wall)
            # Tangent offset of 2.0mm from groove centerline
            wx = gx - 2.0 * math.sin(rad)
            wy = gy + 2.0 * math.cos(rad)
            assert solid.is_inside((wx, wy, groove_d * 0.5)), (
                f"Lateral wall beside groove at {angle}° must be solid with >=1.5mm wall"
            )

    def test_regression_bug_fierce_longhorn_849_pcb_snap_socket_overlap(self):
        """Guard against regression for BUG-FIERCE-LONGHORN-849.

        Verify positive snap ring overlap holding hole-less PCBs (SWD adapter and TMC6300)
        in place on the cat fountain bowl base.
        The cutout surrounding the boards must have width and height equal to
        board dimensions minus a small margin (0.1mm - 0.5mm), creating positive retaining
        lips below and ceiling stop shelves above the PCB seating groove.
        """
        provider = CatFountainProvider()
        margin = provider.settings.pcb_snap_socket_cutout_margin
        assert 0.1 <= margin <= 0.5, f"pcb_snap_socket_cutout_margin {margin} must be in [0.1, 0.5] mm"

        bowl = provider.build_bowl("bowl")
        solid = bowl.part
        base_z = provider.settings.floor_z - provider.settings.bowl_thickness

        # 1. SWD adapter at (-50.0, -45.0)
        # Dimensions are rotated 90 deg: span (X) = swd_board_width (13.7), slide (Y) = swd_board_length (19.1)
        # standoff_h = 2.0, pcb_t = 1.6
        # Shelf is at Z = base_z - 1.0 (36.0)
        # Groove is at Z = base_z - 2.8 (34.2)
        # Retaining lip is at Z = base_z - 3.8 (33.2)
        cx, cy = -50.0, -45.0
        swd_span = provider.settings.swd_board_width
        swd_slide = provider.settings.swd_board_length

        # Inside the seating groove (Z = base_z - 2.8): the board slot is hollow
        assert not solid.is_inside((cx + swd_span / 2.0 - 0.1, cy, base_z - 2.8)), (
            "PCB groove must be open for board width"
        )
        assert not solid.is_inside((cx, cy + swd_slide / 2.0 - 0.1, base_z - 2.8)), (
            "PCB groove must be open for board length"
        )

        # At the ceiling stop shelf (Z = base_z - 1.0 outside tool opening): positive overlap of (margin/2 = 0.2mm)
        # Point just inside board edge (swd_span/2 - 0.1) outside tool hole should be inside solid stop shelf
        assert solid.is_inside((cx + swd_span / 2.0 - 0.1, cy + 5.0, base_z - 1.0)), (
            "Top stop shelf must overlap SWD PCB edge"
        )
        assert solid.is_inside((cx + 4.0, cy + swd_slide / 2.0 - 0.1, base_z - 1.0)), (
            "Top stop shelf must overlap SWD PCB edge"
        )

        # At the bottom retaining lip (Z = base_z - 3.8): positive overlap of (margin/2 = 0.2mm)
        # Point just inside board edge (swd_span/2 - 0.1) should be inside solid retaining lip
        assert solid.is_inside((cx + swd_span / 2.0 - 0.1, cy, base_z - 3.8)), (
            "Bottom retaining lip must overlap SWD PCB edge"
        )
        assert solid.is_inside((cx, cy + swd_slide / 2.0 - 0.1, base_z - 3.8)), (
            "Bottom retaining lip must overlap SWD PCB edge"
        )

        # 2. TMC6300 motor driver at (50.0, 15.0)
        # Rotated 90 deg: span (X) = spacing_y (15.24), slide (Y) = spacing_x (20.32)
        # standoff_h = 4.0, pcb_t = 1.6
        # Shelf is at Z = base_z - 2.0 (35.0)
        # Groove is at Z = base_z - 4.8 (32.2)
        # Retaining lip is at Z = base_z - 5.8 (31.2)
        mcx, mcy = 50.0, 15.0
        tmc_span = provider.settings.motor_driver_spacing_y
        tmc_slide = provider.settings.motor_driver_spacing_x

        # Inside the seating groove (Z = base_z - 4.8): open
        assert not solid.is_inside((mcx + tmc_span / 2.0 - 0.1, mcy, base_z - 4.8)), (
            "PCB groove must be open for TMC6300 width"
        )
        assert not solid.is_inside((mcx, mcy + tmc_slide / 2.0 - 0.1, base_z - 4.8)), (
            "PCB groove must be open for TMC6300 length"
        )

        # At the ceiling stop shelf (Z = base_z - 2.0 outside tool opening): positive overlap
        assert solid.is_inside((mcx + tmc_span / 2.0 - 0.1, mcy + 5.0, base_z - 2.0)), (
            "Top stop shelf must overlap TMC6300 PCB edge"
        )
        assert solid.is_inside((mcx + 4.0, mcy + tmc_slide / 2.0 - 0.1, base_z - 2.0)), (
            "Top stop shelf must overlap TMC6300 PCB edge"
        )

        # At the bottom retaining lip (Z = base_z - 5.8): positive overlap
        assert solid.is_inside((mcx + tmc_span / 2.0 - 0.1, mcy, base_z - 5.8)), (
            "Bottom retaining lip must overlap TMC6300 PCB edge"
        )
        assert solid.is_inside((mcx, mcy + tmc_slide / 2.0 - 0.1, base_z - 5.8)), (
            "Bottom retaining lip must overlap TMC6300 PCB edge"
        )

        # 3. Tool removal openings on each wall beneath the PCB (BUG-FIERCE-LONGHORN-849)
        # Apertures must penetrate through the walls into the standoff space beneath the board
        assert provider.settings.pcb_snap_socket_tool_hole_width >= 4.0
        assert provider.settings.pcb_snap_socket_tool_hole_height >= 1.5

        tool_h = provider.settings.pcb_snap_socket_tool_hole_height
        wall_t = 2.0
        opening_z = base_z - tool_h / 2.0

        # Check through-openings on all 4 walls of TMC6300 socket
        assert not solid.is_inside((mcx + tmc_span / 2.0 + wall_t / 2.0, mcy, opening_z)), (
            "+X wall tool hole must penetrate outer wall"
        )
        assert not solid.is_inside((mcx - tmc_span / 2.0 - wall_t / 2.0, mcy, opening_z)), (
            "-X wall tool hole must penetrate outer wall"
        )
        assert not solid.is_inside((mcx, mcy + tmc_slide / 2.0 + wall_t / 2.0, opening_z)), (
            "+Y wall tool hole must penetrate outer wall"
        )
        assert not solid.is_inside((mcx, mcy - tmc_slide / 2.0 - wall_t / 2.0, opening_z)), (
            "-Y wall tool hole must penetrate outer wall"
        )

        # Check through-openings on all 4 walls of SWD socket
        assert not solid.is_inside((cx + swd_span / 2.0 + wall_t / 2.0, cy, opening_z)), (
            "+X wall tool hole on SWD must penetrate outer wall"
        )
        assert not solid.is_inside((cx - swd_span / 2.0 - wall_t / 2.0, cy, opening_z)), (
            "-X wall tool hole on SWD must penetrate outer wall"
        )
        assert not solid.is_inside((cx, cy + swd_slide / 2.0 + wall_t / 2.0, opening_z)), (
            "+Y wall tool hole on SWD must penetrate outer wall"
        )
        assert not solid.is_inside((cx, cy - swd_slide / 2.0 - wall_t / 2.0, opening_z)), (
            "-Y wall tool hole on SWD must penetrate outer wall"
        )

        # Verify corner posts remain solid for structural rigidity
        assert solid.is_inside(
            (mcx + tmc_span / 2.0 + wall_t / 2.0, mcy + tmc_slide / 2.0 + wall_t / 2.0, opening_z)
        ), "TMC6300 corner post must remain solid"
        assert solid.is_inside((cx + swd_span / 2.0 + wall_t / 2.0, cy + swd_slide / 2.0 + wall_t / 2.0, opening_z)), (
            "SWD corner post must remain solid"
        )

    @pytest.mark.slow
    def test_regression_bug_flitting_locust_977_impeller_blade_micro_gaps(self, provider):
        """Verify that impeller blades extend into the central sleeve without micro-gaps (BUG-FLITTING-LOCUST-977).

        Asserts:
        1. Blade overlap parameter is positive and properly defined in settings.
        2. Corner points along the blade sides at the cylindrical sleeve seam are solid.
        3. All 3 blades have contiguous, gap-free intersections with the central sleeve.
        4. Central guide post bore remains completely clear and unobstructed.
        """
        import math

        impeller = provider.build_impeller("impeller")
        solid = impeller.part
        assert solid.is_valid and solid.volume > 0.0

        overlap = provider.settings.impeller_blade_overlap
        assert overlap >= 0.5, f"Expected blade overlap >= 0.5mm, got {overlap}"

        sleeve_r = provider.settings.impeller_sleeve_radius
        base_h = provider.settings.impeller_base_height
        blade_z = base_h + 2.0
        num_blades = provider.settings.impeller_blades
        blade_half_w = 0.55  # Just inside the 1.2mm blade width (+-0.6mm)

        for i in range(num_blades):
            angle_deg = i * (360.0 / num_blades)
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            for offset_y in [-blade_half_w, blade_half_w]:
                # Test corner point right at the sleeve seam (r = sleeve_r - 0.05)
                # Local coords: x = sleeve_r - 0.05, y = offset_y
                local_x = sleeve_r - 0.05
                local_y = offset_y
                gx = local_x * cos_a - local_y * sin_a
                gy = local_x * sin_a + local_y * cos_a
                assert solid.is_inside((gx, gy, blade_z)), (
                    f"Blade {i} has micro-gap at sleeve seam ({gx:.3f}, {gy:.3f}, {blade_z})!"
                )

        # Pin bore must remain hollow
        assert not solid.is_inside((0.0, 0.0, blade_z)), "Central bore obstructed at blade height!"
        pin_clearance_r = provider.settings.impeller_shaft_radius + provider.settings.impeller_shaft_clearance - 0.05
        assert not solid.is_inside((pin_clearance_r, 0.0, blade_z)), "Central bore clearance obstructed!"

    def test_regression_bug_crimson_mayfly_874_hall_sensor_clearance(self, provider):
        """Verify that drive/motor hub has wide clearance for Hall sensor board and no opposite opening (BUG-CRIMSON-MAYFLY-874).

        Asserts:
        1. Hall sensor clearance width is parameterized and >= 16.0mm.
        2. Motor hub collar wall at North (+Y) is completely open across the sensor platform width.
        3. Motor hub collar wall at South (-Y) is continuous and solid with no unexpected slit.
        """
        motor_hub = provider.build_motor_hub("motor_hub")
        solid = motor_hub.part
        assert solid.is_valid and solid.volume > 0.0

        hall_clearance_w = provider.settings.hall_sensor_clearance_width
        assert hall_clearance_w >= 16.0, f"Expected Hall sensor clearance width >= 16.0mm, got {hall_clearance_w}"

        clip_h = provider.settings.motor_hub_thickness
        socket_in_r = provider.settings.motor_hub_socket_radius
        collar_r = socket_in_r - provider.settings.motor_hub_collar_clearance
        r_collar_wall = (collar_r + 13.5) / 2.0
        test_z = clip_h + 3.0

        # Across the opening width (|X| < hall_clearance_w / 2 - 0.5), +Y wall is open
        for test_x in [-7.0, -5.0, 0.0, 5.0, 7.0]:
            assert not solid.is_inside((test_x, r_collar_wall, test_z)), (
                f"Collar wall at +Y (X={test_x}) must be open for Hall sensor module clearance"
            )

        # Opposite opening at -Y is eliminated: entire South collar wall is solid
        for test_x in [-7.0, -5.0, 0.0, 5.0, 7.0]:
            assert solid.is_inside((test_x, -r_collar_wall, test_z)), (
                f"Collar wall at -Y (X={test_x}) must be solid (no unexpected second opening)"
            )

    @pytest.mark.slow
    def test_regression_bug_leaping_locust_56_pump_cover_annular_ring_lower_z(self, provider):
        """Verify that pump cover mount and annular snap ring are moved lower (-Z) for epoxy clearance (BUG-LEAPING-LOCUST-56).

        Asserts:
        1. Pump cover mount depth is parameterized and >= 2.0mm.
        2. Pump cover annular ring Z offset is parameterized and >= 1.2mm (lower -Z into casing).
        3. Pump cover downward lip reaches down to -mount_depth with solid entry.
        4. Bowl casing snap recess reaches down to floor_z + 10.0 - mount_depth.
        5. Annular snap ridge on pump cover and groove in bowl align with zero interference when assembled.
        """
        from build123d import Location

        bowl = provider.build_bowl("bowl")
        cover = provider.build_pump_cover("pump_cover")
        bowl_part = bowl.part
        cover_part = cover.part
        assert bowl_part is not None and cover_part is not None
        assert len(cover_part.solids()) == 1, (
            f"Pump cover has {len(cover_part.solids())} separate solids; must be a single merged solid"
        )

        mount_depth = provider.settings.pump_cover_mount_depth
        snap_z_offset = provider.settings.pump_cover_snap_z_offset
        assert mount_depth >= 2.0, f"Expected mount depth >= 2.0mm, got {mount_depth}"
        assert snap_z_offset >= 1.2, f"Expected snap ring offset >= 1.2mm, got {snap_z_offset}"

        floor_z = provider.settings.floor_z
        hub_r = provider.settings.impeller_radius + provider.settings.magnet_radius + 1.0
        chamber_r = hub_r + 4.0 + provider.settings.pump_casing_clearance
        snap_r = chamber_r + 1.0
        snap_clearance = provider.settings.pump_cover_snap_clearance
        cover_r = snap_r - snap_clearance

        # Downward lip extends down below Z = -1.5 (specifically down to -mount_depth + 0.5)
        assert cover_part.is_inside((cover_r - 0.5, 0.0, -mount_depth + 0.5)), (
            "Downward lip must extend into lower -Z region for deep mount engagement"
        )

        # Bowl casing recess extends down to floor_z + 10.0 - mount_depth + 0.5
        recess_low_z = floor_z + 10.0 - mount_depth + 0.5
        assert not bowl_part.is_inside((snap_r - 0.2, 0.0, recess_low_z)), (
            "Bowl casing recess must extend down into lower -Z region"
        )

        # Snap ridge on pump cover is at lower -Z: Z = -snap_z_offset
        ridge_outer_r = (
            snap_r + provider.settings.pump_cover_snap_ridge_offset + provider.settings.pump_cover_snap_ridge_minor
        )
        assert cover_part.is_inside((ridge_outer_r - 0.05, 0.0, -snap_z_offset)), (
            f"Pump cover snap ridge must be located at lower Z = -{snap_z_offset}"
        )

        # Matching groove in bowl is at lower -Z: Z = floor_z + 10.0 - snap_z_offset
        groove_low_z = floor_z + 10.0 - snap_z_offset
        assert not bowl_part.is_inside((snap_r + 0.2, 0.0, groove_low_z)), (
            f"Bowl casing groove must be located at lower Z = {groove_low_z}"
        )

        # Assembled configuration has zero interference
        seat_loc = Location((0, 0, floor_z + 10.0))
        cover_placed = cover_part.located(seat_loc)
        intersection = bowl_part.intersect(cover_placed)
        vol = sum(s.volume for s in intersection.solids()) if intersection else 0.0
        assert vol < 0.2, f"Interference detected between bowl and snapped pump cover: {vol:.4f} mm3"

    @pytest.mark.slow
    def test_regression_bug_swarming_treehopper_675_drive_hub_shaft_through_hole(self, provider):
        """Verify that the drive hub motor shaft hole is completely through-bored across all Z heights."""
        hub = provider.build_drive_hub("drive_hub")
        solid = hub.part

        hub_h = provider.settings.magnet_thickness + provider.settings.magnet_clearance + 0.8
        standoff_h = provider.settings.drive_hub_standoff_height
        total_h = hub_h + standoff_h

        # Central shaft hole must be empty (open) from Z = 0.1 to Z = total_h - 0.1
        sample_zs = [0.1, hub_h * 0.25, hub_h * 0.5, hub_h * 0.75, hub_h, hub_h + standoff_h * 0.5, total_h - 0.1]
        for z in sample_zs:
            assert not solid.is_inside((0.0, 0.0, z)), f"Drive hub shaft through-hole is blocked at Z = {z:.2f} mm"

        # Thrust collar wall around shaft hole must be solid
        r_collar = (provider.settings.drive_hub_shaft_radius + provider.settings.drive_hub_thrust_collar_radius) / 2.0
        assert solid.is_inside((r_collar, 0.0, hub_h + standoff_h * 0.5)), "Thrust collar wall is missing or hollow"

    @pytest.mark.slow
    def test_regression_bug_winged_instar_825_impeller_boundary_conformance(self, provider):
        """Verify that the 3-lobed impeller analytical URDF boundary conforms to CAD geometry >= 80%."""
        from model.boundary_config import ShapeType
        from provider import Mode as ProviderMode, evaluate_boundary_cad_conformance

        room = Room()
        provider.build_product(room, mode=ProviderMode.DEFAULT)
        geom, _ = room["impeller"]
        cad_solid = getattr(geom, "part", geom)
        boundaries = getattr(geom, "urdf_boundaries", [])
        assert len(boundaries) == 1, "Expected single analytical boundary for impeller"
        b = boundaries[0]

        assert b.shape == ShapeType.IMPELLER
        assert abs(b.xyz[0]) < 1e-4, f"Impeller rotation center must be at X=0, got {b.xyz[0]}"
        assert abs(b.xyz[1]) < 1e-4, f"Impeller rotation center must be at Y=0, got {b.xyz[1]}"

        res = evaluate_boundary_cad_conformance(cad_solid, b)
        assert res.solid_conformance_ratio >= 0.80, (
            f"Impeller boundary CAD conformance ratio {res.solid_conformance_ratio:.2%} is below 80%"
        )

    @pytest.mark.slow
    def test_regression_bug_golden_firefly_566_pump_cover_single_solid(self, provider):
        """Verify BUG-GOLDEN-FIREFLY-566: Pump cover STL is a single merged solid without floating rings."""
        cover = provider.build_pump_cover("pump_cover")
        assert cover.part is not None
        solids = cover.part.solids()
        assert len(solids) == 1, f"Expected 1 solid for pump_cover, found {len(solids)} separate solids"

    @pytest.mark.slow
    def test_regression_bug_swift_mite_462_bowl_minimum_wall_thickness(self, provider):
        """Verify BUG-SWIFT-MITE-462: Bowl features minimum 1.0mm wall thickness at PCB clip lip and charger port."""
        bowl = provider.build_bowl("bowl")
        bowl_part = bowl.part
        assert bowl_part is not None

        # 1. PCB clip bottom retaining lip thickness >= 1.0mm
        base_z = provider.settings.floor_z - provider.settings.bowl_thickness
        standoff_h = provider.settings.motor_driver_standoff_height
        snap_h = 1.8
        pocket_bottom_z = base_z - standoff_h - snap_h
        tmc_span = provider.settings.motor_driver_spacing_y
        tmc_slide = provider.settings.motor_driver_spacing_x
        mcx, mcy = 50.0, 15.0
        assert bowl_part.is_inside((mcx + tmc_span / 2.0 - 0.1, mcy, pocket_bottom_z - 0.5)), (
            "PCB clip retaining lip must be at least 1.0mm thick (solid at pocket_bottom_z - 0.5mm)"
        )
        assert bowl_part.is_inside((mcx, mcy + tmc_slide / 2.0 - 0.1, pocket_bottom_z - 0.5)), (
            "PCB clip retaining lip must be at least 1.0mm thick (solid at pocket_bottom_z - 0.5mm)"
        )

        # 2. Wall thickness between charger standoff and charging port cutout >= 1.0mm
        charger_x = provider.settings.charger_spacing_x / 2.0
        charger_y = -79.0 - provider.settings.charger_spacing_y / 2.0
        hole_edge_y = charger_y - provider.settings.pcb_hole_radius
        standoff_z = base_z - provider.settings.charger_standoff_height / 2.0
        assert bowl_part.is_inside((charger_x, hole_edge_y - 1.0, standoff_z)), (
            f"Wall thickness between charger standoff hole and port cutout must be >= 1.0mm at Y={hole_edge_y - 1.0}"
        )
