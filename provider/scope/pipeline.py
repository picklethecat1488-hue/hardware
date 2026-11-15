"""Backend Geometry & Tessellation Pipeline for Interactive CAD/PCB Scope Workstation."""

from __future__ import annotations

import base64
import gzip
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import orjson

from model import AppConfig
from shell import Logger
from provider import ProviderManager, Section, Mode, Room, Provider
from target_parser import TargetParser
from provider.pcb.cad_assembler import PCB3DAssembler
from model.pcb import resolve_subassembly_pcb_config
from build123d import Plane, Compound

try:
    from ocp_vscode.config import config as ocp_config
    from ocp_viewer_core.show import Viewer as CoreViewer
except ImportError:
    ocp_config = None
    CoreViewer = None


from model.scope import (
    ScopeProjectModel,
    ScopeTargetModel,
)


class ScopeGeometryPipeline:
    """Manages project discovery, geometry resolution, and tessellation caching."""

    SIM_TELEMETRY_CACHE_VERSION = "v4"
    PCB_METADATA_RENDER_VERSION = 2
    MM_PER_METER = 1000.0
    DEFAULT_PARTICLE_RADIUS_MM = 2.0
    MIN_VOXEL_LATTICE_STEP_MM = 0.25
    VOXEL_LATTICE_QUANT_MM = 0.01
    VOXEL_LATTICE_TOLERANCE_RATIO = 0.03
    VOXEL_LATTICE_INLIER_FRACTION = 0.96
    VOXEL_RADIUS_RATIO_FALLBACK = 0.54
    DEFAULT_WATER_RGBA = [0.502, 0.800, 1.000, 0.750]

    def __init__(
        self,
        manager: Optional[ProviderManager] = None,
        logger: Optional[Logger] = None,
        repo_root: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize the scope geometry pipeline with persistent disk caching."""
        self.config = AppConfig()
        self.logger = logger or Logger(enabled=False)
        self.log = logging.getLogger("scope.pipeline")
        self.manager = manager or ProviderManager(self.config, logger=self.logger)
        self.target_parser = TargetParser(self.manager.router)
        self.repo_root = (repo_root or Path(__file__).resolve().parent.parent.parent).resolve()
        self.cache_dir = (cache_dir or (self.repo_root / "build" / "cache" / "scope")).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[Tuple[str, str, Optional[str], str, Optional[int]], Dict[str, Any]] = {}
        self._gz_cache: Dict[Tuple[str, str, Optional[str], str, Optional[int]], bytes] = {}
        self._lock = threading.Lock()
        self._in_progress: Dict[Tuple[str, str, Optional[str], str, Optional[int]], threading.Event] = {}

        # Silence OCP vscode websocket notifications so converting geometries never blocks or warns
        if ocp_config is not None:
            ocp_config.status = lambda: {}
            ocp_config.workspace_config = lambda: {}
            if hasattr(ocp_config, "_send_viewer_config"):
                ocp_config._send_viewer_config = lambda *a, **k: None
            try:
                from ocp_vscode.config import Camera

                ocp_config.set_defaults(reset_camera=Camera.RESET)
            except Exception:
                pass

    def sync(self):
        """Invalidate geometry caches and refresh project manifests."""
        with self._lock:
            self._cache.clear()
            self._gz_cache.clear()
        if self.cache_dir.is_dir():
            for f in self.cache_dir.glob("*.json.gz"):
                try:
                    f.unlink()
                except OSError:
                    pass
        if hasattr(self.manager.router, "_load_manifest"):
            self.manager.router._load_manifest()

    def _get_cache_path(
        self,
        project: str,
        target: str,
        subassembly: Optional[str],
        mode: str,
        step_index: Optional[int],
    ) -> Path:
        """Derive persistent disk cache filename for a given geometry target."""
        sub_slug = subassembly or "none"
        step_slug = str(step_index) if step_index is not None else "none"
        filename = f"{project}_{target}_{sub_slug}_{mode.upper()}_{step_slug}.json.gz"
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_file: Path, project: str) -> bool:
        """Check if cached geometry file exists and is newer than all relevant source files."""
        if not cache_file.is_file():
            return False
        try:
            cache_mtime = cache_file.stat().st_mtime
            check_dirs = [
                self.repo_root / "projects" / project,
                self.repo_root / "provider" / "pcb",
                self.repo_root / "provider" / "scope",
            ]
            for d in check_dirs:
                if not d.is_dir():
                    continue
                for p in d.rglob("*"):
                    if p.is_file() and p.suffix in (".py", ".yaml", ".sqlx", ".json"):
                        try:
                            if p.stat().st_mtime > cache_mtime:
                                return False
                        except OSError:
                            pass
            return True
        except OSError:
            return False

    @staticmethod
    def _normalize_subassembly(subassembly: Optional[str]) -> Optional[str]:
        """Normalize empty or mode-specifier subassembly strings to None."""
        if not subassembly:
            return None
        cleaned = subassembly.strip()
        if not cleaned or cleaned.lower() in ("cad", "pcb", "simulate", "diagram", "view", "part"):
            return None
        return cleaned

    def get_cached_gzip(
        self,
        project: str,
        target: str,
        subassembly: Optional[str] = None,
        mode: str = "CAD",
        step_index: Optional[int] = None,
    ) -> Optional[bytes]:
        """Return raw gzip-compressed payload bytes from memory or disk cache if available."""
        if project == "cat_fountain" and target == "simulation":
            target = "product"
            mode = "SIMULATE"

        subassembly = self._normalize_subassembly(subassembly)
        mode_upper = mode.upper()
        cache_key = (project, target, subassembly, mode_upper, step_index)
        with self._lock:
            if cache_key in self._gz_cache:
                return self._gz_cache[cache_key]

        cache_file = self._get_cache_path(project, target, subassembly, mode_upper, step_index)
        if self._is_cache_valid(cache_file, project):
            try:
                gz_bytes = cache_file.read_bytes()
                with self._lock:
                    self._gz_cache[cache_key] = gz_bytes
                return gz_bytes
            except Exception:
                pass
        return None

    def get_projects(self) -> List[ScopeProjectModel]:
        """Discover all available projects, targets, subassemblies, and modes."""
        manifest = self.manager.router.manifest
        project_map: Dict[str, Dict[str, ScopeTargetModel]] = {}

        # 1. Inspect manifest keys and filter only viewable geometry targets
        for key, entry in manifest.items():
            if not isinstance(entry, dict):
                continue
            parts = key.split("/")
            if len(parts) >= 2:
                proj = parts[0]
                target = parts[1].split(":")[0]
            else:
                proj = key.split(":")[0]
                target = proj

            modes: List[str] = []
            if Section.PART in entry:
                modes.append("CAD")
            if Section.PCB in entry:
                modes.append("PCB")
            if Section.DIAGRAM in entry:
                modes.append("DIAGRAM")
            if Section.VIEW in entry:
                view_cfg = entry[Section.VIEW]
                if isinstance(view_cfg, dict) and "simulate" in view_cfg.get("modes", []):
                    modes.append("SIMULATE")
                if "CAD" not in modes:
                    modes.append("CAD")

            if not modes:
                continue

            if proj not in project_map:
                project_map[proj] = {}

            if target not in project_map[proj]:
                project_map[proj][target] = ScopeTargetModel(
                    name=target,
                    subassemblies=[],
                    modes=modes,
                )
            else:
                for m in modes:
                    if m not in project_map[proj][target].modes:
                        project_map[proj][target].modes.append(m)

        # 2. Collect targets
        result: List[ScopeProjectModel] = []
        for proj, targets in sorted(project_map.items()):
            t_list: List[ScopeTargetModel] = []
            for t_name, tm in sorted(targets.items()):
                if not tm.modes:
                    tm.modes = ["CAD"]
                t_list.append(tm)
            result.append(ScopeProjectModel(name=proj, targets=t_list))

        return result

    def _resolve_provider(self, project: str) -> Optional[Provider]:
        """Resolve a Provider instance for a project name."""
        for p in getattr(self.manager.router, "providers", []):
            if p.name == project:
                return p
        return None

    def load_geometry(
        self,
        project: str,
        target: str,
        subassembly: Optional[str] = None,
        mode: str = "CAD",
        step_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Load and tessellate 3D geometry for a given target and mode with disk cache backing.

        Returns wire message dictionary containing shapes, states, config, and PCB metadata.
        """
        if project == "cat_fountain" and target == "simulation":
            target = "product"
            mode = "SIMULATE"

        subassembly = self._normalize_subassembly(subassembly)
        mode_upper = mode.upper()
        cache_key = (project, target, subassembly, mode_upper, step_index)

        # 1. Fast in-memory cache check & thread synchronization
        with self._lock:
            if cache_key in self._cache:
                self.log.info("Memory cache hit for geometry %s/%s [%s]", project, target, mode_upper)
                return self._cache[cache_key]

            if cache_key in self._in_progress:
                wait_event = self._in_progress[cache_key]
            else:
                wait_event = None
                self._in_progress[cache_key] = threading.Event()

        if wait_event is not None:
            # Another thread (such as background pre-warm) is already compiling; wait for it
            wait_event.wait(timeout=180.0)
            with self._lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

        # 2. Fast disk cache check
        cache_file = self._get_cache_path(project, target, subassembly, mode_upper, step_index)
        if self._is_cache_valid(cache_file, project):
            try:
                t0_disk = time.time()
                gz_bytes = cache_file.read_bytes()
                decomp = gzip.decompress(gz_bytes)
                payload = orjson.loads(decomp)
                with self._lock:
                    self._cache[cache_key] = payload
                    self._gz_cache[cache_key] = gz_bytes
                    if wait_event is None and cache_key in self._in_progress:
                        self._in_progress.pop(cache_key).set()
                self.log.info(
                    "Disk cache hit for %s/%s [%s] in %.3fs (%.2f MB compressed)",
                    project,
                    target,
                    mode_upper,
                    time.time() - t0_disk,
                    len(gz_bytes) / (1024 * 1024),
                )
                return payload
            except Exception as err:
                self.log.warning("Failed reading disk cache %s: %s", cache_file, err)

        try:
            # 3. Full compilation and tessellation
            t0 = time.time()
            self.log.info(
                "Resolving and compiling geometry for %s/%s [%s] (subassembly: %s, step: %s)...",
                project,
                target,
                mode_upper,
                subassembly,
                step_index,
            )

            display_items: List[Tuple[Any, str, Optional[Tuple[float, float, float]], float]] = []
            pcb_metadata: Optional[Dict[str, Any]] = None
            view_from: Optional[str] = "top" if mode_upper == "DIAGRAM" else None

            provider = self._resolve_provider(project)
            full_target = f"{project}/{target}"
            if subassembly and subassembly != target:
                full_target = f"{full_target}:{subassembly}"

            if mode_upper == "PCB" and provider and getattr(provider, "pcb_config", None):
                # Specialized multi-layer PCB extraction
                from model.wiring import Wiring
                from provider.pcb.exporter import PCBExporter

                sub_param = subassembly or (target if target != project else None)
                wiring = provider.wiring

                solid = None
                sub_pcb_config = None
                item_name = f"{provider.name}_{sub_param or provider.name}_pcb"

                if sub_param and hasattr(provider, "part") and sub_param in provider.part:
                    part_func = provider.part[sub_param]
                    part_res = part_func(sub_param, None, Mode.DEFAULT)
                    solid = getattr(part_res, "part", part_res)
                    if hasattr(part_res, "to_pcb_config"):
                        sub_pcb_config = part_res.to_pcb_config()
                    elif hasattr(part_res, "pcb_metadata"):
                        sub_pcb_config = part_res.pcb_metadata

                pcb_cfg = resolve_subassembly_pcb_config(sub_pcb_config, provider.pcb_config, subassembly=sub_param)

                if solid is None:
                    exporter = PCBExporter(pcb_cfg, wiring, subassembly=sub_param, design_rules=pcb_cfg.design_rules)
                    solid = exporter.build_solid()

                # Canonical soldermask color
                color_map = {
                    "matte_black": (0.06, 0.08, 0.07),
                    "black": (0.06, 0.08, 0.07),
                    "green": (0.04, 0.18, 0.08),
                    "blue": (0.10, 0.25, 0.65),
                    "red": (0.65, 0.10, 0.10),
                    "white": (0.90, 0.90, 0.90),
                    "purple": (0.45, 0.15, 0.55),
                }
                substrate_color = color_map.get(
                    pcb_cfg.stackup.soldermask_color.lower()
                    if pcb_cfg.stackup and getattr(pcb_cfg.stackup, "soldermask_color", None)
                    else "green",
                    (0.04, 0.18, 0.08),
                )

                assembler = PCB3DAssembler(
                    pcb_config=pcb_cfg,
                    wiring=wiring,
                    substrate=solid,
                    substrate_color=substrate_color,
                    pcb_name=item_name,
                )
                # Tessellate ONLY the substrate solid in Mode.PCB (~1,000 triangles vs ~1.33M B-rep copper triangles);
                # copper traces, pads, vias, and silkscreen are rendered at 60-120 FPS via GPU SDF instancing & Retina Canvas2D.
                substrate_geom = assembler.build_substrate() or solid
                display_items.append(
                    (substrate_geom, f"{item_name}_substrate", PCB3DAssembler.KICAD_SUBSTRATE_COLOR, 1.0)
                )

                # Build complete PCB metadata for GPU SDF instancing, Retina silkscreen, and $O(1)$ spatial grid hit-testing
                from model.pcb import BoardType
                from provider.footprints import FOOTPRINT_REGISTRY

                target_ref = getattr(pcb_cfg, "shape_ref", None)
                is_flex = getattr(pcb_cfg, "board_type", None) == BoardType.FLEX or "flex" in item_name.lower()

                all_footprints = list(getattr(wiring, "footprints", []) or []) if wiring else []
                if not all_footprints and getattr(pcb_cfg, "footprints", None):
                    all_footprints = list(pcb_cfg.footprints)

                footprints = []
                for fp in all_footprints:
                    fp_shape = getattr(fp, "shape_ref", None)
                    if target_ref:
                        if fp_shape == target_ref or (not fp_shape and not is_flex):
                            footprints.append(fp)
                    elif not is_flex or fp_shape:
                        footprints.append(fp)

                comps = []
                for c in footprints:
                    fp_factory = FOOTPRINT_REGISTRY.get(c.package)
                    fp_inst = fp_factory() if fp_factory else None
                    if fp_inst and getattr(fp_inst, "part", None):
                        bb = fp_inst.part.bounding_box()
                        dx = round(bb.size.X, 3)
                        dy = round(bb.size.Y, 3)
                    elif getattr(c, "dimensions", None):
                        dims = c.dimensions
                        dx, dy = round(dims[0], 3), round(dims[1], 3)
                    else:
                        dx, dy = 3.0, 3.0

                    comps.append(
                        {
                            "name": getattr(c, "name", ""),
                            "ref_des": getattr(c, "name", ""),
                            "footprint": getattr(c, "package", ""),
                            "value": str(getattr(c, "value", "") or ""),
                            "mpn": str(getattr(c, "mpn", "") or ""),
                            "side": "B.Cu"
                            if (getattr(c, "layer", "F.Cu") == "B.Cu" or c.position[2] < 0.0)
                            else "F.Cu",
                            "position": [round(c.position[0], 3), round(c.position[1], 3), round(c.position[2], 3)],
                            "size": [dx, dy],
                            "yaw": round(c.rotation[2], 2),
                        }
                    )

                traces_data = [
                    {
                        "start": [round(t.start_mm[0], 3), round(t.start_mm[1], 3)],
                        "end": [round(t.end_mm[0], 3), round(t.end_mm[1], 3)],
                        "width": round(t.width_mm, 3),
                        "layer": t.layer,
                        "net": t.net,
                    }
                    for t in getattr(pcb_cfg, "traces", [])
                ]

                vias_data = [
                    {
                        "pos": [round(v.position_mm[0], 3), round(v.position_mm[1], 3)],
                        "drill": round(v.drill_diameter_mm, 3),
                        "pad": round(v.pad_diameter_mm, 3),
                        "layer_start": getattr(v, "layer_start", "F.Cu"),
                        "layer_end": getattr(v, "layer_end", "B.Cu"),
                        "net": v.net,
                    }
                    for v in getattr(pcb_cfg, "vias", [])
                ]

                test_points_data = []
                for tp in getattr(pcb_cfg, "test_points", []):
                    tp_shape = getattr(tp, "shape_ref", None)
                    if target_ref:
                        if tp_shape != target_ref and (tp_shape or is_flex):
                            continue
                    elif is_flex and not tp_shape:
                        continue
                    test_points_data.append(
                        {
                            "name": getattr(tp, "name", "TP"),
                            "net": getattr(tp, "net", "GND"),
                            "x": round(float(tp.position_mm[0]), 3),
                            "y": round(float(tp.position_mm[1]), 3),
                            "dia": round(float(tp.pad_diameter_mm), 3),
                            "drill": round(float(getattr(tp, "drill_diameter_mm", 0.0) or 0.0), 3),
                            "layer": getattr(tp, "layer", "F.Cu"),
                            "label": getattr(tp, "label", None) or getattr(tp, "name", "TP"),
                        }
                    )

                # Map pin to net
                pin_net_map = {}
                if wiring and hasattr(wiring, "nets"):
                    for n in wiring.nets:
                        for p in getattr(n, "pins", []):
                            if isinstance(p, (tuple, list)) and len(p) >= 2:
                                pin_net_map[f"{p[0]}.{p[1]}"] = n.name
                            elif hasattr(p, "component") and hasattr(p, "pin"):
                                pin_net_map[f"{p.component}.{p.pin}"] = n.name

                pads_data = []
                for c in footprints:
                    cx, cy, cz = c.position
                    comp_layer = "B.Cu" if (getattr(c, "layer", "F.Cu") == "B.Cu" or cz < 0.0) else "F.Cu"
                    yaw = float(c.rotation[2])
                    rad = math.radians(yaw)
                    cos_a = math.cos(rad)
                    sin_a = math.sin(rad)
                    fp_factory = FOOTPRINT_REGISTRY.get(c.package)
                    if fp_factory:
                        fp_inst = fp_factory()
                        for p in fp_inst.pins:
                            px, py = p.position[0], p.position[1]
                            wx = cx + px * cos_a - py * sin_a
                            wy = cy + px * sin_a + py * cos_a
                            pw, ph = p.pad_size_mm
                            pin_id = f"{c.name}.{p.name}"
                            raw_shape = getattr(p, "pad_shape", "roundrect")
                            pad_shape = str(getattr(raw_shape, "value", raw_shape)).lower()
                            raw_type = getattr(p, "pad_type", "smd")
                            pad_type = str(getattr(raw_type, "value", raw_type)).lower()
                            drill_mm = round(float(getattr(p, "drill_dia_mm", 0.0) or 0.0), 3)
                            pads_data.append(
                                {
                                    "x": round(wx, 3),
                                    "y": round(wy, 3),
                                    "w": round(pw, 3),
                                    "h": round(ph, 3),
                                    "rot_deg": round(yaw, 2),
                                    "shape": pad_shape,
                                    "pad_type": pad_type,
                                    "drill": drill_mm,
                                    "comp": c.name,
                                    "pin": p.name,
                                    "number": str(p.number) if getattr(p, "number", None) is not None else str(p.name),
                                    "net": pin_net_map.get(pin_id, ""),
                                    "layer": comp_layer,
                                }
                            )

                for cap in getattr(pcb_cfg, "capacitive_sensors", []):
                    cap_shape = getattr(cap, "shape_ref", None)
                    if target_ref:
                        if cap_shape != target_ref and (cap_shape or is_flex):
                            continue
                    elif is_flex and not cap_shape:
                        continue
                    center = cap.center_mm or (0.0, 0.0)
                    pads_data.append(
                        {
                            "x": round(float(center[0]), 3),
                            "y": round(float(center[1]), 3),
                            "w": round(float(cap.area_mm[0]), 3),
                            "h": round(float(cap.area_mm[1]), 3),
                            "rot_deg": 0.0,
                            "shape": "rect",
                            "pad_type": "smd",
                            "drill": 0.0,
                            "comp": getattr(cap, "name", "CAP"),
                            "pin": "1",
                            "number": "1",
                            "net": getattr(cap, "net", ""),
                            "layer": getattr(cap, "layer", "F.Cu"),
                            "is_sensor": True,
                        }
                    )

                for tp in test_points_data:
                    pads_data.append(
                        {
                            "x": tp["x"],
                            "y": tp["y"],
                            "w": tp["dia"],
                            "h": tp["dia"],
                            "rot_deg": 0.0,
                            "shape": "circle",
                            "pad_type": "thru_hole" if tp["drill"] > 0.0 else "smd",
                            "comp": tp["name"],
                            "pin": "1",
                            "number": "1",
                            "net": tp["net"],
                            "layer": tp["layer"],
                            "is_test_point": True,
                            "dia": tp["dia"],
                            "drill": tp["drill"],
                        }
                    )

                silkscreen_texts_data = []
                existing_top_texts = set()
                existing_bot_texts = set()
                for st in getattr(pcb_cfg, "silkscreen_texts", []):
                    st_layer = getattr(st, "layer", "F.SilkS")
                    st_text = str(getattr(st, "text", ""))
                    if st_layer == "B.SilkS":
                        existing_bot_texts.add(st_text)
                    else:
                        existing_top_texts.add(st_text)
                    silkscreen_texts_data.append(
                        {
                            "text": st_text,
                            "layer": st_layer,
                            "x": round(float(st.position[0]), 3),
                            "y": round(float(st.position[1]), 3),
                            "font_size": round(float(getattr(st, "font_size", 0.8) or 0.8), 3),
                            "rotation": round(float(getattr(st, "rotation", 0.0) or 0.0), 2),
                            "mirror": bool(getattr(st, "mirror", False)),
                        }
                    )

                omitted_designators = set(getattr(pcb_cfg, "omitted_silkscreen_designators", []) or [])
                for comp_entry in comps:
                    ref_des = comp_entry["ref_des"]
                    if not ref_des or ref_des in omitted_designators:
                        continue
                    is_bot = comp_entry["side"] == "B.Cu"
                    silk_layer = "B.SilkS" if is_bot else "F.SilkS"
                    known = existing_bot_texts if is_bot else existing_top_texts
                    if ref_des in known:
                        continue
                    cx, cy = comp_entry["position"][0], comp_entry["position"][1]
                    silkscreen_texts_data.append(
                        {
                            "text": ref_des,
                            "layer": silk_layer,
                            "x": round(float(cx), 3),
                            "y": round(float(cy - 1.5), 3),
                            "font_size": 0.8,
                            "rotation": 0.0,
                            "mirror": is_bot,
                            "is_ref_des": True,
                        }
                    )

                silkscreen_graphics_data = []
                for sg in getattr(pcb_cfg, "silkscreen_graphics", []):
                    pts = getattr(sg, "points", None)
                    silkscreen_graphics_data.append(
                        {
                            "layer": getattr(sg, "layer", "F.SilkS"),
                            "shape": getattr(sg, "shape", "rect"),
                            "position": [round(float(sg.position[0]), 3), round(float(sg.position[1]), 3)],
                            "dimensions": [round(float(sg.dimensions[0]), 3), round(float(sg.dimensions[1]), 3)],
                            "thickness": round(float(getattr(sg, "thickness", 0.15) or 0.15), 3),
                            "fill": bool(getattr(sg, "fill", False)),
                            "points": [[round(float(pt[0]), 3), round(float(pt[1]), 3)] for pt in pts] if pts else [],
                        }
                    )

                net_trace_counts = {}
                net_layers = {}
                for t in traces_data:
                    net_trace_counts[t["net"]] = net_trace_counts.get(t["net"], 0) + 1
                    net_layers.setdefault(t["net"], set()).add(t["layer"])

                net_via_counts = {}
                for v in vias_data:
                    net_via_counts[v["net"]] = net_via_counts.get(v["net"], 0) + 1

                nets = []
                if wiring and hasattr(wiring, "nets"):
                    for n in wiring.nets:
                        raw_pins = getattr(n, "pins", [])
                        pin_strings = []
                        for p in raw_pins:
                            if isinstance(p, (tuple, list)) and len(p) >= 2:
                                pin_strings.append(f"{p[0]}.{p[1]}")
                            elif hasattr(p, "component") and hasattr(p, "pin"):
                                pin_strings.append(f"{p.component}.{p.pin}")
                            else:
                                pin_strings.append(str(p))
                        nets.append(
                            {
                                "name": getattr(n, "name", ""),
                                "color": getattr(n, "color", "#ffcc00"),
                                "pins": pin_strings,
                                "traces_count": net_trace_counts.get(getattr(n, "name", ""), 0),
                                "vias_count": net_via_counts.get(getattr(n, "name", ""), 0),
                                "layers": sorted(list(net_layers.get(getattr(n, "name", ""), []))),
                            }
                        )

                pcb_metadata = {
                    "render_version": self.PCB_METADATA_RENDER_VERSION,
                    "board_thickness_mm": round(float(assembler.total_thickness), 3),
                    "z_top_mm": round(float(assembler.z_top), 3),
                    "z_bottom_mm": round(float(assembler.z_bottom), 3),
                    "layers": [
                        {"id": f"{item_name}_substrate", "name": "Substrate", "color": "#041830", "type": "Substrate"},
                        {"id": f"{item_name}_pads", "name": "Pads", "color": "#ce4785", "type": "Pads"},
                        {"id": f"{item_name}_traces_top", "name": "F.Cu (Top)", "color": "#c83434", "type": "F.Cu"},
                        {
                            "id": f"{item_name}_traces_bottom",
                            "name": "B.Cu (Bottom)",
                            "color": "#4d7fc4",
                            "type": "B.Cu",
                        },
                        {"id": f"{item_name}_vias", "name": "Vias", "color": "#ececec", "type": "Vias"},
                        {"id": f"{item_name}_silkscreen_top", "name": "F.SilkS", "color": "#f2eda1", "type": "F.SilkS"},
                        {
                            "id": f"{item_name}_silkscreen_bottom",
                            "name": "B.SilkS",
                            "color": "#e8b2a7",
                            "type": "B.SilkS",
                        },
                    ],
                    "components": comps,
                    "nets": nets,
                    "traces": traces_data,
                    "vias": vias_data,
                    "pads": pads_data,
                    "test_points": test_points_data,
                    "silkscreen_texts": silkscreen_texts_data,
                    "silkscreen_graphics": silkscreen_graphics_data,
                }

            elif mode_upper == "DIAGRAM":
                parsed_targets = self.target_parser.resolve(full_target, Section.DIAGRAM)
                results = self.manager.router.run(parsed_targets)
                for p_name, room in results:
                    if isinstance(room, Room):
                        options = getattr(room, "diagram_options", None)
                        if options is None:
                            prov = next((p for p in self.manager.router.providers if p.name == p_name), None)
                            if prov:
                                options = getattr(prov.settings, "diagram_options", None)
                        if options and getattr(options, "view_from", None):
                            view_from = str(options.view_from).lower()

                    display_items.append(
                        (room.compound if isinstance(room, Room) else room, f"{p_name}_diagram", None, 1.0)
                    )

                    # Project and append diagram text annotation labels so they render in 3D viewport
                    if hasattr(room, "_project_labels") and hasattr(room, "_labels") and room._labels:
                        labels = room._project_labels(Plane.XY)
                        if labels:
                            display_items.append((Compound(children=labels), f"{p_name}_labels", (0.0, 0.0, 0.0), 1.0))

            else:
                # Default CAD mode (VIEW or PART)
                section = Section.VIEW if mode_upper in ("CAD", "SIMULATE") else Section.PART
                try:
                    parsed_targets = self.target_parser.resolve(full_target, section)
                except ValueError:
                    parsed_targets = self.target_parser.resolve(full_target, Section.PART)

                if parsed_targets:
                    results = self.manager.router.run(parsed_targets)
                    subs = (
                        set(parsed_targets.subassemblies) if getattr(parsed_targets, "subassemblies", None) else set()
                    )
                    for room_name, room_or_geom in results:
                        if isinstance(room_or_geom, Room):
                            for item_name, (geom, rgba) in room_or_geom.items():
                                if subs and not any(sub in item_name or item_name in sub for sub in subs):
                                    continue
                                name = item_name if len(results) == 1 else f"{room_name}/{item_name}"
                                display_items.append((geom, name, rgba[:3], rgba[3]))
                        else:
                            rgba = self.manager.router.get_color(room_name, subassembly)
                            display_items.append((room_or_geom, room_name, rgba[:3], rgba[3]))

            if not display_items:
                raise ValueError(f"No geometry found for target '{full_target}' in mode '{mode}'.")

            cad_objs = [it[0] for it in display_items]
            names = [it[1] for it in display_items]
            colors = [it[2] for it in display_items]
            alphas = [it[3] for it in display_items]

            # Convert and tessellate
            if CoreViewer is None:
                raise RuntimeError("ocp_viewer_core is not installed or available.")

            core_v = CoreViewer(ocp_config)
            wire_msg, mapping = core_v._convert(*cad_objs, names=names, colors=colors, alphas=alphas)

            shapes = wire_msg.get("data", {}).get("shapes", {})
            config_data = wire_msg.get("config", {})
            config_data["reset_camera"] = "RESET"
            instances = wire_msg.get("data", {}).get("instances", [])

            payload = {
                "type": "data",
                "shapes": shapes,
                "config": config_data,
                "instances": instances,
                "pcb_metadata": pcb_metadata,
                "target": full_target,
                "project": project,
                "mode": mode_upper,
                "view_from": view_from,
                "stats": {
                    "parts_count": len(shapes.get("parts", [])),
                    "bb": shapes.get("bb"),
                },
            }

            duration = time.time() - t0
            self.log.info(
                "Geometry %s [%s] tessellated in %.2fs (%d parts, %d instances, bounds: %s)",
                full_target,
                mode_upper,
                duration,
                len(shapes.get("parts", [])),
                len(instances),
                payload["stats"]["bb"],
            )

            # Persist to disk cache and in-memory cache
            try:
                raw_bytes = orjson.dumps(payload, option=orjson.OPT_SERIALIZE_NUMPY)
                gz_bytes = gzip.compress(raw_bytes, compresslevel=6)
                with self._lock:
                    self._cache[cache_key] = payload
                    self._gz_cache[cache_key] = gz_bytes
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(gz_bytes)
                self.log.info(
                    "Persisted disk cache for %s/%s [%s] in %.2fs (%.2f MB compressed)",
                    project,
                    target,
                    mode_upper,
                    time.time() - t0,
                    len(gz_bytes) / (1024 * 1024),
                )
            except Exception as err:
                self.log.warning("Failed to persist disk cache: %s", err)
                with self._lock:
                    self._cache[cache_key] = payload

            return payload
        finally:
            if wait_event is None:
                with self._lock:
                    if cache_key in self._in_progress:
                        self._in_progress.pop(cache_key).set()

    @classmethod
    def _detect_voxel_lattice(cls, sample_positions_mm: np.ndarray, radius_mm: float) -> Tuple[bool, float]:
        """Detect whether 3D fluid centers lie on a regular cubic voxel lattice and compute exact voxel_dx_mm."""
        fallback_dx = round(float(radius_mm) / cls.VOXEL_RADIUS_RATIO_FALLBACK, 4)
        if sample_positions_mm.ndim != 2 or len(sample_positions_mm) < 8:
            return False, fallback_dx

        step_candidates: List[float] = []
        for axis in range(3):
            uniq = np.unique(np.round(sample_positions_mm[:, axis], 2))
            if len(uniq) < 2:
                continue
            diffs = np.diff(uniq)
            valid = diffs[diffs >= cls.MIN_VOXEL_LATTICE_STEP_MM]
            if len(valid) > 0:
                step_candidates.append(float(np.min(valid)))

        if not step_candidates:
            return False, fallback_dx

        candidate_dx = round(float(np.median(step_candidates)), 4)
        if candidate_dx <= 0.0:
            return False, fallback_dx

        rel_coords = (sample_positions_mm - sample_positions_mm[0]) / candidate_dx
        frac_err = np.abs(rel_coords - np.rint(rel_coords))
        inliers = np.all(frac_err <= cls.VOXEL_LATTICE_TOLERANCE_RATIO, axis=1)
        inlier_ratio = float(np.mean(inliers))
        if inlier_ratio >= cls.VOXEL_LATTICE_INLIER_FRACTION:
            return True, candidate_dx

        return False, round(2.0 * float(radius_mm), 4)

    def load_simulation_telemetry(self, project: str, target: str) -> Dict[str, Any]:
        """Extract undecimated binary fluid positions, voxel lattice metadata, kinematic transforms, and metrics."""
        cache_key = f"{project}_{target}_sim_telemetry_{self.SIM_TELEMETRY_CACHE_VERSION}"
        cache_file = self.cache_dir / f"{cache_key}.json.gz"

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        if cache_file.exists():
            try:
                raw = gzip.decompress(cache_file.read_bytes())
                data = orjson.loads(raw)
                with self._lock:
                    self._cache[cache_key] = data
                return data
            except Exception as err:
                self.log.warning("Failed to read telemetry cache for %s: %s", cache_key, err)

        recordings_dir = self.repo_root / "recordings"
        candidates = [
            recordings_dir / f"{project}_{target}.rrd",
            recordings_dir / f"{project}.rrd",
            recordings_dir / f"{project}_3blade.rrd",
        ]
        rrd_file: Optional[Path] = None
        for cand in candidates:
            if cand.exists():
                rrd_file = cand
                break

        if rrd_file is None and recordings_dir.exists():
            for f in sorted(recordings_dir.glob("*.rrd")):
                if project in f.name:
                    rrd_file = f
                    break

        if rrd_file is None:
            return {
                "status": "not_found",
                "recording": None,
                "frames_count": 0,
                "max_steps": 0,
                "frames": [],
                "metrics_series": {},
            }

        try:
            import rerun as rr

            reader = rr.bindings.RrdReaderInternal(str(rrd_file))
            chunks = reader.stream().to_chunks()

            particle_chunks = [c for c in chunks if c.entity_path.lstrip("/") == "world/particles"]
            metric_chunks = [c for c in chunks if c.entity_path.lstrip("/").startswith("metrics/")]
            transform_chunks = [
                c
                for c in chunks
                if c.entity_path.lstrip("/").startswith("world/") and c.entity_path.lstrip("/") != "world/particles"
            ]

            metrics_by_step: Dict[int, Dict[str, float]] = {}
            for c in metric_chunks:
                clean_path = c.entity_path.lstrip("/")
                m_name = clean_path[len("metrics/") :]
                rb = c.to_record_batch()
                if "step" not in rb.schema.names or "Scalars:scalars" not in rb.schema.names:
                    continue
                steps_list = rb["step"].to_pylist()
                vals_list = rb["Scalars:scalars"].to_pylist()
                for row_idx, raw_step in enumerate(steps_list):
                    if raw_step is None or not vals_list[row_idx]:
                        continue
                    step = int(raw_step)
                    val = float(vals_list[row_idx][0])
                    metrics_by_step.setdefault(step, {})[m_name] = val

            metrics_series: Dict[str, List[Dict[str, float]]] = {}
            for step, m_dict in sorted(metrics_by_step.items()):
                for m_name, val in m_dict.items():
                    metrics_series.setdefault(m_name, []).append({"step": step, "value": val})

            transforms_by_step: Dict[int, Dict[str, Dict[str, List[float]]]] = {}
            for c in transform_chunks:
                clean_path = c.entity_path.lstrip("/")
                link_name = clean_path[len("world/") :]
                if not link_name:
                    continue
                rb = c.to_record_batch()
                if "step" not in rb.schema.names:
                    continue
                has_trans = "Transform3D:translation" in rb.schema.names
                has_quat = "Transform3D:quaternion" in rb.schema.names
                if not has_trans and not has_quat:
                    continue
                steps_list = rb["step"].to_pylist()
                trans_list = rb["Transform3D:translation"].to_pylist() if has_trans else None
                quat_list = rb["Transform3D:quaternion"].to_pylist() if has_quat else None
                for row_idx, raw_step in enumerate(steps_list):
                    if raw_step is None:
                        continue
                    step = int(raw_step)
                    entry: Dict[str, List[float]] = {}
                    if trans_list is not None and trans_list[row_idx]:
                        t_vec = trans_list[row_idx][0]
                        entry["translation"] = [
                            round(float(t_vec[0]) * self.MM_PER_METER, 4),
                            round(float(t_vec[1]) * self.MM_PER_METER, 4),
                            round(float(t_vec[2]) * self.MM_PER_METER, 4),
                        ]
                    if quat_list is not None and quat_list[row_idx]:
                        q_vec = quat_list[row_idx][0]
                        entry["quaternion"] = [
                            round(float(q_vec[0]), 6),
                            round(float(q_vec[1]), 6),
                            round(float(q_vec[2]), 6),
                            round(float(q_vec[3]), 6),
                        ]
                    if entry:
                        transforms_by_step.setdefault(step, {})[link_name] = entry

            raw_frames: List[Tuple[int, np.ndarray, Optional[np.ndarray]]] = []
            radius_mm = self.DEFAULT_PARTICLE_RADIUS_MM
            uniform_u32_colors: set[int] = set()
            has_varying_colors = False

            for c in particle_chunks:
                rb = c.to_record_batch()
                step = int(rb["step"][0].as_py())
                pos_col = rb["Points3D:positions"]
                pos_mm = pos_col.values.values.to_numpy().reshape(-1, 3) * self.MM_PER_METER

                col_u32: Optional[np.ndarray] = None
                if "Points3D:colors" in rb.schema.names:
                    col_arr = rb["Points3D:colors"].values.to_numpy()
                    if len(col_arr) > 0:
                        first_c = int(col_arr[0])
                        if not has_varying_colors and bool(np.all(col_arr == col_arr[0])):
                            uniform_u32_colors.add(first_c)
                            if len(uniform_u32_colors) > 1:
                                has_varying_colors = True
                                col_u32 = col_arr
                        else:
                            has_varying_colors = True
                            col_u32 = col_arr

                if radius_mm == self.DEFAULT_PARTICLE_RADIUS_MM and "Points3D:radii" in rb.schema.names:
                    rad_arr = rb["Points3D:radii"].values.to_numpy()
                    if len(rad_arr) > 0:
                        radius_mm = round(float(rad_arr[0]) * self.MM_PER_METER, 3)

                raw_frames.append((step, pos_mm, col_u32))

            raw_frames.sort(key=lambda item: item[0])
            counts = [len(pos_mm) for _, pos_mm, _ in raw_frames if len(pos_mm) > 0]
            is_lagrangian = len(counts) > 0 and len(set(counts)) == 1

            first_non_empty = next((pos_mm for _, pos_mm, _ in raw_frames if len(pos_mm) > 0), np.empty((0, 3)))
            is_voxel_grid, voxel_dx_mm = self._detect_voxel_lattice(first_non_empty, radius_mm)

            default_color = list(self.DEFAULT_WATER_RGBA)
            if not has_varying_colors and len(uniform_u32_colors) == 1:
                u32 = next(iter(uniform_u32_colors))
                r_ch = ((u32 >> 24) & 0xFF) / 255.0
                g_ch = ((u32 >> 16) & 0xFF) / 255.0
                b_ch = ((u32 >> 8) & 0xFF) / 255.0
                a_ch = (u32 & 0xFF) / 255.0
                default_color = [round(r_ch, 4), round(g_ch, 4), round(b_ch, 4), round(a_ch, 4)]

            frames = []
            for step, pos_mm, col_u32 in raw_frames:
                pos_f32 = np.ascontiguousarray(pos_mm, dtype="<f4")
                positions_b64 = base64.b64encode(pos_f32.tobytes()).decode("ascii") if len(pos_f32) > 0 else ""

                frame_dict: Dict[str, Any] = {
                    "step": step,
                    "count": int(len(pos_f32)),
                    "positions_b64": positions_b64,
                    "metrics": dict(metrics_by_step.get(step, {})),
                    "transforms": dict(transforms_by_step.get(step, {})),
                }
                if has_varying_colors and col_u32 is not None and len(col_u32) == len(pos_f32):
                    rgb_u8 = np.column_stack(
                        [
                            (col_u32 >> 24) & 0xFF,
                            (col_u32 >> 16) & 0xFF,
                            (col_u32 >> 8) & 0xFF,
                        ]
                    ).astype(np.uint8)
                    frame_dict["colors_b64"] = base64.b64encode(np.ascontiguousarray(rgb_u8).tobytes()).decode("ascii")
                frames.append(frame_dict)

            payload = {
                "status": "ok",
                "recording": str(
                    rrd_file.relative_to(self.repo_root) if rrd_file.is_relative_to(self.repo_root) else rrd_file
                ),
                "encoding": "float32_b64",
                "is_lagrangian": is_lagrangian,
                "is_voxel_grid": is_voxel_grid,
                "voxel_dx_mm": voxel_dx_mm,
                "radius_mm": radius_mm,
                "default_color": default_color,
                "frames_count": len(frames),
                "max_steps": len(frames),
                "frames": frames,
                "metrics_series": metrics_series,
            }

            try:
                gz = gzip.compress(orjson.dumps(payload), compresslevel=6)
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(gz)
            except Exception as err:
                self.log.warning("Failed to persist telemetry cache: %s", err)

            with self._lock:
                self._cache[cache_key] = payload
            return payload
        except Exception as err:
            self.log.exception("Failed to parse simulation telemetry from %s: %s", rrd_file, err)
            return {"status": "error", "error": str(err), "frames_count": 0, "frames": [], "metrics_series": {}}
