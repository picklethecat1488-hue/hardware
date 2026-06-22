"""Simulation methods and constants for the cat fountain using JAX SPH and analytical boundary forces."""

import math
import random
from typing import Any
import pybullet as p
import jax
import jax.numpy as jnp
import numpy as np
from scipy.spatial import cKDTree  # type: ignore
from projects.fluid import Fluid
from provider.types import CollisionGroup, CollisionMask
from provider.room import BulletStateTracker

# Simulation Target & Motor Constants
PARTICLE_RADIUS = 0.0015
TARGET_VOLUME = 0.0005  # 500ml, approx 35360 particles
VOLUME_THRESHOLD_LITERS = 0.400  # 400ml target for spout volume
FALLEN_THRESHOLD_LITERS = 0.050  # 50ml target for water falling out of bowl
BOWL_WALL_BUFFER = 0.002
SPAWN_SPACING_FACTOR = 2.2
Z_SPAWN_BUFFER = 0.001
MAX_SPAWN_HEIGHT = 0.120

# Flow check geometry thresholds and conversion constants
FALLEN_MIN_HEIGHT = 0.0
M3_TO_LITERS = 1000.0


@jax.jit
def q_inv(q):
    """Calculate quaternion inverse (conjugate)."""
    return jnp.array([-q[0], -q[1], -q[2], q[3]], dtype=jnp.float32)


@jax.jit
def q_rotate(q, v):
    """Rotate a batch of 3D vectors v by quaternion q (xyzw)."""
    q_xyz = q[:3]
    w = q[3]
    cross1 = jnp.cross(q_xyz, v) + w * v
    return v + 2.0 * jnp.cross(q_xyz, cross1)


