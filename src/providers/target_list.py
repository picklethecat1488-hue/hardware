"""Specialized list for build targets."""

from typing import Iterable, Optional, TYPE_CHECKING
from .types import Subassembly, Mode, Action, MODES, SUBASSEMBLIES

if TYPE_CHECKING:
    from .provider import Provider


class TargetList(list[str]):
    """A specialized list for manifold build targets."""

    def __init__(
        self,
        provider: "Provider",
        targets: Iterable[str] = (),
        subassemblies: Optional[list[Subassembly]] = None,
        modes: Optional[list[Mode]] = None,
    ):
        """Initialize the TargetList."""
        super().__init__(targets)
        self.provider = provider
        self.subassemblies = subassemblies or []
        self.modes = modes or [Mode.DEFAULT]

    def __str__(self) -> str:
        """Return a string representation of the target list for logging."""
        name = f"{self.provider.name.title()}Targets"
        return f"{name}(targets={super().__repr__()}, subassemblies={self.subassemblies}, modes={self.modes})"

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
        )

    def for_subassemblies(self, subassemblies: list[Subassembly]) -> "TargetList":
        """Filter targets that support any of the specified subassemblies."""

        def target_supports_subs(t: str) -> bool:
            actions_dict = self.provider.manifest.get(t, {})
            for action_cfg in actions_dict.values():
                if any(s in action_cfg.get(SUBASSEMBLIES, []) for s in subassemblies):
                    return True
            return False

        return TargetList(
            self.provider,
            [t for t in self if target_supports_subs(t)],
            subassemblies,
            self.modes,
        )

    def for_modes(self, modes: list[Mode]) -> "TargetList":
        """Filter targets that support any of the specified modes."""

        def target_supports_modes(t: str) -> bool:
            actions_dict = self.provider.manifest.get(t, {})
            # Check if any supported action for this target offers any of the requested modes
            for action_cfg in actions_dict.values():
                if any(m in action_cfg.get(MODES, []) for m in modes):
                    return True
            return False

        return TargetList(
            self.provider,
            [t for t in self if target_supports_modes(t)],
            self.subassemblies,
            modes,
        )
