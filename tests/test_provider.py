"""Unit tests for geometry and data provider."""

import pytest
import yaml
from unittest.mock import MagicMock
from pydantic import BaseModel
from providers.provider import Provider
from providers.target_list import TargetList
from providers.utils import load_manifest
from providers.types import Action, Subassembly, Mode, MODES, SUBASSEMBLIES, COLOR


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
                Action.WIRE: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: [Subassembly.LEFT]},
                Action.PART: {
                    MODES: [Mode.DEFAULT, Mode.BARE],
                    SUBASSEMBLIES: [Subassembly.LEFT],
                },
                Action.SKETCH: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: [Subassembly.LEFT]},
                Action.CONFIG: {
                    MODES: [Mode.DEFAULT, Mode.TEXT, Mode.MOUNT],
                    SUBASSEMBLIES: [Subassembly.LEFT],
                },
                COLOR: (0.8, 0.8, 0.8, 1.0),
            },
            "part_b": {
                Action.PART: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: [Subassembly.RIGHT]},
                Action.DIAGRAM: {
                    MODES: [Mode.DEFAULT],
                    SUBASSEMBLIES: [Subassembly.RIGHT],
                },
                COLOR: {Subassembly.RIGHT: (0.9, 0.9, 0.9, 1.0)},
            },
        }

    @property
    def registry(self) -> dict:
        """Return a mock registry."""
        if not hasattr(self, "_mock_registry"):
            self._mock_registry = {
                Action.WIRE: MagicMock(return_value="wire_obj"),
                Action.PART: MagicMock(return_value="part_obj"),
                Action.SKETCH: MagicMock(return_value="sketch_obj"),
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


class TestProviderMetadata:
    """Tests for provider metadata and color resolution."""

    def test_get_color_single(self, provider):
        """Verify get_color returns a single defined color."""
        assert provider.get_color("part_a") == (0.8, 0.8, 0.8, 1.0)

    def test_get_color_dict_specific(self, provider):
        """Verify get_color returns the specific subassembly color from a dict."""
        assert provider.get_color("part_b", Subassembly.RIGHT) == (0.9, 0.9, 0.9, 1.0)

    def test_get_color_dict_fallback_first(self, provider):
        """Verify get_color returns the first dict color when no subassembly is specified."""
        assert provider.get_color("part_b") == (0.9, 0.9, 0.9, 1.0)

    def test_get_color_fallback_config(self, provider):
        """Verify get_color falls back to config color when missing."""
        assert provider.get_color("part_b", Subassembly.LEFT) == provider.config.color

    def test_provider_default_manifest_path(self, monkeypatch):
        """Verify that Provider.manifest defaults to loading a YAML file by provider name."""
        import providers.provider

        mock_load = MagicMock(return_value={"test": "data"})
        monkeypatch.setattr(providers.provider, "load_manifest", mock_load)

        class MinimalProvider(Provider):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def default_config(self):
                return None

            @property
            def registry(self):
                return {}

        p = MinimalProvider()
        assert p.manifest == {"test": "data"}
        mock_load.assert_called_once_with("minimal_manifest.yaml")

    def test_load_manifest(self, tmp_path, provider):
        """Verify that load_manifest correctly parses Enum keys and values."""
        manifest_path = tmp_path / "manifest.yml"
        yaml_content = {
            "part_c": {"part": {"modes": ["default"], "subassemblies": ["left"]}, "color": [1.0, 1.0, 1.0, 1.0]}
        }
        manifest_path.write_text(yaml.dump(yaml_content))

        loaded = load_manifest(str(manifest_path))
        assert "part_c" in loaded
        assert Action.PART in loaded["part_c"]
        assert loaded["part_c"][Action.PART][MODES] == [Mode.DEFAULT]
        assert loaded["part_c"][COLOR] == (1.0, 1.0, 1.0, 1.0)


class TestProviderOrchestration:
    """Provider base class orchestration tests."""

    def test_build_success(self, provider):
        """Verify successful build orchestration and validation."""
        results = provider.run(provider.targets.supporting(Action.WIRE))
        assert results == [("part_a", "wire_obj")]
        provider.registry[Action.WIRE].assert_called_once_with("part_a", [], [Mode.DEFAULT])

    def test_build_sketch_success(self, provider):
        """Verify successful sketch build orchestration."""
        results = provider.run(provider.targets.supporting(Action.SKETCH))
        assert results == [("part_a", "sketch_obj")]
        provider.registry[Action.SKETCH].assert_called_once_with("part_a", [], [Mode.DEFAULT])

    def test_configure_success(self, provider):
        """Verify successful configuration orchestration."""
        provider.run(provider.targets.supporting(Action.CONFIG))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a", [], [Mode.DEFAULT])

        provider.registry[Action.CONFIG].reset_mock()
        provider.run(provider.targets.supporting(Action.CONFIG).for_modes([Mode.TEXT]))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a", [], [Mode.TEXT])

        provider.registry[Action.CONFIG].reset_mock()
        provider.run(provider.targets.supporting(Action.CONFIG).for_modes([Mode.MOUNT]))
        provider.registry[Action.CONFIG].assert_called_once_with("part_a", [], [Mode.MOUNT])

    def test_build_action_unsupported(self, provider):
        """Verify ValueError when a target does not support an action."""
        with pytest.raises(ValueError, match="Action 'wire' is not supported for part 'part_b'"):
            provider.run(TargetList(provider, ["part_b"], action=Action.WIRE))

    def test_build_diagram_special_case(self, provider):
        """Verify diagram build returns a single object and validates differently."""
        result = provider.run(TargetList(provider, ["part_b"], action=Action.DIAGRAM))
        assert result == "diag_obj"

    def test_pre_build_validation_failures(self, provider):
        """Verify various validation failures in _pre_build."""
        with pytest.raises(ValueError, match="Length of subassemblies"):
            targets = TargetList(
                provider,
                ["part_a", "part_b"],
                subassemblies=[Subassembly.LEFT] * 3,
                action=Action.PART,
            )
            provider.run(targets)

        with pytest.raises(ValueError, match="Mode 'bare' is not supported.*part_b"):
            targets = TargetList(provider, ["part_b"], modes=[Mode.BARE], action=Action.PART)
            provider.run(targets)

    def test_post_build_length_validation(self, provider):
        """Verify build result length validation."""
        # This test is less relevant now as _run guarantees length by construction,
        # but we keep it to ensure _post_build still executes correctly.
        results = provider.run(TargetList(provider, ["part_a", "part_b"], action=Action.PART))
        assert results == [("part_a", "part_obj"), ("part_b", "part_obj")]
        assert provider.registry[Action.PART].call_count == 2
