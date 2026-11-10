"""Vectorized 3D CAD synthesizer for PCB assemblies in CAD and viewer environments."""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from build123d import Box, Compound, Cylinder, Location, Part, Polygon, Shape, Solid, Text, extrude

from model.pcb import BoardType, PCBConfig, StackupModel
from model.wiring import Wiring
from provider.footprints import FOOTPRINT_REGISTRY


class PCB3DAssembler:
    """High-performance 3D CAD assembly synthesizer for declarative PCB designs.

    Vectorizes construction of board substrate, component package bodies, copper pads,
    top/bottom routing traces, plated via barrels, and silkscreen markings into distinct
    CAD layers ready for interactive inspection in ocp_vscode or integration into
    mechanical CAD assemblies.
    """

    DEFAULT_SOLDERMASK_COLOR = (0.08, 0.45, 0.18)  # Standard dark green soldermask
    DEFAULT_COMPONENT_COLOR = (0.20, 0.20, 0.22)  # Molded epoxy IC / passive dark charcoal
    DEFAULT_PAD_COLOR = (0.90, 0.72, 0.22)  # ENIG gold surface finish
    DEFAULT_TOP_TRACE_COLOR = (0.85, 0.55, 0.18)  # F.Cu warm copper foil ribbon
    DEFAULT_BOTTOM_TRACE_COLOR = (0.28, 0.55, 0.85)  # B.Cu contrasting blue/copper ribbon
    DEFAULT_VIA_COLOR = (0.75, 0.75, 0.80)  # Tinned through-hole via barrels
    DEFAULT_SILKSCREEN_COLOR = (0.95, 0.95, 0.95)  # High-contrast crisp white silkscreen legend

    SOLDERMASK_COLORS: Dict[str, Tuple[float, float, float]] = {
        "matte_black": (0.12, 0.12, 0.14),
        "black": (0.12, 0.12, 0.14),
        "green": (0.08, 0.45, 0.18),
        "blue": (0.10, 0.35, 0.65),
        "red": (0.65, 0.12, 0.12),
        "white": (0.92, 0.92, 0.92),
        "purple": (0.40, 0.15, 0.55),
        "yellow": (0.85, 0.70, 0.10),
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
                self.pcb_config.coverlay_color.lower(), (0.12, 0.12, 0.14)
            )
        elif self.pcb_config.stackup and self.pcb_config.stackup.soldermask_color:
            self.substrate_color = self.SOLDERMASK_COLORS.get(
                self.pcb_config.stackup.soldermask_color.lower(), self.DEFAULT_SOLDERMASK_COLOR
            )
        else:
            self.substrate_color = self.DEFAULT_SOLDERMASK_COLOR

        # Resolve silkscreen color
        if self.pcb_config.stackup and self.pcb_config.stackup.silkscreen_color:
            silk_col_name = self.pcb_config.stackup.silkscreen_color.lower()
            if silk_col_name in ("black", "matte_black"):
                self.silkscreen_color = (0.10, 0.10, 0.10)
            elif silk_col_name == "yellow":
                self.silkscreen_color = (0.90, 0.85, 0.15)
            else:
                self.silkscreen_color = self.DEFAULT_SILKSCREEN_COLOR
        elif self.substrate_color == (0.92, 0.92, 0.92):  # White soldermask -> black silkscreen
            self.silkscreen_color = (0.10, 0.10, 0.10)
        else:
            self.silkscreen_color = self.DEFAULT_SILKSCREEN_COLOR

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
        target_ref = getattr(self.pcb_config, "shape_ref", None)
        is_flex = getattr(self.pcb_config, "board_type", None) == BoardType.FLEX or "flex" in self.pcb_name.lower()

        footprints = []
        if self.wiring and hasattr(self.wiring, "footprints") and self.wiring.footprints:
            all_fps = list(self.wiring.footprints)
        elif hasattr(self.pcb_config, "footprints") and getattr(self.pcb_config, "footprints", None):
            all_fps = list(self.pcb_config.footprints)
        else:
            all_fps = []

        for fp in all_fps:
            fp_shape = getattr(fp, "shape_ref", None)
            if target_ref:
                if fp_shape == target_ref:
                    footprints.append(fp)
                elif not fp_shape and not is_flex:
                    footprints.append(fp)
            else:
                if not is_flex or fp_shape:
                    footprints.append(fp)

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

        # Include capacitive sensor electrodes in copper pads (scoped to target subassembly)
        for cap in self.pcb_config.capacitive_sensors:
            cap_shape = getattr(cap, "shape_ref", None)
            if target_ref:
                if cap_shape != target_ref and (cap_shape or is_flex):
                    continue
            elif is_flex and not cap_shape:
                continue

            center = cap.center_mm or (0.0, 0.0)
            ex, ey = center[0], center[1]
            ew, eh = cap.area_mm[0], cap.area_mm[1]
            pad = Box(ew, eh, self.cu_thickness)
            pad.locate(Location((ex, ey, self.z_top + self.cu_thickness / 2.0)))
            pad_solids.append(pad)

        # Include test points in copper pads (scoped to target subassembly)
        for tp in self.pcb_config.test_points:
            tp_shape = getattr(tp, "shape_ref", None)
            if target_ref:
                if tp_shape != target_ref and (tp_shape or is_flex):
                    continue
            elif is_flex and not tp_shape:
                continue

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

    def build_silkscreen(self, layer: str = "F.SilkS") -> Optional[Compound]:
        """Construct a Compound of 3D extruded silkscreen graphics and text annotations.

        Args:
            layer: Target silkscreen layer ('F.SilkS' for top, 'B.SilkS' for bottom).

        Returns:
            Compound containing 3D silkscreen solid primitives, or None if layer is empty.
        """
        is_bottom = layer == "B.SilkS"
        t_silk = 0.02
        # Position silkscreen slightly proud of copper foil to prevent visual z-fighting
        if not is_bottom:
            z_silk = self.z_top + self.cu_thickness + t_silk / 2.0 + 0.005
        else:
            z_silk = self.z_bottom - self.cu_thickness - t_silk / 2.0 - 0.005

        solids: List[Shape] = []

        # 1. Silkscreen text annotations from PCBConfig
        for st in self.pcb_config.silkscreen_texts:
            if st.layer != layer:
                continue
            txt = Text(st.text, font_size=st.font_size)
            s = extrude(txt, t_silk)
            yaw = st.rotation
            if not is_bottom:
                s.locate(Location((st.position[0], st.position[1], z_silk), (0.0, 0.0, yaw)))
            else:
                s.locate(Location((st.position[0], st.position[1], z_silk), (180.0, 0.0, -yaw)))
            solids.append(s)

        # 2. Silkscreen vector graphics (rectangles/frames, lines, polygons)
        for sg in self.pcb_config.silkscreen_graphics:
            if sg.layer != layer:
                continue
            cx, cy = sg.position
            w, h = sg.dimensions
            th = sg.thickness
            match sg.shape:
                case "rect":
                    if sg.fill:
                        b = Box(w, h, t_silk)
                        b.locate(Location((cx, cy, z_silk)))
                        solids.append(b)
                    else:
                        b_top = Box(w, th, t_silk)
                        b_top.locate(Location((cx, cy + h / 2.0, z_silk)))
                        b_bot = Box(w, th, t_silk)
                        b_bot.locate(Location((cx, cy - h / 2.0, z_silk)))
                        b_left = Box(th, h, t_silk)
                        b_left.locate(Location((cx - w / 2.0, cy, z_silk)))
                        b_right = Box(th, h, t_silk)
                        b_right.locate(Location((cx + w / 2.0, cy, z_silk)))
                        solids.extend([b_top, b_bot, b_left, b_right])
                case "line":
                    if sg.points and len(sg.points) >= 2:
                        x1, y1 = sg.points[0]
                        x2, y2 = sg.points[1]
                    else:
                        x1, y1 = cx - w / 2.0, cy - h / 2.0
                        x2, y2 = cx + w / 2.0, cy + h / 2.0
                    dx = x2 - x1
                    dy = y2 - y1
                    length = math.hypot(dx, dy)
                    if length > 1e-4:
                        angle = math.degrees(math.atan2(dy, dx))
                        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                        b = Box(length, th, t_silk)
                        b.locate(Location((mx, my, z_silk), (0.0, 0.0, angle)))
                        solids.append(b)
                case "polygon":
                    if sg.points and len(sg.points) >= 3:
                        pts = [(pt[0], pt[1]) for pt in sg.points]
                        poly = Polygon(*pts)
                        s = extrude(poly, t_silk)
                        s.locate(Location((0.0, 0.0, z_silk)))
                        solids.append(s)

        # 3. Component reference designators (for footprints on this layer without explicit silkscreen text)
        existing_texts = {st.text for st in self.pcb_config.silkscreen_texts if st.layer == layer}
        omitted = set(self.pcb_config.omitted_silkscreen_designators)
        target_ref = getattr(self.pcb_config, "shape_ref", None)
        is_flex = getattr(self.pcb_config, "board_type", None) == BoardType.FLEX or "flex" in self.pcb_name.lower()

        footprints = []
        if self.wiring and hasattr(self.wiring, "footprints") and self.wiring.footprints:
            all_fps = list(self.wiring.footprints)
        elif hasattr(self.pcb_config, "footprints") and getattr(self.pcb_config, "footprints", None):
            all_fps = list(self.pcb_config.footprints)
        else:
            all_fps = []

        for fp in all_fps:
            fp_shape = getattr(fp, "shape_ref", None)
            if target_ref:
                if fp_shape != target_ref and (fp_shape or is_flex):
                    continue
            elif is_flex and not fp_shape:
                continue

            fp_name = getattr(fp, "name", None)
            if not fp_name or fp_name in existing_texts or fp_name in omitted:
                continue

            fp_is_bottom = (getattr(fp, "layer", "F.Cu") == "B.Cu") or (fp.position[2] < 0.0)
            if fp_is_bottom != is_bottom:
                continue

            cx, cy, _ = fp.position
            txt = Text(fp_name, font_size=0.8)
            s = extrude(txt, t_silk)
            if not is_bottom:
                s.locate(Location((cx, cy + 1.5, z_silk)))
            else:
                s.locate(Location((cx, cy + 1.5, z_silk), (180.0, 0.0, 0.0)))
            solids.append(s)

        if not solids:
            return None

        return Compound(children=solids)

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

        # 7. Front Silkscreen (F.SilkS)
        silk_top = self.build_silkscreen("F.SilkS")
        if silk_top is not None:
            items.append((silk_top, f"{pfx}_silkscreen_top", self.silkscreen_color, 1.0))

        # 8. Back Silkscreen (B.SilkS)
        silk_bottom = self.build_silkscreen("B.SilkS")
        if silk_bottom is not None:
            items.append((silk_bottom, f"{pfx}_silkscreen_bottom", self.silkscreen_color, 1.0))

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
