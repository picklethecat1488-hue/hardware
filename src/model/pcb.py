"""Data models for multi-layer printed circuit boards, high-speed constraints, and flex stackups."""

import math
from enum import StrEnum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator

# Default relative permittivity (epsilon_r) for standard FR-4 dielectric substrates
DEFAULT_FR4_DIELECTRIC_PERMITTIVITY: float = 4.2


class LayerType(StrEnum):
    """Functional categorization of a physical stackup layer."""

    SIGNAL = "signal"
    GROUND = "ground"
    POWER = "power"
    DIELECTRIC = "dielectric"
    COVERLAY = "coverlay"
    STIFFENER = "stiffener"


class StackupLayerModel(BaseModel):
    """Data model representing an individual layer in a multi-layer stackup."""

    name: str = Field(description="Layer identifier (e.g. F.Cu, In1.Cu, Prepreg1, B.Cu)")
    layer_type: LayerType = Field(description="Layer functional type")
    thickness_mm: float = Field(gt=0.0, description="Layer thickness in millimeters")
    material: str = Field(default="copper", description="Layer material (e.g. copper, FR4, polyimide)")
    dielectric_constant: Optional[float] = Field(
        default=None, description="Relative dielectric permittivity (epsilon_r) for dielectric layers"
    )
    loss_tangent: Optional[float] = Field(
        default=None, description="Dielectric loss tangent (tan delta) for high-speed signal integrity"
    )


