"""Symbol and feature bounding box calculation for schematic sheets."""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from model.pcb import PCBConfig, SchematicLayoutModel
from model.wiring import FootprintModel, NetModel, Wiring
from provider.schematic.constants import (
    GROUND_NET_NAMES,
    PIN_PITCH_MM,
    POWER_NET_NAMES,
    STUB_GROUND_MM,
    STUB_POWER_MM,
    STUB_SIGNAL_MM,
    _SchematicSheetPlan,
)
from provider.schematic.passives import SchematicPassiveClassifier


class SchematicBoundingBoxCalculator:
    """Calculates symbol and feature bounding boxes across schematic sheets."""

    @classmethod
    def compute_symbol_bounding_boxes(
        cls,
        wiring: Optional[Wiring],
        config: Optional[PCBConfig],
        sheet_plans: List[_SchematicSheetPlan],
    ) -> Dict[int, List[Tuple[float, float, float, float, str]]]:
        """Compute exact bounding boxes (cx, cy, width, height, name) for all symbols on each sheet.

        Args:
            wiring: Wiring model or None.
            config: PCB configuration or None.
            sheet_plans: Planned schematic sheets.

        Returns:
            Dictionary mapping sheet_idx (1-indexed) to list of (cx, cy, width, height, name) bounding boxes.
        """
        if not wiring or not getattr(wiring, "footprints", None) or not sheet_plans:
            return {}

        all_nets = getattr(wiring, "nets", []) or []
        pin_to_net: Dict[Tuple[str, str], str] = {}
        for net in all_nets:
            for pair in net.pins:
                pin_to_net[pair] = net.name

        sheet_boxes: Dict[int, List[Tuple[float, float, float, float, str]]] = {}

        for plan in sheet_plans:
            sheet_fps = plan.footprints
            boxes: List[Tuple[float, float, float, float, str]] = []

            decoupling_caps, pullup_resistors, shunt_caps, main_fps = SchematicPassiveClassifier.classify_passives(
                sheet_fps, pin_to_net
            )

            num_comps = len(main_fps)
            has_bottom_cards = bool(decoupling_caps) or any(
                getattr(fp, "truth_table", None) is not None or fp.name.upper().startswith("Q") for fp in sheet_fps
            )

            sheet_model = (
                config.schematic_sheets[plan.sheet_idx - 1]
                if (config and config.schematic_sheets and (0 <= (plan.sheet_idx - 1) < len(config.schematic_sheets)))
                else None
            )
            layout = (
                getattr(sheet_model, "layout", None)
                or getattr(config, "schematic_layout", None)
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
            detour_wire_pairs = []
            wired_pins = set()
            for net in all_nets:
                if net.name.upper() in POWER_NET_NAMES or net.name.upper() in GROUND_NET_NAMES:
                    continue
                present_pins = [pair for pair in net.pins if pair in pin_side_map]
                if len(present_pins) >= 2:
                    for i, pair1 in enumerate(present_pins):
                        for pair2 in present_pins[i + 1 :]:
                            if pair1 in wired_pins or pair2 in wired_pins:
                                continue
                            if pair1[0] == pair2[0]:
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
                            else:
                                detour_wire_pairs.append((pair1, pair2, net))
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
                if row_top_y - ch < 18.0:
                    ch = max(34.0, row_top_y - 18.0)
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
                n_caps = len(decoupling_caps)
                pitch_x = 28.0
                total_w = (n_caps - 1) * pitch_x
                card_w = max(total_w + 32.0, 75.0)
                max_card_x = 195.0 - card_w
                target_base_x = max(35.0, page_center_x - total_w / 2.0)
                cap_base_x = max(35.0, min(target_base_x, max_card_x + 12.0))
                card_x = cap_base_x - 12.0
                base_y = 66.0 if has_bottom_cards else 60.0
                y_top = base_y + 16.0
                y_bot = base_y - 12.0
                card_y = y_bot - 12.0
                card_h = (y_top - y_bot) + 26.0
                boxes.append((card_x + card_w / 2.0, card_y + card_h / 2.0, card_w, card_h, "DECOUPLING_CARD"))
                for idx, cap in enumerate(decoupling_caps):
                    boxes.append((cap_base_x + idx * pitch_x, base_y, 14.0, 24.0, cap.name))

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

                comp_stub_counts: Dict[Tuple[str, str], int] = defaultdict(int)
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
                            cand_x = min(265.0, x_end + 14.0 + idx * 16.0)
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
                            side = pin_side_map.get(target_pair, "right" if p_x >= 148.5 else "left")
                            stub_idx = comp_stub_counts[(target_pair[0], side)]
                            comp_stub_counts[(target_pair[0], side)] += 1
                            if side == "right":
                                cand_x = min(265.0, p_x + 14.0 + stub_idx * 16.0)
                            else:
                                cand_x = max(22.0, p_x - 24.0 - stub_idx * 16.0)
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
