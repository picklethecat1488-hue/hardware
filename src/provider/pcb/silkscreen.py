"""build123d context manager and primitives for declarative PCB silkscreen text placement."""

import math
from contextvars import ContextVar, Token
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from build123d import Location, LocationList, Text

from model.pcb import SilkscreenTextModel, SilkscreenGraphicModel

_current_silkscreen: ContextVar[Optional["BuildSilkscreen"]] = ContextVar("_current_silkscreen", default=None)


class BuildSilkscreen:
    """Context manager for declarative PCB silkscreen text and graphic placement using CAD locating primitives."""

    def __init__(self, default_layer: str = "F.SilkS") -> None:
        """Initialize silkscreen builder context.

        Args:
            default_layer: Default silkscreen layer ('F.SilkS' for top, 'B.SilkS' for bottom).
        """
        self.default_layer = default_layer
        self.texts: List[SilkscreenTextModel] = []
        self.graphics: List[SilkscreenGraphicModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildSilkscreen":
        """Enter silkscreen context and register as active builder."""
        self._token = _current_silkscreen.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit silkscreen context and restore previous builder."""
        if self._token is not None:
            _current_silkscreen.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            for t in self.texts:
                if t not in active_pcb.silkscreen_texts:
                    active_pcb.silkscreen_texts.append(t)
            for g in self.graphics:
                if hasattr(active_pcb, "silkscreen_graphics") and g not in active_pcb.silkscreen_graphics:
                    active_pcb.silkscreen_graphics.append(g)

    @classmethod
    def _get_context(cls) -> Optional["BuildSilkscreen"]:
        """Retrieve active silkscreen builder context if present."""
        return _current_silkscreen.get()

    def add(
        self,
        item: Union[
            SilkscreenTextModel,
            SilkscreenGraphicModel,
            Sequence[Union[SilkscreenTextModel, SilkscreenGraphicModel]],
        ],
    ) -> None:
        """Add one or more silkscreen text or graphic models to the active context.

        Args:
            item: Single model or sequence of models to append.
        """
        if isinstance(item, SilkscreenTextModel):
            self.texts.append(item)
        elif isinstance(item, SilkscreenGraphicModel):
            self.graphics.append(item)
        else:
            for it in item:
                if isinstance(it, SilkscreenTextModel):
                    self.texts.append(it)
                elif isinstance(it, SilkscreenGraphicModel):
                    self.graphics.append(it)

    def to_shapes(self) -> List[Text]:
        """Convert collected silkscreen texts to 2D build123d CAD Text shapes for 3D inspection.

        Returns:
            List of build123d Text objects located according to silkscreen models.
        """
        shapes: List[Text] = []
        for t in self.texts:
            shape = Text(t.text, font_size=t.font_size)
            loc = Location((t.position[0], t.position[1], 0.0), (0.0, 0.0, t.rotation))
            shapes.append(shape.locate(loc))
        return shapes


class SilkscreenText:
    """Silkscreen text CAD primitive that evaluates active Location contexts."""

    def __init__(
        self,
        text: str,
        layer: Optional[str] = None,
        font_size: float = 1.0,
        thickness: float = 0.15,
        rotation: float = 0.0,
        mirror: Optional[bool] = None,
        position: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Create and place silkscreen text at active CAD locations.

        Args:
            text: Text content to print on silkscreen.
            layer: Target silkscreen layer ('F.SilkS' or 'B.SilkS'). Defaults to context layer.
            font_size: Height/width of text characters in mm.
            thickness: Stroke line thickness in mm.
            rotation: Additional rotation angle in degrees.
            mirror: Whether to mirror text horizontally (defaults True for B.SilkS).
            position: Explicit (x, y) coordinates if not within a Locations context.
        """
        self.text = text
        self.font_size = font_size
        self.thickness = thickness
        self.models: List[SilkscreenTextModel] = []

        ctx = BuildSilkscreen._get_context()
        target_layer = layer or (ctx.default_layer if ctx else "F.SilkS")
        is_mirror = mirror if mirror is not None else (target_layer == "B.SilkS")

        loc_ctx = LocationList._get_context()
        active_locations: List[Location] = (
            loc_ctx.local_locations if loc_ctx is not None and loc_ctx.local_locations else []
        )

        if active_locations:
            for loc in active_locations:
                x_offset = position[0] if position else 0.0
                y_offset = position[1] if position else 0.0
                pos_x = round(loc.position.X + x_offset, 4)
                pos_y = round(loc.position.Y + y_offset, 4)
                rot = round((loc.orientation.Z + rotation) % 360.0, 4)

                model = SilkscreenTextModel(
                    text=text,
                    layer=target_layer,
                    position=(pos_x, pos_y),
                    font_size=font_size,
                    thickness=thickness,
                    rotation=rot,
                    mirror=is_mirror,
                )
                self.models.append(model)
                if ctx is not None:
                    ctx.add(model)
        else:
            pos_x = round(position[0] if position else 0.0, 4)
            pos_y = round(position[1] if position else 0.0, 4)
            rot = round(rotation % 360.0, 4)

            model = SilkscreenTextModel(
                text=text,
                layer=target_layer,
                position=(pos_x, pos_y),
                font_size=font_size,
                thickness=thickness,
                rotation=rot,
                mirror=is_mirror,
            )
            self.models.append(model)
            if ctx is not None:
                ctx.add(model)

    @property
    def model(self) -> SilkscreenTextModel:
        """Return the primary or single SilkscreenTextModel instance."""
        return self.models[0]

    def __iter__(self) -> Iterator[SilkscreenTextModel]:
        """Iterate over generated SilkscreenTextModel instances."""
        return iter(self.models)

    def __len__(self) -> int:
        """Return number of generated text instances."""
        return len(self.models)


class SilkscreenRect:
    """Silkscreen rectangle or square frame CAD primitive evaluating active Location contexts."""

    def __init__(
        self,
        dimensions: Tuple[float, float] = (5.0, 5.0),
        layer: Optional[str] = None,
        thickness: float = 0.15,
        fill: bool = False,
        position: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Create and place silkscreen rectangle or square frame."""
        self.dimensions = dimensions
        self.thickness = thickness
        self.fill = fill
        self.models: List[SilkscreenGraphicModel] = []

        ctx = BuildSilkscreen._get_context()
        target_layer = layer or (ctx.default_layer if ctx else "F.SilkS")

        loc_ctx = LocationList._get_context()
        active_locations: List[Location] = (
            loc_ctx.local_locations if loc_ctx is not None and loc_ctx.local_locations else []
        )

        if active_locations:
            for loc in active_locations:
                x_offset = position[0] if position else 0.0
                y_offset = position[1] if position else 0.0
                pos_x = round(loc.position.X + x_offset, 4)
                pos_y = round(loc.position.Y + y_offset, 4)
                model = SilkscreenGraphicModel(
                    shape="rect",
                    layer=target_layer,
                    position=(pos_x, pos_y),
                    dimensions=dimensions,
                    thickness=thickness,
                    fill=fill,
                )
                self.models.append(model)
                if ctx is not None:
                    ctx.add(model)
        else:
            pos_x = round(position[0] if position else 0.0, 4)
            pos_y = round(position[1] if position else 0.0, 4)
            model = SilkscreenGraphicModel(
                shape="rect",
                layer=target_layer,
                position=(pos_x, pos_y),
                dimensions=dimensions,
                thickness=thickness,
                fill=fill,
            )
            self.models.append(model)
            if ctx is not None:
                ctx.add(model)

    @property
    def model(self) -> SilkscreenGraphicModel:
        """Return the primary SilkscreenGraphicModel instance."""
        return self.models[0]

    def __iter__(self) -> Iterator[SilkscreenGraphicModel]:
        """Iterate over generated graphic models."""
        return iter(self.models)


class SilkscreenLine:
    """Silkscreen vector line segment CAD primitive."""

    def __init__(
        self,
        start_mm: Tuple[float, float],
        end_mm: Tuple[float, float],
        layer: Optional[str] = None,
        thickness: float = 0.15,
    ) -> None:
        """Create and place silkscreen line."""
        self.start_mm = start_mm
        self.end_mm = end_mm
        self.thickness = thickness

        ctx = BuildSilkscreen._get_context()
        target_layer = layer or (ctx.default_layer if ctx else "F.SilkS")

        p1 = (round(start_mm[0], 4), round(start_mm[1], 4))
        p2 = (round(end_mm[0], 4), round(end_mm[1], 4))
        center_x = round((p1[0] + p2[0]) / 2.0, 4)
        center_y = round((p1[1] + p2[1]) / 2.0, 4)

        self.model = SilkscreenGraphicModel(
            shape="line",
            layer=target_layer,
            position=(center_x, center_y),
            thickness=thickness,
            points=[p1, p2],
        )
        if ctx is not None:
            ctx.add(self.model)


class SilkscreenPolygon:
    """Silkscreen vector polygon CAD primitive."""

    def __init__(
        self,
        polygon_points: Sequence[Tuple[float, float]],
        layer: Optional[str] = None,
        thickness: float = 0.15,
        fill: bool = False,
    ) -> None:
        """Create and place silkscreen polygon."""
        self.points = [(round(p[0], 4), round(p[1], 4)) for p in polygon_points]
        self.thickness = thickness
        self.fill = fill

        ctx = BuildSilkscreen._get_context()
        target_layer = layer or (ctx.default_layer if ctx else "F.SilkS")

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        center_x = round((min(xs) + max(xs)) / 2.0, 4)
        center_y = round((min(ys) + max(ys)) / 2.0, 4)

        self.model = SilkscreenGraphicModel(
            shape="polygon",
            layer=target_layer,
            position=(center_x, center_y),
            dimensions=(round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4)),
            thickness=thickness,
            fill=fill,
            points=self.points,
        )
        if ctx is not None:
            ctx.add(self.model)


def find_empty_space_for_label(
    base_x: float,
    base_y: float,
    label_w: float,
    label_h: float,
    circular_obstacles: Optional[Sequence[Tuple[float, float, float]]] = None,
    bounding_boxes: Optional[Sequence[Tuple[float, float, float, float]]] = None,
    board_bounds: Optional[Tuple[float, float, float, float]] = None,
    clearance: float = 0.30,
    preferred_direction: str = "auto",
    step_multiplier: float = 1.0,
) -> Tuple[float, float]:
    """Search the 2D PCB placement plane to find collision-free coordinates for silkscreen text.

    Audits candidate label positions against circular obstacles (vias, pads, drill holes)
    and rectangular bounding boxes (components, courtyards, keepouts) to locate open space.

    Args:
        base_x: Center X coordinate of the component or test point in mm.
        base_y: Center Y coordinate of the component or test point in mm.
        label_w: Width of the text bounding envelope in mm.
        label_h: Height of the text bounding envelope in mm.
        circular_obstacles: Sequence of (x, y, radius) tuples for circular copper/holes.
        bounding_boxes: Sequence of (min_x, min_y, max_x, max_y) obstacle tuples.
        board_bounds: Optional (min_x, min_y, max_x, max_y) outer board envelope.
        clearance: Minimum clearance between text bounding box and any obstacle in mm.
        preferred_direction: Direction preference ('auto', 'north', 'south', 'east', 'west').
        step_multiplier: Scaling factor for radial candidate distances.

    Returns:
        Relative (offset_x, offset_y) from (base_x, base_y) that achieves clear placement.
    """
    circ_obs = list(circular_obstacles or [])
    boxes = list(bounding_boxes or [])

    # Base steps along X and Y
    base_dx = (label_w / 2.0 + clearance) * step_multiplier
    base_dy = (label_h / 2.0 + clearance) * step_multiplier

    # Build candidate vectors based on preferred direction
    match preferred_direction.lower():
        case "north" | "up" | "above":
            directional_vectors = [(0.0, -base_dy), (base_dx, 0.0), (-base_dx, 0.0), (0.0, base_dy)]
        case "south" | "down" | "below":
            directional_vectors = [(0.0, base_dy), (base_dx, 0.0), (-base_dx, 0.0), (0.0, -base_dy)]
        case "east" | "right":
            directional_vectors = [(base_dx, 0.0), (0.0, -base_dy), (0.0, base_dy), (-base_dx, 0.0)]
        case "west" | "left":
            directional_vectors = [(-base_dx, 0.0), (0.0, -base_dy), (0.0, base_dy), (base_dx, 0.0)]
        case _:
            directional_vectors = [
                (0.0, -base_dy),
                (0.0, base_dy),
                (base_dx, 0.0),
                (-base_dx, 0.0),
                (base_dx * 0.707, -base_dy * 0.707),
                (-base_dx * 0.707, -base_dy * 0.707),
                (base_dx * 0.707, base_dy * 0.707),
                (-base_dx * 0.707, base_dy * 0.707),
            ]

    candidates: List[Tuple[float, float]] = []
    for scale in (1.0, 1.4, 1.8, 2.2, 2.8):
        for vx, vy in directional_vectors:
            candidates.append((round(vx * scale, 4), round(vy * scale, 4)))

    for off_x, off_y in candidates:
        cand_x = base_x + off_x
        cand_y = base_y + off_y

        c_min_x = cand_x - (label_w / 2.0)
        c_max_x = cand_x + (label_w / 2.0)
        c_min_y = cand_y - (label_h / 2.0)
        c_max_y = cand_y + (label_h / 2.0)

        # 1. Check board envelope containment
        if board_bounds is not None:
            b_min_x, b_min_y, b_max_x, b_max_y = board_bounds
            if (
                c_min_x < b_min_x + clearance
                or c_max_x > b_max_x - clearance
                or c_min_y < b_min_y + clearance
                or c_max_y > b_max_y - clearance
            ):
                continue

        # 2. Check circular obstacles (pads, vias, drill holes)
        cand_collision = False
        for ox, oy, o_r in circ_obs:
            px = max(c_min_x, min(ox, c_max_x))
            py = max(c_min_y, min(oy, c_max_y))
            dist = math.hypot(ox - px, oy - py) - o_r
            if dist < clearance:
                cand_collision = True
                break

        if cand_collision:
            continue

        # 3. Check rectangular bounding boxes
        for bx_min, by_min, bx_max, by_max in boxes:
            overlap = not (
                c_max_x < bx_min - clearance
                or c_min_x > bx_max + clearance
                or c_max_y < by_min - clearance
                or c_min_y > by_max + clearance
            )
            if overlap:
                cand_collision = True
                break

        if cand_collision:
            continue

        return (off_x, off_y)

    return candidates[0] if candidates else (0.0, round(base_dy, 4))
