"""JAX-accelerated parallel multi-layer PCB maze router running on MPS and CUDA.

This module implements hardware-accelerated grid routing using parallel wavefront
propagation (Lee's algorithm / Bellman-Ford stencil) compiled with JAX JIT.
It maps PCB routing layers and obstacles to dense tensors, solving multi-layer
point-to-point and batched routing paths on Apple Silicon MPS and NVIDIA CUDA GPUs.
"""

import math
from typing import Dict, List, Optional, Set, Tuple

import jax
import jax.numpy as jnp
import numpy as np

from model.pcb import TraceSegmentModel, ViaModel
from provider.pcb.router import Obstacle, polyline_to_trace_segments

INF_COST: float = 1e7
REACHABLE_THRESHOLD: float = 1e6


@jax.jit
def _wavefront_step_2layer(
    cost: jnp.ndarray,
    mask: jnp.ndarray,
    via_mask: jnp.ndarray,
    step_cost: jnp.ndarray,
    via_penalty: float,
) -> jnp.ndarray:
    """Execute one single-step 4-neighborhood planar and via wavefront propagation for 2 layers.

    Args:
        cost: 3D float32 tensor of current shortest path costs (2, H, W).
        mask: 3D boolean tensor of obstacles (2, H, W).
        via_mask: 2D boolean tensor of via keepouts (H, W).
        step_cost: 2D float32 tensor of cell traversal step costs (H, W).
        via_penalty: Layer transition penalty cost.

    Returns:
        Updated 3D float32 cost tensor.
    """
    c_up = jnp.pad(cost[:, :-1, :], ((0, 0), (1, 0), (0, 0)), constant_values=INF_COST) + step_cost
    c_down = jnp.pad(cost[:, 1:, :], ((0, 0), (0, 1), (0, 0)), constant_values=INF_COST) + step_cost
    c_left = jnp.pad(cost[:, :, :-1], ((0, 0), (0, 0), (1, 0)), constant_values=INF_COST) + step_cost
    c_right = jnp.pad(cost[:, :, 1:], ((0, 0), (0, 0), (0, 1)), constant_values=INF_COST) + step_cost

    # Layer swap using explicit concatenation (fully compatible with Apple Silicon MPS and CUDA)
    other = jnp.concatenate([cost[1:2], cost[0:1]], axis=0)
    can_via = (other < REACHABLE_THRESHOLD) & (~via_mask[None, :, :])
    c_via = jnp.where(can_via, other + via_penalty, INF_COST)

    new_c = jnp.minimum(cost, jnp.minimum(jnp.minimum(c_up, c_down), jnp.minimum(c_left, c_right)))
    new_c = jnp.minimum(new_c, c_via)
    return jnp.where(mask, INF_COST, new_c)


@jax.jit
def _run_wavefront_chunk(
    cost: jnp.ndarray,
    mask: jnp.ndarray,
    via_mask: jnp.ndarray,
    step_cost: jnp.ndarray,
    via_penalty: float,
    chunk_size: int,
) -> jnp.ndarray:
    """Execute a chunk of N wavefront propagation iterations using compiled lax.fori_loop.

    Args:
        cost: 3D float32 cost tensor.
        mask: 3D boolean obstacle mask.
        via_mask: 2D boolean via obstacle mask.
        step_cost: 2D float32 tensor of cell traversal step costs.
        via_penalty: Via penalty in cost units.
        chunk_size: Number of steps to iterate per JIT execution.

    Returns:
        Updated cost tensor after chunk_size iterations.
    """

    def body_fn(_idx: int, c: jnp.ndarray) -> jnp.ndarray:
        return _wavefront_step_2layer(c, mask, via_mask, step_cost, via_penalty)

    return jax.lax.fori_loop(0, chunk_size, body_fn, cost)


