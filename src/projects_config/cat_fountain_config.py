"""Cat fountain configuration and measurement logic."""

from typing import Any, Optional, Union, cast
from functools import cached_property
from pydantic import BaseModel, Field
from model import load_measurements, DiagramOptions


class CatFountainConfig(BaseModel):
    """Configuration settings for the cat fountain."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path.",
    )

    diagram_options: DiagramOptions = Field(
        default_factory=lambda: DiagramOptions(line_weight=0.5, view_from="top", show_hidden=True),
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
    def bowl_radius(self) -> float:
        """Return the bowl radius."""
        return float(self._raw_data.get("bowl_radius", 80.0))

    @property
    def bowl_height(self) -> float:
        """Return the bowl height."""
        return float(self._raw_data.get("bowl_height", 40.0))

    @property
    def bowl_thickness(self) -> float:
        """Return the bowl thickness."""
        return float(self._raw_data.get("bowl_thickness", 4.0))

    @property
    def tube_radius(self) -> float:
        """Return the tube outer radius."""
        return float(self._raw_data.get("tube_radius", 8.0))

    @property
    def tube_thickness(self) -> float:
        """Return the tube wall thickness."""
        return float(self._raw_data.get("tube_thickness", 2.0))

    @property
    def tube_height(self) -> float:
        """Return the tube height."""
        return float(self._raw_data.get("tube_height", 100.0))

    @property
    def impeller_radius(self) -> float:
        """Return the impeller outer radius."""
        return float(self._raw_data.get("impeller_radius", 12.0))

    @property
    def impeller_height(self) -> float:
        """Return the impeller height."""
        return float(self._raw_data.get("impeller_height", 15.0))

    @property
    def impeller_shaft_radius(self) -> float:
        """Return the impeller shaft hole radius."""
        return float(self._raw_data.get("impeller_shaft_radius", 2.5))

    @property
    def impeller_blades(self) -> int:
        """Return the number of impeller blades."""
        return int(self._raw_data.get("impeller_blades", 6))

    @property
    def spout_length(self) -> float:
        """Return the spout length extension."""
        return float(self._raw_data.get("spout_length", 30.0))

    @property
    def spout_angle(self) -> float:
        """Return the angle of the spout outlet."""
        return float(self._raw_data.get("spout_angle", 45.0))
