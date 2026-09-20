"""Data models for multi-layer printed circuit boards, high-speed constraints, and flex stackups."""

import math
from enum import StrEnum
from pathlib import Path
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


class BoardType(StrEnum):
    """Substrate construction categorization for printed circuit boards."""

    RIGID = "rigid"
    FLEX = "flex"
    RIGID_FLEX = "rigid-flex"


class FlexType(StrEnum):
    """Classification of flexible PCB subassembly application types."""

    CONNECTOR = "connector"
    COMPONENT = "component"
    CAPACITIVE = "capacitive"


class StackupLayerModel(BaseModel):
    """Data model representing an individual layer in a multi-layer stackup."""

    name: str = Field(description="Layer identifier (e.g. F.Cu, In1.Cu, Prepreg1, B.Cu)")
    layer_type: Optional[LayerType] = Field(default=None, description="Layer functional type")
    thickness_mm: float = Field(gt=0.0, description="Layer thickness in millimeters")
    material: str = Field(default="copper", description="Layer material (e.g. copper, FR4, polyimide)")
    dielectric_constant: Optional[float] = Field(
        default=None, gt=0.0, description="Relative dielectric permittivity (epsilon_r) for dielectric layers"
    )
    loss_tangent: Optional[float] = Field(
        default=None, ge=0.0, description="Dielectric loss tangent (tan delta) for high-speed signal integrity"
    )

    @model_validator(mode="after")
    def validate_dielectric_properties(self) -> "StackupLayerModel":
        """Validate that layer thickness is strictly positive and dielectric permittivity is valid."""
        if self.thickness_mm <= 0.0:
            raise ValueError(
                f"Stackup layer '{self.name}' thickness must be strictly positive (> 0), got {self.thickness_mm} mm."
            )
        if self.layer_type in (LayerType.DIELECTRIC, LayerType.COVERLAY) and self.dielectric_constant is not None:
            if self.dielectric_constant <= 0.0:
                raise ValueError(
                    f"Dielectric layer '{self.name}' relative permittivity must be positive (> 0), got {self.dielectric_constant}."
                )
        if self.loss_tangent is not None and self.loss_tangent < 0.0:
            raise ValueError(f"Layer '{self.name}' loss tangent must be non-negative (>= 0), got {self.loss_tangent}.")
        return self


class PCBMaterialModel(BaseModel):
    """Physical and electrical specifications for a PCB substrate, foil, or finish material."""

    layer_type: Optional[LayerType] = Field(default=None, description="Default stackup layer type for this material.")
    density: float = Field(default=1.85, gt=0.0, description="Material density in g/cm³.")
    boundary_friction: float = Field(default=0.25, ge=0.0, description="Boundary friction coefficient.")
    contact_angle: float = Field(default=70.0, ge=0.0, le=180.0, description="Contact angle in degrees.")
    roughness: float = Field(default=0.30, ge=0.0, le=1.0, description="Surface roughness factor.")
    ior: float = Field(default=1.54, gt=0.0, description="Index of refraction.")
    transmission: float = Field(default=0.0, ge=0.0, le=1.0, description="Optical transmission weight.")
    metallic: float = Field(default=0.0, ge=0.0, le=1.0, description="Metallic reflection weight.")
    specular: float = Field(default=0.50, ge=0.0, le=1.0, description="Specular reflection factor.")
    dielectric_constant: Optional[float] = Field(
        default=None, gt=0.0, description="Relative dielectric permittivity (epsilon_r) for substrates and insulators."
    )
    loss_tangent: Optional[float] = Field(
        default=None, ge=0.0, description="Dielectric loss tangent (tan delta) for high-frequency attenuation."
    )
    breakdown_voltage_v_per_mm: Optional[float] = Field(
        default=None, gt=0.0, description="Dielectric breakdown voltage in V/mm."
    )
    sheet_resistance_mohm_sq: Optional[float] = Field(
        default=None, gt=0.0, description="Conductor sheet resistance in mOhm/sq."
    )
    conductivity_ms_m: Optional[float] = Field(
        default=None, gt=0.0, description="Electrical conductivity in MS/m (MegaSiemens/meter)."
    )