class StackupModel(BaseModel):
    """Data model representing a 4 to 8+ layer physical substrate stackup with impedance solvers."""

    layers: List[StackupLayerModel] = Field(description="Sequential list of layers from top to bottom")
    finish: str = Field(default="ENIG", description="Surface finish (e.g. ENIG, HASL, OSP, Immersion Silver)")
    soldermask_color: str = Field(default="green", description="Solder mask color")
    silkscreen_color: str = Field(default="white", description="Silkscreen legend color")

    @model_validator(mode="after")
    def validate_layer_symmetry_and_count(self) -> "StackupModel":
        """Validate that stackup contains valid conductive layers (4, 6, 8, etc.) and dielectrics."""
        copper_layers = [
            l for l in self.layers if l.layer_type in (LayerType.SIGNAL, LayerType.GROUND, LayerType.POWER)
        ]
        count = len(copper_layers)
        if count < 2:
            raise ValueError(f"PCB stackup must contain at least 2 conductive copper layers, found {count}")
        if count % 2 != 0:
            raise ValueError(f"Multi-layer PCB stackups must have an even copper layer count, found {count}")
        return self

    @property
    def copper_layers(self) -> List[StackupLayerModel]:
        """Return all conductive copper layers."""
        return [l for l in self.layers if l.layer_type in (LayerType.SIGNAL, LayerType.GROUND, LayerType.POWER)]

    @property
    def copper_layer_count(self) -> int:
        """Return total number of conductive copper layers."""
        return len(self.copper_layers)

    @property
    def total_thickness_mm(self) -> float:
        """Calculate total physical stackup thickness across all layers."""
        return sum(l.thickness_mm for l in self.layers)

    def get_reference_plane(self, signal_layer_name: str) -> Tuple[StackupLayerModel, float, float]:
        """Find the nearest adjacent reference plane layer, dielectric distance H, and effective permittivity er.

        Args:
            signal_layer_name: Name of the signal layer to resolve.

        Returns:
            Tuple of (reference_plane_layer, height_h_mm, effective_er).
        """
        layer_names = [l.name for l in self.layers]
        if signal_layer_name not in layer_names:
            raise ValueError(f"Layer '{signal_layer_name}' not found in stackup")

        target_idx = layer_names.index(signal_layer_name)

        # Search downwards and upwards for the closest GROUND or POWER plane
        best_ref = None
        min_dist = float("inf")
        best_er = DEFAULT_FR4_DIELECTRIC_PERMITTIVITY

        for direction in (-1, 1):
            curr_idx = target_idx + direction
            accum_dist = 0.0
            er_sum = 0.0
            er_count = 0
            while 0 <= curr_idx < len(self.layers):
                l = self.layers[curr_idx]
                if l.layer_type in (LayerType.GROUND, LayerType.POWER):
                    if accum_dist < min_dist and accum_dist > 0.0:
                        min_dist = accum_dist
                        best_ref = l
                        best_er = (er_sum / er_count) if er_count > 0 else DEFAULT_FR4_DIELECTRIC_PERMITTIVITY
                    break
                elif l.layer_type == LayerType.DIELECTRIC:
                    accum_dist += l.thickness_mm
                    if l.dielectric_constant is not None:
                        er_sum += l.dielectric_constant
                        er_count += 1
                curr_idx += direction

        if best_ref is None:
            # Fallback default for surface microstrip against inner ground
            best_ref = self.copper_layers[1] if len(self.copper_layers) > 1 else self.copper_layers[0]
            min_dist = 0.100
            best_er = DEFAULT_FR4_DIELECTRIC_PERMITTIVITY

        return best_ref, min_dist, best_er

    @staticmethod
    def calculate_microstrip_impedance(
        width_mm: float,
        copper_thickness_mm: float,
        height_mm: float,
        dielectric_er: float,
    ) -> float:
        """Calculate single-ended microstrip characteristic impedance Z0 using IPC-2141 / Wheeler equations.

        Args:
            width_mm: Trace width W in millimeters.
            copper_thickness_mm: Copper thickness T in millimeters.
            height_mm: Dielectric height H above ground reference plane.
            dielectric_er: Relative permittivity epsilon_r.

        Returns:
            Characteristic impedance Z0 in Ohms.
        """
        w = width_mm
        t = copper_thickness_mm
        h = max(height_mm, 1e-6)
        er = max(dielectric_er, 1.0)

        # IPC-2141 surface microstrip formula
        denom = (0.8 * w) + t
        if denom <= 0:
            return 50.0
        ratio = (5.98 * h) / denom
        if ratio <= 1.0:
            ratio = 1.001
        z0 = (87.0 / math.sqrt(er + 1.41)) * math.log(ratio)
        return float(z0)

    @staticmethod
    def calculate_differential_microstrip_impedance(
        width_mm: float,
        spacing_mm: float,
        copper_thickness_mm: float,
        height_mm: float,
        dielectric_er: float,
    ) -> float:
        """Calculate edge-coupled surface differential microstrip impedance Z_diff.

        Args:
            width_mm: Trace width W in millimeters.
            spacing_mm: Trace edge-to-edge separation S in millimeters.
            copper_thickness_mm: Copper thickness T in millimeters.
            height_mm: Dielectric height H above reference plane.
            dielectric_er: Relative permittivity epsilon_r.

        Returns:
            Differential characteristic impedance Z_diff in Ohms.
        """
        z0 = StackupModel.calculate_microstrip_impedance(width_mm, copper_thickness_mm, height_mm, dielectric_er)
        s = spacing_mm
        h = max(height_mm, 1e-6)
        coupling_factor = 1.0 - (0.48 * math.exp(-0.96 * (s / h)))
        z_diff = 2.0 * z0 * max(coupling_factor, 0.40)
        return float(z_diff)

    @staticmethod
    def calculate_stripline_impedance(
        width_mm: float,
        copper_thickness_mm: float,
        height_total_mm: float,
        dielectric_er: float,
    ) -> float:
        """Calculate single-ended symmetrical stripline characteristic impedance Z0.

        Args:
            width_mm: Trace width W in millimeters.
            copper_thickness_mm: Copper thickness T in millimeters.
            height_total_mm: Total dielectric ground-to-ground spacing B in millimeters.
            dielectric_er: Relative permittivity epsilon_r.

        Returns:
            Characteristic impedance Z0 in Ohms.
        """
        w = width_mm
        t = copper_thickness_mm
        b = max(height_total_mm, 1e-6)
        er = max(dielectric_er, 1.0)

        eff_width = 0.67 * math.pi * (0.8 * w + t)
        if eff_width <= 0:
            eff_width = 1e-4
        ratio = (4.0 * b) / eff_width
        if ratio <= 1.0:
            ratio = 1.001
        z0 = (60.0 / math.sqrt(er)) * math.log(ratio)
        return float(z0)

    @staticmethod
    def calculate_differential_stripline_impedance(
        width_mm: float,
        spacing_mm: float,
        copper_thickness_mm: float,
        height_total_mm: float,
        dielectric_er: float,
    ) -> float:
        """Calculate edge-coupled differential stripline impedance Z_diff.

        Args:
            width_mm: Trace width W in millimeters.
            spacing_mm: Trace edge-to-edge separation S in millimeters.
            copper_thickness_mm: Copper thickness T in millimeters.
            height_total_mm: Total dielectric ground-to-ground spacing B in millimeters.
            dielectric_er: Relative permittivity epsilon_r.

        Returns:
            Differential stripline characteristic impedance Z_diff in Ohms.
        """
        z0 = StackupModel.calculate_stripline_impedance(width_mm, copper_thickness_mm, height_total_mm, dielectric_er)
        s = spacing_mm
        b = max(height_total_mm, 1e-6)
        coupling_factor = 1.0 - (0.374 * math.exp(-2.9 * (s / b)))
        z_diff = 2.0 * z0 * max(coupling_factor, 0.40)
        return float(z_diff)

    @staticmethod
    def _ellip_ratio(k: float) -> float:
        """Compute ratio of complete elliptic integrals K(k)/K'(k) via Hilberg's formula."""
        k = max(min(k, 0.999999), 1e-6)
        k_prime = math.sqrt(1.0 - (k * k))
        if 0.0 <= k <= (1.0 / math.sqrt(2.0)):
            return math.pi / math.log(2.0 * (1.0 + math.sqrt(k_prime)) / (1.0 - math.sqrt(k_prime)))
        else:
            return (1.0 / math.pi) * math.log(2.0 * (1.0 + math.sqrt(k)) / (1.0 - math.sqrt(k)))

    @staticmethod
    def calculate_coplanar_waveguide_impedance(
        width_mm: float,
        gap_mm: Optional[float] = None,
        copper_thickness_mm: float = 0.035,
        height_mm: float = 0.100,
        dielectric_er: float = 4.2,
        ground_gap_mm: Optional[float] = None,
    ) -> float:
        """Calculate characteristic impedance Z0 of a Coplanar Waveguide with Ground (CPWG).

        Args:
            width_mm: Center conductor track width W in mm.
            gap_mm: Gap S to coplanar ground plane in mm.
            copper_thickness_mm: Foil thickness T in mm.
            height_mm: Substrate dielectric height H to bottom ground reference plane in mm.
            dielectric_er: Relative dielectric permittivity epsilon_r.
            ground_gap_mm: Optional alias for gap_mm.

        Returns:
            Characteristic impedance Z0 in Ohms.
        """
        effective_gap = ground_gap_mm if gap_mm is None else gap_mm
        if effective_gap is None:
            effective_gap = 0.20
        w = max(width_mm, 1e-4)
        s = max(effective_gap, 1e-4)
        h = max(height_mm, 1e-4)
        er = max(dielectric_er, 1.0)

        # Conductor thickness correction
        t = copper_thickness_mm
        if t > 0:
            delta_w = (1.25 * t / math.pi) * (1.0 + math.log(max(4.0 * math.pi * w / t, 1e-3)))
            w = w + delta_w
            s = max(s - delta_w, 1e-4)

        k0 = w / (w + 2.0 * s)
        ratio0 = StackupModel._ellip_ratio(k0)

        k1 = math.tanh(math.pi * w / (4.0 * h)) / math.tanh(math.pi * (w + 2.0 * s) / (4.0 * h))
        ratio1 = StackupModel._ellip_ratio(k1)

        eps_eff = (1.0 + er * (ratio1 / ratio0)) / (1.0 + (ratio1 / ratio0))
        z0 = (60.0 * math.pi / math.sqrt(eps_eff)) / (ratio0 + ratio1)
        return float(z0)


