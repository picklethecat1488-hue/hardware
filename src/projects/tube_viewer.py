"""Viewer for manifold tube geometry."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
from model.app_config import AppConfig
from projects_config import TubeConfig
from .tube_builder import TubeBuilder


class TubeViewer:
    """Viewer for tube geometry."""

    def __init__(
        self,
        builder: TubeBuilder,
        config: AppConfig,
        tube_config: TubeConfig,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the viewer with a builder and config."""
        self.builder = builder
        self.config = config
        self.tube_config = tube_config
        self.executor = executor or ThreadPoolExecutor()

    def view_part_positions(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Skeleton for part positions visualization."""
        return []

    def view_overlay(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Skeleton for part positions visualization."""
        return []

    def view_tube_profile(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Skeleton for part positions visualization."""
        return []