@jax.jit
def _compute_boundary_forces_jax(
    pos: jnp.ndarray,
    vel: jnp.ndarray,
    r_s: float,
    K: float,
    D: float,
    bowl_pos: jnp.ndarray,
    bowl_orn: jnp.ndarray,
    bowl_radius: float,
    bowl_height: float,
    bowl_z_offset: float,
    tube_pos: jnp.ndarray,
    tube_orn: jnp.ndarray,
    tube_outer_radius: float,
    tube_inner_radius: float,
    tube_height: float,
    impeller_pos: jnp.ndarray,
    impeller_orn: jnp.ndarray,
    impeller_radius: float,
    impeller_hub_radius: float,
    impeller_height: float,
    omega: float,
    t: float,
    blade_thickness: float,
    num_blades: float,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Compute mathematical penalty forces from bowl, tube, and impeller boundaries in JAX."""
    forces = jnp.zeros_like(pos)

    # --- BOWL BOUNDARY ---
    bowl_orn_inv = q_inv(bowl_orn)
    pos_b = q_rotate(bowl_orn_inv, pos - bowl_pos)
    vel_b = q_rotate(bowl_orn_inv, vel)

    # 1. Bowl side wall (cylinder cavity)
    r_b = jnp.sqrt(pos_b[:, 0] ** 2 + pos_b[:, 1] ** 2)
    r_b = jnp.maximum(r_b, 1e-8)
    r_limit_b = bowl_radius - r_s
    pen_b_side = r_b - r_limit_b
    side_mask = pen_b_side > 0.0

    nx_b = -pos_b[:, 0] / r_b
    ny_b = -pos_b[:, 1] / r_b
    v_n_b = vel_b[:, 0] * (-nx_b) + vel_b[:, 1] * (-ny_b)
    f_mag_b_side = K * pen_b_side + D * jnp.maximum(v_n_b, 0.0)

    force_b_side = jnp.stack([f_mag_b_side * nx_b, f_mag_b_side * ny_b, jnp.zeros_like(r_b)], axis=-1)
    force_b_side = jnp.where(side_mask[:, None], force_b_side, 0.0)

    # 2. Bowl bottom (flat plate)
    z_limit_b = bowl_z_offset + r_s
    pen_b_bottom = z_limit_b - pos_b[:, 2]
    bottom_mask = pen_b_bottom > 0.0
    f_z_b = K * pen_b_bottom - D * vel_b[:, 2]
    force_b_bottom = jnp.stack([jnp.zeros_like(r_b), jnp.zeros_like(r_b), jnp.maximum(f_z_b, 0.0)], axis=-1)
    force_b_bottom = jnp.where(bottom_mask[:, None], force_b_bottom, 0.0)

    forces += q_rotate(bowl_orn, force_b_side + force_b_bottom)

    # --- TUBE BOUNDARY ---
    tube_orn_inv = q_inv(tube_orn)
    pos_t = q_rotate(tube_orn_inv, pos - tube_pos)
    vel_t = q_rotate(tube_orn_inv, vel)

    # Cutout slot at bottom: ry < 0 and rz < 15mm
    cutout_mask = (pos_t[:, 2] < 0.015) & (pos_t[:, 1] < 0.0)
    tube_active_mask = ~cutout_mask

    r_t = jnp.sqrt(pos_t[:, 0] ** 2 + pos_t[:, 1] ** 2)
    r_t = jnp.maximum(r_t, 1e-8)
    r_mid = (tube_inner_radius + tube_outer_radius) / 2.0

    # 1. Inner cavity collision (r_t < r_mid)
    pen_t_in = r_t - (tube_inner_radius - r_s)
    in_mask = tube_active_mask & (r_t < r_mid) & (pen_t_in > 0.0)
    nx_t_in = -pos_t[:, 0] / r_t
    ny_t_in = -pos_t[:, 1] / r_t
    v_n_t_in = vel_t[:, 0] * (-nx_t_in) + vel_t[:, 1] * (-ny_t_in)
    f_mag_t_in = K * pen_t_in + D * jnp.maximum(v_n_t_in, 0.0)
    force_t_in = jnp.stack([f_mag_t_in * nx_t_in, f_mag_t_in * ny_t_in, jnp.zeros_like(r_t)], axis=-1)
    force_t_in = jnp.where(in_mask[:, None], force_t_in, 0.0)

    # 2. Outer solid cylinder collision (r_t >= r_mid)
    pen_t_out = (tube_outer_radius + r_s) - r_t
    out_mask = tube_active_mask & (r_t >= r_mid) & (pen_t_out > 0.0)
    nx_t_out = pos_t[:, 0] / r_t
    ny_t_out = pos_t[:, 1] / r_t
    v_n_t_out = vel_t[:, 0] * nx_t_out + vel_t[:, 1] * ny_t_out
    f_mag_t_out = K * pen_t_out - D * v_n_t_out
    force_t_out = jnp.stack([f_mag_t_out * nx_t_out, f_mag_t_out * ny_t_out, jnp.zeros_like(r_t)], axis=-1)
    force_t_out = jnp.where((out_mask[:, None]) & (f_mag_t_out[:, None] > 0.0), force_t_out, 0.0)

    forces += q_rotate(tube_orn, force_t_in + force_t_out)

    # --- IMPELLER BOUNDARY ---
    impeller_orn_inv = q_inv(impeller_orn)
    pos_i = q_rotate(impeller_orn_inv, pos - impeller_pos)
    vel_i = q_rotate(impeller_orn_inv, vel)

    r_i = jnp.sqrt(pos_i[:, 0] ** 2 + pos_i[:, 1] ** 2)
    r_i = jnp.maximum(r_i, 1e-8)

    imp_height_mask = (pos_i[:, 2] >= 0.0) & (pos_i[:, 2] <= impeller_height)

    # 1. Hub solid cylinder
    pen_i_hub = (impeller_hub_radius + r_s) - r_i
    hub_mask = imp_height_mask & (pen_i_hub > 0.0)
    nx_i_hub = pos_i[:, 0] / r_i
    ny_i_hub = pos_i[:, 1] / r_i
    v_n_i_hub = vel_i[:, 0] * nx_i_hub + vel_i[:, 1] * ny_i_hub
    f_mag_i_hub = K * pen_i_hub - D * v_n_i_hub
    force_i_hub = jnp.stack([f_mag_i_hub * nx_i_hub, f_mag_i_hub * ny_i_hub, jnp.zeros_like(r_i)], axis=-1)
    force_i_hub = jnp.where((hub_mask[:, None]) & (f_mag_i_hub[:, None] > 0.0), force_i_hub, 0.0)

    # 2. Rotating Blades
    theta_t = 0.0
    phi = jnp.arctan2(pos_i[:, 1], pos_i[:, 0])
    d_phi = phi - theta_t

    pi_N = jnp.pi / num_blades
    d_phi_wrapped = (d_phi + pi_N) % (2.0 * pi_N) - pi_N

    dist_to_blade = r_i * jnp.sin(d_phi_wrapped)
    blade_threshold = blade_thickness / 2.0 + r_s
    pen_blade = blade_threshold - jnp.abs(dist_to_blade)

    blade_collision_mask = imp_height_mask & (r_i >= impeller_hub_radius) & (r_i <= impeller_radius) & (pen_blade > 0.0)

    sign_dist = jnp.sign(d_phi_wrapped)
    normal_tx = -sign_dist * jnp.sin(phi)
    normal_ty = sign_dist * jnp.cos(phi)

    v_blade_x = omega * r_i * (-jnp.sin(phi))
    v_blade_y = omega * r_i * jnp.cos(phi)

    v_rel_n_blade = (vel_i[:, 0] - v_blade_x) * normal_tx + (vel_i[:, 1] - v_blade_y) * normal_ty

    f_mag_blade = K * pen_blade - D * v_rel_n_blade
    force_blade = jnp.stack([f_mag_blade * normal_tx, f_mag_blade * normal_ty, jnp.zeros_like(r_i)], axis=-1)
    force_blade = jnp.where((blade_collision_mask[:, None]) & (f_mag_blade[:, None] > 0.0), force_blade, 0.0)

    forces += q_rotate(impeller_orn, force_i_hub + force_blade)

    # Calculate reaction torque on the impeller (Newton's 3rd Law: reaction force is -force_blade)
    torque_z = pos_i[:, 1] * force_blade[:, 0] - pos_i[:, 0] * force_blade[:, 1]
    impeller_torque = jnp.sum(torque_z)

    return forces, impeller_torque


# JIT compiled SPH force computation using a precomputed neighbor list
@jax.jit
def _compute_forces_neighbor_list_jax(
    positions: jnp.ndarray,
    velocities: jnp.ndarray,
    idx_map: jnp.ndarray,
    mass: float,
    h: float,
    rest_density: float,
    viscosity: float,
    stiffness: float,
    poly6_factor: float,
    spiky_grad_factor: float,
    visc_lap_factor: float,
    pressure_avg_factor: float,
    min_dist_threshold: float,
) -> jnp.ndarray:
    """Compute SPH forces (pressure + viscosity) using a neighbor list."""
    n = positions.shape[0]
    h2 = h * h

    neigh_positions = positions[idx_map]  # Shape (N, M, 3)
    neigh_velocities = velocities[idx_map]  # Shape (N, M, 3)

    diff = positions[:, None, :] - neigh_positions  # Shape (N, M, 3)
    r2 = jnp.sum(diff * diff, axis=-1)  # Shape (N, M)

    neigh_mask = idx_map != jnp.arange(n)[:, None]

    # 1. Densities
    w = poly6_factor * (jnp.maximum(h2 - r2, 0.0) ** 3) * neigh_mask
    self_density = mass * poly6_factor * (h2**3)
    densities = jnp.sum(mass * w, axis=1) + self_density
    densities = jnp.maximum(densities, rest_density)
    pressures = stiffness * (densities - rest_density)

    # 2. Forces
    r = jnp.sqrt(r2 + min_dist_threshold * min_dist_threshold)
    hr = jnp.maximum(h - r, 0.0)
    grad_coeff = spiky_grad_factor * (hr**2) * neigh_mask

    neigh_densities = densities[idx_map]
    p_term = mass * (pressures[:, None] + pressures[idx_map]) / (pressure_avg_factor * neigh_densities)
    direction = diff / r[:, :, None]

    f_press = -p_term[:, :, None] * grad_coeff[:, :, None] * direction
    f_press_total = jnp.sum(f_press, axis=1)

    lap_coeff = visc_lap_factor * hr * neigh_mask
    v_diff = neigh_velocities - velocities[:, None, :]
    v_term = viscosity * mass / neigh_densities[:, :, None] * lap_coeff[:, :, None]

    f_visc = v_term * v_diff
    f_visc_total = jnp.sum(f_visc, axis=1)

    vol_factor = (mass / densities)[:, None]
    f_press_scaled = f_press_total * vol_factor
    f_visc_scaled = f_visc_total * vol_factor

    return f_press_scaled + f_visc_scaled


@jax.jit
def _physics_step_jax(
    pos: jnp.ndarray,
    vel: jnp.ndarray,
    idx_map: jnp.ndarray,
    mass: float,
    h: float,
    rest_density: float,
    viscosity: float,
    stiffness: float,
    poly6_factor: float,
    spiky_grad_factor: float,
    visc_lap_factor: float,
    dt_sub: float,
    n_substeps: int,
    gravity: jnp.ndarray,
    bowl_pos: jnp.ndarray,
    bowl_orn: jnp.ndarray,
    bowl_radius: float,
    bowl_height: float,
    bowl_z_offset: float,
    tube_pos: jnp.ndarray,
    tube_orn: jnp.ndarray,
    tube_outer_radius: float,
    tube_inner_radius: float,
    tube_height: float,
    impeller_pos: jnp.ndarray,
    impeller_orn: jnp.ndarray,
    impeller_radius: float,
    impeller_hub_radius: float,
    impeller_height: float,
    omega: float,
    t_start: float,
    blade_thickness: float,
    num_blades: float,
    K_boundary: float,
    D_boundary: float,
    r_s: float,
    damping: float = 1.0,
) -> tuple[jnp.ndarray, jnp.ndarray, float]:
    """Perform a substepped JAX update step integrating forces and resolving boundary collisions."""

    def body_fun(i, val):
        pos_curr, vel_curr, torque_accum = val
        t_curr = t_start + i * dt_sub

        # SPH forces
        sph_forces = _compute_forces_neighbor_list_jax(
            pos_curr,
            vel_curr,
            idx_map,
            mass,
            h,
            rest_density,
            viscosity,
            stiffness,
            poly6_factor,
            spiky_grad_factor,
            visc_lap_factor,
            2.0,  # pressure_avg_factor
            1e-6,  # min_dist_threshold
        )

        # Boundary forces
        b_forces, step_torque = _compute_boundary_forces_jax(
            pos_curr,
            vel_curr,
            r_s,
            K_boundary,
            D_boundary,
            bowl_pos,
            bowl_orn,
            bowl_radius,
            bowl_height,
            bowl_z_offset,
            tube_pos,
            tube_orn,
            tube_outer_radius,
            tube_inner_radius,
            tube_height,
            impeller_pos,
            impeller_orn,
            impeller_radius,
            impeller_hub_radius,
            impeller_height,
            omega,
            t_curr,
            blade_thickness,
            num_blades,
        )

        # Gravitational force
        g_force = mass * gravity

        # SPH acceleration
        sph_accel = sph_forces / mass
        max_sph_accel = 50.0
        sph_accel_mags = jnp.linalg.norm(sph_accel, axis=1, keepdims=True)
        sph_accel_mags_safe = jnp.maximum(sph_accel_mags, 1e-8)
        sph_accel_clamped = sph_accel * jnp.minimum(max_sph_accel / sph_accel_mags_safe, 1.0)

        # Boundary acceleration
        b_accel = b_forces / mass
        max_b_accel = 1000.0
        b_accel_mags = jnp.linalg.norm(b_accel, axis=1, keepdims=True)
        b_accel_mags_safe = jnp.maximum(b_accel_mags, 1e-8)
        b_accel_clamped = b_accel * jnp.minimum(max_b_accel / b_accel_mags_safe, 1.0)

        # Total acceleration
        accel = sph_accel_clamped + b_accel_clamped + gravity

        # Integrate only active particles (z < 100.0)
        active = (pos_curr[:, 2] < 100.0)[:, None]
        vel_next = jnp.where(active, (vel_curr + accel * dt_sub) * damping, 0.0)
        pos_next = jnp.where(active, pos_curr + vel_next * dt_sub, pos_curr)

        # Accumulate torque
        torque_accum_next = torque_accum + step_torque

        return pos_next, vel_next, torque_accum_next

    return jax.lax.fori_loop(0, n_substeps, body_fun, (pos, vel, 0.0))


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

    def spawn_all_at_positions(self, positions: list[tuple[float, float, float]]) -> None:
        """Spawn all water particles at specified 3D positions."""
        for pos in positions:
            w_id = p.createMultiBody(
                baseMass=self.particle_mass,
                baseCollisionShapeIndex=self.sphere_col,
                baseVisualShapeIndex=self.circle_vis,
                basePosition=pos,
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
            p.resetBaseVelocity(w_id, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], physicsClientId=self.physics_client)
            self.water_body_ids.append(w_id)
        self.active_count = len(self.water_body_ids)

    def get_positions_and_velocities(
        self, fallen_ids: set[int] | None = None
    ) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
        """Return positions and velocities of all particles, padding unspawned ones to keep constant JAX shapes."""
        positions = []
        velocities = []
        if fallen_ids is None:
            fallen_ids = set()

        for w_id in self.water_body_ids:
            if w_id in fallen_ids:
                positions.append((0.0, 0.0, 1000.0))
                velocities.append((0.0, 0.0, 0.0))
            else:
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
    """Helper class to manage SPH water particle simulation in JAX with PyBullet dynamic coordinates."""

    PARTICLE_COLOR = [0.5, 0.8, 1.0, 0.7]
    PARTICLE_VISUAL_LENGTH = 0.0001
    LINEAR_DAMPING = 0.05
    ANGULAR_DAMPING = 0.05
    LATERAL_FRICTION = 0.1
    RESTITUTION = 0.0
    REST_DENSITY = 1000.0
    VISCOSITY = 0.02
    STIFFNESS = 100.0

    def __init__(self, provider: Any):
        """Initialize simulation state."""
        self.provider = provider
        self.spawner: WaterSpawner | None = None
        self.fluid: Fluid | None = None
        self.body_id: int | None = None
        self.physics_client: int | None = None
        self.boundaries: dict[str, Any] = {}
        self.pos_jax: Any = None
        self.vel_jax: Any = None
        self.n_particles: int = 0
        self.last_positions: list[list[float]] = []
        self.current_sim_time: float = 0.0
        self.torques: list[float] = []

        # Register self as the active simulator
        BulletStateTracker.active_simulator = self

    @property
    def particle_mass(self) -> float:
        """Calculate the physical mass of a water particle based on radius and rest density."""
        r_s = PARTICLE_RADIUS
        vol_s = (4.0 / 3.0) * math.pi * (r_s**3)
        return float(vol_s * self.REST_DENSITY)

    @property
    def water_body_ids(self) -> list[int]:
        """Return dummy IDs for compatibility."""
        return list(range(self.n_particles))

    @property
    def active_count(self) -> int:
        """Return number of particles."""
        return self.n_particles

    @property
    def vol_s(self) -> float:
        """Return the volume of a single water particle sphere."""
        r_s = PARTICLE_RADIUS
        return (4.0 / 3.0) * math.pi * (r_s**3)

    def get_particle_positions(self) -> list[list[float]]:
        """Return particle positions for logger."""
        return self.last_positions

    def get_particle_colors(self) -> list[list[float]]:
        """Return particle colors for logger."""
        return [self.PARTICLE_COLOR] * self.n_particles

    def get_particle_radii(self) -> list[float]:
        """Return particle radii for logger."""
        return [PARTICLE_RADIUS] * self.n_particles

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
        """Return the bowl outer radius dynamically from parsed boundaries or its AABB."""
        if hasattr(self, "boundaries") and "bowl" in self.boundaries:
            r_inner = self.boundaries["bowl"].get("radius", 0.0725)
            t = 0.0035
            if hasattr(self, "provider") and hasattr(self.provider, "settings"):
                t = getattr(self.provider.settings, "bowl_thickness", 3.5) * 0.001
            return float(r_inner + t)
        if self.body_id is None or self.physics_client is None:
            return 0.080
        try:
            aabb = p.getAABB(self.body_id, -1, physicsClientId=self.physics_client)
            return float((aabb[1][0] - aabb[0][0]) / 2.0)
        except Exception:
            return 0.080

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
        """Return the dynamic maximum Y threshold for spout detection."""
        idx = self.spout_link_idx
        if idx is not None:
            aabb = p.getAABB(self.body_id, idx, physicsClientId=self.physics_client)
            return float(aabb[0][1] + 0.010)
        return 0.030

    @property
    def fallen_max_radius(self) -> float:
        """Return the dynamic threshold radius beyond which particles have fallen."""
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
        """Return target velocity of impeller."""
        if hasattr(self.provider, "room") and self.provider.room:
            room = self.provider.room
            if "impeller" in room:
                impeller_shape = room["impeller"][0]
                return float(getattr(impeller_shape, "urdf_motor_target", 15.0))
        return 15.0

    @property
    def impeller_force(self) -> float:
        """Return force limit of impeller."""
        if hasattr(self.provider, "room") and self.provider.room:
            room = self.provider.room
            if "impeller" in room:
                impeller_shape = room["impeller"][0]
                return float(getattr(impeller_shape, "urdf_motor_force", 10.0))
        return 10.0

    @property
    def tube_outer_radius(self) -> float:
        """Return tube outer radius dynamically from its AABB."""
        idx = self.tube_link_idx
        if idx is not None and self.body_id is not None and self.physics_client is not None:
            aabb = p.getAABB(self.body_id, idx, physicsClientId=self.physics_client)
            return float((aabb[1][0] - aabb[0][0]) / 2.0)
        return 0.008

    @property
    def tube_offset_mm(self) -> float:
        """Return tube offset in mm."""
        idx = self.tube_link_idx
        if idx is not None and self.body_id is not None and self.physics_client is not None:
            info = p.getJointInfo(self.body_id, idx, physicsClientId=self.physics_client)
            tube_y = info[14][1]
            bowl_r_mm = self.bowl_outer_radius * 1000.0
            tube_r_mm = self.tube_outer_radius * 1000.0
            tube_y_mm = tube_y * 1000.0
            return float(bowl_r_mm - tube_r_mm - tube_y_mm)
        return 15.0

    def update_water(self, physics_client: int) -> None:
        """Step simulation and apply SPH fluid and boundary forces in JAX."""
        if not self.fluid or not self.spawner:
            return

        pos_np = np.array(self.pos_jax)
        vel_np = np.array(self.vel_jax)

        active_indices = np.where(pos_np[:, 2] < 100.0)[0]

        idx_map = self.default_idx_map.copy()
        if len(active_indices) > 0:
            active_pos = pos_np[active_indices]
            tree = cKDTree(active_pos)
            k_query = min(64 + 1, len(active_indices))
            dists, indices = tree.query(active_pos, k=k_query, distance_upper_bound=self.fluid.h)

            neigh_indices = indices[:, 1:] if k_query > 1 else indices[:, :0]

            mapper = np.empty(len(active_indices) + 1, dtype=np.int32)
            mapper[:-1] = active_indices
            mapper[-1] = self.n_particles

            mapped_neighs = mapper[neigh_indices]
            self_active_indices = np.array(active_indices)[:, None]
            mapped_neighs = np.where(mapped_neighs == self.n_particles, self_active_indices, mapped_neighs)

            cols = mapped_neighs.shape[1]
            idx_map[active_indices, :cols] = mapped_neighs
            idx_map_jax = jnp.array(idx_map)
        else:
            idx_map_jax = jnp.array(idx_map)

        # Query dynamic world transforms of container components from PyBullet
        bowl_pos, bowl_orn = p.getBasePositionAndOrientation(self.body_id, physicsClientId=physics_client)
        bowl_info = self.boundaries.get("bowl", {})
        bowl_radius = bowl_info.get("radius", 0.076)
        bowl_height = bowl_info.get("height", 0.096)
        bowl_z_offset = bowl_info.get("xyz", [0.0, 0.0, 0.004])[2]

        tube_info = self.boundaries.get("tube", {})
        t_idx = tube_info.get("link_idx")
        if t_idx is not None and t_idx != -1:
            state = p.getLinkState(self.body_id, t_idx, physicsClientId=physics_client)
            tube_pos, tube_orn = state[4], state[5]
        else:
            tube_pos, tube_orn = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]
        tube_outer_radius = tube_info.get("radius", 0.008)
        tube_inner_radius = tube_outer_radius - (self.provider.settings.tube_thickness * 0.001)
        tube_height = tube_info.get("height", 0.120)

        impeller_info = self.boundaries.get("impeller", {})
        imp_idx = impeller_info.get("link_idx")
        if imp_idx is not None and imp_idx != -1:
            state = p.getLinkState(self.body_id, imp_idx, physicsClientId=physics_client)
            impeller_pos, impeller_orn = state[4], state[5]
        else:
            impeller_pos, impeller_orn = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]
        impeller_radius = impeller_info.get("radius", 0.005)
        impeller_hub_radius = (self.provider.settings.impeller_shaft_radius + 1.0) * 0.001
        impeller_height = impeller_info.get("height", 0.015)

        # Settling phase damping and linear impeller speed ramping
        settling_steps = 40
        ramp_steps = 50
        step_idx = len(self.torques)
        target_omega = self.impeller_target_velocity

        if step_idx < settling_steps:
            omega = 0.0
            damping = 0.95
        else:
            ramp_progress = min(1.0, (step_idx - settling_steps) / ramp_steps)
            omega = ramp_progress * target_omega
            damping = 0.998

        # Sync PyBullet joint velocity target dynamically
        if self.body_id:
            motor_idx = self._get_link_index(self.body_id, physics_client, "impeller")
            if motor_idx is not None:
                p.setJointMotorControl2(
                    bodyUniqueId=self.body_id,
                    jointIndex=motor_idx,
                    controlMode=p.VELOCITY_CONTROL,
                    targetVelocity=omega,
                    force=self.impeller_force,
                    physicsClientId=physics_client,
                )

        t_start = self.current_sim_time

        dt = 1.0 / 240.0
        n_substeps = 5
        dt_sub = dt / n_substeps

        self.pos_jax, self.vel_jax, torque_accum = _physics_step_jax(
            self.pos_jax,
            self.vel_jax,
            idx_map_jax,
            self.particle_mass,
            self.fluid.h,
            self.REST_DENSITY,
            self.VISCOSITY,
            self.STIFFNESS,
            self.fluid.poly6_factor,
            self.fluid.spiky_grad_factor,
            self.fluid.visc_lap_factor,
            dt_sub,
            n_substeps,
            jnp.array([0.0, 0.0, -9.81], dtype=jnp.float32),
            jnp.array(bowl_pos, dtype=jnp.float32),
            jnp.array(bowl_orn, dtype=jnp.float32),
            bowl_radius,
            bowl_height,
            bowl_z_offset,
            jnp.array(tube_pos, dtype=jnp.float32),
            jnp.array(tube_orn, dtype=jnp.float32),
            tube_outer_radius,
            tube_inner_radius,
            tube_height,
            jnp.array(impeller_pos, dtype=jnp.float32),
            jnp.array(impeller_orn, dtype=jnp.float32),
            impeller_radius,
            impeller_hub_radius,
            impeller_height,
            omega,
            t_start,
            0.0015,  # blade_thickness
            4.0,  # num_blades
            1000.0,  # K_boundary
            0.3,  # D_boundary
            PARTICLE_RADIUS,
            damping,
        )
        avg_step_torque = float(torque_accum) / n_substeps
        self.torques.append(avg_step_torque)

        # Apply fluid reaction torque back to the impeller in PyBullet to propagate the SPH interaction
        imp_info = self.boundaries.get("impeller", {})
        motor_idx = imp_info.get("link_idx")
        if motor_idx is not None and motor_idx != -1:
            p.applyExternalTorque(
                objectUniqueId=self.body_id,
                linkIndex=motor_idx,
                torqueObj=[0.0, 0.0, avg_step_torque],  # torque is already negative/opposing
                flags=p.LINK_FRAME,
                physicsClientId=physics_client,
            )

        assert self.pos_jax is not None
        self.last_positions = self.pos_jax.tolist()
        self.current_sim_time += dt

    def setup_simulation(
        self,
        body_id: int,
        physics_client: int,
        sim_name: str,
        boundaries: dict[str, Any],
    ) -> None:
        """Configure motor control, parse analytical URDF boundaries, and initialize JAX simulation arrays."""
        self.body_id = body_id
        self.physics_client = physics_client

        motor_idx = self._get_link_index(body_id, physics_client, "impeller")
        if motor_idx is not None:
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=motor_idx,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=0.0,
                force=self.impeller_force,
                physicsClientId=physics_client,
            )

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
        # Note: Do not spawn particles in PyBullet for the main simulation to maximize performance.
        # We manually initialize self.spawner.active_count instead of calling spawner.spawn_all_at_positions().
        self.spawner.active_count = self.n_particles

        self.fluid = Fluid(
            r_s=r_s,
            rest_density=self.REST_DENSITY,
            viscosity=self.VISCOSITY,
            stiffness=self.STIFFNESS,
        )

        self.default_idx_map = np.arange(self.n_particles)[:, None]
        self.default_idx_map = np.repeat(self.default_idx_map, 64, axis=1)

        # Parse boundaries metadata
        self.boundaries = {}
        for k, v in boundaries.items():
            b_info = dict(v)
            xyz_val = b_info.get("xyz")
            if isinstance(xyz_val, str):
                b_info["xyz"] = [float(x) for x in xyz_val.split()]
            elif xyz_val is None:
                b_info["xyz"] = [0.0, 0.0, 0.0]

            rpy_val = b_info.get("rpy")
            if isinstance(rpy_val, str):
                b_info["rpy"] = [float(x) for x in rpy_val.split()]
            elif rpy_val is None:
                b_info["rpy"] = [0.0, 0.0, 0.0]
            self.boundaries[k] = b_info

        # Dynamically link named URDF boundaries to PyBullet body link indices
        for link_name, b_info in self.boundaries.items():
            if link_name == "bowl":
                b_info["link_idx"] = -1
            else:
                b_info["link_idx"] = self._get_link_index(body_id, physics_client, link_name)

        # Generate grid points to initially fill the bowl
        grid_points = []
        spacing = 1.6 * r_s

        tube_x, tube_y = 0.0, 0.0
        tube_idx = self.tube_link_idx
        if tube_idx is not None:
            info = p.getJointInfo(self.body_id, tube_idx, physicsClientId=physics_client)
            tube_x, tube_y = info[14][0], info[14][1]

        bowl_radius = self.provider.settings.bowl_radius * 0.001
        bowl_thickness = self.provider.settings.bowl_thickness * 0.001
        bowl_inner_radius = bowl_radius - bowl_thickness
        tube_r = self.tube_outer_radius

        max_r_sq = (bowl_inner_radius - BOWL_WALL_BUFFER) ** 2
        min_r_sq = (tube_r + BOWL_WALL_BUFFER) ** 2

        xy_coords = []
        lim = int(math.ceil(bowl_inner_radius / spacing))
        for ix in range(-lim, lim + 1):
            for iy in range(-lim, lim + 1):
                x = ix * spacing
                y = iy * spacing
                if x**2 + y**2 < max_r_sq and (x - tube_x) ** 2 + (y - tube_y) ** 2 > min_r_sq:
                    xy_coords.append((x, y))

        xy_coords.sort(key=lambda pt: pt[0] ** 2 + pt[1] ** 2)

        # Spawn particles above the bottom bowl plate to avoid boundary penetration at step 1
        # Spawn particles at physical rest height relative to the bowl bottom
        z = bowl_thickness + r_s
        while len(grid_points) < self.n_particles:
            for x, y in xy_coords:
                if len(grid_points) >= self.n_particles:
                    break
                grid_points.append((x, y, z))
            z += spacing

        # Transform spawned points from bowl local coordinates to world coordinates
        bowl_pos, bowl_orn = p.getBasePositionAndOrientation(body_id, physicsClientId=physics_client)
        world_grid_points = []
        for pt in grid_points:
            wpt, _ = p.multiplyTransforms(bowl_pos, bowl_orn, pt, [0.0, 0.0, 0.0, 1.0])
            world_grid_points.append(wpt)

        self.pos_jax = jnp.array(world_grid_points, dtype=jnp.float32)
        self.vel_jax = jnp.zeros((self.n_particles, 3), dtype=jnp.float32)
        self.last_positions = world_grid_points
        self.current_sim_time = 0.0
        self.torques = []

    def step_simulation(
        self,
        body_id: int,
        physics_client: int,
        step_index: int,
        sim_name: str,
    ) -> str | None:
        """Step JAX simulation, classify particles, and manage deactivation."""
        self.body_id = body_id
        self.physics_client = physics_client

        self.update_water(physics_client)

        positions = self.last_positions
        pos_np = np.array(positions)
        if len(pos_np) > 0:
            xs = pos_np[:, 0]
            ys = pos_np[:, 1]
            zs = pos_np[:, 2]

            active_mask = zs < 100.0

            # Spout indices
            spout_indices = np.where(active_mask & (zs >= self.spout_min_height) & (ys < self.spout_max_y))[0]
            for idx in spout_indices:
                self.provider.spout_water_ids.add(idx)

            # Fallen indices
            fallen_indices = np.where(
                active_mask & ((zs < FALLEN_MIN_HEIGHT) | (xs**2 + ys**2 > self.fallen_max_radius**2))
            )[0]

            if len(fallen_indices) > 0:
                pos_arr = np.array(self.pos_jax)
                vel_arr = np.array(self.vel_jax)
                for idx in fallen_indices:
                    self.provider.fallen_out_water_ids.add(idx)
                    pos_arr[idx] = [0.0, 0.0, 1000.0]
                    vel_arr[idx] = [0.0, 0.0, 0.0]
                self.pos_jax = jnp.array(pos_arr)
                self.vel_jax = jnp.array(vel_arr)
                assert self.pos_jax is not None
                self.last_positions = self.pos_jax.tolist()

        # Compute volumes in liters
        spout_vol = len(self.provider.spout_water_ids) * self.vol_s * M3_TO_LITERS
        fallen_vol = len(self.provider.fallen_out_water_ids) * self.vol_s * M3_TO_LITERS

        # We don't terminate when spout volume is reached, to run the full simulation
        # if spout_vol >= VOLUME_THRESHOLD_LITERS:
        #     return f"{VOLUME_THRESHOLD_LITERS}L of water spout volume reached"
        if fallen_vol >= FALLEN_THRESHOLD_LITERS:
            return f"{FALLEN_THRESHOLD_LITERS}L of water fell out of bowl"
        return None

    def teardown_simulation(
        self,
        body_id: int,
        physics_client: int,
        sim_name: str,
    ) -> None:
        """Calculate and store the impeller torque and recommended DC motor specifications programmatically."""
        if not self.torques:
            return

        torques_np = np.array(self.torques)
        self.average_torque = float(np.mean(torques_np))
        self.peak_torque = float(np.max(torques_np))

        omega = self.impeller_target_velocity  # in rad/s
        self.rpm = omega * 60.0 / (2.0 * math.pi)

        # Mechanical Power P = torque * omega (Watts)
        self.average_mech_power = self.average_torque * omega
        self.peak_mech_power = self.peak_torque * omega

        # Electrical Power assuming BLDC motor efficiency of ~40% for small hobby submersible pumps
        motor_efficiency = 0.40
        self.average_elec_power = self.average_mech_power / motor_efficiency
        self.peak_elec_power = self.peak_mech_power / motor_efficiency

        # Recommended DC motor characteristics
        # Voltage = 5.0V USB standard
        recommended_voltage = 5.0
        self.average_current_ma = (self.average_elec_power / recommended_voltage) * 1000.0
        self.peak_current_ma = (self.peak_elec_power / recommended_voltage) * 1000.0

        # Torque in g*cm (1 N*m = 10197.16 g*cm)
        self.average_torque_gcm = self.average_torque * 10197.16
        self.peak_torque_gcm = self.peak_torque * 10197.16
