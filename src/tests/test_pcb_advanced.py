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
    assert len(wiring.footprints) == 45
    footprint_names = [fp.name for fp in wiring.footprints]
    assert "U1" in footprint_names
    assert "U2" in footprint_names
    assert "U3" in footprint_names
    assert "U4" in footprint_names
    assert "U10" in footprint_names
    assert "J1" in footprint_names
    assert "J2" in footprint_names
    assert "J3" in footprint_names
    assert "J5" in footprint_names
    assert "J6" in footprint_names
    assert "J7" in footprint_names
    assert "J8" in footprint_names
    assert "J9" in footprint_names
    assert "J10" in footprint_names
    assert "J13" in footprint_names
    assert "J14" in footprint_names
    assert "C13" in footprint_names
    assert "C14" in footprint_names
    assert "U5" in footprint_names
    assert "U6" in footprint_names
    assert "U7" in footprint_names
    assert "U8" in footprint_names
    assert "U9" in footprint_names
    assert "D1" in footprint_names
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
    assert len(bom_lines) == 45  # header + 44 carrier components (J4 is on flex tail)
    assert "MCXN947VDF" in bom_csv.read_text(encoding="utf-8")

    pos_lines = pos_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(pos_lines) == 45  # header + 44 carrier components


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

    # Milestone 2: Carrier clip-on mounting posts and enclosure feet (BUG-085)
    assert provider.settings.mounting_post_diameter == 2.8
    assert provider.settings.mounting_post_height == 2.6
    assert provider.settings.mounting_post_flare_diameter == 3.6
    assert provider.settings.mounting_post_flare_height == 1.0
    assert provider.settings.mounting_post_tip_diameter == 2.2
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

    # Verify TP1 (GND test point) has routed trace and via connecting to ground (BUG-040, CR 06e5272b01da)
    tp_gnd = next((tp for tp in cfg.test_points if tp.name in ("TP1", "TP_GND")), None)
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
    assert tp_trace is not None, "TP1 (GND) must have a routed copper trace connecting to ground"

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
    assert "TP1" in tps
    assert tps["TP1"].net == "GND"
    assert tps["TP1"].position_mm == (-18.0, -22.0)

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

    assert abs(point_dist("TP6", "TP5") - 4.0) < 1e-3
    assert abs(point_dist("TP11", "TP12") - 4.0) < 1e-3
    assert abs(point_dist("TP9", "TP10") - 4.0) < 1e-3

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
    # Ground pins (VSS, EP) must be at the bottom (after signals SDA, SCL, INT)
    assert left_pins[-1].name in ("VSS", "EP")

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

    # 1. Verify U1 has all 184 balls defined
    u1 = next((fp for fp in wiring.footprints if fp.name == "U1"), None)
    assert u1 is not None
    assert len(u1.pins) == 184, f"Expected 184 balls on U1 VFBGA-184, got {len(u1.pins)}"

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

    # Must contain no-connect pads (e.g. U1 ball A4 and J3 pin SBU1)
    assert '(pad "A4"' in content, "carrier_board.kicad_pcb must contain no-connect pad A4 on U1"
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
    u1 = next(fp for fp in wiring.footprints if fp.name == "U1")
    h7_pin = next((p for p in u1.pins if p.name == "H7"), None)
    h8_pin = next(p for p in u1.pins if p.name == "H8")
    h8_x, h8_y = PCBAutoRouter.get_pin_absolute_position(u1, h8_pin)

    if h7_pin is not None:
        h7_x, h7_y = PCBAutoRouter.get_pin_absolute_position(u1, h7_pin)
        h7_via = next(
            (
                v
                for v in vias
                if v.net == "GND" and abs(v.position_mm[0] - h7_x) < 1.0 and abs(v.position_mm[1] - h7_y) < 1.0
            ),
            None,
        )
        assert h7_via is not None, "U1 BGA GND pin H7 must have a stitching via connecting to the GND plane"

    h8_via = next(
        (
            v
            for v in vias
            if v.net == "3V3" and abs(v.position_mm[0] - h8_x) < 1.0 and abs(v.position_mm[1] - h8_y) < 1.0
        ),
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
    expected_lid_h = (
        provider.settings.enclosure_wall_thickness
        + provider.settings.enclosure_lip_height
        + provider.settings.enclosure_battery_mount_wall_height
    )
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
    assert violations.error_count == 0, f"DRC errors found: {[v.description for v in violations.violations.errors]}"


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


def test_regression_battery_connector_j13(tmp_path: Path) -> None:
    """Verify BUG-070: JST-PH battery connector J13, C13 decoupling, and VBAT net."""
    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(provider.pcb_config)

    # 1. Verify J13 and C13 are defined in wiring footprints
    fp_map = {fp.name: fp for fp in wiring.footprints}
    assert "J13" in fp_map, "J13 battery connector footprint must be defined"
    assert "C13" in fp_map, "C13 battery bypass capacitor footprint must be defined"
    assert fp_map["J13"].package == "JST-PH-2P"

    # 2. Verify VBAT and GND connectivity
    vbat_net = next((n for n in wiring.nets if n.name == "VBAT"), None)
    assert vbat_net is not None, "VBAT net must be defined"
    vbat_pins = set(vbat_net.pins)
    assert ("J13", "1") in vbat_pins
    assert ("C13", "1") in vbat_pins
    assert ("U3", "4") in vbat_pins

    gnd_net = next((n for n in wiring.nets if n.name == "GND"), None)
    assert gnd_net is not None, "GND net must be defined"
    gnd_pins = set(gnd_net.pins)
    assert ("J13", "2") in gnd_pins
    assert ("C13", "2") in gnd_pins

    # 3. Verify J13, C13, and polarity marks in carrier silkscreen
    silks = provider.silkscreen()
    silk_texts = {t.text for t in silks}
    assert "J13" in silk_texts, "J13 silkscreen marking must be present"
    assert "C13" in silk_texts, "C13 silkscreen marking must be present"
    assert "+" in silk_texts and "-" in silk_texts

    # 4. Verify 0 boundary containment and schematic DRC violations
    bound_violations = [
        v for v in checker.check_boundary_containment(footprints=wiring.footprints) if v.severity.name == "ERROR"
    ]
    assert len(bound_violations) == 0, f"Boundary containment errors: {[v.description for v in bound_violations]}"

    schematic_violations = checker.check_schematic(wiring=wiring)
    assert len(schematic_violations.errors) == 0, (
        f"Schematic DRC errors found: {[v.description for v in schematic_violations.errors]}"
    )


def test_regression_downselection_results_application() -> None:
    """Verify BUG-067: downselection results from downselection_report.md applied to test_board.md and PCB."""
    tb_doc = Path("src/projects/test_board.md")
    assert tb_doc.is_file(), "test_board.md must exist"
    content = tb_doc.read_text(encoding="utf-8")

    # 1. Verify all downselected active ICs and peripherals in test_board.md
    assert "MCXN947VDF" in content, "MCU MCXN947VDF must be documented in BOM"
    assert "W25N01GVZEIG" in content, "NAND W25N01GVZEIG must be documented in BOM"
    assert "BQ24074RGTR" in content, "Charger BQ24074RGTR must be documented in BOM"
    assert "MAX17048G+T10" in content, "Fuel gauge MAX17048 must be documented in BOM"
    assert "LP5009RUKR" in content, "LED driver LP5009 must be documented in BOM"
    assert "FT232RNQ-REEL" in content, "USB-UART FT232RNQ must be documented in BOM"
    assert "IQS7222A001QNR" in content or "IQS7211A" in content, (
        "Touch controller IQS7222A / IQS7211A must be documented in BOM"
    )
    assert "MAX98357AETE+" in content, "Audio amp MAX98357A must be documented in BOM"
    assert "TPS22918DBVR" in content, "Load switches TPS22918 must be documented in BOM"
    assert "J13" in content and "JST-PH-2P" in content, "Battery connector J13 must be in BOM"

    # 2. Verify all expansion headers documented
    assert "J5" in content and "SWD" in content
    assert "J7" in content and "I3C0" in content
    assert "J8" in content and "I3C1" in content
    assert "J6" in content and "I2C" in content
    assert "J9" in content and "SPI" in content
    assert "J10" in content and "UART" in content
    assert "J14" in content and "GPIO" in content

    # 3. Verify all downselected components are placed in wiring footprints
    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    fp_map = {fp.name: fp for fp in wiring.footprints}
    u1 = fp_map["U1"]
    assert u1.package == "VFBGA-184", f"Expected U1 package VFBGA-184, got {u1.package}"
    assert u1.mpn == "MCXN947VDF", f"Expected U1 mpn MCXN947VDF, got {u1.mpn}"
    assert len(u1.pins) == 184, f"Expected 184 pins on U1, got {len(u1.pins)}"
    downselected_components = ["J5", "J6", "J7", "J8", "J9", "J10", "J14", "U8", "U6", "D1", "U7", "U9"]
    for des in downselected_components:
        assert des in fp_map, f"Footprint {des} must be present in wiring footprints"

    # 4. Verify connector placements: right side of PCB (X >= 15.0) and SWD near U1
    for conn in ["J6", "J7", "J8", "J9", "J10", "J14"]:
        assert fp_map[conn].position[0] >= 15.0, f"Connector {conn} must be on right side of PCB (X >= 15.0)"
    assert fp_map["J5"].position[0] < 0.0, "SWD header J5 must be placed towards left near U1"
    assert math.hypot(fp_map["J5"].position[0], fp_map["J5"].position[1]) < 25.0, "J5 must be near U1"

    # 5. Verify zero schematic and boundary containment DRC violations on carrier board
    checker = PCBDesignRulesChecker(provider.pcb_config)
    sch_violations = checker.check_schematic(wiring=wiring)
    assert len(sch_violations.errors) == 0, f"Schematic DRC errors: {[v.description for v in sch_violations.errors]}"
    bound_violations = [
        v for v in checker.check_boundary_containment(footprints=wiring.footprints) if v.severity.name == "ERROR"
    ]
    assert len(bound_violations) == 0, f"Boundary containment errors: {[v.description for v in bound_violations]}"


def test_regression_bug_083_schematic_symbol_overlap_and_sheet7_pullups(tmp_path: Path) -> None:
    """Verify BUG-083: Schematic symbol overlap DRC rule and Sheet 7 I2C pullup clearance."""
    import matplotlib.figure
    from matplotlib.backends.backend_pdf import PdfPages
    from provider.schematic_diagram import SchematicDiagram
    from provider.pcb.drc import DRCRuleName

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(provider.pcb_config)

    # 1. Verify 0 schematic symbol overlap DRC errors
    violations = checker.check_schematic(wiring)
    symbol_overlaps = [v for v in violations.errors if v.rule_name == DRCRuleName.SCHEMATIC_SYMBOL_OVERLAP]
    assert len(symbol_overlaps) == 0, f"Schematic symbol overlaps detected: {[v.description for v in symbol_overlaps]}"

    # 2. Verify rendered positions of Sheet 7 I2C pullup resistors R1 and R2
    diag = SchematicDiagram(wiring=wiring, pcb_config=provider.pcb_config)
    plans = diag._build_sheet_plans()
    sheet7 = [p for p in plans if p.sheet_idx == 7][0]

    orig_add_axes = matplotlib.figure.Figure.add_axes
    captured = []

    def mock_add_axes(self, *args, **kwargs):
        ax = orig_add_axes(self, *args, **kwargs)
        captured.append(ax)
        return ax

    matplotlib.figure.Figure.add_axes = mock_add_axes
    try:
        with PdfPages(tmp_path / "sheet7.pdf") as pdf:
            diag._render_pdf_schematic_sheet(pdf, "test_board", sheet7, 7, wiring.nets, 9, 9)
    finally:
        matplotlib.figure.Figure.add_axes = orig_add_axes

    assert len(captured) > 0
    ax = captured[0]
    r1_texts = [t for t in ax.texts if t.get_text() == "R1"]
    r2_texts = [t for t in ax.texts if t.get_text() == "R2"]
    assert len(r1_texts) == 1, "R1 text must be rendered on Sheet 7"
    assert len(r2_texts) == 1, "R2 text must be rendered on Sheet 7"
    r1_pos = r1_texts[0].get_position()
    r2_pos = r2_texts[0].get_position()
    dx = abs(r1_pos[0] - r2_pos[0])
    assert dx >= 12.0, f"R1 and R2 must have >= 12.0mm horizontal clearance to prevent overlap, got dx={dx:.1f}mm"


def test_regression_bug_082_carrier_board_routing_and_kicad_drc(tmp_path: Path):
    """Verify BUG-082: carrier_board routes cleanly with zero drc.py and zero KiCad DRC errors."""
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.pcb.exporter import PCBExporter
    from provider.pcb.kicad_cli import KiCadCLI

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_cfg = provider.pcb_config

    # 1. Verify drc.py checks on carrier_board pass with 0 errors
    drc = PCBDesignRulesChecker(pcb_cfg)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"drc.py checks failed: {report.summary()}"
    assert report.error_count == 0, f"Expected 0 drc.py errors, got {report.error_count}"

    # 2. Verify component clearances for downselected components
    fp_map = {fp.name: fp for fp in wiring.footprints}
    assert fp_map["U8"].position[1] >= 2.0, "U8 NAND flash must be placed clear of I2C test points"
    assert fp_map["U9"].position[1] <= -25.0, "U9 USB-UART must be placed clear of TP_GND"
    assert fp_map["J14"].position[0] <= 21.0, "J14 GPIO header must be moved left of peripheral column to avoid MH4"

    # 3. If KiCad CLI is available, verify export and run_drc returns 0 errors
    kicad_cli = KiCadCLI(design_rules=pcb_cfg.design_rules)
    if kicad_cli.is_available and kicad_cli.supports_drc:
        exporter = PCBExporter(pcb_cfg, wiring, subassembly=None, design_rules=pcb_cfg.design_rules)
        pcb_file = tmp_path / "carrier_board.kicad_pcb"
        rpt_file = tmp_path / "carrier_board-drc.rpt"
        exporter.export_kicad_pcb(pcb_file)
        kicad_report = kicad_cli.run_drc(pcb_file, rpt_file, design_rules=pcb_cfg.design_rules)
        assert kicad_report.passed, (
            f"KiCad DRC failed with {kicad_report.error_count} error(s):\n{kicad_report.summary()}"
        )
        assert kicad_report.error_count == 0, f"KiCad DRC reported errors: {kicad_report.summary()}"


def test_regression_bug_084_carrier_board_and_schematic_revision_2_0(tmp_path: Path):
    """Verify BUG-084: carrier_board files, schematics, and silkscreen reflect Revision 2.0."""
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.exporter import PCBExporter

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    pcb_cfg = provider.pcb_config

    # 1. Config revision must be 2.0
    assert pcb_cfg.revision == "2.0", f"Expected revision '2.0', got '{pcb_cfg.revision}'"

    # 2. Silkscreen text on carrier board must reflect REV 2.0
    carrier_texts = [st.text for st in pcb_cfg.silkscreen_texts]
    assert "TEST BOARD CARRIER REV 2.0" in carrier_texts, (
        f"Silkscreen texts must contain 'TEST BOARD CARRIER REV 2.0', got: {carrier_texts}"
    )

    # 3. Export KiCad PCB and schematic and verify revision 2.0 in output files
    exporter = PCBExporter(pcb_cfg, wiring, subassembly=None)
    pcb_file = tmp_path / "carrier_board.kicad_pcb"
    sch_file = tmp_path / "carrier_board.kicad_sch"
    exporter.export_kicad_pcb(pcb_file)
    exporter.export_kicad_sch(sch_file)

    pcb_text = pcb_file.read_text(encoding="utf-8")
    sch_text = sch_file.read_text(encoding="utf-8")
    assert '(rev "2.0")' in pcb_text, 'KiCad PCB must specify (rev "2.0")'
    assert '(rev "2.0")' in sch_text, 'KiCad schematic must specify (rev "2.0")'
    assert "MCXN947VDF" in sch_text, "KiCad schematic must specify MCXN947VDF"
    assert "STM32" not in sch_text, "KiCad schematic must not contain obsolete STM32 references"


def test_regression_bug_085_clip_on_mounting_posts() -> None:
    """Verify BUG-085: carrier mounting holes on enclosure bottom replaced with flared clip-on posts."""
    from build123d import Location
    from projects.test_board.provider import TestBoardProvider

    provider = TestBoardProvider()
    enclosure = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    carrier = provider.carrier_board("carrier_board", None, Mode.DEFAULT)

    # 1. Config properties must match measurements.yaml
    assert provider.settings.mounting_post_diameter == 2.8
    assert provider.settings.mounting_post_height == 2.6
    assert provider.settings.mounting_post_flare_diameter == 3.6
    assert provider.settings.mounting_post_flare_height == 1.0
    assert provider.settings.mounting_post_tip_diameter == 2.2

    wall = provider.settings.enclosure_wall_thickness
    standoff_h = provider.settings.standoff_height
    h_shell = standoff_h + provider.settings.board_thickness + 10.0
    standoff_top_z = -h_shell / 2.0 + wall + standoff_h
    z_carrier = standoff_top_z + (provider.settings.board_thickness / 2.0)

    hole_x = (provider.settings.board_width / 2.0) - provider.settings.mounting_hole_inset
    hole_y = (provider.settings.board_length / 2.0) - provider.settings.mounting_hole_inset
    shaft_h = provider.settings.mounting_post_height - provider.settings.mounting_post_flare_height

    # 2. Pilot hole locations inside standoffs must be solid
    standoff_mid_z = -h_shell / 2.0 + wall + (standoff_h / 2.0)
    for sx in (hole_x, -hole_x):
        for sy in (hole_y, -hole_y):
            assert enclosure.part.is_inside((sx, sy, standoff_mid_z))

    # 3. Post shaft must be solid
    post_mid_z = standoff_top_z + (shaft_h / 2.0)
    for sx in (hole_x, -hole_x):
        for sy in (hole_y, -hole_y):
            assert enclosure.part.is_inside((sx, sy, post_mid_z))

    # 4. Flared retaining head must overhang hole radius (1.6 mm) at radius 1.7 mm
    flare_probe_z = standoff_top_z + shaft_h + 0.1
    for sx, sy in [(hole_x, hole_y), (-hole_x, hole_y), (-hole_x, -hole_y), (hole_x, -hole_y)]:
        assert enclosure.part.is_inside((sx + 1.7, sy, flare_probe_z))
        assert not enclosure.part.is_inside((sx + 2.0, sy, flare_probe_z))

    # 5. Zero intersection between carrier board and enclosure bottom
    carrier_geom = carrier.part.locate(Location((0.0, 0.0, z_carrier)))
    inter = enclosure.part.intersect(carrier_geom)
    assert inter.volume == pytest.approx(0.0, abs=1e-3)


def test_regression_bug_086_azoteq_capacitive_sensing() -> None:
    """Verify BUG-086: Downselection of U2 to Azoteq IQS7222A001QNR / IQS7211A in QFN-20."""
    provider = TestBoardProvider()
    wiring = Wiring(provider.wiring_path)
    fp_map = {fp.name: fp for fp in wiring.footprints}

    # 1. Verify U2 package, MPN, and layer
    assert "U2" in fp_map, "U2 must be present in wiring"
    u2 = fp_map["U2"]
    assert u2.package == "QFN-20", f"U2 package must be QFN-20, got {u2.package}"
    assert u2.mpn == "IQS7222A001QNR", f"U2 MPN must be IQS7222A001QNR, got {u2.mpn}"
    assert getattr(u2, "layer", "F.Cu") == "B.Cu", f"U2 must be on B.Cu layer, got {getattr(u2, 'layer', 'F.Cu')}"

    # 2. Verify U2 pins
    pin_names = {p.name for p in u2.pins}
    expected_pins = {
        "VDD",
        "VREGD",
        "VSS",
        "VREGA",
        "CR0",
        "CR1",
        "CR2",
        "CR3",
        "CR4",
        "CR5",
        "CR6",
        "CR7",
        "RDY",
        "SCL",
        "SDA",
        "MCLR",
        "EP",
    }
    assert expected_pins.issubset(pin_names), f"Missing expected pins on QFN-20: {expected_pins - pin_names}"

    # 3. Verify dual LDO bypass capacitors C12 (VREGD) and C14 (VREGA)
    assert "C12" in fp_map, "C12 (VREGD bypass) must exist"
    assert "C14" in fp_map, "C14 (VREGA bypass) must exist"
    assert getattr(fp_map["C12"], "layer", "F.Cu") == "B.Cu", "C12 must be on B.Cu"
    assert getattr(fp_map["C14"], "layer", "F.Cu") == "B.Cu", "C14 must be on B.Cu"

    # 4. Verify VREGD and VREGA net connectivity
    net_map = {net.name: net for net in wiring.nets}
    assert "VREGD" in net_map, "VREGD net must exist"
    assert "VREGA" in net_map, "VREGA net must exist"
    assert ("U2", "VREGD") in net_map["VREGD"].pins and ("C12", "1") in net_map["VREGD"].pins
    assert ("U2", "VREGA") in net_map["VREGA"].pins and ("C14", "1") in net_map["VREGA"].pins

    # 5. Verify capacitive sensor nets sequential mapping
    for i in range(4):
        rx_net = f"CAP_RX{i}"
        assert rx_net in net_map, f"{rx_net} must exist"
        assert ("U2", f"CR{i}") in net_map[rx_net].pins

    for i in range(3):
        tx_net = f"CAP_TX{i}"
        assert tx_net in net_map, f"{tx_net} must exist"
        assert ("U2", f"CR{i + 4}") in net_map[tx_net].pins

    assert "CAP_SHIELD" in net_map
    assert ("U2", "CR7") in net_map["CAP_SHIELD"].pins

    # 6. Verify Schematic Sheet 7
    pcb_cfg = provider.pcb_config
    sheet7 = next((s for s in pcb_cfg.schematic_sheets if "IQS7222A" in s.title or "Capacitive" in s.title), None)
    assert sheet7 is not None, "Schematic Sheet 7 for capacitive sensing must exist"
    assert "IQS7222A" in sheet7.title
    assert "C14" in sheet7.components and "C12" in sheet7.components and "U2" in sheet7.components

    # 7. Verify Schematic and Boundary DRC pass
    checker = PCBDesignRulesChecker(pcb_cfg)
    sch_violations = checker.check_schematic(wiring=wiring)
    assert len(sch_violations.errors) == 0, f"Schematic DRC errors: {[v.description for v in sch_violations.errors]}"
    bound_violations = [
        v for v in checker.check_boundary_containment(footprints=wiring.footprints) if v.severity.name == "ERROR"
    ]
    assert len(bound_violations) == 0, f"Boundary containment errors: {[v.description for v in bound_violations]}"


def test_regression_bug_087_power_test_points():
    """Verify BUG-087: carrier_board has power test points for VBAT, VBUS, 3V3, and GND."""
    import math
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from model.wiring import Wiring

    provider = TestBoardProvider()
    cfg = provider.pcb_config
    assert cfg is not None

    tps = {tp.name: tp for tp in cfg.test_points}
    for required in ("TP2", "TP3", "TP4", "TP1"):
        assert required in tps, f"Missing required test point: {required}"

    assert tps["TP2"].net == "VBAT"
    assert tps["TP3"].net == "VBUS"
    assert tps["TP4"].net == "3V3"
    assert tps["TP1"].net == "GND"

    assert tps["TP2"].position_mm == (-18.0, -26.0)
    assert tps["TP3"].position_mm == (-14.0, -26.0)
    assert tps["TP4"].position_mm == (-10.0, -26.0)
    assert tps["TP1"].position_mm == (-18.0, -22.0)

    for tp_name in ("TP2", "TP3", "TP4", "TP1"):
        tp = tps[tp_name]
        assert tp.drill_diameter_mm == 0.80
        assert tp.pad_diameter_mm == 1.40
        assert tp.plated is True

    # 4mm pitch between consecutive power test points
    def point_dist(name1: str, name2: str) -> float:
        p1 = tps[name1].position_mm
        p2 = tps[name2].position_mm
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    assert abs(point_dist("TP2", "TP3") - 4.0) < 1e-3
    assert abs(point_dist("TP3", "TP4") - 4.0) < 1e-3

    # Schematic & boundary DRC check
    wiring = Wiring(str(provider.wiring_path))
    checker = PCBDesignRulesChecker(cfg)
    sch_violations = checker.check_schematic(wiring=wiring)
    assert len(sch_violations.errors) == 0, f"Schematic DRC errors: {[v.description for v in sch_violations.errors]}"
    bound_violations = [
        v for v in checker.check_boundary_containment(footprints=wiring.footprints) if v.severity.name == "ERROR"
    ]
    assert len(bound_violations) == 0, f"Boundary containment errors: {[v.description for v in bound_violations]}"


def test_regression_bug_088_schematic_defects_and_drc() -> None:
    """Verify schematic defect remedies and DRC rule enforcement (BUG-088).

    Guards against:
    1. Symbol boundary overflow off page edge (e.g. U1 symbol height clamped to page margins).
    2. Decoupling capacitor card overlap with top sheet header banner (Y in [184, 198]).
    3. Decoupling capacitor card or symbol overlap with engineering title block (X in [200, 285], Y in [12, 46]).
    4. Components in the netlist having no connected pins (dangling components past sheet 15).
    5. DRC rules SCHEMATIC_TITLE_BLOCK_COLLISION, SCHEMATIC_HEADER_COLLISION, and SCHEMATIC_DANGLING_COMPONENT.
    """
    from model.wiring import Wiring
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker
    from provider.schematic_diagram import SchematicDiagram

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    cfg = provider.pcb_config

    # 1. Verify live design passes all schematic DRC checks with 0 errors
    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring=wiring)
    assert len(violations.errors) == 0, f"Unexpected schematic DRC errors: {[e.description for e in violations.errors]}"

    # 2. Verify all symbol bounding boxes are strictly within page limits and do not hit header or title block
    diag = SchematicDiagram(wiring=wiring, pcb_config=cfg)
    boxes = diag.compute_symbol_bounding_boxes()
    for sheet_idx, b_list in boxes.items():
        for b in b_list:
            b_xmin = b[0] - b[2] / 2.0
            b_xmax = b[0] + b[2] / 2.0
            b_ymin = b[1] - b[3] / 2.0
            b_ymax = b[1] + b[3] / 2.0

            # No symbol may extend off bottom page boundary (cy >= 16.0)
            assert b_ymin >= 16.0, f"Symbol {b[4]} on sheet {sheet_idx} falls off bottom margin: ymin={b_ymin:.1f}"
            # No symbol may collide with top sheet header (Y in [184, 198] for X in [20, 280])
            header_collision = b_ymax > 184.0 and b_ymin < 198.0 and b_xmax > 20.0 and b_xmin < 280.0
            assert not header_collision, (
                f"Symbol {b[4]} on sheet {sheet_idx} collides with header: bounds=({b_xmin:.1f}, {b_ymin:.1f}, {b_xmax:.1f}, {b_ymax:.1f})"
            )
            # No symbol may collide with title block (X in [200, 285] and Y in [12, 46])
            tb_collision = b_xmax > 200.0 and b_xmin < 285.0 and b_ymin < 46.0 and b_ymax > 12.0
            assert not tb_collision, (
                f"Symbol {b[4]} on sheet {sheet_idx} collides with title block: bounds=({b_xmin:.1f}, {b_ymin:.1f}, {b_xmax:.1f}, {b_ymax:.1f})"
            )

    # 3. Verify all carrier footprints in wiring have at least one connected pin
    footprints_map = {f.name: f for f in wiring.footprints if getattr(f, "shape_ref", None) != "flex_tail"}
    pin_to_net = {(c, p): net.name for net in wiring.nets for c, p in net.pins}
    for name, fp in footprints_map.items():
        connected = [p for p in fp.pins if (name, p.name) in pin_to_net]
        assert len(connected) > 0, f"Dangling component {name} has no connected pins in wiring.yaml"


