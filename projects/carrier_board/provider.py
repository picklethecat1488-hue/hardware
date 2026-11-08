"""Test Board rigid-flex PCB and enclosure geometry provider."""

from pathlib import Path
from typing import cast, Callable, Sequence, Any, Optional
from functools import cached_property
from build123d import (
    Align,
    BuildPart,
    BuildSketch,
    Polygon,
    Rectangle,
    RectangleRounded,
    Plane,
    Location,
    RigidJoint,
    extrude,
    offset,
    Box,
    Circle,
    Cone,
    Cylinder,
    fillet,
    Locations,
    Axis,
    Mode as BuildMode,
    add,
    Text,
    FontStyle,
)
from model import Wiring, DiagramOptions, DiagramStyle
from model.pcb import (
    BoardType,
    LayerType,
    MountingHoleModel,
    SilkscreenTextModel,
    SilkscreenGraphicModel,
    TraceSegmentModel,
    ViaModel,
    PCBConfig,
)
from provider import (
    Provider,
    discover_provider,
    Room,
    Mode,
    Simulate,
    WiringDiagram,
    BuildSilkscreen,
    SilkscreenText,
    SilkscreenRect,
    SilkscreenLine,
    SilkscreenPolygon,
    BuildStackup,
    StackupLayer,
    BuildDrillHoles,
    MountingHole,
    BuildCopperRegions,
    CopperRegion,
    BuildTestPoints,
    TestPoint,
    BuildTraces,
    Trace,
    BuildVias,
    Via,
    BuildPcb,
    BuildFlexPCB,
    FlexType,
)
from projects_config import CarrierBoardConfig
from .cad import CarrierBoardCAD
from .pcb import (
    CarrierBoardPCB,
    build_carrier_board_wiring,
    build_carrier_board_pcb_config,
    build_carrier_board_system_wiring,
    get_flex_tail_traces,
    get_flex_tail_vias,
)


@discover_provider
class CarrierBoardProvider(CarrierBoardCAD, CarrierBoardPCB, Provider):
    """Provider for 6-layer rigid-flex carrier board and enclosure geometry."""

    __test__ = False

    CARRIER_BOARD_COLOR: tuple[float, float, float] = (0.08, 0.40, 0.20)
    FLEX_TAIL_COVERLAY_COLOR: tuple[float, float, float] = (0.12, 0.12, 0.12)

    @cached_property
    def default_config(self) -> CarrierBoardConfig:
        """Return the default configuration for the carrier board project."""
        measurements_file = str(Path(__file__).parent / "measurements.yaml")
        return CarrierBoardConfig(measurements_path=measurements_file)

    @property
    def settings(self) -> CarrierBoardConfig:
        """Return typed configuration settings."""
        return cast(CarrierBoardConfig, super().settings)

    @property
    def pcb_config(self) -> PCBConfig:
        """Return the in-memory strongly typed PCBConfig model."""
        if not hasattr(self, "_cached_pcb_config") or self._cached_pcb_config is None:
            self._building_pcb_config = True
            try:
                self._cached_pcb_config = build_carrier_board_pcb_config(self)
            finally:
                self._building_pcb_config = False
        return self._cached_pcb_config

    @property
    def wiring(self) -> Wiring:
        """Return the in-memory declarative Wiring model."""
        if not hasattr(self, "_cached_wiring") or self._cached_wiring is None:
            self._cached_wiring = build_carrier_board_wiring()
        return self._cached_wiring

    @property
    def system_wiring(self) -> Wiring:
        """Return top-down architecture system wiring for diagram rendering."""
        return build_carrier_board_system_wiring()

    @property
    def part(self) -> dict[str, Callable[..., Any]]:
        """Map part names to CAD builder methods."""
        return {
            "carrier_board": self.carrier_board,
            "flex_tail": self.flex_tail,
            "enclosure_bottom": self.enclosure_bottom,
            "enclosure_lid": self.enclosure_lid,
            "led_cover": self.led_cover,
            "battery_cover": self.battery_cover,
        }

    @property
    def view(self) -> dict[str, Callable[[Room, Mode], None]]:
        """Map view targets to room population functions."""
        return {
            "product": self.view_product,
            "carrier_board": self.view_carrier_board,
            "flex_tail": self.view_flex_tail,
            "battery_cover": self.view_battery_cover,
        }

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """Map diagram targets to render methods."""
        return {
            "product": self.diagram_product,
            "wiring": self.diagram_wiring,
        }

    def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
        """Return flying probe simulation and electrical verification hooks."""
        from .simulate_hooks import get_simulate_hooks_impl as impl

        return impl(self, sim_name)

    @property
    def config(self) -> dict[str, Callable[[str, Optional[str]], Any]]:
        """Map Modes to configuration handler methods."""
        from projects.carrier_board.config import config_route

        def _handler(target: str, subassembly: Optional[str]) -> Any:
            if "route" in target:
                return config_route(self, target, subassembly)
            return None

        return {
            Mode.DEFAULT: _handler,
            "default": _handler,
            "route": _handler,
        }
