"""Dynamic fluid body primitives and volume tracking models."""

from enum import Enum
import math
from typing import Any, Optional
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


def generate_cylinder_mesh(
    radius: float,
    z_min: float,
    z_max: float,
    center: tuple[float, float] = (0.0, 0.0),
    n_segments: int = 32,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a watertight 3D cylinder triangle mesh with outward normals."""
    cx, cy = center
    theta = np.linspace(0.0, 2.0 * np.pi, n_segments, endpoint=False)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    # Bottom ring vertices (0 .. n_segments - 1)
    v_bottom = np.column_stack([cx + radius * cos_t, cy + radius * sin_t, np.full(n_segments, z_min)])
    # Top ring vertices (n_segments .. 2*n_segments - 1)
    v_top = np.column_stack([cx + radius * cos_t, cy + radius * sin_t, np.full(n_segments, z_max)])
    # Bottom center (2*n_segments)
    v_bottom_center = np.array([[cx, cy, z_min]])
    # Top center (2*n_segments + 1)
    v_top_center = np.array([[cx, cy, z_max]])

    vertices = np.vstack([v_bottom, v_top, v_bottom_center, v_top_center]).astype(np.float32)

    idx_bot_c = 2 * n_segments
    idx_top_c = 2 * n_segments + 1

    faces = []
    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        # Side quad (2 triangles)
        faces.append([i, n_segments + i, n_segments + next_i])
        faces.append([i, n_segments + next_i, next_i])
        # Bottom cap (viewed from bottom)
        faces.append([idx_bot_c, next_i, i])
        # Top cap (viewed from top)
        faces.append([idx_top_c, n_segments + i, n_segments + next_i])

    return vertices, np.array(faces, dtype=np.uint32)


def generate_sphere_mesh(
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    radius: float = 0.010,
    n_lat: int = 12,
    n_lon: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a watertight 3D UV sphere triangle mesh with outward normals."""
    cx, cy, cz = center
    radius = max(radius, 1e-4)

    # North pole vertex (index 0)
    v_north = [cx, cy, cz + radius]
    vertices = [v_north]

    # Intermediate rings (latitudes from +pi/2 down to -pi/2 excluding poles)
    latitudes = np.linspace(np.pi / 2.0, -np.pi / 2.0, n_lat)[1:-1]
    longitudes = np.linspace(0.0, 2.0 * np.pi, n_lon, endpoint=False)

    for lat in latitudes:
        r_ring = radius * np.cos(lat)
        z = cz + radius * np.sin(lat)
        for lon in longitudes:
            x = cx + r_ring * np.cos(lon)
            y = cy + r_ring * np.sin(lon)
            vertices.append([x, y, z])

    # South pole vertex (index len(vertices))
    south_idx = len(vertices)
    vertices.append([cx, cy, cz - radius])
    vertices_arr = np.array(vertices, dtype=np.float32)

    faces = []
    # North pole cap triangles (connected to index 0)
    for j in range(n_lon):
        next_j = (j + 1) % n_lon
        faces.append([0, 1 + j, 1 + next_j])

    # Intermediate quads
    n_rings = len(latitudes)
    for i in range(n_rings - 1):
        r1 = 1 + i * n_lon
        r2 = 1 + (i + 1) * n_lon
        for j in range(n_lon):
            next_j = (j + 1) % n_lon
            faces.append([r1 + j, r2 + j, r2 + next_j])
            faces.append([r1 + j, r2 + next_j, r1 + next_j])

    # South pole cap triangles
    last_ring_start = 1 + (n_rings - 1) * n_lon
    for j in range(n_lon):
        next_j = (j + 1) % n_lon
        faces.append([south_idx, last_ring_start + next_j, last_ring_start + j])

    faces_arr = np.array(faces, dtype=np.uint32)
    return vertices_arr, faces_arr


def generate_heightfield_cylinder_mesh(
    radius: float,
    z_floor: float,
    surface_positions: Optional[np.ndarray] = None,
    default_z_top: float = 0.078,
    center: tuple[float, float] = (0.0, 0.0),
    n_rings: int = 6,
    n_spokes: int = 32,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a watertight 3D cylinder triangle mesh with a dynamic top surface heightfield."""
    cx, cy = center
    spoke_angles = np.linspace(0.0, 2.0 * np.pi, n_spokes, endpoint=False)
    cos_s = np.cos(spoke_angles)
    sin_s = np.sin(spoke_angles)

    # 1. Build 2D surface height grid from surface particles if provided
    nx, ny = 32, 32
    x_min, x_max = cx - radius, cx + radius
    y_min, y_max = cy - radius, cy + radius
    dx = max(1e-4, (x_max - x_min) / nx)
    dy = max(1e-4, (y_max - y_min) / ny)
    grid_z = np.full((nx, ny), default_z_top, dtype=np.float32)

    if surface_positions is not None and len(surface_positions) > 0:
        ix = np.clip(np.floor((surface_positions[:, 0] - x_min) / dx).astype(int), 0, nx - 1)
        iy = np.clip(np.floor((surface_positions[:, 1] - y_min) / dy).astype(int), 0, ny - 1)
        np.maximum.at(grid_z, (ix, iy), surface_positions[:, 2])

    def sample_z(x_arr: np.ndarray, y_arr: np.ndarray) -> np.ndarray:
        gx = np.clip(np.floor((x_arr - x_min) / dx).astype(int), 0, nx - 1)
        gy = np.clip(np.floor((y_arr - y_min) / dy).astype(int), 0, ny - 1)
        return grid_z[gx, gy]

    # Top center vertex (index 0)
    z_c = float(sample_z(np.array([cx]), np.array([cy]))[0])
    v_top_center = [cx, cy, z_c]

    # Top ring vertices (indices 1 .. n_rings * n_spokes)
    top_vertices = [v_top_center]
    r_steps = np.linspace(radius / n_rings, radius, n_rings)
    for r in r_steps:
        x_ring = cx + r * cos_s
        y_ring = cy + r * sin_s
        z_ring = sample_z(x_ring, y_ring)
        for s in range(n_spokes):
            top_vertices.append([float(x_ring[s]), float(y_ring[s]), float(z_ring[s])])

    # Bottom ring vertices (outer ring at z_floor)
    bot_ring_start = len(top_vertices)
    for s in range(n_spokes):
        x = float(cx + radius * cos_s[s])
        y = float(cy + radius * sin_s[s])
        top_vertices.append([x, y, z_floor])

    # Bottom center vertex (last index)
    bot_center_idx = len(top_vertices)
    top_vertices.append([cx, cy, z_floor])

    vertices = np.array(top_vertices, dtype=np.float32)

    faces = []
    # Inner ring triangles (connected to top center 0)
    for s in range(n_spokes):
        next_s = (s + 1) % n_spokes
        v1 = 1 + s
        v2 = 1 + next_s
        faces.append([0, v1, v2])

    # Intermediate ring quads (ring r to ring r+1)
    for r in range(n_rings - 1):
        r1_start = 1 + r * n_spokes
        r2_start = 1 + (r + 1) * n_spokes
        for s in range(n_spokes):
            next_s = (s + 1) % n_spokes
            p0 = r1_start + s
            p1 = r1_start + next_s
            p2 = r2_start + next_s
            p3 = r2_start + s
            faces.append([p0, p1, p2])
            faces.append([p0, p2, p3])

    # Side wall quads (connecting top outer ring to bottom ring)
    top_outer_start = 1 + (n_rings - 1) * n_spokes
    for s in range(n_spokes):
        next_s = (s + 1) % n_spokes
        t0 = top_outer_start + s
        t1 = top_outer_start + next_s
        b0 = bot_ring_start + s
        b1 = bot_ring_start + next_s
        faces.append([t0, b0, b1])
        faces.append([t0, b1, t1])

    # Bottom cap fan
    for s in range(n_spokes):
        next_s = (s + 1) % n_spokes
        b0 = bot_ring_start + s
        b1 = bot_ring_start + next_s
        faces.append([bot_center_idx, b1, b0])

    faces_arr = np.array(faces, dtype=np.uint32)
    return vertices, faces_arr


def generate_box_mesh(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a watertight 3D axis-aligned box triangle mesh."""
    x0, y0, z0 = bounds_min
    x1, y1, z1 = bounds_max
    x1 = max(x1, x0 + 1e-4)
    y1 = max(y1, y0 + 1e-4)
    z1 = max(z1, z0 + 1e-4)

    vertices = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=np.float32,
    )

    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [2, 3, 7],
            [2, 7, 6],
            [0, 4, 7],
            [0, 7, 3],
            [1, 2, 6],
            [1, 6, 5],
        ],
        dtype=np.uint32,
    )
    return vertices, faces


