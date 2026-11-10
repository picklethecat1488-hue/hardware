"""Discoverable provider exposing 3D component footprints for inspection in tools/view.py."""

from functools import cached_property
from typing import Any, Callable, Dict, Optional
from build123d import Box, BuildPart, Cylinder, Locations
from pydantic import BaseModel

from provider.pcb.footprint import FOOTPRINT_REGISTRY, BuildFootprint, PadShape
from provider.provider import Provider
from provider.room import Room
from provider.types import Mode as ProviderMode
from provider.utils import discover_provider


class FootprintsConfig(BaseModel):
    """Configuration model for component footprints provider."""

    pass


@discover_provider
class FootprintProvider(Provider):
    """Geometry provider exposing 3D component footprint visual models and inspection views."""

    @property
    def name(self) -> str:
        """Provider identifier for target resolution (e.g. 'footprints/<pkg>')."""
        return "footprints"

    @cached_property
    def default_config(self) -> BaseModel:
        """Return default configuration model."""
        return FootprintsConfig()

    @property
    def part(self) -> Dict[str, Callable[..., BuildPart]]:
        """Map footprint package names to 3D CAD part builder functions."""
        return {
            pkg_name: (
                lambda target, subassembly=None, mode=ProviderMode.DEFAULT, name=pkg_name: self.build_footprint_part(
                    name
                )
            )
            for pkg_name in FOOTPRINT_REGISTRY.keys()
        }

    @property
    def view(self) -> Dict[str, Callable[[Room, ProviderMode], None]]:
        """Map footprint package names to visual 3D inspection views with copper pads and dimensions."""
        return {
            pkg_name: (lambda room, mode=ProviderMode.DEFAULT, name=pkg_name: self.build_footprint_view(room, name))
            for pkg_name in FOOTPRINT_REGISTRY.keys()
        }

    def build_footprint_part(self, name: str) -> BuildPart:
        """Build 3D physical body for component footprint."""
        factory = FOOTPRINT_REGISTRY[name]
        return factory()

    def build_footprint_view(self, room: Room, name: str) -> None:
        """Construct detailed 3D inspection view of footprint body and copper pads."""
        factory = FOOTPRINT_REGISTRY[name]
        fp: BuildFootprint = factory()
        if fp.part is not None:
            room.add(f"{name}_body", fp.part, color=(0.2, 0.2, 0.2), alpha=0.85)

        # Render copper pads as thin 3D copper solids (35 um standard copper foil thickness)
        for idx, pin in enumerate(fp.pins):
            w, h = pin.pad_size_mm
            pad_name = f"{name}_pad_{pin.name}_{idx}"
            thickness = 0.035
            z_offset = fp.dimensions[2] / 2.0 if fp.dimensions[2] > 0 else 0.0
            with BuildPart() as pad_part:
                with Locations([(pin.position[0], pin.position[1], z_offset)]):
                    if pin.pad_shape == PadShape.CIRCLE:
                        Cylinder(radius=w / 2.0, height=thickness)
                    else:
                        Box(w, h, thickness)
            room.add(pad_name, pad_part.part, color=(0.85, 0.55, 0.15), alpha=1.0)
