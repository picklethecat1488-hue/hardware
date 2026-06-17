"""Run manifold configuration steps before building."""

import argparse
import fnmatch
from typing import Optional, Sequence
from model import AppConfig
from target_parser import TargetParser
from shell import Logger
from provider import ProviderManager, Section, TargetList, MODES, Mode


class Configurator:
    """Coordinates configuration actions across discovered projects."""

    def __init__(self, manager: ProviderManager, logger: Optional[Logger] = None):
        """Initialize the configurator."""
        self.manager = manager
        self.config = manager.config
        self.logger = logger or Logger(text="Configuring...", enabled=False)
        self.target_parser = TargetParser(manager.router)

    def _get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the target names."""
        count = len(names)
        if count > 8:
            return f"{', '.join(names[:8])} ... ({count} items)"
        return ", ".join(names)

    def resolve_modes(self, targets: TargetList, base_modes: list[Mode]) -> list[Mode]:
        """Determine the set of configuration modes to run."""
        # If MODES hasn't been overridden, we need to figure out which modes to run
        if Mode.DEFAULT not in base_modes:
            return base_modes
        else:
            all_supported = set()
            for t in list(targets):
                manifest = self.manager.router.manifest.get(t, {})
                all_supported.update(manifest.get(Section.CONFIG, {}).get(MODES, []))
            return sorted(list(all_supported))

    def configure(self, names: Optional[list[str]] = None, mode: Optional[str] = None):
        """Perform configuration tasks for specified targets."""
        target_lists = (
            [self.target_parser.resolve(name, Section.CONFIG) for name in names]
            if names
            else [self.manager.router.targets.supporting(Section.CONFIG)]
        )

        for base_targets in target_lists:
            self.logger.print(
                f"Configuring {self._get_summary(list(base_targets))}",
                symbol="⚙️ ",
            )

            # Batch each configuration step.
            for mode in self.resolve_modes(base_targets, base_targets.modes):
                run_targets = base_targets.for_modes([mode])
                self.manager.router.run(run_targets)


def get_args():
    """Get parsed arguments for the program."""
    parser = argparse.ArgumentParser(description="Configuration Utility.")
    parser.add_argument("-e", "--env", required=False, default=".env", help="Output environment to file and exit.")

    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific targets to configure (e.g. tube/driver, tube/driver_left). If omitted, all targets are processed.",
    )
    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions."""
    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    configurator = Configurator(manager, logger)
    try:
        # Perform requested configurations
        configurator.configure(names=args.targets or None)

        # Output the changed items only and exit.
        if args.env:
            manager.save_configs()
            config.dump_env(args.env)
            logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")
    finally:
        logger.done()


if __name__ == "__main__":
    """Program entry point."""
    logger = Logger(text="Configuring...")
    args = get_args()
    main(logger, args)
