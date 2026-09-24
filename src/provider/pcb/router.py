"""PCB auto-router engine computing collision-free multi-layer routes for component netlists."""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np
import yaml

from model.pcb import BoardType, PCBConfig, TraceSegmentModel, ViaModel, TestPointModel
from model.wiring import Wiring
from provider.geometry_utils import point_in_polygon, dist_point_to_segment

CELL_CONFLICT_MARKER: str = "__CONFLICT__"


def _generate_candidate_via_offsets() -> List[Tuple[float, float]]:
    """Generate radially sorted stitching via candidate offsets using NumPy."""
    radii = [0.40, 0.50, 0.60, 0.75, 1.0, 1.25, 1.50, 1.75, 2.0, 2.25, 2.50]
    angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    circ_pts = [(float(r * np.cos(a)), float(r * np.sin(a))) for r in radii for a in angles]
    knights = [
        (-0.25, -0.50),
        (0.25, -0.50),
        (-0.25, 0.50),
        (0.25, 0.50),
        (-0.20, -0.45),
        (0.20, -0.45),
        (-0.20, 0.45),
        (0.20, 0.45),
        (-0.50, -0.25),
        (0.50, -0.25),
        (-0.50, 0.25),
        (0.50, 0.25),
    ]
    all_pts = np.vstack([np.array(circ_pts), np.array(knights)])
    norms = np.linalg.norm(all_pts, axis=1)
    sorted_pts = all_pts[np.argsort(norms)]
    seen: Set[Tuple[float, float]] = set()
    res: List[Tuple[float, float]] = []
    for p in sorted_pts:
        tup = (round(float(p[0]), 2), round(float(p[1]), 2))
        if tup not in seen:
            seen.add(tup)
            res.append(tup)
    return res


