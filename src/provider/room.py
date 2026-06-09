"""Specialized container for visualization items."""

from typing import Any, Union, Optional, TYPE_CHECKING, cast
import cadquery as cq
from build123d import BuildPart, BuildSketch, BuildLine
from .types import ColorType
from .utils import get_rgba_color

if TYPE_CHECKING:
    from model.app_config import AppConfig
    from model import DiagramOptions


class Room(dict[str, tuple[Any, tuple[float, float, float, float]]]):
    """
    A dictionary-like container for CAD geometry and its visualization metadata.

    Keys are unique names for the items, and values are tuples of (geometry, rgba_tuple).
    """

    def __init__(self, config: Optional["AppConfig"] = None):
        """Initialize the room with an optional application configuration."""
        super().__init__()
        self.config = config

    def add(
        self,
        name: str,
        geometry: Any,
        color: Optional[Union[str, ColorType, tuple[float, float, float]]] = None,
        alpha: float = 1.0,
    ) -> None:
        """
        Add a geometry item (Part, Sketch, Wire, or Builder) to the room.

        Args:
            name: Unique name for the item.
            geometry: The CAD object or build123d builder.
            color: The color name, enum member, RGB 3-tuple, or None to use default.
            alpha: Transparency value from 0.0 to 1.0.
        """
        if name in self:
            raise ValueError(f"An item with the name '{name}' already exists in the Room.")

        default_rgb = self.config.color[:3] if self.config else (1.0, 1.0, 1.0)

        final_color: Union[str, ColorType, tuple[float, float, float]] = ColorType.GREY
        final_alpha = alpha

        if color is not None:
            final_color = color
        elif self.config:
            final_color = self.config.color[:3]
            if alpha == 1.0:
                final_alpha = self.config.color[3]

        rgba = get_rgba_color(final_color, final_alpha, default_rgb)
        self[name] = (geometry, rgba)

    @property
    def assembly(self) -> cq.Assembly:
        """Convert the room contents into a CadQuery Assembly."""
        assy = cq.Assembly()

        for name, (obj, rgba) in self.items():
            # Unpack builders if necessary
            geom = obj
            if isinstance(obj, BuildPart):
                geom = obj.part
            elif isinstance(obj, BuildSketch):
                geom = obj.sketch
            elif isinstance(obj, BuildLine):
                geom = obj.line

            # Ensure we have a valid OCCT-wrapped object or sub-assembly
            if hasattr(geom, "toCompound"):
                assy.add(cast(Any, geom), name=name)
            elif geom is not None and hasattr(geom, "wrapped") and geom.wrapped is not None:
                shape = cq.Shape.cast(geom.wrapped)
                # Note: CadQuery Assembly names use the key as the identifier
                assy.add(cast(Any, shape), name=name, color=cq.Color(*rgba))
            else:
                raise ValueError(f"Item '{name}' in Room could not be converted to a CAD shape.")

        return assy

    def export_svg(self, path: str, options: Optional["DiagramOptions"] = None) -> None:
        """Export the room assembly as an SVG file."""
        svg_opts = {}
        if options:
            # Start with properties from model_dump if it's a Pydantic model
            if hasattr(options, "model_dump"):
                svg_opts = options.model_dump(by_alias=True)

            # Explicitly map DiagramOptions fields to CadQuery SVG export options.
            field_mappings = {
                "width": "width",
                "height": "height",
                "projection_dir": "projectionDir",
                "stroke_width": "strokeWidth",
                "stroke_color": "strokeColor",
                "hidden_color": "hiddenColor",
                "show_hidden": "showHidden",
                "show_dash": "showDash",
                "margin_left": "marginLeft",
                "margin_top": "marginTop",
                "focus": "focus",
            }

            for model_field, cq_option in field_mappings.items():
                if hasattr(options, model_field):
                    val = getattr(options, model_field)
                    if val is not None:
                        svg_opts[cq_option] = val

        self.assembly.toCompound().export(path, opt=svg_opts)
