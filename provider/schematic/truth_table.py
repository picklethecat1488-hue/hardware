"""Discrete logic and transistor truth table generation and visual rendering."""

from typing import Dict, Optional, Tuple

import matplotlib.axes
import matplotlib.patches as patches

from model.wiring import FootprintModel, TruthTableModel, TruthTableRowModel


class SchematicTruthTableDrawer:
    """Generates and renders discrete transistor and logic truth tables on schematic sheets."""

    @staticmethod
    def generate_default_transistor_truth_table(
        fp: FootprintModel,
        pin_to_net: Optional[Dict[Tuple[str, str], str]] = None,
    ) -> TruthTableModel:
        """Generate a default truth table capturing true, false, and invalid states for a discrete transistor network.

        Args:
            fp: Transistor or MOSFET footprint model.
            pin_to_net: Mapping of (footprint, pin) to net names.

        Returns:
            Populated TruthTableModel with functional operating states.
        """
        if pin_to_net is None:
            pin_to_net = {}

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

    @staticmethod
    def draw_truth_table(
        ax: matplotlib.axes.Axes,
        fp: FootprintModel,
        tt: TruthTableModel,
        base_x: float = 118.0,
        base_y: float = 52.0,
        card_w: float = 125.0,
    ) -> None:
        """Render an engineering truth table box displaying TRUE, FALSE, and INVALID circuit states.

        Args:
            ax: Matplotlib axes to render onto.
            fp: Footprint model associated with the truth table.
            tt: TruthTableModel with headers and rows.
            base_x: Center/base X coordinate.
            base_y: Center/base Y coordinate.
            card_w: Width of the rendered table card in mm.
        """
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
