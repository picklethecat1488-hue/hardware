"""View manifold geometry using ocp_vscode."""

import argparse
import importlib
import fnmatch
import os
import sys
from model import AppConfig
from pathlib import Path
from typing import Sequence, Optional, List, Any, cast, Iterable
from build123d import *  # type: ignore
from target_parser import TargetParser
from provider import ProviderManager, Action, TargetList, Room
from pydantic import validate_call
from shell import Logger
from ocp_vscode import set_port, Collapse, Camera, show as ocp_show  # type: ignore


def show(*args, **kwargs):
    """Bypass ocp_vscode visualization during smoke tests."""
    if os.environ.get("SMOKE_TEST") == "1":
        return
    return ocp_show(*args, **kwargs)


class Viewer:
    """Builds and displays geometry rooms for visualization."""

    VISUAL_ACTIONS = [Action.VIEW, Action.PART, Action.DIAGRAM]

    def __init__(self, manager: ProviderManager, logger: Logger):
        """Initialize the viewer."""
        self.manager = manager
        self.logger = logger
        self.target_parser = TargetParser(manager.router)

    def get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the names being shown."""
        if len(names) > 8:
            return f"{', '.join(names[:8])} ... ({len(names)} items)"
        return ", ".join(names)

    def _get_view_items(self, targets: TargetList) -> List[tuple[Any, str, tuple[float, float, float], float]]:
        """Collect items from a VIEW room."""
        items = []
        results = self.manager.router.run(targets)
        for room_name, room in results:
            for item_name, (geom, rgba) in room.items():
                items.append((geom, f"{room_name}_{item_name}", rgba[:3], rgba[3]))
        return items

    def _get_part_items(self, targets: Any) -> List[tuple[Any, str, tuple[float, float, float], float]]:
        """Collect geometry from a PART build."""
        items = []
        results = self.manager.router.run(targets)

        # Determine subassemblies used from the TargetList to correctly label items
        subs = targets.subassemblies if targets.subassemblies else [None]

        for name, geom in results:
            res_list = geom if isinstance(geom, list) else [geom]
            for i, item in enumerate(res_list):
                sub = subs[i] if i < len(subs) else None
                display_name = f"{name}_{sub}" if sub else name
                rgba = self.manager.router.get_color(name, sub)
                items.append((item, display_name, rgba[:3], rgba[3]))
        return items

    def _get_diagram_items(
        self, targets: TargetList
    ) -> List[tuple[Any, str, Optional[tuple[float, float, float]], float]]:
        """Collect a compound from a DIAGRAM build."""
        items = []
        results = self.manager.router.run(targets)
        for p_name, room in results:
            items.append((room.compound, f"{p_name}_diagram", None, 1.0))
        return items

    @validate_call(config={"arbitrary_types_allowed": True})
    def show_view(self, input_targets: Sequence[str]):
        """Build and show the requested geometry in ocp_vscode."""
        display_items = []

        for target in input_targets:
            for action in self.VISUAL_ACTIONS:
                try:
                    targets = self.target_parser.resolve(target, action)
                    if not targets:
                        continue
                    if action == Action.VIEW:
                        display_items.extend(self._get_view_items(targets))
                        break
                    elif action == Action.PART:
                        display_items.extend(self._get_part_items(targets))
                        break
                    elif action == Action.DIAGRAM:
                        display_items.extend(self._get_diagram_items(targets))
                        break
                except ValueError:
                    continue

        if not display_items:
            raise ValueError("No geometry generated for the specified targets.")

        room = Room(config=self.manager.config)
        for obj, name, color, alpha in display_items:
            # Assembly names cannot contain slashes as they are path delimiters
            base_name = name.replace("/", "_")
            safe_name = base_name
            counter = 1
            while safe_name in room:
                safe_name = f"{base_name}_{counter}"
                counter += 1
            room.add(safe_name, obj, color=color, alpha=alpha)

        summary = self.get_summary(list(room.keys()))
        self.logger.print(f"Showing {summary}", symbol="👁️ ")
        show(room.compound, names=["View"], collapse=Collapse.ALL, reset_camera=Camera.RESET)

    def list_targets(self):
        """List all available targets and their supported actions."""
        target_names = self.target_parser.get_names(self.VISUAL_ACTIONS)
        self.logger.print(f"Found {len(target_names)} targets:", symbol="📋")

        if target_names:
            # Use manual control to avoid Halo spinner overhead during long lists
            self.logger.started = False
            for arg in target_names:
                self.logger.print(arg, restart=False)
            self.logger.started = True


def get_args():
    """Get parsed arguments for the viewer."""
    parser = argparse.ArgumentParser(description="View Utility.")
    parser.add_argument(
        "targets", nargs="*", help="The targets to visualize (e.g. tube/driver, tube/wire, tube/driver_left)."
    )
    parser.add_argument("-l", "--list", action="store_true", help="List available targets")
    args = parser.parse_args()

    if not args.list and not args.targets:
        parser.error("the following arguments are required: target (or use --list)")

    return args


def main():
    """Build and show the requested geometry in ocp_vscode."""
    args = get_args()

    # Allow overriding the OCP Viewer port for testing environments
    ocp_port = os.environ.get("OCP_PORT")
    if ocp_port:
        set_port(int(ocp_port))

    logger = Logger(text="Visualizing...")

    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    viewer = Viewer(manager, logger)
    try:
        if args.list:
            logger.text = "Listing targets..."
            viewer.list_targets()
        else:
            viewer.show_view(cast(Sequence[str], args.targets))
    finally:
        logger.done()


if __name__ == "__main__":
    main()
