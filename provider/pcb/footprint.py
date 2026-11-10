"""build123d context manager and primitives for declarative PCB component footprint definition."""

from contextvars import ContextVar, Token
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

from build123d import BuildPart, LocationList

from model.wiring import PinModel, PinSide

_current_build_footprint: ContextVar[Optional["BuildFootprint"]] = ContextVar("_current_build_footprint", default=None)


class PadShape(str, Enum):
    """Supported copper pad geometric shapes."""

    ROUNDRECT = "roundrect"
    CIRCLE = "circle"
    OVAL = "oval"
    RECT = "rect"


class PadType(str, Enum):
    """Supported PCB pad fabrication types."""

    SMD = "smd"
    THRU_HOLE = "thru_hole"


class BuildFootprint(BuildPart):
    """Context manager for declarative PCB component footprint definition.

    Integrates 3D CAD physical body geometry (via BuildPart primitives like Box, Cylinder)
    with 2D electrical copper pads (via Pad primitives).
    """

    def __init__(
        self,
        name: str,
        dimensions: Tuple[float, float, float],
        shape: Optional[str] = None,
        radius_mm: Optional[float] = None,
        mounting_holes: Optional[Tuple[float, float]] = None,
        slots_per_side: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize footprint context.

        Args:
            name: Package or footprint identifier (e.g. '0402', 'SOIC-8').
            dimensions: 3D bounding package dimensions (width, length, height) in mm.
            shape: Optional package contour shape ('circle', 'rect').
            radius_mm: Optional radius for circular component packages.
            mounting_holes: Optional (x, y) spacing for mechanical mounting holes.
            slots_per_side: Optional DIP or header slot count per side.
            kwargs: Additional build123d BuildPart arguments.
        """
        super().__init__(**kwargs)
        self.name = name
        self.dimensions = dimensions
        self.shape_type = shape
        self.radius_mm = radius_mm
        self.mounting_holes = mounting_holes
        self.slots_per_side = slots_per_side
        self.pins: List[PinModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildFootprint":
        """Enter footprint context and set ambient active builder."""
        self._token = _current_build_footprint.set(self)
        super().__enter__()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit footprint context and restore previous builder."""
        super().__exit__(exc_type, exc_val, exc_tb)
        if self._token is not None:
            _current_build_footprint.reset(self._token)
            self._token = None

    @classmethod
    def current(cls) -> Optional["BuildFootprint"]:
        """Retrieve active footprint builder context if present."""
        return _current_build_footprint.get()

    def to_dict(self) -> Dict[str, Any]:
        """Export footprint dictionary representation matching shared footprints schema."""
        pins_data: List[Dict[str, Any]] = []
        for p in self.pins:
            p_dict: Dict[str, Any] = {
                "name": p.name,
                "position": [p.position[0], p.position[1]],
                "side": p.side.value if hasattr(p.side, "value") else str(p.side),
                "pad_type": p.pad_type,
                "pad_shape": p.pad_shape,
                "pad_size_mm": list(p.pad_size_mm),
            }
            if p.number is not None:
                p_dict["number"] = p.number
            if p.pin_name is not None:
                p_dict["pin_name"] = p.pin_name
            if p.signal_name is not None:
                p_dict["signal_name"] = p.signal_name
            if p.drill_dia_mm is not None:
                p_dict["drill_dia_mm"] = p.drill_dia_mm
            if getattr(p, "_explicit_label", False) and p.label is not None:
                p_dict["label"] = p.label
            pins_data.append(p_dict)

        d: Dict[str, Any] = {
            "dimensions": list(self.dimensions),
            "pins": pins_data,
        }
        if self.shape_type is not None:
            d["shape"] = self.shape_type
        if self.radius_mm is not None:
            d["radius_mm"] = self.radius_mm
        if self.mounting_holes is not None:
            d["mounting_holes"] = list(self.mounting_holes)
        if self.slots_per_side is not None:
            d["slots_per_side"] = self.slots_per_side
        return d


class Pad:
    """Declarative copper pad primitive evaluated inside a BuildFootprint context."""

    def __init__(
        self,
        name: Optional[Union[str, Sequence[str]]] = None,
        number: Optional[Union[str, int, Sequence[Union[str, int]]]] = None,
        *,
        size: Tuple[float, float] = (0.5, 0.5),
        shape: Union[PadShape, str] = PadShape.ROUNDRECT,
        pad_type: Union[PadType, str] = PadType.SMD,
        side: Union[PinSide, str, Sequence[Union[PinSide, str]]] = PinSide.LEFT,
        drill_dia_mm: Optional[float] = None,
        pin_name: Optional[Union[str, Sequence[str]]] = None,
        signal_name: Optional[Union[str, Sequence[str]]] = None,
        label: Optional[Union[str, Sequence[str]]] = None,
        position: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Instantiate one or more pads at active Locations.

        Args:
            name: Pin/pad name string or sequence of names for multi-location placement.
            number: Physical pin number or sequence of numbers.
            size: Pad dimensions (width, height) in mm.
            shape: Pad geometric shape (roundrect, circle, oval, rect).
            pad_type: Pad type (smd or thru_hole).
            side: Physical edge/side orientation (left, right, top, bottom).
            drill_dia_mm: Drill hole diameter for thru-hole pads.
            pin_name: Optional functional pin name.
            signal_name: Optional expected signal name.
            position: Explicit (x, y) coordinates if outside a Locations context.
        """
        ctx = BuildFootprint.current()
        if ctx is None:
            raise RuntimeError("Pad must be instantiated inside a BuildFootprint context.")

        resolved_shape = shape.value if isinstance(shape, PadShape) else str(shape)
        resolved_type = pad_type.value if isinstance(pad_type, PadType) else str(pad_type)
        resolved_side = PinSide(side) if isinstance(side, str) else side

        loc_ctx = LocationList._get_context()
        locations = loc_ctx.locations if loc_ctx and loc_ctx.locations else []

        if locations:
            for idx, loc in enumerate(locations):
                p_x = round(loc.position.X, 4)
                p_y = round(loc.position.Y, 4)

                # Resolve pin name
                if isinstance(name, (list, tuple)) and idx < len(name):
                    p_name = str(name[idx])
                elif isinstance(name, str):
                    p_name = name
                else:
                    p_name = str(len(ctx.pins) + 1)

                # Resolve pin number
                if isinstance(number, (list, tuple)) and idx < len(number):
                    p_num = str(number[idx])
                elif number is not None:
                    p_num = str(number)
                else:
                    p_num = None

                # Resolve pin_name
                if isinstance(pin_name, (list, tuple)) and idx < len(pin_name):
                    p_func_name = str(pin_name[idx])
                elif isinstance(pin_name, str):
                    p_func_name = pin_name
                else:
                    p_func_name = None

                # Resolve signal_name
                if isinstance(signal_name, (list, tuple)) and idx < len(signal_name):
                    p_sig_name = str(signal_name[idx])
                elif isinstance(signal_name, str):
                    p_sig_name = signal_name
                else:
                    p_sig_name = None

                # Resolve label
                if isinstance(label, (list, tuple)) and idx < len(label):
                    p_lbl = str(label[idx])
                elif isinstance(label, str):
                    p_lbl = label
                else:
                    p_lbl = None

                # Resolve side
                if isinstance(side, (list, tuple)) and idx < len(side):
                    p_side = PinSide(side[idx]) if isinstance(side[idx], str) else side[idx]
                elif isinstance(side, str):
                    p_side = PinSide(side)
                else:
                    p_side = side

                pin_model = PinModel(
                    name=p_name,
                    number=p_num,
                    pin_name=p_func_name,
                    signal_name=p_sig_name,
                    label=p_lbl,
                    position=(p_x, p_y, 0.0),
                    side=p_side,
                    pad_type=resolved_type,
                    pad_shape=resolved_shape,
                    pad_size_mm=size,
                    drill_dia_mm=drill_dia_mm,
                )
                pin_model._explicit_label = p_lbl is not None
                ctx.pins.append(pin_model)
        elif position is not None:
            p_name = str(name) if name is not None else str(len(ctx.pins) + 1)
            p_num = str(number) if number is not None else None
            p_func_name = str(pin_name) if pin_name is not None else None
            p_sig_name = str(signal_name) if signal_name is not None else None
            p_lbl = str(label) if label is not None else None

            pin_model = PinModel(
                name=p_name,
                number=p_num,
                pin_name=p_func_name,
                signal_name=p_sig_name,
                label=p_lbl,
                position=(position[0], position[1], 0.0),
                side=resolved_side,
                pad_type=resolved_type,
                pad_shape=resolved_shape,
                pad_size_mm=size,
                drill_dia_mm=drill_dia_mm,
            )
            pin_model._explicit_label = p_lbl is not None
            ctx.pins.append(pin_model)


F = TypeVar("F", bound=Callable[..., BuildFootprint])
FOOTPRINT_REGISTRY: Dict[str, Callable[[], BuildFootprint]] = {}


def footprint(name: str, dimensions: Tuple[float, float, float], **meta: Any) -> Callable[[F], F]:
    """Register a declarative footprint factory function.

    Args:
        name: Unique footprint package name (e.g. '0402', 'SOIC-8').
        dimensions: 3D bounding dimensions (w, l, h) in mm.
        meta: Optional metadata attributes.

    Returns:
        Decorated factory function registered in FOOTPRINT_REGISTRY.
    """

    def decorator(func: F) -> F:
        FOOTPRINT_REGISTRY[name] = func
        setattr(func, "_footprint_name", name)
        setattr(func, "_footprint_dimensions", dimensions)
        for k, v in meta.items():
            setattr(func, f"_footprint_{k}", v)
        return func

    return decorator
