"""Configurator for manifold tube geometry."""

from typing import Optional
from provider import Subassembly
from model.app_config import AppConfig
from projects_config import TubeConfig
from .tube_builder import TubeBuilder


class TubeConfigurator:
    """Configurator for tube geometry."""

    def __init__(self, builder: TubeBuilder, config: AppConfig, tube_config: TubeConfig):
        """Initialize the configurator with a builder and config."""
        self.builder = builder
        self.config = config
        self.tube_config = tube_config

    def config_default(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for default configuration logic."""
        pass

    def config_mount(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for mount configuration logic."""
        pass

    def config_text(self, target: str, subassembly: Optional[Subassembly]) -> None:
        """Skeleton for text configuration logic."""
        pass
