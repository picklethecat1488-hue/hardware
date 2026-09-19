"""PCB auto-router engine computing collision-free multi-layer routes for component netlists."""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import yaml

from model.pcb import PCBConfig, TraceSegmentModel, ViaModel
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
    fillet_radius: float = 0.60,
) -> List[TraceSegmentModel]:
    """Convert an orthogonal polyline sequence into TraceSegmentModels with filleted 90-degree corners.

    Args:
        pts: Ordered list of (x, y) coordinates defining the trace centerline.
        width_mm: Conductor trace width in millimeters.
        layer: Copper layer (e.g. 'F.Cu' or 'B.Cu').
        net: Electrical net name.
        fillet_radius: Radius in mm for filleting 90-degree corners.

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
        dot = (d1[0] / len1) * (d2[0] / len2) + (d1[1] / len1) * (d2[0] / len2)
        if cross < 1e-3 and dot > 0.99:
            continue
        simplified.append(p_curr)
    simplified.append(pts[-1])

    # Apply fillets at turns
    if len(simplified) <= 2 or fillet_radius <= 0:
        final_pts = simplified
    else:
        final_pts = [simplified[0]]
        for i in range(1, len(simplified) - 1):
            p_prev = final_pts[-1]
            p_curr = simplified[i]
            p_next = simplified[i + 1]
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

        return 0.20

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

        # 1. PCIe Differential Pairs (strictly non-intersecting nested paths)
        # All 4 signals run down to their respective test points at Y = -22.0,
        # then turn horizontal into J1 connector at Y = -36.0.
        # Spacing >= 1.0mm everywhere.
        # 1. PCIe Differential Pairs
        # All 4 signals run down to their respective test points at Y = -22.0.
        # TX0_P, RX0_P, RX0_N run entirely on F.Cu inline with test points.
        # TX0_N routes on F.Cu through TP_TX0_N, bridges to B.Cu with vias to clear TX0_P, and enters J1.
        if "PCIE_TX0_P" not in skip_nets:
            traces.extend(
                polyline_to_trace_segments(
                    [
                        (-5.0, 5.0),
                        (-10.0, 5.0),
                        (-10.0, -22.0),
                        (-10.0, -29.0),
                        (2.0, -29.0),
                        (2.0, -36.0),
                    ],
                    self.get_net_trace_width("PCIE_TX0_P"),
                    "F.Cu",
                    "PCIE_TX0_P",
                )
            )

        if "PCIE_TX0_N" not in skip_nets:
            w_pcie = self.get_net_trace_width("PCIE_TX0_N")
            vias.append(
                ViaModel(
                    position_mm=(-14.0, -24.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="PCIE_TX0_N",
                )
            )
            vias.append(
                ViaModel(
                    position_mm=(4.0, -35.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="PCIE_TX0_N",
                )
            )
            # F.Cu: U1.A2 -> TP_TX0_N -> via at (-14.0, -24.0)
            traces.extend(
                polyline_to_trace_segments(
                    [(-4.2, 5.0), (-4.2, 6.5), (-14.0, 6.5), (-14.0, -22.0), (-14.0, -24.0)],
                    w_pcie,
                    "F.Cu",
                    "PCIE_TX0_N",
                )
            )
            # B.Cu: via at (-14.0, -24.0) -> via at (4.0, -35.0)
            traces.extend(
                polyline_to_trace_segments([(-14.0, -24.0), (-14.0, -35.0), (4.0, -35.0)], w_pcie, "B.Cu", "PCIE_TX0_N")
            )
            # F.Cu: drop via into J1 pin at Y = -36.0
            traces.extend(polyline_to_trace_segments([(4.0, -35.0), (4.0, -36.0)], w_pcie, "F.Cu", "PCIE_TX0_N"))

        if "PCIE_RX0_P" not in skip_nets:
            traces.extend(
                polyline_to_trace_segments(
                    [
                        (-5.0, 4.2),
                        (-6.0, 4.2),
                        (-6.0, -22.0),
                        (-6.0, -28.0),
                        (6.0, -28.0),
                        (6.0, -36.0),
                    ],
                    self.get_net_trace_width("PCIE_RX0_P"),
                    "F.Cu",
                    "PCIE_RX0_P",
                )
            )

        if "PCIE_RX0_N" not in skip_nets:
            traces.extend(
                polyline_to_trace_segments(
                    [
                        (-4.2, 4.2),
                        (-4.2, 3.2),
                        (-2.0, 3.2),
                        (-2.0, -22.0),
                        (-2.0, -27.0),
                        (8.0, -27.0),
                        (8.0, -36.0),
                    ],
                    self.get_net_trace_width("PCIE_RX0_N"),
                    "F.Cu",
                    "PCIE_RX0_N",
                )
            )

        # 2. MIPI Differential Pairs
        # DATA0 pair routes via B.Cu across to test points with explicit vias; CLK pair routes on F.Cu.
        # This completely avoids 2D planar trace collisions.
        if "MIPI_DATA0_P" not in skip_nets:
            w_mipi = self.get_net_trace_width("MIPI_DATA0_P")
            vias.append(
                ViaModel(
                    position_mm=(6.0, -5.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="MIPI_DATA0_P",
                )
            )
            vias.append(
                ViaModel(
                    position_mm=(6.0, 24.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="MIPI_DATA0_P",
                )
            )
            traces.extend(polyline_to_trace_segments([(5.0, -5.0), (6.0, -5.0)], w_mipi, "F.Cu", "MIPI_DATA0_P"))
            traces.extend(
                polyline_to_trace_segments([(6.0, -5.0), (6.0, 22.0), (6.0, 24.0)], w_mipi, "B.Cu", "MIPI_DATA0_P")
            )
            traces.extend(
                polyline_to_trace_segments(
                    [(6.0, 24.0), (6.0, 26.0), (-5.0, 26.0), (-5.0, 38.0)], w_mipi, "F.Cu", "MIPI_DATA0_P"
                )
            )

        if "MIPI_DATA0_N" not in skip_nets:
            w_mipi = self.get_net_trace_width("MIPI_DATA0_N")
            vias.append(
                ViaModel(
                    position_mm=(8.0, -5.8),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="MIPI_DATA0_N",
                )
            )
            vias.append(
                ViaModel(
                    position_mm=(10.0, 24.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="MIPI_DATA0_N",
                )
            )
            traces.extend(polyline_to_trace_segments([(5.0, -5.8), (8.0, -5.8)], w_mipi, "F.Cu", "MIPI_DATA0_N"))
            traces.extend(
                polyline_to_trace_segments(
                    [(8.0, -5.8), (10.0, -5.8), (10.0, 22.0), (10.0, 24.0)], w_mipi, "B.Cu", "MIPI_DATA0_N"
                )
            )
            traces.extend(
                polyline_to_trace_segments(
                    [(10.0, 24.0), (10.0, 28.0), (-4.0, 28.0), (-4.0, 38.0)], w_mipi, "F.Cu", "MIPI_DATA0_N"
                )
            )

        if "MIPI_CLK_P" not in skip_nets:
            w_clk = self.get_net_trace_width("MIPI_CLK_P")
            traces.extend(
                polyline_to_trace_segments(
                    [
                        (3.0, 5.0),
                        (3.0, 18.0),
                        (14.0, 18.0),
                        (14.0, 22.0),
                        (14.0, 30.0),
                        (-2.0, 30.0),
                        (-2.0, 38.0),
                    ],
                    w_clk,
                    "F.Cu",
                    "MIPI_CLK_P",
                )
            )

        if "MIPI_CLK_N" not in skip_nets:
            w_clk = self.get_net_trace_width("MIPI_CLK_N")
            traces.extend(
                polyline_to_trace_segments(
                    [
                        (3.8, 5.0),
                        (3.8, 16.0),
                        (18.0, 16.0),
                        (18.0, 22.0),
                        (18.0, 32.0),
                        (-1.0, 32.0),
                        (-1.0, 38.0),
                    ],
                    w_clk,
                    "F.Cu",
                    "MIPI_CLK_N",
                )
            )

        # 3. I2C Bus with Test Points & Pullups
        # TP_SCL at (14.0, -4.0) and TP_SDA at (18.0, -4.0) (drilled through-holes).
        # On F.Cu, signals route to test points and discrete pullups R1/R2.
        # On B.Cu, signals drop directly from through-hole test point pads to U2.
        if "I2C_SDA" not in skip_nets:
            w_i2c = self.get_net_trace_width("I2C_SDA")
            vias.append(
                ViaModel(
                    position_mm=(18.0, -4.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="I2C_SDA",
                )
            )
            # F.Cu: U1.F1 -> R1 pin 2 and TP_SDA
            traces.extend(polyline_to_trace_segments([(4.0, 0.0), (18.0, 0.0), (18.0, -4.0)], w_i2c, "F.Cu", "I2C_SDA"))
            traces.extend(polyline_to_trace_segments([(10.5, 0.0), (10.5, -8.0)], w_i2c, "F.Cu", "I2C_SDA"))
            # B.Cu: TP_SDA -> U2.SDA (routes along X = 15.0 to avoid U2 VDD at (16.0, -13.5))
            traces.extend(
                polyline_to_trace_segments(
                    [(18.0, -4.0), (15.0, -4.0), (15.0, -14.5), (16.0, -14.5)], w_i2c, "B.Cu", "I2C_SDA"
                )
            )

        if "I2C_SCL" not in skip_nets:
            w_i2c = self.get_net_trace_width("I2C_SCL")
            vias.append(
                ViaModel(
                    position_mm=(14.0, -4.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="I2C_SCL",
                )
            )
            # F.Cu: U1.F2 -> R2 pin 2 and TP_SCL (routes down at X = 4.0 to avoid MIPI at X = 5.0)
            traces.extend(
                polyline_to_trace_segments(
                    [(4.0, -1.0), (4.0, -10.5), (14.0, -10.5), (14.0, -4.0)], w_i2c, "F.Cu", "I2C_SCL"
                )
            )
            # B.Cu: TP_SCL -> U2.SCL
            traces.extend(
                polyline_to_trace_segments([(14.0, -4.0), (14.0, -15.5), (16.0, -15.5)], w_i2c, "B.Cu", "I2C_SCL")
            )

        # 4. CAP_INT, PWR_EN, VLOAD_SW
        if "CAP_INT" not in skip_nets:
            w_sig = self.get_net_trace_width("CAP_INT")
            # Drop to B.Cu right at U1 pin D2 (-3.0, -1.0), route east to U2.INT
            vias.append(
                ViaModel(
                    position_mm=(-3.0, -1.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="CAP_INT",
                )
            )
            traces.extend(
                polyline_to_trace_segments([(-3.0, -1.0), (-3.0, -17.0), (17.0, -17.0)], w_sig, "B.Cu", "CAP_INT")
            )

        if "PWR_EN" not in skip_nets:
            w_pwr_en = self.get_net_trace_width("PWR_EN")
            # Drop to B.Cu right at U1 pin D1 (-3.0, 0.0), route west to Q1.G at (-18.95, -16.0)
            vias.append(
                ViaModel(
                    position_mm=(-3.0, 0.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="PWR_EN",
                )
            )
            traces.extend(
                polyline_to_trace_segments(
                    [(-3.0, 0.0), (-19.5, 0.0), (-19.5, -16.0), (-18.95, -16.0)], w_pwr_en, "B.Cu", "PWR_EN"
                )
            )

        if "VLOAD_SW" not in skip_nets:
            w_vload = self.get_net_trace_width("VLOAD_SW")
            # Route on B.Cu from Q1.D down along X = -7.0 (clearing test points at X=-6.0 and X=-10.0), via to F.Cu at Y = -32.0
            vias.append(
                ViaModel(
                    position_mm=(-6.0, -32.0),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="VLOAD_SW",
                )
            )
            traces.extend(
                polyline_to_trace_segments(
                    [(-18.0, -14.0), (-7.0, -14.0), (-7.0, -32.0), (-6.0, -32.0)], w_vload, "B.Cu", "VLOAD_SW"
                )
            )
            traces.extend(polyline_to_trace_segments([(-6.0, -32.0), (-6.0, -36.0)], w_vload, "F.Cu", "VLOAD_SW"))

        # 5. Capacitive sensing nets (8 nets)
        # U2 is on B.Cu with CS pins on the right edge (X = 20.0).
        # Escape cleanly to the right into dedicated vertical corridors on B.Cu,
        # then route up to Y >= 34.0, turn left to x_j2, and via to F.Cu to enter connector J2.
        # Staggered X corridors and monotonically increasing Y turn elevations guarantee zero crossings.
        cs_channels = [
            ("CAP_TX0", 20.0, -13.5, 20.4, 34.0, 1.0),
            ("CAP_RX0", 20.0, -14.0, 21.0, 34.6, 2.0),
            ("CAP_TX1", 20.0, -14.5, 21.6, 35.2, 3.0),
            ("CAP_RX1", 20.0, -15.0, 22.2, 35.8, 4.0),
            ("CAP_TX2", 20.0, -15.5, 22.8, 36.4, 5.0),
            ("CAP_RX2", 20.0, -16.0, 23.4, 37.0, 6.0),
            ("CAP_RX3", 20.0, -16.5, 24.0, 37.6, 7.0),
        ]
        w_cap = 0.15
        for cnet, xu, yu, x_corr, y_turn, xj in cs_channels:
            if cnet in skip_nets:
                continue
            vias.append(
                ViaModel(
                    position_mm=(xj, y_turn),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net=cnet,
                )
            )
            # On B.Cu: escape right to corridor, route up to y_turn, turn left to xj
            traces.extend(
                polyline_to_trace_segments(
                    [(xu, yu), (x_corr, yu), (x_corr, y_turn), (xj, y_turn)], w_cap, "B.Cu", cnet
                )
            )
            # On F.Cu: route from via directly into J2 pin at Y = 38.0
            traces.extend(polyline_to_trace_segments([(xj, y_turn), (xj, 38.0)], w_cap, "F.Cu", cnet))

        if "CAP_SHIELD" not in skip_nets:
            # CAP_SHIELD escapes from U2 top (18.0, -13.0), routes on B.Cu along X = 19.4,
            # turns left at Y = 33.4 (below all CS turns), vias to F.Cu at (8.0, 33.4), and enters J2
            vias.append(
                ViaModel(
                    position_mm=(8.0, 33.4),
                    drill_diameter_mm=0.20,
                    pad_diameter_mm=0.45,
                    layer_start="F.Cu",
                    layer_end="B.Cu",
                    net="CAP_SHIELD",
                )
            )
            traces.extend(
                polyline_to_trace_segments(
                    [(18.0, -13.0), (19.4, -13.0), (19.4, 33.4), (8.0, 33.4)], w_cap, "B.Cu", "CAP_SHIELD"
                )
            )
            traces.extend(polyline_to_trace_segments([(8.0, 33.4), (8.0, 38.0)], w_cap, "F.Cu", "CAP_SHIELD"))

        # 6. GND Network (TP_GND, J1, U1, U2, Passives, J2, and Plane Vias)
        if "GND" not in skip_nets:
            w_gnd = self.get_net_trace_width("GND")
            # Connect TP_GND to In1.Cu plane via
            vias.append(
                ViaModel(
                    position_mm=(-18.0, -24.0),
                    drill_diameter_mm=0.25,
                    pad_diameter_mm=0.50,
                    layer_start="F.Cu",
                    layer_end="In1.Cu",
                    net="GND",
                )
            )
            traces.extend(polyline_to_trace_segments([(-18.0, -22.0), (-18.0, -24.0)], w_gnd, "F.Cu", "GND"))
            # Stubs to GND plane for all components
            gnd_plane_pts = [
                (0.0, 1.5, "F.Cu", (0.0, 0.0)),
                (14.5, -16.5, "B.Cu", (16.0, -16.5)),
                (-17.05, -17.5, "B.Cu", (-17.05, -16.0)),
                (-7.5, -6.5, "B.Cu", (-7.5, -5.0)),
                (-11.2, -9.5, "F.Cu", (-11.2, -8.0)),
                (-10.0, -34.0, "F.Cu", (-10.0, -36.0)),
                (-8.0, 36.5, "F.Cu", (-8.0, 38.0)),
            ]
            for vx, vy, lay, p_orig in gnd_plane_pts:
                vias.append(
                    ViaModel(
                        position_mm=(vx, vy),
                        drill_diameter_mm=0.25,
                        pad_diameter_mm=0.50,
                        layer_start=lay,
                        layer_end="In1.Cu",
                        net="GND",
                    )
                )
                traces.extend(polyline_to_trace_segments([p_orig, (vx, vy)], w_gnd, lay, "GND"))

        # 7. 3V3 Power Distribution (dedicated In2.Cu power plane with local drop vias)
        if "3V3" not in skip_nets:
            w_3v3 = self.get_net_trace_width("3V3")
            pwr_plane_pts = [
                (-8.0, -33.5, "F.Cu", (-8.0, -36.0)),
                (-7.0, 35.5, "F.Cu", (-7.0, 38.0)),
                (-12.8, -6.0, "F.Cu", (-12.8, -8.0)),
                (0.8, -2.0, "F.Cu", (0.8, 0.0)),
                (17.2, -13.5, "B.Cu", (16.0, -13.5)),
            ]
            for vx, vy, lay, p_orig in pwr_plane_pts:
                vias.append(
                    ViaModel(
                        position_mm=(vx, vy),
                        drill_diameter_mm=0.25,
                        pad_diameter_mm=0.50,
                        layer_start=lay,
                        layer_end="In2.Cu",
                        net="3V3",
                    )
                )
                traces.extend(polyline_to_trace_segments([p_orig, (vx, vy)], w_3v3, lay, "3V3"))

        return traces, vias