@jax.jit
def _wavefront_step_batch_2layer(
    costs: jnp.ndarray,
    masks: jnp.ndarray,
    via_mask: jnp.ndarray,
    step_cost: jnp.ndarray,
    via_penalty: float,
    chunk_size: int,
) -> jnp.ndarray:
    """Execute parallel wavefront propagation across a batch of nets simultaneously.

    Args:
        costs: 4D float32 tensor of shape (B, 2, H, W).
        masks: 4D boolean tensor of shape (B, 2, H, W).
        via_mask: 2D boolean tensor of via keepouts (H, W).
        step_cost: 2D float32 tensor of cell traversal step costs (H, W).
        via_penalty: Layer transition penalty cost.
        chunk_size: Number of iterations per chunk.

    Returns:
        Updated costs tensor of shape (B, 2, H, W).
    """

    def body_fn(_idx: int, c: jnp.ndarray) -> jnp.ndarray:
        c_up = (
            jnp.pad(c[:, :, :-1, :], ((0, 0), (0, 0), (1, 0), (0, 0)), constant_values=INF_COST)
            + step_cost[None, None, :, :]
        )
        c_down = (
            jnp.pad(c[:, :, 1:, :], ((0, 0), (0, 0), (0, 1), (0, 0)), constant_values=INF_COST)
            + step_cost[None, None, :, :]
        )
        c_left = (
            jnp.pad(c[:, :, :, :-1], ((0, 0), (0, 0), (0, 0), (1, 0)), constant_values=INF_COST)
            + step_cost[None, None, :, :]
        )
        c_right = (
            jnp.pad(c[:, :, :, 1:], ((0, 0), (0, 0), (0, 0), (0, 1)), constant_values=INF_COST)
            + step_cost[None, None, :, :]
        )
        other = jnp.concatenate([c[:, 1:2], c[:, 0:1]], axis=1)
        can_via = (other < REACHABLE_THRESHOLD) & (~via_mask[None, None, :, :])
        c_via = jnp.where(can_via, other + via_penalty, INF_COST)
        new_c = jnp.minimum(c, jnp.minimum(jnp.minimum(c_up, c_down), jnp.minimum(c_left, c_right)))
        new_c = jnp.minimum(new_c, c_via)
        return jnp.where(masks, INF_COST, new_c)

    return jax.lax.fori_loop(0, chunk_size, body_fn, costs)


