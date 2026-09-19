"""build123d context manager and primitives for declarative PCB silkscreen text placement."""

from contextvars import ContextVar, Token
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from build123d import Location, LocationList, Text

from model.pcb import SilkscreenTextModel

_current_silkscreen: ContextVar[Optional["BuildSilkscreen"]] = ContextVar("_current_silkscreen", default=None)


class BuildSilkscreen:
    """Context manager for declarative PCB silkscreen text placement using CAD locating primitives."""

    def __init__(self, default_layer: str = "F.SilkS") -> None:
        """Initialize silkscreen builder context.

        Args:
            default_layer: Default silkscreen layer ('F.SilkS' for top, 'B.SilkS' for bottom).
        """
        self.default_layer = default_layer
        self.texts: List[SilkscreenTextModel] = []
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
            active_pcb.silkscreen_texts.extend(self.texts)

    @classmethod
    def _get_context(cls) -> Optional["BuildSilkscreen"]:
        """Retrieve active silkscreen builder context if present."""
        return _current_silkscreen.get()

    def add(self, item: Union[SilkscreenTextModel, Sequence[SilkscreenTextModel]]) -> None:
        """Add one or more silkscreen text models to the active context.

        Args:
            item: Single SilkscreenTextModel or sequence of models to append.
        """
        if isinstance(item, SilkscreenTextModel):
            self.texts.append(item)
        else:
            self.texts.extend(item)

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
