"""build123d context manager and primitives for declarative PCB component layout and placement."""

import inspect
import re
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from build123d import Location, LocationList

from model.pcb import PCBObstacleModel, SymbolTableEntry
from model.wiring import (
    PIN_LAYOUT_REGISTRY,
    FootprintModel,
    LabelModel,
    PinModel,
    PinRef,
    TruthTableModel,
    load_shared_footprints,
)

_current_build_components: ContextVar[Optional["BuildComponents"]] = ContextVar(
    "_current_build_components", default=None
)


class ComponentInstance:
    """Individual placed component instance on a board exposing pin snapping handles."""

    def __init__(self, footprint: FootprintModel, pins: Sequence[PinRef]) -> None:
        """Initialize placed component instance."""
        self.footprint = footprint
        self._pins = list(pins)
        self._pins_by_name: Dict[str, PinRef] = {}
        for p in pins:
            self._pins_by_name[p.name] = p
            if p.pin_name:
                self._pins_by_name[p.pin_name] = p
            if p.label:
                self._pins_by_name[p.label] = p
        self._pins_by_num: Dict[str, PinRef] = {p.number: p for p in pins if p.number is not None}

    @property
    def name(self) -> str:
        """Component canonical reference designator (e.g. U1, C2)."""
        return self.footprint.name

    @property
    def package(self) -> str:
        """Footprint package identifier."""
        return self.footprint.package

    @property
    def position(self) -> Tuple[float, float, float]:
        """3D absolute placement coordinate (x, y, z) in mm."""
        return self.footprint.position

    @property
    def rotation(self) -> Tuple[float, float, float]:
        """3D orientation angles (pitch, roll, yaw) in deg."""
        return self.footprint.rotation

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        """Physical package dimensions (width, length, thickness) in mm."""
        return self.footprint.dimensions

    @property
    def layer(self) -> str:
        """Copper placement layer ('F.Cu' or 'B.Cu')."""
        return self.footprint.layer

    @property
    def pins(self) -> List[PinRef]:
        """All pins on the component as PinRef handles."""
        return list(self._pins)

    def pin(self, name_or_num: Union[str, int]) -> PinRef:
        """Retrieve a pin by functional name, label, or pin number."""
        key = str(name_or_num).strip()
        if key in self._pins_by_name:
            return self._pins_by_name[key]
        if key in self._pins_by_num:
            return self._pins_by_num[key]

        # Case-insensitive lookup
        key_upper = key.upper()
        for k, p in self._pins_by_name.items():
            if k.upper() == key_upper:
                return p
        for k, p in self._pins_by_num.items():
            if k.upper() == key_upper:
                return p

        available = list(self._pins_by_name.keys())
        raise KeyError(f"Pin '{name_or_num}' not found on component '{self.name}'. Available pins: {available}")

    @property
    def named_pin(self) -> "NamedPinAccessor":
        """Accessor for named pins on this component."""
        return NamedPinAccessor(self._pins_by_name, self.name)

    def __getitem__(self, name_or_num: Union[str, int]) -> PinRef:
        """Lookup pin by name or number with dictionary syntax."""
        return self.pin(name_or_num)

    def __repr__(self) -> str:
        """Return formatted string representation of component instance."""
        return f"<ComponentInstance {self.name} ({self.package}) at {self.position}>"


class NamedPinAccessor:
    """Helper enabling dict indexing, attribute access, and calling by pin functional name."""

    def __init__(self, pins: Dict[str, PinRef], comp_name: str) -> None:
        """Initialize named pin accessor."""
        self._pins = pins
        self._comp_name = comp_name

    def __getitem__(self, name: str) -> PinRef:
        """Retrieve pin by functional name."""
        key = str(name).strip()
        if key in self._pins:
            return self._pins[key]
        for k, p in self._pins.items():
            if k.upper() == key.upper():
                return p
        available = list(self._pins.keys())
        raise KeyError(f"Pin '{name}' not found on component '{self._comp_name}'. Available pins: {available}")

    def __getattr__(self, name: str) -> PinRef:
        """Attribute lookup for pin functional name."""
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(str(err)) from err

    def __call__(self, name: str) -> PinRef:
        """Callable lookup for pin functional name."""
        return self[name]


