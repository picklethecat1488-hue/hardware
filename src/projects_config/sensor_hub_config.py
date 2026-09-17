"""Sensor hub configuration and parameterized measurements."""

from typing import Any, Optional, Union, cast
from functools import cached_property
from pydantic import BaseModel, Field
from model import load_measurements, DiagramOptions, DiagramStyle


class SensorHubConfig(BaseModel):
    """Configuration settings and parameterized dimensions for the sensor hub rigid-flex assembly."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path.",
    )

    diagram_options: DiagramOptions = Field(
        default_factory=lambda: DiagramOptions(line_weight=1, view_from="iso", style=DiagramStyle.HIDDEN),
        description="Diagram export options",
    )

    material: str = Field(
        default="petg",
        description="Material for enclosure and mechanical mounts.",
    )

    @cached_property
    def _raw_data(self) -> dict[Union[int, str], Any]:
        """Load and normalize raw measurements from the YAML file."""
        if self.measurements_path is None:
            raise ValueError("measurements_path is not set.")

        raw = load_measurements(cast(str, self.measurements_path))
        return {int(k) if isinstance(k, int) or (isinstance(k, str) and k.isdigit()) else k: v for k, v in raw.items()}

    @property
    def board_width(self) -> float:
        """Width of the main rigid carrier PCB in mm."""
        return float(self._raw_data.get("board_width", 60.0))

    @property
    def board_length(self) -> float:
        """Length of the main rigid carrier PCB in mm."""
        return float(self._raw_data.get("board_length", 90.0))

    @property
    def corner_radius(self) -> float:
        """Fillet corner radius of the PCB in mm."""
        return float(self._raw_data.get("corner_radius", 4.0))

    @property
    def board_thickness(self) -> float:
        """Total nominal thickness of the rigid PCB stackup in mm."""
        return float(self._raw_data.get("board_thickness", 1.6))

    @property
    def flex_tail_width(self) -> float:
        """Width of the capacitive sensing flex tail ribbon in mm."""
        return float(self._raw_data.get("flex_tail_width", 16.0))

    @property
    def flex_tail_length(self) -> float:
        """Length of the flex tail extension in mm."""
        return float(self._raw_data.get("flex_tail_length", 50.0))

    @property
    def flex_tail_thickness(self) -> float:
        """Thickness of the flexible polyimide substrate in mm."""
        return float(self._raw_data.get("flex_tail_thickness", 0.20))

    @property
    def flex_bend_radius(self) -> float:
        """Allowable dynamic bend radius in mm."""
        return float(self._raw_data.get("flex_bend_radius", 3.0))

    @property
    def enclosure_wall_thickness(self) -> float:
        """Wall thickness of protective enclosure in mm."""
        return float(self._raw_data.get("enclosure_wall_thickness", 2.0))

    @property
    def enclosure_clearance(self) -> float:
        """Clearance between PCB edge and enclosure inner wall in mm."""
        return float(self._raw_data.get("enclosure_clearance", 1.5))

    @property
    def mounting_hole_diameter(self) -> float:
        """Diameter of M3 corner mounting holes in mm."""
        return float(self._raw_data.get("mounting_hole_diameter", 3.2))

    @property
    def mounting_hole_inset(self) -> float:
        """Inset distance of mounting hole centers from board edge in mm."""
        return float(self._raw_data.get("mounting_hole_inset", 4.5))
