"""PCB design engine package for 4-8 layer rigid and flex boards, high-speed signals, and capacitive sensing."""

from .drc import PCBDesignRulesChecker, DRCReport, DRCViolation, DRCSeverity
from .bga_fanout import BGAFanoutRouter, BGAPad, BGAEscapeRoute
from .capacitive import CapacitiveSensingGenerator, CapacitiveGeometry, HatchLine
from .exporter import PCBExporter
from .eye_diagram import EyeDiagramSimulator, EyeDiagramConfig, EyeDiagramResult
from .rerun_logger import log_drc_report, log_eye_diagram
from .silkscreen import BuildSilkscreen, SilkscreenText

__all__ = [
    "PCBDesignRulesChecker",
    "DRCReport",
    "DRCViolation",
    "DRCSeverity",
    "BGAFanoutRouter",
    "BGAPad",
    "BGAEscapeRoute",
    "CapacitiveSensingGenerator",
    "CapacitiveGeometry",
    "HatchLine",
    "PCBExporter",
    "EyeDiagramSimulator",
    "EyeDiagramConfig",
    "EyeDiagramResult",
    "log_drc_report",
    "log_eye_diagram",
    "BuildSilkscreen",
    "SilkscreenText",
]
