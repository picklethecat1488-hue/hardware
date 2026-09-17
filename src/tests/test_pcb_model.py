"""Unit tests for multi-layer PCB stackup models, layer symmetry, and impedance calculations."""

import math
import pytest
from model.pcb import (
    LayerType,
    StackupLayerModel,
    StackupModel,
    DifferentialPairModel,
    NetClassModel,
    PCBConfig,
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
