"""Unit tests for capacitive sensing electrode and flexible PCB ground hatch generator."""

import math
import pytest
from model.pcb import CapacitiveElectrodeModel
from provider.pcb.capacitive import CapacitiveSensingGenerator, CapacitiveGeometry, HatchLine


@pytest.fixture
def interdigital_sensor_config() -> CapacitiveElectrodeModel:
    """Create an interdigital capacitive sensor model."""
    return CapacitiveElectrodeModel(
        name="WaterLevelSensor",
        electrode_type="mutual",
        shape="interdigital",
        area_mm=(20.0, 30.0),
        pitch_mm=1.0,
        gap_mm=0.25,
        drive_shield=True,
        hatch_ground_pour=True,
        hatch_pitch_mm=1.0,
        hatch_line_width_mm=0.15,
    )


def test_interdigital_electrode_generation(interdigital_sensor_config: CapacitiveElectrodeModel):
    """Verify synthesis of interleaved TX and RX comb fingers and busbars."""
    gen = CapacitiveSensingGenerator(config=interdigital_sensor_config, center=(0.0, 0.0))
    geom: CapacitiveGeometry = gen.generate()

    assert geom.name == "WaterLevelSensor"
    # tx_fingers includes TX busbar + multiple comb fingers
    assert len(geom.tx_fingers) > 5
    # rx_fingers includes RX busbar + multiple comb fingers
    assert len(geom.rx_fingers) > 5

    # TX busbar should be at the west (-X) edge
    tx_busbar = geom.tx_fingers[0]
    xs_tx_busbar = [p[0] for p in tx_busbar]
    assert math.isclose(min(xs_tx_busbar), -10.0, abs_tol=1e-3)

    # RX busbar should be at the east (+X) edge
    rx_busbar = geom.rx_fingers[0]
    xs_rx_busbar = [p[0] for p in rx_busbar]
    assert math.isclose(max(xs_rx_busbar), 10.0, abs_tol=1e-3)

    # Guard ring should surround the 20x30 area plus offset
    assert len(geom.guard_ring) == 5  # Closed loop 4 corners + 1 to close
    xs_guard = [p[0] for p in geom.guard_ring]
    ys_guard = [p[1] for p in geom.guard_ring]
    assert min(xs_guard) < -10.0
    assert max(xs_guard) > 10.0
    assert min(ys_guard) < -15.0
    assert max(ys_guard) > 15.0


def test_hatched_ground_lines(interdigital_sensor_config: CapacitiveElectrodeModel):
    """Verify 45-degree cross-hatch line synthesis for flexible low-capacitance ground pour."""
    gen = CapacitiveSensingGenerator(config=interdigital_sensor_config, center=(5.0, 5.0))
    geom: CapacitiveGeometry = gen.generate()

    assert len(geom.hatch_lines) > 0
    slopes = []
    for line in geom.hatch_lines:
        assert math.isclose(line.width_mm, 0.15, abs_tol=1e-4)
        # Verify lines are within or at boundary bounds
        assert -5.0 <= line.start[0] <= 15.0
        assert -10.0 <= line.start[1] <= 20.0
        assert -5.0 <= line.end[0] <= 15.0
        assert -10.0 <= line.end[1] <= 20.0
        dx = line.end[0] - line.start[0]
        dy = line.end[1] - line.start[1]
        if abs(dx) > 1e-4:
            slopes.append(round(dy / dx, 2))

    # Must contain both +45 deg (+1.0 slope) and -45 deg (-1.0 slope) lines
    assert any(math.isclose(s, 1.0, abs_tol=0.1) for s in slopes)
    assert any(math.isclose(s, -1.0, abs_tol=0.1) for s in slopes)


def test_solid_touch_pad_generation():
    """Verify generation of solid touch pad geometry without comb fingers."""
    config = CapacitiveElectrodeModel(
        name="TouchButton",
        electrode_type="self",
        shape="pad",
        area_mm=(12.0, 12.0),
        drive_shield=False,
        hatch_ground_pour=False,
    )
    gen = CapacitiveSensingGenerator(config=config, center=(0.0, 0.0))
    geom = gen.generate()

    assert len(geom.tx_fingers) == 1
    assert len(geom.rx_fingers) == 0
    assert len(geom.guard_ring) == 0
    assert len(geom.hatch_lines) == 0

    pad_poly = geom.tx_fingers[0]
    assert len(pad_poly) == 4
    xs = [p[0] for p in pad_poly]
    ys = [p[1] for p in pad_poly]
    assert math.isclose(max(xs) - min(xs), 12.0, abs_tol=1e-4)
    assert math.isclose(max(ys) - min(ys), 12.0, abs_tol=1e-4)
