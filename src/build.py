"""Orchestrate geometry generation and export for discovered projects."""

import argparse
import io
import hashlib
import yaml
import os
import sys
from typing import cast
from pathlib import Path
from daemon import DaemonClient
from model import AppConfig
from build123d import *  # type: ignore
from build123d import export_stl, export_brep, Shape  # type: ignore
from target_parser import TargetParser
from typing import Optional, Any, Sequence, Callable
from pydantic import validate_call
from provider import ProviderManager, Section, Mode, SUBASSEMBLIES, Room, URDFShape
import zipfile
import shutil
from shell import Logger
from concurrent.futures import ThreadPoolExecutor
import threading
from list import Lister

SPINNER_TEXT = "Building..."


class Builder:
    """Coordinates build actions and file exports using project providers."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize builder dependencies and measurements."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(enabled=False)
        self.target_parser = TargetParser(manager.router)
        self.lister = Lister(manager, self.logger)
        self.build_manifest: dict[str, dict[str, str]] = {"brep": {}, "file": {}}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor()
        template_path = Path(__file__).parent / "urdf_template.yaml"
        with open(template_path, "r") as f:
            templates = yaml.safe_load(f)
        self.robot_template = templates["robot_template"].strip()
        self.link_template = templates["link_template"].strip()
        self.joint_template = templates["joint_template"].strip()
        self.axis_limit_template = templates["axis_limit_template"].strip()

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    def _load_manifest(self, out_dir: str):
        """Load an existing build manifest from the output directory if not already loaded."""
        if getattr(self, "manifest_out_dir", None) == str(out_dir):
            return
        manifest_path = Path(out_dir) / "build_manifest.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    data = yaml.safe_load(f)
                    # Migrate old flat manifest format to nested format
                    if "brep" not in data and "sha1" not in data and "stl" not in data and "file" not in data:
                        self.build_manifest = {"brep": data, "file": {}}
                    else:
                        # Migrate legacy keys to 'file' if present in nested format
                        if "sha1" in data:
                            data["file"] = data.pop("sha1")
                        if "stl" in data:
                            data["file"] = data.pop("stl")
                        self.build_manifest = data
            except (yaml.YAMLError, OSError):
                pass
        self.manifest_out_dir = str(out_dir)

    def _save_manifest(self, out_dir: str):
        """Write the current build manifest to a YAML file in the output directory."""
        manifest_path = Path(out_dir) / "build_manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(self.build_manifest, f, sort_keys=False)

    def _get_part_hash(self, part: Part) -> str:
        """Calculate a stable hash for a build123d Part using its BREP representation."""
        # Use BREP for hashing because it is faster to generate and
        # provides a more stable geometric identity than a mesh.
        with io.BytesIO() as brep_stream:
            export_brep(part, brep_stream)
            return hashlib.sha1(brep_stream.getvalue()).hexdigest()

    def _get_diagram_hash(self, room: Room, options: Any) -> str:
        """Calculate a hash for the diagram based on its room contents and options."""
        hasher = hashlib.sha1()

        # 1. Hash the geometry using BREP representation
        try:
            with io.BytesIO() as brep_stream:
                export_brep(room.compound, brep_stream)
                hasher.update(brep_stream.getvalue())
        except Exception:
            # Fallback to key/item count representation if export_brep fails
            hasher.update(str(sorted(room.keys())).encode("utf-8"))

        # 2. Hash the labels
        sorted_labels = sorted(getattr(room, "_labels", []), key=lambda x: x[0])
        labels_str = str(
            [
                (name, text, (loc.X, loc.Y, loc.Z) if hasattr(loc, "X") else tuple(loc), repr(opts))
                for name, text, loc, opts in sorted_labels
            ]
        )
        hasher.update(labels_str.encode("utf-8"))

        # 3. Hash options representation
        if options:
            opts_dict = (
                options.model_dump(mode="json") if hasattr(options, "model_dump") else getattr(options, "__dict__", {})
            )
            hasher.update(str(sorted(opts_dict.items())).encode("utf-8"))

        return hasher.hexdigest()

    def _get_urdf_hash(self, room: Room, p_name: str) -> str:
        """Calculate a hash for the URDF output."""
        with io.StringIO() as urdf_stream:
            room.export_urdf(urdf_stream, p_name)
            return hashlib.sha1(urdf_stream.getvalue().encode("utf-8")).hexdigest()

    def _get_file_hash(self, path: Path) -> str:
        """Calculate the SHA1 hash of a file on disk."""
        return hashlib.sha1(path.read_bytes()).hexdigest()

    def _export_obj(self, shape: Shape, file_path: str, tolerance: float = 0.1, scale: float = 1.0) -> bool:
        """Export build123d shape to OBJ format."""
        from OCP.BRepTools import BRepTools
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.BRep import BRep_Tool
        from OCP.TopLoc import TopLoc_Location

        if shape.wrapped is not None:
            BRepTools.Clean_s(shape.wrapped)
            BRepMesh_IncrementalMesh(shape.wrapped, tolerance, False, 0.1, True)

        vertices: list[Vector] = []
        triangles: list[tuple[int, int, int]] = []
        offset = 0

        for face in shape.faces():
            loc = TopLoc_Location()
            poly = BRep_Tool.Triangulation_s(face.wrapped, loc)
            if poly is None:
                continue

            trsf = loc.Transformation()
            face_nodes = [
                Vector(
                    float(poly.Node(i).Transformed(trsf).X()),
                    float(poly.Node(i).Transformed(trsf).Y()),
                    float(poly.Node(i).Transformed(trsf).Z()),
                )
                for i in range(1, poly.NbNodes() + 1)
            ]
            vertices.extend(face_nodes)

            for i in range(1, poly.NbTriangles() + 1):
                tri = poly.Triangle(i)
                n1, n2, n3 = tri.Get()
                triangles.append((n1 - 1 + offset, n2 - 1 + offset, n3 - 1 + offset))

            offset += poly.NbNodes()

        with open(file_path, "w") as f:
            f.write("# Exported by build.py\n")
            f.write(f"# Vertices: {len(vertices)}, Triangles: {len(triangles)}\n")

            # Write scaled vertices
            for v in vertices:
                f.write(f"v {v.X * scale:.6f} {v.Y * scale:.6f} {v.Z * scale:.6f}\n")

            # OBJ syntax links normals directly to face formatting: f v1//vn1 v2//vn2 v3//vn3
            for t in triangles:
                # Get the 3 vertices for the triangle face
                v0 = vertices[t[0]]
                v1 = vertices[t[1]]
                v2 = vertices[t[2]]

                # Cross product to find face perpendicular normal vector
                edge1 = Vector(v1.X - v0.X, v1.Y - v0.Y, v1.Z - v0.Z)
                edge2 = Vector(v2.X - v0.X, v2.Y - v0.Y, v2.Z - v0.Z)
                normal = edge1.cross(edge2)

                if normal.length > 1e-6:
                    normal = normal.normalized()

                f.write(f"vn {normal.X:.6f} {normal.Y:.6f} {normal.Z:.6f}\n")

            # Write faces referencing 1-based indexing
            for i, t in enumerate(triangles):
                norm_idx = i + 1  # 1-based indexing for normals
                v1 = t[0] + 1
                v2 = t[1] + 1
                v3 = t[2] + 1
                f.write(f"f {v1}//{norm_idx} {v2}//{norm_idx} {v3}//{norm_idx}\n")

        return True

    def _export_stl_cleaned(
        self,
        shape: Shape,
        file_path: str,
        tolerance: float = 0.001,
        angular_tolerance: float = 0.03,
    ) -> bool:
        """Clean cached OpenCASCADE mesh and export to STL with high resolution settings."""
        from OCP.BRepTools import BRepTools

        if shape.wrapped is not None:
            BRepTools.Clean_s(shape.wrapped)
        return export_stl(shape, file_path, tolerance=tolerance, angular_tolerance=angular_tolerance)

    def _export_single_part_formats(
        self,
        part: Shape,
        out_dir: str,
        export_types: Sequence[str],
        part_outputs: Sequence[str],
        current_hash: str,
        force_update: bool,
    ) -> None:
        """Export all requested formats (STL, OBJ) for a single part sequentially."""
        for export_type in export_types:
            if export_type == "obj":
                obj_file_name = next(p for p in part_outputs if p.endswith(".obj"))
                obj_path = Path(out_dir) / obj_file_name
                obj_path.parent.mkdir(parents=True, exist_ok=True)
                self._export_if_changed(
                    obj_path,
                    obj_file_name,
                    current_hash,
                    lambda p=obj_path: self._export_obj(part, str(p), scale=1.0),
                    force_update,
                )
            elif export_type == "stl":
                mesh_file_name = next(p for p in part_outputs if p.endswith(".stl"))
                path_obj = Path(out_dir) / mesh_file_name
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                path_str = str(path_obj)
                self._export_if_changed(
                    path_obj,
                    mesh_file_name,
                    current_hash,
                    lambda ps=path_str: self._export_stl_cleaned(part, ps),
                    force_update,
                )

    def _export_if_changed(
        self,
        path: Path,
        manifest_key: str,
        current_hash: str,
        export_fn: Callable[[], Any],
        force_update: bool = False,
    ):
        """Register hash in manifest and export content only if it has changed."""
        # Return early if the hash matches the manifest and the file exists.
        with self.lock:
            brep_manifest = self.build_manifest.setdefault("brep", {})
            file_manifest = self.build_manifest.setdefault("file", {})

            if not force_update and brep_manifest.get(manifest_key) == current_hash and path.exists():
                if manifest_key not in file_manifest:
                    file_manifest[manifest_key] = self._get_file_hash(path)
                return

        # Perform the actual export (heavy meshing/writing) outside the lock
        export_fn()

        # Update the manifest and print to log inside the lock
        with self.lock:
            brep_manifest = self.build_manifest.setdefault("brep", {})
            file_manifest = self.build_manifest.setdefault("file", {})
            brep_manifest[manifest_key] = current_hash
            file_manifest[manifest_key] = self._get_file_hash(path)
            self.logger.print(f"Saved {path}", symbol="📄")

    def _resolve_subassemblies(self, targets: Any, base_subs: Any) -> Sequence[str]:
        """Determine which subassemblies should be built for a target."""
        if base_subs:
            return base_subs
        else:
            all_subs = set()
            for target in targets:
                manifest = self.manager.router.manifest.get(target, {})
                action_cfg = manifest.get(Section.PART, {})
                target_subs = action_cfg.get(SUBASSEMBLIES, [])
                all_subs.update(target_subs)
            return sorted(list(all_subs))

    @validate_call(config={"arbitrary_types_allowed": True})
    def _export_parts(self, out_dir: str, batch_results: Any, sub: Optional[str] = None, force_update: bool = False):
        """Export parts from a batch run."""
        futures = []
        for name, results in batch_results:
            # Results is either a single geometry or a list of geometries
            res_list = results if isinstance(results, list) else [results]
            for geom in res_list:
                p_name, _ = TargetParser.split_target(name)

                # Create provider-specific subdirectory
                target_dir = Path(out_dir) / p_name
                target_dir.mkdir(parents=True, exist_ok=True)

                # Resolve export types from manifest
                export_types = self.manager.router.get_export_types(name, sub)

                if geom.part:
                    current_hash = self._get_part_hash(geom.part)
                    part_outputs = self.lister.get_part_outputs(name, sub)

                    futures.append(
                        self.executor.submit(
                            self._export_single_part_formats,
                            geom.part,
                            out_dir,
                            export_types,
                            part_outputs,
                            current_hash,
                            force_update,
                        )
                    )

        # Wait for all submitted exports to complete
        for fut in futures:
            fut.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_parts(self, out_dir, names: list[str] | None = None, force_update: Optional[bool] = None):
        """Export STL files for generated parts."""
        if force_update is None:
            force_update = bool(names)
        if names:
            target_lists = []
            for name in names:
                # Only resolve targets that are intended for the PART action
                if self.target_parser.parse(name, Section.PART) and self.target_parser.can_resolve(name, Section.PART):
                    target_lists.append(self.target_parser.resolve(name, Section.PART))
                elif ":" in name and self.target_parser.parse(name, Section.PART):
                    target_lists.append(self.target_parser.resolve(name, Section.PART))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.PART).for_modes([Mode.PRINT])]

        if not target_lists:
            return

        for base_targets in target_lists:
            self.logger.print(
                f"Compiling {Section.PART}s: {self._get_summary(list(base_targets))}",
                symbol="🛠️ ",
            )
            has_base_targets: set[str] = set(base_targets)

            # Run targets which have subassemblies, then run any remaining base targets.
            for sub in self._resolve_subassemblies(base_targets, base_targets.subassemblies):
                run_targets = base_targets.for_subassemblies([sub])
                batch_results = self.manager.router.run(run_targets)
                self._export_parts(out_dir, batch_results, sub=sub, force_update=force_update)
                for t in run_targets:
                    has_base_targets.discard(t)

            if has_base_targets:
                batch_results = self.manager.router.run(base_targets.for_targets(has_base_targets))
                self._export_parts(out_dir, batch_results, force_update=force_update)

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_diagram(self, out_dir, names: list[str] | None = None, force_update: Optional[bool] = None):
        """Export an exploded diagram for the parts."""
        if force_update is None:
            force_update = bool(names)
        if names:
            target_lists = []
            for name in names:
                # Only resolve targets that are intended for the DIAGRAM action
                if self.target_parser.parse(name, Section.DIAGRAM) and self.target_parser.can_resolve(
                    name, Section.DIAGRAM
                ):
                    target_lists.append(self.target_parser.resolve(name, Section.DIAGRAM))
                elif ":" in name and self.target_parser.parse(name, Section.DIAGRAM):
                    target_lists.append(self.target_parser.resolve(name, Section.DIAGRAM))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.DIAGRAM).for_modes([Mode.DEFAULT])]

        if not target_lists:
            return

        futures = []
        for base_targets in target_lists:
            self.logger.print(
                f"Compiling {Section.DIAGRAM}s: {self._get_summary(list(base_targets))}",
                symbol="🛠️ ",
            )
            for target in base_targets:
                single_target_list = base_targets.for_targets([target])
                results = self.manager.router.run(single_target_list)

                for p_name, room in results or []:
                    diagram_file = self.lister.get_diagram_output(target)
                    path_obj = Path(out_dir) / diagram_file
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    path_str = str(path_obj)

                    provider = next((p for p in self.manager.router.providers if p.name == p_name), None)
                    options = getattr(provider.settings, "diagram_options", None) if provider else None

                    current_hash = self._get_diagram_hash(room, options)
                    futures.append(
                        self.executor.submit(
                            self._export_if_changed,
                            path_obj,
                            diagram_file,
                            current_hash,
                            lambda r=room, ps=path_str, o=options: r.export_diagram(ps, o),
                            force_update,
                        )
                    )

        # Wait for all submitted diagram exports to complete
        for fut in futures:
            fut.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_urdfs(self, out_dir, names: list[str] | None = None, force_update: Optional[bool] = None):
        """Export combined URDF/OBJ assets from views that support simulate mode."""
        if force_update is None:
            force_update = bool(names)
        if names:
            target_lists = []
            for name in names:
                if self.target_parser.parse(name, Section.VIEW) and self.target_parser.can_resolve(name, Section.VIEW):
                    target_lists.append(self.target_parser.resolve(name, Section.VIEW))
                elif ":" in name and self.target_parser.parse(name, Section.VIEW):
                    target_lists.append(self.target_parser.resolve(name, Section.VIEW))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.VIEW).for_modes([Mode.SIMULATE])]

        if not target_lists:
            return

        futures = []
        for base_targets in target_lists:
            self.logger.print(
                f"Compiling URDFs: {self._get_summary(list(base_targets))}",
                symbol="🤖",
            )

            simulate_targets = base_targets.for_modes([Mode.SIMULATE])
            if not simulate_targets:
                continue

            results = self.manager.router.run(simulate_targets)
            for fq_target, room in results or []:
                proj_name = TargetParser.get_project_name(fq_target)

                urdf_file = self.lister.get_urdf_output(fq_target)
                urdf_path = Path(out_dir) / urdf_file
                urdf_path.parent.mkdir(parents=True, exist_ok=True)
                path_str = str(urdf_path)

                # Validate OBJ links
                for geom, _ in room.values():
                    label = getattr(geom, "urdf_label", None)
                    if not label:
                        continue
                    local_shape = geom.location.inverse() * geom

                    # Try progressive fallback on label to locate correct part outputs
                    obj_file_name = None
                    parts = label.split("_")
                    for i in range(len(parts), 0, -1):
                        candidate_label = "_".join(parts[:i])
                        candidate_fq = (
                            f"{proj_name}/{candidate_label}" if "/" not in candidate_label else candidate_label
                        )
                        part_outputs = self.lister.get_part_outputs(candidate_fq, None)
                        found = next((p for p in part_outputs if p.endswith(".obj")), None)
                        if found:
                            obj_file_name = found
                            break

                    if not obj_file_name:
                        raise ValueError(f"OBJ file for link '{label}' could not be resolved.")

                    obj_path = Path(out_dir) / obj_file_name
                    if not obj_path.exists():
                        raise ValueError(f"OBJ file for link '{label}' does not exist: {obj_path}. ")

                    # Save resolved filename on geom so export_urdf can use it
                    u_geom = cast(URDFShape, geom)
                    u_geom.urdf_obj_filename = os.path.basename(obj_file_name)
                    current_hash = self._get_part_hash(local_shape)

                    with self.lock:
                        brep_manifest = self.build_manifest.setdefault("brep", {})
                        manifest_hash = brep_manifest.get(obj_file_name)
                    if manifest_hash != current_hash:
                        raise ValueError(f"OBJ file for link '{label}' is out of date. ")

                current_hash = self._get_urdf_hash(room, proj_name)
                futures.append(
                    self.executor.submit(
                        self._export_if_changed,
                        urdf_path,
                        urdf_file,
                        current_hash,
                        lambda r=room, ps=path_str, pn=proj_name: r.export_urdf(ps, pn),
                        force_update,
                    )
                )

        for fut in futures:
            fut.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_pcbs(self, out_dir: str, names: list[str] | None = None, force_update: Optional[bool] = None):
        """Export PCB Gerber archives, supplier BOM/CPL, vector schematics, and 3D STEP models."""
        from provider.pcb import PCBExporter, PCBDesignRulesChecker
        from model.pcb import PCBConfig
        from model.wiring import Wiring

        for provider in self.manager.router.providers:
            wiring_file = getattr(provider, "wiring_path", None)
            if not wiring_file or not Path(wiring_file).exists():
                continue

            pcb_config = provider.pcb_config
            if not pcb_config:
                if names and any(provider.name in n and (Section.PCB in n or ":pcb" in n) for n in names):
                    raise ValueError(f"Project '{provider.name}' does not configure a PCB manifest or PCBConfig.")
                continue

            if names:
                matches = [
                    n
                    for n in names
                    if provider.name in n
                    and (Section.PCB in n or ":pcb" in n or self.target_parser.can_resolve(n, Section.PCB))
                ]
                if not matches:
                    continue

            from model.pcb import BoardType

            # Discover PCB targets: check manifest for targets configuring the PCB section
            pcb_targets: list[str] = []
            for target_name, target_cfg in self.manager.router.manifest.items():
                if isinstance(target_cfg, dict) and (Section.PCB in target_cfg or "pcb" in target_cfg):
                    pcb_targets.append(target_name)

            if not pcb_targets:
                pcb_targets.append(provider.name)

            for target_name in pcb_targets:
                subassembly = target_name.split("/")[-1]
                if names:
                    match_found = any(
                        n in f"{provider.name}/{subassembly}"
                        or f"{provider.name}/{subassembly}" in n
                        or (subassembly in n and (":pcb" in n or Section.PCB in n))
                        or n == f"{provider.name}:pcb"
                        or n == provider.name
                        for n in names
                    )
                    if not match_found:
                        continue

                self.logger.print(f"Compiling PCBs: {provider.name}/{subassembly}", symbol="🔌 ")
                wiring = Wiring(Path(wiring_file))

                sub_pcb_config = None
                if subassembly in provider.part:
                    part_func = provider.part[subassembly]
                    part_res = part_func(subassembly, None, Mode.DEFAULT)
                    if hasattr(part_res, "to_pcb_config"):
                        sub_pcb_config = part_res.to_pcb_config()
                    elif hasattr(part_res, "pcb_metadata"):
                        sub_pcb_config = part_res.pcb_metadata

                target_cfg = sub_pcb_config or pcb_config
                if sub_pcb_config and not target_cfg.stackup:
                    target_cfg = target_cfg.model_copy(update={"stackup": pcb_config.stackup})
                if sub_pcb_config and not target_cfg.capacitive_sensors and pcb_config.capacitive_sensors:
                    target_cfg = target_cfg.model_copy(update={"capacitive_sensors": pcb_config.capacitive_sensors})
                if sub_pcb_config and not target_cfg.copper_regions and pcb_config.copper_regions:
                    target_cfg = target_cfg.model_copy(update={"copper_regions": pcb_config.copper_regions})
                if sub_pcb_config and not target_cfg.net_classes and pcb_config.net_classes:
                    target_cfg = target_cfg.model_copy(update={"net_classes": pcb_config.net_classes})
                if (
                    sub_pcb_config
                    and not target_cfg.silkscreen_texts
                    and pcb_config.silkscreen_texts
                    and getattr(target_cfg, "board_type", None) != BoardType.FLEX
                ):
                    target_cfg = target_cfg.model_copy(update={"silkscreen_texts": pcb_config.silkscreen_texts})
                if (
                    sub_pcb_config
                    and not target_cfg.traces
                    and pcb_config.traces
                    and getattr(target_cfg, "board_type", None) != BoardType.FLEX
                ):
                    target_cfg = target_cfg.model_copy(update={"traces": pcb_config.traces})
                if (
                    sub_pcb_config
                    and not target_cfg.vias
                    and pcb_config.vias
                    and getattr(target_cfg, "board_type", None) != BoardType.FLEX
                ):
                    target_cfg = target_cfg.model_copy(update={"vias": pcb_config.vias})

                # Run DRC and routing connectivity checks
                drc_checker = PCBDesignRulesChecker(target_cfg)
                drc_report = drc_checker.check_all(wiring=wiring)
                if not drc_report.passed:
                    self.logger.print(
                        f"PCB DRC Violations in {provider.name}/{subassembly}:\n{drc_report.summary()}",
                        symbol="⚠️",
                    )
                    if drc_report.error_count > 0:
                        raise ValueError(
                            f"PCB DRC check failed with {drc_report.error_count} error(s) in {provider.name}/{subassembly}:\n"
                            f"{drc_report.summary()}"
                        )

                subassembly_param = subassembly if subassembly != provider.name else None
                exporter = PCBExporter(target_cfg, wiring, subassembly=subassembly_param)

                board_dir = Path(out_dir) / "board" / provider.name
                schematics_dir = Path(out_dir) / "schematics" / provider.name
                bom_dir = Path(out_dir) / "bom" / provider.name
                step_file = Path(out_dir) / "step" / provider.name / f"{subassembly}_pcb.step"

                # 1. Export native KiCad targets (.kicad_pcb and .kicad_sch)
                kicad_pcb = board_dir / f"{subassembly}.kicad_pcb"
                kicad_sch = schematics_dir / f"{subassembly}.kicad_sch"
                exporter.export_kicad_sch(kicad_sch)

                # 2. Export manufacturing board files via kicad-cli (gerbers + drill + .kicad_pcb)
                exporter.export_board(board_dir, pcb_filename=f"{subassembly}.kicad_pcb")

                if subassembly == "carrier_board":
                    alias_pcb = board_dir / f"{provider.name}.kicad_pcb"
                    if alias_pcb != kicad_pcb:
                        shutil.copy2(kicad_pcb, alias_pcb)
                        pro_src = kicad_pcb.with_suffix(".kicad_pro")
                        pro_dst = alias_pcb.with_suffix(".kicad_pro")
                        if pro_src.exists():
                            shutil.copy2(pro_src, pro_dst)

                # Run KiCad DRC verification and generate report under build/rpt
                from provider.pcb.kicad_cli import KiCadCLI

                kicad_cli = KiCadCLI()
                if kicad_cli.is_available:
                    rpt_dir = Path(out_dir) / "rpt"
                    rpt_dir.mkdir(parents=True, exist_ok=True)
                    rpt_file = rpt_dir / f"{subassembly}-drc.rpt"
                    kicad_drc_report = kicad_cli.run_drc(kicad_pcb, rpt_file)
                    if not kicad_drc_report.passed:
                        self.logger.print(
                            f"KiCad DRC Violations in {provider.name}/{subassembly}:\n{kicad_drc_report.summary()}",
                            symbol="⚠️",
                        )
                        raise ValueError(
                            f"KiCad DRC check failed with {kicad_drc_report.error_count} error(s) in {provider.name}/{subassembly}:\n"
                            f"{kicad_drc_report.summary()}"
                        )
                    self.logger.print(f"Generated KiCad DRC Report: {rpt_file}", symbol="🔍")
                    if subassembly == "carrier_board":
                        shutil.copy2(rpt_file, rpt_dir / f"{provider.name}-drc.rpt")

                # 3. Export manufacturing BOM, CPL, Schematic vector PDF, and 3D STEP
                bom_csv = bom_dir / f"{subassembly}_bom.csv" if subassembly != provider.name else bom_dir / "bom.csv"
                pos_csv = bom_dir / f"{subassembly}_pos.csv" if subassembly != provider.name else bom_dir / "pos.csv"
                schematic_pdf = schematics_dir / f"{subassembly}_schematic.pdf"

                exporter.export_bom_csv(bom_csv)
                exporter.export_pick_and_place_csv(pos_csv)
                exporter.export_schematic_pdf(schematic_pdf)
                exporter.export_step_solid(step_file)

                if target_cfg.capacitive_sensors:
                    cap_json = Path(out_dir) / "config" / provider.name / "capacitive_config.json"
                    exporter.export_capacitive_config_json(cap_json)
                    self.logger.print(f"Generated Capacitive Config: {cap_json}", symbol="⚡")

                self.logger.print(f"Generated KiCad PCB: {kicad_pcb}", symbol="🖥️")
                self.logger.print(f"Generated KiCad Schematic: {kicad_sch}", symbol="📄")
                self.logger.print(f"Generated Board Files: {board_dir}", symbol="📦")
                self.logger.print(f"Generated BOM: {bom_csv}", symbol="📋")
                self.logger.print(f"Generated Schematic PDF: {schematic_pdf}", symbol="📑")

    def generate_all(self, out_dir, names: list[str] | None = None, zip_name="build.zip"):
        """Generate diagrams, parts, and package them."""

        def zip_build(zip_file_str, outputs):
            """Write generated files into a zip archive."""
            with zipfile.ZipFile(zip_file_str, "w", zipfile.ZIP_DEFLATED) as zipf:
                for output in outputs:
                    file_path = Path(out_dir) / output
                    if file_path.exists():
                        zipf.write(str(file_path), output)

        def needs_zip(zip_path, outputs) -> bool:
            """Check if the zip archive needs to be rebuilt."""
            if not zip_path.exists():
                return True

            zip_mtime = zip_path.stat().st_mtime
            for output in outputs:
                file_path = Path(out_dir) / output
                if file_path.exists() and file_path.stat().st_mtime > zip_mtime:
                    return True

            try:
                with zipfile.ZipFile(zip_path, "r") as zipf:
                    namelist = zipf.namelist()
                    for output in outputs:
                        file_path = Path(out_dir) / output
                        if file_path.exists() and output not in namelist:
                            return True
            except Exception:
                return True

            return False

        # Export the diagram and files
        if not self.manager.router.providers:
            raise ValueError("No projects discovered. Nothing to build.")

        if names:
            all_supported_sections = [Section.PART, Section.DIAGRAM, Section.VIEW, Section.PCB]
            for name in names:
                if not any(self.target_parser.can_resolve(name, s) for s in all_supported_sections):
                    target_action = Section.PART
                    if ":" in name:
                        action_str = name.split(":", 1)[1].split("/")[0]
                        if action_str in [s.value for s in Section]:
                            target_action = Section(action_str)
                    self.target_parser.resolve(name, target_action)

        self.generate_parts(out_dir=out_dir, names=names)
        self.generate_diagram(out_dir=out_dir, names=names)
        self.generate_urdfs(out_dir=out_dir, names=names)
        self.generate_pcbs(out_dir=out_dir, names=names)

        # Compress the build
        zip_path = Path(out_dir) / zip_name
        zip_file_str = str(zip_path)
        outputs = self.lister.get_outputs(names)

        if needs_zip(zip_path, outputs):
            zip_build(zip_file_str, outputs)
            self.logger.print(f"Done writing {zip_file_str}", symbol="📦")
        else:
            self.logger.print(f"{zip_name} is already up-to-date", symbol="📦")


def get_args():
    """Get parsed arguments for the program."""
    parser = argparse.ArgumentParser(description="Build Utility.")
    parser.add_argument("-e", "--env", required=False, default=None, help="Output environment to file and exit.")

    parser.add_argument("-out", "--outdir", default="build", help="Target directory for outputs")

    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific targets to build. Usage: build.py part1 part2. If omitted, all targets are built.",
    )

    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions."""
    # Generate optional arguments
    # Create the output directory
    path = Path(args.outdir)
    path.mkdir(parents=True, exist_ok=True)

    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    builder = Builder(manager, logger)
    try:
        if not args.env is None:
            builder.config.dump_env(args.env)
            logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")
        else:
            builder._load_manifest(args.outdir)
            targets = args.targets if args.targets else None
            builder.generate_all(out_dir=args.outdir, names=targets)
            builder._save_manifest(args.outdir)

    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point."""
    DaemonClient().run("build", sys.argv[1:])