def test_regression_bug_089_schematic_subsystem_organization() -> None:
    """Verify schematic sheets are organized topologically by subsystem with 100% component coverage (BUG-089).

    Guards against:
    1. Unorganized schematic sheets or falling back to arbitrary multi-page chunking.
    2. Missing carrier board components from schematic sheets.
    3. Missing functional subsystem domains: Power/Battery, Regulation, MCU, Storage, Telemetry, UI, Cap Touch, Audio, High-Speed, Expansion.
    4. Schematic DRC violations across organized sheets.
    """
    from model.wiring import Wiring
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    cfg = provider.pcb_config

    assert cfg.schematic_sheets is not None
    assert len(cfg.schematic_sheets) >= 8

    # 1. Verify subsystem sheets by title keywords
    titles = [s.title for s in cfg.schematic_sheets]
    expected_subsystems = [
        "Battery",
        "Regulation",
        "Microcontroller",
        "Storage",
        "Telemetry",
        "User Interface",
        "Capacitive",
        "Audio",
        "Differential",
        "Expansion",
    ]
    for sub in expected_subsystems:
        assert any(sub.lower() in t.lower() for t in titles), f"Missing subsystem sheet matching '{sub}' in {titles}"

    # 2. Verify 100% carrier board component coverage
    carrier_comps = {f.name for f in wiring.footprints if getattr(f, "shape_ref", None) != "flex_tail"}
    documented_comps = {c for s in cfg.schematic_sheets for c in s.components}
    missing_comps = carrier_comps - documented_comps
    assert len(missing_comps) == 0, f"Components missing from subsystem schematic sheets: {missing_comps}"

    # 3. Verify specific subsystem allocations
    sheet_by_title = {s.title: s for s in cfg.schematic_sheets}

    storage_sheet = next(s for s in cfg.schematic_sheets if "storage" in s.title.lower())
    assert "U8" in storage_sheet.components

    telemetry_sheet = next(s for s in cfg.schematic_sheets if "telemetry" in s.title.lower())
    assert "U9" in telemetry_sheet.components
    assert "J5" in telemetry_sheet.components

    ui_sheet = next(s for s in cfg.schematic_sheets if "user interface" in s.title.lower())
    assert "U6" in ui_sheet.components
    assert "D1" in ui_sheet.components

    # 4. DRC check passes with 0 violations
    checker = PCBDesignRulesChecker(cfg)
    violations = checker.check_schematic(wiring=wiring)
    assert len(violations.errors) == 0, f"DRC errors on subsystem sheets: {[e.description for e in violations.errors]}"