CANDIDATE_VIA_OFFSETS: List[Tuple[float, float]] = _generate_candidate_via_offsets()


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
    """Bounding box or circular obstacle on a copper layer or across all layers."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    layer: str = "ALL"
    net: Optional[str] = None
    is_circle: bool = False
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    is_pin: bool = False

    def copper_dist(self, px: float, py: float) -> float:
        """Compute minimum distance from point (px, py) to the physical copper of this obstacle."""
        if self.is_circle and self.center is not None and self.radius is not None:
            return max(0.0, math.hypot(px - self.center[0], py - self.center[1]) - self.radius)
        edx = max(self.min_x - px, 0.0, px - self.max_x)
        edy = max(self.min_y - py, 0.0, py - self.max_y)
        return math.hypot(edx, edy)


class PCBAutoRouter:
    """Automated routing engine generating copper traces and interlayer vias for board nets."""

    def __init__(
        self,
        pcb_config: Union[PCBConfig, Dict[str, Any]],
        wiring: Wiring,
        backend: str = "jax",
    ) -> None:
        """Initialize router with board configuration and electrical netlist."""
        if isinstance(pcb_config, dict):
            self.config = PCBConfig(**pcb_config)
        else:
            self.config = pcb_config
        self.wiring = wiring
        self.backend = backend

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
            rx = pin.position[0] * cos_r + pin.position[1] * sin_r
            ry = -pin.position[0] * sin_r + pin.position[1] * cos_r
            return (fp.position[0] + rx, fp.position[1] + ry)
        return (fp.position[0] + pin.position[0], fp.position[1] + pin.position[1])

    @staticmethod
    def _compute_net_edges(
        endpoints: List[Tuple[float, float, str]],
        bga_pins: Set[Tuple[float, float]],
        dense_pins: Set[Tuple[float, float]],
    ) -> List[Tuple[Tuple[float, float, str], Tuple[float, float, str]]]:
        """Compute ordered directed routing segments for a net using Prim's Minimum Spanning Tree (MST).

        Args:
            endpoints: List of physical (x, y, layer) terminal coordinates.
            bga_pins: Set of (x, y) coordinates belonging to BGA/VFBGA packages.
            dense_pins: Set of (x, y) coordinates belonging to high-density packages.

        Returns:
            List of (start_node, end_node) directed edges to route.
        """
        if len(endpoints) < 2:
            return []
        if len(endpoints) == 2:
            p0 = (round(endpoints[0][0], 2), round(endpoints[0][1], 2))
            p1 = (round(endpoints[1][0], 2), round(endpoints[1][1], 2))
            if (p1 in bga_pins and p0 not in bga_pins) or (p1 in dense_pins and p0 not in dense_pins):
                return [(endpoints[1], endpoints[0])]
            return [(endpoints[0], endpoints[1])]

        dense_indices = [idx for idx, pt in enumerate(endpoints) if (round(pt[0], 2), round(pt[1], 2)) in bga_pins]
        if not dense_indices:
            dense_indices = [
                idx for idx, pt in enumerate(endpoints) if (round(pt[0], 2), round(pt[1], 2)) in dense_pins
            ]
        start_idx = dense_indices[0] if dense_indices else 0

        visited = [endpoints[start_idx]]
        unvisited = [pt for idx, pt in enumerate(endpoints) if idx != start_idx]
        edges: List[Tuple[Tuple[float, float, str], Tuple[float, float, str]]] = []

        while unvisited:
            best_edge = None
            best_d = float("inf")
            best_u_idx = 0
            for u_idx, u_pt in enumerate(unvisited):
                for v_pt in visited:
                    d = math.hypot(u_pt[0] - v_pt[0], u_pt[1] - v_pt[1]) + (0.0 if u_pt[2] == v_pt[2] else 3.0)
                    if d < best_d:
                        best_d = d
                        best_edge = (v_pt, u_pt)
                        best_u_idx = u_idx
            if best_edge:
                p_v = (round(best_edge[0][0], 2), round(best_edge[0][1], 2))
                p_u = (round(best_edge[1][0], 2), round(best_edge[1][1], 2))
                if (p_u in bga_pins and p_v not in bga_pins) or (p_u in dense_pins and p_v not in dense_pins):
                    edges.append((best_edge[1], best_edge[0]))
                elif len(edges) >= 1 and p_u not in bga_pins and p_u not in dense_pins:
                    edges.append((best_edge[1], best_edge[0]))
                else:
                    edges.append(best_edge)
            visited.append(unvisited.pop(best_u_idx))

        return edges

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
                pad_margin = 0.05 if (min(eff_w, eff_l) <= 0.30 or max(eff_w, eff_l) <= 0.40) else 0.20
                pin_net = pin_to_net.get((fp.name, pin.name)) or "__NO_NET__"
                is_circle = getattr(pin, "pad_shape", "rect") == "circle"
                copper_r = min(eff_w, eff_l) / 2.0 if is_circle else None
                obstacles.append(
                    Obstacle(
                        min_x=px - eff_w / 2.0 - pad_margin,
                        min_y=py - eff_l / 2.0 - pad_margin,
                        max_x=px + eff_w / 2.0 + pad_margin,
                        max_y=py + eff_l / 2.0 + pad_margin,
                        layer=pin_lay,
                        net=pin_net,
                        is_circle=is_circle,
                        center=(px, py) if is_circle else None,
                        radius=copper_r,
                        is_pin=True,
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
                    is_circle=True,
                    center=(mx, my),
                    radius=r,
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
                    is_circle=True,
                    center=(tx, ty),
                    radius=r,
                    is_pin=True,
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
            if getattr(sensor, "shape", None) == "interdigital":
                if getattr(sensor, "tx_pin", None):
                    obstacles.append(
                        Obstacle(
                            min_x=scx - sw / 2.0 - 0.20,
                            min_y=scy - sl / 2.0 - 0.20,
                            max_x=scx,
                            max_y=scy + sl / 2.0 + 0.20,
                            layer="ALL",
                            net=sensor.tx_pin,
                        )
                    )
                if getattr(sensor, "rx_pin", None):
                    obstacles.append(
                        Obstacle(
                            min_x=scx,
                            min_y=scy - sl / 2.0 - 0.20,
                            max_x=scx + sw / 2.0 + 0.20,
                            max_y=scy + sl / 2.0 + 0.20,
                            layer="ALL",
                            net=sensor.rx_pin,
                        )
                    )
            else:
                s_net = (
                    getattr(sensor, "rx_pin", None)
                    or getattr(sensor, "tx_pin", None)
                    or getattr(sensor, "net_name", None)
                )
                obstacles.append(
                    Obstacle(
                        min_x=scx - sw / 2.0 - 0.20,
                        min_y=scy - sl / 2.0 - 0.20,
                        max_x=scx + sw / 2.0 + 0.20,
                        max_y=scy + sl / 2.0 + 0.20,
                        layer="ALL",
                        net=s_net,
                    )
                )

        for tr in traces:
            w_half = max(tr.width_mm / 2.0 + 0.12, 0.21)
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

        dense_regions: List[Tuple[float, float, float, float, str]] = []
        for fp in board_fps:
            pkg = getattr(fp, "package", "")
            if len(fp.pins) >= 16 or any(
                pkg.startswith(p) for p in ("QFN", "BGA", "DFN", "TQFN", "WQFN", "VFBGA", "TDFN", "WSON", "TSSOP")
            ):
                px0 = fp.position[0]
                py0 = fp.position[1]
                xs = [p.position[0] + px0 for p in fp.pins]
                ys = [p.position[1] + py0 for p in fp.pins]
                dense_regions.append(
                    (min(xs) - 1.50, min(ys) - 1.50, max(xs) + 1.50, max(ys) + 1.50, getattr(fp, "layer", "F.Cu"))
                )

        connector_breakout_zones: List[Tuple[float, float, str]] = []
        for fp in board_fps:
            if fp.name.startswith("J") and fp.pins:
                fp_y = [p.position[1] + fp.position[1] for p in fp.pins]
                min_y = min(fp_y) - 3.50
                max_y = max(fp_y) + 3.50
                if abs(min_y - board_bounds[1]) < 12.0 or abs(max_y - board_bounds[3]) < 12.0:
                    connector_breakout_zones.append((min_y, max_y, getattr(fp, "layer", "F.Cu")))

        qfn_keepouts: List[Tuple[float, float, float, float]] = []
        for fp in board_fps:
            pkg = getattr(fp, "package", "")
            if any(
                pkg.startswith(p)
                for p in ("QFN", "DFN", "TQFN", "WQFN", "TDFN", "WSON", "TSSOP", "MSOP", "SOIC", "SSOP")
            ):
                px0 = fp.position[0]
                py0 = fp.position[1]
                xs = [p.position[0] + px0 for p in fp.pins]
                ys = [p.position[1] + py0 for p in fp.pins]
                if xs and ys:
                    qfn_keepouts.append((min(xs) - 1.00, min(ys) - 1.00, max(xs) + 1.00, max(ys) + 1.00))

        from provider.pcb.jax_router import JaxPCBRouter

        router = JaxPCBRouter(
            board_bounds=board_bounds,
            grid_step=0.25,
            layers=layers,
            obstacles=obstacles,
            via_penalty=2.00 if not is_flex else 50.00,
            dense_regions=dense_regions,
            connector_breakout_zones=connector_breakout_zones,
            outline_polygon=getattr(self.config, "outline_polygon", None),
            edge_clearance=0.40 if is_flex else 0.35,
            qfn_keepouts=qfn_keepouts,
        )
        self.router = router

        fp_by_name = {fp.name: fp for fp in board_fps}
        dense_pins: Set[Tuple[float, float]] = set()
        bga_pins: Set[Tuple[float, float]] = set()
        for fp in board_fps:
            if getattr(fp, "package", "").startswith(("BGA", "VFBGA")):
                for pin in fp.pins:
                    gx, gy = self.get_pin_absolute_position(fp, pin)
                    bga_pins.add((round(gx, 2), round(gy, 2)))
            if (
                getattr(fp, "package", "").startswith(("QFN", "BGA", "DFN", "TQFN", "WQFN", "VFBGA"))
                or len(fp.pins) >= 16
            ):
                for pin in fp.pins:
                    gx, gy = self.get_pin_absolute_position(fp, pin)
                    dense_pins.add((round(gx, 2), round(gy, 2)))

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

        all_board_pin_coords: List[Tuple[float, float]] = []
        for fp in board_fps:
            for p in fp.pins:
                all_board_pin_coords.append(self.get_pin_absolute_position(fp, p))

        if self.wiring and hasattr(self.wiring, "nets"):

            def _dynamic_geometric_priority(n: Any) -> Tuple[int, float, float, int]:
                # 1. Copper plane nets route first to establish ground/power referencing
                if n.name in plane_nets:
                    return (-1, 0.0, 0.0, 0)
                # 2. Honor explicit custom priority configured on NetModel
                if getattr(n, "priority", None) is not None:
                    return (0, float(n.priority), 0.0, 0)
                # 3. Dynamic geometric constraint sorting based on degrees of freedom:
                # - Pin Density & Depth (Escape Difficulty): Inner BGA/QFN pins have few escape corridors
                # - Manhattan Distance: Shorter, local point-to-point nets sort ahead of cross-board buses
                # - Slack: Number of terminals (point-to-point before multi-drop)
                pts: List[Tuple[float, float]] = []
                for comp_name, pin_name in n.pins:
                    fp = fp_by_name.get(comp_name)
                    if fp:
                        pm = next((x for x in fp.pins if x.name == pin_name), None)
                        if pm:
                            pts.append(self.get_pin_absolute_position(fp, pm))
                if n.name in sensor_terminals:
                    pts.append(sensor_terminals[n.name])

                if len(pts) < 2:
                    return (4, 0.0, 999.0, 0)

                # Bottleneck pin density (pins within 2.5mm radius)
                densities = [
                    sum(1 for ox, oy in all_board_pin_coords if math.hypot(px - ox, py - oy) <= 2.5) for px, py in pts
                ]
                max_density = max(densities) if densities else 0.0

                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                manhattan_span = (max(xs) - min(xs)) + (max(ys) - min(ys))

                return (2, -float(max_density), float(manhattan_span), len(pts))

            sorted_nets = sorted(self.wiring.nets, key=_dynamic_geometric_priority)
            for net_idx, net in enumerate(sorted_nets):
                if net.name in skip_nets:
                    continue

                print(f"Routing net [{net_idx + 1}/{len(sorted_nets)}] '{net.name}' ...", flush=True)
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
                            smd_endpoints.append((gx, gy, glay, fp, pin_match))

                for tp in tp_by_net.get(net.name, []):
                    tp_layer = getattr(tp, "layer", "F.Cu")
                    endpoints.append((tp.position_mm[0], tp.position_mm[1], tp_layer))
                    if getattr(tp, "drill_diameter_mm", 0) <= 0 or net.name in plane_nets:
                        smd_endpoints.append((tp.position_mm[0], tp.position_mm[1], tp_layer, None, None))

                if net.name in sensor_terminals:
                    st_pos = sensor_terminals[net.name]
                    endpoints.append((st_pos[0], st_pos[1], "F.Cu"))

                if not endpoints:
                    continue

                # Plane nets connect via local stitching vias directly to inner copper planes
                if net.name in plane_nets and not is_flex:
                    for smd_item in smd_endpoints:
                        px, py, lay = smd_item[0], smd_item[1], smd_item[2]
                        fp = smd_item[3] if len(smd_item) > 3 else None
                        pin_match = smd_item[4] if len(smd_item) > 4 else None

                        is_exposed_pad = pin_match is not None and (
                            pin_match.name in ("EP", "PAD", "EXP", "THERMAL", "33")
                            or (
                                getattr(pin_match, "size_mm", (0, 0))[0] >= 1.0
                                and getattr(pin_match, "size_mm", (0, 0))[1] >= 1.0
                            )
                        )
                        in_qfn_keepout = any(
                            kx_min <= px <= kx_max and ky_min <= py <= ky_max
                            for kx_min, ky_min, kx_max, ky_max in getattr(router, "qfn_keepouts", [])
                        )

                        candidate_offsets = (
                            [(0.0, 0.0)] + CANDIDATE_VIA_OFFSETS if is_exposed_pad else list(CANDIDATE_VIA_OFFSETS)
                        )
                        if fp is not None and in_qfn_keepout and not is_exposed_pad:
                            vx = px - fp.position[0]
                            vy = py - fp.position[1]
                            v_norm = math.hypot(vx, vy)
                            if v_norm > 0.01:
                                vx, vy = vx / v_norm, vy / v_norm
                                candidate_offsets = [
                                    off
                                    for off in candidate_offsets
                                    if math.hypot(off[0], off[1]) > 0.01
                                    and (off[0] * vx + off[1] * vy) / math.hypot(off[0], off[1]) >= 0.50
                                ]
                                candidate_offsets.sort(
                                    key=lambda off: (
                                        -((off[0] * vx + off[1] * vy) / math.hypot(off[0], off[1])),
                                        math.hypot(off[0], off[1]),
                                    )
                                )

                        best_vx, best_vy = px, py
                        found_via_spot = False
                        best_offset = (0.0, 0.0)
                        for dx, dy in candidate_offsets:
                            cand_x, cand_y = px + dx, py + dy
                            if not (half_w - 1.0 > cand_x > -half_w + 1.0 and half_l - 1.0 > cand_y > -half_l + 1.0):
                                continue

                            # Perimeter pins of fine-pitch packages must place stitching vias outside breakout keepouts
                            if in_qfn_keepout and not is_exposed_pad:
                                if any(
                                    kx_min <= cand_x <= kx_max and ky_min <= cand_y <= ky_max
                                    for kx_min, ky_min, kx_max, ky_max in getattr(router, "qfn_keepouts", [])
                                ):
                                    continue

                            is_dense = math.hypot(dx, dy) < 0.65 or in_qfn_keepout
                            v_dia = 0.35 if is_dense else 0.45
                            via_pad_r = v_dia / 2.0
                            req_clearance = 0.12 if is_dense else 0.15
                            conflict = False
                            for obs in router.obstacles:
                                if obs.net is not None and obs.net == net.name:
                                    continue
                                if obs.copper_dist(cand_x, cand_y) - via_pad_r < req_clearance:
                                    conflict = True
                                    break
                            if conflict:
                                continue

                            # Check connecting trace clearance if fanout has non-zero length
                            if math.hypot(dx, dy) > 0.01:
                                seg_w = min(width_mm, 0.20) if is_dense else width_mm
                                trace_half_w = seg_w / 2.0
                                trace_conflict = False
                                for obs in router.obstacles:
                                    if obs.net is not None and obs.net == net.name:
                                        continue
                                    if obs.layer in (lay, "ALL"):
                                        if obs.is_circle and obs.center:
                                            d = dist_point_to_segment(obs.center, (px, py), (cand_x, cand_y))
                                            if d - (obs.radius or 0.0) - trace_half_w < req_clearance:
                                                trace_conflict = True
                                                break
                                        else:
                                            m = req_clearance + trace_half_w
                                            if (
                                                min(px, cand_x) - m < obs.max_x
                                                and max(px, cand_x) + m > obs.min_x
                                                and min(py, cand_y) - m < obs.max_y
                                                and max(py, cand_y) + m > obs.min_y
                                            ):
                                                obs_center = (
                                                    (obs.min_x + obs.max_x) / 2.0,
                                                    (obs.min_y + obs.max_y) / 2.0,
                                                )
                                                obs_hw = (obs.max_x - obs.min_x) / 2.0
                                                obs_hl = (obs.max_y - obs.min_y) / 2.0
                                                obs_r = max(obs_hw, obs_hl)
                                                d = dist_point_to_segment(obs_center, (px, py), (cand_x, cand_y))
                                                if d - obs_r - trace_half_w < req_clearance:
                                                    trace_conflict = True
                                                    break
                                if trace_conflict:
                                    continue

                            best_vx, best_vy = cand_x, cand_y
                            best_offset = (dx, dy)
                            found_via_spot = True
                            break

                        if found_via_spot:
                            is_dense = math.hypot(best_offset[0], best_offset[1]) < 0.65 or in_qfn_keepout
                            v_dia = 0.36 if is_dense else 0.45
                            v_drill = 0.16 if is_dense else 0.20
                            stitching_via = ViaModel(
                                net=net.name,
                                position_mm=(best_vx, best_vy),
                                pad_diameter_mm=v_dia,
                                drill_diameter_mm=v_drill,
                                layer_start="F.Cu",
                                layer_end="B.Cu",
                            )
                            vias.append(stitching_via)

                            if math.hypot(best_vx - px, best_vy - py) > 0.01:
                                seg_w = min(width_mm, 0.20) if is_dense else width_mm
                                trace_seg = TraceSegmentModel(
                                    net=net.name,
                                    layer=lay,
                                    width_mm=seg_w,
                                    start_mm=(px, py),
                                    end_mm=(best_vx, best_vy),
                                )
                                traces.append(trace_seg)
                                w_h = max(seg_w / 2.0 + (0.12 if is_dense else 0.15), 0.21)
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

                            # Register obstacle for the stitching via
                            v_r = v_dia / 2.0 + (0.12 if is_dense else 0.15)
                            router.add_obstacle(
                                Obstacle(
                                    min_x=best_vx - v_r,
                                    min_y=best_vy - v_r,
                                    max_x=best_vx + v_r,
                                    max_y=best_vy + v_r,
                                    layer="ALL",
                                    net=net.name,
                                    is_circle=True,
                                    center=(best_vx, best_vy),
                                    radius=v_dia / 2.0,
                                )
                            )
                    continue

                # Signal nets: compute optimal Minimum Spanning Tree (MST) routing edges
                net_edges = self._compute_net_edges(endpoints, bga_pins, dense_pins)
                junction_pts = [(pt[0], pt[1]) for pt in endpoints] if len(endpoints) > 2 else []

                for start_node, end_node in net_edges:
                    start_pt = (start_node[0], start_node[1])
                    start_layer = start_node[2]
                    end_pt = (end_node[0], end_node[1])
                    end_layer = end_node[2]

                    if math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1]) < 1e-3 and start_layer == end_layer:
                        continue

                    try:
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
                    except RuntimeError as initial_err:
                        # Two-stage Rip-up and Reroute:
                        # Identify conflicting previously-routed signal nets in the bounding corridor
                        min_x = min(start_pt[0], end_pt[0]) - 2.5
                        max_x = max(start_pt[0], end_pt[0]) + 2.5
                        min_y = min(start_pt[1], end_pt[1]) - 2.5
                        max_y = max(start_pt[1], end_pt[1]) + 2.5

                        conflicting_nets = set()
                        for (cx_cell, cy_cell, _), cell_net in list(router.routed_cells.items()):
                            rx = router.min_x + cx_cell * router.grid_step
                            ry = router.min_y + cy_cell * router.grid_step
                            if min_x <= rx <= max_x and min_y <= ry <= max_y:
                                if (
                                    cell_net != net.name
                                    and cell_net not in plane_nets
                                    and cell_net != CELL_CONFLICT_MARKER
                                ):
                                    conflicting_nets.add(cell_net)

                        if not conflicting_nets:
                            raise initial_err

                        # Rip up conflicting nets (preserve physical pin obstacles!)
                        traces = [tr for tr in traces if tr.net not in conflicting_nets]
                        vias = [v for v in vias if v.net not in conflicting_nets]

                        router.obstacles = [
                            obs for obs in router.obstacles if obs.is_pin or obs.net not in conflicting_nets
                        ]
                        router.rebuild_spatial_index()
                        router.routed_cells = {
                            k: v for k, v in router.routed_cells.items() if v not in conflicting_nets
                        }

                        try:
                            # Re-attempt routing current net with cleared corridor
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

                            # Reroute the ripped-up nets in their original priority order
                            conflicting_in_order = [
                                n for n in sorted_nets if n.name in conflicting_nets and n.name != net.name
                            ]
                            for c_net in conflicting_in_order:
                                c_width = self.get_net_trace_width(c_net.name)
                                c_endpoints = []
                                for c_comp, c_pin in c_net.pins:
                                    c_fp = fp_by_name.get(c_comp)
                                    if c_fp:
                                        c_pm = next((x for x in c_fp.pins if x.name == c_pin), None)
                                        if c_pm:
                                            c_gx, c_gy = self.get_pin_absolute_position(c_fp, c_pm)
                                            c_pad_type = getattr(c_pm, "pad_type", "smd")
                                            c_glay = (
                                                "F.Cu" if c_pad_type == "thru_hole" else getattr(c_fp, "layer", "F.Cu")
                                            )
                                            c_endpoints.append((c_gx, c_gy, c_glay))
                                for tp in tp_by_net.get(c_net.name, []):
                                    tp_layer = getattr(tp, "layer", "F.Cu")
                                    c_endpoints.append((tp.position_mm[0], tp.position_mm[1], tp_layer))
                                if c_net.name in sensor_terminals:
                                    st_pos = sensor_terminals[c_net.name]
                                    c_endpoints.append((st_pos[0], st_pos[1], "F.Cu"))

                                c_edges = self._compute_net_edges(c_endpoints, bga_pins, dense_pins)
                                if c_edges:
                                    c_junction = [(pt[0], pt[1]) for pt in c_endpoints] if len(c_endpoints) > 2 else []
                                    for c_start_node, c_end_node in c_edges:
                                        c_tr, c_vi = router.route_net(
                                            start_pt=(c_start_node[0], c_start_node[1]),
                                            start_layer=c_start_node[2],
                                            end_pt=(c_end_node[0], c_end_node[1]),
                                            end_layer=c_end_node[2],
                                            net_name=c_net.name,
                                            width_mm=c_width,
                                            junction_points=c_junction,
                                        )
                                        traces.extend(c_tr)
                                        vias.extend(c_vi)
                        except Exception as ripup_err:
                            # If rip-up reroute fails, raise the original descriptive error
                            raise initial_err

        traces = straighten_junction_traces(traces, fillet_radius=0.20)
        return traces, vias
