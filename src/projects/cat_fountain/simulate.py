"""Simulation methods and constants for the cat fountain."""

import math
import random
from typing import Any
import pybullet as p
import jax
import jax.numpy as jnp
from projects.fluid import Fluid
from provider.types import CollisionGroup, CollisionMask

# Simulation Target & Motor Constants
PARTICLE_RADIUS = 0.0015
TARGET_VOLUME = 0.000015  # 15ml, approx 1060 particles
VOLUME_THRESHOLD_LITERS = 0.002  # 2ml target for spout volume
FALLEN_THRESHOLD_LITERS = 0.010  # 10ml target for water falling out of bowl
BOWL_WALL_BUFFER = 0.002
SPAWN_SPACING_FACTOR = 2.2
Z_SPAWN_BUFFER = 0.001
MAX_SPAWN_HEIGHT = 0.120

# Flow check geometry thresholds and conversion constants
FALLEN_MIN_HEIGHT = 0.0
M3_TO_LITERS = 1000.0


class WaterSpawner:
    """Helper class to manage PyBullet body spawning, shapes, and state for water particles."""

    def __init__(
        self,
        physics_client: int,
        r_s: float,
        n_particles: int,
        particle_mass: float,
        particle_color: list[float],
        particle_visual_length: float,
        linear_damping: float,
        angular_damping: float,
        lateral_friction: float,
        restitution: float,
    ):
        """Initialize the spawner."""
        self.physics_client = physics_client
        self.r_s = r_s
        self.n_particles = n_particles
        self.particle_mass = particle_mass
        self.vol_s = (4.0 / 3.0) * math.pi * (r_s**3)

        self.sphere_col = p.createCollisionShape(p.GEOM_SPHERE, radius=r_s, physicsClientId=physics_client)
        self.circle_vis = p.createVisualShape(
            shapeType=p.GEOM_CYLINDER,
            radius=r_s,
            length=particle_visual_length,
            rgbaColor=particle_color,
            physicsClientId=physics_client,
        )

        self.linear_damping = linear_damping
        self.angular_damping = angular_damping
        self.lateral_friction = lateral_friction
        self.restitution = restitution

        self.water_body_ids: list[int] = []
        self.active_count: int = 0

    def spawn_batch(self, spawn_z: float, batch_size: int, spacing: float) -> int:
        """Spawn a batch of water particles up to n_particles total. Returns number of newly spawned particles."""
        if self.active_count >= self.n_particles:
            return 0
        to_activate = min(batch_size, self.n_particles - self.active_count)
        for i in range(to_activate):
            # Add a small horizontal jitter to avoid perfect vertical alignment and resulting SPH pressure explosions
            jitter_x = random.uniform(-2 * PARTICLE_RADIUS, 2 * PARTICLE_RADIUS)
            jitter_y = random.uniform(-2 * PARTICLE_RADIUS, 2 * PARTICLE_RADIUS)
            w_id = p.createMultiBody(
                baseMass=self.particle_mass,
                baseCollisionShapeIndex=self.sphere_col,
                baseVisualShapeIndex=self.circle_vis,
                basePosition=[jitter_x, jitter_y, spawn_z + i * spacing],
                physicsClientId=self.physics_client,
            )
            p.changeDynamics(
                w_id,
                -1,
                linearDamping=self.linear_damping,
                angularDamping=self.angular_damping,
                lateralFriction=self.lateral_friction,
                restitution=self.restitution,
                physicsClientId=self.physics_client,
            )
            p.setCollisionFilterGroupMask(
                w_id, -1, CollisionGroup.PARTICLE, CollisionMask.CONTAINER, physicsClientId=self.physics_client
            )
            p.resetBaseVelocity(w_id, [0.0, 0.0, -1.0], [0.0, 0.0, 0.0], physicsClientId=self.physics_client)
            self.water_body_ids.append(w_id)
        self.active_count += to_activate
        return to_activate

    def get_positions_and_velocities(self) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
        """Return positions and velocities of all particles, padding unspawned ones to keep constant JAX shapes."""
        positions = []
        velocities = []
        for w_id in self.water_body_ids:
            pos, _ = p.getBasePositionAndOrientation(w_id, physicsClientId=self.physics_client)
            vel, _ = p.getBaseVelocity(w_id, physicsClientId=self.physics_client)
            positions.append(pos)
            velocities.append(vel)

        unspawned_count = self.n_particles - len(self.water_body_ids)
        if unspawned_count > 0:
            positions.extend([(0.0, 0.0, 1000.0)] * unspawned_count)
            velocities.extend([(0.0, 0.0, 0.0)] * unspawned_count)

        return positions, velocities


