"""Unit tests for the ProviderRouter class."""

import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel, Field
from providers.provider_router import ProviderRouter
from providers.provider import Provider
from providers.types import Action, Mode, Subassembly, MODES, SUBASSEMBLIES
from providers.target_list import TargetList
from model import AppConfig


class SimpleMockProvider(Provider):
    """Simplified provider for ProviderRouter testing."""

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
    def registry(self):
        """Return an empty handler registry."""
        return {}

    def run(self, targets):
        """Perform a mock build action."""
        return [("mock", "res")]


class MockSettings(BaseModel):
    """Mock settings model for testing."""

    val: str = "default"
    num: int = 0
    items: list[int] = Field(default_factory=list)


def test_router_init():
    """Verify router initializes with providers."""
    p1 = SimpleMockProvider("p1", {})
    c = ProviderRouter(providers=[p1])
    assert c.providers == [p1]
    assert c.provider_names == ["p1"]


def test_router_manifest_aggregation():
    """Verify manifest merging from multiple providers."""
    p1 = SimpleMockProvider("p1", {"a": {Action.PART: {}}})
    p2 = SimpleMockProvider("p2", {"b": {Action.PART: {}}})
    c = ProviderRouter(providers=[p1, p2])

    manifest = c.manifest
    assert "p1/a" in manifest
    assert "p2/b" in manifest
    assert len(manifest) == 2


def test_router_path_syntax_avoids_collision():
    """Verify that duplicate target names are namespaced correctly."""
    p1 = SimpleMockProvider("p1", {"collision": {}})
    p2 = SimpleMockProvider("p2", {"collision": {}})
    c = ProviderRouter(providers=[p1, p2])

    assert "p1/collision" in c.manifest
    assert "p2/collision" in c.manifest


def test_router_run_delegation():
    """Verify run calls the orchestrator with correct types."""
    p1 = SimpleMockProvider("p1", {"part_a": {Action.PART: {}}})
    c = ProviderRouter(providers=[p1])
    c.orchestrator = MagicMock()

    targets = TargetList(c, ["p1/part_a"], action=Action.PART)
    c.run(targets)

    c.orchestrator.execute.assert_called_once_with(("p1/part_a",), Action.PART, (), (Mode.DEFAULT,))


def test_router_default_configs():
    """Verify router aggregates default configs from all providers."""
    p1 = SimpleMockProvider("p1", {}, default_config={"cfg": 1})
    p2 = SimpleMockProvider("p2", {}, default_config={"cfg": 2})
    c = ProviderRouter(providers=[p1, p2])

    assert c.default_configs == {"p1": {"cfg": 1}, "p2": {"cfg": 2}}


def test_router_get_color():
    """Verify router delegates get_color to the correct provider."""
    p1 = SimpleMockProvider("p1", {"part_a": {}})
    p1.get_color.return_value = (1.0, 0.0, 0.0, 1.0)  # type: ignore
    p1.get_color.return_value = (1.0, 0.0, 0.0, 1.0)  # type: ignore
    c = ProviderRouter(providers=[p1])

    color = c.get_color("p1/part_a", Subassembly.LEFT)
    assert color == (1.0, 0.0, 0.0, 1.0)
    p1.get_color.assert_called_once_with("part_a", Subassembly.LEFT)  # type: ignore

    with pytest.raises(ValueError, match="Target 'missing' not found"):
        c.get_color("missing")


def test_router_load_configs():
    """Verify loading and routing of environment variables."""
    p_settings = MockSettings()
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)
    c = ProviderRouter(providers=[p1])

    config = AppConfig()
    config.model_extra["P1__VAL"] = "env_val"  # type: ignore
    config.model_extra["P1__NUM"] = 10  # type: ignore
    config.model_extra["P1__ITEMS"] = "[1, 2, 3]"  # type: ignore

    c.load_configs(config)

    assert p1.settings.val == "env_val"
    assert p1.settings.num == 10
    assert p1.settings.items == [1, 2, 3]
    assert getattr(config, "p1") == p1.settings


def test_router_load_configs_json_error():
    """Verify ValueError on malformed JSON in environment variables."""
    p_settings = MockSettings()
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)
    c = ProviderRouter(providers=[p1])

    config = AppConfig()
    config.model_extra["P1__ITEMS"] = "[1, 2"  # type: ignore

    with pytest.raises(ValueError, match="Failed to parse JSON configuration"):
        c.load_configs(config)


def test_router_save_configs():
    """Verify preparation of AppConfig for environment dumping."""
    p_settings = MockSettings(val="custom")
    p1 = SimpleMockProvider("p1", {}, default_config=p_settings)
    c = ProviderRouter(providers=[p1])

    config = AppConfig()
    c.save_configs(config)

    assert getattr(config, "p1") == p_settings
    assert "P1" in config._env_flattened_keys