class BuildComponents:
    """Context manager for declarative PCB component placement and layout blocks."""

    def __init__(
        self,
        name: Optional[str] = None,
        subassembly: Optional[str] = None,
        parent_part: Optional[Any] = None,
    ) -> None:
        """Initialize component layout context block.

        Args:
            name: Block identifier (e.g. 'power_supply', 'mcu_core', 'sensors').
            subassembly: Optional subassembly identifier (e.g. 'carrier_board', 'flex_tail').
            parent_part: Optional CAD assembly / part defining kinematic joints.
        """
        self.name = name or "layout"
        self.subassembly = subassembly
        self.parent_part = parent_part
        self.components: List[FootprintModel] = []
        self.instances: List[ComponentInstance] = []
        self.symbol_table_entries: Dict[str, SymbolTableEntry] = {}
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildComponents":
        """Enter component layout builder context."""
        self._token = _current_build_components.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit component layout context and register into active BuildPcb."""
        if self._token is not None:
            _current_build_components.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            # Register footprints avoiding duplicates
            for fp in self.components:
                if not any(existing.name == fp.name for existing in active_pcb.footprints):
                    active_pcb.footprints.append(fp)

            # Update symbol table
            active_pcb.symbol_table.update(self.symbol_table_entries)

            # Derive 3D clearance obstacle boxes
            for fp in self.components:
                if not any(obs.name == fp.name for obs in active_pcb.obstacles):
                    obs = PCBObstacleModel(
                        name=fp.name,
                        shape="box",
                        dimensions_mm=fp.dimensions,
                        position_mm=fp.position,
                        layer=fp.layer,
                        description=f"Component {fp.name} ({fp.package}) from block '{self.name}'",
                    )
                    active_pcb.obstacles.append(obs)

    @classmethod
    def _get_context(cls) -> Optional["BuildComponents"]:
        """Retrieve active component layout context if present."""
        return _current_build_components.get()

    @classmethod
    def get_highest_designator_number(cls, prefix: str) -> int:
        """Find highest numerical suffix for an existing component with the given prefix."""
        designators: List[str] = []

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            designators.extend(fp.name for fp in active_pcb.footprints)
            designators.extend(active_pcb.symbol_table.keys())

        ctx = cls._get_context()
        if ctx is not None:
            designators.extend(fp.name for fp in ctx.components)
            designators.extend(ctx.symbol_table_entries.keys())

        nums = []
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        for des in set(designators):
            m = pattern.match(des)
            if m:
                nums.append(int(m.group(1)))

        return max(nums) if nums else 0

    def add(self, instance: ComponentInstance, symbol_entry: Optional[SymbolTableEntry] = None) -> None:
        """Register a placed component instance into this context."""
        self.instances.append(instance)
        self.components.append(instance.footprint)
        if symbol_entry is not None:
            self.symbol_table_entries[instance.name] = symbol_entry


class Component(list):
    """Declarative component primitive evaluated inside a BuildComponents context."""

    def __init__(
        self,
        name_or_prefix: Optional[str] = None,
        package: str = "custom",
        value: Optional[str] = None,
        mpn: Optional[str] = None,
        supplier_pn: Optional[str] = None,
        layer: str = "F.Cu",
        shape_ref: Optional[str] = None,
        unconnected: bool = False,
        dnp: bool = False,
        omit_silkscreen: bool = False,
        position: Optional[Tuple[float, float, float]] = None,
        rotation: Optional[Tuple[float, float, float]] = None,
        dimensions: Optional[Tuple[float, float, float]] = None,
        pins: Optional[Union[Sequence[Union[Dict[str, Any], PinModel]], Any]] = None,
        label: Optional[Union[str, LabelModel, Dict[str, Any]]] = None,
        truth_table: Optional[TruthTableModel] = None,
        slots_per_side: Optional[int] = None,
        joint_ref: Optional[Dict[str, Any]] = None,
        parent_part: Optional[Any] = None,
        auto_number: bool = True,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Instantiate one or more components using ambient LocationList context."""
        super().__init__()
        if name is not None:
            name_or_prefix = name
            auto_number = False
        elif not name_or_prefix:
            pkg_lower = package.lower()
            val_lower = (value or "").lower()
            if "resistor" in pkg_lower or pkg_lower.startswith("r_"):
                name_or_prefix = "R"
            elif (
                "capacitor" in pkg_lower
                or pkg_lower.startswith("c_")
                or any(u in val_lower for u in ("f", "uf", "pf", "nf"))
            ):
                name_or_prefix = "C"
            elif any(d in pkg_lower for d in ("led", "sod", "diode")):
                name_or_prefix = "D"
            elif "sw" in pkg_lower or "switch" in pkg_lower:
                name_or_prefix = "SW"
            elif any(j in pkg_lower for j in ("jst", "fpc", "usb", "header", "conn")):
                name_or_prefix = "J"
            elif any(u in pkg_lower for u in ("qfn", "bga", "sot", "tssop", "wson", "mod", "ic")):
                name_or_prefix = "U"
            elif "xtal" in pkg_lower or "osc" in pkg_lower:
                name_or_prefix = "Y"
            elif "tp" in pkg_lower or "test_point" in pkg_lower:
                name_or_prefix = "TP"
            else:
                name_or_prefix = "U"
            auto_number = True

        ctx = BuildComponents._get_context()
        block_name = ctx.name if ctx else "default"

        # 1. Determine placement locations
        loc_ctx = LocationList._get_context()
        if joint_ref is not None:
            p_part = parent_part or (ctx.parent_part if ctx else None)
            if p_part is not None and "joint" in joint_ref:
                j_name = joint_ref["joint"]
                j_offset = joint_ref.get("offset", (0.0, 0.0, 0.0))
                if hasattr(p_part, "joints") and j_name in p_part.joints:
                    j_loc = p_part.joints[j_name].location * Location(tuple(j_offset))
                    locations = [j_loc]
                else:
                    locations = [Location(position or (0.0, 0.0, 0.0), rotation or (0.0, 0.0, 0.0))]
            else:
                locations = [Location(position or (0.0, 0.0, 0.0), rotation or (0.0, 0.0, 0.0))]
        elif position is not None:
            rot = rotation or (0.0, 0.0, 0.0)
            locations = [Location(position, rot)]
        elif loc_ctx is not None and getattr(loc_ctx, "locations", None):
            locations = list(loc_ctx.locations)
        else:
            locations = [Location((0.0, 0.0, 0.0))]

        # 2. Determine designators (continuous auto-numbering across blocks)
        if not auto_number:
            if len(locations) == 1:
                designators = [name_or_prefix]
            else:
                designators = [f"{name_or_prefix}_{i + 1}" for i in range(len(locations))]
        else:
            prefix_match = re.match(r"^([A-Za-z_]+)(\d*)$", name_or_prefix)
            if prefix_match:
                prefix, num_part = prefix_match.group(1), prefix_match.group(2)
            else:
                prefix, num_part = name_or_prefix, ""

            if num_part:
                start_num = int(num_part)
                designators = [f"{prefix}{start_num + i}" for i in range(len(locations))]
            else:
                start_num = BuildComponents.get_highest_designator_number(prefix) + 1
                designators = [f"{prefix}{start_num + i}" for i in range(len(locations))]

        # 3. Resolve package template and pins
        shared_templates = load_shared_footprints()
        pkg_key = package
        namespace = None
        if ":" in package:
            namespace, pkg_name = package.split(":", 1)
        else:
            pkg_name = package

        tmpl = shared_templates.get(pkg_key, {}) or shared_templates.get(pkg_name, {})

        resolved_dims = dimensions or tmpl.get("dimensions") or (5.0, 5.0, 1.0)
        w, l, thickness = resolved_dims

        # Merge pin definitions
        base_raw_pins = tmpl.get("pins", [])
        if pins is not None and base_raw_pins:
            overrides = {}
            for p in pins:
                key = str(
                    getattr(p, "number", None)
                    or getattr(p, "name", None)
                    or (p.get("number") or p.get("name") if isinstance(p, dict) else "")
                )
                overrides[key] = p
            raw_pins = []
            for bp in base_raw_pins:
                merged = dict(bp)
                p_key = str(bp.get("number") or bp.get("name"))
                if p_key in overrides:
                    ov = overrides[p_key]
                    if isinstance(ov, PinModel):
                        merged.update(ov.model_dump(exclude_none=True))
                    elif isinstance(ov, dict):
                        merged.update(ov)
                raw_pins.append(merged)
        elif pins is not None:
            raw_pins = list(pins)
        else:
            raw_pins = list(base_raw_pins)

        parsed_pins: List[PinModel] = []
        for p in raw_pins:
            if isinstance(p, PinModel):
                parsed_pins.append(p.model_copy())
                continue
            p_dict = dict(p)
            if "name" in p_dict:
                p_dict["name"] = str(p_dict["name"])
            if "number" in p_dict:
                p_dict["number"] = str(p_dict["number"])
            elif "name" in p_dict and p_dict["name"].isdigit():
                p_dict["number"] = p_dict["name"]
            if "label" not in p_dict:
                p_dict["label"] = p_dict.get("pin_name") or p_dict.get("name", "")
            if "position" in p_dict and len(p_dict["position"]) == 2:
                p_dict["position"] = (p_dict["position"][0], p_dict["position"][1], 0.0)
            parsed_pins.append(PinModel(**p_dict))

        # Inspect caller frame for source tracking
        source_file = None
        source_line = None
        caller_project = None
        stack = inspect.stack()
        if len(stack) > 1:
            caller = stack[1]
            source_file = Path(caller.filename).name
            source_line = caller.lineno
            caller_project = Path(caller.filename).parent.name

        # Check layout registry
        layout_func = None
        if namespace is not None:
            layout_func = PIN_LAYOUT_REGISTRY.get(f"{namespace}:{pkg_name}")
        elif caller_project is not None:
            layout_func = PIN_LAYOUT_REGISTRY.get(f"{caller_project}:{pkg_name}")
        if layout_func is None:
            layout_func = PIN_LAYOUT_REGISTRY.get(pkg_name)
        if layout_func is None:
            matches = [v for k, v in PIN_LAYOUT_REGISTRY.items() if k.endswith(f":{pkg_name}")]
            if len(matches) == 1:
                layout_func = matches[0]

        if layout_func is not None:
            layout_func(parsed_pins, w, l, slots_per_side)

        # 4. Instantiate each component across locations
        for i, loc in enumerate(locations):
            des = designators[i]
            if position is not None and len(locations) == 1:
                pos_3d = (
                    0.0 if abs(position[0]) == 0.0 else round(float(position[0]), 4),
                    0.0 if abs(position[1]) == 0.0 else round(float(position[1]), 4),
                    0.0 if abs(position[2]) == 0.0 else round(float(position[2]), 4),
                )
            else:
                pos_3d = (
                    0.0 if abs(loc.position.X) == 0.0 else round(float(loc.position.X), 4),
                    0.0 if abs(loc.position.Y) == 0.0 else round(float(loc.position.Y), 4),
                    0.0 if abs(loc.position.Z) == 0.0 else round(float(loc.position.Z), 4),
                )

            if rotation is not None and len(locations) == 1:
                rot_3d = (
                    0.0 if abs(rotation[0]) == 0.0 else round(float(rotation[0]), 4),
                    0.0 if abs(rotation[1]) == 0.0 else round(float(rotation[1]), 4),
                    0.0 if abs(rotation[2]) == 0.0 else round(float(rotation[2]), 4),
                )
            else:
                rot_3d = (
                    0.0 if abs(loc.orientation.X) == 0.0 else round(float(loc.orientation.X), 4),
                    0.0 if abs(loc.orientation.Y) == 0.0 else round(float(loc.orientation.Y), 4),
                    0.0 if abs(loc.orientation.Z) == 0.0 else round(float(loc.orientation.Z), 4),
                )

            # Deep copy pins for this instance
            inst_pins = [p.model_copy() for p in parsed_pins]

            lbl = None
            if isinstance(label, str):
                lbl = LabelModel(text=label)
            elif isinstance(label, LabelModel):
                lbl = label
            elif isinstance(label, dict):
                lbl = LabelModel(**label)
            else:
                lbl = LabelModel(text=des)

            fp = FootprintModel(
                name=des,
                package=pkg_name,
                namespace=namespace,
                position=pos_3d,
                rotation=rot_3d,
                dimensions=tuple(resolved_dims),
                label=lbl,
                value=value,
                pins=inst_pins,
                mpn=mpn,
                supplier_pn=supplier_pn,
                layer=layer,
                truth_table=truth_table,
                shape_ref=shape_ref,
                unconnected=unconnected,
                dnp=dnp,
                omit_silkscreen=omit_silkscreen,
            )

            pin_refs = [
                PinRef(
                    component_name=des,
                    pin=p,
                    component_position=pos_3d,
                    component_rotation=rot_3d,
                )
                for p in inst_pins
            ]

            instance = ComponentInstance(fp, pin_refs)
            self.append(instance)

            sym_entry = SymbolTableEntry(
                designator=des,
                block=block_name,
                subassembly=getattr(ctx, "subassembly", None),
                package=package,
                value=value,
                mpn=mpn,
                supplier_pn=supplier_pn,
                position_mm=pos_3d,
                rotation_deg=rot_3d,
                layer=layer,
                source_file=source_file,
                source_line=source_line,
            )

            if ctx is not None:
                ctx.add(instance, sym_entry)

    # Convenience forwards to primary instance when single component
    @property
    def primary(self) -> ComponentInstance:
        """Return the primary single component instance."""
        if not self:
            raise IndexError("Component contains no instances.")
        return self[0]

    @property
    def name(self) -> str:
        """Primary component designator."""
        return self.primary.name

    @property
    def position(self) -> Tuple[float, float, float]:
        """Primary component position."""
        return self.primary.position

    @property
    def rotation(self) -> Tuple[float, float, float]:
        """Primary component orientation."""
        return self.primary.rotation

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        """Primary component physical dimensions."""
        return self.primary.dimensions

    @property
    def pins(self) -> List[PinRef]:
        """Pins on primary component."""
        return self.primary.pins

    def pin(self, name_or_num: Union[str, int]) -> PinRef:
        """Retrieve pin from primary component."""
        return self.primary.pin(name_or_num)

    @property
    def named_pin(self) -> NamedPinAccessor:
        """Named pin accessor for primary component instance."""
        return self.primary.named_pin
