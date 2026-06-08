"""Configuration options for SVG assembly diagram export."""

from typing import Tuple
from pydantic import BaseModel, Field


class DiagramOptions(BaseModel):
    """Diagram export configuration."""

    show_axes: bool = Field(default=False, alias="show_axes", description="Show coordinate axes")
    stroke_width: float = Field(default=3, alias="line_weight", description="Width of lines")
    stroke_color: Tuple[int, int, int] = Field(default=(0, 0, 0), alias="line_color", description="RGB color of lines")
    projection_dir: Tuple[float, float, float] = Field(
        default=(1, 1, 1), alias="projection_dir", description="Camera projection direction"
    )
    width: int = Field(default=1024, description="Output image width")
    height: int = Field(default=1024, description="Output image height")
