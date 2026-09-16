"""Test board configuration and parameterized measurements."""

from typing import Any, Optional, Union, cast
from functools import cached_property
from pydantic import BaseModel, Field
from model import load_measurements, DiagramOptions, DiagramStyle


class TestBoardConfig(BaseModel):
    """Configuration settings and parameterized dimensions for the test board rigid-flex assembly."""

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
        return float(self._raw_data["board_width"])

    @property
    def board_length(self) -> float:
        """Length of the main rigid carrier PCB in mm."""
        return float(self._raw_data["board_length"])

    @property
    def corner_radius(self) -> float:
        """Fillet corner radius of the PCB in mm."""
        return float(self._raw_data["corner_radius"])

    @property
    def board_thickness(self) -> float:
        """Total nominal thickness of the rigid PCB stackup in mm."""
        return float(self._raw_data["board_thickness"])

    @property
    def flex_tail_width(self) -> float:
        """Width of the capacitive sensing flex tail ribbon in mm."""
        return float(self._raw_data["flex_tail_width"])

    @property
    def flex_tail_length(self) -> float:
        """Length of the flex tail extension in mm."""
        return float(self._raw_data["flex_tail_length"])

    @property
    def flex_tail_thickness(self) -> float:
        """Thickness of the flexible polyimide substrate in mm."""
        return float(self._raw_data["flex_tail_thickness"])

    @property
    def flex_bend_radius(self) -> float:
        """Allowable dynamic bend radius in mm."""
        return float(self._raw_data["flex_bend_radius"])

    @property
    def enclosure_wall_thickness(self) -> float:
        """Wall thickness of protective enclosure in mm."""
        return float(self._raw_data["enclosure_wall_thickness"])

    @property
    def enclosure_clearance(self) -> float:
        """Clearance between PCB edge and enclosure inner wall in mm."""
        return float(self._raw_data["enclosure_clearance"])

    @property
    def mounting_hole_diameter(self) -> float:
        """Diameter of M3 corner mounting holes in mm."""
        return float(self._raw_data["mounting_hole_diameter"])

    @property
    def mounting_hole_inset(self) -> float:
        """Inset distance of mounting hole centers from board edge in mm."""
        return float(self._raw_data["mounting_hole_inset"])

    @property
    def standoff_height(self) -> float:
        """Height of enclosure mounting standoffs in mm."""
        return float(self._raw_data["standoff_height"])

    @property
    def standoff_radius(self) -> float:
        """Radius of enclosure mounting standoffs in mm."""
        return float(self._raw_data["standoff_radius"])

    @property
    def test_tdr_rise_time_ps(self) -> float:
        """TDR step rise time in picoseconds for factory impedance testing."""
        return float(self._raw_data.get("test_tdr_rise_time_ps", 100.0))

    @property
    def test_cap_stimulus_freq_khz(self) -> float:
        """Stimulus frequency in kHz for factory capacitive touch testing."""
        return float(self._raw_data.get("test_cap_stimulus_freq_khz", 250.0))

    @property
    def test_pcie_diff_target_ohm(self) -> float:
        """Target differential impedance in ohms for PCIe lines."""
        return float(self._raw_data.get("test_pcie_diff_target_ohm", 85.0))