class DifferentialPairModel(BaseModel):
    """Data model representing a high-speed differential net pair (e.g. PCIe, USB, LVDS)."""

    name: str = Field(description="Differential pair name (e.g. PCIE_TX0)")
    pos_net: str = Field(description="Positive signal net identifier (e.g. PCIE_TX0_P)")
    neg_net: str = Field(description="Negative signal net identifier (e.g. PCIE_TX0_N)")
    target_impedance_ohms: float = Field(
        default=85.0, description="Target differential impedance (e.g. 85 Ohms for PCIe, 90 for USB, 100 for Ethernet)"
    )
    impedance_tolerance_percent: float = Field(default=10.0, description="Allowable impedance variance percentage")
    max_intra_pair_skew_mm: float = Field(
        default=0.15, description="Maximum allowable intra-pair trace length mismatch (approx 1ps delay)"
    )
    max_inter_pair_skew_mm: float = Field(
        default=1.0, description="Maximum allowable inter-pair / lane-to-lane length mismatch"
    )
    max_via_count: int = Field(default=2, description="Maximum allowed layer transition vias per differential pair")


class NetClassModel(BaseModel):
    """Data model representing electrical constraints, design rules, and routing attributes for a group of nets."""

    name: str = Field(description="Net class name (e.g. PCIE_GEN3, POWER_3V3, SENSOR_I2C)")
    interface_type: str = Field(
        default="generic",
        description="Electrical interface type: 'pcie', 'display', 'rf', 'usb', 'ethernet', 'generic'",
    )
    clearance_mm: float = Field(default=0.127, gt=0.0, description="Minimum copper-to-copper clearance in millimeters")
    trace_width_mm: float = Field(default=0.127, gt=0.0, description="Default trace conductor width in millimeters")
    via_dia_mm: float = Field(default=0.45, gt=0.0, description="Default via pad outer diameter in millimeters")
    via_drill_mm: float = Field(default=0.20, gt=0.0, description="Default via drill hole diameter in millimeters")
    diff_pairs: List[DifferentialPairModel] = Field(
        default_factory=list, description="High-speed differential pairs associated with this net class"
    )
    single_nets: List[str] = Field(default_factory=list, description="Single-ended signals belonging to this net class")
    coplanar_waveguide: bool = Field(
        default=False,
        description="Whether traces use Coplanar Waveguide with Ground (CPWG) for RF routing",
    )
    ground_gap_mm: Optional[float] = Field(
        default=None, description="Gap to adjacent coplanar ground plane for CPWG traces"
    )
    keepout_clearance_mm: Optional[float] = Field(
        default=None, description="Keep-out exclusion clearance around RF antenna traces"
    )
    require_ground_stitch_via: bool = Field(
        default=True, description="Enforce GND return stitching via within proximity when transitioning signal layers"
    )
    max_stitch_via_distance_mm: float = Field(
        default=1.0, description="Maximum distance in mm allowed between high-speed signal via and GND stitch via"
    )
    disallow_split_plane_crossings: bool = Field(
        default=True, description="Disallow traces from crossing splits in their adjacent reference ground/power plane"
    )


