"""Common types and enums for build providers."""

from enum import StrEnum, IntEnum
from typing import Protocol, Optional, Any


class CollisionGroup(IntEnum):
    """Collision filter groups for physics simulations."""

    CONTAINER = 1
    PARTICLE = 2


class CollisionMask(IntEnum):
    """Collision filter masks for physics simulations."""

    CONTAINER = 1
    PARTICLE = 2
    ALL = 3


class URDFCollisionType(StrEnum):
    """URDF collision representation types."""

    CONVEX = "convex"
    CONCAVE = "concave"
    COMPOUND = "compound"
    ANALYTICAL = "analytical"
    NONE = "none"


class URDFCollisionShapeType(StrEnum):
    """URDF collision shape types."""

    BOX = "box"
    CYLINDER = "cylinder"
    SPHERE = "sphere"


class URDFBoundaryType(StrEnum):
    """URDF analytical boundary types."""

    CAVITY = "cavity"
    SOLID = "solid"
    SOLID_CAVITY = "solid_cavity"


class URDFShape(Protocol):
    """Protocol for build123d shapes with attached URDF properties."""

    urdf_label: Optional[str]
    urdf_parent: Optional[str]
    urdf_joint_type: Optional[str]
    urdf_joint_axis: Optional[str]
    urdf_joint_lower: Optional[float]
    urdf_joint_upper: Optional[float]
    urdf_material: Optional[str]
    urdf_density: Optional[float]
    urdf_motor_type: Optional[str]
    urdf_motor_target: Optional[float]
    urdf_motor_force: Optional[float]
    urdf_collision_type: Optional[str]
    urdf_collision_primitives: Optional[list[dict[str, Any]]]
    urdf_boundaries: Optional[list[dict[str, Any]]]
    urdf_boundary_friction: Optional[float]
    urdf_contact_angle: Optional[float]
    urdf_boundary_shape: Optional[str]
    urdf_boundary_type: Optional[str]
    urdf_boundary_radius: Optional[float]
    urdf_boundary_height: Optional[float]
    urdf_boundary_xyz: Optional[str]
    urdf_boundary_rpy: Optional[str]
    urdf_boundary_thickness: Optional[float]
    urdf_boundary_slot_height: Optional[float]
    urdf_boundary_vane_twist: Optional[float]

    def __getattr__(self, name: str) -> Any:
        """Get an attribute from the object."""
        ...


MODES = "modes"
SUBASSEMBLIES = "subassemblies"
COLOR = "color"
MATERIAL = "material"
EXPORT = "export"


class Section(StrEnum):
    """Manifest sections."""

    PART = "part"
    DIAGRAM = "diagram"
    CONFIG = "config"
    VIEW = "view"
    MATERIAL = "material"


class Mode(StrEnum):
    """Build modes for shapes."""

    DEFAULT = "default"
    PRINT = "print"
    SIMULATE = "simulate"


class Simulate(StrEnum):
    """Simulation hook types."""

    SETUP = "setup"
    STEP = "step"


class ColorType(StrEnum):
    """Standard color names for visualization."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    ORANGE = "orange"
    CYAN = "cyan"
    YELLOW = "yellow"
    MAGENTA = "magenta"
    GREY = "grey"