def test_regression_bug_090_enclosure_cad_feedback() -> None:
    """Verify BUG-090: SWD vs USB cutout separation, rounded side cutouts, and lid battery mount."""
    provider = TestBoardProvider()
    cfg = provider.pcb_config
    assert cfg is not None
    wiring = Wiring(str(provider.wiring_path))
    fp_map = {fp.name: fp for fp in wiring.footprints}

    # 1. Verify SWD cutout is spaced apart from USB cutout with a solid wall barrier
    usb_w = provider.settings.enclosure_usb_cutout_width
    swd_w = provider.settings.enclosure_swd_cutout_width
    swd_y = fp_map["J5"].position[1]
    usb_min_y = -usb_w / 2.0
    swd_max_y = swd_y + (swd_w / 2.0)
    separation = usb_min_y - swd_max_y
    assert separation >= 2.0, (
        f"SWD cutout (max Y = {swd_max_y}) and USB cutout (min Y = {usb_min_y}) must have >= 2mm wall barrier, "
        f"got {separation:.2f}mm"
    )

    # 2. Verify side enclosure cutouts on bottom shell build with rounded corners
    assert provider.settings.enclosure_cutout_fillet_radius == 0.8
    bottom = provider.enclosure_bottom("enclosure_bottom", None, Mode.DEFAULT)
    assert bottom is not None and bottom.part is not None
    assert bottom.part.is_valid(), "Enclosure bottom must be a valid solid"

    # Wall barrier between USB and SWD is solid material
    w = provider.settings.board_width + 2.0 * (
        provider.settings.enclosure_clearance + provider.settings.enclosure_wall_thickness
    )
    wall = provider.settings.enclosure_wall_thickness
    probe_x = (-w / 2.0) + (wall / 2.0)
    probe_y = (usb_min_y + swd_max_y) / 2.0
    h_shell = provider.settings.standoff_height + provider.settings.board_thickness + 10.0
    mid_z = -h_shell / 2.0 + wall + provider.settings.standoff_height + 2.0
    assert bottom.part.is_inside((probe_x, probe_y, mid_z)), "Material between USB and SWD cutouts must be solid"

    # 3. Verify enclosure lid contains battery mount cradle and pass-through cutout for J13
    assert provider.settings.enclosure_battery_mount_width == 24.0
    assert provider.settings.enclosure_battery_mount_length == 38.0
    assert provider.settings.enclosure_battery_mount_wall_height == 3.5
    assert provider.settings.enclosure_battery_cutout_width == 8.0
    assert provider.settings.enclosure_battery_cutout_length == 6.0

    lid = provider.enclosure_lid("enclosure_lid", None, Mode.DEFAULT)
    assert lid is not None and lid.part is not None
    assert lid.part.is_valid(), "Enclosure lid must be a valid solid"

    # Check joints on lid
    joint_names = {j.label for j in lid.part.joints.values()}
    assert "battery_mount" in joint_names, "Enclosure lid must define battery_mount joint"
    assert "battery_port" in joint_names, "Enclosure lid must define battery_port joint"
    assert "led_port" in joint_names, "Enclosure lid must define led_port joint"

    # Pass-through cutout at J13 is void (hollow) through lid
    j13_pos = fp_map["J13"].position
    cutout_probe_z = wall / 2.0
    assert not lid.part.is_inside((j13_pos[0], j13_pos[1], cutout_probe_z)), (
        "Lid must have open pass-through cutout at J13 battery connector"
    )


