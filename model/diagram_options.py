"""Configuration options for SVG assembly diagram export."""

from enum import StrEnum
from typing import Tuple, Optional
from pydantic import BaseModel, Field


class DiagramStyle(StrEnum):
    """Supported styles for SVG diagram export."""

    OUTLINE = "outline"
    COLOR = "color"
    HIDDEN = "hidden"
    COLOR_HIDDEN = "color_hidden"


class DiagramOptions(BaseModel):
    """Diagram export configuration."""

    show_axes: bool = Field(default=False, description="Show coordinate axes")
    style: DiagramStyle = Field(
        default=DiagramStyle.OUTLINE,
        description="Export style (outline, color, hidden, color_hidden)",
    )
    stroke_width: float = Field(default=3, alias="line_weight", description="Width of lines")
    stroke_color: Tuple[int, int, int] = Field(default=(0, 0, 0), alias="line_color", description="RGB color of lines")
    view_from: str = Field(default="iso", description="Named view direction (e.g. 'top', 'top rear')")
    projection_origin: Optional[Tuple[float, float, float]] = Field(
        default=None, alias="projection_origin", description="Override camera position"
    )
    projection_dir: Optional[Tuple[float, float, float]] = Field(
        default=None, alias="projection_dir", description="Override camera target point"
    )
    width: int = Field(default=1024, description="Output image width")
    height: int = Field(default=1024, description="Output image height")
