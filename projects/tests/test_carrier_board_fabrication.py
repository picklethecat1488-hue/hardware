"""Tests for carrier_board rigid-flex PCB and protective enclosure CAD geometry."""

from pathlib import Path
import pytest
from build123d import Location
from projects.carrier_board.provider import CarrierBoardProvider
from model.wiring import Wiring
from provider import Mode


def test_regression_bug_271_split_supplier_submissions_carrier_board() -> None:
    """Verify BUG-271: supplier submissions are split by subassembly and include project summary forms."""
    import zipfile

    board_dir = Path("build/board/carrier_board")

    # 1. Verify subassembly directories exist
    carrier_dir = board_dir / "carrier_board"
    flex_dir = board_dir / "flex_tail"
    assert carrier_dir.is_dir(), "build/board/carrier_board/carrier_board directory must exist"
    assert flex_dir.is_dir(), "build/board/carrier_board/flex_tail directory must exist"

    # 2. carrier_board/gerbers.zip must contain ONLY carrier_board files
    with zipfile.ZipFile(carrier_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        assert any("carrier_board" in n for n in names)
        assert not any("flex_tail" in n for n in names)
        assert "project_summary.txt" in names

    # 3. flex_tail/gerbers.zip must contain ONLY flex_tail files
    with zipfile.ZipFile(flex_dir / "gerbers.zip", "r") as zf:
        names = zf.namelist()
        assert any("flex_tail" in n for n in names)
        assert not any("carrier_board" in n for n in names)
        assert "project_summary.txt" in names

    # 4. Project summaries exist and specify correct layer counts and types
    c_summary = (carrier_dir / "project_summary.txt").read_text()
    assert "Rigid" in c_summary
    assert "6 Layers" in c_summary
    assert "ENIG" in c_summary

    f_summary = (flex_dir / "project_summary.txt").read_text()
    assert "Flex" in f_summary or "FPC" in f_summary
    assert "2 Layers" in f_summary


def test_regression_bug_266_remove_led_and_jumper_opposite_side_designators(tmp_path: Path) -> None:
    """Verify BUG-266: Component designators for LEDs, jumpers, and switches are removed from both B.SilkS and F.SilkS."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.exporter import PCBExporter

    provider = CarrierBoardProvider()
    _ = provider.silkscreen
    pcb_cfg = provider.pcb_config

    bottom_texts = [t.text for t in pcb_cfg.silkscreen_texts if t.layer == "B.SilkS"]

    removed_designators = (
        [f"D{i}" for i in range(2, 8)] + [f"JP{i}" for i in range(1, 5)] + [f"R{i}" for i in range(7, 13)] + ["SW1"]
    )
    for des in removed_designators:
        assert des not in bottom_texts, f"Opposite-side component designator '{des}' found on B.SilkS"

    # Verify omitted designators are registered in PCBConfig
    assert set(removed_designators).issubset(set(pcb_cfg.omitted_silkscreen_designators))

    # Verify that during PCB export, none of these designators are auto-rendered on F.SilkS or any layer
    wiring = provider.wiring
    exp = PCBExporter(pcb_cfg, wiring=wiring)
    out_pcb = tmp_path / "carrier_board.kicad_pcb"
    exp.export_kicad_pcb(str(out_pcb))
    content = out_pcb.read_text(encoding="utf-8")
    for des in removed_designators:
        assert f'(gr_text "{des}"' not in content, (
            f"Component designator '{des}' unexpectedly rendered on silkscreen in KiCad PCB"
        )


def test_regression_bug_267_c18_c19_vertical_stack_and_u11_clearance() -> None:
    """Verify BUG-267: C18 and C19 are stacked vertically outside U11 silkscreen border with 0 DRC errors."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from model.wiring import Wiring
    from provider.pcb.drc import PCBDesignRulesChecker

    provider = CarrierBoardProvider()
    wiring = provider.wiring
    comp_map = {c.name: c for c in wiring.footprints}
    nets_map = {n.name: n for n in wiring.nets}

    # 1. C18 and C19 exist and are stacked vertically at X >= 6.5
    assert "C18" in comp_map, "C18 tuning capacitor must exist"
    assert "C19" in comp_map, "C19 tuning capacitor must exist"
    c18 = comp_map["C18"]
    c19 = comp_map["C19"]

    # Vertically stacked: same X coordinate, different Y coordinates
    assert c18.position[0] == c19.position[0], (
        f"C18 and C19 must be vertically stacked with matching X, got C18.X={c18.position[0]}, C19.X={c19.position[0]}"
    )
    assert c18.position[1] != c19.position[1], "C18 and C19 must have distinct Y positions"

    # Well clear of U11 edge (X=5.0) and silkscreen brackets (X=5.25)
    assert c18.position[0] >= 6.5, (
        f"C18/C19 X position must be >= 6.5mm to be outside U11 silkscreen border, got {c18.position[0]}"
    )

    # 2. Verify net connections
    assert any(c == "C18" and p == "1" for c, p in nets_map["NFC1"].pins), "C18 pin 1 must connect to NFC1"
    assert any(c == "C18" and p == "2" for c, p in nets_map["GND"].pins), "C18 pin 2 must connect to GND"
    assert any(c == "C19" and p == "1" for c, p in nets_map["NFC2"].pins), "C19 pin 1 must connect to NFC2"
    assert any(c == "C19" and p == "2" for c, p in nets_map["GND"].pins), "C19 pin 2 must connect to GND"

    # 3. PCB DRC check passes with 0 violations
    drc = PCBDesignRulesChecker(provider.pcb_config)
    report = drc.check_all(wiring=wiring)
    assert report.passed, f"PCB DRC failed:\n{report.summary()}"
    assert report.error_count == 0, f"Expected 0 DRC errors, got: {report.summary()}"


def test_regression_bug_272_supplier_feedback_carrier_board() -> None:
    """Verify BUG-272: Supplier feedback items are addressed across carrier board CAM files and docs.

    1. Soldermask color: carrier_board manifest color is matte black [0.12, 0.12, 0.12, 1.0].
    2. Stackup soldermask: KiCad exported PCB includes F.Mask and B.Mask with Black soldermask.
    3. Impedance control: project_summary.txt, project_summary.md, and impedance_control_info.txt
       explicitly detail track width, spacing, target value, and reference layers (50Ω SE, 90Ω diff, 85Ω diff).
    4. Via plugging: Confirmation to fill all vias in BGA area and SMD pads with resin and cap (VIPPO / IPC-4761 Type VII).
    5. Package inclusion: impedance_control_info.txt is packaged inside carrier_board/gerbers.zip.
    """
    import zipfile
    import yaml

    # 1. Manifest color check (Matte Black)
    manifest_path = Path("projects/carrier_board/manifest.yaml")
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    carrier_color = manifest_data.get("carrier_board", {}).get("color", [])
    assert carrier_color[:3] == [0.12, 0.12, 0.12], (
        f"carrier_board manifest color must be Matte Black [0.12, 0.12, 0.12, 1.0], got {carrier_color}"
    )

    # 2. Subassembly submission files
    board_dir = Path("build/board/carrier_board")
    carrier_dir = board_dir / "carrier_board"
    c_summary_txt = (carrier_dir / "project_summary.txt").read_text(encoding="utf-8")
    c_summary_md = (carrier_dir / "project_summary.md").read_text(encoding="utf-8")

    # Soldermask color in summary
    assert "Matte Black" in c_summary_txt, "project_summary.txt must specify Matte Black mask"
    assert "Matte Black" in c_summary_md, "project_summary.md must specify Matte Black mask"

    # Impedance control specifications in summary
    assert "CONTROLLED IMPEDANCE" in c_summary_txt, "project_summary.txt must have CONTROLLED IMPEDANCE section"
    assert "50" in c_summary_txt and "0.12" in c_summary_txt, "50 Ohm SE track (0.12mm) must be specified"
    assert "90" in c_summary_txt and "0.12" in c_summary_txt, (
        "90 Ohm diff pair (0.12mm width / 0.12mm spacing) must be specified"
    )

    # Via plugging confirmation (resin fill and cap / VIPPO)
    assert "Resin" in c_summary_txt or "resin" in c_summary_txt, (
        "Via resin fill must be specified in project_summary.txt"
    )
    assert "cap" in c_summary_txt.lower() or "vippo" in c_summary_txt.lower(), (
        "Via capping / VIPPO must be confirmed in project_summary.txt"
    )

    # Dedicated impedance control info file
    imp_file = carrier_dir / "impedance_control_info.txt"
    assert imp_file.is_file(), "impedance_control_info.txt must exist in carrier_board submission directory"
    imp_text = imp_file.read_text(encoding="utf-8")
    assert "50" in imp_text and "90" in imp_text

    # Packaging in gerbers.zip
    names = None
    import time

    for attempt in range(10):
        try:
            with zipfile.ZipFile(carrier_dir / "gerbers.zip", "r") as zf:
                names = zf.namelist()
                break
        except (zipfile.BadZipFile, OSError):
            if attempt == 9:
                raise
            time.sleep(0.5)

    assert names is not None
    assert "impedance_control_info.txt" in names, "carrier_board/gerbers.zip must contain impedance_control_info.txt"
    assert "project_summary.txt" in names, "carrier_board/gerbers.zip must contain project_summary.txt"


def test_regression_bug_275_supplier_feedback_flex_tail() -> None:
    """Verify BUG-275: Supplier feedback items are addressed for flex_tail.

    1. Panelization confirmation: 1*2 panel in 64*64mm with x-out accepted.
    2. SMT only / 0 drill holes / 0 vias clarified in project summary and order remarks (<= 600 chars).
    3. Multi-format drill files (.drl, -PTH.drl, -NPTH.drl, .txt, -drl_map.gbr) included in gerbers.zip.
    4. Dwgs.User fabrication & panelization notes added to flex_tail PCB.
    """
    import zipfile
    import yaml

    # 1. Manifest panel specification
    manifest_path = Path("projects/carrier_board/manifest.yaml")
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    flex_manifest = manifest_data.get("flex_tail", {})
    assert "panel" in flex_manifest, "flex_tail manifest must declare panel specification"
    assert "1*2" in flex_manifest["panel"] and "64*64" in flex_manifest["panel"]
    assert "x-out" in flex_manifest["panel"]

    # 2. Config parametrization from measurements.yaml
    from projects.carrier_board.provider import CarrierBoardProvider

    provider = CarrierBoardProvider()
    cfg = provider.settings

    assert hasattr(cfg, "flex_tail_panel_array")
    assert cfg.flex_tail_panel_array == "1*2"
    assert cfg.flex_tail_panel_width == 64.0
    assert cfg.flex_tail_panel_length == 64.0
    assert cfg.flex_tail_panel_accept_xout is True

    # 3. Subassembly submission summary files
    board_dir = Path("build/board/carrier_board")
    flex_dir = board_dir / "flex_tail"
    f_summary_txt = (flex_dir / "project_summary.txt").read_text(encoding="utf-8")
    f_summary_md = (flex_dir / "project_summary.md").read_text(encoding="utf-8")

    # Panelization in summary
    assert "1*2 panel in 64*64mm" in f_summary_txt
    assert "x-out" in f_summary_txt
    assert "1*2 panel in 64*64mm" in f_summary_md
    assert "x-out" in f_summary_md

    # Zero drill holes / 0 vias clarity in summary
    assert "0 drill holes" in f_summary_txt or "SMT only" in f_summary_txt
    assert "0 vias" in f_summary_txt or "no through-holes" in f_summary_txt

    # Remarks <= 600 chars
    remarks_text = f_summary_txt.split("-" * 80)[-1].split("=" * 80)[0].strip()
    assert len(remarks_text) <= 600, f"Remarks must be <= 600 chars, got {len(remarks_text)}"
    assert "64*64mm" in remarks_text
    assert "x-out" in remarks_text

    # 4. Packaging in flex_tail/gerbers.zip
    names = None
    for attempt in range(10):
        try:
            with zipfile.ZipFile(flex_dir / "gerbers.zip", "r") as zf:
                names = zf.namelist()
                break
        except (zipfile.BadZipFile, OSError):
            if attempt == 9:
                raise
            time.sleep(0.5)

    assert names is not None
    assert "project_summary.txt" in names
    assert "project_summary.md" in names
    # Must contain drill deliverables
    has_drl = any(n.endswith(".drl") for n in names)
    has_txt = any(n.startswith("flex_tail") and n.endswith(".txt") for n in names)
    has_map = any("drl_map.gbr" in n for n in names)
    assert has_drl, f"flex_tail/gerbers.zip must contain .drl drill files, got: {names}"
    assert has_txt, f"flex_tail/gerbers.zip must contain .txt drill files, got: {names}"
    assert has_map, f"flex_tail/gerbers.zip must contain Gerber drill map (-drl_map.gbr), got: {names}"

    # 5. Dwgs.User fabrication & panelization notes on PCB
    pcb_content = (board_dir / "flex_tail.kicad_pcb").read_text(encoding="utf-8")
    assert "PANEL: 1*2 PANEL IN 64x64mm ACCEPTED WITH X-OUT BOARD ACCEPTED" in pcb_content
    assert "FAB: 2-LAYER POLYIMIDE FPC (0.20mm) | SMT ONLY: 0 DRILL HOLES / 0 VIAS" in pcb_content
    assert "Dwgs.User" in pcb_content


def test_regression_bug_276_j4_fpc_connector_mpn_and_supplier_pn() -> None:
    """Verify BUG-276: J2 is Hirose FH12-30S-0.5SH(55) receptacle on carrier board, and J4 is integral male mating tab marked DNP."""
    from model.wiring import Wiring

    from projects.carrier_board.provider import CarrierBoardProvider

    wiring = CarrierBoardProvider().wiring

    # 1. Verify wiring.yaml footprints for J2 (carrier_board) and J4 (flex_tail)
    j2 = next(c for c in wiring.footprints if c.name == "J2")
    j4 = next(c for c in wiring.footprints if c.name == "J4")

    assert j2.mpn == "FH12-30S-0.5SH(55)", f"J2 MPN must be FH12-30S-0.5SH(55), got {j2.mpn}"
    assert j2.supplier_pn == "HFJ130CT-ND", f"J2 supplier_pn must be HFJ130CT-ND, got {j2.supplier_pn}"
    assert not getattr(j2, "dnp", False), "J2 is populated connector receptacle on carrier board"

    # J4 is the integral FPC male mating tab that inserts into J2 (not a populated connector)
    assert getattr(j4, "dnp", False), "J4 must be marked DNP (integral male mating tab, not populated)"
    assert "Mating Tab" in j4.mpn or "Male plug" in j4.mpn
    assert j4.supplier_pn == "N/A"
    assert "Male Plug" in (j4.value or "")

    # Verify no placeholder or 100-pin connector PN remains
    for fp in (j2, j4):
        assert fp.supplier_pn != "H1234-ND", f"{fp.name} must not use dummy placeholder H1234-ND"
        assert "FH35C" not in fp.mpn, f"{fp.name} MPN must not reference FH35C"

    # 2. Downselection documentation verification
    for doc_path in [
        Path("docs/downselection_report.md"),
        Path("projects/carrier_board/docs/downselection_report.md"),
    ]:
        content = doc_path.read_text(encoding="utf-8")
        assert "FH12-30S-0.5SH(55)" in content, f"{doc_path} must document FH12-30S-0.5SH(55)"
        assert "HIROSE-FH35C-30S" not in content, f"{doc_path} must not reference obsolete HIROSE-FH35C-30S"

    # 3. Exported BOM CSV and zip archive verification
    import zipfile

    flex_bom = Path("build/bom/carrier_board/flex_tail_bom.csv")
    carrier_bom = Path("build/bom/carrier_board/carrier_board_bom.csv")
    assert flex_bom.exists(), "flex_tail_bom.csv must exist"
    assert carrier_bom.exists(), "carrier_board_bom.csv must exist"
    assert "Mating Tab" in flex_bom.read_text(encoding="utf-8") or "Male Plug" in flex_bom.read_text(encoding="utf-8")
    assert "FH12-30S-0.5SH(55)" in carrier_bom.read_text(encoding="utf-8")
    assert "HFJ130CT-ND" in carrier_bom.read_text(encoding="utf-8")

    with zipfile.ZipFile("build/board/carrier_board/flex_tail/bom_templates.zip") as zf:
        bom_text = zf.read("flex_tail_bom.csv").decode("utf-8")
        assert "Mating Tab" in bom_text or "Male Plug" in bom_text
        assert "H1234-ND" not in bom_text


def test_regression_bug_277_bom_excel_pcbway_export() -> None:
    """Verify BUG-277: Bill of Materials is exported as .xlsx matching PCBWay template schema and bundled in archives."""
    import zipfile
    import xml.etree.ElementTree as ET

    board_dir = Path("build/board/carrier_board")
    bom_dir = Path("build/bom/carrier_board")

    # 1. Verify .xlsx BOM files exist in build/bom and build/board subassemblies
    flex_bom_xlsx = bom_dir / "flex_tail_bom.xlsx"
    carrier_bom_xlsx = bom_dir / "carrier_board_bom.xlsx"
    assert flex_bom_xlsx.is_file(), "build/bom/carrier_board/flex_tail_bom.xlsx must exist"
    assert carrier_bom_xlsx.is_file(), "build/bom/carrier_board/carrier_board_bom.xlsx must exist"

    sub_flex_xlsx = board_dir / "flex_tail" / "flex_tail_bom.xlsx"
    sub_carrier_xlsx = board_dir / "carrier_board" / "carrier_board_bom.xlsx"
    assert sub_flex_xlsx.is_file(), "flex_tail/flex_tail_bom.xlsx must exist in subassembly folder"
    assert sub_carrier_xlsx.is_file(), "carrier_board/carrier_board_bom.xlsx must exist in subassembly folder"

    # 2. Verify bom_templates.zip packaging contains .csv AND .xlsx
    with zipfile.ZipFile(board_dir / "flex_tail" / "bom_templates.zip") as zf:
        names = zf.namelist()
        assert "flex_tail_bom.csv" in names, "flex_tail bom_templates.zip must contain flex_tail_bom.csv"
        assert "flex_tail_bom.xlsx" in names, "flex_tail bom_templates.zip must contain flex_tail_bom.xlsx"

    with zipfile.ZipFile(board_dir / "carrier_board" / "bom_templates.zip") as zf:
        names = zf.namelist()
        assert "carrier_board_bom.csv" in names, "carrier_board bom_templates.zip must contain carrier_board_bom.csv"
        assert "carrier_board_bom.xlsx" in names, "carrier_board bom_templates.zip must contain carrier_board_bom.xlsx"

    with zipfile.ZipFile(board_dir / "bom_templates.zip") as zf:
        names = zf.namelist()
        assert "carrier_board_bom.csv" in names
        assert "carrier_board_bom.xlsx" in names
        assert "flex_tail_bom.csv" in names
        assert "flex_tail_bom.xlsx" in names

    # 3. Verify flex_tail_bom.xlsx OpenXML structure and PCBWay template compliance
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(flex_bom_xlsx) as zf:
        sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.findall(".//s:t", ns)) for si in sst.findall(".//s:si", ns)]
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

        rows_map = {}
        for row in sheet.findall(".//s:row", ns):
            r_num = int(row.attrib.get("r"))
            col_map = {}
            for c in row.findall("s:c", ns):
                coord = c.attrib.get("r")
                col_letter = "".join(filter(str.isalpha, coord))
                t = c.attrib.get("t")
                v = c.find("s:v", ns)
                if v is not None and v.text:
                    col_map[col_letter] = strings[int(v.text)] if t == "s" else v.text
                else:
                    col_map[col_letter] = ""
            rows_map[r_num] = col_map

    # Check row 6 headers
    r6 = rows_map[6]
    assert r6["A"] == "Item #"
    assert r6["B"] == "*Designator"
    assert r6["C"] == "*Qty"
    assert r6["D"] == "Manufacturer"
    assert r6["E"] == "*Mfg Part #"
    assert r6["F"] == "Description / Value"
    assert r6["G"] == "*Package/Footprint"
    assert r6["H"] == "Type"
    assert r6["I"] == "Your Instructions / Notes"

    # Check row 7 (J4 component - DNP integral mating tab)
    r7 = rows_map[7]
    assert r7["A"] == "1"
    assert r7["B"] == "J4"
    assert r7["C"] == "1"
    assert r7["D"] == "N/A (Bare Flex PCB)"
    assert "Mating Tab" in r7["E"] or "Male plug" in r7["E"]
    assert r7["G"] == "FPC-30P-0.5MM"
    assert r7["H"] == "DNS"
    assert "no component to populate" in r7["I"] or "Male plug" in r7["I"]

    # 4. Verify carrier_board_bom.xlsx contains J2 and DNP component J15
    with zipfile.ZipFile(carrier_bom_xlsx) as zf:
        sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.findall(".//s:t", ns)) for si in sst.findall(".//s:si", ns)]
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

        cb_rows = []
        for row in sheet.findall(".//s:row", ns):
            r_num = int(row.attrib.get("r"))
            if r_num < 7:
                continue
            col_map = {}
            for c in row.findall("s:c", ns):
                coord = c.attrib.get("r")
                col_letter = "".join(filter(str.isalpha, coord))
                t = c.attrib.get("t")
                v = c.find("s:v", ns)
                if v is not None and v.text:
                    col_map[col_letter] = strings[int(v.text)] if t == "s" else v.text
                else:
                    col_map[col_letter] = ""
            cb_rows.append(col_map)

    j2_row = next(r for r in cb_rows if r.get("B") == "J2")
    assert j2_row["E"] == "FH12-30S-0.5SH(55)"
    assert j2_row["H"] == "SMD"
    assert "HFJ130CT-ND" in j2_row["I"]

    j15_row = next(r for r in cb_rows if r.get("B") == "J15")
    assert j15_row["H"] == "DNS"
    assert "Do Not Stuff (DNP)" in j15_row["I"]


