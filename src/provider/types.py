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
    urdf_boundary_friction: Optional[float]
    urdf_contact_angle: Optional[float]

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
    TEARDOWN = "teardown"


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
