"""PCB auto-router engine computing collision-free multi-layer routes for component netlists."""

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import yaml

from model.pcb import BoardType, PCBConfig, TraceSegmentModel, ViaModel, TestPointModel
from model.wiring import Wiring


def fillet_corner(
    p0: Tuple[float, float],
    v: Tuple[float, float],
    p2: Tuple[float, float],
    radius: float = 0.60,
    num_segments: int = 3,
) -> List[Tuple[float, float]]:
    """Generate a series of points approximating a circular fillet around 90-degree corner vertex v.

    Args:
        p0: Starting point of incoming segment.
        v: Corner vertex where the turn occurs.
        p2: Ending point of outgoing segment.
        radius: Target fillet radius in mm.
        num_segments: Number of linear segments used to approximate the rounded arc.

    Returns:
        List of points [p0, pt_start, arc_1, arc_2, ..., pt_end, p2].
    """
    dx1, dy1 = p0[0] - v[0], p0[1] - v[1]
    len1 = math.hypot(dx1, dy1)
    dx2, dy2 = p2[0] - v[0], p2[1] - v[1]
    len2 = math.hypot(dx2, dy2)

    r = min(radius, len1 * 0.45, len2 * 0.45)
    if r < 0.05:
        return [p0, v, p2]

    u1 = (dx1 / len1, dy1 / len1)
    u2 = (dx2 / len2, dy2 / len2)

    # Check if lines are parallel/collinear
    cross = abs(u1[0] * u2[1] - u1[1] * u2[0])
    if cross < 0.1:
        return [p0, v, p2]

    pt_start = (round(v[0] + u1[0] * r, 4), round(v[1] + u1[1] * r, 4))
    pt_end = (round(v[0] + u2[0] * r, 4), round(v[1] + u2[1] * r, 4))
    center = (v[0] + (u1[0] + u2[0]) * r, v[1] + (u1[1] + u2[1]) * r)

    ang_start = math.atan2(pt_start[1] - center[1], pt_start[0] - center[0])
    ang_end = math.atan2(pt_end[1] - center[1], pt_end[0] - center[0])

    diff = ang_end - ang_start
    while diff > math.pi:
        diff -= 2 * math.pi
    while diff < -math.pi:
        diff += 2 * math.pi

    pts = [p0, pt_start]
    for i in range(1, num_segments):
        t = i / num_segments
        theta = ang_start + diff * t
        pts.append((round(center[0] + r * math.cos(theta), 4), round(center[1] + r * math.sin(theta), 4)))
    pts.append(pt_end)
    pts.append(p2)
    return pts


def polyline_to_trace_segments(
    pts: Sequence[Tuple[float, float]],
    width_mm: float,
    layer: str,
    net: str,
    fillet_radius: float = 0.20,
    junction_points: Optional[Sequence[Tuple[float, float]]] = None,
) -> List[TraceSegmentModel]:
    """Convert an orthogonal polyline sequence into TraceSegmentModels with filleted 90-degree corners.

    Args:
        pts: Ordered list of (x, y) coordinates defining the trace centerline.
        width_mm: Conductor trace width in millimeters.
        layer: Copper layer (e.g. 'F.Cu' or 'B.Cu').
        net: Electrical net name.
        fillet_radius: Radius in mm for filleting 90-degree corners.
        junction_points: Optional coordinates of T-junctions or pins that must remain straight.

    Returns:
        List of TraceSegmentModel primitives.
    """
    if len(pts) < 2:
        return []

    # Simplify consecutive collinear points
    simplified: List[Tuple[float, float]] = [pts[0]]
    for i in range(1, len(pts) - 1):
        p_prev = simplified[-1]
        p_curr = pts[i]
        p_next = pts[i + 1]

        d1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        d2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        len1 = math.hypot(d1[0], d1[1])
        len2 = math.hypot(d2[0], d2[1])
        if len1 < 1e-4 or len2 < 1e-4:
            continue
        cross = abs((d1[0] / len1) * (d2[1] / len2) - (d1[1] / len1) * (d2[0] / len2))
        dot = (d1[0] / len1) * (d2[0] / len2) + (d1[1] / len1) * (d2[1] / len2)
        if cross < 1e-3 and dot > 0.99:
            continue
        simplified.append(p_curr)
    simplified.append(pts[-1])

    # Apply fillets at turns, keeping junction points straight
    if len(simplified) <= 2 or fillet_radius <= 0:
        final_pts = simplified
    else:
        final_pts = [simplified[0]]
        for i in range(1, len(simplified) - 1):
            p_prev = final_pts[-1]
            p_curr = simplified[i]
            p_next = simplified[i + 1]
            is_junction = False
            if junction_points:
                for jp in junction_points:
                    if math.hypot(p_curr[0] - jp[0], p_curr[1] - jp[1]) <= (fillet_radius + 0.15):
                        is_junction = True
                        break
            if is_junction:
                final_pts.append(p_curr)
            else:
                arc = fillet_corner(p_prev, p_curr, p_next, radius=fillet_radius)
                final_pts.extend(arc[1:-1])
        final_pts.append(simplified[-1])

    traces: List[TraceSegmentModel] = []
    for i in range(len(final_pts) - 1):
        p1 = final_pts[i]
        p2 = final_pts[i + 1]
        if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-4:
            traces.append(
                TraceSegmentModel(
                    start_mm=(round(p1[0], 4), round(p1[1], 4)),
                    end_mm=(round(p2[0], 4), round(p2[1], 4)),
                    width_mm=width_mm,
                    layer=layer,
                    net=net,
                )
            )
    return traces