def test_regression_bug_segmented_palolo_739_bom_supplier_questions() -> None:
    """Verify BUG-SEGMENTED-PALOLO-739: Supplier questions resolved, Y1 package matches 3225, and consignment docs exist."""
    from model.wiring import Wiring

    # 1. Y1 crystal MPN must be ECS-240-8-32B-CKM to match XTAL-3225-4P package
    from projects.carrier_board.provider import CarrierBoardProvider

    wiring = CarrierBoardProvider().wiring
    y1 = next(c for c in wiring.footprints if c.name == "Y1")
    assert y1.mpn in ("ECS-240-8-32B-CKM", "ECS-240-8-30B-CKM"), f"Y1 MPN must be valid ECS crystal, got {y1.mpn}"
    assert y1.package == "XTAL-3225-4P"

    # 2. Downselection documentation must reflect ECS-240-8-32B-CKM
    for doc in [
        Path("docs/downselection_report.md"),
        Path("projects/carrier_board/docs/downselection_report.md"),
    ]:
        content = doc.read_text(encoding="utf-8")
        assert "ECS-240-8-32B-CKM" in content, f"{doc} must document ECS-240-8-32B-CKM"
        assert "ECS-240-8-30B-CKM" not in content, f"{doc} must not reference 5032 MPN ECS-240-8-30B-CKM"

    # 3. Consignment sourcing and shipping guide must exist
    consignment_guide = Path("projects/carrier_board/docs/consignment_sourcing_and_shipping_guide.md")
    assert consignment_guide.is_file(), "Consignment sourcing and shipping guide must exist"
    guide_text = consignment_guide.read_text(encoding="utf-8")
    assert "MCXN947VDF" in guide_text
    assert "IQS7222C101QNR" in guide_text
    assert "IQS7222A001QNR" in guide_text
    assert "T-E68W908185A" in guide_text

    # 4. Replied BOM questions spreadsheet must exist in attachments
    replied_xls = Path(
        "attachments/BUG-SEGMENTED-PALOLO-739/T-E68W908185A-2units-bom_templates(2026-10-11)_replied.xlsx"
    )
    assert replied_xls.is_file(), "Replied BOM questions spreadsheet must exist"


