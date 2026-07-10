"""List targets and outputs."""

import argparse
from typing import cast
from model import AppConfig
from target_parser import TargetParser
from provider import ProviderManager, Section, Mode, SUBASSEMBLIES
from shell import Logger
import fnmatch


class Lister:
    """Lists available targets and their expected outputs."""

    LIST_SYMBOL = " "

    def __init__(self, manager: ProviderManager, logger: Logger):
        """Initialize the lister."""
        self.manager = manager
        self.logger = logger
        self.target_parser = TargetParser(manager.router)

    def list_targets(self, actions: list[Section] | None = None, names: list[str] | None = None):
        """List all available targets and their supported actions."""
        actions = actions or list(Section)
        target_names = self.target_parser.get_names(actions)

        if names:
            filtered = set()
            for name in names:
                for t in target_names:
                    base = TargetParser.get_base_target(t)
                    if fnmatch.fnmatch(base, name) or fnmatch.fnmatch(t, name):
                        filtered.add(t)
            target_names = sorted(list(filtered))

        self.logger.print(f"Found {len(target_names)} targets:", symbol="📋")

        if target_names:
            self.logger.started = False
            for arg in target_names:
                self.logger.print(arg, restart=False, symbol=self.LIST_SYMBOL)
            self.logger.started = True

    def get_part_outputs(self, target: str, sub: str | None) -> list[str]:
        """Get output paths for a part."""
        p_name, t_name = TargetParser.split_target(target)

        side_suffix = f"_{sub}" if sub else ""
        export_types = self.manager.router.get_export_types(target, sub)
        return [f"{et}/{p_name}/{t_name}{side_suffix}.{et}" for et in export_types]

    def get_diagram_output(self, target: str) -> str:
        """Get output path for a diagram."""
        known_providers = {p.name for p in self.manager.router.providers}
        if target in known_providers:
            p_name = target
        else:
            p_name = TargetParser.get_project_name(target)
        return f"svg/{p_name}/{p_name}_diagram.svg"

    def get_urdf_output(self, target: str) -> str:
        """Get output path for a URDF view."""
        p_name, t_name = TargetParser.split_target(target)
        return f"urdf/{p_name}/{t_name}.urdf"

    def _resolve_targets(self, names: list[str] | None, section: Section, default_mode: Mode):
        """Resolve targets for a specific section and default mode."""
        if names:
            target_lists = []
            for name in names:
                if self.target_parser.parse(name, section):
                    target_lists.append(self.target_parser.resolve(name, section))
            return target_lists
        return [self.manager.router.targets.supporting(section).for_modes([default_mode])]

    def get_outputs(self, names: list[str] | None = None) -> list[str]:
        """Compute all expected build outputs."""
        outputs = []

        # 1. Parts
        target_lists = self._resolve_targets(names, Section.PART, Mode.PRINT)

        for base_targets in target_lists:
            if not base_targets:
                continue

            has_base_targets = set(base_targets)
            all_subs = set()
            for target in base_targets:
                manifest = self.manager.router.manifest.get(target, {})
                action_cfg = manifest.get(Section.PART, {})
                target_subs = action_cfg.get(SUBASSEMBLIES, [])
                all_subs.update(target_subs)

            subs = sorted(list(all_subs))

            for sub in subs:
                run_targets = base_targets.for_subassemblies([sub])
                for target in run_targets:
                    has_base_targets.discard(target)
                    outputs.extend(self.get_part_outputs(target, sub))

            for target in has_base_targets:
                outputs.extend(self.get_part_outputs(target, None))

        # 2. Diagrams
        diagram_targets = self._resolve_targets(names, Section.DIAGRAM, Mode.DEFAULT)

        for base_targets in diagram_targets:
            if not base_targets:
                continue
            p_names = set()
            for target in base_targets:
                p_names.add(TargetParser.get_project_name(target))
            for p_name in p_names:
                outputs.append(self.get_diagram_output(p_name))

        # 3. URDFs
        view_targets = self._resolve_targets(names, Section.VIEW, Mode.SIMULATE)

        for base_targets in view_targets:
            if not base_targets:
                continue
            for target in base_targets:
                outputs.append(self.get_urdf_output(target))

        return sorted(list(set(outputs)))

    def list_outputs(self, names: list[str] | None = None):
        """List all expected build outputs."""
        outputs = self.get_outputs(names)
        self.logger.print(f"Found {len(outputs)} outputs:", symbol="📋")
        if outputs:
            self.logger.started = False
            for out in outputs:
                self.logger.print(out, restart=False, symbol=self.LIST_SYMBOL)
            self.logger.started = True


def get_args():
    """Get parsed arguments for the lister."""
    parser = argparse.ArgumentParser(description="List Utility.")
    parser.add_argument("command", choices=["targets", "outputs"], help="What to list")
    parser.add_argument("targets", nargs="*", help="Optional targets to list outputs for")
    return parser.parse_args()


def main():
    """Run the list utility."""
    args = get_args()
    logger = Logger(text="Listing...")
    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    lister = Lister(manager, logger)
    try:
        if args.command == "targets":
            lister.list_targets(names=getattr(args, "targets", None) or None)
        elif args.command == "outputs":
            lister.list_outputs(getattr(args, "targets", None) or None)
    finally:
        logger.done()


if __name__ == "__main__":
    main()