def generate_manifold_mesh_around_particles(
    positions: np.ndarray,
    r_s: float = 0.0025,
) -> tuple[np.ndarray, np.ndarray]:
    """Construct a watertight 3D manifold triangle mesh wrapped tightly around particle coordinates."""
    if positions is None or len(positions) == 0:
        return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.uint32)

    if len(positions) < 4:
        centroid = tuple(float(x) for x in np.mean(positions, axis=0))
        vol = len(positions) * (4.0 / 3.0) * math.pi * (r_s**3)
        radius = max(r_s, (3.0 * vol / (4.0 * math.pi)) ** (1.0 / 3.0))
        return generate_sphere_mesh(center=centroid, radius=radius)

    try:
        from scipy.spatial import ConvexHull

        hull = ConvexHull(positions)
        unique_indices = np.unique(hull.simplices)
        index_map = {orig: new for new, orig in enumerate(unique_indices)}
        vertices = positions[unique_indices].astype(np.float32)
        faces = np.vectorize(index_map.get)(hull.simplices).astype(np.uint32)
        return vertices, faces
    except Exception:
        centroid = tuple(float(x) for x in np.mean(positions, axis=0))
        radius = float(np.max(np.linalg.norm(positions - centroid, axis=1))) + r_s
        return generate_sphere_mesh(center=centroid, radius=radius)


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
    surface_positions: Optional[np.ndarray] = Field(
        default=None, description="Local or surface particle positions (M, 3) for dynamic surface heightfield sampling."
    )

    def to_mesh(self, n_segments: int = 32) -> tuple[np.ndarray, np.ndarray]:
        """Generate watertight 3D triangle mesh vertices and face indices for this fluid body."""
        cx, cy, _ = self.centroid
        z_min = self.bounds_min[2]
        z_max = self.bounds_max[2]

        if self.body_type == FluidBodyType.POOL:
            rx = (self.bounds_max[0] - self.bounds_min[0]) / 2.0
            ry = (self.bounds_max[1] - self.bounds_min[1]) / 2.0
            radius = max(0.010, (rx + ry) / 2.0)
            return generate_heightfield_cylinder_mesh(
                radius=radius,
                z_floor=z_min,
                surface_positions=self.surface_positions,
                default_z_top=z_max,
                center=(0.0, 0.0),
                n_rings=6,
                n_spokes=n_segments,
            )
        elif self.body_type == FluidBodyType.STREAM:
            rx = (self.bounds_max[0] - self.bounds_min[0]) / 2.0
            ry = (self.bounds_max[1] - self.bounds_min[1]) / 2.0
            radius = max(0.003, (rx + ry) / 2.0)
            return generate_cylinder_mesh(radius, z_min, z_max, center=(cx, cy), n_segments=n_segments)
        elif self.body_type == FluidBodyType.WATERFALL:
            if self.surface_positions is not None and len(self.surface_positions) >= 4:
                return generate_manifold_mesh_around_particles(self.surface_positions)
            rx = max(0.003, (self.bounds_max[0] - self.bounds_min[0]) / 2.0)
            ry = max(0.003, (self.bounds_max[1] - self.bounds_min[1]) / 2.0)
            radius = max(0.003, min(0.015, (rx + ry) / 2.0))
            return generate_cylinder_mesh(radius, z_min, z_max, center=(cx, cy), n_segments=n_segments)
        elif self.body_type == FluidBodyType.SHEET:
            rx = (self.bounds_max[0] - self.bounds_min[0]) / 2.0
            ry = (self.bounds_max[1] - self.bounds_min[1]) / 2.0
            radius = max(0.010, (rx + ry) / 2.0)
            return generate_cylinder_mesh(radius, z_min, z_max, center=(cx, cy), n_segments=n_segments)
        else:
            if self.surface_positions is not None and len(self.surface_positions) >= 4:
                return generate_manifold_mesh_around_particles(self.surface_positions)
            equiv_radius = max(0.002, (3.0 * max(1e-9, self.volume) / (4.0 * math.pi)) ** (1.0 / 3.0))
            equiv_radius = min(equiv_radius, max(0.004, (self.bounds_max[2] - self.bounds_min[2]) / 2.0))
            return generate_sphere_mesh(center=self.centroid, radius=equiv_radius, n_lat=10, n_lon=20)

    def to_cad_solid(self) -> Any:
        """Build and return a watertight build123d Solid representation conforming to CAD design principles."""
        from build123d import Cylinder, Sphere, Align, Location

        cx, cy, _ = self.centroid
        z_min = self.bounds_min[2]
        z_max = self.bounds_max[2]
        h = max(0.001, z_max - z_min)

        if self.body_type in (FluidBodyType.POOL, FluidBodyType.STREAM, FluidBodyType.SHEET, FluidBodyType.WATERFALL):
            rx = (self.bounds_max[0] - self.bounds_min[0]) / 2.0
            ry = (self.bounds_max[1] - self.bounds_min[1]) / 2.0
            radius = max(0.002, (rx + ry) / 2.0)
            c = Cylinder(radius=radius, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            pos = (0.0, 0.0, z_min) if self.body_type == FluidBodyType.POOL else (cx, cy, z_min)
            return c.locate(Location(pos))
        else:
            equiv_radius = max(0.002, (3.0 * max(1e-9, self.volume) / (4.0 * math.pi)) ** (1.0 / 3.0))
            s = Sphere(radius=equiv_radius)
            return s.locate(Location(self.centroid))

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
            self.surface_positions = None
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

        if self.body_type == FluidBodyType.POOL and len(body_pos) > 0:
            z_thresh = np.percentile(body_pos[:, 2], 75.0)
            top_mask = body_pos[:, 2] >= z_thresh
            self.surface_positions = body_pos[top_mask]
        else:
            self.surface_positions = body_pos

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

        # Distinguish drain waterfall streams from isolated droplet clusters
        d_drain_xy = np.sqrt(pos_act[:, 0] ** 2 + (pos_act[:, 1] + 0.020) ** 2)
        r_basin_xy = np.sqrt(pos_act[:, 0] ** 2 + pos_act[:, 1] ** 2)
        is_waterfall = is_falling & ((d_drain_xy < 0.040) | (r_basin_xy > 0.070))
        is_cluster = is_falling & (~is_waterfall)

        body_types = [
            (FluidBodyType.STREAM, is_stream),
            (FluidBodyType.SHEET, is_sheet),
            (FluidBodyType.WATERFALL, is_waterfall),
            (FluidBodyType.CLUSTER, is_cluster),
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
