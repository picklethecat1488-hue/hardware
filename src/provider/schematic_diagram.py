"""Dedicated vector schematic diagram and multi-page PDF generator for electronic components and nets."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import matplotlib.patches as patches

from model.pcb import PCBConfig
from model.wiring import FootprintModel, NetModel, Wiring


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
            svg_lines.append(
                f'  <text x="{cx + bw / 2.0:.1f}" y="{cy + 22:.1f}" font-family="system-ui, sans-serif" '
                f'font-size="13" font-weight="bold" text-anchor="middle" fill="#0f172a">{ref}</text>'
            )
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
        chunk_size = 2 if len(fps) > 2 else len(fps)
        fp_chunks = [fps[i : i + chunk_size] for i in range(0, len(fps), max(1, chunk_size))]
        total_sheets = max(1, len(fp_chunks))
        total_pages = 2 + total_sheets

        with PdfPages(out_path) as pdf:
            # Page 1: Title Cover Page
            self._render_pdf_title_page(pdf, board_name, board_type, layer_count, fps, self.wiring.nets, total_pages)

            # Page 2: Table of Contents & Netlist Summary
            self._render_pdf_toc_page(
                pdf, board_name, board_type, layer_count, fps, self.wiring.nets, fp_chunks, total_pages
            )

            # Pages 3+: Schematic Drawing Sheets
            for sheet_idx, sheet_fps in enumerate(fp_chunks, start=1):
                self._render_pdf_schematic_sheet(
                    pdf=pdf,
                    board_name=board_name,
                    sheet_idx=sheet_idx,
                    total_sheets=total_sheets,
                    sheet_fps=sheet_fps,
                    all_nets=self.wiring.nets,
                    page_num=2 + sheet_idx,
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
        ax.text(168, 72, f"Total Footprints: {len(fps)} | Nets: {len(nets)}", fontsize=9.5, color="#334155")
        ax.text(168, 60, f"Date: {date_str} | Rev: 1.0", fontsize=9.5, color="#334155")

        # Footer
        ax.text(148.5, 20, f"Page 1 of {total_pages}", ha="center", fontsize=9, color="#64748b")
        pdf.savefig(fig)

    def _render_pdf_toc_page(
        self,
        pdf: PdfPages,
        board_name: str,
        board_type: str,
        layer_count: int,
        fps: List[FootprintModel],
        nets: List[NetModel],
        fp_chunks: List[List[FootprintModel]],
        total_pages: int,
    ) -> None:
        """Render Table of Contents and Interconnect Bill of Materials."""
        fig = Figure(figsize=(11.693, 8.268), dpi=300)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 297)
        ax.set_ylim(0, 210)
        ax.axis("off")

        # Double outer engineering border
        ax.add_patch(patches.Rectangle((10, 10), 277, 190, fill=False, edgecolor="#1e293b", linewidth=2.0))
        ax.add_patch(patches.Rectangle((12, 12), 273, 186, fill=False, edgecolor="#94a3b8", linewidth=0.8))

        # Header
        ax.text(20, 188, "TABLE OF CONTENTS & SYSTEM OVERVIEW", fontsize=15, fontweight="bold", color="#0f172a")
        ax.text(20, 180, f"{board_name} | {board_type} | {layer_count}-Layer Stackup", fontsize=10, color="#475569")
        ax.plot([20, 277], [175, 175], color="#0284c7", linewidth=1.5)

        # Section 1: Document Index
        ax.text(20, 166, "1. Document Structure", fontsize=11, fontweight="bold", color="#1e293b")
        y = 157.0
        ax.text(28, y, "Page 1: Document Cover & Engineering Specifications", fontsize=9, color="#334155")
        y -= 7.0
        ax.text(28, y, "Page 2: Table of Contents, Bill of Footprints & Netlist Summary", fontsize=9, color="#334155")
        y -= 7.0
        for s_idx, chunk in enumerate(fp_chunks, start=1):
            comps = ", ".join(f"{c.name} ({c.package})" for c in chunk)
            ax.text(28, y, f"Page {2 + s_idx}: Schematic Sheet {s_idx} - {comps}", fontsize=9, color="#334155")
            y -= 7.0

        # Section 2: Footprint Schedule Table
        y -= 4.0
        ax.text(20, y, "2. Component Bill of Footprints", fontsize=11, fontweight="bold", color="#1e293b")
        y -= 7.0
        # Table Header
        ax.add_patch(patches.Rectangle((20, y - 5), 257, 6.5, facecolor="#0f172a", edgecolor="none"))
        ax.text(25, y - 3.5, "Designator", fontsize=8.5, fontweight="bold", color="#ffffff")
        ax.text(55, y - 3.5, "Package", fontsize=8.5, fontweight="bold", color="#ffffff")
        ax.text(105, y - 3.5, "Manufacturer Part Number (MPN)", fontsize=8.5, fontweight="bold", color="#ffffff")
        ax.text(185, y - 3.5, "Pins", fontsize=8.5, fontweight="bold", color="#ffffff")
        ax.text(210, y - 3.5, "Sheet", fontsize=8.5, fontweight="bold", color="#ffffff")
        y -= 6.5

        for col_idx, fp in enumerate(fps):
            bg = "#f8fafc" if col_idx % 2 == 0 else "#ffffff"
            ax.add_patch(patches.Rectangle((20, y - 5), 257, 5.5, facecolor=bg, edgecolor="#e2e8f0", linewidth=0.5))
            sheet_num = 1
            for idx, c in enumerate(fp_chunks, start=1):
                if fp in c:
                    sheet_num = idx
                    break
            mpn = fp.mpn or (fp.label.text if fp.label else fp.package)
            ax.text(25, y - 3.5, fp.name, fontsize=8, fontweight="bold", color="#0f172a")
            ax.text(55, y - 3.5, fp.package, fontsize=8, color="#334155")
            ax.text(105, y - 3.5, str(mpn), fontsize=8, color="#334155")
            ax.text(185, y - 3.5, str(len(fp.pins)), fontsize=8, color="#334155")
            ax.text(210, y - 3.5, f"Sheet {sheet_num}", fontsize=8, color="#0284c7")
            y -= 5.5

        # Section 3: Primary Signal Nets Summary
        y -= 6.0
        ax.text(20, y, "3. Primary Signal Nets", fontsize=11, fontweight="bold", color="#1e293b")
        y -= 6.0
        net_chunks = [nets[i : i + 4] for i in range(0, len(nets), 4)]
        for row in net_chunks:
            for n_idx, net in enumerate(row):
                nx = 28 + (n_idx * 62)
                pin_count = len(net.pins)
                ax.text(nx, y, f"• {net.name} ({pin_count} pins)", fontsize=8, color="#475569")
            y -= 5.0

        # Footer
        ax.text(148.5, 15, f"Page 2 of {total_pages}", ha="center", fontsize=9, color="#64748b")
        pdf.savefig(fig)

    def _render_pdf_schematic_sheet(
        self,
        pdf: PdfPages,
        board_name: str,
        sheet_idx: int,
        total_sheets: int,
        sheet_fps: List[FootprintModel],
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

        # Standard KiCad/Engineering Title Block (Bottom-Right)
        tb_x, tb_y, tb_w, tb_h = 202.0, 12.0, 83.0, 32.0
        ax.add_patch(
            patches.Rectangle((tb_x, tb_y), tb_w, tb_h, facecolor="#f8fafc", edgecolor="#1e293b", linewidth=1.2)
        )
        ax.plot([tb_x, tb_x + tb_w], [tb_y + 20, tb_y + 20], color="#cbd5e1", linewidth=0.8)
        ax.plot([tb_x, tb_x + tb_w], [tb_y + 10, tb_y + 10], color="#cbd5e1", linewidth=0.8)
        ax.plot([tb_x + 45, tb_x + 45], [tb_y, tb_y + 20], color="#cbd5e1", linewidth=0.8)

        ax.text(tb_x + 3, tb_y + 26, f"{board_name} Schematic", fontsize=9, fontweight="bold", color="#0f172a")
        ax.text(
            tb_x + 3,
            tb_y + 21.5,
            f"Sheet {sheet_idx} of {total_sheets} (Page {page_num} of {total_pages})",
            fontsize=7.5,
            color="#475569",
        )
        ax.text(tb_x + 3, tb_y + 14, "Rev: 1.0", fontsize=7.5, color="#334155")
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

        num_comps = len(sheet_fps)
        col_width = (185.0 - 20.0) / max(1, num_comps)
        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]] = {}

        for c_idx, fp in enumerate(sheet_fps):
            cx = 25.0 + (c_idx * col_width) + (col_width * 0.15)
            cw = min(60.0, col_width * 0.70)

            left_pins = [p for p in fp.pins if p.side.value in ("left", "bottom")]
            right_pins = [p for p in fp.pins if p.side.value in ("right", "top")]
            if not left_pins and not right_pins:
                left_pins = fp.pins[: len(fp.pins) // 2]
                right_pins = fp.pins[len(fp.pins) // 2 :]

            max_pin_rows = max(len(left_pins), len(right_pins), 2)
            ch = max(45.0, max_pin_rows * 8.0 + 20.0)
            cy = 185.0 - ch

            # IC Body Box
            ax.add_patch(
                patches.Rectangle((cx, cy), cw, ch, facecolor="#ffffff", edgecolor="#334155", linewidth=1.5, zorder=2)
            )

            # Component header inside box
            ax.text(
                cx + cw / 2.0,
                cy + ch - 5,
                fp.name,
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color="#0f172a",
                zorder=3,
            )
            val = fp.label.text if fp.label else fp.package
            ax.text(
                cx + cw / 2.0,
                cy + ch - 10.5,
                str(val),
                ha="center",
                va="center",
                fontsize=7.5,
                color="#64748b",
                zorder=3,
            )
            ax.plot([cx + 3, cx + cw - 3], [cy + ch - 13, cy + ch - 13], color="#e2e8f0", linewidth=0.8, zorder=3)

            # Left Pins
            stub_len = 8.0
            for p_idx, p in enumerate(left_pins):
                py = cy + ch - 19.0 - (p_idx * 7.5)
                ax.plot([cx - stub_len, cx], [py, py], color="#475569", linewidth=1.0, zorder=2)
                ax.plot(cx - stub_len, py, marker="o", markersize=3, color="#0284c7", zorder=3)
                ax.text(cx + 2.0, py, p.name, ha="left", va="center", fontsize=7, color="#1e293b", zorder=3)
                sheet_pin_coords[(fp.name, p.name)] = (cx - stub_len, py)

                net_name = pin_to_net.get((fp.name, p.name))
                if net_name:
                    ax.text(
                        cx - stub_len - 1.5,
                        py,
                        net_name,
                        ha="right",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=3,
                    )

            # Right Pins
            for p_idx, p in enumerate(right_pins):
                py = cy + ch - 19.0 - (p_idx * 7.5)
                ax.plot([cx + cw, cx + cw + stub_len], [py, py], color="#475569", linewidth=1.0, zorder=2)
                ax.plot(cx + cw + stub_len, py, marker="o", markersize=3, color="#0284c7", zorder=3)
                ax.text(cx + cw - 2.0, py, p.name, ha="right", va="center", fontsize=7, color="#1e293b", zorder=3)
                sheet_pin_coords[(fp.name, p.name)] = (cx + cw + stub_len, py)

                net_name = pin_to_net.get((fp.name, p.name))
                if net_name:
                    ax.text(
                        cx + cw + stub_len + 1.5,
                        py,
                        net_name,
                        ha="left",
                        va="center",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#0369a1",
                        zorder=3,
                    )

        # Wire connections between pins on this sheet sharing a net
        for net in all_nets:
            present_pins = [pair for pair in net.pins if pair in sheet_pin_coords]
            if len(present_pins) >= 2:
                for i in range(len(present_pins) - 1):
                    p1 = sheet_pin_coords[present_pins[i]]
                    p2 = sheet_pin_coords[present_pins[i + 1]]
                    mid_x = (p1[0] + p2[0]) / 2.0
                    ax.plot(
                        [p1[0], mid_x, mid_x, p2[0]],
                        [p1[1], p1[1], p2[1], p2[1]],
                        color="#2563eb",
                        linewidth=1.2,
                        zorder=1,
                    )

        pdf.savefig(fig)
