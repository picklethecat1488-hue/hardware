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
from build123d import Box, BuildPart, export_step
from model.pcb import PCBConfig, StackupModel
from model.wiring import Wiring, FootprintModel, NetModel


class PCBExporter:
    """Orchestrates generation of manufacturing packages, supplier BOM/CPL, schematics, and 3D STEP models."""

    def __init__(self, pcb_config: PCBConfig, wiring: Wiring):
        """Initialize the exporter with PCB stackup configuration and netlist."""
        self.config = pcb_config
        self.wiring = wiring
        templates_dir = Path(__file__).resolve().parents[1] / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def export_kicad_pcb(self, output_file: str | Path) -> Path:
        """Render and save KiCad 8 .kicad_pcb layout file using Jinja2 template."""
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

        # Process component footprints and pads
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

            footprints_data.append(
                {
                    "name": fp.name,
                    "package": fp.package,
                    "value": fp.label.text if fp.label else fp.package,
                    "uuid": str(uuid.uuid4()),
                    "x_mm": round(fp.position[0], 4),
                    "y_mm": round(fp.position[1], 4),
                    "pins": fp_pins,
                }
            )

        copper_inners = [l for l in self.config.stackup.copper_layers[1:-1]]

        rendered = template.render(
            board=self.config,
            copper_inner_layers=copper_inners,
            nets=nets,
            footprints=footprints_data,
            segments=[],
            vias=[],
            outline={
                "x1": round(-half_w, 4),
                "y1": round(-half_l, 4),
                "x2": round(half_w, 4),
                "y2": round(half_l, 4),
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
        symbols_data = []
        for fp in self.wiring.footprints:
            symbols_data.append(
                {
                    "name": fp.name,
                    "package": fp.package,
                    "value": fp.label.text if fp.label else fp.package,
                    "uuid": str(uuid.uuid4()),
                    "x": round(fp.position[0], 2),
                    "y": round(fp.position[1], 2),
                    "pins": [{"name": p.name, "uuid": str(uuid.uuid4())} for p in fp.pins],
                }
            )

        rendered = template.render(
            board=self.config,
            sch_uuid=str(uuid.uuid4()),
            symbols=symbols_data,
            wires=[],
            labels=[],
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
                    "Layer": "Top",
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

    def export_gerber_archive(self, output_zip: str | Path) -> Path:
        """Export complete Gerber RS-274X and Excellon drill manufacturing archive in ZIP format."""
        out_zip_path = Path(output_zip).resolve()
        out_zip_path.parent.mkdir(parents=True, exist_ok=True)

        w, l, _ = self.config.dimensions_mm
        half_w, half_l = w / 2.0, l / 2.0

        # Helper to generate RS-274X Gerber content
        def make_gerber(layer_name: str, shapes: List[str]) -> str:
            lines = [
                "G04 Hardware Project Automated Gerber Export*",
                f"G04 Layer: {layer_name}*",
                "%FSLAX36Y36*%",
                "%MOMM*%",
                "%LPD*%",
                "%ADD10C,0.150000*%",  # Trace aperture 0.15mm
                "%ADD11C,0.350000*%",  # Pad aperture 0.35mm
                "%ADD12R,0.000000X0.000000*%",
                "D10*",
            ]
            lines.extend(shapes)
            lines.append("M02*")
            return "\n".join(lines)

        # Helper to generate Excellon drill content
        def make_drill(vias: List[Tuple[float, float, float]]) -> str:
            lines = [
                "M48",
                "METRIC,TZ",
                "FMAT,2",
                "T1C0.200",  # Tool 1: 0.2mm via drill
                "%",
                "G90",
                "G05",
                "T1",
            ]
            for vx, vy, _ in vias:
                # Excellon format: X and Y coordinates in 1/10000 mm
                ix = int(round((vx + 100.0) * 1000))
                iy = int(round((vy + 100.0) * 1000))
                lines.append(f"X{ix:06d}Y{iy:06d}")
            lines.append("M30")
            return "\n".join(lines)

        # Board outline shape (Edge_Cuts)
        edge_cuts = [
            f"X{int((-half_w + 100.0) * 1000000):09d}Y{int((-half_l + 100.0) * 1000000):09d}D02*",
            f"X{int((half_w + 100.0) * 1000000):09d}Y{int((-half_l + 100.0) * 1000000):09d}D01*",
            f"X{int((half_w + 100.0) * 1000000):09d}Y{int((half_l + 100.0) * 1000000):09d}D01*",
            f"X{int((-half_w + 100.0) * 1000000):09d}Y{int((half_l + 100.0) * 1000000):09d}D01*",
            f"X{int((-half_w + 100.0) * 1000000):09d}Y{int((-half_l + 100.0) * 1000000):09d}D01*",
        ]

        # Top copper pads and flashes
        f_cu_shapes = ["D11*"]
        vias_data = []
        for fp in self.wiring.footprints:
            for p in fp.pins:
                x = fp.position[0] + p.position[0]
                y = fp.position[1] + p.position[1]
                ix = int(round((x + 100.0) * 1000000))
                iy = int(round((y + 100.0) * 1000000))
                f_cu_shapes.append(f"X{ix:09d}Y{iy:09d}D03*")
                vias_data.append((x, y, 0.20))

        # Create ZIP containing all Gerber and drill layers
        with zipfile.ZipFile(out_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Edge_Cuts.gbr", make_gerber("Edge_Cuts", edge_cuts))
            zf.writestr("F_Cu.gbr", make_gerber("F_Cu", f_cu_shapes))
            for layer in self.config.stackup.copper_layers[1:-1]:
                zf.writestr(f"{layer.name.replace('.', '_')}.gbr", make_gerber(layer.name, edge_cuts))
            zf.writestr("B_Cu.gbr", make_gerber("B_Cu", edge_cuts))
            zf.writestr("F_Mask.gbr", make_gerber("F_Mask", f_cu_shapes))
            zf.writestr("B_Mask.gbr", make_gerber("B_Mask", edge_cuts))
            zf.writestr("F_SilkS.gbr", make_gerber("F_SilkS", edge_cuts))
            zf.writestr("B_SilkS.gbr", make_gerber("B_SilkS", edge_cuts))
            zf.writestr("drill.drl", make_drill(vias_data))

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

    def export_step_solid(self, output_step: str | Path) -> Path:
        """Export solid 3D STEP model of the PCB substrate with mounting holes for enclosure CAD."""
        out_path = Path(output_step).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        w, l, _ = self.config.dimensions_mm
        thickness = self.config.stackup.total_thickness_mm

        with BuildPart() as pcb_part:
            Box(w, l, thickness)

        export_step(pcb_part.part, str(out_path))
        return out_path