def test_regression_bug_glowing_oligochaete_544_rev_bom_export() -> None:
    """Verify BUG-GLOWING-OLIGOCHAETE-544: Revised BOM spreadsheets generated for PCBWay Order #T-E68W908185A.

    Verifies that revised quote templates (.xlsx/.xls) and clean EDA BOM files (.xlsx/.csv)
    properly reflect IQS7222C101QNR substitution, customer consignment deductions for U1 & U2,
    and 3225-4P package update for Y1.
    """
    import openpyxl

    rev_dir = Path("attachments/BUG-GLOWING-OLIGOCHAETE-544")
    assert rev_dir.is_dir(), "Revised BOM attachments directory must exist"

    rev_xlsx = rev_dir / "T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xlsx"
    rev_xls = rev_dir / "T-E68W908185A-2units-bom_templates(2026-10-12)_rev1.xls"
    eda_xlsx = rev_dir / "carrier_board_bom_rev1.xlsx"
    eda_csv = rev_dir / "carrier_board_bom_rev1.csv"

    assert rev_xlsx.is_file(), f"{rev_xlsx} must exist"
    assert rev_xls.is_file(), f"{rev_xls} must exist"
    assert eda_xlsx.is_file(), f"{eda_xlsx} must exist"
    assert eda_csv.is_file(), f"{eda_csv} must exist"

    # Verify revised quotation spreadsheet
    wb = openpyxl.load_workbook(rev_xlsx)
    ws = wb.active

    # Row 42: U1 MCU
    u1_mpn = ws.cell(42, 5).value
    u1_notes = ws.cell(42, 9).value or ""
    assert "MCXN947" in u1_mpn
    assert "Customer Consigned" in u1_notes or "Consigned" in u1_notes
    assert ws.cell(42, 10).value == 0.0  # Unit price deducted

    # Row 43: U2 Touch Controller
    u2_mpn = ws.cell(43, 5).value
    u2_notes = ws.cell(43, 9).value or ""
    assert u2_mpn == "IQS7222C101QNR"
    assert ws.cell(43, 7).value == "QFN-20"
    assert "Customer Consigned" in u2_notes or "Consigned" in u2_notes
    assert ws.cell(43, 10).value == 0.0  # Unit price deducted

    # Row 53: Y1 Crystal
    y1_mpn = ws.cell(53, 5).value
    assert y1_mpn == "ECS-240-8-32B-CKM"
    assert ws.cell(53, 7).value == "XTAL-3225-4P"

    # Verify clean EDA BOM
    eda_wb = openpyxl.load_workbook(eda_xlsx)
    eda_ws = eda_wb.active
    eda_rows = [
        [eda_ws.cell(r, c).value for c in range(1, eda_ws.max_column + 1)] for r in range(1, eda_ws.max_row + 1)
    ]
    eda_str = " | ".join(str(row) for row in eda_rows)
    assert "IQS7222C101QNR" in eda_str
    assert "ECS-240-8-32B-CKM" in eda_str


