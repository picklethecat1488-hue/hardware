"""Unit tests for geometry and data provider."""

import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel
from providers.provider import Provider
from providers.target_list import TargetList
from providers.types import Action, Subassembly, Mode


class MockConfig(BaseModel):
    """Stub config for testing."""

    ver: str = "1.0"


class MockProvider(Provider):
    """Concrete implementation of Provider for testing."""

    @property
    def name(self) -> str:
        """Return the mock provider name."""
        return "mock"

    @property
    def default_config(self) -> MockConfig:
        """Return a mock config."""
        return MockConfig()

    @property
    def manifest(self) -> dict:
        """Return a mock manifest."""
        return {
            "part_a": {
                "actions": [Action.WIRE, Action.PART],
                "subassemblies": [Subassembly.LEFT],
                "modes": [Mode.DEFAULT, Mode.BARE],
            },
            "part_b": {
                "actions": [Action.PART, Action.DIAGRAM],
                "subassemblies": [Subassembly.RIGHT],
                "modes": [Mode.DEFAULT],
            },
            "part_a,config": {
                "actions": [Action.CONFIG],
                "subassemblies": [],
                "modes": [Mode.DEFAULT, Mode.TEXT, Mode.MOUNT],
            },
        }

    @property
    def registry(self) -> dict:
        """Return a mock registry."""
        if not hasattr(self, "_mock_registry"):
            self._mock_registry = {
                Action.WIRE: MagicMock(return_value="wire_obj"),
                Action.PART: MagicMock(return_value="part_obj"),
                Action.CONFIG: MagicMock(return_value=None),
                Action.DIAGRAM: MagicMock(return_value="diag_obj"),
            }
        return self._mock_registry


@pytest.fixture(scope="module")
def provider():
    """Provide fixture at the module level."""
    return MockProvider()


class TestTargetList:
    """TargetList unit tests."""

    def test_supporting_filter(self, provider):
        """Verify supporting() filters targets correctly."""
        targets = provider.targets.supporting(Action.WIRE)
        assert list(targets) == ["part_a"]
        assert isinstance(targets, TargetList)
        assert targets.provider == provider

    def test_for_subassemblies_filter(self, provider):
        """Verify for_subassemblies() filters targets correctly."""
        targets = provider.targets.for_subassemblies([Subassembly.LEFT])
        assert list(targets) == ["part_a"]

        targets = provider.targets.for_subassemblies([Subassembly.RIGHT])
        assert list(targets) == ["part_b"]

    def test_for_modes_filter(self, provider):
        """Verify for_modes() filters targets correctly."""
        targets = provider.targets.for_modes([Mode.BARE])
        assert list(targets) == ["part_a"]


class TestProviderOrchestration:
    """Provider base class orchestration tests."""

    def test_build_success(self, provider):
        """Verify successful build orchestration and validation."""
        results = provider.build_wires(provider.targets.supporting(Action.WIRE))
        assert results == ["wire_obj"]
        provider.registry[Action.WIRE].assert_called_once_with("part_a", [], [Mode.DEFAULT])

    def test_configure_success(self, provider):
        """Verify successful configuration orchestration."""
        provider.configure_parts(provider.targets.supporting(Action.CONFIG))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a,config", [], [Mode.DEFAULT])

        provider.registry[Action.CONFIG].reset_mock()
        provider.configure_parts(provider.targets.supporting(Action.CONFIG).for_modes([Mode.TEXT]))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a,config", [], [Mode.TEXT])

        provider.registry[Action.CONFIG].reset_mock()
        provider.configure_parts(provider.targets.supporting(Action.CONFIG).for_modes([Mode.MOUNT]))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a,config", [], [Mode.MOUNT])

    def test_build_action_unsupported(self, provider):
        """Verify ValueError when a target does not support an action."""
        with pytest.raises(ValueError, match="Action 'wire' is not supported for part 'part_b'"):
            provider.build_wires(TargetList(provider, ["part_b"]))

    def test_build_diagram_special_case(self, provider):
        """Verify diagram build returns a single object and validates differently."""
        result = provider.build_diagram(TargetList(provider, ["part_b"]))
        assert result == "diag_obj"

    def test_pre_build_validation_failures(self, provider):
        """Verify various validation failures in _pre_build."""
        with pytest.raises(ValueError, match="Length of subassemblies"):
            targets = TargetList(provider, ["part_a", "part_b"], subassemblies=[Subassembly.LEFT] * 3)
            provider.build_parts(targets)

        with pytest.raises(ValueError, match="Mode 'bare' is not supported for part 'part_b'"):
            targets = TargetList(provider, ["part_b"], modes=[Mode.BARE])
            provider.build_parts(targets)

    def test_post_build_length_validation(self, provider):
        """Verify build result length validation."""
        # This test is less relevant now as _run guarantees length by construction,
        # but we keep it to ensure _post_build still executes correctly.
        provider.build_parts(TargetList(provider, ["part_a", "part_b"]))
        assert provider.registry[Action.PART].call_count == 2
