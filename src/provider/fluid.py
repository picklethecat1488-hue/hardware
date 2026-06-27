"""Fluid simulation classes and JAX solvers for SPH based fluid dynamics with boundary rejection."""

from __future__ import annotations
import math
from functools import partial
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
    from model import BoundaryConfig, FluidConfig


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
    """Compute SPH forces (pressure and viscosity) using vectorized JAX.

    Args:
        positions: (N, 3) array of SPH particle positions (meters).
        velocities: (N, 3) array of SPH particle velocities (m/s).
        mass: Mass of a single SPH particle (kg).
        h: SPH kernel smoothing radius (meters).
        rest_density: Target rest density of the fluid (kg/m^3).
        viscosity: SPH viscosity coefficient.
        stiffness: SPH pressure stiffness parameter.
        poly6_factor: Precomputed coefficient factor for the Poly6 SPH density kernel.
        spiky_grad_factor: Precomputed coefficient factor for the Spiky kernel gradient.
        visc_lap_factor: Precomputed coefficient factor for the viscosity Laplacian kernel.
        pressure_avg_factor: Coefficient for averaging pairwise particle pressures.
        min_dist_threshold: Minimum squared distance to prevent divide-by-zero errors.

    Returns:
        (N, 3) array of SPH forces acting on each particle.
    """
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
    """Compute SPH forces (pressure and viscosity) using a precomputed neighbor list.

    Args:
        positions: (N, 3) array of SPH particle positions (meters).
        velocities: (N, 3) array of SPH particle velocities (m/s).
        idx_map: (N, M) mapping of particle indices to their respective neighbors.
        mass: Mass of a single SPH particle (kg).
        h: SPH kernel smoothing radius (meters).
        rest_density: Target rest density of the fluid (kg/m^3).
        viscosity: SPH viscosity coefficient.
        stiffness: SPH pressure stiffness parameter.
        poly6_factor: Precomputed coefficient factor for the Poly6 SPH density kernel.
        spiky_grad_factor: Precomputed coefficient factor for the Spiky kernel gradient.
        visc_lap_factor: Precomputed coefficient factor for the viscosity Laplacian kernel.
        pressure_avg_factor: Coefficient for averaging pairwise particle pressures.
        min_dist_threshold: Minimum squared distance to prevent divide-by-zero errors.

    Returns:
        (N, 3) array of SPH forces acting on each particle.
    """
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