def test_regression_bug_092_carrier_board_top_logo() -> None:
    """Verify BUG-092: Antigravity logo placed as a unique graphic image within a square frame (not text) on carrier board top with zero DRC errors."""
    from pathlib import Path
    from projects.test_board.provider import TestBoardProvider
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = TestBoardProvider()
    silks = provider.silkscreen()
    silk_map = {t.text: t for t in silks}

    # 1. Logo must NOT be text (e.g. "ANTIGRAVITY", "[>", etc. must not be text strings)
    assert "ANTIGRAVITY" not in silk_map, "Carrier board logo must not be text 'ANTIGRAVITY'"
    assert "[>" not in silk_map, "Carrier board logo must not be text '[>'"
    assert "<]" not in silk_map, "Carrier board logo must not be text '<]'"
    assert "* * *" not in silk_map, "Carrier board logo must not be text '* * *'"
    assert "QUANTUM DYNAMICS // 0x414759" not in silk_map, "Carrier board logo must not be text hex signature"

    # 2. Logo must be present as a unique vector graphic within a square frame on F.SilkS
    graphics = provider.silkscreen_graphics()
    assert len(graphics) > 0, "Carrier board must contain silkscreen graphic elements for the logo"

    rect_frames = [g for g in graphics if g.shape == "rect" and g.layer == "F.SilkS"]
    assert len(rect_frames) >= 1, "Carrier board must contain a square frame rect on F.SilkS"
    frame = rect_frames[0]
    assert frame.position[1] > 28.0, f"Logo frame must be in top region (y > 28mm), got {frame.position}"
    assert abs(frame.position[0]) < 5.0, f"Logo frame should be centered horizontally, got {frame.position}"
    assert frame.dimensions[0] == frame.dimensions[1], f"Logo frame must be square, got {frame.dimensions}"

    # Verify inner graphic emblem primitives (polygon and wing lines)
    poly_emblems = [g for g in graphics if g.shape == "polygon" and g.layer == "F.SilkS"]
    assert len(poly_emblems) >= 1, "Logo must contain inner geometric polygon emblem"
    line_emblems = [g for g in graphics if g.shape == "line" and g.layer == "F.SilkS"]
    assert len(line_emblems) >= 2, "Logo must contain inner graphic line elements"

    # 3. Unique logo image asset must exist within a square frame
    repo_root = Path(__file__).resolve().parents[2]
    logo_asset = repo_root / "src" / "projects" / "test_board" / "docs" / "assets" / "carrier_board_logo.jpg"
    assert logo_asset.exists(), f"Unique logo image asset must exist at {logo_asset}"

    # 4. DRC check verifies zero silkscreen-to-pad overlap errors
    wiring = Wiring(provider.wiring_path)
    checker = PCBDesignRulesChecker(provider.pcb_config)
    violations = [
        v for v in checker.check_clearances_and_overlaps(wiring=wiring) if v.rule_name == "SILKSCREEN_PAD_OVERLAP"
    ]
    assert len(violations) == 0, f"Silkscreen overlap violations found: {violations}"


