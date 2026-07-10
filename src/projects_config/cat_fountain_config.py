"""Cat fountain configuration and measurement logic."""

from typing import Any, Optional, Union, cast
from functools import cached_property
from pathlib import Path
from pydantic import BaseModel, Field
from model import load_measurements, DiagramOptions


class CatFountainConfig(BaseModel):
    """Configuration settings for the cat fountain."""

    measurements_path: Optional[str] = Field(
        default=None,
        description="Optional override for the measurements YAML file path.",
    )

    diagram_options: DiagramOptions = Field(
        default_factory=lambda: DiagramOptions(line_weight=1, view_from="iso", show_hidden=True),
        description="Diagram export options",
    )

    material: str = Field(
        default="petg",
        description="The material name to use for the cat fountain parts (e.g. petg, pla, abs).",
    )

    # =========================================================================
    # Internal & Helper Properties
    # =========================================================================

    @cached_property
    def _raw_data(self) -> dict[Union[int, str], Any]:
        """Load and normalize raw measurements from the YAML file."""
        if self.measurements_path is None:
            raise ValueError("measurements_path is not set.")

        raw = load_measurements(cast(str, self.measurements_path))
        return {int(k) if isinstance(k, int) or (isinstance(k, str) and k.isdigit()) else k: v for k, v in raw.items()}

    @property
    def manifest_path(self) -> Path:
        """Return the path to the manifest configuration file."""
        if self.measurements_path is not None:
            return Path(self.measurements_path).parent / "manifest.yaml"
        return Path(__file__).parent.parent / "projects" / "cat_fountain" / "manifest.yaml"

    @cached_property
    def _material_data(self) -> dict[str, Any]:
        """Load and return materials data from the manifest."""
        from provider.utils import load_manifest

        path = self.manifest_path
        if path.exists():
            manifest = load_manifest(str(path))
        else:
            manifest = {}
        return manifest.get("material", {})

    # =========================================================================
    # Bowl Parameters
    # =========================================================================

    @cached_property
    def bowl_radius(self) -> float:
        """Return the bowl radius."""
        return float(self._raw_data.get("bowl_radius", 80.0))

    @cached_property
    def bowl_height(self) -> float:
        """Return the bowl height."""
        return float(self._raw_data.get("bowl_height", 40.0))

    @cached_property
    def bowl_thickness(self) -> float:
        """Return the bowl thickness."""
        return float(self._raw_data.get("bowl_thickness", 4.0))

    # =========================================================================
    # Tube Parameters
    # =========================================================================

    @cached_property
    def tube_radius(self) -> float:
        """Return the tube outer radius."""
        return float(self._raw_data.get("tube_radius", 8.0))

    @cached_property
    def tube_thickness(self) -> float:
        """Return the tube wall thickness."""
        return float(self._raw_data.get("tube_thickness", 2.0))

    @cached_property
    def tube_height(self) -> float:
        """Return the tube height."""
        return float(self._raw_data.get("tube_height", 100.0))

    @cached_property
    def slot_height(self) -> float:
        """Return the vertical tube intake slot height in millimeters."""
        return float(self._raw_data.get("slot_height", 15.0))

    # =========================================================================
    # Impeller Parameters
    # =========================================================================

    @cached_property
    def impeller_radius(self) -> float:
        """Return the impeller outer radius."""
        return float(self._raw_data.get("impeller_radius", 12.0))

    @cached_property
    def impeller_height(self) -> float:
        """Return the impeller height."""
        return float(self._raw_data.get("impeller_height", 15.0))

    @cached_property
    def impeller_shaft_radius(self) -> float:
        """Return the impeller shaft hole radius."""
        return float(self._raw_data.get("impeller_shaft_radius", 2.5))

    @cached_property
    def impeller_blades(self) -> int:
        """Return the number of impeller blades."""
        return int(self._raw_data.get("impeller_blades", 6))

    @cached_property
    def vane_twist(self) -> float:
        """Return the total twist angle of the impeller blades in degrees."""
        return float(self._raw_data.get("vane_twist", -1080.0))

    # =========================================================================
    # Spout Parameters
    # =========================================================================

    @cached_property
    def spout_length(self) -> float:
        """Return the spout length extension."""
        return float(self._raw_data.get("spout_length", 30.0))

    @cached_property
    def spout_angle(self) -> float:
        """Return the angle of the spout outlet."""
        return float(self._raw_data.get("spout_angle", 45.0))

    # =========================================================================
    # Material Parameters
    # =========================================================================

    @cached_property
    def petg_density(self) -> float:
        """Return the density of PETG material dynamically from manifest configuration."""
        return float(self._material_data.get("petg", {}).get("density", 1.27))

    @cached_property
    def petg_boundary_friction(self) -> float:
        """Return the boundary friction of PETG material dynamically from manifest configuration."""
        return float(self._material_data.get("petg", {}).get("boundary_friction", 0.20))

    @cached_property
    def petg_contact_angle(self) -> float:
        """Return the contact angle of PETG material dynamically from manifest configuration."""
        return float(self._material_data.get("petg", {}).get("contact_angle", 75.0))

    @property
    def density(self) -> float:
        """Return the density of the configured material dynamically from manifest configuration."""
        return float(self._material_data.get(self.material, {}).get("density", 1.27))

    @property
    def boundary_friction(self) -> float:
        """Return the boundary friction of the configured material dynamically from manifest configuration."""
        return float(self._material_data.get(self.material, {}).get("boundary_friction", 0.20))

    @property
    def contact_angle(self) -> float:
        """Return the contact angle of the configured material dynamically from manifest configuration."""
        return float(self._material_data.get(self.material, {}).get("contact_angle", 75.0))

    # =========================================================================
    # Lid & Spout Deflection Boundary Parameters
    # =========================================================================

    @cached_property
    def lid_pocket_radius(self) -> float:
        """Return the lid pocket radius in millimeters."""
        return float(self._raw_data.get("lid_pocket_radius", 80.0))

    @cached_property
    def lid_pocket_cavity_height(self) -> float:
        """Return the lid pocket cavity height in millimeters."""
        return float(self._raw_data.get("lid_pocket_cavity_height", 10.0))

    @cached_property
    def lid_pocket_thickness(self) -> float:
        """Return the lid pocket wall thickness in millimeters."""
        return float(self._raw_data.get("lid_pocket_thickness", 4.0))

    @cached_property
    def lid_pocket_z_offset(self) -> float:
        """Return the lid pocket Z offset in millimeters."""
        return float(self._raw_data.get("lid_pocket_z_offset", 3.0))

    @cached_property
    def drain_hole_y(self) -> float:
        """Return the drain hole Y coordinate in millimeters."""
        return float(self._raw_data.get("drain_hole_y", 65.0))

    @cached_property
    def drain_hole_radius(self) -> float:
        """Return the drain hole radius in millimeters."""
        return float(self._raw_data.get("drain_hole_radius", 15.0))

    @cached_property
    def spout_deflection_radius(self) -> float:
        """Return the spout deflection cap radius in millimeters."""
        return float(self._raw_data.get("spout_deflection_radius", 13.0))

    @cached_property
    def spout_deflection_height(self) -> float:
        """Return the spout deflection cap cavity height in millimeters."""
        return float(self._raw_data.get("spout_deflection_height", 0.0))

    @cached_property
    def spout_deflection_thickness(self) -> float:
        """Return the spout deflection cap thickness in millimeters."""
        return float(self._raw_data.get("spout_deflection_thickness", 40.0))

    @cached_property
    def spout_deflection_z_offset(self) -> float:
        """Return the spout deflection cap Z offset in millimeters."""
        return float(self._raw_data.get("spout_deflection_z_offset", 16.0))

    # =========================================================================
    # Simulation Parameters
    # =========================================================================

    @cached_property
    def spawn_spacing_factor(self) -> float:
        """Return the spawn spacing factor."""
        return float(self._raw_data.get("spawn_spacing_factor", 2.2))

    @cached_property
    def z_spawn_buffer(self) -> float:
        """Return the Z spawn buffer."""
        return float(self._raw_data.get("z_spawn_buffer", 0.001))

    @cached_property
    def max_spawn_height(self) -> float:
        """Return the max spawn height."""
        return float(self._raw_data.get("max_spawn_height", 0.120))

    @cached_property
    def impeller_clearance_radius(self) -> float:
        """Return the impeller clearance radius."""
        return float(self._raw_data.get("impeller_clearance_radius", 0.015))

    @cached_property
    def spout_min_height(self) -> float:
        """Return the spout min height."""
        return float(self._raw_data.get("spout_min_height", 0.095))

    @cached_property
    def spout_max_y(self) -> float:
        """Return the spout max Y limit."""
        return float(self._raw_data.get("spout_max_y", 0.030))

    # =========================================================================
    # Refinement Clearances & Dimensions
    # =========================================================================

    @cached_property
    def lid_clearance(self) -> float:
        """Return the lid fitment clearance."""
        return float(self._raw_data.get("lid_clearance", 0.15))

    @cached_property
    def lid_step_depth(self) -> float:
        """Return the lid step depth."""
        return float(self._raw_data.get("lid_step_depth", 5.0))

    @cached_property
    def lid_step_width(self) -> float:
        """Return the lid step width."""
        return float(self._raw_data.get("lid_step_width", 2.0))

    @cached_property
    def tube_lid_clearance(self) -> float:
        """Return the clearance between the tube and the lid socket."""
        return float(self._raw_data.get("tube_lid_clearance", 0.1))

    @cached_property
    def bottom_cover_clearance(self) -> float:
        """Return the bottom cover clearance."""
        return float(self._raw_data.get("bottom_cover_clearance", 0.2))

    @cached_property
    def bottom_cover_drain_radius(self) -> float:
        """Return the bottom cover central drainage hole radius."""
        return float(self._raw_data.get("bottom_cover_drain_radius", 8.0))

    @cached_property
    def pcb_hole_radius(self) -> float:
        """Return the mounting hole radius for PCBs."""
        return float(self._raw_data.get("pcb_hole_radius", 1.0))

    @cached_property
    def pcb_boss_radius(self) -> float:
        """Return the outer boss radius for PCB mounting posts."""
        return float(self._raw_data.get("pcb_boss_radius", 2.2))

    # Fuel Gauge
    @cached_property
    def fuel_gauge_spacing_x(self) -> float:
        """Return X hole spacing for the Fuel Gauge."""
        return float(self._raw_data.get("fuel_gauge_spacing_x", 20.0))

    @cached_property
    def fuel_gauge_spacing_y(self) -> float:
        """Return Y hole spacing for the Fuel Gauge."""
        return float(self._raw_data.get("fuel_gauge_spacing_y", 16.0))

    @cached_property
    def fuel_gauge_standoff_height(self) -> float:
        """Return standoff height for the Fuel Gauge."""
        return float(self._raw_data.get("fuel_gauge_standoff_height", 4.0))

    # Proximity Sensor
    @cached_property
    def proximity_sensor_spacing_x(self) -> float:
        """Return X hole spacing for the proximity sensor."""
        return float(self._raw_data.get("proximity_sensor_spacing_x", 21.0))

    @cached_property
    def proximity_sensor_spacing_y(self) -> float:
        """Return Y hole spacing for the proximity sensor."""
        return float(self._raw_data.get("proximity_sensor_spacing_y", 13.5))

    @cached_property
    def proximity_sensor_standoff_height(self) -> float:
        """Return standoff height for the proximity sensor."""
        return float(self._raw_data.get("proximity_sensor_standoff_height", 4.0))

    # Raspberry Pi Pico
    @cached_property
    def pico_spacing_x(self) -> float:
        """Return X hole spacing for Raspberry Pi Pico W."""
        return float(self._raw_data.get("pico_spacing_x", 13.0))

    @cached_property
    def pico_spacing_y(self) -> float:
        """Return Y hole spacing for Raspberry Pi Pico W."""
        return float(self._raw_data.get("pico_spacing_y", 48.0))

    @cached_property
    def pico_standoff_height(self) -> float:
        """Return standoff height for Raspberry Pi Pico W."""
        return float(self._raw_data.get("pico_standoff_height", 4.0))

    # Charger
    @cached_property
    def charger_spacing_x(self) -> float:
        """Return X hole spacing for Charger."""
        return float(self._raw_data.get("charger_spacing_x", 14.0))

    @cached_property
    def charger_spacing_y(self) -> float:
        """Return Y hole spacing for Charger."""
        return float(self._raw_data.get("charger_spacing_y", 25.0))

    @cached_property
    def charger_standoff_height(self) -> float:
        """Return standoff height for Charger."""
        return float(self._raw_data.get("charger_standoff_height", 2.0))

    # NeoDriver
    @cached_property
    def neodriver_spacing_x(self) -> float:
        """Return X hole spacing for NeoDriver."""
        return float(self._raw_data.get("neodriver_spacing_x", 21.0))

    @cached_property
    def neodriver_spacing_y(self) -> float:
        """Return Y hole spacing for NeoDriver."""
        return float(self._raw_data.get("neodriver_spacing_y", 14.0))

    @cached_property
    def neodriver_standoff_height(self) -> float:
        """Return standoff height for NeoDriver."""
        return float(self._raw_data.get("neodriver_standoff_height", 4.0))

    # Current Monitor
    @cached_property
    def current_monitor_spacing_x(self) -> float:
        """Return X hole spacing for current monitor."""
        return float(self._raw_data.get("current_monitor_spacing_x", 21.0))

    @cached_property
    def current_monitor_spacing_y(self) -> float:
        """Return Y hole spacing for current monitor."""
        return float(self._raw_data.get("current_monitor_spacing_y", 17.5))

    @cached_property
    def current_monitor_standoff_height(self) -> float:
        """Return standoff height for current monitor."""
        return float(self._raw_data.get("current_monitor_standoff_height", 4.0))

    # Motor Driver
    @cached_property
    def motor_driver_spacing_x(self) -> float:
        """Return X hole spacing for motor driver."""
        return float(self._raw_data.get("motor_driver_spacing_x", 20.0))

    @cached_property
    def motor_driver_spacing_y(self) -> float:
        """Return Y hole spacing for motor driver."""
        return float(self._raw_data.get("motor_driver_spacing_y", 15.0))

    @cached_property
    def motor_driver_standoff_height(self) -> float:
        """Return standoff height for motor driver."""
        return float(self._raw_data.get("motor_driver_standoff_height", 4.0))

    # Motor mount
    @cached_property
    def motor_spacing_x(self) -> float:
        """Return mounting screw spacing for N20 Motor."""
        return float(self._raw_data.get("motor_spacing_x", 17.0))

    # LED Button / hole
    @cached_property
    def led_hole_width(self) -> float:
        """Return the side width of the square LED hole."""
        return float(self._raw_data.get("led_hole_width", 5.0))

    @cached_property
    def led_plug_width(self) -> float:
        """Return the side width of the LED plug insert."""
        return float(self._raw_data.get("led_plug_width", 4.8))

    @cached_property
    def led_flange_width(self) -> float:
        """Return the side width of the LED cover flange."""
        return float(self._raw_data.get("led_flange_width", 7.0))

    @cached_property
    def led_flange_thickness(self) -> float:
        """Return the thickness of the LED cover flange."""
        return float(self._raw_data.get("led_flange_thickness", 1.0))

    @cached_property
    def led_plug_length(self) -> float:
        """Return the length/depth of the LED plug insert."""
        return float(self._raw_data.get("led_plug_length", 3.0))

    # Sensor Port Boss
    @cached_property
    def sensor_boss_x(self) -> float:
        """Return X size of sensor outer boss."""
        return float(self._raw_data.get("sensor_boss_x", 12.0))

    @cached_property
    def sensor_boss_y(self) -> float:
        """Return Y size of sensor outer boss."""
        return float(self._raw_data.get("sensor_boss_y", 14.0))

    @cached_property
    def sensor_boss_z(self) -> float:
        """Return Z size of sensor outer boss."""
        return float(self._raw_data.get("sensor_boss_z", 14.0))
