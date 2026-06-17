"""Models package root."""

import OCP.TopoDS  # type: ignore

# Monkey-patch TopoDS_Shape to resolve Pydantic validation errors.
# Pydantic 2 probes for a HashCode method when validating OCP-wrapped types.
if not hasattr(OCP.TopoDS.TopoDS_Shape, "HashCode"):
    OCP.TopoDS.TopoDS_Shape.HashCode = lambda self, upper: id(self) % upper  # type: ignore

from .provider import Provider
from .types import Mode, Section, MODES, ColorType, SUBASSEMBLIES, MATERIAL, EXPORT
from .target_list import TargetList
from .room import Room
from .provider_router import ProviderRouter
from .provider_manager import ProviderManager
from .utils import load_manifest, discover_provider
