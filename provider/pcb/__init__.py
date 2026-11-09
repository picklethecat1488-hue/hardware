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
from model.pcb import FlexType, PinSideDef, ElectrodeType, ElectrodeShape
from .routing import (
    BuildTraces,
    Trace,
    make_trace,
    Route,
    RouteStyle,
    BuildVias,
    Via,
    BuildCopperRegions,
    CopperRegion,
    BuildTestPoints,
    TestPoint,
)
from .jax_router import JaxPCBRouter
from .layout import BuildComponents, Component
from model.wiring import PinListModel, PinModel, Pin, PinSide

PinList = PinListModel
from .wiring import BuildWiring, Net, DiffPair, Bus
from .test_steps import BuildAssemblyTests, TestStep
from .schematic import BuildSchematic, SchematicConfig, SchematicSheet
from .rules import (
    BuildDesignRules,
    BuildNetClasses,
    BuildFlexZones,
    BuildObstacles,
    BuildCapacitiveSensors,
)
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
    "make_trace",
    "Route",
    "RouteStyle",
    "BuildVias",
    "Via",
    "BuildCopperRegions",
    "CopperRegion",
    "BuildTestPoints",
    "TestPoint",
    "BuildPcb",
    "BuildFlexPCB",
    "FlexType",
    "ElectrodeType",
    "ElectrodeShape",
    "find_empty_space_for_label",
    "JaxPCBRouter",
    "package_supplier_pcb_files",
    "generate_pcb_project_summary",
    "BuildAssemblyTests",
    "TestStep",
    "BuildSchematic",
    "SchematicConfig",
    "SchematicSheet",
    "BuildDesignRules",
    "BuildNetClasses",
    "BuildFlexZones",
    "BuildObstacles",
    "BuildCapacitiveSensors",
    "PcbMetadata",
    "BuildComponents",
    "Component",
    "Pin",
    "PinList",
    "PinListModel",
    "PinModel",
    "PinSide",
    "PinSideDef",
    "BuildWiring",
    "Net",
    "DiffPair",
    "Bus",
]
