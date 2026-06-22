"""Fluid simulation class using Smoothed Particle Hydrodynamics (SPH)."""

import math
from typing import Any, Optional
import jax
import jax.numpy as jnp


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
    # diff[i, j] = pos[i] - pos[j]
    diff = positions[:, None, :] - positions[None, :, :]

    # Pairwise squared distances: shape (N, N)
    r2 = jnp.sum(diff * diff, axis=-1)

    # Neighborhood mask (distance < h)
    mask = r2 < h2

    # 1. Compute density for each particle
    # Poly6 kernel: W = poly6_factor * (h^2 - r^2)^3
    w = poly6_factor * (jnp.maximum(h2 - r2, 0.0) ** 3) * mask
    densities = jnp.sum(mass * w, axis=1)

    # Clamp density to rest_density to prevent negative pressures
    densities = jnp.maximum(densities, rest_density)

    # Ideal gas equation of state: P = k * (rho - rho_0)
    pressures = stiffness * (densities - rest_density)

    # 2. Compute forces for each particle
    # Distances between particles: shape (N, N)
    # Add a small epsilon to avoid division by zero / NaN in gradients
    r = jnp.sqrt(r2 + min_dist_threshold * min_dist_threshold)

    # Spiky kernel gradient: grad_W = spiky_grad_factor * (h - r)^2 * r_vec/r
    hr = jnp.maximum(h - r, 0.0)
    grad_coeff = spiky_grad_factor * (hr**2) * mask

    # Pressure force term: (p_i + p_j) / (2 * rho_j)
    p_term = mass * (pressures[:, None] + pressures[None, :]) / (pressure_avg_factor * densities[None, :])

    # Direction vector: diff / r
    direction = diff / r[:, :, None]

    # Exclude self-interaction (i == j) using a mask
    self_mask = (1.0 - jnp.eye(n))[:, :, None]

    # Pressure force: f_press_j = -m_j * (p_i + p_j) / (2 * rho_j) * grad_W
    f_press = -p_term[:, :, None] * grad_coeff[:, :, None] * direction * self_mask
    f_press_total = jnp.sum(f_press, axis=1)

    # Viscosity force term: laplacian_W = visc_lap_factor * (h - r)
    lap_coeff = visc_lap_factor * hr * mask

    # Relative velocities: v_diff = v_j - v_i
    v_diff = velocities[None, :, :] - velocities[:, None, :]
    v_term = viscosity * mass / densities[None, :, None] * lap_coeff[:, :, None]

    f_visc = v_term * v_diff * self_mask
    f_visc_total = jnp.sum(f_visc, axis=1)

    # Multiply by particle volume (mass / density) to convert force density to force
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

    # Gather neighbor states
    neigh_positions = positions[idx_map]  # Shape (N, M, 3)
    neigh_velocities = velocities[idx_map]  # Shape (N, M, 3)

    diff = positions[:, None, :] - neigh_positions  # Shape (N, M, 3)
    r2 = jnp.sum(diff * diff, axis=-1)  # Shape (N, M)

    # Exclude padded and self interactions (both map to own index i)
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