class BgaFanoutModel(BaseModel):
    """Configuration for Ball Grid Array (BGA) package breakout routing."""

    strategy: str = Field(
        default="dogbone_vippo",
        description="Escape fanout strategy: 'dogbone' (outer), 'vippo' (via-in-pad), or 'microvia' (HDI)",
    )
    pitch_mm: float = Field(gt=0.0, description="Ball pitch spacing in millimeters (e.g. 0.4, 0.5, 0.65, 0.8)")
    ball_dia_mm: float = Field(gt=0.0, description="Solder ball sphere diameter in millimeters")
    pad_dia_mm: float = Field(gt=0.0, description="Copper land pad diameter in millimeters")
    via_drill_mm: float = Field(default=0.20, gt=0.0, description="Breakout via drill diameter")
    via_pad_mm: float = Field(default=0.40, gt=0.0, description="Breakout via outer copper pad diameter")
    neck_down_width_mm: float = Field(
        default=0.09, gt=0.0, description="Trace width reduction used strictly inside BGA ball matrix"
    )
    escape_layers: List[str] = Field(
        default_factory=lambda: ["F.Cu", "In1.Cu", "In2.Cu"],
        description="Stackup layers allocated for escaping internal BGA rings",
    )


class FlexZoneModel(BaseModel):
    """Configuration for flexible PCB sub-regions, bend lines, and stiffeners."""

    name: str = Field(description="Identifier for the flex region (e.g. sensor_tail, hinge_flex)")
    bounds: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = Field(
        default=None,
        description="2D rectangular envelope ((x_min, y_min), (x_max, y_max)) defining the flex boundary",
    )
    shape_ref: Optional[str] = Field(
        default=None,
        description="Reference to build123d CAD shape defining flex zone boundary in manifest",
    )
    base_substrate: str = Field(default="polyimide", description="Flex core dielectric substrate")
    substrate_thickness_mm: float = Field(default=0.025, gt=0.0, description="Polyimide dielectric core thickness")
    coverlay_thickness_mm: float = Field(default=0.025, gt=0.0, description="Protective coverlay film thickness")
    min_bend_radius_mm: float = Field(
        default=2.5, gt=0.0, description="Minimum allowable bend radius under dynamic/static flexing"
    )
    stiffener_material: Optional[str] = Field(
        default=None, description="Optional stiffener material (e.g. FR4, polyimide, aluminum, stainless_steel)"
    )
    stiffener_thickness_mm: Optional[float] = Field(
        default=None, description="Thickness of reinforcement stiffener under connectors or components"
    )


