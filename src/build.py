"""Orchestrate geometry generation and export for discovered projects."""

import argparse
import os
from pathlib import Path
import fnmatch
import importlib
from model import AppConfig
from build123d import *  # type: ignore
from build123d import export_stl
from typing import Optional, Any, Sequence
from pydantic import validate_call
from provider import ProviderManager, Action, Mode
import zipfile
from shell import Logger


class Builder:
    """Coordinates build actions and file exports using project providers."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize builder dependencies and measurements."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(enabled=False)

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    def _resolve_modes(self, target: str, mode_override: Optional[str] = None) -> Sequence[str]:
        """Determine the set of build modes for a target."""
        manifest = self.manager.router.manifest.get(target, {})
        supported = manifest.get(Action.PART, {}).get("modes", [])
        supported_strs = [m.value if hasattr(m, "value") else str(m) for m in supported]

        if mode_override:
            if any(c in mode_override for c in "*?[]"):
                return fnmatch.filter(supported_strs, mode_override)
            return [mode_override]

        # Default logic: only export targets that support PRINT mode
        if Mode.PRINT in supported:
            return [Mode.PRINT.value if hasattr(Mode.PRINT, "value") else str(Mode.PRINT)]
        return []

    def _resolve_subassemblies(self, target: str, subassembly_override: Optional[str] = None) -> Sequence[str | None]:
        """Determine which subassemblies should be built for a target."""
        manifest = self.manager.router.manifest.get(target, {})
        action_cfg = manifest.get(Action.PART, {})
        manifest_subs = action_cfg.get("subassemblies", [])

        if subassembly_override:
            if any(c in subassembly_override for c in "*?[]"):
                target_subs: Sequence[str | None] = fnmatch.filter(manifest_subs, subassembly_override)
            else:
                target_subs = [subassembly_override]
        else:
            target_subs = manifest_subs

        if not target_subs:
            target_subs = [None]
        return target_subs

    def generate_parts(self, out_dir, names=None, subassembly=None, mode=None):
        """Export STL files for generated parts."""
        base_targets = self.manager.router.targets.supporting(Action.PART)
        if names:
            base_targets = base_targets.for_targets(names)

        if not base_targets:
            msg = "No matching part targets found."
            if names and any(any(c in n for c in "*?[]") for n in names):
                msg = "No part targets matched wildcard pattern."
            raise ValueError(msg)

        self.logger.print(f"Building {Action.PART}s: {self._get_summary(list(base_targets))}", symbol="🛠️ ")

        for t in list(base_targets):
            modes = self._resolve_modes(t, mode)
            target_subs = self._resolve_subassemblies(t, subassembly)

            if not modes or not target_subs:
                continue

            run_targets = (
                self.manager.router.targets.for_targets([t])
                .supporting(Action.PART)
                .for_modes(modes)
                .for_subassemblies(target_subs)
            )

            batch_results = self.manager.router.run(run_targets)
            for name, results in batch_results:
                # Results is either a single geometry or a list of geometries
                res_list = results if isinstance(results, list) else [results]
                for i, geom in enumerate(res_list):
                    if "/" in name:
                        p_name, t_name = name.split("/", 1)
                    else:
                        p_name, t_name = "default", name

                    # Create provider-specific subdirectory
                    target_dir = Path(out_dir) / p_name
                    target_dir.mkdir(parents=True, exist_ok=True)

                    sub = target_subs[i]
                    side_suffix = f"_{sub}" if sub else ""

                    mesh_file_name = f"{t_name}{side_suffix}.stl"
                    path_str = str(target_dir / mesh_file_name)
                    # Extract the geometry from the BuildPart before exporting
                    if geom.part:
                        export_stl(geom.part, path_str)
                    self.logger.print(f"Saved {path_str}", symbol="📄")

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_diagram(self, out_dir, names=None):
        """Export an exploded diagram for the parts."""
        targets = self.manager.router.targets.supporting(Action.DIAGRAM)
        if names:
            targets = targets.for_targets(names)

        if not targets:
            msg = "No matching diagram targets found."
            if names and any(any(c in n for c in "*?[]") for n in names):
                msg = "No diagram targets matched wildcard pattern."
            raise ValueError(msg)
        self.logger.print(f"Building {Action.DIAGRAM}s: {self._get_summary(list(targets))}", symbol="🛠️ ")

        results = self.manager.router.run(targets)
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

    def generate_all(self, out_dir, subassembly=None, zip_name="build.zip"):
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

        self.generate_parts(out_dir=out_dir, subassembly=subassembly)
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

    parser.add_argument("-s", "--subassembly", default=None, help="Filter by subassembly (supports wildcards)")

    parser.add_argument("-m", "--mode", default=None, help="Build mode override (supports wildcards)")

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
            builder.generate_all(out_dir=args.outdir, subassembly=args.subassembly)
        elif args.parts:
            builder.generate_parts(
                out_dir=args.outdir, names=args.targets or None, subassembly=args.subassembly, mode=args.mode
            )
        elif args.diagram:
            builder.generate_diagram(out_dir=args.outdir, names=args.targets or None)

    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point.
    """
    logger = Logger()
    args = get_args()
    main(logger, args)
