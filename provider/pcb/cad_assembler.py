"""Vectorized 3D CAD synthesizer for PCB assemblies in CAD and viewer environments."""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from build123d import Box, Compound, Cylinder, Location, Part, Shape, Solid

from model.pcb import PCBConfig, StackupModel
from model.wiring import Wiring
from provider.footprints import FOOTPRINT_REGISTRY


class PCB3DAssembler:
    """High-performance 3D CAD assembly synthesizer for declarative PCB designs.

    Vectorizes construction of board substrate, component package bodies, copper pads,
    top/bottom routing traces, and via barrels into distinct CAD layers ready for interactive
    inspection in ocp_vscode or integration into mechanical CAD assemblies.
    """

    DEFAULT_SOLDERMASK_COLOR = (0.08, 0.40, 0.20)  # Standard dark green soldermask
    DEFAULT_COMPONENT_COLOR = (0.20, 0.20, 0.22)  # Molded epoxy IC / passive black
    DEFAULT_PAD_COLOR = (0.85, 0.55, 0.15)  # ENIG gold / bare copper
    DEFAULT_TOP_TRACE_COLOR = (0.80, 0.50, 0.15)  # F.Cu copper ribbon
    DEFAULT_BOTTOM_TRACE_COLOR = (0.30, 0.50, 0.80)  # B.Cu contrasting blue/copper ribbon
    DEFAULT_VIA_COLOR = (0.70, 0.70, 0.75)  # Tinned copper / silver barrel

    SOLDERMASK_COLORS: Dict[str, Tuple[float, float, float]] = {
        "matte_black": (0.12, 0.12, 0.12),
        "black": (0.12, 0.12, 0.12),
        "green": (0.08, 0.40, 0.20),
        "blue": (0.10, 0.25, 0.65),
        "red": (0.65, 0.10, 0.10),
        "white": (0.90, 0.90, 0.90),
        "purple": (0.45, 0.15, 0.55),
    }

    def __init__(
        self,
        pcb_config: PCBConfig,
        wiring: Optional[Wiring] = None,
        substrate: Optional[Any] = None,
        cu_thickness: float = 0.035,
        substrate_color: Optional[Tuple[float, float, float]] = None,
        pcb_name: Optional[str] = None,
    ) -> None:
        """Initialize PCB 3D assembler.

        Args:
            pcb_config: Strongly typed PCB configuration containing traces, vias, stackup, etc.
            wiring: Optional Wiring container containing component footprints and nets.
            substrate: Optional pre-constructed 3D CAD solid for the PCB substrate.
            cu_thickness: Copper foil layer thickness in mm (defaults to 35µm / 1oz Cu).
            substrate_color: Optional RGB tuple for substrate soldermask.
            pcb_name: Optional prefix name for assembly and layer tree items.
        """
        self.pcb_config = pcb_config
        self.wiring = wiring
        self.substrate = substrate
        self.cu_thickness = cu_thickness
        self.pcb_name = pcb_name or pcb_config.name or "board"

        # Determine board thickness and vertical bounds
        self.total_thickness = self._resolve_board_thickness()
        self.z_top = self.total_thickness / 2.0
        self.z_bottom = -self.total_thickness / 2.0
        self.z_mid = 0.0

        # Resolve soldermask color
        if substrate_color is not None:
            self.substrate_color = substrate_color
        elif self.pcb_config.coverlay_color:
            self.substrate_color = self.SOLDERMASK_COLORS.get(
                self.pcb_config.coverlay_color.lower(), (0.12, 0.12, 0.12)
            )
        elif self.pcb_config.stackup and self.pcb_config.stackup.soldermask_color:
            self.substrate_color = self.SOLDERMASK_COLORS.get(
                self.pcb_config.stackup.soldermask_color.lower(), self.DEFAULT_SOLDERMASK_COLOR
            )
        else:
            self.substrate_color = self.DEFAULT_SOLDERMASK_COLOR

    def _resolve_board_thickness(self) -> float:
        """Derive physical board substrate thickness in mm."""
        if self.pcb_config.stackup and self.pcb_config.stackup.total_thickness_mm:
            return float(self.pcb_config.stackup.total_thickness_mm)
        if self.pcb_config.dimensions_mm and len(self.pcb_config.dimensions_mm) > 2:
            return float(self.pcb_config.dimensions_mm[2])
        return 1.6

    @classmethod
    def from_build_pcb(
        cls,
        builder: Any,
        wiring: Optional[Wiring] = None,
        substrate_color: Optional[Tuple[float, float, float]] = None,
        pcb_name: Optional[str] = None,
    ) -> "PCB3DAssembler":
        """Instantiate PCB3DAssembler directly from an active or finished BuildPcb/BuildFlexPCB builder."""
        cfg = builder.to_pcb_config() if hasattr(builder, "to_pcb_config") else builder.pcb_config
        resolved_wiring = wiring or getattr(builder, "wiring", None)
        if resolved_wiring is None and hasattr(builder, "footprints") and builder.footprints:
            resolved_wiring = Wiring.from_models(footprints=list(builder.footprints), nets=[])
        substrate_part = getattr(builder, "part", None)
        name = pcb_name or getattr(builder, "name", cfg.name)
        return cls(
            pcb_config=cfg,
            wiring=resolved_wiring,
            substrate=substrate_part,
            substrate_color=substrate_color,
            pcb_name=name,
        )

    @classmethod
    def from_provider(
        cls,
        provider: Any,
        subassembly: Optional[str] = None,
        substrate_color: Optional[Tuple[float, float, float]] = None,
    ) -> "PCB3DAssembler":
        """Instantiate PCB3DAssembler directly from a Provider instance."""
        cfg = getattr(provider, "pcb_config", None)
        if cfg is None:
            raise ValueError(f"Provider {provider} does not have a valid pcb_config.")
        wiring = getattr(provider, "wiring", None)
        substrate = getattr(provider, "substrate", None)
        name = subassembly or getattr(provider, "name", "board")
        return cls(
            pcb_config=cfg,
            wiring=wiring,
            substrate=substrate,
            substrate_color=substrate_color,
            pcb_name=name,
        )

    def build_substrate(self) -> Optional[Union[Solid, Compound]]:
        """Construct the 3D substrate solid with drill holes subtracted."""
        if self.substrate is not None:
            if hasattr(self.substrate, "part"):
                return self.substrate.part
            return self.substrate

        # Fallback: extrude substrate solid from dimensions
        if not self.pcb_config.dimensions_mm:
            return None

        w, length = self.pcb_config.dimensions_mm[0], self.pcb_config.dimensions_mm[1]
        solid = Box(w, length, self.total_thickness)

        # Subtract mounting holes if specified
        holes = []
        for mh in self.pcb_config.mounting_holes:
            hx, hy = mh.position_mm
            dia = getattr(mh, "drill_diameter_mm", None) or getattr(mh, "diameter_mm", 3.2)
            drill = Cylinder(radius=dia / 2.0, height=self.total_thickness + 1.0)
            drill.locate(Location((hx, hy, 0.0)))
            holes.append(drill)

        if holes:
            solid = solid - Compound(children=holes)

        return solid

    def build_traces(self, layer: str) -> Optional[Compound]:
        """Construct a Compound of copper trace ribbons for a specified layer."""
        matching_traces = [t for t in self.pcb_config.traces if t.layer == layer]
        if not matching_traces:
            return None

        if layer == "F.Cu":
            z_pos = self.z_top + self.cu_thickness / 2.0
        elif layer == "B.Cu":
            z_pos = self.z_bottom - self.cu_thickness / 2.0
        else:
            z_pos = self.z_mid

        boxes = []
        for t in matching_traces:
            x1, y1 = t.start_mm
            x2, y2 = t.end_mm
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length < 1e-4:
                continue

            angle_deg = math.degrees(math.atan2(dy, dx))
            mx = (x1 + x2) / 2.0
            my = (y1 + y2) / 2.0

            b = Box(length, t.width_mm, self.cu_thickness)
            b.locate(Location((mx, my, z_pos), (0.0, 0.0, angle_deg)))
            boxes.append(b)

        if not boxes:
            return None

        return Compound(children=boxes)

    def build_vias(self) -> Optional[Compound]:
        """Construct a Compound of plated through-hole via barrel cylinders."""
        if not self.pcb_config.vias:
            return None

        via_height = self.total_thickness + 2.0 * self.cu_thickness
        cylinders = []
        for v in self.pcb_config.vias:
            vx, vy = v.position_mm
            dia = v.pad_diameter_mm
            c = Cylinder(radius=dia / 2.0, height=via_height)
            c.locate(Location((vx, vy, self.z_mid)))
            cylinders.append(c)

        if not cylinders:
            return None

        return Compound(children=cylinders)

    def build_components_and_pads(self) -> Tuple[Optional[Compound], Optional[Compound]]:
        """Construct Compounds of 3D component package bodies and copper pads."""
        footprints = []
        if self.wiring and hasattr(self.wiring, "footprints") and self.wiring.footprints:
            footprints = list(self.wiring.footprints)
        elif hasattr(self.pcb_config, "footprints") and getattr(self.pcb_config, "footprints", None):
            footprints = list(self.pcb_config.footprints)

        comp_solids: List[Shape] = []
        pad_solids: List[Shape] = []

        for c in footprints:
            cx, cy, cz = c.position
            yaw = c.rotation[2]
            rad = math.radians(yaw)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            is_bottom = (getattr(c, "layer", "F.Cu") == "B.Cu") or (cz < 0.0)

            pad_z = (
                (self.z_top + self.cu_thickness / 2.0) if not is_bottom else (self.z_bottom - self.cu_thickness / 2.0)
            )

            fp_factory = FOOTPRINT_REGISTRY.get(c.package)
            if fp_factory is not None:
                fp_inst = fp_factory()
                if fp_inst.part is not None:
                    body = fp_inst.part
                    if is_bottom:
                        loc = Location((cx, cy, cz), (180.0, 0.0, -yaw))
                    else:
                        loc = Location((cx, cy, cz), (0.0, 0.0, yaw))
                    body.locate(loc)
                    comp_solids.append(body)

                for p in fp_inst.pins:
                    px, py = p.position[0], p.position[1]
                    wx = cx + px * cos_a - py * sin_a
                    wy = cy + px * sin_a + py * cos_a
                    pw, ph = p.pad_size_mm
                    pad_shape_str = str(getattr(p, "pad_shape", "rect")).lower()

                    if "circle" in pad_shape_str:
                        pad = Cylinder(radius=pw / 2.0, height=self.cu_thickness)
                        pad.locate(Location((wx, wy, pad_z)))
                    else:
                        pad = Box(pw, ph, self.cu_thickness)
                        pad.locate(Location((wx, wy, pad_z), (0.0, 0.0, yaw)))
                    pad_solids.append(pad)
            else:
                dims = getattr(c, "dimensions", None) or (5.0, 5.0, 1.0)
                dx, dy, dz = dims[0], dims[1], dims[2]
                box_z = cz + (dz / 2.0 if not is_bottom else -dz / 2.0)
                body = Box(dx, dy, dz)
                body.locate(Location((cx, cy, box_z), (0.0, 0.0, yaw)))
                comp_solids.append(body)

        # Include capacitive sensor electrodes in copper pads
        for cap in self.pcb_config.capacitive_sensors:
            center = cap.center_mm or (0.0, 0.0)
            ex, ey = center[0], center[1]
            ew, eh = cap.area_mm[0], cap.area_mm[1]
            pad = Box(ew, eh, self.cu_thickness)
            pad.locate(Location((ex, ey, self.z_top + self.cu_thickness / 2.0)))
            pad_solids.append(pad)

        # Include test points in copper pads
        for tp in self.pcb_config.test_points:
            tpx, tpy = tp.position_mm[0], tp.position_mm[1]
            dia = tp.pad_diameter_mm
            tp_is_bottom = getattr(tp, "layer", "F.Cu") == "B.Cu"
            tp_z = (
                (self.z_top + self.cu_thickness / 2.0)
                if not tp_is_bottom
                else (self.z_bottom - self.cu_thickness / 2.0)
            )
            pad = Cylinder(radius=dia / 2.0, height=self.cu_thickness)
            pad.locate(Location((tpx, tpy, tp_z)))
            pad_solids.append(pad)

        comps_cmp = Compound(children=comp_solids) if comp_solids else None
        pads_cmp = Compound(children=pad_solids) if pad_solids else None

        return comps_cmp, pads_cmp

    def get_display_items(
        self, prefix: Optional[str] = None
    ) -> List[Tuple[Any, str, Tuple[float, float, float], float]]:
        """Return list of (geometry, layer_name, rgb_color, alpha) for all active PCB layers."""
        pfx = prefix or self.pcb_name
        items: List[Tuple[Any, str, Tuple[float, float, float], float]] = []

        # 1. Substrate
        substrate = self.build_substrate()
        if substrate is not None:
            items.append((substrate, f"{pfx}_substrate", self.substrate_color, 1.0))

        # 2. Components
        comps, pads = self.build_components_and_pads()
        if comps is not None:
            items.append((comps, f"{pfx}_components", self.DEFAULT_COMPONENT_COLOR, 1.0))

        # 3. Copper Pads
        if pads is not None:
            items.append((pads, f"{pfx}_pads", self.DEFAULT_PAD_COLOR, 1.0))

        # 4. Front Copper Traces (F.Cu)
        traces_top = self.build_traces("F.Cu")
        if traces_top is not None:
            items.append((traces_top, f"{pfx}_traces_top", self.DEFAULT_TOP_TRACE_COLOR, 1.0))

        # 5. Back Copper Traces (B.Cu)
        traces_bottom = self.build_traces("B.Cu")
        if traces_bottom is not None:
            items.append((traces_bottom, f"{pfx}_traces_bottom", self.DEFAULT_BOTTOM_TRACE_COLOR, 1.0))

        # 6. Vias
        vias = self.build_vias()
        if vias is not None:
            items.append((vias, f"{pfx}_vias", self.DEFAULT_VIA_COLOR, 1.0))

        return items

    def populate_room(self, room: Any, prefix: Optional[str] = None) -> None:
        """Populate distinct CAD layers directly into a Room object for interactive CAD viewing."""
        for geom, name, color, alpha in self.get_display_items(prefix=prefix):
            room.add(name, geom, color=color, alpha=alpha)

    def to_cad_assembly(self) -> Compound:
        """Synthesize a complete 3D CAD Compound containing all active layers."""
        children = []
        for geom, _, _, _ in self.get_display_items():
            if hasattr(geom, "part"):
                children.append(geom.part)
            else:
                children.append(geom)

        return Compound(children=children)
