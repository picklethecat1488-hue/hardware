"""Orchestrate geometry generation and export for discovered projects."""

import argparse
import io
import hashlib
import yaml
import os
from pathlib import Path
import fnmatch
import importlib
from model import AppConfig
from build123d import *  # type: ignore
from build123d import export_stl, export_brep, Shape  # type: ignore
from target_parser import TargetParser
from typing import Optional, Any, Sequence, Callable
from pydantic import validate_call
from provider import ProviderManager, Section, Mode, SUBASSEMBLIES, TargetList, Room, MATERIAL
import zipfile
from shell import Logger
from concurrent.futures import ThreadPoolExecutor
import threading


class Builder:
    """Coordinates build actions and file exports using project providers."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize builder dependencies and measurements."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(enabled=False)
        self.target_parser = TargetParser(manager.router)
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
        """Calculate a hash for the diagram based on its SVG output."""
        with io.BytesIO() as svg_stream:
            room.export_diagram(svg_stream, options)
            return hashlib.sha1(svg_stream.getvalue()).hexdigest()

    def _get_file_hash(self, path: Path) -> str:
        """Calculate the SHA1 hash of a file on disk."""
        return hashlib.sha1(path.read_bytes()).hexdigest()

    def _export_obj(self, shape: Shape, file_path: str, tolerance: float = 0.1, scale: float = 1.0) -> bool:
        """Export build123d shape to OBJ format."""
        vertices, triangles = shape.tessellate(tolerance)
        with open(file_path, "w") as f:
            f.write("# Exported by build.py\n")
            for v in vertices:
                f.write(f"v {v.X * scale:.6f} {v.Y * scale:.6f} {v.Z * scale:.6f}\n")
            for t in triangles:
                f.write(f"f {t[0] + 1} {t[1] + 1} {t[2] + 1}\n")
        return True

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
                if "/" in name:
                    p_name, t_name = name.split("/", 1)
                else:
                    p_name, t_name = "default", name

                # Create provider-specific subdirectory
                target_dir = Path(out_dir) / p_name
                target_dir.mkdir(parents=True, exist_ok=True)
                side_suffix = f"_{sub}" if sub else ""

                # Resolve export types from manifest
                export_types = self.manager.router.get_export_types(name, sub)

                if geom.part:
                    current_hash = self._get_part_hash(geom.part)

                    for export_type in export_types:
                        if export_type == "obj":
                            obj_file_name = f"{t_name}{side_suffix}.obj"
                            obj_path = target_dir / obj_file_name

                            # Export OBJ in standard mm scale
                            futures.append(
                                self.executor.submit(
                                    self._export_if_changed,
                                    obj_path,
                                    f"{p_name}/{obj_file_name}",
                                    current_hash,
                                    lambda g=geom.part, p=obj_path: self._export_obj(g, str(p), scale=1.0),
                                    force_update,
                                )
                            )

                        elif export_type == "stl":
                            mesh_file_name = f"{t_name}{side_suffix}.stl"
                            path_obj = target_dir / mesh_file_name
                            path_str = str(path_obj)
                            futures.append(
                                self.executor.submit(
                                    self._export_if_changed,
                                    path_obj,
                                    f"{p_name}/{mesh_file_name}",
                                    current_hash,
                                    lambda g=geom.part, ps=path_str: export_stl(g, ps),
                                    force_update,
                                )
                            )

        # Wait for all submitted exports to complete
        for fut in futures:
            fut.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_parts(self, out_dir, names: list[str] | None = None):
        """Export STL files for generated parts."""
        if names:
            target_lists = []
            for name in names:
                # Only resolve targets that are intended for the PART action
                if self.target_parser.parse(name, Section.PART):
                    target_lists.append(self.target_parser.resolve(name, Section.PART))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.PART).for_modes([Mode.PRINT])]

        if not target_lists:
            return

        for base_targets in target_lists:
            self.logger.print(
                f"Building {Section.PART}s: {self._get_summary(list(base_targets))}",
                symbol="🛠️ ",
            )
            has_base_targets: set[str] = set(base_targets)

            # Run targets which have subassemblies, then run any remaining base targets.
            for sub in self._resolve_subassemblies(base_targets, base_targets.subassemblies):
                run_targets = base_targets.for_subassemblies([sub])
                batch_results = self.manager.router.run(run_targets)
                self._export_parts(out_dir, batch_results, sub=sub, force_update=bool(names))
                for t in run_targets:
                    has_base_targets.discard(t)

            if has_base_targets:
                batch_results = self.manager.router.run(base_targets.for_targets(has_base_targets))
                self._export_parts(out_dir, batch_results, force_update=bool(names))

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_diagram(self, out_dir, names: list[str] | None = None):
        """Export an exploded diagram for the parts."""
        if names:
            target_lists = []
            for name in names:
                # Only resolve targets that are intended for the DIAGRAM action
                if self.target_parser.parse(name, Section.DIAGRAM):
                    target_lists.append(self.target_parser.resolve(name, Section.DIAGRAM))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.DIAGRAM).for_modes([Mode.DEFAULT])]

        if not target_lists:
            return

        futures = []
        for base_targets in target_lists:
            self.logger.print(
                f"Building {Section.DIAGRAM}s: {self._get_summary(list(base_targets))}",
                symbol="🛠️ ",
            )
            results = self.manager.router.run(base_targets)

            for p_name, room in results or []:
                # Create provider-specific subdirectory
                target_dir = Path(out_dir) / p_name
                target_dir.mkdir(parents=True, exist_ok=True)

                diagram_name = f"{p_name}_diagram.svg"
                path_obj = target_dir / diagram_name
                path_str = str(path_obj)

                provider = next((p for p in self.manager.router.providers if p.name == p_name), None)
                options = getattr(provider.settings, "diagram_options", None) if provider else None

                current_hash = self._get_diagram_hash(room, options)
                futures.append(
                    self.executor.submit(
                        self._export_if_changed,
                        path_obj,
                        f"{p_name}/{diagram_name}",
                        current_hash,
                        lambda r=room, ps=path_str, o=options: r.export_diagram(ps, o),
                        bool(names),
                    )
                )

        # Wait for all submitted diagram exports to complete
        for fut in futures:
            fut.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_urdfs(self, out_dir, names: list[str] | None = None):
        """Export combined URDF/OBJ assets from views that support simulate mode."""
        if names:
            target_lists = []
            for name in names:
                if self.target_parser.parse(name, Section.VIEW):
                    target_lists.append(self.target_parser.resolve(name, Section.VIEW))
        else:
            target_lists = [self.manager.router.targets.supporting(Section.VIEW).for_modes([Mode.SIMULATE])]

        if not target_lists:
            return

        futures = []
        for base_targets in target_lists:
            simulate_targets = base_targets.for_modes([Mode.SIMULATE])
            if not simulate_targets:
                continue

            results = self.manager.router.run(simulate_targets)
            for fq_target, room in results or []:
                parts = fq_target.split("/", 1)
                proj_name = parts[0]
                target_name = parts[1] if len(parts) > 1 else proj_name
                target_dir = Path(out_dir) / proj_name
                target_dir.mkdir(parents=True, exist_ok=True)

                futures.append(
                    self.executor.submit(
                        self._export_combined_urdf_from_room,
                        room,
                        target_dir,
                        proj_name,
                        target_name,
                        bool(names),
                    )
                )

        for fut in futures:
            fut.result()

    def _export_combined_urdf_from_room(
        self, room: Room, target_dir: Path, p_name: str, target_name: str, force_update: bool = False
    ):
        """Export a combined URDF and individual OBJ links from a Room object."""
        links_info = []
        for name, (geom, rgba) in room.items():
            label = getattr(geom, "urdf_label", None)
            if not label:
                continue

            parent = getattr(geom, "urdf_parent", None)
            joint_type = getattr(geom, "urdf_joint_type", "fixed")
            joint_axis = getattr(geom, "urdf_joint_axis", "0 0 1")
            density = getattr(geom, "urdf_density", 1.0)

            # Extract location
            pos = geom.location.position
            xyz = [pos.X * 0.001, pos.Y * 0.001, pos.Z * 0.001]
            rpy = [0.0, 0.0, 0.0]

            # Invert the translation to get the local shape centered at local origin
            local_shape = geom.location.inverse() * geom

            # Export local shape to OBJ
            obj_file_name = f"{label}.obj"
            obj_path = target_dir / obj_file_name
            current_hash = self._get_part_hash(local_shape)

            # Validate that the OBJ file exists and is up to date
            if not obj_path.exists():
                raise ValueError(f"OBJ file for link '{label}' does not exist: {obj_path}. ")

            with self.lock:
                brep_manifest = self.build_manifest.setdefault("brep", {})
                manifest_hash = brep_manifest.get(f"{p_name}/{obj_file_name}")

            if manifest_hash != current_hash:
                raise ValueError(f"OBJ file for link '{label}' is out of date. ")

            # Mass and inertia calculations using local shape and density
            density_g_mm3 = density * 1e-3
            volume_mm3 = local_shape.volume  # type: ignore
            mass_kg = volume_mm3 * density_g_mm3 * 1e-3

            com = local_shape.center(CenterOf.MASS)  # type: ignore
            com_m = [com.X * 0.001, com.Y * 0.001, com.Z * 0.001]

            raw_inertia = local_shape.matrix_of_inertia
            scale_factor = density * 1e-12

            ixx = raw_inertia[0][0] * scale_factor
            ixy = raw_inertia[0][1] * scale_factor
            ixz = raw_inertia[0][2] * scale_factor
            iyy = raw_inertia[1][1] * scale_factor
            iyz = raw_inertia[1][2] * scale_factor
            izz = raw_inertia[2][2] * scale_factor

            # Format RGBA
            rgba_str = f"{rgba[0]:.6f} {rgba[1]:.6f} {rgba[2]:.6f} {rgba[3]:.6f}"

            links_info.append(
                {
                    "name": label,
                    "parent": parent,
                    "joint_type": joint_type,
                    "joint_axis": joint_axis,
                    "xyz": xyz,
                    "rpy": rpy,
                    "mass_kg": mass_kg,
                    "com_x": com_m[0],
                    "com_y": com_m[1],
                    "com_z": com_m[2],
                    "ixx": ixx,
                    "ixy": ixy,
                    "ixz": ixz,
                    "iyy": iyy,
                    "iyz": iyz,
                    "izz": izz,
                    "obj_filename": obj_file_name,
                    "rgba_str": rgba_str,
                }
            )

        if not links_info:
            return

        # Build combined URDF XML representation using templates
        links_strings = []
        for link in links_info:
            link_str = self.link_template.format(
                link_name=link["name"],
                com_x=link["com_x"],
                com_y=link["com_y"],
                com_z=link["com_z"],
                mass_kg=link["mass_kg"],
                ixx=link["ixx"],
                ixy=link["ixy"],
                ixz=link["ixz"],
                iyy=link["iyy"],
                iyz=link["iyz"],
                izz=link["izz"],
                project_name=p_name,
                obj_filename=link["obj_filename"],
                rgba=link["rgba_str"],
            )
            links_strings.append(link_str)

        joints_strings = []
        for link in links_info:
            if link["parent"] is not None:
                axis_limit_str = ""
                if link["joint_type"] in ("revolute", "prismatic"):
                    axis_limit_str = self.axis_limit_template.format(joint_axis=link["joint_axis"]) + "\n  "

                joint_str = self.joint_template.format(
                    parent_name=link["parent"],
                    child_name=link["name"],
                    joint_type=link["joint_type"],
                    xyz_x=link["xyz"][0],
                    xyz_y=link["xyz"][1],
                    xyz_z=link["xyz"][2],
                    rpy_r=link["rpy"][0],
                    rpy_p=link["rpy"][1],
                    rpy_y=link["rpy"][2],
                    axis_limit=axis_limit_str,
                )
                joints_strings.append(joint_str)

        urdf_content = self.robot_template.format(
            robot_name=p_name,
            links="\n".join(links_strings),
            joints="\n".join(joints_strings),
        )

        urdf_file_name = f"{target_name}.urdf"
        urdf_path = target_dir / urdf_file_name

        with open(urdf_path, "w") as f:
            f.write(urdf_content)
        self.logger.print(f"Saved {urdf_path}", symbol="📄")

    def generate_all(self, out_dir, names: list[str] | None = None, zip_name="build.zip"):
        """Generate diagrams, parts, and package them."""

        def zip_build(zip_file_str):
            """Write generated files into a zip archive."""
            with zipfile.ZipFile(zip_file_str, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(out_dir):
                    for file in files:
                        file_path = Path(root) / file
                        if not os.path.samefile(zip_file_str, str(file_path)):
                            # Preserve directory structure in zip
                            zipf.write(str(file_path), str(file_path.relative_to(out_dir)))

        # Export the diagram and files
        if not self.manager.router.providers:
            raise ValueError("No projects discovered. Nothing to build.")

        self.generate_parts(out_dir=out_dir, names=names)
        self.generate_diagram(out_dir=out_dir, names=names)
        self.generate_urdfs(out_dir=out_dir, names=names)

        # Compress the build
        zip_file_str = str(Path(out_dir) / zip_name)
        zip_build(zip_file_str)
        self.logger.print(f"Done writing {zip_file_str}", symbol="📦")


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
    logger = Logger()
    args = get_args()
    main(logger, args)
