"""Detection, classification, and rendering of schematic passive components."""

from collections import defaultdict
import re
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.axes
import matplotlib.patches as patches

from model.wiring import FootprintModel
from provider.schematic.constants import GROUND_NET_NAMES, POWER_NET_NAMES
from provider.schematic.jumper import draw_vertical_wire_with_jumpers


class SchematicPassiveClassifier:
    """Identifies and classifies electronic passives (decoupling caps, pull resistors, shunt caps)."""

    @staticmethod
    def is_decoupling_cap(fp: FootprintModel, pin_to_net: Dict[Tuple[str, str], str]) -> bool:
        """Check if a footprint is a 2-terminal decoupling capacitor connected between power and ground."""
        name_u = fp.name.upper()
        pkg_u = fp.package.upper()
        if not (name_u.startswith("C") or "CAP" in pkg_u) or len(fp.pins) != 2:
            return False
        n1 = pin_to_net.get((fp.name, fp.pins[0].name), "").upper()
        n2 = pin_to_net.get((fp.name, fp.pins[1].name), "").upper()
        return (n1 in POWER_NET_NAMES and n2 in GROUND_NET_NAMES) or (n2 in POWER_NET_NAMES and n1 in GROUND_NET_NAMES)

    @staticmethod
    def is_pull_resistor(
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
        # The signal line must connect to another footprint on this sheet (excluding indicator LEDs)
        for other in all_fps:
            if other.name == fp.name:
                continue
            if other.name.upper().startswith("D") or "LED" in other.package.upper():
                continue
            for p in other.pins:
                if pin_to_net.get((other.name, p.name)) == sig_net:
                    return True
        return False

    @classmethod
    def is_pullup_resistor(
        cls,
        fp: FootprintModel,
        pin_to_net: Dict[Tuple[str, str], str],
        all_fps: List[FootprintModel],
    ) -> bool:
        """Alias for is_pull_resistor supporting both pull-up and pull-down configurations."""
        return cls.is_pull_resistor(fp, pin_to_net, all_fps)

    @staticmethod
    def is_shunt_cap(
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

    @classmethod
    def classify_passives(
        cls,
        sheet_fps: List[FootprintModel],
        pin_to_net: Dict[Tuple[str, str], str],
        grid_positions: Optional[Dict[str, List[int]]] = None,
    ) -> Tuple[List[FootprintModel], List[FootprintModel], List[FootprintModel], List[FootprintModel]]:
        """Classify footprints on a sheet into decoupling caps, pullups, shunt caps, and main ICs.

        Args:
            sheet_fps: Footprints on the current sheet.
            pin_to_net: Net mapping.
            grid_positions: Optional explicit layout grid positions dict.

        Returns:
            Tuple of (decoupling_caps, pullup_resistors, shunt_caps, main_fps).
        """
        grid_names = set(grid_positions.keys()) if grid_positions else set()
        decoupling_caps = [
            fp for fp in sheet_fps if fp.name not in grid_names and cls.is_decoupling_cap(fp, pin_to_net)
        ]
        pullup_resistors = [
            fp for fp in sheet_fps if fp.name not in grid_names and cls.is_pull_resistor(fp, pin_to_net, sheet_fps)
        ]
        shunt_caps = [
            fp for fp in sheet_fps if fp.name not in grid_names and cls.is_shunt_cap(fp, pin_to_net, sheet_fps)
        ]
        passive_names = {fp.name for fp in decoupling_caps + pullup_resistors + shunt_caps}
        if passive_names and (len(passive_names) < len(sheet_fps)):
            main_fps = [fp for fp in sheet_fps if fp.name not in passive_names]
        else:
            decoupling_caps = []
            pullup_resistors = []
            shunt_caps = []
            main_fps = sheet_fps
        return decoupling_caps, pullup_resistors, shunt_caps, main_fps


class SchematicPassiveDrawer:
    """Renders vertical and bank passive components (decoupling cap banks, pull-up/pull-down resistor branches)."""

    @staticmethod
    def format_resistor_value(fp: FootprintModel) -> str:
        """Format a human-readable, concise resistance string from footprint metadata."""
        if getattr(fp, "value", None):
            return fp.value
        if fp.label and fp.label.text and fp.label.text != fp.name:
            return fp.label.text
        mpn = getattr(fp, "mpn", None)
        if mpn:
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

    @staticmethod
    def draw_decoupling_cap_bank(
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
        x_min = base_x
        x_max = base_x + total_w

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
            card_x + 3.0,
            card_y + card_h - 2.8,
            "POWER DECOUPLING & BULK CAPACITORS",
            fontsize=5.5,
            fontweight="bold",
            color="#334155",
            zorder=2,
        )

        # Determine power rail for each cap
        cap_pwr_nets = []
        for fp in caps:
            pwr = "3V3"
            for p in fp.pins:
                n = pin_to_net.get((fp.name, p.name), "")
                if n.upper() in POWER_NET_NAMES:
                    pwr = n
                    break
            cap_pwr_nets.append(pwr)

        # Group caps by power net
        pwr_groups: Dict[str, List[int]] = defaultdict(list)
        for idx, pwr in enumerate(cap_pwr_nets):
            pwr_groups[pwr].append(idx)

        # Draw top rail and arrow for each power net group
        for pwr_net, indices in pwr_groups.items():
            grp_x_min = base_x + min(indices) * delta_x
            grp_x_max = base_x + max(indices) * delta_x
            if len(indices) > 1:
                ax.plot([grp_x_min, grp_x_max], [y_top, y_top], color="#dc2626", linewidth=1.5, zorder=2)
            x_arrow = (grp_x_min + grp_x_max) / 2.0
            ax.plot([x_arrow, x_arrow], [y_top, y_top + 4.0], color="#dc2626", linewidth=1.5, zorder=2)
            ax.plot(
                [x_arrow - 2.5, x_arrow, x_arrow + 2.5],
                [y_top + 2.5, y_top + 5.0, y_top + 2.5],
                color="#dc2626",
                linewidth=1.2,
                zorder=2,
            )
            ax.text(
                x_arrow,
                y_top + 6.0,
                pwr_net,
                ha="center",
                va="bottom",
                fontsize=6.5,
                fontweight="bold",
                color="#dc2626",
                zorder=4,
            )

        # Common GND Bottom Rail
        ax.plot([x_min, x_max], [y_bot, y_bot], color="#475569", linewidth=1.5, zorder=2)

        # 3-bar GND symbol at bottom rail center
        x_gnd = (x_min + x_max) / 2.0
        y_gnd = y_bot
        ax.plot([x_gnd, x_gnd], [y_gnd, y_gnd - 3.5], color="#475569", linewidth=1.2, zorder=2)
        ax.plot([x_gnd - 3.5, x_gnd + 3.5], [y_gnd - 3.5, y_gnd - 3.5], color="#475569", linewidth=1.5, zorder=2)
        ax.plot([x_gnd - 2.2, x_gnd + 2.2], [y_gnd - 5.0, y_gnd - 5.0], color="#475569", linewidth=1.2, zorder=2)
        ax.plot([x_gnd - 1.0, x_gnd + 1.0], [y_gnd - 6.5, y_gnd - 6.5], color="#475569", linewidth=1.0, zorder=2)
        ax.text(
            x_gnd,
            y_gnd - 8.5,
            "GND",
            ha="center",
            va="top",
            fontsize=6.0,
            fontweight="bold",
            color="#475569",
            zorder=3,
        )

        plate_w = 7.0
        plate_gap = 2.4

        for idx, fp in enumerate(caps):
            cx = base_x + idx * delta_x

            # Vertical wire from top rail down to top plate
            ax.plot([cx, cx], [y_top, y_mid + (plate_gap / 2.0)], color="#dc2626", linewidth=1.2, zorder=2)
            pwr = cap_pwr_nets[idx]
            if len(pwr_groups[pwr]) > 1:
                ax.plot(cx, y_top, marker="o", markersize=2.5, color="#dc2626", zorder=3)

            # Top plate
            ax.plot(
                [cx - plate_w / 2.0, cx + plate_w / 2.0],
                [y_mid + (plate_gap / 2.0), y_mid + (plate_gap / 2.0)],
                color="#1e293b",
                linewidth=2.0,
                zorder=3,
            )

            # Bottom plate
            ax.plot(
                [cx - plate_w / 2.0, cx + plate_w / 2.0],
                [y_mid - (plate_gap / 2.0), y_mid - (plate_gap / 2.0)],
                color="#1e293b",
                linewidth=2.0,
                zorder=3,
            )

            # Vertical wire from bottom plate down to GND rail
            ax.plot([cx, cx], [y_mid - (plate_gap / 2.0), y_bot], color="#475569", linewidth=1.2, zorder=2)
            ax.plot(cx, y_bot, marker="o", markersize=2.5, color="#475569", zorder=3)

            # RefDes and capacitance label
            ax.text(
                cx + 4.8,
                y_mid + 2.5,
                fp.name,
                ha="left",
                va="center",
                fontsize=7.0,
                fontweight="bold",
                color="#0f172a",
                zorder=4,
            )
            val = getattr(fp, "value", None) or (fp.label.text if fp.label else fp.package)
            if val == fp.name:
                val = fp.package
            ax.text(
                cx + 4.8,
                y_mid - 2.5,
                val,
                ha="left",
                va="center",
                fontsize=5.5,
                color="#0369a1",
                zorder=4,
            )

    @classmethod
    def compute_pullup_tap_points(
        cls,
        pullups: List[FootprintModel],
        pin_to_net: Dict[Tuple[str, str], str],
        h_wire_segments: List[Tuple[float, float, float, str, str]],
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]],
        wired_pins: Optional[set[Tuple[str, str]]] = None,
        pin_side_map: Optional[Dict[Tuple[str, str], str]] = None,
        ax: Optional[matplotlib.axes.Axes] = None,
    ) -> List[Tuple[float, float, FootprintModel, str, str]]:
        """Compute connection coordinates (x_pull, y_base) and net assignments for vertical passives."""
        if not pullups:
            return []
        if wired_pins is None:
            wired_pins = set()

        pullup_points: List[Tuple[float, float, FootprintModel, str, str]] = []

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
        if center_x + total_span / 2.0 > x_max_all - 14.0:
            center_x = (x_max_all - 14.0) - total_span / 2.0
        if center_x - total_span / 2.0 < x_min_all + 6.0:
            center_x = (x_min_all + 6.0) + total_span / 2.0

        comp_stub_counts: Dict[Tuple[str, str], int] = defaultdict(int)
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

            term_x_end: Optional[float] = None
            term_side: Optional[str] = None
            matching_segs = [s for s in h_wire_segments if s[3] == sig_net]
            if matching_segs:
                x_start = min(min(s[0], s[1]) for s in matching_segs)
                x_end = max(max(s[0], s[1]) for s in matching_segs)
                seg_len = x_end - x_start
                if seg_len >= 18.0:
                    chan_fps = []
                    for other_fp in pullups:
                        o_n1 = pin_to_net.get((other_fp.name, other_fp.pins[0].name), "")
                        o_n2 = pin_to_net.get((other_fp.name, other_fp.pins[1].name), "")
                        o_sig = o_n2 if (o_n1.upper() in POWER_NET_NAMES or o_n1.upper() in GROUND_NET_NAMES) else o_n1
                        o_segs = [s for s in h_wire_segments if s[3] == o_sig]
                        if o_segs:
                            o_xs = min(min(s[0], s[1]) for s in o_segs)
                            o_xe = max(max(s[0], s[1]) for s in o_segs)
                            if max(x_start, o_xs) < min(x_end, o_xe) - 5.0:
                                chan_fps.append(other_fp)

                    n_chan = max(1, len(chan_fps))
                    chan_idx = chan_fps.index(fp) if fp in chan_fps else (idx % n_chan)
                    safe_min = x_start + 10.0
                    safe_max = x_end - 12.0
                    ch_pitch = 20.0
                    ch_total_span = (n_chan - 1) * ch_pitch
                    if safe_max - safe_min >= ch_total_span:
                        mid_x = (safe_min + safe_max) / 2.0
                        cand_x = (mid_x - ch_total_span / 2.0) + chan_idx * ch_pitch
                    else:
                        step = (safe_max - safe_min) / max(1, n_chan - 1) if n_chan > 1 else 0.0
                        cand_x = safe_min + chan_idx * step

                    for _ in range(15):
                        if not any(abs(cand_x - ux) < 16.0 for ux in used_x_positions):
                            break
                        if cand_x + 16.0 <= safe_max:
                            cand_x += 16.0
                        elif cand_x - 16.0 >= safe_min:
                            cand_x -= 16.0
                        else:
                            break
                elif x_start < 100.0:
                    min_page_x = 22.0
                    cand_x = max(min_page_x, x_start - 24.0 - idx * 16.0)
                    for _ in range(10):
                        if not any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                            break
                        if cand_x - 10.0 >= min_page_x:
                            cand_x -= 10.0
                        elif cand_x + 10.0 <= x_start - 6.0:
                            cand_x += 10.0
                        else:
                            break
                    if ax is not None:
                        ax.plot(
                            [cand_x, x_start],
                            [matching_segs[0][2], matching_segs[0][2]],
                            color="#2563eb",
                            linewidth=1.2,
                            zorder=2,
                        )
                    h_wire_segments.append((cand_x, x_start, matching_segs[0][2], sig_net, "#2563eb"))
                else:
                    max_page_x = 265.0
                    cand_x = min(max_page_x, x_end + 14.0 + idx * 16.0)
                    for _ in range(10):
                        if not any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                            break
                        if cand_x + 10.0 <= max_page_x:
                            cand_x += 10.0
                        elif cand_x - 10.0 >= x_end + 6.0:
                            cand_x -= 10.0
                        else:
                            break
                    if ax is not None:
                        ax.plot(
                            [x_end, cand_x],
                            [matching_segs[0][2], matching_segs[0][2]],
                            color="#2563eb",
                            linewidth=1.2,
                            zorder=2,
                        )
                    h_wire_segments.append((x_end, cand_x, matching_segs[0][2], sig_net, "#2563eb"))
                x_pull = cand_x
                containing_seg = next(
                    (s for s in matching_segs if min(s[0], s[1]) - 0.1 <= cand_x <= max(s[0], s[1]) + 0.1),
                    None,
                )
                if containing_seg:
                    y_base = containing_seg[2]
                else:
                    closest_seg = min(
                        matching_segs,
                        key=lambda s: min(abs(s[0] - cand_x), abs(s[1] - cand_x)),
                    )
                    y_base = closest_seg[2]
                    seg_min = min(closest_seg[0], closest_seg[1])
                    seg_max = max(closest_seg[0], closest_seg[1])
                    if cand_x < seg_min:
                        bridge_x1, bridge_x2 = cand_x, seg_min
                    elif cand_x > seg_max:
                        bridge_x1, bridge_x2 = seg_max, cand_x
                    else:
                        bridge_x1, bridge_x2 = cand_x, cand_x

                    if bridge_x2 - bridge_x1 > 0.05:
                        if ax is not None:
                            ax.plot([bridge_x1, bridge_x2], [y_base, y_base], color="#2563eb", linewidth=1.2, zorder=2)
                        h_wire_segments.append((bridge_x1, bridge_x2, y_base, sig_net, "#2563eb"))
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
                    stub_idx = comp_stub_counts[(target_pair[0], side)]
                    comp_stub_counts[(target_pair[0], side)] += 1
                    if side == "right":
                        next_comp_left = min(
                            (c[0] for p, c in sheet_pin_coords.items() if c[0] > p_x + 10.0 and p[0] != target_pair[0]),
                            default=280.0,
                        )
                        cand_x = min(265.0, p_x + 14.0 + stub_idx * 16.0)
                        if cand_x > next_comp_left - 12.0:
                            avail_span = (next_comp_left - 10.0) - (p_x + 8.0)
                            if avail_span > 18.0:
                                cand_x = (p_x + 8.0) + (stub_idx + 1) * (avail_span / 3.0)
                            else:
                                cand_x = (p_x + next_comp_left) / 2.0 + (stub_idx - 0.5) * 12.0
                        for _ in range(10):
                            if not any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                                break
                            if cand_x + 7.0 < min(268.0, next_comp_left - 8.0):
                                cand_x += 7.0
                            elif cand_x - 7.0 > p_x + 6.0:
                                cand_x -= 7.0
                            else:
                                break
                        x_end = min(next_comp_left - 8.0, max(cand_x + 12.0, p_x + 28.0 + stub_idx * 12.0))
                    else:
                        min_page_x = 22.0
                        cand_x = max(min_page_x + 8.0, p_x - 24.0 - stub_idx * 16.0)
                        for _ in range(10):
                            if not any(abs(cand_x - ux) < 10.0 for ux in used_x_positions):
                                break
                            if cand_x - step >= min_page_x + 8.0:
                                cand_x -= step
                            elif cand_x + step <= p_x - 6.0:
                                cand_x += step
                            else:
                                break
                        x_end = min_page_x
                    x_pull = cand_x
                    term_x_end = x_end
                    term_side = side

                    w_x1 = min(p_x, x_end)
                    w_x2 = max(p_x, x_end)
                    if not any(abs(s[2] - y_base) < 0.2 and s[3] == sig_net for s in h_wire_segments):
                        h_wire_segments.append((w_x1, w_x2, y_base, sig_net, "#2563eb"))
                    if wired_pins is not None:
                        wired_pins.add(target_pair)

                    if ax is not None:
                        ax.plot([w_x1, w_x2], [y_base, y_base], color="#2563eb", linewidth=1.2, zorder=2)
                        ax.plot(x_end, y_base, marker="o", markersize=2.5, color="#2563eb", zorder=3)
                        if side == "left":
                            ax.text(
                                x_end - 1.5,
                                y_base,
                                sig_net,
                                ha="right",
                                va="center",
                                fontsize=6.5,
                                fontweight="bold",
                                color="#0369a1",
                                zorder=4,
                            )
                        else:
                            ax.text(
                                x_end + 1.5,
                                y_base,
                                sig_net,
                                ha="left",
                                va="center",
                                fontsize=6.5,
                                fontweight="bold",
                                color="#0369a1",
                                zorder=4,
                            )
                else:
                    x_pull = center_x - total_span / 2.0 + idx * pitch
                    y_base = 120.0

            used_x_positions.append(x_pull)
            pullup_points.append((x_pull, y_base, fp, sig_net, rail_net, term_x_end, term_side))

        return pullup_points

    @classmethod
    def draw_pullup_resistors(
        cls,
        ax: matplotlib.axes.Axes,
        pullups: List[FootprintModel],
        pin_to_net: Dict[Tuple[str, str], str],
        h_wire_segments: List[Tuple[float, float, float, str, str]],
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]],
        wired_pins: Optional[set[Tuple[str, str]]] = None,
        pin_side_map: Optional[Dict[Tuple[str, str], str]] = None,
        pullup_points: Optional[List[Any]] = None,
    ) -> None:
        """Render pull-up and pull-down resistors as vertical branches directly attached to signal lines."""
        if not pullups:
            return
        if wired_pins is None:
            wired_pins = set()

        if pullup_points is None:
            pullup_points = cls.compute_pullup_tap_points(
                pullups=pullups,
                pin_to_net=pin_to_net,
                h_wire_segments=h_wire_segments,
                sheet_pin_coords=sheet_pin_coords,
                wired_pins=wired_pins,
                pin_side_map=pin_side_map,
                ax=ax,
            )

        pwr_pullups = [p for p in pullup_points if p[4].upper() in POWER_NET_NAMES]
        pullup_max_y = max((p[1] for p in pwr_pullups), default=120.0)

        for pt in pullup_points:
            x_pull, y_base, fp, sig_net, rail_net = pt[0], pt[1], pt[2], pt[3], pt[4]
            term_x_end = pt[5] if len(pt) > 5 else None
            term_side = pt[6] if len(pt) > 6 else None

            # Render wire end terminal dot and off-sheet designator if computed
            if term_x_end is not None:
                ax.plot(term_x_end, y_base, marker="o", markersize=2.5, color="#2563eb", zorder=3)
                if term_side == "left":
                    ax.text(
                        term_x_end - 1.5,
                        y_base,
                        sig_net,
                        ha="right",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=4,
                    )
                else:
                    ax.text(
                        term_x_end + 1.5,
                        y_base,
                        sig_net,
                        ha="left",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=4,
                    )

            ax.plot(x_pull, y_base, marker="o", markersize=3.0, color="#2563eb", zorder=4)

            is_pullup = rail_net.upper() in POWER_NET_NAMES
            if is_pullup:
                y_zz_bot = max(pullup_max_y + 8.0, 158.0)
                y_zz_top = y_zz_bot + 9.0
                y_top_rail = y_zz_top + 6.0

                draw_vertical_wire_with_jumpers(
                    ax,
                    x_v=x_pull,
                    y_start=y_base,
                    y_end=y_zz_bot,
                    col="#475569",
                    h_wire_segments=h_wire_segments,
                    net_name=sig_net,
                )
                cls._draw_zigzag_resistor(ax, x_pull, y_zz_bot, y_zz_top)

                val_text = cls.format_resistor_value(fp)
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
                y_zz_top = y_base - 8.0
                y_zz_bot = y_zz_top - 9.0
                y_drop = y_zz_bot - 4.0

                draw_vertical_wire_with_jumpers(
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
                    ax.plot([x_pull, x_pull], [y_zz_top, y_zz_top - 2.5], color="#475569", linewidth=1.2, zorder=2)
                    ax.plot([x_pull, x_pull], [y_zz_top - 4.9, y_zz_bot], color="#475569", linewidth=1.2, zorder=2)
                else:
                    cls._draw_zigzag_resistor(ax, x_pull, y_zz_top, y_zz_bot)

                val_text = cls.format_resistor_value(fp)
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

                cls._draw_gnd_3bar(ax, x_pull, y_zz_bot, y_drop)

    @staticmethod
    def _draw_zigzag_resistor(ax: matplotlib.axes.Axes, x: float, y_start: float, y_end: float) -> None:
        """Render a vertical zig-zag resistor body between y_start and y_end."""
        dy = (y_end - y_start) / 8.0
        zz_y = [y_start + i * dy for i in range(9)]
        zz_x = [x, x + 1.6, x - 1.6, x + 1.6, x - 1.6, x + 1.6, x - 1.6, x + 1.6, x]
        ax.plot(zz_x, zz_y, color="#334155", linewidth=1.5, zorder=3)

    @staticmethod
    def _draw_gnd_3bar(ax: matplotlib.axes.Axes, x: float, y_start: float, y_drop: float) -> None:
        """Render a standard 3-bar ground symbol hanging down at y_drop."""
        ax.plot([x, x], [y_start, y_drop], color="#475569", linewidth=1.2, zorder=2)
        ax.plot([x - 2.8, x + 2.8], [y_drop, y_drop], color="#475569", linewidth=1.4, zorder=2)
        ax.plot([x - 1.8, x + 1.8], [y_drop - 1.2, y_drop - 1.2], color="#475569", linewidth=1.2, zorder=2)
        ax.plot([x - 0.8, x + 0.8], [y_drop - 2.4, y_drop - 2.4], color="#475569", linewidth=1.0, zorder=2)
        ax.text(
            x, y_drop - 3.8, "GND", ha="center", va="top", fontsize=5.5, fontweight="bold", color="#475569", zorder=3
        )
