"""Common types and enums for build providers."""

from enum import StrEnum, IntEnum
from typing import Protocol, Optional, Any
from build123d import Shape  # type: ignore


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


class URDFJointType(StrEnum):
    """URDF joint types."""

    FIXED = "fixed"
    REVOLUTE = "revolute"
    CONTINUOUS = "continuous"
    PRISMATIC = "prismatic"
    PLANAR = "planar"
    SPHERICAL = "spherical"


class URDFMotorType(StrEnum):
    """URDF motor control types."""

    VELOCITY = "velocity"
    TORQUE = "torque"


class URDFShape(Protocol):
    """Protocol for build123d shapes with attached URDF properties."""

    urdf_label: Optional[str]
    urdf_parent: Optional[str]
    urdf_joint_type: Optional[URDFJointType | str]
    urdf_joint_axis: Optional[str]
    urdf_joint_lower: Optional[float]
    urdf_joint_upper: Optional[float]
    urdf_material: Optional[str]
    urdf_density: Optional[float]
    urdf_motor_type: Optional[URDFMotorType | str]
    urdf_motor_target: Optional[float]
    urdf_motor_force: Optional[float]
    urdf_collision_type: Optional[str]
    urdf_collision_primitives: Optional[list[dict[str, Any]]]
    urdf_boundaries: Optional[list[dict[str, Any]]]
    urdf_boundary_friction: Optional[float]
    urdf_obj_filename: Optional[str]

    @property
    def urdf_height(self) -> float:
        """Derived height of the shape in meters."""
        ...

    @property
    def urdf_thickness(self) -> float:
        """Derived minimum thickness of the shape in meters."""
        ...


if not hasattr(Shape, "urdf_height"):

    @property
    def _urdf_height(self: Shape) -> float:
        bbox = self.bounding_box()
        return float((bbox.max.Z - bbox.min.Z) * 0.001)

    Shape.urdf_height = _urdf_height  # type: ignore

if not hasattr(Shape, "urdf_thickness"):

    @property
    def _urdf_thickness(self: Shape) -> float:
        bbox = self.bounding_box()
        dx = bbox.max.X - bbox.min.X
        dy = bbox.max.Y - bbox.min.Y
        dz = bbox.max.Z - bbox.min.Z
        return float(min(dx, dy, dz) * 0.001)

    Shape.urdf_thickness = _urdf_thickness  # type: ignore


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
