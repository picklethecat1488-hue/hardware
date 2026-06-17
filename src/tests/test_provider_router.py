"""Unit tests for the ProviderRouter class."""

import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel, Field
from model import AppConfig
from provider.provider_router import ProviderRouter
from provider.provider_manager import ProviderManager
from provider.provider import Provider
from provider.types import Section, Mode, MODES, SUBASSEMBLIES
from provider.target_list import TargetList


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
    def build(self):
        """Return an empty build registry."""
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
    p1 = SimpleMockProvider("p1", {"a": {Section.PART: {}}})
    p2 = SimpleMockProvider("p2", {"b": {Section.PART: {}}})
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
    p1 = SimpleMockProvider("p1", {"part_a": {Section.PART: {}}})
    c = ProviderRouter(providers=[p1])
    c.orchestrator = MagicMock()

    targets = TargetList(c, ["p1/part_a"], action=Section.PART)
    c.run(targets)

    c.orchestrator.execute.assert_called_once_with(("p1/part_a",), Section.PART, (), (Mode.DEFAULT,))


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

    color = c.get_color("p1/part_a", "left")
    assert color == (1.0, 0.0, 0.0, 1.0)
    p1.get_color.assert_called_once_with("part_a", "left")  # type: ignore

    with pytest.raises(ValueError, match="Target 'missing' not found"):
        c.get_color("missing")