def straighten_junction_traces(
    traces: List[TraceSegmentModel],
    fillet_radius: float = 0.20,
) -> List[TraceSegmentModel]:
    """Ensure all trace segments meeting at a junction (3 or more connections) are straightened without rounded fillets."""
    if not traces:
        return traces

    from collections import defaultdict

    def quant(pt: Tuple[float, float]) -> Tuple[float, float]:
        return (round(pt[0], 2), round(pt[1], 2))

    degree: Dict[Tuple[str, str, Tuple[float, float]], int] = defaultdict(int)
    for tr in traces:
        degree[(tr.layer, tr.net, quant(tr.start_mm))] += 1
        degree[(tr.layer, tr.net, quant(tr.end_mm))] += 1

    junctions = {k for k, count in degree.items() if count >= 3}
    if not junctions:
        return traces

    cleaned: List[TraceSegmentModel] = []
    for tr in traces:
        p1 = quant(tr.start_mm)
        p2 = quant(tr.end_mm)
        is_near_junction = (tr.layer, tr.net, p1) in junctions or (tr.layer, tr.net, p2) in junctions

        dx = abs(tr.end_mm[0] - tr.start_mm[0])
        dy = abs(tr.end_mm[1] - tr.start_mm[1])
        is_orthogonal = (dx < 1e-4) or (dy < 1e-4)
        length = math.hypot(dx, dy)

        if is_near_junction and not is_orthogonal and length <= (fillet_radius * 2.0):
            j_key = (tr.layer, tr.net, p1) if (tr.layer, tr.net, p1) in junctions else (tr.layer, tr.net, p2)
            j_pt = j_key[2]
            other_pt = tr.end_mm if j_pt == p1 else tr.start_mm
            corner = (other_pt[0], j_pt[1])
            if math.hypot(corner[0] - other_pt[0], corner[1] - other_pt[1]) > 1e-4:
                cleaned.append(
                    TraceSegmentModel(
                        start_mm=(round(other_pt[0], 4), round(other_pt[1], 4)),
                        end_mm=(round(corner[0], 4), round(corner[1], 4)),
                        width_mm=tr.width_mm,
                        layer=tr.layer,
                        net=tr.net,
                    )
                )
            if math.hypot(j_pt[0] - corner[0], j_pt[1] - corner[1]) > 1e-4:
                cleaned.append(
                    TraceSegmentModel(
                        start_mm=(round(corner[0], 4), round(corner[1], 4)),
                        end_mm=(round(j_pt[0], 4), round(j_pt[1], 4)),
                        width_mm=tr.width_mm,
                        layer=tr.layer,
                        net=tr.net,
                    )
                )
        else:
            cleaned.append(tr)

    return cleaned


