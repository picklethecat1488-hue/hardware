"""Data model for 3D text generation and alignment settings."""

from typing import Tuple, Any, Annotated
from pydantic import BaseModel, Field, BeforeValidator
from build123d import Align, FontStyle


def _coerce_to_int(v: Any) -> Any:
    """Coerce string representations of integers to actual integers for Enum validation."""
    try:
        if isinstance(v, str) and v.isdigit():
            return int(v)
    except (ValueError, TypeError):
        pass
    return v


class TextArgs(BaseModel):
    """Text configuration arguments."""

    font_size: float = Field(default=10, description="Font size in points")
    font: str = Field(default="Sans", description="Font name")
    align: Tuple[Align, Align] = Field(
        default=(Align.CENTER, Align.CENTER), description="Horizontal and vertical alignment"
    )
    font_style: Annotated[FontStyle, BeforeValidator(_coerce_to_int)] = Field(
        default=FontStyle.BOLD, description="Font style (Regular, Bold, Italic)"
    )
    height: float = Field(default=3, description="Extrusion height of the text")
