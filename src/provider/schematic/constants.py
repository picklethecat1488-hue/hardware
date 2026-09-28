"""Constants, data classes, and pattern matchers for schematic diagram rendering."""

from dataclasses import dataclass, field
import fnmatch
from typing import Dict, List, Sequence, Tuple

from model.wiring import FootprintModel, NetModel, PinModel


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


POWER_NET_PATTERNS = (
    "*3V3*",
    "*5V*",
    "*1V8*",
    "*1V2*",
    "*VCC*",
    "*VDD*",
    "*VLOAD*",
    "*VBUS*",
    "*VBAT*",
    "*SENSOR_3V3*",
    "*PWR*",
    "*POWER*",
)


class PowerNetMatcher:
    """Matches net names against standard power rail wildcard glob patterns."""

    def __init__(self, patterns: Sequence[str] = POWER_NET_PATTERNS) -> None:
        """Initialize matcher with glob patterns.

        Args:
            patterns: Sequence of glob pattern strings to match against.
        """
        self.patterns = tuple(patterns)

    def __contains__(self, item: object) -> bool:
        """Return True if the net name matches any power net glob pattern.

        Args:
            item: Net name or string to test.
        """
        if not isinstance(item, str):
            return False
        name_u = item.upper()
        return any(fnmatch.fnmatch(name_u, pat) for pat in self.patterns)

    def is_power_net(self, name: str) -> bool:
        """Check if a net name matches power rail patterns.

        Args:
            name: Net name string.

        Returns:
            True if matching power rail pattern.
        """
        return name in self


POWER_NET_NAMES = PowerNetMatcher()
GROUND_NET_NAMES = {"GND", "GROUND", "VSS"}
JUMPER_BRIDGE_RADIUS_MM = 1.2
PIN_PITCH_MM = 5.0
PIN_NUMBER_OFFSET_MM = 2.5
STUB_SIGNAL_MM = 5.0
STUB_POWER_MM = 10.0
STUB_GROUND_MM = 18.0


def partition_component_pins(
    fp: FootprintModel,
    comp_side_overrides: Dict[str, str],
    pin_to_net: Dict[Tuple[str, str], str],
    has_breakout: bool = False,
) -> Tuple[List[PinModel], List[PinModel]]:
    """Partition component pins into left and right sides.

    If has_breakout is False, pins are sorted so power pins are at top and ground at bottom.
    If has_breakout is True, pins strictly maintain the declared breakout order.
    """
    left_pins = []
    right_pins = []
    for p in fp.pins:
        side_val = comp_side_overrides.get(p.name, p.side.value if hasattr(p, "side") else "left")
        if side_val in ("right", "top"):
            right_pins.append(p)
        else:
            left_pins.append(p)
    if not left_pins and not right_pins:
        left_pins = fp.pins[: len(fp.pins) // 2]
        right_pins = fp.pins[len(fp.pins) // 2 :]

    if not has_breakout:

        def _pin_sort_key(p: PinModel) -> int:
            net = pin_to_net.get((fp.name, p.name), "").upper()
            if net in POWER_NET_NAMES:
                return 0
            if net in GROUND_NET_NAMES:
                return 2
            return 1

        left_pins.sort(key=_pin_sort_key)
        right_pins.sort(key=_pin_sort_key)

    return left_pins, right_pins