class PCBMaterialsModel(BaseModel):
    """Collection of PCB material specifications indexed by material identifier."""

    material: dict[str, PCBMaterialModel] = Field(
        default_factory=dict, description="Dictionary of PCB material models keyed by material name."
    )

    def get(self, name: Optional[str], default: Optional[PCBMaterialModel] = None) -> Optional[PCBMaterialModel]:
        """Resolve a PCB material model by name with case-insensitive normalization."""
        if not name:
            return default
        clean_key = str(name).lower().replace("_", "").replace("-", "")
        for k, v in self.material.items():
            if k.lower().replace("_", "").replace("-", "") == clean_key:
                return v
        return default

    def __getitem__(self, key: str) -> PCBMaterialModel:
        """Access PCB material model by key with normalization."""
        res = self.get(key)
        if res is None:
            raise KeyError(f"PCB material '{key}' not found in PCBMaterialsModel.")
        return res

    @classmethod
    def from_yaml(cls, yaml_path: Path | str) -> "PCBMaterialsModel":
        """Load PCB materials from a YAML file."""
        from provider.utils import load_manifest

        data = load_manifest(str(yaml_path))
        mat_dict = data.get("material", data)
        materials = {
            k: PCBMaterialModel.model_validate(v) if isinstance(v, dict) else v
            for k, v in mat_dict.items()
            if isinstance(v, (dict, PCBMaterialModel))
        }
        return cls(material=materials)

    @classmethod
    def default(cls) -> "PCBMaterialsModel":
        """Load default PCB materials from standard pcb_materials.yaml."""
        materials_path = Path(__file__).parent.parent / "projects" / "pcb_materials.yaml"
        if materials_path.exists():
            return cls.from_yaml(materials_path)
        return cls()


class StackupModel(BaseModel):
    """Data model representing a 4 to 8+ layer physical substrate stackup with impedance solvers."""

    layers: List[StackupLayerModel] = Field(description="Sequential list of layers from top to bottom")
    finish: str = Field(default="ENIG", description="Surface finish (e.g. ENIG, HASL, OSP, Immersion Silver)")
    soldermask_color: str = Field(default="green", description="Solder mask color")
    silkscreen_color: str = Field(default="white", description="Silkscreen legend color")

    @model_validator(mode="after")
    def validate_layer_symmetry_and_count(self) -> "StackupModel":
        """Validate that stackup contains valid conductive layers (4, 6, 8, etc.) and dielectrics."""
        self.resolve_materials()
        copper_layers = [
            l for l in self.layers if l.layer_type in (LayerType.SIGNAL, LayerType.GROUND, LayerType.POWER)
        ]
        count = len(copper_layers)
        if count < 2:
            raise ValueError(f"PCB stackup must contain at least 2 conductive copper layers, found {count}")
        if count % 2 != 0:
            raise ValueError(f"Multi-layer PCB stackups must have an even copper layer count, found {count}")
        return self

    def resolve_materials(self, materials: Optional[PCBMaterialsModel] = None) -> "StackupModel":
        """Resolve layer types, dielectric constants, and loss tangents from materials catalog."""
        if materials is None:
            materials = PCBMaterialsModel.default()
        for layer in self.layers:
            mat = materials.get(layer.material)
            if layer.layer_type is None:
                if mat and mat.layer_type is not None:
                    layer.layer_type = mat.layer_type
                else:
                    lower = layer.name.lower()
                    if "gnd" in lower:
                        layer.layer_type = LayerType.GROUND
                    elif "pwr" in lower:
                        layer.layer_type = LayerType.POWER
                    elif ".cu" in lower:
                        layer.layer_type = LayerType.SIGNAL
                    else:
                        layer.layer_type = LayerType.DIELECTRIC

            if layer.dielectric_constant is None and mat and mat.dielectric_constant is not None:
                layer.dielectric_constant = mat.dielectric_constant

            if layer.loss_tangent is None and mat and mat.loss_tangent is not None:
                layer.loss_tangent = mat.loss_tangent
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
    center_mm: Optional[Tuple[float, float]] = Field(
        default=None, description="Center coordinate (x, y) relative to the substrate center"
    )
    shape_ref: Optional[str] = Field(
        default=None, description="Subassembly or shape reference for this electrode (e.g. 'flex_tail')"
    )


