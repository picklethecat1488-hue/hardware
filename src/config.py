"""Run manifold configuration steps before building."""

import argparse
import importlib
import fnmatch
import sys
from pathlib import Path
from typing import Optional, Sequence
from model import AppConfig
from shell import Logger
from provider import ProviderManager, Action, TargetList


class Configurator:
    """Coordinates configuration actions across discovered projects."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize the configurator."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(text="Configuring...", enabled=False)

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    def _resolve_targets(self, names: Optional[list[str]] = None) -> TargetList:
        """Resolve the list of targets to configure."""
        base_targets = self.manager.router.targets.supporting(Action.CONFIG)
        if names:
            base_targets = base_targets.for_targets(names)

        if not base_targets and names:
            msg = "No matching configuration targets found."
            if any(any(c in n for c in "*?[]") for n in names):
                msg = "No targets matched wildcard pattern."
            raise ValueError(msg)
        return base_targets

    def _resolve_modes(self, targets: TargetList, mode_override: Optional[str] = None) -> Sequence[str]:
        """Determine the set of configuration modes to run."""
        all_supported = set()
        for t in list(targets):
            manifest = self.manager.router.manifest.get(t, {})
            all_supported.update(manifest.get(Action.CONFIG, {}).get("modes", []))

        if mode_override:
            if any(c in mode_override for c in "*?[]"):
                modes = fnmatch.filter(list(all_supported), mode_override)
            else:
                modes = [mode_override]
        else:
            modes = list(all_supported)

        if not modes and targets:
            raise ValueError("No configuration modes found for the selected targets.")

        return sorted(list(modes))

    def configure(self, names: Optional[list[str]] = None, mode: Optional[str] = None):
        """Perform configuration tasks for specified targets."""
        base_targets = self._resolve_targets(names)
        modes_to_run = self._resolve_modes(base_targets, mode)

        for m in modes_to_run:
            run_targets = base_targets.for_modes([m])
            if run_targets:
                self.logger.print(f"Configuring {m}s for {self._get_summary(list(run_targets))}", symbol="⚙️ ")
                self.manager.router.run(run_targets)


def get_args():
    """Get parsed arguments for the program.

    :return _type_: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Configuration Utility.")
    parser.add_argument("-e", "--env", required=False, default=".env", help="Output environment to file and exit.")
    parser.add_argument("-m", "--mode", required=False, default=None, help="Specific configuration mode to run.")

    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific targets to configure. Usage: config.py part1 part2. If omitted, all targets are processed.",
    )
    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions.

    :param _type_ args: The program arguments.
    """
    # Ensure the projects package is imported so subclasses are registered for discovery.
    try:
        src_path = str(Path(__file__).resolve().parent)
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        importlib.import_module("projects")
    except ImportError:
        pass

    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    configurator = Configurator(manager, logger)
    try:
        # Perform requested configurations
        configurator.configure(names=args.targets or None, mode=args.mode)

        # Output the changed items only and exit.
        if args.env:
            manager.save_configs()
            config.dump_env(args.env)
            logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")
    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point.
    """
    logger = Logger(text="Configuring...")
    args = get_args()
    main(logger, args)
