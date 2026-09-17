"""Unit tests for PCB manufacturing artifact export (Gerber, BOM, CPL, SVG, KiCad, STEP, iBOM)."""

import csv
import zipfile
from pathlib import Path
import pytest

from unittest.mock import MagicMock
from model.pcb import (
    LayerType,
    StackupLayerModel,
    StackupModel,
    PCBConfig,
)
from model.wiring import Wiring, FootprintModel, PinModel, PinSide, NetModel, LabelModel
from provider.pcb.exporter import PCBExporter


@pytest.fixture
def mock_wiring() -> MagicMock:
    """Create a sample Wiring model with footprints and net connections."""
    fp1 = FootprintModel(
        name="U1",
        package="BGA-196",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        dimensions=(12.0, 12.0, 1.2),
        pins=[
            PinModel(name="A1", position=(-4.0, 4.0, 0.0), label="A1", side=PinSide.LEFT),
            PinModel(name="A2", position=(-3.35, 4.0, 0.0), label="A2", side=PinSide.LEFT),
            PinModel(name="GND", position=(0.0, 0.0, 0.0), label="GND", side=PinSide.LEFT),
        ],
        label=LabelModel(text="MCU_HOST", position=(0.0, 0.0, 0.0), align=("center", "center")),
        mpn="STM32H7B3IIT6",
        supplier_pn="C2682619",
    )
    fp2 = FootprintModel(
        name="C1",
        package="0402",
        position=(10.0, 5.0, 0.0),
        rotation=(0.0, 0.0, 90.0),
        dimensions=(1.0, 0.5, 0.5),
        pins=[
            PinModel(name="1", position=(9.5, 5.0, 0.0), label="1", side=PinSide.LEFT),
            PinModel(name="2", position=(10.5, 5.0, 0.0), label="2", side=PinSide.RIGHT),
        ],
        label=LabelModel(text="100nF", position=(0.0, 0.0, 0.0), align=("center", "center")),
        mpn="CL05B104KO5NNNC",
        supplier_pn="C1525",
    )
    net_vdd = NetModel(
        name="VDD_3V3",
        color="#ff0000",
        pins=[("U1", "A1"), ("C1", "1")],
    )
    net_gnd = NetModel(
        name="GND",
        color="#000000",
        pins=[("U1", "GND"), ("C1", "2")],
    )
    wiring = MagicMock()
    wiring.footprints = [fp1, fp2]
    wiring.nets = [net_vdd, net_gnd]
    return wiring


@pytest.fixture
def mock_pcb_config() -> PCBConfig:
    """Create a 4-layer PCBConfig for export testing."""
    stackup = StackupModel(
        layers=[
            StackupLayerModel(name="F.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
            StackupLayerModel(name="Prepreg1", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100),
            StackupLayerModel(name="In1.Cu", layer_type=LayerType.GROUND, thickness_mm=0.035),
            StackupLayerModel(name="Core", layer_type=LayerType.DIELECTRIC, thickness_mm=1.000),
            StackupLayerModel(name="In2.Cu", layer_type=LayerType.POWER, thickness_mm=0.035),
            StackupLayerModel(name="Prepreg2", layer_type=LayerType.DIELECTRIC, thickness_mm=0.100),
            StackupLayerModel(name="B.Cu", layer_type=LayerType.SIGNAL, thickness_mm=0.035),
        ],
        finish="ENIG",
    )
    return PCBConfig(
        name="TestBoard",
        board_type="rigid",
        dimensions_mm=(50.0, 40.0, 1.6),
        stackup=stackup,
    )


def test_export_kicad_pcb(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of KiCad 8 .kicad_pcb S-expression file."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "test.kicad_pcb"
    res = exporter.export_kicad_pcb(out_file)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "(kicad_pcb" in content
    assert "(version" in content
    assert "F.Cu" in content
    assert "In1.Cu" in content
    assert "B.Cu" in content
    assert "MCU_HOST" in content
    assert "VDD_3V3" in content


def test_export_kicad_sch(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of KiCad 8 .kicad_sch schematic file with embedded lib_symbols and net labels."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "test.kicad_sch"
    res = exporter.export_kicad_sch(out_file)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "(kicad_sch" in content
    assert "(version" in content
    assert "(lib_symbols" in content
    assert "BGA-196" in content
    assert "rectangle" in content
    assert "pin passive line" in content
    assert "U1" in content
    assert "C1" in content
    assert "VDD_3V3" in content
    assert "GND" in content


def test_export_bom_csv(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of supplier Bill of Materials (BOM) CSV."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "bom.csv"
    res = exporter.export_bom_csv(out_file)

    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    refs = [r["Designator"] for r in rows]
    assert "U1" in refs
    assert "C1" in refs

    row_u1 = next(r for r in rows if r["Designator"] == "U1")
    assert row_u1["MPN"] == "STM32H7B3IIT6"
    assert row_u1["Supplier_PN"] == "C2682619"


def test_export_pick_and_place_csv(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of Centroid / Pick-and-Place (CPL) CSV."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "pos.csv"
    res = exporter.export_pick_and_place_csv(out_file)

    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    row_c1 = next(r for r in rows if r["Designator"] == "C1")
    assert "10.0000mm" in row_c1["Mid X"]
    assert "5.0000mm" in row_c1["Mid Y"]
    assert "90.0" in row_c1["Rotation"]


def test_export_schematic_svg(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify generation of SVG vector schematic."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "schematic.svg"
    res = exporter.export_schematic_svg(out_file)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "</svg>" in content
    assert "TestBoard Schematic" in content
    assert "MCU_HOST" in content


def test_export_board_archive(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify creation of board layer and Excellon drill zip archive."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "board.zip"
    res = exporter.export_board_archive(out_file)

    assert res.exists()
    with zipfile.ZipFile(res, "r") as zf:
        namelist = zf.namelist()
        assert "TestBoard.kicad_pcb" in namelist
        assert any(n.endswith("-F_Cu.gbr") for n in namelist)
        assert any(n.endswith("-B_Cu.gbr") for n in namelist)
        assert any(n.endswith("-Edge_Cuts.gbr") for n in namelist)
        assert any(n.endswith(".drl") for n in namelist)


def test_export_board_directory(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of canonical KiCad board and kicad-cli manufacturing files into directory."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_dir = tmp_path / "board"
    exported = exporter.export_board(out_dir)

    assert (out_dir / "TestBoard.kicad_pcb").is_file()
    assert "TestBoard.kicad_pcb" in exported
    assert (out_dir / "TestBoard-F_Cu.gbr").is_file()
    assert (out_dir / "TestBoard-B_Cu.gbr").is_file()
    assert (out_dir / "TestBoard-Edge_Cuts.gbr").is_file()
    assert (out_dir / "TestBoard.drl").is_file()
    assert (out_dir / "TestBoard-job.gbrjob").is_file()


def test_export_interactive_bom(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify generation of interactive HTML BOM."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "ibom.html"
    res = exporter.export_interactive_bom(out_file)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "TestBoard - Interactive Bill of Materials" in content
    assert "STM32H7B3IIT6" in content
    assert "C2682619" in content


def test_export_step_solid(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of 3D solid STEP substrate for enclosure CAD assembly."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "board.step"
    res = exporter.export_step_solid(out_file)

    assert res.exists()
    assert res.stat().st_size > 500  # Non-trivial STEP file size
