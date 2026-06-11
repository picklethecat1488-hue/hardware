"""Orchestrate geometry generation and export for discovered projects."""

import argparse
import io
import hashlib
import json
import os
from pathlib import Path
import fnmatch
import importlib
from model import AppConfig
from build123d import *  # type: ignore
from build123d import export_stl, export_brep
from target_parser import TargetParser
from typing import Optional, Any, Sequence, Callable
from pydantic import validate_call
from provider import ProviderManager, Action, Mode, SUBASSEMBLIES, TargetList, Room
import zipfile
from shell import Logger


class Builder:
    """Coordinates build actions and file exports using project providers."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize builder dependencies and measurements."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(enabled=False)
        self.target_parser = TargetParser(manager.router)
        self.build_manifest: dict[str, str] = {}

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    def _load_manifest(self, out_dir: str):
        """Load an existing build manifest from the output directory if not already loaded."""
        if getattr(self, "_manifest_out_dir", None) == str(out_dir):
            return
        manifest_path = Path(out_dir) / "build_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    self.build_manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        self._manifest_out_dir = str(out_dir)

    def _save_manifest(self, out_dir: str):
        """Write the current build manifest to a JSON file in the output directory."""
        manifest_path = Path(out_dir) / "build_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(self.build_manifest, f, indent=4)
        self.logger.print(f"Saved build manifest to {manifest_path}", symbol="📜")

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
        if not force_update and self.build_manifest.get(manifest_key) == current_hash and path.exists():
            return

        export_fn()
        self.build_manifest[manifest_key] = current_hash
        self.logger.print(f"Saved {path}", symbol="📄")

    def _resolve_subassemblies(self, targets: Any, base_subs: Any) -> Sequence[str]:
        """Determine which subassemblies should be built for a target."""
        if base_subs:
            return base_subs
        else:
            all_subs = set()
            for target in targets:
                manifest = self.manager.router.manifest.get(target, {})
                action_cfg = manifest.get(Action.PART, {})
                target_subs = action_cfg.get(SUBASSEMBLIES, [])
                all_subs.update(target_subs)
            return sorted(list(all_subs))

    @validate_call(config={"arbitrary_types_allowed": True})
    def _export_parts(self, out_dir: str, batch_results: Any, sub: Optional[str] = None, force_update: bool = False):
        """Export parts from a batch run."""
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

                mesh_file_name = f"{t_name}{side_suffix}.stl"
                # Correctly form the path using Path objects
                path_obj = target_dir / mesh_file_name
                path_str = str(path_obj)

                if geom.part:
                    current_hash = self._get_part_hash(geom.part)
                    self._export_if_changed(
                        path_obj,
                        f"{p_name}/{mesh_file_name}",
                        current_hash,
                        lambda: export_stl(geom.part, path_str),
                        force_update=force_update,
                    )

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_parts(self, out_dir, names: list[str] | None = None):
        """Export STL files for generated parts."""
        if names:
            target_lists = []
            for name in names:
                # Only resolve targets that are intended for the PART action
                if self.target_parser.parse(name, Action.PART):
                    target_lists.append(self.target_parser.resolve(name, Action.PART))
        else:
            target_lists = [self.manager.router.targets.supporting(Action.PART).for_modes([Mode.PRINT])]

        if not target_lists:
            return

        for base_targets in target_lists:
            self.logger.print(
                f"Building {Action.PART}s: {self._get_summary(list(base_targets))}",
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
                if self.target_parser.parse(name, Action.DIAGRAM):
                    target_lists.append(self.target_parser.resolve(name, Action.DIAGRAM))
        else:
            target_lists = [self.manager.router.targets.supporting(Action.DIAGRAM).for_modes([Mode.DEFAULT])]

        if not target_lists:
            return

        for base_targets in target_lists:
            self.logger.print(
                f"Building {Action.DIAGRAM}s: {self._get_summary(list(base_targets))}",
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
                self._export_if_changed(
                    path_obj,
                    f"{p_name}/{diagram_name}",
                    current_hash,
                    lambda: room.export_diagram(path_str, options),
                    force_update=bool(names),
                )

    def generate_all(self, out_dir, zip_name="build.zip"):
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

        self.generate_parts(out_dir=out_dir)
        self.generate_diagram(out_dir=out_dir)

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
            if not args.targets:
                builder.generate_all(out_dir=args.outdir)
            else:
                builder.generate_parts(out_dir=args.outdir, names=args.targets)
                builder.generate_diagram(out_dir=args.outdir, names=args.targets)
            builder._save_manifest(args.outdir)

    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point."""
    logger = Logger()
    args = get_args()
    main(logger, args)
