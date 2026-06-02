"""Valve actuator limiter geometry provider."""

from functools import cached_property
from build123d import *
import cadquery as cq
from model import method_cache
from pathlib import Path
from provider import Provider, Action, Mode, discover_provider
from projects_config.valve_actuator_limiter_config import ValveActuatorLimiterConfig
from typing import Any, cast, Callable


@discover_provider
class ValveActuatorLimiterProvider(Provider):
    """Provider for valve actuator limiter geometry.

    This provider manages the creation of mechanical stops used to limit the rotation
    of exhaust valve actuators, typically used when aftermarket exhaust components
    interfere with OEM actuator sweep ranges.
    """

    @cached_property
    def default_config(self) -> ValveActuatorLimiterConfig:
        """Return the default configuration for the limiter project."""
        return ValveActuatorLimiterConfig(measurements_path=str(Path(__file__).parent / "measurements.yaml"))

    @property
    def part(self) -> dict[str, Callable[..., Part]]:
        """A mapping of part names to their build handler methods."""
        return {name: self.build_part for name in self.targets.supporting(Action.PART)}

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """A mapping of diagram names to their build handler methods."""
        return {name: self.build_diagram for name in self.targets.supporting(Action.DIAGRAM)}

    def build_part(self, target: str, subassembly: str, mode: Mode) -> Part:
        """Build the geometry for a limiter plate."""
        with BuildPart() as p:
            Box(20, 30, self.settings.base_thickness)
            if subassembly == "right":
                mirror(about=Plane.YZ)
        if p.part is None:
            raise ValueError(f"Failed to build part for target '{target}'")
        return p.part

    def build_diagram(self, targets: list[str], mode: Mode) -> Any:
        """Build an assembly diagram for the limiter plates."""
        assy = cq.Assembly()
        # Build the left subassembly for the diagram view
        plate = self.build_part("limiter_plate", "left", mode=mode)

        # Pylance fix: Ensure the wrapped OCCT shape is not None before casting to CadQuery
        if plate.wrapped is not None:
            assy.add(cq.Shape.cast(plate.wrapped), name="plate")

        return assy
