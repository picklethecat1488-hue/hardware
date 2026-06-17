"""Common types and enums for build providers."""

from enum import StrEnum


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
