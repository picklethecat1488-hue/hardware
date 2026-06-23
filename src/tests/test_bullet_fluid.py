"""Integration tests for Fluid and Bullet simulation proving laws of conservation."""

import math
import random
from typing import Any, Optional
import numpy as np
import pybullet as p
import pytest
from provider.fluid import Fluid


class TestBulletFluid:
    """Class containing integration tests for Bullet and SPH Fluid interaction."""

    # Simulation step constants
    FAST_STEPS = 100
    SLOW_STEPS = 3000

    class ConservationFluid(Fluid):
        """Subclass of Fluid overriding link index lookup for custom multibody."""

        def _get_link_index(self, body_id: int | None, physics_client: int | None, name_substring: str) -> int | None:
            if "outlet" in name_substring or "spout" in name_substring:
                return None
            if "hollow_cylinder" in name_substring or "tube" in name_substring:
                return 0
            if "rotary_vanes" in name_substring or "impeller" in name_substring:
                return 1
            return None

        @property
        def radii(self) -> list[float]:
            """Return the list of radii settings with overridden activation bounds."""
            r = super().radii
            # Override fallen_max_radius to be very large (10.0m) to prevent deactivation of active fluid particles
            # when the bowl moves away from the world origin.
            r[3] = 10.0
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
                "shape": "cylinder",
                "type": "cavity",
                "radius": 0.076,
                "height": 0.096,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
            },
            "hollow_cylinder": {
                "shape": "cylinder",
                "type": "solid_cavity",
                "radius": 0.008,
                "height": 0.120,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
            },
            "rotary_vanes": {
                "shape": "cylinder",
                "type": "solid",
                "radius": 0.050,  # Large radius to interact with most particles in the rotation test
                "height": 0.015,
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
            },
        }

    @staticmethod
    def disable_pybullet_particle_collisions(physics_client: int, body_id: int, fluid: Fluid) -> None:
        """Disable PyBullet-level collisions between the particle bodies and the bowl/links."""
        assert fluid.spawner is not None, "Fluid spawner is not initialized"
        for w_id in fluid.spawner.water_body_ids:
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
    def get_system_energy(physics_client: int, body_id: int, fluid: Fluid, gravity_z: float) -> float:
        """Compute the combined mechanical energy (KE + PE) of the fluid and the bowl."""
        e_fluid = TestBulletFluid.get_fluid_energy(fluid, gravity_z)

        lin_vel, ang_vel = p.getBaseVelocity(body_id, physicsClientId=physics_client)
        lin_vel = np.array(lin_vel)
        ang_vel = np.array(ang_vel)

        # Bowl mass is 1.0. Total multibody mass is 1.2
        ke_bowl_lin = 0.5 * 1.2 * np.sum(lin_vel**2)
        ke_bowl_ang = 0.5 * 0.1 * np.sum(ang_vel**2)

        return e_fluid + float(ke_bowl_lin + ke_bowl_ang)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_at_rest(self, mode: str):
        """Verify that fluid spawned in the bowl stays at rest when the bowl is stationary."""
        random.seed(42)
        np.random.seed(42)
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, 0, physicsClientId=physics_client)  # Zero gravity and zero stiffness for pure static check
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                provider=provider,
                r_s=0.003,
                target_volume=0.00001,
                viscosity=0.02,
                stiffness=0.0,
                bowl_wall_buffer=0.004,  # Clear hollow cylinder boundary at spawn
                body_id=body_id,
                physics_client=physics_client,
                boundaries=self.get_boundaries(),
                gravity=(0.0, 0.0, 0.0),
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            # Step simulation and update fluid
            for step in range(max_steps):
                fluid.update(body_id, physics_client, step, "rest_test")
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, 0.0)
                assert e < 1e-7, f"Fluid energy changed at step {step}: {e}"

            # Get positions and velocities
            vels = np.array(fluid.vel_jax)
            speeds = np.linalg.norm(vels, axis=1)

            # Average speed of the fluid should be extremely small
            avg_speed = np.mean(speeds)
            assert avg_speed < 0.01, f"Fluid did not stay at rest, average speed: {avg_speed}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_tipped_bowl(self, mode: str):
        """Verify that fluid escapes when the bowl is tipped, and escape time can be measured."""
        random.seed(42)
        np.random.seed(42)
        physics_client = p.connect(p.DIRECT)
        try:
            # Set gravity to normal conditions
            p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            # Initialize fluid while bowl is upright to spawn cleanly inside
            fluid = self.ConservationFluid(
                provider=provider,
                r_s=0.003,
                target_volume=0.00001,
                viscosity=0.02,
                stiffness=100.0,
                bowl_wall_buffer=0.004,
                body_id=body_id,
                physics_client=physics_client,
                boundaries=self.get_boundaries(),
                gravity=(0.0, 0.0, -9.81),
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            escaped_at_step = None
            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            for step in range(max_steps):
                if step == 2:
                    # Tip the bowl by 45 degrees (rotation about Y axis) after spawning has completed
                    tipped_orientation = p.getQuaternionFromEuler([0.0, 0.785, 0.0])
                    p.resetBasePositionAndOrientation(
                        body_id, [0.0, 0.0, 0.0], tipped_orientation, physicsClientId=physics_client
                    )

                fluid.update(body_id, physics_client, step, "tipped_test")
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, -9.81)

                # Energy is bounded during the tipping/sliding process
                assert e <= 0.05, f"Energy exceeded bound at step {step}: {e}"

                if len(fluid.fallen_out_water_ids) > 0 and escaped_at_step is None:
                    escaped_at_step = step

            assert escaped_at_step is not None, "Fluid did not escape from the tipped bowl."
            # Known escape time bounds (should escape within 3 to 45 steps)
            assert 3 <= escaped_at_step <= 45, f"Escape step {escaped_at_step} was outside bounds [3, 45]"

            # At the end, almost all fluid has escaped so the energy is virtually 0
            final_e = self.get_fluid_energy(fluid, -9.81)
            assert final_e < 1e-7, f"Final energy was non-zero after escaping: {final_e}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_bowl_external_force(self, mode: str):
        """Verify that after applying a velocity to the bowl/fluid, the system decays back to rest."""
        random.seed(42)
        np.random.seed(42)
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, 0, physicsClientId=physics_client)  # Zero gravity so the bowl doesn't accelerate downwards
            body_id = self.create_test_body(physics_client, mass=1.0)

            # Enable very high damping in PyBullet to bring the rigid body back to rest quickly (within ~0.4s)
            p.changeDynamics(body_id, -1, linearDamping=20.0, angularDamping=20.0, physicsClientId=physics_client)

            provider = self.DummyProvider()
            # Use high SPH viscosity=2.0 to damp sloshing forces quickly
            fluid = self.ConservationFluid(
                provider=provider,
                r_s=0.003,
                target_volume=0.00001,
                viscosity=2.0,
                stiffness=100.0,
                bowl_wall_buffer=0.004,
                body_id=body_id,
                physics_client=physics_client,
                boundaries=self.get_boundaries(),
                gravity=(0.0, 0.0, 0.0),
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            # Apply a high initial linear velocity to the bowl
            p.resetBaseVelocity(body_id, linearVelocity=[1.5, 0.0, 0.0], physicsClientId=physics_client)

            # Verify initial velocity is non-zero
            base_vel, _ = p.getBaseVelocity(body_id, physicsClientId=physics_client)
            assert abs(base_vel[0]) > 1.0

            last_e = self.get_system_energy(physics_client, body_id, fluid, 0.0)
            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            # Step simulation to let damping work
            for step in range(max_steps):
                fluid.update(body_id, physics_client, step, "force_test")
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_system_energy(physics_client, body_id, fluid, 0.0)
                # Energy must decrease strictly monotonically (plus a tiny tolerance for float precision)
                assert e <= last_e + 1e-7, f"Energy increased at step {step}: {e} vs {last_e}"
                last_e = e

            # Verify both bowl and fluid return to rest
            final_bowl_vel, _ = p.getBaseVelocity(body_id, physicsClientId=physics_client)
            final_bowl_speed = np.linalg.norm(final_bowl_vel)

            final_fluid_vels = np.array(fluid.vel_jax)
            final_fluid_speeds = np.linalg.norm(final_fluid_vels, axis=1)
            final_fluid_avg_speed = np.mean(final_fluid_speeds)

            assert final_bowl_speed < 0.02, f"Bowl did not return to rest: {final_bowl_speed}"
            assert final_fluid_avg_speed < 0.05, f"Fluid did not return to rest: {final_fluid_avg_speed}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_rotated_by_impeller(self, mode: str):
        """Verify that fluid being rotated by the impeller starts rotating in the same direction."""
        random.seed(42)
        np.random.seed(42)
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, 0, physicsClientId=physics_client)  # Zero gravity for stable rotation tracking
            body_id = self.create_test_body(physics_client, vanes_z=0.004, mass=0.0)  # Enable impeller centered in the bowl

            # Rotate the impeller at constant angular velocity (5.0 rad/s) in PyBullet
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=1,  # rotary_vanes / impeller is joint 1
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=5.0,
                force=10.0,
                physicsClientId=physics_client,
            )

            provider = self.DummyProvider(target_vel=5.0, force=10.0, has_room=True)
            fluid = self.ConservationFluid(
                provider=provider,
                r_s=0.003,
                target_volume=0.00001,
                viscosity=0.02,
                stiffness=100.0,
                bowl_wall_buffer=0.004,
                body_id=body_id,
                physics_client=physics_client,
                boundaries=self.get_boundaries(),
                gravity=(0.0, 0.0, 0.0),
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            # Run for the steps (passing step_index >= 40 so rotation is active in Fluid update)
            for step in range(max_steps):
                fluid.update(body_id, physics_client, step + 40, "rotation_test")
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, 0.0)
                assert 0.0 <= e <= 0.02, f"Rotation energy exceeded bounds at step {step}: {e}"

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
            assert avg_omega > 0.5, f"Fluid particles did not rotate as expected. Avg omega: {avg_omega}"
        finally:
            p.disconnect(physicsClientId=physics_client)

    @pytest.mark.parametrize("mode", ["fast", pytest.param("slow", marks=pytest.mark.slow)])
    def test_fluid_drag_fixed_velocity(self, mode: str):
        """Verify that in a bowl moving at a fixed velocity, the fluid moves at the same velocity."""
        random.seed(42)
        np.random.seed(42)
        physics_client = p.connect(p.DIRECT)
        try:
            p.setGravity(0, 0, 0, physicsClientId=physics_client)  # Zero gravity for stable translation tracking
            body_id = self.create_test_body(physics_client, mass=0.0)

            provider = self.DummyProvider()
            fluid = self.ConservationFluid(
                provider=provider,
                r_s=0.003,
                target_volume=0.00001,
                viscosity=0.02,
                stiffness=100.0,
                bowl_wall_buffer=0.004,
                body_id=body_id,
                physics_client=physics_client,
                boundaries=self.get_boundaries(),
                gravity=(0.0, 0.0, 0.0),
            )
            self.disable_pybullet_particle_collisions(physics_client, body_id, fluid)

            # Move bowl at a constant speed of 0.5 m/s in X direction
            target_velocity = [0.5, 0.0, 0.0]
            max_steps = self.SLOW_STEPS if mode == "slow" else self.FAST_STEPS

            for step in range(max_steps):
                p.resetBaseVelocity(body_id, linearVelocity=target_velocity, physicsClientId=physics_client)
                fluid.update(body_id, physics_client, step, "drag_test")
                p.stepSimulation(physicsClientId=physics_client)
                e = self.get_fluid_energy(fluid, 0.0)
                assert 0.0 <= e <= 0.02, f"Drag energy exceeded bounds at step {step}: {e}"

            # Check average velocity of all active particles
            positions = np.array(fluid.pos_jax)
            velocities = np.array(fluid.vel_jax)
            active_mask = positions[:, 2] < 100.0
            active_vels = velocities[active_mask]

            assert len(active_vels) > 0, "No active fluid particles."

            avg_vel = np.mean(active_vels, axis=0)

            # Assert fluid particles are moving along with the bowl (with sloshing allowance)
            assert 0.35 <= avg_vel[0] <= 0.95, f"Fluid speed X was {avg_vel[0]}, expected drag around 0.5 m/s"
            assert math.isclose(avg_vel[1], 0.0, abs_tol=0.1), f"Fluid speed Y was {avg_vel[1]}, expected ~0.0"
            # SPH height settling may cause minor Z movement, but should be close to 0
            assert math.isclose(avg_vel[2], 0.0, abs_tol=0.1), f"Fluid speed Z was {avg_vel[2]}, expected ~0.0"
        finally:
            p.disconnect(physicsClientId=physics_client)
