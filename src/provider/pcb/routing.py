"""build123d context managers and primitives for declarative PCB routing, vias, copper regions, and test points."""

from contextvars import ContextVar, Token
from typing import Any, List, Optional, Sequence, Tuple, Union

from model.pcb import CopperRegionModel, TestPointModel, TraceSegmentModel, ViaModel

_current_traces: ContextVar[Optional["BuildTraces"]] = ContextVar("_current_traces", default=None)
_current_vias: ContextVar[Optional["BuildVias"]] = ContextVar("_current_vias", default=None)
_current_regions: ContextVar[Optional["BuildCopperRegions"]] = ContextVar("_current_regions", default=None)
_current_test_points: ContextVar[Optional["BuildTestPoints"]] = ContextVar("_current_test_points", default=None)


class BuildTraces:
    """Context manager for declarative PCB copper trace routing."""

    def __init__(self, default_layer: str = "F.Cu", default_width_mm: float = 0.20) -> None:
        """Initialize trace routing builder context."""
        self.default_layer = default_layer
        self.default_width_mm = default_width_mm
        self.traces: List[TraceSegmentModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildTraces":
        """Enter trace builder context."""
        self._token = _current_traces.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit trace builder context."""
        if self._token is not None:
            _current_traces.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.traces.extend(self.traces)

    @classmethod
    def _get_context(cls) -> Optional["BuildTraces"]:
        """Retrieve active trace builder context if present."""
        return _current_traces.get()

    def add(self, item: Union[TraceSegmentModel, Sequence[TraceSegmentModel]]) -> None:
        """Append one or more trace segment models."""
        if isinstance(item, TraceSegmentModel):
            self.traces.append(item)
        else:
            self.traces.extend(item)


class Trace:
    """Declarative copper routing trace primitive evaluated inside a BuildTraces context."""

    def __init__(
        self,
        net: str,
        layer: Optional[str] = None,
        width_mm: Optional[float] = None,
        points: Optional[Sequence[Tuple[float, float]]] = None,
        start: Optional[Tuple[float, float]] = None,
        end: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Route a copper trace along polyline points or between start and end.

        Args:
            net: Electrical net name.
            layer: Copper layer (defaults to context default or F.Cu).
            width_mm: Trace conductor width in mm (defaults to context default).
            points: Ordered sequence of vertices (x, y) defining the trace route.
            start: Start coordinate (x, y) if 2-point trace.
            end: End coordinate (x, y) if 2-point trace.
        """
        ctx = BuildTraces._get_context()
        resolved_layer = layer or (ctx.default_layer if ctx else "F.Cu")
        resolved_width = width_mm or (ctx.default_width_mm if ctx else 0.20)
        self.segments: List[TraceSegmentModel] = []

        pts: List[Tuple[float, float]] = []
        if points:
            pts = list(points)
        elif start is not None and end is not None:
            pts = [start, end]

        for i in range(len(pts) - 1):
            seg = TraceSegmentModel(
                start_mm=(round(pts[i][0], 4), round(pts[i][1], 4)),
                end_mm=(round(pts[i + 1][0], 4), round(pts[i + 1][1], 4)),
                width_mm=resolved_width,
                layer=resolved_layer,
                net=net,
            )
            self.segments.append(seg)
            if ctx:
                ctx.add(seg)


class BuildVias:
    """Context manager for declarative PCB interlayer via placement."""

    def __init__(
        self,
        default_layer_start: str = "F.Cu",
        default_layer_end: str = "B.Cu",
        default_drill_mm: float = 0.20,
        default_pad_mm: float = 0.45,
    ) -> None:
        """Initialize via builder context."""
        self.default_layer_start = default_layer_start
        self.default_layer_end = default_layer_end
        self.default_drill_mm = default_drill_mm
        self.default_pad_mm = default_pad_mm
        self.vias: List[ViaModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildVias":
        """Enter via builder context."""
        self._token = _current_vias.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit via builder context."""
        if self._token is not None:
            _current_vias.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.vias.extend(self.vias)

    @classmethod
    def _get_context(cls) -> Optional["BuildVias"]:
        """Retrieve active via builder context if present."""
        return _current_vias.get()

    def add(self, item: Union[ViaModel, Sequence[ViaModel]]) -> None:
        """Append one or more via models."""
        if isinstance(item, ViaModel):
            self.vias.append(item)
        else:
            self.vias.extend(item)


class Via:
    """Declarative interlayer via primitive evaluated inside a BuildVias context."""

    def __init__(
        self,
        net: str,
        at: Tuple[float, float],
        drill_mm: Optional[float] = None,
        diameter_mm: Optional[float] = None,
        layer1: Optional[str] = None,
        layer2: Optional[str] = None,
    ) -> None:
        """Place an interlayer via at coordinates.

        Args:
            net: Electrical net name.
            at: Center position (x, y) in mm.
            drill_mm: Hole drill diameter in mm.
            diameter_mm: Annular copper pad outer diameter in mm.
            layer1: Starting copper layer.
            layer2: Ending copper layer.
        """
        ctx = BuildVias._get_context()
        resolved_drill = drill_mm or (ctx.default_drill_mm if ctx else 0.20)
        resolved_pad = diameter_mm or (ctx.default_pad_mm if ctx else 0.45)
        resolved_l1 = layer1 or (ctx.default_layer_start if ctx else "F.Cu")
        resolved_l2 = layer2 or (ctx.default_layer_end if ctx else "B.Cu")

        self.model = ViaModel(
            position_mm=(round(at[0], 4), round(at[1], 4)),
            drill_diameter_mm=resolved_drill,
            pad_diameter_mm=resolved_pad,
            layer_start=resolved_l1,
            layer_end=resolved_l2,
            net=net,
        )
        if ctx:
            ctx.add(self.model)


class BuildCopperRegions:
    """Context manager for declarative PCB copper pours, planes, and shielding fills."""

    def __init__(self, default_layer: str = "In1.Cu", default_net: str = "GND") -> None:
        """Initialize copper region builder context."""
        self.default_layer = default_layer
        self.default_net = default_net
        self.regions: List[CopperRegionModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildCopperRegions":
        """Enter copper region builder context."""
        self._token = _current_regions.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit copper region builder context."""
        if self._token is not None:
            _current_regions.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.copper_regions.extend(self.regions)

    @classmethod
    def _get_context(cls) -> Optional["BuildCopperRegions"]:
        """Retrieve active copper region builder context if present."""
        return _current_regions.get()

    def add(self, item: Union[CopperRegionModel, Sequence[CopperRegionModel]]) -> None:
        """Append one or more copper region models."""
        if isinstance(item, CopperRegionModel):
            self.regions.append(item)
        else:
            self.regions.extend(item)


class CopperRegion:
    """Declarative copper plane or shield zone primitive evaluated inside a BuildCopperRegions context."""

    def __init__(
        self,
        net: Optional[str] = None,
        layer: Optional[str] = None,
        outline: Optional[Sequence[Tuple[float, float]]] = None,
        clearance_mm: float = 0.20,
        priority: int = 1,
    ) -> None:
        """Define a filled polygonal copper region.

        Args:
            net: Electrical net name (defaults to GND).
            layer: Target copper layer.
            outline: Sequence of boundary polygon vertices [(x1, y1), (x2, y2), ...].
            clearance_mm: Electrical clearance to foreign copper tracks and pads.
            priority: Plane fill priority.
        """
        ctx = BuildCopperRegions._get_context()
        resolved_net = net or (ctx.default_net if ctx else "GND")
        resolved_layer = layer or (ctx.default_layer if ctx else "In1.Cu")
        pts = [(round(p[0], 4), round(p[1], 4)) for p in (outline or [])]

        self.model = CopperRegionModel(
            net=resolved_net,
            layer=resolved_layer,
            polygon_points_mm=pts,
            clearance_mm=clearance_mm,
            priority=priority,
        )
        if ctx:
            ctx.add(self.model)


# Alias
CopperZone = CopperRegion


class BuildTestPoints:
    """Context manager for declarative PCB test point placement."""

    def __init__(
        self,
        default_layer: str = "F.Cu",
        default_diameter_mm: float = 1.40,
        default_drill_diameter_mm: float = 0.80,
    ) -> None:
        """Initialize test point builder context.

        Args:
            default_layer: Default copper layer ('F.Cu' or 'B.Cu').
            default_diameter_mm: Default outer pad annular ring diameter in mm.
            default_drill_diameter_mm: Default plated through-hole drill diameter in mm for probe / fly wire insertion.
        """
        self.default_layer = default_layer
        self.default_diameter_mm = default_diameter_mm
        self.default_drill_diameter_mm = default_drill_diameter_mm
        self.test_points: List[TestPointModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildTestPoints":
        """Enter test point builder context."""
        self._token = _current_test_points.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit test point builder context."""
        if self._token is not None:
            _current_test_points.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.test_points.extend(self.test_points)

    @classmethod
    def _get_context(cls) -> Optional["BuildTestPoints"]:
        """Retrieve active test point builder context if present."""
        return _current_test_points.get()

    def add(self, item: Union[TestPointModel, Sequence[TestPointModel]]) -> None:
        """Append one or more test point models."""
        if isinstance(item, TestPointModel):
            self.test_points.append(item)
        else:
            self.test_points.extend(item)

    def to_shapes(self, depth_mm: float = 10.0) -> List[Any]:
        """Convert collected test point drill holes to 3D cylinders for subtraction from CAD solids.

        Args:
            depth_mm: Height of cylinder along Z for clean boolean cutouts.

        Returns:
            List of build123d Cylinder shapes located at test point coordinates.
        """
        from build123d import Cylinder, Location, Pos

        shapes = []
        for tp in self.test_points:
            cyl = Cylinder(radius=tp.drill_diameter_mm / 2.0, height=depth_mm)
            loc = Location(Pos(tp.position_mm[0], tp.position_mm[1], 0.0))
            shapes.append(cyl.locate(loc))
        return shapes


class TestPoint:
    """Declarative test point primitive evaluated inside a BuildTestPoints context."""

    def __init__(
        self,
        name: str,
        net: str,
        at: Tuple[float, float],
        diameter_mm: Optional[float] = None,
        drill_diameter_mm: Optional[float] = None,
        plated: bool = True,
        layer: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        """Place an exposed copper / through-hole test point for probing or wire soldering.

        Args:
            name: Test point identifier (e.g. TP_SDA, TP_GND).
            net: Electrical net name.
            at: Position coordinate (x, y) in mm relative to board center.
            diameter_mm: Outer pad annular diameter in mm.
            drill_diameter_mm: Hole drill diameter in mm for probe / fly wire insertion.
            plated: Whether test point through-hole is copper plated.
            layer: Copper layer ('F.Cu' or 'B.Cu').
            label: Optional silkscreen text annotation.
        """
        ctx = BuildTestPoints._get_context()
        resolved_dia = diameter_mm or (ctx.default_diameter_mm if ctx else 1.40)
        resolved_drill = drill_diameter_mm or (ctx.default_drill_diameter_mm if ctx else 0.80)
        resolved_layer = layer or (ctx.default_layer if ctx else "F.Cu")

        self.model = TestPointModel(
            name=name,
            net=net,
            position_mm=(round(at[0], 4), round(at[1], 4)),
            pad_diameter_mm=resolved_dia,
            drill_diameter_mm=resolved_drill,
            plated=plated,
            layer=resolved_layer,
            label=label or name,
        )
        if ctx:
            ctx.add(self.model)