class CapacitiveElectrodeModel(BaseModel):
    """Configuration for capacitive touch and liquid-level sensing electrodes on flexible or rigid substrates."""

    name: str = Field(description="Sensor electrode net or identifier (e.g. SENSE_LEVEL_LOW, TOUCH_PAD_1)")
    electrode_type: str = Field(default="mutual", description="Capacitive sensing principle: 'self' or 'mutual'")
    shape: str = Field(default="interdigital", description="Electrode geometry: 'interdigital', 'pad', or 'slider'")
    area_mm: Tuple[float, float] = Field(description="Dimensions (width, length) of the sensor active electrode")
    pitch_mm: float = Field(default=1.0, gt=0.0, description="Interdigital comb finger pitch spacing in millimeters")
    gap_mm: float = Field(default=0.3, gt=0.0, description="Interdigital comb gap between TX and RX fingers")
    drive_shield: bool = Field(
        default=True, description="Surround sensing electrode with an actively driven shield to prevent false triggers"
    )
    hatch_ground_pour: bool = Field(
        default=True,
        description="Use cross-hatched copper ground fill beneath electrodes to minimize parasitic loading",
    )
    hatch_line_width_mm: float = Field(default=0.15, gt=0.0, description="Hatch grid copper conductor line width")
    hatch_pitch_mm: float = Field(default=0.50, gt=0.0, description="Hatch grid spacing (~30% copper fill factor)")
    hatch_angle_deg: float = Field(default=45.0, description="Hatch mesh orientation angle in degrees")
    tx_pin: Optional[str] = Field(
        default=None, description="Transmitter pin name or GPIO channel for mutual capacitance"
    )
    rx_pin: Optional[str] = Field(default=None, description="Receiver pin name or analog channel")
    threshold_raw: Optional[int] = Field(
        default=None, description="Raw touch/liquid trigger threshold for microcontroller firmware"
    )
    channel_id: Optional[int] = Field(default=None, description="Hardware capacitive controller channel index (0..15)")


class PCBConfig(BaseModel):
    """Top-level configuration model defining complete physical board, stackup, and high-speed rules."""

    name: str = Field(description="PCB project or sub-assembly name")
    board_type: str = Field(default="rigid-flex", description="Substrate type: 'rigid', 'flex', or 'rigid-flex'")
    dimensions_mm: Tuple[float, float, float] = Field(
        description="Physical board bounding envelope (width, length, overall_thickness)"
    )
    shape_ref: Optional[str] = Field(
        default=None,
        description="Name of build123d shape or part in manifest defining board outline",
    )
    stackup: StackupModel = Field(description="Multi-layer physical stackup definition")
    net_classes: List[NetClassModel] = Field(
        default_factory=list, description="High-speed and standard electrical net classes"
    )
    flex_zones: List[FlexZoneModel] = Field(
        default_factory=list, description="Defined flexible PCB regions and bend parameters"
    )
    capacitive_sensors: List[CapacitiveElectrodeModel] = Field(
        default_factory=list, description="Capacitive sensing electrodes and ground shield definitions"
    )
