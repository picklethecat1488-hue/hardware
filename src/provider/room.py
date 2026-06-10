"""Specialized container for visualization items."""

from typing import Any, Union, Optional, TYPE_CHECKING, cast
from build123d import (
    BoundBox,
    BuildPart,
    BuildSketch,
    BuildLine,
    Compound,
    Vector,
    Plane,
    Text,
    Align,
    Location,
    Sketch,
)
from build123d.exporters import ExportSVG, Drawing
from model import DiagramOptions, TextArgs
from .types import ColorType
from .utils import get_rgba_color

if TYPE_CHECKING:
    from model.app_config import AppConfig


class Room(dict[str, tuple[Any, tuple[float, float, float, float]]]):
    """
    A dictionary-like container for CAD geometry and its visualization metadata.

    Keys are unique names for the items, and values are tuples of (geometry, rgba_tuple).
    """

    def __init__(self, config: Optional["AppConfig"] = None):
        """Initialize the room with an optional application configuration."""
        super().__init__()
        self.config = config
        self._labels: list[tuple[str, str, Any, TextArgs]] = []

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

        # Support BuildPart objects by extracting the underlying geometry
        if isinstance(geometry, BuildPart):
            geometry = geometry.part
        elif isinstance(geometry, BuildSketch):
            geometry = geometry.sketch
        elif isinstance(geometry, BuildLine):
            geometry = geometry.line

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

    def add_label(self, name: str, text: str, location: Any, options: Optional[TextArgs] = None) -> None:
        """Add a camera-aligned text annotation at a 3D location."""
        self._labels.append((name, text, Vector(location), options or TextArgs()))

    @property
    def compound(self) -> Compound:
        """Return the room contents as a single build123d Compound."""
        children = []

        for name, (obj, _) in self.items():
            if hasattr(obj, "label"):
                # Setting the label allows visualization tools like ocp_vscode to identify parts.
                setattr(obj, "label", name)
                children.append(obj)
            else:
                raise ValueError(f"Item '{name}' in Room could not be converted to a build123d object.")

        return Compound(children=children)

    def export_diagram(self, path: str, options: Optional["DiagramOptions"] = None) -> None:
        """Export the room contents to a file, inferring format from extension."""
        if not path.lower().endswith(".svg"):
            raise ValueError(f"Unsupported diagram format for '{path}'. Only .svg is supported.")

        svg_opts = self._parse_options(options)
        look_from, look_at, up_vector = self._get_projection_vectors(svg_opts)
        drawing = Drawing(
            self.compound,
            look_from=look_from,
            look_at=look_at,
            look_up=up_vector,
            with_hidden=svg_opts.get("show_hidden", False),
        )
        export_shapes = [drawing.visible_lines]

        if svg_opts.get("show_hidden"):
            export_shapes.append(drawing.hidden_lines)

        # Get the bounding box of the projected geometry to calculate triad placement.
        model_bb = drawing.visible_lines.bounding_box()

        # Add debug axes if requested, placed in the corner and scaled to the viewpane.
        if svg_opts.get("show_axes"):
            axes = self._create_debug_axes(model_bb, look_from, look_at, up_vector)
            if axes:
                export_shapes.append(axes)

        # Define the view plane for projecting annotations to match the Drawing's 2D space.
        # The view direction is the vector from the target back to the camera.
        view_dir = (look_from - look_at).normalized()
        view_x = up_vector.cross(view_dir).normalized()
        view_plane = Plane(origin=look_at, x_dir=view_x, z_dir=view_dir)

        export_shapes.extend(self._project_labels(view_plane))

        # Combine projected geometry and flat annotations for final scaling and export.
        final_drawing = Compound(children=export_shapes)
        bb = final_drawing.bounding_box()

        # ExportSVG uses 'scale' to determine physical dimensions from model units.
        if "width" in svg_opts and bb.size.X > 0:
            svg_opts["scale"] = svg_opts.pop("width") / bb.size.X
        elif "height" in svg_opts and bb.size.Y > 0:
            svg_opts["scale"] = svg_opts.pop("height") / bb.size.Y

        # Filter for fields explicitly supported by build123d's ExportSVG class.
        supported_fields = {
            "unit",
            "scale",
            "margin",
            "fit_to_stroke",
            "precision",
            "fill_color",
            "line_weight",
            "line_color",
            "line_type",
            "dot_length",
        }
        filtered_opts = {k: v for k, v in svg_opts.items() if k in supported_fields}

        exporter = ExportSVG(**filtered_opts)
        exporter.add_shape(final_drawing)
        exporter.write(path)

    def _parse_options(self, options: Optional["DiagramOptions"]) -> dict[str, Any]:
        """Extract and normalize diagram options from Pydantic models or mock objects."""
        if not options:
            return {}

        if hasattr(options, "model_dump"):
            # Use aliases to map stroke_width/color to line_weight/color
            return options.model_dump(by_alias=True, exclude_none=True)

        # Fallback for simple objects or mocks
        fields = [
            "width",
            "height",
            "stroke_width",
            "stroke_color",
            "margin",
            "projection_dir",
            "projection_origin",
            "show_axes",
            "show_hidden",
            "look_up",
        ]
        svg_opts = {}
        for field in fields:
            if hasattr(options, field):
                val = getattr(options, field)
                if val is not None:
                    svg_opts[field] = val

        # Manual mapping for mock objects if they don't use aliases
        if "stroke_width" in svg_opts:
            svg_opts["line_weight"] = svg_opts.pop("stroke_width")
        if "stroke_color" in svg_opts:
            svg_opts["line_color"] = svg_opts.pop("stroke_color")

        return svg_opts

    def _get_projection_vectors(self, svg_opts: dict[str, Any]) -> tuple[Vector, Vector, Vector]:
        # Calculate the camera projection direction and a stable "up" vector.
        look_from_val = svg_opts.get("projection_origin")
        if look_from_val is None:
            look_from_val = DiagramOptions.model_fields["projection_origin"].default
        look_from = Vector(look_from_val)

        look_at_val = svg_opts.get("projection_dir")
        if look_at_val is None:
            look_at_val = DiagramOptions.model_fields["projection_dir"].default
        look_at = Vector(look_at_val)

        view_dir = (look_from - look_at).normalized()

        z_axis = Vector(0, 0, 1)
        up_vector = Vector(svg_opts.get("look_up", z_axis))
        if abs(view_dir.dot(up_vector)) > 0.99 and "look_up" not in svg_opts:
            up_vector = Vector(0, 1, 0)
        return look_from, look_at, up_vector

    def _project_labels(self, view_plane: Plane) -> list[Sketch]:
        """Project 3D annotations into 2D sketches aligned with the view plane."""
        projected_sketches = []
        for _, text, loc, opts in self._labels:
            local_loc = cast(Vector, view_plane.to_local_coords(loc))
            with BuildSketch() as s:
                Text(
                    text,
                    font_size=opts.font_size,
                    font=opts.font,
                    font_style=opts.font_style,
                    align=opts.align,
                )

            # Place the 2D text at the projected X/Y coordinates.
            projected_sketches.append(s.sketch.moved(Location((local_loc.X, local_loc.Y))))
        return projected_sketches

    def _create_debug_axes(
        self,
        model_bb: BoundBox,
        look_from: Vector,
        look_at: Vector,
        up_vector: Vector,
    ) -> Optional[Any]:
        """Create a projected coordinate system triad scaled and positioned for the viewpane."""
        # Create and project the triad separately to keep it in a corner.
        axes_triad = Compound.make_triad(axes_scale=1.0)
        axes_drawing = Drawing(axes_triad, look_from=look_from, look_at=look_at, look_up=up_vector)
        projected_axes = axes_drawing.visible_lines

        # Scale to ~9% of the model's larger dimension.
        model_dim = max(model_bb.size.X, model_bb.size.Y)
        axes_bb = projected_axes.bounding_box()
        axes_dim = max(axes_bb.size.X, axes_bb.size.Y)

        if axes_dim > 0:
            axes_scale = (model_dim * 0.09) / axes_dim
            projected_axes = projected_axes.scale(axes_scale)

            # Move to bottom-left corner with margin.
            margin = model_dim * 0.05
            new_axes_bb = projected_axes.bounding_box()
            offset = Vector(
                model_bb.min.X - new_axes_bb.min.X - margin,
                model_bb.min.Y - new_axes_bb.min.Y - margin,
            )
            return projected_axes.translate(offset)
        return None
