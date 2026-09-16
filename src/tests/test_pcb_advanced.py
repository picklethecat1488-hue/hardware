"""Unit tests for advanced PCB features: CPWG impedance, RF/Display DRC, CAD boundary containment, Eye diagram, and SensorHub."""

import json
from pathlib import Path
import pytest
from model.pcb import (
    LayerType,
    StackupLayerModel,
    StackupModel,
    NetClassModel,
    DifferentialPairModel,
    CapacitiveElectrodeModel,
    PCBConfig,
)
from model.wiring import Wiring, FootprintModel, PinModel, PinSide, NetModel
from provider.pcb.drc import PCBDesignRulesChecker, DRCSeverity
from provider.pcb.exporter import PCBExporter
from provider.pcb.eye_diagram import EyeDiagramSimulator, EyeDiagramConfig, generate_prbs9
from provider.pcb.rerun_logger import log_drc_report, log_eye_diagram
from projects.sensor_hub.provider import SensorHubProvider


@pytest.fixture
def advanced_pcb_stackup() -> StackupModel:
    """Create a 6-layer high-speed stackup with microstrip and coplanar waveguide capabilities."""
    return StackupModel(
        finish="ENIG",
        layers=[
            StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.1
            ),
            StackupLayerModel(name="In1.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
            StackupLayerModel(
                name="Core1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.450, dielectric_constant=4.3
            ),
            StackupLayerModel(name="In2.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.200, dielectric_constant=3.4
            ),
            StackupLayerModel(name="In3.Cu", layer_type=LayerType.POWER, thickness_mm=0.035),
            StackupLayerModel(
                name="Core2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.450, dielectric_constant=4.3
            ),
            StackupLayerModel(name="In4.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg3", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.1
            ),
            StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
        ],
    )


def test_coplanar_waveguide_impedance(advanced_pcb_stackup: StackupModel):
    """Verify coplanar waveguide (CPWG) characteristic impedance calculation around 50 Ohms."""
    z_cpwg = advanced_pcb_stackup.calculate_coplanar_waveguide_impedance(
        width_mm=0.160,
        ground_gap_mm=0.200,
        copper_thickness_mm=0.035,
        height_mm=0.100,
        dielectric_er=4.1,
    )
    # Standard CPWG at these dimensions yields ~48 to 55 Ohms
    assert 45.0 <= z_cpwg <= 60.0


def test_drc_rf_cpwg_impedance_check(advanced_pcb_stackup: StackupModel):
    """Verify DRC detection of RF CPWG impedance mismatch."""
    rf_net_class = NetClassModel(
        name="RF_ANTENNA",
        trace_width_mm=0.800,  # Far too wide for 50 Ohm CPWG with 0.2mm gap
        clearance_mm=0.200,
        via_dia_mm=0.45,
        via_drill_mm=0.20,
        interface_type="rf",
        coplanar_waveguide=True,
        ground_gap_mm=0.200,
    )
    config = PCBConfig(
        name="RFBoard",
        board_type="rigid",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        net_classes=[rf_net_class],
    )
    checker = PCBDesignRulesChecker(config)
    report = checker.check_all()

    assert not report.passed
    assert any(
        v.rule_name == "RF_CPWG_IMPEDANCE_MISMATCH" and v.severity == DRCSeverity.ERROR for v in report.violations
    )


def test_drc_display_impedance_target_check(advanced_pcb_stackup: StackupModel):
    """Verify warning when display interface differential pair deviates from standard 100 Ohm range."""
    display_net_class = NetClassModel(
        name="MIPI_DSI",
        trace_width_mm=0.120,
        clearance_mm=0.150,
        via_dia_mm=0.45,
        via_drill_mm=0.20,
        interface_type="display",
        diff_pairs=[
            DifferentialPairModel(
                name="MIPI_DATA0",
                pos_net="MIPI_D0_P",
                neg_net="MIPI_D0_N",
                target_impedance_ohms=50.0,  # Invalid: standard display diff impedance is ~100 Ohm
            )
        ],
    )
    config = PCBConfig(
        name="DisplayBoard",
        board_type="rigid",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        net_classes=[display_net_class],
    )
    checker = PCBDesignRulesChecker(config)
    report = checker.check_all()

    assert any(
        v.rule_name == "DISPLAY_IMPEDANCE_TARGET_INVALID" and v.severity == DRCSeverity.WARNING
        for v in report.violations
    )


