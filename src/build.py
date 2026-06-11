"""Orchestrate geometry generation and export for discovered projects."""

import argparse
import os
from pathlib import Path
import fnmatch
import importlib
from model import AppConfig
from build123d import *  # type: ignore
from build123d import export_stl
from target_parser import TargetParser
from typing import Optional, Any, Sequence
from pydantic import validate_call
from provider import ProviderManager, Action, Mode, SUBASSEMBLIES, TargetList
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

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    @validate_call(config={"arbitrary_types_allowed": True})
    def resolve_subassemblies(self, targets: TargetList, base_subs: list[str]) -> Sequence[str | None]:
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
            return sorted(list(all_subs)) if all_subs else [None]

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_parts(self, out_dir, names: list[str] | None = None):
        """Export STL files for generated parts."""
        target_lists = (
            [self.target_parser.resolve(name, Action.PART) for name in names]
            if names
            else [self.manager.router.targets.supporting(Action.PART).for_modes([Mode.PRINT])]
        )

        for base_targets in target_lists:
            self.logger.print(
                f"Building {Action.PART}s: {self._get_summary(list(base_targets))}",
                symbol="🛠️ ",
            )

            for sub in self.resolve_subassemblies(base_targets, base_targets.subassemblies):
                run_targets = base_targets.for_subassemblies([sub]) if sub else base_targets
                batch_results = self.manager.router.run(run_targets)

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
                        path_str = str(target_dir / mesh_file_name)
                        # Extract the geometry from the BuildPart before exporting
                        if geom.part:
                            export_stl(geom.part, path_str)
                        self.logger.print(f"Saved {path_str}", symbol="📄")

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_diagram(self, out_dir, names: list[str] | None = None):
        """Export an exploded diagram for the parts."""
        target_lists = (
            [self.target_parser.resolve(name, Action.DIAGRAM) for name in names]
            if names
            else [self.manager.router.targets.supporting(Action.DIAGRAM).for_modes([Mode.DEFAULT])]
        )

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
                path_str = str(target_dir / diagram_name)

                provider = next((p for p in self.manager.router.providers if p.name == p_name), None)
                options = getattr(provider.settings, "diagram_options", None) if provider else None
                room.export_diagram(path_str, options)
                self.logger.print(f"Saved {path_str}", symbol="📄")

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


def str2bool(v: Any) -> bool:
    """Convert various string representations to boolean."""
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def get_args():
    """Get parsed arguments for the program."""
    parser = argparse.ArgumentParser(description="Build Utility.")
    parser.add_argument("-e", "--env", required=False, default=None, help="Output environment to file and exit.")

    parser.add_argument("-out", "--outdir", default="build", help="Target directory for outputs")

    parser.add_argument(
        "-d",
        "--diagram",
        type=str2bool,
        nargs="?",
        const=True,
        default=True,
        help="Generate diagrams. Defaults to True.",
    )
    parser.add_argument(
        "-p",
        "--parts",
        type=str2bool,
        nargs="?",
        const=True,
        default=True,
        help="Generate parts. Defaults to True.",
    )

    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific targets to build. Usage: build.py part1 part2. If omitted, all targets are built.",
    )

    args = parser.parse_args()

    if not args.diagram and not args.parts:
        parser.error("At least one of --diagram or --parts must be True.")

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
        elif args.diagram and args.parts and not args.targets:
            builder.generate_all(out_dir=args.outdir)
        elif args.parts:
            builder.generate_parts(out_dir=args.outdir, names=args.targets or None)
        elif args.diagram:
            builder.generate_diagram(out_dir=args.outdir, names=args.targets or None)

    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point."""
    logger = Logger()
    args = get_args()
    main(logger, args)
