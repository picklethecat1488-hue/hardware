"""Design rule checking (DRC) engine for high-speed differential signals, stackup impedance, and flex rules."""

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Optional, Tuple, Dict, Any, Union
from model.pcb import (
    PCBConfig,
    StackupModel,
    DifferentialPairModel,
    NetClassModel,
    FlexZoneModel,
    LayerType,
    BoardType,
    SchematicLayoutModel,
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


def _get_pin_absolute_pos(fp: Any, pin: Any) -> Tuple[float, float]:
    """Compute absolute (x, y) coordinates for a footprint pin taking rotation into account."""
    rot_deg = fp.rotation[2] if hasattr(fp, "rotation") and len(fp.rotation) >= 3 else 0.0
    if abs(rot_deg) > 1e-4:
        rad = math.radians(rot_deg)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        rx = pin.position[0] * cos_r + pin.position[1] * sin_r
        ry = -pin.position[0] * sin_r + pin.position[1] * cos_r
        return (fp.position[0] + rx, fp.position[1] + ry)
    return (fp.position[0] + pin.position[0], fp.position[1] + pin.position[1])


class DRCSeverity(StrEnum):
    """Severity classification for DRC violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DRCRuleName(StrEnum):
    """Enumeration of standard Design Rule Checking (DRC) rule identifiers."""

    MIN_TRACE_WIDTH = "MIN_TRACE_WIDTH"
    MIN_ANNULAR_RING = "MIN_ANNULAR_RING"
    DIFF_IMPEDANCE_MISMATCH = "DIFF_IMPEDANCE_MISMATCH"
    RF_CPWG_IMPEDANCE_MISMATCH = "RF_CPWG_IMPEDANCE_MISMATCH"
    DISPLAY_IMPEDANCE_TARGET_INVALID = "DISPLAY_IMPEDANCE_TARGET_INVALID"
    INTRA_PAIR_SKEW_EXCEEDED = "INTRA_PAIR_SKEW_EXCEEDED"
    DIFFERENTIAL_SKEW_COMPLIANT = "DIFFERENTIAL_SKEW_COMPLIANT"
    INTER_PAIR_SKEW_EXCEEDED = "INTER_PAIR_SKEW_EXCEEDED"
    MAX_VIA_COUNT_EXCEEDED = "MAX_VIA_COUNT_EXCEEDED"
    RETURN_PATH_GND_STITCH_MISSING = "RETURN_PATH_GND_STITCH_MISSING"
    FLEX_BEND_RADIUS_TOO_TIGHT = "FLEX_BEND_RADIUS_TOO_TIGHT"
    FLEX_DYNAMIC_BEND_WARNING = "FLEX_DYNAMIC_BEND_WARNING"
    FLEX_DYNAMIC_BEND_COMPLIANT = "FLEX_DYNAMIC_BEND_COMPLIANT"
    BOUNDARY_CONTAINMENT_ERROR = "BOUNDARY_CONTAINMENT_ERROR"
    BOUNDARY_CLEARANCE_VIOLATION = "BOUNDARY_CLEARANCE_VIOLATION"
    TRACE_OUTSIDE_BOARD_BOUNDARY = "TRACE_OUTSIDE_BOARD_BOUNDARY"
    VIA_OUTSIDE_BOARD_BOUNDARY = "VIA_OUTSIDE_BOARD_BOUNDARY"
    TEST_POINT_OUTSIDE_BOARD_BOUNDARY = "TEST_POINT_OUTSIDE_BOARD_BOUNDARY"
    SINGLE_PIN_NET = "SINGLE_PIN_NET"
    SHORT_CIRCUIT_DETECTED = "SHORT_CIRCUIT_DETECTED"
    UNROUTED_NET_AIRWIRE = "UNROUTED_NET_AIRWIRE"
    DANGLING_COMPONENT = "DANGLING_COMPONENT"
    DISCONNECTED_TEST_POINT_AIRWIRE = "DISCONNECTED_TEST_POINT_AIRWIRE"
    PIN_NOT_CONNECTED_TO_PLANE = "PIN_NOT_CONNECTED_TO_PLANE"
    PIN_NOT_CONNECTED_TO_TRACE = "PIN_NOT_CONNECTED_TO_TRACE"
    NET_ROUTING_INCOMPLETE = "NET_ROUTING_INCOMPLETE"
    DISCONNECTED_TRACE_SEGMENT = "DISCONNECTED_TRACE_SEGMENT"
    DISCONNECTED_VIA = "DISCONNECTED_VIA"
    TEST_POINT_DISCONNECTED = "TEST_POINT_DISCONNECTED"
    MOUNTING_HOLE_DISCONNECTED = "MOUNTING_HOLE_DISCONNECTED"
    VIA_DRILL_HOLE_COLLISION = "VIA_DRILL_HOLE_COLLISION"
    PAD_DRILL_HOLE_COLLISION = "PAD_DRILL_HOLE_COLLISION"
    TRACE_SHORT_CIRCUIT = "TRACE_SHORT_CIRCUIT"
    CLEARANCE_VIOLATION = "CLEARANCE_VIOLATION"
    VIA_TRACE_COLLISION = "VIA_TRACE_COLLISION"
    TEST_POINT_TRACE_COLLISION = "TEST_POINT_TRACE_COLLISION"
    SILKSCREEN_PAD_OVERLAP = "SILKSCREEN_PAD_OVERLAP"
    ANTENNA_TRACE_DETECTED = "ANTENNA_TRACE_DETECTED"
    SCHEMATIC_SYMBOL_OVERLAP = "SCHEMATIC_SYMBOL_OVERLAP"
    SCHEMATIC_TEXT_COLLISION = "SCHEMATIC_TEXT_COLLISION"
    SCHEMATIC_UNCONNECTED_PIN = "SCHEMATIC_UNCONNECTED_PIN"
    SCHEMATIC_NET_ANTENNA = "SCHEMATIC_NET_ANTENNA"
    SCHEMATIC_PAGE_TRANSITION_MISSING = "SCHEMATIC_PAGE_TRANSITION_MISSING"
    SCHEMATIC_DANGLING_COMPONENT = "SCHEMATIC_DANGLING_COMPONENT"
    SCHEMATIC_PAGE_BOUNDARY_EXCEEDED = "SCHEMATIC_PAGE_BOUNDARY_EXCEEDED"


@dataclass
class DRCViolation:
    """Represents a specific design constraint violation."""

    rule_name: Union[DRCRuleName, str]
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


class DRCViolationCollection(List[DRCViolation]):
    """Custom collection for DRC violations providing structured helper factory methods."""

    def add_violation(
        self,
        rule_name: Union[DRCRuleName, str],
        severity: DRCSeverity,
        net_or_zone: str,
        description: str,
        actual_value: Optional[float] = None,
        expected_range: Optional[Tuple[float, float]] = None,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append a DRC violation to the collection."""
        v = DRCViolation(
            rule_name=rule_name,
            severity=severity,
            net_or_zone=net_or_zone,
            description=description,
            actual_value=actual_value,
            expected_range=expected_range,
            location=location,
        )
        self.append(v)
        return v

    def add_error(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        description: str,
        actual_value: Optional[float] = None,
        expected_range: Optional[Tuple[float, float]] = None,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append an ERROR DRC violation."""
        return self.add_violation(
            rule_name=rule_name,
            severity=DRCSeverity.ERROR,
            net_or_zone=net_or_zone,
            description=description,
            actual_value=actual_value,
            expected_range=expected_range,
            location=location,
        )

    def add_warning(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        description: str,
        actual_value: Optional[float] = None,
        expected_range: Optional[Tuple[float, float]] = None,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append a WARNING DRC violation."""
        return self.add_violation(
            rule_name=rule_name,
            severity=DRCSeverity.WARNING,
            net_or_zone=net_or_zone,
            description=description,
            actual_value=actual_value,
            expected_range=expected_range,
            location=location,
        )

    def add_info(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        description: str,
        actual_value: Optional[float] = None,
        expected_range: Optional[Tuple[float, float]] = None,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append an INFO DRC violation."""
        return self.add_violation(
            rule_name=rule_name,
            severity=DRCSeverity.INFO,
            net_or_zone=net_or_zone,
            description=description,
            actual_value=actual_value,
            expected_range=expected_range,
            location=location,
        )

    def add_boundary_violation(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        element_name: str,
        x: float,
        y: float,
        is_outline: bool = False,
    ) -> DRCViolation:
        """Construct and append a boundary containment violation."""
        boundary_type = "CAD board boundary outline" if is_outline else "board envelope"
        description = f"{element_name} at ({x:.2f}, {y:.2f}) is outside {boundary_type}"
        return self.add_error(
            rule_name=rule_name,
            net_or_zone=net_or_zone,
            description=description,
            location=(x, y, 0.0),
        )

    def add_clearance_violation(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        description: str,
        actual_distance: float,
        min_clearance: float,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append a clearance distance violation."""
        return self.add_error(
            rule_name=rule_name,
            net_or_zone=net_or_zone,
            description=description,
            actual_value=actual_distance,
            expected_range=(min_clearance, float("inf")),
            location=location,
        )

    def add_continuity_violation(
        self,
        rule_name: Union[DRCRuleName, str],
        net_or_zone: str,
        description: str,
        severity: DRCSeverity = DRCSeverity.ERROR,
        location: Optional[Tuple[float, float, float]] = None,
    ) -> DRCViolation:
        """Construct and append a netlist or routing continuity violation."""
        return self.add_violation(
            rule_name=rule_name,
            severity=severity,
            net_or_zone=net_or_zone,
            description=description,
            location=location,
        )

    @property
    def errors(self) -> List[DRCViolation]:
        """Return all violations with ERROR severity."""
        return [v for v in self if v.severity == DRCSeverity.ERROR]

    @property
    def warnings(self) -> List[DRCViolation]:
        """Return all violations with WARNING severity."""
        return [v for v in self if v.severity == DRCSeverity.WARNING]

    @property
    def infos(self) -> List[DRCViolation]:
        """Return all violations with INFO severity."""
        return [v for v in self if v.severity == DRCSeverity.INFO]


@dataclass
class DRCReport:
    """Collection of DRC violations and overall constraint conformance status."""

    passed: bool
    violations: DRCViolationCollection = field(default_factory=DRCViolationCollection)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Count total errors."""
        return sum(1 for v in self.violations if v.severity == DRCSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count total warnings."""
        return sum(1 for v in self.violations if v.severity == DRCSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Count total informational notifications."""
        return sum(1 for v in self.violations if v.severity == DRCSeverity.INFO)

    def summary(self) -> str:
        """Return a formatted text summary of the DRC audit."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"=== PCB Design Rule Check (DRC) Report: {status} ===",
            f"Total Errors: {self.error_count}, Total Warnings: {self.warning_count}, Total Info: {self.info_count}",
        ]
        for v in self.violations:
            lines.append(f"  * {v}")
        return "\n".join(lines)


class PCBDesignRulesChecker:
    """Audits PCB designs against high-speed signal integrity, impedance, and flex mechanical constraints."""

    def __init__(self, config: PCBConfig):
        """Initialize the checker with the board configuration."""
        self.config = config
        self.is_flex = (
            (getattr(self.config, "name", "") == "flex_tail")
            or (getattr(self.config, "shape_ref", "") == "flex_tail")
            or (getattr(self.config, "board_type", None) == BoardType.FLEX)
        )

    def get_footprints_for_board(self, wiring: Any) -> List[Any]:
        """Filter footprints belonging specifically to this board target."""
        if not wiring or not hasattr(wiring, "footprints"):
            return []
        fps = list(wiring.footprints)
        target_ref = getattr(self.config, "shape_ref", None)
        if target_ref:
            return [
                fp
                for fp in fps
                if getattr(fp, "shape_ref", None) == target_ref
                or (not getattr(fp, "shape_ref", None) and not self.is_flex)
            ]
        return [fp for fp in fps if not self.is_flex or getattr(fp, "shape_ref", None)]

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
        violations = DRCViolationCollection()

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
        fps = self.get_footprints_for_board(wiring)
        violations.extend(self.check_boundary_containment(fps, outline_polygon))

        # 6. Netlist connectivity validation
        if wiring and hasattr(wiring, "nets"):
            violations.extend(self.check_netlist_connectivity(wiring))

        # 7. Routing completeness validation (traces, airwires, dangling components)
        if wiring:
            violations.extend(self.check_routing_connectivity(wiring))

        # 8. Physical clearance and overlap validation (pads, vias, drill holes)
        violations.extend(self.check_clearances_and_overlaps(wiring))

        # 9. Antenna and dangling trace validation
        if wiring:
            violations.extend(self.check_antennae(wiring))

        # 10. Schematic design rule checks (symbol overlaps, dangling components, page transitions, antennas)
        if self.config.schematic_sheets and wiring:
            violations.extend(self.check_schematic(wiring))

        # 11. Via boundary and multi-layer connectivity checks
        violations.extend(self.check_via_connectivity(wiring))

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
                    else:
                        violations.append(
                            DRCViolation(
                                rule_name="DIFFERENTIAL_SKEW_COMPLIANT",
                                severity=DRCSeverity.INFO,
                                net_or_zone=diff_pair.name,
                                description=(
                                    f"Intra-pair skew between '{diff_pair.pos_net}' ({l_pos:.3f}mm) and "
                                    f"'{diff_pair.neg_net}' ({l_neg:.3f}mm) is compliant "
                                    f"({intra_skew:.3f}mm <= {diff_pair.max_intra_pair_skew_mm}mm)"
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

    def check_via_connectivity(self, wiring: Optional[Any] = None) -> List[DRCViolation]:
        """Verify that every via is placed on the board envelope, belongs to an active net, and connects across layers."""
        violations = []
        if not self.config.vias:
            return violations

        board_fps = self.get_footprints_for_board(wiring) if wiring else []
        carrier_fps = {fp.name: fp for fp in board_fps}
        plane_nets = {cr.net for cr in self.config.copper_regions} if self.config.copper_regions else set()

        board_nets = set(plane_nets)
        if wiring and hasattr(wiring, "nets"):
            for net in wiring.nets:
                if any(comp in carrier_fps for comp, _ in net.pins):
                    board_nets.add(net.name)
        for tp in self.config.test_points:
            if tp.net:
                board_nets.add(tp.net)

        traces = self.config.traces
        outline_poly = getattr(self.config, "outline_polygon", None)
        w_board, l_board, _ = self.config.dimensions_mm
        half_w = w_board / 2.0
        half_l = l_board / 2.0

        for v in self.config.vias:
            vx, vy = v.position_mm

            # 1. Check board envelope containment
            if outline_poly:
                if not _point_in_polygon(vx, vy, outline_poly):
                    violations.append(
                        DRCViolation(
                            rule_name="VIA_OUTSIDE_BOARD_BOUNDARY",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=v.net,
                            description=f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) is located outside board envelope",
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
                            description=f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) is outside board perimeter bounds",
                            location=(vx, vy, 0.0),
                        )
                    )

            # 2. Check net validity on this board
            if board_nets and v.net not in board_nets:
                violations.append(
                    DRCViolation(
                        rule_name="DISCONNECTED_VIA",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=v.net,
                        description=(
                            f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) belongs to a net not present on "
                            f"board '{self.config.name}'"
                        ),
                        location=(vx, vy, 0.0),
                    )
                )
                continue

            # 3. Check connectivity across layers
            is_plane = v.net in plane_nets
            connected_layers = set()
            if is_plane:
                connected_layers.add("In1.Cu")  # Inner copper plane

            v_pad_r = v.pad_diameter_mm / 2.0
            for tr in traces:
                if tr.net == v.net:
                    dist = _dist_point_to_segment((vx, vy), tr.start_mm, tr.end_mm)
                    if dist <= v_pad_r + tr.width_mm / 2.0 + 0.15:
                        connected_layers.add(tr.layer)

            for fp in board_fps:
                for p in getattr(fp, "pins", []):
                    px, py = _get_pin_absolute_pos(fp, p)
                    p_s = getattr(p, "pad_size_mm", (0.8, 0.8))
                    p_r = max(p_s) / 2.0
                    if math.hypot(vx - px, vy - py) <= v_pad_r + p_r + 0.15:
                        p_lay = getattr(fp, "layer", "F.Cu")
                        connected_layers.add(p_lay)

            if len(connected_layers) < 2:
                violations.append(
                    DRCViolation(
                        rule_name="DISCONNECTED_VIA",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=v.net,
                        description=(
                            f"Via on net '{v.net}' at ({vx:.2f}, {vy:.2f}) is not connected across multiple layers "
                            f"(only connects on layers: {list(connected_layers) or 'none'})"
                        ),
                        location=(vx, vy, 0.0),
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
            else:
                violations.append(
                    DRCViolation(
                        rule_name="FLEX_DYNAMIC_BEND_COMPLIANT",
                        severity=DRCSeverity.INFO,
                        net_or_zone=zone.name,
                        description=(
                            f"Flex zone '{zone.name}' bend radius ({zone.min_bend_radius_mm:.2f}mm) "
                            f"complies with IPC-2223 dynamic flexing guidelines (>={min_recommended_dynamic:.2f}mm)"
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
        violations = DRCViolationCollection()
        outline_polygon = outline_polygon or getattr(self.config, "outline_polygon", None)
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
                        violations.add_boundary_violation(
                            "BOUNDARY_CONTAINMENT_ERROR",
                            fp.name,
                            f"Component '{fp.name}'",
                            cx,
                            cy,
                            is_outline=True,
                        )
                        break
            else:
                # Bounding box check against board envelope with edge clearance
                min_x = -half_w + edge_clearance_mm
                max_x = half_w - edge_clearance_mm
                min_y = -half_l + edge_clearance_mm
                max_y = half_l - edge_clearance_mm

                # Edge connectors (USB receptacles, FPC connectors, card edge) are mounted at the perimeter
                pkg = getattr(fp, "package", "").upper()
                fp_n = fp.name.upper()
                is_conn = fp_n.startswith("J") or fp_n.startswith("P") or fp_n.startswith("CONN")
                is_edge_connector = (
                    any(tok in pkg for tok in ("USB", "FPC", "M.2", "CARD-EDGE", "EDGE_CONNECTOR", "JACK"))
                    or (is_conn and any(tok in fp_n for tok in ("USB", "FPC", "EDGE")))
                    or getattr(fp, "edge_connector", False)
                )
                if is_edge_connector and abs(fx) <= half_w and abs(fy) <= half_l:
                    continue

                fp_min_x = fx - (fw / 2.0)
                fp_max_x = fx + (fw / 2.0)
                fp_min_y = fy - (fl / 2.0)
                fp_max_y = fy + (fl / 2.0)

                if fp_min_x < min_x or fp_max_x > max_x or fp_min_y < min_y or fp_max_y > max_y:
                    violations.add_clearance_violation(
                        "BOUNDARY_CLEARANCE_VIOLATION",
                        fp.name,
                        (
                            f"Component '{fp.name}' at ({fx:.2f}, {fy:.2f}) with size {fw:.1f}x{fl:.1f}mm violates "
                            f"{edge_clearance_mm}mm edge clearance constraint to board boundary"
                        ),
                        actual_distance=min(half_w - abs(fx), half_l - abs(fy)),
                        min_clearance=edge_clearance_mm,
                        location=(fx, fy, 0.0),
                    )

        # Check trace segments containment
        for tr in self.config.traces:
            for pt in (tr.start_mm, tr.end_mm):
                if outline_polygon:
                    if not _point_in_polygon(pt[0], pt[1], outline_polygon):
                        violations.add_boundary_violation(
                            "TRACE_OUTSIDE_BOARD_BOUNDARY",
                            tr.net,
                            f"Trace on net '{tr.net}' on layer '{tr.layer}'",
                            pt[0],
                            pt[1],
                            is_outline=True,
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
                            violations.add_boundary_violation(
                                "TRACE_OUTSIDE_BOARD_BOUNDARY",
                                tr.net,
                                f"Trace on net '{tr.net}' on layer '{tr.layer}'",
                                pt[0],
                                pt[1],
                                is_outline=False,
                            )
                            break

        # Check via locations containment
        for v in self.config.vias:
            vx, vy = v.position_mm
            if outline_polygon:
                if not _point_in_polygon(vx, vy, outline_polygon):
                    violations.add_boundary_violation(
                        "VIA_OUTSIDE_BOARD_BOUNDARY",
                        v.net,
                        f"Via on net '{v.net}'",
                        vx,
                        vy,
                        is_outline=True,
                    )
            else:
                if vx < -half_w or vx > half_w or vy < -half_l or vy > half_l:
                    violations.add_boundary_violation(
                        "VIA_OUTSIDE_BOARD_BOUNDARY",
                        v.net,
                        f"Via on net '{v.net}'",
                        vx,
                        vy,
                        is_outline=False,
                    )

        # Check test points containment
        for tp in self.config.test_points:
            tx, ty = tp.position_mm
            if outline_polygon:
                if not _point_in_polygon(tx, ty, outline_polygon):
                    violations.add_boundary_violation(
                        "TEST_POINT_OUTSIDE_BOARD_BOUNDARY",
                        tp.name,
                        f"Test point '{tp.name}'",
                        tx,
                        ty,
                        is_outline=True,
                    )
            else:
                if tx < -half_w or tx > half_w or ty < -half_l or ty > half_l:
                    violations.add_boundary_violation(
                        "TEST_POINT_OUTSIDE_BOARD_BOUNDARY",
                        tp.name,
                        f"Test point '{tp.name}'",
                        tx,
                        ty,
                        is_outline=False,
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
        board_footprints = self.get_footprints_for_board(wiring)
        board_fp_names = {fp.name for fp in board_footprints}
        board_sensor_nets = {
            s.rx_pin for s in getattr(self.config, "capacitive_sensors", []) if getattr(s, "rx_pin", None)
        } | {s.tx_pin for s in getattr(self.config, "capacitive_sensors", []) if getattr(s, "tx_pin", None)}

        # Check for unrouted nets (airwires) if routing has been performed
        if self.config.traces:
            for net in wiring.nets:
                # Count terminals belonging specifically to this board target
                board_pins_count = sum(1 for c_name, _ in net.pins if c_name in board_fp_names)
                if net.name in board_sensor_nets:
                    board_pins_count += 1

                if board_pins_count >= 2:
                    # Disregard plane nets if net is GND or in copper regions
                    is_plane_net = any(cr.net == net.name for cr in self.config.copper_regions)
                    if net.name not in routed_nets and not is_plane_net:
                        violations.append(
                            DRCViolation(
                                rule_name="UNROUTED_NET_AIRWIRE",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=net.name,
                                description=f"Net '{net.name}' with {board_pins_count} pins has no routed copper traces",
                                actual_value=float(board_pins_count),
                            )
                        )

        # Check for dangling components (components where all pins are unassigned or disconnected)
        connected_components = {comp_name for net in wiring.nets for comp_name, _ in net.pins}
        board_footprints = self.get_footprints_for_board(wiring)
        for fp in board_footprints:
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

        # 4. Check end-to-end net continuity between source and target component pins
        violations.extend(self.check_net_continuity(wiring))

        return violations

    def check_net_continuity(self, wiring: Any) -> List[DRCViolation]:
        """Verify that all net segments form an unbroken electrical path between source and target component pins."""
        violations: List[DRCViolation] = []
        if not wiring or not hasattr(wiring, "nets") or not self.config.traces:
            return violations

        board_footprints = self.get_footprints_for_board(wiring)
        carrier_fps = {fp.name: fp for fp in board_footprints}

        traces = self.config.traces
        vias = self.config.vias
        copper_regions = self.config.copper_regions

        class _UnionFind:
            def __init__(self) -> None:
                self.parent: Dict[Any, Any] = {}

            def find(self, i: Any) -> Any:
                if i not in self.parent:
                    self.parent[i] = i
                if self.parent[i] != i:
                    self.parent[i] = self.find(self.parent[i])
                return self.parent[i]

            def union(self, i: Any, j: Any) -> None:
                ri, rj = self.find(i), self.find(j)
                if ri != rj:
                    self.parent[ri] = rj

        for net in wiring.nets:
            pins_on_board = [(comp, pin) for comp, pin in net.pins if comp in carrier_fps]
            if len(pins_on_board) < 2:
                continue

            # Check if net is distributed via copper plane (e.g. GND, 3V3 inner planes)
            is_plane_net = any(cr.net == net.name for cr in copper_regions)
            if is_plane_net:
                for comp, pin in pins_on_board:
                    fp = carrier_fps[comp]
                    p_obj = next((p for p in getattr(fp, "pins", []) if p.name == pin), None)
                    if not p_obj:
                        continue
                    px, py = _get_pin_absolute_pos(fp, p_obj)
                    pad_type = getattr(p_obj, "pad_type", "smd")
                    pad_s = getattr(p_obj, "pad_size_mm", (0.8, 0.8))
                    pad_r = max(pad_s) / 2.0

                    connected = pad_type == "thru_hole"
                    if not connected:
                        for v in vias:
                            if v.net == net.name:
                                if (
                                    math.hypot(px - v.position_mm[0], py - v.position_mm[1])
                                    <= pad_r + v.pad_diameter_mm / 2.0 + 0.50
                                ):
                                    connected = True
                                    break
                    if not connected:
                        for tr in traces:
                            if tr.net == net.name:
                                if (
                                    _dist_point_to_segment((px, py), tr.start_mm, tr.end_mm)
                                    <= pad_r + tr.width_mm / 2.0 + 0.35
                                ):
                                    connected = True
                                    break
                    if not connected:
                        violations.append(
                            DRCViolation(
                                rule_name="PIN_NOT_CONNECTED_TO_PLANE",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=f"{comp}.{pin}",
                                description=f"Pin '{comp}.{pin}' on plane net '{net.name}' has no via or trace connection to the copper plane",
                                location=(px, py, 0.0),
                            )
                        )
                continue

            net_tr = [tr for tr in traces if tr.net == net.name]
            net_v = [v for v in vias if v.net == net.name]
            net_tp = [tp for tp in self.config.test_points if tp.net == net.name]
            net_mh = [mh for mh in self.config.mounting_holes if mh.plated and mh.net == net.name]

            uf = _UnionFind()

            # 1. Add trace segment internal connections
            for tr in net_tr:
                p1 = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                p2 = (round(tr.end_mm[0], 2), round(tr.end_mm[1], 2), tr.layer)
                uf.union(p1, p2)

            # 2. Add via connections across layers
            for v in net_v:
                p_f = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "F.Cu")
                p_b = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "B.Cu")
                uf.union(p_f, p_b)

            # 3. Connect co-located trace vertices, vias, and T-junctions
            all_nodes = list(uf.parent.keys())
            for n in all_nodes:
                for tr in net_tr:
                    if tr.layer == n[2]:
                        d = _dist_point_to_segment((n[0], n[1]), tr.start_mm, tr.end_mm)
                        if d <= tr.width_mm / 2.0 + 0.10:
                            tr_node = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                            uf.union(n, tr_node)

            # 4. Connect component pin pads to copper features
            pin_connected: Dict[str, bool] = {}
            for comp, pin in pins_on_board:
                fp = carrier_fps[comp]
                p_obj = next((p for p in getattr(fp, "pins", []) if p.name == pin), None)
                if not p_obj:
                    continue
                px, py = _get_pin_absolute_pos(fp, p_obj)
                fp_layer = getattr(fp, "layer", "F.Cu") or ("B.Cu" if fp.position[2] < 0 else "F.Cu")
                pad_type = getattr(p_obj, "pad_type", "smd")
                pad_s = getattr(p_obj, "pad_size_mm", (0.8, 0.8))
                pad_r = max(pad_s) / 2.0

                pin_key = f"{comp}.{pin}"
                connected = False

                for tr in net_tr:
                    if pad_type != "thru_hole" and tr.layer != fp_layer:
                        continue
                    d = _dist_point_to_segment((px, py), tr.start_mm, tr.end_mm)
                    if d <= pad_r + tr.width_mm / 2.0 + 0.20:
                        node = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                        uf.union(pin_key, node)
                        connected = True

                for v in net_v:
                    dv = math.hypot(px - v.position_mm[0], py - v.position_mm[1])
                    if dv <= pad_r + v.pad_diameter_mm / 2.0 + 0.20:
                        node_f = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "F.Cu")
                        uf.union(pin_key, node_f)
                        connected = True

                pin_connected[pin_key] = connected
                if not connected:
                    violations.append(
                        DRCViolation(
                            rule_name="PIN_NOT_CONNECTED_TO_TRACE",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=pin_key,
                            description=f"Pin '{pin_key}' on net '{net.name}' is not connected to any routed copper trace or via",
                            location=(px, py, 0.0),
                        )
                    )

            # 5. Connect test points (pads/holes) to net copper features
            for tp in net_tp:
                tp_key = f"TP.{tp.name}"
                tx, ty = tp.position_mm
                tp_r = tp.pad_diameter_mm / 2.0
                for tr in net_tr:
                    d = _dist_point_to_segment((tx, ty), tr.start_mm, tr.end_mm)
                    if d <= tp_r + tr.width_mm / 2.0 + 0.20:
                        node = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                        uf.union(tp_key, node)
                for v in net_v:
                    dv = math.hypot(tx - v.position_mm[0], ty - v.position_mm[1])
                    if dv <= tp_r + v.pad_diameter_mm / 2.0 + 0.20:
                        node_f = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "F.Cu")
                        uf.union(tp_key, node_f)

            # 6. Connect plated mounting holes to net copper features
            for mh in net_mh:
                mh_key = f"MH.{mh.name}"
                mx, my = mh.position_mm
                mh_r = (mh.pad_diameter_mm or mh.drill_diameter_mm) / 2.0
                for tr in net_tr:
                    d = _dist_point_to_segment((mx, my), tr.start_mm, tr.end_mm)
                    if d <= mh_r + tr.width_mm / 2.0 + 0.20:
                        node = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                        uf.union(mh_key, node)
                for v in net_v:
                    dv = math.hypot(mx - v.position_mm[0], my - v.position_mm[1])
                    if dv <= mh_r + v.pad_diameter_mm / 2.0 + 0.20:
                        node_f = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "F.Cu")
                        uf.union(mh_key, node_f)

            # 7. Verify all net segments (pins, traces, vias, test points, holes) belong to the same component
            first_pin_key = f"{pins_on_board[0][0]}.{pins_on_board[0][1]}"
            if pin_connected.get(first_pin_key):
                root = uf.find(first_pin_key)

                # Verify all other component pins reach root
                for comp, pin in pins_on_board[1:]:
                    target_key = f"{comp}.{pin}"
                    if pin_connected.get(target_key) and uf.find(target_key) != root:
                        violations.append(
                            DRCViolation(
                                rule_name="NET_ROUTING_INCOMPLETE",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=net.name,
                                description=(
                                    f"Net '{net.name}' routing is broken: source pin '{first_pin_key}' "
                                    f"is not electrically continuous with target pin '{target_key}'"
                                ),
                            )
                        )

                # Verify all trace segments reach root
                for tr in net_tr:
                    p1 = (round(tr.start_mm[0], 2), round(tr.start_mm[1], 2), tr.layer)
                    if uf.find(p1) != root:
                        violations.append(
                            DRCViolation(
                                rule_name="DISCONNECTED_TRACE_SEGMENT",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=net.name,
                                description=(
                                    f"Trace segment on net '{net.name}' from ({tr.start_mm[0]:.2f}, {tr.start_mm[1]:.2f}) "
                                    f"to ({tr.end_mm[0]:.2f}, {tr.end_mm[1]:.2f}) on layer '{tr.layer}' "
                                    f"is disconnected from source/target component pins"
                                ),
                                location=(tr.start_mm[0], tr.start_mm[1], 0.0),
                            )
                        )

                # Verify all vias reach root
                for v in net_v:
                    p_f = (round(v.position_mm[0], 2), round(v.position_mm[1], 2), "F.Cu")
                    if uf.find(p_f) != root:
                        violations.append(
                            DRCViolation(
                                rule_name="DISCONNECTED_VIA",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=net.name,
                                description=(
                                    f"Via on net '{net.name}' at ({v.position_mm[0]:.2f}, {v.position_mm[1]:.2f}) "
                                    f"is disconnected from source/target component pins"
                                ),
                                location=(v.position_mm[0], v.position_mm[1], 0.0),
                            )
                        )

                # Verify all test points reach root
                for tp in net_tp:
                    tp_key = f"TP.{tp.name}"
                    if tp_key not in uf.parent or uf.find(tp_key) != root:
                        violations.append(
                            DRCViolation(
                                rule_name="TEST_POINT_DISCONNECTED",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=tp.name,
                                description=(
                                    f"Test point '{tp.name}' on net '{net.name}' at "
                                    f"({tp.position_mm[0]:.2f}, {tp.position_mm[1]:.2f}) is disconnected "
                                    f"from source/target component pins"
                                ),
                                location=(tp.position_mm[0], tp.position_mm[1], 0.0),
                            )
                        )

                # Verify all plated mounting holes reach root
                for mh in net_mh:
                    mh_key = f"MH.{mh.name}"
                    if mh_key not in uf.parent or uf.find(mh_key) != root:
                        violations.append(
                            DRCViolation(
                                rule_name="MOUNTING_HOLE_DISCONNECTED",
                                severity=DRCSeverity.ERROR,
                                net_or_zone=mh.name,
                                description=(
                                    f"Plated mounting hole '{mh.name}' on net '{net.name}' at "
                                    f"({mh.position_mm[0]:.2f}, {mh.position_mm[1]:.2f}) is disconnected "
                                    f"from source/target component pins"
                                ),
                                location=(mh.position_mm[0], mh.position_mm[1], 0.0),
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
        if wiring:
            board_footprints = self.get_footprints_for_board(wiring)
            for mh in holes:
                mh_r = mh.drill_diameter_mm / 2.0
                mh_x, mh_y = mh.position_mm
                for fp in board_footprints:
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

        # 5. Check test point to trace collisions and clearance violations
        for tp in self.config.test_points:
            tx, ty = tp.position_mm
            tp_r = tp.pad_diameter_mm / 2.0
            for tr in traces:
                if tp.net == tr.net:
                    continue
                dist = _dist_point_to_segment((tx, ty), tr.start_mm, tr.end_mm)
                min_copper = tp_r + (tr.width_mm / 2.0)
                if dist < min_copper - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="TEST_POINT_TRACE_COLLISION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{tp.name}<->{tr.net}",
                            description=(
                                f"Test point '{tp.name}' on net '{tp.net}' at ({tx:.2f}, {ty:.2f}) collides with "
                                f"trace on net '{tr.net}' on layer '{tr.layer}' (dist: {dist:.3f}mm < {min_copper:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(min_copper, 100.0),
                            location=(tx, ty, 0.0),
                        )
                    )
                elif dist < min_copper + clearance_default - 1e-4:
                    violations.append(
                        DRCViolation(
                            rule_name="CLEARANCE_VIOLATION",
                            severity=DRCSeverity.ERROR,
                            net_or_zone=f"{tp.name}<->{tr.net}",
                            description=(
                                f"Clearance violation between test point '{tp.name}' on net '{tp.net}' at ({tx:.2f}, {ty:.2f}) "
                                f"and trace on net '{tr.net}' (dist: {dist:.3f}mm < required {min_copper + clearance_default:.3f}mm)"
                            ),
                            actual_value=dist,
                            expected_range=(min_copper + clearance_default, 100.0),
                            location=(tx, ty, 0.0),
                        )
                    )

        # 6. Check trace-to-pad short circuits and clearance violations
        if wiring:
            board_fps = self.get_footprints_for_board(wiring)
            pin_to_net: Dict[Tuple[str, str], str] = {}
            if hasattr(wiring, "nets"):
                for net in wiring.nets:
                    for c_name, p_name in net.pins:
                        pin_to_net[(c_name, p_name)] = net.name

            for fp in board_fps:
                fp_layer = getattr(fp, "layer", "F.Cu")
                for p in getattr(fp, "pins", []):
                    p_net = pin_to_net.get((fp.name, p.name))
                    px, py = _get_pin_absolute_pos(fp, p)
                    pad_type = getattr(p, "pad_type", "smd")
                    pad_size = getattr(p, "pad_size_mm", (0.5, 0.5))
                    p_r = min(pad_size) / 2.0

                    for tr in traces:
                        # Allow trace belonging to the pad's own net
                        if p_net and tr.net == p_net:
                            continue
                        # If different copper layers (and not through-hole), no collision
                        if pad_type != "thru_hole" and tr.layer != fp_layer:
                            continue

                        dist = _dist_point_to_segment((px, py), tr.start_mm, tr.end_mm)
                        min_copper = p_r + (tr.width_mm / 2.0)
                        if dist < min_copper - 1e-4:
                            violations.append(
                                DRCViolation(
                                    rule_name="TRACE_SHORT_CIRCUIT",
                                    severity=DRCSeverity.ERROR,
                                    net_or_zone=f"{fp.name}.{p.name}<->{tr.net}",
                                    description=(
                                        f"Trace on net '{tr.net}' on layer '{tr.layer}' collides with pad '{p.name}' "
                                        f"of component '{fp.name}' (net: '{p_net or '<no net>'}') "
                                        f"(dist: {dist:.3f}mm < copper threshold {min_copper:.3f}mm)"
                                    ),
                                    actual_value=dist,
                                    expected_range=(min_copper, 100.0),
                                    location=(px, py, 0.0),
                                )
                            )
                        elif dist < min_copper + clearance_default - 1e-4:
                            violations.append(
                                DRCViolation(
                                    rule_name="CLEARANCE_VIOLATION",
                                    severity=DRCSeverity.ERROR,
                                    net_or_zone=f"{fp.name}.{p.name}<->{tr.net}",
                                    description=(
                                        f"Clearance violation between trace on net '{tr.net}' on layer '{tr.layer}' "
                                        f"and pad '{p.name}' of component '{fp.name}' (net: '{p_net or '<no net>'}') "
                                        f"(dist: {dist:.3f}mm < required {min_copper + clearance_default:.3f}mm)"
                                    ),
                                    actual_value=dist,
                                    expected_range=(min_copper + clearance_default, 100.0),
                                    location=(px, py, 0.0),
                                )
                            )

        # 7. Check silkscreen-to-pad and courtyard overlap
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
            if wiring:
                board_footprints = self.get_footprints_for_board(wiring)
                for fp in board_footprints:
                    fp_layer = getattr(fp, "layer", "F.Cu") or ("B.Cu" if fp.position[2] < 0 else "F.Cu")
                    pad_silk_layer = "B.SilkS" if fp_layer == "B.Cu" else "F.SilkS"
                    fx, fy = fp.position[0], fp.position[1]
                    for p in getattr(fp, "pins", []):
                        pad_type = getattr(p, "pad_type", "smd")
                        if pad_type != "thru_hole" and st.layer != pad_silk_layer:
                            continue
                        px = fx + p.position[0]
                        py = fy + p.position[1]
                        pad_size = getattr(p, "pad_size_mm", (0.5, 0.5))
                        p_r = max(pad_size) / 2.0
                        dist = math.hypot(sx - px, sy - py)
                        min_dist = p_r + 0.30
                        if dist < min_dist:
                            violations.append(
                                DRCViolation(
                                    rule_name="SILKSCREEN_PAD_OVERLAP",
                                    severity=DRCSeverity.ERROR,
                                    net_or_zone=st.text,
                                    description=(
                                        f"Silkscreen text '{st.text}' at ({sx:.2f}, {sy:.2f}) overlaps pad '{p.name}' "
                                        f"on component '{fp.name}' at ({px:.2f}, {py:.2f})"
                                    ),
                                    actual_value=dist,
                                    expected_range=(min_dist, 100.0),
                                    location=(sx, sy, 0.0),
                                )
                            )

        return violations

    def check_antennae(self, wiring: Any) -> List[DRCViolation]:
        """Detect open-ended stubs and antenna traces that radiate EMI or fail signal integrity."""
        violations: List[DRCViolation] = []
        traces = self.config.traces
        vias = self.config.vias
        test_points = self.config.test_points
        copper_regions = self.config.copper_regions

        if not traces:
            return violations

        # Pre-collect all valid termination targets per net and layer
        # 1. Component pin pads
        footprints = self.get_footprints_for_board(wiring)
        pin_targets: Dict[str, List[Tuple[float, float, str, float]]] = {}
        for fp in footprints:
            fp_x, fp_y = fp.position[0], fp.position[1]
            fp_layer = getattr(fp, "layer", "F.Cu") or ("B.Cu" if fp.position[2] < 0 else "F.Cu")
            for p in getattr(fp, "pins", []):
                p_net = ""
                if wiring and hasattr(wiring, "nets"):
                    for n in wiring.nets:
                        for comp_name, pin_name in n.pins:
                            if comp_name == fp.name and pin_name == p.name:
                                p_net = n.name
                                break
                        if p_net:
                            break
                if not p_net:
                    continue

                px, py = _get_pin_absolute_pos(fp, p)
                pad_type = getattr(p, "pad_type", "smd")
                pad_size = getattr(p, "pad_size_mm", (0.5, 0.5))
                pad_r = max(pad_size) / 2.0
                target_layer = "all" if pad_type == "thru_hole" else fp_layer
                if p_net not in pin_targets:
                    pin_targets[p_net] = []
                pin_targets[p_net].append((px, py, target_layer, pad_r))

        # 2. Vias per net
        via_targets: Dict[str, List[Tuple[float, float, str, str, float]]] = {}
        for v in vias:
            if v.net not in via_targets:
                via_targets[v.net] = []
            via_targets[v.net].append(
                (v.position_mm[0], v.position_mm[1], v.layer_start, v.layer_end, v.pad_diameter_mm / 2.0)
            )

        # 3. Test points per net (through-hole, valid on all copper layers)
        tp_targets: Dict[str, List[Tuple[float, float, str, float]]] = {}
        for tp in test_points:
            if tp.net not in tp_targets:
                tp_targets[tp.net] = []
            tp_targets[tp.net].append((tp.position_mm[0], tp.position_mm[1], "all", tp.pad_diameter_mm / 2.0))

        # 4. Capacitive sensor terminals per net
        for s in getattr(self.config, "capacitive_sensors", []):
            scx, scy = getattr(s, "center_mm", (0.0, 0.0))
            sw, sl = getattr(s, "area_mm", (10.0, 10.0))
            s_layer = getattr(s, "layer", "F.Cu")
            term_r = 1.0
            if s.shape == "interdigital":
                if s.tx_pin:
                    pin_targets.setdefault(s.tx_pin, []).append((scx - sw / 2.0, scy, s_layer, term_r))
                if s.rx_pin:
                    pin_targets.setdefault(s.rx_pin, []).append((scx + sw / 2.0, scy, s_layer, term_r))
            else:
                if s.rx_pin:
                    pin_targets.setdefault(s.rx_pin, []).append((scx, scy - sl / 2.0, s_layer, term_r))

        # Check both endpoints (start_mm, end_mm) of each trace segment
        for tr_idx, tr in enumerate(traces):
            for pt in (tr.start_mm, tr.end_mm):
                pt_x, pt_y = pt[0], pt[1]

                # Check connection to another trace of the same net and layer
                connected_to_trace = False
                for other_idx, other_tr in enumerate(traces):
                    if other_idx == tr_idx or other_tr.net != tr.net or other_tr.layer != tr.layer:
                        continue
                    if (
                        _dist_point_to_segment(pt, other_tr.start_mm, other_tr.end_mm)
                        <= (other_tr.width_mm / 2.0) + 0.05
                    ):
                        connected_to_trace = True
                        break
                if connected_to_trace:
                    continue

                # Check connection to a via of the same net
                connected_to_via = False
                for vx, vy, l_start, l_end, v_r in via_targets.get(tr.net, []):
                    if tr.layer in (l_start, l_end) or l_start == "all":
                        if math.hypot(pt_x - vx, pt_y - vy) <= v_r + 0.10:
                            connected_to_via = True
                            break
                if connected_to_via:
                    continue

                # Check connection to a pin pad of the same net
                connected_to_pin = False
                for px, py, p_lay, p_r in pin_targets.get(tr.net, []):
                    if p_lay in (tr.layer, "all"):
                        if math.hypot(pt_x - px, pt_y - py) <= p_r + 0.10:
                            connected_to_pin = True
                            break
                if connected_to_pin:
                    continue

                # Check connection to a test point of the same net
                connected_to_tp = False
                for tx, ty, t_lay, tp_r in tp_targets.get(tr.net, []):
                    if t_lay in (tr.layer, "all"):
                        if math.hypot(pt_x - tx, pt_y - ty) <= tp_r + 0.10:
                            connected_to_tp = True
                            break
                if connected_to_tp:
                    continue

                # Check connection to a copper region / plane of the same net
                connected_to_plane = False
                for cr in copper_regions:
                    if cr.net == tr.net and cr.layer == tr.layer:
                        if _point_in_polygon(pt_x, pt_y, cr.polygon_points_mm):
                            connected_to_plane = True
                            break
                if connected_to_plane:
                    continue

                # If not connected to anything, flag antenna violation
                violations.append(
                    DRCViolation(
                        rule_name="ANTENNA_TRACE_DETECTED",
                        severity=DRCSeverity.ERROR,
                        net_or_zone=tr.net,
                        description=(
                            f"Dangling trace stub / antenna detected on net '{tr.net}' on layer '{tr.layer}' "
                            f"at ({pt_x:.2f}, {pt_y:.2f}) with no pad, via, test point, or connected trace"
                        ),
                        location=(pt_x, pt_y, 0.0),
                    )
                )

        return violations

    def check_schematic(self, wiring: Any) -> DRCViolationCollection:
        """Perform Schematic Design Rule Checks (DRC).

        Enforces:
        - SCHEMATIC_DANGLING_COMPONENT: Every component on every sheet has at least one connected pin in the netlist.
        - SCHEMATIC_SYMBOL_OVERLAP: No two component symbols on a sheet overlap in bounding envelope.
        - SCHEMATIC_NET_ANTENNA: No schematic net is an open 1-pin antenna without an off-page destination or termination.
        - SCHEMATIC_PAGE_TRANSITION_MISSING: Multi-sheet nets connect across all participating sheets without orphaned sheet nodes.
        """
        violations = DRCViolationCollection()
        if not self.config.schematic_sheets or not wiring:
            return violations

        footprints_map = {}
        if hasattr(wiring, "footprints"):
            if isinstance(wiring.footprints, dict):
                footprints_map = wiring.footprints
            elif isinstance(wiring.footprints, list):
                footprints_map = {fp.name: fp for fp in wiring.footprints}

        all_nets = getattr(wiring, "nets", [])
        pin_to_net: Dict[Tuple[str, str], str] = {}
        for net in all_nets:
            for pair in net.pins:
                if len(pair) >= 2:
                    pin_to_net[(pair[0], pair[1])] = net.name

        # 1. Check for single-pin nets / schematic antennas across the entire schematic
        for net in all_nets:
            net_u = net.name.upper()
            if net_u in ("GND", "VBUS", "3V3", "5V", "1V8", "1V2", "VBAT"):
                continue
            if len(net.pins) < 2:
                violations.add_error(
                    rule_name=DRCRuleName.SCHEMATIC_NET_ANTENNA,
                    net_or_zone=net.name,
                    description=(
                        f"Schematic net '{net.name}' is an open antenna with only {len(net.pins)} connected pin "
                        f"({net.pins[0] if net.pins else 'none'}) without an off-page destination or termination"
                    ),
                )

        # 2. Check multi-sheet page transitions ("page transitions replacing vias")
        comp_to_sheets: Dict[str, List[str]] = {}
        for sheet in self.config.schematic_sheets:
            for comp_name in sheet.components:
                comp_to_sheets.setdefault(comp_name, []).append(sheet.title)

        board_fps = self.get_footprints_for_board(wiring)
        board_comp_names = {fp.name for fp in board_fps}

        for net in all_nets:
            participating_sheets = set()
            orphan_pins = []
            for pair in net.pins:
                c_name = pair[0]
                if c_name in comp_to_sheets:
                    participating_sheets.update(comp_to_sheets[c_name])
                elif c_name in board_comp_names:
                    orphan_pins.append(pair)

            if orphan_pins and participating_sheets:
                violations.add_error(
                    rule_name=DRCRuleName.SCHEMATIC_PAGE_TRANSITION_MISSING,
                    net_or_zone=net.name,
                    description=(
                        f"Schematic net '{net.name}' connects to pin(s) {orphan_pins} belonging to component(s) "
                        f"not placed on any schematic sheet, resulting in a missing page transition"
                    ),
                )

            if len(participating_sheets) > 1:
                for sheet_title in participating_sheets:
                    sheet_pins = [p for p in net.pins if sheet_title in comp_to_sheets.get(p[0], [])]
                    if not sheet_pins:
                        violations.add_error(
                            rule_name=DRCRuleName.SCHEMATIC_PAGE_TRANSITION_MISSING,
                            net_or_zone=net.name,
                            description=(
                                f"Schematic net '{net.name}' connects across sheets {list(participating_sheets)} "
                                f"but missing valid page transition or pin connections on sheet '{sheet_title}'"
                            ),
                        )

        # 3. Per-sheet checks: Dangling components and symbol overlaps
        for sheet_idx, sheet in enumerate(self.config.schematic_sheets):
            sheet_fps = []
            for c in sheet.components:
                if c in footprints_map:
                    orig_fp = footprints_map[c]
                    if sheet.pin_breakouts and c in sheet.pin_breakouts:
                        allowed_pins = set(sheet.pin_breakouts[c])
                        matched_pins = [
                            p
                            for p in orig_fp.pins
                            if p.name in allowed_pins or getattr(p, "label", None) in allowed_pins
                        ]
                        sheet_fps.append(orig_fp.model_copy(update={"pins": matched_pins}))
                    else:
                        sheet_fps.append(orig_fp)

            # 3a. Dangling component check
            for fp in sheet_fps:
                connected_pins = [p for p in fp.pins if (fp.name, p.name) in pin_to_net]
                if not connected_pins:
                    violations.add_error(
                        rule_name=DRCRuleName.SCHEMATIC_DANGLING_COMPONENT,
                        net_or_zone=fp.name,
                        description=(
                            f"Component '{fp.name}' on schematic sheet {sheet_idx + 1} ('{sheet.title}') "
                            f"has no pins connected to any nets in the netlist"
                        ),
                    )

            # 3b. Symbol overlap check
            passive_names = set()
            for fp in sheet_fps:
                name_u = fp.name.upper()
                pkg_u = fp.package.upper()
                if (name_u.startswith("R") or "RES" in pkg_u) and len(fp.pins) == 2:
                    n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
                    n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
                    if n1 in ("3V3", "VBUS", "GND") or n2 in ("3V3", "VBUS", "GND"):
                        passive_names.add(fp.name)
                elif (name_u.startswith("C") or "CAP" in pkg_u) and len(fp.pins) == 2:
                    n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
                    n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
                    if (n1 in ("3V3", "VBUS", "GND") and n2) or (n2 in ("3V3", "VBUS", "GND") and n1):
                        passive_names.add(fp.name)

            main_fps = [fp for fp in sheet_fps if fp.name not in passive_names]
            if not main_fps:
                main_fps = sheet_fps

            layout = (
                getattr(sheet, "layout", None)
                or getattr(self.config, "schematic_layout", None)
                or SchematicLayoutModel()
            )
            col_width = layout.col_width
            col_gap = layout.col_gap
            sheet_center_x = layout.sheet_center_x
            sheet_center_y = layout.sheet_center_y
            row_step_y = layout.row_step_y
            def_sym_w = layout.default_symbol_width
            def_sym_h = layout.default_symbol_height

            num_comps = len(main_fps)
            if num_comps == 2 and layout.cols_per_row is None and not grid_positions:
                col_gap = 55.0
            elif num_comps == 3 and layout.cols_per_row is None and not grid_positions:
                col_gap = 35.0
            cols_per_row = layout.cols_per_row if layout.cols_per_row is not None else max(1, min(num_comps, 3))
            num_rows = (num_comps + cols_per_row - 1) // cols_per_row
            total_content_w = (cols_per_row * col_width) + ((cols_per_row - 1) * col_gap)
            start_x = sheet_center_x - (total_content_w / 2.0)
            top_row_y = sheet_center_y + ((num_rows - 1) * 27.5)

            grid_positions = getattr(layout, "grid_positions", {}) or {}
            boxes: List[Tuple[float, float, float, float, str]] = []
            main_box_map: Dict[str, Tuple[float, float, float, float]] = {}
            for c_idx, fp in enumerate(main_fps):
                if fp.name in grid_positions:
                    r_idx, col = grid_positions[fp.name]
                else:
                    col = c_idx % cols_per_row
                    r_idx = c_idx // cols_per_row
                cx = start_x + (col * (col_width + col_gap)) + (col_width / 2.0)
                cy = top_row_y - (r_idx * row_step_y)
                cw = def_sym_w
                num_pins = len(fp.pins)
                ch = max(def_sym_h, (num_pins // 2) * 5.0 + 10.0)
                boxes.append((cx, cy, cw, ch, fp.name))
                main_box_map[fp.name] = (cx, cy, cw, ch)

            # Include passives (decoupling caps, pull-ups, and shunts) in symbol overlap checks
            decoupling_caps = []
            vert_passives = []
            for fp in sheet_fps:
                if fp.name in passive_names:
                    n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
                    n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
                    if (n1 in ("3V3", "VBUS", "VDD") and n2 == "GND") or (n2 in ("3V3", "VBUS", "VDD") and n1 == "GND"):
                        decoupling_caps.append(fp)
                    else:
                        vert_passives.append(fp)

            if decoupling_caps:
                base_y = 35.0
                total_w = (len(decoupling_caps) - 1) * 28.0
                base_x = max(35.0, sheet_center_x - (total_w / 2.0))
                for idx, cap in enumerate(decoupling_caps):
                    boxes.append((base_x + idx * 28.0, base_y, 14.0, 24.0, cap.name))

            comp_passive_count: Dict[Tuple[str, str], int] = {}
            for p_fp in vert_passives:
                n1 = pin_to_net.get((p_fp.name, p_fp.pins[0].name), "").upper()
                n2 = pin_to_net.get((p_fp.name, p_fp.pins[1].name), "").upper()
                is_pullup = n1 in ("3V3", "VBUS") or n2 in ("3V3", "VBUS")
                sig_net = n2 if (n1 in ("3V3", "VBUS", "GND")) else n1
                target_comp = next((c for (c, _), n in pin_to_net.items() if n == sig_net and c in main_box_map), None)
                if target_comp:
                    m_cx, m_cy, m_cw, _ = main_box_map[target_comp]
                    other_comps = [
                        c for (c, _), n in pin_to_net.items() if n == sig_net and c in main_box_map and c != target_comp
                    ]
                    if other_comps:
                        side_key = (target_comp, "channel")
                        local_idx = comp_passive_count.get(side_key, 0)
                        comp_passive_count[side_key] = local_idx + 1
                        o_cx, _, o_cw, _ = main_box_map[other_comps[0]]
                        ch_left = min(m_cx + m_cw / 2.0, o_cx + o_cw / 2.0)
                        px = ch_left + 10.0 + (local_idx % 2) * 9.0
                        py = m_cy + (12.0 if is_pullup else -12.0)
                    else:
                        m_fp = next(f for f in main_fps if f.name == target_comp)
                        p_obj = next((p for p in m_fp.pins if pin_to_net.get((target_comp, p.name)) == sig_net), None)
                        sheet_sides = getattr(sheet, "pin_sides", {}) or {}
                        comp_sides = sheet_sides.get(target_comp, {})
                        p_side = comp_sides.get(p_obj.name, p_obj.side.value if p_obj else "left") if p_obj else "left"
                        side_key = (target_comp, p_side)
                        local_idx = comp_passive_count.get(side_key, 0)
                        comp_passive_count[side_key] = local_idx + 1
                        if p_side in ("right", "top"):
                            px = m_cx + (m_cw / 2.0) + 12.0 + (local_idx * 12.0)
                        else:
                            px = m_cx - (m_cw / 2.0) - 14.0 - (local_idx * 10.0)
                        py = m_cy + (12.0 if is_pullup else -12.0)
                    boxes.append((px, py, 8.0, 18.0, p_fp.name))
                elif main_fps:
                    m_cx, m_cy, m_cw, _ = main_box_map[main_fps[0].name]
                    px = m_cx - (m_cw / 2.0) - 24.0
                    py = m_cy + (12.0 if is_pullup else -12.0)
                    boxes.append((px, py, 8.0, 18.0, p_fp.name))

            for i, b1 in enumerate(boxes):
                for b2 in boxes[i + 1 :]:
                    dx = abs(b1[0] - b2[0])
                    dy = abs(b1[1] - b2[1])
                    min_dx = (b1[2] + b2[2]) / 2.0
                    min_dy = (b1[3] + b2[3]) / 2.0
                    if dx < min_dx and dy < min_dy:
                        violations.add_error(
                            rule_name=DRCRuleName.SCHEMATIC_SYMBOL_OVERLAP,
                            net_or_zone=f"{b1[4]} & {b2[4]}",
                            description=(
                                f"Schematic symbol overlap on sheet {sheet_idx + 1} ('{sheet.title}'): "
                                f"Symbol '{b1[4]}' overlaps with '{b2[4]}' "
                                f"(dx={dx:.1f}mm < {min_dx:.1f}mm, dy={dy:.1f}mm < {min_dy:.1f}mm)"
                            ),
                            location=(b1[0], b1[1], 0.0),
                        )

            # 3c. Schematic page boundary check (BUG-068)
            for b in boxes:
                b_xmin = b[0] - b[2] / 2.0
                b_xmax = b[0] + b[2] / 2.0
                b_ymin = b[1] - b[3] / 2.0
                b_ymax = b[1] + b[3] / 2.0
                if b_xmin < 15.0 or b_xmax > 282.0 or b_ymin < 15.0 or b_ymax > 195.0:
                    violations.add_error(
                        rule_name=DRCRuleName.SCHEMATIC_PAGE_BOUNDARY_EXCEEDED,
                        net_or_zone=b[4],
                        description=(
                            f"Component '{b[4]}' on schematic sheet {sheet_idx + 1} ('{sheet.title}') "
                            f"exceeds page printable boundaries: bounds=({b_xmin:.1f}, {b_ymin:.1f}, {b_xmax:.1f}, {b_ymax:.1f})"
                        ),
                        location=(b[0], b[1], 0.0),
                    )

        return violations
