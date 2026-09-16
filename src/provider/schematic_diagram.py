"""Dedicated vector schematic diagram generator for electronic components and nets."""

from pathlib import Path
from typing import List, Tuple, Optional, Any
from model.pcb import PCBConfig
from model.wiring import Wiring, FootprintModel, NetModel


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

        # Calculate bounding dimensions
        fps = self.wiring.footprints
        svg_w = max(900, len(fps) * 220)
        svg_h = 700

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

        # Arrange components in schematic grid
        comp_spacing_x = 240.0
        start_x = 60.0
        start_y = 120.0

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