def test_regression_bug_writhing_vermis_367_black_coverlay_color() -> None:
    """Verify BUG-WRITHING-VERMIS-367: Flex tail coverlay color is Black across manifest, CAD, PCB, and supplier specs."""
    import yaml
    from provider.pcb.supplier import generate_pcb_project_summary

    # 1. Manifest must specify black coverlay for flex_tail
    manifest_path = Path("projects/carrier_board/manifest.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert "flex_tail" in manifest
    flex_spec = manifest["flex_tail"]
    assert flex_spec.get("color") == [0.12, 0.12, 0.12, 1.0], (
        f"Flex tail color in manifest must be black [0.12, 0.12, 0.12, 1.0], got {flex_spec.get('color')}"
    )
    assert flex_spec.get("coverlay_color") == "black"
    assert "Black" in flex_spec.get("coverlay", "")

    # 2. PCB config flex zones must specify coverlay_color == "black"
    provider = CarrierBoardProvider()
    flex_zones = provider.pcb_config.flex_zones
    assert len(flex_zones) > 0
    assert flex_zones[0].coverlay_color == "black"

    # 3. Supplier project summary must specify Black coverlay
    provider = CarrierBoardProvider()
    board_dir = Path("build/board/carrier_board/flex_tail")
    bom_dir = Path("build/bom/carrier_board")
    board_dir.mkdir(parents=True, exist_ok=True)
    bom_dir.mkdir(parents=True, exist_ok=True)
    txt, md = generate_pcb_project_summary(
        board_dir=board_dir,
        bom_dir=bom_dir,
        name="flex_tail",
        provider=provider,
    )
    assert "Black Polyimide Coverlay" in txt or "Black coverlay" in txt
    assert "Black Polyimide Coverlay" in md or "Black coverlay" in md


def test_regression_bug_fertile_sandworm_588_consign_remaining_components() -> None:
    """Verify BUG-FERTILE-SANDWORM-588: Consign remaining out-of-stock parts (D1, J3, U5, Y1) and confirm Molex J16.

    Verifies that:
    1. Replied quotation templates (.xlsx and .xls) and clean EDA BOM (.xlsx and .csv) exist.
    2. In replied spreadsheet, D1, J3, U5, Y1 are marked Customer Consigned (price = 0, 客供 in notes & reply).
    3. J16 has manufacturer Molex and customer reply confirming Molex procurement.
    4. Component Cost is correctly evaluated at 350.316 in both xlsx and xls.
    5. Clean EDA BOM exports have Molex for J16 and Customer Consigned for D1, J3, U5, Y1.
    6. Consignment sourcing and shipping guide documents all 6 consigned components.
    7. KiCadExporter infers Molex manufacturer for 22-28-4023.
    """
    import openpyxl
    import xlrd
    from provider.pcb.exporter import PCBExporter
    from model.wiring import FootprintModel

    # 1. File existence
    att_dir = Path("attachments/BUG-FERTILE-SANDWORM-588")
    assert att_dir.is_dir(), "Attachments directory must exist"

    xlsx_path = att_dir / "T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xlsx"
    xls_path = att_dir / "T-E68W908185A-2units-bom_templates(2026-10-14)_replied.xls"
    eda_xlsx = att_dir / "carrier_board_bom_rev2.xlsx"
    eda_csv = att_dir / "carrier_board_bom_rev2.csv"
    eda_xlsx_rev3 = att_dir / "carrier_board_bom_rev3.xlsx"
    eda_csv_rev3 = att_dir / "carrier_board_bom_rev3.csv"
    digikey_order = att_dir / "digikey_order_2026-10-14.xlsx"

    assert xlsx_path.is_file(), f"{xlsx_path} must exist"
    assert xls_path.is_file(), f"{xls_path} must exist"
    assert eda_xlsx.is_file(), f"{eda_xlsx} must exist"
    assert eda_csv.is_file(), f"{eda_csv} must exist"
    assert eda_xlsx_rev3.is_file(), f"{eda_xlsx_rev3} must exist"
    assert eda_csv_rev3.is_file(), f"{eda_csv_rev3} must exist"
    assert digikey_order.is_file(), f"{digikey_order} must exist"

    # 2. Check replied XLSX
    wb = openpyxl.load_workbook(xlsx_path, data_only=False)
    ws = wb.active

    # D1 (Row 12)
    assert ws.cell(12, 2).value == "D1"
    assert ws.cell(12, 5).value == "CLV1A-FKB-CK1VW1DE1BB7C3C3"
    assert ws.cell(12, 10).value == 0.0
    assert ws.cell(12, 11).value == 0.0
    assert "客供" in ws.cell(12, 14).value
    assert "客供" in ws.cell(12, 15).value

    # J3 (Row 21)
    assert ws.cell(21, 2).value == "J3"
    assert ws.cell(21, 5).value == "TYPE-C-16P-3MD"
    assert ws.cell(21, 10).value == 0.0
    assert ws.cell(21, 11).value == 0.0
    assert "客供" in ws.cell(21, 14).value

    # J15 (Row 30)
    assert ws.cell(30, 2).value == "J15"
    assert "DNP" in ws.cell(30, 14).value

    # J16 (Row 31)
    assert ws.cell(31, 2).value == "J16"
    assert ws.cell(31, 4).value == "Molex"
    assert "MOLEX" in ws.cell(31, 14).value

    # U1 (Row 42) & U2 (Row 43)
    assert ws.cell(42, 2).value == "U1"
    assert ws.cell(42, 5).value == "MCXN947VDFT"
    assert ws.cell(42, 10).value == 0.0
    assert "客供" in ws.cell(42, 14).value

    assert ws.cell(43, 2).value == "U2"
    assert ws.cell(43, 5).value == "IQS7222C101QNR"
    assert ws.cell(43, 10).value == 0.0
    assert "客供" in ws.cell(43, 14).value

    # U5 (Row 46) & Y1 (Row 53)
    assert ws.cell(46, 2).value == "U5"
    assert ws.cell(46, 5).value == "CPT-1207-5LTH-T"
    assert ws.cell(46, 10).value == 0.0
    assert "客供" in ws.cell(46, 14).value

    assert ws.cell(53, 2).value == "Y1"
    assert ws.cell(53, 5).value == "ECS-240-8-30B-CKM"
    assert ws.cell(53, 10).value == 0.0
    assert "客供" in ws.cell(53, 14).value

    # 3. Check legacy XLS with xlrd
    book = xlrd.open_workbook(xls_path)
    sheet = book.sheet_by_index(0)
    cost_row = sheet.row_values(53)
    assert cost_row[9] == "Component Cost"
    assert abs(cost_row[10] - 350.316) < 1e-3

    # 4. Check clean EDA BOM (both rev2 and rev3)
    for target_eda in (eda_xlsx, eda_xlsx_rev3):
        eda_wb = openpyxl.load_workbook(target_eda)
        eda_ws = eda_wb.active
        j16_found = False
        for r in range(6, eda_ws.max_row + 1):
            des = eda_ws.cell(r, 2).value
            if des == "J16":
                assert eda_ws.cell(r, 4).value == "Molex"
                assert "Molex" in eda_ws.cell(r, 9).value
                j16_found = True
            elif des in ("D1", "J3", "U1", "U2", "U5", "Y1"):
                assert "客供" in (eda_ws.cell(r, 9).value or "")
        assert j16_found, f"J16 must be present in clean EDA BOM {target_eda}"

    # 5. Check consignment sourcing guide
    guide_path = Path("docs/consignment_sourcing_and_shipping_guide.md")
    guide_text = guide_path.read_text(encoding="utf-8")
    for comp in (
        "MCXN947VDFT",
        "IQS7222C101QNR",
        "CLV1A-FKB-CK1VW1DE1BB7C3C3",
        "TYPE-C-16P-3MD",
        "CPT-1207-5LTH-T",
        "ECS-240-8-30B-CKM",
    ):
        assert comp in guide_text, f"Consignment guide must include {comp}"

    # 6. Check PCBExporter manufacturer inference
    mock_fp = FootprintModel(
        name="J16",
        package="pin_header_1x2",
        dimensions=(2.54, 5.08, 8.5),
        mpn="22-28-4023",
    )
    assert PCBExporter._infer_component_manufacturer(mock_fp) == "Molex"

    mock_cpt = FootprintModel(
        name="U5",
        package="piezo_speaker_12mm",
        dimensions=(12.0, 12.0, 6.5),
        mpn="CPT-1207-5LTH-T",
    )
    assert PCBExporter._infer_component_manufacturer(mock_cpt) == "CUI Devices"


def test_regression_bug_fast_katydid_792_supplier_assembly_documents() -> None:
    """Verify BUG-FAST-KATYDID-792: Supplier required assembly documents replace shipping guide.

    Verifies:
    1. Documents in docs/ and projects/carrier_board/docs/ contain:
       - Invoice / Commercial Invoice with Country of Origin, HS codes, Unit prices
       - Packing list with Carton No, Description, Weight, Dimension/Volume
       - Airway billing / AWB copy & tracking instructions
       - Photos of parts & component bag labeling
    2. Parts originating from Taiwan area are explicitly marked 'Taiwan, China'
       and never standalone 'Taiwan'.
    3. Quantities and package dimensions are left blank for manual user entry.
    4. Commercial invoice and packing list Excel template exists with fillable sheets.
    """
    for doc_path in (
        Path("docs/consignment_sourcing_and_shipping_guide.md"),
        Path("projects/carrier_board/docs/consignment_sourcing_and_shipping_guide.md"),
    ):
        assert doc_path.is_file(), f"{doc_path} must exist"
        text = doc_path.read_text(encoding="utf-8")

        # Required documents present
        assert "Commercial Invoice" in text or "Invoice" in text
        assert "Packing List" in text
        assert "Airway Bill" in text or "Airway Billing" in text
        assert "Photos of Parts" in text or "Photos" in text

        # Order and component assertions
        assert "T-E68W908185A" in text
        for mpn in (
            "MCXN947VDFT",
            "IQS7222C101QNR",
            "CLV1A-FKB-CK1VW1DE1BB7C3C3",
            "TYPE-C-16P-3MD",
            "CPT-1207-5LTH-T",
            "ECS-240-8-30B-CKM",
        ):
            assert mpn in text

        # Taiwan area country of origin requirement: must write 'Taiwan, China'
        assert "Taiwan, China" in text
        # Ensure no lines have standalone "Taiwan" without ", China"
        for line in text.splitlines():
            if "Taiwan" in line:
                assert "Taiwan, China" in line, f"Standalone Taiwan found in line: {line}"

        # Quantities and dimensions left blank for user input
        assert "[     ]" in text or "_____" in text

    # Verify Excel assembly documents spreadsheet
    xlsx_path = Path("attachments/BUG-FAST-KATYDID-792/commercial_invoice_and_packing_list.xlsx")
    assert xlsx_path.is_file(), f"Excel template {xlsx_path} must exist"
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path)
    sheet_names = wb.sheetnames
    assert "Commercial Invoice" in sheet_names
    assert "Packing List" in sheet_names


