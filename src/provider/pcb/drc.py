"""Design rule checking (DRC) engine for high-speed differential signals, stackup impedance, and flex rules."""

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Optional, Tuple, Dict, Any
from model.pcb import (
    PCBConfig,
    StackupModel,
    DifferentialPairModel,
    NetClassModel,
    FlexZoneModel,
    LayerType,
)
from provider.geometry_utils import point_in_polygon

_point_in_polygon = point_in_polygon


def _dist_point_to_segment(
    p: Tuple[float, float],
    a: Tuple[float, float],
    b: Tuple[float, float],
) -> float:
    """Compute the shortest Euclidean distance from a 2D point p to line segment (a, b)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / seg_len_sq))
    proj_x = a[0] + t * dx
    proj_y = a[1] + t * dy
    return math.hypot(p[0] - proj_x, p[1] - proj_y)


def _segments_intersect(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    q0: Tuple[float, float],
    q1: Tuple[float, float],
) -> bool:
    """Determine whether two 2D line segments (p0, p1) and (q0, q1) intersect."""

    def ccw(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1 = ccw(p0, p1, q0)
    d2 = ccw(p0, p1, q1)
    d3 = ccw(q0, q1, p0)
    d4 = ccw(q0, q1, p1)

    if ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and (
        (d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9)
    ):
        return True

    # Check collinear or touching endpoints
    for pt, seg_a, seg_b in [(q0, p0, p1), (q1, p0, p1), (p0, q0, q1), (p1, q0, q1)]:
        if _dist_point_to_segment(pt, seg_a, seg_b) < 1e-6:
            return True
    return False


def _dist_segment_to_segment(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    q0: Tuple[float, float],
    q1: Tuple[float, float],
) -> float:
    """Compute the minimum Euclidean distance between two 2D line segments."""
    if _segments_intersect(p0, p1, q0, q1):
        return 0.0
    return min(
        _dist_point_to_segment(p0, q0, q1),
        _dist_point_to_segment(p1, q0, q1),
        _dist_point_to_segment(q0, p0, p1),
        _dist_point_to_segment(q1, p0, p1),
    )


class DRCSeverity(StrEnum):
    """Severity classification for DRC violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DRCViolation:
    """Represents a specific design constraint violation."""

    rule_name: str
    severity: DRCSeverity
    net_or_zone: str
    description: str
    actual_value: Optional[float] = None
    expected_range: Optional[Tuple[float, float]] = None
    location: Optional[Tuple[float, float, float]] = None

    def __str__(self) -> str:
        """Format the violation as a human-readable string."""
        expected = f" (expected {self.expected_range[0]} to {self.expected_range[1]})" if self.expected_range else ""
        actual = f" [actual: {self.actual_value:.4f}]" if self.actual_value is not None else ""
        loc = f" at ({self.location[0]:.2f}, {self.location[1]:.2f})" if self.location else ""
        return f"[{self.severity.upper()}] {self.rule_name} on '{self.net_or_zone}'{loc}: {self.description}{actual}{expected}"


