"""Unit tests for PCB Design Rules Checking (DRC) engine."""

import math
import pytest
from model.pcb import (
    LayerType,
    StackupLayerModel,
    StackupModel,
    DifferentialPairModel,
    NetClassModel,
    FlexZoneModel,
    PCBConfig,
    TraceSegmentModel,
    ViaModel,
    MountingHoleModel,
    TestPointModel as PcbTestPointModel,
    SilkscreenTextModel,
)
from provider.pcb.drc import PCBDesignRulesChecker, DRCSeverity, DRCReport


@pytest.fixture
def four_layer_pcie_stackup() -> StackupModel:
    """Create a 4-layer PCIe stackup (Sig - GND - PWR - Sig)."""
    return StackupModel(
        layers=[
            StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.2
            ),
            StackupLayerModel(name="In1.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
            StackupLayerModel(
                name="Core", layer_type=LayerType.DIELECTRIC, thickness_mm=1.000, dielectric_constant=4.4
            ),
            StackupLayerModel(name="In2.Cu", layer_type=LayerType.POWER, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.2
            ),
            StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
        ],
        finish="ENIG",
    )


@pytest.fixture
def base_pcb_config(four_layer_pcie_stackup: StackupModel) -> PCBConfig:
    """Create a valid PCBConfig with a PCIe differential pair net class."""
    diff_pair = DifferentialPairModel(
        name="PCIE_TX0",
        pos_net="PCIE_TX0_P",
        neg_net="PCIE_TX0_N",
        target_impedance_ohms=85.0,
        impedance_tolerance_percent=10.0,
        max_intra_pair_skew_mm=0.150,
        max_inter_pair_skew_mm=1.000,
        max_via_count=2,
    )
    net_class = NetClassModel(
        name="PCIe_Gen4",
        trace_width_mm=0.160,
        clearance_mm=0.120,
        via_dia_mm=0.45,
        via_drill_mm=0.20,
        diff_pairs=[diff_pair],
        require_ground_stitch_via=True,
        max_stitch_via_distance_mm=1.000,
    )
    return PCBConfig(
        name="ComputeCarrier",
        board_type="rigid",
        stackup=four_layer_pcie_stackup,
        dimensions_mm=(80.0, 50.0, 1.6),
        net_classes=[net_class],
    )


def test_drc_all_passing(base_pcb_config: PCBConfig):
    """Verify that a compliant design passes DRC with zero errors."""
    checker = PCBDesignRulesChecker(base_pcb_config)
    net_lengths = {
        "PCIE_TX0_P": 35.200,
        "PCIE_TX0_N": 35.250,  # intra skew = 0.050mm < 0.150mm
    }
    via_locations = {
        "PCIE_TX0_P": [(10.0, 10.0, "F.Cu", "B.Cu")],
        "PCIE_TX0_N": [(10.2, 10.0, "F.Cu", "B.Cu")],
    }
    gnd_vias = [(10.0, 10.5)]  # dist = 0.5mm < 1.0mm

    report = checker.check_all(
        net_lengths_mm=net_lengths,
        via_locations=via_locations,
        gnd_via_locations=gnd_vias,
    )

    assert report.passed
    assert report.error_count == 0
    assert "PASSED" in report.summary()


