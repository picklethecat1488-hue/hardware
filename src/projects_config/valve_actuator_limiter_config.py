"""Valve actuator limiter configuration and measurement logic."""

from typing import Any, Optional, Union, cast, List
from functools import cached_property
import numpy as np
from build123d import Vector
from pydantic import BaseModel, Field
from model import load_measurements, DiagramOptions


class ValveActuatorLimiterConfig(BaseModel):
    """Configuration settings for the valve actuator limiter."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path.",
    )

    base_thickness: float = Field(default=5.0, description="The thickness of the limiter plate base.", gt=0)

    diagram_options: DiagramOptions = Field(
        default_factory=lambda: DiagramOptions(line_weight=0.5, projection_origin=(0, 0, -1), show_hidden=True),
        description="Diagram export options",
    )

    @cached_property
    def _raw_data(self) -> dict[Union[int, str], Any]:
        """Load and normalize raw measurements from the YAML file."""
        if self.measurements_path is None:
            raise ValueError("measurements_path is not set.")

        raw = load_measurements(cast(str, self.measurements_path))
        return {int(k) if isinstance(k, int) or (isinstance(k, str) and k.isdigit()) else k: v for k, v in raw.items()}

    @property
    def wall_thickness(self) -> float:
        """Return the part wall thickness."""
        return float(self._raw_data.get("wall_thickness", 0.0))

    @property
    def pocket_depth(self) -> float:
        """Return the clearance for the gear protrusion."""
        return float(self._raw_data.get("pocket_depth", 0.0))

    @property
    def pocket_radius(self) -> float:
        """Return the pocket radius."""
        return float(self._raw_data.get("pocket_radius", 0.0))

    @property
    def bolt_radius(self) -> float:
        """Return the bolt alignment radius."""
        return float(self._raw_data.get("bolt_radius", 0.0))

    @property
    def stop_angle(self) -> float:
        """Return the valve travel span angle."""
        return float(self._raw_data.get("stop_angle", 0.0))

    @property
    def zip_tie_hole_offset(self) -> float:
        """Return the distance from the bolt hole center to the zip tie notch."""
        return float(self._raw_data.get("zip_tie_hole_offset", 0.0))

    @property
    def zip_tie_cut_width(self) -> float:
        """Return the width of the zip tie notch cut."""
        return float(self._raw_data.get("zip_tie_cut_width", 0.0))

    @property
    def zip_tie_cut_height(self) -> float:
        """Return the height of the zip tie notch cut (radial depth)."""
        return float(self._raw_data.get("zip_tie_cut_height", 0.0))

    @property
    def bolt_holes(self) -> List[Vector]:
        """Return the list of asymmetric bolt hole coordinates."""
        return [self._ndarray2vec(np.array(p)) for p in self._raw_data.get("bolt_holes", [])]

    def _ndarray2vec(self, arr: np.ndarray) -> Vector:
        """Convert a numpy array to a build123d Vector."""
        if arr.shape == (2,):
            # Defaults Z to 0.0
            return Vector(X=float(arr[0]), Y=float(arr[1]))
        return Vector(X=float(arr[0]), Y=float(arr[1]), Z=float(arr[2]))