class WaterSimulator:
    """Helper class to manage SPH water particle simulation in PyBullet."""

    # Visual and physical properties of particles
    PARTICLE_COLOR = [0.5, 0.8, 1.0, 0.7]
    PARTICLE_VISUAL_LENGTH = 0.0001
    LINEAR_DAMPING = 0.05
    ANGULAR_DAMPING = 0.05
    LATERAL_FRICTION = 0.1
    RESTITUTION = 0.0
    # SPH fluid simulator settings
    REST_DENSITY = 1000.0
    VISCOSITY = 0.02
    STIFFNESS = 100.0

    def __init__(self, provider: Any):
        """Initialize simulation state linked to a specific provider."""
        self.provider = provider
        self.spawner: WaterSpawner | None = None
        self.fluid: Fluid | None = None
        self.body_id: int | None = None
        self.physics_client: int | None = None

    @property
    def particle_mass(self) -> float:
        """Calculate the physical mass of a water particle based on radius and rest density."""
        r_s = PARTICLE_RADIUS
        vol_s = (4.0 / 3.0) * math.pi * (r_s**3)
        return float(vol_s * self.REST_DENSITY)

    @property
    def water_body_ids(self) -> list[int]:
        """Return the PyBullet body unique IDs of all spawned water particles."""
        if self.spawner is not None:
            return self.spawner.water_body_ids
        return []

    @property
    def active_count(self) -> int:
        """Return the number of spawned (active) water particles."""
        if self.spawner is not None:
            return self.spawner.active_count
        return 0

    @property
    def vol_s(self) -> float:
        """Return the volume of a single water particle sphere."""
        if self.spawner is not None:
            return self.spawner.vol_s
        return 0.0

    def _get_link_index(self, body_id: int, physics_client: int, name_substring: str) -> int | None:
        """Find the link index containing the given substring."""
        num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
        for i in range(num_joints):
            info = p.getJointInfo(body_id, i, physicsClientId=physics_client)
            link_name = info[12].decode("utf-8")
            if name_substring in link_name:
                return i
        return None

    @property
    def spout_link_idx(self) -> int | None:
        """Return the link index of the spout."""
        if self.body_id is None or self.physics_client is None:
            return None
        return self._get_link_index(self.body_id, self.physics_client, "spout")

    @property
    def tube_link_idx(self) -> int | None:
        """Return the link index of the tube."""
        if self.body_id is None or self.physics_client is None:
            return None
        return self._get_link_index(self.body_id, self.physics_client, "tube")

    @property
    def impeller_link_idx(self) -> int | None:
        """Return the link index of the impeller."""
        if self.body_id is None or self.physics_client is None:
            return None
        return self._get_link_index(self.body_id, self.physics_client, "impeller")

    @property
    def bowl_outer_radius(self) -> float:
        """Return the bowl outer radius dynamically from its AABB."""
        if self.body_id is None or self.physics_client is None:
            return 0.080
        aabb = p.getAABB(self.body_id, -1, physicsClientId=self.physics_client)
        return float((aabb[1][0] - aabb[0][0]) / 2.0)

    @property
    def spout_min_height(self) -> float:
        """Return the dynamic minimum height threshold for spout detection."""
        idx = self.spout_link_idx
        if idx is not None:
            state = p.getLinkState(self.body_id, idx, physicsClientId=self.physics_client)
            return float(state[0][2])
        return 0.095

    @property
    def spout_max_y(self) -> float:
        """Return the dynamic maximum Y threshold for spout detection based on spout nozzle tip."""
        idx = self.spout_link_idx
        if idx is not None:
            aabb = p.getAABB(self.body_id, idx, physicsClientId=self.physics_client)
            # Spout nozzle extends in -Y direction, so min_y + small buffer is the nozzle tip
            return float(aabb[0][1] + 0.010)
        return 0.030

    @property
    def fallen_max_radius(self) -> float:
        """Return the dynamic threshold radius beyond which particles have fallen out of the bowl."""
        return self.bowl_outer_radius + 0.010

    @property
    def impeller_clearance_radius(self) -> float:
        """Return the impeller clearance radius dynamically from its AABB."""
        idx = self.impeller_link_idx
        if idx is not None:
            aabb = p.getAABB(self.body_id, idx, physicsClientId=self.physics_client)
            impeller_r = (aabb[1][0] - aabb[0][0]) / 2.0
            return float(impeller_r + 0.003)
        return 0.015

    @property
    def impeller_target_velocity(self) -> float:
        """Return the target velocity for the impeller motor dynamically from shape metadata."""
        if hasattr(self.provider, "room") and self.provider.room:
            room = self.provider.room
            if "impeller" in room:
                impeller_shape = room["impeller"][0]
                return float(getattr(impeller_shape, "urdf_motor_target", 15.0))
        return 15.0

    @property
    def impeller_force(self) -> float:
        """Return the force limit for the impeller motor dynamically from shape metadata."""
        if hasattr(self.provider, "room") and self.provider.room:
            room = self.provider.room
            if "impeller" in room:
                impeller_shape = room["impeller"][0]
                return float(getattr(impeller_shape, "urdf_motor_force", 10.0))
        return 10.0

    @property
    def tube_outer_radius(self) -> float:
        """Return the tube outer radius dynamically from its AABB."""
        idx = self.tube_link_idx
        if idx is not None and self.body_id is not None and self.physics_client is not None:
            aabb = p.getAABB(self.body_id, idx, physicsClientId=self.physics_client)
            return float((aabb[1][0] - aabb[0][0]) / 2.0)
        return 0.008

    @property
    def tube_offset_mm(self) -> float:
        """Return the tube offset in millimeters, calculated dynamically from PyBullet link positions/AABBs."""
        idx = self.tube_link_idx
        if idx is not None and self.body_id is not None and self.physics_client is not None:
            info = p.getJointInfo(self.body_id, idx, physicsClientId=self.physics_client)
            tube_y = info[14][1]  # parentFramePosition Y coordinate in meters
            # Convert bowl_outer_radius and tube_outer_radius to mm to calculate offset in mm
            bowl_r_mm = self.bowl_outer_radius * 1000.0
            tube_r_mm = self.tube_outer_radius * 1000.0
            tube_y_mm = tube_y * 1000.0
            return float(bowl_r_mm - tube_r_mm - tube_y_mm)
        return 15.0

    def update_water(self, physics_client: int) -> None:
        """Step simulation and apply standard SPH fluid forces scaled by mass ratio."""
        if not self.fluid or not self.spawner:
            return

        # Dynamically spawn water particles only when ready to drop them
        spawn_batch = 5
        if self.active_count < self.n_particles:
            bowl_rim_height = self.provider.settings.bowl_height * 0.001
            spawn_z = bowl_rim_height + 0.050
            spacing = 0.004
            self.spawner.spawn_batch(spawn_z=spawn_z, batch_size=spawn_batch, spacing=spacing)

        positions, velocities = self.spawner.get_positions_and_velocities()

        scale_factor = self.particle_mass / self.fluid.mass

        # Convert to JAX arrays (always has constant shape self.n_particles, 3)
        pos_jax = jnp.array(positions, dtype=jnp.float32)
        vel_jax = jnp.array(velocities, dtype=jnp.float32)

        # Compute SPH forces directly as a JAX array
        sph_forces_jax = self.fluid.compute_forces_jax(pos_jax, vel_jax)
        scaled_forces_jax = sph_forces_jax * scale_factor

        final_forces = scaled_forces_jax.tolist()

        # Clamp SPH forces to prevent numerical explosions (max acceleration of 30.0 m/s^2)
        max_accel = 30.0
        max_force = self.particle_mass * max_accel

        # Apply standard physics SPH forces only to spawned particles in PyBullet
        for idx, w_id in enumerate(self.water_body_ids):
            f = final_forces[idx]
            f_mag = math.sqrt(sum(x**2 for x in f))
            if f_mag > max_force:
                scale = max_force / f_mag
                f = [x * scale for x in f]

            p.applyExternalForce(
                w_id,
                -1,
                f,
                [0.0, 0.0, 0.0],
                p.WORLD_FRAME,
                physicsClientId=physics_client,
            )

    def setup_simulation(self, body_id: int, physics_client: int, sim_name: str) -> None:
        """Configure motor control, calculate particle positions, and populate fluid simulation."""
        self.body_id = body_id
        self.physics_client = physics_client

        motor_idx = self._get_link_index(body_id, physics_client, "impeller")
        if motor_idx is not None:
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=motor_idx,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=self.impeller_target_velocity,
                force=self.impeller_force,
                physicsClientId=physics_client,
            )

        # Apply top rear camera view using the room helper
        if hasattr(self.provider, "room") and self.provider.room:
            self.provider.room.reset_camera(physics_client, view_from="top rear")

        r_s = PARTICLE_RADIUS
        vol_s = (4.0 / 3.0) * math.pi * (r_s**3)
        self.n_particles = int(round(TARGET_VOLUME / vol_s))

        self.provider.spout_water_ids = set()
        self.provider.fallen_out_water_ids = set()

        self.spawner = WaterSpawner(
            physics_client=physics_client,
            r_s=r_s,
            n_particles=self.n_particles,
            particle_mass=self.particle_mass,
            particle_color=self.PARTICLE_COLOR,
            particle_visual_length=self.PARTICLE_VISUAL_LENGTH,
            linear_damping=self.LINEAR_DAMPING,
            angular_damping=self.ANGULAR_DAMPING,
            lateral_friction=self.LATERAL_FRICTION,
            restitution=self.RESTITUTION,
        )
        self.fluid = Fluid(
            r_s=r_s,
            rest_density=self.REST_DENSITY,
            viscosity=self.VISCOSITY,
            stiffness=self.STIFFNESS,
        )

    def step_simulation(
        self,
        body_id: int,
        physics_client: int,
        step_index: int,
        sim_name: str,
    ) -> str | None:
        """Step simulation and apply fluid forces via WaterSimulator helper."""
        self.body_id = body_id
        self.physics_client = physics_client

        self.update_water(physics_client)
        # Classify active particle positions based on cat fountain specific geometry
        for idx in range(self.active_count):
            w_id = self.water_body_ids[idx]
            pos, _ = p.getBasePositionAndOrientation(w_id, physicsClientId=physics_client)
            x, y, z = pos
            if z >= 100.0:
                continue
            if z >= self.spout_min_height and y < self.spout_max_y:
                self.provider.spout_water_ids.add(w_id)
            if z < FALLEN_MIN_HEIGHT or (x**2 + y**2 > self.fallen_max_radius**2):
                self.provider.fallen_out_water_ids.add(w_id)
                # Deactivate the particle in PyBullet to stop infinite falling and save CPU
                p.resetBasePositionAndOrientation(
                    w_id, [0.0, 0.0, 1000.0], [0.0, 0.0, 0.0, 1.0], physicsClientId=physics_client
                )
                p.resetBaseVelocity(w_id, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], physicsClientId=physics_client)
                p.changeDynamics(w_id, -1, mass=0.0, physicsClientId=physics_client)
                p.setCollisionFilterGroupMask(w_id, -1, 0, 0, physicsClientId=physics_client)

        # Compute volumes in liters
        spout_vol = len(self.provider.spout_water_ids) * self.vol_s * M3_TO_LITERS
        fallen_vol = len(self.provider.fallen_out_water_ids) * self.vol_s * M3_TO_LITERS

        # Evaluate termination conditions in the provider
        if spout_vol >= VOLUME_THRESHOLD_LITERS:
            return f"{VOLUME_THRESHOLD_LITERS}L of water spout volume reached"
        if fallen_vol >= FALLEN_THRESHOLD_LITERS:
            return f"{FALLEN_THRESHOLD_LITERS}L of water fell out of bowl"
        return None
