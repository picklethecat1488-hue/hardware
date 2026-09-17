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

from model.pcb import PCBConfig
from model.wiring import FootprintModel, NetModel, Wiring


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
                            allowed_pins = set(sheet_def.pin_breakouts[comp_name])
                            filtered_pins = [
                                p for p in orig_fp.pins if p.name in allowed_pins or p.label in allowed_pins
                            ]
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
        num_comps = len(sheet_fps)
        pin_pitch = 5.0
        stub_len = 5.0

        if num_comps == 1:
            cols_per_row = 1
            col_x_positions = [120.0]
            col_y_positions = [180.0]
            cw = 38.0
        elif num_comps == 2:
            cols_per_row = 2
            col_x_positions = [45.0, 175.0]
            col_y_positions = [180.0, 180.0]
            cw = 38.0
        elif num_comps == 3:
            cols_per_row = 3
            col_x_positions = [30.0, 110.0, 190.0]
            col_y_positions = [180.0, 180.0, 180.0]
            cw = 36.0
        else:
            cols_per_row = (num_comps + 1) // 2
            col_w = 230.0 / max(1, cols_per_row)
            cw = min(36.0, col_w * 0.55)
            col_x_positions = []
            col_y_positions = []
            for i in range(num_comps):
                r_idx = i // cols_per_row
                c_idx_col = i % cols_per_row
                col_x_positions.append(22.0 + c_idx_col * col_w + (col_w - cw) / 2.0)
                col_y_positions.append(180.0 - (r_idx * 68.0))

        sheet_pin_coords: Dict[Tuple[str, str], Tuple[float, float]] = {}
        pin_side_map: Dict[Tuple[str, str], str] = {}
        comp_of_pin: Dict[Tuple[str, str], int] = {}
        comp_boxes: List[Tuple[float, float, float, float]] = []

        for c_idx, fp in enumerate(sheet_fps):
            cx = col_x_positions[c_idx]
            row_top_y = col_y_positions[c_idx]

            left_pins = [p for p in fp.pins if p.side.value in ("left", "bottom")]
            right_pins = [p for p in fp.pins if p.side.value in ("right", "top")]
            if not left_pins and not right_pins:
                left_pins = fp.pins[: len(fp.pins) // 2]
                right_pins = fp.pins[len(fp.pins) // 2 :]

            mpn = getattr(fp, "mpn", None)
            has_mpn = bool(mpn)
            header_offset = 18.0 if has_mpn else 15.0
            max_pin_rows = max(len(left_pins), len(right_pins), 2)
            ch = max(34.0, header_offset + (max_pin_rows - 1) * pin_pitch + 6.0)
            cy = row_top_y - ch
            comp_boxes.append((cx, cy, cw, ch))

            # IC Body Box
            ax.add_patch(
                patches.Rectangle((cx, cy), cw, ch, facecolor="#ffffff", edgecolor="#334155", linewidth=1.5, zorder=2)
            )

            # Component header inside box
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
                # Part number (MPN)
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
                # Package
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
                ax.plot([cx - stub_len, cx], [py, py], color="#475569", linewidth=1.0, zorder=2)
                ax.plot(cx - stub_len, py, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                ax.text(cx + 1.5, py, p.name, ha="left", va="center", fontsize=6.5, color="#1e293b", zorder=3)
                sheet_pin_coords[(fp.name, p.name)] = (cx - stub_len, py)
                pin_side_map[(fp.name, p.name)] = "left"
                comp_of_pin[(fp.name, p.name)] = c_idx

            # Right Pins
            for p_idx, p in enumerate(right_pins):
                py = cy + ch - header_offset - (p_idx * pin_pitch)
                ax.plot([cx + cw, cx + cw + stub_len], [py, py], color="#475569", linewidth=1.0, zorder=2)
                ax.plot(cx + cw + stub_len, py, marker="o", markersize=2.5, color="#0284c7", zorder=3)
                ax.text(cx + cw - 1.5, py, p.name, ha="right", va="center", fontsize=6.5, color="#1e293b", zorder=3)
                sheet_pin_coords[(fp.name, p.name)] = (cx + cw + stub_len, py)
                pin_side_map[(fp.name, p.name)] = "right"
                comp_of_pin[(fp.name, p.name)] = c_idx

        # Set of pins that are directly wired across the open channel
        wired_pins: set[Tuple[str, str]] = set()

        # Wire connections between pins on this sheet sharing a net
        # Only route a direct wire if the path stays completely within the open channel
        # and does not cross or touch any component body
        for net in all_nets:
            present_pins = [pair for pair in net.pins if pair in sheet_pin_coords]
            if len(present_pins) >= 2:
                for i in range(len(present_pins)):
                    for j in range(i + 1, len(present_pins)):
                        pair1, pair2 = present_pins[i], present_pins[j]
                        if pair1 in wired_pins or pair2 in wired_pins:
                            continue
                        c1, c2 = comp_of_pin[pair1], comp_of_pin[pair2]
                        s1, s2 = pin_side_map[pair1], pin_side_map[pair2]

                        # Ensure pair1 is on the left component and pair2 is on the right component
                        if c1 > c2:
                            pair1, pair2 = pair2, pair1
                            c1, c2 = c2, c1
                            s1, s2 = s2, s1

                        r1 = c1 // cols_per_row
                        r2 = c2 // cols_per_row

                        # Wires are cleanly drawn when connecting facing pins across the channel
                        # on the same row between adjacent columns
                        if r1 == r2 and c1 != c2 and (c2 == c1 + 1) and s1 == "right" and s2 == "left":
                            p1 = sheet_pin_coords[pair1]
                            p2 = sheet_pin_coords[pair2]
                            mid_x = (p1[0] + p2[0]) / 2.0

                            if abs(p1[1] - p2[1]) < 0.1:
                                # Straight horizontal wire
                                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#2563eb", linewidth=1.2, zorder=2)
                                ax.text(
                                    mid_x,
                                    p1[1] + 1.2,
                                    net.name,
                                    ha="center",
                                    va="bottom",
                                    fontsize=6.5,
                                    fontweight="bold",
                                    color="#0369a1",
                                    zorder=3,
                                )
                            else:
                                # Orthogonal dogleg wire
                                ax.plot(
                                    [p1[0], mid_x, mid_x, p2[0]],
                                    [p1[1], p1[1], p2[1], p2[1]],
                                    color="#2563eb",
                                    linewidth=1.2,
                                    zorder=2,
                                )
                                ax.text(
                                    mid_x,
                                    max(p1[1], p2[1]) + 1.2,
                                    net.name,
                                    ha="center",
                                    va="bottom",
                                    fontsize=6.5,
                                    fontweight="bold",
                                    color="#0369a1",
                                    zorder=3,
                                )
                            wired_pins.add(pair1)
                            wired_pins.add(pair2)

        # Place net labels for all unwired pins (off-sheet nets, or nets connected via net flags)
        for pair, (px, py) in sheet_pin_coords.items():
            if pair in wired_pins:
                continue
            net_name = pin_to_net.get(pair)
            if not net_name:
                continue

            side = pin_side_map[pair]
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

        pdf.savefig(fig)
