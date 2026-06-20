"""Unified target string parser for build, config, and view utilities."""

import fnmatch
from typing import Sequence, Optional, List, Tuple, cast
from provider import Section, TargetList, ProviderRouter, Mode, SUBASSEMBLIES, MODES


class TargetInfo:
    """Contain parsed target info."""

    def __init__(
        self,
        target: str,
        subassembly: Optional[str],
        action: Section,
        mode: Mode,
    ):
        """Initialize the TargetInfo class."""
        self.target = target
        self.subassembly = subassembly
        self.action = action
        self.mode = mode


class TargetParser:
    """Parses target strings into resolved TargetList objects."""

    @staticmethod
    def get_base_target(target: str) -> str:
        """Get the base target name without action or mode suffix."""
        return target.split(":", 1)[0]

    @staticmethod
    def get_project_name(target: str) -> str:
        """Extract the project/provider name from a target string."""
        base = TargetParser.get_base_target(target)
        return base.split("/", 1)[0] if "/" in base else "default"

    @staticmethod
    def split_target(target: str) -> tuple[str, str]:
        """Split a target string into (project/provider, leaf_target_name)."""
        base = TargetParser.get_base_target(target)
        if "/" in base:
            p_name, t_name = base.split("/", 1)
            return p_name, t_name
        return "default", base

    def __init__(self, router: ProviderRouter):
        """Initialize the parser with a router for manifest lookups."""
        self.router = router

    def parse(self, raw_target: str, default_action: Section) -> Optional[TargetInfo]:
        """Parse a target string into components and match against manifest."""
        # Target format: target[_subassembly][:action[/mode]]
        target_part = self.get_base_target(raw_target)
        action_part = raw_target.split(":", 1)[1] if ":" in raw_target else ""

        action_tokens = action_part.split("/") if action_part else []
        action_str = action_tokens[0] if action_tokens else None

        # Default to the expected action if none is specified
        action = Section(action_str) if action_str else default_action

        # Only process if this info matches the requested action type
        if action != default_action:
            return None

        mode = cast(Mode, action_tokens[1]) if len(action_tokens) > 1 else Mode.DEFAULT

        # Determine target vs subassembly.
        # Since manifest keys are "provider/target", we use '_' as a delimiter for subassemblies.
        target = target_part
        subassembly = None

        if target_part not in self.router.manifest and "_" in target_part:
            # Try splitting off the last component as a subassembly
            p_target, p_sub = target_part.rsplit("_", 1)
            if p_target in self.router.manifest or "*" in p_target:
                target = p_target
                subassembly = p_sub

        return TargetInfo(target, subassembly, action, mode)

    def resolve_targets(self, pattern: str, action: Section, mode: Mode) -> Optional[List[str]]:
        """Resolve all targets supporting action and mode against the manifest."""
        manifest_keys = self.router.manifest.keys()
        matches = []

        for target_name in manifest_keys:
            if fnmatch.fnmatch(target_name, pattern):
                manifest = self.router.manifest[target_name]
                if action not in manifest:
                    continue
                modes = manifest[action].get(MODES, [])
                if mode not in modes:
                    continue
                matches.append(target_name)
        return matches if matches else None

    def resolve_subassemblies(self, pattern: str, target_names: List[str], action: Section) -> Optional[List[str]]:
        """Resolve a subassembly pattern against the manifest's supported subassemblies."""
        subs: set[str] = set()

        # Build the set of all subassemblies for all target names.
        for target_name in target_names:
            target_manifest = self.router.manifest[target_name]
            if action not in target_manifest:
                continue

            action_cfg = target_manifest.get(action, {})
            supported = action_cfg.get(SUBASSEMBLIES, [])
            if not supported:
                continue
            [subs.add(s) for s in supported if fnmatch.fnmatch(s, pattern)]

        # Finally, return the list of resolved subassemblies
        return list(subs) if subs else None

    def resolve(
        self,
        raw_target: str,
        action: Section,
    ) -> TargetList:
        """Resolve a raw target string into a single target list."""
        # Create the raw target lists.
        target_info = self.parse(raw_target, action)
        if not target_info:
            raise ValueError(f"Failed to parse target info from {raw_target}.")

        # Resolve target names
        if "*" in target_info.target:
            resolved_names = self.resolve_targets(target_info.target, action, target_info.mode)
        else:
            resolved_names = [target_info.target]

        if not resolved_names:
            raise ValueError(f"Failed to resolve target names from {raw_target}.")

        res = self.router.targets.supporting(action).for_targets(resolved_names)

        # Only filter by mode if one was explicitly requested or if it's not the default.
        # This allows tools like config.py to resolve targets even if they don't have a 'default' mode.
        if target_info.mode != Mode.DEFAULT:
            res = res.for_modes([target_info.mode])

        # Resolve subassemblies
        resolved_subs = None
        if target_info.subassembly and "*" in target_info.subassembly:
            resolved_subs = self.resolve_subassemblies(target_info.subassembly, resolved_names, action)
        elif target_info.subassembly:
            resolved_subs = [target_info.subassembly]

        if resolved_subs:
            res = res.for_subassemblies(resolved_subs)

        if not res:
            if any(any(c in n for c in "*?[]") for n in raw_target):
                msg = f"No {action} targets matched wildcard pattern."
            else:
                msg = f"No matching {action} targets found."
            raise ValueError(msg)
        return res

    def get_names(self, supported_actions: Sequence[Section]) -> List[str]:
        """List the target names supporting actions."""
        manifest = self.router.manifest
        valid_args = set()

        # Target format: target[_subassembly][:action[/mode]]
        for target_name in manifest.keys():
            target_cfg = manifest[target_name]
            actions = [a for a in supported_actions if a in target_cfg]

            if not actions:
                continue

            # These are the valid target formats:
            # 1) target
            # 2) target:action
            # 2) target:action/mode
            # 3) target_subassembly
            # 4) target_subassembly:action
            # 5) target_subassembly:action/mode

            # Generate all valid argument combinations for this target
            valid_args.add(target_name)
            for action in actions:
                valid_args.add(f"{target_name}:{action}")

                action_cfg = target_cfg[action]
                if not isinstance(action_cfg, dict):
                    continue

                subs = action_cfg.get(SUBASSEMBLIES, [])
                for sub in subs:
                    valid_args.add(f"{target_name}_{sub}")
                    valid_args.add(f"{target_name}_{sub}:{action}")

                modes = action_cfg.get(MODES, [])
                for mode in modes:
                    valid_args.add(f"{target_name}:{action}/{mode}")
                    for sub in subs:
                        valid_args.add(f"{target_name}_{sub}:{action}/{mode}")

        return sorted(list(valid_args))
