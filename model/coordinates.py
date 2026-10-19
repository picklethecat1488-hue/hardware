"""Coordinate spaces and systems data models."""

from enum import StrEnum
import math
from typing import Tuple
from pydantic import BaseModel, Field, field_validator


class CoordinateSpace(StrEnum):
    """Reference coordinate spaces across the CAD, PyBullet, and Fluid engines."""

    WORLD = "world"  # Global simulation frame
    BASE_LINK = "base_link"  # Base container / robot base link frame
    LOCAL_LINK = "local_link"  # Specific link / boundary frame (e.g. impeller, tube, casing)
    VOXEL_GRID = "voxel_grid"  # Lattice Boltzmann / collision grid indices [0, N-1]


class CoordinateSystem(StrEnum):
    """Metric coordinate systems for spatial geometry."""

    CARTESIAN_3D = "cartesian_3d"  # (x, y, z) in meters
    CYLINDRICAL = "cylindrical"  # (r, theta, z) with r >= 0, theta in [-pi, pi], z in meters
    POLAR_2D = "polar_2d"  # (r, theta) with r >= 0, theta in [-pi, pi]
    SPHERICAL = "spherical"  # (r, theta, phi)


class SpatialPose(BaseModel):
    """Strongly typed 3D pose with explicit reference frame annotation."""

    xyz: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Translation (x, y, z) in meters")
    rpy: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Roll, pitch, yaw in radians")
    space: CoordinateSpace = Field(default=CoordinateSpace.LOCAL_LINK)
    system: CoordinateSystem = Field(default=CoordinateSystem.CARTESIAN_3D)

    @field_validator("rpy")
    @classmethod
    def validate_radians(cls, rpy: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Validate that angles are within standard rotational bounds [-2pi, 2pi]."""
        for angle in rpy:
            if not (-2.0 * math.pi <= angle <= 2.0 * math.pi):
                raise ValueError(f"Angle {angle} rad exceeds valid rotation bounds [-2pi, 2pi]")
        return rpy
