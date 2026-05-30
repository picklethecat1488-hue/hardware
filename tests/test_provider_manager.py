"""Unit tests for the ProviderManager class."""

import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel, Field
from providers.provider_manager import ProviderManager
from providers.provider import Provider
from model import AppConfig


class SimpleMockProvider(Provider):
    """Simplified provider for ProviderManager testing."""

    def __init__(self, name: str, manifest: dict, default_config=None):
        """Initialize the simplified mock provider."""
        self._name = name
        self._manifest = manifest
        self._default_config = default_config
        # Initialize without calling super().__init__ to avoid complex setup
        self.orchestrator = MagicMock()
        self.get_color = MagicMock()

    @property
    def name(self) -> str:
        """Return the mock provider name."""
        return self._name

    @property
    def manifest(self) -> dict:
        """Return the mock provider manifest."""
        return self._manifest

    @property
    def default_config(self):
        """Return a mock configuration instance."""
        return self._default_config

    @property
    def build(self):
        """Return an empty build registry."""
        return {}


class MockSettings(BaseModel):
    """Mock settings model for testing."""

    val: str = "default"
    num: int = 0
    items: list[int] = Field(default_factory=list)


def test_manager_init():
    """Verify manager initializes with config and router."""
    config = AppConfig()
    p1 = SimpleMockProvider("p1", {})
    m = ProviderManager(config, providers=[p1])
    assert m.config == config
    assert m.router.providers == [p1]


def test_manager_load_configs():
    """Verify loading and routing of environment variables."""
    p_settings = MockSettings()
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)

    config = AppConfig()
    config.model_extra["P1__VAL"] = "env_val"  # type: ignore
    config.model_extra["P1__NUM"] = 10  # type: ignore
    config.model_extra["P1__ITEMS"] = "[1, 2, 3]"  # type: ignore

    mgr = ProviderManager(config, providers=[p1])
    mgr.load_configs()

    assert p1.settings.val == "env_val"
    assert p1.settings.num == 10
    assert p1.settings.items == [1, 2, 3]
    assert getattr(config, "p1") == p1.settings


def test_manager_load_configs_json_error():
    """Verify ValueError on malformed JSON in environment variables."""
    p_settings = MockSettings()
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)

    config = AppConfig()
    config.model_extra["P1__ITEMS"] = "[1, 2"  # type: ignore

    mgr = ProviderManager(config, providers=[p1])
    with pytest.raises(ValueError, match="Failed to parse JSON configuration"):
        mgr.load_configs()


def test_manager_save_configs():
    """Verify preparation of AppConfig for environment dumping."""
    p_settings = MockSettings(val="custom")
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)

    config = AppConfig()
    mgr = ProviderManager(config, providers=[p1])
    mgr.save_configs()

    assert getattr(config, "p1") == p_settings
    assert "P1" in config._env_flattened_keys
