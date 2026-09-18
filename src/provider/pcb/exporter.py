"""Manufacturing artifacts, BOM, Pick-and-Place, and vector schematic exporter for PCBs."""

import csv
import io
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import jinja2
from build123d import Box, BuildPart, Compound, Part, Solid, export_step
from model.pcb import PCBConfig, StackupModel
from model.wiring import Wiring, FootprintModel, NetModel


SCH_PIN_LEN_MM: float = 5.08
SCH_PIN_SPACING_MM: float = 5.08
SCH_BOX_MIN_HALF_H_MM: float = 10.16
SCH_BOX_MIN_HALF_W_MM: float = 15.24


class PCBExporter:
    """Orchestrates generation of manufacturing packages, supplier BOM/CPL, schematics, and 3D STEP models."""

    def __init__(self, pcb_config: PCBConfig, wiring: Wiring):
        """Initialize the exporter with PCB stackup configuration and netlist."""
        self.config = pcb_config
        self.wiring = wiring
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(Path(__file__).parent.parent / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def export_kicad_pcb(self, output_file: str | Path) -> Path:
        """Render and save KiCad 7/8 compatible .kicad_pcb file using Jinja2 template."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        template = self.jinja_env.get_template("kicad_pcb.j2")
        w, l, _ = self.config.dimensions_mm
        half_w, half_l = w / 2.0, l / 2.0

        # Build net mapping
        nets = []
        net_name_to_idx = {"": 0}
        for idx, n in enumerate(self.wiring.nets, start=1):
            net_name_to_idx[n.name] = idx
            nets.append({"idx": idx, "name": n.name})

        # Process component footprints and pads (centered on drawing sheet)
        footprints_data = []
        for fp in self.wiring.footprints:
            fp_pins = []
            for p in fp.pins:
                # Find net connected to this pin
                net_name = ""
                for net in self.wiring.nets:
                    for comp_name, pin_name in net.pins:
                        if comp_name == fp.name and pin_name == p.name:
                            net_name = net.name
                            break
                    if net_name:
                        break

                net_idx = net_name_to_idx.get(net_name, 0)
                fp_pins.append(
                    {
                        "name": p.name,
                        "x_mm": round(p.position[0], 4),
                        "y_mm": round(p.position[1], 4),
                        "pad_dia_mm": 0.35,
                        "net_idx": net_idx,
                        "net_name": net_name,
                    }
                )

            fp_layer = getattr(fp, "layer", None) or ("B.Cu" if fp.position[2] < 0 else "F.Cu")
            silk_layer = "B.SilkS" if fp_layer == "B.Cu" else "F.SilkS"
            fab_layer = "B.Fab" if fp_layer == "B.Cu" else "F.Fab"
            paste_layer = "B.Paste" if fp_layer == "B.Cu" else "F.Paste"
            mask_layer = "B.Mask" if fp_layer == "B.Cu" else "F.Mask"

            dim_w = fp.dimensions[0] if fp.dimensions else 4.0
            dim_h = fp.dimensions[1] if fp.dimensions else 4.0
            w_half = round(dim_w / 2.0 + 0.4, 4)
            h_half = round(dim_h / 2.0 + 0.4, 4)
            ref_y = round(-h_half - 1.2, 4)
            val_y = round(h_half + 1.2, 4)

            tick_w = round(min(1.0, max(0.2, w_half * 0.4)), 4)
            tick_h = round(min(1.0, max(0.2, h_half * 0.4)), 4)
            alignment_lines = [
                {"x1": -w_half, "y1": -h_half, "x2": round(-w_half + tick_w, 4), "y2": -h_half},
                {"x1": -w_half, "y1": -h_half, "x2": -w_half, "y2": round(-h_half + tick_h, 4)},
                {"x1": w_half, "y1": -h_half, "x2": round(w_half - tick_w, 4), "y2": -h_half},
                {"x1": w_half, "y1": -h_half, "x2": w_half, "y2": round(-h_half + tick_h, 4)},
                {"x1": -w_half, "y1": h_half, "x2": round(-w_half + tick_w, 4), "y2": h_half},
                {"x1": -w_half, "y1": h_half, "x2": -w_half, "y2": round(h_half - tick_h, 4)},
                {"x1": w_half, "y1": h_half, "x2": round(w_half - tick_w, 4), "y2": h_half},
                {"x1": w_half, "y1": h_half, "x2": w_half, "y2": round(h_half - tick_h, 4)},
            ]
            pin1_dot = {
                "cx": round(-w_half - 0.5, 4),
                "cy": round(-h_half - 0.5, 4),
                "ex": round(-w_half - 0.25, 4),
                "ey": round(-h_half - 0.5, 4),
            }

            footprints_data.append(
                {
                    "name": fp.name,
                    "package": fp.package,
                    "value": fp.label.text if fp.label else fp.package,
                    "uuid": str(uuid.uuid4()),
                    "x_mm": round(self.config.sheet_center_x_mm + fp.position[0], 4),
                    "y_mm": round(self.config.sheet_center_y_mm + fp.position[1], 4),
                    "layer": fp_layer,
                    "silk_layer": silk_layer,
                    "fab_layer": fab_layer,
                    "paste_layer": paste_layer,
                    "mask_layer": mask_layer,
                    "ref_y": ref_y,
                    "val_y": val_y,
                    "alignment_lines": alignment_lines,
                    "pin1_dot": pin1_dot,
                    "pins": fp_pins,
                }
            )

        copper_inners = [l for l in self.config.stackup.copper_layers[1:-1]]

        silkscreen_data = []
        for st in self.config.silkscreen_texts:
            silkscreen_data.append(
                {
                    "text": st.text,
                    "layer": st.layer,
                    "x_mm": round(self.config.sheet_center_x_mm + st.position[0], 4),
                    "y_mm": round(self.config.sheet_center_y_mm + st.position[1], 4),
                    "font_size": st.font_size,
                    "thickness": st.thickness,
                    "rotation": st.rotation,
                    "mirror": st.mirror or (st.layer == "B.SilkS"),
                }
            )

        mounting_holes_data = []
        for mh in self.config.mounting_holes:
            net_name = mh.net or ""
            net_idx = net_name_to_idx.get(net_name, 0)
            pad_dia = mh.pad_diameter_mm or (mh.drill_diameter_mm + 1.2 if mh.plated else mh.drill_diameter_mm)
            mounting_holes_data.append(
                {
                    "name": mh.name,
                    "x_mm": round(self.config.sheet_center_x_mm + mh.position_mm[0], 4),
                    "y_mm": round(self.config.sheet_center_y_mm + mh.position_mm[1], 4),
                    "drill_mm": round(mh.drill_diameter_mm, 4),
                    "pad_mm": round(pad_dia, 4),
                    "plated": mh.plated,
                    "net_idx": net_idx,
                    "net_name": net_name,
                }
            )

        # Traces
        segments_data = []
        for tr in self.config.traces:
            net_idx = net_name_to_idx.get(tr.net, 0)
            segments_data.append(
                {
                    "x1": round(self.config.sheet_center_x_mm + tr.start_mm[0], 4),
                    "y1": round(self.config.sheet_center_y_mm + tr.start_mm[1], 4),
                    "x2": round(self.config.sheet_center_x_mm + tr.end_mm[0], 4),
                    "y2": round(self.config.sheet_center_y_mm + tr.end_mm[1], 4),
                    "width": tr.width_mm,
                    "layer": tr.layer,
                    "net_idx": net_idx,
                }
            )

        # Vias
        vias_data = []
        for v in self.config.vias:
            net_idx = net_name_to_idx.get(v.net, 0)
            vias_data.append(
                {
                    "x": round(self.config.sheet_center_x_mm + v.position_mm[0], 4),
                    "y": round(self.config.sheet_center_y_mm + v.position_mm[1], 4),
                    "dia": round(v.pad_diameter_mm, 4),
                    "drill": round(v.drill_diameter_mm, 4),
                    "layer1": v.layer_start,
                    "layer2": v.layer_end,
                    "net_idx": net_idx,
                }
            )

        # Copper Zones
        zones_data = []
        for z in self.config.copper_regions:
            net_idx = net_name_to_idx.get(z.net, 0)
            pts = [
                {
                    "x": round(self.config.sheet_center_x_mm + pt[0], 4),
                    "y": round(self.config.sheet_center_y_mm + pt[1], 4),
                }
                for pt in z.polygon_points_mm
            ]
            zones_data.append(
                {
                    "net_idx": net_idx,
                    "net_name": z.net,
                    "layer": z.layer,
                    "priority": z.priority,
                    "clearance_mm": z.clearance_mm,
                    "pts": pts,
                }
            )

        # Test Points
        test_points_data = []
        for tp in self.config.test_points:
            net_idx = net_name_to_idx.get(tp.net, 0)
            silk_layer = "B.SilkS" if tp.layer == "B.Cu" else "F.SilkS"
            mask_layer = "B.Mask" if tp.layer == "B.Cu" else "F.Mask"
            test_points_data.append(
                {
                    "name": tp.name,
                    "x_mm": round(self.config.sheet_center_x_mm + tp.position_mm[0], 4),
                    "y_mm": round(self.config.sheet_center_y_mm + tp.position_mm[1], 4),
                    "dia_mm": round(tp.pad_diameter_mm, 4),
                    "drill_mm": round(tp.drill_diameter_mm, 4),
                    "label_x": 0.0,
                    "label_y": -round(tp.pad_diameter_mm / 2.0 + 0.8, 4),
                    "label_angle": 90,
                    "layer": tp.layer,
                    "silk_layer": silk_layer,
                    "mask_layer": mask_layer,
                    "net_idx": net_idx,
                    "net_name": tp.net,
                }
            )

        rendered = template.render(
            board=self.config,
            copper_inner_layers=copper_inners,
            nets=nets,
            footprints=footprints_data,
            silkscreen_texts=silkscreen_data,
            mounting_holes=mounting_holes_data,
            test_points=test_points_data,
            segments=segments_data,
            vias=vias_data,
            zones=zones_data,
            outline={
                "x1": round(self.config.sheet_center_x_mm - half_w, 4),
                "y1": round(self.config.sheet_center_y_mm - half_l, 4),
                "x2": round(self.config.sheet_center_x_mm + half_w, 4),
                "y2": round(self.config.sheet_center_y_mm + half_l, 4),
            },
        )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        return out_path

    def export_kicad_sch(self, output_file: str | Path) -> Path:
        """Render and save KiCad 8 .kicad_sch schematic file using Jinja2 template."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        template = self.jinja_env.get_template("kicad_sch.j2")
        lib_symbols_dict: Dict[str, Any] = {}

        def sort_footprints(fp: Any) -> tuple[int, str]:
            order = {"J1": 0, "U1": 1, "U2": 2, "J2": 3}
            return (order.get(fp.name, 99), fp.name)

        sorted_fps = sorted(self.wiring.footprints, key=sort_footprints) if self.wiring else []

        for fp in sorted_fps:
            pkg = fp.package
            if pkg not in lib_symbols_dict:
                left_pins = [p for p in fp.pins if getattr(p, "side", None) == "left"]
                right_pins = [p for p in fp.pins if getattr(p, "side", None) == "right"]
                top_pins = [p for p in fp.pins if getattr(p, "side", None) == "top"]
                bottom_pins = [p for p in fp.pins if getattr(p, "side", None) == "bottom"]
                other_pins = [p for p in fp.pins if getattr(p, "side", None) not in ("left", "right", "top", "bottom")]
                for idx, p in enumerate(other_pins):
                    if idx % 2 == 0:
                        left_pins.append(p)
                    else:
                        right_pins.append(p)

                n_v = max(len(left_pins), len(right_pins), 1)
                n_h = max(len(top_pins), len(bottom_pins), 1)
                half_h = round(max(SCH_BOX_MIN_HALF_H_MM, (n_v + 1) * SCH_PIN_SPACING_MM / 2.0), 2)
                half_w = round(max(SCH_BOX_MIN_HALF_W_MM, (n_h + 1) * SCH_PIN_SPACING_MM / 2.0), 2)

                pins_meta = []
                start_y = (len(left_pins) - 1) * SCH_PIN_SPACING_MM / 2.0
                for i, p in enumerate(left_pins):
                    pins_meta.append(
                        {
                            "name": p.name,
                            "number": p.name,
                            "x": round(-half_w - SCH_PIN_LEN_MM, 2),
                            "y": round(start_y - i * SCH_PIN_SPACING_MM, 2),
                            "angle": 0,
                            "length": SCH_PIN_LEN_MM,
                            "side": "left",
                        }
                    )
                start_y = (len(right_pins) - 1) * SCH_PIN_SPACING_MM / 2.0
                for i, p in enumerate(right_pins):
                    pins_meta.append(
                        {
                            "name": p.name,
                            "number": p.name,
                            "x": round(half_w + SCH_PIN_LEN_MM, 2),
                            "y": round(start_y - i * SCH_PIN_SPACING_MM, 2),
                            "angle": 180,
                            "length": SCH_PIN_LEN_MM,
                            "side": "right",
                        }
                    )
                start_x = -(len(top_pins) - 1) * SCH_PIN_SPACING_MM / 2.0
                for i, p in enumerate(top_pins):
                    pins_meta.append(
                        {
                            "name": p.name,
                            "number": p.name,
                            "x": round(start_x + i * SCH_PIN_SPACING_MM, 2),
                            "y": round(-half_h - SCH_PIN_LEN_MM, 2),
                            "angle": 270,
                            "length": SCH_PIN_LEN_MM,
                            "side": "top",
                        }
                    )
                start_x = -(len(bottom_pins) - 1) * SCH_PIN_SPACING_MM / 2.0
                for i, p in enumerate(bottom_pins):
                    pins_meta.append(
                        {
                            "name": p.name,
                            "number": p.name,
                            "x": round(start_x + i * SCH_PIN_SPACING_MM, 2),
                            "y": round(half_h + SCH_PIN_LEN_MM, 2),
                            "angle": 90,
                            "length": SCH_PIN_LEN_MM,
                            "side": "bottom",
                        }
                    )

                prefix = "U" if pkg.startswith(("BGA", "QFN", "SOIC", "TSSOP")) else "J"
                lib_symbols_dict[pkg] = {
                    "package": pkg,
                    "prefix": prefix,
                    "half_w": half_w,
                    "half_h": half_h,
                    "pins": pins_meta,
                }

        net_map: Dict[tuple[str, str], str] = {}
        if self.wiring and getattr(self.wiring, "nets", None):
            for net in self.wiring.nets:
                for fp_pin in net.pins:
                    if len(fp_pin) == 2:
                        net_map[(fp_pin[0], fp_pin[1])] = net.name

        layout_slots = {
            "J1": (65.0, 65.0),
            "U1": (130.0, 105.0),
            "U2": (185.0, 65.0),
            "J2": (65.0, 145.0),
        }

        symbols_data = []
        labels_data = []

        for idx, fp in enumerate(sorted_fps):
            pkg = fp.package
            lib_sym = lib_symbols_dict[pkg]
            sym_x, sym_y = layout_slots.get(
                fp.name,
                (round(65.0 + (idx % 3) * 75.0, 2), round(65.0 + (idx // 3) * 75.0, 2)),
            )

            sym_pins = []
            for p_def in lib_sym["pins"]:
                sym_pins.append({"number": p_def["number"], "uuid": str(uuid.uuid4())})
                net_name = net_map.get((fp.name, p_def["number"]))
                if net_name:
                    side = p_def["side"]
                    pin_tip_x = round(sym_x + p_def["x"], 2)
                    pin_tip_y = round(sym_y + p_def["y"], 2)
                    match side:
                        case "left":
                            lbl_x = pin_tip_x - 1.0
                            lbl_y = pin_tip_y
                            angle = 0
                            justify = "right"
                        case "right":
                            lbl_x = pin_tip_x + 1.0
                            lbl_y = pin_tip_y
                            angle = 0
                            justify = "left"
                        case "top":
                            lbl_x = pin_tip_x
                            lbl_y = pin_tip_y - 1.0
                            angle = 90
                            justify = "right"
                        case "bottom" | _:
                            lbl_x = pin_tip_x
                            lbl_y = pin_tip_y + 1.0
                            angle = 90
                            justify = "left"

                    labels_data.append(
                        {
                            "text": net_name,
                            "x": lbl_x,
                            "y": lbl_y,
                            "angle": angle,
                            "justify": justify,
                            "uuid": str(uuid.uuid4()),
                        }
                    )

            symbols_data.append(
                {
                    "package": pkg,
                    "name": fp.name,
                    "value": getattr(fp, "mpn", None) or (fp.label.text if fp.label else pkg),
                    "mpn": getattr(fp, "mpn", None) or "",
                    "uuid": str(uuid.uuid4()),
                    "x": sym_x,
                    "y": sym_y,
                    "half_w": lib_sym["half_w"],
                    "half_h": lib_sym["half_h"],
                    "pins": sym_pins,
                }
            )

        rendered = template.render(
            board=self.config,
            sch_uuid=str(uuid.uuid4()),
            lib_symbols=list(lib_symbols_dict.values()),
            symbols=symbols_data,
            wires=[],
            labels=labels_data,
        )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        return out_path

    def export_bom_csv(self, output_file: str | Path) -> Path:
        """Export supplier-ready Bill of Materials (BOM) in standard CSV format."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "Id",
            "Designator",
            "Package",
            "Quantity",
            "Designation",
            "MPN",
            "Supplier_PN",
        ]

        # Group components by package and MPN to aggregate quantities
        rows = []
        for idx, fp in enumerate(self.wiring.footprints, start=1):
            rows.append(
                {
                    "Id": idx,
                    "Designator": fp.name,
                    "Package": fp.package,
                    "Quantity": 1,
                    "Designation": fp.label.text if fp.label else fp.package,
                    "MPN": fp.mpn or f"GENERIC-{fp.package.upper()}",
                    "Supplier_PN": fp.supplier_pn or "N/A",
                }
            )

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return out_path

    def export_pick_and_place_csv(self, output_file: str | Path) -> Path:
        """Export Centroid / Pick-and-Place (CPL) file for automated SMT assembly."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"]
        rows = []
        for fp in self.wiring.footprints:
            rows.append(
                {
                    "Designator": fp.name,
                    "Val": fp.label.text if fp.label else fp.package,
                    "Package": fp.package,
                    "Mid X": f"{fp.position[0]:.4f}mm",
                    "Mid Y": f"{fp.position[1]:.4f}mm",
                    "Rotation": f"{fp.rotation[2]:.1f}",
                    "Layer": "Bottom" if getattr(fp, "layer", "F.Cu") == "B.Cu" or fp.position[2] < 0 else "Top",
                }
            )

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return out_path

    def export_schematic_svg(self, output_file: str | Path) -> Path:
        """Generate a vector SVG schematic diagram showing components, pins, and net connections."""
        from provider.schematic_diagram import SchematicDiagram

        diagram = SchematicDiagram(self.wiring, pcb_config=self.config)
        return diagram.render_svg(output_file)

    def export_schematic_pdf(self, output_file: str | Path) -> Path:
        """Generate a multi-page PDF schematic showing title page, TOC, and schematic sheets."""
        from provider.schematic_diagram import SchematicDiagram

        diagram = SchematicDiagram(self.wiring, pcb_config=self.config)
        return diagram.render_pdf(output_file)

    def export_capacitive_config_json(self, output_file: str | Path) -> Path:
        """Export firmware-ready capacitive electrode channel, threshold, and geometry configuration."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        channels = []
        for idx, sensor in enumerate(self.config.capacitive_sensors):
            ch_id = sensor.channel_id if sensor.channel_id is not None else idx
            channels.append(
                {
                    "channel_id": ch_id,
                    "name": sensor.name,
                    "electrode_type": sensor.electrode_type,
                    "shape": sensor.shape,
                    "dimensions_mm": list(sensor.area_mm),
                    "pitch_mm": sensor.pitch_mm,
                    "gap_mm": sensor.gap_mm,
                    "drive_shield": sensor.drive_shield,
                    "hatch_ground_pour": sensor.hatch_ground_pour,
                    "hatch_pitch_mm": sensor.hatch_pitch_mm,
                    "hatch_line_width_mm": sensor.hatch_line_width_mm,
                    "tx_pin": sensor.tx_pin or f"TX_{ch_id}",
                    "rx_pin": sensor.rx_pin or f"RX_{ch_id}",
                    "threshold_raw": sensor.threshold_raw if sensor.threshold_raw is not None else 2500,
                    "shape_ref": getattr(sensor, "shape_ref", None),
                }
            )

        data = {
            "board": self.config.name,
            "board_type": self.config.board_type,
            "channel_count": len(channels),
            "channels": channels,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return out_path

    def export_board(self, output_dir: str | Path, pcb_filename: Optional[str] = None) -> Dict[str, Path]:
        """Export native KiCad board file and compile manufacturing Gerbers + drill via kicad-cli."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export canonical .kicad_pcb target
        fname = pcb_filename or f"{self.config.name}.kicad_pcb"
        if not fname.endswith(".kicad_pcb"):
            fname += ".kicad_pcb"
        kicad_pcb_path = out_dir / fname
        self.export_kicad_pcb(kicad_pcb_path)

        exported_files: Dict[str, Path] = {kicad_pcb_path.name: kicad_pcb_path}

        # 2. Invoke kicad-cli for manufacturing CAM files (Gerber RS-274X, drill, job)
        from provider.pcb.kicad_cli import KiCadCLI

        cli = KiCadCLI()
        if cli.is_available:
            copper_count = len(self.config.stackup.copper_layers)
            fab_layers = [
                "F.Cu",
                *[f"In{i}.Cu" for i in range(1, copper_count - 1)],
                "B.Cu",
                "F.Mask",
                "B.Mask",
                "F.SilkS",
                "B.SilkS",
                "Edge.Cuts",
            ]
            cam_files = cli.export_all_board_files(kicad_pcb_path, out_dir, layers=fab_layers)
            exported_files.update(cam_files)

        return exported_files

    def export_board_archive(self, output_zip: str | Path) -> Path:
        """Export manufacturing Gerbers, drill, and board files packaged in a ZIP archive."""
        out_zip_path = Path(output_zip).resolve()
        out_zip_path.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = out_zip_path.parent / f"_temp_{out_zip_path.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            exported = self.export_board(temp_dir)
            with zipfile.ZipFile(out_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, fpath in exported.items():
                    if fpath.is_file():
                        zf.write(fpath, arcname=fname)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return out_zip_path

    def export_interactive_bom(self, output_html: str | Path) -> Path:
        """Export standalone Interactive HTML BOM (iBOM) for visual component inspection."""
        out_path = Path(output_html).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        components_data = []
        for idx, fp in enumerate(self.wiring.footprints, start=1):
            components_data.append(
                {
                    "ref": fp.name,
                    "val": fp.label.text if fp.label else fp.package,
                    "package": fp.package,
                    "mpn": fp.mpn or "N/A",
                    "supplier_pn": fp.supplier_pn or "N/A",
                    "x": fp.position[0],
                    "y": fp.position[1],
                }
            )

        template = self.jinja_env.get_template("ibom.html.j2")
        html_content = template.render(
            board=self.config,
            components=components_data,
        )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return out_path

    def build_solid(self) -> Compound:
        """Build and return solid 3D CAD geometry of the PCB substrate."""
        w, l, _ = self.config.dimensions_mm
        thickness = self.config.stackup.total_thickness_mm

        with BuildPart() as pcb_part:
            Box(w, l, thickness)

        return pcb_part.part

    def export_step_solid(self, output_step: str | Path) -> Path:
        """Export solid 3D STEP model of the PCB substrate with mounting holes for enclosure CAD."""
        out_path = Path(output_step).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        solid = self.build_solid()
        export_step(solid, str(out_path))
        return out_path
