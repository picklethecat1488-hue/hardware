"""Data models and container class for component wiring, footprints, and net connections."""

import math
import yaml
from enum import StrEnum
from pathlib import Path
from typing import Tuple, List, Optional, Callable, Any, Dict
from functools import cached_property
from pydantic import BaseModel, Field, validate_call, field_validator
from build123d import Vector, Location
from model.pcb import BgaFanoutModel

# Footprint Layout Registry
PIN_LAYOUT_REGISTRY = {}


@validate_call
def register_layout(package_name: str, namespace: Optional[str] = None, surface_mount: bool = False):
    """Register a footprint pin layout function as a decorator.

    Raises ValueError if a layout for the key is already registered.
    """

    def decorator(func):
        inferred_namespace = namespace
        if not inferred_namespace:
            module_parts = func.__module__.split(".")
            if len(module_parts) > 1 and module_parts[0] == "projects":
                inferred_namespace = module_parts[1]

        key = f"{inferred_namespace}:{package_name}" if inferred_namespace else package_name
        if key in PIN_LAYOUT_REGISTRY:
            raise ValueError(f"Layout for '{key}' is already registered by '{PIN_LAYOUT_REGISTRY[key].__name__}'")
        func.surface_mount = surface_mount
        PIN_LAYOUT_REGISTRY[key] = func
        return func

    return decorator


class PinSide(StrEnum):
    """Placement side for a pin label."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class PinModel(BaseModel):
    """Data model representing a connection pin on a footprint."""

    name: str = Field(description="Name of the pin (e.g. GND, GP2)")
    number: Optional[str] = Field(default=None, description="Physical pin number on the package")
    pin_name: Optional[str] = Field(default=None, description="Functional pin name or signal designation")
    signal_name: Optional[str] = Field(
        default=None, description="Expected electrical signal name connected to this pin"
    )
    position: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D offset relative to component center (x, y, z)"
    )
    label: str = Field(description="Display label text for the pin")
    side: PinSide = Field(description="Placement side for the pin label (left, right, top, bottom)")
    slot: Optional[int] = Field(default=None, description="Optional slot index for DIP spacing")
    pad_type: str = Field(default="smd", description="Pad type: smd or thru_hole")
    pad_shape: str = Field(default="circle", description="Pad shape: circle, rect, oval, roundrect")
    pad_size_mm: Tuple[float, float] = Field(default=(0.5, 0.5), description="Pad dimensions (width, height)")
    drill_dia_mm: Optional[float] = Field(default=None, description="Drill hole diameter in mm for thru_hole pads")


class LabelModel(BaseModel):
    """Data model representing textual label arguments and alignment."""

    text: str = Field(description="The display text for the label")
    position: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D position offset relative to component center"
    )
    align: Tuple[str, str] = Field(
        default=("center", "center"), description="Horizontal and vertical text alignment (e.g. ['center', 'max'])"
    )


class TruthTableState(StrEnum):
    """Classification of discrete component network truth table states."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    INVALID = "INVALID"


class TruthTableRowModel(BaseModel):
    """Row in a component truth table capturing inputs, outputs, state, and functional mode."""

    inputs: Dict[str, str] = Field(description="Input pin or signal logic levels (e.g. {'PWR_EN': 'HIGH'})")
    outputs: Dict[str, str] = Field(description="Output pin or signal logic levels (e.g. {'VLOAD_SW': 'LOW (0V)'})")
    state: TruthTableState = Field(description="State classification: TRUE, FALSE, or INVALID")
    description: str = Field(description="Functional operational mode or circuit note")

    @field_validator("state", mode="before")
    @classmethod
    def parse_state(cls, v: Any) -> TruthTableState:
        """Coerce strings to TruthTableState enum values."""
        if isinstance(v, TruthTableState):
            return v
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in TruthTableState.__members__:
                return TruthTableState[v_upper]
        return v


class TruthTableModel(BaseModel):
    """Truth table representing true, false, and invalid states for discrete component networks."""

    title: str = Field(default="Truth Table", description="Table title or circuit functional name")
    input_headers: List[str] = Field(default_factory=list, description="Column headers for input signals")
    output_headers: List[str] = Field(default_factory=list, description="Column headers for output signals")
    rows: List[TruthTableRowModel] = Field(default_factory=list, description="Truth table rows")


