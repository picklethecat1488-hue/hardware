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


def _point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm for 2D point-in-polygon test."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


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

        # 5. Boundary containment check
        if wiring and hasattr(wiring, "footprints"):
            violations.extend(self.check_boundary_containment(wiring.footprints, outline_polygon))

        # 6. Netlist connectivity validation
        if wiring and hasattr(wiring, "nets"):
            violations.extend(self.check_netlist_connectivity(wiring))

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
        if not footprints:
            return violations

        w_board, l_board, _ = self.config.dimensions_mm
        half_w = w_board / 2.0
        half_l = l_board / 2.0

        for fp in footprints:
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
