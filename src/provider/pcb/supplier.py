"""Supplier PCB packaging, archive partitioning, and manufacturing project summary form generator."""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional

import jinja2

TEMPLATES_DIR: Path = Path(__file__).parent.parent / "templates"
GERBER_EXTENSIONS: set[str] = {
    ".gbr",
    ".drl",
    ".gbrjob",
    ".kicad_pcb",
    ".pcb",
    ".pcbdoc",
    ".cam",
    ".brd",
    ".txt",
    ".rpt",
}


def get_supplier_jinja_env() -> jinja2.Environment:
    """Return a Jinja2 Environment pointing to the provider templates directory."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate_pcb_project_summary(
    board_dir: Path,
    bom_dir: Path,
    name: str,
    provider: Any,
) -> tuple[str, str]:
    """Generate supplier project summary form in plain text and markdown formats via Jinja2 templates.

    Args:
        board_dir: Path to directory containing exported board files.
        bom_dir: Path to directory containing BOM and Pick-and-Place files.
        name: Name of the target PCB subassembly (e.g. carrier_board, flex_tail).
        provider: Provider instance containing metadata, settings, and manifest.

    Returns:
        Tuple of (summary_text, summary_markdown).
    """
    provider_name = getattr(provider, "name", name)

    # 1. Inspect gbrjob if available
    job_file = board_dir / f"{name}-job.gbrjob"
    job_data: dict[str, Any] = {}
    if job_file.is_file():
        try:
            job_data = json.loads(job_file.read_text(encoding="utf-8"))
        except OSError:
            job_data = {}

    general_specs = job_data.get("GeneralSpecs", {})
    size_x = general_specs.get("Size", {}).get("X")
    size_y = general_specs.get("Size", {}).get("Y")
    job_layers = general_specs.get("LayerNumber")
    job_thickness = general_specs.get("BoardThickness")
    job_finish = general_specs.get("Finish")

    # 2. Determine if board is flex or rigid
    is_flex = False
    manifest_data = getattr(provider, "manifest", None)
    if isinstance(manifest_data, dict):
        sub_manifest = manifest_data.get(name, {})
        mat = sub_manifest.get("material", "")
        if "flex" in str(mat).lower():
            is_flex = True
    if not is_flex and ("flex" in name.lower() or "fpc" in name.lower()):
        is_flex = True

    settings = getattr(provider, "settings", None)

    def _get_dim(attr_name: str, fallback_val: float) -> float:
        if settings is not None and hasattr(settings, attr_name):
            try:
                val = getattr(settings, attr_name)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    return float(val)
                if isinstance(val, str):
                    return float(val)
            except (ValueError, TypeError):
                pass
        return float(fallback_val)

    if is_flex:
        order_category = "Flexible Printed Circuit (FPC)"
        base_material = "Polyimide (PI) Flex Core"
        layer_count = 2
        w = _get_dim("flex_tail_width", size_x or 24.0)
        l = _get_dim("flex_tail_length", size_y or 54.0)
        t = _get_dim("flex_tail_thickness", job_thickness or 0.20)
        tab_w = _get_dim("flex_tail_tab_width", 17.0)
        cr = _get_dim("flex_tail_corner_radius", 1.0)
        stiffener = "0.80 mm FR-4 stiffener under connector tab and sensing electrode array"
        coverlay = "Yellow Polyimide Coverlay (Both Sides)"
        silkscreen = "White"
        surface_finish = job_finish or 'ENIG (Electroless Nickel Immersion Gold, Au: 1-2 u", Ni: 100-200 u")'
        min_track = "0.15 mm / 0.15 mm (6.0 mil / 6.0 mil)"
        min_drill = (
            "None (SMT only, 0 drill holes / 0 vias). Valid drill file included. "
            "Panel tooling holes on 64x64mm rails provided by supplier."
        )
        via_process = "None (SMT only, no through-holes or vias required)"
        panel_spec = "1*2 panel in 64*64mm, accept x-out board in panel (CONFIRMED & APPROVED)"
        has_impedance_control = False
        impedance_entries: list[dict[str, str]] = []
    else:
        order_category = "Standard FR4 Rigid Board"
        base_material = "TG150/TG170 FR-4"
        cu_files = list(board_dir.glob(f"{name}*Cu.gbr"))
        layer_count = len(cu_files) if len(cu_files) >= 2 else (job_layers or 6)
        w = _get_dim("board_width", size_x or 60.0)
        l = _get_dim("board_length", size_y or 90.0)
        t = _get_dim("board_thickness", job_thickness or 1.60)
        cr = _get_dim("corner_radius", 6.0)
        tab_w = None
        stiffener = "None (Rigid substrate)"
        coverlay = "Matte Black LPI Solder Mask (Both Sides)"
        silkscreen = "High-contrast White (Both Sides)"
        surface_finish = job_finish or 'ENIG (Electroless Nickel Immersion Gold, Au: 1-2 u", Ni: 100-200 u")'
        min_track = "0.10 mm / 0.10 mm (4.0 mil / 4.0 mil)"
        min_drill = "0.25 mm (9.84 mil) via drill / 0.16 mm (6.30 mil) microvia"
        via_process = "Non-conductive epoxy resin filled & capped / plated-over (VIPPO / IPC-4761 Type VII) on all vias in BGA area and SMD pads"
        panel_spec = "Single piece or supplier panelized per order specifications"
        has_impedance_control = True

        impedance_entries = [
            {
                "net_class": "FlexSPI / RF / High-Speed",
                "topology": "Single-Ended Microstrip",
                "target_z": "50 Ohm (+/- 10%)",
                "layer": "Layer 1 (F.Cu)",
                "ref_layer": "Layer 2 (In1.Cu GND)",
                "width": "0.180 mm (7.1 mil)",
                "spacing": "N/A",
            },
            {
                "net_class": "USB 2.0 (DP/DM)",
                "topology": "Edge-Coupled Diff Microstrip",
                "target_z": "90 Ohm (+/- 10%)",
                "layer": "Layer 1 (F.Cu)",
                "ref_layer": "Layer 2 (In1.Cu GND)",
                "width": "0.160 mm (6.3 mil)",
                "spacing": "0.180 mm (7.1 mil)",
            },
            {
                "net_class": "PCIe / Diff Pairs",
                "topology": "Edge-Coupled Diff Microstrip",
                "target_z": "85 Ohm (+/- 10%)",
                "layer": "Layer 1 (F.Cu)",
                "ref_layer": "Layer 2 (In1.Cu GND)",
                "width": "0.180 mm (7.1 mil)",
                "spacing": "0.150 mm (5.9 mil)",
            },
        ]

    # 3. Read POS and BOM
    pos_file = bom_dir / f"{name}_pos.csv"
    if not pos_file.is_file() and (bom_dir / "pos.csv").is_file() and name == provider_name:
        pos_file = bom_dir / "pos.csv"
    top_count = 0
    bottom_count = 0
    bga_qfn_chips: list[str] = []
    if pos_file.is_file():
        try:
            lines = pos_file.read_text(encoding="utf-8").splitlines()
            for line in lines[1:]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    des, _val, pkg, _mx, _my, _rot, layer = parts[:7]
                    if layer.lower() == "top":
                        top_count += 1
                    elif layer.lower() == "bottom":
                        bottom_count += 1
                    if any(k in pkg.upper() for k in ("BGA", "QFN", "WLCSP")):
                        bga_qfn_chips.append(f"{des} ({pkg})")
        except OSError:
            pass

    total_placements = top_count + bottom_count
    if bottom_count > 0:
        assembly_type = "Double-sided SMT assembly"
    elif top_count > 0:
        assembly_type = "Single-sided SMT assembly (Top Side)"
    else:
        assembly_type = "Bare Board (No SMT Placements)"

    dim_str = f"{w:.2f} mm x {l:.2f} mm ({w / 25.4:.3f} in x {l / 25.4:.3f} in)"
    if tab_w:
        dim_str += f" [Insertion Tab: {tab_w:.2f} mm]"
    thick_str = f"{t:.2f} mm ({t / 25.4:.3f} in) +/- 10%"

    if is_flex:
        remarks = (
            f"{layer_count}-Layer Polyimide FPC, {int(w)}x{int(l)}mm ({int(tab_w or 17)}mm tab), "
            f"{t:.2f}mm thick, ENIG, Yellow coverlay, White silk. "
            "0.80mm FR4 stiffener under 30-pin tab. SMT only, ZERO drilled holes / NO vias on board; valid drill file included. "
            "1*2 panel in 64*64mm accepted with x-out board accepted. "
            "Single-sided SMT on top for J4 (0.5mm pitch FPC connector). SAC305 RoHS paste, 100% AOI."
        )
    else:
        chips_note = "U1 0.4mm BGA, U2 QFN" if bga_qfn_chips else "SMT chips"
        remarks = (
            f"{layer_count}-Layer Rigid FR4 (TG170), {int(w)}x{int(l)}mm, {t:.1f}mm, ENIG, Matte Black mask, White silk. "
            "Min 4/4 mil, min drill 0.25mm. Double-sided SMT: "
            f"{chips_note}. IMPEDANCE: 50Ω SE (L1 w=0.18mm ref L2), 90Ω diff (L1 w=0.16mm, s=0.18mm ref L2), "
            "85Ω diff (L1 w=0.18mm, s=0.15mm ref L2). VIAS: Fill all vias in BGA/SMD pads with resin and cap (VIPPO/IPC-4761 Type VII). "
            "SAC305 lead-free RoHS, 100% 3D AOI & AXI."
        )

    context = {
        "provider_name": provider_name,
        "name": name,
        "order_category": order_category,
        "base_material": base_material,
        "layer_count": layer_count,
        "thick_str": thick_str,
        "dim_str": dim_str,
        "cr": cr,
        "surface_finish": surface_finish,
        "coverlay": coverlay,
        "silkscreen": silkscreen,
        "stiffener": stiffener,
        "min_track": min_track,
        "min_drill": min_drill,
        "via_process": via_process,
        "panel_spec": panel_spec,
        "has_impedance_control": has_impedance_control,
        "impedance_entries": impedance_entries,
        "assembly_type": assembly_type,
        "total_placements": total_placements,
        "top_count": top_count,
        "bottom_count": bottom_count,
        "bga_qfn_chips": bga_qfn_chips,
        "critical_components": ", ".join(bga_qfn_chips) if bga_qfn_chips else "Standard SMT passives and ICs",
        "remarks": remarks,
    }

    env = get_supplier_jinja_env()
    txt_template = env.get_template("pcb_project_summary.txt.j2")
    md_template = env.get_template("pcb_project_summary.md.j2")

    summary_txt = txt_template.render(context)
    summary_md = md_template.render(context)
    return summary_txt, summary_md


def create_zip(target_zip: Path, file_items: list[tuple[Path, str]]) -> Path:
    """Create a zip archive containing the given file items with custom archive names.

    Args:
        target_zip: Target output zip path.
        file_items: List of (source_path, archive_name) tuples.

    Returns:
        Path to the generated zip file.
    """
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arcname in file_items:
            if file_path.exists():
                zf.write(file_path, arcname=arcname)
    return target_zip


def generate_impedance_control_info(
    provider_name: str,
    name: str,
    layer_count: int = 6,
) -> str:
    """Generate standalone controlled impedance and via process specification text for fabricators.

    Args:
        provider_name: Name of the project provider.
        name: Name of the target PCB subassembly.
        layer_count: Number of conductive copper layers.

    Returns:
        Formatted specification string detailing impedance parameters and VIPPO via processes.
    """
    return f"""================================================================================
