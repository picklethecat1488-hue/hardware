"""Handles the validation and execution strategy for build actions."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
from .types import Mode, Section


class Orchestrator(ABC):
    """Base class for orchestrators."""

    executor: ThreadPoolExecutor

    @abstractmethod
    def __init__(self, context: Any, executor: Optional[ThreadPoolExecutor] = None):
        """Initialize the orchestrator."""
        pass

    @abstractmethod
    def execute(
        self,
        targets: tuple[str, ...],
        action: Section,
        subassemblies: tuple[str | None, ...] = (),  # noqa: B006
        modes: tuple[Mode | str, ...] = (Mode.DEFAULT,),
    ) -> Any:
        """Perform a build action."""
        pass