@dataclass
class DRCReport:
    """Collection of DRC violations and overall constraint conformance status."""

    passed: bool
    violations: List[DRCViolation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Count total errors."""
        return sum(1 for v in self.violations if v.severity == DRCSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count total warnings."""
        return sum(1 for v in self.violations if v.severity == DRCSeverity.WARNING)

    def summary(self) -> str:
        """Return a formatted text summary of the DRC audit."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"=== PCB Design Rule Check (DRC) Report: {status} ===",
            f"Total Errors: {self.error_count}, Total Warnings: {self.warning_count}",
        ]
        for v in self.violations:
            lines.append(f"  * {v}")
        return "\n".join(lines)


class PCBDesignRulesChecker:
    """Audits PCB designs against high-speed signal integrity, impedance, and flex mechanical constraints."""

    def __init__(self, config: PCBConfig):
        """Initialize the checker with the board configuration."""
        self.config = config

    def check_all(
        self,
        net_lengths_mm: Optional[Dict[str, float]] = None,
        via_locations: Optional[Dict[str, List[Tuple[float, float, str, str]]]] = None,
        gnd_via_locations: Optional[List[Tuple[float, float]]] = None,
        wiring: Optional[Any] = None,
        outline_polygon: Optional[List[Tuple[float, float]]] = None,
    ) -> DRCReport:
        """Run all DRC checks and return a unified DRCReport.

        Args:
            net_lengths_mm: Optional mapping of net names to routed conductor physical lengths in mm.
            via_locations: Optional mapping of net name to list of (x, y, from_layer, to_layer) vias.
            gnd_via_locations: Optional list of (x, y) coordinates of ground return stitching vias.
            wiring: Optional Wiring model to check component boundary placement and netlist connectivity.
            outline_polygon: Optional list of (x, y) vertices defining board outline from CAD.

        Returns:
            DRCReport detailing all passed/failed constraints.
        """
        violations: List[DRCViolation] = []

        # 1. Stackup impedance verification (differential, CPWG RF, display)
        violations.extend(self.check_impedances())

        # 2. High-speed skew and length matching checks
        if net_lengths_mm:
            violations.extend(self.check_differential_skews(net_lengths_mm))

        # 3. High-speed via count and return path ground stitching checks
        if via_locations:
            violations.extend(self.check_via_rules(via_locations, gnd_via_locations or []))

        # 4. Flexible PCB mechanical bend radius checks
        violations.extend(self.check_flex_rules())

        # 5. Boundary containment check (footprints, traces, vias, test points)
        fps = getattr(wiring, "footprints", []) if wiring else []
        violations.extend(self.check_boundary_containment(fps, outline_polygon))

        # 6. Netlist connectivity validation
        if wiring and hasattr(wiring, "nets"):
            violations.extend(self.check_netlist_connectivity(wiring))

        # 7. Routing completeness validation (traces, airwires, dangling components)
        if wiring:
            violations.extend(self.check_routing_connectivity(wiring))

        # 8. Physical clearance and overlap validation (pads, vias, drill holes)
        violations.extend(self.check_clearances_and_overlaps(wiring))

        passed = not any(v.severity == DRCSeverity.ERROR for v in violations)
        return DRCReport(passed=passed, violations=violations)

    def check_impedances(self) -> List[DRCViolation]:
        """Verify that differential net classes meet their target characteristic impedances."""
        violations = []
        stackup = self.config.stackup

        for net_class in self.config.net_classes:
            w = net_class.trace_width_mm
            w_via = net_class.via_dia_mm

            # Check track width manufacturability (minimum 0.075mm / 3mil standard)
            if w < 0.075:
                violations.append(
                    DRCViolation(
                        rule_name="MIN_TRACE_WIDTH",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=net_class.name,
                        description=f"Trace width {w:.3f}mm is below fab minimum (0.075mm)",
                        actual_value=w,
                        expected_range=(0.075, 5.0),
                    )
                )

            # Check via annular ring manufacturability
            annular_ring = (w_via - net_class.via_drill_mm) / 2.0
            if annular_ring < 0.100:
                violations.append(
                    DRCViolation(
                        rule_name="MIN_ANNULAR_RING",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=net_class.name,
                        description=f"Via annular ring {annular_ring:.3f}mm is below standard minimum (0.100mm)",
                        actual_value=annular_ring,
                        expected_range=(0.100, 1.0),
                    )
                )

            # Audit each differential pair
            for diff_pair in net_class.diff_pairs:
                target_z = diff_pair.target_impedance_ohms
                tol_pct = diff_pair.impedance_tolerance_percent
                z_min = target_z * (1.0 - tol_pct / 100.0)
                z_max = target_z * (1.0 + tol_pct / 100.0)

                # Microstrip surface impedance (L1 / F.Cu)
                copper_t = stackup.copper_layers[0].thickness_mm
                ref_layer, h_dielectric, er = stackup.get_reference_plane(stackup.copper_layers[0].name)
                s = net_class.clearance_mm  # Pair intra-spacing

                z_diff = stackup.calculate_differential_microstrip_impedance(
                    width_mm=w,
                    spacing_mm=s,
                    copper_thickness_mm=copper_t,
                    height_mm=h_dielectric,
                    dielectric_er=er,
                )

                if not (z_min <= z_diff <= z_max):
                    violations.append(
                        DRCViolation(
                            rule_name="DIFF_IMPEDANCE_MISMATCH",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=diff_pair.name,
                            description=(
                                f"Calculated differential impedance {z_diff:.1f}Ω deviates from target "
                                f"{target_z:.1f}Ω ±{tol_pct}% on layer '{stackup.copper_layers[0].name}'"
                            ),
                            actual_value=z_diff,
                            expected_range=(z_min, z_max),
                        )
                    )

            # Audit RF Coplanar Waveguide (CPWG) single-ended 50Ω traces
            if net_class.coplanar_waveguide or net_class.interface_type == "rf":
                target_rf_z = 50.0
                rf_tol_pct = 10.0
                ground_gap = net_class.ground_gap_mm or 0.20
                copper_t = stackup.copper_layers[0].thickness_mm
                ref_layer, h_dielectric, er = stackup.get_reference_plane(stackup.copper_layers[0].name)
                z_cpwg = stackup.calculate_coplanar_waveguide_impedance(
                    width_mm=w,
                    ground_gap_mm=ground_gap,
                    copper_thickness_mm=copper_t,
                    height_mm=h_dielectric,
                    dielectric_er=er,
                )
                z_rf_min = target_rf_z * (1.0 - rf_tol_pct / 100.0)
                z_rf_max = target_rf_z * (1.0 + rf_tol_pct / 100.0)
                if not (z_rf_min <= z_cpwg <= z_rf_max):
                    violations.append(
                        DRCViolation(
                            rule_name="RF_CPWG_IMPEDANCE_MISMATCH",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=net_class.name,
                            description=(
                                f"Calculated coplanar waveguide (CPWG) impedance {z_cpwg:.1f}Ω deviates from target "
                                f"{target_rf_z:.1f}Ω ±{rf_tol_pct}% on layer '{stackup.copper_layers[0].name}'"
                            ),
                            actual_value=z_cpwg,
                            expected_range=(z_rf_min, z_rf_max),
                        )
                    )

            # Audit Display interface target impedance bounds (MIPI/eDP standard 100Ω)
            if net_class.interface_type in ("display", "mipi", "edp"):
                for diff_pair in net_class.diff_pairs:
                    if not (85.0 <= diff_pair.target_impedance_ohms <= 115.0):
                        violations.append(
                            DRCViolation(
                                rule_name="DISPLAY_IMPEDANCE_TARGET_INVALID",
                                severity=DRCSeverity.WARNING,
                                net_or_zone=diff_pair.name,
                                description=(
                                    f"Display interface differential pair target {diff_pair.target_impedance_ohms:.1f}Ω "
                                    f"is outside standard 100Ω (85-115Ω) range"
                                ),
                                actual_value=diff_pair.target_impedance_ohms,
                                expected_range=(85.0, 115.0),
                            )
                        )

        return violations

    def check_differential_skews(self, net_lengths_mm: Dict[str, float]) -> List[DRCViolation]:
        """Verify intra-pair and inter-pair length matching / timing skew constraints."""
        violations = []

        for net_class in self.config.net_classes:
            pair_avg_lengths = []

            for diff_pair in net_class.diff_pairs:
                l_pos = net_lengths_mm.get(diff_pair.pos_net)
                l_neg = net_lengths_mm.get(diff_pair.neg_net)

                if l_pos is not None and l_neg is not None:
                    intra_skew = abs(l_pos - l_neg)
                    if intra_skew > diff_pair.max_intra_pair_skew_mm:
                        violations.append(
                            DRCViolation(
                                rule_name="INTRA_PAIR_SKEW_EXCEEDED",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=diff_pair.name,
                                description=(
                                    f"Intra-pair skew between '{diff_pair.pos_net}' ({l_pos:.3f}mm) and "
                                    f"'{diff_pair.neg_net}' ({l_neg:.3f}mm) exceeds limit "
                                    f"({diff_pair.max_intra_pair_skew_mm}mm)"
                                ),
                                actual_value=intra_skew,
                                expected_range=(0.0, diff_pair.max_intra_pair_skew_mm),
                            )
                        )
                    pair_avg_lengths.append((diff_pair.name, (l_pos + l_neg) / 2.0))

            # Inter-pair / lane-to-lane matching across the net class
            if len(pair_avg_lengths) > 1:
                lengths = [length for _, length in pair_avg_lengths]
                inter_skew = max(lengths) - min(lengths)
                max_inter = net_class.diff_pairs[0].max_inter_pair_skew_mm if net_class.diff_pairs else 1.0
                if inter_skew > max_inter:
                    violations.append(
                        DRCViolation(
                            rule_name="INTER_PAIR_SKEW_EXCEEDED",
                            severity=DRCSeverity.WARNING,
                            net_or_zone=net_class.name,
                            description=(
                                f"Inter-pair lane-to-lane length variance {inter_skew:.3f}mm exceeds limit ({max_inter}mm)"
                            ),
                            actual_value=inter_skew,
                            expected_range=(0.0, max_inter),
                        )
                    )

        return violations

    def check_via_rules(
        self,
        via_locations: Dict[str, List[Tuple[float, float, str, str]]],
        gnd_via_locations: List[Tuple[float, float]],
    ) -> List[DRCViolation]:
        """Verify layer transition via counts and return path ground stitching proximity."""
        violations = []

        for net_class in self.config.net_classes:
            for diff_pair in net_class.diff_pairs:
                for signal_net in (diff_pair.pos_net, diff_pair.neg_net):
                    vias = via_locations.get(signal_net, [])
                    via_count = len(vias)

                    # 1. Via count check
                    if via_count > diff_pair.max_via_count:
                        violations.append(
                            DRCViolation(
                                rule_name="MAX_VIA_COUNT_EXCEEDED",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=signal_net,
                                description=(
                                    f"Net '{signal_net}' has {via_count} vias, exceeding maximum "
                                    f"limit of {diff_pair.max_via_count}"
                                ),
                                actual_value=float(via_count),
                                expected_range=(0.0, float(diff_pair.max_via_count)),
                            )
                        )

                    # 2. Ground return stitching proximity check
                    if net_class.require_ground_stitch_via:
                        for vx, vy, l_from, l_to in vias:
                            if l_from != l_to:
                                # Find nearest ground via
                                min_dist = float("inf")
                                for gx, gy in gnd_via_locations:
                                    dist = math.hypot(vx - gx, vy - gy)
                                    if dist < min_dist:
                                        min_dist = dist

                                if min_dist > net_class.max_stitch_via_distance_mm:
                                    violations.append(
                                        DRCViolation(
                                            rule_name="RETURN_PATH_GND_STITCH_MISSING",
                                            severity=DRCSeverity.ERROR,
                                            net_or_zone=signal_net,
                                            description=(
                                                f"High-speed via transition at ({vx:.2f}, {vy:.2f}) from '{l_from}' "
                                                f"to '{l_to}' has no ground return stitching via within "
                                                f"{net_class.max_stitch_via_distance_mm}mm"
                                            ),
                                            actual_value=min_dist,
                                            expected_range=(0.0, net_class.max_stitch_via_distance_mm),
                                        )
                                    )

        return violations

    def check_flex_rules(self) -> List[DRCViolation]:
        """Verify flexible PCB dynamic and static bend radius mechanical design rules."""
        violations = []

        for zone in self.config.flex_zones:
            # Total flex thickness = polyimide core + 2x coverlay + 2x copper
            t_flex = zone.substrate_thickness_mm + (2.0 * zone.coverlay_thickness_mm) + (2.0 * 0.035)
            # IPC-2223 minimum bend radius: 10x thickness for dynamic flexing, 6x for static bend
            min_recommended_dynamic = 10.0 * t_flex
            min_recommended_static = 6.0 * t_flex

            if zone.min_bend_radius_mm < min_recommended_static:
                violations.append(
                    DRCViolation(
                        rule_name="FLEX_BEND_RADIUS_TOO_TIGHT",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=zone.name,
                        description=(
                            f"Flex zone '{zone.name}' bend radius ({zone.min_bend_radius_mm:.2f}mm) is tighter "
                            f"than IPC-2223 static limit ({min_recommended_static:.2f}mm)"
                        ),
                        actual_value=zone.min_bend_radius_mm,
                        expected_range=(min_recommended_static, 50.0),
                    )
                )
            elif zone.min_bend_radius_mm < min_recommended_dynamic:
                violations.append(
                    DRCViolation(
                        rule_name="FLEX_DYNAMIC_BEND_WARNING",
                        severity=DRCSeverity.WARNING,
                        net_or_zone=zone.name,
                        description=(
                            f"Flex zone '{zone.name}' bend radius ({zone.min_bend_radius_mm:.2f}mm) permits "
                            f"one-time static installation, but is below recommended dynamic flexing radius "
                            f"({min_recommended_dynamic:.2f}mm)"
                        ),
                        actual_value=zone.min_bend_radius_mm,
                        expected_range=(min_recommended_dynamic, 50.0),
                    )
                )

        return violations

    def check_boundary_containment(
        self,
        footprints: Optional[List[Any]] = None,
        outline_polygon: Optional[List[Tuple[float, float]]] = None,
        edge_clearance_mm: float = 0.5,
    ) -> List[DRCViolation]:
        """Verify that all component footprints and pads remain strictly inside the board outline.

        Args:
            footprints: List of component FootprintModel instances.
            outline_polygon: Optional list of (x, y) 2D polygon vertices defining the CAD board outline.
            edge_clearance_mm: Minimum required clearance between component edges and board perimeter.

        Returns:
            List of DRCViolation instances for any boundary clearance violations.
        """
        violations = []
        w_board, l_board, _ = self.config.dimensions_mm
        half_w = w_board / 2.0
        half_l = l_board / 2.0

        for fp in footprints or []:
            fx, fy = fp.position[0], fp.position[1]
            fw, fl = (fp.dimensions[0], fp.dimensions[1]) if hasattr(fp, "dimensions") else (2.0, 2.0)

            if outline_polygon:
                # Check center point and 4 corner points
                corners = [
                    (fx - fw / 2.0, fy - fl / 2.0),
                    (fx + fw / 2.0, fy - fl / 2.0),
                    (fx + fw / 2.0, fy + fl / 2.0),
                    (fx - fw / 2.0, fy + fl / 2.0),
                ]
                for cx, cy in corners:
                    if not _point_in_polygon(cx, cy, outline_polygon):
                        violations.append(
                            DRCViolation(
                                rule_name="BOUNDARY_CONTAINMENT_ERROR",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=fp.name,
                                description=(
                                    f"Component '{fp.name}' extends outside CAD board boundary outline at ({cx:.2f}, {cy:.2f})"
                                ),
                                location=(cx, cy, 0.0),
                            )
                        )
                        break
            else:
                # Bounding box check against board envelope with edge clearance
                min_x = -half_w + edge_clearance_mm
                max_x = half_w - edge_clearance_mm
                min_y = -half_l + edge_clearance_mm
                max_y = half_l - edge_clearance_mm

                fp_min_x = fx - (fw / 2.0)
                fp_max_x = fx + (fw / 2.0)
                fp_min_y = fy - (fl / 2.0)
                fp_max_y = fy + (fl / 2.0)

                if fp_min_x < min_x or fp_max_x > max_x or fp_min_y < min_y or fp_max_y > max_y:
                    violations.append(
                        DRCViolation(
                            rule_name="BOUNDARY_CLEARANCE_VIOLATION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=fp.name,
                            description=(
                                f"Component '{fp.name}' at ({fx:.2f}, {fy:.2f}) with size {fw:.1f}x{fl:.1f}mm violates "
                                f"{edge_clearance_mm}mm edge clearance constraint to board boundary"
                            ),
                            location=(fx, fy, 0.0),
                            expected_range=(edge_clearance_mm, half_w),
                        )
                    )

        # Check trace segments containment
        for tr in self.config.traces:
            for pt in (tr.start_mm, tr.end_mm):
                if outline_polygon:
                    if not _point_in_polygon(pt[0], pt[1], outline_polygon):
                        violations.append(
                            DRCViolation(
                                rule_name="TRACE_OUTSIDE_BOARD_BOUNDARY",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=tr.net,
                                description=(
                                    f"Trace on net '{tr.net}' on layer '{tr.layer}' at ({pt[0]:.2f}, {pt[1]:.2f}) "
                                    f"extends outside CAD board boundary outline"
                                ),
                                location=(pt[0], pt[1], 0.0),
                            )
                        )
                        break
                else:
                    if pt[0] < -half_w or pt[0] > half_w or pt[1] < -half_l or pt[1] > half_l:
                        in_flex = any(
                            getattr(fz, "start_x_mm", -1e9)
                            <= pt[0]
                            <= getattr(fz, "start_x_mm", -1e9) + getattr(fz, "length_mm", 0.0)
                            for fz in self.config.flex_zones
                        )
                        if not in_flex:
                            violations.append(
                                DRCViolation(
                                    rule_name="TRACE_OUTSIDE_BOARD_BOUNDARY",
                                    severity=DRCSeverity.ERROR,
                                    net_or_zone=tr.net,
                                    description=(
                                        f"Trace on net '{tr.net}' on layer '{tr.layer}' at ({pt[0]:.2f}, {pt[1]:.2f}) "
                                        f"extends outside board envelope"
                                    ),
                                    location=(pt[0], pt[1], 0.0),
                                )
                            )
                            break

        # Check via locations containment
        for v in self.config.vias:
            vx, vy = v.position_mm
            if outline_polygon:
                if not _point_in_polygon(vx, vy, outline_polygon):
                    violations.append(
                        DRCViolation(
                            rule_name="VIA_OUTSIDE_BOARD_BOUNDARY",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=v.net,
                            description=f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) is outside CAD board boundary outline",
                            location=(vx, vy, 0.0),
                        )
                    )
            else:
                if vx < -half_w or vx > half_w or vy < -half_l or vy > half_l:
                    violations.append(
                        DRCViolation(
                            rule_name="VIA_OUTSIDE_BOARD_BOUNDARY",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=v.net,
                            description=f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) is outside board envelope",
                            location=(vx, vy, 0.0),
                        )
                    )

        # Check test points containment
        for tp in self.config.test_points:
            tx, ty = tp.position_mm
            if outline_polygon:
                if not _point_in_polygon(tx, ty, outline_polygon):
                    violations.append(
                        DRCViolation(
                            rule_name="TEST_POINT_OUTSIDE_BOARD_BOUNDARY",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=tp.name,
                            description=f"Test point '{tp.name}' at ({tx:.2f}, {ty:.2f}) is outside CAD board boundary outline",
                            location=(tx, ty, 0.0),
                        )
                    )
            else:
                if tx < -half_w or tx > half_w or ty < -half_l or ty > half_l:
                    violations.append(
                        DRCViolation(
                            rule_name="TEST_POINT_OUTSIDE_BOARD_BOUNDARY",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=tp.name,
                            description=f"Test point '{tp.name}' at ({tx:.2f}, {ty:.2f}) is outside board envelope",
                            location=(tx, ty, 0.0),
                        )
                    )

        return violations

    def check_netlist_connectivity(self, wiring: Any) -> List[DRCViolation]:
        """Verify electrical netlist integrity, detecting unrouted nets, floating pins, and short circuits."""
        violations = []
        if not wiring or not hasattr(wiring, "nets"):
            return violations

        pin_to_nets: Dict[Tuple[str, str], List[str]] = {}

        for net in wiring.nets:
            # 1. Single pin or unrouted net check
            if len(net.pins) < 2:
                violations.append(
                    DRCViolation(
                        rule_name="SINGLE_PIN_NET",
                        severity=DRCSeverity.WARNING,
                        net_or_zone=net.name,
                        description=f"Net '{net.name}' has fewer than 2 connected pins ({len(net.pins)})",
                        actual_value=float(len(net.pins)),
                        expected_range=(2.0, 100.0),
                    )
                )

            # Record pin usage for short circuit check
            for comp_name, pin_name in net.pins:
                key = (comp_name, pin_name)
                if key not in pin_to_nets:
                    pin_to_nets[key] = []
                pin_to_nets[key].append(net.name)

        # 2. Short circuit check: multiple nets connected to the exact same component pin
        for (comp_name, pin_name), net_names in pin_to_nets.items():
            unique_nets = set(net_names)
            if len(unique_nets) > 1:
                violations.append(
                    DRCViolation(
                        rule_name="SHORT_CIRCUIT_DETECTED",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=f"{comp_name}.{pin_name}",
                        description=(
                            f"Pin '{pin_name}' on component '{comp_name}' is connected to conflicting nets: "
                            f"{', '.join(sorted(unique_nets))}"
                        ),
                    )
                )

        return violations

    def check_routing_connectivity(self, wiring: Any) -> List[DRCViolation]:
        """Verify routing completeness: ensuring multi-pin nets have traces and no dangling components."""
        violations = []
        if not wiring or not hasattr(wiring, "nets"):
            return violations

        # If board has no traces and no test points defined yet, skip routing enforcement
        if not self.config.traces and not self.config.test_points:
            return violations

        # Track nets that have copper traces
        routed_nets = {tr.net for tr in self.config.traces}

        # Check for unrouted nets (airwires) if routing has been performed
        if self.config.traces:
            for net in wiring.nets:
                if len(net.pins) >= 2:
                    # Disregard plane nets if net is GND or in copper regions
                    is_plane_net = any(cr.net == net.name for cr in self.config.copper_regions)
                    if net.name not in routed_nets and not is_plane_net:
                        violations.append(
                            DRCViolation(
                                rule_name="UNROUTED_NET_AIRWIRE",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=net.name,
                                description=f"Net '{net.name}' with {len(net.pins)} pins has no routed copper traces",
                                actual_value=float(len(net.pins)),
                            )
                        )

        # Check for dangling components (components where all pins are unassigned or disconnected)
        connected_components = {comp_name for net in wiring.nets for comp_name, _ in net.pins}
        for fp in getattr(wiring, "footprints", []):
            if fp.name not in connected_components and getattr(fp, "pins", []):
                violations.append(
                    DRCViolation(
                        rule_name="DANGLING_COMPONENT",
                        severity=DRCSeverity.WARNING,
                        net_or_zone=fp.name,
                        description=f"Component '{fp.name}' ({fp.package}) has no pins assigned to any electrical net",
                        location=(fp.position[0], fp.position[1], 0.0),
                    )
                )

        # Check disconnected test points (airwires on test points)
        for tp in self.config.test_points:
            tp_x, tp_y = tp.position_mm
            tp_r = tp.pad_diameter_mm / 2.0
            connected = False
            for tr in self.config.traces:
                if tr.net == tp.net:
                    dist = _dist_point_to_segment((tp_x, tp_y), tr.start_mm, tr.end_mm)
                    if dist <= tp_r + (tr.width_mm / 2.0) + 0.15:
                        connected = True
                        break
            # Also consider connected if covered by copper region of the same net
            if not connected:
                connected = any(cr.net == tp.net for cr in self.config.copper_regions)
            if not connected:
                violations.append(
                    DRCViolation(
                        rule_name="DISCONNECTED_TEST_POINT_AIRWIRE",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=tp.name,
                        description=(
                            f"Test point '{tp.name}' on net '{tp.net}' at ({tp_x:.2f}, {tp_y:.2f}) "
                            f"is not connected to any routed copper trace"
                        ),
                        location=(tp_x, tp_y, 0.0),
                    )
                )

        return violations

    def check_clearances_and_overlaps(self, wiring: Any) -> List[DRCViolation]:
        """Verify that pads, vias, traces, and drill holes do not overlap or violate clearance rules."""
        violations = []
        holes = self.config.mounting_holes
        vias = self.config.vias
        traces = self.config.traces
        clearance_default = 0.10  # Standard fab minimum clearance

        # 1. Check via to drill hole overlaps
        for mh in holes:
            mh_r = mh.drill_diameter_mm / 2.0
            mh_x, mh_y = mh.position_mm
            for v in vias:
                vx, vy = v.position_mm
                dist = math.hypot(mh_x - vx, mh_y - vy)
                min_clearance = mh_r + (v.pad_diameter_mm / 2.0) + 0.20
                if dist < min_clearance:
                    violations.append(
                        DRCViolation(
                            rule_name="VIA_DRILL_HOLE_COLLISION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{mh.name}<->{v.net}",
                            description=(
                                f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) collides with "
                                f"drill hole '{mh.name}' at ({mh_x:.2f}, {mh_y:.2f}) (dist: {dist:.2f}mm < {min_clearance:.2f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(min_clearance, 100.0),
                            location=(vx, vy, 0.0),
                        )
                    )

        # 2. Check component pads to drill hole overlaps
        if wiring and hasattr(wiring, "footprints"):
            for mh in holes:
                mh_r = mh.drill_diameter_mm / 2.0
                mh_x, mh_y = mh.position_mm
                for fp in wiring.footprints:
                    fx, fy = fp.position[0], fp.position[1]
                    f_diag = (
                        math.hypot(fp.dimensions[0], fp.dimensions[1]) / 2.0 if getattr(fp, "dimensions", None) else 5.0
                    )
                    if math.hypot(mh_x - fx, mh_y - fy) > mh_r + f_diag + 0.2:
                        continue

                    for p in getattr(fp, "pins", []):
                        px = fx + p.position[0]
                        py = fy + p.position[1]
                        dist = math.hypot(mh_x - px, mh_y - py)
                        min_dist = mh_r + 0.30
                        if dist < min_dist:
                            violations.append(
                                DRCViolation(
                                    rule_name="PAD_DRILL_HOLE_COLLISION",
                                    severity=DRCSeverity.ERROR,
                                    net_or_zone=f"{fp.name}.{p.name}",
                                    description=(
                                        f"Pad '{p.name}' on component '{fp.name}' at ({px:.2f}, {py:.2f}) "
                                        f"overlaps drill hole '{mh.name}' at ({mh_x:.2f}, {mh_y:.2f})"
                                    ),
                                    actual_value=dist,
                                    expected_range=(min_dist, 100.0),
                                    location=(px, py, 0.0),
                                )
                            )

        # 3. Check trace-to-trace short circuits and clearance violations
        for i, t1 in enumerate(traces):
            t1_min_x = min(t1.start_mm[0], t1.end_mm[0])
            t1_max_x = max(t1.start_mm[0], t1.end_mm[0])
            t1_min_y = min(t1.start_mm[1], t1.end_mm[1])
            t1_max_y = max(t1.start_mm[1], t1.end_mm[1])
            for j in range(i + 1, len(traces)):
                t2 = traces[j]
                if t1.layer != t2.layer or t1.net == t2.net:
                    continue

                # Bounding box filter
                margin = (t1.width_mm + t2.width_mm) / 2.0 + clearance_default
                if (
                    t1_min_x - margin > max(t2.start_mm[0], t2.end_mm[0])
                    or t1_max_x + margin < min(t2.start_mm[0], t2.end_mm[0])
                    or t1_min_y - margin > max(t2.start_mm[1], t2.end_mm[1])
                    or t1_max_y + margin < min(t2.start_mm[1], t2.end_mm[1])
                ):
                    continue

                dist = _dist_segment_to_segment(t1.start_mm, t1.end_mm, t2.start_mm, t2.end_mm)
                copper_thresh = (t1.width_mm + t2.width_mm) / 2.0
                if dist < copper_thresh - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="TRACE_SHORT_CIRCUIT",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{t1.net}<->{t2.net}",
                            description=(
                                f"Trace on net '{t1.net}' collides with trace on net '{t2.net}' on layer '{t1.layer}' "
                                f"(dist: {dist:.3f}mm < copper threshold {copper_thresh:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(copper_thresh, 100.0),
                            location=(t1.start_mm[0], t1.start_mm[1], 0.0),
                        )
                    )
                elif dist < copper_thresh + clearance_default - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="CLEARANCE_VIOLATION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{t1.net}<->{t2.net}",
                            description=(
                                f"Trace clearance violation between net '{t1.net}' and net '{t2.net}' on layer '{t1.layer}' "
                                f"(dist: {dist:.3f}mm < required {copper_thresh + clearance_default:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(copper_thresh + clearance_default, 100.0),
                            location=(t1.start_mm[0], t1.start_mm[1], 0.0),
                        )
                    )

        # 4. Check via-to-trace short circuits and clearance violations
        for v in vias:
            vx, vy = v.position_mm
            v_r = v.pad_diameter_mm / 2.0
            for tr in traces:
                if v.net == tr.net:
                    continue
                # Check layer overlap
                if tr.layer not in (v.layer_start, v.layer_end) and v.layer_start != "F.Cu":
                    continue
                dist = _dist_point_to_segment((vx, vy), tr.start_mm, tr.end_mm)
                min_copper = v_r + (tr.width_mm / 2.0)
                if dist < min_copper - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="VIA_TRACE_COLLISION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{v.net}<->{tr.net}",
                            description=(
                                f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) collides with trace on net '{tr.net}' "
                                f"on layer '{tr.layer}' (dist: {dist:.3f}mm < {min_copper:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(min_copper, 100.0),
                            location=(vx, vy, 0.0),
                        )
                    )
                elif dist < min_copper + clearance_default - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="CLEARANCE_VIOLATION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{v.net}<->{tr.net}",
                            description=(
                                f"Clearance violation between via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) and trace on net '{tr.net}' "
                                f"(dist: {dist:.3f}mm < required {min_copper + clearance_default:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(min_copper + clearance_default, 100.0),
                            location=(vx, vy, 0.0),
                        )
                    )

        # 5. Check silkscreen-to-pad overlap
        for st in self.config.silkscreen_texts:
            sx, sy = st.position
            for mh in holes:
                dist = math.hypot(sx - mh.position_mm[0], sy - mh.position_mm[1])
                min_dist = (mh.drill_diameter_mm / 2.0) + 0.30
                if dist < min_dist:
                    violations.append(
                        DRCViolation(
                            rule_name="SILKSCREEN_PAD_OVERLAP",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=st.text,
                            description=(
                                f"Silkscreen text '{st.text}' at ({sx:.2f}, {sy:.2f}) overlaps drill hole '{mh.name}'"
                            ),
                            actual_value=dist,
                            expected_range=(min_dist, 100.0),
                            location=(sx, sy, 0.0),
                        )
                    )
            for tp in self.config.test_points:
                dist = math.hypot(sx - tp.position_mm[0], sy - tp.position_mm[1])
                min_dist = (tp.pad_diameter_mm / 2.0) + 0.30
                if dist < min_dist:
                    violations.append(
                        DRCViolation(
                            rule_name="SILKSCREEN_PAD_OVERLAP",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=st.text,
                            description=(
                                f"Silkscreen text '{st.text}' at ({sx:.2f}, {sy:.2f}) overlaps test point pad '{tp.name}'"
                            ),
                            actual_value=dist,
                            expected_range=(min_dist, 100.0),
                            location=(sx, sy, 0.0),
                        )
                    )

        return violations