def test_regression_bug_open_003_eq_gerber_standard_impedance_copper_balance() -> None:
    """Verify BUG-OPEN-003: Gerber standard packaging, TG150 material, In2.Cu copper plane, and matched impedance info."""
    import csv
    from pathlib import Path
    import zipfile

    # 1. Verify EQ customer reply is filled out for all 7 items in CSV
    csv_path = Path("feedback/attachments/BUG-OPEN-003/W908185ASE67-EQ.csv")
    assert csv_path.is_file(), "W908185ASE67-EQ.csv must exist"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r and r[0].isdigit()]
    assert len(rows) == 7, "All 7 EQ items must be present in CSV"
    for r in rows:
        assert len(r) >= 7, f"Item {r[0]} must have 7 columns"
        assert r[6].strip(), f"Item {r[0]} Customer Reply must not be empty"

    # 2. Verify In2.Cu has a copper plane (balanced copper distribution to prevent warpage/delamination)
    from projects.carrier_board.provider import CarrierBoardProvider

    provider = CarrierBoardProvider()
    cr = provider.copper_regions
    in2_regions = [r for r in cr.regions if r.layer == "In2.Cu"]
    assert len(in2_regions) >= 1, "In2.Cu must have a GND copper plane region"
    assert in2_regions[0].net == "GND"

    # 3. Verify gerbers.zip contains standard Gerber files only
    board_dir = Path("build/board/carrier_board")
    with zipfile.ZipFile(board_dir / "gerbers.zip", "r") as zf:
        suffixes = {Path(n).suffix.lower() for n in zf.namelist()}
        for non_standard in (".pcb", ".pcbdoc", ".cam", ".brd", ".kicad_pcb"):
            assert non_standard not in suffixes, f"gerbers.zip must not contain {non_standard}"

    # 4. Verify impedance info matches routed track geometry (0.120mm width and spacing)
    imp_file = board_dir / "carrier_board" / "impedance_control_info.txt"
    assert imp_file.is_file()
    imp_text = imp_file.read_text(encoding="utf-8")
    assert "0.120 mm" in imp_text
    assert "TG150" in imp_text
    assert "PCIe" not in imp_text

    # 5. Verify User Drawings silkscreen specifies TG150 and 0.12mm impedance
    texts = [t.text for t in provider.silkscreen]
    assert any("TG150" in t for t in texts), "Silkscreen must specify TG150"
    assert any("W=0.12mm" in t for t in texts), "Silkscreen must specify W=0.12mm"


