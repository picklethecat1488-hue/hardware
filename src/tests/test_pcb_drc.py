"""Unit tests for PCB Design Rules Checking (DRC) engine."""

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
from provider.pcb.drc import PCBDesignRulesChecker, DRCSeverity


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
