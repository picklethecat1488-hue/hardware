"""Multi-page Table of Contents and Bill of Footprints pagination and rendering."""

from typing import List, Optional, Tuple

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import matplotlib.patches as patches

from model.pcb import PCBConfig
from model.wiring import FootprintModel, NetModel
from provider.schematic.constants import _SchematicSheetPlan, _TOCPagePlan


class SchematicTOCRenderer:
    """Plans and renders multi-page engineering Table of Contents and schedules."""

    @staticmethod
    def plan_pdf_toc_pages(
        fps: List[FootprintModel],
        nets: List[NetModel],
        sheet_plans: List[_SchematicSheetPlan],
    ) -> List[_TOCPagePlan]:
        """Plan and paginate the Table of Contents across one or more drawing sheets.

        Args:
            fps: List of footprints across the design.
            nets: List of signal and power nets.
            sheet_plans: List of planned schematic drawing sheets.

        Returns:
            List of planned Table of Contents pages with paginated rows.
        """
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

    @staticmethod
    def render_pdf_toc_page(
        pdf: PdfPages,
        board_name: str,
        board_type: str,
        layer_count: int,
        plan: _TOCPagePlan,
        total_toc_pages: int,
        total_pages: int,
        config: Optional[PCBConfig] = None,
    ) -> None:
        """Render a single paginated Table of Contents and Interconnect Bill of Materials sheet.

        Args:
            pdf: Active PdfPages target.
            board_name: Name of the board project.
            board_type: Technology type string (e.g. RIGID, FLEX).
            layer_count: Number of copper layers.
            plan: Page plan data with rows to render.
            total_toc_pages: Count of total TOC sheets.
            total_pages: Count of all pages in the PDF document.
            config: Optional PCB configuration model.
        """
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

        board_rev = config.revision if config and config.revision else "1.0"
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
