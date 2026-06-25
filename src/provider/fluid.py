"""Fluid simulation classes and JAX solvers for SPH based fluid dynamics with boundary rejection."""

from __future__ import annotations
import math
from enum import Enum, IntEnum
import random
from typing import Any, Optional, cast, TYPE_CHECKING
import jax
import jax.numpy as jnp
import numpy as np
import pybullet as p
from scipy.spatial import cKDTree  # type: ignore

from provider.types import CollisionGroup, CollisionMask, URDFShape
from provider.room import BulletStateTracker
from provider.bullet import LinkType, _is_real_physics_client

if TYPE_CHECKING:
    from model import BoundaryConfig, FluidConfig, FluidMotorConfig


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


# JIT compiled SPH force computation
@jax.jit
def _compute_forces_jax(
    positions: jnp.ndarray,
    velocities: jnp.ndarray,
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
    """Compute SPH forces (pressure + viscosity) using vectorized JAX."""
    n = positions.shape[0]
    h2 = h * h

    # Pairwise difference vectors: shape (N, N, 3)
    diff = positions[:, None, :] - positions[None, :, :]

    # Pairwise squared distances: shape (N, N)
    r2 = jnp.sum(diff * diff, axis=-1)

    # Neighborhood mask (distance < h)
    mask = r2 < h2

    # 1. Compute density for each particle
    w = poly6_factor * (jnp.maximum(h2 - r2, 0.0) ** 3) * mask
    densities = jnp.sum(mass * w, axis=1)

    # Clamp density to rest_density to prevent negative pressures
    densities = jnp.maximum(densities, rest_density)

    # Ideal gas equation of state
    pressures = stiffness * (densities - rest_density)

    # 2. Compute forces for each particle
    r = jnp.sqrt(r2 + min_dist_threshold * min_dist_threshold)

    # Spiky kernel gradient
    hr = jnp.maximum(h - r, 0.0)
    grad_coeff = spiky_grad_factor * (hr**2) * mask

    # Pressure force term
    p_term = mass * (pressures[:, None] + pressures[None, :]) / (pressure_avg_factor * densities[None, :])

    direction = diff / r[:, :, None]

    # Exclude self-interaction (i == j)
    self_mask = (1.0 - jnp.eye(n))[:, :, None]

    f_press = -p_term[:, :, None] * grad_coeff[:, :, None] * direction * self_mask
    f_press_total = jnp.sum(f_press, axis=1)

    # Viscosity force term
    lap_coeff = visc_lap_factor * hr * mask

    # Relative velocities
    v_diff = velocities[None, :, :] - velocities[:, None, :]
    v_term = viscosity * mass / densities[None, :, None] * lap_coeff[:, :, None]

    f_visc = v_term * v_diff * self_mask
    f_visc_total = jnp.sum(f_visc, axis=1)

    vol_factor = (mass / densities)[:, None]
    f_press_scaled = f_press_total * vol_factor
    f_visc_scaled = f_visc_total * vol_factor

    return f_press_scaled + f_visc_scaled


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

    # Pad positions and velocities with a dummy particle at index n
    padded_positions = jnp.vstack([positions, jnp.array([[0.0, 0.0, 1000.0]])])
    padded_velocities = jnp.vstack([velocities, jnp.zeros((1, 3))])

    neigh_positions = padded_positions[idx_map]  # Shape (N, M, 3)
    neigh_velocities = padded_velocities[idx_map]  # Shape (N, M, 3)

    diff = positions[:, None, :] - neigh_positions  # Shape (N, M, 3)
    r2 = jnp.sum(diff * diff, axis=-1)  # Shape (N, M)

    # Mask out self-interaction and padding elements (indices matching self or equal to n)
    neigh_mask = (idx_map != jnp.arange(n)[:, None]) & (idx_map != n)

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

    # Pad densities and pressures to index them safely using idx_map
    padded_densities = jnp.append(densities, rest_density)
    padded_pressures = jnp.append(pressures, 0.0)

    neigh_densities = padded_densities[idx_map]
    neigh_pressures = padded_pressures[idx_map]

    p_term = mass * (pressures[:, None] + neigh_pressures) / (pressure_avg_factor * neigh_densities)
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
def _compute_boundary_forces_jax(
    pos: jnp.ndarray,
    vel: jnp.ndarray,
    r_s: float,
    K: float,
    D: float,
    # Cylinder Cavity (formerly bowl)
    cavity_pos: jnp.ndarray,
    cavity_orn: jnp.ndarray,
    cavity_radius: float,
    cavity_height: float,
    cavity_z_offset: float,
    # Hollow Cylinder (formerly tube)
    hollow_cyl_pos: jnp.ndarray,
    hollow_cyl_orn: jnp.ndarray,
    hollow_cyl_outer_radius: float,
    hollow_cyl_inner_radius: float,
    hollow_cyl_height: float,
    slot_height: float,
    # Rotary Vanes (formerly impeller)
    vanes_pos: jnp.ndarray,
    vanes_orn: jnp.ndarray,
    vanes_radius: float,
    vanes_hub_radius: float,
    vanes_height: float,
    omega: float,
    t: float,
    vane_thickness: float,
    num_vanes: float,
    vane_twist_rad: float,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Compute mathematical penalty forces from cylinder cavity, hollow cylinder, and rotary vanes in JAX."""
    forces = jnp.zeros_like(pos)

    # --- CYLINDER CAVITY BOUNDARY ---
    cavity_orn_inv = q_inv(cavity_orn)
    pos_c = q_rotate(cavity_orn_inv, pos - cavity_pos)
    vel_c = q_rotate(cavity_orn_inv, vel)

    # 1. Cavity side wall (finite-height cup wall with containment active for r_c < cavity_radius + r_s)
    r_c = jnp.sqrt(pos_c[:, 0] ** 2 + pos_c[:, 1] ** 2)
    r_c = jnp.maximum(r_c, 1e-8)
    r_limit_c = cavity_radius - r_s
    pen_c_side = r_c - r_limit_c
    side_mask = pen_c_side > 0.0

    nx_c = -pos_c[:, 0] / r_c
    ny_c = -pos_c[:, 1] / r_c
    v_n_c = vel_c[:, 0] * (-nx_c) + vel_c[:, 1] * (-ny_c)
    f_mag_c_side = K * pen_c_side + D * jnp.maximum(v_n_c, 0.0)

    force_c_side = jnp.stack([f_mag_c_side * nx_c, f_mag_c_side * ny_c, jnp.zeros_like(r_c)], axis=-1)
    force_c_side = jnp.where(side_mask[:, None], force_c_side, 0.0)

    # 2. Cavity bottom
    z_limit_c = cavity_z_offset + r_s
    pen_c_bottom = z_limit_c - pos_c[:, 2]
    bottom_mask = pen_c_bottom > 0.0
    f_z_c = K * pen_c_bottom - D * vel_c[:, 2]
    force_c_bottom = jnp.stack([jnp.zeros_like(r_c), jnp.zeros_like(r_c), jnp.maximum(f_z_c, 0.0)], axis=-1)
    force_c_bottom = jnp.where(bottom_mask[:, None], force_c_bottom, 0.0)

    forces += q_rotate(cavity_orn, force_c_side + force_c_bottom)

    # --- HOLLOW CYLINDER BOUNDARY ---
    hollow_cyl_orn_inv = q_inv(hollow_cyl_orn)
    pos_hc = q_rotate(hollow_cyl_orn_inv, pos - hollow_cyl_pos)
    vel_hc = q_rotate(hollow_cyl_orn_inv, vel)

    # Active vertically within the physical tube height bounds (0 to hollow_cyl_height)
    height_mask = (pos_hc[:, 2] >= 0.0) & (pos_hc[:, 2] <= hollow_cyl_height)
    # Cutout slot at bottom: ry > 0 and rz < slot_height
    cutout_mask = (pos_hc[:, 2] < slot_height) & (pos_hc[:, 1] > 0.0)
    hollow_cyl_active_mask = height_mask & (~cutout_mask)

    r_hc = jnp.sqrt(pos_hc[:, 0] ** 2 + pos_hc[:, 1] ** 2)
    r_hc = jnp.maximum(r_hc, 1e-8)
    r_hc_mid = (hollow_cyl_inner_radius + hollow_cyl_outer_radius) / 2.0

    # 1. Inner cavity collision (r_hc < r_hc_mid)
    pen_hc_in = r_hc - (hollow_cyl_inner_radius - r_s)
    in_mask = hollow_cyl_active_mask & (hollow_cyl_inner_radius > 0.0) & (r_hc < r_hc_mid) & (pen_hc_in > 0.0)
    nx_hc_in = -pos_hc[:, 0] / r_hc
    ny_hc_in = -pos_hc[:, 1] / r_hc
    v_n_hc_in = vel_hc[:, 0] * (-nx_hc_in) + vel_hc[:, 1] * (-ny_hc_in)
    f_mag_hc_in = K * pen_hc_in + D * jnp.maximum(v_n_hc_in, 0.0)
    force_hc_in = jnp.stack([f_mag_hc_in * nx_hc_in, f_mag_hc_in * ny_hc_in, jnp.zeros_like(r_hc)], axis=-1)
    force_hc_in = jnp.where(in_mask[:, None], force_hc_in, 0.0)

    # 2. Outer solid cylinder collision (r_hc >= r_hc_mid)
    pen_hc_out = (hollow_cyl_outer_radius + r_s) - r_hc
    out_mask = hollow_cyl_active_mask & (hollow_cyl_outer_radius > 0.0) & (r_hc >= r_hc_mid) & (pen_hc_out > 0.0)
    nx_hc_out = pos_hc[:, 0] / r_hc
    ny_hc_out = pos_hc[:, 1] / r_hc
    v_n_hc_out = vel_hc[:, 0] * nx_hc_out + vel_hc[:, 1] * ny_hc_out
    f_mag_hc_out = K * pen_hc_out - D * v_n_hc_out
    force_hc_out = jnp.stack([f_mag_hc_out * nx_hc_out, f_mag_hc_out * ny_hc_out, jnp.zeros_like(r_hc)], axis=-1)
    force_hc_out = jnp.where((out_mask[:, None]) & (f_mag_hc_out[:, None] > 0.0), force_hc_out, 0.0)

    forces += q_rotate(hollow_cyl_orn, force_hc_in + force_hc_out)

    # --- ROTARY VANES BOUNDARY ---
    vanes_orn_inv = q_inv(vanes_orn)
    pos_v = q_rotate(vanes_orn_inv, pos - vanes_pos)
    vel_v = q_rotate(vanes_orn_inv, vel)

    r_v = jnp.sqrt(pos_v[:, 0] ** 2 + pos_v[:, 1] ** 2)
    r_v = jnp.maximum(r_v, 1e-8)

    vanes_height_mask = (pos_v[:, 2] >= 0.0) & (pos_v[:, 2] <= vanes_height)

    # 1. Hub solid cylinder
    pen_v_hub = (vanes_hub_radius + r_s) - r_v
    hub_mask = vanes_height_mask & (vanes_hub_radius > 0.0) & (pen_v_hub > 0.0)
    nx_v_hub = pos_v[:, 0] / r_v
    ny_v_hub = pos_v[:, 1] / r_v
    v_n_v_hub = vel_v[:, 0] * nx_v_hub + vel_v[:, 1] * ny_v_hub
    f_mag_v_hub = K * pen_v_hub - D * v_n_v_hub
    force_v_hub = jnp.stack([f_mag_v_hub * nx_v_hub, f_mag_v_hub * ny_v_hub, jnp.zeros_like(r_v)], axis=-1)
    force_v_hub = jnp.where((hub_mask[:, None]) & (f_mag_v_hub[:, None] > 0.0), force_v_hub, 0.0)

    # 2. Rotating Vanes (Blades)
    total_twist_rad = vane_twist_rad
    safe_height = jnp.where(vanes_height > 0.0, vanes_height, 1.0)
    pitch = total_twist_rad / safe_height
    theta_t = pos_v[:, 2] * pitch
    phi = jnp.arctan2(pos_v[:, 1], pos_v[:, 0])
    d_phi = phi - theta_t

    pi_N = jnp.pi / num_vanes
    d_phi_wrapped = (d_phi + pi_N) % (2.0 * pi_N) - pi_N

    dist_to_vane = r_v * jnp.sin(d_phi_wrapped)
    vane_threshold = vane_thickness / 2.0 + r_s
    pen_vane = vane_threshold - jnp.abs(dist_to_vane)

    vane_collision_mask = (
        vanes_height_mask & (vanes_radius > 0.0) & (r_v >= vanes_hub_radius) & (r_v <= vanes_radius) & (pen_vane > 0.0)
    )

    sign_dist = jnp.sign(d_phi_wrapped)
    normal_tx = -sign_dist * jnp.sin(phi - d_phi_wrapped)
    normal_ty = sign_dist * jnp.cos(phi - d_phi_wrapped)
    normal_tz = -sign_dist * r_v * pitch

    norm = jnp.sqrt(normal_tx**2 + normal_ty**2 + normal_tz**2)
    norm_safe = jnp.maximum(norm, 1e-8)
    normal_tx /= norm_safe
    normal_ty /= norm_safe
    normal_tz /= norm_safe

    v_vane_x = omega * r_v * (-jnp.sin(phi))
    v_vane_y = omega * r_v * jnp.cos(phi)

    v_rel_n_vane = (
        (vel_v[:, 0] - v_vane_x) * normal_tx + (vel_v[:, 1] - v_vane_y) * normal_ty + (vel_v[:, 2] - 0.0) * normal_tz
    )

    f_mag_vane = K * pen_vane - D * v_rel_n_vane
    force_vane = jnp.stack([f_mag_vane * normal_tx, f_mag_vane * normal_ty, f_mag_vane * normal_tz], axis=-1)
    force_vane = jnp.where((vane_collision_mask[:, None]) & (f_mag_vane[:, None] > 0.0), force_vane, 0.0)

    forces += q_rotate(vanes_orn, force_v_hub + force_vane)

    # Calculate reaction torque on the rotary vanes
    torque_z = pos_v[:, 1] * force_vane[:, 0] - pos_v[:, 0] * force_vane[:, 1]
    vanes_torque = jnp.sum(torque_z)

    return forces, vanes_torque


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
    # Cylinder Cavity
    cavity_pos: jnp.ndarray,
    cavity_orn: jnp.ndarray,
    cavity_radius: float,
    cavity_height: float,
    cavity_z_offset: float,
    # Hollow Cylinder
    hollow_cyl_pos: jnp.ndarray,
    hollow_cyl_orn: jnp.ndarray,
    hollow_cyl_outer_radius: float,
    hollow_cyl_inner_radius: float,
    hollow_cyl_height: float,
    slot_height: float,
    # Rotary Vanes
    vanes_pos: jnp.ndarray,
    vanes_orn: jnp.ndarray,
    vanes_radius: float,
    vanes_hub_radius: float,
    vanes_height: float,
    omega: float,
    t_start: float,
    vane_thickness: float,
    num_vanes: float,
    vane_twist_rad: float,
    K_boundary: float,
    D_boundary: float,
    r_s: float,
    pressure_avg_factor: float = 2.0,
    min_dist_threshold: float = 1e-6,
    damping: float = -1.0,
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
            pressure_avg_factor,
            min_dist_threshold,
        )

        # Boundary forces
        b_forces, step_torque = _compute_boundary_forces_jax(
            pos_curr,
            vel_curr,
            r_s,
            K_boundary,
            D_boundary,
            cavity_pos,
            cavity_orn,
            cavity_radius,
            cavity_height,
            cavity_z_offset,
            hollow_cyl_pos,
            hollow_cyl_orn,
            hollow_cyl_outer_radius,
            hollow_cyl_inner_radius,
            hollow_cyl_height,
            slot_height,
            vanes_pos,
            vanes_orn,
            vanes_radius,
            vanes_hub_radius,
            vanes_height,
            omega,
            t_curr,
            vane_thickness,
            num_vanes,
            vane_twist_rad,
        )

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
        active_mask = pos_curr[:, 2] < 100.0
        speeds = jnp.linalg.norm(vel_curr, axis=1)
        num_active = jnp.sum(active_mask)
        total_speed = jnp.sum(speeds * active_mask)
        avg_speed = jnp.where(num_active > 0.0, total_speed / num_active, 0.0)

        v_target = jnp.abs(omega) * 0.015
        gamma_base = jnp.where(jnp.abs(omega) > 0.0, 0.95, 0.998)

        v_excess = jnp.maximum(0.0, avg_speed - v_target)
        dynamic_damping = gamma_base - 0.16 * v_excess
        dynamic_damping = jnp.maximum(0.90, jnp.minimum(gamma_base, dynamic_damping))

        damping_val = jnp.where(damping >= 0.0, damping, dynamic_damping)

        vel_next = jnp.where(active, (vel_curr + accel * dt_sub) * damping_val, 0.0)
        pos_next = jnp.where(active, pos_curr + vel_next * dt_sub, pos_curr)

        # Accumulate torque
        torque_accum_next = torque_accum + step_torque

        return pos_next, vel_next, torque_accum_next

    return jax.lax.fori_loop(0, n_substeps, body_fun, (pos, vel, 0.0))


class FluidSpawner:
    """Helper class to manage PyBullet body spawning, shapes, and state for fluid particles."""

    def __init__(
        self,
        physics_client: int,
        r_s: float,
        n_particles: int,
        particle_mass: float,
        particle_color: list[float],
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
            shapeType=p.GEOM_SPHERE,
            radius=r_s,
            rgbaColor=particle_color,
            physicsClientId=physics_client,
        )

        self.linear_damping = linear_damping
        self.angular_damping = angular_damping
        self.lateral_friction = lateral_friction
        self.restitution = restitution

        self.particle_body_ids: list[int] = []
        self.active_count: int = 0

    def spawn_batch(self, spawn_z: float, batch_size: int, spacing: float) -> int:
        """Spawn a batch of fluid particles up to n_particles total."""
        if self.active_count >= self.n_particles:
            return 0
        to_activate = min(batch_size, self.n_particles - self.active_count)
        for i in range(to_activate):
            jitter_x = random.uniform(-2 * self.r_s, 2 * self.r_s)
            jitter_y = random.uniform(-2 * self.r_s, 2 * self.r_s)
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
            self.particle_body_ids.append(w_id)
        self.active_count += to_activate
        return to_activate

    def spawn_all_at_positions(self, positions: list[tuple[float, float, float]]) -> None:
        """Spawn all fluid particles at specified 3D positions."""
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
            self.particle_body_ids.append(w_id)
        self.active_count = len(self.particle_body_ids)

    def get_positions_and_velocities(
        self, fallen_ids: set[int] | None = None
    ) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
        """Return positions and velocities of all particles, padding unspawned ones to keep constant shapes."""
        positions = []
        velocities = []
        if fallen_ids is None:
            fallen_ids = set()

        for w_id in self.particle_body_ids:
            if w_id in fallen_ids:
                positions.append((0.0, 0.0, 1000.0))
                velocities.append((0.0, 0.0, 0.0))
            else:
                pos, _ = p.getBasePositionAndOrientation(w_id, physicsClientId=self.physics_client)
                vel, _ = p.getBaseVelocity(w_id, physicsClientId=self.physics_client)
                positions.append(pos)
                velocities.append(vel)

        unspawned_count = self.n_particles - len(self.particle_body_ids)
        if unspawned_count > 0:
            positions.extend([(0.0, 0.0, 1000.0)] * unspawned_count)
            velocities.extend([(0.0, 0.0, 0.0)] * unspawned_count)

        return positions, velocities


class Fluid:
    """Handles SPH fluid dynamics simulation for fluid particles in PyBullet using JAX."""

    PARTICLE_COLOR = [0.5, 0.8, 1.0, 1.0]
    LINEAR_DAMPING = 0.05
    ANGULAR_DAMPING = 0.05
    LATERAL_FRICTION = 0.1
    RESTITUTION = 0.0
    REST_DENSITY = 1000.0
    VISCOSITY = 0.02
    STIFFNESS = 100.0
    DEACTIVATION_BOX_FACTOR = 50.0

    def __init__(
        self,
        config: Optional[FluidConfig] = None,
        provider: Any = None,
        body_id: Optional[int] = None,
        physics_client: Optional[int] = None,
        state_tracker: Optional[Any] = None,
        link_indices: Optional[dict[LinkType, Optional[int]]] = None,
    ):
        """Initialize the fluid simulation constants and state using a FluidConfig."""
        from model import BoundaryConfig, FluidConfig, FluidMotorConfig

        if config is None:
            config = FluidConfig()

        self.provider = provider

        particle_rad = config.r_s if config.r_s is not None else config.particle_radius
        self.particle_radius = particle_rad
        self.r_s = self.particle_radius

        self.target_volume = config.target_volume
        self.bowl_wall_buffer = config.bowl_wall_buffer
        self.rest_density = config.rest_density
        self.viscosity = config.viscosity

        stiff = config.k if config.k is not None else config.stiffness
        self.stiffness = stiff
        self.k = self.stiffness

        self.smoothing_factor = config.smoothing_factor
        self.sphere_vol_factor = config.sphere_vol_factor
        self.poly6_coeff_numerator = config.poly6_coeff_numerator
        self.poly6_coeff_denominator = config.poly6_coeff_denominator
        self.spiky_grad_coeff = config.spiky_grad_coeff
        self.visc_lap_coeff = config.visc_lap_coeff
        self.pressure_avg_factor = config.pressure_avg_factor
        self.min_distance_threshold = config.min_distance_threshold

        self.characteristic_length = config.characteristic_length
        self.volume_threshold_liters = config.volume_threshold_liters
        self.fallen_threshold_liters = config.fallen_threshold_liters
        self.recycle_fluid = config.recycle_fluid
        self.neighbor_list_box = config.neighbor_list_box
        self.vane_twist = config.vane_twist
        self.slot_height = config.slot_height

        # SPH values computed from settings
        self.h = self.smoothing_factor * self.r_s
        self.mass = self.sphere_vol_factor * math.pi * (self.r_s**3) * self.rest_density

        # Precompute kernel constants
        self.poly6_factor = self.poly6_coeff_numerator / (self.poly6_coeff_denominator * math.pi * (self.h**9))
        self.spiky_grad_factor = self.spiky_grad_coeff / (math.pi * (self.h**6))
        self.visc_lap_factor = self.visc_lap_coeff / (math.pi * (self.h**6))

        # Simulator state variables (formerly from FluidSimulator)
        self.spawner = None
        self.body_id = body_id
        self.physics_client = physics_client
        self.boundaries: dict[LinkType, BoundaryConfig] = {}
        self.pos_jax = None
        self.vel_jax = None
        vol_s = (4.0 / 3.0) * math.pi * (self.r_s**3)
        self.n_particles = int(round(self.target_volume / vol_s))
        self.last_positions: list[list[float]] = []
        self.current_sim_time = 0.0
        self.torques: list[float] = []
        self.motor_config = FluidMotorConfig()
        self.spout_water_ids = set()
        self.fallen_out_water_ids = set()
        self.state_tracker = state_tracker

        self._cached_active_indices = None
        self._cached_mapper = None
        self._cached_self_active_indices = None

        self.link_indices = link_indices if link_indices is not None else {}

        if config.gravity is not None:
            self.gravity = config.gravity
        elif hasattr(self.provider, "room") and self.provider.room and hasattr(self.provider.room, "gravity"):
            self.gravity = self.provider.room.gravity
        else:
            self.gravity = (0.0, 0.0, -9.81)

        if physics_client is not None and body_id is not None and config.boundaries is not None:
            if state_tracker is not None:
                state_tracker.has_fluid_simulator = True
                state_tracker.particle_positions = self.get_particle_positions()
                state_tracker.particle_colors = self.get_particle_colors()
                state_tracker.particle_radii = self.get_particle_radii()

            self.spawner = FluidSpawner(
                physics_client=physics_client,
                r_s=self.r_s,
                n_particles=self.n_particles,
                particle_mass=self.particle_mass,
                particle_color=self.PARTICLE_COLOR,
                linear_damping=0.05,
                angular_damping=0.05,
                lateral_friction=0.1,
                restitution=0.0,
            )
            self.spawner.active_count = self.n_particles

            self.default_idx_map = np.arange(self.n_particles)[:, None]
            self.default_idx_map = np.repeat(self.default_idx_map, 64, axis=1)

            # Parse boundaries metadata using BoundaryConfig Pydantic model and link indices
            for _, v in config.boundaries.items():
                if isinstance(v, BoundaryConfig):
                    b_info = v
                else:
                    b_info = BoundaryConfig.model_validate(v)

                if b_info.link_type is not None:
                    b_info.link_idx = (
                        -1 if b_info.link_type == LinkType.BASE else self.link_indices.get(b_info.link_type)
                    )
                    self.boundaries[b_info.link_type] = b_info

            # Generate grid points to initially fill the cavity
            grid_points: list[tuple[float, float, float]] = []
            spacing = 1.6 * self.r_s

            hc_idx = self.link_indices.get(LinkType.TUBE)
            hc_x, hc_y = (
                (p.getJointInfo(self.body_id, hc_idx, physicsClientId=physics_client)[14][:2])
                if hc_idx is not None
                else (0.0, 0.0)
            )

            cavity_info = self.boundaries.get(LinkType.BASE)
            cavity_inner_radius = cavity_info.radius if cavity_info and cavity_info.radius is not None else 0.076
            cavity_z_offset = cavity_info.xyz[2] if cavity_info else 0.004
            hc_r = self.radii[LinkType.TUBE]

            max_r_sq = (cavity_inner_radius - self.bowl_wall_buffer) ** 2
            min_r_sq = (hc_r + self.bowl_wall_buffer) ** 2

            xy_coords = []
            lim = int(math.ceil(cavity_inner_radius / spacing))
            for ix in range(-lim, lim + 1):
                for iy in range(-lim, lim + 1):
                    x = ix * spacing
                    y = iy * spacing
                    if x**2 + y**2 < max_r_sq and (x - hc_x) ** 2 + (y - hc_y) ** 2 > min_r_sq:
                        xy_coords.append((x, y))

            xy_coords.sort(key=lambda pt: pt[0] ** 2 + pt[1] ** 2)
            self.spawn_xy_coords = xy_coords

            # Spawn particles above bottom plate
            z = cavity_z_offset + self.r_s + self.bowl_wall_buffer
            while len(grid_points) < self.n_particles:
                for x, y in xy_coords:
                    if len(grid_points) >= self.n_particles:
                        break
                    grid_points.append((x, y, z))
                z += spacing

            # Transform spawned points from local coordinates to world coordinates
            bowl_pos, bowl_orn = self._get_base_link_origin(body_id, physics_client)
            world_grid_points = []
            for pt in grid_points:
                wpt, _ = p.multiplyTransforms(bowl_pos, bowl_orn, pt, [0.0, 0.0, 0.0, 1.0])
                world_grid_points.append(wpt)

            self.pos_jax = jnp.array(world_grid_points, dtype=jnp.float32)
            self.vel_jax = jnp.zeros((self.n_particles, 3), dtype=jnp.float32)
            self.last_positions = world_grid_points

    @property
    def particle_mass(self) -> float:
        """Calculate physical mass of a particle."""
        vol_s = (4.0 / 3.0) * math.pi * (self.r_s**3)
        return float(vol_s * self.rest_density)

    @property
    def particle_body_ids(self) -> list[int]:
        """Return dummy IDs for compatibility."""
        return list(range(self.n_particles))

    @property
    def active_count(self) -> int:
        """Return number of particles."""
        return self.n_particles

    @property
    def vol_s(self) -> float:
        """Return volume of a particle."""
        return (4.0 / 3.0) * math.pi * (self.r_s**3)

    def _get_base_link_origin(
        self, body_id: int, physics_client: int
    ) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
        """Get the true base link origin by subtracting the local inertia offset."""
        if _is_real_physics_client(physics_client):
            base_pos, base_orn = p.getBasePositionAndOrientation(body_id, physicsClientId=physics_client)
            dynamics = p.getDynamicsInfo(body_id, -1, physicsClientId=physics_client)
            local_inertia_pos = dynamics[3]
            local_inertia_orn = dynamics[4]
            inv_inertia_pos, inv_inertia_orn = p.invertTransform(local_inertia_pos, local_inertia_orn)
            return p.multiplyTransforms(base_pos, base_orn, inv_inertia_pos, inv_inertia_orn)
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)

    def get_particle_positions(self) -> list[list[float]]:
        """Return particle positions for logger."""
        return self.last_positions

    def get_particle_colors(self) -> list[list[float]]:
        """Return particle colors for logger."""
        return [self.PARTICLE_COLOR] * self.n_particles

    def get_particle_radii(self) -> list[float]:
        """Return particle radii for logger."""
        return [self.r_s] * self.n_particles

    def compute_forces_jax(
        self,
        pos_jax: jnp.ndarray,
        vel_jax: jnp.ndarray,
        idx_map: Optional[jnp.ndarray] = None,
    ) -> jnp.ndarray:
        """Compute SPH forces for all particles returning a JAX array."""
        if idx_map is not None:
            return _compute_forces_neighbor_list_jax(
                pos_jax,
                vel_jax,
                idx_map,
                self.mass,
                self.h,
                self.rest_density,
                self.viscosity,
                self.stiffness,
                self.poly6_factor,
                self.spiky_grad_factor,
                self.visc_lap_factor,
                self.pressure_avg_factor,
                self.min_distance_threshold,
            )
        return _compute_forces_jax(
            pos_jax,
            vel_jax,
            self.mass,
            self.h,
            self.rest_density,
            self.viscosity,
            self.stiffness,
            self.poly6_factor,
            self.spiky_grad_factor,
            self.visc_lap_factor,
            self.pressure_avg_factor,
            self.min_distance_threshold,
        )

    def compute_forces(
        self,
        positions: list[tuple[float, float, float]],
        velocities: list[tuple[float, float, float]],
    ) -> list[list[float]]:
        """Compute SPH forces for all particles using JAX."""
        n = len(positions)
        if n == 0:
            return []

        # Convert to JAX arrays
        pos_jax = jnp.array(positions, dtype=jnp.float32)
        vel_jax = jnp.array(velocities, dtype=jnp.float32)

        forces_jax = self.compute_forces_jax(pos_jax, vel_jax)

        # Convert back to standard list of lists
        return forces_jax.tolist()

    def compute_knudsen_number(
        self,
        positions: list[tuple[float, float, float]],
        characteristic_length: Optional[float] = None,
    ) -> float:
        """Calculate the Knudsen number (Kn = mean_free_path / L)."""
        if characteristic_length is None:
            characteristic_length = self.characteristic_length
        n = len(positions)
        if n < 2:
            return 0.0

        pos_jax = jnp.array(positions, dtype=jnp.float32)

        diff = pos_jax[:, None, :] - pos_jax[None, :, :]
        r2 = jnp.sum(diff * diff, axis=-1)

        self_mask_large = jnp.eye(n) * 1e10
        r2_masked = r2 + self_mask_large

        min_dists = jnp.sqrt(jnp.min(r2_masked, axis=1))
        mean_free_path = jnp.mean(min_dists)

        return float(mean_free_path / characteristic_length)

    @property
    def radii(self) -> dict[LinkType, float]:
        """Return dict mapping LinkType keys to their float radius values."""
        hc_idx = self.link_indices.get(LinkType.TUBE)
        hc_r = 0.008
        if hc_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            aabb = p.getAABB(self.body_id, hc_idx, physicsClientId=self.physics_client)
            hc_r = float((aabb[1][0] - aabb[0][0]) / 2.0)

        cavity_r = 0.080
        found_cavity = False
        if LinkType.BASE in self.boundaries:
            b_info = self.boundaries[LinkType.BASE]
            r_inner = b_info.radius if b_info.radius is not None else 0.0725
            t = b_info.thickness if b_info.thickness is not None else 0.0035
            cavity_r = float(r_inner + t)
            found_cavity = True

        if not found_cavity and self.body_id is not None and _is_real_physics_client(self.physics_client):
            aabb = p.getAABB(self.body_id, -1, physicsClientId=self.physics_client)
            cavity_r = float((aabb[1][0] - aabb[0][0]) / 2.0)

        vanes_clearance = 0.015
        vanes_idx = self.link_indices.get(LinkType.IMPELLER)
        if vanes_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            aabb = p.getAABB(self.body_id, vanes_idx, physicsClientId=self.physics_client)
            vanes_r = (aabb[1][0] - aabb[0][0]) / 2.0
            vanes_clearance = float(vanes_r + 0.003)

        fallen_r = cavity_r + 0.010
        return {
            LinkType.TUBE: hc_r,
            LinkType.BASE: cavity_r,
            LinkType.IMPELLER: vanes_clearance,
            LinkType.FALLEN: fallen_r,
        }

    @property
    def thresholds(self) -> dict[LinkType, float]:
        """Return dict mapping LinkType keys to their float thresholds."""
        outlet_idx = self.link_indices.get(LinkType.OUTLET)
        min_h = 0.095
        if outlet_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            state = p.getLinkState(self.body_id, outlet_idx, physicsClientId=self.physics_client)
            hc_info = self.boundaries.get(LinkType.TUBE)
            hc_height = hc_info.height if hc_info and hc_info.height is not None else 0.075
            min_h = float(state[4][2] + hc_height - 0.005)

        max_y = 0.030
        if outlet_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            aabb = p.getAABB(self.body_id, outlet_idx, physicsClientId=self.physics_client)
            max_y = float(aabb[1][1] + 0.005)

        offset_mm = 15.0
        hc_idx = self.link_indices.get(LinkType.TUBE)
        if hc_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            info = p.getJointInfo(self.body_id, hc_idx, physicsClientId=self.physics_client)
            hc_y = info[14][1]
            cavity_r_mm = self.radii[LinkType.BASE] * 1000.0
            hc_r_mm = self.radii[LinkType.TUBE] * 1000.0
            hc_y_mm = hc_y * 1000.0
            offset_mm = float(cavity_r_mm - hc_r_mm - hc_y_mm)

        return {
            LinkType.OUTLET: min_h,
            LinkType.OUTLET_MAX_Y: max_y,
            LinkType.TUBE: offset_mm,
        }

    def update(
        self,
        body_id: int,
        physics_client: int,
        damping: Optional[float] = None,
        motor_config: Optional[FluidMotorConfig] = None,
    ) -> None:
        """Step simulation and manage deactivation."""
        self.body_id = body_id
        self.physics_client = physics_client
        if motor_config is not None:
            self.motor_config = motor_config

        if not self.spawner:
            raise RuntimeError("Fluid spawner is not initialized.")

        damping_val = damping if damping is not None else -1.0

        pos_np = np.array(self.pos_jax)
        active_indices = np.where(pos_np[:, 2] < 100.0)[0]

        idx_map = self.default_idx_map.copy()
        if len(active_indices) > 0:
            active_pos = pos_np[active_indices]
            tree = cKDTree(active_pos)
            k_query = min(64 + 1, len(active_indices))
            _, indices = tree.query(active_pos, k=k_query, distance_upper_bound=self.h, workers=-1)

            if k_query > 1:
                neigh_indices = indices[:, 1:]
            else:
                neigh_indices = np.empty((len(active_indices), 0), dtype=np.int32)

            if self._cached_active_indices is not None and np.array_equal(self._cached_active_indices, active_indices):
                mapper = self._cached_mapper
                self_active_indices = self._cached_self_active_indices
            else:
                mapper = np.empty(len(active_indices) + 1, dtype=np.int32)
                mapper[:-1] = active_indices
                mapper[-1] = self.n_particles

                self_active_indices = np.array(active_indices)[:, None]

                self._cached_active_indices = active_indices
                self._cached_mapper = mapper
                self._cached_self_active_indices = self_active_indices

            if mapper is not None and self_active_indices is not None:
                mapped_neighs = mapper[neigh_indices]
                mapped_neighs = np.where(mapped_neighs == self.n_particles, self_active_indices, mapped_neighs)

                cols = mapped_neighs.shape[1]
                idx_map[active_indices, :cols] = mapped_neighs
                idx_map_jax = jnp.array(idx_map)
        else:
            idx_map_jax = jnp.array(idx_map)

        cavity_pos, cavity_orn = self._get_base_link_origin(self.body_id, physics_client)
        cavity_info = self.boundaries.get(LinkType.BASE)
        cavity_radius = cavity_info.radius if cavity_info and cavity_info.radius is not None else 0.076
        cavity_height = cavity_info.height if cavity_info and cavity_info.height is not None else 0.096
        cavity_z_offset = cavity_info.xyz[2] if cavity_info else 0.004

        hc_info = self.boundaries.get(LinkType.TUBE)
        hc_idx = self.link_indices.get(LinkType.TUBE) if hc_info else None
        if hc_idx is not None and hc_idx != -1:
            state = p.getLinkState(self.body_id, hc_idx, physicsClientId=physics_client)
            hc_pos, hc_orn = state[4], state[5]
        else:
            hc_pos, hc_orn = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]
        if hc_info:
            hc_outer_radius = hc_info.radius if hc_info.radius is not None else 0.008
            hc_thickness = hc_info.thickness if hc_info.thickness is not None else 0.0015
            hc_inner_radius = hc_outer_radius - hc_thickness
            hc_height = hc_info.height if hc_info.height is not None else 0.120
        else:
            hc_outer_radius = 0.0
            hc_inner_radius = 0.0
            hc_height = 0.0

        vanes_info = self.boundaries.get(LinkType.IMPELLER)
        v_idx = self.link_indices.get(LinkType.IMPELLER) if vanes_info else None
        if v_idx is not None and v_idx != -1:
            state = p.getLinkState(self.body_id, v_idx, physicsClientId=physics_client)
            v_pos, v_orn = state[4], state[5]
        else:
            v_pos, v_orn = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]
        if vanes_info:
            vanes_radius = vanes_info.radius if vanes_info.radius is not None else 0.005
            v_shaft_r = vanes_info.thickness if vanes_info.thickness is not None else 0.0015
            vanes_hub_radius = v_shaft_r + 0.001
            vanes_height = vanes_info.height if vanes_info.height is not None else 0.015
        else:
            vanes_radius = 0.0
            vanes_hub_radius = 0.0
            vanes_height = 0.0

        self.pos_jax, self.vel_jax, torque_accum = _physics_step_jax(
            self.pos_jax,
            self.vel_jax,
            idx_map_jax,
            self.particle_mass,
            self.h,
            self.rest_density,
            self.viscosity,
            self.stiffness,
            self.poly6_factor,
            self.spiky_grad_factor,
            self.visc_lap_factor,
            1.0 / (240.0 * 5),
            5,
            jnp.array(self.gravity, dtype=jnp.float32),
            jnp.array(cavity_pos, dtype=jnp.float32),
            jnp.array(cavity_orn, dtype=jnp.float32),
            cavity_radius,
            cavity_height,
            cavity_z_offset,
            jnp.array(hc_pos, dtype=jnp.float32),
            jnp.array(hc_orn, dtype=jnp.float32),
            hc_outer_radius,
            hc_inner_radius,
            hc_height,
            self.slot_height,
            jnp.array(v_pos, dtype=jnp.float32),
            jnp.array(v_orn, dtype=jnp.float32),
            vanes_radius,
            vanes_hub_radius,
            vanes_height,
            self.motor_config.target_omega,
            self.current_sim_time,
            0.0015,
            4.0,
            jnp.radians(self.vane_twist),
            1000.0,
            0.3,
            self.r_s,
            self.pressure_avg_factor,
            self.min_distance_threshold,
            damping_val,
        )
        avg_step_torque = float(torque_accum) / 5
        self.torques.append(avg_step_torque)

        self.last_positions = self.pos_jax.tolist()

        positions = self.last_positions
        pos_np = np.array(positions)
        if len(pos_np) > 0:
            xs = pos_np[:, 0]
            ys = pos_np[:, 1]
            zs = pos_np[:, 2]

            active_mask = zs < 100.0

            # Spout/outlet indices
            spout_indices = np.where(
                active_mask & (zs >= self.thresholds[LinkType.OUTLET]) & (ys < self.thresholds[LinkType.OUTLET_MAX_Y])
            )[0]
            for idx in spout_indices:
                self.spout_water_ids.add(idx)

            # Fallen indices
            fallen_indices = np.where(
                active_mask & ((zs < 0.0) | (xs**2 + ys**2 > (self.radii[LinkType.FALLEN]) ** 2))
            )[0]

            if len(fallen_indices) > 0:
                pos_arr = np.array(self.pos_jax)
                vel_arr = np.array(self.vel_jax)
                for idx in fallen_indices:
                    if self.recycle_fluid:
                        # Select a random coordinate from pre-calculated grid
                        if hasattr(self, "spawn_xy_coords") and self.spawn_xy_coords:
                            x, y = random.choice(self.spawn_xy_coords)
                        else:
                            x, y = 0.0, 0.0
                        z_local = cavity_z_offset + self.r_s + self.bowl_wall_buffer + random.uniform(0.0, 0.010)
                        wpt, _ = p.multiplyTransforms(cavity_pos, cavity_orn, [x, y, z_local], [0.0, 0.0, 0.0, 1.0])
                        pos_arr[idx] = wpt
                        vel_arr[idx] = [0.0, 0.0, 0.0]
                    else:
                        self.fallen_out_water_ids.add(idx)
                        pos_arr[idx] = [0.0, 0.0, 1000.0]
                        vel_arr[idx] = [0.0, 0.0, 0.0]
                self.pos_jax = jnp.array(pos_arr)
                self.vel_jax = jnp.array(vel_arr)
                self.last_positions = self.pos_jax.tolist()

        if self.state_tracker is not None:
            self.state_tracker.particle_positions = self.get_particle_positions()
            self.state_tracker.particle_colors = self.get_particle_colors()
            self.state_tracker.particle_radii = self.get_particle_radii()