class FootprintModel(BaseModel):
    """Data model representing a physical/electrical footprint package."""

    name: str = Field(description="Unique identifier for the component (e.g. charger, pico)")
    package: str = Field(description="Component shape/package type (e.g. board, ic, motor, led, tof_sensor)")
    namespace: Optional[str] = Field(default=None, description="Optional namespace prefix for the package")
    position: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D absolute center position (x, y, z)"
    )
    rotation: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="3D absolute rotation (pitch, roll, yaw)"
    )
    dimensions: Tuple[float, float, float] = Field(
        description="Component physical package dimensions (width, length, thickness)"
    )
    mounting_holes: Optional[Tuple[float, float]] = Field(
        default=None, description="Optional x/y spacing for mounting holes"
    )
    slots_per_side: Optional[int] = Field(default=None, description="Optional total number of DIP slots per side")
    label: Optional[LabelModel] = Field(default=None, description="Label settings for the footprint")
    value: Optional[str] = Field(default=None, description="Component electrical value (e.g. '100nF', '10k', '2.2uF')")
    pins: List[PinModel] = Field(default_factory=list, description="List of pins on the footprint")
    mpn: Optional[str] = Field(default=None, description="Manufacturer part number for BOM generation")
    supplier_pn: Optional[str] = Field(default=None, description="Supplier part number (e.g. LCSC, DigiKey)")
    bga_fanout: Optional[BgaFanoutModel] = Field(default=None, description="Optional BGA fanout configuration")
    layer: str = Field(default="F.Cu", description="PCB copper placement layer ('F.Cu' for top, 'B.Cu' for bottom)")
    truth_table: Optional[TruthTableModel] = Field(
        default=None, description="Optional truth table capturing true, false, and invalid states for discrete networks"
    )
    shape_ref: Optional[str] = Field(
        default=None,
        description="Optional subassembly or shape reference for this footprint (e.g. 'carrier_board', 'flex_tail')",
    )
    color: Optional[str] = Field(
        default=None,
        description="Optional display color for the component package in wiring diagrams",
    )
    unconnected: bool = Field(
        default=False,
        description="Whether this component footprint is intentionally unconnected to the electrical netlist",
    )
    dnp: bool = Field(
        default=False,
        description="Do Not Populate (DNP) flag - excludes component from manufacturing BOM",
    )


class NetModel(BaseModel):
    """Data model representing a wiring connection network."""

    name: str = Field(description="Name of the signal net (e.g. gnd, vcc_logic)")
    color: str = Field(description="Display color for the net wire path (e.g. black, red)")
    pins: List[Tuple[str, str]] = Field(description="List of connected pins as (component_name, pin_name) pairs")
    pin_names: Dict[Tuple[str, str], str] = Field(
        default_factory=dict,
        description="Optional mapping of (component_name, pin_number) to declared pin functional name",
    )
    offset: Tuple[float, float] = Field(default=(0.0, 0.0), description="2D offset for drawing parallel wire paths")
    path: List[Tuple[float, float, float]] = Field(
        default_factory=list, description="Explicit 3D intermediate routing points for the net wire path"
    )
    priority: Optional[int] = Field(
        default=None, description="Optional custom routing priority (lower integer routes earlier)"
    )


