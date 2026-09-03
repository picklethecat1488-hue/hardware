"""Dynamic fluid body primitives and volume tracking models."""

from enum import Enum
import math
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class FluidBodyType(str, Enum):
    """Semantic classification of dynamic fluid bodies."""

    POOL = "pool"
    STREAM = "stream"
    SHEET = "sheet"
    WATERFALL = "waterfall"
    CLUSTER = "cluster"


class FluidBody(BaseModel):
    """Represents a dynamic, contiguous 3D fluid body undergoing motion, deformation, splitting, or merging."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    body_id: int = Field(description="Unique identifier for the dynamic fluid body.")
    body_type: FluidBodyType = Field(
        default=FluidBodyType.POOL, description="Semantic classification of the fluid body."
    )
    particle_indices: np.ndarray = Field(description="Array of global particle indices belonging to this fluid body.")
    centroid: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Current 3D centroid coordinates."
    )
    bounds_min: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Axis-aligned bounding box minimum."
    )
    bounds_max: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Axis-aligned bounding box maximum."
    )
    velocity: tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Mean 3D velocity vector (m/s).")
    volume: float = Field(default=0.0, description="Physical fluid volume of the body in cubic meters.")
    particle_count: int = Field(default=0, description="Total number of particles in this fluid body.")

    def move(self, displacement: tuple[float, float, float] | np.ndarray) -> None:
        """Translate the fluid body bounding geometry and centroid by a 3D displacement vector.

        Args:
            displacement: 3D vector representing translational shift (dx, dy, dz).
        """
        disp = np.asarray(displacement, dtype=np.float32)
        self.centroid = (
            float(self.centroid[0] + disp[0]),
            float(self.centroid[1] + disp[1]),
            float(self.centroid[2] + disp[2]),
        )
        self.bounds_min = (
            float(self.bounds_min[0] + disp[0]),
            float(self.bounds_min[1] + disp[1]),
            float(self.bounds_min[2] + disp[2]),
        )
        self.bounds_max = (
            float(self.bounds_max[0] + disp[0]),
            float(self.bounds_max[1] + disp[1]),
            float(self.bounds_max[2] + disp[2]),
        )

    def recompute_shape(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        r_s: float,
    ) -> None:
        """Continuously recompute the physical geometric bounds, centroid, and volume of the moving fluid body.

        Args:
            positions: Global particle positions array of shape (N, 3).
            velocities: Global particle velocities array of shape (N, 3).
            r_s: Particle radius in meters.
        """
        if len(self.particle_indices) == 0:
            self.particle_count = 0
            self.volume = 0.0
            return

        body_pos = positions[self.particle_indices]
        body_vel = velocities[self.particle_indices]

        self.particle_count = len(self.particle_indices)
        vol_particle = (4.0 / 3.0) * math.pi * (r_s**3)
        self.volume = self.particle_count * vol_particle

        mean_c = np.mean(body_pos, axis=0)
        self.centroid = (float(mean_c[0]), float(mean_c[1]), float(mean_c[2]))

        min_b = np.min(body_pos, axis=0) - r_s
        self.bounds_min = (float(min_b[0]), float(min_b[1]), float(min_b[2]))

        max_b = np.max(body_pos, axis=0) + r_s
        self.bounds_max = (float(max_b[0]), float(max_b[1]), float(max_b[2]))

        mean_v = np.mean(body_vel, axis=0)
        self.velocity = (float(mean_v[0]), float(mean_v[1]), float(mean_v[2]))

    def split(
        self,
        clusters: list[np.ndarray],
        positions: np.ndarray,
        velocities: np.ndarray,
        r_s: float,
        next_id_fn: Any,
    ) -> list["FluidBody"]:
        """Split this fluid body into multiple independent child bodies based on disconnected cluster indices.

        Args:
            clusters: List of index arrays, each containing particle indices for a disconnected cluster.
            positions: Global particle positions array of shape (N, 3).
            velocities: Global particle velocities array of shape (N, 3).
            r_s: Particle radius in meters.
            next_id_fn: Callable returning a new unique integer body ID.

        Returns:
            List of newly created child FluidBody instances.
        """
        if len(clusters) <= 1:
            self.recompute_shape(positions, velocities, r_s)
            return [self]

        child_bodies: list[FluidBody] = []
        for cluster_indices in clusters:
            if len(cluster_indices) == 0:
                continue
            child = FluidBody(
                body_id=next_id_fn(),
                body_type=self.body_type,
                particle_indices=cluster_indices,
            )
            child.recompute_shape(positions, velocities, r_s)
            child_bodies.append(child)
        return child_bodies

    def merge(
        self,
        other: "FluidBody",
        positions: np.ndarray,
        velocities: np.ndarray,
        r_s: float,
    ) -> "FluidBody":
        """Merge another fluid body into this fluid body, forming a single unified fluid volume.

        Args:
            other: The other FluidBody instance to merge with.
            positions: Global particle positions array of shape (N, 3).
            velocities: Global particle velocities array of shape (N, 3).
            r_s: Particle radius in meters.

        Returns:
            Self, updated with merged particle indices and recomputed physical shape.
        """
        merged_indices = np.union1d(self.particle_indices, other.particle_indices)
        self.particle_indices = merged_indices
        self.recompute_shape(positions, velocities, r_s)
        return self


class FluidBodyTracker:
    """Manages the dynamic lifecycle of fluid bodies, performing move, split, and merge transitions."""

    def __init__(self, r_s: float = 0.0025) -> None:
        """Initialize tracker with particle radius.

        Args:
            r_s: Particle radius in meters.
        """
        self.r_s = r_s
        self._next_id = 1
        self.bodies: dict[int, FluidBody] = {}

    def _get_next_id(self) -> int:
        """Generate unique integer body ID."""
        nid = self._next_id
        self._next_id += 1
        return nid

    def update_bodies(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        z_floor: float,
        z_lid: float,
        tube_y: float = 0.028,
        tube_r: float = 0.010,
    ) -> list[FluidBody]:
        """Classify and recompute dynamic fluid bodies using move, split, and merge primitives.

        Args:
            positions: Global particle positions array of shape (N, 3).
            velocities: Global particle velocities array of shape (N, 3).
            z_floor: Cavity floor elevation in meters.
            z_lid: Lid terrace elevation in meters.
            tube_y: Center Y offset of the delivery tube.
            tube_r: Delivery tube inner radius.

        Returns:
            List of active FluidBody instances with recomputed physical shapes.
        """
        if len(positions) == 0:
            self.bodies.clear()
            return []

        active = positions[:, 2] < 100.0
        active_indices = np.flatnonzero(active)

        if len(active_indices) == 0:
            self.bodies.clear()
            return []

        pos_act = positions[active_indices]
        d_tube_xy = np.sqrt(pos_act[:, 0] ** 2 + (pos_act[:, 1] - tube_y) ** 2)

        # Dynamic particle classification across moving fluid bodies
        is_stream = (
            (d_tube_xy <= tube_r + self.r_s) & (pos_act[:, 2] >= z_floor) & (pos_act[:, 2] <= z_lid + self.r_s * 4.0)
        )
        is_sheet = (pos_act[:, 2] >= z_lid - self.r_s) & (~is_stream)
        in_basin = (~is_sheet) & (~is_stream)

        # Dynamically determine continuous reservoir pool free-surface elevation via spatial contiguity
        basin_indices = np.flatnonzero(in_basin)
        if len(basin_indices) > 0:
            basin_z = pos_act[basin_indices, 2]
            sorted_order = np.argsort(basin_z)
            sorted_z = basin_z[sorted_order]
            z_diffs = np.diff(sorted_z)
            gap_threshold = 4.0 * self.r_s
            gap_idx = np.where(z_diffs > gap_threshold)[0]
            if len(gap_idx) > 0:
                first_gap = gap_idx[0]
                z_pool_surf = float(sorted_z[first_gap] + self.r_s)
            else:
                z_pool_surf = float(np.max(basin_z))
        else:
            z_pool_surf = float(z_floor)

        is_pool = in_basin & (pos_act[:, 2] <= z_pool_surf)
        is_falling = in_basin & (pos_act[:, 2] > z_pool_surf)

        body_types = [
            (FluidBodyType.STREAM, is_stream),
            (FluidBodyType.SHEET, is_sheet),
            (FluidBodyType.CLUSTER, is_falling),
            (FluidBodyType.POOL, is_pool),
        ]

        active_bodies: list[FluidBody] = []
        for b_type, mask in body_types:
            indices = active_indices[mask]
            if len(indices) == 0:
                continue

            # Find matching existing body or create new one
            matched = False
            for body in self.bodies.values():
                if body.body_type == b_type:
                    # Move & update body with current indices
                    body.particle_indices = indices
                    body.recompute_shape(positions, velocities, self.r_s)
                    active_bodies.append(body)
                    matched = True
                    break

            if not matched:
                new_body = FluidBody(
                    body_id=self._get_next_id(),
                    body_type=b_type,
                    particle_indices=indices,
                )
                new_body.recompute_shape(positions, velocities, self.r_s)
                self.bodies[new_body.body_id] = new_body
                active_bodies.append(new_body)

        # Prune dead bodies
        active_ids = {b.body_id for b in active_bodies}
        self.bodies = {k: v for k, v in self.bodies.items() if k in active_ids}

        return active_bodies
