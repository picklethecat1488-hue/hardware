"""Backend Geometry & Tessellation Pipeline for Interactive CAD/PCB Scope Workstation."""

from __future__ import annotations

import gzip
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import orjson
from pydantic import BaseModel, Field

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
    ScopeAnnotationModel,
    ScopeMarkupModel,
    ScopeProjectModel,
    ScopeTargetBugRequest,
    ScopeTargetModel,
)


class ScopeGeometryPipeline:
    """Manages project discovery, geometry resolution, and tessellation caching."""

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
                layer_items = assembler.get_display_items(prefix=item_name)
                if layer_items:
                    display_items.extend(layer_items)
                else:
                    display_items.append((solid, item_name, substrate_color, 1.0))

                # Build PCB metadata for KiCad inspector & net highlight
                from provider.footprints import FOOTPRINT_REGISTRY

                comps = []
                footprints = getattr(wiring, "footprints", []) if wiring else []
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
                            "side": getattr(c, "layer", "F.Cu"),
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

                # Map pin to net
                pin_net_map = {}
                if wiring and hasattr(wiring, "nets"):
                    for n in wiring.nets:
                        for p in getattr(n, "pins", []):
                            if isinstance(p, (tuple, list)) and len(p) >= 2:
                                pin_net_map[f"{p[0]}.{p[1]}"] = n.name
                            elif hasattr(p, "component") and hasattr(p, "pin"):
                                pin_net_map[f"{p.component}.{p.pin}"] = n.name

                from provider.footprints import FOOTPRINT_REGISTRY

                pads_data = []
                for c in footprints:
                    cx, cy, _ = c.position
                    yaw = c.rotation[2]
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
                            pads_data.append(
                                {
                                    "x": round(wx, 3),
                                    "y": round(wy, 3),
                                    "w": round(pw, 3),
                                    "h": round(ph, 3),
                                    "comp": c.name,
                                    "pin": p.name,
                                    "net": pin_net_map.get(pin_id, ""),
                                    "layer": getattr(c, "layer", "F.Cu"),
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
                    "layers": [
                        {"id": f"{item_name}_substrate", "name": "Substrate", "color": "#0a1c10", "type": "Substrate"},
                        {
                            "id": f"{item_name}_components",
                            "name": "Components",
                            "color": "#1e2229",
                            "type": "Components",
                        },
                        {"id": f"{item_name}_pads", "name": "Pads", "color": "#ffcc00", "type": "Pads"},
                        {"id": f"{item_name}_traces_top", "name": "F.Cu (Top)", "color": "#ff3333", "type": "F.Cu"},
                        {
                            "id": f"{item_name}_traces_bottom",
                            "name": "B.Cu (Bottom)",
                            "color": "#3366ff",
                            "type": "B.Cu",
                        },
                        {"id": f"{item_name}_vias", "name": "Vias", "color": "#e0a820", "type": "Vias"},
                        {"id": f"{item_name}_silkscreen_top", "name": "F.SilkS", "color": "#ffffff", "type": "F.SilkS"},
                        {
                            "id": f"{item_name}_silkscreen_bottom",
                            "name": "B.SilkS",
                            "color": "#ffffff",
                            "type": "B.SilkS",
                        },
                    ],
                    "components": comps,
                    "nets": nets,
                    "traces": traces_data,
                    "vias": vias_data,
                    "pads": pads_data,
                }

            elif mode_upper == "DIAGRAM":
                parsed_targets = self.target_parser.resolve(full_target, Section.DIAGRAM)
                results = self.manager.router.run(parsed_targets)
                for p_name, room in results:
                    display_items.append((room.compound, f"{p_name}_diagram", None, 1.0))
                    # Project and append diagram text annotation labels so they render in 3D viewport
                    if hasattr(room, "_project_labels") and hasattr(room, "_labels") and room._labels:
                        labels = room._project_labels(Plane.XY)
                        if labels:
                            display_items.append(
                                (Compound(children=labels), f"{p_name}_labels", (0.95, 0.95, 0.95), 1.0)
                            )

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
