"""Specialized list for build targets."""

from typing import Iterable, Optional, TYPE_CHECKING, Union, Sequence
from .types import Mode, Action, MODES, SUBASSEMBLIES

if TYPE_CHECKING:
    from .provider import Provider
    from .provider_router import ProviderRouter


class TargetList(list[str]):
    """A specialized list for manifold build targets."""

    def __init__(
        self,
        provider: Union["Provider", "ProviderRouter"],
        targets: Iterable[str] = (),
        subassemblies: Optional[list[str]] = None,
        modes: Optional[list[Mode]] = None,
        action: Optional[Action] = None,
    ):
        """Initialize the TargetList."""
        super().__init__(targets)
        self.provider = provider
        self.subassemblies = subassemblies or []
        self.modes = modes or [Mode.DEFAULT]
        self.action = action

    def __str__(self) -> str:
        """Return a string representation of the target list for logging."""
        p_name = getattr(self.provider, "name", self.provider.__class__.__name__.lower())

        paths = []
        for i, target in enumerate(self):
            # Router targets are already "provider/target"
            path = target if "/" in target else f"{p_name}/{target}"
            if self.subassemblies:
                sub = self.subassemblies[i] if len(self.subassemblies) == len(self) else self.subassemblies[0]
                path = f"{path}_{sub}"
            paths.append(path)

        return f"Targets({paths}, modes={self.modes})"

    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return self.__str__()

    def supporting(self, action: Action) -> "TargetList":
        """Filter targets that support the specified action."""
        return TargetList(
            self.provider,
            [t for t in self if action in self.provider.manifest.get(t, {})],
            self.subassemblies,
            self.modes,
            action=action,
        )

    def for_subassemblies(self, subassemblies: Sequence[str]) -> "TargetList":
        """Filter targets that support all of the specified subassemblies."""

        def target_supports_subs(t: str) -> bool:
            manifest = self.provider.manifest.get(t, {})
            if self.action:
                action_cfg = manifest.get(self.action)
                if not isinstance(action_cfg, dict):
                    return False
                supported = action_cfg.get(SUBASSEMBLIES, [])
                return all(s in supported for s in subassemblies)

            for action_cfg in manifest.values():
                if isinstance(action_cfg, dict) and all(s in action_cfg.get(SUBASSEMBLIES, []) for s in subassemblies):
                    return True
            return False

        return TargetList(
            self.provider,
            [t for t in self if target_supports_subs(t)],
            list(subassemblies),
            self.modes,
            action=self.action,
        )

    def for_modes(self, modes: Sequence[Mode]) -> "TargetList":
        """Filter targets that support all of the specified modes."""

        def target_supports_modes(t: str) -> bool:
            manifest = self.provider.manifest.get(t, {})
            if self.action:
                action_cfg = manifest.get(self.action)
                if not isinstance(action_cfg, dict):
                    return False
                supported = action_cfg.get(MODES, [])
                return all(m in supported for m in modes)

            for action_cfg in manifest.values():
                if isinstance(action_cfg, dict) and all(m in action_cfg.get(MODES, []) for m in modes):
                    return True
            return False

        return TargetList(
            self.provider,
            [t for t in self if target_supports_modes(t)],
            self.subassemblies,
            list(modes),
            action=self.action,
        )

    def for_targets(self, names: Iterable[str]) -> "TargetList":
        """Filter the target list to include only the specified names."""
        # Now names are expected to be exact matches (resolved by TargetParser)
        target_set = set(names)
        filtered_targets = [t for t in self if t in target_set]

        return TargetList(
            self.provider, filtered_targets, action=self.action, subassemblies=self.subassemblies, modes=self.modes
        )
