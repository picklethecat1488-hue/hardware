"""Unit tests for PCB manufacturing artifact export (Gerber, BOM, CPL, SVG, KiCad, STEP, iBOM)."""

import csv
import json
import zipfile
from pathlib import Path
import pytest

import os
import sys
from unittest.mock import MagicMock, patch
from model.pcb import (
    CapacitiveElectrodeModel,
    LayerType,
    PCBConfig,
    PCBDesignRulesModel,
    SilkscreenTextModel,
    StackupLayerModel,
    StackupModel,
)
from model.wiring import Wiring, FootprintModel, PinModel, PinSide, NetModel, LabelModel
from provider.pcb.exporter import PCBExporter
from provider.pcb.kicad_cli import KiCadCLI


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
        silkscreen_texts=[SilkscreenTextModel(text="TEST PCB REV 1.0", layer="F.SilkS", position=(0.0, 15.0))],
    )


@pytest.fixture
def mock_kicad_cam_files_if_unavailable(monkeypatch):
    """Ensure CAM files are produced for export tests when kicad-cli is not installed locally."""
    if not KiCadCLI().is_available:

        def fake_export_all(self, kicad_pcb_path, output_dir, layers=None):
            stem = Path(kicad_pcb_path).stem
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            cam = {
                f"{stem}-F_Cu.gbr": out / f"{stem}-F_Cu.gbr",
                f"{stem}-B_Cu.gbr": out / f"{stem}-B_Cu.gbr",
                f"{stem}-Edge_Cuts.gbr": out / f"{stem}-Edge_Cuts.gbr",
                f"{stem}.drl": out / f"{stem}.drl",
                f"{stem}-job.gbrjob": out / f"{stem}-job.gbrjob",
            }
            for p in cam.values():
                p.touch()
            return cam

        monkeypatch.setattr(KiCadCLI, "is_available", True)
        monkeypatch.setattr(KiCadCLI, "export_all_board_files", fake_export_all)


def test_export_kicad_pcb(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export of KiCad 7/8 compatible .kicad_pcb S-expression file."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "test.kicad_pcb"
    res = exporter.export_kicad_pcb(out_file)

    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "(kicad_pcb" in content
    assert "(version" in content
    assert '(paper "A4")' in content
    assert 'gr_text "TEST PCB REV 1.0"' in content
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


def test_export_board_archive(
    tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring, mock_kicad_cam_files_if_unavailable
):
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


def test_export_board_archive_without_kicad_cli(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export_board_archive cleanly creates zip with .kicad_pcb when kicad-cli is missing."""
    with patch.object(KiCadCLI, "is_available", False):
        exporter = PCBExporter(mock_pcb_config, mock_wiring)
        out_file = tmp_path / "board_no_cli.zip"
        res = exporter.export_board_archive(out_file)

        assert res.exists()
        with zipfile.ZipFile(res, "r") as zf:
            namelist = zf.namelist()
            assert "TestBoard.kicad_pcb" in namelist
            assert not any(n.endswith(".gbr") for n in namelist)


def test_export_board_directory(
    tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring, mock_kicad_cam_files_if_unavailable
):
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


def test_export_schematic_pdf(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify generation of multi-page schematic PDF with title page, TOC, and schematic sheets."""
    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_file = tmp_path / "schematic.pdf"
    res = exporter.export_schematic_pdf(out_file)

    assert res.exists()
    assert res.is_file()
    assert res.stat().st_size > 5000  # Multi-page vector PDF

    # Read binary content to verify PDF header and trailer
    data = res.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"%%EOF" in data


def test_kicad_cli_discovery_platforms():
    """Verify kicad-cli locates standard paths across macOS, Linux, and Windows."""
    # macOS discovery
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("shutil.which", return_value=None),
        patch("sys.platform", "darwin"),
        patch.object(
            Path, "is_file", autospec=True, side_effect=lambda self: str(self) == "/opt/homebrew/bin/kicad-cli"
        ),
    ):
        cli = KiCadCLI()
        assert cli.is_available
        assert cli._local_bin == Path("/opt/homebrew/bin/kicad-cli")

    # Linux discovery
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("shutil.which", return_value=None),
        patch("sys.platform", "linux"),
        patch.object(Path, "is_file", autospec=True, side_effect=lambda self: str(self) == "/usr/bin/kicad-cli"),
    ):
        cli = KiCadCLI()
        assert cli.is_available
        assert cli._local_bin == Path("/usr/bin/kicad-cli")

    # Windows discovery
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("shutil.which", return_value=None),
        patch("sys.platform", "win32"),
        patch.object(Path, "is_file", autospec=True, side_effect=lambda self: "8.0" in str(self)),
    ):
        cli = KiCadCLI()
        assert cli.is_available
        assert "8.0" in str(cli._local_bin)


def test_kicad_cli_env_override(tmp_path: Path):
    """Verify KICAD_CLI_BIN environment variable overrides PATH discovery."""
    fake_bin = tmp_path / "custom_kicad_cli"
    fake_bin.touch()

    with patch.dict(os.environ, {"KICAD_CLI_BIN": str(fake_bin)}):
        cli = KiCadCLI()
        assert cli.is_available
        assert cli._local_bin == fake_bin