@dataclass
class Obstacle:
    """Bounding box obstacle on a copper layer or across all layers."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    layer: str = "ALL"
    net: Optional[str] = None


class AStarPCBRouter:
    """Multi-layer and flexible PCB grid auto-router using obstacle-aware A* search."""

    def __init__(
        self,
        board_bounds: Tuple[float, float, float, float],
        grid_step: float = 0.25,
        layers: Optional[List[str]] = None,
        obstacles: Optional[List[Obstacle]] = None,
        turn_penalty: float = 0.35,
        via_penalty: float = 2.50,
    ) -> None:
        """Initialize the grid router with board boundaries and layer configuration."""
        self.min_x, self.min_y, self.max_x, self.max_y = board_bounds
        self.grid_step = grid_step
        self.layers = layers or ["F.Cu", "B.Cu"]
        self.layer_to_idx = {lay: i for i, lay in enumerate(self.layers)}
        self.idx_to_layer = {i: lay for i, lay in enumerate(self.layers)}
        self.obstacles: List[Obstacle] = []
        self.turn_penalty = turn_penalty
        self.via_penalty = via_penalty
        self.routed_cells: Dict[Tuple[int, int, int], str] = {}
        self.blocked_cells: Dict[Tuple[int, int, str], Optional[str]] = {}
        if obstacles:
            for obs in obstacles:
                self.add_obstacle(obs)

    def add_obstacle(self, obs: Obstacle) -> None:
        """Register an obstacle in the routing domain and index into spatial grid."""
        self.obstacles.append(obs)
        gx_min = math.ceil(obs.min_x / self.grid_step)
        gx_max = math.floor(obs.max_x / self.grid_step)
        if gx_min > gx_max:
            gx_mid = round((obs.min_x + obs.max_x) / (2.0 * self.grid_step))
            gx_min, gx_max = gx_mid, gx_mid

        gy_min = math.ceil(obs.min_y / self.grid_step)
        gy_max = math.floor(obs.max_y / self.grid_step)
        if gy_min > gy_max:
            gy_mid = round((obs.min_y + obs.max_y) / (2.0 * self.grid_step))
            gy_min, gy_max = gy_mid, gy_mid

        layers = self.layers if obs.layer == "ALL" else [obs.layer]
        for lay in layers:
            for gx in range(gx_min, gx_max + 1):
                for gy in range(gy_min, gy_max + 1):
                    key = (gx, gy, lay)
                    existing = self.blocked_cells.get(key)
                    if existing is None or obs.net is not None:
                        self.blocked_cells[key] = obs.net

    def is_cell_blocked(
        self,
        px: float,
        py: float,
        layer_idx: int,
        net_name: str,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
    ) -> bool:
        """Check if physical coordinate (px, py) on layer is blocked by obstacles or existing nets."""
        layer_name = self.idx_to_layer.get(layer_idx, "F.Cu")
        gx = round(px / self.grid_step)
        gy = round(py / self.grid_step)

        # 1. Check routed grid cells from other nets
        cell_net = self.routed_cells.get((gx, gy, layer_idx))
        if cell_net is not None and cell_net != net_name:
            return True

        # 2. Check spatial obstacle map (O(1) dictionary lookup)
        key = (gx, gy, layer_name)
        if key in self.blocked_cells:
            obs_net = self.blocked_cells[key]
            if obs_net == net_name:
                return False
            if obs_net is not None and obs_net != net_name:
                return True
            # Unassigned obstacle (e.g. sensor envelope): allow connecting at start/end
            d_start = math.hypot(px - start_pt[0], py - start_pt[1])
            d_end = math.hypot(px - end_pt[0], py - end_pt[1])
            if d_start < 0.30 or d_end < 0.30:
                return False
            return True

        return False

    def route_net(
        self,
        start_pt: Tuple[float, float],
        start_layer: str,
        end_pt: Tuple[float, float],
        end_layer: str,
        net_name: str,
        width_mm: float = 0.20,
        fillet_radius: float = 0.20,
        junction_points: Optional[Sequence[Tuple[float, float]]] = None,
    ) -> Tuple[List[TraceSegmentModel], List[ViaModel]]:
        """Find an obstacle-avoiding orthogonal path between start and end using A* search."""
        l0 = self.layer_to_idx.get(start_layer, 0)
        l1 = self.layer_to_idx.get(end_layer, 0)
        gx0 = round(start_pt[0] / self.grid_step)
        gy0 = round(start_pt[1] / self.grid_step)
        gx1 = round(end_pt[0] / self.grid_step)
        gy1 = round(end_pt[1] / self.grid_step)

        queue: List[Tuple[float, float, int, int, int, Optional[Tuple[int, int]]]] = []
        h0 = (abs(gx0 - gx1) + abs(gy0 - gy1)) * self.grid_step + abs(l0 - l1) * self.via_penalty
        heapq.heappush(queue, (h0, 0.0, gx0, gy0, l0, None))

        g_scores: Dict[Tuple[int, int, int], float] = {(gx0, gy0, l0): 0.0}
        came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}

        found_state: Optional[Tuple[int, int, int]] = None

        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        max_expansions = 150000
        expansions = 0

        while queue and expansions < max_expansions:
            expansions += 1
            f, curr_g, gx, gy, l_idx, last_dir = heapq.heappop(queue)
            state = (gx, gy, l_idx)

            if curr_g > g_scores.get(state, float("inf")):
                continue

            if gx == gx1 and gy == gy1 and l_idx == l1:
                found_state = state
                break

            # 1. Planar moves on same layer
            for dx, dy in dirs:
                ngx, ngy = gx + dx, gy + dy
                px = ngx * self.grid_step
                py = ngy * self.grid_step

                if not (self.min_x <= px <= self.max_x and self.min_y <= py <= self.max_y):
                    continue

                if self.is_cell_blocked(px, py, l_idx, net_name, start_pt, end_pt):
                    continue

                step_cost = self.grid_step
                if last_dir is not None and (dx, dy) != last_dir:
                    step_cost += self.turn_penalty
                if abs(dx) > 0 and (34.5 <= py <= 41.5 or -39.5 <= py <= -32.5):
                    step_cost += 3.5

                tentative_g = curr_g + step_cost
                next_state = (ngx, ngy, l_idx)

                if tentative_g < g_scores.get(next_state, float("inf")):
                    g_scores[next_state] = tentative_g
                    came_from[next_state] = state
                    h = ((abs(ngx - gx1) + abs(ngy - gy1)) * self.grid_step) * 1.2 + abs(l_idx - l1) * self.via_penalty
                    heapq.heappush(queue, (tentative_g + h, tentative_g, ngx, ngy, l_idx, (dx, dy)))

            # 2. Layer transitions (Vias) - only if multi-layer
            if len(self.layers) > 1:
                for target_l_idx in range(len(self.layers)):
                    if target_l_idx == l_idx:
                        continue

                    px = gx * self.grid_step
                    py = gy * self.grid_step

                    via_r = 0.225
                    blocked = False
                    for obs in self.obstacles:
                        if obs.layer in ("ALL", self.idx_to_layer[l_idx], self.idx_to_layer[target_l_idx]):
                            if obs.net is not None and obs.net == net_name:
                                continue
                            if (obs.min_x - via_r <= px <= obs.max_x + via_r) and (
                                obs.min_y - via_r <= py <= obs.max_y + via_r
                            ):
                                blocked = True
                                break
                    if blocked:
                        continue

                    if self.is_cell_blocked(px, py, l_idx, net_name, start_pt, end_pt) or self.is_cell_blocked(
                        px, py, target_l_idx, net_name, start_pt, end_pt
                    ):
                        continue

                    tentative_g = curr_g + self.via_penalty
                    next_state = (gx, gy, target_l_idx)

                    if tentative_g < g_scores.get(next_state, float("inf")):
                        g_scores[next_state] = tentative_g
                        came_from[next_state] = state
                        h = ((abs(gx - gx1) + abs(gy - gy1)) * self.grid_step) * 1.2 + abs(
                            target_l_idx - l1
                        ) * self.via_penalty
                        heapq.heappush(queue, (tentative_g + h, tentative_g, gx, gy, target_l_idx, last_dir))

        raw_path: List[Tuple[float, float, str]] = []
        if found_state is not None:
            curr = found_state
            while curr in came_from:
                gx, gy, l_idx = curr
                raw_path.append((gx * self.grid_step, gy * self.grid_step, self.idx_to_layer[l_idx]))
                curr = came_from[curr]
            raw_path.append((gx0 * self.grid_step, gy0 * self.grid_step, self.idx_to_layer[l0]))
            raw_path.reverse()
            if raw_path:
                raw_path[0] = (start_pt[0], start_pt[1], start_layer)
                raw_path[-1] = (end_pt[0], end_pt[1], end_layer)
        else:
            raise RuntimeError(
                f"A* router could not find collision-free path for net '{net_name}' "
                f"from ({start_pt[0]:.2f}, {start_pt[1]:.2f}) [{start_layer}] "
                f"to ({end_pt[0]:.2f}, {end_pt[1]:.2f}) [{end_layer}]"
            )

        traces: List[TraceSegmentModel] = []
        vias: List[ViaModel] = []

        if len(raw_path) < 2:
            return traces, vias

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
                vias.append(
                    ViaModel(
                        net=net_name,
                        position_mm=(px, py),
                        pad_diameter_mm=0.45,
                        drill_diameter_mm=0.20,
                        layer_start=min(current_layer, lay),
                        layer_end=max(current_layer, lay),
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
            v_r = v.pad_diameter_mm / 2.0 + 0.22
            self.add_obstacle(
                Obstacle(
                    min_x=v.position_mm[0] - v_r,
                    min_y=v.position_mm[1] - v_r,
                    max_x=v.position_mm[0] + v_r,
                    max_y=v.position_mm[1] + v_r,
                    layer="ALL",
                    net=net_name,
                )
            )
            gx_v = round(v.position_mm[0] / self.grid_step)
            gy_v = round(v.position_mm[1] / self.grid_step)
            for l_i in range(len(self.layers)):
                self.routed_cells[(gx_v, gy_v, l_i)] = net_name

        for tr in traces:
            w_half = tr.width_mm / 2.0 + 0.12
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
            gx_s = round(tr.start_mm[0] / self.grid_step)
            gy_s = round(tr.start_mm[1] / self.grid_step)
            gx_e = round(tr.end_mm[0] / self.grid_step)
            gy_e = round(tr.end_mm[1] / self.grid_step)
            l_idx = self.layer_to_idx.get(tr.layer, 0)
            dist_cells = max(abs(gx_e - gx_s), abs(gy_e - gy_s), 1)
            for s in range(dist_cells + 1):
                t = s / dist_cells
                cgx = round(gx_s + t * (gx_e - gx_s))
                cgy = round(gy_s + t * (gy_e - gy_s))
                self.routed_cells[(cgx, cgy, l_idx)] = net_name

        return traces, vias


class PCBAutoRouter:
    """Automated routing engine generating copper traces and interlayer vias for board nets."""

    def __init__(self, pcb_config: Union[PCBConfig, Dict[str, Any]], wiring: Wiring) -> None:
        """Initialize router with board configuration and electrical netlist."""
        if isinstance(pcb_config, dict):
            self.config = PCBConfig(**pcb_config)
        else:
            self.config = pcb_config
        self.wiring = wiring

    def get_net_trace_width(self, net_name: str) -> float:
        """Resolve trace width for a given net based on net classes and interfaces."""
        net_upper = net_name.upper()

        # Check differential pairs in net classes
        for nc in self.config.net_classes:
            for dp in nc.diff_pairs:
                if net_name in (dp.pos_net, dp.neg_net):
                    return nc.trace_width_mm
            if nc.name.upper() in net_upper:
                return nc.trace_width_mm

        # Check standard interface patterns
        if "PCIE" in net_upper:
            return 0.14
        if "MIPI" in net_upper or "DISP" in net_upper:
            return 0.12
        if "RF" in net_upper or "CPWG" in net_upper:
            return 0.22
        if any(pwr in net_upper for pwr in ("GND", "3V3", "5V", "VCC", "VDD", "VLOAD")):
            return 0.30
        if "PDM" in net_upper or "SPK" in net_upper or "AUDIO" in net_upper or "I2S" in net_upper:
            return 0.14
        if "I2C" in net_upper:
            return 0.14

        return 0.15

    @classmethod
    def save_routing_yaml(
        cls,
        path: Union[str, Path],
        traces: List[TraceSegmentModel],
        vias: List[ViaModel],
    ) -> Path:
        """Persist generated or manually adjusted routing to a project YAML file.

        Args:
            path: Destination file path for routing YAML.
            traces: List of trace segment models to serialize.
            vias: List of via models to serialize.

        Returns:
            Resolved Path of the saved file.
        """
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "traces": [
                {
                    "net": tr.net,
                    "layer": tr.layer,
                    "width_mm": round(tr.width_mm, 4),
                    "start_mm": [round(tr.start_mm[0], 4), round(tr.start_mm[1], 4)],
                    "end_mm": [round(tr.end_mm[0], 4), round(tr.end_mm[1], 4)],
                }
                for tr in traces
            ],
            "vias": [
                {
                    "net": v.net,
                    "position_mm": [round(v.position_mm[0], 4), round(v.position_mm[1], 4)],
                    "pad_diameter_mm": round(v.pad_diameter_mm, 4),
                    "drill_diameter_mm": round(v.drill_diameter_mm, 4),
                    "layer_start": v.layer_start,
                    "layer_end": v.layer_end,
                }
                for v in vias
            ],
        }
        with open(p, "w") as f:
            yaml.dump(data, f, sort_keys=False)
        return p

    @classmethod
    def load_routing_yaml(cls, path: Union[str, Path]) -> Tuple[List[TraceSegmentModel], List[ViaModel]]:
        """Load persisted traces and vias from a project routing YAML file.

        Args:
            path: Source file path for routing YAML.

        Returns:
            Tuple of (traces, vias).
        """
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Routing file not found: {p}")
        with open(p, "r") as f:
            data = yaml.safe_load(f) or {}

        traces = [
            TraceSegmentModel(
                net=item["net"],
                layer=item.get("layer", "F.Cu"),
                width_mm=item.get("width_mm", 0.20),
                start_mm=tuple(item["start_mm"]),
                end_mm=tuple(item["end_mm"]),
            )
            for item in data.get("traces", [])
        ]
        vias = [
            ViaModel(
                net=item.get("net", ""),
                position_mm=tuple(item["position_mm"]),
                pad_diameter_mm=item.get("pad_diameter_mm", 0.45),
                drill_diameter_mm=item.get("drill_diameter_mm", 0.20),
                layer_start=item.get("layer_start", "F.Cu"),
                layer_end=item.get("layer_end", "B.Cu"),
            )
            for item in data.get("vias", [])
        ]
        return traces, vias

    def get_footprints_for_board(self) -> List[Any]:
        """Return footprints belonging specifically to this board target (filtering by shape_ref)."""
        fps = list(self.wiring.footprints) if self.wiring else []
        target_ref = getattr(self.config, "shape_ref", None)
        is_flex = getattr(self.config, "board_type", None) == BoardType.FLEX or getattr(self.config, "is_flex", False)
        if target_ref:
            return [
                fp
                for fp in fps
                if getattr(fp, "shape_ref", None) == target_ref or (not getattr(fp, "shape_ref", None) and not is_flex)
            ]
        return [fp for fp in fps if not is_flex or getattr(fp, "shape_ref", None)]

    @staticmethod
    def get_pin_absolute_position(fp: Any, pin: Any) -> Tuple[float, float]:
        """Compute absolute (x, y) coordinates for a footprint pin taking rotation into account."""
        rot_deg = fp.rotation[2] if hasattr(fp, "rotation") and len(fp.rotation) >= 3 else 0.0
        if abs(rot_deg) > 1e-4:
            rad = math.radians(rot_deg)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            rx = pin.position[0] * cos_r - pin.position[1] * sin_r
            ry = pin.position[0] * sin_r + pin.position[1] * cos_r
            return (fp.position[0] + rx, fp.position[1] + ry)
        return (fp.position[0] + pin.position[0], fp.position[1] + pin.position[1])

    def route_all_nets(
        self,
        exclude_nets: Optional[Set[str]] = None,
        manual_traces: Optional[List[TraceSegmentModel]] = None,
        manual_vias: Optional[List[ViaModel]] = None,
    ) -> Tuple[List[TraceSegmentModel], List[ViaModel]]:
        """Route all electrical nets with collision-free channel allocation and filleted 90-degree corners.

        Supports partial manual routing: Any pre-existing manual traces or vias are preserved,
        and nets fully satisfied by manual routing are automatically skipped.

        Args:
            exclude_nets: Set of net names to skip.
            manual_traces: Optional pre-existing manual trace segments (e.g. BGA fanout escapes).
            manual_vias: Optional pre-existing manual vias.

        Returns:
            Tuple of (generated_trace_segments, generated_interlayer_vias).
        """
        skip_nets = set(exclude_nets or set())
        traces: List[TraceSegmentModel] = list(manual_traces or [])
        vias: List[ViaModel] = list(manual_vias or [])

        # If a net is already fully covered by manual traces, skip it
        manual_net_names = {tr.net for tr in traces}
        for m_net in manual_net_names:
            skip_nets.add(m_net)

        if self.config.dimensions_mm:
            w_board, l_board, _ = self.config.dimensions_mm
        else:
            w_board, l_board = 100.0, 100.0
        half_w = w_board / 2.0
        half_l = l_board / 2.0
        board_bounds = (-half_w, -half_l, half_w, half_l)

        is_flex = getattr(self.config, "board_type", None) == BoardType.FLEX or getattr(self.config, "is_flex", False)
        layers = ["F.Cu"] if is_flex else ["F.Cu", "B.Cu"]

        obstacles: List[Obstacle] = []

        pin_to_net: Dict[Tuple[str, str], str] = {}
        if self.wiring and hasattr(self.wiring, "nets"):
            for net in self.wiring.nets:
                for c_name, p_name in net.pins:
                    pin_to_net[(c_name, p_name)] = net.name

        board_fps = self.get_footprints_for_board()
        for fp in board_fps:
            rot_deg = fp.rotation[2] if hasattr(fp, "rotation") and len(fp.rotation) >= 3 else 0.0
            rad = math.radians(rot_deg)
            cos_r, sin_r = abs(math.cos(rad)), abs(math.sin(rad))

            fp_layer = getattr(fp, "layer", "F.Cu")
            for pin in fp.pins:
                px, py = self.get_pin_absolute_position(fp, pin)
                pw, pl = getattr(pin, "pad_size_mm", (0.5, 0.5))
                eff_w = pw * cos_r + pl * sin_r
                eff_l = pw * sin_r + pl * cos_r
                pin_lay = "ALL" if getattr(pin, "pad_type", "smd") == "thru_hole" else fp_layer
                pad_margin = 0.05
                obstacles.append(
                    Obstacle(
                        min_x=px - eff_w / 2.0 - pad_margin,
                        min_y=py - eff_l / 2.0 - pad_margin,
                        max_x=px + eff_w / 2.0 + pad_margin,
                        max_y=py + eff_l / 2.0 + pad_margin,
                        layer=pin_lay,
                        net=pin_to_net.get((fp.name, pin.name)),
                    )
                )

        for mh in getattr(self.config, "mounting_holes", []):
            mx, my = mh.position_mm
            r = (mh.pad_diameter_mm or mh.drill_diameter_mm) / 2.0
            obstacles.append(
                Obstacle(
                    min_x=mx - r - 0.25,
                    min_y=my - r - 0.25,
                    max_x=mx + r + 0.25,
                    max_y=my + r + 0.25,
                    layer="ALL",
                    net=getattr(mh, "net", None),
                )
            )

        for tp in getattr(self.config, "test_points", []):
            tx, ty = tp.position_mm
            r = tp.pad_diameter_mm / 2.0
            tp_drill = getattr(tp, "drill_diameter_mm", 0) or 0
            obstacles.append(
                Obstacle(
                    min_x=tx - r - 0.22,
                    min_y=ty - r - 0.22,
                    max_x=tx + r + 0.22,
                    max_y=ty + r + 0.22,
                    layer="ALL" if tp_drill > 0 else (tp.layer if hasattr(tp, "layer") else "F.Cu"),
                    net=tp.net,
                )
            )

        target_shape_ref = getattr(self.config, "shape_ref", None)
        for sensor in getattr(self.config, "capacitive_sensors", []):
            sensor_shape = getattr(sensor, "shape_ref", None)
            if target_shape_ref and sensor_shape and sensor_shape != target_shape_ref:
                continue
            if not is_flex and sensor_shape != target_shape_ref:
                continue
            scx, scy = getattr(sensor, "center_mm", (0.0, 0.0))
            sw, sl = getattr(sensor, "area_mm", (10.0, 10.0))
            obstacles.append(
                Obstacle(
                    min_x=scx - sw / 2.0 - 0.20,
                    min_y=scy - sl / 2.0 - 0.20,
                    max_x=scx + sw / 2.0 + 0.20,
                    max_y=scy + sl / 2.0 + 0.20,
                    layer="ALL",
                )
            )

        for tr in traces:
            w_half = tr.width_mm / 2.0 + 0.12
            obstacles.append(
                Obstacle(
                    min_x=min(tr.start_mm[0], tr.end_mm[0]) - w_half,
                    min_y=min(tr.start_mm[1], tr.end_mm[1]) - w_half,
                    max_x=max(tr.start_mm[0], tr.end_mm[0]) + w_half,
                    max_y=max(tr.start_mm[1], tr.end_mm[1]) + w_half,
                    layer=tr.layer,
                    net=tr.net,
                )
            )

        router = AStarPCBRouter(
            board_bounds=board_bounds,
            grid_step=0.25,
            layers=layers,
            obstacles=obstacles,
            turn_penalty=0.50,
            via_penalty=8.00,
        )

        fp_by_name = {fp.name: fp for fp in board_fps}
        tp_by_net: Dict[str, List[TestPointModel]] = {}
        for tp in getattr(self.config, "test_points", []):
            tp_by_net.setdefault(tp.net, []).append(tp)

        sensor_terminals: Dict[str, Tuple[float, float]] = {}
        for s in getattr(self.config, "capacitive_sensors", []):
            sensor_shape = getattr(s, "shape_ref", None)
            if target_shape_ref and sensor_shape and sensor_shape != target_shape_ref:
                continue
            if not is_flex and sensor_shape != target_shape_ref:
                continue
            scx, scy = getattr(s, "center_mm", (0.0, 0.0))
            sw, sl = getattr(s, "area_mm", (10.0, 10.0))
            if s.shape == "interdigital":
                if s.tx_pin:
                    sensor_terminals[s.tx_pin] = (scx - sw / 2.0, scy)
                if s.rx_pin:
                    sensor_terminals[s.rx_pin] = (scx + sw / 2.0, scy)
            else:
                if s.rx_pin:
                    sensor_terminals[s.rx_pin] = (scx, scy - sl / 2.0)

        plane_nets = {cr.net for cr in getattr(self.config, "copper_regions", [])}

        if self.wiring and hasattr(self.wiring, "nets"):
            for net in self.wiring.nets:
                if net.name in skip_nets:
                    continue

                width_mm = self.get_net_trace_width(net.name)

                endpoints: List[Tuple[float, float, str]] = []
                smd_endpoints: List[Tuple[float, float, str]] = []

                for comp_name, pin_name in net.pins:
                    fp = fp_by_name.get(comp_name)
                    if not fp:
                        continue

                    pin_match = next((p for p in fp.pins if p.name == pin_name), None)
                    if pin_match:
                        gx, gy = self.get_pin_absolute_position(fp, pin_match)
                        pad_type = getattr(pin_match, "pad_type", "smd")
                        glay = "F.Cu" if pad_type == "thru_hole" else getattr(fp, "layer", "F.Cu")
                        endpoints.append((gx, gy, glay))
                        if pad_type != "thru_hole":
                            smd_endpoints.append((gx, gy, glay))

                for tp in tp_by_net.get(net.name, []):
                    tp_layer = getattr(tp, "layer", "F.Cu")
                    endpoints.append((tp.position_mm[0], tp.position_mm[1], tp_layer))
                    if getattr(tp, "drill_diameter_mm", 0) <= 0:
                        smd_endpoints.append((tp.position_mm[0], tp.position_mm[1], tp_layer))

                if net.name in sensor_terminals:
                    st_pos = sensor_terminals[net.name]
                    endpoints.append((st_pos[0], st_pos[1], "F.Cu"))

                if not endpoints:
                    continue

                # Plane nets connect via local stitching vias directly to inner copper planes
                if net.name in plane_nets and not is_flex:
                    for px, py, lay in smd_endpoints:
                        # Try offsets around the pad for a stitching via
                        candidate_offsets = [
                            (0.0, 0.75),
                            (0.0, -0.75),
                            (0.75, 0.0),
                            (-0.75, 0.0),
                            (0.75, 0.75),
                            (-0.75, -0.75),
                            (0.75, -0.75),
                            (-0.75, 0.75),
                            (0.0, 1.0),
                            (0.0, -1.0),
                            (1.0, 0.0),
                            (-1.0, 0.0),
                        ]
                        best_vx, best_vy = px, py
                        found_via_spot = False
                        via_pad_r = 0.225 + 0.16
                        for dx, dy in candidate_offsets:
                            cand_x, cand_y = px + dx, py + dy
                            if not (half_w - 1.0 > cand_x > -half_w + 1.0 and half_l - 1.0 > cand_y > -half_l + 1.0):
                                continue
                            conflict = False
                            for obs in router.obstacles:
                                if obs.net is not None and obs.net == net.name:
                                    continue
                                if (obs.min_x - via_pad_r <= cand_x <= obs.max_x + via_pad_r) and (
                                    obs.min_y - via_pad_r <= cand_y <= obs.max_y + via_pad_r
                                ):
                                    conflict = True
                                    break
                            if not conflict:
                                best_vx, best_vy = cand_x, cand_y
                                found_via_spot = True
                                break

                        if found_via_spot:
                            stitching_via = ViaModel(
                                net=net.name,
                                position_mm=(best_vx, best_vy),
                                pad_diameter_mm=0.45,
                                drill_diameter_mm=0.20,
                                layer_start="F.Cu",
                                layer_end="B.Cu",
                            )
                            vias.append(stitching_via)
                            trace_seg = TraceSegmentModel(
                                net=net.name,
                                layer=lay,
                                width_mm=width_mm,
                                start_mm=(px, py),
                                end_mm=(best_vx, best_vy),
                            )
                            traces.append(trace_seg)

                            # Register obstacle for the stitching via and trace
                            v_r = 0.45
                            router.add_obstacle(
                                Obstacle(
                                    min_x=best_vx - v_r,
                                    min_y=best_vy - v_r,
                                    max_x=best_vx + v_r,
                                    max_y=best_vy + v_r,
                                    layer="ALL",
                                    net=net.name,
                                )
                            )
                            w_h = width_mm / 2.0 + 0.12
                            router.add_obstacle(
                                Obstacle(
                                    min_x=min(px, best_vx) - w_h,
                                    min_y=min(py, best_vy) - w_h,
                                    max_x=max(px, best_vx) + w_h,
                                    max_y=max(py, best_vy) + w_h,
                                    layer=lay,
                                    net=net.name,
                                )
                            )
                    continue

                # Signal nets: order endpoints spatially to avoid self-crossing and backtracking
                if len(endpoints) > 2:
                    unvisited = list(endpoints)
                    ordered = [unvisited.pop(0)]
                    while unvisited:
                        curr = ordered[-1]
                        best_idx = 0
                        best_d = float("inf")
                        for idx, pt in enumerate(unvisited):
                            d = math.hypot(pt[0] - curr[0], pt[1] - curr[1]) + (0.0 if pt[2] == curr[2] else 3.0)
                            if d < best_d:
                                best_d = d
                                best_idx = idx
                        ordered.append(unvisited.pop(best_idx))
                    endpoints = ordered

                junction_pts = [(pt[0], pt[1]) for pt in endpoints] if len(endpoints) > 2 else []

                for i in range(len(endpoints) - 1):
                    start_pt = (endpoints[i][0], endpoints[i][1])
                    start_layer = endpoints[i][2]
                    end_pt = (endpoints[i + 1][0], endpoints[i + 1][1])
                    end_layer = endpoints[i + 1][2]

                    if math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1]) < 1e-3 and start_layer == end_layer:
                        continue

                    net_traces, net_vias = router.route_net(
                        start_pt=start_pt,
                        start_layer=start_layer,
                        end_pt=end_pt,
                        end_layer=end_layer,
                        net_name=net.name,
                        width_mm=width_mm,
                        junction_points=junction_pts,
                    )
                    traces.extend(net_traces)
                    vias.extend(net_vias)

        traces = straighten_junction_traces(traces, fillet_radius=0.20)
        return traces, vias
