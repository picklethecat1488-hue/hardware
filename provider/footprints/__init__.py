"""Standard component footprint library defined with build123d primitives."""

from typing import Any, Dict

from provider.pcb.footprint import FOOTPRINT_REGISTRY, BuildFootprint, Pad, PadShape, PadType, footprint
from . import ic, smd, thru_hole
from .provider import FootprintProvider


def get_shared_footprints() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all standard component footprints serialized from build123d primitives."""
    return {name: factory().to_dict() for name, factory in FOOTPRINT_REGISTRY.items()}


ALL_SHARED_FOOTPRINTS: Dict[str, Dict[str, Any]] = get_shared_footprints()

__all__ = [
    "ALL_SHARED_FOOTPRINTS",
    "BuildFootprint",
    "FOOTPRINT_REGISTRY",
    "FootprintProvider",
    "Pad",
    "PadShape",
    "PadType",
    "footprint",
    "get_shared_footprints",
    "ic",
    "smd",
    "thru_hole",
]