class AssemblyTestStepModel(BaseModel):
    """Factory assembly testing step for automated test fixtures (bed-of-nails, flying probe)."""

    step_id: str = Field(description="Unique test step identifier (e.g. TEST_IMP_DIFF_100)")
    description: str = Field(description="Test procedure description")
    test_type: str = Field(description="Type of test: continuity, isolation, impedance, capacitance, voltage")
    net_or_points: List[str] = Field(description="Nets, component pins, or test coupon pads under test")
    expected_nominal: Optional[float] = Field(default=None, description="Nominal expected value")
    tolerance_pct: Optional[float] = Field(
        default=None, ge=0.0, description="Acceptable percentage tolerance (e.g. 10.0 for +/-10%)"
    )
    unit: str = Field(default="", description="Measurement unit (e.g. ohm, pF, V, mA)")
    stimulus: Optional[str] = Field(default=None, description="Optional stimulus signal (e.g. 100kHz 1V RMS)")


class AssemblyTestModel(BaseModel):
    """Factory assembly test plan containing ordered verification instructions."""

    instructions: List[AssemblyTestStepModel] = Field(
        default_factory=list, description="Ordered sequence of factory assembly test steps"
    )
    test_fixture: str = Field(
        default="bed_of_nails", description="Target test fixture: bed_of_nails, flying_probe, manual"
    )
    pass_criteria: str = Field(
        default="all_steps_within_tolerance", description="Overall pass criteria for assembly QC"
    )


class SheetSize(StrEnum):
    """Standard drawing sheet format for KiCad PCB and schematic layouts."""

    A4 = "A4"
    A3 = "A3"
    A2 = "A2"
    A1 = "A1"
    A0 = "A0"
    LETTER = "Letter"
    LEGAL = "Legal"
    USER = "User"


class SilkscreenTextModel(BaseModel):
    """Declarative silkscreen text label placed on PCB copper outer layers."""

    text: str = Field(description="Content string printed on silkscreen")
    layer: str = Field(default="F.SilkS", description="Target layer ('F.SilkS' for top, 'B.SilkS' for bottom)")
    position: Tuple[float, float] = Field(
        default=(0.0, 0.0), description="Coordinates (x, y) in mm on board relative to board center"
    )
    font_size: float = Field(default=1.0, gt=0.0, description="Font height and width in mm")
    thickness: float = Field(default=0.15, gt=0.0, description="Stroke thickness in mm")
    rotation: float = Field(default=0.0, description="Text rotation angle in degrees")
    mirror: bool = Field(default=False, description="Whether text is mirrored (default True for B.SilkS)")


class SchematicLayoutModel(BaseModel):
    """Layout grid and dimension parameters for schematic diagram sheets."""

    col_width: float = Field(default=60.0, description="Nominal column width in mm for multi-column layout")
    col_gap: float = Field(default=15.0, description="Gap between columns in mm")
    sheet_center_x: float = Field(default=148.5, description="Drawing sheet center X coordinate in mm")
    sheet_center_y: float = Field(default=105.0, description="Drawing sheet center Y coordinate in mm")
    row_step_y: float = Field(default=55.0, description="Vertical pitch step between symbol rows in mm")
    default_symbol_width: float = Field(default=45.0, description="Default symbol width in mm for DRC overlap checks")
    default_symbol_height: float = Field(default=35.0, description="Default symbol height in mm for DRC overlap checks")