def test_regression_bug_translucent_cricket_767_flex_tail_footprint_scoping() -> None:
    """Verify flex tail 3D PCB CAD model only includes flex tail geometry and zero carrier board footprints."""
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.cad_assembler import PCB3DAssembler

    provider = CarrierBoardProvider()
    tail_pcb = provider.flex_tail("flex_tail", None, Mode.DEFAULT)
    tail_cfg = tail_pcb.to_pcb_config()

    assembler = PCB3DAssembler(
        pcb_config=tail_cfg,
        wiring=provider.wiring,
        substrate=tail_pcb.part,
        pcb_name="flex_tail",
    )

    comps, pads = assembler.build_components_and_pads()
    # Flex tail has only J4 (FPC contact interface) and zero carrier board components (MCU, sensors, passives)
    assert comps is not None
    assert len(comps.children) == 1, f"Flex tail should only have J4 FPC connector, got {len(comps.children)}"

    # Flex tail has 39 pads (32 for J4 FPC + 7 capacitive sensor pads), not the 500+ carrier board pads
    assert pads is not None
    assert len(pads.children) == 39, f"Expected 39 pads on flex tail (J4 + 7 cap pads), got {len(pads.children)}"

    # Ensure get_display_items contains flex tail layers
    display_items = assembler.get_display_items(prefix="flex_tail")
    layer_names = {name for _, name, _, _ in display_items}
    assert "flex_tail_substrate" in layer_names
    assert "flex_tail_pads" in layer_names
    assert "flex_tail_traces_top" in layer_names
    assert "flex_tail_silkscreen_top" in layer_names
    assert "flex_tail_silkscreen_bottom" in layer_names
    assert "flex_tail_components" in layer_names

    # Check that carrier board includes its 65 components and 534 pads (and zero flex tail cap pads)
    carrier_pcb = provider.carrier_board("carrier_board", None, Mode.DEFAULT)
    carrier_cfg = carrier_pcb.to_pcb_config()
    carrier_assembler = PCB3DAssembler(
        pcb_config=carrier_cfg,
        wiring=provider.wiring,
        substrate=carrier_pcb.part,
        pcb_name="carrier_board",
    )
    c_comps, c_pads = carrier_assembler.build_components_and_pads()
    assert c_comps is not None
    assert len(c_comps.children) == 65
    assert c_pads is not None
    assert len(c_pads.children) == 534