def test_kicad_cli_custom_path(tmp_path: Path):
    """Verify custom cli_path passed to constructor takes highest precedence."""
    custom_bin = tmp_path / "my_cli"
    custom_bin.touch()

    cli = KiCadCLI(cli_path=custom_bin)
    assert cli.is_available
    assert cli._local_bin == custom_bin


def test_kicad_cli_missing_raises():
    """Verify run_command raises descriptive RuntimeError when kicad-cli is not installed."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("shutil.which", return_value=None),
        patch.object(Path, "is_file", autospec=True, return_value=False),
    ):
        cli = KiCadCLI()
        assert not cli.is_available
        with pytest.raises(RuntimeError, match="kicad-cli is not installed locally"):
            cli.run_command(["version"])


def test_kicad_cli_nonzero_exit_raises(tmp_path: Path):
    """Verify run_command raises descriptive RuntimeError when kicad-cli returns non-zero."""
    fake_bin = tmp_path / "kicad-cli"
    fake_bin.touch()

    cli = KiCadCLI(cli_path=fake_bin)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Syntax error in board file", stdout="")
        with pytest.raises(RuntimeError, match="kicad-cli error \\(1\\): Syntax error in board file"):
            cli.run_command(["pcb", "export"])


def test_pcb_exporter_all_methods_integration(
    tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring, mock_kicad_cam_files_if_unavailable
):
    """Verify integration testing of kicad_pcb.j2 and kicad_sch.j2 code generators for all export methods in PCBExporter."""
    from provider.room import Room

    # Add capacitive sensor to config
    mock_pcb_config.capacitive_sensors = [
        CapacitiveElectrodeModel(
            name="SENSE_LEVEL_LOW",
            electrode_type="mutual",
            shape="interdigital",
            area_mm=(10.0, 30.0),
            channel_id=0,
            tx_pin="PA0",
            rx_pin="PA1",
            threshold_raw=2800,
        )
    ]

    exporter = PCBExporter(mock_pcb_config, mock_wiring)
    out_dir = tmp_path / "integration_export"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. export_kicad_pcb (renders kicad_pcb.j2)
    pcb_file = out_dir / "test.kicad_pcb"
    res_pcb = exporter.export_kicad_pcb(pcb_file)
    assert res_pcb.is_file()
    pcb_content = res_pcb.read_text(encoding="utf-8")
    assert "(kicad_pcb" in pcb_content
    assert '(paper "A4")' in pcb_content
    assert 'gr_text "TEST PCB REV 1.0"' in pcb_content
    assert "F.Cu" in pcb_content
    assert "B.Cu" in pcb_content
    assert "MCU_HOST" in pcb_content

    # 2. export_kicad_sch (renders kicad_sch.j2)
    sch_file = out_dir / "test.kicad_sch"
    res_sch = exporter.export_kicad_sch(sch_file)
    assert res_sch.is_file()
    sch_content = res_sch.read_text(encoding="utf-8")
    assert "(kicad_sch" in sch_content
    assert "(lib_symbols" in sch_content
    assert "BGA-196" in sch_content
    assert "VDD_3V3" in sch_content
    assert "GND" in sch_content

    # 3. export_board (invokes kicad-cli)
    board_dir = out_dir / "board"
    board_files = exporter.export_board(board_dir)
    assert "TestBoard.kicad_pcb" in board_files
    assert (board_dir / "TestBoard-F_Cu.gbr").is_file()
    assert (board_dir / "TestBoard.drl").is_file()

    # 4. export_board_archive (zip archive)
    board_zip = out_dir / "TestBoard_cad.zip"
    res_zip = exporter.export_board_archive(board_zip)
    assert res_zip.is_file()
    with zipfile.ZipFile(res_zip, "r") as zf:
        names = zf.namelist()
        assert "TestBoard.kicad_pcb" in names
        assert any(n.endswith("-F_Cu.gbr") for n in names)
        assert any(n.endswith(".drl") for n in names)

    # 5. export_bom_csv
    bom_file = out_dir / "bom.csv"
    res_bom = exporter.export_bom_csv(bom_file)
    assert res_bom.is_file()
    with open(res_bom, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert len(list(reader)) == 2

    # 6. export_pick_and_place_csv
    cpl_file = out_dir / "cpl.csv"
    res_cpl = exporter.export_pick_and_place_csv(cpl_file)
    assert res_cpl.is_file()
    with open(res_cpl, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert len(list(reader)) == 2

    # 7. export_schematic_svg
    svg_file = out_dir / "schematic.svg"
    res_svg = exporter.export_schematic_svg(svg_file)
    assert res_svg.is_file()
    assert "<svg" in res_svg.read_text(encoding="utf-8")

    # 8. export_schematic_pdf
    pdf_file = out_dir / "schematic.pdf"
    res_pdf = exporter.export_schematic_pdf(pdf_file)
    assert res_pdf.is_file()
    assert res_pdf.read_bytes().startswith(b"%PDF")

    # 9. export_capacitive_config_json
    cap_file = out_dir / "capacitive_config.json"
    res_cap = exporter.export_capacitive_config_json(cap_file)
    assert res_cap.is_file()
    with open(res_cap, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["channel_count"] == 1
        assert data["channels"][0]["name"] == "SENSE_LEVEL_LOW"
        assert data["channels"][0]["threshold_raw"] == 2800

    # 10. export_interactive_bom
    ibom_file = out_dir / "ibom.html"
    res_ibom = exporter.export_interactive_bom(ibom_file)
    assert res_ibom.is_file()
    assert "<!DOCTYPE html>" in res_ibom.read_text(encoding="utf-8")

    # 11. export_step_solid and Room STEP assembly integration
    step_file = out_dir / "board.step"
    res_step = exporter.export_step_solid(step_file)
    assert res_step.is_file()
    assert res_step.stat().st_size > 500

    # Test STEP support in Room
    room = Room()
    room.add_step("pcb_substrate", res_step, color="#00ff00", alpha=0.9)
    assert "pcb_substrate" in room
    room.add("pcb_direct_import", str(res_step))
    assert "pcb_direct_import" in room

    comp = room.compound
    assert len(comp.children) == 2

    exported_assembly = room.export_step(out_dir / "product_assembly.step")
    assert exported_assembly.is_file()
    assert exported_assembly.stat().st_size > 500


def test_provider_pcb_output_cad_archive(tmp_path: Path, mock_pcb_config: PCBConfig, monkeypatch):
    """Verify ProviderOrchestrator PCB build includes cad_zip archive."""
    from provider.provider import ProviderOrchestrator
    from provider import Section, Mode

    monkeypatch.chdir(tmp_path)
    mock_prov = MagicMock()
    mock_prov.name = "test_board"
    mock_prov.targets = ("pcb_unit",)
    mock_prov.manifest = {"pcb_unit": {Section.PCB: {"modes": [Mode.DEFAULT]}}}
    mock_prov.pcb = {}
    mock_prov.pcb_config = mock_pcb_config
    mock_prov.wiring_path = str(tmp_path / "wiring.yaml")

    orch = ProviderOrchestrator(mock_prov)
    results = orch.execute(("pcb_unit",), Section.PCB, (None,), (Mode.DEFAULT,))
    assert len(results) == 1
    target, outputs = results[0]
    assert target == "pcb_unit"
    assert "cad" in outputs
    assert outputs["cad"].is_file()
    assert outputs["cad"].name.endswith("_cad.zip")
    assert "board" in outputs
    assert "bom" in outputs
    assert "cpl" in outputs
    assert "schematic" in outputs
    assert "schematic_pdf" in outputs


def test_export_kicad_pcb_with_design_rules(tmp_path: Path, mock_pcb_config: PCBConfig, mock_wiring: Wiring):
    """Verify export_kicad_pcb generates matching .kicad_pro with custom design rules."""
    custom_rules = PCBDesignRulesModel(
        min_clearance_mm=0.22,
        min_track_width_mm=0.18,
        min_copper_edge_clearance_mm=0.25,
        default_track_width_mm=0.25,
        default_via_diameter_mm=0.45,
        default_via_drill_mm=0.20,
    )
    exporter = PCBExporter(mock_pcb_config, mock_wiring, design_rules=custom_rules)
    out_file = tmp_path / "test_rules.kicad_pcb"
    exporter.export_kicad_pcb(out_file)

    pro_file = out_file.with_suffix(".kicad_pro")
    assert pro_file.is_file()
    pro_data = json.loads(pro_file.read_text(encoding="utf-8"))
    assert pro_data["board"]["design_settings"]["rules"]["min_clearance"] == 0.22
    assert pro_data["board"]["design_settings"]["rules"]["min_track_width"] == 0.18
    assert pro_data["board"]["design_settings"]["rules"]["board_edge_clearance"] == 0.25


def test_kicad_cli_run_drc_syncs_design_rules(tmp_path: Path):
    """Verify KiCadCLI.run_drc syncs custom design rules into .kicad_pro before running DRC."""
    pcb_file = tmp_path / "board.kicad_pcb"
    pcb_file.write_text("(kicad_pcb (version 20240108))\n", encoding="utf-8")
    rpt_file = tmp_path / "board.rpt"

    custom_rules = PCBDesignRulesModel(min_clearance_mm=0.30, min_track_width_mm=0.20)
    cli = KiCadCLI(design_rules=custom_rules)

    with patch.object(cli, "run_command") as mock_run:
        mock_run.return_value = "dummy"
        rpt_file.write_text(
            "** Drc report for board **\n** Found 0 DRC violations **\n** Found 0 unconnected pads **\n** Found 0 Footprint errors **\n",
            encoding="utf-8",
        )
        report = cli.run_drc(pcb_file, rpt_file)
        assert report.passed
        pro_file = pcb_file.with_suffix(".kicad_pro")
        assert pro_file.is_file()
        pro_data = json.loads(pro_file.read_text(encoding="utf-8"))
        assert pro_data["board"]["design_settings"]["rules"]["min_clearance"] == 0.30