# Shared Footprint Library Cache
_SHARED_FOOTPRINTS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def load_shared_footprints(search_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load standard footprint definitions from shared yaml libraries (smd.yaml, thru_hole.yaml, ic.yaml)."""
    global _SHARED_FOOTPRINTS_CACHE
    if _SHARED_FOOTPRINTS_CACHE is not None and search_dir is None:
        return _SHARED_FOOTPRINTS_CACHE

    footprints: Dict[str, Dict[str, Any]] = {}
    base = search_dir or Path(__file__).parent.parent / "projects" / "footprints"
    if base.exists() and base.is_dir():
        for yml in sorted(base.glob("*.yaml")):
            with open(yml, "r") as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                fps = data.get("footprints", {})
                if isinstance(fps, dict):
                    footprints.update(fps)

    if search_dir is None:
        _SHARED_FOOTPRINTS_CACHE = footprints
    return footprints


class Wiring:
    """Class encapsulating wiring layout, component footprints, and net connections."""

    @validate_call
    def __init__(self, yaml_path: Path, parent_part: Optional[Any] = None):
        """Initialize the Wiring configuration container and load components/nets."""
        self.yaml_path = yaml_path
        self.parent_part = parent_part
        with open(yaml_path, "r") as f:
            self.config = yaml.safe_load(f) or {}

        # Resolve any explicit imports in wiring YAML
        self.shared_footprints = dict(load_shared_footprints())
        imports = self.config.get("imports", [])
        for imp in imports:
            imp_path = (self.yaml_path.parent / imp).resolve()
            if not imp_path.exists():
                imp_path = (self.yaml_path.parent.parent / imp).resolve()
            if imp_path.exists():
                with open(imp_path, "r") as f:
                    imp_data = yaml.safe_load(f)
                if imp_data and isinstance(imp_data, dict):
                    fps = imp_data.get("footprints", {})
                    if isinstance(fps, dict):
                        self.shared_footprints.update(fps)

    @cached_property
    def footprints(self) -> List[FootprintModel]:
        """Load and compute all component footprints with resolved positions and pin layouts."""
        components = []
        raw_items = self.config.get("components") or self.config.get("footprints") or []
        for c in raw_items:
            position = c.get("position", [0.0, 0.0, 0.0])
            rotation = c.get("rotation", [0.0, 0.0, 0.0])

            # Resolve joint reference dynamically if specified
            if c.get("joint_ref") is not None and self.parent_part is not None:
                joint_name = c["joint_ref"]["joint"]
                offset = c["joint_ref"].get("offset", [0.0, 0.0, 0.0])
                joint_loc = self.parent_part.joints[joint_name].location
                loc = joint_loc * Location(tuple(offset))
                position = [loc.position.X, loc.position.Y, loc.position.Z]

            pkg_str = c.get("package", "")
            shared_tmpl = self.shared_footprints.get(pkg_str, {})

            # Default dimensions from shared footprint template if not specified on component
            dims = c.get("dimensions") or shared_tmpl.get("dimensions", [5.0, 5.0, 1.0])
            w, l, thickness = dims

            pins = []
            comp_pins = c.get("pins")
            if comp_pins is not None and "pins" in shared_tmpl:
                # Merge per-component pin overrides with shared template
                tmpl_pins = shared_tmpl["pins"]
                overrides = {}
                for p in comp_pins:
                    if "number" in p:
                        overrides[str(p["number"])] = p
                    if "name" in p:
                        overrides[str(p["name"])] = p
                    if "label" in p:
                        overrides[str(p["label"])] = p
                raw_pins = []
                for tp in tmpl_pins:
                    merged = dict(tp)
                    p_key_name = str(tp.get("name", ""))
                    p_key_num = str(tp.get("number", ""))
                    p_override = overrides.get(p_key_num) or overrides.get(p_key_name)
                    if p_override:
                        merged.update(p_override)
                    raw_pins.append(merged)
            elif comp_pins is not None:
                raw_pins = comp_pins
            elif "pins" in shared_tmpl:
                raw_pins = shared_tmpl["pins"]
            else:
                raw_pins = []

            for p in raw_pins:
                p_dict = dict(p)
                if "name" in p_dict:
                    p_dict["name"] = str(p_dict["name"])
                if "number" in p_dict:
                    p_dict["number"] = str(p_dict["number"])
                elif "name" in p_dict and (
                    p_dict["name"].isdigit()
                    or (len(p_dict["name"]) <= 4 and p_dict["name"][0].isalpha() and p_dict["name"][1:].isdigit())
                ):
                    p_dict["number"] = p_dict["name"]
                if "pin_name" in p_dict:
                    p_dict["pin_name"] = str(p_dict["pin_name"])
                elif "label" in p_dict and p_dict.get("label") != p_dict.get("name"):
                    p_dict["pin_name"] = str(p_dict["label"])
                if "signal_name" in p_dict:
                    p_dict["signal_name"] = str(p_dict["signal_name"])
                if "label" not in p_dict:
                    p_dict["label"] = p_dict.get("pin_name") or p_dict["name"]
                if "position" in p_dict and len(p_dict["position"]) == 2:
                    p_dict["position"] = (p_dict["position"][0], p_dict["position"][1], 0.0)
                pins.append(PinModel(**p_dict))

            # Parse package and namespace from the YAML value
            if ":" in pkg_str:
                ns, pkg = pkg_str.split(":", 1)
                layout_func = PIN_LAYOUT_REGISTRY.get(f"{ns}:{pkg}")
            else:
                pkg = pkg_str
                project_name = self.yaml_path.parent.name
                ns = project_name
                layout_func = PIN_LAYOUT_REGISTRY.get(f"{ns}:{pkg}")
                if layout_func is None:
                    # Fallback to global package name if namespaced key is not found
                    layout_func = PIN_LAYOUT_REGISTRY.get(pkg)
                    if layout_func is not None:
                        ns = None

            if layout_func is not None:
                layout_func(pins, w, l, c.get("slots_per_side"))

            label_data = c.get("label")
            if isinstance(label_data, str):
                label = LabelModel(text=label_data)
            elif isinstance(label_data, dict):
                label = LabelModel(**label_data)
            else:
                label = LabelModel(text=c["name"], position=(0.0, 0.0, 0.0), align=("center", "center"))

            tt_data = c.get("truth_table")
            truth_table = TruthTableModel(**tt_data) if tt_data else None

            components.append(
                FootprintModel(
                    name=c["name"],
                    package=pkg,
                    namespace=ns,
                    position=tuple(position),
                    rotation=tuple(rotation),
                    dimensions=tuple(dims),
                    mounting_holes=tuple(c["mounting_holes"]) if c.get("mounting_holes") is not None else None,
                    slots_per_side=c.get("slots_per_side"),
                    label=label,
                    value=c.get("value"),
                    pins=pins,
                    mpn=c.get("mpn"),
                    supplier_pn=c.get("supplier_pn"),
                    bga_fanout=c.get("bga_fanout"),
                    layer=c.get("layer") or ("B.Cu" if position[2] < 0 else "F.Cu"),
                    truth_table=truth_table,
                    shape_ref=c.get("shape_ref"),
                    unconnected=bool(c.get("unconnected", False)),
                    dnp=bool(c.get("dnp", False)),
                )
            )
        return components

    @cached_property
    def nets(self) -> List[NetModel]:
        """Load and return structured network connections."""
        nets = []
        for n in self.config.get("nets", []):
            pins = []
            pin_names: Dict[Tuple[str, str], str] = {}
            for p in n.get("pins", []):
                if isinstance(p, (list, tuple)):
                    if len(p) == 2:
                        comp = str(p[0]).strip()
                        pin_spec = str(p[1]).strip()
                        if ":" in pin_spec:
                            pin_num, pin_func = pin_spec.split(":", 1)
                            pin_num_str = pin_num.strip()
                            pins.append((comp, pin_num_str))
                            pin_names[(comp, pin_num_str)] = pin_func.strip()
                        elif "/" in pin_spec:
                            pin_num, pin_func = pin_spec.split("/", 1)
                            pin_num_str = pin_num.strip()
                            pins.append((comp, pin_num_str))
                            pin_names[(comp, pin_num_str)] = pin_func.strip()
                        else:
                            pins.append((comp, pin_spec))
                    elif len(p) >= 3:
                        comp = str(p[0]).strip()
                        pin_num_str = str(p[1]).strip()
                        pin_func_str = str(p[2]).strip()
                        pins.append((comp, pin_num_str))
                        pin_names[(comp, pin_num_str)] = pin_func_str
                elif isinstance(p, dict):
                    comp = str(p.get("component") or p.get("comp")).strip()
                    pin_num_str = str(p.get("pin") or p.get("number")).strip()
                    pin_func = p.get("name") or p.get("pin_name") or p.get("label")
                    pins.append((comp, pin_num_str))
                    if pin_func:
                        pin_names[(comp, pin_num_str)] = str(pin_func).strip()

            nets.append(
                NetModel(
                    name=n["name"],
                    color=n["color"],
                    pins=pins,
                    pin_names=pin_names,
                    offset=tuple(n.get("offset", (0.0, 0.0))),
                    path=[tuple(pt) for pt in n.get("path", [])],
                    priority=n.get("priority"),
                )
            )
        return nets

    @validate_call
    def is_surface_mount(self, component_name: str) -> bool:
        """Check if a component footprint's package is registered as surface mount."""
        for fp in self.footprints:
            if fp.name == component_name:
                key = f"{fp.namespace}:{fp.package}" if fp.namespace else fp.package
                func = PIN_LAYOUT_REGISTRY.get(key)
                if func is None:
                    func = PIN_LAYOUT_REGISTRY.get(fp.package)
                if func is not None:
                    return getattr(func, "surface_mount", False)
        return False

    def filter_by_footprints(self, footprints: List[Any]) -> "Wiring":
        """Return a shallow copy of this Wiring instance with a filtered footprint list."""
        filtered = Wiring.__new__(Wiring)
        filtered.yaml_path = self.yaml_path
        filtered.parent_part = self.parent_part
        filtered.config = self.config
        filtered.shared_footprints = self.shared_footprints
        if footprints and isinstance(footprints[0], str):
            target_names = set(footprints)
            filtered.__dict__["footprints"] = [fp for fp in self.footprints if fp.name in target_names]
        else:
            filtered.__dict__["footprints"] = list(footprints)
        filtered.__dict__["nets"] = self.nets
        return filtered
