"""Fluid simulation configuration models."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class FluidConfig(BaseModel):
    """Configuration options for SPH fluid solver."""

    # --- SPH Particle & Fluid Properties ---
    r_s: Optional[float] = Field(
        default=None, description="Optional override for the SPH search/spacing radius (meters)."
    )
    particle_radius: float = Field(default=0.003, description="Physical radius of each SPH fluid particle (meters).")
    rest_density: float = Field(default=1000.0, description="Rest density of the fluid (kg/m^3).")
    viscosity: float = Field(default=0.5, description="Dynamic viscosity coefficient of the fluid solver.")
    stiffness: float = Field(default=2000.0, description="Stiffness parameter (k) for the equation of state.")
    k: Optional[float] = Field(default=None, description="Alternate stiffness parameter identifier.")
    gravity: Optional[tuple[float, float, float]] = Field(
        default=None, description="Gravity vector (x, y, z) in m/s^2."
    )

    # --- SPH Kernel & Numerical Solvers Constants ---
    smoothing_factor: float = Field(
        default=3.0, description="Kernel smoothing radius multiplier relative to particle radius."
    )
    sphere_vol_factor: float = Field(
        default=4.0 / 3.0, description="Volume coefficient multiplier for spherical particle volumes."
    )
    poly6_coeff_numerator: float = Field(
        default=315.0, description="Numerator coefficient for Poly6 density kernel estimation."
    )
    poly6_coeff_denominator: float = Field(
        default=64.0, description="Denominator coefficient for Poly6 density kernel estimation."
    )
    spiky_grad_coeff: float = Field(default=-45.0, description="Coefficient for Spiky gradient kernel calculation.")
    visc_lap_coeff: float = Field(default=45.0, description="Coefficient for Viscosity Laplacian kernel calculation.")
    pressure_avg_factor: float = Field(
        default=2.0, description="Averaging coefficient for pairwise SPH pressure calculation."
    )
    min_distance_threshold: float = Field(
        default=1e-6, description="Minimum distance threshold to prevent numerical divide-by-zero errors."
    )

    # --- Simulation Domain & Volumes ---
    target_volume: float = Field(default=0.0005, description="Target total fluid volume to spawn (m^3).")
    bowl_wall_buffer: float = Field(
        default=0.002, description="Spawning buffer distance offset from container side walls (meters)."
    )
    characteristic_length: float = Field(
        default=0.076, description="Characteristic container scale or length dimension (meters)."
    )
    volume_threshold_liters: float = Field(default=0.400, description="Container target volume threshold (liters).")
    fallen_threshold_liters: float = Field(
        default=0.050, description="Maximum allowed volume of fluid to leak or fall (liters)."
    )
    boundaries: Optional[dict[str, Any]] = Field(
        default=None, description="Dictionary of physical boundary definitions."
    )
    sim_name: str = Field(default="", description="User-defined simulation run name tag.")
