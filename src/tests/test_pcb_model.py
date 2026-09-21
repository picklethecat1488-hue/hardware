"""Unit tests for multi-layer PCB stackup models, layer symmetry, and impedance calculations."""

import math
from pathlib import Path
import pytest
from model.pcb import (
    LayerType,
    StackupLayerModel,
    StackupModel,
    DifferentialPairModel,
    NetClassModel,
    AssemblyTestStepModel,
    AssemblyTestModel,
    PCBMaterialModel,
    PCBMaterialsModel,
    PCBDesignRulesModel,
    PCBConfig,
    SheetSize,
    SilkscreenTextModel,
    SchematicSheetModel,
    MountingHoleModel,
)


@pytest.fixture
def standard_6_layer_stackup():
    """Create a standard 6-layer ENIG stackup (Sig - GND - Sig - PWR - GND - Sig)."""
    return StackupModel(
        layers=[
            StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.2
            ),
            StackupLayerModel(name="In1.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
            StackupLayerModel(
                name="Core1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.500, dielectric_constant=4.4
            ),
            StackupLayerModel(name="In2.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.200, dielectric_constant=4.2
            ),
            StackupLayerModel(name="In3.Cu", layer_type=LayerType.POWER, thickness_mm=0.035),
            StackupLayerModel(
                name="Core2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.500, dielectric_constant=4.4
            ),
            StackupLayerModel(name="In4.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
            StackupLayerModel(
                name="Prepreg3", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.2
            ),
            StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
        ],
        finish="ENIG",
    )


def test_stackup_validation_layer_count():
    """Verify that odd copper layer counts raise a validation error."""
    with pytest.raises(ValueError, match="even copper layer count"):
        StackupModel(
            layers=[
                StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
                StackupLayerModel(
                    name="Prepreg1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=4.2
                ),
                StackupLayerModel(name="In1.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
                StackupLayerModel(
                    name="Core", layer_type=LayerType.DIELECTRIC, thickness_mm=0.500, dielectric_constant=4.4
                ),
                StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            ]
        )


def test_stackup_properties(standard_6_layer_stackup):
    """Verify copper layer count and total physical thickness calculations."""
    assert standard_6_layer_stackup.copper_layer_count == 6
    total_t = standard_6_layer_stackup.total_thickness_mm
    assert 1.5 <= total_t <= 1.7
    assert standard_6_layer_stackup.finish == "ENIG"


def test_microstrip_single_ended_impedance():
    """Verify single-ended microstrip characteristic impedance calculation (target 50 Ohms)."""
    # 0.15mm trace, 0.035mm copper, 0.100mm height, er=4.2 -> approx 50 Ohms
    z0 = StackupModel.calculate_microstrip_impedance(
        width_mm=0.150,
        copper_thickness_mm=0.035,
        height_mm=0.100,
        dielectric_er=4.2,
    )
    assert 48.0 <= z0 <= 55.0


def test_differential_microstrip_impedance_pcie():
    """Verify PCIe 85-Ohm differential microstrip impedance calculation."""
    # 0.15mm trace width, 0.13mm spacing, 0.100mm height, er=4.2
    z_diff = StackupModel.calculate_differential_microstrip_impedance(
        width_mm=0.150,
        spacing_mm=0.130,
        copper_thickness_mm=0.035,
        height_mm=0.100,
        dielectric_er=4.2,
    )
    assert 80.0 <= z_diff <= 95.0


def test_stripline_differential_impedance():
    """Verify internal stripline differential impedance calculation."""
    z_diff = StackupModel.calculate_differential_stripline_impedance(
        width_mm=0.120,
        spacing_mm=0.180,
        copper_thickness_mm=0.035,
        height_total_mm=0.400,
        dielectric_er=4.2,
    )
    assert 75.0 <= z_diff <= 95.0


def test_get_reference_plane(standard_6_layer_stackup):
    """Verify resolving nearest reference plane and dielectric height from signal layer."""
    ref_layer, h, er = standard_6_layer_stackup.get_reference_plane("F.Cu")
    assert ref_layer.name == "In1.Cu"
    assert math.isclose(h, 0.100, abs_tol=1e-5)
    assert math.isclose(er, 4.2, abs_tol=1e-5)


def test_stackup_layer_thickness_and_dielectric_validation():
    """Verify non-negative and positive thickness and dielectric permittivity constraints."""
    # Thickness must be strictly positive (> 0)
    with pytest.raises(ValueError):
        StackupLayerModel(name="ZeroThick", layer_type=LayerType.DIELECTRIC, thickness_mm=0.0)

    with pytest.raises(ValueError):
        StackupLayerModel(name="NegThick", layer_type=LayerType.DIELECTRIC, thickness_mm=-0.1)

    # Dielectric permittivity must be positive (> 0)
    with pytest.raises(ValueError):
        StackupLayerModel(name="NegEr", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, dielectric_constant=-2.0)

    # Loss tangent must be non-negative (>= 0)
    with pytest.raises(ValueError):
        StackupLayerModel(name="NegLoss", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100, loss_tangent=-0.01)


def test_pcb_materials_model_from_yaml():
    """Verify loading dedicated pcb_materials.yaml into PCBMaterialsModel."""
    materials = PCBMaterialsModel.default()
    assert "fr4_core" in materials.material
    assert "polyimide_flex" in materials.material
    assert "copper_1oz" in materials.material

    fr4 = materials["fr4_core"]
    assert fr4.dielectric_constant == 4.4
    assert fr4.loss_tangent == 0.018

    polyimide = materials.get("polyimide_flex")
    assert polyimide is not None
    assert polyimide.dielectric_constant == 3.4
    assert polyimide.loss_tangent == 0.002

    copper = materials["copper_1oz"]
    assert copper.conductivity_ms_m == 58.0


def test_assembly_test_model_validation():
    """Verify factory assembly test plan and instruction validation."""
    step = AssemblyTestStepModel(
        step_id="TEST_IMP_1",
        description="Check 50-ohm single-ended impedance",
        test_type="impedance",
        net_or_points=["RF_ANT"],
        expected_nominal=50.0,
        tolerance_pct=10.0,
        unit="ohm",
    )
    assert step.expected_nominal == 50.0
    assert step.tolerance_pct == 10.0

    test_plan = AssemblyTestModel(
        instructions=[step],
        test_fixture="flying_probe",
        pass_criteria="all_steps_within_tolerance",
    )
    assert len(test_plan.instructions) == 1
    assert test_plan.test_fixture == "flying_probe"


def test_sheet_size_and_silkscreen_model(standard_6_layer_stackup):
    """Verify drawing sheet dimensions and silkscreen text modeling."""
    cfg = PCBConfig(
        name="TestCarrier",
        board_type="rigid",
        dimensions_mm=(60.0, 90.0, 1.6),
        stackup=standard_6_layer_stackup,
        sheet_size=SheetSize.A4,
        silkscreen_texts=[
            SilkscreenTextModel(
                text="REV 1.0",
                layer="F.SilkS",
                position=(0.0, 35.0),
                font_size=1.2,
            ),
            SilkscreenTextModel(
                text="BOTTOM SHIELD",
                layer="B.SilkS",
                position=(0.0, -35.0),
                mirror=True,
            ),
        ],
    )
    assert cfg.sheet_size == SheetSize.A4
    assert cfg.sheet_width_mm == 297.0
    assert cfg.sheet_height_mm == 210.0
    assert cfg.sheet_center_x_mm == 148.5
    assert cfg.sheet_center_y_mm == 105.0
    assert len(cfg.silkscreen_texts) == 2
    assert cfg.silkscreen_texts[0].text == "REV 1.0"
    assert cfg.silkscreen_texts[1].mirror is True


def test_build_silkscreen_context_manager_and_locations():
    """Verify that BuildSilkscreen captures texts using build123d Locations and PolarLocations."""
    from build123d import Locations, PolarLocations
    from provider.pcb.silkscreen import BuildSilkscreen, SilkscreenText

    with BuildSilkscreen(default_layer="F.SilkS") as silk:
        with Locations((10.0, 20.0)):
            SilkscreenText("TOP_LABEL", font_size=1.5, thickness=0.2)
        with Locations((-10.0, -20.0)):
            SilkscreenText("BOTTOM_LABEL", layer="B.SilkS", font_size=1.0)
        with PolarLocations(radius=25.0, count=4):
            t_polar = SilkscreenText("PIN", font_size=0.8)

    assert len(silk.texts) == 6  # 1 + 1 + 4
    assert silk.texts[0].text == "TOP_LABEL"
    assert silk.texts[0].position == (10.0, 20.0)
    assert silk.texts[0].layer == "F.SilkS"
    assert silk.texts[0].mirror is False

    assert silk.texts[1].text == "BOTTOM_LABEL"
    assert silk.texts[1].position == (-10.0, -20.0)
    assert silk.texts[1].layer == "B.SilkS"
    assert silk.texts[1].mirror is True  # Auto-mirrored on B.SilkS

    assert len(t_polar.models) == 4
    for pt in t_polar.models:
        assert pt.text == "PIN"

    # Verify conversion to 2D CAD shapes
    shapes = silk.to_shapes()
    assert len(shapes) == 6


def test_test_board_provider_cad_silkscreen():
    """Verify that TestBoardProvider dynamically generates silkscreen text from CAD geometry."""
    from projects.test_board.provider import TestBoardProvider

    provider = TestBoardProvider()
    texts = provider.silkscreen()
    assert len(texts) >= 3
    assert texts[0].text == "TEST BOARD CARRIER REV 1.0"
    assert texts[0].position == (0.0, 26.0)
    assert texts[0].layer == "F.SilkS"

    assert texts[1].text == "LAYER 1-6 RIGID-FLEX"
    assert texts[1].position == (0.0, -28.0)

    assert texts[2].text == "BOTTOM SHIELD / GROUND REF"
    assert texts[2].layer == "B.SilkS"
    assert texts[2].mirror is True

    # Check that pcb_config inherits them
    pcb_cfg = provider.pcb_config
    assert pcb_cfg is not None
    assert len(pcb_cfg.silkscreen_texts) >= 3


def test_schematic_sheet_model():
    """Verify SchematicSheetModel creation and field validations."""
    sheet = SchematicSheetModel(
        title="Power Regulation & Inrush Control",
        description="Regulates 5V to 3.3V system rail",
        components=["U1", "Q1", "C1"],
        pin_breakouts={"U1": ["VIN", "VOUT", "GND"]},
    )
    assert sheet.title == "Power Regulation & Inrush Control"
    assert sheet.description == "Regulates 5V to 3.3V system rail"
    assert sheet.components == ["U1", "Q1", "C1"]
    assert sheet.pin_breakouts["U1"] == ["VIN", "VOUT", "GND"]


def test_mounting_hole_model():
    """Verify MountingHoleModel creation, drill/pad dimensions, and plated nets."""
    hole_plated = MountingHoleModel(
        name="MH1",
        position_mm=(-25.5, -40.5),
        drill_diameter_mm=3.2,
        pad_diameter_mm=4.5,
        plated=True,
        net="GND",
    )
    assert hole_plated.name == "MH1"
    assert hole_plated.position_mm == (-25.5, -40.5)
    assert hole_plated.drill_diameter_mm == 3.2
    assert hole_plated.pad_diameter_mm == 4.5
    assert hole_plated.plated is True
    assert hole_plated.net == "GND"

    hole_unplated = MountingHoleModel(
        name="MH5",
        position_mm=(0.0, 0.0),
        drill_diameter_mm=2.5,
        plated=False,
    )
    assert hole_unplated.plated is False
    assert hole_unplated.net is None


def test_shared_footprint_libraries_loading_and_resolution(tmp_path: Path):
    """Verify loading shared SMD, TH, and IC footprint libraries and merging into Wiring models."""
    from model.wiring import Wiring, load_shared_footprints

    shared = load_shared_footprints()
    assert "0402" in shared
    assert "0603" in shared
    assert "SOT-23" in shared
    assert "pin_header_1x2" in shared
    assert "QFN-24" in shared
    assert "USB-C-16P" in shared

    # Verify that a custom wiring YAML with imports resolves package footprints automatically
    custom_yaml = tmp_path / "custom_wiring.yaml"
    custom_yaml.write_text(
        """
imports:
  - footprints/smd.yaml
  - footprints/thru_hole.yaml
  - footprints/ic.yaml

footprints:
  - name: R_TEST
    package: "0402"
    position: [5.0, 10.0, 0.8]
  - name: J_HEADER
    package: "pin_header_1x2"
    position: [-5.0, -10.0, 0.8]
"""
    )

    w = Wiring(custom_yaml)
    fps = w.footprints
    assert len(fps) == 2

    # R_TEST inherited dimensions and 2 pins from 0402
    r_test = next(fp for fp in fps if fp.name == "R_TEST")
    assert r_test.dimensions == (1.0, 0.5, 0.35)
    assert len(r_test.pins) == 2
    assert r_test.pins[0].name == "1"
    assert r_test.pins[0].pad_type == "smd"

    # J_HEADER inherited dimensions and 2 pins from pin_header_1x2
    j_hdr = next(fp for fp in fps if fp.name == "J_HEADER")
    assert j_hdr.dimensions == (5.08, 2.54, 8.5)
    assert len(j_hdr.pins) == 2
    assert j_hdr.pins[0].pad_type == "thru_hole"
    assert j_hdr.pins[0].drill_dia_mm == 1.00


def test_pcb_design_rules_model_and_kicad_pro_generation():
    """Verify PCBDesignRulesModel defaults, custom rules, and .kicad_pro dictionary serialization."""
    default_rules = PCBDesignRulesModel()
    assert default_rules.min_clearance_mm == 0.12
    assert default_rules.min_track_width_mm == 0.10
    assert default_rules.min_copper_edge_clearance_mm == 0.15

    kicad_rules = default_rules.to_kicad_pro_rules()
    assert kicad_rules["min_clearance"] == 0.12
    assert kicad_rules["min_track_width"] == 0.10
    assert kicad_rules["board_edge_clearance"] == 0.15

    custom_rules = PCBDesignRulesModel(
        min_clearance_mm=0.20,
        min_track_width_mm=0.25,
        min_copper_edge_clearance_mm=0.30,
        min_via_diameter_mm=0.50,
        default_track_width_mm=0.30,
        default_via_diameter_mm=0.50,
        default_via_drill_mm=0.25,
    )
    pro_dict = custom_rules.to_kicad_pro_dict(
        net_classes=[
            NetClassModel(
                name="POWER",
                clearance_mm=0.35,
                trace_width_mm=0.50,
                via_dia_mm=0.70,
                via_drill_mm=0.35,
            )
        ]
    )

    assert pro_dict["board"]["design_settings"]["rules"]["min_clearance"] == 0.20
    assert pro_dict["board"]["design_settings"]["rules"]["min_track_width"] == 0.25
    assert len(pro_dict["net_settings"]["classes"]) == 2
    assert pro_dict["net_settings"]["classes"][0]["name"] == "Default"
    assert pro_dict["net_settings"]["classes"][0]["track_width"] == 0.30
    assert pro_dict["net_settings"]["classes"][1]["name"] == "POWER"
    assert pro_dict["net_settings"]["classes"][1]["clearance"] == 0.35