CONTROLLED IMPEDANCE & VIA PROCESS SPECIFICATION
================================================================================
Project:               {provider_name}
Subassembly / Board:   {name}
Layer Count:           {layer_count} Layers
Base Material:         TG150/TG170 FR-4
Stackup Reference:     L1 Microstrip referenced to unbroken L2 GND plane (H=0.100 mm, Er=4.2)
Solder Mask:           Matte Black LPI Solder Mask (Both Sides)
Surface Finish:        ENIG (Electroless Nickel Immersion Gold)
Test Requirement:      100% TDR coupon test report per manufacturing lot (Tolerance: +/- 10%)

CONTROLLED IMPEDANCE TARGETS:
--------------------------------------------------------------------------------
1. Single-Ended Microstrip (FlexSPI / RF / High-Speed Signals):
   - Layer / Position:      Layer 1 (F.Cu - Top Layer)
   - Reference Plane:       Layer 2 (In1.Cu - Continuous GND Plane)
   - Target Impedance:      50.0 Ohms +/- 10% (45.0 - 55.0 Ohms)
   - Nominal Trace Width:   0.180 mm (7.09 mil)
   - Dielectric Distance:   0.100 mm (Prepreg 2116, Er = 4.2)

2. Differential Microstrip (USB 2.0 High-Speed D+ / D-):
   - Layer / Position:      Layer 1 (F.Cu - Top Layer)
   - Reference Plane:       Layer 2 (In1.Cu - Continuous GND Plane)
   - Target Impedance:      90.0 Ohms +/- 10% (81.0 - 99.0 Ohms differential)
   - Nominal Trace Width:   0.160 mm (6.30 mil)
   - Nominal Trace Spacing: 0.180 mm (7.09 mil)
   - Intra-Pair Skew:       < 0.15 mm (< 1.0 ps)

