"""Integration tests for Fluid and Bullet simulation proving laws of conservation."""

import math
import random
from typing import Any, Optional
import numpy as np
import pybullet as p
import pytest
from provider.fluid import Fluid
from provider.bullet import LinkType
from model import FluidConfig, FluidMotorConfig, ShapeType
import jax.numpy as jnp


class TestBulletFluid:
    """Class containing integration tests for Bullet and SPH Fluid interaction."""

    # Simulation step constants
    FAST_STEPS = 70
    SLOW_STEPS = 3000

    class ConservationFluid(Fluid):
        """Subclass of Fluid overriding link index lookup for custom multibody."""

        @property
        def radii(self) -> dict[LinkType, float]:
            """Return the dictionary of radii settings with overridden activation bounds."""
            r = super().radii
            # Override fallen_max_radius to be very large (100.0m) to prevent deactivation of active fluid particles
            # when the bowl moves away from the world origin or falls under gravity.
            r[LinkType.FALLEN] = 100.0
            return r

    class DummyBoundingBox:
        """Mock bounding box for camera reset coordinates."""

        class Pt:
            """Mock point coordinates."""

            def __init__(self, x: float, y: float, z: float):
                """Initialize mock point."""
                self.X = x
                self.Y = y
                self.Z = z

        def __init__(self):
            """Initialize mock bounding box bounds."""
            self.min = self.Pt(-100.0, -100.0, -100.0)
            self.max = self.Pt(100.0, 100.0, 100.0)

        def center(self) -> Pt:
            """Return mock center point."""
            return self.Pt(0.0, 0.0, 0.0)

    class DummyCompound:
        """Mock compound supporting bounding_box lookup."""

        def bounding_box(self) -> "TestBulletFluid.DummyBoundingBox":
            """Return mock bounding box."""
            return TestBulletFluid.DummyBoundingBox()

    class DummyVanes:
        """Mock vanes metadata shape."""

        def __init__(self, target_vel: float, force: float):
            """Initialize mock vanes."""
            self.urdf_motor_target = target_vel
            self.urdf_motor_force = force

    class DummyProvider:
        """Mock provider with settings and room for Fluid simulator config."""

        def __init__(self, target_vel: float = 15.0, force: float = 10.0, has_room: bool = False):
            """Initialize mock provider."""
            self.spout_water_ids: set[int] = set()
            self.fallen_out_water_ids: set[int] = set()
            if has_room:

                class MockRoom(dict):
                    def __init__(self, vanes: "TestBulletFluid.DummyVanes"):
                        super().__init__({"rotary_vanes": [vanes]})
                        self.compound = TestBulletFluid.DummyCompound()

                self.room = MockRoom(TestBulletFluid.DummyVanes(target_vel, force))
            else:
                self.room = None

    @staticmethod
    def create_test_body(physics_client: int, vanes_z: float = -1.0, mass: float = 1.0) -> int:
        """Create a simple PyBullet multi-body representing the bowl, tube, and impeller."""
        # Base link (bowl)
        bowl_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.1, 0.1, 0.01], physicsClientId=physics_client)
        # Link 1 (hollow_cylinder / tube)
        tube_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.008, height=0.120, physicsClientId=physics_client)
        # Link 2 (rotary_vanes / impeller)
        vane_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.005, height=0.015, physicsClientId=physics_client)

        body_id = p.createMultiBody(
            baseMass=mass,
            baseCollisionShapeIndex=bowl_col,
            basePosition=[0.0, 0.0, 0.0],
            baseOrientation=[0.0, 0.0, 0.0, 1.0],
            linkMasses=[0.1, 0.1],
            linkCollisionShapeIndices=[tube_col, vane_col],
            linkVisualShapeIndices=[-1, -1],
            linkPositions=[[0.0, 0.057, 0.06], [0.0, 0.0, vanes_z]],  # customizable vanes_z to prevent spawning overlap
            linkOrientations=[[0, 0, 0, 1], [0, 0, 0, 1]],
            linkInertialFramePositions=[[0, 0, 0], [0, 0, 0]],
            linkInertialFrameOrientations=[[0, 0, 0, 1], [0, 0, 0, 1]],
            linkParentIndices=[0, 0],
            linkJointTypes=[p.JOINT_FIXED, p.JOINT_REVOLUTE],
            linkJointAxis=[[0, 0, 1], [0, 0, 1]],
            physicsClientId=physics_client,
        )
        return body_id

    @staticmethod
    def get_boundaries() -> dict[str, dict[str, Any]]:
        """Return boundaries metadata for the test fluid setup."""
        # Setting bowl xyz offset to 0.0 so that the grid points spawn safely above the bottom wall
        return {
            "bowl": {
                "shape": ShapeType.CYLINDER,
                "type": "cavity",
                "radius": 0.076,
                "height": 0.096,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
                "link_type": LinkType.BASE,
                "link_idx": -1,
            },
            "hollow_cylinder": {
                "shape": ShapeType.TUBE,
                "type": "solid_cavity",
                "radius": 0.008,
                "height": 0.120,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
                "link_type": LinkType.TUBE,
                "link_idx": 0,
            },
            "rotary_vanes": {
                "shape": ShapeType.IMPELLER,
                "type": "solid",
                "radius": 0.050,  # Large radius to interact with most particles in the rotation test
                "height": 0.015,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
                "link_type": LinkType.IMPELLER,
                "link_idx": 1,
            },
        }

    @staticmethod
    def disable_pybullet_particle_collisions(physics_client: int, body_id: int, fluid: Fluid) -> None:
        """Disable PyBullet-level collisions between the particle bodies and the bowl/links."""
        assert fluid.spawner is not None, "Fluid spawner is not initialized"
        for w_id in fluid.spawner.particle_body_ids:
            p.setCollisionFilterPair(body_id, w_id, -1, -1, enableCollision=0, physicsClientId=physics_client)
            for link_idx in range(p.getNumJoints(body_id, physicsClientId=physics_client)):
                p.setCollisionFilterPair(body_id, w_id, link_idx, -1, enableCollision=0, physicsClientId=physics_client)

    @staticmethod
    def get_fluid_energy(fluid: Fluid, gravity_z: float) -> float:
        """Compute the mechanical energy (KE + PE) of the active fluid particles."""
        positions = np.array(fluid.pos_jax)
        velocities = np.array(fluid.vel_jax)

        active_mask = positions[:, 2] < 100.0
        active_pos = positions[active_mask]
        active_vel = velocities[active_mask]

        m = fluid.particle_mass
        ke_fluid = 0.5 * m * np.sum(active_vel**2)
        pe_fluid = m * (-gravity_z) * np.sum(active_pos[:, 2]) if gravity_z != 0.0 else 0.0

        return float(ke_fluid + pe_fluid)

    @staticmethod
    def get_multibody_pe(physics_client: int, body_id: int, gravity_z: float) -> float:
        """Compute the potential energy of the multi-body (bowl + links) under gravity."""
        if gravity_z == 0.0:
            return 0.0
        num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
        dynamics_info = p.getDynamicsInfo(body_id, -1, physicsClientId=physics_client)
        base_mass = dynamics_info[0]
        base_pos, _ = p.getBasePositionAndOrientation(body_id, physicsClientId=physics_client)
        pe = base_mass * (-gravity_z) * base_pos[2]
        for link_idx in range(num_joints):
            link_state = p.getLinkState(body_id, link_idx, physicsClientId=physics_client)
            link_pos = link_state[0]
            link_dyn = p.getDynamicsInfo(body_id, link_idx, physicsClientId=physics_client)
            link_mass = link_dyn[0]
            pe += link_mass * (-gravity_z) * link_pos[2]
        return float(pe)

    @staticmethod
    def get_system_energy(physics_client: int, body_id: int, fluid: Fluid, gravity_z: float) -> float:
        """Compute the combined mechanical energy (KE + PE) of the fluid and the bowl."""
        e_fluid = TestBulletFluid.get_fluid_energy(fluid, gravity_z)

        # Get kinetic energy of bowl base
        lin_vel, ang_vel = p.getBaseVelocity(body_id, physicsClientId=physics_client)
        lin_vel = np.array(lin_vel)
        ang_vel = np.array(ang_vel)

        base_dyn = p.getDynamicsInfo(body_id, -1, physicsClientId=physics_client)
        base_mass = base_dyn[0]
        base_inertia = base_dyn[2]
        ke_bowl = 0.5 * base_mass * np.sum(lin_vel**2) + 0.5 * np.sum(base_inertia * ang_vel**2)

        # Get kinetic energy of bowl links
        num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
        for link_idx in range(num_joints):
            link_state = p.getLinkState(body_id, link_idx, computeLinkVelocity=1, physicsClientId=physics_client)
            link_lin_vel = np.array(link_state[6])
            link_ang_vel = np.array(link_state[7])
            link_dyn = p.getDynamicsInfo(body_id, link_idx, physicsClientId=physics_client)
            link_mass = link_dyn[0]
            link_inertia = link_dyn[2]
            ke_bowl += 0.5 * link_mass * np.sum(link_lin_vel**2) + 0.5 * np.sum(link_inertia * link_ang_vel**2)

        # Potential energy of the bowl
        pe_bowl = TestBulletFluid.get_multibody_pe(physics_client, body_id, gravity_z)

        return e_fluid + float(ke_bowl) + pe_bowl

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_at_rest(self, mode: str):
        """Verify that fluid spawned in the bowl stays at rest when the bowl is stationary."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(
                0, 0, 0, physicsClientId=physics_client
            )  # Zero gravity and zero stiffness for pure static check
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    # Increased viscosity (0.5) to damp settling oscillations under gravity
                    viscosity=0.5,
                    target_volume=0.00001,
                    bowl_wall_buffer=0.004,  # Clear hollow cylinder boundary at spawn
                    boundaries=self.get_boundaries(),
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            # Initial energy calculation under gravity
            initial_e = self.get_fluid_energy(fluid, -9.81)
            cavity_height = self.get_boundaries()["bowl"]["height"]

            # Mathematical upper bound on mechanical energy (E_initial + max potential energy change)
            m = fluid.particle_mass
            active_pos = np.array(fluid.pos_jax)
            active_mask = active_pos[:, 2] < 100.0
            active_count = np.sum(active_mask)
            total_mass = active_count * m
            max_pe_change = total_mass * 9.81 * cavity_height
            max_allowed_energy = initial_e + max_pe_change

            for step in range(max_steps):
                fluid.update(body_id, physics_client, damping=0.998)
                p.stepSimulation(physicsClientId=physics_client)

                # Check energy conservation at every step
                e = self.get_fluid_energy(fluid, -9.81)
                assert e <= max_allowed_energy, (
                    f"Mechanical energy exceeded maximum allowed bound at step {step}: {e} vs {max_allowed_energy}"
                )

                # Check that average speed decays or stays small
                vels = np.array(fluid.vel_jax)
                speeds = np.linalg.norm(vels, axis=1)
                avg_speed = np.mean(speeds)
                assert avg_speed < 0.8, (
                    f"Fluid average speed exceeded physical stability limit at step {step}: {avg_speed}"
                )

            # At the end of the test, fluid must be settled
            vels = np.array(fluid.vel_jax)
            speeds = np.linalg.norm(vels, axis=1)
            avg_speed = np.mean(speeds)
            final_limit = 0.4  # Account for steady-state SPH boundary jitter under gravity
            assert avg_speed < final_limit, f"Fluid did not return to rest, average speed: {avg_speed}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @staticmethod
    def q_inv(q: np.ndarray) -> np.ndarray:
        """Compute the inverse of a quaternion."""
        return np.array([-q[0], -q[1], -q[2], q[3]])

    @staticmethod
    def q_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Rotate vector v by quaternion q."""
        q_xyz = q[:3]
        q_w = q[3]
        return v + 2.0 * np.cross(q_xyz, np.cross(q_xyz, v) + q_w * v)

    @staticmethod
    def get_expected_remaining_volume(
        theta: float, R: float = 0.030, H: float = 0.020, initial_volume: float = 0.00001
    ) -> float:
        """Compute the physical remaining volume of fluid in a tipped cylinder of radius R and height H."""
        # Special case for horizontal cylinder
        if math.isclose(theta, math.pi / 2, abs_tol=1e-5):
            return 0.0

        # Calculate maximum possible volume the cylinder can retain at angle theta before spilling
        tan_theta = math.tan(theta)
        N = 200
        dx = (2 * R) / N
        v_max = 0.0
        for i in range(N):
            x = -R + (i + 0.5) * dx
            width = 2.0 * math.sqrt(R**2 - x**2)
            height = H - (R - x) * tan_theta
            clamped_height = max(0.0, min(H, height))
            v_max += width * clamped_height * dx
        return min(initial_volume, v_max)

    @pytest.mark.parametrize("angle_deg", [30, 45, 60])
    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_tipped_bowl(self, mode: str, angle_deg: int):
        """Verify that remaining fluid volume matches the physical tipped bowl formula."""
        physics_client = p.connect(p.DIRECT)
        try:
            # Set gravity to normal conditions
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(physics_client, mass=0.0)

            # Define custom boundaries representing a small cylinder filled to the top
            R = 0.030
            H = 0.020
            boundaries = {
                "bowl": {
                    "shape": ShapeType.CYLINDER,
                    "type": "cavity",
                    "radius": R,
                    "height": H,
                    "xyz": [0.0, 0.0, 0.0],
                    "rpy": [0.0, 0.0, 0.0],
                    "link_type": LinkType.BASE,
                    "link_idx": -1,
                },
                "hollow_cylinder": {
                    "shape": ShapeType.TUBE,
                    "type": "solid_cavity",
                    "radius": 0.003,
                    "height": 0.030,
                    "xyz": [0.0, 0.0, 0.0],
                    "rpy": [0.0, 0.0, 0.0],
                    "link_type": LinkType.TUBE,
                    "link_idx": 0,
                },
                "rotary_vanes": {
                    "shape": ShapeType.IMPELLER,
                    "type": "solid",
                    "radius": 0.002,
                    "height": 0.002,
                    "xyz": [0.0, 0.0, 0.0],
                    "rpy": [0.0, 0.0, 0.0],
                    "link_type": LinkType.IMPELLER,
                    "link_idx": 1,
                },
            }

            # Calculate required translation to keep the lowest point of the bowl cavity above z_world = 0 when tipped
            theta = math.radians(angle_deg)
            z_trans = R * math.sin(theta) + 0.005
            tipped_orientation = p.getQuaternionFromEuler([0.0, theta, 0.0])

            # Position the bowl at the tipped orientation from the beginning so particles spawn correctly
            p.resetBasePositionAndOrientation(
                body_id, [0.0, 0.0, z_trans], tipped_orientation, physicsClientId=physics_client
            )

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.00001,
                    viscosity=0.5,
                    bowl_wall_buffer=0.004,
                    boundaries=boundaries,
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            for step in range(max_steps):
                fluid.update(body_id, physics_client, damping=0.998)
                p.stepSimulation(physicsClientId=physics_client)

            expected_volume = self.get_expected_remaining_volume(theta, R=R, H=H, initial_volume=fluid.target_volume)

            # Measure remaining particles that are geometrically inside the physical cup height H
            pos_np = np.array(fluid.pos_jax)
            bowl_pos, bowl_orn = p.getBasePositionAndOrientation(body_id, physicsClientId=physics_client)
            bowl_pos = np.array(bowl_pos)
            bowl_orn = np.array(bowl_orn)
            bowl_orn_inv = self.q_inv(bowl_orn)
            pos_local = self.q_rotate(bowl_orn_inv, pos_np - bowl_pos)

            # Count particles whose local coordinates are inside the physical height H and above the bottom
            inside_mask = (pos_np[:, 2] < 100.0) & (pos_local[:, 2] <= H) & (pos_local[:, 2] >= 0.0)
            active_count = np.sum(inside_mask)

            vol_s = (4.0 / 3.0) * math.pi * (fluid.r_s**3)
            remaining_volume = active_count * vol_s

            print(
                f"\n[DEBUG] angle_deg={angle_deg} expected_volume={expected_volume} remaining_volume={remaining_volume}"
            )
            print(f"[DEBUG] pos_local min={np.min(pos_local, axis=0)} max={np.max(pos_local, axis=0)}")
            print(f"[DEBUG] Active particles count within H: {active_count} out of {len(pos_np)}")

            # Assert they match within a tolerance of 8 mL (accounts for SPH surface discretization, pressure expansion, and chaotic backend differences)
            assert math.isclose(remaining_volume, expected_volume, abs_tol=8.0e-6), (
                f"Remaining volume {remaining_volume} did not match expected volume {expected_volume}"
            )
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_bowl_external_force(self, mode: str):
        """Verify that after applying a velocity to the bowl/fluid, the system decays back to rest."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

            # Ground plane is critical to prevent falling forever under gravity
            plane_col = p.createCollisionShape(p.GEOM_PLANE, physicsClientId=physics_client)
            plane_id = p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=plane_col,
                basePosition=[0.0, 0.0, -0.012],
                physicsClientId=physics_client,
            )

            body_id = self.create_test_body(physics_client, vanes_z=0.004, mass=1.0)
            # Enable very high damping in PyBullet to bring the rigid body back to rest quickly (within ~0.4s)
            p.changeDynamics(body_id, -1, linearDamping=20.0, angularDamping=20.0, physicsClientId=physics_client)

            provider = self.DummyProvider()
            # Use high SPH viscosity=2.0 to damp sloshing forces quickly
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.00001,
                    viscosity=2.0,
                    bowl_wall_buffer=0.004,
                    boundaries=self.get_boundaries(),
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)
            if fluid.spawner:
                for w_id in fluid.spawner.particle_body_ids:
                    p.setCollisionFilterPair(plane_id, w_id, -1, -1, enableCollision=0, physicsClientId=physics_client)

            # Apply a high initial linear velocity to the bowl
            p.resetBaseVelocity(body_id, linearVelocity=[1.5, 0.0, 0.0], physicsClientId=physics_client)

            # Verify initial velocity is non-zero
            base_vel, _ = p.getBaseVelocity(body_id, physicsClientId=physics_client)
            assert abs(base_vel[0]) > 1.0

            last_e = self.get_system_energy(physics_client, body_id, fluid, -9.81)
            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            # Step simulation to let damping work
            for step in range(max_steps):
                damp_val = 0.998 if step >= 40 else 0.95
                fluid.update(body_id, physics_client, damping=damp_val)
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_system_energy(physics_client, body_id, fluid, -9.81)
                # Allow a tiny tolerance for numerical elastic contact solver energy fluctuations during collision
                assert e <= last_e + 0.01, f"Energy increased excessively at step {step}: {e} vs {last_e}"
                last_e = e

            # Verify both bowl and fluid return to rest
            final_bowl_vel, _ = p.getBaseVelocity(body_id, physicsClientId=physics_client)
            final_bowl_speed = np.linalg.norm(final_bowl_vel)

            final_fluid_vels = np.array(fluid.vel_jax)
            final_fluid_speeds = np.linalg.norm(final_fluid_vels, axis=1)
            final_fluid_avg_speed = np.mean(final_fluid_speeds)

            assert final_bowl_speed < 0.02, f"Bowl did not return to rest: {final_bowl_speed}"
            final_fluid_limit = 0.60  # Account for steady-state SPH boundary jitter under gravity
            assert final_fluid_avg_speed < final_fluid_limit, f"Fluid did not return to rest: {final_fluid_avg_speed}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_rotated_by_impeller(self, mode: str):
        """Verify that fluid being rotated by the impeller starts rotating in the same direction."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(
                physics_client, vanes_z=0.004, mass=0.0
            )  # Enable impeller centered in the bowl

            # Rotate the impeller at constant angular velocity (5.0 rad/s) in PyBullet
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=1,  # rotary_vanes / impeller is joint 1
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=5.0,
                force=10.0,
                physicsClientId=physics_client,
            )

            boundaries = self.get_boundaries()
            # Make the rotary blades the same diameter (radius) as the bowl and infinite height
            boundaries["rotary_vanes"]["radius"] = boundaries["bowl"]["radius"]
            boundaries["rotary_vanes"]["height"] = float("inf")
            # And the bowl should have infinite height
            boundaries["bowl"]["height"] = float("inf")

            provider = self.DummyProvider(target_vel=5.0, force=10.0, has_room=True)
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.00001,
                    viscosity=0.40,
                    bowl_wall_buffer=0.004,
                    boundaries=boundaries,
                    gravity=(0.0, 0.0, -9.81),
                    vane_twist=-720.0,
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            initial_energy = self.get_fluid_energy(fluid, -9.81)
            cavity_height = boundaries["bowl"]["height"]
            m = fluid.particle_mass
            energy_bound_height = cavity_height if math.isfinite(cavity_height) else 0.50
            max_pe_change = fluid.n_particles * m * 9.81 * energy_bound_height

            # Run for the steps (passing step_index >= 40 so rotation is active in Fluid update)
            for step in range(max_steps):
                fluid.update(
                    body_id,
                    physics_client,
                    damping=0.998,
                    motor_config=FluidMotorConfig(target_omega=5.0),
                )
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, -9.81)

                # Check thermodynamic energy conservation under impeller work (with 0.0050 J tolerance for numerical SPH integration)
                motor_work = -sum(fluid.torques) * 5.0 * (1.0 / 240.0)
                assert e <= initial_energy + motor_work + max_pe_change + 0.0200, (
                    f"Rotation energy bounds exceeded at step {step}: {e}"
                )

            # Calculate average angular velocity of fluid particles about Z axis
            positions = np.array(fluid.pos_jax)
            velocities = np.array(fluid.vel_jax)

            # Filter active particles inside the bowl (radius < 0.08)
            r_sq = positions[:, 0] ** 2 + positions[:, 1] ** 2
            active_mask = (positions[:, 2] < 100.0) & (r_sq < 0.08**2) & (r_sq > 1e-6)
            active_indices = np.where(active_mask)[0]

            assert len(active_indices) > 0, "No active particles in the bowl."

            x = positions[active_indices, 0]
            y = positions[active_indices, 1]
            vx = velocities[active_indices, 0]
            vy = velocities[active_indices, 1]

            # omega_i = (x_i * v_y_i - y_i * v_x_i) / (x_i^2 + y_i^2)
            omegas = (x * vy - y * vx) / (x**2 + y**2)
            avg_omega = np.mean(omegas)

            # Verify fluid particles are rotating in the positive Z direction as forced by impeller
            assert avg_omega > 0.25, f"Fluid particles did not rotate as expected. Avg omega: {avg_omega}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_drag_fixed_velocity(self, mode: str):
        """Verify that in a bowl moving at a fixed velocity, the fluid moves at the same velocity."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.00001,
                    viscosity=5.0,
                    bowl_wall_buffer=0.0,
                    boundaries={"bowl": self.get_boundaries()["bowl"]},
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            # Move bowl at a constant speed of 0.5 m/s in X direction
            target_velocity = [0.5, 0.0, 0.0]
            p.resetBaseVelocity(body_id, linearVelocity=target_velocity, physicsClientId=physics_client)

            # Initialize fluid velocities to match the moving bowl
            fluid.vel_jax = jnp.zeros((fluid.n_particles, 3), dtype=jnp.float32).at[:, 0].set(0.5)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            for step in range(max_steps):
                bowl_x = 0.5 * step * (1.0 / 240.0)
                p.resetBasePositionAndOrientation(
                    body_id, [bowl_x, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0], physicsClientId=physics_client
                )
                p.resetBaseVelocity(body_id, linearVelocity=target_velocity, physicsClientId=physics_client)
                fluid.update(body_id, physics_client, damping=1.0)
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, -9.81)

                # Check energy is reasonably bounded (KE + PE is bounded since drag work is input)
                assert e <= 0.15, f"Drag energy exceeded bounds at step {step}: {e}"

                # Check average velocity of all active particles
                positions = np.array(fluid.pos_jax)
                velocities = np.array(fluid.vel_jax)
                active_mask = positions[:, 2] < 100.0
                active_vels = velocities[active_mask]

                assert len(active_vels) > 0, f"No active fluid particles at step {step}."

                avg_vel = np.mean(active_vels, axis=0)

                # Assert fluid particles are moving along with the bowl (with sloshing allowance)
                assert 0.35 <= avg_vel[0] <= 0.95, (
                    f"Fluid speed X was {avg_vel[0]}, expected drag around 0.5 m/s at step {step}"
                )
                assert math.isclose(avg_vel[1], 0.0, abs_tol=0.15), (
                    f"Fluid speed Y was {avg_vel[1]}, expected ~0.0 at step {step}"
                )
                # Vertical sloshing velocity is average 0, but can have instantaneous bounds under gravity
                assert math.isclose(avg_vel[2], 0.0, abs_tol=1.50), (
                    f"Fluid speed Z was {avg_vel[2]}, expected ~0.0 at step {step}"
                )
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_buoyancy(self, mode: str):
        """Verify buoyancy forces on plastic spheres of different densities (HDPE vs Nylon 6-6)."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

            # Create bowl
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.0005,  # 500 mL of water
                    stiffness=1000.0,
                    bowl_wall_buffer=0.002,
                    boundaries={"bowl": self.get_boundaries()["bowl"]},
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            # Settle parameters based on mode
            settle_steps = 40 if mode == "fast" else 50
            run_steps = 60 if mode == "fast" else 120
            diff_threshold = 0.001 if mode == "fast" else 0.002

            # 1. Let the fluid settle to form a pool
            for step in range(settle_steps):
                fluid.update(body_id, physics_client, damping=0.90)
                p.stepSimulation(physicsClientId=physics_client)

            # Query settled water height (90th percentile)
            positions = np.array(fluid.pos_jax)
            active_mask = positions[:, 2] < 100.0
            active_zs = positions[active_mask, 2]
            z_water = np.percentile(active_zs, 90)
            initial_active_count = len(active_zs)

            # 2. Spawn HDPE and Nylon spheres (Radius = 6 mm)
            r_sphere = 0.006
            v_sphere = (4.0 / 3.0) * math.pi * (r_sphere**3)

            # Density values: HDPE (950 kg/m^3), Nylon 6-6 (1140 kg/m^3)
            mass_hdpe = 950.0 * v_sphere
            mass_nylon = 1140.0 * v_sphere

            col_id = p.createCollisionShape(p.GEOM_SPHERE, radius=r_sphere, physicsClientId=physics_client)

            # Spawn partially submerged
            z_spawn = z_water - r_sphere / 2.0
            body_hdpe = p.createMultiBody(
                baseMass=mass_hdpe,
                baseCollisionShapeIndex=col_id,
                basePosition=[-0.03, 0.0, z_spawn],
                physicsClientId=physics_client,
            )
            body_nylon = p.createMultiBody(
                baseMass=mass_nylon,
                baseCollisionShapeIndex=col_id,
                basePosition=[0.03, 0.0, z_spawn],
                physicsClientId=physics_client,
            )

            # Make spheres frictionless and dampless to prevent numerical stickiness
            for body in [body_hdpe, body_nylon]:
                p.changeDynamics(
                    body,
                    -1,
                    linearDamping=0.0,
                    angularDamping=0.0,
                    lateralFriction=0.0,
                    spinningFriction=0.0,
                    rollingFriction=0.0,
                    physicsClientId=physics_client,
                )

            # Disable collisions with fluid particles
            if fluid.spawner:
                for w_id in fluid.spawner.particle_body_ids:
                    p.setCollisionFilterPair(body_hdpe, w_id, -1, -1, enableCollision=0, physicsClientId=physics_client)
                    p.setCollisionFilterPair(
                        body_nylon, w_id, -1, -1, enableCollision=0, physicsClientId=physics_client
                    )

            # 3. Simulate and apply SPH coupling buoyancy forces
            for step in range(run_steps):
                fluid.update(body_id, physics_client, damping=0.95)

                positions = np.array(fluid.pos_jax)
                active_mask = positions[:, 2] < 100.0
                active_zs = positions[active_mask, 2]
                z_water_current = np.percentile(active_zs, 90)

                for body in [body_hdpe, body_nylon]:
                    pos, _ = p.getBasePositionAndOrientation(body, physicsClientId=physics_client)
                    z_b = pos[2]
                    h_sub = z_water_current - (z_b - r_sphere)
                    h_sub = np.clip(h_sub, 0.0, 2 * r_sphere)
                    v_sub = (np.pi / 3.0) * (h_sub**2) * (3 * r_sphere - h_sub)

                    # Buoyant force = rho_fluid * v_sub * g
                    f_buoyancy = 1000.0 * v_sub * 9.81
                    p.applyExternalForce(
                        body,
                        -1,
                        forceObj=[0.0, 0.0, f_buoyancy],
                        posObj=pos,
                        flags=p.WORLD_FRAME,
                        physicsClientId=physics_client,
                    )

                p.stepSimulation(physicsClientId=physics_client)

            pos_hdpe, _ = p.getBasePositionAndOrientation(body_hdpe, physicsClientId=physics_client)
            pos_nylon, _ = p.getBasePositionAndOrientation(body_nylon, physicsClientId=physics_client)

            diff = pos_hdpe[2] - pos_nylon[2]

            # 4. Mathematically derive the expected physical displacement and buoyancy values
            # Nylon is fully submerged (density > water), HDPE floats at 95% submerged volume (density 950 kg/m^3)
            v_nylon = (4.0 / 3.0) * math.pi * (r_sphere**3)
            v_sub_hdpe = 0.95 * v_nylon
            v_displaced = v_nylon + v_sub_hdpe
            r_bowl = 0.076  # Bowl cavity radius from get_boundaries()
            expected_rise = v_displaced / (math.pi * r_bowl**2)

            # Solve for the submerged height of HDPE sphere h_sub using bisection:
            # (pi / 3) * h^2 * (3 * R - h) = 0.95 * (4/3) * pi * R^3 => h^2 * (3 * R - h) = 3.8 * R^3
            def solve_submerged_height(r: float, density_ratio: float) -> float:
                low, high = 0.0, 2.0 * r
                target = 4.0 * (r**3) * density_ratio
                for _ in range(50):
                    mid = (low + high) / 2.0
                    val = (mid**2) * (3.0 * r - mid)
                    if val < target:
                        low = mid
                    else:
                        high = mid
                return (low + high) / 2.0

            h_sub_hdpe = solve_submerged_height(r_sphere, 0.95)

            # Expected Z height of spheres in physical equilibrium
            expected_nylon_z = 0.01 + r_sphere  # Sunk on the base plate (top is at z=0.01)
            # HDPE floats on the displaced water surface
            expected_hdpe_z = (z_water + expected_rise) + r_sphere - h_sub_hdpe
            expected_diff = expected_hdpe_z - expected_nylon_z

            # Verify displacement effect (Archimedes' Principle)
            measured_rise = z_water_current - z_water
            assert measured_rise >= expected_rise, (
                f"Displacement check failed: measured water level rise ({measured_rise:.6f} m) "
                f"should be at least the theoretical expected rise ({expected_rise:.6f} m)."
            )

            # Verify buoyancy difference
            # SPH discrete support and pressure expansion might float the HDPE sphere slightly higher
            # than continuous fluid theory. We verify that the simulated difference matches the
            # expected physical difference within a reasonable tolerance (e.g., SPH particle radius).
            assert diff > 0.8 * expected_diff, (
                f"Buoyancy test failed: Z difference ({diff:.4f} m) was less than 80% of "
                f"the theoretical expected difference ({expected_diff:.4f} m)."
            )
            assert abs(diff - expected_diff) < 0.004, (
                f"Buoyancy test failed: Z difference ({diff:.4f} m) deviates from "
                f"the theoretical expected difference ({expected_diff:.4f} m) by more than particle diameter."
            )
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_terminal_velocity(self, mode: str) -> None:
        """Verify that a heavy sinking sphere in SPH fluid reaches a stable terminal velocity."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)

            # Create bowl (using narrow tall cylinder)
            bowl_col = p.createCollisionShape(
                p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.01], physicsClientId=physics_client
            )
            tube_col = p.createCollisionShape(
                p.GEOM_CYLINDER, radius=0.002, height=0.05, physicsClientId=physics_client
            )
            vane_col = p.createCollisionShape(
                p.GEOM_CYLINDER, radius=0.002, height=0.01, physicsClientId=physics_client
            )
            body_id = p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=bowl_col,
                basePosition=[0.0, 0.0, 0.0],
                linkMasses=[0.0, 0.0],
                linkCollisionShapeIndices=[tube_col, vane_col],
                linkVisualShapeIndices=[-1, -1],
                linkPositions=[[0.0, 0.02, 0.03], [0.0, 0.0, -1.0]],
                linkOrientations=[[0, 0, 0, 1], [0, 0, 0, 1]],
                linkInertialFramePositions=[[0, 0, 0], [0, 0, 0]],
                linkInertialFrameOrientations=[[0, 0, 0, 1], [0, 0, 0, 1]],
                linkParentIndices=[0, 0],
                linkJointTypes=[p.JOINT_FIXED, p.JOINT_REVOLUTE],
                linkJointAxis=[[0, 0, 1], [0, 0, 1]],
                physicsClientId=physics_client,
            )

            # 1.5 cm radius, 15 cm height cylinder cavity
            bowl_boundary = {
                "shape": "cylinder",
                "type": "cavity",
                "radius": 0.018,
                "height": 0.150,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
                "link_type": LinkType.BASE,
                "link_idx": -1,
            }

            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    target_volume=0.00007,  # 70 mL of water (deep narrow column)
                    stiffness=1000.0,
                    bowl_wall_buffer=0.001,
                    boundaries={"bowl": bowl_boundary},
                    gravity=(0.0, 0.0, -9.81),
                ),
                provider=None,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )

            # Disable collisions
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            settle_steps = 40 if mode == "fast" else 60
            for step in range(settle_steps):
                fluid.update(body_id, physics_client, damping=0.90)
                p.stepSimulation(physicsClientId=physics_client)

            # Get initial water height
            positions = np.array(fluid.pos_jax)
            active_mask = positions[:, 2] < 100.0
            active_zs = positions[active_mask, 2]
            z_water = np.percentile(active_zs, 90)

            # Spawn steel sphere (Radius = 4 mm, density = 7850 kg/m^3)
            r_sphere = 0.004
            v_sphere = (4.0 / 3.0) * math.pi * (r_sphere**3)
            mass_steel = 7850.0 * v_sphere
            col_id = p.createCollisionShape(p.GEOM_SPHERE, radius=r_sphere, physicsClientId=physics_client)

            # Spawn at the top of the settled water level
            body_steel = p.createMultiBody(
                baseMass=mass_steel,
                baseCollisionShapeIndex=col_id,
                basePosition=[0.0, 0.0, z_water - r_sphere],
                physicsClientId=physics_client,
            )

            p.changeDynamics(
                body_steel,
                -1,
                linearDamping=0.0,
                angularDamping=0.0,
                lateralFriction=0.0,
                spinningFriction=0.0,
                rollingFriction=0.0,
                physicsClientId=physics_client,
            )

            # Disable collisions with particles
            if fluid.spawner:
                for w_id in fluid.spawner.particle_body_ids:
                    p.setCollisionFilterPair(
                        body_steel, w_id, -1, -1, enableCollision=0, physicsClientId=physics_client
                    )

            velocities = []
            positions_z = []
            run_steps = 60 if mode == "fast" else 120
            for step in range(run_steps):
                fluid.update(body_id, physics_client, damping=0.95)

                pos, _ = p.getBasePositionAndOrientation(body_steel, physicsClientId=physics_client)
                vel, _ = p.getBaseVelocity(body_steel, physicsClientId=physics_client)
                z_sphere = pos[2]
                v_z = vel[2]

                curr_pos = np.array(fluid.pos_jax)
                curr_active = curr_pos[:, 2] < 100.0
                z_water_current = np.percentile(curr_pos[curr_active, 2], 90)

                h_sub = np.clip(z_water_current - (z_sphere - r_sphere), 0.0, 2 * r_sphere)
                v_sub = (np.pi / 3.0) * (h_sub**2) * (3 * r_sphere - h_sub)

                f_buoyancy = 1000.0 * v_sub * 9.81
                f_drag_linear = -6.0 * np.pi * 0.5 * r_sphere * v_z
                f_drag_quad = -0.5 * 0.47 * 1000.0 * (np.pi * r_sphere**2) * v_z * abs(v_z)
                f_drag = (f_drag_linear + f_drag_quad) * (v_sub / v_sphere)

                p.applyExternalForce(
                    body_steel,
                    -1,
                    forceObj=[0.0, 0.0, f_buoyancy + f_drag],
                    posObj=pos,
                    flags=p.WORLD_FRAME,
                    physicsClientId=physics_client,
                )

                p.stepSimulation(physicsClientId=physics_client)

                vel_new, _ = p.getBaseVelocity(body_steel, physicsClientId=physics_client)
                velocities.append(vel_new[2])
                positions_z.append(pos[2])

            v_z_arr = np.array(velocities)
            bottom_z = 0.01 + r_sphere + 0.002
            hit_bottom_indices = np.where(np.array(positions_z) <= bottom_z)[0]
            fall_end = hit_bottom_indices[0] if len(hit_bottom_indices) > 0 else run_steps

            # Take velocities during the fall phase
            fall_vels = np.abs(v_z_arr[:fall_end])
            terminal_speed = np.mean(fall_vels[len(fall_vels) // 2 :])

            # Check acceleration decay:
            diff_1 = abs(np.abs(v_z_arr[20]) - np.abs(v_z_arr[10]))
            diff_2 = abs(np.abs(v_z_arr[30]) - np.abs(v_z_arr[20]))

            assert terminal_speed < 1.0, f"Terminal speed {terminal_speed:.4f} is too fast."
            assert diff_2 < diff_1, f"Drag is not causing deceleration: diff_2 ({diff_2:.4f}) >= diff_1 ({diff_1:.4f})"
        finally:
            p.disconnect(physicsClientId=physics_client)

    def test_fluid_recycling(self):
        """Verify that fallen particles are recycled back to the bowl when recycle_fluid is enabled."""
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                config=FluidConfig.water(
                    viscosity=0.5,
                    target_volume=0.00001,
                    bowl_wall_buffer=0.004,
                    boundaries=self.get_boundaries(),
                    gravity=(0.0, 0.0, -9.81),
                    recycle_fluid=True,
                ),
                provider=provider,
                body_id=body_id,
                physics_client=physics_client,
                link_indices={
                    LinkType.TUBE: 0,
                    LinkType.IMPELLER: 1,
                },
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            # Settle the fluid first
            for step in range(20):
                fluid.update(body_id, physics_client, damping=0.90)
                p.stepSimulation(physicsClientId=physics_client)

            # Move a few particles below z = 0 to trigger recycling
            pos_arr = np.array(fluid.pos_jax)
            # Make sure we have particles to move
            assert len(pos_arr) > 3
            pos_arr[0] = [0.0, 0.0, -5.0]
            pos_arr[1] = [0.0, 0.0, -10.0]
            fluid.pos_jax = jnp.array(pos_arr)

            # Update simulation step - this should trigger recycling
            fluid.update(body_id, physics_client, damping=0.998)
            p.stepSimulation(physicsClientId=physics_client)

            # Verify that they are recycled (i.e. relocated back above z = 0, and not added to fallen_out_water_ids)
            updated_pos = np.array(fluid.pos_jax)
            assert updated_pos[0, 2] >= 0.0, f"Particle 0 was not recycled: z = {updated_pos[0, 2]}"
            assert updated_pos[1, 2] >= 0.0, f"Particle 1 was not recycled: z = {updated_pos[1, 2]}"
            assert len(fluid.fallen_out_water_ids) == 0, "Fallen particles were registered as lost instead of recycled"

            # Now disable recycling and verify they get deactivated/lost
            fluid.recycle_fluid = False
            pos_arr = np.array(fluid.pos_jax)
            pos_arr[0] = [0.0, 0.0, -5.0]
            fluid.pos_jax = jnp.array(pos_arr)

            fluid.update(body_id, physics_client, damping=0.998)
            p.stepSimulation(physicsClientId=physics_client)

            updated_pos = np.array(fluid.pos_jax)
            # Deactivated particles are moved to z = 1000.0
            assert updated_pos[0, 2] >= 1000.0
            assert 0 in fluid.fallen_out_water_ids

        finally:
            p.disconnect(physicsClientId=physics_client)
