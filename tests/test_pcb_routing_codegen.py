"""Unit tests for templatized PCB routing code generator and dynamic module loader."""

import ast
from pathlib import Path
from model.pcb import TraceSegmentModel, ViaModel
from provider.pcb.router import PCBAutoRouter


def test_generate_routing_code_syntax_and_primitives() -> None:
    """Verify generate_routing_code produces valid, compilable Python source using build123d primitives."""
    traces = [
        # Multi-bend path
        TraceSegmentModel(
            net="CAP_TX0",
            layer="F.Cu",
            width_mm=0.15,
            start_mm=(0.0, 0.0),
            end_mm=(5.0, 0.0),
        ),
        TraceSegmentModel(
            net="CAP_TX0",
            layer="F.Cu",
            width_mm=0.15,
            start_mm=(5.0, 0.0),
            end_mm=(5.0, 10.0),
        ),
        # 2-point line
        TraceSegmentModel(
            net="CAP_TX0",
            layer="F.Cu",
            width_mm=0.15,
            start_mm=(5.0, 10.0),
            end_mm=(8.0, 10.0),
        ),
        # Distinct net on B.Cu
        TraceSegmentModel(
            net="GND",
            layer="B.Cu",
            width_mm=0.20,
            start_mm=(-1.0, -1.0),
            end_mm=(2.0, -1.0),
        ),
    ]
    vias = [
        ViaModel(
            net="GND",
            position_mm=(2.0, -1.0),
            pad_diameter_mm=0.36,
            drill_diameter_mm=0.16,
            layer_start="F.Cu",
            layer_end="B.Cu",
        ),
        ViaModel(
            net="3V3",
            position_mm=(10.0, 5.0),
            pad_diameter_mm=0.60,
            drill_diameter_mm=0.30,
            layer_start="F.Cu",
            layer_end="B.Cu",
        ),
    ]

    code = PCBAutoRouter.generate_routing_code(
        traces=traces,
        vias=vias,
        function_prefix="test_board",
        board_name="Test Board",
    )

    # 1. Parse AST to verify valid Python syntax
    parsed = ast.parse(code)
    assert parsed is not None

    # 2. Check essential primitives and identifiers in generated code
    assert "def get_test_board_traces() -> List[TraceSegmentModel]:" in code
    assert "def get_test_board_vias() -> List[ViaModel]:" in code
    assert "def get_test_board_routing() -> Tuple[List[TraceSegmentModel], List[ViaModel]]:" in code
    assert "with BuildTraces(" in code
    assert "with BuildLine():" in code
    assert "Polyline(" in code
    assert "make_trace(" in code
    assert "with BuildVias(" in code
    assert 'Via(\n            "GND",' in code or 'Via("GND",' in code or 'Via(\n            "3V3",' in code


def test_save_and_load_routing_python_roundtrip(tmp_path: Path) -> None:
    """Verify saving to Python file and loading back preserves 1:1 trace segments and vias."""
    out_file = tmp_path / "custom_routing.py"

    traces = [
        TraceSegmentModel(
            net="SIG_A",
            layer="F.Cu",
            width_mm=0.12,
            start_mm=(1.0, 2.0),
            end_mm=(5.0, 2.0),
        ),
        TraceSegmentModel(
            net="SIG_A",
            layer="F.Cu",
            width_mm=0.12,
            start_mm=(5.0, 2.0),
            end_mm=(5.0, 8.0),
        ),
        TraceSegmentModel(
            net="SIG_B",
            layer="B.Cu",
            width_mm=0.15,
            start_mm=(0.0, 0.0),
            end_mm=(10.0, 0.0),
        ),
    ]
    vias = [
        ViaModel(
            net="SIG_A",
            position_mm=(5.0, 8.0),
            pad_diameter_mm=0.36,
            drill_diameter_mm=0.16,
            layer_start="F.Cu",
            layer_end="B.Cu",
        ),
    ]

    saved = PCBAutoRouter.save_routing_python(
        path=out_file,
        traces=traces,
        vias=vias,
        function_prefix="roundtrip_board",
        board_name="Roundtrip Board",
    )
    assert saved.exists()
    assert saved.is_file()

    loaded_traces, loaded_vias = PCBAutoRouter.load_routing_python(saved)

    assert len(loaded_traces) == len(traces)
    assert len(loaded_vias) == len(vias)

    orig_trace_keys = {(t.net, t.layer, round(t.width_mm, 4), tuple(sorted([t.start_mm, t.end_mm]))) for t in traces}
    loaded_trace_keys = {
        (t.net, t.layer, round(t.width_mm, 4), tuple(sorted([t.start_mm, t.end_mm]))) for t in loaded_traces
    }
    assert orig_trace_keys == loaded_trace_keys

    orig_via_keys = {
        (v.net, v.position_mm, v.pad_diameter_mm, v.drill_diameter_mm, v.layer_start, v.layer_end) for v in vias
    }
    loaded_via_keys = {
        (v.net, v.position_mm, v.pad_diameter_mm, v.drill_diameter_mm, v.layer_start, v.layer_end) for v in loaded_vias
    }
    assert orig_via_keys == loaded_via_keys


def test_carrier_board_persisted_routing_module() -> None:
    """Verify projects/carrier_board/carrier_board_routing.py loads and contains all carrier board nets."""
    from projects.carrier_board.carrier_board_routing import (
        get_carrier_board_traces,
        get_carrier_board_vias,
        get_carrier_board_routing,
    )

    traces = get_carrier_board_traces()
    vias = get_carrier_board_vias()
    r_traces, r_vias = get_carrier_board_routing()

    assert len(traces) == 1607
    assert len(vias) == 446
    assert len(r_traces) == 1607
    assert len(r_vias) == 446

    # Verify key carrier board power and high-speed nets are present
    nets = {t.net for t in traces}
    assert "3V3" in nets
    assert "GND" in nets
    assert "USB_DP" in nets
    assert "USB_DM" in nets
    assert "SPI0_SCK" in nets


def test_load_routing_python_missing_file_raises(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised when target module does not exist."""
    import pytest

    with pytest.raises(FileNotFoundError):
        PCBAutoRouter.load_routing_python(tmp_path / "nonexistent.py")
