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
from provider import ProviderManager, Action, TargetList, Room
from shell import Logger
from ocp_vscode import set_port, Collapse, Camera, show  # type: ignore


class Viewer:
    """Builds and displays geometry rooms for visualization."""

    def __init__(self, manager: ProviderManager, logger: Logger):
        """Initialize the viewer."""
        self.manager = manager
        self.logger = logger

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
                items.append((geom, f"{room_name}/{item_name}", rgba[:3], rgba[3]))
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
                display_name = f"{name}/{sub}" if sub else name
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

    def _resolve_targets(self, raw_target: str) -> tuple[TargetList, Optional[str], Optional[str]]:
        """Parse a target string and resolve it to a TargetList, action, and subassembly."""
        visual_actions = [Action.VIEW.value, Action.PART.value, Action.DIAGRAM.value]
        parts = raw_target.split("/")
        target_path, remaining = None, []

        # 1. Resolve namespaced or local target path
        if len(parts) >= 2:
            p_t = "/".join(parts[:2])
            # Check if this pattern matches any registered targets
            if fnmatch.filter(self.manager.router.manifest.keys(), p_t):
                target_path, remaining = p_t, parts[2:]

        if not target_path and parts:
            # Check if the local pattern matches any targets
            if self.manager.router.targets.for_targets([parts[0]]):
                target_path, remaining = parts[0], parts[1:]

        if not target_path:
            raise ValueError(f"Target '{raw_target}' not found in any registered provider.")

        # 2. Parse inline action and subassembly from remaining segments
        target_action_str, target_sub = None, None
        if len(remaining) >= 2:
            target_action_str, target_sub = remaining[0], remaining[1]
        elif len(remaining) == 1:
            if remaining[0] in visual_actions:
                target_action_str = remaining[0]
            else:
                target_sub = remaining[0]

        # Resolve the target through the router to handle namespacing/discovery
        targets = self.manager.router.targets.for_targets([target_path])
        return targets, target_action_str, target_sub

    def _resolve_subassemblies(
        self, target_sub: str, manifest: dict, action: Action, target_name: str, has_wildcards: bool
    ) -> Optional[List[str]]:
        """Resolve a subassembly string (with wildcard support) against the manifest."""
        action_cfg = manifest.get(action, {})
        manifest_subs = action_cfg.get("subassemblies", [])

        if any(c in target_sub for c in "*?[]"):
            requested_subs = fnmatch.filter(manifest_subs, target_sub)
        else:
            requested_subs = [target_sub] if target_sub in manifest_subs else []

        if not requested_subs:
            return None

        return requested_subs

    def show_view(self, input_targets: Sequence[str]):
        """Build and show the requested geometry in ocp_vscode."""
        display_items = []

        for raw_target in input_targets:
            has_wildcards = any(c in raw_target for c in "*?[]")
            matched_targets, target_action_str, target_sub = self._resolve_targets(raw_target)

            for resolved_target in matched_targets:
                manifest = self.manager.router.manifest[resolved_target]

                # Determine available visual actions
                supported_actions = [a for a in [Action.VIEW, Action.PART, Action.DIAGRAM] if a in manifest]
                if not supported_actions:
                    continue

                selected_action: Action
                if target_action_str:
                    selected_action = Action(target_action_str)
                    if selected_action not in supported_actions:
                        self.logger.print(
                            f"Action '{target_action_str}' is not supported for '{resolved_target}'.",
                            symbol="⚠️",
                        )
                        continue
                else:
                    selected_action = supported_actions[0]

                # 3. Configure the specific run for this target
                run_targets = TargetList(
                    matched_targets.provider,
                    [resolved_target],
                    action=selected_action,
                    modes=matched_targets.modes,
                )

                if target_sub:
                    resolved_subs = self._resolve_subassemblies(
                        target_sub, manifest, selected_action, resolved_target, has_wildcards
                    )
                    if resolved_subs is None:
                        self.logger.print(
                            f"Subassembly '{target_sub}' not supported for '{resolved_target}'.",
                            symbol="⚠️",
                        )
                        continue
                    run_targets = run_targets.for_subassemblies(resolved_subs)

                if selected_action == Action.VIEW:
                    display_items.extend(self._get_view_items(run_targets))
                elif selected_action == Action.PART:
                    display_items.extend(self._get_part_items(run_targets))
                elif selected_action == Action.DIAGRAM:
                    display_items.extend(self._get_diagram_items(run_targets))

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
        manifest = self.manager.router.manifest
        targets = sorted(manifest.keys())

        self.logger.print(f"Found {len(targets)} targets:", symbol="📋")
        all_valid_args = []
        for t in targets:
            target_cfg = manifest[t]
            supported_actions = [a for a in [Action.VIEW, Action.PART, Action.DIAGRAM] if a in target_cfg]

            if not supported_actions:
                continue

            # Generate all valid argument combinations for this target
            valid_args = {t}
            for i, action in enumerate(supported_actions):
                act_val = action.value
                valid_args.add(f"{t}/{act_val}")

                subs = target_cfg[action].get("subassemblies", [])
                for sub in subs:
                    valid_args.add(f"{t}/{act_val}/{sub}")
                    if i == 0:
                        # Shorthand for the primary visual action
                        valid_args.add(f"{t}/{sub}")

            all_valid_args.extend(sorted(list(valid_args)))

        if all_valid_args:
            # Use manual control to avoid Halo spinner overhead during long lists
            self.logger.started = False
            for arg in all_valid_args:
                self.logger.print(arg, restart=False)
            self.logger.started = True


def get_args():
    """Get parsed arguments for the viewer."""
    parser = argparse.ArgumentParser(description="View Utility.")
    parser.add_argument(
        "targets", nargs="*", help="The targets to visualize (e.g. tube/driver, tube/wire, tube/driver/part)."
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