def test_drc_boundary_containment_checking(advanced_pcb_stackup: StackupModel):
    """Verify DRC detects components violating board edge clearance or lying outside boundary."""
    config = PCBConfig(
        name="BoundaryBoard",
        board_type="rigid",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
    )
    checker = PCBDesignRulesChecker(config)

    from model.wiring import LabelModel

    # Component placed too close to board edge (half_w=30.0, component at x=29.0 with width 4.0 extends to 31.0)
    fp_violating = FootprintModel(
        name="U_EDGE",
        package="SOIC-8",
        position=(29.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        dimensions=(4.0, 4.0, 1.0),
        label=LabelModel(text="U_EDGE", position=(0.0, 0.0, 0.0), align=("center", "center")),
        pins=[],
    )
    fp_inside = FootprintModel(
        name="U_SAFE",
        package="0805",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        dimensions=(2.0, 1.25, 0.8),
        label=LabelModel(text="U_SAFE", position=(0.0, 0.0, 0.0), align=("center", "center")),
        pins=[],
    )
    from unittest.mock import MagicMock

    wiring = MagicMock()
    wiring.footprints = [fp_violating, fp_inside]
    wiring.nets = []

    violations = checker.check_boundary_containment(wiring.footprints, edge_clearance_mm=0.5)
    assert len(violations) >= 1
    assert violations[0].rule_name == "BOUNDARY_CLEARANCE_VIOLATION"
    assert violations[0].net_or_zone == "U_EDGE"


def test_drc_netlist_connectivity_checking(advanced_pcb_stackup: StackupModel):
    """Verify DRC detects single-pin nets and short circuits between nets."""
    from unittest.mock import MagicMock

    config = PCBConfig(
        name="NetlistBoard",
        board_type="rigid",
        dimensions_mm=(50.0, 50.0, 1.6),
        stackup=advanced_pcb_stackup,
    )
    checker = PCBDesignRulesChecker(config)

    # Single-pin floating net
    net_floating = NetModel(name="FLOAT_NET", color="#000", pins=[("U1", "PIN1")])
    # Short circuit: two different nets connecting to the exact same pin
    net_pwr = NetModel(name="VCC", color="#f00", pins=[("U1", "PWR_PIN"), ("U2", "PWR_PIN")])
    net_gnd = NetModel(name="GND", color="#000", pins=[("U1", "PWR_PIN"), ("U2", "GND_PIN")])

    wiring = MagicMock()
    wiring.footprints = []
    wiring.nets = [net_floating, net_pwr, net_gnd]
    violations = checker.check_netlist_connectivity(wiring)

    assert any(v.rule_name == "SINGLE_PIN_NET" and v.net_or_zone == "FLOAT_NET" for v in violations)
    assert any(v.rule_name == "SHORT_CIRCUIT_DETECTED" and "U1.PWR_PIN" in v.net_or_zone for v in violations)


def test_export_capacitive_config_json(tmp_path: Path, advanced_pcb_stackup: StackupModel):
    """Verify export of firmware capacitive sensing register configuration to JSON."""
    from unittest.mock import MagicMock

    sensor1 = CapacitiveElectrodeModel(
        name="WATER_LOW",
        channel_id=0,
        area_mm=(10.0, 15.0),
        pitch_mm=1.0,
        gap_mm=0.25,
        threshold_raw=2100,
        tx_pin="GPIO_TX0",
        rx_pin="ADC_RX0",
    )
    sensor2 = CapacitiveElectrodeModel(
        name="WATER_HIGH",
        channel_id=1,
        area_mm=(10.0, 15.0),
        pitch_mm=1.0,
        gap_mm=0.25,
        threshold_raw=2600,
        tx_pin="GPIO_TX1",
        rx_pin="ADC_RX1",
    )
    config = PCBConfig(
        name="CapSenseBoard",
        board_type="flex",
        dimensions_mm=(30.0, 80.0, 0.20),
        stackup=advanced_pcb_stackup,
        capacitive_sensors=[sensor1, sensor2],
    )
    wiring = MagicMock()
    wiring.footprints = []
    wiring.nets = []
    exporter = PCBExporter(config, wiring)

    out_file = tmp_path / "capacitive_config.json"
    res = exporter.export_capacitive_config_json(out_file)

    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["board"] == "CapSenseBoard"
    assert data["channel_count"] == 2
    assert len(data["channels"]) == 2
    ch0 = data["channels"][0]
    assert ch0["name"] == "WATER_LOW"
    assert ch0["channel_id"] == 0
    assert ch0["threshold_raw"] == 2100
    assert ch0["tx_pin"] == "GPIO_TX0"
    assert ch0["rx_pin"] == "ADC_RX0"


def test_eye_diagram_simulation():
    """Verify PCIe Gen4 Eye Diagram simulation, PRBS-9 generation, and figure of merit calculations."""
    bits = generate_prbs9(num_bits=511)
    assert len(bits) == 511
    assert set(bits).issubset({0, 1})

    eye_cfg = EyeDiagramConfig(
        pcie_gen=4,
        data_rate_gts=16.0,
        trace_length_mm=80.0,
        characteristic_impedance_ohms=85.0,
        trace_width_mm=0.14,
        dielectric_constant=4.2,
        loss_tangent=0.018,
        ctle_peaking_db=6.0,
    )
    sim = EyeDiagramSimulator(eye_cfg)
    result = sim.simulate()

    assert result.pcie_gen == 4
    assert result.data_rate_gts == 16.0
    assert result.eye_height_mv > 0.0
    assert result.eye_width_ps > 0.0
    assert result.eye_width_ui > 0.0
    assert len(result.folded_traces) > 0
    assert "mask_polygon" in result.compliance_mask


def test_rerun_logger_drc_and_eye(advanced_pcb_stackup: StackupModel):
    """Verify rerun logger executes without errors when rerun is present or absent."""
    config = PCBConfig(
        name="RerunBoard",
        board_type="rigid",
        dimensions_mm=(50.0, 50.0, 1.6),
        stackup=advanced_pcb_stackup,
    )
    checker = PCBDesignRulesChecker(config)
    report = checker.check_all()

    # Should not raise any exceptions
    log_drc_report(report)

    eye_cfg = EyeDiagramConfig(trace_length_mm=50.0)
    eye_res = EyeDiagramSimulator(eye_cfg).simulate()
    log_eye_diagram(eye_res)


def test_sensor_hub_provider_cad_and_assembly():
    """Verify SensorHubProvider builds valid 3D shapes, loads measurements, and populates Room."""
    from provider import Room, Mode

    provider = SensorHubProvider()
    assert provider.settings.board_width == 60.0
    assert provider.settings.board_length == 90.0

    # Build parts
    carrier = provider.carrier_board("carrier_board", None, Mode.DEFAULT)
    assert carrier.part is not None
    assert carrier.part.is_valid()

    tail = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    assert tail.part is not None
    assert tail.part.is_valid()

    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert enclosure.part is not None
    assert enclosure.part.is_valid()

    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid.part is not None
    assert lid.part.is_valid()

    # Populate view room
    room = Room(config=provider.app_config, materials=provider.materials)
    provider.view_product(room, Mode.DEFAULT)
    assert "carrier_board" in room
    assert "flex_tail" in room
    assert "enclosure_bottom" in room

    # Check PCB config loading
    assert provider.pcb_config is not None
    assert provider.pcb_config.name == "SensorHub_Carrier"
    assert provider.pcb_config.board_type == "rigid-flex"
    assert len(provider.pcb_config.stackup.layers) == 11
    assert len(provider.pcb_config.capacitive_sensors) == 2
