"""Boundary configuration data models."""

from typing import Any, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from enum import StrEnum
import math
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
    """Pydantic model representing boundary geometry and properties.

    Enforces shape-specific field validation to ensure properties match the ShapeType.
    """

    # Dictionary mapping each ShapeType to the fields it supports/uses
    SHAPE_SUPPORTED_FIELDS: dict[ShapeType, set[str]] = {
        ShapeType.CYLINDER: {
            "radius",
            "height",
            "thickness",
            "z_offset",
            "has_tube",
            "tube_radius",
            "has_drain",
            "drain_hole_y",
            "drain_hole_radius",
        },
        ShapeType.SPHERE: {
            "radius",
        },
        ShapeType.TUBE: {
            "radius",
            "height",
            "thickness",
            "slot_height",
        },
        ShapeType.IMPELLER: {
            "radius",
            "height",
            "thickness",
            "vane_thickness",
            "num_vanes",
            "vane_twist",
            "target_omega",
            "max_force",
        },
        ShapeType.BOX: {
            "height",
        },
        ShapeType.PLANE: {
            "thickness",
        },
    }

    @model_validator(mode="after")
    def validate_shape_fields(self) -> "BoundaryConfig":
        """Validate shape-specific fields and ensure unsupported fields are not configured."""
        if self.shape is None:
            return self

        supported = self.SHAPE_SUPPORTED_FIELDS.get(self.shape, set())
        common = {"shape", "type", "link_type", "link_idx", "xyz", "rpy"}

        for field_name in self.model_fields_set:
            if field_name not in common and field_name not in supported:
                raise ValueError(f"Field '{field_name}' is not supported for shape type '{self.shape.value}'.")

        # Value constraints validation:
        if self.shape is not None and "radius" in self.SHAPE_SUPPORTED_FIELDS.get(self.shape, set()):
            if self.radius <= 0.0:
                raise ValueError(f"{self.shape.name} shape requires a positive radius.")

        return self

    # ----------------------------------------------------
    # Core Identity & Link Metadata (Required, No Defaults)
    # ----------------------------------------------------
    link_type: LinkType = Field(description="Enum type of the link")
    link_idx: int = Field(description="Associated PyBullet multi-body link index")

    # ----------------------------------------------------
    # Boundary Categorization
    # ----------------------------------------------------
    _label: Optional[str] = PrivateAttr(default=None)
    shape: Optional[ShapeType] = Field(default=None, description="Geometry shape of the boundary element")
    type: Optional[BoundaryType] = Field(
        default=None, description="Collision type (cavity container, solid obstacle, or solid cavity)"
    )

    # ----------------------------------------------------
    # Spatial Transform Fields
    # ----------------------------------------------------
    xyz: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Local translation offset [x, y, z]")
    rpy: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Local orientation roll-pitch-yaw [r, p, y]"
    )
    z_offset: Optional[float] = Field(default=0.0, description="Computed or explicit Z offset")

    # ----------------------------------------------------
    # Common Geometric Parameters
    # ----------------------------------------------------
    radius: float = Field(default=0.0, ge=0.0, description="Radius parameter (applicable for cylinders)")
    height: float = Field(default=0.0, ge=0.0, description="Height parameter (applicable for cylinders or boxes)")
    thickness: float = Field(default=0.0, description="Wall/plate thickness parameter if applicable")

    # ----------------------------------------------------
    # Cylinder / Cavity Specific Parameters
    # ----------------------------------------------------
    has_drain: Optional[bool] = Field(default=False, description="Flag indicating if the boundary has a drain hole")
    drain_hole_y: Optional[float] = Field(default=0.0, description="Y coordinate of the drain hole")
    drain_hole_radius: Optional[float] = Field(default=0.0, description="Radius of the drain hole")
    has_tube: Optional[bool] = Field(default=False, description="Flag indicating if the boundary has a tube hole")
    tube_radius: float = Field(default=0.008, description="Tube hole radius")

    # ----------------------------------------------------
    # Tube Specific Parameters
    # ----------------------------------------------------
    slot_height: float = Field(default=0.015, description="Height of pump slots if applicable")

    # ----------------------------------------------------
    # Impeller Specific Parameters
    # ----------------------------------------------------
    vane_thickness: Optional[float] = Field(default=0.0015, description="Impeller/propeller vane thickness")
    num_vanes: Optional[float] = Field(default=4.0, description="Number of vanes on impeller/propeller")
    vane_twist: float = Field(
        default=-1080.0, description="Total twist angle of the rotary vanes (impeller blades) in degrees."
    )
    target_omega: float = Field(default=15.0, description="Target motor speed/angular velocity")
    max_force: float = Field(default=10.0, description="Maximum motor force/torque limit")

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
                self.vane_twist,
                self.drain_hole_y,
                self.drain_hole_radius,
                self.has_drain,
                self.has_tube,
                self.tube_radius,
                self.target_omega,
                self.max_force,
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
            and self.vane_twist == other.vane_twist
            and self.drain_hole_y == other.drain_hole_y
            and self.drain_hole_radius == other.drain_hole_radius
            and self.has_drain == other.has_drain
            and self.has_tube == other.has_tube
            and self.tube_radius == other.tube_radius
            and self.target_omega == other.target_omega
            and self.max_force == other.max_force
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

    @property
    def vane_twist_rad(self) -> float:
        """Calculate and return vane_twist in radians."""
        return float(math.radians(self.vane_twist))