@partial(jax.jit, static_argnums=(7,))
def _compute_boundary_forces_jax(
    pos: jnp.ndarray,
    vel: jnp.ndarray,
    r_s: float,
    K: float,
    D: float,
    b_pos_arr: jnp.ndarray,
    b_orn_arr: jnp.ndarray,
    boundary_configs: tuple,
    omega: float,
    t: float,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Compute boundary collision and friction forces using penalty-based methods.

    Args:
        pos: (N, 3) array of SPH particle positions in world coordinates (meters).
        vel: (N, 3) array of SPH particle velocities in world coordinates (m/s).
        r_s: SPH particle radius/search scale (meters).
        K: Boundary collision penalty stiffness coefficient.
        D: Boundary collision penalty damping coefficient.
        b_pos_arr: (B, 3) array of boundary element positions.
        b_orn_arr: (B, 4) array of boundary element orientation quaternions.
        boundary_configs: Tuple of static boundary configurations defining geometry/colliders.
        omega: Target impeller angular speed (rad/s).
        t: Current simulation time (seconds).

    Returns:
        A tuple containing:
            - forces: (N, 3) array of boundary forces acting on each particle in world coordinates.
            - vanes_torque: Reaction torque acting on the rotary vanes (impeller).
    """
    from model import ShapeType, BoundaryType

    forces = jnp.zeros_like(pos)
    vanes_torque = jnp.array(0.0)

    for i, cfg in enumerate(boundary_configs):
        b_pos = b_pos_arr[i]
        b_orn = b_orn_arr[i]
        b_orn_inv = q_inv(b_orn)
        pos_local = q_rotate(b_orn_inv, pos - b_pos)
        vel_local = q_rotate(b_orn_inv, vel)

        shape = cfg.shape
        b_type = cfg.type
        radius = cfg.radius
        height = cfg.height
        thickness = cfg.thickness
        z_offset = cfg.z_offset
        slot_height = cfg.slot_height
        vane_thickness = cfg.vane_thickness
        num_vanes = cfg.num_vanes
        vane_twist_rad = cfg.vane_twist_rad
        drain_hole_y = cfg.drain_hole_y
        drain_hole_radius = cfg.drain_hole_radius

        match shape:
            case ShapeType.CYLINDER:
                if b_type == BoundaryType.CAVITY:
                    r_c = jnp.sqrt(pos_local[:, 0] ** 2 + pos_local[:, 1] ** 2)
                    r_c = jnp.maximum(r_c, 1e-8)

                    # 1. Cavity side wall
                    r_limit_c = radius - r_s
                    pen_c_side = r_c - r_limit_c
                    side_mask = (pen_c_side > 0.0) & (pos_local[:, 2] >= z_offset) & (pos_local[:, 2] <= height)
                    nx_c = -pos_local[:, 0] / r_c
                    ny_c = -pos_local[:, 1] / r_c
                    v_n_c = vel_local[:, 0] * (-nx_c) + vel_local[:, 1] * (-ny_c)
                    f_mag_c_side = K * pen_c_side + D * jnp.maximum(v_n_c, 0.0)
                    force_c_side = jnp.stack([f_mag_c_side * nx_c, f_mag_c_side * ny_c, jnp.zeros_like(r_c)], axis=-1)
                    force_c_side = jnp.where(side_mask[:, None], force_c_side, 0.0)

                    # 2. Cavity bottom
                    z_limit_c = z_offset + r_s
                    pen_c_bottom = z_limit_c - pos_local[:, 2]
                    bottom_limit = z_offset - jnp.maximum(thickness, 0.002)
                    has_tube = cfg.has_tube
                    has_drain = cfg.has_drain
                    tube_y = cfg.xyz[1]
                    in_tube_hole = has_tube & (
                        pos_local[:, 0] ** 2 + (pos_local[:, 1] - tube_y) ** 2 < cfg.tube_radius**2
                    )
                    in_drain_hole = (
                        (has_drain & (drain_hole_radius > 0.0))
                        & (pos_local[:, 0] ** 2 + (pos_local[:, 1] - drain_hole_y) ** 2 < drain_hole_radius**2)
                    ) | in_tube_hole
                    bottom_mask = (
                        (pen_c_bottom > 0.0) & (r_c < radius) & (pos_local[:, 2] >= bottom_limit) & (~in_drain_hole)
                    )
                    f_z_c = K * pen_c_bottom - D * vel_local[:, 2]
                    force_c_bottom = jnp.stack(
                        [jnp.zeros_like(r_c), jnp.zeros_like(r_c), jnp.maximum(f_z_c, 0.0)], axis=-1
                    )
                    force_c_bottom = jnp.where(bottom_mask[:, None], force_c_bottom, 0.0)

                    forces += q_rotate(b_orn, force_c_side + force_c_bottom)

            case ShapeType.SPHERE:
                if b_type == BoundaryType.SOLID:
                    dist = jnp.sqrt(pos_local[:, 0] ** 2 + pos_local[:, 1] ** 2 + pos_local[:, 2] ** 2)
                    dist = jnp.maximum(dist, 1e-8)
                    pen = (radius + r_s) - dist
                    mask = pen > 0.0
                    nx = pos_local[:, 0] / dist
                    ny = pos_local[:, 1] / dist
                    nz = pos_local[:, 2] / dist
                    v_n = vel_local[:, 0] * nx + vel_local[:, 1] * ny + vel_local[:, 2] * nz
                    f_mag = K * pen - D * v_n
                    force = jnp.stack([f_mag * nx, f_mag * ny, f_mag * nz], axis=-1)
                    force = jnp.where((mask & (f_mag > 0.0))[:, None], force, 0.0)
                    forces += q_rotate(b_orn, force)

            case ShapeType.TUBE:
                height_mask = (pos_local[:, 2] >= 0.0) & (pos_local[:, 2] <= height)
                cutout_mask = (pos_local[:, 2] < slot_height) & (pos_local[:, 1] > 0.0)
                active_mask = height_mask & (~cutout_mask)

                r_hc = jnp.sqrt(pos_local[:, 0] ** 2 + pos_local[:, 1] ** 2)
                r_hc = jnp.maximum(r_hc, 1e-8)

                inner_r = radius - thickness
                r_hc_mid = (inner_r + radius) / 2.0

                # 1. Inner cavity collision
                pen_hc_in = r_hc - (inner_r - r_s)
                in_mask = active_mask & (inner_r > 0.0) & (r_hc < r_hc_mid) & (pen_hc_in > 0.0)
                nx_hc_in = -pos_local[:, 0] / r_hc
                ny_hc_in = -pos_local[:, 1] / r_hc
                v_n_hc_in = vel_local[:, 0] * (-nx_hc_in) + vel_local[:, 1] * (-ny_hc_in)
                f_mag_hc_in = K * pen_hc_in + D * jnp.maximum(v_n_hc_in, 0.0)
                force_hc_in = jnp.stack([f_mag_hc_in * nx_hc_in, f_mag_hc_in * ny_hc_in, jnp.zeros_like(r_hc)], axis=-1)
                force_hc_in = jnp.where(in_mask[:, None], force_hc_in, 0.0)

                # 2. Outer solid cylinder collision
                pen_hc_out = (radius + r_s) - r_hc
                out_mask = active_mask & (radius > 0.0) & (r_hc >= r_hc_mid) & (pen_hc_out > 0.0)
                nx_hc_out = pos_local[:, 0] / r_hc
                ny_hc_out = pos_local[:, 1] / r_hc
                v_n_hc_out = vel_local[:, 0] * nx_hc_out + vel_local[:, 1] * ny_hc_out
                f_mag_hc_out = K * pen_hc_out - D * v_n_hc_out
                force_hc_out = jnp.stack(
                    [f_mag_hc_out * nx_hc_out, f_mag_hc_out * ny_hc_out, jnp.zeros_like(r_hc)], axis=-1
                )
                force_hc_out = jnp.where((out_mask[:, None]) & (f_mag_hc_out[:, None] > 0.0), force_hc_out, 0.0)

                forces += q_rotate(b_orn, force_hc_in + force_hc_out)

            case ShapeType.IMPELLER:
                r_v = jnp.sqrt(pos_local[:, 0] ** 2 + pos_local[:, 1] ** 2)
                r_v = jnp.maximum(r_v, 1e-8)

                height_mask = (pos_local[:, 2] >= 0.0) & (pos_local[:, 2] <= height)

                # 1. Hub solid cylinder
                hub_r = thickness + 0.001
                pen_v_hub = (hub_r + r_s) - r_v
                hub_mask = height_mask & (hub_r > 0.0) & (pen_v_hub > 0.0)
                nx_v_hub = pos_local[:, 0] / r_v
                ny_v_hub = pos_local[:, 1] / r_v
                v_n_v_hub = vel_local[:, 0] * nx_v_hub + vel_local[:, 1] * ny_v_hub
                f_mag_v_hub = K * pen_v_hub - D * v_n_v_hub
                force_v_hub = jnp.stack([f_mag_v_hub * nx_v_hub, f_mag_v_hub * ny_v_hub, jnp.zeros_like(r_v)], axis=-1)
                force_v_hub = jnp.where((hub_mask[:, None]) & (f_mag_v_hub[:, None] > 0.0), force_v_hub, 0.0)

                # 2. Rotating Vanes (Blades)
                safe_height = jnp.where(height > 0.0, height, 1.0)
                pitch = vane_twist_rad / safe_height
                theta_t = pos_local[:, 2] * pitch
                phi = jnp.arctan2(pos_local[:, 1], pos_local[:, 0])
                d_phi = phi - theta_t

                pi_N = jnp.pi / num_vanes
                d_phi_wrapped = (d_phi + pi_N) % (2.0 * pi_N) - pi_N

                dist_to_vane = r_v * jnp.sin(d_phi_wrapped)
                vane_threshold = vane_thickness / 2.0 + r_s
                pen_vane = vane_threshold - jnp.abs(dist_to_vane)

                vane_collision_mask = height_mask & (radius > 0.0) & (r_v >= hub_r) & (r_v <= radius) & (pen_vane > 0.0)

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
                    (vel_local[:, 0] - v_vane_x) * normal_tx
                    + (vel_local[:, 1] - v_vane_y) * normal_ty
                    + (vel_local[:, 2] - 0.0) * normal_tz
                )

                f_mag_vane = K * pen_vane - D * v_rel_n_vane
                force_vane = jnp.stack(
                    [f_mag_vane * normal_tx, f_mag_vane * normal_ty, f_mag_vane * normal_tz], axis=-1
                )
                force_vane = jnp.where((vane_collision_mask[:, None]) & (f_mag_vane[:, None] > 0.0), force_vane, 0.0)

                forces += q_rotate(b_orn, force_v_hub + force_vane)

                # Reaction torque on the rotary vanes
                t_z = pos_local[:, 1] * force_vane[:, 0] - pos_local[:, 0] * force_vane[:, 1]
                vanes_torque += jnp.sum(t_z)

    return forces, vanes_torque


@partial(jax.jit, static_argnums=(13, 22))
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
    boundary_configs: tuple,
    gravity: jnp.ndarray,
    b_pos_arr: jnp.ndarray,
    b_orn_arr: jnp.ndarray,
    omega: float,
    t_start: float,
    K_boundary: float,
    D_boundary: float,
    r_s: float,
    base_idx: int,
    pressure_avg_factor: float = 2.0,
    min_dist_threshold: float = 1e-6,
    damping: float = -1.0,
    high_damping_value: float = 0.998,
) -> tuple[jnp.ndarray, jnp.ndarray, float]:
    """Perform a substepped SPH simulation update integrating forces and boundary collisions.

    Args:
        pos: (N, 3) array of current SPH particle positions (meters).
        vel: (N, 3) array of current SPH particle velocities (m/s).
        idx_map: (N, M) mapping of particle indices to their respective neighbors.
        mass: SPH particle mass (kg).
        h: SPH kernel smoothing radius (meters).
        rest_density: Target rest density of the fluid (kg/m^3).
        viscosity: Dynamic viscosity coefficient.
        stiffness: SPH pressure stiffness parameter.
        poly6_factor: Precomputed Poly6 density kernel coefficient.
        spiky_grad_factor: Precomputed Spiky pressure gradient kernel coefficient.
        visc_lap_factor: Precomputed viscosity Laplacian kernel coefficient.
        dt_sub: Solver substep time increment (seconds).
        n_substeps: Number of integration substeps per step invocation.
        boundary_configs: Tuple of static boundary configurations defining shapes.
        gravity: Gravity acceleration vector (3,).
        b_pos_arr: (B, 3) array of boundary positions in world coordinates.
        b_orn_arr: (B, 4) array of boundary orientations in world coordinates.
        omega: Target impeller angular speed (rad/s).
        t_start: Starting simulation time (seconds) for this substepped update.
        K_boundary: Boundary collision penalty stiffness coefficient.
        D_boundary: Boundary collision penalty damping coefficient.
        r_s: SPH particle radius/search scale (meters).
        base_idx: Cached index of the base boundary config in boundary_configs tuple.
        pressure_avg_factor: Coefficient for averaging pairwise particle pressures.
        min_dist_threshold: Minimum squared distance to prevent divide-by-zero errors.
        damping: Explicit damping value. If negative, defaults to dynamic speed-adaptive damping.
        high_damping_value: Damping value applied to particles outside the base boundaries.

    Returns:
        A tuple containing:
            - pos_next: (N, 3) updated particle positions array.
            - vel_next: (N, 3) updated particle velocities array.
            - torque_accum: Accumulated reaction torque on the impeller vanes.
    """

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
            b_pos_arr,
            b_orn_arr,
            boundary_configs,
            omega,
            t_curr,
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

        if base_idx != -1:
            base_cfg = boundary_configs[base_idx]
            base_pos = b_pos_arr[base_idx]
            base_orn = b_orn_arr[base_idx]
            base_orn_inv = q_inv(base_orn)
            pos_local = q_rotate(base_orn_inv, pos_curr - base_pos)
            r_local = jnp.sqrt(pos_local[:, 0] ** 2 + pos_local[:, 1] ** 2)
            outside_base = (
                (r_local > base_cfg.radius)
                | (pos_local[:, 2] < base_cfg.z_offset)
                | (pos_local[:, 2] > base_cfg.height)
            )
        else:
            outside_base = jnp.zeros(pos_curr.shape[0], dtype=jnp.bool_)

        damping_val = jnp.where(damping >= 0.0, damping, dynamic_damping)
        damping_by_zone = jnp.where((damping >= 0.0) | (~outside_base), damping_val, high_damping_value)[:, None]

        vel_next = jnp.where(active, (vel_curr + accel * dt_sub) * damping_by_zone, 0.0)
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
        from model import BoundaryConfig, FluidConfig

        if config is None:
            config = FluidConfig()

        self.provider = provider

        self.r_s = config.r_s
        self.particle_radius = config.particle_radius

        self.target_volume = config.target_volume
        self.spawn_buffer = config.spawn_buffer
        self.rest_density = config.rest_density
        self.viscosity = config.viscosity

        self.stiffness = config.stiffness
        self.k = self.stiffness

        self.smoothing_factor = config.smoothing_factor
        self.sphere_vol_factor = config.sphere_vol_factor
        self.poly6_coeff_numerator = config.poly6_coeff_numerator
        self.poly6_coeff_denominator = config.poly6_coeff_denominator
        self.spiky_grad_coeff = config.spiky_grad_coeff
        self.visc_lap_coeff = config.visc_lap_coeff
        self.pressure_avg_factor = config.pressure_avg_factor
        self.min_distance_threshold = config.min_distance_threshold
        self.stiffness_boundary = config.stiffness_boundary
        self.damping_boundary = config.damping_boundary

        self.volume_threshold_liters = config.volume_threshold_liters
        self.fallen_threshold_liters = config.fallen_threshold_liters
        self.recycle_fluid = config.recycle_fluid
        self.high_damping_value = config.high_damping_value

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
        self.boundary_list: list[BoundaryConfig] = []
        self.pos_jax = None
        self.vel_jax = None
        vol_s = (4.0 / 3.0) * math.pi * (self.r_s**3)
        self.n_particles = int(round(self.target_volume / vol_s))
        self.last_positions: list[list[float]] = []
        self.current_sim_time = 0.0
        self.torques: list[float] = []
        # Motor configurations are consolidated into BoundaryConfig
        self.spout_water_ids = set()
        self.fallen_out_water_ids = set()
        self.state_tracker = state_tracker

        self._cached_active_indices = None
        self._cached_mapper = None
        self._cached_self_active_indices = None
        self.spawn_xy_coords: list[tuple[float, float]] = []

        self.link_indices = link_indices if link_indices is not None else {}

        self.gravity = config.gravity

        # Parse boundaries metadata using BoundaryConfig Pydantic model
        self.boundary_list = []
        if config.boundaries is not None:
            for label, val in config.boundaries.items():
                vals = val if isinstance(val, list) else [val]
                for item in vals:
                    b_info = item if isinstance(item, BoundaryConfig) else BoundaryConfig.model_validate(item)
                    b_info._label = label
                    self.boundary_list.append(b_info)

        self.boundaries = {}
        for b in self.boundary_list:
            match b.link_type:
                case LinkType.BASE:
                    self.boundaries[LinkType.BASE] = b
                case LinkType.TUBE:
                    self.boundaries[LinkType.TUBE] = b
                case LinkType.IMPELLER:
                    self.boundaries[LinkType.IMPELLER] = b

        # Derive characteristic length from base boundary radius LinkType.BASE (enforced to be present in every model)
        base_info = self.boundaries[LinkType.BASE]
        self.characteristic_length = base_info.radius

        # Derive neighbor list box size from boundaries (2x the base boundary radius)
        self.neighbor_list_box = 2.0 * base_info.radius

        self.base_idx = -1
        for idx, b in enumerate(self.boundary_list):
            if b.link_type == LinkType.BASE:
                self.base_idx = idx
                break

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

            # Generate grid points to initially fill the cavity
            grid_points: list[tuple[float, float, float]] = []
            spacing = 1.3 * self.r_s

            hc_idx = self.link_indices.get(LinkType.TUBE)
            hc_x, hc_y = (
                (p.getJointInfo(self.body_id, hc_idx, physicsClientId=physics_client)[14][:2])
                if hc_idx is not None
                else (0.0, 0.0)
            )

            cavity_info = self.boundaries.get(LinkType.BASE)
            cavity_inner_radius = cavity_info.radius if cavity_info is not None else 0.0
            cavity_z_offset = cavity_info.xyz[2] if cavity_info is not None else 0.0
            hc_r = self.radii[LinkType.TUBE]

            max_r_sq = (cavity_inner_radius - self.spawn_buffer) ** 2
            min_r_sq = (hc_r + self.spawn_buffer) ** 2

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
            z = cavity_z_offset + self.r_s + self.spawn_buffer
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
        hc_info = self.boundaries.get(LinkType.TUBE)
        hc_r = hc_info.radius if hc_info is not None else 0.0

        base_info = self.boundaries.get(LinkType.BASE)
        cavity_r = float(base_info.radius + base_info.thickness) if base_info is not None else 0.0

        impeller_info = self.boundaries.get(LinkType.IMPELLER)
        vanes_clearance = float(impeller_info.radius + 0.003) if impeller_info is not None else 0.0

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
        min_h = 0.0
        if outlet_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            state = p.getLinkState(self.body_id, outlet_idx, physicsClientId=self.physics_client)
            hc_info = self.boundaries.get(LinkType.TUBE)
            hc_height = hc_info.height if hc_info is not None else 0.0
            min_h = float(state[4][2] + hc_height - 0.005)

        max_y = 0.0
        if outlet_idx is not None and self.body_id is not None and _is_real_physics_client(self.physics_client):
            aabb = p.getAABB(self.body_id, outlet_idx, physicsClientId=self.physics_client)
            max_y = float(aabb[1][1] + 0.005)

        offset_mm = 0.0
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
        target_omega: Optional[float] = None,
        max_force: Optional[float] = None,
    ) -> None:
        """Step simulation and manage deactivation."""
        self.body_id = body_id
        self.physics_client = physics_client
        impeller_b = self.boundaries.get(LinkType.IMPELLER)
        if impeller_b is not None:
            if target_omega is not None:
                impeller_b.target_omega = target_omega
            if max_force is not None:
                impeller_b.max_force = max_force

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
        cavity_z_offset = cavity_info.xyz[2] if cavity_info is not None else 0.0

        b_pos_list = []
        b_orn_list = []
        b_static_list = []

        for b in self.boundary_list:
            link_idx = b.link_idx
            if link_idx != -1 and self.body_id is not None and _is_real_physics_client(physics_client):
                state = p.getLinkState(self.body_id, link_idx, physicsClientId=physics_client)
                parent_pos, parent_orn = state[4], state[5]
            elif link_idx == -1 and self.body_id is not None and _is_real_physics_client(physics_client):
                parent_pos, parent_orn = self._get_base_link_origin(self.body_id, physics_client)
            else:
                parent_pos, parent_orn = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]

            local_xyz = b.xyz
            local_rpy = b.rpy
            if local_xyz != (0.0, 0.0, 0.0) or local_rpy != (0.0, 0.0, 0.0):
                local_orn = p.getQuaternionFromEuler(local_rpy)
                b_pos, b_orn = p.multiplyTransforms(parent_pos, parent_orn, local_xyz, local_orn)
            else:
                b_pos, b_orn = parent_pos, parent_orn

            b_pos_list.append(b_pos)
            b_orn_list.append(b_orn)
            b_static_list.append(b)

        b_pos_arr = jnp.array(b_pos_list, dtype=jnp.float32)
        b_orn_arr = jnp.array(b_orn_list, dtype=jnp.float32)
        boundary_configs = tuple(b_static_list)

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
            boundary_configs,
            jnp.array(self.gravity, dtype=jnp.float32),
            b_pos_arr,
            b_orn_arr,
            impeller_b.target_omega if impeller_b is not None else 0.0,
            self.current_sim_time,
            self.stiffness_boundary,
            self.damping_boundary,
            self.r_s,
            self.base_idx,
            self.pressure_avg_factor,
            self.min_distance_threshold,
            damping_val,
            self.high_damping_value,
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
                active_mask & ((zs < 0.0) | (zs > 0.160) | (xs**2 + ys**2 > (self.radii[LinkType.FALLEN]) ** 2))
            )[0]

            if len(fallen_indices) > 0:
                pos_arr = np.array(self.pos_jax)
                vel_arr = np.array(self.vel_jax)
                for idx in fallen_indices:
                    if self.recycle_fluid:
                        # Select a random coordinate from pre-calculated grid
                        if self.spawn_xy_coords:
                            x, y = random.choice(self.spawn_xy_coords)
                        else:
                            x, y = 0.0, 0.0
                        z_local = cavity_z_offset + self.r_s + self.spawn_buffer + random.uniform(0.0, 0.010)
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
