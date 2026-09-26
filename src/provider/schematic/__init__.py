"""Schematic diagram generation, symbol layout, passive rendering, and wire routing."""

from provider.schematic.bbox import SchematicBoundingBoxCalculator
from provider.schematic.constants import (
    GROUND_NET_NAMES,
    JUMPER_BRIDGE_RADIUS_MM,
    PIN_NUMBER_OFFSET_MM,
    PIN_PITCH_MM,
    POWER_NET_NAMES,
    POWER_NET_PATTERNS,
    STUB_GROUND_MM,
    STUB_POWER_MM,
    STUB_SIGNAL_MM,
    PowerNetMatcher,
    _SchematicSheetPlan,
    _TOCPagePlan,
)
from provider.schematic.jumper import draw_vertical_wire_with_jumpers
from provider.schematic.passives import SchematicPassiveClassifier, SchematicPassiveDrawer
from provider.schematic.toc import SchematicTOCRenderer
from provider.schematic.truth_table import SchematicTruthTableDrawer
from provider.schematic.wire_router import SchematicWireSegmentPlanner

__all__ = [
    "GROUND_NET_NAMES",
    "JUMPER_BRIDGE_RADIUS_MM",
    "PIN_NUMBER_OFFSET_MM",
    "PIN_PITCH_MM",
    "POWER_NET_NAMES",
    "POWER_NET_PATTERNS",
    "PowerNetMatcher",
    "SchematicBoundingBoxCalculator",
    "SchematicPassiveClassifier",
    "SchematicPassiveDrawer",
    "SchematicTOCRenderer",
    "SchematicTruthTableDrawer",
    "SchematicWireSegmentPlanner",
    "STUB_GROUND_MM",
    "STUB_POWER_MM",
    "STUB_SIGNAL_MM",
    "_SchematicSheetPlan",
    "_TOCPagePlan",
    "draw_vertical_wire_with_jumpers",
]
