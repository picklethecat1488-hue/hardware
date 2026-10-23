"""Rerun visualizer integration for PCB 3D DRC violation markers and 2D Eye Diagram plots."""

from typing import Optional, List, Tuple
from model.pcb import PCBConfig
from provider.pcb.drc import DRCReport, DRCSeverity
from provider.pcb.eye_diagram import EyeDiagramResult

try:
    import rerun as rr
except ImportError:
    rr = None


COLOR_ERROR_RGBA = [239, 68, 68, 255]  # Red
COLOR_WARNING_RGBA = [245, 158, 11, 255]  # Amber
COLOR_INFO_RGBA = [59, 130, 246, 255]  # Blue
DEFAULT_MARKER_RADIUS_M = 0.0015


def log_drc_report(
    report: DRCReport,
    board_thickness_mm: float = 1.6,
    prefix: str = "world/pcb/drc",
) -> None:
    """Log 3D visual violation markers, callout text, and summary report to Rerun.

    Args:
        report: Design rule check report containing violations.
        board_thickness_mm: Board thickness in mm for Z positioning.
        prefix: Rerun entity path root for DRC markers.
    """
    if rr is None:
        return

    # Log text summary
    rr.log(f"{prefix}/summary", rr.TextLog(report.summary()), static=True)

    positions = []
    colors = []
    labels = []
    radii = []

    for idx, v in enumerate(report.violations):
        color = COLOR_ERROR_RGBA if v.severity == DRCSeverity.ERROR else COLOR_WARNING_RGBA
        z_pos = (board_thickness_mm / 2.0) * 1e-3
        x_pos, y_pos = 0.0, 0.0

        if v.location is not None:
            x_pos = v.location[0] * 1e-3
            y_pos = v.location[1] * 1e-3
            if len(v.location) > 2 and v.location[2] != 0.0:
                z_pos = v.location[2] * 1e-3

        positions.append([x_pos, y_pos, z_pos])
        colors.append(color)
        labels.append(f"[{v.severity.upper()}] {v.rule_name}: {v.net_or_zone}")
        radii.append(DEFAULT_MARKER_RADIUS_M)

    if positions:
        rr.log(
            f"{prefix}/violations",
            rr.Points3D(
                positions=positions,
                colors=colors,
                labels=labels,
                radii=radii,
            ),
            static=True,
        )


def log_eye_diagram(
    result: EyeDiagramResult,
    prefix: str = "pcb/eye_diagram",
) -> None:
    """Log 2D eye diagram waveforms, compliance mask boundaries, and quantitative metrics to Rerun.

    Args:
        result: Eye diagram simulation result.
        prefix: Rerun entity path root for eye diagram data.
    """
    if rr is None:
        return

    # Log quantitative scalar figures of merit
    rr.log(f"{prefix}/metrics/eye_height_mv", rr.Scalars(float(result.eye_height_mv)))
    rr.log(f"{prefix}/metrics/eye_width_ps", rr.Scalars(float(result.eye_width_ps)))
    rr.log(f"{prefix}/metrics/jitter_ps", rr.Scalars(float(result.jitter_ps)))
    rr.log(f"{prefix}/metrics/attenuation_db", rr.Scalars(float(result.attenuation_db)))
    rr.log(f"{prefix}/metrics/mask_margin_mv", rr.Scalars(float(result.mask_margin_mv)))

    # Log folded 2D waveforms as 2D line strips
    all_strips = []
    t_coords = result.folded_time_ps
    for trace in result.folded_traces:
        strip = [[t, v] for t, v in zip(t_coords, trace)]
        all_strips.append(strip)

    if all_strips:
        rr.log(
            f"{prefix}/folded_waveforms",
            rr.LineStrips2D(
                all_strips,
                colors=[[56, 189, 248, 120]],  # Light blue with alpha
            ),
            static=True,
        )

    # Log hexagonal compliance mask polygon
    if "mask_polygon" in result.compliance_mask:
        mask_poly = result.compliance_mask["mask_polygon"]
        closed_poly = mask_poly + [mask_poly[0]]
        rr.log(
            f"{prefix}/compliance_mask",
            rr.LineStrips2D(
                [closed_poly],
                colors=[[239, 68, 68, 255]],  # Red boundary
            ),
            static=True,
        )
