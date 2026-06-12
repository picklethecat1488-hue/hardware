"""Configuration options for SVG assembly diagram export."""

from typing import Tuple, Optional
from pydantic import BaseModel, Field


class DiagramOptions(BaseModel):
    """Diagram export configuration."""

    show_axes: bool = Field(default=False, description="Show coordinate axes")
    show_hidden: bool = Field(default=False, description="Show hiden lines")
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
