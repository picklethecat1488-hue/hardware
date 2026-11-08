"""build123d context managers and primitives for declarative PCB routing, vias, copper regions, and test points."""

import math
from contextvars import ContextVar, Token
from enum import StrEnum
from typing import Any, List, Optional, Sequence, Tuple, Union

from model.pcb import CopperRegionModel, RouteStyle, TestPointModel, TraceSegmentModel, ViaModel
from model.wiring import PinRef

_current_traces: ContextVar[Optional["BuildTraces"]] = ContextVar("_current_traces", default=None)
_current_vias: ContextVar[Optional["BuildVias"]] = ContextVar("_current_vias", default=None)
_current_regions: ContextVar[Optional["BuildCopperRegions"]] = ContextVar("_current_regions", default=None)
_current_test_points: ContextVar[Optional["BuildTestPoints"]] = ContextVar("_current_test_points", default=None)


class BuildTraces:
    """Context manager for declarative PCB copper trace routing."""

    def __init__(
        self,
        default_layer: str = "F.Cu",
        default_width_mm: float = 0.20,
        layer: Optional[str] = None,
    ) -> None:
        """Initialize trace routing builder context."""
        self.default_layer = layer or default_layer
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


def _resolve_coord(pt: Any) -> Tuple[float, float]:
    """Extract (x, y) coordinate from a PinRef, tuple, list, or object with pos attribute."""
    if isinstance(pt, PinRef):
        return (pt.x, pt.y)
    if hasattr(pt, "pos_2d"):
        return tuple(pt.pos_2d)
    if hasattr(pt, "pos"):
        return tuple(pt.pos)
    if isinstance(pt, (tuple, list)) and len(pt) >= 2:
        return (round(float(pt[0]), 4), round(float(pt[1]), 4))
    raise ValueError(f"Cannot resolve coordinate from: {pt}")


def _discretize_curve(path: Any, tolerance_mm: float = 0.05) -> List[Tuple[float, float]]:
    """Discretize build123d curve, wire, or edge geometry into ordered planar (x, y) vertices."""
    wire = path
    if hasattr(path, "wire"):
        wire = path.wire()
    elif hasattr(path, "line"):
        wire = path.line

    edges = []
    if hasattr(wire, "edges"):
        edges = list(wire.edges())
    elif hasattr(wire, "__iter__"):
        edges = list(wire)
    else:
        edges = [wire]

    pts: List[Tuple[float, float]] = []
    for edge in edges:
        if not hasattr(edge, "positions"):
            continue
        geom_str = str(getattr(edge, "geom_type", "")).upper()
        if "LINE" in geom_str:
            vecs = edge.positions([0.0, 1.0])
        else:
            length = getattr(edge, "length", 1.0)
            num_samples = max(8, int(math.ceil(length / max(tolerance_mm, 0.1))))
            params = [i / (num_samples - 1) for i in range(num_samples)]
            vecs = edge.positions(params)

        for v in vecs:
            p = (round(float(v.X), 4), round(float(v.Y), 4))
            if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > 1e-4:
                pts.append(p)

    return pts


