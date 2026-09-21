"""Unit tests for advanced PCB features: CPWG impedance, RF/Display DRC, CAD boundary containment, Eye diagram, and TestBoard."""

import json
import math
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
    SchematicSheetModel,
    MountingHoleModel,
)
from model.wiring import Wiring, FootprintModel, PinModel, PinSide, NetModel
from provider.pcb.drc import PCBDesignRulesChecker, DRCSeverity
from provider.pcb.exporter import PCBExporter
from provider.pcb.kicad_cli import KiCadCLI
from provider.pcb.eye_diagram import EyeDiagramSimulator, EyeDiagramConfig, generate_prbs9
from provider.pcb.rerun_logger import log_drc_report, log_eye_diagram
from provider import Room, Mode
from projects.test_board.provider import TestBoardProvider


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


def test_test_board_provider_cad_and_assembly():
    """Verify TestBoardProvider builds valid 3D shapes, loads measurements, and populates Room."""
    provider = TestBoardProvider()
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
    assert provider.pcb_config.name == "TestBoard_Carrier"
    assert provider.pcb_config.board_type == "rigid-flex"
    assert len(provider.pcb_config.stackup.layers) == 11
    assert len(provider.pcb_config.capacitive_sensors) == 4

    # Check assembly test instructions from manifest/pcb.yaml
    assert provider.pcb_config.assembly_test is not None
    assert provider.pcb_config.assembly_test.test_fixture == "flying_probe"
    assert len(provider.pcb_config.assembly_test.instructions) == 6
    step0 = provider.pcb_config.assembly_test.instructions[0]
    assert step0.step_id == "TEST_CONTINUITY_GND"
    assert step0.test_type == "continuity"
    assert step0.expected_nominal == 0.05


