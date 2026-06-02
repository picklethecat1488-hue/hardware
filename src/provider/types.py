"""Common types and enums for build providers."""

from enum import StrEnum


MODES = "modes"
SUBASSEMBLIES = "subassemblies"
COLOR = "color"


class Action(StrEnum):
    """Build actions for shapes."""

    PART = "part"
    DIAGRAM = "diagram"
    CONFIG = "config"
    VIEW = "view"


class Mode(StrEnum):
    """Build modes for shapes."""

    DEFAULT = "default"
    PRINT = "print"
