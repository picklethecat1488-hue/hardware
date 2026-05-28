"""Data model for 3D text generation and alignment settings."""

from typing import Tuple
from pydantic import BaseModel, Field
from build123d import Align, FontStyle


class TextArgs(BaseModel):
    """Text configuration arguments."""

    font_size: float = Field(default=10, description="Font size in points")
    font: str = Field(default="Sans", description="Font name")
    align: Tuple[Align, Align] = Field(
        default=(Align.CENTER, Align.CENTER), description="Horizontal and vertical alignment"
    )
    font_style: FontStyle = Field(default=FontStyle.BOLD, description="Font style (Regular, Bold, Italic)")
    height: float = Field(default=3, description="Extrusion height of the text")
