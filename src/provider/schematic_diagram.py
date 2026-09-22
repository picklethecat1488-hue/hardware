"""Dedicated vector schematic diagram and multi-page PDF generator for electronic components and nets."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import matplotlib.patches as patches

from model.pcb import PCBConfig, SchematicLayoutModel
from model.wiring import FootprintModel, NetModel, Wiring, TruthTableModel, TruthTableRowModel, PinModel


@dataclass
class _SchematicSheetPlan:
    """Planned contents and metadata for an individual schematic drawing sheet."""

    sheet_idx: int
    title: str
    description: str = ""
    footprints: List[FootprintModel] = field(default_factory=list)


@dataclass
class _TOCPagePlan:
    """Planned contents for a single paginated Table of Contents sheet."""

    page_index: int
    doc_entries: List[Tuple[str, str]] = field(default_factory=list)
    show_footprints_header: bool = False
    is_footprints_continuation: bool = False
    footprints: List[Tuple[int, FootprintModel, str]] = field(default_factory=list)
    show_nets_header: bool = False
    is_nets_continuation: bool = False
    net_rows: List[List[NetModel]] = field(default_factory=list)


POWER_NET_NAMES = {"3V3", "5V", "1V8", "1V2", "VCC", "VDD", "VLOAD_SW", "VBUS"}
GROUND_NET_NAMES = {"GND", "GROUND", "VSS"}
JUMPER_BRIDGE_RADIUS_MM = 1.2
PIN_PITCH_MM = 5.0
PIN_NUMBER_OFFSET_MM = 2.5
STUB_SIGNAL_MM = 5.0
STUB_POWER_MM = 10.0
STUB_GROUND_MM = 18.0


class SchematicDiagram:
    """Generates standard electronic schematic vector diagrams (SVG) from wiring and PCB configs."""

    def __init__(self, wiring: Wiring, pcb_config: Optional[PCBConfig] = None):
        """Initialize schematic diagram generator with wiring netlist and optional PCB config."""
        self.wiring = wiring
        self.config = pcb_config

    def render_svg(self, output_file: str | Path) -> Path:
        """Generate a clean, high-resolution vector SVG schematic diagram."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        board_name = self.config.name if self.config else "Schematic"
        layer_count = self.config.stackup.copper_layer_count if self.config else 2
        board_type = self.config.board_type.upper() if self.config else "RIGID"

        # Arrange components in schematic grid
        comp_spacing_x = 240.0
        start_x = 60.0
        start_y = 120.0

        # Calculate dynamic bounding dimensions
        fps = self.wiring.footprints
        svg_w = max(900, int(start_x + len(fps) * comp_spacing_x + 60.0))
        max_pins = max((len(fp.pins) for fp in fps), default=2)
        half_pins = max(2, (max_pins + 1) // 2)
        max_bh = max(100.0, half_pins * 28.0 + 80.0)
        svg_h = max(700, int(start_y + 100.0 + max_bh + 60.0))

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">',
            '  <rect width="100%" height="100%" fill="#ffffff"/>',
            "  <defs>",
            '    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">',
            '      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f1f5f9" stroke-width="0.5"/>',
            "    </pattern>",
            "  </defs>",
            '  <rect width="100%" height="100%" fill="url(#grid)"/>',
            f'  <text x="30" y="40" font-family="system-ui, sans-serif" font-size="20" font-weight="bold" fill="#0f172a">{board_name} Schematic</text>',
            f'  <text x="30" y="65" font-family="system-ui, sans-serif" font-size="12" fill="#64748b">Layer Count: {layer_count} | Type: {board_type} | Components: {len(fps)}</text>',
        ]

        pin_coords = {}  # (comp_name, pin_name) -> (x, y)

        for col_idx, fp in enumerate(fps):
            cx = start_x + (col_idx * comp_spacing_x)
            cy = start_y + 100.0
            bw = 180.0
            pin_count = max(len(fp.pins), 2)
            bh = max(100.0, pin_count * 28.0 + 40.0)

            # Draw IC symbol body
            svg_lines.append(
                f'  <rect x="{cx:.1f}" y="{cy:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'rx="6" fill="#f8fafc" stroke="#334155" stroke-width="2"/>'
            )
            # Component reference designator and value/label
            ref = fp.name
            val = fp.label.text if fp.label else fp.package
            mpn = getattr(fp, "mpn", None)
            svg_lines.append(
                f'  <text x="{cx + bw / 2.0:.1f}" y="{cy + 20:.1f}" font-family="system-ui, sans-serif" '
                f'font-size="13" font-weight="bold" text-anchor="middle" fill="#0f172a">{ref}</text>'
            )
            if mpn and mpn != val:
                svg_lines.append(
                    f'  <text x="{cx + bw / 2.0:.1f}" y="{cy + 34:.1f}" font-family="system-ui, sans-serif" '
                    f'font-size="10" font-weight="bold" text-anchor="middle" fill="#0369a1">{mpn}</text>'
                )
                svg_lines.append(
                    f'  <text x="{cx + bw / 2.0:.1f}" y="{cy + 47:.1f}" font-family="system-ui, sans-serif" '
                    f'font-size="9" text-anchor="middle" fill="#64748b">{val}</text>'
                )
            else:
                svg_lines.append(
                    f'  <text x="{cx + bw / 2.0:.1f}" y="{cy + 38:.1f}" font-family="system-ui, sans-serif" '
                    f'font-size="10" text-anchor="middle" fill="#64748b">{val}</text>'
                )

            # Draw pins
            left_pins = [p for p in fp.pins if p.side.value in ("left", "bottom")]
            right_pins = [p for p in fp.pins if p.side.value in ("right", "top")]
            if not left_pins and not right_pins:
                left_pins = fp.pins[: len(fp.pins) // 2]
                right_pins = fp.pins[len(fp.pins) // 2 :]

            for p_idx, p in enumerate(left_pins):
                py = cy + 60.0 + (p_idx * 24.0)
                # Pin stub line
                svg_lines.append(
                    f'  <line x1="{cx - 15:.1f}" y1="{py:.1f}" x2="{cx:.1f}" y2="{py:.1f}" stroke="#475569" stroke-width="1.5"/>'
                )
                svg_lines.append(f'  <circle cx="{cx - 15:.1f}" cy="{py:.1f}" r="3" fill="#0284c7"/>')
                svg_lines.append(
                    f'  <text x="{cx + 8:.1f}" y="{py + 4:.1f}" font-family="system-ui, sans-serif" font-size="9" fill="#1e293b">{p.name}</text>'
                )
                pin_coords[(fp.name, p.name)] = (cx - 15, py)

            for p_idx, p in enumerate(right_pins):
                py = cy + 60.0 + (p_idx * 24.0)
                # Pin stub line
                svg_lines.append(
                    f'  <line x1="{cx + bw:.1f}" y1="{py:.1f}" x2="{cx + bw + 15:.1f}" y2="{py:.1f}" stroke="#475569" stroke-width="1.5"/>'
                )
                svg_lines.append(f'  <circle cx="{cx + bw + 15:.1f}" cy="{py:.1f}" r="3" fill="#0284c7"/>')
                svg_lines.append(
                    f'  <text x="{cx + bw - 8:.1f}" y="{py + 4:.1f}" font-family="system-ui, sans-serif" font-size="9" text-anchor="end" fill="#1e293b">{p.name}</text>'
                )
                pin_coords[(fp.name, p.name)] = (cx + bw + 15, py)

        # Draw net connection wires
        for net in self.wiring.nets:
            color = net.color if hasattr(net, "color") and net.color else "#2563eb"
            points = [pin_coords[pair] for pair in net.pins if pair in pin_coords]
            if len(points) >= 2:
                for i in range(len(points) - 1):
                    p1, p2 = points[i], points[i + 1]
                    # Orthogonal routing via midpoint
                    mid_x = (p1[0] + p2[0]) / 2.0
                    svg_lines.append(
                        f'  <polyline points="{p1[0]:.1f},{p1[1]:.1f} {mid_x:.1f},{p1[1]:.1f} {mid_x:.1f},{p2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" '
                        f'fill="none" stroke="{color}" stroke-width="1.5"/>'
                    )

        svg_lines.append("</svg>")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(svg_lines))

        return out_path

    def _build_sheet_plans(self) -> List[_SchematicSheetPlan]:
        """Build the sequence of schematic sheet plans either from declarative config or auto-chunking."""
        fps = self.wiring.footprints
        if self.config and self.config.schematic_sheets:
            fp_map = {fp.name: fp for fp in fps}
            plans: List[_SchematicSheetPlan] = []
            for s_idx, sheet_def in enumerate(self.config.schematic_sheets, start=1):
                sheet_fps: List[FootprintModel] = []
                for comp_name in sheet_def.components:
                    if comp_name in fp_map:
                        orig_fp = fp_map[comp_name]
                        if sheet_def.pin_breakouts and comp_name in sheet_def.pin_breakouts:
                            pin_order_list = sheet_def.pin_breakouts[comp_name]
                            pin_order_map = {name: idx for idx, name in enumerate(pin_order_list)}
                            allowed_pins = set(pin_order_map.keys())
                            matched_pins = [
                                p for p in orig_fp.pins if p.name in allowed_pins or p.label in allowed_pins
                            ]
                            filtered_pins = sorted(
                                matched_pins,
                                key=lambda p: pin_order_map.get(p.name, pin_order_map.get(p.label, 999)),
                            )
                            sheet_fps.append(orig_fp.model_copy(update={"pins": filtered_pins}))
                        else:
                            sheet_fps.append(orig_fp)
                plans.append(
                    _SchematicSheetPlan(
                        sheet_idx=s_idx,
                        title=sheet_def.title,
                        description=sheet_def.description,
                        footprints=sheet_fps,
                    )
                )
            return plans

        # Auto-chunking fallback (up to 2 components per sheet)
        chunk_size = 2 if len(fps) > 2 else len(fps)
        fp_chunks = [fps[i : i + chunk_size] for i in range(0, len(fps), max(1, chunk_size))]
        return [
            _SchematicSheetPlan(
                sheet_idx=s_idx,
                title=f"Schematic Sheet {s_idx}",
                description=", ".join(f"{c.name} ({c.package})" for c in chunk),
                footprints=chunk,
            )
            for s_idx, chunk in enumerate(fp_chunks, start=1)
        ]

    def compute_symbol_bounding_boxes(
        self,
    ) -> Dict[int, List[Tuple[float, float, float, float, str]]]:
        """Compute exact bounding boxes (cx, cy, width, height, name) for all symbols on each sheet.

        Returns:
            Dictionary mapping sheet_idx (1-indexed) to list of (cx, cy, width, height, name) bounding boxes.
        """
        if not self.wiring or not getattr(self.wiring, "footprints", None):
            return {}

        sheet_plans = self._build_sheet_plans()
        if not sheet_plans:
            return {}

        all_nets = getattr(self.wiring, "nets", []) or []
        pin_to_net: Dict[Tuple[str, str], str] = {}
        for net in all_nets:
            for pair in net.pins:
                pin_to_net[pair] = net.name

        sheet_boxes: Dict[int, List[Tuple[float, float, float, float, str]]] = {}

        for plan in sheet_plans:
            sheet_fps = plan.footprints
            boxes: List[Tuple[float, float, float, float, str]] = []

            decoupling_caps = [fp for fp in sheet_fps if self._is_decoupling_cap(fp, pin_to_net)]
            pullup_resistors = [fp for fp in sheet_fps if self._is_pull_resistor(fp, pin_to_net, sheet_fps)]
            shunt_caps = [fp for fp in sheet_fps if self._is_shunt_cap(fp, pin_to_net, sheet_fps)]
            passive_names = {fp.name for fp in decoupling_caps + pullup_resistors + shunt_caps}

            if passive_names and (len(passive_names) < len(sheet_fps)):
                main_fps = [fp for fp in sheet_fps if fp.name not in passive_names]
            else:
                decoupling_caps = []
                pullup_resistors = []
                shunt_caps = []
                main_fps = sheet_fps

            num_comps = len(main_fps)
            has_bottom_cards = bool(decoupling_caps) or any(
                getattr(fp, "truth_table", None) is not None or fp.name.upper().startswith("Q") for fp in sheet_fps
            )

            sheet_model = (
                self.config.schematic_sheets[plan.sheet_idx - 1]
                if (
                    self.config
                    and self.config.schematic_sheets
                    and (0 <= (plan.sheet_idx - 1) < len(self.config.schematic_sheets))
                )
                else None
            )
            layout = (
                getattr(sheet_model, "layout", None)
                or getattr(self.config, "schematic_layout", None)
                or SchematicLayoutModel()
            )
            page_center_x = layout.sheet_center_x
            top_row_y = 158.0 if has_bottom_cards else 138.0

            cols_override = getattr(layout, "cols_per_row", None)
            grid_positions = getattr(layout, "grid_positions", {}) or {}

            if cols_override is not None:
                cols_per_row = cols_override
                col_w = 210.0 / max(1, cols_per_row)
                cw = min(38.0, col_w * 0.55)
                gap = (210.0 - (cols_per_row * cw)) / max(1, cols_per_row - 1) if cols_per_row > 1 else 0.0
                start_x = 45.0
                col_x_positions = []
                col_y_positions = []
                comp_col_map = {}
                for i, fp in enumerate(main_fps):
                    if fp.name in grid_positions:
                        r_idx, c_idx_col = grid_positions[fp.name]
                    else:
                        r_idx = i // cols_per_row
                        c_idx_col = i % cols_per_row
                    comp_col_map[fp.name] = c_idx_col
                    col_x_positions.append(start_x + c_idx_col * (cw + gap))
                    col_y_positions.append(top_row_y - (r_idx * layout.row_step_y))
            elif num_comps == 1:
                cw = 38.0
                col_x_positions = [page_center_x - cw / 2.0]
                col_y_positions = [top_row_y]
                comp_col_map = {main_fps[0].name: 0}
            elif num_comps == 2:
                cw = 38.0
                gap = 55.0
                total_w = 2 * cw + gap
                start_x = page_center_x - total_w / 2.0
                col_x_positions = [start_x, start_x + cw + gap]
                col_y_positions = [top_row_y, top_row_y]
                comp_col_map = {main_fps[0].name: 0, main_fps[1].name: 1}
            elif num_comps == 3:
                cw = 36.0
                gap = getattr(layout, "col_gap", 50.0) if getattr(layout, "col_gap", 15.0) != 15.0 else 50.0
                total_w = 3 * cw + 2 * gap
                start_x = max(40.0, page_center_x - total_w / 2.0)
                col_x_positions = [start_x, start_x + cw + gap, start_x + 2 * (cw + gap)]
                col_y_positions = [top_row_y, top_row_y, top_row_y]
                comp_col_map = {fp.name: idx for idx, fp in enumerate(main_fps)}
            else:
                cols_per_row = (num_comps + 1) // 2
                col_w = 210.0 / max(1, cols_per_row)
                cw = min(36.0, col_w * 0.55)
                col_x_positions = []
                col_y_positions = []
                comp_col_map = {}
                for i, fp in enumerate(main_fps):
                    r_idx = i // cols_per_row
                    c_idx_col = i % cols_per_row
                    comp_col_map[fp.name] = c_idx_col
                    col_x_positions.append(45.0 + c_idx_col * col_w + (col_w - cw) / 2.0)
                    col_y_positions.append(top_row_y - (r_idx * layout.row_step_y))

            sheet_pin_sides = getattr(sheet_model, "pin_sides", {}) or {}
            pin_side_map: Dict[Tuple[str, str], str] = {}
            for fp in main_fps:
                comp_side_overrides = sheet_pin_sides.get(fp.name, {})
                left_p, right_p = [], []
                for p in fp.pins:
                    side_val = comp_side_overrides.get(p.name, p.side.value if hasattr(p, "side") else "left")
                    if side_val in ("right", "top"):
                        right_p.append(p)
                    else:
                        left_p.append(p)
                if not left_p and not right_p:
                    left_p = fp.pins[: len(fp.pins) // 2]
                    right_p = fp.pins[len(fp.pins) // 2 :]
                for p in left_p:
                    pin_side_map[(fp.name, p.name)] = "left"
                for p in right_p:
                    pin_side_map[(fp.name, p.name)] = "right"

            direct_wire_pairs = []
            wired_pins = set()
            for net in all_nets:
                present_pins = [pair for pair in net.pins if pair in pin_side_map]
                if len(present_pins) >= 2:
                    for i, pair1 in enumerate(present_pins):
                        for pair2 in present_pins[i + 1 :]:
                            if pair1 in wired_pins or pair2 in wired_pins:
                                continue
                            c1, c2 = comp_col_map[pair1[0]], comp_col_map[pair2[0]]
                            s1, s2 = pin_side_map[pair1], pin_side_map[pair2]
                            if c1 > c2:
                                pair1, pair2 = pair2, pair1
                                c1, c2 = c2, c1
                                s1, s2 = s2, s1
                            if (c2 == c1 + 1) and s1 == "right" and s2 == "left":
                                direct_wire_pairs.append((pair1, pair2, net))
                                wired_pins.add(pair1)
                                wired_pins.add(pair2)

            sheet_pin_coords = {}
            for c_idx, fp in enumerate(main_fps):
                cx = col_x_positions[c_idx]
                row_top_y = col_y_positions[c_idx]
                comp_side_overrides = sheet_pin_sides.get(fp.name, {})
                left_pins = [
                    p
                    for p in fp.pins
                    if comp_side_overrides.get(p.name, p.side.value if hasattr(p, "side") else "left")
                    in ("left", "bottom")
                ]
                right_pins = [
                    p
                    for p in fp.pins
                    if comp_side_overrides.get(p.name, p.side.value if hasattr(p, "side") else "right")
                    in ("right", "top")
                ]
                if not left_pins and not right_pins:
                    left_pins = fp.pins[: len(fp.pins) // 2]
                    right_pins = fp.pins[len(fp.pins) // 2 :]

                header_offset = 18.0 if getattr(fp, "mpn", None) else 15.0
                max_pin_rows = max(len(left_pins), len(right_pins), 2)
                ch = max(34.0, header_offset + (max_pin_rows - 1) * PIN_PITCH_MM + 6.0)
                cy = row_top_y - ch
                boxes.append((cx + cw / 2.0, cy + ch / 2.0, cw, ch, fp.name))

                for p_idx, p in enumerate(left_pins):
                    net_u = pin_to_net.get((fp.name, p.name), "").upper()
                    stub = (
                        STUB_POWER_MM
                        if net_u in POWER_NET_NAMES
                        else (STUB_GROUND_MM if net_u in GROUND_NET_NAMES else STUB_SIGNAL_MM)
                    )
                    sheet_pin_coords[(fp.name, p.name)] = (cx - stub, cy + ch - header_offset - p_idx * PIN_PITCH_MM)
                for p_idx, p in enumerate(right_pins):
                    net_u = pin_to_net.get((fp.name, p.name), "").upper()
                    stub = (
                        STUB_POWER_MM
                        if net_u in POWER_NET_NAMES
                        else (STUB_GROUND_MM if net_u in GROUND_NET_NAMES else STUB_SIGNAL_MM)
                    )
                    sheet_pin_coords[(fp.name, p.name)] = (
                        cx + cw + stub,
                        cy + ch - header_offset - p_idx * PIN_PITCH_MM,
                    )

            if decoupling_caps:
                base_y = 35.0
                pitch_x = 28.0
                total_w = (len(decoupling_caps) - 1) * pitch_x
                start_x = max(35.0, page_center_x - total_w / 2.0)
                for idx, cap in enumerate(decoupling_caps):
                    boxes.append((start_x + idx * pitch_x, base_y, 14.0, 24.0, cap.name))

            h_segments = []
            trans_map = {}
            for pair1, pair2, net in direct_wire_pairs:
                trans_map.setdefault((pair1[0], pair2[0]), []).append((pair1, pair2, net))

            for (c1, c2), pairs in trans_map.items():
                has_pullups_in_channel = any(
                    any(p[2].name == pin_to_net.get((fp.name, pin.name)) for pin in fp.pins for p in pairs)
                    for fp in pullup_resistors
                )
                dogleg_idx = 0
                for pair1, pair2, net in pairs:
                    p1 = sheet_pin_coords[pair1]
                    p2 = sheet_pin_coords[pair2]
                    col = net.color if hasattr(net, "color") and net.color else "#2563eb"
                    if abs(p1[1] - p2[1]) < 0.1:
                        h_segments.append((p1[0], p2[0], p1[1], net.name, col))
                    else:
                        if has_pullups_in_channel:
                            x_v = (p2[0] - 14.0) + dogleg_idx * 2.0
                        else:
                            num_doglegs = len(
                                [p for p in pairs if abs(sheet_pin_coords[p[0]][1] - sheet_pin_coords[p[1]][1]) >= 0.1]
                            )
                            mid_base = (p1[0] + p2[0]) / 2.0
                            offset = (dogleg_idx - (num_doglegs - 1) / 2.0) * 8.0 if num_doglegs > 1 else 0.0
                            x_v = mid_base + offset
                        dogleg_idx += 1
                        h_segments.append((p1[0], x_v, p1[1], net.name, col))
                        h_segments.append((x_v, p2[0], p2[1], net.name, col))

            vertical_passives = pullup_resistors + shunt_caps
            if vertical_passives:
                channel_map = {}
                for fp in vertical_passives:
                    n1 = pin_to_net.get((fp.name, fp.pins[0].name), "")
                    n2 = pin_to_net.get((fp.name, fp.pins[1].name), "")
                    sig = n2 if (n1.upper() in POWER_NET_NAMES or n1.upper() in GROUND_NET_NAMES) else n1
                    segs = [s for s in h_segments if s[3] == sig]
                    if segs:
                        xs = min(min(s[0], s[1]) for s in segs)
                        xe = max(max(s[0], s[1]) for s in segs)
                        if xe - xs >= 18.0:
                            channel_map.setdefault((round(xs, 1), round(xe, 1)), []).append(fp)

                p_pts = []
                for idx, fp in enumerate(vertical_passives):
                    n1 = pin_to_net.get((fp.name, fp.pins[0].name), "")
                    n2 = pin_to_net.get((fp.name, fp.pins[1].name), "")
                    if n1.upper() in POWER_NET_NAMES or n1.upper() in GROUND_NET_NAMES:
                        rail_net = n1
                        sig_net = n2
                    else:
                        rail_net = n2
                        sig_net = n1

                    matching_segs = [s for s in h_segments if s[3] == sig_net]
                    if matching_segs:
                        x_start = min(min(s[0], s[1]) for s in matching_segs)
                        x_end = max(max(s[0], s[1]) for s in matching_segs)
                        seg_len = x_end - x_start
                        if seg_len >= 18.0:
                            chan_fps = channel_map.get((round(x_start, 1), round(x_end, 1)), [fp])
                            n_chan = max(1, len(chan_fps))
                            chan_idx = chan_fps.index(fp) if fp in chan_fps else (idx % n_chan)
                            safe_min = x_start + 6.0
                            safe_max = x_end - 10.0
                            pitch = 14.0
                            total_span = (n_chan - 1) * pitch
                            if safe_max - safe_min >= total_span:
                                mid_x = (safe_min + safe_max) / 2.0
                                cand_x = (mid_x - total_span / 2.0) + chan_idx * pitch
                            else:
                                step = (safe_max - safe_min) / max(1, n_chan - 1) if n_chan > 1 else 0.0
                                cand_x = safe_min + chan_idx * step
                        elif x_start < 100.0:
                            cand_x = max(22.0, x_start - 24.0 - idx * 16.0)
                        else:
                            cand_x = min(275.0, x_end + 14.0 + idx * 16.0)
                        x_pull = cand_x
                        y_base = matching_segs[0][2]
                    else:
                        target_pair = next(
                            (
                                p
                                for p, c in sheet_pin_coords.items()
                                if pin_to_net.get(p) == sig_net and p[0] != fp.name
                            ),
                            None,
                        )
                        if target_pair:
                            p_x, p_y = sheet_pin_coords[target_pair]
                            y_base = p_y
                            cand_x = p_x + 14.0 + idx * 16.0 if p_x >= 148.5 else max(22.0, p_x - 24.0 - idx * 16.0)
                            x_pull = cand_x
                        else:
                            x_pull = page_center_x + idx * 14.0
                            y_base = 120.0
                    p_pts.append((x_pull, y_base, fp, sig_net, rail_net))

                pwr_pts = [p for p in p_pts if p[4].upper() in POWER_NET_NAMES]
                pullup_max_y = max((p[1] for p in pwr_pts), default=120.0)
                for x_pull, y_base, fp, sig_net, rail_net in p_pts:
                    is_pullup = rail_net.upper() in POWER_NET_NAMES
                    if is_pullup:
                        y_zz_bot = pullup_max_y + 8.0
                        boxes.append((x_pull + 4.0, y_zz_bot + 6.5, 12.0, 14.0, fp.name))
                    else:
                        y_zz_top = y_base - 8.0
                        y_zz_bot = y_zz_top - 9.0
                        boxes.append((x_pull + 4.0, y_zz_bot + 6.5, 12.0, 14.0, fp.name))

            sheet_boxes[plan.sheet_idx] = boxes

        return sheet_boxes

    def render_pdf(self, output_file: str | Path) -> Path:
        """Generate a multi-page PDF schematic including Title page, TOC, and schematic sheets.

        Args:
            output_file: Target file path for the exported PDF.

        Returns:
            Resolved Path of the generated PDF document.
        """
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        board_name = self.config.name if self.config else "Schematic"
        layer_count = self.config.stackup.copper_layer_count if self.config else 2
        board_type = self.config.board_type.upper() if self.config else "RIGID"

        fps = self.wiring.footprints
        sheet_plans = self._build_sheet_plans()
        total_sheets = max(1, len(sheet_plans))

        # Plan multi-page Table of Contents sheets dynamically
        toc_plans = self._plan_pdf_toc_pages(fps, self.wiring.nets, sheet_plans)
        toc_page_count = len(toc_plans)
        total_pages = 1 + toc_page_count + total_sheets

        with PdfPages(out_path) as pdf:
            # Page 1: Title Cover Page
            self._render_pdf_title_page(pdf, board_name, board_type, layer_count, fps, self.wiring.nets, total_pages)

            # Pages 2 .. 1 + toc_page_count: Table of Contents & Interconnect Schedule
            for toc_plan in toc_plans:
                self._render_pdf_toc_page(
                    pdf=pdf,
                    board_name=board_name,
                    board_type=board_type,
                    layer_count=layer_count,
                    plan=toc_plan,
                    total_toc_pages=toc_page_count,
                    total_pages=total_pages,
                )

            # Pages (1 + toc_page_count + 1) .. total_pages: Schematic Drawing Sheets
            for sheet_idx, plan in enumerate(sheet_plans, start=1):
                self._render_pdf_schematic_sheet(
                    pdf=pdf,
                    board_name=board_name,
                    sheet_plan=plan,
                    total_sheets=total_sheets,
                    all_nets=self.wiring.nets,
                    page_num=1 + toc_page_count + sheet_idx,
                    total_pages=total_pages,
                )

        return out_path

    def _render_pdf_title_page(
        self,
        pdf: PdfPages,
        board_name: str,
        board_type: str,
        layer_count: int,
        fps: List[FootprintModel],
        nets: List[NetModel],
        total_pages: int,
    ) -> None:
        """Render Title Cover Page with project metadata and engineering border."""
        fig = Figure(figsize=(11.693, 8.268), dpi=300)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 297)
        ax.set_ylim(0, 210)
        ax.axis("off")

        # Double outer engineering border
        ax.add_patch(patches.Rectangle((10, 10), 277, 190, fill=False, edgecolor="#1e293b", linewidth=2.0))
        ax.add_patch(patches.Rectangle((12, 12), 273, 186, fill=False, edgecolor="#94a3b8", linewidth=0.8))

        # Title & Subtitle
        ax.text(
            148.5,
            145,
            f"{board_name.upper()} SCHEMATIC",
            ha="center",
            va="center",
            fontsize=24,
            fontweight="bold",
            color="#0f172a",
        )
        ax.text(
            148.5,
            132,
            "Hardware Schematic & Interconnect Architecture Specification",
            ha="center",
            va="center",
            fontsize=12,
            color="#475569",
        )
        ax.plot([45, 252], [122, 122], color="#0284c7", linewidth=2.5)

        # Specifications & Metadata Card
        ax.add_patch(
            patches.Rectangle((60, 48), 177, 60, facecolor="#f8fafc", edgecolor="#cbd5e1", linewidth=1.2, zorder=1)
        )

        doc_id = f"SCH-{board_name.upper().replace(' ', '-')}-001"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        ax.text(72, 96, f"Document ID: {doc_id}", fontsize=10, fontweight="bold", color="#0f172a")
        ax.text(72, 84, f"Project: {board_name}", fontsize=9.5, color="#334155")
        ax.text(72, 72, f"Board Technology: {board_type} PCB", fontsize=9.5, color="#334155")
        ax.text(72, 60, f"Layer Stackup: {layer_count} Copper Layers", fontsize=9.5, color="#334155")

        ax.text(168, 96, "Classification: ENGINEERING SPEC", fontsize=9, fontweight="bold", color="#0369a1")
        ax.text(168, 84, "Status: RELEASED", fontsize=9.5, fontweight="bold", color="#16a34a")
        board_rev = self.config.revision if self.config and self.config.revision else "1.0"
        ax.text(168, 60, f"Date: {date_str} | Rev: {board_rev}", fontsize=9.5, color="#334155")

        # Footer
        ax.text(148.5, 20, f"Page 1 of {total_pages}", ha="center", fontsize=9, color="#64748b")
        pdf.savefig(fig)

    def _plan_pdf_toc_pages(
        self,
        fps: List[FootprintModel],
        nets: List[NetModel],
        sheet_plans: List[_SchematicSheetPlan],
    ) -> List["_TOCPagePlan"]:
        """Plan and paginate the Table of Contents across one or more drawing sheets."""
        y_start = 166.0
        y_min = 25.0
        doc_header_h = 9.0
        doc_row_h = 7.0
        fp_header_h = 10.0
        fp_table_header_h = 6.5
        fp_row_h = 5.5
        nets_header_h = 10.0
        nets_row_h = 5.0
        section_gap = 5.0

        doc_entries: List[Tuple[str, str]] = [
            ("Page 1", "Document Cover & Engineering Specifications"),
            ("Page 2", "Table of Contents, Bill of Footprints & Netlist Summary"),
        ]
        for sp in sheet_plans:
            desc = f"Schematic Sheet {sp.sheet_idx} - {sp.title}"
            if sp.description:
                desc += f" ({sp.description})"
            doc_entries.append(("Page ?", desc))

        pages: List[_TOCPagePlan] = [_TOCPagePlan(page_index=1)]
        y = y_start

        # Section 1: Document Structure
        y -= doc_header_h
        for entry in doc_entries:
            if y - doc_row_h < y_min:
                pages.append(_TOCPagePlan(page_index=len(pages) + 1))
                y = y_start
            pages[-1].doc_entries.append(entry)
            y -= doc_row_h

        # Section 2: Footprint Schedule Table
        if fps:
            y -= section_gap
            min_fp_space = fp_header_h + fp_table_header_h + fp_row_h
            if y - min_fp_space < y_min:
                pages.append(_TOCPagePlan(page_index=len(pages) + 1))
                y = y_start

            pages[-1].show_footprints_header = True
            y -= fp_header_h + fp_table_header_h

            for idx, fp in enumerate(fps):
                matching_sheets = [
                    str(sp.sheet_idx) for sp in sheet_plans if any(f.name == fp.name for f in sp.footprints)
                ]
                sheet_str = ", ".join(matching_sheets) if matching_sheets else "1"
                if y - fp_row_h < y_min:
                    pages.append(_TOCPagePlan(page_index=len(pages) + 1))
                    y = y_start
                    pages[-1].is_footprints_continuation = True
                    y -= fp_table_header_h
                pages[-1].footprints.append((idx, fp, sheet_str))
                y -= fp_row_h

        # Section 3: Primary Signal Nets Summary
        if nets:
            y -= section_gap
            net_chunks = [nets[i : i + 4] for i in range(0, len(nets), 4)]
            min_nets_space = nets_header_h + nets_row_h
            if y - min_nets_space < y_min:
                pages.append(_TOCPagePlan(page_index=len(pages) + 1))
                y = y_start

            pages[-1].show_nets_header = True
            y -= nets_header_h

            for row in net_chunks:
                if y - nets_row_h < y_min:
                    pages.append(_TOCPagePlan(page_index=len(pages) + 1))
                    y = y_start
                    pages[-1].is_nets_continuation = True
                pages[-1].net_rows.append(row)
                y -= nets_row_h

        # Update sheet page references once total TOC pages is known
        toc_page_count = len(pages)
        toc_desc_page = "Page 2" if toc_page_count == 1 else f"Pages 2–{1 + toc_page_count}"
        for p in pages:
            updated = []
            for page_label, desc in p.doc_entries:
                if page_label == "Page 1":
                    updated.append((page_label, desc))
                elif page_label == "Page 2":
                    updated.append((toc_desc_page, desc))
                elif page_label == "Page ?":
                    parts = desc.split()
                    s_idx = int(parts[2])
                    real_page = 1 + toc_page_count + s_idx
                    updated.append((f"Page {real_page}", desc))
                else:
                    updated.append((page_label, desc))
            p.doc_entries = updated

        return pages

    def _render_pdf_toc_page(
        self,
        pdf: PdfPages,
        board_name: str,
        board_type: str,
        layer_count: int,
        plan: "_TOCPagePlan",
        total_toc_pages: int,
        total_pages: int,
    ) -> None:
        """Render a single paginated Table of Contents and Interconnect Bill of Materials sheet."""
        fig = Figure(figsize=(11.693, 8.268), dpi=300)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 297)
        ax.set_ylim(0, 210)
        ax.axis("off")

        # Double outer engineering border
        ax.add_patch(patches.Rectangle((10, 10), 277, 190, fill=False, edgecolor="#1e293b", linewidth=2.0))
        ax.add_patch(patches.Rectangle((12, 12), 273, 186, fill=False, edgecolor="#94a3b8", linewidth=0.8))

        # Header
        if plan.page_index == 1 and total_toc_pages == 1:
            title = "TABLE OF CONTENTS & SYSTEM OVERVIEW"
        elif plan.page_index == 1:
            title = f"TABLE OF CONTENTS & SYSTEM OVERVIEW (PAGE 1 OF {total_toc_pages})"
        else:
            title = f"TABLE OF CONTENTS & INTERCONNECT SCHEDULE (PAGE {plan.page_index} OF {total_toc_pages})"

        board_rev = self.config.revision if self.config and self.config.revision else "1.0"
        ax.text(
            20,
            180,
            f"{board_name} | {board_type} | {layer_count}-Layer Stackup | Rev: {board_rev}",
            fontsize=10,
            color="#475569",
        )
        ax.plot([20, 277], [175, 175], color="#0284c7", linewidth=1.5)

        y = 166.0

        # Section 1: Document Structure
        if plan.doc_entries:
            ax.text(20, y, "1. Document Structure", fontsize=11, fontweight="bold", color="#1e293b")
            y -= 9.0
            for page_label, desc in plan.doc_entries:
                ax.text(28, y, f"{page_label}: {desc}", fontsize=9, color="#334155")
                y -= 7.0

        # Section 2: Footprint Schedule Table
        if plan.show_footprints_header or plan.is_footprints_continuation or plan.footprints:
            y -= 4.0
            if plan.show_footprints_header:
                ax.text(20, y, "2. Component Bill of Footprints", fontsize=11, fontweight="bold", color="#1e293b")
            else:
                ax.text(
                    20,
                    y,
                    f"2. Component Bill of Footprints (Cont. - Page {plan.page_index} of {total_toc_pages})",
                    fontsize=11,
                    fontweight="bold",
                    color="#1e293b",
                )
            y -= 7.0

            # Table Header
            ax.add_patch(patches.Rectangle((20, y - 5), 257, 6.5, facecolor="#0f172a", edgecolor="none"))
            ax.text(25, y - 3.5, "Designator", fontsize=8.5, fontweight="bold", color="#ffffff")
            ax.text(55, y - 3.5, "Package", fontsize=8.5, fontweight="bold", color="#ffffff")
            ax.text(105, y - 3.5, "Manufacturer Part Number (MPN)", fontsize=8.5, fontweight="bold", color="#ffffff")
            ax.text(185, y - 3.5, "Pins", fontsize=8.5, fontweight="bold", color="#ffffff")
            ax.text(210, y - 3.5, "Sheet", fontsize=8.5, fontweight="bold", color="#ffffff")
            y -= 6.5

            for row_idx, fp, sheet_num in plan.footprints:
                bg = "#f8fafc" if row_idx % 2 == 0 else "#ffffff"
                ax.add_patch(patches.Rectangle((20, y - 5), 257, 5.5, facecolor=bg, edgecolor="#e2e8f0", linewidth=0.5))
                mpn = fp.mpn or (fp.label.text if fp.label else fp.package)
                ax.text(25, y - 3.5, fp.name, fontsize=8, fontweight="bold", color="#0f172a")
                ax.text(55, y - 3.5, fp.package, fontsize=8, color="#334155")
                ax.text(105, y - 3.5, str(mpn), fontsize=8, color="#334155")
                ax.text(185, y - 3.5, str(len(fp.pins)), fontsize=8, color="#334155")
                sheet_label = str(sheet_num) if str(sheet_num).startswith("Sheet") else f"Sheet {sheet_num}"
                ax.text(210, y - 3.5, sheet_label, fontsize=8, color="#0284c7")
                y -= 5.5

        # Section 3: Primary Signal Nets Summary
        if plan.show_nets_header or plan.is_nets_continuation or plan.net_rows:
            y -= 4.0
            if plan.show_nets_header:
                ax.text(20, y, "3. Primary Signal Nets", fontsize=11, fontweight="bold", color="#1e293b")
            else:
                ax.text(
                    20,
                    y,
                    f"3. Primary Signal Nets (Cont. - Page {plan.page_index} of {total_toc_pages})",
                    fontsize=11,
                    fontweight="bold",
                    color="#1e293b",
                )
            y -= 6.0

            for row in plan.net_rows:
                for n_idx, net in enumerate(row):
                    nx = 28 + (n_idx * 62)
                    pin_count = len(net.pins)
                    ax.text(nx, y, f"• {net.name} ({pin_count} pins)", fontsize=8, color="#475569")
                y -= 5.0

        # Footer
        current_page_num = 1 + plan.page_index
        ax.text(148.5, 15, f"Page {current_page_num} of {total_pages}", ha="center", fontsize=9, color="#64748b")
        pdf.savefig(fig)

    def _is_decoupling_cap(self, fp: FootprintModel, pin_to_net: Dict[Tuple[str, str], str]) -> bool:
        """Check if a footprint is a 2-terminal decoupling capacitor connected between power and ground."""
        name_u = fp.name.upper()
        pkg_u = fp.package.upper()
        if not (name_u.startswith("C") or "CAP" in pkg_u) or len(fp.pins) != 2:
            return False
        n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
        n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
        return (n1 in POWER_NET_NAMES and n2 in GROUND_NET_NAMES) or (n2 in POWER_NET_NAMES and n1 in GROUND_NET_NAMES)

    def _is_pull_resistor(
        self,
        fp: FootprintModel,
        pin_to_net: Dict[Tuple[str, str], str],
        all_fps: List[FootprintModel],
    ) -> bool:
        """Check if a footprint is a 2-terminal pull-up or pull-down resistor connected to a signal line on the sheet."""
        name_u = fp.name.upper()
        pkg_u = fp.package.upper()
        if not (name_u.startswith("R") or "RES" in pkg_u) or len(fp.pins) != 2:
            return False
        n1 = pin_to_net.get((fp.name, fp.pins[0].name), "")
        n2 = pin_to_net.get((fp.name, fp.pins[1].name), "")
        is_rail_1 = n1.upper() in POWER_NET_NAMES or n1.upper() in GROUND_NET_NAMES
        is_rail_2 = n2.upper() in POWER_NET_NAMES or n2.upper() in GROUND_NET_NAMES
        if not (is_rail_1 or is_rail_2):
            return False
        sig_net = n2 if is_rail_1 else n1
        # The signal line must connect to another footprint on this sheet
        for other in all_fps:
            if other.name == fp.name:
                continue
            for p in other.pins:
                if pin_to_net.get((other.name, p.name)) == sig_net:
                    return True
        return False

    def _is_pullup_resistor(
        self,
        fp: FootprintModel,
        pin_to_net: Dict[Tuple[str, str], str],
        all_fps: List[FootprintModel],
    ) -> bool:
        """Alias for _is_pull_resistor supporting both pull-up and pull-down configurations."""
        return self._is_pull_resistor(fp, pin_to_net, all_fps)

    def _is_shunt_cap(
        self,
        fp: FootprintModel,
        pin_to_net: Dict[Tuple[str, str], str],
        all_fps: List[FootprintModel],
    ) -> bool:
        """Check if a footprint is a 2-terminal capacitor with one ground pin and one signal pin on the sheet."""
        name_u = fp.name.upper()
        pkg_u = fp.package.upper()
        if not (name_u.startswith("C") or "CAP" in pkg_u) or len(fp.pins) != 2:
            return False
        n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
        n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
        is_gnd_1 = n1 in GROUND_NET_NAMES
        is_gnd_2 = n2 in GROUND_NET_NAMES
        if not (is_gnd_1 or is_gnd_2):
            return False
        sig_net = n2 if is_gnd_1 else n1
        if sig_net in POWER_NET_NAMES:
            return False  # Handled as power decoupling capacitor
        for other in all_fps:
            if other.name == fp.name:
                continue
            for p in other.pins:
                if pin_to_net.get((other.name, p.name)) == sig_net:
                    return True
        return False

    def _draw_decoupling_cap_bank(
        self,
        ax: matplotlib.axes.Axes,
        caps: List[FootprintModel],
        pin_to_net: Dict[Tuple[str, str], str],
        base_x: float = 35.0,
        base_y: float = 62.0,
    ) -> None:
        """Render a compact vertical decoupling capacitor bank sharing single VCC and GND rails."""
        if not caps:
            return

        delta_x = 28.0
        n_caps = len(caps)
        total_w = (n_caps - 1) * delta_x

        y_top = base_y + 16.0
        y_bot = base_y - 12.0
        y_mid = (y_top + y_bot) / 2.0

        # Background dashed bounding card
        card_x = base_x - 12.0
        card_w = max(total_w + 32.0, 75.0)
        card_y = y_bot - 12.0
        card_h = (y_top - y_bot) + 26.0

        ax.add_patch(
            patches.Rectangle(
                (card_x, card_y),
                card_w,
                card_h,
                facecolor="#f8fafc",
                edgecolor="#cbd5e1",
                linestyle="--",
                linewidth=0.8,
                zorder=1,
            )
        )
        ax.text(
            card_x + 4.0,
            y_top + 8.5,
            "DECOUPLING CAPACITORS",
            fontsize=7.5,
            fontweight="bold",
            color="#334155",
            zorder=2,
        )

        rail_left = base_x - 4.0
        rail_right = base_x + total_w + 4.0

        # Draw Power Rails (Top) grouped by power net
        cap_pwr_map: Dict[str, str] = {}
        for cap in caps:
            pwr = "3V3"
            for p in cap.pins:
                net = pin_to_net.get((cap.name, p.name), "")
                if net.upper() in POWER_NET_NAMES:
                    pwr = net
                    break
            cap_pwr_map[cap.name] = pwr

        # Draw power rail segments per distinct power net
        pwr_nets_ordered: List[str] = []
        for cap in caps:
            pwr = cap_pwr_map[cap.name]
            if pwr not in pwr_nets_ordered:
                pwr_nets_ordered.append(pwr)

        for pwr_net in pwr_nets_ordered:
            sub_indices = [idx for idx, c in enumerate(caps) if cap_pwr_map[c.name] == pwr_net]
            if len(sub_indices) == 1:
                cx_single = base_x + sub_indices[0] * delta_x
                ax.plot([cx_single, cx_single], [y_top, y_top + 3.5], color="#dc2626", linewidth=1.2, zorder=2)
                ax.plot(
                    [cx_single - 2.5, cx_single, cx_single + 2.5],
                    [y_top + 2.0, y_top + 4.5, y_top + 2.0],
                    color="#dc2626",
                    linewidth=1.2,
                    zorder=2,
                )
                ax.text(
                    cx_single,
                    y_top + 5.5,
                    pwr_net,
                    ha="center",
                    va="bottom",
                    fontsize=5.8,
                    fontweight="bold",
                    color="#dc2626",
                    zorder=3,
                )
            else:
                sub_left = base_x + sub_indices[0] * delta_x
                sub_right = base_x + sub_indices[-1] * delta_x
                ax.plot([sub_left, sub_right], [y_top, y_top], color="#dc2626", linewidth=1.2, zorder=2)
                ax.plot([sub_left, sub_left], [y_top, y_top + 3.5], color="#dc2626", linewidth=1.2, zorder=2)
                ax.plot(
                    [sub_left - 2.5, sub_left, sub_left + 2.5],
                    [y_top + 2.0, y_top + 4.5, y_top + 2.0],
                    color="#dc2626",
                    linewidth=1.2,
                    zorder=2,
                )
                ax.text(
                    sub_left,
                    y_top + 5.5,
                    pwr_net,
                    ha="center",
                    va="bottom",
                    fontsize=5.8,
                    fontweight="bold",
                    color="#dc2626",
                    zorder=3,
                )

        # Common Ground Rail (Bottom) - ends exactly at the last capacitor to prevent antennae
        rail_left = base_x - 6.0
        rail_right = base_x + total_w
        ax.plot([rail_left, rail_right], [y_bot, y_bot], color="#475569", linewidth=1.2, zorder=2)

        # Common Ground 3-bar symbol (Left of rail)
        ax.plot([rail_left, rail_left], [y_bot, y_bot - 3.0], color="#475569", linewidth=1.2, zorder=2)
        ax.plot(
            [rail_left - 3.5, rail_left + 3.5],
            [y_bot - 3.0, y_bot - 3.0],
            color="#475569",
            linewidth=1.4,
            zorder=2,
        )
        ax.plot(
            [rail_left - 2.2, rail_left + 2.2],
            [y_bot - 4.2, y_bot - 4.2],
            color="#475569",
            linewidth=1.2,
            zorder=2,
        )
        ax.plot(
            [rail_left - 1.0, rail_left + 1.0],
            [y_bot - 5.4, y_bot - 5.4],
            color="#475569",
            linewidth=1.0,
            zorder=2,
        )
        ax.text(
            rail_left,
            y_bot - 6.8,
            "GND",
            ha="center",
            va="top",
            fontsize=5.5,
            fontweight="bold",
            color="#475569",
            zorder=3,
        )

        # Draw each vertical capacitor
        for idx, cap in enumerate(caps):
            cx = base_x + idx * delta_x

            # Power junction dot and lead
            ax.plot(cx, y_top, marker="o", markersize=2.5, color="#dc2626", zorder=3)
            ax.plot([cx, cx], [y_top, y_mid + 1.2], color="#475569", linewidth=1.2, zorder=2)

            # Parallel plates (compact, width 7mm)
            plate_w = 7.0
            ax.plot(
                [cx - plate_w / 2.0, cx + plate_w / 2.0],
                [y_mid + 1.2, y_mid + 1.2],
                color="#334155",
                linewidth=2.0,
                zorder=2,
            )
            ax.plot(
                [cx - plate_w / 2.0, cx + plate_w / 2.0],
                [y_mid - 1.2, y_mid - 1.2],
                color="#334155",
                linewidth=2.0,
                zorder=2,
            )

            # Ground lead and junction dot
            ax.plot([cx, cx], [y_mid - 1.2, y_bot], color="#475569", linewidth=1.2, zorder=2)
            ax.plot(cx, y_bot, marker="o", markersize=2.5, color="#475569", zorder=3)

            # Designator and Value text
            ax.text(
                cx + plate_w / 2.0 + 1.5,
                y_mid + 2.5,
                cap.name,
                ha="left",
                va="center",
                fontsize=7.5,
                fontweight="bold",
                color="#0f172a",
                zorder=3,
            )
            val = cap.mpn or (cap.label.text if cap.label else cap.package)
            ax.text(
                cx + plate_w / 2.0 + 1.5,
                y_mid - 2.5,
                str(val),
                ha="left",
                va="center",
                fontsize=5.5,
                color="#0369a1",
                zorder=3,
            )

    @staticmethod
    def _format_resistor_value(fp: FootprintModel) -> str:
        """Format a human-readable, concise resistance string from footprint metadata."""
        if fp.label and fp.label.text and fp.label.text != fp.name:
            return fp.label.text
        mpn = getattr(fp, "mpn", None)
        if mpn:
            import re

            if "4K7" in mpn or "4.7K" in mpn.upper():
                return "4.7k"
            m = re.search(r"(\d+[RKMGT]\d*|\d+\.\d+[kKMG]?)", mpn)
            if m:
                val = m.group(1).replace("K", "k")
                if "k" in val and not val.endswith("k"):
                    val = val.replace("k", ".") + "k"
                return val
            if len(mpn) > 8:
                return mpn[:8]
            return mpn
        return fp.package

    def _draw_pullup_resistors(
        self,
        ax: matplotlib.axes.Axes,
        pullups: List[FootprintModel],
        pin_to_net: Dict[Tuple[str, str], str],
        h_wire_segments: List[Tuple[float, float, float, str, str]],
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]],
        wired_pins: Optional[set[Tuple[str, str]]] = None,
        pin_side_map: Optional[Dict[Tuple[str, str], str]] = None,
    ) -> None:
        """Render pull-up and pull-down resistors as vertical branches directly attached to signal lines."""
        if not pullups:
            return
        if wired_pins is None:
            wired_pins = set()

        pullup_points: List[Tuple[float, float, FootprintModel, str, str]] = []

        # Determine common horizontal span across all pullup signal wires in the channel
        matching_segs = []
        for fp in pullups:
            n1 = pin_to_net.get((fp.name, fp.pins[0].name), "")
            n2 = pin_to_net.get((fp.name, fp.pins[1].name), "")
            sig = n2 if (n1.upper() in POWER_NET_NAMES or n1.upper() in GROUND_NET_NAMES) else n1
            seg = next((s for s in h_wire_segments if s[3] == sig), None)
            if seg:
                matching_segs.append(seg)

        x_min_all = max(min(s[0], s[1]) for s in matching_segs) if matching_segs else 80.0
        x_max_all = min(max(s[0], s[1]) for s in matching_segs) if matching_segs else 120.0
        pitch = 10.0
        total_span = (len(pullups) - 1) * pitch
        center_x = (x_min_all + x_max_all) / 2.0
        # Enforce at least 14.0 mm clearance from the right-hand component pins/symbols
        if center_x + total_span / 2.0 > x_max_all - 14.0:
            center_x = (x_max_all - 14.0) - total_span / 2.0
        if center_x - total_span / 2.0 < x_min_all + 6.0:
            center_x = (x_min_all + 6.0) + total_span / 2.0

        used_x_positions: List[float] = []
        for idx, fp in enumerate(pullups):
            n1 = pin_to_net.get((fp.name, fp.pins[0].name), "")
            n2 = pin_to_net.get((fp.name, fp.pins[1].name), "")
            if n1.upper() in POWER_NET_NAMES or n1.upper() in GROUND_NET_NAMES:
                rail_net = n1
                sig_net = n2
            else:
                rail_net = n2
                sig_net = n1

            matching_segs = [s for s in h_wire_segments if s[3] == sig_net]
            if matching_segs:
                x_start = min(min(s[0], s[1]) for s in matching_segs)
                x_end = max(max(s[0], s[1]) for s in matching_segs)
                seg_len = x_end - x_start
                if seg_len >= 18.0:
                    # Inter-component channel: space within segment with clearance from both ends
                    chan_fps = []
                    for other_fp in pullups:
                        o_n1 = pin_to_net.get((other_fp.name, other_fp.pins[0].name), "")
                        o_n2 = pin_to_net.get((other_fp.name, other_fp.pins[1].name), "")
                        o_sig = o_n2 if (o_n1.upper() in POWER_NET_NAMES or o_n1.upper() in GROUND_NET_NAMES) else o_n1
                        o_segs = [s for s in h_wire_segments if s[3] == o_sig]
                        if o_segs:
                            o_xs = min(min(s[0], s[1]) for s in o_segs)
                            o_xe = max(max(s[0], s[1]) for s in o_segs)
                            if abs(o_xs - x_start) < 2.0 and abs(o_xe - x_end) < 2.0:
                                chan_fps.append(other_fp)

                    n_chan = max(1, len(chan_fps))
                    chan_idx = chan_fps.index(fp) if fp in chan_fps else (idx % n_chan)
                    safe_min = x_start + 6.0
                    safe_max = x_end - 10.0
                    pitch = 14.0
                    total_span = (n_chan - 1) * pitch
                    if safe_max - safe_min >= total_span:
                        mid_x = (safe_min + safe_max) / 2.0
                        cand_x = (mid_x - total_span / 2.0) + chan_idx * pitch
                    else:
                        step = (safe_max - safe_min) / max(1, n_chan - 1) if n_chan > 1 else 0.0
                        cand_x = safe_min + chan_idx * step

                    while any(abs(cand_x - ux) < 7.0 for ux in used_x_positions):
                        if cand_x + 7.0 <= safe_max:
                            cand_x += 7.0
                        elif cand_x - 7.0 >= safe_min:
                            cand_x -= 7.0
                        else:
                            break
                elif x_start < 100.0:
                    # Left breakout stub: extend outward to the left well clear of GND symbols while staying on-page
                    min_page_x = 22.0
                    cand_x = max(min_page_x, x_start - 24.0 - idx * 16.0)
                    while any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                        if cand_x - 10.0 >= min_page_x:
                            cand_x -= 10.0
                        elif cand_x + 10.0 <= x_start - 6.0:
                            cand_x += 10.0
                        else:
                            break
                    ax.plot(
                        [cand_x, x_start],
                        [matching_segs[0][2], matching_segs[0][2]],
                        color="#2563eb",
                        linewidth=1.2,
                        zorder=2,
                    )
                    h_wire_segments.append((cand_x, x_start, matching_segs[0][2], sig_net, "#2563eb"))
                else:
                    # Right breakout stub: extend outward to the right while staying on-page
                    max_page_x = 275.0
                    cand_x = min(max_page_x, x_end + 14.0 + idx * 16.0)
                    while any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                        if cand_x + 10.0 <= max_page_x:
                            cand_x += 10.0
                        elif cand_x - 10.0 >= x_end + 6.0:
                            cand_x -= 10.0
                        else:
                            break
                    ax.plot(
                        [x_end, cand_x],
                        [matching_segs[0][2], matching_segs[0][2]],
                        color="#2563eb",
                        linewidth=1.2,
                        zorder=2,
                    )
                    h_wire_segments.append((x_end, cand_x, matching_segs[0][2], sig_net, "#2563eb"))
                x_pull = cand_x
                y_base = matching_segs[0][2]
            else:
                target_pair = next(
                    (p for p, c in sheet_pin_coords.items() if pin_to_net.get(p) == sig_net and p[0] != fp.name),
                    None,
                )
                if target_pair:
                    p_x, p_y = sheet_pin_coords[target_pair]
                    y_base = p_y
                    side = "right"
                    if pin_side_map and target_pair in pin_side_map:
                        side = pin_side_map[target_pair]
                    elif p_x < 148.5:
                        side = "left"

                    step = 14.0
                    if side == "right":
                        next_comp_left = min(
                            (c[0] for p, c in sheet_pin_coords.items() if c[0] > p_x + 10.0 and p[0] != target_pair[0]),
                            default=280.0,
                        )
                        cand_x = p_x + 14.0 + idx * 16.0
                        if cand_x > next_comp_left - 12.0:
                            cand_x = (p_x + next_comp_left) / 2.0
                        while any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                            if cand_x - 7.0 > p_x + 6.0:
                                cand_x -= 7.0
                            elif cand_x + 7.0 < next_comp_left - 8.0:
                                cand_x += 7.0
                            else:
                                break
                    else:
                        min_page_x = 22.0
                        cand_x = max(min_page_x, p_x - 24.0 - idx * 16.0)
                        while any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                            if cand_x - step >= min_page_x:
                                cand_x -= step
                            elif cand_x + step <= p_x - 6.0:
                                cand_x += step
                            else:
                                break
                    x_pull = cand_x

                    # Draw connecting line from component pin to pullup junction
                    ax.plot([p_x, x_pull], [y_base, y_base], color="#2563eb", linewidth=1.2, zorder=2)
                    ax.text(
                        (p_x + x_pull) / 2.0,
                        y_base + 1.2,
                        sig_net,
                        ha="center",
                        va="bottom",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=4,
                    )
                    wired_pins.add(target_pair)
                    h_wire_segments.append((min(p_x, x_pull), max(p_x, x_pull), y_base, sig_net, "#2563eb"))
                else:
                    x_pull = center_x - total_span / 2.0 + idx * pitch
                    y_base = 120.0

            used_x_positions.append(x_pull)
            pullup_points.append((x_pull, y_base, fp, sig_net, rail_net))

        channel_wire_ys = [seg[2] for seg in h_wire_segments]
        channel_top_y = max(channel_wire_ys) if channel_wire_ys else max(p[1] for p in pullup_points)

        pwr_pullups = [p for p in pullup_points if p[4].upper() in POWER_NET_NAMES]
        same_pwr = len({p[4] for p in pwr_pullups}) == 1 and len(pwr_pullups) > 1
        common_pwr = pwr_pullups[0][4] if same_pwr else "3V3"
        pullup_max_y = max((p[1] for p in pwr_pullups), default=120.0)

        for x_pull, y_base, fp, sig_net, rail_net in pullup_points:
            # Junction dot on the signal wire
            ax.plot(x_pull, y_base, marker="o", markersize=3.0, color="#2563eb", zorder=4)

            is_pullup = rail_net.upper() in POWER_NET_NAMES
            if is_pullup:
                y_zz_bot = pullup_max_y + 8.0
                y_zz_top = y_zz_bot + 9.0
                y_top_rail = y_zz_top + 6.0

                # Lead up to resistor body with jumper bridges over crossing wires
                self._draw_vertical_wire_with_jumpers(
                    ax,
                    x_v=x_pull,
                    y_start=y_base,
                    y_end=y_zz_bot,
                    col="#475569",
                    h_wire_segments=h_wire_segments,
                    net_name=sig_net,
                )

                # Vertical zig-zag resistor body (height 9mm)
                zz_y = [
                    y_zz_bot,
                    y_zz_bot + 1.125,
                    y_zz_bot + 2.25,
                    y_zz_bot + 3.375,
                    y_zz_bot + 4.5,
                    y_zz_bot + 5.625,
                    y_zz_bot + 6.75,
                    y_zz_bot + 7.875,
                    y_zz_top,
                ]
                zz_x = [
                    x_pull,
                    x_pull + 1.6,
                    x_pull - 1.6,
                    x_pull + 1.6,
                    x_pull - 1.6,
                    x_pull + 1.6,
                    x_pull - 1.6,
                    x_pull + 1.6,
                    x_pull,
                ]
                ax.plot(zz_x, zz_y, color="#334155", linewidth=1.5, zorder=3)

                # Resistor RefDes & Value text to the right
                val_text = self._format_resistor_value(fp)
                ax.text(
                    x_pull + 2.2,
                    y_zz_bot + 6.2,
                    fp.name,
                    ha="left",
                    va="center",
                    fontsize=7.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=4,
                )
                ax.text(
                    x_pull + 2.2,
                    y_zz_bot + 2.2,
                    val_text,
                    ha="left",
                    va="center",
                    fontsize=5.5,
                    color="#0369a1",
                    zorder=4,
                )

                if same_pwr:
                    ax.plot([x_pull, x_pull], [y_zz_top, y_top_rail], color="#dc2626", linewidth=1.2, zorder=2)
                    ax.plot(x_pull, y_top_rail, marker="o", markersize=2.0, color="#dc2626", zorder=3)
                else:
                    y_arrow = y_zz_top + 4.0
                    ax.plot([x_pull, x_pull], [y_zz_top, y_arrow], color="#dc2626", linewidth=1.2, zorder=2)
                    ax.plot(
                        [x_pull - 2.5, x_pull, x_pull + 2.5],
                        [y_arrow - 1.5, y_arrow + 1.0, y_arrow - 1.5],
                        color="#dc2626",
                        linewidth=1.2,
                        zorder=2,
                    )
                    ax.text(
                        x_pull,
                        y_arrow + 2.2,
                        rail_net,
                        ha="center",
                        va="bottom",
                        fontsize=5.8,
                        fontweight="bold",
                        color="#dc2626",
                        zorder=4,
                    )
            else:
                # Pull-down resistor to GND
                y_zz_top = y_base - 8.0
                y_zz_bot = y_zz_top - 9.0
                y_drop = y_zz_bot - 4.0

                # Lead down to resistor body
                self._draw_vertical_wire_with_jumpers(
                    ax,
                    x_v=x_pull,
                    y_start=y_base,
                    y_end=y_zz_top,
                    col="#475569",
                    h_wire_segments=h_wire_segments,
                    net_name=sig_net,
                )

                if fp.name.upper().startswith("C"):
                    plate_w = 7.0
                    ax.plot(
                        [x_pull - plate_w / 2.0, x_pull + plate_w / 2.0],
                        [y_zz_top - 2.5, y_zz_top - 2.5],
                        color="#334155",
                        linewidth=2.0,
                        zorder=3,
                    )
                    ax.plot(
                        [x_pull - plate_w / 2.0, x_pull + plate_w / 2.0],
                        [y_zz_top - 4.9, y_zz_top - 4.9],
                        color="#334155",
                        linewidth=2.0,
                        zorder=3,
                    )
                    ax.plot(
                        [x_pull, x_pull],
                        [y_zz_top, y_zz_top - 2.5],
                        color="#475569",
                        linewidth=1.2,
                        zorder=2,
                    )
                    ax.plot(
                        [x_pull, x_pull],
                        [y_zz_top - 4.9, y_zz_bot],
                        color="#475569",
                        linewidth=1.2,
                        zorder=2,
                    )
                else:
                    # Vertical zig-zag resistor body
                    zz_y = [
                        y_zz_top,
                        y_zz_top - 1.125,
                        y_zz_top - 2.25,
                        y_zz_top - 3.375,
                        y_zz_top - 4.5,
                        y_zz_top - 5.625,
                        y_zz_top - 6.75,
                        y_zz_top - 7.875,
                        y_zz_bot,
                    ]
                    zz_x = [
                        x_pull,
                        x_pull + 1.6,
                        x_pull - 1.6,
                        x_pull + 1.6,
                        x_pull - 1.6,
                        x_pull + 1.6,
                        x_pull - 1.6,
                        x_pull + 1.6,
                        x_pull,
                    ]
                    ax.plot(zz_x, zz_y, color="#334155", linewidth=1.5, zorder=3)

                # Resistor / Capacitor RefDes & Value text to the right
                val_text = self._format_resistor_value(fp)
                text_x_off = 4.8 if fp.name.upper().startswith("C") else 2.2
                ax.text(
                    x_pull + text_x_off,
                    y_zz_bot + 6.2,
                    fp.name,
                    ha="left",
                    va="center",
                    fontsize=7.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=4,
                )
                ax.text(
                    x_pull + text_x_off,
                    y_zz_bot + 2.2,
                    val_text,
                    ha="left",
                    va="center",
                    fontsize=5.5,
                    color="#0369a1",
                    zorder=4,
                )

                # Lead down to 3-bar GND symbol
                ax.plot([x_pull, x_pull], [y_zz_bot, y_drop], color="#475569", linewidth=1.2, zorder=2)
                ax.plot([x_pull - 2.8, x_pull + 2.8], [y_drop, y_drop], color="#475569", linewidth=1.4, zorder=2)
                ax.plot(
                    [x_pull - 1.8, x_pull + 1.8], [y_drop - 1.2, y_drop - 1.2], color="#475569", linewidth=1.2, zorder=2
                )
                ax.plot(
                    [x_pull - 0.8, x_pull + 0.8], [y_drop - 2.4, y_drop - 2.4], color="#475569", linewidth=1.0, zorder=2
                )
                ax.text(
                    x_pull,
                    y_drop - 3.8,
                    "GND",
                    ha="center",
                    va="top",
                    fontsize=5.5,
                    fontweight="bold",
                    color="#475569",
                    zorder=3,
                )

        if same_pwr and len(pwr_pullups) > 1:
            x_min_pull = min(p[0] for p in pwr_pullups)
            x_max_pull = max(p[0] for p in pwr_pullups)
            y_zz_top = pullup_max_y + 17.0
            y_top_rail = y_zz_top + 6.0

            # Dedicated dashed section card for pull-up resistors
            card_x = x_min_pull - 5.0
            card_w = (x_max_pull - x_min_pull) + 16.0
            card_y = min(p[1] for p in pwr_pullups) + 4.0
            card_h = (y_top_rail + 16.0) - card_y
            is_i2c = any("SDA" in p[3].upper() or "SCL" in p[3].upper() for p in pwr_pullups)
            card_title = "I2C PULL-UP RESISTORS" if is_i2c else "PULL-UP RESISTORS"

            ax.add_patch(
                patches.Rectangle(
                    (card_x, card_y),
                    card_w,
                    card_h,
                    facecolor="#f8fafc",
                    edgecolor="#cbd5e1",
                    linestyle="--",
                    linewidth=0.8,
                    zorder=1,
                )
            )
            ax.text(
                card_x + 3.0,
                card_y + card_h - 2.8,
                card_title,
                fontsize=5.5,
                fontweight="bold",
                color="#334155",
                zorder=2,
            )

            ax.plot([x_min_pull, x_max_pull], [y_top_rail, y_top_rail], color="#dc2626", linewidth=1.2, zorder=2)
            x_arrow = (x_min_pull + x_max_pull) / 2.0
            ax.plot([x_arrow, x_arrow], [y_top_rail, y_top_rail + 3.5], color="#dc2626", linewidth=1.2, zorder=2)
            ax.plot(
                [x_arrow - 2.5, x_arrow, x_arrow + 2.5],
                [y_top_rail + 2.0, y_top_rail + 4.5, y_top_rail + 2.0],
                color="#dc2626",
                linewidth=1.2,
                zorder=2,
            )
            ax.text(
                x_arrow,
                y_top_rail + 5.5,
                common_pwr,
                ha="center",
                va="bottom",
                fontsize=5.8,
                fontweight="bold",
                color="#dc2626",
                zorder=4,
            )

    def _draw_vertical_wire_with_jumpers(
        self,
        ax: matplotlib.axes.Axes,
        x_v: float,
        y_start: float,
        y_end: float,
        col: str,
        h_wire_segments: List[Tuple[float, float, float, str, str]],
        net_name: str = "",
    ) -> None:
        """Render a vertical wire segment with semicircular jumper bridge loops over crossing horizontal wires."""
        r = JUMPER_BRIDGE_RADIUS_MM
        y_min = min(y_start, y_end)
        y_max = max(y_start, y_end)

        crossings: List[float] = []
        for h_start, h_end, h_y, h_net, _ in h_wire_segments:
            if h_net and net_name and h_net == net_name:
                continue
            hx_min = min(h_start, h_end)
            hx_max = max(h_start, h_end)
            if (hx_min + 0.5 < x_v < hx_max - 0.5) and (y_min + 0.5 < h_y < y_max - 0.5):
                crossings.append(h_y)

        s = 1.0 if y_end >= y_start else -1.0
        crossings.sort(reverse=(s < 0))

        y_curr = y_start
        for y_c in crossings:
            # Vertical segment up to jumper loop
            ax.plot([x_v, x_v], [y_curr, y_c - s * r], color=col, linewidth=1.2, zorder=2)
            # Semicircular jumper bridge loop bulging to the right
            arc = patches.Arc(
                (x_v, y_c),
                width=2 * r,
                height=2 * r,
                angle=0,
                theta1=270,
                theta2=90,
                color=col,
                linewidth=1.2,
                zorder=3,
            )
            ax.add_patch(arc)
            y_curr = y_c + s * r

        # Final vertical segment to endpoint
        ax.plot([x_v, x_v], [y_curr, y_end], color=col, linewidth=1.2, zorder=2)

    @staticmethod
    def _generate_default_transistor_truth_table(
        fp: FootprintModel,
        pin_to_net: Dict[Tuple[str, str], str],
    ) -> TruthTableModel:
        """Generate a default truth table capturing true, false, and invalid states for a discrete transistor network."""
        gate_pin = next((p for p in fp.pins if p.name.upper() in ("G", "GATE", "B", "BASE", "1")), None)
        drain_pin = next((p for p in fp.pins if p.name.upper() in ("D", "DRAIN", "C", "COLL", "3")), None)
        source_pin = next((p for p in fp.pins if p.name.upper() in ("S", "SOURCE", "E", "EMIT", "2")), None)

        gate_net = pin_to_net.get((fp.name, gate_pin.name), "GATE") if gate_pin else "GATE"
        drain_net = pin_to_net.get((fp.name, drain_pin.name), "DRAIN") if drain_pin else "DRAIN"
        source_net = pin_to_net.get((fp.name, source_pin.name), "GND") if source_pin else "GND"

        in_header = f"{gate_net} (Gate)"
        out_header = f"{drain_net} (Drain)"

        rows = [
            TruthTableRowModel(
                inputs={in_header: "0 (Low, <0.8V)"},
                outputs={out_header: "Hi-Z (Pull-up)"},
                state="FALSE",
                description="Cutoff; load de-asserted / isolated",
            ),
            TruthTableRowModel(
                inputs={in_header: "1 (High, >1.5V)"},
                outputs={out_header: f"0V ({source_net})"},
                state="TRUE",
                description="Saturation; active conduction to ground",
            ),
            TruthTableRowModel(
                inputs={in_header: "Float / High-Z"},
                outputs={out_header: "Indeterminate"},
                state="INVALID",
                description="Prohibited floating gate; leakage/glitch risk",
            ),
            TruthTableRowModel(
                inputs={in_header: "Over-Voltage (>20V)"},
                outputs={out_header: "Fault / Breakdown"},
                state="INVALID",
                description="Dielectric rupture; permanent gate short",
            ),
        ]

        title = f"{fp.name} ({fp.mpn or fp.package}) Network Logic"
        return TruthTableModel(
            title=title,
            input_headers=[in_header],
            output_headers=[out_header],
            rows=rows,
        )

    def _draw_truth_table(
        self,
        ax: matplotlib.axes.Axes,
        fp: FootprintModel,
        tt: TruthTableModel,
        base_x: float = 118.0,
        base_y: float = 52.0,
        card_w: float = 125.0,
    ) -> None:
        """Render an engineering truth table box displaying TRUE, FALSE, and INVALID circuit states."""
        n_rows = len(tt.rows)
        row_h = 5.4
        header_h = 7.0
        col_hdr_h = 5.5
        card_h = header_h + col_hdr_h + n_rows * row_h + 3.0
        card_y = base_y - card_h / 2.0

        # Card container with subtle shadow border
        ax.add_patch(
            patches.Rectangle(
                (base_x, card_y),
                card_w,
                card_h,
                facecolor="#ffffff",
                edgecolor="#cbd5e1",
                linewidth=1.0,
                zorder=1,
            )
        )

        # Title bar
        y_top = card_y + card_h
        ax.add_patch(
            patches.Rectangle(
                (base_x, y_top - header_h),
                card_w,
                header_h,
                facecolor="#0f172a",
                edgecolor="none",
                zorder=2,
            )
        )
        title_text = f"⚡ {tt.title.upper()} - {fp.name}"
        ax.text(
            base_x + 3.0,
            y_top - (header_h / 2.0),
            title_text,
            ha="left",
            va="center",
            fontsize=6.5,
            fontweight="bold",
            color="#ffffff",
            zorder=3,
        )

        # Column headers
        y_col = y_top - header_h - 3.5
        col_state_x = base_x + 3.0
        col_in_x = base_x + 18.0
        col_out_x = base_x + 42.0
        col_desc_x = base_x + 82.0

        ax.text(
            col_state_x + 6.5,
            y_col,
            "STATE",
            ha="center",
            va="center",
            fontsize=5.0,
            fontweight="bold",
            color="#64748b",
            zorder=3,
        )
        in_lbl = "/".join(tt.input_headers) if tt.input_headers else "INPUT"
        ax.text(
            col_in_x,
            y_col,
            in_lbl,
            ha="left",
            va="center",
            fontsize=4.8,
            fontweight="bold",
            color="#64748b",
            zorder=3,
        )
        out_lbl = "/".join(tt.output_headers) if tt.output_headers else "OUTPUT"
        ax.text(
            col_out_x,
            y_col,
            out_lbl,
            ha="left",
            va="center",
            fontsize=4.6,
            fontweight="bold",
            color="#64748b",
            zorder=3,
        )
        ax.text(
            col_desc_x,
            y_col,
            "FUNCTIONAL MODE",
            ha="left",
            va="center",
            fontsize=5.0,
            fontweight="bold",
            color="#64748b",
            zorder=3,
        )

        # Header divider line
        y_div = y_col - 2.5
        ax.plot([base_x, base_x + card_w], [y_div, y_div], color="#e2e8f0", linewidth=0.8, zorder=2)

        # Rows
        for r_idx, row in enumerate(tt.rows):
            y_row_mid = y_div - ((r_idx + 0.5) * row_h)

            # Zebra striping
            if r_idx % 2 == 1:
                ax.add_patch(
                    patches.Rectangle(
                        (base_x + 0.5, y_row_mid - (row_h / 2.0)),
                        card_w - 1.0,
                        row_h,
                        facecolor="#f8fafc",
                        edgecolor="none",
                        zorder=2,
                    )
                )

            # State badge pill
            state_str = str(row.state).upper()
            if "TRUE" in state_str:
                pill_bg = "#dcfce7"
                pill_fg = "#15803d"
                pill_edge = "#86efac"
            elif "FALSE" in state_str:
                pill_bg = "#f1f5f9"
                pill_fg = "#475569"
                pill_edge = "#cbd5e1"
            else:  # INVALID / PROHIBITED / FLOAT
                pill_bg = "#fee2e2"
                pill_fg = "#b91c1c"
                pill_edge = "#fca5a5"

            pill_w = 13.0
            pill_h = 3.6
            ax.add_patch(
                patches.FancyBboxPatch(
                    (col_state_x, y_row_mid - pill_h / 2.0),
                    pill_w,
                    pill_h,
                    boxstyle="round,pad=0.2,rounding_size=1.0",
                    facecolor=pill_bg,
                    edgecolor=pill_edge,
                    linewidth=0.6,
                    zorder=3,
                )
            )
            ax.text(
                col_state_x + pill_w / 2.0,
                y_row_mid,
                state_str[:7],
                ha="center",
                va="center",
                fontsize=4.5,
                fontweight="bold",
                color=pill_fg,
                zorder=4,
            )

            # Inputs values
            in_val = ", ".join(row.inputs.values())
            ax.text(col_in_x, y_row_mid, in_val, ha="left", va="center", fontsize=5.0, color="#1e293b", zorder=3)

            # Outputs values
            out_val = ", ".join(row.outputs.values())
            ax.text(col_out_x, y_row_mid, out_val, ha="left", va="center", fontsize=5.0, color="#1e293b", zorder=3)

            # Description
            ax.text(
                col_desc_x,
                y_row_mid,
                row.description,
                ha="left",
                va="center",
                fontsize=4.8,
                color="#64748b",
                zorder=3,
            )

            # Row bottom divider
            y_row_bot = y_row_mid - (row_h / 2.0)
            ax.plot([base_x, base_x + card_w], [y_row_bot, y_row_bot], color="#f1f5f9", linewidth=0.5, zorder=2)

    def _render_pdf_schematic_sheet(
        self,
        pdf: PdfPages,
        board_name: str,
        sheet_plan: _SchematicSheetPlan,
        total_sheets: int,
        all_nets: List[NetModel],
        page_num: int,
        total_pages: int,
    ) -> None:
        """Render an individual schematic drawing sheet with component symbols and nets."""
        fig = Figure(figsize=(11.693, 8.268), dpi=300)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 297)
        ax.set_ylim(0, 210)
        ax.axis("off")

        # Outer border
        ax.add_patch(patches.Rectangle((10, 10), 277, 190, fill=False, edgecolor="#1e293b", linewidth=1.8))
        ax.add_patch(patches.Rectangle((12, 12), 273, 186, fill=False, edgecolor="#94a3b8", linewidth=0.6))

        # Grid Zone Markers
        v_zones = [("A", 152.5, 198.0), ("B", 105.0, 152.5), ("C", 57.5, 105.0), ("D", 12.0, 57.5)]
        for label, y_min, y_max in v_zones:
            mid_y = (y_min + y_max) / 2.0
            ax.text(10.8, mid_y, label, ha="center", va="center", fontsize=6.5, color="#64748b")
            ax.text(285.2, mid_y, label, ha="center", va="center", fontsize=6.5, color="#64748b")

        h_step = 273.0 / 6.0
        for i in range(6):
            mid_x = 12.0 + (i + 0.5) * h_step
            ax.text(mid_x, 199.2, str(i + 1), ha="center", va="center", fontsize=6.5, color="#64748b")
            ax.text(mid_x, 10.8, str(i + 1), ha="center", va="center", fontsize=6.5, color="#64748b")

        # Top banner for sheet title & description
        ax.text(
            20,
            191.0,
            f"SHEET {sheet_plan.sheet_idx}: {sheet_plan.title.upper()}",
            fontsize=10,
            fontweight="bold",
            color="#1e293b",
        )
        if sheet_plan.description:
            ax.text(20, 185.5, sheet_plan.description, fontsize=7.5, color="#64748b")

        # Standard KiCad/Engineering Title Block (Bottom-Right)
        tb_x, tb_y, tb_w, tb_h = 202.0, 12.0, 83.0, 32.0
        ax.add_patch(
            patches.Rectangle((tb_x, tb_y), tb_w, tb_h, facecolor="#f8fafc", edgecolor="#1e293b", linewidth=1.2)
        )
        ax.plot([tb_x, tb_x + tb_w], [tb_y + 20, tb_y + 20], color="#cbd5e1", linewidth=0.8)
        ax.plot([tb_x, tb_x + tb_w], [tb_y + 10, tb_y + 10], color="#cbd5e1", linewidth=0.8)
        ax.plot([tb_x + 45, tb_x + 45], [tb_y, tb_y + 20], color="#cbd5e1", linewidth=0.8)

        sheet_title_display = sheet_plan.title if len(sheet_plan.title) <= 24 else sheet_plan.title[:22] + "..."
        ax.text(tb_x + 3, tb_y + 26, sheet_title_display, fontsize=8.5, fontweight="bold", color="#0f172a")
        ax.text(
            tb_x + 3,
            tb_y + 21.5,
            f"Sheet {sheet_plan.sheet_idx} of {total_sheets} (Page {page_num} of {total_pages})",
            fontsize=7.5,
            color="#475569",
        )
        board_rev = self.config.revision if self.config and self.config.revision else "1.0"
        ax.text(tb_x + 3, tb_y + 14, f"Rev: {board_rev}", fontsize=7.5, color="#334155")
        ax.text(
            tb_x + 3,
            tb_y + 4,
            f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            fontsize=7.5,
            color="#334155",
        )
        ax.text(tb_x + 48, tb_y + 14, "Status: APPROVED", fontsize=7, fontweight="bold", color="#16a34a")
        ax.text(tb_x + 48, tb_y + 4, "Tool: kicad-cli", fontsize=7, color="#64748b")

        # Map pins to net names
        pin_to_net: Dict[Tuple[str, str], str] = {}
        for net in all_nets:
            for pair in net.pins:
                pin_to_net[pair] = net.name

        sheet_fps = sheet_plan.footprints

        # Classify footprints into main components, decoupling capacitors, and vertical passives
        decoupling_caps = [fp for fp in sheet_fps if self._is_decoupling_cap(fp, pin_to_net)]
        pullup_resistors = [fp for fp in sheet_fps if self._is_pull_resistor(fp, pin_to_net, sheet_fps)]
        shunt_caps = [fp for fp in sheet_fps if self._is_shunt_cap(fp, pin_to_net, sheet_fps)]

        # If other main components exist on the sheet, extract decoupling caps & passives
        passive_names = {fp.name for fp in decoupling_caps + pullup_resistors + shunt_caps}
        if passive_names and (len(passive_names) < len(sheet_fps)):
            main_fps = [fp for fp in sheet_fps if fp.name not in passive_names]
        else:
            decoupling_caps = []
            pullup_resistors = []
            shunt_caps = []
            main_fps = sheet_fps

        num_comps = len(main_fps)
        pin_pitch = PIN_PITCH_MM

        has_bottom_cards = bool(decoupling_caps) or any(
            getattr(fp, "truth_table", None) is not None or fp.name.upper().startswith("Q") for fp in sheet_fps
        )

        sheet_model = (
            self.config.schematic_sheets[sheet_plan.sheet_idx - 1]
            if (
                self.config
                and self.config.schematic_sheets
                and (0 <= (sheet_plan.sheet_idx - 1) < len(self.config.schematic_sheets))
            )
            else None
        )
        layout = (
            getattr(sheet_model, "layout", None)
            or getattr(self.config, "schematic_layout", None)
            or SchematicLayoutModel()
        )
        page_center_x = layout.sheet_center_x
        page_center_y = layout.sheet_center_y

        if has_bottom_cards:
            top_row_y = 158.0
            bottom_cards_y = 66.0
        elif pullup_resistors:
            top_row_y = 138.0
            bottom_cards_y = 60.0
        else:
            top_row_y = 138.0
            bottom_cards_y = 60.0

        cols_override = getattr(layout, "cols_per_row", None)
        grid_positions = getattr(layout, "grid_positions", {}) or {}

        if cols_override is not None:
            cols_per_row = cols_override
            col_w = 210.0 / max(1, cols_per_row)
            cw = min(38.0, col_w * 0.55)
            gap = (210.0 - (cols_per_row * cw)) / max(1, cols_per_row - 1) if cols_per_row > 1 else 0.0
            start_x = 45.0
            col_x_positions = []
            col_y_positions = []
            comp_col_map = {}
            comp_row_map = {}
            for i, fp in enumerate(main_fps):
                if fp.name in grid_positions:
                    r_idx, c_idx_col = grid_positions[fp.name]
                else:
                    r_idx = i // cols_per_row
                    c_idx_col = i % cols_per_row
                comp_row_map[fp.name] = r_idx
                comp_col_map[fp.name] = c_idx_col
                col_x_positions.append(start_x + c_idx_col * (cw + gap))
                col_y_positions.append(top_row_y - (r_idx * layout.row_step_y))
        elif num_comps == 1:
            cols_per_row = 1
            cw = 38.0
            col_x_positions = [page_center_x - cw / 2.0]
            col_y_positions = [top_row_y]
            comp_col_map = {main_fps[0].name: 0}
            comp_row_map = {main_fps[0].name: 0}
        elif num_comps == 2:
            cols_per_row = 2
            cw = 38.0
            gap = 55.0
            total_w = 2 * cw + gap
            start_x = page_center_x - total_w / 2.0
            col_x_positions = [start_x, start_x + cw + gap]
            col_y_positions = [top_row_y, top_row_y]
            comp_col_map = {main_fps[0].name: 0, main_fps[1].name: 1}
            comp_row_map = {main_fps[0].name: 0, main_fps[1].name: 0}
        elif num_comps == 3:
            cols_per_row = 3
            cw = 36.0
            gap = getattr(layout, "col_gap", 50.0) if getattr(layout, "col_gap", 15.0) != 15.0 else 50.0
            total_w = 3 * cw + 2 * gap
            start_x = max(40.0, page_center_x - total_w / 2.0)
            col_x_positions = [start_x, start_x + cw + gap, start_x + 2 * (cw + gap)]
            col_y_positions = [top_row_y, top_row_y, top_row_y]
            comp_col_map = {fp.name: idx for idx, fp in enumerate(main_fps)}
            comp_row_map = {fp.name: 0 for fp in main_fps}
        else:
            cols_per_row = (num_comps + 1) // 2
            col_w = 210.0 / max(1, cols_per_row)
            cw = min(36.0, col_w * 0.55)
            col_x_positions = []
            col_y_positions = []
            comp_col_map = {}
            comp_row_map = {}
            for i, fp in enumerate(main_fps):
                r_idx = i // cols_per_row
                c_idx_col = i % cols_per_row
                comp_row_map[fp.name] = r_idx
                comp_col_map[fp.name] = c_idx_col
                col_x_positions.append(45.0 + c_idx_col * col_w + (col_w - cw) / 2.0)
                col_y_positions.append(top_row_y - (r_idx * layout.row_step_y))

        sheet_pin_sides = getattr(sheet_model, "pin_sides", {}) or {}
        pin_side_map: Dict[Tuple[str, str], str] = {}
        for fp in main_fps:
            comp_side_overrides = sheet_pin_sides.get(fp.name, {})
            left_p = []
            right_p = []
            for p in fp.pins:
                if p.name in comp_side_overrides:
                    if comp_side_overrides[p.name] == "right":
                        right_p.append(p)
                    else:
                        left_p.append(p)
                elif p.side.value in ("right", "top"):
                    right_p.append(p)
                elif p.side.value in ("left", "bottom"):
                    left_p.append(p)
            if not left_p and not right_p:
                left_p = fp.pins[: len(fp.pins) // 2]
                right_p = fp.pins[len(fp.pins) // 2 :]
            for p in left_p:
                pin_side_map[(fp.name, p.name)] = "left"
            for p in right_p:
                pin_side_map[(fp.name, p.name)] = "right"

        # Discover direct wire pairs between facing pins of adjacent components
        direct_wire_pairs: List[Tuple[Tuple[str, str], Tuple[str, str], NetModel]] = []
        wired_pins: set[Tuple[str, str]] = set()

        for net in all_nets:
            present_pins = [pair for pair in net.pins if pair in pin_side_map]
            if len(present_pins) >= 2:
                for i, pair1 in enumerate(present_pins):
                    for pair2 in present_pins[i + 1 :]:
                        if pair1 in wired_pins or pair2 in wired_pins:
                            continue
                        c1, c2 = comp_col_map[pair1[0]], comp_col_map[pair2[0]]
                        s1, s2 = pin_side_map[pair1], pin_side_map[pair2]
                        if c1 > c2:
                            pair1, pair2 = pair2, pair1
                            c1, c2 = c2, c1
                            s1, s2 = s2, s1
                        if (c2 == c1 + 1) and s1 == "right" and s2 == "left":
                            direct_wire_pairs.append((pair1, pair2, net))
                            wired_pins.add(pair1)
                            wired_pins.add(pair2)

        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]] = {}
        comp_boxes: List[Tuple[float, float, float, float]] = []

        for c_idx, fp in enumerate(main_fps):
            cx = col_x_positions[c_idx]
            row_top_y = col_y_positions[c_idx]

            comp_side_overrides = sheet_pin_sides.get(fp.name, {})
            left_pins = []
            right_pins = []
            for p in fp.pins:
                if p.name in comp_side_overrides:
                    if comp_side_overrides[p.name] == "right":
                        right_pins.append(p)
                    else:
                        left_pins.append(p)
                elif p.side.value in ("right", "top"):
                    right_pins.append(p)
                elif p.side.value in ("left", "bottom"):
                    left_pins.append(p)
            if not left_pins and not right_pins:
                left_pins = fp.pins[: len(fp.pins) // 2]
                right_pins = fp.pins[len(fp.pins) // 2 :]

            # Sort pins on IC sides so Power pins are placed at the top and Ground pins at the bottom
            def _pin_sort_key(p: PinModel) -> int:
                net = pin_to_net.get((fp.name, p.name), "").upper()
                if net in POWER_NET_NAMES:
                    return 0
                if net in GROUND_NET_NAMES:
                    return 2
                return 1

            left_pins.sort(key=_pin_sort_key)
            right_pins.sort(key=_pin_sort_key)

            mpn = getattr(fp, "mpn", None)
            has_mpn = bool(mpn)
            header_offset = 18.0 if has_mpn else 15.0
            max_pin_rows = max(len(left_pins), len(right_pins), 2)
            ch = max(34.0, header_offset + (max_pin_rows - 1) * pin_pitch + 6.0)
            cy = row_top_y - ch
            comp_boxes.append((cx, cy, cw, ch))

            fp_name_upper = fp.name.upper()
            fp_pkg_upper = fp.package.upper()

            # 1. Resistor standard symbol (if in main_fps)
            if fp_name_upper.startswith("R") or "RES" in fp_pkg_upper:
                ym = cy + ch / 2.0
                x_mid = cx + cw / 2.0
                ax.text(
                    x_mid,
                    cy + ch - 5.0,
                    fp.name,
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=3,
                )
                label_val = mpn or (fp.label.text if fp.label else fp.package)
                ax.text(
                    x_mid,
                    cy + ch - 10.5,
                    str(label_val),
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="#0369a1",
                    zorder=3,
                )

                # Leads and zig-zag
                p1 = fp.pins[0] if fp.pins else None
                p2 = fp.pins[1] if len(fp.pins) > 1 else None
                stub1 = STUB_SIGNAL_MM
                stub2 = STUB_SIGNAL_MM
                if p1:
                    n1 = pin_to_net.get((fp.name, p1.name), "").upper()
                    if (fp.name, p1.name) not in wired_pins:
                        stub1 = (
                            STUB_GROUND_MM
                            if n1 in GROUND_NET_NAMES
                            else (STUB_POWER_MM if n1 in POWER_NET_NAMES else STUB_SIGNAL_MM)
                        )
                if p2:
                    n2 = pin_to_net.get((fp.name, p2.name), "").upper()
                    if (fp.name, p2.name) not in wired_pins:
                        stub2 = (
                            STUB_GROUND_MM
                            if n2 in GROUND_NET_NAMES
                            else (STUB_POWER_MM if n2 in POWER_NET_NAMES else STUB_SIGNAL_MM)
                        )

                ax.plot([cx - stub1, x_mid - 10.0], [ym, ym], color="#475569", linewidth=1.2, zorder=2)
                ax.plot([x_mid + 10.0, cx + cw + stub2], [ym, ym], color="#475569", linewidth=1.2, zorder=2)

                zz_x = [
                    x_mid - 10.0,
                    x_mid - 7.5,
                    x_mid - 5.0,
                    x_mid - 2.5,
                    x_mid,
                    x_mid + 2.5,
                    x_mid + 5.0,
                    x_mid + 7.5,
                    x_mid + 10.0,
                ]
                zz_y = [ym, ym + 3.0, ym - 3.0, ym + 3.0, ym - 3.0, ym + 3.0, ym - 3.0, ym + 3.0, ym]
                ax.plot(zz_x, zz_y, color="#334155", linewidth=1.5, zorder=2)

                if p1:
                    px1 = cx - stub1
                    sheet_pin_coords[(fp.name, p1.name)] = (px1, ym)
                    ax.plot(px1, ym, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                if p2:
                    px2 = cx + cw + stub2
                    sheet_pin_coords[(fp.name, p2.name)] = (px2, ym)
                    ax.plot(px2, ym, marker="o", markersize=2.5, color="#0284c7", zorder=3)

            # 2. Capacitor standard symbol (if in main_fps)
            elif fp_name_upper.startswith("C") or "CAP" in fp_pkg_upper:
                ym = cy + ch / 2.0
                x_mid = cx + cw / 2.0
                ax.text(
                    x_mid,
                    cy + ch - 5.0,
                    fp.name,
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=3,
                )
                label_val = mpn or (fp.label.text if fp.label else fp.package)
                ax.text(
                    x_mid,
                    cy + ch - 10.5,
                    str(label_val),
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="#0369a1",
                    zorder=3,
                )

                p1 = fp.pins[0] if fp.pins else None
                p2 = fp.pins[1] if len(fp.pins) > 1 else None
                stub1 = STUB_SIGNAL_MM
                stub2 = STUB_SIGNAL_MM
                if p1:
                    n1 = pin_to_net.get((fp.name, p1.name), "").upper()
                    if (fp.name, p1.name) not in wired_pins:
                        stub1 = (
                            STUB_GROUND_MM
                            if n1 in GROUND_NET_NAMES
                            else (STUB_POWER_MM if n1 in POWER_NET_NAMES else STUB_SIGNAL_MM)
                        )
                if p2:
                    n2 = pin_to_net.get((fp.name, p2.name), "").upper()
                    if (fp.name, p2.name) not in wired_pins:
                        stub2 = (
                            STUB_GROUND_MM
                            if n2 in GROUND_NET_NAMES
                            else (STUB_POWER_MM if n2 in POWER_NET_NAMES else STUB_SIGNAL_MM)
                        )

                ax.plot([cx - stub1, x_mid - 2.2], [ym, ym], color="#475569", linewidth=1.2, zorder=2)
                ax.plot([x_mid + 2.2, cx + cw + stub2], [ym, ym], color="#475569", linewidth=1.2, zorder=2)

                plate_h = 7.5
                ax.plot(
                    [x_mid - 2.2, x_mid - 2.2], [ym - plate_h, ym + plate_h], color="#334155", linewidth=2.0, zorder=2
                )
                ax.plot(
                    [x_mid + 2.2, x_mid + 2.2], [ym - plate_h, ym + plate_h], color="#334155", linewidth=2.0, zorder=2
                )

                if p1:
                    px1 = cx - stub1
                    sheet_pin_coords[(fp.name, p1.name)] = (px1, ym)
                    ax.plot(px1, ym, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                if p2:
                    px2 = cx + cw + stub2
                    sheet_pin_coords[(fp.name, p2.name)] = (px2, ym)
                    ax.plot(px2, ym, marker="o", markersize=2.5, color="#0284c7", zorder=3)

            # 3. Transistor standard symbol (MOSFET / BJT)
            elif fp_name_upper.startswith("Q"):
                ym = cy + ch / 2.0
                x_mid = cx + cw / 2.0
                ax.text(
                    x_mid,
                    cy + ch - 4.5,
                    fp.name,
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=3,
                )
                label_val = mpn or (fp.label.text if fp.label else fp.package)
                ax.text(
                    x_mid,
                    cy + ch - 9.5,
                    str(label_val),
                    ha="center",
                    va="center",
                    fontsize=6.0,
                    color="#0369a1",
                    zorder=3,
                )

                pin_g = next(
                    (p for p in fp.pins if p.name.upper() in ("G", "GATE", "1")), fp.pins[0] if fp.pins else None
                )
                pin_d = next(
                    (p for p in fp.pins if p.name.upper() in ("D", "DRAIN", "3")),
                    fp.pins[1] if len(fp.pins) > 1 else None,
                )
                pin_s = next(
                    (p for p in fp.pins if p.name.upper() in ("S", "SOURCE", "2")),
                    fp.pins[2] if len(fp.pins) > 2 else None,
                )

                stub_g = STUB_SIGNAL_MM
                stub_d = STUB_SIGNAL_MM
                stub_s = STUB_GROUND_MM

                # Gate bar and lead
                ax.plot([cx - stub_g, x_mid - 3.5], [ym - 2.0, ym - 2.0], color="#475569", linewidth=1.2, zorder=2)
                ax.plot([x_mid - 3.5, x_mid - 3.5], [ym - 7.0, ym + 4.0], color="#334155", linewidth=2.0, zorder=2)

                # Channel bar
                ax.plot([x_mid - 1.2, x_mid - 1.2], [ym - 8.0, ym + 6.0], color="#334155", linewidth=2.4, zorder=2)

                # Drain lead
                ax.plot(
                    [x_mid - 1.2, x_mid + 4.5, cx + cw + stub_d],
                    [ym + 5.0, ym + 5.0, ym + 5.0],
                    color="#475569",
                    linewidth=1.2,
                    zorder=2,
                )
                # Source lead
                ax.plot(
                    [x_mid - 1.2, x_mid + 4.5, cx + cw + stub_s],
                    [ym - 5.0, ym - 5.0, ym - 5.0],
                    color="#475569",
                    linewidth=1.2,
                    zorder=2,
                )
                # Source arrow
                ax.annotate(
                    "",
                    xy=(x_mid - 1.2, ym - 5.0),
                    xytext=(x_mid + 3.0, ym - 5.0),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.2),
                )

                if pin_g:
                    sheet_pin_coords[(fp.name, pin_g.name)] = (cx - stub_g, ym - 2.0)
                    ax.plot(cx - stub_g, ym - 2.0, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                if pin_d:
                    sheet_pin_coords[(fp.name, pin_d.name)] = (cx + cw + stub_d, ym + 5.0)
                    ax.plot(cx + cw + stub_d, ym + 5.0, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                if pin_s:
                    sheet_pin_coords[(fp.name, pin_s.name)] = (cx + cw + stub_s, ym - 5.0)
                    ax.plot(cx + cw + stub_s, ym - 5.0, marker="o", markersize=2.5, color="#0284c7", zorder=3)

            # 4. Standard IC Body Box & Pins
            else:
                ax.add_patch(
                    patches.Rectangle(
                        (cx, cy), cw, ch, facecolor="#ffffff", edgecolor="#334155", linewidth=1.5, zorder=2
                    )
                )
                ax.text(
                    cx + cw / 2.0,
                    cy + ch - 4.2,
                    fp.name,
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    fontweight="bold",
                    color="#0f172a",
                    zorder=3,
                )
                if mpn:
                    ax.text(
                        cx + cw / 2.0,
                        cy + ch - 8.0,
                        str(mpn),
                        ha="center",
                        va="center",
                        fontsize=5.8,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=3,
                    )
                    ax.text(
                        cx + cw / 2.0,
                        cy + ch - 11.5,
                        str(fp.package),
                        ha="center",
                        va="center",
                        fontsize=5.5,
                        color="#64748b",
                        zorder=3,
                    )
                    divider_y = cy + ch - 13.8
                else:
                    val = fp.label.text if fp.label and fp.label.text != fp.name else fp.package
                    ax.text(
                        cx + cw / 2.0,
                        cy + ch - 8.5,
                        str(val),
                        ha="center",
                        va="center",
                        fontsize=6.5,
                        color="#64748b",
                        zorder=3,
                    )
                    divider_y = cy + ch - 11.5

                ax.plot([cx + 2.5, cx + cw - 2.5], [divider_y, divider_y], color="#e2e8f0", linewidth=0.8, zorder=3)

                # Left Pins
                for p_idx, p in enumerate(left_pins):
                    py = cy + ch - header_offset - (p_idx * pin_pitch)
                    pair = (fp.name, p.name)
                    sig_name = pin_to_net.get(pair, "")
                    net_u = sig_name.upper()

                    if pair in wired_pins:
                        pin_stub = STUB_SIGNAL_MM
                    elif net_u in GROUND_NET_NAMES:
                        pin_stub = STUB_GROUND_MM
                    elif net_u in POWER_NET_NAMES:
                        pin_stub = STUB_POWER_MM
                    else:
                        pin_stub = STUB_SIGNAL_MM

                    px = cx - pin_stub
                    sheet_pin_coords[pair] = (px, py)

                    # Stub line and terminal dot
                    ax.plot([cx, px], [py, py], color="#475569", linewidth=1.0, zorder=2)
                    ax.plot(px, py, marker="o", markersize=2.5, color="#0284c7", zorder=3)

                    # Signal name inside IC box
                    pin_display = sig_name if sig_name else (p.label if p.label and p.label != p.name else p.name)
                    ax.text(cx + 1.5, py, pin_display, ha="left", va="center", fontsize=6.5, color="#1e293b", zorder=3)

                    # Pin number next to IC box (only if distinct from pin_display)
                    if p.name != pin_display:
                        ax.text(
                            cx - PIN_NUMBER_OFFSET_MM,
                            py + 1.2,
                            p.name,
                            ha="center",
                            va="bottom",
                            fontsize=5.0,
                            color="#64748b",
                            zorder=3,
                        )

                # Right Pins
                for p_idx, p in enumerate(right_pins):
                    py = cy + ch - header_offset - (p_idx * pin_pitch)
                    pair = (fp.name, p.name)
                    sig_name = pin_to_net.get(pair, "")
                    net_u = sig_name.upper()

                    if pair in wired_pins:
                        pin_stub = STUB_SIGNAL_MM
                    elif net_u in GROUND_NET_NAMES:
                        pin_stub = STUB_GROUND_MM
                    elif net_u in POWER_NET_NAMES:
                        pin_stub = STUB_POWER_MM
                    else:
                        pin_stub = STUB_SIGNAL_MM

                    px = cx + cw + pin_stub
                    sheet_pin_coords[pair] = (px, py)

                    # Stub line and terminal dot
                    ax.plot([cx + cw, px], [py, py], color="#475569", linewidth=1.0, zorder=2)
                    ax.plot(px, py, marker="o", markersize=2.5, color="#0284c7", zorder=3)

                    # Signal name inside IC box
                    pin_display = sig_name if sig_name else (p.label if p.label and p.label != p.name else p.name)
                    ax.text(
                        cx + cw - 1.5,
                        py,
                        pin_display,
                        ha="right",
                        va="center",
                        fontsize=6.5,
                        color="#1e293b",
                        zorder=3,
                    )

                    # Pin number next to IC box (only if distinct from pin_display)
                    if p.name != pin_display:
                        ax.text(
                            cx + cw + PIN_NUMBER_OFFSET_MM,
                            py + 1.2,
                            p.name,
                            ha="center",
                            va="bottom",
                            fontsize=5.0,
                            color="#64748b",
                            zorder=3,
                        )

        # Draw wire routes between facing components
        h_segments: List[Tuple[float, float, float, str, str]] = []  # (x_start, x_end, y, net_name, color)
        v_segments: List[Tuple[float, float, float, str, str]] = []  # (x, y_start, y_end, net_name, color)
        wire_labels: List[Tuple[float, float, str]] = []

        # Group direct wire pairs by adjacent column transitions
        trans_map: Dict[Tuple[str, str], List[Tuple[Tuple[str, str], Tuple[str, str], NetModel]]] = {}
        for pair1, pair2, net in direct_wire_pairs:
            trans_map.setdefault((pair1[0], pair2[0]), []).append((pair1, pair2, net))

        for (c1, c2), pairs in trans_map.items():
            dogleg_pairs = [p for p in pairs if abs(sheet_pin_coords[p[0]][1] - sheet_pin_coords[p[1]][1]) >= 0.1]
            num_doglegs = len(dogleg_pairs)

            has_pullups_in_channel = any(
                any(p[2].name == pin_to_net.get((fp.name, pin.name)) for pin in fp.pins for p in pairs)
                for fp in pullup_resistors
            )

            dogleg_idx = 0
            for pair1, pair2, net in pairs:
                p1 = sheet_pin_coords[pair1]
                p2 = sheet_pin_coords[pair2]
                col = net.color if hasattr(net, "color") and net.color else "#2563eb"

                if abs(p1[1] - p2[1]) < 0.1:
                    # Straight horizontal wire
                    h_segments.append((p1[0], p2[0], p1[1], net.name, col))
                    if not has_pullups_in_channel:
                        wire_labels.append(((p1[0] + p2[0]) / 2.0, p1[1] + 1.2, net.name))
                else:
                    # Staggered vertical corridor
                    if has_pullups_in_channel:
                        x_v = (p2[0] - 14.0) + dogleg_idx * 2.0
                    else:
                        mid_base = (p1[0] + p2[0]) / 2.0
                        offset = (dogleg_idx - (num_doglegs - 1) / 2.0) * 8.0 if num_doglegs > 1 else 0.0
                        x_v = mid_base + offset
                    dogleg_idx += 1

                    h_segments.append((p1[0], x_v, p1[1], net.name, col))
                    v_segments.append((x_v, p1[1], p2[1], net.name, col))
                    h_segments.append((x_v, p2[0], p2[1], net.name, col))
                    if not has_pullups_in_channel:
                        wire_labels.append((p1[0] + 6.0, p1[1] + 1.2, net.name))

        # Render all horizontal wire segments
        for x_start, x_end, y, net_name, col in h_segments:
            ax.plot([x_start, x_end], [y, y], color=col, linewidth=1.2, zorder=2)

        # Render all vertical wire segments with jumper bridge loops at crossings
        for x_v, y_start, y_end, net_name, col in v_segments:
            self._draw_vertical_wire_with_jumpers(
                ax,
                x_v=x_v,
                y_start=y_start,
                y_end=y_end,
                col=col,
                h_wire_segments=h_segments,
                net_name=net_name,
            )

        # Render wire labels
        for lx, ly, l_name in wire_labels:
            ax.text(
                lx,
                ly,
                l_name,
                ha="center",
                va="bottom",
                fontsize=6.5,
                fontweight="bold",
                color="#0369a1",
                zorder=4,
            )

        # Draw vertical passives (pullup/pulldown resistors and shunt caps) first so their pin connections are wired
        vertical_passives = pullup_resistors + shunt_caps
        if vertical_passives:
            self._draw_pullup_resistors(
                ax=ax,
                pullups=vertical_passives,
                pin_to_net=pin_to_net,
                h_wire_segments=h_segments,
                sheet_pin_coords=sheet_pin_coords,
                wired_pins=wired_pins,
                pin_side_map=pin_side_map,
            )

        # Draw power/ground symbols and net labels for all UNWIRED pins
        handled_pins: set[Tuple[str, str]] = set()

        # Group multiple GND pins on the same component & side to avoid overlapping GND symbols
        for fp in main_fps:
            for side_val in ("left", "right"):
                comp_gnd_pins = [
                    p
                    for p in sheet_pin_coords
                    if p[0] == fp.name
                    and p not in wired_pins
                    and pin_side_map.get(p) == side_val
                    and pin_to_net.get(p, "").upper() in GROUND_NET_NAMES
                ]
                if len(comp_gnd_pins) >= 2:
                    px_gnd = sheet_pin_coords[comp_gnd_pins[0]][0]
                    py_vals = [sheet_pin_coords[p][1] for p in comp_gnd_pins]
                    py_min = min(py_vals)
                    py_max = max(py_vals)
                    y_drop = py_min - 4.0
                    # Draw vertical trunk connecting all ground pins on this side
                    ax.plot([px_gnd, px_gnd], [py_max, y_drop], color="#475569", linewidth=1.2, zorder=2)
                    for p in comp_gnd_pins:
                        ax.plot(px_gnd, sheet_pin_coords[p][1], marker="o", markersize=2.0, color="#475569", zorder=3)
                        handled_pins.add(p)
                    # Single 3-bar GND symbol at bottom of trunk
                    ax.plot([px_gnd - 2.8, px_gnd + 2.8], [y_drop, y_drop], color="#475569", linewidth=1.4, zorder=2)
                    ax.plot(
                        [px_gnd - 1.8, px_gnd + 1.8],
                        [y_drop - 1.2, y_drop - 1.2],
                        color="#475569",
                        linewidth=1.2,
                        zorder=2,
                    )
                    ax.plot(
                        [px_gnd - 0.8, px_gnd + 0.8],
                        [y_drop - 2.4, y_drop - 2.4],
                        color="#475569",
                        linewidth=1.0,
                        zorder=2,
                    )
                    ax.text(
                        px_gnd,
                        y_drop - 3.8,
                        "GND",
                        ha="center",
                        va="top",
                        fontsize=5.5,
                        fontweight="bold",
                        color="#475569",
                        zorder=3,
                    )

                # Group multiple pins sharing the same POWER net on the same component & side (e.g. U3 VIN & EN)
                power_pin_map: Dict[str, List[Tuple[str, str]]] = {}
                for p in sheet_pin_coords:
                    if p[0] == fp.name and p not in wired_pins and pin_side_map.get(p) == side_val:
                        n = pin_to_net.get(p, "")
                        if n.upper() in POWER_NET_NAMES:
                            power_pin_map.setdefault(n, []).append(p)
                for pwr_net, comp_pwr_pins in power_pin_map.items():
                    if len(comp_pwr_pins) >= 2:
                        px_pwr = sheet_pin_coords[comp_pwr_pins[0]][0]
                        py_vals = [sheet_pin_coords[p][1] for p in comp_pwr_pins]
                        py_min = min(py_vals)
                        py_max = max(py_vals)
                        y_arrow = py_max + 4.0
                        ax.plot([px_pwr, px_pwr], [py_min, y_arrow], color="#dc2626", linewidth=1.2, zorder=2)
                        for p in comp_pwr_pins:
                            ax.plot(
                                px_pwr, sheet_pin_coords[p][1], marker="o", markersize=2.0, color="#dc2626", zorder=3
                            )
                            handled_pins.add(p)
                        ax.plot(
                            [px_pwr - 2.5, px_pwr, px_pwr + 2.5],
                            [y_arrow - 1.5, y_arrow + 1.0, y_arrow - 1.5],
                            color="#dc2626",
                            linewidth=1.2,
                            zorder=2,
                        )
                        ax.text(
                            px_pwr,
                            y_arrow + 2.2,
                            pwr_net,
                            ha="center",
                            va="bottom",
                            fontsize=5.8,
                            fontweight="bold",
                            color="#dc2626",
                            zorder=4,
                        )

        for pair, (px, py) in sheet_pin_coords.items():
            if pair in wired_pins or pair in handled_pins:
                continue
            net_name = pin_to_net.get(pair)
            if not net_name:
                continue

            side = pin_side_map.get(pair, "left")
            net_upper = net_name.upper()

            has_pin_above = any(
                p2 != pair
                and p2[0] == pair[0]
                and pin_side_map.get(p2) == side
                and abs(sheet_pin_coords[p2][0] - px) < 4.0
                and sheet_pin_coords[p2][1] > py
                and sheet_pin_coords[p2][1] - py < 8.0
                for p2 in sheet_pin_coords
            )
            has_pin_below = any(
                p2 != pair
                and p2[0] == pair[0]
                and pin_side_map.get(p2) == side
                and abs(sheet_pin_coords[p2][0] - px) < 4.0
                and sheet_pin_coords[p2][1] < py
                and py - sheet_pin_coords[p2][1] < 8.0
                for p2 in sheet_pin_coords
            )
            has_wire_above = any(
                0.1 < seg[2] - py < 10.0 and min(seg[0], seg[1]) - 1.0 <= px <= max(seg[0], seg[1]) + 1.0
                for seg in h_segments
            )
            has_wire_below = any(
                0.1 < py - seg[2] < 10.0 and min(seg[0], seg[1]) - 1.0 <= px <= max(seg[0], seg[1]) + 1.0
                for seg in h_segments
            )

            # GND symbol
            if net_upper in GROUND_NET_NAMES:
                # Always prefer standard vertical 3-bar hanging DOWN under components and traces
                y_drop = py - 3.0
                if has_pin_below or has_wire_below:
                    # Drop down below the component and any nearby wires in the channel
                    comp_box = next(
                        (b for b in comp_boxes if abs(b[0] - px) < 15.0 or (b[0] <= px <= b[0] + b[2])), None
                    )
                    comp_bottom = comp_box[1] if comp_box else py - 10.0
                    channel_wires = [
                        seg[2] for seg in h_segments if min(seg[0], seg[1]) - 2.0 <= px <= max(seg[0], seg[1]) + 2.0
                    ]
                    min_wire_y = min(channel_wires) if channel_wires else py
                    y_drop = min(comp_bottom - 2.0, min_wire_y - 3.0, py - 4.0)

                # Vertical connection lead down to ground bar
                ax.plot([px, px], [py, y_drop], color="#475569", linewidth=1.2, zorder=2)
                # Standard vertical 3-bar hanging DOWN
                ax.plot([px - 2.8, px + 2.8], [y_drop, y_drop], color="#475569", linewidth=1.4, zorder=2)
                ax.plot([px - 1.8, px + 1.8], [y_drop - 1.2, y_drop - 1.2], color="#475569", linewidth=1.2, zorder=2)
                ax.plot([px - 0.8, px + 0.8], [y_drop - 2.4, y_drop - 2.4], color="#475569", linewidth=1.0, zorder=2)
                ax.text(
                    px,
                    y_drop - 3.8,
                    "GND",
                    ha="center",
                    va="top",
                    fontsize=5.5,
                    fontweight="bold",
                    color="#475569",
                    zorder=3,
                )

            # Power symbol
            elif net_upper in POWER_NET_NAMES:
                if not has_pin_above and not has_wire_above:
                    # Standard upward arrow
                    ax.plot([px, px], [py, py + 3.0], color="#dc2626", linewidth=1.2, zorder=2)
                    ax.plot(
                        [px - 2.5, px, px + 2.5],
                        [py + 2.0, py + 4.5, py + 2.0],
                        color="#dc2626",
                        linewidth=1.2,
                        zorder=2,
                    )
                    ax.text(
                        px,
                        py + 5.5,
                        net_name,
                        ha="center",
                        va="bottom",
                        fontsize=5.8,
                        fontweight="bold",
                        color="#dc2626",
                        zorder=3,
                    )
                else:
                    # Horizontal power arrow pointing outward away from component
                    if side == "left":
                        ax.plot([px, px - 2.5], [py, py], color="#dc2626", linewidth=1.2, zorder=2)
                        ax.plot(
                            [px - 0.5, px - 3.0, px - 0.5],
                            [py + 2.2, py, py - 2.2],
                            color="#dc2626",
                            linewidth=1.2,
                            zorder=2,
                        )
                        ax.text(
                            px - 4.5,
                            py,
                            net_name,
                            ha="right",
                            va="center",
                            fontsize=5.8,
                            fontweight="bold",
                            color="#dc2626",
                            zorder=3,
                        )
                    else:
                        ax.plot([px, px + 2.5], [py, py], color="#dc2626", linewidth=1.2, zorder=2)
                        ax.plot(
                            [px + 0.5, px + 3.0, px + 0.5],
                            [py + 2.2, py, py - 2.2],
                            color="#dc2626",
                            linewidth=1.2,
                            zorder=2,
                        )
                        ax.text(
                            px + 4.5,
                            py,
                            net_name,
                            ha="left",
                            va="center",
                            fontsize=5.8,
                            fontweight="bold",
                            color="#dc2626",
                            zorder=3,
                        )

            # Signal net flag / label
            else:
                if side == "left":
                    ax.text(
                        px - 1.5,
                        py,
                        net_name,
                        ha="right",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=3,
                    )
                else:
                    ax.text(
                        px + 1.5,
                        py,
                        net_name,
                        ha="left",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=3,
                    )

        # Check if truth table is present on this sheet
        has_truth_table = any(
            (getattr(fp, "truth_table", None) is not None or fp.name.upper().startswith("Q")) for fp in sheet_fps
        )

        # Draw Decoupling Capacitor Bank
        if decoupling_caps:
            n_caps = len(decoupling_caps)
            total_w = (n_caps - 1) * 28.0
            if has_truth_table:
                cap_base_x = 35.0
            elif cols_override == 2:
                cap_base_x = col_x_positions[0]
            else:
                cap_base_x = max(35.0, page_center_x - (total_w / 2.0))
            self._draw_decoupling_cap_bank(
                ax=ax,
                caps=decoupling_caps,
                pin_to_net=pin_to_net,
                base_x=cap_base_x,
                base_y=bottom_cards_y,
            )

        # Draw Truth Tables for discrete component networks (e.g. transistor networks)
        for fp in sheet_fps:
            tt = getattr(fp, "truth_table", None)
            is_transistor = fp.name.upper().startswith("Q")
            if tt is None and is_transistor:
                tt = self._generate_default_transistor_truth_table(fp, pin_to_net)

            if tt:
                tt_card_w = 125.0
                if decoupling_caps:
                    tt_x = 135.0
                else:
                    tt_x = 118.0
                    c_idx = next((i for i, f in enumerate(main_fps) if f.name == fp.name), None)
                    if c_idx is not None:
                        comp_cx = col_x_positions[c_idx]
                        tt_x = max(116.0, min(145.0, comp_cx + cw / 2.0 - tt_card_w / 2.0 + 20.0))
                self._draw_truth_table(ax=ax, fp=fp, tt=tt, base_x=tt_x, base_y=bottom_cards_y, card_w=tt_card_w)

        pdf.savefig(fig)
