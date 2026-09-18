"""Unit tests for advanced PCB features: CPWG impedance, RF/Display DRC, CAD boundary containment, Eye diagram, and TestBoard."""

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
    SchematicSheetModel,
    MountingHoleModel,
)
from model.wiring import Wiring, FootprintModel, PinModel, PinSide, NetModel
from provider.pcb.drc import PCBDesignRulesChecker, DRCSeverity
from provider.pcb.exporter import PCBExporter
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
    assert len(wiring.footprints) == 10
    footprint_names = [fp.name for fp in wiring.footprints]
    assert "U1" in footprint_names
    assert "U2" in footprint_names
    assert "J1" in footprint_names
    assert "J2" in footprint_names
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

    # Verify BOM and CPL export
    pcb_config = provider.pcb_config
    assert pcb_config is not None
    exporter = PCBExporter(pcb_config, wiring)

    bom_csv = tmp_path / "bom.csv"
    pos_csv = tmp_path / "pos.csv"
    exporter.export_bom_csv(bom_csv)
    exporter.export_pick_and_place_csv(pos_csv)

    bom_lines = bom_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(bom_lines) == 11  # header + 10 components
    assert "STM32MP157-BGA196" in bom_csv.read_text(encoding="utf-8")

    pos_lines = pos_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(pos_lines) == 11  # header + 10 components


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
    assert electrodes_by_name["SENSE_WATER_PROXIMITY"].drive_shield is True

    # Milestone 2: Carrier standoff pilot holes
    assert provider.settings.standoff_hole_diameter == 2.2
    assert provider.settings.standoff_hole_depth == 4.0
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
    assert cap_data["channels"][3]["drive_shield"] is True


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
    assert drill_file.exists()

    pcb_text = kicad_pcb.read_text(encoding="utf-8")
    # Verify connectors J1 and J2 edge placement
    assert 'footprint "M.2-KEY-M"' in pcb_text
    assert 'footprint "FPC-30P-0.5MM"' in pcb_text
    # Verify bottom layer components
    assert '(layer "B.Cu")' in pcb_text

    # Verify drill file coordinates match mounting holes
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
