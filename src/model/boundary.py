"""Boundary configuration data models."""

from typing import Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from enum import StrEnum
from provider.bullet import LinkType


class ShapeType(StrEnum):
    """Supported boundary shape types."""

    CYLINDER = "cylinder"
    BOX = "box"
    PLANE = "plane"
    IMPELLER = "impeller"
    TUBE = "tube"
    SPHERE = "sphere"


class BoundaryType(StrEnum):
    """Supported boundary collision types."""

    CAVITY = "cavity"
    SOLID = "solid"
    SOLID_CAVITY = "solid_cavity"


class BoundaryConfig(BaseModel):
    """Pydantic model representing boundary geometry and properties."""

    _label: Optional[str] = PrivateAttr(default=None)
    shape: Optional[ShapeType] = Field(default=None, description="Geometry shape of the boundary element")
    type: Optional[BoundaryType] = Field(
        default=None, description="Collision type (cavity container, solid obstacle, or solid cavity)"
    )
    link_type: LinkType = Field(description="Enum type of the link")
    radius: Optional[float] = Field(default=None, description="Radius parameter (applicable for cylinders)")
    height: Optional[float] = Field(default=None, description="Height parameter (applicable for cylinders or boxes)")
    xyz: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Local translation offset [x, y, z]")
    rpy: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Local orientation roll-pitch-yaw [r, p, y]"
    )
    link_idx: int = Field(description="Associated PyBullet multi-body link index")
    thickness: Optional[float] = Field(default=None, description="Wall/plate thickness parameter if applicable")
    z_offset: Optional[float] = Field(default=0.0, description="Computed or explicit Z offset")
    slot_height: Optional[float] = Field(default=0.0, description="Height of pump slots if applicable")
    vane_thickness: Optional[float] = Field(default=0.0015, description="Impeller/propeller vane thickness")
    num_vanes: Optional[float] = Field(default=4.0, description="Number of vanes on impeller/propeller")
    vane_twist_rad: Optional[float] = Field(default=0.0, description="Vane twist in radians")
    drain_hole_y: Optional[float] = Field(default=0.0, description="Y coordinate of the drain hole")
    drain_hole_radius: Optional[float] = Field(default=0.0, description="Radius of the drain hole")
    has_drain: Optional[bool] = Field(default=False, description="Flag indicating if the boundary has a drain hole")
    has_tube: Optional[bool] = Field(default=False, description="Flag indicating if the boundary has a tube hole")

    def __hash__(self) -> int:
        """Return a hash value calculated from model properties."""
        return hash(
            (
                self.shape,
                self.type,
                self.link_type,
                self.radius,
                self.height,
                self.xyz,
                self.rpy,
                self.link_idx,
                self.thickness,
                self.z_offset,
                self.slot_height,
                self.vane_thickness,
                self.num_vanes,
                self.vane_twist_rad,
                self.drain_hole_y,
                self.drain_hole_radius,
                self.has_drain,
                self.has_tube,
            )
        )

    def __eq__(self, other: object) -> bool:
        """Compare equality with another BoundaryConfig based on properties."""
        if not isinstance(other, BoundaryConfig):
            return NotImplemented
        return (
            self.shape == other.shape
            and self.type == other.type
            and self.link_type == other.link_type
            and self.radius == other.radius
            and self.height == other.height
            and self.xyz == other.xyz
            and self.rpy == other.rpy
            and self.link_idx == other.link_idx
            and self.thickness == other.thickness
            and self.z_offset == other.z_offset
            and self.slot_height == other.slot_height
            and self.vane_thickness == other.vane_thickness
            and self.num_vanes == other.num_vanes
            and self.vane_twist_rad == other.vane_twist_rad
            and self.drain_hole_y == other.drain_hole_y
            and self.drain_hole_radius == other.drain_hole_radius
            and self.has_drain == other.has_drain
            and self.has_tube == other.has_tube
        )

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
