"""Orthogonal wire corridor planning, obstacle detour routing, and jumper bridging."""

from typing import Dict, List, Optional, Tuple

import matplotlib.axes

from model.pcb import PCBConfig, SchematicLayoutModel
from model.wiring import FootprintModel, NetModel, Wiring
from provider.schematic.constants import (
    GROUND_NET_NAMES,
    PIN_PITCH_MM,
    POWER_NET_NAMES,
    STUB_SIGNAL_MM,
    _SchematicSheetPlan,
    partition_component_pins,
)
from provider.schematic.jumper import draw_vertical_wire_with_jumpers
from provider.schematic.passives import SchematicPassiveClassifier


class SchematicWireSegmentPlanner:
    """Plans orthogonal wire corridors, doglegs, component detours, and jumper bridges."""

    @staticmethod
    def draw_vertical_wire_with_jumpers(
        ax: matplotlib.axes.Axes,
        x_v: float,
        y_start: float,
        y_end: float,
        col: str,
        h_wire_segments: List[Tuple[float, float, float, str, str]],
        net_name: str = "",
    ) -> None:
        """Render a vertical wire segment with semicircular jumper bridge loops over crossing horizontal wires."""
        draw_vertical_wire_with_jumpers(
            ax=ax,
            x_v=x_v,
            y_start=y_start,
            y_end=y_end,
            col=col,
            h_wire_segments=h_wire_segments,
            net_name=net_name,
        )

    @classmethod
    def compute_sheet_wire_segments_for_plan(
        cls,
        sheet_plan: _SchematicSheetPlan,
        all_nets: List[NetModel],
        config: Optional[PCBConfig] = None,
    ) -> Tuple[
        List[Tuple[float, float, float, str, str]],
        List[Tuple[float, float, float, str, str]],
        List[Tuple[float, float, str]],
    ]:
        """Compute exact wire routes and labels for a single schematic sheet plan."""
        pin_to_net: Dict[Tuple[str, str], str] = {}
        for net in all_nets:
            for pair in net.pins:
                pin_to_net[pair] = net.name

        sheet_fps = sheet_plan.footprints
        sheet_model = (
            config.schematic_sheets[sheet_plan.sheet_idx - 1]
            if (config and config.schematic_sheets and (0 <= (sheet_plan.sheet_idx - 1) < len(config.schematic_sheets)))
            else None
        )
        layout = (
            getattr(sheet_model, "layout", None) or getattr(config, "schematic_layout", None) or SchematicLayoutModel()
        )
        grid_positions = getattr(layout, "grid_positions", {}) or {}

        decoupling_caps, pullup_resistors, shunt_caps, main_fps = SchematicPassiveClassifier.classify_passives(
            sheet_fps, pin_to_net, grid_positions=grid_positions
        )

        num_comps = len(main_fps)
        pin_pitch = PIN_PITCH_MM
        has_bottom_cards = bool(decoupling_caps) or any(
            getattr(fp, "truth_table", None) is not None or fp.name.upper().startswith("Q") for fp in sheet_fps
        )

        page_center_x = layout.sheet_center_x
        if getattr(layout, "top_row_y", None) is not None:
            top_row_y = layout.top_row_y
        elif has_bottom_cards:
            top_row_y = 158.0
        else:
            top_row_y = 138.0

        cols_override = getattr(layout, "cols_per_row", None)

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
        sheet_pin_breakouts = getattr(sheet_model, "pin_breakouts", {}) or {}
        pin_side_map: Dict[Tuple[str, str], str] = {}
        for fp in main_fps:
            comp_side_overrides = sheet_pin_sides.get(fp.name, {})
            has_breakout = bool(sheet_pin_breakouts.get(fp.name))
            left_p, right_p = partition_component_pins(
                fp=fp,
                comp_side_overrides=comp_side_overrides,
                pin_to_net=pin_to_net,
                has_breakout=has_breakout,
            )
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

        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]] = {}
        comp_boxes: List[Tuple[float, float, float, float]] = []

        for c_idx, fp in enumerate(main_fps):
            cx = col_x_positions[c_idx]
            row_top_y = col_y_positions[c_idx]

            comp_side_overrides = sheet_pin_sides.get(fp.name, {})
            has_breakout = bool(sheet_pin_breakouts.get(fp.name))
            left_pins, right_pins = partition_component_pins(
                fp=fp,
                comp_side_overrides=comp_side_overrides,
                pin_to_net=pin_to_net,
                has_breakout=has_breakout,
            )

            header_offset = 18.0 if getattr(fp, "mpn", None) else 15.0
            max_pin_rows = max(len(left_pins), len(right_pins), 2)
            ch = max(34.0, header_offset + (max_pin_rows - 1) * pin_pitch + 6.0)
            if row_top_y - ch < 18.0:
                ch = max(34.0, row_top_y - 18.0)
                pin_pitch = max(2.5, (ch - header_offset - 6.0) / max(1, max_pin_rows - 1))
            cy = row_top_y - ch
            comp_boxes.append((cx, cy, cw, ch))

            fp_name_upper = fp.name.upper()
            fp_pkg_upper = fp.package.upper()

            if (
                fp_name_upper.startswith("R")
                or "RES" in fp_pkg_upper
                or fp_name_upper.startswith("C")
                or "CAP" in fp_pkg_upper
            ):
                ym = cy + ch / 2.0
                p1 = fp.pins[0] if fp.pins else None
                p2 = fp.pins[1] if len(fp.pins) > 1 else None
                stub1 = STUB_SIGNAL_MM
                stub2 = STUB_SIGNAL_MM
                if p1:
                    sheet_pin_coords[(fp.name, p1.name)] = (cx - stub1, ym)
                if p2:
                    sheet_pin_coords[(fp.name, p2.name)] = (cx + cw + stub2, ym)
            elif fp_name_upper.startswith("Q"):
                ym = cy + ch / 2.0
                gate_pin = next(
                    (p for p in fp.pins if p.name in ("1", "G", "B", "GATE", "BASE")), fp.pins[0] if fp.pins else None
                )
                drain_pin = next(
                    (p for p in fp.pins if p.name in ("3", "D", "C", "DRAIN", "COLLECTOR")),
                    fp.pins[1] if len(fp.pins) > 1 else None,
                )
                source_pin = next(
                    (p for p in fp.pins if p.name in ("2", "S", "E", "SOURCE", "EMITTER")),
                    fp.pins[2] if len(fp.pins) > 2 else None,
                )
                if gate_pin:
                    sheet_pin_coords[(fp.name, gate_pin.name)] = (cx - STUB_SIGNAL_MM, ym)
                if drain_pin:
                    sheet_pin_coords[(fp.name, drain_pin.name)] = (cx + cw + STUB_SIGNAL_MM, ym + 5.0)
                if source_pin:
                    sheet_pin_coords[(fp.name, source_pin.name)] = (cx + cw + STUB_SIGNAL_MM, ym - 5.0)
            else:
                for p_idx, p in enumerate(left_pins):
                    sheet_pin_coords[(fp.name, p.name)] = (
                        cx - STUB_SIGNAL_MM,
                        cy + ch - header_offset - (p_idx * pin_pitch),
                    )
                for p_idx, p in enumerate(right_pins):
                    sheet_pin_coords[(fp.name, p.name)] = (
                        cx + cw + STUB_SIGNAL_MM,
                        cy + ch - header_offset - (p_idx * pin_pitch),
                    )

        h_segments: List[Tuple[float, float, float, str, str]] = []
        v_segments: List[Tuple[float, float, float, str, str]] = []
        wire_labels: List[Tuple[float, float, str]] = []

        # Route direct adjacent-column wires
        cls._route_direct_wire_pairs(
            direct_wire_pairs=direct_wire_pairs,
            sheet_pin_coords=sheet_pin_coords,
            pin_to_net=pin_to_net,
            pullup_resistors=pullup_resistors,
            h_segments=h_segments,
            v_segments=v_segments,
            wire_labels=wire_labels,
        )

        # Route on-sheet detour wires around components
        comp_box_dict = {fp.name: comp_boxes[c_idx] for c_idx, fp in enumerate(main_fps)}
        cls._route_detour_wire_pairs(
            detour_wire_pairs=detour_wire_pairs,
            sheet_pin_coords=sheet_pin_coords,
            pin_side_map=pin_side_map,
            comp_box_dict=comp_box_dict,
            h_segments=h_segments,
            v_segments=v_segments,
            wire_labels=wire_labels,
        )

        return h_segments, v_segments, wire_labels

    @staticmethod
    def _route_direct_wire_pairs(
        direct_wire_pairs: List[Tuple[Tuple[str, str], Tuple[str, str], NetModel]],
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]],
        pin_to_net: Dict[Tuple[str, str], str],
        pullup_resistors: List[FootprintModel],
        h_segments: List[Tuple[float, float, float, str, str]],
        v_segments: List[Tuple[float, float, float, str, str]],
        wire_labels: List[Tuple[float, float, str]],
    ) -> None:
        """Route horizontal connections and staggered doglegs between adjacent columns."""
        trans_map = {}
        for pair1, pair2, net in direct_wire_pairs:
            trans_map.setdefault((pair1[0], pair2[0]), []).append((pair1, pair2, net))

        for (c1, c2), pairs in trans_map.items():
            dogleg_pairs = [p for p in pairs if abs(sheet_pin_coords[p[0]][1] - sheet_pin_coords[p[1]][1]) >= 0.1]
            num_doglegs = len(dogleg_pairs)

            has_pullups_in_channel = any(
                any(p[2].name == pin_to_net.get((fp.name, pin.name)) for pin in fp.pins for p in pairs)
                for fp in pullup_resistors
            )

            def _dogleg_sort_key(item: Tuple[Tuple[str, str], Tuple[str, str], NetModel]) -> Tuple[int, float]:
                y1 = sheet_pin_coords[item[0]][1]
                y2 = sheet_pin_coords[item[1]][1]
                if y1 > y2:
                    return (0, min(y1, y2))
                else:
                    return (1, -max(y1, y2))

            sorted_doglegs = sorted(dogleg_pairs, key=_dogleg_sort_key)
            dogleg_order = {(p[0], p[1]): idx for idx, p in enumerate(sorted_doglegs)}

            for pair1, pair2, net in pairs:
                p1 = sheet_pin_coords[pair1]
                p2 = sheet_pin_coords[pair2]
                col = net.color if hasattr(net, "color") and net.color else "#2563eb"

                if abs(p1[1] - p2[1]) < 0.1:
                    h_segments.append((min(p1[0], p2[0]), max(p1[0], p2[0]), p1[1], net.name, col))
                    if not has_pullups_in_channel:
                        wire_labels.append(((p1[0] + p2[0]) / 2.0, p1[1] + 1.2, net.name))
                else:
                    d_idx = dogleg_order.get((pair1, pair2), 0)
                    if has_pullups_in_channel:
                        x_v = (p2[0] - 14.0) + d_idx * 2.0
                    else:
                        x_min_v = p1[0] + 10.0
                        x_max_v = p2[0] - 10.0
                        avail = max(4.0, x_max_v - x_min_v)
                        step = min(8.0, max(3.5, avail / (num_doglegs + 1)))
                        total_span = (num_doglegs - 1) * step
                        mid_base = (x_min_v + x_max_v) / 2.0
                        x_v = max(x_min_v, min(x_max_v, mid_base - total_span / 2.0 + d_idx * step))

                    h_segments.append((min(p1[0], x_v), max(p1[0], x_v), p1[1], net.name, col))
                    v_segments.append((x_v, min(p1[1], p2[1]), max(p1[1], p2[1]), net.name, col))
                    h_segments.append((min(x_v, p2[0]), max(x_v, p2[0]), p2[1], net.name, col))
                    if not has_pullups_in_channel:
                        seg1_len = abs(x_v - p1[0])
                        seg2_len = abs(p2[0] - x_v)
                        if seg1_len >= 16.0:
                            wire_labels.append(((p1[0] + x_v) / 2.0, p1[1] + 1.2, net.name))
                        elif seg2_len >= 16.0:
                            wire_labels.append(((x_v + p2[0]) / 2.0, p2[1] + 1.2, net.name))

    @staticmethod
    def _route_detour_wire_pairs(
        detour_wire_pairs: List[Tuple[Tuple[str, str], Tuple[str, str], NetModel]],
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]],
        pin_side_map: Dict[Tuple[str, str], str],
        comp_box_dict: Dict[str, Tuple[float, float, float, float]],
        h_segments: List[Tuple[float, float, float, str, str]],
        v_segments: List[Tuple[float, float, float, str, str]],
        wire_labels: List[Tuple[float, float, str]],
    ) -> None:
        """Route detour wires around intervening components."""
        detour_count_by_channel: Dict[Tuple[str, str], int] = {}

        def _detour_sort_key(item: Tuple[Tuple[str, str], Tuple[str, str], NetModel]) -> Tuple[int, float]:
            pair1, pair2, _ = item
            s1 = pin_side_map[pair1]
            s2 = pin_side_map[pair2]
            p1 = sheet_pin_coords[pair1]
            p2 = sheet_pin_coords[pair2]
            if s1 == "left" and s2 == "left":
                return (0, p1[1])
            elif s1 == "right" and s2 == "right":
                return (1, p2[1])
            else:
                return (2, p1[1])

        sorted_detour_pairs = sorted(detour_wire_pairs, key=_detour_sort_key)
        for pair1, pair2, net in sorted_detour_pairs:
            p1 = sheet_pin_coords[pair1]
            p2 = sheet_pin_coords[pair2]
            c1_name, c2_name = pair1[0], pair2[0]
            s1 = pin_side_map[pair1]
            s2 = pin_side_map[pair2]
            col = net.color if hasattr(net, "color") and net.color else "#2563eb"

            ch_key = (min(c1_name, c2_name), max(c1_name, c2_name))
            d_idx = detour_count_by_channel.get(ch_key, 0)
            detour_count_by_channel[ch_key] = d_idx + 1

            b1 = comp_box_dict[c1_name]
            b2 = comp_box_dict[c2_name]
            min_y_bottom = min(b1[1], b2[1])
            y_detour = min_y_bottom - 8.0 - d_idx * 3.5

            if s1 == "right" and s2 == "right":
                if abs(b1[0] - b2[0]) < 1.0:
                    x_col = max(b1[0] + b1[2] + 6.0 + d_idx * 2.5, max(p1[0], p2[0]) + 3.0)
                    while any(
                        abs(x_col - s[0]) < 0.2 and (min(max(p1[1], p2[1]), s[2]) - max(min(p1[1], p2[1]), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_col += 2.0
                    h_segments.append((min(p1[0], x_col), max(p1[0], x_col), p1[1], net.name, col))
                    v_segments.append((x_col, min(p1[1], p2[1]), max(p1[1], p2[1]), net.name, col))
                    h_segments.append((min(p2[0], x_col), max(p2[0], x_col), p2[1], net.name, col))
                    wire_labels.append((x_col + 1.5, (p1[1] + p2[1]) / 2.0, net.name))
                else:
                    x_drop = b2[0] - 6.0 - d_idx * 2.5
                    while any(
                        abs(x_drop - s[0]) < 0.2
                        and (min(max(p1[1], y_detour), s[2]) - max(min(p1[1], y_detour), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_drop -= 2.0
                    x_rise = max(b2[0] + b2[2] + 6.0 + d_idx * 2.5, p2[0] + 6.0 + d_idx * 2.5)
                    while any(
                        abs(x_rise - s[0]) < 0.2
                        and (min(max(p2[1], y_detour), s[2]) - max(min(p2[1], y_detour), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_rise += 2.0

                    h_segments.append((min(p1[0], x_drop), max(p1[0], x_drop), p1[1], net.name, col))
                    v_segments.append((x_drop, min(p1[1], y_detour), max(p1[1], y_detour), net.name, col))
                    h_segments.append((min(x_drop, x_rise), max(x_drop, x_rise), y_detour, net.name, col))
                    v_segments.append((x_rise, min(y_detour, p2[1]), max(y_detour, p2[1]), net.name, col))
                    h_segments.append((min(p2[0], x_rise), max(p2[0], x_rise), p2[1], net.name, col))
                    wire_labels.append(((x_drop + x_rise) / 2.0, y_detour + 1.2, net.name))

            elif s1 == "left" and s2 == "left":
                if abs(b1[0] - b2[0]) < 1.0:
                    x_col = min(b1[0] - 6.0 - d_idx * 2.5, min(p1[0], p2[0]) - 3.0)
                    while any(
                        abs(x_col - s[0]) < 0.2 and (min(max(p1[1], p2[1]), s[2]) - max(min(p1[1], p2[1]), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_col -= 2.0
                    h_segments.append((min(x_col, p1[0]), max(x_col, p1[0]), p1[1], net.name, col))
                    v_segments.append((x_col, min(p1[1], p2[1]), max(p1[1], p2[1]), net.name, col))
                    h_segments.append((min(x_col, p2[0]), max(x_col, p2[0]), p2[1], net.name, col))
                    wire_labels.append((x_col - 1.5, (p1[1] + p2[1]) / 2.0, net.name))
                elif p1[1] >= (b1[1] + b1[3] / 2.0):
                    x_drop = min(b1[0] - 6.0 - d_idx * 2.5, p1[0] - 6.0 - d_idx * 2.5)
                    while any(
                        abs(x_drop - s[0]) < 0.2
                        and (min(max(p1[1], y_over), s[2]) - max(min(p1[1], y_over), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_drop -= 2.0
                    y_over = max(b1[1] + b1[3], b2[1] + b2[3]) + 8.0 + d_idx * 3.5
                    x_rise = min(b2[0] - 6.0 - d_idx * 2.5, p2[0] - 6.0 - d_idx * 2.5)
                    while any(
                        abs(x_rise - s[0]) < 0.2
                        and (min(max(y_over, p2[1]), s[2]) - max(min(y_over, p2[1]), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_rise -= 2.0
                    h_segments.append((min(x_drop, p1[0]), max(x_drop, p1[0]), p1[1], net.name, col))
                    v_segments.append((x_drop, min(p1[1], y_over), max(p1[1], y_over), net.name, col))
                    h_segments.append((min(x_drop, x_rise), max(x_drop, x_rise), y_over, net.name, col))
                    v_segments.append((x_rise, min(y_over, p2[1]), max(y_over, p2[1]), net.name, col))
                    h_segments.append((min(x_rise, p2[0]), max(x_rise, p2[0]), p2[1], net.name, col))
                    wire_labels.append(((x_drop + x_rise) / 2.0, y_over + 1.2, net.name))
                else:
                    x_drop = min(b1[0] - 6.0 - d_idx * 2.5, p1[0] - 6.0 - d_idx * 2.5)
                    while any(
                        abs(x_drop - s[0]) < 0.2
                        and (min(max(p1[1], y_detour), s[2]) - max(min(p1[1], y_detour), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_drop -= 2.0
                    x_rise = min(b2[0] - 6.0 - d_idx * 2.5, p2[0] - 6.0 - d_idx * 2.5)
                    while any(
                        abs(x_rise - s[0]) < 0.2
                        and (min(max(y_detour, p2[1]), s[2]) - max(min(y_detour, p2[1]), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_rise -= 2.0

                    h_segments.append((min(x_drop, p1[0]), max(x_drop, p1[0]), p1[1], net.name, col))
                    v_segments.append((x_drop, min(p1[1], y_detour), max(p1[1], y_detour), net.name, col))
                    h_segments.append((min(x_drop, x_rise), max(x_drop, x_rise), y_detour, net.name, col))
                    v_segments.append((x_rise, min(y_detour, p2[1]), max(y_detour, p2[1]), net.name, col))
                    h_segments.append((min(x_rise, p2[0]), max(x_rise, p2[0]), p2[1], net.name, col))
                    wire_labels.append(((x_drop + x_rise) / 2.0, y_detour + 1.2, net.name))

            elif s1 == "right" and s2 == "left":
                intervening = [
                    b
                    for c, b in comp_box_dict.items()
                    if c not in (c1_name, c2_name)
                    and not (b[0] + b[2] <= min(p1[0], p2[0]) or b[0] >= max(p1[0], p2[0]))
                ]
                if intervening:
                    max_y_top = max(b[1] + b[3] for b in [b1, b2] + intervening)
                    y_over = max_y_top + 16.0 + d_idx * 3.5
                    x_rise = b1[0] + b1[2] + 6.0 + d_idx * 2.5
                    while any(
                        abs(x_rise - s[0]) < 0.2
                        and (min(max(p1[1], y_over), s[2]) - max(min(p1[1], y_over), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_rise += 2.0
                    x_drop = b2[0] - 6.0 - d_idx * 2.5
                    while any(
                        abs(x_drop - s[0]) < 0.2
                        and (min(max(y_over, p2[1]), s[2]) - max(min(y_over, p2[1]), s[1]) > 0.1)
                        for s in v_segments
                    ):
                        x_drop -= 2.0
                    h_segments.append((min(p1[0], x_rise), max(p1[0], x_rise), p1[1], net.name, col))
                    v_segments.append((x_rise, min(p1[1], y_over), max(p1[1], y_over), net.name, col))
                    h_segments.append((min(x_rise, x_drop), max(x_rise, x_drop), y_over, net.name, col))
                    v_segments.append((x_drop, min(y_over, p2[1]), max(y_over, p2[1]), net.name, col))
                    h_segments.append((min(x_drop, p2[0]), max(x_drop, p2[0]), p2[1], net.name, col))
                    wire_labels.append(((x_rise + x_drop) / 2.0, y_over + 1.2, net.name))
                else:
                    if abs(p1[1] - p2[1]) < 0.1:
                        h_segments.append((min(p1[0], p2[0]), max(p1[0], p2[0]), p1[1], net.name, col))
                        wire_labels.append(((p1[0] + p2[0]) / 2.0, p1[1] + 1.2, net.name))
                    else:
                        x_mid = (p1[0] + p2[0]) / 2.0 + (d_idx - 1) * 3.5
                        h_segments.append((min(p1[0], x_mid), max(p1[0], x_mid), p1[1], net.name, col))
                        v_segments.append((x_mid, min(p1[1], p2[1]), max(p1[1], p2[1]), net.name, col))
                        h_segments.append((min(x_mid, p2[0]), max(x_mid, p2[0]), p2[1], net.name, col))
                        wire_labels.append((x_mid, (p1[1] + p2[1]) / 2.0 + 1.2, net.name))

            else:
                x_drop = min(b1[0] - 6.0 - d_idx * 2.5, p1[0] - 6.0 - d_idx * 2.5)
                x_rise = max(b2[0] + b2[2] + 6.0 + d_idx * 2.5, p2[0] + 6.0 + d_idx * 2.5)
                h_segments.append((min(x_drop, p1[0]), max(x_drop, p1[0]), p1[1], net.name, col))
                v_segments.append((x_drop, min(p1[1], y_detour), max(p1[1], y_detour), net.name, col))
                h_segments.append((min(x_drop, x_rise), max(x_drop, x_rise), y_detour, net.name, col))
                v_segments.append((x_rise, min(y_detour, p2[1]), max(y_detour, p2[1]), net.name, col))
                h_segments.append((min(p2[0], x_rise), max(p2[0], x_rise), p2[1], net.name, col))
                wire_labels.append(((x_drop + x_rise) / 2.0, y_detour + 1.2, net.name))

        return h_segments, v_segments, wire_labels

    @classmethod
    def compute_sheet_wire_segments(
        cls,
        wiring: Optional[Wiring],
        sheet_plans: List[_SchematicSheetPlan],
        config: Optional[PCBConfig] = None,
    ) -> Dict[int, Tuple[List[Tuple[float, float, float, str]], List[Tuple[float, float, float, str]]]]:
        """Compute all horizontal and vertical wire segments for each schematic sheet plan.

        Args:
            wiring: Wiring model or None.
            sheet_plans: Planned schematic sheets.
            config: PCB configuration or None.

        Returns:
            Dict mapping sheet_idx -> (h_segments, v_segments)
            where h_segments are (x_min, x_max, y, net_name)
            and v_segments are (x, y_min, y_max, net_name).
        """
        all_nets = getattr(wiring, "nets", []) or [] if wiring else []
        result: Dict[int, Tuple[List[Tuple[float, float, float, str]], List[Tuple[float, float, float, str]]]] = {}
        for plan in sheet_plans:
            h_segs, v_segs, _ = cls.compute_sheet_wire_segments_for_plan(plan, all_nets, config)
            h_clean = [(min(s[0], s[1]), max(s[0], s[1]), s[2], s[3]) for s in h_segs]
            v_clean = [(s[0], min(s[1], s[2]), max(s[1], s[2]), s[3]) for s in v_segs]
            result[plan.sheet_idx] = (h_clean, v_clean)
        return result
