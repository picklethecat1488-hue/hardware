"""build123d context manager and primitives for declarative PCB drill holes and mounting hole placement."""

from contextvars import ContextVar, Token
from typing import List, Optional, Sequence, Tuple, Union

from build123d import Cylinder, Location, LocationList, Pos

from model.pcb import MountingHoleModel

_current_drill_holes: ContextVar[Optional["BuildDrillHoles"]] = ContextVar("_current_drill_holes", default=None)


class BuildDrillHoles:
    """Context manager for declarative PCB drill hole and mounting hole placement."""

    def __init__(self, default_plated: bool = True, default_net: str = "GND") -> None:
        """Initialize drill holes builder context.

        Args:
            default_plated: Default plating status for holes.
            default_net: Default net connection for plated holes (typically GND).
        """
        self.default_plated = default_plated
        self.default_net = default_net
        self.holes: List[MountingHoleModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildDrillHoles":
        """Enter drill holes context and register as active builder."""
        self._token = _current_drill_holes.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit drill holes context and restore previous builder."""
        if self._token is not None:
            _current_drill_holes.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.mounting_holes.extend(self.holes)

    @classmethod
    def _get_context(cls) -> Optional["BuildDrillHoles"]:
        """Retrieve active drill holes builder context if present."""
        return _current_drill_holes.get()

    def add(self, item: Union[MountingHoleModel, Sequence[MountingHoleModel]]) -> None:
        """Append one or more mounting hole models directly."""
        if isinstance(item, MountingHoleModel):
            self.holes.append(item)
        else:
            self.holes.extend(item)

    def to_shapes(self, depth_mm: float = 10.0) -> List[Cylinder]:
        """Convert collected mounting holes to 3D cylinders for subtraction from CAD solids.

        Args:
            depth_mm: Height of cylinder along Z for clean boolean cutouts.

        Returns:
            List of build123d Cylinder shapes located at hole coordinates.
        """
        shapes: List[Cylinder] = []
        for h in self.holes:
            cyl = Cylinder(radius=h.drill_diameter_mm / 2.0, height=depth_mm)
            loc = Location(Pos(h.position_mm[0], h.position_mm[1], 0.0))
            shapes.append(cyl.locate(loc))
        return shapes


class MountingHole:
    """Mounting hole CAD primitive evaluating active build123d Location contexts."""

    def __init__(
        self,
        name: str = "MH",
        drill_diameter_mm: float = 3.2,
        pad_diameter_mm: Optional[float] = None,
        plated: Optional[bool] = None,
        net: Optional[str] = None,
        position: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Place mounting hole(s) at active CAD locations.

        Args:
            name: Hole identifier prefix (e.g. "MH").
            drill_diameter_mm: Finished hole drill diameter in mm.
            pad_diameter_mm: Annular copper pad diameter for plated holes.
            plated: Whether hole is plated through (defaults to context default).
            net: Net name if plated (defaults to context default).
            position: Explicit (x, y) coordinates if outside a Locations context.
        """
        self.models: List[MountingHoleModel] = []
        ctx = BuildDrillHoles._get_context()
        resolved_plated = plated if plated is not None else (ctx.default_plated if ctx else True)
        resolved_net = (
            net
            if net is not None
            else (ctx.default_net if ctx and resolved_plated else (None if not resolved_plated else "GND"))
        )
        resolved_pad = pad_diameter_mm or (drill_diameter_mm + 1.3 if resolved_plated else drill_diameter_mm)

        loc_ctx = LocationList._get_context()
        if loc_ctx and loc_ctx.locations:
            locations = loc_ctx.locations
            multiple = len(locations) > 1
            for idx, loc in enumerate(locations, start=1):
                hole_name = f"{name}{idx}" if multiple else name
                model = MountingHoleModel(
                    name=hole_name,
                    position_mm=(round(loc.position.X, 4), round(loc.position.Y, 4)),
                    drill_diameter_mm=drill_diameter_mm,
                    pad_diameter_mm=resolved_pad,
                    plated=resolved_plated,
                    net=resolved_net,
                )
                self.models.append(model)
                if ctx:
                    ctx.add(model)
        else:
            pos = position or (0.0, 0.0)
            model = MountingHoleModel(
                name=name,
                position_mm=(round(pos[0], 4), round(pos[1], 4)),
                drill_diameter_mm=drill_diameter_mm,
                pad_diameter_mm=resolved_pad,
                plated=resolved_plated,
                net=resolved_net,
            )
            self.models.append(model)
            if ctx:
                ctx.add(model)


# Alias for semantics
DrillHole = MountingHole
