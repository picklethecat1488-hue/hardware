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

    routing_path: Optional[str] = Field(
        default=None,
        description="Path to persisted routing YAML file defining traces and vias.",
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
    def flex_tail_corner_radius(self) -> float:
        """Fillet corner radius of flex tail contour in mm."""
        return float(self._raw_data.get("flex_tail_corner_radius", 1.0))

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
    def mounting_post_diameter(self) -> float:
        """Shaft diameter of clip-on mounting posts in mm."""
        return float(self._raw_data["mounting_post_diameter"])

    @property
    def mounting_post_height(self) -> float:
        """Total height of clip-on mounting posts above standoff shoulder in mm."""
        return float(self._raw_data["mounting_post_height"])

    @property
    def mounting_post_flare_diameter(self) -> float:
        """Maximum diameter of flared retaining head on mounting posts in mm."""
        return float(self._raw_data["mounting_post_flare_diameter"])

    @property
    def mounting_post_flare_height(self) -> float:
        """Height of flared retaining head on mounting posts in mm."""
        return float(self._raw_data["mounting_post_flare_height"])

    @property
    def mounting_post_tip_diameter(self) -> float:
        """Lead-in tip diameter at top of mounting posts in mm."""
        return float(self._raw_data["mounting_post_tip_diameter"])

    @property
    def silkscreen_margin(self) -> float:
        """Margin between board edge and silkscreen text markings in mm."""
        return float(self._raw_data["silkscreen_margin"])

    @property
    def enclosure_foot_diameter(self) -> float:
        """Diameter of rubber foot indentations on enclosure bottom in mm."""
        return float(self._raw_data["enclosure_foot_diameter"])

    @property
    def enclosure_foot_depth(self) -> float:
        """Depth of rubber foot indentations on enclosure bottom in mm."""
        return float(self._raw_data["enclosure_foot_depth"])

    @property
    def enclosure_foot_inset(self) -> float:
        """Inset distance of foot indentations from enclosure edge in mm."""
        return float(self._raw_data["enclosure_foot_inset"])

    @property
    def enclosure_corner_radius(self) -> float:
        """Outer corner radius of protective enclosure in mm."""
        return float(self._raw_data["enclosure_corner_radius"])

    @property
    def enclosure_usb_cutout_width(self) -> float:
        """Width of USB-C connector cutout on enclosure side in mm."""
        return float(self._raw_data["enclosure_usb_cutout_width"])

    @property
    def enclosure_usb_cutout_height(self) -> float:
        """Height of USB-C connector cutout on enclosure side in mm."""
        return float(self._raw_data["enclosure_usb_cutout_height"])

    @property
    def enclosure_lip_height(self) -> float:
        """Height of enclosure lid locating rim in mm."""
        return float(self._raw_data["enclosure_lip_height"])

    @property
    def enclosure_m2_cutout_width(self) -> float:
        """Width of M.2 connector cutout on enclosure rear wall in mm."""
        return float(self._raw_data["enclosure_m2_cutout_width"])

    @property
    def enclosure_m2_cutout_height(self) -> float:
        """Height of M.2 connector cutout on enclosure rear wall in mm."""
        return float(self._raw_data["enclosure_m2_cutout_height"])

    @property
    def enclosure_gpio_cutout_width(self) -> float:
        """Width of GPIO header cutout in enclosure lid in mm."""
        return float(self._raw_data["enclosure_gpio_cutout_width"])

    @property
    def enclosure_gpio_cutout_length(self) -> float:
        """Length of GPIO header cutout in enclosure lid in mm."""
        return float(self._raw_data["enclosure_gpio_cutout_length"])

    @property
    def enclosure_swd_cutout_width(self) -> float:
        """Width of SWD connector cutout on enclosure side in mm."""
        return float(self._raw_data["enclosure_swd_cutout_width"])

    @property
    def enclosure_swd_cutout_height(self) -> float:
        """Height of SWD connector cutout on enclosure side in mm."""
        return float(self._raw_data["enclosure_swd_cutout_height"])

    @property
    def enclosure_snap_ridge_depth(self) -> float:
        """Protrusion depth of snap-fit ridges on enclosure lid lip in mm."""
        return float(self._raw_data["enclosure_snap_ridge_depth"])

    @property
    def enclosure_snap_ridge_height(self) -> float:
        """Height of snap-fit ridges on enclosure lid lip in mm."""
        return float(self._raw_data["enclosure_snap_ridge_height"])

    @property
    def enclosure_snap_ridge_length(self) -> float:
        """Length of snap-fit ridges along enclosure rim in mm."""
        return float(self._raw_data["enclosure_snap_ridge_length"])

    @property
    def enclosure_snap_groove_depth(self) -> float:
        """Depth of matching snap-fit retaining grooves in enclosure bottom in mm."""
        return float(self._raw_data["enclosure_snap_groove_depth"])

    @property
    def enclosure_snap_groove_height(self) -> float:
        """Height of matching snap-fit retaining grooves in enclosure bottom in mm."""
        return float(self._raw_data["enclosure_snap_groove_height"])

    @property
    def enclosure_snap_groove_length(self) -> float:
        """Length of matching snap-fit retaining grooves in enclosure bottom in mm."""
        return float(self._raw_data["enclosure_snap_groove_length"])

    @property
    def enclosure_vent_slot_width(self) -> float:
        """Width of ventilation slot along Y in mm."""
        return float(self._raw_data["enclosure_vent_slot_width"])

    @property
    def enclosure_vent_slot_height(self) -> float:
        """Height of ventilation slot along Z in mm."""
        return float(self._raw_data["enclosure_vent_slot_height"])

    @property
    def enclosure_vent_slot_spacing(self) -> float:
        """Center-to-center pitch between ventilation slots in mm."""
        return float(self._raw_data["enclosure_vent_slot_spacing"])

    @property
    def enclosure_vent_count(self) -> int:
        """Number of ventilation slots between charger and amplifier."""
        return int(self._raw_data["enclosure_vent_count"])

    @property
    def led_flange_thickness(self) -> float:
        """Thickness of top flange on clear LED cover in mm."""
        return float(self._raw_data["led_flange_thickness"])

    @property
    def led_flange_width(self) -> float:
        """Width of top square flange on clear LED cover in mm."""
        return float(self._raw_data["led_flange_width"])

    @property
    def led_hole_width(self) -> float:
        """Width of square LED cutout hole through enclosure lid in mm."""
        return float(self._raw_data["led_hole_width"])

    @property
    def led_plug_length(self) -> float:
        """Downward insertion length of LED cover plug in mm."""
        return float(self._raw_data["led_plug_length"])

    @property
    def led_plug_width(self) -> float:
        """Width of square LED cover plug in mm."""
        return float(self._raw_data["led_plug_width"])

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
