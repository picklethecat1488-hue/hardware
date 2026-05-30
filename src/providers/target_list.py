"""Specialized list for build targets."""

from typing import Iterable, Optional, TYPE_CHECKING
from .types import Subassembly, Mode, Action

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
            [t for t in self if action in self.provider.manifest.get(t, {}).get("actions", [])],
            self.subassemblies,
            self.modes,
        )

    def for_subassemblies(self, subassemblies: list[Subassembly]) -> "TargetList":
        """Filter targets that support any of the specified subassemblies."""
        return TargetList(
            self.provider,
            [
                t
                for t in self
                if any(s in self.provider.manifest.get(t, {}).get("subassemblies", []) for s in subassemblies)
            ],
            subassemblies,
            self.modes,
        )

    def for_modes(self, modes: list[Mode]) -> "TargetList":
        """Filter targets that support any of the specified modes."""
        return TargetList(
            self.provider,
            [t for t in self if any(m in self.provider.manifest.get(t, {}).get("modes", []) for m in modes)],
            self.subassemblies,
            modes,
        )
