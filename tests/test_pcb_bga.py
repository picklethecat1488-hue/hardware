"""Unit tests for BGA footprint generation and fanout breakout router."""

import math
import pytest
from model.pcb import BgaFanoutModel
from provider.pcb.bga_fanout import BGAFanoutRouter, BGAPad, BGAEscapeRoute


@pytest.fixture
def bga_196_config() -> BgaFanoutModel:
    """Create a 196-ball 0.65mm pitch BGA configuration."""
    return BgaFanoutModel(
        pitch_mm=0.65,
        ball_dia_mm=0.35,
        pad_dia_mm=0.30,
        strategy="hybrid",
        escape_layers=["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"],
    )


def test_jedec_pin_label_convention():
    """Verify JEDEC alphanumeric pin labeling excludes confusing letters I, O, Q, S, X, Z."""
    # Rows 0-19: A, B, C, D, E, F, G, H, J, K, L, M, N, P, R, T, U, V, W, Y
    expected_rows = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "J",
        "K",
        "L",
        "M",
        "N",
        "P",
        "R",
        "T",
        "U",
        "V",
        "W",
        "Y",
    ]
    for r_idx, exp_letter in enumerate(expected_rows):
        label = BGAFanoutRouter.get_pin_label(r_idx, 0)
        assert label == f"{exp_letter}1", f"Row {r_idx} expected {exp_letter}1, got {label}"

    # Verify column 1-indexing
    assert BGAFanoutRouter.get_pin_label(0, 0) == "A1"
    assert BGAFanoutRouter.get_pin_label(0, 13) == "A14"
    assert BGAFanoutRouter.get_pin_label(13, 13) == "P14"


def test_bga_pad_matrix_generation(bga_196_config: BgaFanoutModel):
    """Verify 14x14 BGA pad matrix generation, symmetry, and ring classification."""
    router = BGAFanoutRouter(rows=14, cols=14, config=bga_196_config, center_pos=(10.0, 20.0))
    pads = router.generate_pads()

    assert len(pads) == 196

    # Verify corner pads and ring numbers
    pad_map = {p.name: p for p in pads}
    assert "A1" in pad_map
    assert "A14" in pad_map
    assert "P1" in pad_map
    assert "P14" in pad_map

    # Perimeter pads must be ring 0
    assert pad_map["A1"].ring == 0
    assert pad_map["A7"].ring == 0
    assert pad_map["P14"].ring == 0

    # Ring 1 pads
    assert pad_map["B2"].ring == 1
    assert pad_map["B13"].ring == 1

    # Center pads in 14x14 matrix: rows 6-7, cols 6-7 (G7, G8, H7, H8) -> ring 6
    assert pad_map["G7"].ring == 6
    assert pad_map["H8"].ring == 6

    # Center alignment check
    xs = [p.x_mm for p in pads]
    ys = [p.y_mm for p in pads]
    assert math.isclose((min(xs) + max(xs)) / 2.0, 10.0, abs_tol=1e-4)
    assert math.isclose((min(ys) + max(ys)) / 2.0, 20.0, abs_tol=1e-4)


def test_bga_fanout_routing_dogbone_and_vippo(bga_196_config: BgaFanoutModel):
    """Verify hybrid fanout generates diagonal dogbones for outer rings and VIPPO for inner rings."""
    router = BGAFanoutRouter(rows=14, cols=14, config=bga_196_config, center_pos=(0.0, 0.0))
    routes = router.route_fanouts()

    assert len(routes) == 196
    route_map = {r.pad.name: r for r in routes}

    # Outer ring 0: A1 must have a dogbone via offset diagonally away from center
    route_a1 = route_map["A1"]
    assert route_a1.pad.ring == 0
    assert len(route_a1.trace_path) == 2
    # A1 is in quadrant 2 (-x, +y), so dogbone offset is (-dx, +dy)
    assert route_a1.via_x_mm < route_a1.pad.x_mm
    assert route_a1.via_y_mm > route_a1.pad.y_mm
    assert route_a1.escape_layer == "F.Cu"

    # Inner ring 2+: G7 (ring 6) must use Via-In-Pad (VIPPO) with via directly on pad center
    route_g7 = route_map["G7"]
    assert route_g7.pad.ring == 6
    assert math.isclose(route_g7.via_x_mm, route_g7.pad.x_mm, abs_tol=1e-5)
    assert math.isclose(route_g7.via_y_mm, route_g7.pad.y_mm, abs_tol=1e-5)
    assert len(route_g7.trace_path) == 1
    # Should escape on an internal copper layer
    assert route_g7.escape_layer in ("In2.Cu", "In3.Cu", "B.Cu")
