"""Manufacturing artifacts, BOM, Pick-and-Place, and vector schematic exporter for PCBs."""

import csv
import io
import json
import math
import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import jinja2
from build123d import Box, BuildPart, Compound, Part, Solid, export_step
from model.pcb import BoardType, CapacitiveElectrodeModel, PCBConfig, StackupModel
from model.wiring import Wiring, FootprintModel, NetModel
from provider.pcb.capacitive import CapacitiveSensingGenerator
from provider.pcb.silkscreen import find_empty_space_for_label


SCH_PIN_LEN_MM: float = 5.08
SCH_PIN_SPACING_MM: float = 5.08
SCH_BOX_MIN_HALF_H_MM: float = 10.16
SCH_BOX_MIN_HALF_W_MM: float = 15.24


class PCBExporter:
    """Orchestrates generation of manufacturing packages, supplier BOM/CPL, schematics, and 3D STEP models."""

    def __init__(
        self,
        pcb_config: PCBConfig,
        wiring: Optional[Wiring] = None,
        subassembly: Optional[str] = None,
    ):
        """Initialize the exporter with PCB stackup configuration and netlist."""
        self.config = pcb_config
        self.wiring = wiring
        self.subassembly = subassembly or (
            pcb_config.shape_ref if getattr(pcb_config, "board_type", None) == BoardType.FLEX else None
        )
        self.is_flex = (
            (self.subassembly == "flex_tail")
            or (self.config.name == "flex_tail")
            or (getattr(self.config, "board_type", None) == BoardType.FLEX)
        )
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
        existing_net_names = set()
        if self.wiring:
            for idx, n in enumerate(self.wiring.nets, start=1):
                net_name_to_idx[n.name] = idx
                nets.append({"idx": idx, "name": n.name})
                existing_net_names.add(n.name)

        for sensor in getattr(self.config, "capacitive_sensors", []):
            for s_net in (sensor.tx_pin, sensor.rx_pin, "CAP_SHIELD"):
                if s_net and s_net not in existing_net_names:
                    idx = len(nets) + 1
                    net_name_to_idx[s_net] = idx
                    nets.append({"idx": idx, "name": s_net})
                    existing_net_names.add(s_net)

        # Process component footprints and pads (centered on drawing sheet)
        footprints_data = []
        fps_to_process = self.get_footprints_for_board()

        # Collect board perimeter and obstacle circles for silkscreen placement
        w_board, l_board, _ = self.config.dimensions_mm
        board_bounds = (-w_board / 2.0, -l_board / 2.0, w_board / 2.0, l_board / 2.0)
        circ_obstacles: List[Tuple[float, float, float]] = []
        for mh in getattr(self.config, "mounting_holes", []):
            circ_obstacles.append((mh.position_mm[0], mh.position_mm[1], mh.drill_diameter_mm / 2.0))
        for v in getattr(self.config, "vias", []):
            circ_obstacles.append((v.position_mm[0], v.position_mm[1], v.pad_diameter_mm / 2.0))
        for tp_obs in getattr(self.config, "test_points", []):
            circ_obstacles.append((tp_obs.position_mm[0], tp_obs.position_mm[1], tp_obs.pad_diameter_mm / 2.0))
        placed_component_label_boxes: List[Tuple[float, float, float, float]] = []
        for fp_obs in fps_to_process:
            rot_deg = fp_obs.rotation[2] if hasattr(fp_obs, "rotation") and len(fp_obs.rotation) >= 3 else 0.0
            rad = math.radians(rot_deg) if abs(rot_deg) > 1e-4 else 0.0
            cos_r, sin_r = (math.cos(rad), math.sin(rad)) if rad else (1.0, 0.0)
            for p_obs in getattr(fp_obs, "pins", []):
                rx = p_obs.position[0] * cos_r - p_obs.position[1] * sin_r
                ry = p_obs.position[0] * sin_r + p_obs.position[1] * cos_r
                pad_s = getattr(p_obs, "pad_size_mm", (0.5, 0.5))
                circ_obstacles.append((fp_obs.position[0] + rx, fp_obs.position[1] + ry, max(pad_s) / 2.0))

        for fp in fps_to_process:
            fp_pins = []
            for p in fp.pins:
                # Find net connected to this pin
                net_name = ""
                if self.wiring:
                    for net in self.wiring.nets:
                        for comp_name, pin_name in net.pins:
                            if comp_name == fp.name and pin_name == p.name:
                                net_name = net.name
                                break
                        if net_name:
                            break

                net_idx = net_name_to_idx.get(net_name, 0)
                pad_type = getattr(p, "pad_type", None)
                drill_dia = getattr(p, "drill_dia_mm", None)
                pad_size = getattr(p, "pad_size_mm", None)
                pad_shape = getattr(p, "pad_shape", None)

                # Default connectors to through-hole if not otherwise specified
                if fp.name.startswith("J") or "KEY-M" in fp.package.upper() or "FPC" in fp.package.upper():
                    pad_type = pad_type or "thru_hole"
                    drill_dia = drill_dia or 0.70
                    pad_shape = pad_shape or "circle"
                    pad_size = pad_size or (1.2, 1.2)
                else:
                    pkg_upper = fp.package.upper()
                    if "0402" in pkg_upper:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "roundrect"
                        pad_size = pad_size or (0.60, 0.50)
                    elif "0603" in pkg_upper:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "roundrect"
                        pad_size = pad_size or (0.80, 0.80)
                    elif "SOT-23" in pkg_upper or "SOT23" in pkg_upper:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "roundrect"
                        pad_size = pad_size or (0.60, 1.00)
                    elif "QFN" in pkg_upper:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "roundrect"
                        side = getattr(p, "side", None)
                        if side in ("top", "bottom"):
                            pad_size = pad_size or (0.25, 0.60)
                        else:
                            pad_size = pad_size or (0.60, 0.25)
                    elif "BGA" in pkg_upper:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "circle"
                        pad_size = pad_size or (0.35, 0.35)
                    else:
                        pad_type = pad_type or "smd"
                        pad_shape = pad_shape or "circle"
                        pad_size = pad_size or (0.5, 0.5)

                fp_pins.append(
                    {
                        "name": p.name,
                        "x_mm": round(p.position[0], 4),
                        "y_mm": round(p.position[1], 4),
                        "pad_type": pad_type,
                        "pad_shape": pad_shape,
                        "pad_size_x": round(pad_size[0], 4),
                        "pad_size_y": round(pad_size[1], 4),
                        "drill_dia_mm": round(drill_dia, 4) if drill_dia else None,
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
            if hasattr(fp, "pins") and fp.pins:
                pad_max_x = max(abs(p.position[0]) + getattr(p, "pad_size_mm", (0.35, 1.2))[0] / 2.0 for p in fp.pins)
                pad_max_y = max(abs(p.position[1]) + getattr(p, "pad_size_mm", (0.35, 1.2))[1] / 2.0 for p in fp.pins)
                w_half = max(w_half, round(pad_max_x + 0.35, 4))
                h_half = max(h_half, round(pad_max_y + 0.35, 4))
            val_y = round(h_half + 1.2, 4)

            is_round = (
                getattr(fp, "shape", None) == "circle"
                or "PIEZO" in fp.package.upper()
                or "SPK" in fp.name.upper()
                or "SPEAKER" in fp.package.upper()
            )
            radius = round((fp.dimensions[0] / 2.0) if fp.dimensions else 6.0, 4)

            # Find empty space for component reference label
            ref_w = len(fp.name) * 0.7 + 0.4
            ref_h = 1.0 + 0.4
            ref_off_x, ref_off_y = find_empty_space_for_label(
                base_x=fp.position[0],
                base_y=fp.position[1],
                label_w=ref_w,
                label_h=ref_h,
                circular_obstacles=circ_obstacles,
                bounding_boxes=placed_component_label_boxes,
                board_bounds=board_bounds,
                clearance=0.30,
                preferred_direction="north",
                step_multiplier=1.2,
            )
            cand_ref_x = fp.position[0] + ref_off_x
            cand_ref_y = fp.position[1] + ref_off_y
            if fp.name == "J_FLEX":
                cand_ref_x = fp.position[0]
                cand_ref_y = fp.position[1]
            placed_component_label_boxes.append(
                (
                    cand_ref_x - ref_w / 2.0,
                    cand_ref_y - ref_h / 2.0,
                    cand_ref_x + ref_w / 2.0,
                    cand_ref_y + ref_h / 2.0,
                )
            )

            tick_w = round(min(1.0, max(0.2, w_half * 0.4)), 4)
            tick_h = round(min(1.0, max(0.2, h_half * 0.4)), 4)
            alignment_lines = [
                {"x1": -w_half, "y1": -h_half, "x2": round(-w_half + tick_w, 4), "y2": -h_half},
                {"x1": -w_half, "y1": -h_half, "x2": -w_half, "y2": round(-h_half + tick_h, 4)},
                {"x1": w_half, "y1": -h_half, "x2": round(w_half - tick_w, 4), "y2": -h_half},
                {"x1": w_half, "y1": -h_half, "x2": w_half, "y2": round(-h_half + tick_h, 4)},
                {"x1": -w_half, "y1": h_half, "x2": round(-w_half + tick_w, 4), "y2": -h_half},
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

            fp_x = round(self.config.sheet_center_x_mm + fp.position[0], 4)
            fp_y = round(self.config.sheet_center_y_mm + fp.position[1], 4)

            footprints_data.append(
                {
                    "name": fp.name,
                    "package": fp.package,
                    "value": fp.label.text if fp.label else fp.package,
                    "uuid": str(uuid.uuid4()),
                    "x_mm": fp_x,
                    "y_mm": fp_y,
                    "rotation": fp.rotation if hasattr(fp, "rotation") and fp.rotation else None,
                    "layer": fp_layer,
                    "silk_layer": silk_layer,
                    "fab_layer": fab_layer,
                    "paste_layer": paste_layer,
                    "mask_layer": mask_layer,
                    "ref_x": round(ref_off_x, 4),
                    "ref_y": round(ref_off_y, 4),
                    "val_y": val_y,
                    "is_round": is_round,
                    "radius": radius,
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
        if not self.is_flex:
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

        segments_data = []
        vias_data = []
        zones_data = []

        if not self.is_flex:
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

            for v in self.config.vias:
                net_idx = net_name_to_idx.get(v.net, 0)
                l1, l2 = v.layer_start, v.layer_end
                if l1 == "B.Cu" and l2 == "F.Cu":
                    l1, l2 = "F.Cu", "B.Cu"
                vias_data.append(
                    {
                        "x": round(self.config.sheet_center_x_mm + v.position_mm[0], 4),
                        "y": round(self.config.sheet_center_y_mm + v.position_mm[1], 4),
                        "dia": round(v.pad_diameter_mm, 4),
                        "drill": round(v.drill_diameter_mm, 4),
                        "layer1": l1,
                        "layer2": l2,
                        "net_idx": net_idx,
                    }
                )

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

        # Process capacitive sensors (scoped to this board's shape_ref)
        target_shape = getattr(self.config, "shape_ref", None)
        capacitive_sensors = [
            sensor
            for sensor in self.config.capacitive_sensors
            if getattr(sensor, "shape_ref", None) == target_shape
            or (self.is_flex and not getattr(sensor, "shape_ref", None))
        ]
        for idx, sensor in enumerate(capacitive_sensors):
            center = getattr(sensor, "center_mm", None)
            if center is None:
                default_centers = {
                    0: (0.0, -12.0),
                    1: (0.0, -0.5),
                    2: (0.0, 11.0),
                    3: (0.0, 20.5),
                }
                center = default_centers.get(idx, (0.0, 0.0))

            gen = CapacitiveSensingGenerator(sensor, center=center)
            geom = gen.generate()

            tx_net = getattr(sensor, "tx_pin", f"CAP_TX{idx}")
            rx_net = getattr(sensor, "rx_pin", f"CAP_RX{idx}")
            tx_net_idx = net_name_to_idx.get(tx_net, 0)
            rx_net_idx = net_name_to_idx.get(rx_net, 0)
            shield_net_idx = net_name_to_idx.get("CAP_SHIELD", net_name_to_idx.get("GND", 0))

            # Helper to emit polyline fingers/busbars as copper trace segments
            def _poly_to_segments(poly: List[Tuple[float, float]], net_idx: int) -> None:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                dx = max_x - min_x
                dy = max_y - min_y
                if dx >= dy:
                    # Horizontal finger
                    y_mid = (min_y + max_y) / 2.0
                    segments_data.append(
                        {
                            "x1": round(self.config.sheet_center_x_mm + min_x, 4),
                            "y1": round(self.config.sheet_center_y_mm + y_mid, 4),
                            "x2": round(self.config.sheet_center_x_mm + max_x, 4),
                            "y2": round(self.config.sheet_center_y_mm + y_mid, 4),
                            "width": round(max(0.15, dy), 4),
                            "layer": "F.Cu",
                            "net_idx": net_idx,
                        }
                    )
                else:
                    # Vertical busbar
                    x_mid = (min_x + max_x) / 2.0
                    segments_data.append(
                        {
                            "x1": round(self.config.sheet_center_x_mm + x_mid, 4),
                            "y1": round(self.config.sheet_center_y_mm + min_y, 4),
                            "x2": round(self.config.sheet_center_x_mm + x_mid, 4),
                            "y2": round(self.config.sheet_center_y_mm + max_y, 4),
                            "width": round(max(0.15, dx), 4),
                            "layer": "F.Cu",
                            "net_idx": net_idx,
                        }
                    )

            # TX comb fingers / self pad
            for poly in geom.tx_fingers:
                pts = [
                    {
                        "x": round(self.config.sheet_center_x_mm + pt[0], 4),
                        "y": round(self.config.sheet_center_y_mm + pt[1], 4),
                    }
                    for pt in poly
                ]
                active_net_idx = tx_net_idx if sensor.shape == "interdigital" else rx_net_idx
                active_net_name = tx_net if sensor.shape == "interdigital" else rx_net
                zones_data.append(
                    {
                        "net_idx": active_net_idx,
                        "net_name": active_net_name,
                        "layer": "F.Cu",
                        "priority": 2,
                        "clearance_mm": 0.20,
                        "pts": pts,
                    }
                )
                if sensor.shape == "interdigital":
                    _poly_to_segments(poly, active_net_idx)
                else:
                    # Fill self-cap touch pad with solid copper trace strips
                    pad_w, pad_l = sensor.area_mm
                    pad_cx, pad_cy = center
                    y_c = pad_cy - pad_l / 2.0 + 0.15
                    while y_c <= (pad_cy + pad_l / 2.0):
                        segments_data.append(
                            {
                                "x1": round(self.config.sheet_center_x_mm + pad_cx - pad_w / 2.0, 4),
                                "y1": round(self.config.sheet_center_y_mm + y_c, 4),
                                "x2": round(self.config.sheet_center_x_mm + pad_cx + pad_w / 2.0, 4),
                                "y2": round(self.config.sheet_center_y_mm + y_c, 4),
                                "width": 0.25,
                                "layer": "F.Cu",
                                "net_idx": active_net_idx,
                            }
                        )
                        y_c += 0.30

            # RX comb fingers
            for poly in geom.rx_fingers:
                pts = [
                    {
                        "x": round(self.config.sheet_center_x_mm + pt[0], 4),
                        "y": round(self.config.sheet_center_y_mm + pt[1], 4),
                    }
                    for pt in poly
                ]
                zones_data.append(
                    {
                        "net_idx": rx_net_idx,
                        "net_name": rx_net,
                        "layer": "F.Cu",
                        "priority": 2,
                        "clearance_mm": 0.20,
                        "pts": pts,
                    }
                )
                _poly_to_segments(poly, rx_net_idx)

            # Back layer 45-degree cross-hatch ground fill
            for hl in geom.hatch_lines:
                segments_data.append(
                    {
                        "x1": round(self.config.sheet_center_x_mm + hl.start[0], 4),
                        "y1": round(self.config.sheet_center_y_mm + hl.start[1], 4),
                        "x2": round(self.config.sheet_center_x_mm + hl.end[0], 4),
                        "y2": round(self.config.sheet_center_y_mm + hl.end[1], 4),
                        "width": hl.width_mm,
                        "layer": "B.Cu",
                        "net_idx": shield_net_idx,
                    }
                )

        # Test Points (carrier board only)
        test_points_data = []
        if not self.is_flex:
            placed_label_boxes: List[Tuple[float, float, float, float]] = []
            for tp in self.config.test_points:
                net_idx = net_name_to_idx.get(tp.net, 0)
                silk_layer = "B.SilkS" if tp.layer == "B.Cu" else "F.SilkS"
                mask_layer = "B.Mask" if tp.layer == "B.Cu" else "F.Mask"
                preferred = "north" if tp.position_mm[1] >= 0 else "south"
                lbl_w = 0.8
                lbl_h = len(tp.name) * 0.5 + 0.6
                lbl_off_x, lbl_off_y = find_empty_space_for_label(
                    base_x=tp.position_mm[0],
                    base_y=tp.position_mm[1],
                    label_w=lbl_w,
                    label_h=lbl_h,
                    circular_obstacles=circ_obstacles,
                    bounding_boxes=placed_label_boxes,
                    board_bounds=board_bounds,
                    clearance=0.35,
                    preferred_direction=preferred,
                    step_multiplier=1.4,
                )
                cand_x = tp.position_mm[0] + lbl_off_x
                cand_y = tp.position_mm[1] + lbl_off_y
                placed_label_boxes.append(
                    (cand_x - lbl_w / 2.0, cand_y - lbl_h / 2.0, cand_x + lbl_w / 2.0, cand_y + lbl_h / 2.0)
                )
                test_points_data.append(
                    {
                        "name": tp.name,
                        "x_mm": round(self.config.sheet_center_x_mm + tp.position_mm[0], 4),
                        "y_mm": round(self.config.sheet_center_y_mm + tp.position_mm[1], 4),
                        "dia_mm": round(tp.pad_diameter_mm, 4),
                        "drill_mm": round(tp.drill_diameter_mm, 4),
                        "label_x": round(lbl_off_x, 4),
                        "label_y": round(lbl_off_y, 4),
                        "label_angle": 90,
                        "layer": tp.layer,
                        "silk_layer": silk_layer,
                        "mask_layer": mask_layer,
                        "net_idx": net_idx,
                        "net_name": tp.net,
                    }
                )

        poly_segments = []
        if getattr(self.config, "outline_polygon", None):
            poly_pts = [
                (
                    round(self.config.sheet_center_x_mm + pt[0], 4),
                    round(self.config.sheet_center_y_mm + pt[1], 4),
                )
                for pt in self.config.outline_polygon
            ]
            for idx, p1 in enumerate(poly_pts):
                p2 = poly_pts[(idx + 1) % len(poly_pts)]
                poly_segments.append({"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1]})

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
                "corner_radius": round(
                    getattr(self.config, "corner_radius", 0.0) or (6.0 if not self.is_flex else 0.0), 4
                ),
                "polygon_segments": poly_segments,
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

    def get_footprints_for_board(self) -> List[FootprintModel]:
        """Return the list of footprints belonging to this board target (filtering by shape_ref)."""
        fps = list(self.wiring.footprints) if self.wiring else []
        target_ref = getattr(self.config, "shape_ref", None)
        if target_ref:
            return [
                fp
                for fp in fps
                if getattr(fp, "shape_ref", None) == target_ref
                or (not getattr(fp, "shape_ref", None) and not self.is_flex)
            ]
        return fps

    def export_bom_csv(self, output_file: str | Path) -> Path:
        """Export Bill of Materials (BOM) in CSV format for component procurement and assembly."""
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
        fps_to_process = self.get_footprints_for_board()
        for idx, fp in enumerate(fps_to_process, start=1):
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
        fps_to_process = self.get_footprints_for_board()
        for fp in fps_to_process:
            mid_x = fp.position[0]
            mid_y = fp.position[1]
            rows.append(
                {
                    "Designator": fp.name,
                    "Val": fp.label.text if fp.label else fp.package,
                    "Package": fp.package,
                    "Mid X": f"{mid_x:.4f}mm",
                    "Mid Y": f"{mid_y:.4f}mm",
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
        fps_to_process = self.get_footprints_for_board()
        for idx, fp in enumerate(fps_to_process, start=1):
            x = fp.position[0]
            y = fp.position[1]
            components_data.append(
                {
                    "ref": fp.name,
                    "val": fp.label.text if fp.label else fp.package,
                    "package": fp.package,
                    "mpn": fp.mpn or "N/A",
                    "supplier_pn": fp.supplier_pn or "N/A",
                    "x": x,
                    "y": y,
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
