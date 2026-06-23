"""Boundary configuration data models."""

from typing import Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from provider.bullet import LinkType


class BoundaryConfig(BaseModel):
    """Pydantic model representing boundary geometry and properties."""

    shape: Optional[Literal["cylinder", "box", "plane", "impeller", "tube"]] = Field(
        default=None, description="Geometry shape of the boundary element"
    )
    type: Optional[Literal["cavity", "solid", "solid_cavity"]] = Field(
        default=None, description="Collision type (cavity container, solid obstacle, or solid cavity)"
    )
    link_type: Optional[LinkType] = Field(default=None, description="Enum type of the link")
    radius: Optional[float] = Field(default=None, description="Radius parameter (applicable for cylinders)")
    height: Optional[float] = Field(default=None, description="Height parameter (applicable for cylinders or boxes)")
    xyz: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Local translation offset [x, y, z]")
    rpy: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Local orientation roll-pitch-yaw [r, p, y]"
    )
    link_idx: Optional[int] = Field(default=None, description="Associated PyBullet multi-body link index")
    thickness: Optional[float] = Field(default=None, description="Wall/plate thickness parameter if applicable")

    @field_validator("xyz", "rpy", mode="before")
    @classmethod
    def parse_string_to_tuple(
        cls, v: Union[str, Tuple[float, float, float], list[float]]
    ) -> Tuple[float, float, float]:
        """Convert space-separated string configurations to a tuple of floats."""
        if isinstance(v, str):
            parts = [float(x) for x in v.strip().split()]
            if len(parts) != 3:
                raise ValueError("xyz/rpy string must contain exactly 3 float values")
            return (parts[0], parts[1], parts[2])
        if isinstance(v, (list, tuple)):
            if len(v) != 3:
                raise ValueError("xyz/rpy must have exactly 3 values")
            return (float(v[0]), float(v[1]), float(v[2]))
        return v

    @model_validator(mode="after")
    def populate_link_type(self) -> "BoundaryConfig":
        """Populate link_type from collision type if not explicitly set."""
        if self.link_type is None and self.type is not None:
            if self.type == "cavity":
                self.link_type = LinkType.BASE
            elif self.type == "solid_cavity":
                self.link_type = LinkType.TUBE
            elif self.type == "solid":
                self.link_type = LinkType.IMPELLER
        return self
