"""PCB design engine package for 4-8 layer rigid and flex boards, high-speed signals, and capacitive sensing."""

from .drc import PCBDesignRulesChecker, DRCReport, DRCViolation, DRCSeverity, DRCViolationCollection, DRCRuleName
from .bga_fanout import BGAFanoutRouter, BGAPad, BGAEscapeRoute
from .capacitive import CapacitiveSensingGenerator, CapacitiveGeometry, HatchLine
from .exporter import PCBExporter
from .eye_diagram import EyeDiagramSimulator, EyeDiagramConfig, EyeDiagramResult
from .rerun_logger import log_drc_report, log_eye_diagram
from .silkscreen import (
    BuildSilkscreen,
    SilkscreenText,
    SilkscreenRect,
    SilkscreenLine,
    SilkscreenPolygon,
    find_empty_space_for_label,
)
from .stackup import BuildStackup, StackupLayer
from .drill_holes import BuildDrillHoles, MountingHole, DrillHole
from .board import BuildPcb, BuildFlexPCB
from model.pcb import FlexType
from .routing import (
    BuildTraces,
    Trace,
    Route,
    RouteStyle,
    BuildVias,
    Via,
    BuildCopperRegions,
    CopperRegion,
    CopperZone,
    BuildTestPoints,
    TestPoint,
)
from .jax_router import JaxPCBRouter
from .layout import BuildComponents, Component
from .wiring import BuildWiring, Net, DiffPair, Bus
from .test_steps import BuildTestSteps, BuildAssemblyTestSteps, AssemblyTestMetadata, TestStep
from .schematic import SchematicMetadata, SchematicSheet
from .metadata import PcbMetadata
from .supplier import package_supplier_pcb_files, generate_pcb_project_summary

__all__ = [
    "PCBDesignRulesChecker",
    "DRCReport",
    "DRCViolation",
    "DRCSeverity",
    "DRCRuleName",
    "DRCViolationCollection",
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
    "BuildStackup",
    "StackupLayer",
    "BuildDrillHoles",
    "MountingHole",
    "DrillHole",
    "BuildTraces",
    "Trace",
    "Route",
    "RouteStyle",
    "BuildVias",
    "Via",
    "BuildCopperRegions",
    "CopperRegion",
    "CopperZone",
    "BuildTestPoints",
    "TestPoint",
    "BuildPcb",
    "BuildFlexPCB",
    "FlexType",
    "find_empty_space_for_label",
    "JaxPCBRouter",
    "package_supplier_pcb_files",
    "generate_pcb_project_summary",
    "BuildTestSteps",
    "BuildAssemblyTestSteps",
    "AssemblyTestMetadata",
    "TestStep",
    "SchematicMetadata",
    "SchematicSheet",
    "PcbMetadata",
    "BuildComponents",
    "Component",
    "BuildWiring",
    "Net",
    "DiffPair",
    "Bus",
]