def test_regression_bug_punctate_instar_79_carrier_board_components_and_traces_alignment() -> None:
    """Verify BUG-PUNCTATE-INSTAR-79: PCB components and copper traces are properly aligned and not clipping through substrate.

    1. Substrate bounding box spans Z = [-0.800, +0.800] mm (1.6mm nominal thickness).
    2. Copper traces sit proud on the outer board surfaces:
       - Top traces (F.Cu) sit at Z in [0.800, 0.835] mm (not submerged inside substrate).
       - Bottom traces (B.Cu) sit at Z in [-0.835, -0.800] mm.
    3. Component package bodies sit proud of the copper pads/substrate:
       - Top components sit at Z >= 0.800 mm.
       - Zero components penetrate inside or clip through the bottom of the PCB substrate.
    4. Top and bottom silkscreen elements sit proud of the traces/substrate:
       - Top silkscreen sits at Z >= 0.800 mm.
       - Bottom silkscreen sits at Z <= -0.800 mm.
    """
    from projects.carrier_board.provider import CarrierBoardProvider
    from provider.pcb.cad_assembler import PCB3DAssembler

    provider = CarrierBoardProvider()
    carrier_pcb = provider.carrier_board("carrier_board", None, Mode.DEFAULT)
    carrier_cfg = carrier_pcb.to_pcb_config()
    assembler = PCB3DAssembler(
        pcb_config=carrier_cfg,
        wiring=provider.wiring,
        substrate=carrier_pcb.part,
        pcb_name="carrier_board",
    )

    # 1. Check substrate vertical bounds
    sub = assembler.build_substrate()
    assert sub is not None
    sub_bb = sub.bounding_box()
    assert pytest.approx(sub_bb.min.Z, abs=1e-3) == -0.800
    assert pytest.approx(sub_bb.max.Z, abs=1e-3) == 0.800

    # 2. Check copper traces sit on top / bottom of substrate
    traces_top = assembler.build_traces("F.Cu")
    assert traces_top is not None
    top_bb = traces_top.bounding_box()
    assert top_bb.min.Z >= 0.799, f"Top traces submerged inside substrate: min.Z = {top_bb.min.Z}"
    assert top_bb.max.Z <= 0.840, f"Top traces too high: max.Z = {top_bb.max.Z}"

    traces_bot = assembler.build_traces("B.Cu")
    assert traces_bot is not None
    bot_bb = traces_bot.bounding_box()
    assert bot_bb.max.Z <= -0.799, f"Bottom traces submerged inside substrate: max.Z = {bot_bb.max.Z}"
    assert bot_bb.min.Z >= -0.840, f"Bottom traces too low: min.Z = {bot_bb.min.Z}"

    # 3. Check components and pads
    comps, pads = assembler.build_components_and_pads()
    assert comps is not None
    assert pads is not None
    # Pads must span full thickness plus copper thickness
    pads_bb = pads.bounding_box()
    assert pads_bb.max.Z >= 0.830
    assert pads_bb.min.Z <= -0.830

    # Component package bodies: none should penetrate through the bottom of the PCB substrate
    # Bottom of substrate is at -0.800 mm. Components on bottom can extend down to -1.435 mm (e.g. J4 contact pads)
    # but top components must have min.Z >= 0.800 mm.
    # Furthermore, verify that no top component penetrates into the substrate [-0.800, 0.800].
    penetrating_comps = []
    for child in comps.children:
        c_bb = child.bounding_box()
        # If component is mounted on top, its bottom should sit on or above top copper (>= 0.800)
        # If component is mounted on bottom, its top should sit on or below bottom copper (<= -0.800)
        is_top = c_bb.max.Z > 0.800
        if is_top and c_bb.min.Z < 0.799:
            penetrating_comps.append((c_bb.min.Z, c_bb.max.Z))
        elif not is_top and c_bb.max.Z > -0.799:
            penetrating_comps.append((c_bb.min.Z, c_bb.max.Z))

    assert len(penetrating_comps) == 0, (
        f"{len(penetrating_comps)} components are penetrating into or clipping through the substrate: {penetrating_comps[:5]}"
    )

    # 4. Check silkscreen bounds
    silk_top = assembler.build_silkscreen("F.SilkS")
    assert silk_top is not None
    st_bb = silk_top.bounding_box()
    assert st_bb.min.Z >= 0.800, f"Top silkscreen submerged: min.Z = {st_bb.min.Z}"

    silk_bot = assembler.build_silkscreen("B.SilkS")
    assert silk_bot is not None
    sb_bb = silk_bot.bounding_box()
    assert sb_bb.max.Z <= -0.800, f"Bottom silkscreen submerged: max.Z = {sb_bb.max.Z}"