class SchematicSheetModel(BaseModel):
    """Configuration for an individual functional schematic drawing sheet."""

    title: str = Field(description="Sheet title in engineering title block")
    description: str = Field(default="", description="Functional description of circuitry")
    components: List[str] = Field(
        default_factory=list, description="List of component reference designators on this sheet"
    )
    pin_breakouts: dict[str, List[str]] = Field(
        default_factory=dict, description="Component -> subset of pin names to display on this sheet"
    )
    layout: SchematicLayoutModel = Field(
        default_factory=SchematicLayoutModel, description="Layout grid and dimension parameters for this sheet"
    )


class TraceSegmentModel(BaseModel):
    """Linear copper trace segment routing a net on a specific layer."""

    start_mm: Tuple[float, float] = Field(description="Start coordinate (x, y) in mm relative to board center")
    end_mm: Tuple[float, float] = Field(description="End coordinate (x, y) in mm relative to board center")
    width_mm: float = Field(gt=0.0, description="Trace conductor width in mm")
    layer: str = Field(default="F.Cu", description="Copper layer name (e.g. F.Cu, In1.Cu, B.Cu)")
    net: str = Field(description="Electrical net name connected by this trace segment")


class ViaModel(BaseModel):
    """Through-hole or microvia connecting traces between copper layers."""

    position_mm: Tuple[float, float] = Field(description="Via center coordinate (x, y) in mm relative to board center")
    drill_diameter_mm: float = Field(default=0.20, gt=0.0, description="Via hole drill diameter in mm")
    pad_diameter_mm: float = Field(default=0.45, gt=0.0, description="Via annular copper pad outer diameter in mm")
    layer_start: str = Field(default="F.Cu", description="Starting copper layer name")
    layer_end: str = Field(default="B.Cu", description="Ending copper layer name")
    net: str = Field(description="Electrical net name for this via")


class CopperRegionModel(BaseModel):
    """Filled polygonal copper pour, plane, or shield zone."""

    net: str = Field(default="GND", description="Net name to which the copper region connects (typically GND)")
    layer: str = Field(default="In1.Cu", description="Copper layer on which the plane is poured")
    polygon_points_mm: List[Tuple[float, float]] = Field(
        description="Boundary vertices (x, y) in mm relative to board center"
    )
    clearance_mm: float = Field(default=0.20, ge=0.0, description="Clearance from copper region to foreign traces/pads")
    priority: int = Field(default=1, ge=0, description="Filling priority (higher numbers fill first)")


class TestPointModel(BaseModel):
    """Exposed copper test point pad or through-hole probe point for probing and validation."""

    name: str = Field(description="Test point identifier (e.g. TP_SDA, TP_TX0_P)")
    net: str = Field(description="Electrical net name monitored by this test point")
    position_mm: Tuple[float, float] = Field(description="Test point coordinate (x, y) in mm relative to board center")
    pad_diameter_mm: float = Field(default=1.40, gt=0.0, description="Exposed copper annular pad diameter in mm")
    drill_diameter_mm: float = Field(
        default=0.80, gt=0.0, description="Drilled plated hole diameter in mm for probe / fly wire insertion"
    )
    plated: bool = Field(default=True, description="Whether test point drill hole is through-hole plated")
    layer: str = Field(default="F.Cu", description="Copper layer for test point pad ('F.Cu' or 'B.Cu')")
    label: Optional[str] = Field(default=None, description="Optional silkscreen label annotation")


class MountingHoleModel(BaseModel):
    """Physical mounting or tooling drill hole on PCB."""

    name: str = Field(description="Hole identifier (e.g. MH1, MH2)")
    position_mm: Tuple[float, float] = Field(description="Coordinates (x, y) in mm relative to board center")
    drill_diameter_mm: float = Field(gt=0.0, description="Finished hole drill diameter in mm")
    pad_diameter_mm: Optional[float] = Field(default=None, description="Copper annular ring diameter for plated holes")
    plated: bool = Field(default=False, description="Whether hole is plated through")
    net: Optional[str] = Field(default=None, description="Net name if plated (typically GND)")