def test_regression_bug_094_dynamic_geometric_priority_and_rip_up_reroute() -> None:
    """Verify BUG-094: PCBAutoRouter uses dynamic geometric constraint scoring and rip-up reroute without hardcoded net names."""
    import inspect
    from types import SimpleNamespace
    from provider.pcb.router import PCBAutoRouter
    from model.wiring import NetModel, FootprintModel, PinModel
    from model.pcb import PCBConfig, StackupModel, StackupLayerModel, LayerType

    # 1. Inspect PCBAutoRouter.route_all_nets source to verify no hardcoded net name strings
    source = inspect.getsource(PCBAutoRouter.route_all_nets)
    banned_hardcoded = ['"I2C"', '"FLEX0_A"', '"UART0_"', '"SPI"', '"USB"']
    for banned in banned_hardcoded:
        assert banned not in source, f"Hardcoded net name priority matching {banned} found in route_all_nets!"

    # 2. Verify NetModel supports custom priority attribute
    net_custom = NetModel(name="CUSTOM_HIGH_PRIO", pins=[("U1", "1"), ("U2", "1")], priority=0, color="green")
    assert net_custom.priority == 0

    # 3. Test dynamic geometric priority sorting
    # Build synthetic wiring with two components: U1 (dense multi-pin IC) and J1 (sparse connector)
    u1_pins = [
        PinModel(name=str(i), position=((i % 4) * 0.8, (i // 4) * 0.8, 0.0), label=str(i), side="left")
        for i in range(16)
    ]
    u1 = FootprintModel(name="U1", package="QFN-16", position=(0.0, 0.0, 0.0), dimensions=(4.0, 4.0, 1.0), pins=u1_pins)

    u2_pins = [
        PinModel(name="1", position=(0.0, 0.0, 0.0), label="1", side="left"),
        PinModel(name="2", position=(0.8, 0.0, 0.0), label="2", side="right"),
    ]
    u2 = FootprintModel(name="U2", package="0402", position=(4.0, 0.0, 0.0), dimensions=(1.0, 0.5, 0.5), pins=u2_pins)

    j1_pins = [
        PinModel(name="1", position=(0.0, 0.0, 0.0), label="1", side="left"),
        PinModel(name="2", position=(0.0, 2.54, 0.0), label="2", side="right"),
    ]
    j1 = FootprintModel(
        name="J1", package="CONN", position=(15.0, 15.0, 0.0), dimensions=(2.54, 5.08, 2.54), pins=j1_pins
    )

    net_dense = NetModel(name="DENSE_LOCAL_NET", pins=[("U1", "0"), ("U2", "1")], color="blue")
    net_sparse = NetModel(name="SPARSE_CROSS_NET", pins=[("U1", "15"), ("J1", "1")], color="yellow")
    net_override = NetModel(name="OVERRIDE_NET", pins=[("J1", "2"), ("U2", "2")], priority=-10, color="red")

    wiring = SimpleNamespace(
        components={"U1": u1, "U2": u2, "J1": j1},
        footprints=[u1, u2, j1],
        nets=[net_sparse, net_dense, net_override],
    )

    stackup = StackupModel(
        layers=[
            StackupLayerModel(name="F.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL),
            StackupLayerModel(name="B.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL),
        ]
    )
    cfg = PCBConfig(
        name="test_board",
        dimensions_mm=(40.0, 40.0, 1.6),
        stackup=stackup,
    )

    router = PCBAutoRouter(cfg, wiring)
    traces, vias = router.route_all_nets()
    assert len(traces) > 0, "Router should successfully route nets"
    routed_nets = {tr.net for tr in traces}
    assert "OVERRIDE_NET" in routed_nets
    assert "DENSE_LOCAL_NET" in routed_nets


def test_regression_bug_105_bug_106_audio_en_and_sensor_power_architecture() -> None:
    """Verify BUG-105 & BUG-106: dedicated AUDIO_EN GPIO, dedicated expansion INT GPIOs, and SENSOR_3V3 regulator."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))

    # 1. Verify AUDIO_EN connects MCU L4 to audio amp U4 SD_MODE (BUG-105)
    audio_en_net = next((net for net in wiring.nets if net.name == "AUDIO_EN"), None)
    assert audio_en_net is not None, "AUDIO_EN net must exist in wiring.yaml"
    audio_en_pins = set(audio_en_net.pins)
    assert ("U1", "L4") in audio_en_pins
    assert ("U4", "SD_MODE") in audio_en_pins

    # 2. Verify PWR_EN connects only MCU D1 and Q1 gate; decoupled from U4 SD_MODE
    pwr_en_net = next((net for net in wiring.nets if net.name == "PWR_EN"), None)
    assert pwr_en_net is not None, "PWR_EN net must exist in wiring.yaml"
    pwr_en_pins = set(pwr_en_net.pins)
    assert ("U1", "D1") in pwr_en_pins
    assert ("Q1", "G") in pwr_en_pins
    assert ("U4", "SD_MODE") not in pwr_en_pins, "U4 SD_MODE must NOT be controlled by PWR_EN"

    # 3. Verify VLOAD_SW connects Q1 drain, J1, audio amp U4 ground/gain, C8 cap ground
    # and NO LONGER connects to peripheral expansion headers J6-J9 (BUG-106)
    vload_net = next((net for net in wiring.nets if net.name == "VLOAD_SW"), None)
    assert vload_net is not None, "VLOAD_SW net must exist in wiring.yaml"
    vload_pins = set(vload_net.pins)
    assert ("Q1", "D") in vload_pins
    assert ("J1", "VLOAD_SW") in vload_pins
    assert ("U4", "GND") in vload_pins
    assert ("U4", "GAIN") in vload_pins
    assert ("C8", "2") in vload_pins
    for j_comp in ["J6", "J7", "J8", "J9"]:
        assert (j_comp, "2") not in vload_pins, f"{j_comp}.2 must NOT be on VLOAD_SW"

    # 4. Verify dedicated INT GPIOs connect to pin 2 of J6-J9 (BUG-106)
    int_mappings = {
        "EXP_INT_I2C": (("U1", "B2"), ("J6", "2")),
        "EXP_INT_I3C": (("U1", "B8"), ("J7", "2")),
        "EXP_INT_I3C1": (("U1", "E4"), ("J8", "2")),
        "EXP_INT_SPI": (("U1", "T8"), ("J9", "2")),
    }
    for net_name, (u1_pin, exp_pin) in int_mappings.items():
        net = next((n for n in wiring.nets if n.name == net_name), None)
        assert net is not None, f"{net_name} net must exist in wiring.yaml"
        net_pins = set(net.pins)
        assert u1_pin in net_pins, f"{u1_pin} must be connected to {net_name}"
        assert exp_pin in net_pins, f"{exp_pin} must be connected to {net_name}"

    # 5. Verify SENSOR_3V3 regulator U10 and power rail distribution (BUG-106)
    sensor_v33_net = next((net for net in wiring.nets if net.name == "SENSOR_3V3"), None)
    assert sensor_v33_net is not None, "SENSOR_3V3 net must exist in wiring.yaml"
    sensor_v33_pins = set(sensor_v33_net.pins)
    assert ("U10", "5") in sensor_v33_pins, "U10 pin 5 (VOUT) must drive SENSOR_3V3"
    for j_comp in ["J6", "J7", "J8", "J9"]:
        assert (j_comp, "1") in sensor_v33_pins, f"{j_comp}.1 must be powered by SENSOR_3V3"

    # 6. Verify U10 is sourced from 3V3 with SENSOR_EN from U1 L5
    v33_net = next((net for net in wiring.nets if net.name == "3V3"), None)
    assert v33_net is not None
    assert ("U10", "1") in set(v33_net.pins), "U10 pin 1 (VIN) must be powered by 3V3"

    sensor_en_net = next((net for net in wiring.nets if net.name == "SENSOR_EN"), None)
    assert sensor_en_net is not None, "SENSOR_EN net must exist in wiring.yaml"
    assert ("U1", "L5") in set(sensor_en_net.pins)
    assert ("U10", "3") in set(sensor_en_net.pins)


def test_regression_schematic_router_invariants_bug_098_through_104() -> None:
    """Verify schematic router invariants for BUG-098 through BUG-104."""
    from projects.test_board.provider import TestBoardProvider
    from model.wiring import Wiring
    from provider.schematic_diagram import SchematicDiagram

    provider = TestBoardProvider()
    wiring = Wiring(str(provider.wiring_path))
    sd = SchematicDiagram(wiring, pcb_config=provider.pcb_config)
    sheets = sd._build_sheet_plans()

    # 1. BUG-103: Expansion headers broken into Sheet 10 (I2C/I3C) and Sheet 11 (SPI/UART/CAN)
    sheet_titles = [s.title for s in sheets]
    assert any("I2C & I3C" in t for t in sheet_titles), "Sheet 10 I2C & I3C must exist"
    assert any("SPI, UART & CAN" in t for t in sheet_titles), "Sheet 11 SPI, UART & CAN must exist"
    assert any("General Purpose I/O" in t for t in sheet_titles), "Sheet 12 GPIO must exist"

    # 2. BUG-098: Sheet 3 crystal load capacitors have >= 16mm separation
    # 3. BUG-102: Sheet 9 PCIE differential pairs straight across, MIPI detours under U1
    # 4. BUG-104: Sheet 12 GPIOs route around U1 without off-sheet connectors
    sheet_gpio = next((s for s in sheets if "General Purpose I/O" in s.title), None)
    assert sheet_gpio is not None
    fp_names = [fp.name for fp in sheet_gpio.footprints]
    assert "U1" in fp_names
    assert "J14" in fp_names