def test_drc_trace_width_too_thin(base_pcb_config: PCBConfig):
    """Verify violation when trace width is below fab minimum."""
    base_pcb_config.net_classes[0].trace_width_mm = 0.050  # < 0.075mm
    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "MIN_TRACE_WIDTH" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_annular_ring_too_small(base_pcb_config: PCBConfig):
    """Verify violation when via annular ring is below standard minimum."""
    base_pcb_config.net_classes[0].via_dia_mm = 0.30
    base_pcb_config.net_classes[0].via_drill_mm = 0.25  # annular ring = 0.025mm < 0.100mm
    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "MIN_ANNULAR_RING" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_impedance_mismatch(base_pcb_config: PCBConfig):
    """Verify violation when geometry produces impedance deviating from target tolerance."""
    # Drastically widen trace to drop impedance far below 85 ohms (to ~30-40 ohms)
    base_pcb_config.net_classes[0].trace_width_mm = 0.800
    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "DIFF_IMPEDANCE_MISMATCH" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_intra_pair_skew_exceeded(base_pcb_config: PCBConfig):
    """Verify error when differential intra-pair skew exceeds budget."""
    checker = PCBDesignRulesChecker(base_pcb_config)
    net_lengths = {
        "PCIE_TX0_P": 30.000,
        "PCIE_TX0_N": 30.300,  # skew = 0.300mm > 0.150mm
    }
    report = checker.check_all(net_lengths_mm=net_lengths)

    assert not report.passed
    assert any(v.rule_name == "INTRA_PAIR_SKEW_EXCEEDED" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_inter_pair_skew_warning(base_pcb_config: PCBConfig):
    """Verify warning when lane-to-lane inter-pair skew exceeds limit."""
    # Add second diff pair to net class
    diff_pair_1 = DifferentialPairModel(
        name="PCIE_TX1",
        pos_net="PCIE_TX1_P",
        neg_net="PCIE_TX1_N",
        target_impedance_ohms=85.0,
        max_inter_pair_skew_mm=1.000,
    )
    base_pcb_config.net_classes[0].diff_pairs.append(diff_pair_1)

    checker = PCBDesignRulesChecker(base_pcb_config)
    net_lengths = {
        "PCIE_TX0_P": 30.000,
        "PCIE_TX0_N": 30.050,  # lane 0 avg = 30.025
        "PCIE_TX1_P": 32.500,
        "PCIE_TX1_N": 32.550,  # lane 1 avg = 32.525 -> diff = 2.500mm > 1.0mm
    }
    report = checker.check_all(net_lengths_mm=net_lengths)

    assert any(
        v.rule_name == "INTER_PAIR_SKEW_EXCEEDED" and v.severity == DRCSeverity.WARNING for v in report.violations
    )


def test_drc_max_via_count_exceeded(base_pcb_config: PCBConfig):
    """Verify error when a high-speed signal has more vias than allowed."""
    checker = PCBDesignRulesChecker(base_pcb_config)
    via_locations = {
        "PCIE_TX0_P": [
            (10.0, 10.0, "F.Cu", "In2.Cu"),
            (15.0, 10.0, "In2.Cu", "B.Cu"),
            (20.0, 10.0, "B.Cu", "F.Cu"),  # 3 vias > max_via_count=2
        ]
    }
    report = checker.check_all(via_locations=via_locations)

    assert not report.passed
    assert any(v.rule_name == "MAX_VIA_COUNT_EXCEEDED" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_missing_return_path_ground_stitch(base_pcb_config: PCBConfig):
    """Verify error when a high-speed via has no ground return stitching via nearby."""
    checker = PCBDesignRulesChecker(base_pcb_config)
    via_locations = {
        "PCIE_TX0_P": [(10.0, 10.0, "F.Cu", "B.Cu")],
    }
    gnd_vias = [(20.0, 20.0)]  # dist = 14.14mm >> max_stitch_via_distance_mm (1.0mm)
    report = checker.check_all(via_locations=via_locations, gnd_via_locations=gnd_vias)

    assert not report.passed
    assert any(
        v.rule_name == "RETURN_PATH_GND_STITCH_MISSING" and v.severity == DRCSeverity.ERROR for v in report.violations
    )


def test_drc_flex_bend_radius_rules(base_pcb_config: PCBConfig):
    """Verify error and warning for flex PCB bend radius violations."""
    # Flex zone with substrate=0.050, coverlay=0.025, copper=0.035 -> t_flex = 0.050 + 0.050 + 0.070 = 0.170mm
    # Static min = 6 * 0.170 = 1.02mm, Dynamic min = 10 * 0.170 = 1.70mm
    base_pcb_config.flex_zones = [
        FlexZoneModel(
            name="Zone_Static_Pass_Dynamic_Warn",
            bounds=((0.0, 0.0), (20.0, 10.0)),
            min_bend_radius_mm=1.20,  # 1.02 <= 1.20 < 1.70 -> WARNING
            substrate_thickness_mm=0.050,
            coverlay_thickness_mm=0.025,
        ),
        FlexZoneModel(
            name="Zone_Too_Tight",
            bounds=((25.0, 0.0), (45.0, 10.0)),
            min_bend_radius_mm=0.50,  # 0.50 < 1.02 -> ERROR
            substrate_thickness_mm=0.050,
            coverlay_thickness_mm=0.025,
        ),
    ]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(
        v.rule_name == "FLEX_BEND_RADIUS_TOO_TIGHT" and v.severity == DRCSeverity.ERROR for v in report.violations
    )
    assert any(
        v.rule_name == "FLEX_DYNAMIC_BEND_WARNING" and v.severity == DRCSeverity.WARNING for v in report.violations
    )


def test_drc_trace_short_circuit(base_pcb_config: PCBConfig):
    """Verify error when two traces of different nets intersect on the same layer."""
    t1 = TraceSegmentModel(
        start_mm=(-5.0, 0.0),
        end_mm=(5.0, 0.0),
        width_mm=0.20,
        layer="F.Cu",
        net="NET_A",
    )
    t2 = TraceSegmentModel(
        start_mm=(0.0, -5.0),
        end_mm=(0.0, 5.0),
        width_mm=0.20,
        layer="F.Cu",
        net="NET_B",
    )
    base_pcb_config.traces = [t1, t2]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "TRACE_SHORT_CIRCUIT" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_trace_clearance_violation(base_pcb_config: PCBConfig):
    """Verify error when two traces of different nets pass closer than the required clearance."""
    t1 = TraceSegmentModel(
        start_mm=(-5.0, 0.0),
        end_mm=(5.0, 0.0),
        width_mm=0.20,
        layer="F.Cu",
        net="NET_A",
    )
    # Distance between centerlines is 0.25mm. Copper threshold is (0.2+0.2)/2 = 0.20mm.
    # Center distance 0.25mm means surface-to-surface gap is 0.05mm < 0.10mm clearance default.
    t2 = TraceSegmentModel(
        start_mm=(-5.0, 0.25),
        end_mm=(5.0, 0.25),
        width_mm=0.20,
        layer="F.Cu",
        net="NET_B",
    )
    base_pcb_config.traces = [t1, t2]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "CLEARANCE_VIOLATION" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_via_trace_collision_and_clearance(base_pcb_config: PCBConfig):
    """Verify error when a via collides with or breaches clearance to a foreign net trace."""
    via = ViaModel(
        position_mm=(0.0, 0.0),
        pad_diameter_mm=0.45,
        drill_diameter_mm=0.20,
        layer_start="F.Cu",
        layer_end="B.Cu",
        net="NET_VIA",
    )
    # Collision: trace passes through center of via
    tr_collide = TraceSegmentModel(
        start_mm=(-2.0, 0.0),
        end_mm=(2.0, 0.0),
        width_mm=0.20,
        layer="F.Cu",
        net="NET_TRACE",
    )
    base_pcb_config.vias = [via]
    base_pcb_config.traces = [tr_collide]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "VIA_TRACE_COLLISION" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_trace_outside_board_boundary(base_pcb_config: PCBConfig):
    """Verify error when a trace extends outside the board envelope or CAD outline."""
    # Board dimensions are 80.0 x 50.0 (half_w = 40.0, half_l = 25.0)
    t_outside = TraceSegmentModel(
        start_mm=(35.0, 0.0),
        end_mm=(45.0, 0.0),  # 45.0 > 40.0
        width_mm=0.20,
        layer="F.Cu",
        net="NET_A",
    )
    base_pcb_config.traces = [t_outside]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(
        v.rule_name == "TRACE_OUTSIDE_BOARD_BOUNDARY" and v.severity == DRCSeverity.ERROR for v in report.violations
    )


def test_drc_via_and_test_point_outside_board_boundary(base_pcb_config: PCBConfig):
    """Verify error when vias or test points are placed outside the board boundary."""
    via_outside = ViaModel(
        position_mm=(45.0, 0.0),  # 45.0 > 40.0
        pad_diameter_mm=0.45,
        drill_diameter_mm=0.20,
        layer_start="F.Cu",
        layer_end="B.Cu",
        net="NET_VIA",
    )
    tp_outside = PcbTestPointModel(
        name="TP_OUT",
        net="NET_TP",
        position_mm=(0.0, 30.0),  # 30.0 > 25.0
        pad_diameter_mm=1.40,
        drill_diameter_mm=0.80,
    )
    base_pcb_config.vias = [via_outside]
    base_pcb_config.test_points = [tp_outside]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(
        v.rule_name == "VIA_OUTSIDE_BOARD_BOUNDARY" and v.severity == DRCSeverity.ERROR for v in report.violations
    )
    assert any(
        v.rule_name == "TEST_POINT_OUTSIDE_BOARD_BOUNDARY" and v.severity == DRCSeverity.ERROR
        for v in report.violations
    )


def test_drc_disconnected_test_point_airwire(base_pcb_config: PCBConfig):
    """Verify error when a test point with an active net has no connecting trace."""
    from unittest.mock import MagicMock

    tp = PcbTestPointModel(
        name="TP_DISCONNECTED",
        net="NET_MONITOR",
        position_mm=(10.0, 10.0),
        pad_diameter_mm=1.40,
        drill_diameter_mm=0.80,
    )
    base_pcb_config.test_points = [tp]
    base_pcb_config.traces = []  # No traces connected to TP_DISCONNECTED

    wiring_mock = MagicMock()
    wiring_mock.footprints = []
    wiring_mock.nets = []

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all(wiring=wiring_mock)

    assert not report.passed
    assert any(
        v.rule_name == "DISCONNECTED_TEST_POINT_AIRWIRE" and v.severity == DRCSeverity.ERROR for v in report.violations
    )


def test_drc_silkscreen_pad_overlap(base_pcb_config: PCBConfig):
    """Verify error when silkscreen text overlaps an exposed test point pad or mounting hole."""
    tp = PcbTestPointModel(
        name="TP1",
        net="NET_1",
        position_mm=(10.0, 10.0),
        pad_diameter_mm=1.40,
        drill_diameter_mm=0.80,
    )
    # Silkscreen placed directly on top of test point pad
    silk_overlap = SilkscreenTextModel(
        text="TP1",
        position=(10.1, 10.1),
        layer="F.Silkscreen",
    )
    base_pcb_config.test_points = [tp]
    base_pcb_config.silkscreen_texts = [silk_overlap]

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all()

    assert not report.passed
    assert any(v.rule_name == "SILKSCREEN_PAD_OVERLAP" and v.severity == DRCSeverity.ERROR for v in report.violations)


def test_drc_antenna_detection(base_pcb_config: PCBConfig):
    """Verify DRC flags open-ended dangling trace stubs as ANTENNA_TRACE_DETECTED."""
    from unittest.mock import MagicMock
    from model.wiring import FootprintModel, PinModel, NetModel

    fp = FootprintModel(
        name="U1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(4.0, 4.0, 1.0),
        pins=[PinModel(name="1", position=(-2.0, 0.0, 0.0), label="IN", side="left", pad_type="smd")],
    )
    net = NetModel(name="SIG_A", color="blue", pins=[("U1", "1")])

    wiring_mock = MagicMock()
    wiring_mock.footprints = [fp]
    wiring_mock.nets = [net]

    # Trace starts at U1.1 (-2.0, 0.0) and ends in open space (15.0, 0.0) without a via or pad
    dangling_tr = TraceSegmentModel(
        net="SIG_A",
        layer="F.Cu",
        width_mm=0.15,
        start_mm=(-2.0, 0.0),
        end_mm=(15.0, 0.0),
    )
    base_pcb_config.traces = [dangling_tr]
    base_pcb_config.vias = []
    base_pcb_config.test_points = []

    checker = PCBDesignRulesChecker(base_pcb_config)
    report = checker.check_all(wiring=wiring_mock)

    assert not report.passed
    assert any(v.rule_name == "ANTENNA_TRACE_DETECTED" and v.severity == DRCSeverity.ERROR for v in report.violations)

    # Now bridge the antenna with a via at (15.0, 0.0)
    base_pcb_config.vias = [
        ViaModel(
            position_mm=(15.0, 0.0),
            drill_diameter_mm=0.20,
            pad_diameter_mm=0.45,
            layer_start="F.Cu",
            layer_end="B.Cu",
            net="SIG_A",
        )
    ]
    report_fixed = checker.check_all(wiring=wiring_mock)
    assert not any(v.rule_name == "ANTENNA_TRACE_DETECTED" for v in report_fixed.violations)


def test_drc_test_point_trace_collision(base_pcb_config: PCBConfig):
    """Verify DRC catches traces of a different net short-circuiting into test point pads."""
    tp = PcbTestPointModel(
        name="TP_RX0_P",
        net="PCIE_RX0_P",
        position_mm=(-6.0, -22.0),
        pad_diameter_mm=1.40,
        drill_diameter_mm=0.80,
    )
    # A trace on net VLOAD_SW cuts through TP_RX0_P at (-6.0, -22.0)
    colliding_tr = TraceSegmentModel(
        net="VLOAD_SW",
        layer="B.Cu",
        width_mm=0.35,
        start_mm=(-6.0, -14.0),
        end_mm=(-6.0, -30.0),
    )
    base_pcb_config.test_points = [tp]
    base_pcb_config.traces = [colliding_tr]

    checker = PCBDesignRulesChecker(base_pcb_config)
    violations = checker.check_clearances_and_overlaps(wiring=None)

    assert any(
        v.rule_name == "TEST_POINT_TRACE_COLLISION" and "TP_RX0_P<->VLOAD_SW" in v.net_or_zone for v in violations
    )


def test_drc_severity_coverage_info_warning_error(base_pcb_config: PCBConfig):
    """Verify DRCReport properly classifies and tabulates ERROR, WARNING, and INFO severities."""
    # 1. INFO: Compliant flex zone bend radius
    info_zone = FlexZoneModel(
        name="compliant_flex",
        start_x_mm=10.0,
        length_mm=20.0,
        substrate_thickness_mm=0.05,
        coverlay_thickness_mm=0.025,
        min_bend_radius_mm=5.0,  # > 10x thickness (1.7mm)
    )
    # 2. WARNING: Flex zone bend radius between static and dynamic limit
    warning_zone = FlexZoneModel(
        name="warning_flex",
        start_x_mm=40.0,
        length_mm=20.0,
        substrate_thickness_mm=0.05,
        coverlay_thickness_mm=0.025,
        min_bend_radius_mm=1.2,  # Between static (1.02mm) and dynamic (1.7mm)
    )
    # 3. ERROR: Flex zone bend radius below static limit
    error_zone = FlexZoneModel(
        name="error_flex",
        start_x_mm=70.0,
        length_mm=20.0,
        substrate_thickness_mm=0.05,
        coverlay_thickness_mm=0.025,
        min_bend_radius_mm=0.5,  # < static (1.02mm)
    )
    base_pcb_config.flex_zones = [info_zone, warning_zone, error_zone]

    checker = PCBDesignRulesChecker(base_pcb_config)
    violations = checker.check_flex_rules()

    has_info = any(v.severity == DRCSeverity.INFO for v in violations)
    has_warning = any(v.severity == DRCSeverity.WARNING for v in violations)
    has_error = any(v.severity == DRCSeverity.ERROR for v in violations)

    assert has_info, "Expected at least one INFO severity violation"
    assert has_warning, "Expected at least one WARNING severity violation"
    assert has_error, "Expected at least one ERROR severity violation"

    report = DRCReport(passed=False, violations=violations)
    assert report.info_count >= 1
    assert report.warning_count >= 1
    assert report.error_count >= 1
    assert "Total Info:" in report.summary()


def test_find_empty_space_for_silkscreen_label():
    """Verify find_empty_space_for_label finds collision-free coordinates avoiding pads and holes."""
    from provider.pcb.silkscreen import find_empty_space_for_label

    # Obstacle at (10.0, 10.0) with radius 1.5mm (e.g. test point pad)
    obstacles = [(10.0, 10.0, 1.5)]
    board_bounds = (0.0, 0.0, 50.0, 50.0)

    # Search for label at base (10.0, 10.0)
    off_x, off_y = find_empty_space_for_label(
        base_x=10.0,
        base_y=10.0,
        label_w=3.0,
        label_h=1.0,
        circular_obstacles=obstacles,
        board_bounds=board_bounds,
        clearance=0.30,
        preferred_direction="north",
    )

    cand_x = 10.0 + off_x
    cand_y = 10.0 + off_y

    # Verify label center is at least (pad_r + label_h/2 + clearance) away from obstacle
    dist = math.hypot(cand_x - 10.0, cand_y - 10.0)
    min_dist = 1.5 + 0.5 + 0.30
    assert dist >= min_dist - 1e-4, f"Distance {dist} < required clearance {min_dist}"

    # Verify inside board bounds
    assert cand_x - 1.5 >= board_bounds[0]
    assert cand_x + 1.5 <= board_bounds[2]
    assert cand_y - 0.5 >= board_bounds[1]
    assert cand_y + 0.5 <= board_bounds[3]


def test_test_board_carrier_and_flex_tail_zero_drc_errors_and_warnings():
    """Verify test_board carrier and flex tail subassembly both pass DRC with 0 errors and 0 warnings."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring

    provider = TestBoardProvider()
    wiring = Wiring(provider.wiring_path)

    # 1. Carrier PCB check
    carrier_checker = PCBDesignRulesChecker(provider.pcb_config)
    carrier_report = carrier_checker.check_all(wiring=wiring)
    assert carrier_report.passed, f"Carrier DRC failed: {carrier_report.summary()}"
    assert carrier_report.error_count == 0, f"Carrier has {carrier_report.error_count} errors"
    assert carrier_report.warning_count == 0, f"Carrier has {carrier_report.warning_count} warnings"

    # 2. Flex tail PCB check
    flex_part = provider.part["flex_tail"]("flex_tail", None, None)
    flex_config = flex_part.to_pcb_config()
    if not flex_config.stackup:
        flex_config = flex_config.model_copy(update={"stackup": provider.pcb_config.stackup})
    flex_checker = PCBDesignRulesChecker(flex_config)
    flex_report = flex_checker.check_all(wiring=wiring)
    assert flex_report.passed, f"Flex tail DRC failed: {flex_report.summary()}"
    assert flex_report.error_count == 0, f"Flex tail has {flex_report.error_count} errors"
    assert flex_report.warning_count == 0, f"Flex tail has {flex_report.warning_count} warnings"


def test_drc_net_continuity_source_target_reachability(base_pcb_config: PCBConfig):
    """Verify DRC validates net segments are fully connected between source and target components."""
    from unittest.mock import MagicMock
    from model.wiring import FootprintModel, PinModel, NetModel

    # Source component U1 at (0.0, 0.0) with pin 1 at (-2.0, 0.0)
    fp_u1 = FootprintModel(
        name="U1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(4.0, 4.0, 1.0),
        pins=[PinModel(name="1", position=(-2.0, 0.0, 0.0), label="OUT", side="left", pad_type="smd")],
    )
    # Target component U2 at (20.0, 0.0) with pin 2 at (-2.0, 0.0) -> global pos (18.0, 0.0)
    fp_u2 = FootprintModel(
        name="U2",
        package="SOIC-8",
        position=(20.0, 0.0, 0.0),
        dimensions=(4.0, 4.0, 1.0),
        pins=[PinModel(name="2", position=(-2.0, 0.0, 0.0), label="IN", side="left", pad_type="smd")],
    )
    net = NetModel(name="CTRL_SIG", color="green", pins=[("U1", "1"), ("U2", "2")])

    wiring_mock = MagicMock()
    wiring_mock.footprints = [fp_u1, fp_u2]
    wiring_mock.nets = [net]

    # Case 1: Pin not connected (U2.2 has no trace)
    tr_partial = TraceSegmentModel(
        net="CTRL_SIG",
        layer="F.Cu",
        width_mm=0.20,
        start_mm=(-2.0, 0.0),
        end_mm=(5.0, 0.0),
    )
    base_pcb_config.traces = [tr_partial]
    base_pcb_config.vias = []

    checker = PCBDesignRulesChecker(base_pcb_config)
    violations_missing = checker.check_net_continuity(wiring_mock)
    assert any(v.rule_name == "PIN_NOT_CONNECTED_TO_TRACE" and "U2.2" in v.net_or_zone for v in violations_missing)

    # Case 2: Broken trace in middle (U1 has a trace and U2 has a trace, but airwire/gap between them)
    tr_u2 = TraceSegmentModel(
        net="CTRL_SIG",
        layer="F.Cu",
        width_mm=0.20,
        start_mm=(10.0, 0.0),
        end_mm=(18.0, 0.0),
    )
    base_pcb_config.traces = [tr_partial, tr_u2]  # Gap between (5.0, 0.0) and (10.0, 0.0)
    violations_broken = checker.check_net_continuity(wiring_mock)
    assert any(v.rule_name == "NET_ROUTING_INCOMPLETE" and v.net_or_zone == "CTRL_SIG" for v in violations_broken)

    # Case 3: Fully connected from source U1 to target U2
    tr_bridge = TraceSegmentModel(
        net="CTRL_SIG",
        layer="F.Cu",
        width_mm=0.20,
        start_mm=(5.0, 0.0),
        end_mm=(10.0, 0.0),
    )
    base_pcb_config.traces = [tr_partial, tr_bridge, tr_u2]
    violations_complete = checker.check_net_continuity(wiring_mock)
    assert len(violations_complete) == 0, f"Expected 0 violations, got {violations_complete}"

    # Case 4: Disconnected trace segment floating on the net
    tr_orphan = TraceSegmentModel(
        net="CTRL_SIG",
        layer="F.Cu",
        width_mm=0.20,
        start_mm=(30.0, 30.0),
        end_mm=(35.0, 30.0),
    )
    base_pcb_config.traces = [tr_partial, tr_bridge, tr_u2, tr_orphan]
    violations_orphan_tr = checker.check_net_continuity(wiring_mock)
    assert any(
        v.rule_name == "DISCONNECTED_TRACE_SEGMENT" and v.net_or_zone == "CTRL_SIG" for v in violations_orphan_tr
    )

    # Case 5: Disconnected via on the net
    base_pcb_config.traces = [tr_partial, tr_bridge, tr_u2]
    from model.pcb import ViaModel, TestPointModel, MountingHoleModel

    via_orphan = ViaModel(
        net="CTRL_SIG",
        position_mm=(40.0, 40.0),
        pad_diameter_mm=0.6,
        drill_diameter_mm=0.3,
        layer_start="F.Cu",
        layer_end="B.Cu",
    )
    base_pcb_config.vias = [via_orphan]
    violations_orphan_via = checker.check_net_continuity(wiring_mock)
    assert any(v.rule_name == "DISCONNECTED_VIA" and v.net_or_zone == "CTRL_SIG" for v in violations_orphan_via)

    # Case 6: Disconnected test point pad/hole on the net
    base_pcb_config.vias = []
    tp_orphan = TestPointModel(
        name="TP_CTRL",
        net="CTRL_SIG",
        position_mm=(50.0, 50.0),
        pad_diameter_mm=1.0,
        hole_diameter_mm=0.5,
    )
    base_pcb_config.test_points = [tp_orphan]
    violations_orphan_tp = checker.check_net_continuity(wiring_mock)
    assert any(v.rule_name == "TEST_POINT_DISCONNECTED" and v.net_or_zone == "TP_CTRL" for v in violations_orphan_tp)

    # Case 7: Disconnected plated mounting hole on the net
    base_pcb_config.test_points = []
    mh_orphan = MountingHoleModel(
        name="MH_CTRL",
        net="CTRL_SIG",
        position_mm=(60.0, 60.0),
        drill_diameter_mm=2.0,
        pad_diameter_mm=3.0,
        plated=True,
    )
    base_pcb_config.mounting_holes = [mh_orphan]
    violations_orphan_mh = checker.check_net_continuity(wiring_mock)
    assert any(v.rule_name == "MOUNTING_HOLE_DISCONNECTED" and v.net_or_zone == "MH_CTRL" for v in violations_orphan_mh)

    # Case 8: All segments properly connected inline
    base_pcb_config.mounting_holes = []
    tp_connected = TestPointModel(
        name="TP_CTRL",
        net="CTRL_SIG",
        position_mm=(2.0, 0.0),  # directly along tr_partial
        pad_diameter_mm=1.0,
        hole_diameter_mm=0.5,
    )
    base_pcb_config.test_points = [tp_connected]
    violations_all_ok = checker.check_net_continuity(wiring_mock)
    assert len(violations_all_ok) == 0, f"Expected 0 violations, got {violations_all_ok}"