class PCBConfig(BaseModel):
    """Top-level configuration model defining complete physical board, stackup, and high-speed rules."""

    name: str = Field(description="PCB project or sub-assembly name")
    board_type: BoardType = Field(
        default=BoardType.RIGID_FLEX, description="Substrate type: 'rigid', 'flex', or 'rigid-flex'"
    )
    flex_type: Optional[FlexType] = Field(
        default=None, description="Flexible PCB application type ('connector', 'component', 'capacitive')"
    )
    revision: str = Field(default="1.0", description="Board revision identifier (e.g. '1.0', 'A', 'rev2')")
    dimensions_mm: Optional[Tuple[float, float, float]] = Field(
        default=None,
        description="Physical board bounding envelope (width, length, overall_thickness), dynamically calculated from CAD shape and stackup if omitted",
    )
    shape_ref: Optional[str] = Field(
        default=None,
        description="Name of build123d shape or part in manifest defining board outline",
    )
    stackup: Optional[StackupModel] = Field(default=None, description="Multi-layer physical stackup definition")
    sheet_size: SheetSize = Field(
        default=SheetSize.A4,
        description="Standard drawing sheet format for PCB and schematic exports ('A4', 'A3', etc.)",
    )
    silkscreen_texts: List[SilkscreenTextModel] = Field(
        default_factory=list,
        description="Top and bottom silkscreen text markings and annotations",
    )
    net_classes: List[NetClassModel] = Field(
        default_factory=list, description="High-speed and standard electrical net classes"
    )
    flex_zones: List[FlexZoneModel] = Field(
        default_factory=list, description="Defined flexible PCB regions and bend parameters"
    )
    capacitive_sensors: List[CapacitiveElectrodeModel] = Field(
        default_factory=list, description="Capacitive sensing electrodes and ground shield definitions"
    )
    assembly_test: Optional[AssemblyTestModel] = Field(
        default=None, description="Factory assembly test instructions and tolerances"
    )
    schematic_sheets: List[SchematicSheetModel] = Field(
        default_factory=list,
        description="Defined schematic sheets for multi-page functional signal breakout",
    )
    schematic_layout: SchematicLayoutModel = Field(
        default_factory=SchematicLayoutModel,
        description="Default grid layout and dimension parameters for schematic sheets",
    )
    mounting_holes: List[MountingHoleModel] = Field(
        default_factory=list,
        description="Drill and mounting holes for carrier assembly",
    )
    traces: List[TraceSegmentModel] = Field(
        default_factory=list, description="Copper traces routing electrical nets across layers"
    )
    vias: List[ViaModel] = Field(default_factory=list, description="Through-hole and blind/buried interlayer vias")
    copper_regions: List[CopperRegionModel] = Field(
        default_factory=list, description="Filled copper pours, planes, and shielding zones"
    )
    test_points: List[TestPointModel] = Field(default_factory=list, description="Exposed test point probing pads")

    @property
    def sheet_dimensions_mm(self) -> Tuple[float, float]:
        """Drawing sheet dimensions (width_mm, height_mm)."""
        dims = {
            SheetSize.A4: (297.0, 210.0),
            SheetSize.A3: (420.0, 297.0),
            SheetSize.A2: (594.0, 420.0),
            SheetSize.A1: (841.0, 594.0),
            SheetSize.A0: (1189.0, 841.0),
            SheetSize.LETTER: (279.4, 215.9),
            SheetSize.LEGAL: (355.6, 215.9),
            SheetSize.USER: (297.0, 210.0),
        }
        return dims.get(self.sheet_size, (297.0, 210.0))

    @property
    def sheet_width_mm(self) -> float:
        """Drawing sheet width in mm."""
        return self.sheet_dimensions_mm[0]

    @property
    def sheet_height_mm(self) -> float:
        """Drawing sheet height in mm."""
        return self.sheet_dimensions_mm[1]

    @property
    def sheet_center_x_mm(self) -> float:
        """X coordinate of sheet center in mm."""
        return self.sheet_width_mm / 2.0

    @property
    def sheet_center_y_mm(self) -> float:
        """Y coordinate of sheet center in mm."""
        return self.sheet_height_mm / 2.0
