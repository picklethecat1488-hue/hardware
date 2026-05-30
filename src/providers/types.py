"""Common types and enums for build providers."""

from enum import StrEnum


MODES = "modes"
SUBASSEMBLIES = "subassemblies"
COLOR = "color"


class Action(StrEnum):
    """Build actions for shapes."""

    WIRE = "wire"
    SKETCH = "sketch"
    PART = "part"
    DIAGRAM = "diagram"
    CONFIG = "config"


class Subassembly(StrEnum):
    """Side identifiers for shapes."""

    LEFT = "left"
    RIGHT = "right"


class Mode(StrEnum):
    """Build modes for shapes."""

    DEFAULT = "default"
    BARE = "bare"
    TEXT = "text"
    MOUNT = "mount"