class JaxPCBRouter:
    """Hardware-accelerated multi-layer PCB grid router utilizing JAX on MPS and CUDA."""

    def __init__(
        self,
        board_bounds: Tuple[float, float, float, float],
        grid_step: float = 0.25,
        layers: Optional[List[str]] = None,
        obstacles: Optional[List[Obstacle]] = None,
        via_penalty: float = 2.00,
        dense_regions: Optional[List[Tuple[float, float, float, float, str]]] = None,
        connector_breakout_zones: Optional[List[Tuple[float, float, str]]] = None,
        outline_polygon: Optional[List[Tuple[float, float]]] = None,
        edge_clearance: float = 0.35,
        qfn_keepouts: Optional[List[Tuple[float, float, float, float]]] = None,
    ) -> None:
        """Initialize the JAX-accelerated PCB router.

        Args:
            board_bounds: Physical board boundaries (min_x, min_y, max_x, max_y) in mm.
            grid_step: Planar grid resolution in mm (default 0.25 mm).
            layers: Copper layer stack identifiers (default ["F.Cu", "B.Cu"]).
            obstacles: Initial physical obstacles to register.
            via_penalty: Cost penalty associated with drilling a through-hole via.
            dense_regions: Optional list of dense component bounding regions.
            connector_breakout_zones: Optional list of connector breakout centers.
            outline_polygon: Optional closed polygon defining the outer board contour.
            edge_clearance: Minimum clearance between routed traces and outer board edge.
            qfn_keepouts: Keepout zones beneath fine-pitch packages.
        """
        self.min_x, self.min_y, self.max_x, self.max_y = board_bounds
        self.grid_step = grid_step
        self.layers = layers or ["F.Cu", "B.Cu"]
        self.layer_to_idx = {lay: i for i, lay in enumerate(self.layers)}
        self.idx_to_layer = {i: lay for i, lay in enumerate(self.layers)}
        self.via_penalty = via_penalty
        self.dense_regions = dense_regions or []
        self.connector_breakout_zones = connector_breakout_zones or []
        self.outline_polygon = outline_polygon
        self.edge_clearance = edge_clearance
        self.qfn_keepouts = qfn_keepouts or []

        self.width_mm = self.max_x - self.min_x
        self.height_mm = self.max_y - self.min_y

        self.w_cells = int(math.ceil(self.width_mm / self.grid_step)) + 1
        self.h_cells = int(math.ceil(self.height_mm / self.grid_step)) + 1
        self.num_layers = len(self.layers)

        # Host NumPy obstacle mask synchronized with JAX device
        self.mask_np = np.zeros((self.num_layers, self.h_cells, self.w_cells), dtype=bool)
        self.via_mask_np = np.zeros((self.h_cells, self.w_cells), dtype=bool)
        self.step_cost_np = np.full((self.h_cells, self.w_cells), self.grid_step, dtype=np.float32)
        if self.dense_regions:
            for dr_min_x, dr_min_y, dr_max_x, dr_max_y, _ in self.dense_regions:
                gx_min = max(0, int(math.floor((dr_min_x - self.min_x) / self.grid_step)))
                gx_max = min(self.w_cells - 1, int(math.ceil((dr_max_x - self.min_x) / self.grid_step)))
                gy_min = max(0, int(math.floor((dr_min_y - self.min_y) / self.grid_step)))
                gy_max = min(self.h_cells - 1, int(math.ceil((dr_max_y - self.min_y) / self.grid_step)))
                self.step_cost_np[gy_min : gy_max + 1, gx_min : gx_max + 1] = self.grid_step * 1.5

        self.obstacles: List[Obstacle] = []
        self.pin_cells: Set[Tuple[int, int, str]] = set()
        self.routed_cells: Dict[Tuple[int, int, int], str] = {}
        self.blocked_cells: Dict[Tuple[int, int, str], Optional[str]] = {}

        self._apply_boundary_and_keepouts()

        if obstacles:
            for obs in obstacles:
                self.add_obstacle(obs)

    def _apply_boundary_and_keepouts(self) -> None:
        """Apply board edge clearances, outline polygon boundaries, and QFN via keepouts to obstacle masks."""
        if self.edge_clearance > 0.0:
            c_cells_x = int(math.ceil(self.edge_clearance / self.grid_step))
            c_cells_y = int(math.ceil(self.edge_clearance / self.grid_step))
            self.mask_np[:, :c_cells_y, :] = True
            self.mask_np[:, -c_cells_y:, :] = True
            self.mask_np[:, :, :c_cells_x] = True
            self.mask_np[:, :, -c_cells_x:] = True
            self.via_mask_np[:c_cells_y, :] = True
            self.via_mask_np[-c_cells_y:, :] = True
            self.via_mask_np[:, :c_cells_x] = True
            self.via_mask_np[:, -c_cells_x:] = True

        if self.outline_polygon and len(self.outline_polygon) >= 3:
            from provider.geometry_utils import point_in_polygon

            for gy in range(self.h_cells):
                for gx in range(self.w_cells):
                    px, py, _ = self.grid_to_world(0, gy, gx)
                    if not point_in_polygon(px, py, self.outline_polygon):
                        self.mask_np[:, gy, gx] = True
                        self.via_mask_np[gy, gx] = True

        for kx_min, ky_min, kx_max, ky_max in self.qfn_keepouts:
            gx_min = max(0, int(math.floor((kx_min - self.min_x) / self.grid_step)))
            gx_max = min(self.w_cells - 1, int(math.ceil((kx_max - self.min_x) / self.grid_step)))
            gy_min = max(0, int(math.floor((ky_min - self.min_y) / self.grid_step)))
            gy_max = min(self.h_cells - 1, int(math.ceil((ky_max - self.min_y) / self.grid_step)))
            self.via_mask_np[gy_min : gy_max + 1, gx_min : gx_max + 1] = True

    def world_to_grid(self, px: float, py: float, layer_name: str) -> Tuple[int, int, int]:
        """Convert continuous physical board coordinate to discrete 3D grid cell indices.

        Args:
            px: Physical X coordinate in mm.
            py: Physical Y coordinate in mm.
            layer_name: Copper layer name (e.g. 'F.Cu').

        Returns:
            Tuple of (layer_idx, gy, gx).
        """
        layer_idx = self.layer_to_idx.get(layer_name, 0)
        gx = int(round((px - self.min_x) / self.grid_step))
        gy = int(round((py - self.min_y) / self.grid_step))
        gx = max(0, min(self.w_cells - 1, gx))
        gy = max(0, min(self.h_cells - 1, gy))
        return (layer_idx, gy, gx)

    def grid_to_world(self, layer_idx: int, gy: int, gx: int) -> Tuple[float, float, str]:
        """Convert discrete 3D grid cell indices back to continuous physical board coordinates.

        Args:
            layer_idx: Layer index in routing stack.
            gy: Discrete Y grid row.
            gx: Discrete X grid column.

        Returns:
            Tuple of (px, py, layer_name).
        """
        px = self.min_x + gx * self.grid_step
        py = self.min_y + gy * self.grid_step
        layer_name = self.idx_to_layer.get(layer_idx, "F.Cu")
        return (round(px, 3), round(py, 3), layer_name)

    def is_via_allowed(self, px: float, py: float) -> bool:
        """Check if a via is permitted at the specified physical coordinate."""
        gx = int(round((px - self.min_x) / self.grid_step))
        gy = int(round((py - self.min_y) / self.grid_step))
        if 0 <= gx < self.w_cells and 0 <= gy < self.h_cells:
            return not bool(self.via_mask_np[gy, gx])
        return False

    def add_obstacle(self, obs: Obstacle) -> None:
        """Register a physical keepout or copper boundary obstacle in the router domain.

        Args:
            obs: Obstacle model instance with bounding envelope and layer constraint.
        """
        self.obstacles.append(obs)
        gx_min = max(0, int(math.floor((obs.min_x - self.min_x) / self.grid_step)))
        gx_max = min(self.w_cells - 1, int(math.ceil((obs.max_x - self.min_x) / self.grid_step)))
        gy_min = max(0, int(math.floor((obs.min_y - self.min_y) / self.grid_step)))
        gy_max = min(self.h_cells - 1, int(math.ceil((obs.max_y - self.min_y) / self.grid_step)))

        target_layer_indices = (
            list(range(self.num_layers))
            if obs.layer == "ALL"
            else [self.layer_to_idx[obs.layer]]
            if obs.layer in self.layer_to_idx
            else []
        )

        for l_idx in target_layer_indices:
            lay_name = self.idx_to_layer[l_idx]
            if obs.is_circle and obs.center and obs.radius:
                r_eff = obs.max_x - obs.center[0]
                for gy in range(gy_min, gy_max + 1):
                    py = self.min_y + gy * self.grid_step
                    for gx in range(gx_min, gx_max + 1):
                        px = self.min_x + gx * self.grid_step
                        if math.hypot(px - obs.center[0], py - obs.center[1]) <= r_eff:
                            self.mask_np[l_idx, gy, gx] = True
                            key = (gx, gy, lay_name)
                            if obs.is_pin:
                                self.pin_cells.add(key)
                            self.blocked_cells[key] = obs.net
            else:
                self.mask_np[l_idx, gy_min : gy_max + 1, gx_min : gx_max + 1] = True
                for gy in range(gy_min, gy_max + 1):
                    for gx in range(gx_min, gx_max + 1):
                        key = (gx, gy, lay_name)
                        if obs.is_pin:
                            self.pin_cells.add(key)
                        self.blocked_cells[key] = obs.net

    def rebuild_spatial_index(self) -> None:
        """Rebuild dense obstacle tensor and dictionary indices from current registered obstacles."""
        self.mask_np.fill(False)
        self.via_mask_np.fill(False)
        self.blocked_cells.clear()
        self.pin_cells.clear()
        self._apply_boundary_and_keepouts()
        all_obs = list(self.obstacles)
        self.obstacles.clear()
        for obs in all_obs:
            self.add_obstacle(obs)

    def route_net(
        self,
        start_pt: Tuple[float, float],
        start_layer: str,
        end_pt: Tuple[float, float],
        end_layer: str,
        net_name: str,
        width_mm: float = 0.20,
        chunk_size: int = 25,
        max_chunks: int = 48,
        junction_points: Optional[List[Tuple[float, float]]] = None,
        fillet_radius: float = 0.20,
    ) -> Tuple[List[TraceSegmentModel], List[ViaModel]]:
        """Solve optimal collision-free multi-layer path between start and end using GPU JAX wavefronts.

        Args:
            start_pt: Physical (x, y) start coordinate in mm.
            start_layer: Starting copper layer name.
            end_pt: Physical (x, y) target coordinate in mm.
            end_layer: Target copper layer name.
            net_name: Identifier of the electrical net being routed.
            width_mm: Physical trace copper width in mm.
            chunk_size: Wavefront propagation steps per JIT-compiled loop chunk.
            max_chunks: Maximum number of chunks before declaring route unreachable.
            junction_points: Optional list of T-junction points to preserve.
            fillet_radius: Corner chamfer / fillet radius in mm.

        Returns:
            Tuple of (list of TraceSegmentModel, list of ViaModel).

        Raises:
            RuntimeError: If target is completely unreachable or blocked by obstacles.
        """
        l0, y0, x0 = self.world_to_grid(start_pt[0], start_pt[1], start_layer)
        l1, y1, x1 = self.world_to_grid(end_pt[0], end_pt[1], end_layer)

        # Prepare active obstacle mask for this net
        active_mask = np.copy(self.mask_np)
        for (gx, gy, lay_name), obs_net in self.blocked_cells.items():
            if obs_net == net_name:
                l_idx = self.layer_to_idx.get(lay_name, 0)
                active_mask[l_idx, gy, gx] = False

        # Ensure start and target endpoints are open
        active_mask[l0, max(0, y0 - 1) : y0 + 2, max(0, x0 - 1) : x0 + 2] = False
        active_mask[l1, max(0, y1 - 1) : y1 + 2, max(0, x1 - 1) : x1 + 2] = False

        mask_jax = jnp.array(active_mask, dtype=bool)
        via_mask_jax = jnp.array(self.via_mask_np, dtype=bool)
        step_cost_jax = jnp.array(self.step_cost_np, dtype=jnp.float32)

        cost = jnp.full((self.num_layers, self.h_cells, self.w_cells), INF_COST, dtype=jnp.float32)
        cost = cost.at[l0, y0, x0].set(0.0)

        # Iteratively expand wavefront in JIT chunks on MPS/CUDA until target is reached
        target_cost = float(INF_COST)
        for _ in range(max_chunks):
            cost = _run_wavefront_chunk(cost, mask_jax, via_mask_jax, step_cost_jax, self.via_penalty, chunk_size)
            target_cost = float(cost[l1, y1, x1])
            if target_cost < REACHABLE_THRESHOLD:
                break

        if target_cost >= REACHABLE_THRESHOLD:
            raise RuntimeError(
                f"JAX router could not find collision-free path for net '{net_name}' "
                f"from ({start_pt[0]:.2f}, {start_pt[1]:.2f}) [{start_layer}] "
                f"to ({end_pt[0]:.2f}, {end_pt[1]:.2f}) [{end_layer}] "
                f"(grid start=({l0}, {y0}, {x0}), target=({l1}, {y1}, {x1}))"
            )

        # Backtrack optimal shortest path along negative gradient on host NumPy array
        cost_np = np.array(cost)
        curr = (l1, y1, x1)
        grid_path = [curr]

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while curr != (l0, y0, x0):
            cl, cy, cx = curr
            best_cost = cost_np[cl, cy, cx]
            best_next = None

            # 1. Check 4 planar orthogonal neighbors
            for dy, dx in dirs:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < self.h_cells and 0 <= nx < self.w_cells:
                    c_cand = cost_np[cl, ny, nx]
                    if c_cand < best_cost:
                        best_cost = c_cand
                        best_next = (cl, ny, nx)

            # 2. Check layer transition via (if not in via_mask)
            if not self.via_mask_np[cy, cx]:
                other_l = 1 - cl if self.num_layers == 2 else (cl + 1) % self.num_layers
                c_via_cand = cost_np[other_l, cy, cx]
                if c_via_cand + self.via_penalty <= cost_np[cl, cy, cx] + 1e-4 and c_via_cand < best_cost:
                    best_cost = c_via_cand
                    best_next = (other_l, cy, cx)

            if best_next is None or best_next == curr:
                break

            curr = best_next
            grid_path.append(curr)

        grid_path.reverse()

        raw_path: List[Tuple[float, float, str]] = []
        for gl, gy, gx in grid_path:
            px, py, lay = self.grid_to_world(gl, gy, gx)
            raw_path.append((px, py, lay))

        if len(raw_path) < 2:
            return [], []

        raw_path[0] = (start_pt[0], start_pt[1], start_layer)
        raw_path[-1] = (end_pt[0], end_pt[1], end_layer)

        traces: List[TraceSegmentModel] = []
        vias: List[ViaModel] = []

        current_layer_pts: List[Tuple[float, float]] = [(raw_path[0][0], raw_path[0][1])]
        current_layer = raw_path[0][2]

        for i in range(1, len(raw_path)):
            px, py, lay = raw_path[i]
            if lay == current_layer:
                current_layer_pts.append((px, py))
            else:
                if len(current_layer_pts) >= 2:
                    traces.extend(
                        polyline_to_trace_segments(
                            current_layer_pts,
                            width_mm,
                            current_layer,
                            net_name,
                            fillet_radius=fillet_radius,
                            junction_points=junction_points,
                        )
                    )
                is_dense_via = False
                if self.dense_regions:
                    for dr_min_x, dr_min_y, dr_max_x, dr_max_y, _ in self.dense_regions:
                        if dr_min_x - 0.10 <= px <= dr_max_x + 0.10 and dr_min_y - 0.10 <= py <= dr_max_y + 0.10:
                            is_dense_via = True
                            break
                v_pad = 0.36 if is_dense_via else 0.45
                v_drill = 0.16 if is_dense_via else 0.20
                vias.append(
                    ViaModel(
                        net=net_name,
                        position_mm=(px, py),
                        pad_diameter_mm=v_pad,
                        drill_diameter_mm=v_drill,
                        layer_start="F.Cu",
                        layer_end="B.Cu",
                    )
                )
                current_layer = lay
                current_layer_pts = [(px, py)]

        if len(current_layer_pts) >= 2:
            traces.extend(
                polyline_to_trace_segments(
                    current_layer_pts,
                    width_mm,
                    current_layer,
                    net_name,
                    fillet_radius=fillet_radius,
                    junction_points=junction_points,
                )
            )

        for v in vias:
            v_r = v.pad_diameter_mm / 2.0 + 0.14
            self.add_obstacle(
                Obstacle(
                    min_x=v.position_mm[0] - v_r,
                    min_y=v.position_mm[1] - v_r,
                    max_x=v.position_mm[0] + v_r,
                    max_y=v.position_mm[1] + v_r,
                    layer="ALL",
                    net=net_name,
                    is_circle=True,
                    center=v.position_mm,
                    radius=v.pad_diameter_mm / 2.0,
                )
            )
            gx_v = round((v.position_mm[0] - self.min_x) / self.grid_step)
            gy_v = round((v.position_mm[1] - self.min_y) / self.grid_step)
            for l_i in range(len(self.layers)):
                self.routed_cells[(gx_v, gy_v, l_i)] = net_name

        for tr in traces:
            w_half = max(tr.width_mm / 2.0 + 0.12, 0.21)
            self.add_obstacle(
                Obstacle(
                    min_x=min(tr.start_mm[0], tr.end_mm[0]) - w_half,
                    min_y=min(tr.start_mm[1], tr.end_mm[1]) - w_half,
                    max_x=max(tr.start_mm[0], tr.end_mm[0]) + w_half,
                    max_y=max(tr.start_mm[1], tr.end_mm[1]) + w_half,
                    layer=tr.layer,
                    net=net_name,
                )
            )
            gx_s = round((tr.start_mm[0] - self.min_x) / self.grid_step)
            gy_s = round((tr.start_mm[1] - self.min_y) / self.grid_step)
            gx_e = round((tr.end_mm[0] - self.min_x) / self.grid_step)
            gy_e = round((tr.end_mm[1] - self.min_y) / self.grid_step)
            l_idx = self.layer_to_idx.get(tr.layer, 0)
            dist_cells = max(abs(gx_e - gx_s), abs(gy_e - gy_s), 1)
            for s in range(dist_cells + 1):
                t = s / dist_cells
                cgx = round(gx_s + t * (gx_e - gx_s))
                cgy = round(gy_s + t * (gy_e - gy_s))
                self.routed_cells[(cgx, cgy, l_idx)] = net_name

        return traces, vias

    def route_batch(
        self,
        net_specs: List[Tuple[Tuple[float, float], str, Tuple[float, float], str, str, float]],
        chunk_size: int = 25,
        max_chunks: int = 16,
    ) -> List[Tuple[List[TraceSegmentModel], List[ViaModel]]]:
        """Solve multiple independent routing nets in parallel across GPU tensor batches.

        Args:
            net_specs: List of tuples (start_pt, start_layer, end_pt, end_layer, net_name, width_mm).
            chunk_size: Wavefront propagation iterations per chunk.
            max_chunks: Maximum number of chunks to run.

        Returns:
            List of (traces, vias) per net in the batch.
        """
        if not net_specs:
            return []

        b_size = len(net_specs)
        costs_np = np.full((b_size, self.num_layers, self.h_cells, self.w_cells), INF_COST, dtype=np.float32)
        masks_np = np.repeat(self.mask_np[np.newaxis, :, :, :], b_size, axis=0)

        targets: List[Tuple[int, int, int]] = []
        starts: List[Tuple[int, int, int]] = []

        for b_idx, (s_pt, s_lay, e_pt, e_lay, _net_name, _w) in enumerate(net_specs):
            l0, y0, x0 = self.world_to_grid(s_pt[0], s_pt[1], s_lay)
            l1, y1, x1 = self.world_to_grid(e_pt[0], e_pt[1], e_lay)
            costs_np[b_idx, l0, y0, x0] = 0.0
            masks_np[b_idx, l0, max(0, y0 - 1) : y0 + 2, max(0, x0 - 1) : x0 + 2] = False
            masks_np[b_idx, l1, max(0, y1 - 1) : y1 + 2, max(0, x1 - 1) : x1 + 2] = False
            starts.append((l0, y0, x0))
            targets.append((l1, y1, x1))

        costs_jax = jnp.array(costs_np)
        masks_jax = jnp.array(masks_np)
        via_mask_jax = jnp.array(self.via_mask_np, dtype=bool)
        step_cost_jax = jnp.array(self.step_cost_np, dtype=jnp.float32)

        for _ in range(max_chunks):
            costs_jax = _wavefront_step_batch_2layer(
                costs_jax, masks_jax, via_mask_jax, step_cost_jax, self.via_penalty, chunk_size
            )
            # Check if all reached
            reached_all = True
            for b_idx, (tl, ty, tx) in enumerate(targets):
                if float(costs_jax[b_idx, tl, ty, tx]) >= REACHABLE_THRESHOLD:
                    reached_all = False
                    break
            if reached_all:
                break

        costs_final = np.array(costs_jax)
        batch_results: List[Tuple[List[TraceSegmentModel], List[ViaModel]]] = []

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for b_idx, (s_pt, s_lay, e_pt, e_lay, net_name, width_mm) in enumerate(net_specs):
            l0, y0, x0 = starts[b_idx]
            l1, y1, x1 = targets[b_idx]

            if costs_final[b_idx, l1, y1, x1] >= REACHABLE_THRESHOLD:
                # Fall back to single-net routing for failed batch net
                net_res = self.route_net(s_pt, s_lay, e_pt, e_lay, net_name, width_mm)
                batch_results.append(net_res)
                continue

            curr = (l1, y1, x1)
            grid_path = [curr]
            while curr != (l0, y0, x0):
                cl, cy, cx = curr
                best_cost = costs_final[b_idx, cl, cy, cx]
                best_next = None

                for dy, dx in dirs:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < self.h_cells and 0 <= nx < self.w_cells:
                        c_cand = costs_final[b_idx, cl, ny, nx]
                        if c_cand < best_cost:
                            best_cost = c_cand
                            best_next = (cl, ny, nx)

                if not self.via_mask_np[cy, cx]:
                    other_l = 1 - cl if self.num_layers == 2 else (cl + 1) % self.num_layers
                    c_via_cand = costs_final[b_idx, other_l, cy, cx]
                    if (
                        c_via_cand + self.via_penalty <= costs_final[b_idx, cl, cy, cx] + 1e-4
                        and c_via_cand < best_cost
                    ):
                        best_cost = c_via_cand
                        best_next = (other_l, cy, cx)

                if best_next is None or best_next == curr:
                    break
                curr = best_next
                grid_path.append(curr)

            grid_path.reverse()
            raw_pts = [self.grid_to_world(gl, gy, gx) for gl, gy, gx in grid_path]
            if not raw_pts:
                batch_results.append(([], []))
                continue

            raw_pts[0] = (s_pt[0], s_pt[1], s_lay)
            raw_pts[-1] = (e_pt[0], e_pt[1], e_lay)

            compressed_pts: List[Tuple[float, float, str]] = [raw_pts[0]]
            for i in range(1, len(raw_pts) - 1):
                p_prev = compressed_pts[-1]
                p_curr = raw_pts[i]
                p_next = raw_pts[i + 1]

                if p_curr[2] != p_prev[2] or p_curr[2] != p_next[2]:
                    compressed_pts.append(p_curr)
                    continue

                dx1 = p_curr[0] - p_prev[0]
                dy1 = p_curr[1] - p_prev[1]
                dx2 = p_next[0] - p_curr[0]
                dy2 = p_next[1] - p_curr[1]

                is_collinear = (abs(dx1) < 1e-4 and abs(dx2) < 1e-4) or (abs(dy1) < 1e-4 and abs(dy2) < 1e-4)
                if not is_collinear:
                    compressed_pts.append(p_curr)

            compressed_pts.append(raw_pts[-1])
            net_traces: List[TraceSegmentModel] = []
            net_vias: List[ViaModel] = []

            for i in range(len(compressed_pts) - 1):
                p0 = compressed_pts[i]
                p1 = compressed_pts[i + 1]
                if p0[2] != p1[2]:
                    net_vias.append(
                        ViaModel(
                            net=net_name,
                            position_mm=(p0[0], p0[1]),
                            pad_diameter_mm=0.45,
                            drill_diameter_mm=0.20,
                            layer_start=min(p0[2], p1[2]),
                            layer_end=max(p0[2], p1[2]),
                        )
                    )
                else:
                    d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                    if d > 1e-4:
                        net_traces.append(
                            TraceSegmentModel(
                                net=net_name,
                                layer=p0[2],
                                width_mm=width_mm,
                                start_mm=(p0[0], p0[1]),
                                end_mm=(p1[0], p1[1]),
                            )
                        )

            batch_results.append((net_traces, net_vias))

        return batch_results