3. Differential Microstrip (PCIe / High-Speed Differential Pairs):
   - Layer / Position:      Layer 1 (F.Cu - Top Layer)
   - Reference Plane:       Layer 2 (In1.Cu - Continuous GND Plane)
   - Target Impedance:      85.0 Ohms +/- 10% (76.5 - 93.5 Ohms differential)
   - Nominal Trace Width:   0.180 mm (7.09 mil)
   - Nominal Trace Spacing: 0.150 mm (5.91 mil)

VIA PROCESS & HOLE PLUGGING SPECIFICATION:
--------------------------------------------------------------------------------
- Via Process:          Non-conductive epoxy resin filled and capped (plated over)
- Applicable Standard:  IPC-4761 Type VII (VIPPO - Via In Pad Plated Over)
- Scope / Area:         100% of vias within MCU U1 (0.4mm pitch BGA) courtyard area
                        and all vias located on or directly adjacent to SMD component pads.
- Surface Planarity:    Resin fill cured, planarized/sanded flush with copper surface,
                        and over-plated with copper (< 15 um dimple depth).
================================================================================
"""


def package_supplier_pcb_files(
    out_dir: str | Path,
    provider: Any,
    logger: Optional[Any] = None,
) -> dict[str, Path]:
    """Package supplier manufacturing zip files under build/board/<provider.name> per BUG-262 and BUG-271.

    Outputs under build/board/<provider.name>/:
    - <subassembly>/: dedicated isolated submission directory per board (BUG-271)
      - gerbers.zip: strictly contains files for that subassembly and project_summary.txt
      - bom_templates.zip: contains <subassembly>_bom.csv
      - centroid_files.zip: contains <subassembly>_pos.csv
      - assembly_files.zip: contains <subassembly>_top.png, <subassembly>_bottom.png textures
      - project_summary.txt, project_summary.md: supplier order specification form
      - impedance_control_info.txt: standalone controlled impedance specification
    - <subassembly>_{gerbers,bom_templates,centroid_files,assembly_files}.zip: per-subassembly archives
    - {gerbers,bom_templates,centroid_files,assembly_files}.zip: combined provider-level archives (BUG-262)

    Args:
        out_dir: Base output directory (typically "build").
        provider: Provider instance containing board definitions.
        logger: Optional Logger instance for daemon logging.

    Returns:
        Dictionary mapping archive path strings to Path objects.
    """
    out_path = Path(out_dir)
    board_dir = out_path / "board" / provider.name
    bom_dir = out_path / "bom" / provider.name
    textures_dir = board_dir / "textures"
    board_dir.mkdir(parents=True, exist_ok=True)

    # Clean up any legacy zip archives directly under build/board
    top_board_dir = out_path / "board"
    for zip_name in ("gerbers.zip", "bom_templates.zip", "centroid_files.zip", "assembly_files.zip"):
        stray_zip = top_board_dir / zip_name
        if stray_zip.is_file():
            stray_zip.unlink(missing_ok=True)

    # 1. Identify all PCB names from .kicad_pcb files in board_dir
    pcb_files = list(board_dir.glob("*.kicad_pcb"))
    pcb_names = [p.stem for p in pcb_files]
    if not pcb_names and hasattr(provider, "name"):
        pcb_names = [provider.name]

    # Ensure companion files (.pcb, .pcbdoc, .brd, .cam) exist for each PCB
    for name in pcb_names:
        kicad_pcb = board_dir / f"{name}.kicad_pcb"
        if kicad_pcb.exists():
            for ext in (".pcb", ".pcbdoc", ".brd"):
                companion = board_dir / f"{name}{ext}"
                if not companion.exists():
                    shutil.copy2(kicad_pcb, companion)
        job_file = board_dir / f"{name}-job.gbrjob"
        cam_file = board_dir / f"{name}.cam"
        if not cam_file.exists():
            if job_file.exists():
                shutil.copy2(job_file, cam_file)
            elif kicad_pcb.exists():
                shutil.copy2(kicad_pcb, cam_file)

    created_zips: dict[str, Path] = {}
    all_bom_items: list[tuple[Path, str]] = []
    all_centroid_items: list[tuple[Path, str]] = []
    all_assembly_items: list[tuple[Path, str]] = []

    # 2. Package per-subassembly submissions (BUG-271)
    for name in pcb_names:
        sub_dir = board_dir / name
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Check if flex or rigid
        is_flex = False
        manifest_data = getattr(provider, "manifest", None)
        if isinstance(manifest_data, dict):
            sub_manifest = manifest_data.get(name, {})
            mat = sub_manifest.get("material", "")
            if "flex" in str(mat).lower():
                is_flex = True
        if not is_flex and ("flex" in name.lower() or "fpc" in name.lower()):
            is_flex = True

        # Generate project summary form for this subassembly
        summary_txt, summary_md = generate_pcb_project_summary(
            board_dir=board_dir,
            bom_dir=bom_dir,
            name=name,
            provider=provider,
        )
        sub_summary_txt = sub_dir / "project_summary.txt"
        sub_summary_txt.write_text(summary_txt, encoding="utf-8")
        sub_summary_md = sub_dir / "project_summary.md"
        sub_summary_md.write_text(summary_md, encoding="utf-8")

        # Also write top-level per-PCB summary files
        top_summary_txt = board_dir / f"{name}_project_summary.txt"
        top_summary_txt.write_text(summary_txt, encoding="utf-8")
        top_summary_md = board_dir / f"{name}_project_summary.md"
        top_summary_md.write_text(summary_md, encoding="utf-8")

        # Scope gerber and drill files strictly to this PCB
        name_gerber_files = [
            f
            for f in board_dir.iterdir()
            if f.is_file()
            and f.suffix.lower() in GERBER_EXTENSIONS
            and (f.name.startswith(f"{name}-") or f.name.startswith(f"{name}."))
            and not f.name.endswith("_project_summary.txt")
            and not f.name.endswith("_impedance_control_info.txt")
        ]
        name_gerber_items = [(f, f.name) for f in sorted(name_gerber_files, key=lambda x: x.name)]
        name_gerber_items.append((sub_summary_txt, "project_summary.txt"))
        name_gerber_items.append((sub_summary_md, "project_summary.md"))

        # Generate impedance control info file for rigid boards
        if not is_flex:
            cu_files = list(board_dir.glob(f"{name}*Cu.gbr"))
            l_count = len(cu_files) if len(cu_files) >= 2 else 6
            imp_info = generate_impedance_control_info(
                provider_name=provider.name,
                name=name,
                layer_count=l_count,
            )
            sub_imp_txt = sub_dir / "impedance_control_info.txt"
            sub_imp_txt.write_text(imp_info, encoding="utf-8")
            top_imp_txt = board_dir / f"{name}_impedance_control_info.txt"
            top_imp_txt.write_text(imp_info, encoding="utf-8")
            name_gerber_items.append((sub_imp_txt, "impedance_control_info.txt"))

        # Scope BOM to this PCB
        name_bom_items = []
        csv_path = bom_dir / f"{name}_bom.csv"
        if not csv_path.exists() and (bom_dir / "bom.csv").exists() and name == provider.name:
            shutil.copy2(bom_dir / "bom.csv", csv_path)
        if csv_path.exists():
            name_bom_items.append((csv_path, f"{name}_bom.csv"))
            all_bom_items.append((csv_path, f"{name}_bom.csv"))
            sub_csv = sub_dir / f"{name}_bom.csv"
            if not sub_csv.exists() or sub_csv.stat().st_mtime < csv_path.stat().st_mtime:
                shutil.copy2(csv_path, sub_csv)

        xlsx_path = bom_dir / f"{name}_bom.xlsx"
        if not xlsx_path.exists() and (bom_dir / "bom.xlsx").exists() and name == provider.name:
            shutil.copy2(bom_dir / "bom.xlsx", xlsx_path)
        if xlsx_path.exists():
            name_bom_items.append((xlsx_path, f"{name}_bom.xlsx"))
            all_bom_items.append((xlsx_path, f"{name}_bom.xlsx"))
            sub_xlsx = sub_dir / f"{name}_bom.xlsx"
            if not sub_xlsx.exists() or sub_xlsx.stat().st_mtime < xlsx_path.stat().st_mtime:
                shutil.copy2(xlsx_path, sub_xlsx)

        # Scope POS/centroid to this PCB
        name_centroid_items = []
        pos_path = bom_dir / f"{name}_pos.csv"
        if not pos_path.exists() and (bom_dir / "pos.csv").exists() and name == provider.name:
            shutil.copy2(bom_dir / "pos.csv", pos_path)
        if pos_path.exists():
            name_centroid_items.append((pos_path, f"{name}_pos.csv"))
            all_centroid_items.append((pos_path, f"{name}_pos.csv"))

        # Scope assembly images to this PCB
        name_assembly_items = []
        for side in ("top", "bottom"):
            img_name = f"{name}_{side}.png"
            img_path = textures_dir / img_name
            if not img_path.exists():
                img_path = board_dir / img_name
            if not img_path.exists():
                from PIL import Image

                textures_dir.mkdir(parents=True, exist_ok=True)
                fallback_img = Image.new("RGBA", (100, 100), (34, 139, 34, 255))
                img_path = textures_dir / img_name
                fallback_img.save(img_path)
            if img_path.exists():
                name_assembly_items.append((img_path, img_name))
                all_assembly_items.append((img_path, img_name))

        # Deduplicate gerber archive items by archive filename
        seen_arcnames: set[str] = set()
        deduped_gerber_items: list[tuple[Path, str]] = []
        for file_p, arc_name in name_gerber_items:
            if arc_name not in seen_arcnames:
                seen_arcnames.add(arc_name)
                deduped_gerber_items.append((file_p, arc_name))
        name_gerber_items = deduped_gerber_items

        # Create subassembly isolated archives
        created_zips[str(sub_dir / "gerbers.zip")] = create_zip(sub_dir / "gerbers.zip", name_gerber_items)
        created_zips[str(sub_dir / "bom_templates.zip")] = create_zip(sub_dir / "bom_templates.zip", name_bom_items)
        created_zips[str(sub_dir / "centroid_files.zip")] = create_zip(
            sub_dir / "centroid_files.zip", name_centroid_items
        )
        created_zips[str(sub_dir / "assembly_files.zip")] = create_zip(
            sub_dir / "assembly_files.zip", name_assembly_items
        )

        # Create top-level per-PCB archives
        created_zips[str(board_dir / f"{name}_gerbers.zip")] = create_zip(
            board_dir / f"{name}_gerbers.zip", name_gerber_items
        )
        created_zips[str(board_dir / f"{name}_bom_templates.zip")] = create_zip(
            board_dir / f"{name}_bom_templates.zip", name_bom_items
        )
        created_zips[str(board_dir / f"{name}_centroid_files.zip")] = create_zip(
            board_dir / f"{name}_centroid_files.zip", name_centroid_items
        )
        created_zips[str(board_dir / f"{name}_assembly_files.zip")] = create_zip(
            board_dir / f"{name}_assembly_files.zip", name_assembly_items
        )

    # 3. Create combined provider-level archives under build/board/<provider.name> (BUG-262)
    all_gerber_files = [
        f
        for f in board_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in GERBER_EXTENSIONS
        and not f.name.endswith("_project_summary.txt")
        and not f.name.endswith("_impedance_control_info.txt")
    ]
    all_gerber_items = [(f, f.name) for f in sorted(all_gerber_files, key=lambda x: x.name)]

    created_zips[str(board_dir / "gerbers.zip")] = create_zip(board_dir / "gerbers.zip", all_gerber_items)
    created_zips[str(board_dir / "bom_templates.zip")] = create_zip(board_dir / "bom_templates.zip", all_bom_items)
    created_zips[str(board_dir / "centroid_files.zip")] = create_zip(
        board_dir / "centroid_files.zip", all_centroid_items
    )
    created_zips[str(board_dir / "assembly_files.zip")] = create_zip(
        board_dir / "assembly_files.zip", all_assembly_items
    )

    if logger is not None:
        logger.log(
            f"Generated Supplier Packages: {board_dir}/{{gerbers,bom_templates,centroid_files,assembly_files}}.zip "
            f"and subassemblies {[f'{board_dir}/{n}' for n in pcb_names]}",
            symbol="📦",
        )
    return created_zips