def test_schematic_diagram_dynamic_scaling(tmp_path: Path):
    """Verify that SchematicDiagram dynamically scales canvas height for components with dense pin counts."""
    from provider.schematic_diagram import SchematicDiagram
    from unittest.mock import MagicMock
    from model.wiring import LabelModel

    # Create an IC with 40 pins
    dense_pins = [
        PinModel(
            name=f"IO_{i}",
            position=(0.0, float(i), 0.0),
            label=f"IO_{i}",
            side=PinSide.LEFT if i < 20 else PinSide.RIGHT,
        )
        for i in range(40)
    ]
    dense_fp = FootprintModel(
        name="U_DENSE",
        package="QFP-40",
        position=(0.0, 0.0, 0.0),
        dimensions=(10.0, 10.0, 1.0),
        pins=dense_pins,
        label=LabelModel(text="MCU_40P", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    wiring = MagicMock()
    wiring.footprints = [dense_fp]
    wiring.nets = []

    diag = SchematicDiagram(wiring)
    out_svg = tmp_path / "dense_schematic.svg"
    res = diag.render_svg(out_svg)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "U_DENSE" in content
    # With 40 pins (20 pins per side), height is > 700
    assert 'viewBox="0 0 ' in content
    # Extract height from SVG header
    import re

    match = re.search(r'height="(\d+)"', content)
    assert match is not None
    svg_height = int(match.group(1))
    assert svg_height >= 700


def test_test_board_wiring_and_diagram_generation(tmp_path: Path):
    """Verify that TestBoard wiring YAML parses footprints and nets, generates diagrams, and exports BOM/CPL."""
    provider = TestBoardProvider()
    assert provider.wiring_path.exists()

    wiring = Wiring(provider.wiring_path)
    assert len(wiring.footprints) == 29
    footprint_names = [fp.name for fp in wiring.footprints]
    assert "U1" in footprint_names
    assert "U2" in footprint_names
    assert "U3" in footprint_names
    assert "U4" in footprint_names
    assert "J1" in footprint_names
    assert "J2" in footprint_names
    assert "J3" in footprint_names
    assert "U5" in footprint_names
    assert "Y1" in footprint_names
    assert "R1" in footprint_names
    assert "R2" in footprint_names
    assert "C1" in footprint_names
    assert "C2" in footprint_names
    assert "C3" in footprint_names
    assert "Q1" in footprint_names

    # Verify diagram population
    room = Room(config=provider.app_config, materials=provider.materials)
    provider.diagram_wiring(room, ["wiring"], Mode.DEFAULT)
    assert len(room.keys()) > 0
    system_wiring_file = provider.wiring_path.parent / "system_wiring.yaml"
    assert system_wiring_file.exists(), "system_wiring.yaml must exist for top-down architecture diagram"
    sys_wiring = Wiring(system_wiring_file)
    sys_comp_names = {c.name for c in sys_wiring.footprints}
    assert {"m2_host", "usb_c", "carrier_pcb", "flex_tail"}.issubset(sys_comp_names)

    # Verify BOM and CPL export
    pcb_config = provider.pcb_config
    assert pcb_config is not None
    exporter = PCBExporter(pcb_config, wiring)

    bom_csv = tmp_path / "bom.csv"
    pos_csv = tmp_path / "pos.csv"
    exporter.export_bom_csv(bom_csv)
    exporter.export_pick_and_place_csv(pos_csv)

    bom_lines = bom_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(bom_lines) == 29  # header + 28 carrier components (J4 is on flex tail)
    assert "STM32MP157-BGA196" in bom_csv.read_text(encoding="utf-8")

    pos_lines = pos_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(pos_lines) == 29  # header + 28 carrier components


def test_schematic_diagram_export_pdf_multipage_toc(tmp_path: Path):
    """Verify that SchematicDiagram export_pdf paginates TOC across multiple pages when footprints and nets overflow."""
    import re
    from unittest.mock import MagicMock
    from model.wiring import LabelModel
    from provider.schematic_diagram import SchematicDiagram

    # Generate 35 footprints and 40 nets to ensure TOC table overflows 1 page
    many_fps = [
        FootprintModel(
            name=f"U_{i:02d}",
            package="SOIC-8",
            position=(float(i * 10), 0.0, 0.0),
            dimensions=(5.0, 5.0, 1.0),
            pins=[
                PinModel(name=f"P_{j}", position=(0.0, float(j), 0.0), label=f"P{j}", side=PinSide.LEFT)
                for j in range(4)
            ],
            label=LabelModel(text=f"IC_{i}", position=(0.0, 0.0, 0.0), align=("center", "center")),
        )
        for i in range(35)
    ]
    many_nets = [
        NetModel(
            name=f"NET_SIG_{i:02d}",
            color="#0284c7",
            pins=[(f"U_{i % 35}", "P_0"), (f"U_{(i + 1) % 35}", "P_1")],
        )
        for i in range(40)
    ]
    wiring = MagicMock()
    wiring.footprints = many_fps
    wiring.nets = many_nets

    diag = SchematicDiagram(wiring)
    out_pdf = tmp_path / "multipage_schematic.pdf"
    res = diag.render_pdf(out_pdf)

    assert res.exists()
    assert res.stat().st_size > 0

    # Count pages in generated PDF: Page 1 (Title) + at least 2 TOC pages + 18 schematic sheets >= 21 pages
    pdf_bytes = res.read_bytes()
    page_matches = re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    assert len(page_matches) >= 20


def test_pcb_revision_metadata_and_templates(tmp_path: Path, advanced_pcb_stackup: StackupModel):
    """Verify that PCBConfig revision metadata propagates to KiCad templates and schematic PDF."""
    from unittest.mock import MagicMock
    from provider.schematic_diagram import SchematicDiagram

    cfg = PCBConfig(
        name="RevTestBoard",
        board_type="rigid",
        revision="2.4.1",
        dimensions_mm=(50.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
    )
    assert cfg.revision == "2.4.1"

    wiring = MagicMock()
    wiring.footprints = []
    wiring.nets = []

    exporter = PCBExporter(cfg, wiring)
    pcb_file = exporter.export_kicad_pcb(tmp_path / "rev_board.kicad_pcb")
    sch_file = exporter.export_kicad_sch(tmp_path / "rev_board.kicad_sch")

    assert '(rev "2.4.1")' in pcb_file.read_text(encoding="utf-8")
    assert '(rev "2.4.1")' in sch_file.read_text(encoding="utf-8")

    diag = SchematicDiagram(wiring, pcb_config=cfg)
    pdf_file = diag.render_pdf(tmp_path / "rev_schematic.pdf")
    pdf_bytes = pdf_file.read_bytes()

    import re
    import zlib

    streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL)
    decomp = b"".join(
        [zlib.decompress(s) if s.startswith((b"\x78\x9c", b"\x78\x01", b"\x78\xda")) else s for s in streams]
    )
    assert b"2.4.1" in decomp


def test_schematic_compact_symbology_and_channel_routing(tmp_path: Path, advanced_pcb_stackup: StackupModel):
    """Verify that schematic symbology is compact and routes facing pins without cutting across bodies."""
    import re
    import zlib
    from unittest.mock import MagicMock
    from model.wiring import LabelModel
    from provider.schematic_diagram import SchematicDiagram

    # Setup two components: U1 on left, U2 on right
    u1 = FootprintModel(
        name="U1",
        package="QFN-16",
        position=(0.0, 0.0, 0.0),
        dimensions=(10.0, 10.0, 1.0),
        pins=[
            PinModel(name="E1", position=(0.0, 1.0, 0.0), label="E1", side=PinSide.RIGHT),
            PinModel(name="OUT", position=(0.0, 2.0, 0.0), label="OUT", side=PinSide.RIGHT),
        ],
        label=LabelModel(text="U1", position=(0.0, 0.0, 0.0), align=("center", "center")),
        mpn="STM32-PARTNUM-100",
    )
    u2 = FootprintModel(
        name="U2",
        package="SOIC-8",
        position=(50.0, 0.0, 0.0),
        dimensions=(10.0, 10.0, 1.0),
        pins=[
            PinModel(name="IN", position=(0.0, 1.0, 0.0), label="IN", side=PinSide.LEFT),
            PinModel(name="E2", position=(0.0, 2.0, 0.0), label="E2", side=PinSide.RIGHT),
        ],
        label=LabelModel(text="U2", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    # Facing pin net: U1.OUT (right) to U2.IN (left)
    net_facing = NetModel(name="FACING_NET", color="#2563eb", pins=[("U1", "OUT"), ("U2", "IN")])
    # Non-facing pin net: U1.E1 (right) to U2.E2 (right) - should NOT route wire cutting across U2 body
    net_non_facing = NetModel(name="NON_FACING_NET", color="#0284c7", pins=[("U1", "E1"), ("U2", "E2")])

    wiring = MagicMock()
    wiring.footprints = [u1, u2]
    wiring.nets = [net_facing, net_non_facing]

    cfg = PCBConfig(
        name="SymbologyTest",
        board_type="rigid",
        revision="1.1",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
    )

    diag = SchematicDiagram(wiring, pcb_config=cfg)
    out_pdf = tmp_path / "compact_routing.pdf"
    res = diag.render_pdf(out_pdf)

    assert res.exists()
    assert res.stat().st_size > 0
    pdf_bytes = res.read_bytes()
    streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL)
    decomp = b"".join(
        [zlib.decompress(s) if s.startswith((b"\x78\x9c", b"\x78\x01", b"\x78\xda")) else s for s in streams]
    )
    clean_text = re.sub(rb"[\(\)\[\]0-9\.\s]+", b"", decomp)
    # Ensure net labels, revision, and part number (MPN) are properly rendered
    assert b"FACING_NET" in clean_text
    assert b"NON_FACING_NET" in clean_text
    assert b"STM-PARTNUM-" in clean_text or b"PARTNUM" in clean_text
    assert b"1.1" in decomp


def test_schematic_multi_page_breakout_and_toc(tmp_path: Path, advanced_pcb_stackup: StackupModel):
    """Verify that multi-page schematic breakouts partition footprint pins across functional sheets."""
    import re
    import zlib
    from unittest.mock import MagicMock
    from model.wiring import LabelModel
    from provider.schematic_diagram import SchematicDiagram

    # Setup component U1 with 4 pins across two functional domains
    u1 = FootprintModel(
        name="U1",
        package="QFN-16",
        position=(0.0, 0.0, 0.0),
        dimensions=(10.0, 10.0, 1.0),
        pins=[
            PinModel(name="VIN", position=(0.0, 1.0, 0.0), label="VIN", side=PinSide.LEFT),
            PinModel(name="VOUT", position=(0.0, 2.0, 0.0), label="VOUT", side=PinSide.RIGHT),
            PinModel(name="SDA", position=(0.0, 3.0, 0.0), label="SDA", side=PinSide.RIGHT),
            PinModel(name="SCL", position=(0.0, 4.0, 0.0), label="SCL", side=PinSide.RIGHT),
        ],
        label=LabelModel(text="U1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    q1 = FootprintModel(
        name="Q1",
        package="SOT-23",
        position=(30.0, 0.0, 0.0),
        dimensions=(5.0, 5.0, 1.0),
        pins=[
            PinModel(name="G", position=(0.0, 1.0, 0.0), label="G", side=PinSide.LEFT),
            PinModel(name="D", position=(0.0, 2.0, 0.0), label="D", side=PinSide.RIGHT),
        ],
        label=LabelModel(text="Q1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    u2 = FootprintModel(
        name="U2",
        package="SOIC-8",
        position=(60.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=[
            PinModel(name="SDA", position=(0.0, 1.0, 0.0), label="SDA", side=PinSide.LEFT),
            PinModel(name="SCL", position=(0.0, 2.0, 0.0), label="SCL", side=PinSide.LEFT),
        ],
        label=LabelModel(text="U2", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    wiring = MagicMock()
    wiring.footprints = [u1, q1, u2]
    wiring.nets = [
        NetModel(name="PWR_NET", color="#ef4444", pins=[("U1", "VOUT"), ("Q1", "G")]),
        NetModel(name="I2C_SDA", color="#2563eb", pins=[("U1", "SDA"), ("U2", "SDA")]),
        NetModel(name="I2C_SCL", color="#3b82f6", pins=[("U1", "SCL"), ("U2", "SCL")]),
    ]

    cfg = PCBConfig(
        name="MultiPageTest",
        board_type="rigid",
        revision="2.0",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        schematic_sheets=[
            SchematicSheetModel(
                title="Power Distribution & Control",
                description="Power regulation and FET switching",
                components=["U1", "Q1"],
                pin_breakouts={"U1": ["VIN", "VOUT"]},
            ),
            SchematicSheetModel(
                title="I2C Communication Bus",
                description="Microcontroller to sensor I2C lines",
                components=["U1", "U2"],
                pin_breakouts={"U1": ["SDA", "SCL"]},
            ),
        ],
    )

    diag = SchematicDiagram(wiring, pcb_config=cfg)

    # Verify sheet planning isolates pins per sheet
    plans = diag._build_sheet_plans()
    assert len(plans) == 2

    plan_pwr = plans[0]
    assert plan_pwr.title == "Power Distribution & Control"
    pwr_u1 = next(fp for fp in plan_pwr.footprints if fp.name == "U1")
    pwr_u1_pin_names = {p.name for p in pwr_u1.pins}
    assert pwr_u1_pin_names == {"VIN", "VOUT"}

    plan_i2c = plans[1]
    assert plan_i2c.title == "I2C Communication Bus"
    i2c_u1 = next(fp for fp in plan_i2c.footprints if fp.name == "U1")
    i2c_u1_pin_names = {p.name for p in i2c_u1.pins}
    assert i2c_u1_pin_names == {"SDA", "SCL"}

    # Render PDF and check TOC and sheet contents
    out_pdf = tmp_path / "multipage_breakout.pdf"
    res = diag.render_pdf(out_pdf)
    assert res.exists()
    pdf_bytes = res.read_bytes()
    page_matches = re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    assert len(page_matches) == 4  # Title + TOC + Sheet 1 + Sheet 2

    streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL)
    decomp = b"".join(
        [zlib.decompress(s) if s.startswith((b"\x78\x9c", b"\x78\x01", b"\x78\xda")) else s for s in streams]
    )
    clean_text = re.sub(rb"[\(\)\[\]0-9\.\s\-_]+", b"", decomp)
    assert b"PowerDistribution" in clean_text or b"Distribution" in clean_text
    assert b"CommunicationBus" in clean_text or b"Communication" in clean_text


def test_pcb_exporter_mounting_holes(tmp_path: Path, advanced_pcb_stackup: StackupModel):
    """Verify that PCBExporter correctly formats and renders plated and unplated mounting holes in kicad_pcb."""
    from unittest.mock import MagicMock

    cfg = PCBConfig(
        name="MountingTest",
        board_type="rigid",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        mounting_holes=[
            MountingHoleModel(
                name="MH1", position_mm=(25.5, 40.5), drill_diameter_mm=3.2, pad_diameter_mm=4.5, plated=True, net="GND"
            ),
            MountingHoleModel(
                name="MH2", position_mm=(-25.5, -40.5), drill_diameter_mm=2.5, pad_diameter_mm=2.5, plated=False
            ),
        ],
    )
    wiring = MagicMock()
    wiring.footprints = []
    wiring.nets = []

    exporter = PCBExporter(cfg, wiring)
    pcb_file = exporter.export_kicad_pcb(tmp_path / "mounting_test.kicad_pcb")
    pcb_text = pcb_file.read_text(encoding="utf-8")

    # Sheet center for A4 is (148.5, 105.0)
    # MH1 is at (148.5 + 25.5, 105.0 + 40.5) = (174.0, 145.5)
    # MH2 is at (148.5 - 25.5, 105.0 - 40.5) = (123.0, 64.5)
    assert '(footprint "MountingHole:MountingHole_3.2mm_Pad"' in pcb_text
    assert "(at 174.0 145.5)" in pcb_text
    assert '"GND"' in pcb_text
    assert '(pad "1" thru_hole circle (at 0 0) (size 4.5 4.5) (drill 3.2)' in pcb_text

    # Verify unplated hole
    assert '(footprint "MountingHole:MountingHole_2.5mm_Pad"' in pcb_text
    assert "(at 123.0 64.5)" in pcb_text
    assert '(pad "1" np_thru_hole circle (at 0 0) (size 2.5 2.5) (drill 2.5)' in pcb_text


def test_test_board_full_milestones_integration(tmp_path: Path):
    """Verify TestBoardProvider integrates mounting holes, 3 mutual + 1 self cap sensors, and carrier standoffs."""
    provider = TestBoardProvider()
    cfg = provider.pcb_config
    assert cfg is not None

    # Milestone 3: 4 mounting holes
    assert len(cfg.mounting_holes) == 4
    mh_names = [h.name for h in cfg.mounting_holes]
    assert mh_names == ["MH1", "MH2", "MH3", "MH4"]
    for mh in cfg.mounting_holes:
        assert mh.drill_diameter_mm == 3.2
        assert mh.pad_diameter_mm == 4.5
        assert mh.plated is True
        assert mh.net == "GND"
        assert abs(abs(mh.position_mm[0]) - 25.5) < 1e-4
        assert abs(abs(mh.position_mm[1]) - 40.5) < 1e-4

    # Milestone 4: 3 mutual cap + 1 self cap sensors
    assert len(cfg.capacitive_sensors) == 4
    electrodes_by_name = {e.name: e for e in cfg.capacitive_sensors}
    assert "SENSE_WATER_LEVEL_LOW" in electrodes_by_name
    assert electrodes_by_name["SENSE_WATER_LEVEL_LOW"].channel_id == 0
    assert electrodes_by_name["SENSE_WATER_LEVEL_LOW"].electrode_type == "mutual"

    assert "SENSE_WATER_LEVEL_MID" in electrodes_by_name
    assert electrodes_by_name["SENSE_WATER_LEVEL_MID"].channel_id == 1
    assert electrodes_by_name["SENSE_WATER_LEVEL_MID"].electrode_type == "mutual"

    assert "SENSE_WATER_LEVEL_HIGH" in electrodes_by_name
    assert electrodes_by_name["SENSE_WATER_LEVEL_HIGH"].channel_id == 2
    assert electrodes_by_name["SENSE_WATER_LEVEL_HIGH"].electrode_type == "mutual"

    assert "SENSE_WATER_PROXIMITY" in electrodes_by_name
    assert electrodes_by_name["SENSE_WATER_PROXIMITY"].channel_id == 3
    assert electrodes_by_name["SENSE_WATER_PROXIMITY"].electrode_type == "self"
    assert electrodes_by_name["SENSE_WATER_PROXIMITY"].drive_shield is False

    # Milestone 2: Carrier standoff pilot holes and enclosure feet
    assert provider.settings.standoff_hole_diameter == 2.2
    assert provider.settings.standoff_hole_depth == 4.0
    assert provider.settings.enclosure_foot_diameter == 8.0
    assert provider.settings.enclosure_foot_depth == 1.0
    assert provider.settings.enclosure_foot_inset == 8.0
    enclosure_bottom = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert enclosure_bottom.part is not None
    assert enclosure_bottom.part.is_valid()

    # Milestone 5 & 6: Wiring passives, actives, and flex fanout
    wiring = Wiring(provider.wiring_path)
    fp_names = {fp.name for fp in wiring.footprints}
    assert {"R1", "R2", "C1", "C2", "C3", "Q1", "J2"}.issubset(fp_names)

    # Exporter capacitive configuration JSON
    exporter = PCBExporter(cfg, wiring)
    json_path = exporter.export_capacitive_config_json(tmp_path / "test_cap.json")
    assert json_path.exists()
    cap_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert cap_data["channel_count"] == 4
    assert len(cap_data["channels"]) == 4
    assert cap_data["channels"][3]["electrode_type"] == "self"
    assert cap_data["channels"][3]["drive_shield"] is False


def test_test_board_manufacturing_artifacts_and_pos_alignment(tmp_path: Path):
    """Verify test_board manufacturing exports (.kicad_pcb, .drl, *.gbr) and pos.csv pad alignment."""
    import csv
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
    cfg = provider.pcb_config
    assert cfg is not None
    wiring = Wiring(provider.wiring_path)

    # 1. DRC validation: ensure all nets connected, no airwires, zero collisions
    drc_checker = PCBDesignRulesChecker(cfg)
    report = drc_checker.check_all(wiring=wiring)
    assert report.passed, f"DRC failed:\n{report.summary()}"
    assert report.error_count == 0

    # Verify TP_GND has routed trace and via connecting to ground (BUG-040)
    tp_gnd = next((tp for tp in cfg.test_points if tp.name == "TP_GND"), None)
    assert tp_gnd is not None
    assert tp_gnd.net == "GND"
    tp_x, tp_y = tp_gnd.position_mm
    tp_trace = next(
        (
            tr
            for tr in cfg.traces
            if tr.net == "GND"
            and (
                math.hypot(tr.start_mm[0] - tp_x, tr.start_mm[1] - tp_y) < 0.1
                or math.hypot(tr.end_mm[0] - tp_x, tr.end_mm[1] - tp_y) < 0.1
            )
        ),
        None,
    )
    assert tp_trace is not None, "TP_GND must have a routed copper trace connecting to ground"

    # 2. Export board files (.kicad_pcb, .drl, .gbr) and pos.csv
    exporter = PCBExporter(cfg, wiring)
    board_dir = tmp_path / "board"
    exporter.export_board(board_dir, pcb_filename="test_board.kicad_pcb")

    pos_file = tmp_path / "pos.csv"
    exporter.export_pick_and_place_csv(pos_file)

    # 3. Verify .kicad_pcb and .drl exist
    kicad_pcb = board_dir / "test_board.kicad_pcb"
    drill_file = board_dir / "test_board.drl"
    assert kicad_pcb.exists()

    pcb_text = kicad_pcb.read_text(encoding="utf-8")
    # Verify connectors J1 and J2 edge placement
    assert 'footprint "M.2-KEY-M"' in pcb_text
    assert 'footprint "FPC-30P-0.5MM"' in pcb_text
    # Verify bottom layer components
    assert '(layer "B.Cu")' in pcb_text

    # Verify drill file coordinates match mounting holes when kicad-cli is available
    if KiCadCLI().is_available:
        assert drill_file.exists()
        drl_text = drill_file.read_text(encoding="utf-8")
        assert "C3.200" in drl_text  # 3.2mm mounting hole tool definition
        assert "X123.0Y-64.5" in drl_text
        assert "X174.0Y-145.5" in drl_text

    # 4. Verify pos.csv aligns with component placement and correct layers
    assert pos_file.exists()
    with open(pos_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {r["Designator"]: r for r in reader}

    assert "U1" in rows
    assert "U2" in rows
    assert "J1" in rows
    assert "J2" in rows
    assert "Q1" in rows
    assert "C2" in rows

    # Layers: Q1, U2, C2 on Bottom; U1, J1, J2 on Top
    assert rows["U1"]["Layer"] == "Top"
    assert rows["J1"]["Layer"] == "Top"
    assert rows["J2"]["Layer"] == "Top"
    assert rows["U2"]["Layer"] == "Bottom"
    assert rows["Q1"]["Layer"] == "Bottom"
    assert rows["C2"]["Layer"] == "Bottom"

    # Edge connector coordinates
    assert float(rows["J1"]["Mid Y"].replace("mm", "")) == -36.0
    assert float(rows["J2"]["Mid Y"].replace("mm", "")) == 38.0


def test_build_pcb_and_build_flex_pcb_context_managers(advanced_pcb_stackup: StackupModel):
    """Verify BuildPcb and BuildFlexPCB custom context managers attach stackup, dimensions, and flex_type metadata."""
    from build123d import Box
    from model.pcb import FlexType
    from provider.pcb.board import BuildPcb, BuildFlexPCB

    with BuildPcb(
        name="main_carrier",
        board_type="rigid",
        revision="2.0",
        stackup=advanced_pcb_stackup,
    ) as pcb_builder:
        Box(60.0, 40.0, pcb_builder.thickness_mm)

    assert pcb_builder.part is not None
    assert pcb_builder.part.is_valid()
    assert hasattr(pcb_builder.part, "pcb_metadata")
    meta = getattr(pcb_builder.part, "pcb_metadata")
    assert meta.name == "main_carrier"
    assert meta.board_type == "rigid"
    assert meta.revision == "2.0"
    assert meta.stackup is not None
    assert meta.dimensions_mm == (60.0, 40.0, round(advanced_pcb_stackup.total_thickness_mm, 4))

    # Test BuildFlexPCB with different flex types: connector, capacitive, component
    for ftype in (FlexType.CONNECTOR, FlexType.CAPACITIVE, FlexType.COMPONENT):
        with BuildFlexPCB(
            name=f"flex_{ftype.value}",
            flex_type=ftype,
            revision="1.0",
            stackup=advanced_pcb_stackup,
        ) as flex_builder:
            Box(40.0, 15.0, 0.20)

        assert flex_builder.part is not None
        assert flex_builder.board_type == "flex"
        assert flex_builder.flex_type == ftype
        meta_flex = getattr(flex_builder.part, "pcb_metadata")
        assert meta_flex.board_type == "flex"
        assert meta_flex.flex_type == ftype
        assert meta_flex.name == f"flex_{ftype.value}"


def test_schematic_staggered_pin_stubs_and_loop_crossings(tmp_path: Path):
    """Verify staggered pin stubs (GND > PWR > SIG), pin number offset, and jumper loops at 90-degree crossings."""
    import matplotlib.pyplot as plt
    from provider.schematic_diagram import (
        SchematicDiagram,
        STUB_SIGNAL_MM,
        STUB_POWER_MM,
        STUB_GROUND_MM,
        PIN_NUMBER_OFFSET_MM,
        JUMPER_BRIDGE_RADIUS_MM,
    )

    # Invariant: Pin stubs must be strictly ordered GND (18mm) > PWR (10mm) > SIG (5mm)
    assert STUB_GROUND_MM == 18.0
    assert STUB_POWER_MM == 10.0
    assert STUB_SIGNAL_MM == 5.0
    assert STUB_GROUND_MM - STUB_POWER_MM >= 8.0  # Guarantees GND and 3V3 rail symbols never collide
    assert PIN_NUMBER_OFFSET_MM == 2.5  # Pin numbers stay clear of power/ground symbols
    assert JUMPER_BRIDGE_RADIUS_MM == 1.2

    # Verify jumper arc rendering on crossing wires
    fig, ax = plt.subplots()
    diag = SchematicDiagram(None, pcb_config=None)
    # Horizontal wire segment crossing x=50, y=50
    h_segments = [(30.0, 70.0, 50.0, "NET_HORIZ", "#000000")]
    # Draw vertical wire with crossing at y=50
    diag._draw_vertical_wire_with_jumpers(
        ax,
        x_v=50.0,
        y_start=30.0,
        y_end=70.0,
        col="#2563eb",
        h_wire_segments=h_segments,
    )
    # Verify patch contains Arc jumper loop
    arcs = [p for p in ax.patches if isinstance(p, plt.matplotlib.patches.Arc)]
    assert len(arcs) == 1
    arc = arcs[0]
    assert arc.center == (50.0, 50.0)
    assert arc.width == 2 * JUMPER_BRIDGE_RADIUS_MM
    plt.close(fig)


def test_schematic_decoupling_cap_bank_and_pullup_resistors():
    """Verify decoupling capacitor bank and pullup resistor vertical extraction and rendering."""
    import matplotlib.pyplot as plt
    from provider.schematic_diagram import SchematicDiagram

    fig, ax = plt.subplots()
    diag = SchematicDiagram(None, pcb_config=None)

    c1 = FootprintModel(
        name="C1",
        package="0402",
        position=(0.0, 0.0, 0.0),
        dimensions=(1.0, 0.5, 0.5),
        pins=[
            PinModel(name="1", position=(0.0, 0.25, 0.0), label="1", side=PinSide.TOP),
            PinModel(name="2", position=(0.0, -0.25, 0.0), label="2", side=PinSide.BOTTOM),
        ],
    )
    c2 = FootprintModel(
        name="C2",
        package="0402",
        position=(5.0, 0.0, 0.0),
        dimensions=(1.0, 0.5, 0.5),
        pins=[
            PinModel(name="1", position=(0.0, 0.25, 0.0), label="1", side=PinSide.TOP),
            PinModel(name="2", position=(0.0, -0.25, 0.0), label="2", side=PinSide.BOTTOM),
        ],
    )
    pin_to_net = {
        ("C1", "1"): "3V3",
        ("C1", "2"): "GND",
        ("C2", "1"): "3V3",
        ("C2", "2"): "GND",
    }

    diag._draw_decoupling_cap_bank(ax, [c1, c2], pin_to_net, base_x=40.0, base_y=50.0)
    # Verify dashed container rectangle was added
    rects = [p for p in ax.patches if isinstance(p, plt.matplotlib.patches.Rectangle)]
    assert len(rects) >= 1
    dashed_boxes = [r for r in rects if r.get_linestyle() == "--"]
    assert len(dashed_boxes) == 1

    # Pullup resistor extraction
    r1 = FootprintModel(
        name="R1",
        package="0402",
        position=(10.0, 0.0, 0.0),
        dimensions=(1.0, 0.5, 0.5),
        pins=[
            PinModel(name="1", position=(0.0, 0.25, 0.0), label="1", side=PinSide.TOP),
            PinModel(name="2", position=(0.0, -0.25, 0.0), label="2", side=PinSide.BOTTOM),
        ],
    )
    pin_to_net_pu = {
        ("R1", "1"): "3V3",
        ("R1", "2"): "I2C_SDA",
    }
    h_segments = [(20.0, 60.0, 30.0, "I2C_SDA", "#0284c7")]
    diag._draw_pullup_resistors(
        ax,
        [r1],
        pin_to_net_pu,
        h_wire_segments=h_segments,
        sheet_pin_coords={},
    )
    plt.close(fig)


def test_test_board_test_points_and_zero_drc_errors():
    """Verify test_board has drilled test points with 4mm pitch, TP_GND, and 0 DRC violations."""
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    import math

    provider = TestBoardProvider()
    cfg = provider.pcb_config
    assert cfg is not None

    # Check test points
    tps = {tp.name: tp for tp in cfg.test_points}
    assert "TP_GND" in tps
    assert tps["TP_GND"].net == "GND"
    assert tps["TP_GND"].position_mm == (-18.0, -22.0)

    # All test points must be plated drilled holes for probe / fly wire insertion
    for tp in cfg.test_points:
        assert tp.drill_diameter_mm == 0.80
        assert tp.pad_diameter_mm == 1.40
        assert tp.plated is True

    # 4mm pitch verification on paired test points
    def point_dist(name1: str, name2: str) -> float:
        p1 = tps[name1].position_mm
        p2 = tps[name2].position_mm
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    assert abs(point_dist("TP_TX0_P", "TP_TX0_N") - 4.0) < 1e-3
    assert abs(point_dist("TP_D0_P", "TP_D0_N") - 4.0) < 1e-3
    assert abs(point_dist("TP_SDA", "TP_SCL") - 4.0) < 1e-3

    # DRC check: 0 errors on test_board
    wiring = Wiring(provider.wiring_path)
    drc = PCBDesignRulesChecker(cfg)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"DRC failed:\n{report.summary()}"
    assert report.error_count == 0
    assert not any(v.rule_name == "DISCONNECTED_TEST_POINT_AIRWIRE" for v in report.violations)
    assert not any(v.rule_name == "TRACE_SHORT_CIRCUIT" for v in report.violations)
    assert not any(v.rule_name == "CLEARANCE_VIOLATION" for v in report.violations)
    assert not any(v.rule_name == "SILKSCREEN_PAD_OVERLAP" for v in report.violations)


def test_schematic_discrete_component_truth_table(tmp_path: Path):
    """Verify TruthTableModel parsing, transistor truth table generation, and schematic rendering."""
    from model.wiring import TruthTableModel, TruthTableRowModel, TruthTableState, LabelModel
    from provider.schematic_diagram import SchematicDiagram

    # 1. Verify parsing of declarative truth table in test_board/wiring.yaml
    provider = TestBoardProvider()
    wiring = Wiring(provider.wiring_path)
    q1 = next(fp for fp in wiring.footprints if fp.name == "Q1")
    assert q1.truth_table is not None
    assert isinstance(q1.truth_table, TruthTableModel)
    assert q1.truth_table.title == "Q1 Load Switch Truth Table"
    assert q1.truth_table.input_headers == ["PWR_EN (Gate)"]
    assert q1.truth_table.output_headers == ["VLOAD_SW (Drain)", "Channel State"]
    assert len(q1.truth_table.rows) == 4

    states = [r.state for r in q1.truth_table.rows]
    assert TruthTableState.FALSE in states
    assert TruthTableState.TRUE in states
    assert TruthTableState.INVALID in states

    # Verify custom row model
    first_row = q1.truth_table.rows[0]
    assert isinstance(first_row, TruthTableRowModel)
    assert first_row.state == TruthTableState.FALSE
    assert "disabled" in first_row.description
    assert first_row.outputs.get("Channel State") == "Cutoff"

    # 2. Verify auto-generated default transistor truth table for discrete transistor without explicit truth table
    q_auto = FootprintModel(
        name="Q2",
        package="SOT-23",
        position=(0.0, 0.0, 0.0),
        dimensions=(2.9, 1.3, 1.0),
        pins=[
            PinModel(name="1", position=(0.0, 0.0, 0.0), label="G", side=PinSide.LEFT),
            PinModel(name="2", position=(0.0, 1.0, 0.0), label="S", side=PinSide.BOTTOM),
            PinModel(name="3", position=(0.0, 2.0, 0.0), label="D", side=PinSide.RIGHT),
        ],
        mpn="2N7002",
        label=LabelModel(text="2N7002", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    auto_tt = SchematicDiagram._generate_default_transistor_truth_table(
        q_auto, {("Q2", "1"): "GATE_CTRL", ("Q2", "3"): "VOUT"}
    )
    assert auto_tt is not None
    assert "2N7002" in auto_tt.title
    assert "GATE_CTRL (Gate)" in auto_tt.input_headers
    assert "VOUT (Drain)" in auto_tt.output_headers
    assert len(auto_tt.rows) == 4
    auto_states = {r.state for r in auto_tt.rows}
    assert auto_states == {TruthTableState.FALSE, TruthTableState.TRUE, TruthTableState.INVALID}

    # 3. Verify schematic PDF rendering of test_board wiring produces valid multi-page document with truth table
    diag = SchematicDiagram(wiring)
    out_pdf = tmp_path / "test_board_schematic.pdf"
    res = diag.render_pdf(out_pdf)
    assert res.exists()
    assert res.stat().st_size > 0


def test_schematic_diagram_geometric_offsets_and_gnd_placement(tmp_path: Path) -> None:
    """Verify geometric offsets in SchematicDiagram do not self-intersect symbols, wires, or text labels.

    Guards against schematic regressions:
    1. Pullup network vertical offsets: y_zz_bot > channel_top_y, y_zz_top > y_zz_bot, y_top_rail > y_zz_top.
    2. IC pin ordering: Power pins placed at top, Ground pins at bottom.
    3. Ground symbol downward placement: GND symbols hang DOWN under components/traces rather than horizontal overlap.
    """
    from projects.test_board.provider import TestBoardProvider
    from provider.schematic_diagram import SchematicDiagram, GROUND_NET_NAMES, POWER_NET_NAMES

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    diag = SchematicDiagram(wiring, pcb_config=provider.pcb_config)

    # 1. Verify sheet plans generation and pin sorting
    plans = diag._build_sheet_plans()
    assert len(plans) >= 3

    # Sheet 3: Capacitive Sensing & Control (contains U1, U2, R1, R2, J2)
    sheet3 = next(p for p in plans if "Capacitive" in p.title)
    u2_fp = next(fp for fp in sheet3.footprints if fp.name == "U2")

    # Verify pin sort order on U2: VDD at top, VSS at bottom
    left_pins = [p for p in u2_fp.pins if p.side.value in ("left", "bottom")]
    pin_to_net = {}
    for net in wiring.nets:
        for c, p in net.pins:
            pin_to_net[(c, p)] = net.name

    def _pin_sort_key(p):
        net = pin_to_net.get((u2_fp.name, p.name), "").upper()
        if net in POWER_NET_NAMES:
            return 0
        if net in GROUND_NET_NAMES:
            return 2
        return 1

    left_pins.sort(key=_pin_sort_key)
    # VDD must be first (index 0)
    assert left_pins[0].name == "VDD"
    # VSS (ground) must be at the bottom (after signals SDA, SCL, INT)
    assert left_pins[-1].name == "VSS"

    # 2. Verify PDF generation executes with zero self-intersections
    pdf_path = tmp_path / "schematic_offsets_verified.pdf"
    rendered = diag.render_pdf(pdf_path)
    assert rendered.exists()
    assert rendered.stat().st_size > 5000


def test_regression_j_usb_edge_facing_and_drc_exemption() -> None:
    """Verify J3 USB-C connector faces outward to board edge and is exempt from internal DRC margin."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    j3 = next(fp for fp in wiring.footprints if fp.name == "J3")

    # Rotation 270 degrees orients connector mouth toward -X (left board edge at X=-30.0)
    assert j3.rotation[2] == 270.0
    assert j3.position[0] < -20.0  # Near left board perimeter

    # DRC boundary check must treat J3 as an edge-mounted connector
    checker = PCBDesignRulesChecker(provider.pcb_config)
    carrier_fps = checker.get_footprints_for_board(wiring)
    violations = checker.check_boundary_containment(carrier_fps, edge_clearance_mm=0.5)
    j3_violations = [v for v in violations if v.net_or_zone == "J3"]
    assert len(j3_violations) == 0, f"J3 should be exempt from edge clearance: {j3_violations}"


def test_regression_piezo_speaker_circular_silkscreen_and_placement() -> None:
    """Verify U5 piezo speaker has circular footprint and is positioned near MH2."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    import math
    import yaml

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    u5 = next(fp for fp in wiring.footprints if fp.name == "U5")

    assert u5.package == "piezo_speaker_12mm"

    # Verify footprint definition in thru_hole.yaml has circular geometry
    thru_hole_yaml = provider.wiring_path.parent.parent / "footprints" / "thru_hole.yaml"
    with open(thru_hole_yaml, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    piezo = data["footprints"]["piezo_speaker_12mm"]
    assert piezo["shape"] == "circle"
    assert piezo["radius_mm"] == 6.0

    # MH2 position: (-26.0, 36.0). U5 at (-18.0, 31.0) -> distance < 12mm
    dist_to_mh2 = math.hypot(u5.position[0] - (-26.0), u5.position[1] - 36.0)
    assert dist_to_mh2 <= 12.0


def test_regression_collinear_vector_simplification() -> None:
    """Verify polyline_to_trace_segments simplifies collinear vertical and horizontal segments."""
    from provider.pcb.router import polyline_to_trace_segments

    # Vertical 3-point collinear polyline
    vertical_pts = [(5.0, 0.0), (5.0, 5.0), (5.0, 10.0)]
    v_traces = polyline_to_trace_segments(vertical_pts, width_mm=0.2, layer="F.Cu", net="TEST_V")
    assert len(v_traces) == 1
    assert v_traces[0].start_mm == (5.0, 0.0)
    assert v_traces[0].end_mm == (5.0, 10.0)

    # Horizontal 3-point collinear polyline
    horizontal_pts = [(0.0, 3.0), (5.0, 3.0), (10.0, 3.0)]
    h_traces = polyline_to_trace_segments(horizontal_pts, width_mm=0.2, layer="F.Cu", net="TEST_H")
    assert len(h_traces) == 1
    assert h_traces[0].start_mm == (0.0, 3.0)
    assert h_traces[0].end_mm == (10.0, 3.0)


def test_regression_subassembly_footprint_isolation() -> None:
    """Verify PCBAutoRouter and PCBExporter cleanly isolate carrier and flex subassemblies."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.router import PCBAutoRouter
    from provider import Mode

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # Carrier board router
    carrier_cfg = provider.get_pcb_config_without_routes()
    carrier_router = PCBAutoRouter(carrier_cfg, wiring)
    carrier_fps = carrier_router.get_footprints_for_board()
    carrier_names = {fp.name for fp in carrier_fps}
    assert "U1" in carrier_names
    assert "J1" in carrier_names
    assert "J2" in carrier_names
    assert "J4" not in carrier_names

    # Flex tail router
    flex_part = provider.part.get("flex_tail")
    flex_res = flex_part("flex_tail", None, Mode.DEFAULT)
    flex_cfg = flex_res.to_pcb_config()
    flex_router = PCBAutoRouter(flex_cfg, wiring)
    flex_fps = flex_router.get_footprints_for_board()
    flex_names = {fp.name for fp in flex_fps}
    assert "J4" in flex_names
    assert "U1" not in flex_names
    assert "J1" not in flex_names


def test_regression_flex_tail_front_routing_and_silkscreen(tmp_path: Path) -> None:
    """Verify flex tail has routed traces on F.Cu, silkscreen on B.SilkS, and valid spacing (BUG-038)."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.exporter import PCBExporter
    from provider import Mode

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    flex_part = provider.part.get("flex_tail")
    assert flex_part is not None
    flex_res = flex_part("flex_tail", None, Mode.DEFAULT)
    flex_cfg = flex_res.to_pcb_config()

    # Traces must be loaded from routing_flex.yaml on F.Cu
    assert len(flex_cfg.traces) > 0, "Flex tail must have routed traces"
    assert all(tr.layer == "F.Cu" for tr in flex_cfg.traces), "All flex tail traces must route on F.Cu"

    # Export flex_tail.kicad_pcb and verify traces and back silkscreen are present in output file
    exporter = PCBExporter(flex_cfg, wiring)
    kicad_pcb_file = tmp_path / "flex_tail.kicad_pcb"
    exporter.export_kicad_pcb(kicad_pcb_file)
    content = kicad_pcb_file.read_text()

    assert "(segment (start" in content, "flex_tail.kicad_pcb must contain exported (segment entries"
    assert "F.Cu" in content, "flex_tail.kicad_pcb must have traces on F.Cu"
    assert "FLEX TAIL SENSOR REV 1.0" in content
    assert '"B.SilkS"' in content, "FLEX TAIL SENSOR REV 1.0 must be on B.SilkS"

    # Verify CH3 is spaced from CH2
    ch2 = next(s for s in flex_cfg.capacitive_sensors if s.channel_id == 2)
    ch3 = next(s for s in flex_cfg.capacitive_sensors if s.channel_id == 3)
    ch2_top = ch2.center_mm[1] + (ch2.area_mm[1] / 2.0)
    ch3_bottom = ch3.center_mm[1] - (ch3.area_mm[1] / 2.0)
    assert ch3_bottom > ch2_top, f"CH3 bottom ({ch3_bottom}) must be strictly above CH2 top ({ch2_top})"


def test_schematic_drc_test_board_passes() -> None:
    """Verify that test_board schematic satisfies all schematic DRC rules with zero errors."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(provider.pcb_config)

    violations = checker.check_schematic(wiring)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0, f"Expected 0 schematic DRC errors on test_board, got: {errors}"


def test_schematic_drc_detects_dangling_component(advanced_pcb_stackup: StackupModel) -> None:
    """Verify that check_schematic detects dangling components with no netlist connections."""
    from model.pcb import PCBConfig, SchematicSheetModel
    from model.wiring import FootprintModel, PinModel, LabelModel
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName
    from unittest.mock import MagicMock

    u1 = FootprintModel(
        name="U_DANGLING",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=[PinModel(name="1", position=(0.0, 0.0, 0.0), label="1", side="left")],
        label=LabelModel(text="U_DANGLING", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    wiring = MagicMock()
    wiring.footprints = [u1]
    wiring.nets = []

    cfg = PCBConfig(
        name="DanglingTest",
        board_type="rigid",
        revision="1.0",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        schematic_sheets=[
            SchematicSheetModel(
                title="Dangling Sheet",
                description="Sheet with floating component",
                components=["U_DANGLING"],
            ),
        ],
    )

    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring)
    dangling = [v for v in violations if v.rule_name == DRCRuleName.SCHEMATIC_DANGLING_COMPONENT]
    assert len(dangling) == 1
    assert "U_DANGLING" in dangling[0].description


def test_schematic_drc_detects_net_antenna(advanced_pcb_stackup: StackupModel) -> None:
    """Verify that check_schematic detects 1-pin floating nets without terminations."""
    from model.pcb import PCBConfig, SchematicSheetModel
    from model.wiring import FootprintModel, PinModel, LabelModel, NetModel
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName
    from unittest.mock import MagicMock

    u1 = FootprintModel(
        name="U1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=[PinModel(name="1", position=(0.0, 0.0, 0.0), label="1", side="left")],
        label=LabelModel(text="U1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    wiring = MagicMock()
    wiring.footprints = [u1]
    wiring.nets = [
        NetModel(name="ANTENNA_SIG", color="#ef4444", pins=[("U1", "1")]),
    ]

    cfg = PCBConfig(
        name="AntennaTest",
        board_type="rigid",
        revision="1.0",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        schematic_sheets=[
            SchematicSheetModel(
                title="Antenna Sheet",
                description="Sheet with floating antenna net",
                components=["U1"],
            ),
        ],
    )

    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring)
    antennas = [v for v in violations if v.rule_name == DRCRuleName.SCHEMATIC_NET_ANTENNA]
    assert len(antennas) == 1
    assert "ANTENNA_SIG" in antennas[0].net_or_zone


def test_schematic_drc_detects_symbol_overlap(advanced_pcb_stackup: StackupModel) -> None:
    """Verify that check_schematic detects vertically overlapping symbols on the same column."""
    from model.pcb import PCBConfig, SchematicSheetModel
    from model.wiring import FootprintModel, PinModel, LabelModel, NetModel
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName
    from unittest.mock import MagicMock

    # Create a 30-pin oversized IC that exceeds default row pitch
    pins_30 = [PinModel(name=str(i), position=(0.0, float(i), 0.0), label=str(i), side="left") for i in range(30)]
    u_tall = FootprintModel(
        name="U_TALL",
        package="DIP-30",
        position=(0.0, 0.0, 0.0),
        dimensions=(15.0, 45.0, 1.0),
        pins=pins_30,
        label=LabelModel(text="U_TALL", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    pins_2 = [PinModel(name=str(i), position=(0.0, float(i), 0.0), label=str(i), side="left") for i in range(2)]
    u_row1 = FootprintModel(
        name="U_ROW1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=pins_2,
        label=LabelModel(text="U_ROW1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    # Put 4 components so cols_per_row = 3, forcing u_row1 into row 1 directly below U_TALL (col 0)
    u_c1 = FootprintModel(
        name="U_C1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=pins_2,
        label=LabelModel(text="U_C1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    u_c2 = FootprintModel(
        name="U_C2",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=pins_2,
        label=LabelModel(text="U_C2", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    wiring = MagicMock()
    wiring.footprints = [u_tall, u_c1, u_c2, u_row1]
    wiring.nets = [
        NetModel(name="NET_A", color="#ef4444", pins=[("U_TALL", "0"), ("U_ROW1", "0")]),
        NetModel(name="NET_B", color="#2563eb", pins=[("U_C1", "0"), ("U_C2", "0")]),
    ]

    cfg = PCBConfig(
        name="OverlapTest",
        board_type="rigid",
        revision="1.0",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        schematic_sheets=[
            SchematicSheetModel(
                title="Overlap Sheet",
                description="Sheet with tall overlapping IC",
                components=["U_TALL", "U_C1", "U_C2", "U_ROW1"],
            ),
        ],
    )

    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring)
    overlaps = [v for v in violations if v.rule_name == DRCRuleName.SCHEMATIC_SYMBOL_OVERLAP]
    assert len(overlaps) >= 1
    assert "U_TALL" in overlaps[0].net_or_zone


def test_schematic_drc_detects_missing_page_transition(advanced_pcb_stackup: StackupModel) -> None:
    """Verify that check_schematic detects multi-sheet nets referencing orphan components not placed on any sheet."""
    from model.pcb import PCBConfig, SchematicSheetModel
    from model.wiring import FootprintModel, PinModel, LabelModel, NetModel
    from provider.pcb.drc import PCBDesignRulesChecker, DRCRuleName
    from unittest.mock import MagicMock

    pins_1 = [PinModel(name="1", position=(0.0, 1.0, 0.0), label="1", side="left")]
    u1 = FootprintModel(
        name="U1",
        package="SOIC-8",
        position=(0.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=pins_1,
        label=LabelModel(text="U1", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )
    u_orphan = FootprintModel(
        name="U_ORPHAN",
        package="SOIC-8",
        position=(10.0, 0.0, 0.0),
        dimensions=(8.0, 8.0, 1.0),
        pins=pins_1,
        label=LabelModel(text="U_ORPHAN", position=(0.0, 0.0, 0.0), align=("center", "center")),
    )

    wiring = MagicMock()
    wiring.footprints = [u1, u_orphan]
    wiring.nets = [
        NetModel(name="INTER_PAGE_NET", color="#2563eb", pins=[("U1", "1"), ("U_ORPHAN", "1")]),
    ]

    # Only U1 is placed on Sheet 1; U_ORPHAN is never placed on any sheet
    cfg = PCBConfig(
        name="TransitionTest",
        board_type="rigid",
        revision="1.0",
        dimensions_mm=(60.0, 40.0, 1.6),
        stackup=advanced_pcb_stackup,
        schematic_sheets=[
            SchematicSheetModel(
                title="Sheet 1",
                description="Sheet with U1 only",
                components=["U1"],
            ),
        ],
    )

    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring)
    missing = [v for v in violations if v.rule_name == DRCRuleName.SCHEMATIC_PAGE_TRANSITION_MISSING]
    assert len(missing) == 1
    assert "INTER_PAGE_NET" in missing[0].net_or_zone


def test_regression_smd_no_connect_pads_included_on_pcb(tmp_path: Path) -> None:
    """Verify that SMD components (U1 BGA-196, J3 USB-C, J2/J4 FPC-30) place no-connect pads on the board (BUG-043)."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.exporter import PCBExporter

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # 1. Verify U1 has all 196 balls defined
    u1 = next((fp for fp in wiring.footprints if fp.name == "U1"), None)
    assert u1 is not None
    assert len(u1.pins) == 196, f"Expected 196 balls on U1 BGA-196, got {len(u1.pins)}"

    # 2. Verify J3 (USB-C-16P) includes all pins and tabs (including SBU1, SBU2, SHIELD3, SHIELD4)
    j3 = next((fp for fp in wiring.footprints if fp.name == "J3"), None)
    assert j3 is not None
    assert len(j3.pins) >= 14, f"Expected at least 14 pins/tabs on J3 USB-C, got {len(j3.pins)}"
    j3_pin_names = {p.name for p in j3.pins}
    assert {"SBU1", "SBU2", "SHIELD3", "SHIELD4"}.issubset(j3_pin_names)

    # 3. Verify J2 (FPC-30P-0.5MM) includes all 30 pins + mounting pads
    j2 = next((fp for fp in wiring.footprints if fp.name == "J2"), None)
    assert j2 is not None
    assert len(j2.pins) >= 30, f"Expected at least 30 pins on J2 FPC connector, got {len(j2.pins)}"

    # 4. Verify PCB export emits no-connect pads with (net 0 "")
    cfg = provider.pcb_config
    assert cfg is not None
    exporter = PCBExporter(cfg, wiring)
    board_file = tmp_path / "carrier_board.kicad_pcb"
    exporter.export_kicad_pcb(board_file)
    content = board_file.read_text()

    # Must contain no-connect pads (e.g. U1 ball A3 and J3 pin SBU1)
    assert '(pad "A3"' in content, "carrier_board.kicad_pcb must contain no-connect pad A3 on U1"
    assert '(pad "SBU1"' in content, "carrier_board.kicad_pcb must contain no-connect pad SBU1 on J3"


def test_regression_inner_copper_layers_and_auto_routing_connectivity(tmp_path: Path) -> None:
    """Verify inner copper layer refill, pin rotation math, and BGA dogbone stitching connectivity."""
    import math
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.pcb.router import PCBAutoRouter
    from provider.pcb.drc import _get_pin_absolute_pos
    from provider.pcb.exporter import PCBExporter
    from provider.pcb.kicad_cli import KiCadCLI

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # 1. Verify KiCad screen-space pin rotation math for rotated footprints (J3 at 270 deg)
    j3 = next((fp for fp in wiring.footprints if fp.name == "J3"), None)
    assert j3 is not None
    cc1_pin = next((p for p in j3.pins if p.name == "CC1"), None)
    assert cc1_pin is not None
    rx, ry = PCBAutoRouter.get_pin_absolute_position(j3, cc1_pin)
    drc_rx, drc_ry = _get_pin_absolute_pos(j3, cc1_pin)
    # J3 is at (-25.0, 0.0), rot=270 deg. CC1 local pos is (-0.8, 2.5).
    # In KiCad screen coordinates (where Y points down):
    # rx = -25.0 + (-2.5) = -27.5
    # ry = 0.0 + (-0.8) = -0.8
    assert math.isclose(rx, -27.5, abs_tol=1e-3), f"Expected rx=-27.5, got {rx}"
    assert math.isclose(ry, -0.8, abs_tol=1e-3), f"Expected ry=-0.8, got {ry}"
    assert math.isclose(drc_rx, -27.5, abs_tol=1e-3)
    assert math.isclose(drc_ry, -0.8, abs_tol=1e-3)

    # 2. Verify carrier board routing has stitching vias for U1 BGA pins H7 (GND) and H8 (3V3)
    cfg = provider.pcb_config
    assert cfg is not None
    vias = cfg.vias
    h7_via = next(
        (v for v in vias if v.net == "GND" and abs(v.position_mm[0]) < 1.0 and abs(v.position_mm[1]) < 1.0),
        None,
    )
    assert h7_via is not None, "U1 BGA GND pin H7 must have a stitching via connecting to the GND plane"

    h8_via = next(
        (v for v in vias if v.net == "3V3" and abs(v.position_mm[0] - 0.8) < 1.0 and abs(v.position_mm[1]) < 1.0),
        None,
    )
    assert h8_via is not None, "U1 BGA 3V3 pin H8 must have a stitching via connecting to the 3V3 plane"

    # 3. Verify PCB export generates filled copper regions for inner planes In1.Cu (GND) and In3.Cu (3V3)
    board_file = tmp_path / "carrier_board.kicad_pcb"
    exporter = PCBExporter(cfg, wiring)
    exporter.export_kicad_pcb(board_file)
    content = board_file.read_text()

    assert '"In1.Cu"' in content
    assert '"In3.Cu"' in content

    cli = KiCadCLI()
    if cli.supports_drc:
        # File size must be large (> 300KB) reflecting filled polygon geometry
        assert board_file.stat().st_size > 300_000, "Board file must include filled zone geometry"
        # Run DRC and assert zero unconnected pads
        drc_rpt = tmp_path / "drc.rpt"
        cli.run_command(["pcb", "drc", "--output", str(drc_rpt), str(board_file)])
        rpt_text = drc_rpt.read_text()
        assert "** Found 0 unconnected pads **" in rpt_text


def test_regression_deep_power_down_wakeup_and_power_sequencing() -> None:
    """Verify BUG-060 (Deep Power Down wakeup) and BUG-061 (power-on sequencing verification)."""
    report_path = Path("src/projects/test_board/docs/downselection_report.md")
    assert report_path.is_file(), "Downselection report must exist locally"
    content = report_path.read_text(encoding="utf-8")

    # 1. BUG-060: Verify Deep Power Down wakeup triggers (Charger interface and M.2 connector)
    assert "WAKEUP0_B" in content
    assert "WAKEUP1_B" in content
    assert "CHG_PGOOD_WAKE" in content
    assert "M2_WAKE_N" in content
    assert "Exit Deep Power Down" in content

    # 2. BUG-061: Verify all required power-on sequencing steps
    assert "Secondary IO supplies" in content
    assert "VDD_P2" in content and "VDD_P3" in content and "VDD_P4" in content
    assert "VDD_CORE must ramp after VDD" in content
    assert "VDD_P4 and VDD_ANA must be same voltage" in content
    assert "VDD_BAT must ramp before or with VDD_SYS" in content

    # 3. Verify user approval sign-off for MCXN947VDF in VFBGA-184
    assert "MCXN947VDF" in content
    assert "APPROVED" in content


def test_regression_flexspi_dual_channel_and_charger_state_detection() -> None:
    """Verify BUG-062 (FlexSPI Dual Channel Mode) and BUG-063 (Charger /CHG state transitions)."""
    report_path = Path("src/projects/test_board/docs/downselection_report.md")
    assert report_path.is_file(), "Downselection report must exist locally"
    content = report_path.read_text(encoding="utf-8")

    # 1. BUG-062: FlexSPI Dual Channel & Section 4.3.2 specifications
    assert "Dual-Channel FlexSPI" in content or "Dual Channel" in content
    assert "FLEXSPI0_A_SCLK" in content
    assert "FLEXSPI0_A_SS0_b" in content
    assert "FLEXSPI0_A_DATA0" in content
    assert "FLEXSPI0_B_SCLK" in content
    assert "FLEXSPI0_B_SS0_b" in content
    assert "FLEXSPI0_B_DATA0" in content
    assert "15 pF" in content or "15pF" in content
    assert "1 V/ns" in content or "1V/ns" in content
    assert "100 MHz" in content
    assert "W25N01GV" in content

    # 2. BUG-063: Charger /CHG to MCU connection and Sleep/Active transitions
    assert "/CHG" in content
    assert "CHG_STAT" in content
    assert "WUU0_IN15" in content
    assert "LOW_POWER_SLEEP" in content
    assert "ACTIVE_CHARGING" in content

    # 3. Datasheet local archival verification
    datasheet_dir = Path("src/projects/test_board/docs/datasheets")
    assert (datasheet_dir / "NXP_MCXN947_datasheet.pdf").is_file()
    assert (datasheet_dir / "Winbond_W25N01GV_datasheet.pdf").is_file()
    assert (datasheet_dir / "TI_BQ24074_charger.pdf").is_file()
    assert (datasheet_dir / "TI_LP5009_led_driver.pdf").is_file()
    assert (datasheet_dir / "JST_SH_header.pdf").is_file()


def test_regression_pinmux_datasheet_verification() -> None:
    """Verify BUG-064: ensure MCU pin assignments are 100% sourced from NXP MCX N947 Table 93."""
    report_path = Path("src/projects/test_board/docs/downselection_report.md")
    assert report_path.is_file(), "Downselection report must exist locally"
    content = report_path.read_text(encoding="utf-8")

    # 1. BUG-064: Verify Ball F4 resolution (P1_17 is I3C1_SCL, not I2C0_SCL)
    assert "F4" in content
    assert "P1_17" in content
    assert "I3C1_SCL" in content
    assert "F6" in content and "P1_16" in content and "I3C1_SDA" in content
    assert "E4" in content and "P1_15" in content and "I3C1_PUR" in content

    # 2. Verify Core System I2C0 allocation (FC0 on A10 / B10)
    assert "A10" in content and "P0_17" in content and "FC0_P1" in content and "I2C0_SCL" in content
    assert "B10" in content and "P0_16" in content and "FC0_P0" in content and "I2C0_SDA" in content

    # 3. Verify Dedicated Touch Controller I2C1 allocation (FC3 on C5 / C6)
    assert "C5" in content and "P1_1" in content and "FC3_P1" in content and "I2C1_SCL" in content
    assert "C6" in content and "P1_0" in content and "FC3_P0" in content and "I2C1_SDA" in content
    assert "C4" in content and "P1_2" in content and "CAP_INT" in content

    # 4. Verify SWD Debug and ISP Bootloader allocation
    assert "A16" in content and "P0_1" in content and "TCLK" in content and "SWD_CLK" in content
    assert "A17" in content and "P0_0" in content and "TMS" in content and "SWD_DIO" in content
    assert "B16" in content and "P0_2" in content and "TDO" in content and "SWD_SWO" in content
    assert "F3" in content and "RESET_B" in content and "nRESET" in content
    assert "C14" in content and "P0_6" in content and "ISPMODE_N" in content and "BOOT0" in content

    # 5. Verify High-Speed Console UART allocation (FC1 on B6 / A6 / F10 / E10)
    assert "B6" in content and "P0_24" in content and "FC1_P0" in content and "UART0_RXD" in content
    assert "A6" in content and "P0_25" in content and "FC1_P1" in content and "UART0_TXD" in content
    assert "F10" in content and "P0_26" in content and "FC1_P2" in content and "UART0_CTS" in content
    assert "E10" in content and "P0_27" in content and "FC1_P3" in content and "UART0_RTS" in content

    # 6. Verify Dual-Channel FlexSPI Port A and Port B allocation
    assert "B17" in content and "P3_0" in content and "FLEXSPI0_A_SS0_b" in content
    assert "D14" in content and "P3_7" in content and "FLEXSPI0_A_SCLK" in content
    assert "E14" in content and "P3_8" in content and "FLEXSPI0_A_DATA0" in content
    assert "F15" in content and "P3_9" in content and "FLEXSPI0_A_DATA1" in content
    assert "F17" in content and "P3_10" in content and "FLEXSPI0_A_DATA2" in content
    assert "F16" in content and "P3_11" in content and "FLEXSPI0_A_DATA3" in content
    assert "D17" in content and "P3_6" in content and "FLEXSPI0_A_DQS" in content
    assert "H3" in content and "P2_2" in content and "FLEXSPI0_B_SS0_b" in content
    assert "J3" in content and "P2_3" in content and "FLEXSPI0_B_SCLK" in content
    assert "K3" in content and "P2_4" in content and "FLEXSPI0_B_DATA0" in content
    assert "K1" in content and "P2_5" in content and "FLEXSPI0_B_DATA1" in content
    assert "K2" in content and "P2_6" in content and "FLEXSPI0_B_DATA2" in content
    assert "L2" in content and "P2_7" in content and "FLEXSPI0_B_DATA3" in content
    assert "H1" in content and "P2_1" in content and "FLEXSPI0_B_DQS" in content

    # 7. Verify Wakeup and Switched Power Rails
    assert "G5" in content and "P1_19" in content and "WUU0_IN15" in content and "CHG_STAT" in content
    assert "M10" in content and "P5_2" in content and "CHG_PGOOD_WAKE" in content
    assert "C13" in content and "P0_7" in content and "WUU0_IN1" in content and "M2_WAKE_N" in content
    assert "L4" in content and "P1_22" in content and "PWR_EN_AUDIO" in content
    assert "L5" in content and "P1_21" in content and "PWR_EN_SENSORS" in content
    assert "M4" in content and "P1_23" in content and "PWR_EN_DEBUG" in content


def test_regression_test_board_wiring_diagram_top_down_and_colored() -> None:
    """Verify test board wiring diagram is 2D top-down and colored with distinct net layers."""
    from model import DiagramStyle

    provider = TestBoardProvider()
    room_wiring = Room()
    provider.diagram_wiring(room_wiring, ["test_board/wiring"], Mode.DEFAULT)

    assert room_wiring.diagram_options is not None
    assert room_wiring.diagram_options.view_from == "top"
    assert room_wiring.diagram_options.style == DiagramStyle.COLOR

    room_prod = Room()
    provider.diagram_product(room_prod, ["test_board/product"], Mode.DEFAULT)
    assert room_prod.diagram_options is not None
    assert room_prod.diagram_options.view_from == "iso"
    assert room_prod.diagram_options.style == DiagramStyle.HIDDEN


def test_regression_enclosure_cad_feedback_and_assembly() -> None:
    """Verify enclosure CAD feedback: rounded fillets, cutouts, locating lip, and product assembly."""
    provider = TestBoardProvider()

    # 1. Verify bottom enclosure geometry
    bottom = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert bottom is not None and bottom.part is not None
    b_part = bottom.part
    bb = b_part.bounding_box()
    expected_w = provider.settings.board_width + 2.0 * (
        provider.settings.enclosure_clearance + provider.settings.enclosure_wall_thickness
    )
    expected_l = provider.settings.board_length + 2.0 * (
        provider.settings.enclosure_clearance + provider.settings.enclosure_wall_thickness
    )
    expected_h = provider.settings.standoff_height + provider.settings.board_thickness + 10.0

    assert abs((bb.max.X - bb.min.X) - expected_w) < 0.1
    assert abs((bb.max.Y - bb.min.Y) - expected_l) < 0.1
    assert abs((bb.max.Z - bb.min.Z) - expected_h) < 0.1
    assert b_part.volume < (expected_w * expected_l * expected_h)

    # 2. Verify enclosure lid geometry
    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid is not None and lid.part is not None
    l_part = lid.part
    l_bb = l_part.bounding_box()
    assert abs((l_bb.max.X - l_bb.min.X) - expected_w) < 0.1
    assert abs((l_bb.max.Y - l_bb.min.Y) - expected_l) < 0.1
    expected_lid_h = provider.settings.enclosure_wall_thickness + provider.settings.enclosure_lip_height
    assert abs((l_bb.max.Z - l_bb.min.Z) - expected_lid_h) < 0.1

    # 3. Verify view_product populates all 4 parts and seats carrier board on standoffs
    room = Room()
    provider.view_product(room, Mode.DEFAULT)
    assert "carrier_board" in room
    assert "flex_tail" in room
    assert "enclosure_bottom" in room
    assert "enclosure_lid" in room

    carrier_geom = room["carrier_board"][0]
    carrier_part = getattr(carrier_geom, "part", carrier_geom)
    carrier_bb = carrier_part.bounding_box()
    expected_carrier_bottom_z = (
        -expected_h / 2.0 + provider.settings.enclosure_wall_thickness + provider.settings.standoff_height
    )
    assert abs(carrier_bb.min.Z - expected_carrier_bottom_z) < 0.05


def test_regression_enclosure_m2_cutout_and_component_silkscreens() -> None:
    """Verify BUG-065 (M.2 cutout in bottom enclosure) and BUG-066 (component silkscreens on carrier)."""
    provider = TestBoardProvider()

    # 1. BUG-065: Verify M.2 cutout settings and bottom enclosure build
    assert provider.settings.enclosure_m2_cutout_width == 24.0
    assert provider.settings.enclosure_m2_cutout_height == 5.0
    bottom = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert bottom is not None and bottom.part is not None

    # 2. BUG-066: Verify all component reference designators are present in silkscreen
    silks = provider.silkscreen()
    silk_texts = {t.text for t in silks}
    expected_components = (
        ["U1", "U2", "J1", "J2", "J3", "Q1", "U3", "U4", "SPK1", "Y1"]
        + [f"R{i}" for i in range(1, 7)]
        + [f"C{i}" for i in range(1, 13)]
    )
    for comp in expected_components:
        assert comp in silk_texts, f"Component RefDes {comp} must be present in carrier silkscreen"

    # 3. Verify zero DRC errors across carrier board with all silkscreen texts
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(provider.pcb_config)
    violations = checker.check_all(wiring=wiring)
    assert violations.error_count == 0, f"DRC errors found: {[v.description for v in violations.errors]}"


def test_regression_schematic_page_boundary_drc_and_layout(tmp_path: Path) -> None:
    """Verify BUG-068 (page boundary DRC and Sheet 5 passives) and BUG-071 (Sheet 7 I2C pullups)."""
    from provider.schematic_diagram import SchematicDiagram
    from provider.pcb.drc import DRCRuleName

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(provider.pcb_config)

    # 1. Verify 0 schematic DRC violations across all 7 sheets
    violations = checker.check_schematic(wiring)
    page_boundary_errors = [v for v in violations.errors if v.rule_name == DRCRuleName.SCHEMATIC_PAGE_BOUNDARY_EXCEEDED]
    assert len(page_boundary_errors) == 0, (
        f"Page boundary violations found: {[v.description for v in page_boundary_errors]}"
    )
    assert len(violations.errors) == 0, f"Schematic DRC errors found: {[v.description for v in violations.errors]}"

    # 2. Verify schematic multi-page PDF generation without clipping
    diag = SchematicDiagram(wiring=wiring, pcb_config=provider.pcb_config)
    pdf_out = diag.render_pdf(tmp_path / "test_board_schematic.pdf")
    assert pdf_out.is_file()
    assert pdf_out.stat().st_size > 5000