class Fluid:
    """Handles SPH fluid dynamics simulation for fluid particles in PyBullet using JAX."""

    # SPH smoothing length scaling factor
    SMOOTHING_FACTOR = 3.0

    # Volume of a sphere constant factor: 4/3
    SPHERE_VOL_FACTOR = 4.0 / 3.0

    # Poly6 kernel constant: 315 / (64 * pi * h^9)
    POLY6_COEFF_NUMERATOR = 315.0
    POLY6_COEFF_DENOMINATOR = 64.0

    # Spiky kernel gradient constant: -45 / (pi * h^6)
    SPIKY_GRAD_COEFF = -45.0

    # Viscosity Laplacian constant: 45 / (pi * h^6)
    VISC_LAP_COEFF = 45.0

    # Averaging factor for symmetric pressure force interaction: 2.0
    PRESSURE_AVG_FACTOR = 2.0

    # Small epsilon value to avoid division by zero when particles overlap
    MIN_DISTANCE_THRESHOLD = 1e-6

    # Default parameters for fluid particles
    DEFAULT_PARTICLE_RADIUS = 0.003
    DEFAULT_REST_DENSITY = 1000.0
    DEFAULT_VISCOSITY = 0.5
    DEFAULT_STIFFNESS = 2000.0

    # Default characteristic length for Knudsen number calculation
    DEFAULT_CHARACTERISTIC_LENGTH = 0.076

    def __init__(
        self,
        r_s: float = DEFAULT_PARTICLE_RADIUS,
        rest_density: float = DEFAULT_REST_DENSITY,
        viscosity: float = DEFAULT_VISCOSITY,
        stiffness: float = DEFAULT_STIFFNESS,
    ):
        """
        Initialize the fluid simulation constants.

        Args:
            r_s: Radius of the fluid particle spheres in meters.
            rest_density: Rest density of the fluid (1000 kg/m^3 for water).
            viscosity: Newtonian viscosity coefficient (Pa*s).
            stiffness: Gas constant parameter for pressure calculation.
        """
        self.r_s = r_s
        self.h = self.SMOOTHING_FACTOR * r_s  # Smoothing length
        self.mass = self.SPHERE_VOL_FACTOR * math.pi * (r_s**3) * rest_density
        self.rest_density = rest_density
        self.viscosity = viscosity
        self.k = stiffness

        # Precompute kernel constants
        self.poly6_factor = self.POLY6_COEFF_NUMERATOR / (self.POLY6_COEFF_DENOMINATOR * math.pi * (self.h**9))
        self.spiky_grad_factor = self.SPIKY_GRAD_COEFF / (math.pi * (self.h**6))
        self.visc_lap_factor = self.VISC_LAP_COEFF / (math.pi * (self.h**6))

    def compute_forces_jax(
        self,
        pos_jax: jnp.ndarray,
        vel_jax: jnp.ndarray,
        idx_map: Optional[jnp.ndarray] = None,
    ) -> jnp.ndarray:
        """
        Compute SPH forces (pressure + viscosity) for all particles returning a JAX array.
        """
        if idx_map is not None:
            return _compute_forces_neighbor_list_jax(
                pos_jax,
                vel_jax,
                idx_map,
                self.mass,
                self.h,
                self.rest_density,
                self.viscosity,
                self.k,
                self.poly6_factor,
                self.spiky_grad_factor,
                self.visc_lap_factor,
                self.PRESSURE_AVG_FACTOR,
                self.MIN_DISTANCE_THRESHOLD,
            )
        return _compute_forces_jax(
            pos_jax,
            vel_jax,
            self.mass,
            self.h,
            self.rest_density,
            self.viscosity,
            self.k,
            self.poly6_factor,
            self.spiky_grad_factor,
            self.visc_lap_factor,
            self.PRESSURE_AVG_FACTOR,
            self.MIN_DISTANCE_THRESHOLD,
        )

    def compute_forces(
        self,
        positions: list[tuple[float, float, float]],
        velocities: list[tuple[float, float, float]],
    ) -> list[list[float]]:
        """
        Compute SPH forces (pressure + viscosity) for all particles using JAX.

        Args:
            positions: Current 3D positions of the particles.
            velocities: Current 3D velocities of the particles.

        Returns:
            List of 3D force vectors to apply to each particle.
        """
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
        characteristic_length: float = DEFAULT_CHARACTERISTIC_LENGTH,
    ) -> float:
        """
        Calculate the Knudsen number (Kn = mean_free_path / L).

        If Kn < 0.1, the substance is in the continuum flow regime.
        """
        n = len(positions)
        if n < 2:
            return 0.0

        pos_jax = jnp.array(positions, dtype=jnp.float32)

        # Vectorized Knudsen number computation using JAX
        diff = pos_jax[:, None, :] - pos_jax[None, :, :]
        r2 = jnp.sum(diff * diff, axis=-1)

        # Mask self-interaction with a large number instead of inf
        # to avoid NaN issues on experimental GPU/MPS backends
        self_mask_large = jnp.eye(n) * 1e10
        r2_masked = r2 + self_mask_large

        min_dists = jnp.sqrt(jnp.min(r2_masked, axis=1))
        mean_free_path = jnp.mean(min_dists)

        return float(mean_free_path / characteristic_length)