def _generate_chamfer_45(p0: Tuple[float, float], p1: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Generate 45-degree chamfered path between p0 and p1."""
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    if abs(dx) < 1e-4 or abs(dy) < 1e-4 or abs(abs(dx) - abs(dy)) < 1e-4:
        return [p0, p1]

    if abs(dx) > abs(dy):
        sx = 1.0 if dx > 0 else -1.0
        x_turn = p1[0] - sx * abs(dy)
        return [p0, (round(x_turn, 4), p0[1]), p1]
    else:
        sy = 1.0 if dy > 0 else -1.0
        y_turn = p1[1] - sy * abs(dx)
        return [p0, (p0[0], round(y_turn, 4)), p1]


class Trace:
    """Declarative copper routing trace primitive evaluated inside a BuildTraces context."""

    def __init__(
        self,
        net: str,
        layer: Optional[str] = None,
        width_mm: Optional[float] = None,
        points: Optional[Sequence[Union[PinRef, Tuple[float, float]]]] = None,
        start: Optional[Union[PinRef, Tuple[float, float]]] = None,
        end: Optional[Union[PinRef, Tuple[float, float]]] = None,
        path: Optional[Any] = None,
    ) -> None:
        """Route a copper trace along polyline points, between start and end, or from build123d curve.

        Args:
            net: Electrical net name.
            layer: Copper layer (defaults to context default or F.Cu).
            width_mm: Trace conductor width in mm (defaults to context default).
            points: Ordered sequence of vertices defining the trace route.
            start: Start coordinate or PinRef if 2-point trace.
            end: End coordinate or PinRef if 2-point trace.
            path: Optional build123d Wire, BuildLine, or Edge compound to discretize.
        """
        ctx = BuildTraces._get_context()
        resolved_layer = layer or (ctx.default_layer if ctx else "F.Cu")
        resolved_width = width_mm or (ctx.default_width_mm if ctx else 0.20)
        self.segments: List[TraceSegmentModel] = []

        pts: List[Tuple[float, float]] = []
        if path is not None:
            pts = _discretize_curve(path)
        elif points:
            pts = [_resolve_coord(p) for p in points]
        elif start is not None and end is not None:
            pts = [_resolve_coord(start), _resolve_coord(end)]

        for i in range(len(pts) - 1):
            p1 = pts[i]
            p2 = pts[i + 1]
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-4:
                seg = TraceSegmentModel(
                    start_mm=(round(p1[0], 4), round(p1[1], 4)),
                    end_mm=(round(p2[0], 4), round(p2[1], 4)),
                    width_mm=resolved_width,
                    layer=resolved_layer,
                    net=net,
                )
                self.segments.append(seg)
                if ctx:
                    ctx.add(seg)


class Route:
    """Declarative routed trace primitive supporting styled geometry, pin snapping, and inline vias."""

    def __init__(
        self,
        net: str,
        start: Optional[Union[PinRef, Tuple[float, float]]] = None,
        end: Optional[Union[PinRef, Tuple[float, float]]] = None,
        style: Union[RouteStyle, str] = RouteStyle.CHAMFER_45,
        layer: Optional[str] = None,
        width_mm: Optional[float] = None,
        via_at: Optional[Sequence[Union[PinRef, Tuple[float, float]]]] = None,
        layer_end: Optional[str] = None,
        via_drill_mm: Optional[float] = None,
        via_pad_mm: Optional[float] = None,
        start_mm: Optional[Union[PinRef, Tuple[float, float]]] = None,
        end_mm: Optional[Union[PinRef, Tuple[float, float]]] = None,
    ) -> None:
        """Route an electrical net connection between start and end.

        Args:
            net: Electrical net name.
            start: Starting pin or coordinate.
            end: Ending pin or coordinate.
            style: Geometric routing style (RouteStyle.CHAMFER_45, STRAIGHT, CURVED, MANHATTAN).
            layer: Starting copper layer (default 'F.Cu').
            width_mm: Conductor width in mm.
            via_at: Optional via coordinates along the route for interlayer transitions.
            layer_end: Copper layer after via transition (default 'B.Cu').
            via_drill_mm: Via drill hole diameter in mm.
            via_pad_mm: Via annular pad outer diameter in mm.
            start_mm: Alias for start.
            end_mm: Alias for end.
        """
        ctx = BuildTraces._get_context()
        resolved_layer = layer or (ctx.default_layer if ctx else "F.Cu")
        resolved_layer_end = layer_end or "B.Cu"
        resolved_width = width_mm or (ctx.default_width_mm if ctx else 0.20)
        route_style = RouteStyle(style) if isinstance(style, str) else style

        p_start = _resolve_coord(start if start is not None else start_mm)
        p_end = _resolve_coord(end if end is not None else end_mm)
        via_pts = [_resolve_coord(v) for v in (via_at or [])]

        waypoints = [p_start] + via_pts + [p_end]
        self.segments: List[TraceSegmentModel] = []
        self.vias: List[ViaModel] = []

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()

        current_layer = resolved_layer
        for i in range(len(waypoints) - 1):
            w0 = waypoints[i]
            w1 = waypoints[i + 1]

            # Generate segment points according to style
            match route_style:
                case RouteStyle.STRAIGHT:
                    seg_pts = [w0, w1]
                case RouteStyle.MANHATTAN:
                    mid_x = (w0[0] + w1[0]) / 2.0
                    seg_pts = [w0, (round(mid_x, 4), w0[1]), (round(mid_x, 4), w1[1]), w1]
                case RouteStyle.CHAMFER_45:
                    seg_pts = _generate_chamfer_45(w0, w1)
                case RouteStyle.CURVED:
                    mid_x = (w0[0] + w1[0]) / 2.0
                    seg_pts = [w0, (round(mid_x, 4), w0[1]), (round(mid_x, 4), w1[1]), w1]
                case _:
                    seg_pts = [w0, w1]

            # Create trace segments for this leg
            for j in range(len(seg_pts) - 1):
                pt_a = seg_pts[j]
                pt_b = seg_pts[j + 1]
                if math.hypot(pt_b[0] - pt_a[0], pt_b[1] - pt_a[1]) > 1e-4:
                    seg = TraceSegmentModel(
                        start_mm=(round(pt_a[0], 4), round(pt_a[1], 4)),
                        end_mm=(round(pt_b[0], 4), round(pt_b[1], 4)),
                        width_mm=resolved_width,
                        layer=current_layer,
                        net=net,
                    )
                    self.segments.append(seg)
                    if ctx:
                        ctx.add(seg)

            # If transitioning at a via
            if i < len(via_pts):
                v_pos = waypoints[i + 1]
                v_model = ViaModel(
                    position_mm=(round(v_pos[0], 4), round(v_pos[1], 4)),
                    drill_diameter_mm=via_drill_mm or 0.20,
                    pad_diameter_mm=via_pad_mm or 0.45,
                    layer_start=current_layer,
                    layer_end=resolved_layer_end,
                    net=net,
                )
                self.vias.append(v_model)
                if active_pcb is not None:
                    active_pcb.vias.append(v_model)
                v_ctx = BuildVias._get_context()
                if v_ctx is not None:
                    v_ctx.add(v_model)

                # Switch active layer for next leg
                current_layer = resolved_layer_end


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
            for r in self.regions:
                if r not in active_pcb.copper_regions:
                    active_pcb.copper_regions.append(r)

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
